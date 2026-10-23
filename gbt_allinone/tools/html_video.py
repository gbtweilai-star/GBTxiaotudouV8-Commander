# -*- coding: utf-8 -*-
"""GBT小土豆V8 · HTML → MP4（**我们自己的**最小管线）

Owner 2026-09-22 选 A：参照 html-video（Open Design 团队 · Apache-2.0）的**结构**，
**但用我们自己的代码重写** —— 不搬它的代码。
理由（写在这里防后来人图省事直接抄）：
  ① 直接抄 ⇒ 产物不是我们的，违反 Owner 铁律「只能是我们自己的资料，不能混入其他资料」
  ② Apache-2.0 要求保留对方归属、声明改动；我们自己的「署名不可篡改」对别人同样适用
  ③ 重写 ⇒ 产物、署名、维护责任全是我们的

═══ 底座全是**已有的我们自己的件**，不引入任何新依赖 ═══
  · 抓帧：`gbt_allinone/native_browser.py` —— 我们自己的 CDP 控制器，
          自带「最小的 RFC6455 客户端」（零第三方 WebSocket 依赖）
  · 编码：系统 ffmpeg（实测 8.1.2 full build 在 PATH）

═══ 三步 ═══
  1 起/接 Chrome（native_browser.ensure）→ 打开 HTML
  2 逐帧：注入**确定性时钟**把动画钉在 t 秒 → 截图成一帧 PNG
  3 ffmpeg 把帧序列编成 MP4 → ffprobe 回读验证

═══ 反假执行 ═══
  · 帧数不够就如实报缺口，**不把"少了几帧"说成"渲染成功"**
  · ffmpeg 非零退出必须原样带出来，不吞
  · 编码完**必须 ffprobe 回读**（分辨率/时长/体积），用回读值说话，不用"应该是"
"""
from __future__ import annotations

import contextlib
import functools
import http.server
import json
import shutil
import socketserver
import subprocess
import sys
import threading
import time
from pathlib import Path

from .. import native_browser as nb          # 仅用于 doctor() 里找浏览器路径（只读）


def _browser(action: str, **params) -> dict:
    """**走门**调用原生浏览器（2026-09-22 还债）。

    原来这里直接 `nb.ensure/screenshot/execute_script` —— 那是**绕过授权门**：
    `browser_control` 在 policy 里是需要作用域的门后动作，直调让门形同虚设。
    （这正是我自己在根因报告里点过的同型问题，标了两次，这一步把它还了。）
    只保留 `find_browser()` 直调 —— 它**只读文件系统找 exe 路径**，不做任何浏览器动作。
    """
    import gbt_allinone as _g
    r = _g.run_task("browser", {"action": action, **params})
    b = r.get("gbt_result") or r
    if isinstance(b, dict) and "result" in b:
        inner = b.get("result")
        if isinstance(inner, dict):
            return inner
    return b if isinstance(b, dict) else {"ok": False, "error": str(b)[:200]}

_IMPL_VERSION = "1.0"


@contextlib.contextmanager
def _serve(directory: Path):
    """给一张本地 HTML 起个**临时** http 服务。

    为什么必须这样：`native_browser` 的 URL 守卫明确拒绝 `file://`
    （「原生浏览器只接受 http/https URL」）—— 实测撞过。
    **不该为图省事去放宽那条守卫**，起个临时服务才是正路。
    只绑 127.0.0.1，随机端口，用完就关。
    """
    handler = functools.partial(http.server.SimpleHTTPRequestHandler,
                                directory=str(directory))

    class _Srv(socketserver.ThreadingTCPServer):
        allow_reuse_address = True
        daemon_threads = True

        def log_message(self, *a):                                  # noqa: A003
            pass                                                    # 静音访问日志

    httpd = _Srv(("127.0.0.1", 0), handler)
    port = httpd.server_address[1]
    th = threading.Thread(target=httpd.serve_forever, daemon=True)
    th.start()
    try:
        yield port
    finally:
        with contextlib.suppress(Exception):
            httpd.shutdown()
        with contextlib.suppress(Exception):
            httpd.server_close()


def _find(exe: str) -> str:
    """找可执行文件。找不到就返回空串（调用方如实报缺，不猜路径）。"""
    return shutil.which(exe) or ""


