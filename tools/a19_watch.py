#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""a19_watch —— 探到 :1234 **真能应答**（不只是 TCP 通）就立刻打一发快枪。

为什么要分辨"TCP 通"和"能应答"：
  实测 iSH 里 TCP 握手能成（内核排队），但 App 进程被 iOS 挂起 ⇒ 请求超时。
  只看端口通会白打。所以先发一个 3 秒的 /v1/models 探活，通了才开火。
"""
import json
import pathlib
import socket
import sys
import time
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))


def tcp() -> bool:
    s = socket.socket(); s.settimeout(1.0)
    try:
        s.connect(("127.0.0.1", 1234)); return True
    except OSError:
        return False
    finally:
        s.close()


def alive() -> bool:
    """真能应答才算活（3 秒硬限）。"""
    try:
        urllib.request.urlopen(urllib.request.Request(
            "http://127.0.0.1:1234/v1/models",
            headers={"Authorization": "Bearer gbt"}), timeout=3).read()
        return True
    except Exception:                                         # noqa: BLE001
        return False


def main() -> int:
    print("  🎯 哨兵（快枪版）· 每 2s 探；只认'真能应答'", flush=True)
    n = 0
    while True:
        n += 1
        if tcp() and alive():
            print("  ✅ :1234 真活着 —— 开火", flush=True)
            import a19_shot
            try:
                a19_shot.main()
            except SystemExit:
                pass
            return 0
        if n % 30 == 0:
            print("    …%ds（TCP=%s）" % (n * 2, "通" if tcp() else "断"), flush=True)
        time.sleep(2)


if __name__ == "__main__":
    raise SystemExit(main())
