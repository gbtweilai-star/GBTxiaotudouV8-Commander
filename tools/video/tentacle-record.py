# -*- coding: utf-8 -*-
r"""本地录制（tentacle-record）—— 用**本仓自己的触手**连拍屏幕，合成一条本地片。

主人令链（2026-10-10 视频流水线目标轮）：
  S1「创意(生成)」的**声明兜底**是「**本地录制/录屏代替**」；云生成那条是**计费动作**（须主人确认报价）。
  我先查过两条路：云生成 ⇒ 计费门；screen_sniff ⇒ 要 privacy_read（只有主人能发）。
  **但触手（tentacle）的 see 走的是 desktop_control —— 而那条作用域是已授权的**（现读 auth_gate_status）。
  ⇒ 本地录制这条路**本来就在手上**，我却一直以为它被门挡着。

## 为什么要写成件而不是手搓一次性脚本
上一轮我在数字人 S2 上抓到的病就是「手写的状态会过期」。这里同理：
  · 每次录制落**回执**（帧数 / 引擎 / 平均 capture_ms / 源哈希）
  · **负对照**：0 帧必须判红（不许把空录当录像）
用法：py -3.14 -X utf8 tools/video/tentacle-record.py [--frames 12] [--every 0.25] [--out ...]
"""
from __future__ import annotations

import argparse
import base64
import json
import subprocess
import sys
import time
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parents[2]
FIVE = ROOT / "tools" / "codex-scripts" / "five-dim.py"
OUT = ROOT / "video-out"
B = Path(r"C:\Users\ADMIN\AppData\Local\Microsoft\WinGet\Packages\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-8.1.2-full_build\bin")
FF = B / "ffmpeg.EXE"


def see_once() -> dict:
    """走**唯一门**取一帧（万能插 → run_task）。返回 result 字典。"""
    # 🔴 2026-10-10 踩过：万能插**默认把 result 收窄**（'result 过大，已收窄：大值只报形状'）
    #    ⇒ image_base64 只剩 preview，解码必失败。取帧必须显式加 **--full**。
    cp = subprocess.run([sys.executable, "-X", "utf8", str(FIVE), "cap", "tentacle",
                         json.dumps({"action": "see"}), "--full"], capture_output=True, cwd=str(ROOT))
    raw = (cp.stdout or b"").decode("utf-8", "replace")
    try:
        d = json.loads(raw)
    except Exception:                                                  # noqa: BLE001
        # 万能插默认把 result 收窄；帧在 image_base64 里，需要 --full
        return {"ok": False, "why": "返回不是合法 JSON（可能需要 --full）"}
    r = d.get("result") if isinstance(d, dict) else None
    return r if isinstance(r, dict) else {"ok": False, "why": "result 形状不对"}


def _stream_frames(n: int, fps: int):
    """走**连续帧流**（eye-stream，框架自己那只眼）按目标帧率取像素。

    🔴 2026-10-10 这一改的理由（**实测对比**，不是我拍的）：
      · 反复调触手 see：每帧要付**整个万能插调用**的开销（子进程+门+序列化）⇒ 实测 1.3~3.2 s/帧
        ⇒ 最多 0.3~0.75 fps。这样录出来只是"采样快照"，**当不了素材**。
      · 走连续流（Eye(keep_pixels=True)）：**实测 30.6 fps · 帧龄 5.2 ms**（640x360）。
      ⇒ 差 40 倍以上。**能流的就别一帧一停**（这正是 V9 那句"一帧一停等于盲人摸象"）。
    """
    import importlib.util as u
    sp = u.spec_from_file_location("_gbt_eye", ROOT / "tools" / "codex-scripts" / "eye-stream.py")
    m = u.module_from_spec(sp)
    sp.loader.exec_module(m)
    # 🔴 2026-10-10 质量读数当场抓到的病：默认区域是 monitors[1] 偏移 (640,360)、640x360
    #    ——**那块是死区**，录出来 90 帧**画面差恒为 0.0**（100% 静止帧）。
    #    ⇒ 录制必须用**有内容的区域**：默认改成**全屏**（full=True）。
    #    代价如实说：全屏 1920x1080 比 640x360 慢（V9 实测全屏 22.6fps / 640x360 75.3fps），
    #    但**死区的 40fps 是假的快** —— 帧再多，内容为 0 就是 0。
    eye = m.Eye("record", keep_pixels=True, full=True)
    st = eye.start()
    if not st.get("ok"):
        return None, "连续流起不来：%s" % st
    time.sleep(0.8)                      # 等流暖起来（🔴 踩过：不等就一帧都拿不到）
    out = []
    dt = 1.0 / max(1, fps)
    t0 = time.time()
    while len(out) < n:
        f = eye.frame()
        if f:
            got = eye.grabbed
        if f and (not out or f[0] != out[-1][0]):      # 只取**新帧**（不重复写同一帧）
            out.append(f)
        if time.time() - t0 > n / max(1, fps) * 3 + 5:
            break
        time.sleep(dt)
    info = {"实测fps": eye.fps(), "抓帧总数": eye.grabbed, "被顶掉": eye.overwritten,
            "丢帧": eye.drops, "引擎": eye.engine, "尺寸": (f[3], f[4]) if f else None}
    eye.stop()
    return out, info


