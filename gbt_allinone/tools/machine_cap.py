# gbt-capability: machine_film
# ⛔ 开发者：自由的风 · 永久钢印 · 禁止删除
"""Machine 光写实仿真 + 成片能力位 —— 一句话 → 可交互三维真机 → 28 秒成片。

## 这件外部件的来历（主人 2026-10-19 指名抓取：「这两个能力不就可以完美补齐缺失了吗」）
上游真身：`AirsupHQ/machine-skill`（MIT · 303★ · 2026-10-13 推）——
`_upstream/machine-skill/` 是**逐字节克隆**，本文件没改它一个字。
它补的是本仓原来**空着的那一格**：**科普成片那条腿**（本仓有剪辑/合成工具，但"把机理跑成真数、
再拍成片"这条路是空的；这也正是台账里 N7「video-frames 未安装」所缺的那半）。

## 它产出什么（现读实物）
  · `<name>.html`：**单文件**光写实三维真机（three.js · PBR 金属/涂装/玻璃 · 影棚光 · 软阴影）
    —— 真实尺寸（米）、真实材料、真实方程驱动的运动、爆炸/剖切/透视/慢放/标注/破坏七种模式
  · **成片**：`?film=1` 让页面时钟**只由录制方步进**（每一帧都渲染完整，任何机器速度都拍得出，
    每次录制结果一致）→ 逐帧截图 → ffmpeg 出 H.264 MP4 · 秒级 story（6 拍：一句话/造机/运行/剖开/拆开/破坏）
  · 主数字（推力/扭矩/转速/流量/效率）**由求解器算出来**，不是打上去的字

## 依赖面（已现读 · 全部本机已有，零付费）
  · `node` v24.15.0 · `Chrome`（标准位）· `ffmpeg` 8.1.2 · **python playwright 已装**
  · **不用 npm install**：上游 `scripts/lib/browser.mjs` 找 node 版 playwright，本机没有；
    我们改用**本机已有**的 python playwright + `channel="chrome"` 驱动同一个 Chrome（垫片，不改上游源码）
  · 页面里 three.js 从 jsDelivr 取（公网 CDN、无凭据）；本机另有 vendored three（离线可换，见 status.three_cdn）

## 门（处理器层挂闸，不碰 policy.py）
  · 读面免门：`status` / `examples` / `docs` / `where`
  · 写面挂 `filesystem_write`：`shot`（渲染静帧/审片图）· `film`（录成片）
  · **注意**：这里起的是**本机无头 Chrome 打开本地文件**，不是远控他人浏览器；也不上传任何数据

ops：`status` / `examples` / `docs` / `shot` / `film` / `where`
"""
from __future__ import annotations

import json
import re
import shutil
import sys
import time
from pathlib import Path

# 编码守门（本仓规矩：Windows 控制台默认 GBK，不带 -X utf8 时不许静默输不出中文）
for _s in (sys.stdout, sys.stderr):
    if hasattr(_s, "reconfigure"):
        _s.reconfigure(encoding="utf-8", errors="replace")

WS = Path(__file__).resolve().parents[2]
SRC = WS / "_upstream" / "machine-skill"
OUT = WS / "outputs" / "machine-film"
CHROME_CANDIDATES = [
    Path(r"C:\Program Files\Google\Chrome\Application\chrome.exe"),
    Path(r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe"),
]
NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,60}$")
OPS = ("status", "examples", "docs", "shot", "film", "where")
LAUNCH_ARGS = ["--ignore-gpu-blocklist", "--enable-gpu-rasterization",
               "--disable-background-timer-throttling", "--disable-renderer-backgrounding"]


def _chrome() -> str:
    for p in CHROME_CANDIDATES:
        if p.is_file():
            return str(p)
    return ""


def _ffmpeg() -> str:
    return shutil.which("ffmpeg") or ""


