#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""按 DSH 适配器真实请求体的各种字段组合，逐档打我们的 Worker，看哪一档把流弄坏。

背景（已现读的适配器源码 openai-completions.js）：
  · 它一定会带 `stream_options = {include_usage: true}`（supportsUsageInStreaming: true）
  · 可能带 `store:false` / `prompt_cache_key` / `max_completion_tokens` / `temperature`
  · 收流结束时**必须有 finish_reason**，否则报 `Stream ended without finish_reason`
    —— 页面就卡在“thought for a while”转圈（本仓实测：宿主里打 gbt-potato 就是这么死的）。

用法：py -3.14 tools/model-bridge/worker-body-matrix.py
"""
import json
import re
import sys
import time
import urllib.error
import urllib.request

URL = "https://gbt-potato-cloud-10.paysssk.workers.dev/v1/chat/completions"
CRED = r"C:\Users\ADMIN\.dsh\.credentials.yaml"
BASE = {"model": "gbt-potato-v8",
        "messages": [{"role": "user", "content": "说三个字：我到了"}],
        "stream": True}

VARIANTS = {
    "bare": {},
    "usage": {"stream_options": {"include_usage": True}},
    "usage+store": {"stream_options": {"include_usage": True}, "store": False},
    "usage+cachekey": {"stream_options": {"include_usage": True},
                       "prompt_cache_key": "gbt-mat-0001"},
    "usage+max_completion": {"stream_options": {"include_usage": True},
                             "max_completion_tokens": 24},
    "usage+tools": {"stream_options": {"include_usage": True},
                    "tools": [{"type": "function",
                               "function": {"name": "read", "description": "读文件",
                                            "parameters": {"type": "object",
                                                           "properties": {"path": {"type": "string"}}}}}]},
    "adapter-ish": {"stream_options": {"include_usage": True}, "store": False,
                    "prompt_cache_key": "gbt-mat-0002", "temperature": 0.3,
                    "max_tokens": 24, "tools": [],
                    "tool_choice": "auto"},
}


def gw():
    t = open(CRED, encoding="utf-8").read()
    m = re.search(r"(?m)^\s*GW_AUTH:\s*(\S+)\s*$", t)
    return m.group(1).strip().strip("\"'") if m else ""


def run(name, extra):
    body = dict(BASE)
    body.update(extra)
    if "max_tokens" not in body and "max_completion_tokens" not in body:
        body["max_tokens"] = 24
    req = urllib.request.Request(URL, data=json.dumps(body, ensure_ascii=False).encode(), method="POST")
    req.add_header("Content-Type", "application/json")
    req.add_header("Authorization", "Bearer " + gw())
    req.add_header("Accept", "text/event-stream")
    req.add_header("User-Agent", "GBTxiaotudouV8-matrix/1.0")
    t0 = time.time()
    status = None
    lines = []
    text = ""
    err = None
    try:
        with urllib.request.urlopen(req, timeout=240) as resp:
            status = resp.status
            buf = b""
            while True:
                chunk = resp.read(4096)
                if not chunk:
                    break
                buf += chunk
                while b"\n" in buf:
                    line, _, buf = buf.partition(b"\n")
                    s = line.strip().decode("utf-8", "replace")
                    if not s:
                        continue
                    lines.append(s)
                    if s.startswith("data:") and "[DONE]" not in s:
                        try:
                            j = json.loads(s[5:].strip())
                        except Exception:
                            continue
                        for ch in j.get("choices") or []:
                            piece = (ch.get("delta") or {}).get("content")
                            if piece:
                                text += piece
    except urllib.error.HTTPError as e:
        err = "HTTP %s %s" % (e.code, e.read().decode("utf-8", "replace")[:200])
    except Exception as e:  # noqa: BLE001
        err = "%s: %s" % (type(e).__name__, e)
    tail = " ".join(lines[-4:])
    has_finish = '"finish_reason":"stop"' in tail or '"finish_reason": "stop"' in tail
    return {"variant": name, "status": status, "ms": int((time.time() - t0) * 1000),
            "lines": len(lines), "chars": len(text), "text": text[:30],
            "finish_in_tail": has_finish, "err": err,
            "tail": tail[:160]}


def main():
    rows = []
    for name, extra in VARIANTS.items():
        r = run(name, extra)
        rows.append(r)
        print(json.dumps(r, ensure_ascii=False), flush=True)
    print("\n=== 人话表 ===")
    print("%-22s %6s %7s %6s %6s %8s  %s" % ("variant", "status", "ms", "lines", "chars", "finish?", "err"))
    bad = 0
    for r in rows:
        if r["err"] or not r["finish_in_tail"]:
            bad += 1
        print("%-22s %6s %7d %6d %6d %8s  %s" % (
            r["variant"], r["status"], r["ms"], r["lines"], r["chars"],
            r["finish_in_tail"], (r["err"] or "")[:60]))
    print("\n坏档 %d/%d" % (bad, len(rows)))
    return 0 if bad == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
