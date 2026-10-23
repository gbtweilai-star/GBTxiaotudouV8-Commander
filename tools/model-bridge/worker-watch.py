#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""只读：轮询 RunPod 端点 /health，看 worker 有没有起来（不打印密钥）。"""
import json
import os
import re
import sys
import time
import urllib.request

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        pass

CRED = os.path.expanduser(r"~\.dsh\.credentials.yaml")
EP = "qnnqf9w8xcefj8"


def key():
    try:
        t = open(CRED, encoding="utf-8").read()
    except OSError:
        return None
    m = re.search(r"GBT_POTATO_API_KEY:[ \t]*(?:ref:)?[ \t]*[\"']?([A-Za-z0-9_\-]{16,})", t)
    return m.group(1) if m else os.environ.get("GBT_POTATO_API_KEY")


def health(k):
    url = "https://api.runpod.ai/v2/%s/health" % EP
    req = urllib.request.Request(url, headers={"Authorization": "Bearer " + k,
                                               "User-Agent": "gbt-watch/1.0"})
    t0 = time.time()
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.loads(r.read(600).decode("utf-8", "replace")), round((time.time() - t0) * 1000)


def main():
    rounds = int(sys.argv[1]) if len(sys.argv) > 1 else 10
    gap = int(sys.argv[2]) if len(sys.argv) > 2 else 15
    k = key()
    if not k:
        print("拿不到 GBT_POTATO_API_KEY")
        return 2
    for i in range(rounds):
        try:
            j, ms = health(k)
            w = j.get("workers") or {}
            jobs = j.get("jobs") or {}
            print("t+%3ds  ready=%s running=%s init=%s unhealthy=%s standby=%s  inQueue=%s  (%dms)"
                  % (i * gap, w.get("ready"), w.get("running"), w.get("initializing"),
                     w.get("unhealthy"), w.get("standby"), jobs.get("inQueue"), ms), flush=True)
            if int(w.get("ready") or 0) + int(w.get("running") or 0) > 0:
                print("✅ worker 起来了")
                return 0
        except Exception as e:  # noqa: BLE001
            print("t+%3ds  probe err %s: %s" % (i * gap, type(e).__name__, str(e)[:80]), flush=True)
        if i < rounds - 1:
            time.sleep(gap)
    print("❌ 轮询结束仍未起来")
    return 1


if __name__ == "__main__":
    sys.exit(main())