def _playwright() -> tuple[bool, str]:
    try:
        import playwright  # noqa: F401
        from playwright.sync_api import sync_playwright  # noqa: F401
        return True, ""
    except Exception as exc:                                   # noqa: BLE001
        return False, "%s: %s" % (type(exc).__name__, str(exc)[:160])


def _gate(what: str) -> dict | None:
    from .. import auth_gate
    from ..security import policy as _policy
    if _policy.is_trusted():
        return None
    got = auth_gate.check_and_consume("filesystem_write", detail=str(what)[:60])
    if got.get("ok"):
        return None
    return {"ok": False, "denied": True, "gate": "filesystem_write",
            "error": got.get("error"), "how_to_grant": got.get("how_to_grant"),
            "note": "shot/film 会落盘（静帧/成片），且会起本机无头 Chrome —— 写面必须人工授权"}


def _page_path(name: str) -> tuple[Path | None, str]:
    name = str(name or "").strip() or "turbofan"
    if not NAME_RE.match(name):
        return None, "页面名不合法（只许字母/数字/下划线/点/短横线）：%r" % name
    p = SRC / "examples" / name
    if p.suffix.lower() not in (".html", ".htm"):
        p = p.with_suffix(".html")
    if not p.is_file():
        have = sorted(x.stem for x in (SRC / "examples").glob("*.html"))
        return None, "没有这个页面（现读 examples 里有：%s）" % ", ".join(have)
    return p, ""


# ── 读面 ─────────────────────────────────────────────────────────────────────
def status(**_kw) -> dict:
    pw_ok, pw_why = _playwright()
    out = {"ok": _chk(SRC), "op": "status", "kind": "machine_film",
           "上游": "AirsupHQ/machine-skill", "许可": "MIT",
           "落点": _rel(SRC), "产物目录": _rel(OUT), "ops": list(OPS),
           "node": shutil.which("node") or "", "chrome": _chrome(),
           "ffmpeg": _ffmpeg(), "python_playwright": pw_ok,
           "driver": "python playwright + channel=chrome（本机 Chrome，不下载 Chromium）"}
    if not _chk(SRC):
        out.update({"installed": False,
                    "error": "未落位：%s（克隆：git clone --depth 1 https://github.com/AirsupHQ/machine-skill.git _upstream/machine-skill）"
                             % SRC})
        return out
    out["installed"] = True
    out["kit"] = sorted(p.name for p in (SRC / "kit").glob("*"))
    out["scripts"] = sorted(p.name for p in (SRC / "scripts").glob("*.mjs"))
    out["examples"] = sorted(x.stem for x in (SRC / "examples").glob("*.html"))
    out["films"] = sorted(p.name for p in (SRC / "film" / "stills").glob("*.jpg"))[:1] and \
                   sorted(p.name for p in (SRC / "film" / "stills").glob("*.jpg"))
    out["three_cdn"] = _three_cdn()
    missing = [k for k, v in (("node", out["node"]), ("chrome", out["chrome"]),
                              ("ffmpeg", out["ffmpeg"]), ("python_playwright", pw_ok)) if not v]
    out["就绪"] = not missing
    if missing:
        out["error"] = "缺依赖：%s（film 要全部齐；shot 至少要 chrome+playwright）" % ", ".join(missing)
        if not pw_ok:
            out["playwright_why"] = pw_why
    out["口径"] = "读面免门；shot/film 过 filesystem_write 门；起的是本机无头 Chrome，不上传数据"
    return out


def _chk(p: Path) -> bool:
    return p.is_dir()


def _rel(p: Path) -> str:
    try:
        return str(p.relative_to(WS)).replace("\\", "/")
    except ValueError:
        return str(p)