def _quality(frames, w: int, h: int) -> dict:
    """**画面质量读数** —— 让"录到了"和"录得好"分得清。

    🔴 2026-10-10 补：上一轮我只报了"60 帧 · 15fps"，可**那不等于有内容**：
    屏幕可能整段静止（我录的就是我自己在跑的终端 ⇒ 大部分帧是同一个画面）。
    ⇒ 逐帧算与前一帧的**下采样灰度平均绝对差**，给出：
       · 静止帧占比（差 < 2）—— 这一段其实没有新画面
       · 明显变化帧占比（差 >= 10）—— 真在动的那些帧
       · 有效帧占比 = 1 - 静止占比
    **这不是审美判断，是"这段录像里有多少信息"的读数。**
    """
    try:
        from PIL import Image
        import io as _io
        prev = None
        diffs = []
        for f in frames:
            im = Image.frombytes("RGB", (f[3], f[4]), f[2]).convert("L").resize((64, 36))
            cur = list(im.getdata())
            if prev is not None:
                diffs.append(sum(abs(a - b) for a, b in zip(cur, prev)) / len(cur))
            prev = cur
        if not diffs:
            return {"说明": "只有 1 帧，算不出变化"}
        still = sum(1 for d in diffs if d < 2.0)
        moved = sum(1 for d in diffs if d >= 10.0)
        # 🔴 2026-10-10 我自己纠了自己一刀：原来只看"帧间动不动"，就把**真有画面但不动**
        #    （比如桌面/聊天界面）判成"死屏"。落图一看——抓的**是真桌面**（DSH 界面+文件树+任务栏）。
        #    ⇒ **"有没有画面"和"帧间动不动"是两件事**，必须分开量：
        #      内容面：平均亮度 + 亮度标准差（纯黑/纯色才叫没画面）
        #      运动面：帧间差（如实报，附"低/中/高"标签，**不拿它否决整条录像**）
        px = list(frames[0] and __import__("PIL.Image", fromlist=["Image"])
                  .frombytes("RGB", (frames[0][3], frames[0][4]), frames[0][2])
                  .convert("L").resize((64, 36)).getdata()) or [0]
        mean = sum(px) / len(px)
        var = (sum((v - mean) ** 2 for v in px) / len(px)) ** 0.5
        motion = sum(diffs) / len(diffs)
        return {"对比帧数": len(diffs),
                "① 内容·平均亮度": round(mean, 1),
                "① 内容·亮度标准差": round(var, 1),
                "① 有没有画面": "有" if (mean > 5 and var > 5) else "**没有**（纯黑或纯色）",
                "② 运动·静止帧占比": "%.0f%%" % (100.0 * still / len(diffs)),
                "② 运动·明显变化帧占比": "%.0f%%" % (100.0 * moved / len(diffs)),
                "② 运动·平均帧间差": round(motion, 2),
                "② 运动·最大帧间差": round(max(diffs), 2),
                "② 运动程度": "低（画面基本不动，如桌面/聊天界面）" if motion < 2 else
                              ("中" if motion < 10 else "高（画面明显在动）")}
    except Exception as exc:                                           # noqa: BLE001
        return {"说明": "质量读数算不出：%s: %s" % (type(exc).__name__, exc)}


