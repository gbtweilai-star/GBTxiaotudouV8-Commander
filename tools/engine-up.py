# -*- coding: utf-8 -*-
"""本机引擎守护：确保 127.0.0.1:8792 有 llama-server 在跑（2026-11-02）

口径：桌面 APP 一开就有脑子，不再出现「离线」；有健康实例就直接复用。
路径全部相对 REPO：tools/llama/llama-server.exe + state/weights/*.gguf。
"""
from __future__ import annotations

import glob
import json
import os
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LOG = ROOT / "state" / "engine.log"
PORT = int(os.environ.get("GBT_ENGINE_PORT") or 8792)
BASE = "http://127.0.0.1:%d" % PORT


def health(timeout: float = 2.0) -> bool:
    try:
        with urllib.request.urlopen(BASE + "/health", timeout=timeout) as r:
            return r.status == 200
    except Exception:  # noqa: BLE001
        return False


def find_exe() -> str | None:
    cands = [ROOT / "tools" / "llama" / "llama-server.exe",
             ROOT / "vendor" / "llama-server.exe"]
    for p in cands:
        if p.is_file():
            return str(p)
    return None


def find_model() -> str | None:
    env = (os.environ.get("GBT_GGUF") or "").strip()
    if env and Path(env).is_file():
        return env
    files = []
    for pat in ("gbt-v8-v82-q5_0.gguf", "gbt-v8-v82-q4_k_m.gguf", "*.gguf"):
        files = sorted(glob.glob(str(ROOT / "state" / "weights" / pat)))
        if files:
            break
    return files[0] if files else None


def log(text: str) -> None:
    try:
        LOG.parent.mkdir(parents=True, exist_ok=True)
        with LOG.open("a", encoding="utf-8") as f:
            f.write("[%s] %s\n" % (time.strftime("%Y-%m-%dT%H:%M:%S"), text))
    except Exception:  # noqa: BLE001
        pass


def main() -> int:
    if health():
        log("engine already up on %d" % PORT)
        return 0
    exe, model = find_exe(), find_model()
    if not exe:
        log("no llama-server.exe under tools/llama or vendor")
        return 2
    if not model:
        log("no .gguf in state/weights")
        return 3
    args = [exe, "-m", model, "--host", "127.0.0.1", "--port", str(PORT),
            "-c", "4096", "--no-webui"]
    try:
        log("starting: %s" % " ".join(args))
        out = (ROOT / "state" / "engine.out.log").open("ab")
        err = (ROOT / "state" / "engine.err.log").open("ab")
        proc = subprocess.Popen(args, cwd=str(Path(exe).parent),
                                stdout=out, stderr=err,
                                creationflags=0x00000008 | 0x00000200)  # DETACHED|NEW_GROUP
        for i in range(90):
            if health():
                log("engine up after %ds pid=%s" % (i, proc.pid))
                return 0
            time.sleep(1)
        log("engine did NOT become healthy in 90s pid=%s" % proc.pid)
        return 4
    except Exception as exc:  # noqa: BLE001
        log("start failed: %s: %s" % (type(exc).__name__, exc))
        return 5


if __name__ == "__main__":
    sys.exit(main())