def _three_cdn() -> dict:
    """页面里 three.js 从哪来（离线可换的依据：本仓已有 vendored three）。"""
    hits = {}
    for x in (SRC / "examples").glob("*.html"):
        t = x.read_text(encoding="utf-8", errors="replace")[:400000]
        m = re.search(r"https://cdn\.jsdelivr\.net/npm/three@([\d.]+)/build/(three[.\w]*)", t)
        hits[x.stem] = ("three@" + m.group(1) + "/" + m.group(2)) if m else "（未取到 import map）"
    vend = WS / "holo_pet_w3" / "brain" / "vendor" / "three.module.min.js"
    return {"每页取法": hits, "本机 vendored": _rel(vend) if vend.is_file() else "无",
            "离线换法": "把 import map 的 cdn 地址改成本机 vendored 路径（出网只需一次，公开 CDN、无凭据）"}


def examples(**_kw) -> dict:
    if not _chk(SRC):
        return {"ok": False, "op": "examples", "error": "未落位：%s" % SRC}
    rows = []
    for p in sorted((SRC / "examples").glob("*.html")):
        rows.append({"name": p.stem, "bytes": p.stat().st_size,
                     "poster": (SRC / "examples" / "posters" / (p.stem + ".jpg")).is_file()})
    stills = sorted(x.name for x in (SRC / "film" / "stills").glob("*.jpg"))
    return {"ok": True, "op": "examples", "count": len(rows), "rows": rows,
            "示例成片静帧": {"count": len(stills), "sample": stills[:6]},
            "怎么出片": "cap machine_film '{\"op\":\"film\",\"name\":\"turbofan\"}'"}


def docs(**_kw) -> dict:
    if not _chk(SRC):
        return {"ok": False, "op": "docs", "error": "未落位：%s" % SRC}
    rows = []
    for p in [SRC / "SKILL.md", SRC / "README.md", SRC / "references" / "solvers.md"]:
        if p.is_file():
            rows.append({"file": _rel(p), "bytes": p.stat().st_size,
                         "lines": len(p.read_text(encoding="utf-8", errors="replace").splitlines())})
    return {"ok": True, "op": "docs", "count": len(rows), "rows": rows,
            "读法": "先读 SKILL.md（九步：研究真机→建页→几何→材料→求解器→流热→七模式→审片→成片），"
                    "再读 examples/turbofan.html 全文（它是质量基准）"}


# ── 写面（起本机 Chrome）────────────────────────────────────────────────────
def _launch(p, width: int, height: int):
    return p.chromium.launch(headless=True, channel="chrome",
                             args=LAUNCH_ARGS).new_page(viewport={"width": int(width),
                                                                  "height": int(height)})


def _open_film(page, path: Path, shot: str = "main", ss: float = 1.5, wait_s: int = 180) -> dict:
    """打开 `?film=1` 的确定性时钟页，返回 __film 元数据。**契约来自上游页面自己**（不改它）。"""
    url = path.as_uri() + "?film=1&shot=%s&ss=%s" % (shot, ss)
    page.goto(url, wait_until="load", timeout=120000)
    page.wait_for_function("() => window.__film && window.__film.ready && window.__film.loaded()",
                           timeout=wait_s * 1000, polling=250)
    page.evaluate("() => document.fonts.ready")
    meta = page.evaluate("() => ({len: window.__film.len})")
    page.evaluate("() => window.__film.start()")
    for _ in range(6):
        page.evaluate("() => window.__film.step(0)")
    page.wait_for_timeout(400)
    return {"url": url, "len": float(meta.get("len") or 0)}


