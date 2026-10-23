#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""只读：账号面 + 另一条端点状态（判是不是"账号级并发配额被那条端点占着"）。"""
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
                                               "User-Agent": "gbt-account/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=to) as r:
            return r.status, r.read(400000).decode("utf-8", "replace")
    except Exception as e:  # noqa: BLE001
        return type(e).__name__, str(e)[:160]


k = key()
for path in ("me", "billing", "endpoints/7b5inowyar12yh", "networkvolumes"):
    st, txt = get("https://rest.runpod.io/v1/" + path, k)
    print("== %s => %s" % (path, st))
    try:
        j = json.loads(txt)
        if isinstance(j, dict):
            for kk in ("id", "email", "balance", "creditBalance", "spendPerHr",
                       "maxConcurrentWorkers", "currentSpendPerHr", "machineQuota",
                       "workersMin", "workersMax", "idleTimeout", "name", "size", "dataCenterId"):
                if kk in j:
                    print("   %-22s %s" % (kk, j[kk]))
        else:
            print("   列表 %d 项；首项键=%s" % (len(j), sorted(j[0].keys())[:12] if j else []))
            for it in j[:5]:
                print("   -", json.dumps({x: it.get(x) for x in list(it)[:6]}, ensure_ascii=False)[:200])
    except ValueError:
        print("   ", txt[:200])