def doctor() -> dict:
    """工具链就绪度：**实测**，缺什么报什么。"""
    ff, fp = _find("ffmpeg"), _find("ffprobe")
    try:
        browser = nb.find_browser()
    except Exception as e:                                          # noqa: BLE001
        browser = f"(探测失败: {type(e).__name__})"
    ffver = ""
    if ff:
        try:
            r = subprocess.run([ff, "-version"], capture_output=True, text=True,
                               timeout=15, encoding="utf-8", errors="replace")
            ffver = (r.stdout or "").splitlines()[0][:60] if r.stdout else ""
        except Exception:                                           # noqa: BLE001
            ffver = "(版本探测失败)"
    missing = [n for n, v in (("ffmpeg", ff), ("ffprobe", fp), ("chrome", browser)) if not v]
    return {"ok": not missing, "ffmpeg": ff, "ffmpeg_version": ffver,
            "ffprobe": fp, "browser": browser, "missing": missing,
            "note": "工具链齐全" if not missing else f"缺: {missing}"}


# ═══════════════ 确定性时钟：把动画钉在某一秒 ═══════════════
# 为什么要这个：canvas / rAF 驱动的动画不认 CSS 的 getAnimations()，
# 只有把「时间」本身接管过来，才能一帧一帧地定格。
# 页面若自带 `window.__gbtSetTime(t)` 就优先用它（最准）；否则用下面这套接管。
_CLOCK_SHIM = r"""
(function () {
  if (window.__gbtClockInstalled) { return 'already'; }
  window.__gbtClockInstalled = true;
  var T0 = (window.__gbtT0 !== undefined) ? window.__gbtT0 : 0;   // 起始时刻(ms)
  var vnow = T0;
  var realRaf = window.requestAnimationFrame;
  var queue = [];
  window.__gbtNow = function () { return vnow; };
  window.__gbtAdvance = function (ms) {          // 推进虚拟时间并跑一帧回调
    vnow += ms;
    var q = queue; queue = [];
    for (var i = 0; i < q.length; i++) {
      try { q[i](vnow); } catch (e) { /* 单帧回调错不该拖垮整轮 */ }
    }
    return vnow;
  };
  // rAF 改为登记到队列，由 __gbtAdvance 驱动 —— 时间由我们说了算
  window.requestAnimationFrame = function (cb) { queue.push(cb); return queue.length; };
  window.cancelAnimationFrame = function () { /* 虚拟时钟下无需真取消 */ };
  // 时间源也接管，免得动画自己按真实时间跑飞
  try {
    var RP = performance.now.bind(performance);
    performance.now = function () { return vnow; };
    window.__gbtRealPerfNow = RP;
  } catch (e) { /* 改不了就退化为只接管 rAF */ }
  try {
    var RD = Date.now;
    Date.now = function () { return T0 + vnow; };
    window.__gbtRealDateNow = RD;
  } catch (e) { /* 同上 */ }
  return 'installed';
})();
"""


def _set_time(js_time: float) -> str:
    """生成"把页面钉到第 t 秒"的 JS。优先用页面自己的钩子。"""
    ms = max(0.0, float(js_time) * 1000.0)
    return (
        "(function(){var t=%f;"
        "if(typeof window.__gbtSetTime==='function'){try{window.__gbtSetTime(t/1000);"
        "return 'hook';}catch(e){}}"
        "if(typeof window.__gbtAdvance==='function'){"
        "var target=t, now=(typeof window.__gbtNow==='function')?window.__gbtNow():0;"
        "while(now<target){now=window.__gbtAdvance(Math.min(16.7,target-now));}"
        "return 'advance';}"
        "var as=document.getAnimations?document.getAnimations():[];"
        "for(var i=0;i<as.length;i++){try{as[i].currentTime=t;}catch(e){}}"
        "return 'getAnimations';})()" % ms
    )


