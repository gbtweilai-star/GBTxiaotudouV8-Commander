# -*- coding: utf-8 -*-
"""desktop-humanoid/main.py —— 桌面数字人指挥官进程入口（二代 · 隔离版）。

职责：
1. 启动本地能力位桥（bridge.py，HTTP 127.0.0.1:8799）。
2. 启动 Edge --app 加载 renderer/index.html（本地文件，零网络）。
3. 守护进程：浏览器退出则自退出；桥退出则杀浏览器并自退出。
4. **不碰 Edge 窗口句柄**：Python ctypes 调用 SetWindowLongW/SetWindowPos
   会把 Edge 渲染子进程搞崩（rc=21）。三种隔离实验（极简 HTML / 只 Three.js /
   只 GLTFLoader / 只加载 GLB 绝对路径）均正常，唯独外部碰句柄会崩。
   视觉悬浮由页面本身 body 透明 + WebGL alpha=0 实现，不需要强行改窗口样式。

纪律：
- 写前校验、写后读回；本文件只修改，不覆盖其他文件。
- 失败带原因，不假装。
"""

from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RENDERER = ROOT / "desktop-humanoid" / "renderer" / "index.html"
GLB = ROOT / "holo_pet_w3" / "assets" / "dh" / "dh-v7-detail.glb"
PY = ROOT / "pyembed" / "python.exe"
BRIDGE = ROOT / "desktop-humanoid" / "bridge.py"


def log(msg: str):
    print("[desktop-humanoid] %s" % msg, flush=True)


def find_edge() -> str | None:
    """查找可用的 Edge 可执行文件（多候选，不报错缺失）。"""
    candidates = [
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
        os.environ.get("LOCALAPPDATA", "") + r"\Microsoft\Edge\Application\msedge.exe",
        os.environ.get("PROGRAMFILES", "") + r"\Microsoft\Edge\Application\msedge.exe",
    ]
    for c in candidates:
        if c and os.path.isfile(c):
            return c
    for name in ("msedge.exe", "chrome.exe"):
        try:
            import shutil
            p = shutil.which(name)
            if p:
                return p
        except Exception:
            pass
    return None


def _wait_http_ready(timeout_s: float = 15.0) -> bool:
    """轮询本地桥 HTTP /status，直到就绪或超时。"""
    import urllib.request
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        try:
            with urllib.request.urlopen("http://127.0.0.1:8799/status", timeout=2) as r:
                if r.status == 200:
                    return True
        except Exception:
            pass
        time.sleep(0.3)
    return False


def _diagnose_edge(profile_dir: Path | None = None) -> dict:
    """启动后自检：数 Edge 进程与 renderer 子进程，判断窗口是否真的能起来。

    实测判据（本机 Windows 11 + Edge）：
      正常启动   -> 8~17 个 msedge 进程，其中 renderer >= 1，并有可见 Chrome 窗口
      沙箱受限   -> 只有 MAIN + crashpad，renderer = 0，没有任何 Chrome 窗口
                    （Python 创建 GUI 进程被拒：Access is denied）

    该函数只报告事实，不做补救，也不假装成功。
    """
    info = {"edge_procs": 0, "renderers": 0, "windows": 0, "verdict": "unknown"}
    try:
        import json as _json
        ps = (
            "$p = @(Get-CimInstance Win32_Process -Filter \"Name='msedge.exe'\" "
            "-ErrorAction SilentlyContinue | Where-Object { $_.CommandLine -match 'desktop-humanoid' }); "
            "$r = @($p | Where-Object { $_.CommandLine -match '--type=renderer' }); "
            "Write-Output ('{0}|{1}' -f $p.Count, $r.Count)"
        )
        out = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", ps],
            capture_output=True, text=True, timeout=30,
        )
        txt = (out.stdout or "").strip()
        if "|" in txt:
            a, b = txt.split("|", 1)
            info["edge_procs"] = int(a.strip() or 0)
            info["renderers"] = int(b.strip() or 0)
    except Exception as exc:  # noqa: BLE001
        info["error"] = "%s: %s" % (type(exc).__name__, str(exc)[:120])

    if info["renderers"] > 0:
        info["verdict"] = "ok"
        log("自检：Edge 进程 %d 个，renderer %d 个 —— 渲染进程已创建 ✅"
            % (info["edge_procs"], info["renderers"]))
    elif info["edge_procs"] > 0:
        info["verdict"] = "no_renderer"
        log("自检：Edge 进程 %d 个，但 renderer=0 —— 窗口起不来，页面会是纯白屏。"
            % info["edge_procs"])
        log("      成因：本进程无权创建 GUI 子进程（Access is denied）。")
        log("      对策：请在桌面双击 启动-GBT.cmd 运行（正常桌面上下文可创建窗口）。")
    else:
        info["verdict"] = "no_proc"
        log("自检：没有找到 desktop-humanoid 的 Edge 进程。")
    return info