def shot(name: str = "turbofan", js: str = "", width: int = 1280, height: int = 800,
         at: str = "", out: str = "", timeout: int = 300, **_kw) -> dict:
    path, why = _page_path(name)
    if not path:
        return {"ok": False, "op": "shot", "error": why, "fail_closed": True}
    denied = _gate("machine:shot:%s" % path.stem)
    if denied:
        return {"op": "shot", "name": path.stem, **denied}
    pw_ok, pw_why = _playwright()
    if not (pw_ok and _chrome()):
        return {"ok": False, "op": "shot", "error": "缺依赖：%s" % ("playwright" if not pw_ok else "chrome"),
                "why": pw_why}
    dst = Path(out) if out else (OUT / path.stem / ("shot.png" if not at else "film"))
    if not dst.is_absolute():
        dst = WS / dst
    dst.parent.mkdir(parents=True, exist_ok=True)
    from playwright.sync_api import sync_playwright
    t0 = time.time()
    errs: list = []
    files: list = []
    try:
        with sync_playwright() as p:
            page = _launch(p, width, height)
            page.on("pageerror", lambda e: errs.append("ERR:" + str(e)[:200]))
            if at:
                meta = _open_film(page, path)
                want = [float(x) for x in str(at).split(",") if x.strip()]
                cur = 0.0
                for t in sorted(want):
                    while cur < t - 1e-6:
                        step = min(1 / 30, t - cur)
                        page.evaluate("(dt) => window.__film.step(dt)", step)
                        cur += step
                    f = Path(str(dst) + "_%.1f.jpg" % t)
                    page.screenshot(path=str(f), type="jpeg", quality=93)
                    files.append({"file": _rel(f), "bytes": f.stat().st_size, "t": t})
                meta_out = meta
            else:
                page.goto(path.as_uri(), wait_until="load", timeout=120000)
                page.wait_for_timeout(5000)
                if js:
                    page.evaluate(js)
                    page.wait_for_timeout(1200)
                page.screenshot(path=str(dst))
                files.append({"file": _rel(dst), "bytes": dst.stat().st_size})
                meta_out = page.evaluate("() => ({canvases: document.querySelectorAll('canvas').length,"
                                         " title: document.title})")
            page.context.browser.close()
    except Exception as exc:                                   # noqa: BLE001
        return {"ok": False, "op": "shot", "name": path.stem,
                "error": "%s: %s" % (type(exc).__name__, str(exc)[:400]),
                "console": errs[:6], "elapsed_s": round(time.time() - t0, 1)}
    return {"ok": bool(files), "op": "shot", "name": path.stem, "文件": files,
            "meta": meta_out, "console": errs[:6], "elapsed_s": round(time.time() - t0, 1)}


