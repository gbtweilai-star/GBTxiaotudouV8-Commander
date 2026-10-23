#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""用 .credentials.yaml 里的 GW_AUTH 打一次 Worker，量首字与整轮（不打印密钥）。"""
import json
import re
import sys
import time
import urllib.error
import urllib.request

CRED = r"C:\Users\ADMIN\.dsh\.credentials.yaml"
URL = "https://gbt-potato-cloud-10.paysssk.workers.dev/v1/chat/completions"


def gw():
    t = open(CRED, encoding="utf-8").read()
    m = re.search(r"(?m)^\s*GW_AUTH:\s*(\S+)\s*$", t)
    if not m:
        return ""
    v = m.group(1).strip()
    return v.strip("\"'")


def main():
    key = gw()
    print("GW_AUTH len=%d prefix=%s****" % (len(key), key[:4] if key else ""))
    if not key:
        return 2
    body = {"model": "gbt-potato-v8",
            "messages": [{"role": "user", "content": "用一句话介绍你自己。"}],
            "max_tokens": 48, "stream": False}
    data = json.dumps(body, ensure_ascii=False).encode()
    r = urllib.request.Request(URL, data=data, method="POST")
    r.add_header("Content-Type", "application/json")
    r.add_header("Authorization", "Bearer " + key)
    r.add_header("User-Agent", "GBTxiaotudouV8-probe/1.0")
    t0 = time.time()
    try:
        with urllib.request.urlopen(r, timeout=240) as resp:
            raw = resp.read().decode("utf-8", "replace")
            j = json.loads(raw)
            ch = (j.get("choices") or [{}])[0]
            print("HTTP", resp.status, "ms", int((time.time() - t0) * 1000))
            print("model", j.get("model"))
            print("gbt", json.dumps(j.get("gbt"), ensure_ascii=False))
            print("finish", ch.get("finish_reason"))
            print("content", repr(((ch.get("message") or {}).get("content") or "")[:160]))
    except urllib.error.HTTPError as e:
        print("HTTP", e.code, "ms", int((time.time() - t0) * 1000), e.read().decode("utf-8", "replace")[:400])
        return 1
    except Exception as e:  # noqa: BLE001
        print("ERR", type(e).__name__, e, int((time.time() - t0) * 1000), "ms")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
