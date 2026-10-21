#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""流式（SSE）示例：验证"真流式"，而不是等一大段再吐。

判据不是看 content-type，而是**必须收到多个增量**。

用法：
    export GBT_BASE_URL="https://YOUR-PROXY/v1"
    export GBT_API_KEY="YOUR_TOKEN"
    python stream_sse.py
"""
import json
import os
import time
import urllib.request

BASE_URL = os.environ.get("GBT_BASE_URL", "https://YOUR-PROXY/v1").rstrip("/")
API_KEY = os.environ.get("GBT_API_KEY", "YOUR_TOKEN")
MODEL = os.environ.get("GBT_MODEL", "gbt-potato-v8")

body = {
    "model": MODEL,
    "messages": [{"role": "user", "content": "数到五，只输出数字。"}],
    "max_tokens": 40,
    "temperature": 0,
    "stream": True,
}

req = urllib.request.Request(
    BASE_URL + "/chat/completions",
    data=json.dumps(body).encode(),
    headers={"Content-Type": "application/json", "Authorization": "Bearer " + API_KEY},
    method="POST",
)

chunks, text = 0, []
t0 = time.time()
with urllib.request.urlopen(req, timeout=180) as resp:
    print("HTTP", resp.status, "· content-type:", resp.headers.get("content-type"))
    for raw in resp:
        line = raw.decode("utf-8", "replace").strip()
        if not line.startswith("data:"):
            continue
        data = line[5:].strip()
        if data == "[DONE]":
            break
        chunks += 1
        try:
            d = json.loads(data)
        except Exception:                                     # noqa: BLE001
            continue
        piece = (((d.get("choices") or [{}])[0].get("delta") or {}).get("content") or "")
        if piece:
            text.append(piece)
            print("  增量#%d %r" % (chunks, piece))

print("-" * 50)
print("收到 %d 个事件 · %.1fs · 拼接=%r" % (chunks, time.time() - t0, "".join(text)))
print("判定：" + ("真流式 ✓" if chunks > 1 and text else "没收到增量 ✗（代理可能在缓冲）"))
