#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""**语音剧场验收器** —— 给 `holo_pet_w3/voice-theater/index.html` 一道可复跑的闸。

开发者：自由的风 · 本署名不可删除、不可篡改归属

## 为什么要有它
2026-10-17 按主人「之前的语音交互不行，你重新设计一下」出了新设计稿（A·全屏对话剧场）。
设计稿最容易骗人的地方是：**截图看着好看，里面是空的** —— 波形是假动画、
状态灯永远亮着、点了没反应、素材路径 404。这三件事在**静态阅读**里全都看不出来。
⇒ 本器只做一件事：**把设计稿当产品验收** —— 静态结构 · 素材真实 · 真渲染 · 非空画面。

## 五条判据（每条都能单独解释），任一不过 = 红
  C1 结构齐：状态轨 4 态 / 波形画布 / 光球 / 字幕 / 体检位 —— 少一个就不算这套交互。
  C2 素材真：立绘 jpg 与欢迎语音 wav **在盘上且非空**；wav 头必须是 RIFF/WAVE。
  C3 无外网面：不许 `<script src=` / `<link href=` 引外部地址（壳里 CSP 会拒，且不该偷网）。
  C4 真渲染：本机无头浏览器**真打开**该页并截图（不是读源码猜）。
  C5 非空画面：截图是合法 PNG、尺寸对、**字节量够大**（纯黑空页压不出几十万字节）。

## 诚实边界（写死，免得以后念错）
  · 本器**不验声音好不好听**、不验 ASR/TTS 能不能用 —— 那要等 `audio_output` 授权与壳桥。
  · 它验的是「设计稿本身不是空壳」，**不等于**「语音链路已接通」。
  · 🔴 **无头浏览器不跑页面的异步任务**（2026-10-18 实测）：截图里 `录音端点` 停在「正在枚举…」、
    `解码状态` 停在「载入中…」—— 这是**截图环境**的限制，不是页面坏了。
    因此 C4/C5 **只证明静态画面与素材在位**；解码/开麦/说话这些异步行为，本器一律不宣称验过。
  · 拿不到浏览器时**报 `skipped` 且非零**（不许记成通过：不适用 ≠ 通过）。
  · 截图落 `.scratch/voice-theater-check.png`，人可复核。

## 用法
  # ① 静态三条（结构 / 素材 / 无外网面）随时可跑：
  py -3.14 tools/codex-scripts/voice-theater-check.py
  # ② 要连 C4/C5（真渲染 + 非空画面）—— 本沙箱里浏览器**只能从 shell 起**，
  #    所以先在外面拍一张，再把路径喂进来（两条命令照抄即可）：
  #    py -3.14 -m http.server 8899 --bind 127.0.0.1 *> $env:TEMP/vt-server.log   # 另开一个窗口
  #    msedge --headless=new --disable-gpu --no-sandbox --window-size=1600,1000 \
  #      --virtual-time-budget=6000 --screenshot=.scratch/voice-theater-check.png \
  #      http://127.0.0.1:8899/holo_pet_w3/voice-theater/index.html
  py -3.14 tools/codex-scripts/voice-theater-check.py --shot .scratch/voice-theater-check.png
  py -3.14 tools/codex-scripts/voice-theater-check.py --json