def render(html: str, out: str, *, fps: int = 12, duration: float = 2.0,
           viewport: tuple = (640, 360), tab_id: str = "", port=None,
           keep_frames: bool = False, settle: float = 0.0,
           progress=None) -> dict:
    """把一张 HTML 渲成 MP4。

    参数
      html      本地 HTML 路径（file:// 会自动处理）
      out       输出 mp4 路径
      fps       帧率；帧数 = round(fps*duration)
      duration  时长（秒）
      viewport  (宽, 高)
      settle    每帧截图前的额外等待秒数（默认 0，虚拟时钟下通常不需要）
    """
    t0 = time.time()
    doc = doctor()
    if not doc["ok"]:
        return {"ok": False, "stage": "doctor", "error": doc["note"], **doc}

    html_path = Path(html).resolve()
    if not html_path.is_file():
        return {"ok": False, "stage": "input", "error": f"HTML 不存在: {html_path}"}
    out_path = Path(out).resolve()
    out_path.parent.mkdir(parents=True, exist_ok=True)

    w, h = int(viewport[0]), int(viewport[1])
    fps = max(1, int(fps))
    n_frames = max(1, int(round(fps * float(duration))))

    frames_dir = out_path.parent / (out_path.stem + "_frames")
    frames_dir.mkdir(parents=True, exist_ok=True)

    url = html_path.as_uri()
    with _serve(html_path.parent) as _port:
        url = f"http://127.0.0.1:{_port}/{html_path.name}"
        try:
            nav = _browser("ensure", url=url, allow_private=True)
        except Exception as e:                                      # noqa: BLE001
            return {"ok": False, "stage": "browser",
                    "error": f"{type(e).__name__}: {e}", "url": url}
        return _capture_and_encode(
            nav=nav, out_path=out_path, frames_dir=frames_dir, doc=doc,
            fps=fps, n_frames=n_frames, duration=duration, tab_id=tab_id,
            port=port, settle=settle, keep_frames=keep_frames,
            progress=progress, t0=t0, viewport=(w, h))


def _capture_and_encode(*, nav, out_path, frames_dir, doc, fps, n_frames, duration,
                        tab_id, port, settle, keep_frames, progress, t0,
                        viewport) -> dict:
    w, h = int(viewport[0]), int(viewport[1])

    # 装确定性时钟（装不上不算失败：退化为 CSS getAnimations 路径）
    shim = ""
    try:
        r = _browser("execute_script", js=_CLOCK_SHIM, tab_id=tab_id or None)
        shim = "installed" if r.get("ok") else f"failed: {str(r.get('error') or r)[:120]}"
    except Exception as e:                                          # noqa: BLE001
        shim = f"failed: {type(e).__name__}"

    # 视口必须**真的**设上去。
    # 2026-09-22 实测教训：原来 `viewport` 参数只是收了没用，截图跟着 Chrome 窗口走
    # （抓出 1223×660）—— 而 **1223 是奇数**，H.264 的 yuv420p 要求宽高皆偶数，
    # libx264 直接打不开编码器（ffmpeg 报 -22 Invalid argument + Could not open encoder）。
    # 两个修：① 用 CDP 真设视口；② 编码时再兜一道偶数化。
    # 视口：CDP `Emulation.setDeviceMetricsOverride` **不是门后动作**，
    # 为了不绕过门，这里不再直调 CDP；输出尺寸由下方 ffmpeg 的 `-vf scale` 定死。
    # 代价如实说：页面按浏览器窗口尺寸排版，再缩放到目标尺寸（不是按目标尺寸排版）。
    viewport_applied = f"scale-to {w}x{h}（经 ffmpeg；未用 CDP 改视口）"

    shots, failures = [], []
    for i in range(n_frames):
        tsec = i / float(fps)
        mode = ""
        try:
            r = _browser("execute_script", js=_set_time(tsec), tab_id=tab_id or None)
            mode = str((r.get("result") if isinstance(r, dict) else "") or "")[:40]
        except Exception as e:                                      # noqa: BLE001
            failures.append({"frame": i, "why": f"set_time: {type(e).__name__}"})
        if settle:
            time.sleep(settle)
        fp = frames_dir / f"frame{i:05d}.png"
        try:
            s = _browser("screenshot", tab_id=tab_id or None, out=str(fp), fmt="png")
            if s.get("ok", True) and fp.is_file() and fp.stat().st_size > 0:
                shots.append(fp)
            else:
                failures.append({"frame": i, "why": f"截图无效: {str(s)[:100]}"})
        except Exception as e:                                      # noqa: BLE001
            failures.append({"frame": i, "why": f"shot: {type(e).__name__}: {str(e)[:80]}"})
        if progress:
            try:
                progress(i + 1, n_frames)
            except Exception:                                       # noqa: BLE001
                pass

    if not shots:
        return {"ok": False, "stage": "capture", "frames_wanted": n_frames,
                "frames_got": 0, "failures": failures[:5],
                "error": "一帧都没抓到 —— 不编成功"}

    # ffmpeg 编码（帧序列 → MP4）
    # 输出尺寸**定死**：既保证偶数，又不受系统 DPR 影响。
    # 实测两坑：① 1223 是奇数 ⇒ yuv420p 打不开 libx264（-22）；
    #           ② 本机 Windows 显示缩放 125% ⇒ 请求 640×360 抓到 800×450（640×1.25）。
    # 用 scale 一步定死，两头都堵上。
    ow, oh = w - (w % 2), h - (h % 2)
    cmd = [doc["ffmpeg"], "-y", "-hide_banner", "-loglevel", "error",
           "-framerate", str(fps), "-i", str(frames_dir / "frame%05d.png"),
           "-vf", f"scale={ow}:{oh}:flags=lanczos",
           "-c:v", "libx264", "-pix_fmt", "yuv420p", "-movflags", "+faststart",
           str(out_path)]
    try:
        cp = subprocess.run(cmd, capture_output=True, text=True, timeout=600,
                            encoding="utf-8", errors="replace")
    except Exception as e:                                          # noqa: BLE001
        return {"ok": False, "stage": "encode", "error": f"{type(e).__name__}: {e}",
                "frames_got": len(shots)}

    if cp.returncode != 0 or not out_path.is_file():
        return {"ok": False, "stage": "encode", "exit_code": cp.returncode,
                "stderr": (cp.stderr or "")[-500:], "frames_got": len(shots),
                "error": "ffmpeg 非零退出 —— 原样带出来，不吞"}

    # 回读验证：用 ffprobe 的真值说话
    info = probe(str(out_path))
    if not keep_frames:
        for f in shots:
            try:
                f.unlink()
            except OSError:
                pass
        try:
            frames_dir.rmdir()
        except OSError:
            pass

    return {
        "ok": True,
        "out": str(out_path),
        "frames_wanted": n_frames,
        "frames_got": len(shots),
        "frames_short": n_frames - len(shots),
        "fps": fps, "duration_target": float(duration),
        "viewport": [w, h],
        "clock_shim": shim,
        "viewport_requested": [w, h],
        "viewport_applied": viewport_applied,
        "bytes": out_path.stat().st_size,
        "probe": info,
        "capture_failures": failures[:5],
        "elapsed_s": round(time.time() - t0, 1),
        "note": ("帧数齐" if len(shots) == n_frames
                 else f"**少了 {n_frames - len(shots)} 帧** —— 如实报，不粉饰"),
    }


