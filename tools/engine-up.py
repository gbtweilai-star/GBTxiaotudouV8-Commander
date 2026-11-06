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
             ROOT / "vendor" / "llama" / "llama-server.exe",
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
    # 🔧 2026-11-05 统一启动路径（主人令）：本文件不再自己拼命令行，也不再写死 ctx。
    #    唯一真源 = gbt_allinone.tentacle.commander.start()：
    #      · 权重现读 state/weights/ACTIVE.json（不在代码里写死路径）
    #      · 引擎自己扫 tools/llama 与 vendor/ 找 llama-server（2026-11-06 补 tools/llama：
    #        打包版 exe 在那里，只扫 vendor 会报「没有 exe」而起不来）
    #      · ctx 取 commander.DEFAULT_CTX（= 权重声明的 32768），THREADS/IDLE 同源
    #      · 会带 --sleep-idle-seconds（按需激活：闲置卸权重让内存），这条 engine-up 原先拿不到
    #    影响面：1 跳 tools/console-server.py · tools · MANIFEST.json · state/trunk-cover.json
    try:
        _root = str(ROOT)
        if _root not in sys.path:      # weights.py 同款：脚本在 tools/ 下，仓根要自己上路径
            sys.path.insert(0, _root)
        from gbt_allinone.tentacle import commander as C
    except Exception as exc:                             # noqa: BLE001
        log("commander import failed: %s: %s" % (type(exc).__name__, exc))
        return 2
    log("delegate -> commander.start(base=%s ctx=%s idle=%s)"
        % (BASE, C.DEFAULT_CTX, C.DEFAULT_IDLE_S))
    r = C.start(base=BASE, wait=90.0)
    if r.get("ok"):
        log("engine up via commander pid=%s boot=%ss weights=%s"
            % (r.get("pid"), r.get("boot_s"), (r.get("weights") or {}).get("name")))
        return 0
    log("commander.start failed: %s" % json.dumps(r, ensure_ascii=False)[:400])
    return 4
    # 旧实现（自己 Popen）已移除：命令行、ctx、日志、pid 全部交给 commander 管，
    # 否则两条路径会各说各话（一边 4096 一边 32768，一边带 --sleep-idle-seconds 一边不带）。


if __name__ == "__main__":
    sys.exit(main())