def film(name: str = "turbofan", fps: int = 30, width: int = 1920, height: int = 1080,
         ss: float = 1.5, shot_name: str = "main", frm: float = 0.0, to: float = 0.0,
         out: str = "", timeout: int = 1800, **_kw) -> dict:
    """逐帧步进 + ffmpeg 出 MP4。帧率/尺寸/区间都可调；`to=0` = 整条 story。"""
    path, why = _page_path(name)
    if not path:
        return {"ok": False, "op": "film", "error": why, "fail_closed": True}
    denied = _gate("machine:film:%s" % path.stem)
    if denied:
        return {"op": "film", "name": path.stem, **denied}
    pw_ok, pw_why = _playwright()
    ff = _ffmpeg()
    if not (pw_ok and _chrome() and ff):
        return {"ok": False, "op": "film",
                "error": "缺依赖：%s" % ", ".join(k for k, v in
                                                 (("playwright", pw_ok), ("chrome", _chrome()),
                                                  ("ffmpeg", ff)) if not v),
                "why": pw_why}
    fps = max(6, min(60, int(fps)))
    dst = Path(out) if out else (OUT / path.stem / ("%s.mp4" % path.stem))
    if not dst.is_absolute():
        dst = WS / dst
    dst.parent.mkdir(parents=True, exist_ok=True)
    from playwright.sync_api import sync_playwright
    t0 = time.time()
    errs: list = []
    frames = 0
    try:
        with sync_playwright() as p:
            page = _launch(p, width, height)
            page.on("pageerror", lambda e: errs.append("ERR:" + str(e)[:200]))
            page.on("console", lambda m: errs.append("%s:%s" % (m.type, m.text[:160]))
                    if m.type in ("error", "warning") else None)
            meta = _open_film(page, path, shot=shot_name, ss=ss)
            length = float(to or meta.get("len") or 0)
            if not length:
                page.context.browser.close()
                return {"ok": False, "op": "film", "name": path.stem,
                        "error": "页面没报 __film.len（不是 film 模式页？）", "meta": meta}
            start = max(0.0, float(frm or 0))
            if start:
                page.evaluate("(t) => window.__film.seek(t)", start)
            span = max(0.0, length - start)
            n = int(round(span * fps))
            import subprocess
            ffp = subprocess.Popen([ff, "-y", "-loglevel", "error", "-f", "image2pipe",
                                    "-framerate", str(fps), "-c:v", "png", "-i", "pipe:0",
                                    "-r", str(fps), "-c:v", "libx264", "-preset", "slow",
                                    "-crf", "15", "-pix_fmt", "yuv420p", "-tune", "film",
                                    "-movflags", "+faststart", str(dst)],
                                   stdin=subprocess.PIPE, stderr=subprocess.PIPE)
            for i in range(n):
                if i > 0:
                    page.evaluate("(dt) => window.__film.step(dt)", 1.0 / fps)
                png = page.screenshot(type="png", timeout=600000)
                ffp.stdin.write(png)
                frames += 1
                if frames % 60 == 0:
                    ffp.stdin.flush()
            ffp.stdin.close()
            err_txt = (ffp.stderr.read() or b"").decode("utf-8", "replace")[-1500:]
            ffp.wait(timeout=600)
            page.context.browser.close()
    except Exception as exc:                                   # noqa: BLE001
        return {"ok": False, "op": "film", "name": path.stem, "frames": frames,
                "error": "%s: %s" % (type(exc).__name__, str(exc)[:400]),
                "console": errs[:6], "elapsed_s": round(time.time() - t0, 1)}
    ok = dst.is_file() and dst.stat().st_size > 0 and ffp.returncode == 0
    return {"ok": ok, "op": "film", "name": path.stem, "文件": _rel(dst),
            "bytes": dst.stat().st_size if dst.is_file() else 0,
            "frames": frames, "fps": fps, "size": [width, height], "区间": [start, length],
            "ffmpeg_exit": ffp.returncode, "ffmpeg_err": (err_txt or "") if not ok else "",
            "console": errs[:6], "elapsed_s": round(time.time() - t0, 1),
            "音轨": "无（上游 --music 会去 archive.org 下载 CC0 曲；本能力位不联网取曲，静音出片）"}


def where(**_kw) -> dict:
    return {"ok": True, "op": "where", "kind": "machine_film",
            "entry": "py -3.14 tools/codex-scripts/five-dim.py cap machine_film '{\"op\":\"status\"}'",
            "上游": "https://github.com/AirsupHQ/machine-skill（MIT）",
            "本机落点": "_upstream/machine-skill/", "产物": _rel(OUT),
            "ops": list(OPS),
            "what": "一句话 → 光写实可交互三维真机（单文件 HTML）→ 28 秒成片（MP4）；数字由求解器算出",
            "不接": "上游 npm 依赖（playwright 包）：本机用**已有**的 python playwright + 本机 Chrome 驱动同一个页面协议",
            "质量基准": "examples/turbofan.html 全文（先读再动手）"}


def run_op(op: str = "status", **kw) -> dict:
    table = {"status": status, "examples": examples, "docs": docs,
             "shot": shot, "film": film, "where": where}
    fn = table.get(str(op or "status").strip().lower())
    if fn is None:
        return {"ok": False, "op": op, "status": "unknown_op", "available": sorted(table),
                "fail_closed": True, "_口径": "未知 op 一律拒，不猜"}
    return fn(**kw)


if __name__ == "__main__":
    import sys
    print(json.dumps(run_op(sys.argv[1] if len(sys.argv) > 1 else "status"), ensure_ascii=False, indent=1))