def probe(mp4: str) -> dict:
    """ffprobe 回读：分辨率 / 时长 / 编码 / 体积。用真值说话。"""
    fp = _find("ffprobe")
    p = Path(mp4)
    if not fp or not p.is_file():
        return {"ok": False, "error": "ffprobe 缺失或文件不存在"}
    cmd = [fp, "-v", "error", "-select_streams", "v:0",
           "-show_entries", "stream=width,height,codec_name,nb_frames,r_frame_rate,duration",
           "-show_entries", "format=duration,size,format_name",
           "-of", "json", str(p)]
    try:
        cp = subprocess.run(cmd, capture_output=True, text=True, timeout=60,
                            encoding="utf-8", errors="replace")
        if cp.returncode != 0:
            return {"ok": False, "error": (cp.stderr or "")[-300:]}
        j = json.loads(cp.stdout or "{}")
        st = (j.get("streams") or [{}])[0]
        fm = j.get("format") or {}
        return {"ok": True,
                "width": st.get("width"), "height": st.get("height"),
                "codec": st.get("codec_name"), "nb_frames": st.get("nb_frames"),
                "r_frame_rate": st.get("r_frame_rate"),
                "duration_s": float(fm.get("duration") or 0),
                "size_bytes": int(fm.get("size") or p.stat().st_size),
                "container": fm.get("format_name")}
    except Exception as e:                                          # noqa: BLE001
        return {"ok": False, "error": f"{type(e).__name__}: {e}"}


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "doctor":
        print(json.dumps(doctor(), ensure_ascii=False, indent=2))
        raise SystemExit(0)
    if len(sys.argv) > 2:
        r = render(sys.argv[1], sys.argv[2],
                   fps=int(sys.argv[3]) if len(sys.argv) > 3 else 12,
                   duration=float(sys.argv[4]) if len(sys.argv) > 4 else 2.0,
                   progress=lambda i, n: print(f"  帧 {i}/{n}", flush=True))
        print(json.dumps(r, ensure_ascii=False, indent=2))
        raise SystemExit(0 if r.get("ok") else 1)
    print("用法: html_video.py doctor | html_video.py <in.html> <out.mp4> [fps] [秒]")