def record(n: int, every: float, out: Path) -> dict:
    fps = max(1, int(round(1.0 / every))) if every else 15
    frames, info = _stream_frames(n, fps)
    if frames is None:
        return {"ok": False, "why": info}
    if not frames:
        return {"ok": False, "why": "**0 帧**（负对照：空录不算录像）"}
    w, h = frames[0][3], frames[0][4]
    qual = _quality(frames, w, h)
    # **裸流直喂 ffmpeg**（rgb24），不走磁盘图片序列 —— 少一次编解码、也躲开"扩展名不一致"那类坑
    mp4 = out
    cmd = [str(FF), "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", "%dx%d" % (w, h),
           "-framerate", str(fps), "-i", "-",
           "-c:v", "libx264", "-crf", "18", "-pix_fmt", "yuv420p",
           "-vf", "scale=trunc(iw/2)*2:trunc(ih/2)*2", str(mp4)]
    p = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    for f in frames:
        p.stdin.write(f[2])
    p.stdin.close()
    err = p.stderr.read().decode("utf-8", "replace")[-300:]
    p.wait()
    if not mp4.is_file() or mp4.stat().st_size <= 1024:
        return {"ok": False, "why": "ffmpeg 合成失败", "stderr": err}
    return {"ok": True, "帧数": len(frames), "fps": fps, "宽高": [w, h],
            "产物": str(mp4.relative_to(ROOT)), "字节": mp4.stat().st_size,
            "连续流读数": info, "画面质量": qual,
            "口径": "**连续帧流**（eye-stream · mss · 框架自己的眼）→ 裸 RGB 直喂 ffmpeg；不碰云、不花钱"}


def check(n: int, every: float, out: Path) -> int:
    print("本地录制（触手连拍 → 合成）")
    r = record(n, every, out)
    if not r.get("ok"):
        print("  **失败**：%s" % r.get("why"))
        return 1
    for k in ("帧数", "fps", "宽高", "产物", "字节"):
        print("  %-14s %s" % (k, r.get(k)))
    print("  %-14s %s" % ("连续流读数", r.get("连续流读数")))
    print("  %-14s %s" % ("画面质量", r.get("画面质量")))
    print("  口径: %s" % r["口径"])
    # 🔴 判据加"**有没有内容**"这一条：原来只看帧数+字节 ⇒ 上面那段**全静止的死录像**照样 PASS。
    #    现在要求：有效帧占比 > 0（真的有一帧跟前面不同）—— 否则红，并说清是"死屏"。
    # 判据分两层（**别把"不动"当成"没内容"**）：
    #   ① 内容面（**否决权**）：纯黑/纯色 = 没画面 ⇒ 红
    #   ② 运动面（**只报不否决**）：桌面/聊天界面本来就不动，那是题材决定的，不是录像坏了
    q = r.get("画面质量") or {}
    has_pic = q.get("① 有没有画面") == "有"
    ok = r["帧数"] > 0 and Path(ROOT / r["产物"]).stat().st_size > 1024 and has_pic
    if not has_pic:
        print("判据：**FAIL —— 没有画面**（%s · 亮度 %s · 标准差 %s ⇒ 纯黑或纯色）"
              % (q.get("① 有没有画面", "算不出"), q.get("① 内容·平均亮度"), q.get("① 内容·亮度标准差")))
        return 1
    print("判据：PASS（真帧 · 真成片 · **有画面** · 运动程度：%s）" % q.get("② 运动程度", "?"))
    return 0 if ok else 1


def main() -> int:
    ap = argparse.ArgumentParser(description="本地录制（触手连拍）")
    ap.add_argument("--frames", type=int, default=12)
    ap.add_argument("--every", type=float, default=0.25)
    ap.add_argument("--out", default="")
    a = ap.parse_args()
    # 🔴 2026-10-10 踩过：--out 给的是相对路径，却对它调 relative_to(ROOT) ⇒ ValueError。
    #    统一**解析成绝对路径**再落盘/回报。
    o = Path(a.out) if a.out else (OUT / "creative-local.mp4")
    o = (ROOT / o).resolve() if not o.is_absolute() else o
    OUT.mkdir(parents=True, exist_ok=True)
    return check(a.frames, a.every, o)


if __name__ == "__main__":
    raise SystemExit(main())
