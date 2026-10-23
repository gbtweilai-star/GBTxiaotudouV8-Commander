#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""F25 抢救实验二：把 live 的 workersMin 降到 0（对齐那条在跑的端点），再真发一个 /run 逼它按需拉起。

依据（现读差异，见 endpoint-diff.py）：
  · 两条端点**同模板同镜像同 MODEL_NAME 同网络卷**；
  · `gbt-v8-uncensored`（workersMin=0）**running=1 在跑**；`gbt-v8-live`（workersMin=1）**0 worker、队列 10**。
  ⇒ 假设：`workersMin=1` 的最小保活拉起在这个账号/型号组合下静默失败，而**按需拉起是好的**。
本件只做两件事：PATCH workersMin=0 → POST /run → 轮询；成功就把读数留下，失败就把 workersMin 恢复成 1。
"""
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        pass

CRED = os.path.expanduser(r"~\.dsh\.credentials.yaml")
EP = "qnnqf9w8xcefj8"
REST = "https://rest.runpod.io/v1/endpoints/%s" % EP
RUN = "https://api.runpod.ai/v2/%s/run" % EP
HEALTH = "https://api.runpod.ai/v2/%s/health" % EP


def key():
    t = open(CRED, encoding="utf-8").read() if os.path.isfile(CRED) else ""
    m = re.search(r"GBT_POTATO_API_KEY:[ \t]*(?:ref:)?[ \t]*[\"']?([A-Za-z0-9_\-]{16,})", t)
    return m.group(1) if m else os.environ.get("GBT_POTATO_API_KEY")


def call(url, k, method="GET", body=None, to=40):
    data = json.dumps(body).encode("utf-8") if body is not None else None
    hdr = {"Authorization": "Bearer " + k, "User-Agent": "gbt-rescue/1.0",
           "Content-Type": "application/json"}
    req = urllib.request.Request(url, data=data, headers=hdr, method=method)
    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=to) as r:
            return r.status, round((time.time() - t0) * 1000), r.read(4000).decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, round((time.time() - t0) * 1000), e.read(800).decode("utf-8", "replace")
    except Exception as e:  # noqa: BLE001
        return type(e).__name__, round((time.time() - t0) * 1000), str(e)[:200]


def health(k):
    st, ms, txt = call(HEALTH, k, to=15)
    if isinstance(st, str):
        return None
    try:
        j = json.loads(txt)
    except ValueError:
        return None
    w = j.get("workers") or {}
    return {"ready": int(w.get("ready") or 0), "running": int(w.get("running") or 0),
            "init": int(w.get("initializing") or 0),
            "inQueue": int((j.get("jobs") or {}).get("inQueue") or 0)}


k = key()
if not k:
    print("拿不到钥")
    sys.exit(2)

print("① PATCH workersMin=0（对齐在跑那条）")
st, ms, txt = call(REST, k, "PATCH", {"workersMin": 0})
print("   status=%s (%dms)" % (st, ms))

print("② 真发一个 /run（逼按需拉起）")
payload = {"input": {"prompt": "ping", "max_tokens": 8, "stream": False}}
st, ms, txt = call(RUN, k, "POST", payload, to=40)
print("   /run status=%s (%dms) body=%s" % (st, ms, txt[:200]))
job_id = None
try:
    job_id = (json.loads(txt) or {}).get("id")
except ValueError:
    pass

print("③ 轮询 150 秒")
t0 = time.time()
ok = False
while time.time() - t0 < 150:
    h = health(k)
    el = int(time.time() - t0)
    if h:
        print("   t+%3ds ready=%d running=%d init=%d q=%d"
              % (el, h["ready"], h["running"], h["init"], h["inQueue"]), flush=True)
        if h["ready"] + h["running"] > 0:
            ok = True
            break
    time.sleep(15)

if ok:
    print("\n✅ 按需拉起成功 ⇒ **workersMin=1 的保活拉起是坏的，按需是好的**（保留 workersMin=0）")
    if job_id:
        st, ms, txt = call("https://api.runpod.ai/v2/%s/status/%s" % (EP, job_id), k, to=30)
        print("   job %s status 回执=%s" % (job_id, txt[:300]))
    sys.exit(0)

print("\n❌ 按需也没起来 ⇒ 不是 workersMin 的问题，恢复 workersMin=1 并交回控制台")
st, ms, txt = call(REST, k, "PATCH", {"workersMin": 1})
print("   恢复 PATCH status=%s · 现 health=%s" % (st, health(k)))
sys.exit(1)
