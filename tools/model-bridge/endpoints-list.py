#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""只读：列本账号所有端点 + 各自 health（判"是账号级问题"还是"只有这条端点"）。"""
import json
import os
import re
import sys
import urllib.request

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        pass

CRED = os.path.expanduser(r"~\.dsh\.credentials.yaml")


def key():
    t = open(CRED, encoding="utf-8").read() if os.path.isfile(CRED) else ""
    m = re.search(r"GBT_POTATO_API_KEY:[ \t]*(?:ref:)?[ \t]*[\"']?([A-Za-z0-9_\-]{16,})", t)
    return m.group(1) if m else os.environ.get("GBT_POTATO_API_KEY")


def get(url, k, to=25):
    req = urllib.request.Request(url, headers={"Authorization": "Bearer " + k,
                                               "User-Agent": "gbt-stock/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=to) as r:
            return r.status, r.read(400000).decode("utf-8", "replace")
    except Exception as e:  # noqa: BLE001
        return type(e).__name__, str(e)[:200]


k = key()
st, txt = get("https://rest.runpod.io/v1/endpoints", k)
print("端点列表 status=%s" % st)
try:
    data = json.loads(txt)
except ValueError:
    print(txt[:300])
    sys.exit(1)
eps = data if isinstance(data, list) else (data.get("data") or data.get("items") or [])
print("共 %d 个端点" % len(eps))
for e in eps:
    eid = e.get("id")
    h = "-"
    try:
        st2, t2 = get("https://api.runpod.ai/v2/%s/health" % eid, k, to=15)
        j = json.loads(t2)
        w = j.get("workers") or {}
        h = "ready=%s running=%s init=%s q=%s" % (
            w.get("ready"), w.get("running"), w.get("initializing"),
            (j.get("jobs") or {}).get("inQueue"))
    except Exception:  # noqa: BLE001
        pass
    print("  %-18s %-26s min=%s max=%s idle=%s gpus=%s | %s"
          % (eid, e.get("name"), e.get("workersMin"), e.get("workersMax"),
             e.get("idleTimeout"), (e.get("gpuTypeIds") or [])[:2], h))
