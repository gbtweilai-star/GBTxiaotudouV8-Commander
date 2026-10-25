# -*- coding: utf-8 -*-
"""抓 /api/events 的原始 SSE 事件，看 cap_result 到底长什么样。

主进程侧 settleCapPending 目前按 ev.request_id 找 —— 如果发布器把字段
包进 data/meta 里，就永远匹配不上（超时的真因）。
"""
import json
import sys
import threading
import time
import urllib.request
from pathlib import Path

ROOT = next(p for p in Path(__file__).resolve().parents
            if (p / "holo_pet_w3").is_dir() and (p / "gbt_allinone").is_dir())
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

events = []


def listen(seconds=25):
    try:
        req = urllib.request.Request("http://127.0.0.1:8765/api/events")
        with urllib.request.urlopen(req, timeout=seconds + 5) as r:
            buf = ""
            t0 = time.time()
            while time.time() - t0 < seconds:
                chunk = r.read(1)
                if not chunk:
                    break
                buf += chunk.decode("utf-8", "replace")
                while "\n\n" in buf:
                    block, buf = buf.split("\n\n", 1)
                    if block.startswith("data: "):
                        try:
                            events.append(json.loads(block[6:]))
                        except Exception:
                            events.append({"_raw": block[:200]})
    except Exception as e:  # noqa: BLE001
        events.append({"_listen_error": str(e)})


th = threading.Thread(target=listen, daemon=True)
th.start()
time.sleep(2.0)

# 触发一次能力调用
body = json.dumps({"kind": "coverage_auditor", "payload": {}, "confirm": True}).encode()
req = urllib.request.Request("http://127.0.0.1:8765/api/capability", data=body,
                             headers={"Content-Type": "application/json"}, method="POST")
with urllib.request.urlopen(req, timeout=20) as r:
    posted = json.loads(r.read().decode())
print("POST 返回:", json.dumps(posted, ensure_ascii=False))
rid = posted.get("request_id")

th.join(timeout=24)

print("\n收到 %d 个事件" % len(events))
from collections import Counter  # noqa: E402
print("事件类型分布:", dict(Counter(str(e.get("event") or e.get("type") or "?") for e in events)))
print()
for e in events:
    if rid and rid in json.dumps(e, ensure_ascii=False):
        print("=== 命中 request_id=%s 的事件 ===" % rid)
        print(json.dumps(e, ensure_ascii=False)[:1200])
        break
else:
    print("=== 没有任何事件带 request_id=%s ===" % rid)
    for e in events[:6]:
        print("  ", json.dumps(e, ensure_ascii=False)[:300])
