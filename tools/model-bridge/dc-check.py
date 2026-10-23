#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""只读：两条端点的数据中心 + 卷挂载（DC 不匹配 ⇒ 卷挂不上 ⇒ 容器起不来 ⇒ 0 worker）。"""
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
EPS = {"qnnqf9w8xcefj8": "live(起不来)", "7b5inowyar12yh": "uncensored(在跑)"}


def key():
    t = open(CRED, encoding="utf-8").read() if os.path.isfile(CRED) else ""
    m = re.search(r"GBT_POTATO_API_KEY:[ \t]*(?:ref:)?[ \t]*[\"']?([A-Za-z0-9_\-]{16,})", t)
    return m.group(1) if m else os.environ.get("GBT_POTATO_API_KEY")


def get(url, k):
    req = urllib.request.Request(url, headers={"Authorization": "Bearer " + k,
                                               "User-Agent": "gbt-dc/1.0"})
    with urllib.request.urlopen(req, timeout=25) as r:
        return json.loads(r.read(400000).decode("utf-8", "replace"))


k = key()
vol = get("https://rest.runpod.io/v1/networkvolumes", k)
vols = vol if isinstance(vol, list) else (vol.get("data") or [])
print("网络卷：")
for v in vols:
    print("  %-14s %-16s DC=%-8s %sGB" % (v.get("id"), v.get("name"),
                                          v.get("dataCenterId"), v.get("size")))
print()
for eid, label in EPS.items():
    e = get("https://rest.runpod.io/v1/endpoints/%s" % eid, k)
    keys = [x for x in e if "ata" in x or "egion" in x or "volume" in x.lower()]
    print("%-18s %s" % (label, eid))
    for kk in sorted(keys):
        print("   %-22s %s" % (kk, e.get(kk)))
