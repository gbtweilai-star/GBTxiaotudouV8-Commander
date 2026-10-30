# -*- coding: utf-8 -*-
"""A19 看门狗（2026-10-31）

为什么要有它：`lmpocket://` 能把 App 拉起来并**让服务真的起**（实测 8 秒内 :1234 通），
但 App 被 iOS 挂起后端口会消失。以前这要人盯着 —— 现在让它自己回来。

策略：
  ① 端口不通 → apple-open lmpocket:// → 最多等 12 秒
  ② 通了 → 轻量打一次 /v1/models 确认不是僵死；429/401 如实记，不重试轰炸
  ③ 每轮都落账 state/a19_keeper.jsonl，能查"什么时候被拉回来过几次"
"""
from __future__ import annotations

import json
import socket
import subprocess
import sys
import time
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[1]
LOG = ROOT / "state" / "a19_keeper.jsonl"
KEY = "gbt"


def up(host="127.0.0.1", port=1234, tmo=1.5):
    try:
        s = socket.create_connection((host, port), timeout=tmo)
        s.close()
        return True
    except Exception:                                               # noqa: BLE001
        return False


def models():
    import urllib.request
    try:
        req = urllib.request.Request("http://127.0.0.1:1234/v1/models",
                                     headers={"Authorization": "Bearer " + KEY})
        with urllib.request.urlopen(req, timeout=6) as r:
            d = json.loads(r.read())
            return [m.get("id") for m in (d.get("data") or [])][:3]
    except Exception as e:                                          # noqa: BLE001
        return "ERR:%s" % type(e).__name__


def log(rec):
    LOG.parent.mkdir(parents=True, exist_ok=True)
    with LOG.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(rec, ensure_ascii=False) + "\n")


def once(wait=12.0, verbose=True):
    t0 = time.time()
    if up():
        m = models()
        rec = {"at": time.strftime("%Y-%m-%dT%H:%M:%S"), "act": "alive", "models": m}
        log(rec)
        if verbose:
            print("  A19 活着 · models=%s" % (m if not isinstance(m, str) else m))
        return True
    try:
        subprocess.run(["apple-open", "lmpocket://"], capture_output=True, timeout=25)
    except Exception as e:                                          # noqa: BLE001
        if verbose:
            print("  apple-open 失败：%s" % type(e).__name__)
    while time.time() - t0 < wait:
        time.sleep(1)
        if up():
            m = models()
            rec = {"at": time.strftime("%Y-%m-%dT%H:%M:%S"), "act": "relaunched",
                   "sec": round(time.time() - t0, 1), "models": m}
            log(rec)
            if verbose:
                print("  ✅ 拉起成功 · %.1fs · models=%s" % (rec["sec"], m))
            return True
    log({"at": time.strftime("%Y-%m-%dT%H:%M:%S"), "act": "still_down"})
    if verbose:
        print("  🔴 拉起后 %.0fs 仍不通（Auto-Start 关了？需要人在 App 里点一次 Start）" % wait)
    return False


def main(argv):
    if len(argv) > 1 and argv[1] == "watch":
        every = float(argv[2]) if len(argv) > 2 else 120.0
        print("  A19 看门狗 · 每 %.0fs 一轮" % every, flush=True)
        while True:
            once(verbose=True)
            time.sleep(every)
    ok = once()
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
