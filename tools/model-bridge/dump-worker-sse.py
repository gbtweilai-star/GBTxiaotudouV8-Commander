#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""把 Worker 的流式 SSE 原样抓回来（看它到底有没有发 finish_reason）。

为什么：DSH 的 openai 适配器在流结束时必须有 finish_reason，没有就报
`Stream ended without finish_reason (TRANSPORT)` —— 页面就永远转圈。
这把尺子只读、不判，原样打印每一行的头部与尾部。
"""
import json
import re
import sys
import urllib.error
import urllib.request

URL = "https://gbt-potato-cloud-10.paysssk.workers.dev/v1/chat/completions"
CRED = r"C:\Users\ADMIN\.dsh\.credentials.yaml"


def gw():
    t = open(CRED, encoding="utf-8").read()
    m = re.search(r"(?m)^\s*GW_AUTH:\s*(\S+)\s*$", t)
    return m.group(1).strip().strip("\"'") if m else ""


def main():
    body = {"model": "gbt-potato-v8",
            "messages": [{"role": "user", "content": "说三个字：我到了"}],
            "max_tokens": 24, "stream": True}
    req = urllib.request.Request(URL, data=json.dumps(body, ensure_ascii=False).encode(), method="POST")
    req.add_header("Content-Type", "application/json")
    req.add_header("Authorization", "Bearer " + gw())
    req.add_header("Accept", "text/event-stream")
    req.add_header("User-Agent", "GBTxiaotudouV8-sse/1.0")
    lines = []
    try:
        with urllib.request.urlopen(req, timeout=240) as resp:
            print("HTTP", resp.status, "ct=", resp.headers.get("content-type"))
            buf = b""
            while True:
                chunk = resp.read(4096)
                if not chunk:
                    break
                buf += chunk
                while b"\n" in buf:
                    line, _, buf = buf.partition(b"\n")
                    s = line.strip().decode("utf-8", "replace")
                    if s:
                        lines.append(s)
    except urllib.error.HTTPError as e:
        print("HTTP", e.code, e.read().decode("utf-8", "replace")[:400])
        return 1
    except Exception as e:  # noqa: BLE001
        print("ERR", type(e).__name__, e)
        return 1
    print("总行数", len(lines))
    for s in lines:
        print(repr(s[:220]))
    # 判据：最后 6 行里必须出现 finish_reason
    tail = " ".join(lines[-6:])
    print("\n末尾是否出现 finish_reason:", "finish_reason" in tail)
    return 0


if __name__ == "__main__":
    sys.exit(main())
