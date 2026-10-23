#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""F25 抢救实验三（主人批的「甲」）：把模板推一个新版本，逼端点重建 worker 定义，然后看 worker 起不起来。

做法：PATCH 模板 `containerDiskInGb` 30→31（一次真实变更 ⇒ 模板升版），再立刻改回 30（再升一版）。
      两次都只改这一个无害字段，不动镜像/环境变量/端口。然后 PATCH 端点指向同一模板（触发重读），
      再发一个 /run，轮询 150 秒。
失败即如实报「甲 无效」，并给出「乙 重建端点 / 丙 借在跑那条」的下一步。
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
TPL = "e4iwgiqa7t"
REST_EP = "https://rest.runpod.io/v1/endpoints/%s" % EP
REST_TPL = "https://rest.runpod.io/v1/templates/%s" % TPL
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

print("① 模板升版：containerDiskInGb 30 → 31")
st, ms, txt = call(REST_TPL, k, "PATCH", {"containerDiskInGb": 31})
print("   status=%s (%dms)" % (st, ms))
if st != 200:
    print("   失败：", txt[:300])
    sys.exit(1)
ver1 = None
try:
    ver1 = (json.loads(txt) or {}).get("version")
except ValueError:
    pass
print("   新版本 =", ver1)

print("② 改回 30（再升一版，保持磁盘不变）")
st, ms, txt = call(REST_TPL, k, "PATCH", {"containerDiskInGb": 30})
ver2 = None
try:
    ver2 = (json.loads(txt) or {}).get("version")
except ValueError:
    pass
print("   status=%s · 版本 =%s" % (st, ver2))

print("③ 端点指向同模板（触发重读）")
st, ms, txt = call(REST_EP, k, "PATCH", {"templateId": TPL, "workersMin": 1, "workersMax": 1,
                                        "idleTimeout": 600})
print("   status=%s" % st)

print("④ 发 /run 逼拉起")
st, ms, txt = call(RUN, k, "POST", {"input": {"prompt": "ping", "max_tokens": 8}}, to=40)
print("   /run status=%s body=%s" % (st, txt[:120]))

print("⑤ 轮询 180 秒")
t0 = time.time()
ok = False
while time.time() - t0 < 180:
    h = health(k)
    if h:
        print("   t+%3ds ready=%d running=%d init=%d q=%d"
              % (int(time.time() - t0), h["ready"], h["running"], h["init"], h["inQueue"]), flush=True)
        if h["ready"] + h["running"] > 0:
            ok = True
            break
    time.sleep(15)

if ok:
    print("\n✅ 甲 生效：模板升版后 worker 起来了")
    sys.exit(0)

print("\n❌ 甲 无效（升版后 180 秒仍 0 worker）⇒ 建议 乙 重建端点 / 丙 临时借在跑那条")
print("   现读：", health(k))
sys.exit(1)