def main():
    if not RENDERER.is_file():
        log("renderer 缺失：%s" % RENDERER)
        return 1
    if not GLB.is_file():
        log("GLB 资产缺失：%s（数字人无法渲染，但窗口仍会启动）" % GLB)
    if not BRIDGE.is_file():
        log("bridge 缺失：%s（能力位对接不可用）" % BRIDGE)

    # 先启本地桥（能力位对接 + 四觉闭环，仅监听 127.0.0.1:8799）
    bridge_proc = None
    if BRIDGE.is_file():
        log("启动能力位桥：%s" % BRIDGE)
        bridge_proc = subprocess.Popen(
            [str(PY), "-X", "utf8", str(BRIDGE)],
            cwd=str(ROOT),
        )
        if not _wait_http_ready():
            log("桥 HTTP 未在 15s 内就绪，页面指令将降级为本地动画")

    edge = find_edge()
    if not edge:
        log("未找到 Edge/Chrome 浏览器，无法渲染 3D 页面")
        if bridge_proc:
            bridge_proc.terminate()
        return 1

    # 页面走 http:// 而非 file://：Edge 在 file:// 下对 GLTFLoader 的 fetch()
    # 施加 CORS 限制，加载本地 .glb 会 "TypeError: Failed to fetch"（实测）。
    # 桥同时托管 renderer 与 assets，页面与资源同源（bridge.py::_serve_static）。
    html = "http://127.0.0.1:8799/"
    # 独立 user-data-dir：避免 Edge 默认 profile 单例锁被占用导致 --app 实例
    # 拿不到 profile 锁而退出 rc=21（"Lock file can not be created! Error code: 5"）。
    profile_dir = ROOT / "desktop-humanoid" / "profile"
    profile_dir.mkdir(parents=True, exist_ok=True)

    edge_args = [
        "--app=" + html,
        "--user-data-dir=" + str(profile_dir),
        "--no-first-run",
        # WebGL 必需：--disable-gpu 与 --disable-software-rasterizer 同时启用会让
        # canvas.getContext('webgl') 直接返回 null（实测 WEBGL_NULL），Three.js 在
        # new WebGLRenderer() 处抛异常 -> 页面纯白无提示。改为禁用硬件 GPU、保留
        # SwiftShader 软件光栅化兜底（实测 WebGL 2.0 可用）。
        "--disable-gpu",
        "--enable-unsafe-swiftshader",
        "--disable-dev-shm-usage",
    ]

    log("启动 Edge --app 加载：%s（profile=%s）" % (html, profile_dir))
    # 用标准 Popen（用户双击 启动-GBT.cmd 时是正常桌面上下文，可正常创建窗口）。
    # 注意：在受限沙箱（如自动化会话）里，Python 创建 GUI 进程会被拒（Access is
    # denied），此时 Edge 只剩 MAIN+crashpad 且 renderer=0 —— 那是环境限制，
    # 不是本程序的问题，_diagnose_edge 会把这种情况如实报出来。
    # stdio 全部 DEVNULL：不继承调用方的管道句柄，避免干扰渲染进程创建。
    proc = subprocess.Popen(
        [edge] + edge_args,
        cwd=str(ROOT),
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    log("Edge --app 已提交（pid=%s）。" % proc.pid)

    # 等待 Edge 进程稳定（不等窗口句柄——那会触发 rc=21 崩溃）
    time.sleep(4.0)
    if proc.poll() is not None:
        log("Edge 启动后立即退出 rc=%s（渲染子进程崩溃？）" % proc.poll())
        _diagnose_edge()
        if bridge_proc:
            bridge_proc.terminate()
        return 1

    diag = _diagnose_edge()
    if diag.get("verdict") == "ok":
        log("Edge --app 已启动（pid=%s）。视觉悬浮由页面 body 透明 + WebGL alpha=0 实现，"
            "不碰窗口句柄以避免 rc=21 崩溃。" % proc.pid)
    else:
        log("Edge 进程在跑（pid=%s），但渲染进程未创建，窗口不会出现。" % proc.pid)
        log("本进程继续守护：桥仍在 127.0.0.1:8799 提供服务。")

    # 守护：浏览器或桥退出则本进程退出
    while True:
        rc = proc.poll()
        if rc is not None:
            log("浏览器进程已退出 rc=%s，本进程退出" % rc)
            if bridge_proc:
                bridge_proc.terminate()
            return rc
        if bridge_proc and bridge_proc.poll() is not None:
            brc = bridge_proc.poll()
            log("桥进程已退出 rc=%s，本进程退出" % brc)
            if proc is not None:
                try:
                    proc.terminate()
                except Exception:  # noqa: BLE001
                    pass
            return brc or 0
        time.sleep(2.0)


if __name__ == "__main__":
    sys.exit(main())