退出码：0 全过 · 1 有红 · 2 环境不足（浏览器/服务起不来 —— 仍非零）
"""
from __future__ import annotations

import argparse
import http.server
import json
import os
import shutil
import socket
import struct
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PAGE_REL = "holo_pet_w3/voice-theater/index.html"
PAGE = ROOT / PAGE_REL
PORTRAIT = ROOT / "holo_pet_w3/digital-human/digital-human-hero-3q.jpg"
SAMPLE = ROOT / "holo_pet_w3/digital-human/welcome-gbt-v8-zh.wav"
SHOT = ROOT / ".scratch/voice-theater-check.png"

BROWSERS = [
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
]

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        pass


def ok(name: str, detail: str) -> dict:
    return {"check": name, "ok": True, "detail": detail}


def bad(name: str, detail: str) -> dict:
    return {"check": name, "ok": False, "detail": detail}


# ── C1 结构齐 ───────────────────────────────────────────────────────────────
def check_structure(html: str) -> dict:
    need = {
        "状态轨 4 态": html.count('data-state="') >= 4,
        "波形画布 #wave": 'id="wave"' in html,
        "光球 #orb": 'id="orb"' in html,
        "字幕位 #caption": 'id="caption"' in html,
        "体检位 #pMic": 'id="pMic"' in html,
        "打断入口": 'id="stop"' in html,
        "真音频驱动": "createAnalyser" in html and "getByteFrequencyData" in html,
        "状态机唯一改口": "function setState(" in html,
    }
    miss = [k for k, v in need.items() if not v]
    if miss:
        return bad("C1 结构齐", "缺：" + "、".join(miss))
    return ok("C1 结构齐", "8 项结构全在（状态轨/波形/光球/字幕/体检/打断/真音频/状态机）")


# ── C2 素材真 ───────────────────────────────────────────────────────────────
def check_assets(html: str) -> dict:
    problems = []
    glb = ROOT / "holo_pet_w3/voice-theater/assets/dh-v2-rigged.glb"
    dh3d = ROOT / "holo_pet_w3/voice-theater/dh3d.js"
    chat = ROOT / "holo_pet_w3/voice-theater/chat-ui.js"
    motion = ROOT / "holo_pet_w3/voice-theater/motion.js"
    drawer = ROOT / "holo_pet_w3/voice-theater/nav-drawer.js"
    vendor = [
        ROOT / "holo_pet_w3/brain/vendor/three.global.js",
        ROOT / "holo_pet_w3/brain/vendor/BufferGeometryUtils.global.js",
        ROOT / "holo_pet_w3/brain/vendor/GLTFLoader.global.js",
    ]
    stage_src = dh3d.read_text(encoding="utf-8") if dh3d.is_file() else ""

    # ① 真 3D 资产：绑骨骼 glb（2026-10-18 主人令「按源码实现」后，立绘 jpg 已撤）
    if not glb.is_file():
        problems.append(f"绑骨骼模型不在盘上：{glb.relative_to(ROOT)}")
    elif glb.stat().st_size < 5_000_000:
        problems.append(f"模型过小（{glb.stat().st_size} B），不像带贴图的绑骨件")
    else:
        magic, ver = struct.unpack("<II", glb.open("rb").read(8))
        if magic != 0x46546C67 or ver != 2:
            problems.append(f"不是 glTF 2.0 二进制：magic={magic:#x} ver={ver}")
    if "dh-v2-rigged.glb" not in html and "dh-v2-rigged.glb" not in stage_src:
        problems.append("页面/舞台都没引用绑骨骼模型")

    # ② three + GLTFLoader 必须已在壳里 vendor（零 CDN；缺一个舞台就是空的）
    for f in vendor:
        if not f.is_file():
            problems.append(f"vendor 缺件：{f.relative_to(ROOT)}")
    for name in ("three.global.js", "BufferGeometryUtils.global.js", "GLTFLoader.global.js"):
        if name not in html:
            problems.append(f"页面没挂 {name}")
    for name, path in (("dh3d.js", dh3d), ("chat-ui.js", chat), ("motion.js", motion), ("nav-drawer.js", drawer)):
        if not path.is_file():
            problems.append(f"{name} 不在盘上")
        elif name not in html:
            problems.append(f"页面没挂 {name}")

    # ③ 欢迎语音（波形真包络来源）
    if not SAMPLE.is_file():
        problems.append(f"欢迎语音不在盘上：{SAMPLE.relative_to(ROOT)}")
    elif SAMPLE.stat().st_size < 20_000:
        problems.append(f"欢迎语音过小（{SAMPLE.stat().st_size} B）")
    else:
        head = SAMPLE.open("rb").read(12)
        if not (head[:4] == b"RIFF" and head[8:12] == b"WAVE"):
            problems.append(f"欢迎语音不是 RIFF/WAVE：头={head!r}")
        if "welcome-gbt-v8-zh.wav" not in html:
            problems.append("页面没引用欢迎语音 —— 波形就不是真包络了")

    if problems:
        return bad("C2 素材真", "；".join(problems))
    return ok("C2 素材真", f"绑骨骼模型 {glb.stat().st_size // 1024} KB glTF2 · "
                           f"three/BufferGeometryUtils/GLTFLoader 三件在壳内 · "
                           f"语音 {SAMPLE.stat().st_size // 1024} KB RIFF/WAVE")


# ── C3 无外网面 ─────────────────────────────────────────────────────────────
def check_no_network(html: str) -> dict:
    import re

    offenders = []
    for m in re.finditer(r'<(script|link|img)[^>]*?(?:src|href)\s*=\s*["\']([^"\']+)["\']', html, re.I):
        url = m.group(2).strip()
        if url.startswith(("http://", "https://", "//")):
            offenders.append(url)
    fetches = re.findall(r"fetch\(\s*['\"](https?://[^'\"]+)", html)
    offenders.extend(fetches)
    if offenders:
        return bad("C3 无外网面", "引了外部地址：" + "、".join(offenders[:5]))
    return ok("C3 无外网面", "无外部 script/link/img/fetch（素材全是仓内相对路径）")


# ── C4 真渲染 ───────────────────────────────────────────────────────────────
def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class _Quiet(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *_a):  # noqa: D401
        return


def _serve(root: Path, port: int):
    handler = lambda *a, **k: _Quiet(*a, directory=str(root), **k)  # noqa: E731
    httpd = http.server.ThreadingHTTPServer(("127.0.0.1", port), handler)
    t = threading.Thread(target=httpd.serve_forever, daemon=True)
    t.start()
    return httpd


def _browser() -> str | None:
    for p in BROWSERS:
        if Path(p).is_file():
            return p
    return shutil.which("chrome") or shutil.which("msedge")


def _browser_candidates() -> list[str]:
    """按**实测可用顺序**返回候选：本机 Edge 稳、Chrome 会挂住不退出（16 个残留进程实测）。"""
    order = [
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    ]
    out = [p for p in order if Path(p).is_file()]
    if not out:
        for name in ("msedge", "chrome"):
            w = shutil.which(name)
            if w:
                out.append(w)
    return out


def _server_speaks(port: int) -> tuple[bool, str]:
    """真去 GET 一次：**端口被别人占着**时 python 的 http.server 起不来，
    而浏览器会拿到别人的 404（实测：8778 上是另一个 uvicorn 服务）。
    ⇒ 不验这一步，C4 会把"别人的 404 页"当成我们的截图。"""
    import urllib.error
    import urllib.request

    url = f"http://127.0.0.1:{port}/{PAGE_REL}"
    try:
        with urllib.request.urlopen(url, timeout=5) as resp:
            body = resp.read(2048).decode("utf-8", "replace")
            if resp.status == 200 and "GBT小土豆V8" in body:
                return True, f"200 · {len(body)}B 首段含品牌字"
            return False, f"HTTP {resp.status} 但正文不含品牌字（疑似别人的服务）"
    except urllib.error.HTTPError as e:
        return False, f"HTTP {e.code}（该端口可能是别的服务）"
    except Exception as e:  # noqa: BLE001
        return False, f"连不上：{e}"


def check_render(timeout_s: int = 25, shot: Path | None = None) -> dict:
    """真渲染。

    🔴 2026-10-18 实测环境约束（写死，免得下次又踩）：
       浏览器**从 Python 子进程里起不来** —— 本沙箱挡住它自己的进程间通信，
       表现是「启动器 rc=0、后台工作进程挂住、截图永不落地」（一次实测留了 16 个残留进程）。
       而**同一个浏览器从 shell 直接起就正常**。
       ⇒ 因此本判据两种来源都认：
         ① `--shot <path>` 由外部（shell）现拍一张给进来 —— 本器只验它在不在、新不新、是不是真 PNG；
         ② 没给就自己试着起（短预算）；起不来就**明确报红 + 给替代命令**，不记成"跳过=通过"。
    """
    if shot is not None:
        if not shot.is_file():
            return bad("C4 真渲染", f"--shot 指定的文件不存在：{shot}")
        age = time.time() - shot.stat().st_mtime
        if age > 3600:
            return bad("C4 真渲染", f"--shot 的截图过旧（{age / 60:.0f} 分钟前）⇒ 重新拍一张")
        if PAGE.stat().st_mtime > shot.stat().st_mtime:
            return bad("C4 真渲染", "--shot 的截图**比页面还旧** ⇒ 页面改过，截图不能作证")
        return ok("C4 真渲染", f"外部现拍截图有效（{age:.0f}s 前）· {shot.name}")

    browsers = _browser_candidates()[:2]
    if not browsers:
        return bad("C4 真渲染", "本机找不到 chrome/msedge ⇒ 这一条**没跑**（不适用≠通过）")

    port = _free_port()
    httpd = _serve(ROOT, port)
    proc = None
    try:
        time.sleep(0.5)
        speaks, why = _server_speaks(port)
        if not speaks:
            return bad("C4 真渲染", f"本地静态服务没起来：{why}（端口 {port}）")

        SHOT.parent.mkdir(parents=True, exist_ok=True)
        errs = []
        for browser in browsers:
            for mode in ("--headless=new", "--headless"):
                if SHOT.exists():
                    SHOT.unlink()
                prof = tempfile.mkdtemp(prefix="voice-theater-prof-")
                logdir = tempfile.mkdtemp(prefix="voice-theater-log-")
                logpath = Path(logdir) / "browser.log"
                cmd = [
                    browser, mode, "--disable-gpu", "--no-sandbox",
                    f"--user-data-dir={prof}", "--hide-scrollbars",
                    "--window-size=1600,1000", "--virtual-time-budget=6000",
                    f"--screenshot={SHOT}",
                    f"http://127.0.0.1:{port}/{PAGE_REL}",
                ]
                try:
 # 不用 pipe 接 stdio（本沙箱会挡）；输出走真文件。
                    with logpath.open("wb") as log:
                        proc = subprocess.Popen(cmd, stdout=log, stderr=log)
 # **不许因为"启动器已退出"就提前收工**：Edge/Chrome 的 chrome.exe
                        #    只是启动器，真正落截图的是后台工作进程（实测：启动器秒退、截图 1–3s 后才落）。
                        #    这里只按**文件是否出现**判，且给足预算。
                        deadline = time.time() + timeout_s
                        while time.time() < deadline and not SHOT.exists():
                            time.sleep(0.25)
                finally:
                    if proc is not None and proc.poll() is None:
                        subprocess.run(["taskkill", "/PID", str(proc.pid), "/T", "/F"],
                                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                    shutil.rmtree(prof, ignore_errors=True)
                if SHOT.exists():
                    tail = logpath.read_text("utf-8", "replace")[-200:] if logpath.exists() else ""
                    shutil.rmtree(logdir, ignore_errors=True)
                    return ok("C4 真渲染", f"已真打开并截图 · {Path(browser).name} {mode} · "
                                           f"{SHOT.relative_to(ROOT)}" + (f" · 日志尾：{tail}" if tail else ""))
                tail = logpath.read_text("utf-8", "replace")[-160:] if logpath.exists() else ""
                shutil.rmtree(logdir, ignore_errors=True)
                errs.append(f"{Path(browser).name}{mode}：无截图" + (f"（{tail}）" if tail.strip() else ""))
        return bad("C4 真渲染", "逐个头无头浏览器都试过仍无截图：" + "；".join(errs[:2])
                   + "\n     ⇒ 本沙箱请走外部截图（两条命令照着抄）：\n"
                     "       py -3.14 -m http.server 8899 --bind 127.0.0.1 *> $env:TEMP/vt-server.log   # 另开一个窗口\n"
                     "       msedge --headless=new --disable-gpu --no-sandbox --window-size=1600,1000 "
                     "--virtual-time-budget=6000 --screenshot=.scratch/voice-theater-check.png "
                     "http://127.0.0.1:8899/holo_pet_w3/voice-theater/index.html\n"
                     "       py -3.14 tools/codex-scripts/voice-theater-check.py --shot .scratch/voice-theater-check.png")
    finally:
        httpd.shutdown()


# ── C5 非空画面 ─────────────────────────────────────────────────────────────
def check_shot() -> dict:
    if not SHOT.is_file():
        return bad("C5 非空画面", "没有截图可验（C4 已红）")
    data = SHOT.read_bytes()
    if data[:8] != b"\x89PNG\r\n\x1a\n":
        return bad("C5 非空画面", "不是合法 PNG")
    w, h = struct.unpack(">II", data[16:24])
    if (w, h) != (1600, 1000):
        return bad("C5 非空画面", f"尺寸不对：{w}x{h}（期望 1600x1000）")
    if len(data) < 150_000:
        return bad("C5 非空画面", f"字节量只有 {len(data) // 1024} KB ⇒ 疑似空/纯色页")
    return ok("C5 非空画面", f"1600x1000 · {len(data) // 1024} KB（非空判据 ≥150KB）")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="语音剧场设计稿验收（只读）")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--shot", default="",
                    help="外部现拍的截图（本沙箱里浏览器只能从 shell 起 ⇒ 常走这条）")
    ap.add_argument("--keep", action="store_true", help="保留截图（默认也保留，此参数仅为兼容）")
    a = ap.parse_args(argv)

    if not PAGE.is_file():
        print(f"🔴 页面不在：{PAGE_REL}")
        return 1

    html = PAGE.read_text(encoding="utf-8", errors="replace")
    results = [
        check_structure(html),
        check_assets(html),
        check_no_network(html),
        check_render(shot=Path(a.shot) if a.shot else None),
        check_shot(),
    ]
    red = [r for r in results if not r["ok"]]

    if a.json:
        print(json.dumps({"ok": not red, "page": PAGE_REL, "results": results},
                         ensure_ascii=False, indent=2))
    else:
        print("═" * 74)
        print(f"  语音剧场验收 · {PAGE_REL}")
        print("═" * 74)
        for r in results:
            print(f"  {'✅' if r['ok'] else '🔴'} {r['check']:<14} {r['detail']}")
        print("-" * 74)
        print(f"结论：{'全过' if not red else '有红 %d 条' % len(red)}")
        print("边界：只验「设计稿不是空壳」；不验音质、不验 ASR/TTS 是否接通"
              "（那要 audio_output 授权与壳桥）。无头浏览器不跑页面异步任务 ⇒ "
              "解码/开麦/说话这三件事本器**不宣称验过**。")
    return 0 if not red else 1


if __name__ == "__main__":
    raise SystemExit(main())
