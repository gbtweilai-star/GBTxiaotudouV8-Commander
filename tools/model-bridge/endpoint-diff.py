#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""只读：并排两条端点的全部关键配置，找出"这条起不来、那条在跑"的差异点。"""
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
EPS = ["qnnqf9w8xcefj8", "7b5inowyar12yh"]
LABEL = {"qnnqf9w8xcefj8": "gbt-v8-live(起不来)", "7b5inowyar12yh": "gbt-v8-uncensored(在跑)"}


def key():
    t = open(CRED, encoding="utf-8").read() if os.path.isfile(CRED) else ""
    m = re.search(r"GBT_POTATO_API_KEY:[ \t]*(?:ref:)?[ \t]*[\"']?([A-Za-z0-9_\-]{16,})", t)
    return m.group(1) if m else os.environ.get("GBT_POTATO_API_KEY")


def get(url, k, to=25):
    req = urllib.request.Request(url, headers={"Authorization": "Bearer " + k,
                                               "User-Agent": "gbt-diff/1.0"})
    with urllib.request.urlopen(req, timeout=to) as r:
        return json.loads(r.read(400000).decode("utf-8", "replace"))


k = key()
info = {}
for eid in EPS:
    e = get("https://rest.runpod.io/v1/endpoints/%s" % eid, k)
    t = {}
    tid = e.get("templateId") or (e.get("template") or {}).get("id")
    if tid:
        try:
            t = get("https://rest.runpod.io/v1/templates/%s" % tid, k)
        except Exception as ex:  # noqa: BLE001
            t = {"_err": str(ex)[:80]}
    info[eid] = (e, t)

FIELDS = ["workersMin", "workersMax", "idleTimeout", "flashboot", "scalerType", "scalerValue",
          "gpuTypeIds", "gpuCount", "networkVolumeId", "executionTimeoutMs", "version"]
print("%-22s %-34s %-34s" % ("字段", LABEL[EPS[0]], LABEL[EPS[1]]))
for f in FIELDS:
    a = str(info[EPS[0]][0].get(f))
    b = str(info[EPS[1]][0].get(f))
    mark = "  <<< 不同" if a != b else ""
    print("%-22s %-34s %-34s%s" % (f, a[:32], b[:32], mark))

print("\n%-22s %-34s %-34s" % ("模板字段", LABEL[EPS[0]], LABEL[EPS[1]]))
for f in ["templateId", "imageName", "containerDiskInGb", "volumeMountPath", "ports",
          "isServerless", "startJupyter", "startSsh"]:
    a = str(info[EPS[0]][1].get(f) if info[EPS[0]][1].get(f) is not None
            else info[EPS[0]][0].get(f))
    b = str(info[EPS[1]][1].get(f) if info[EPS[1]][1].get(f) is not None
            else info[EPS[1]][0].get(f))
    mark = "  <<< 不同" if a != b else ""
    print("%-22s %-34s %-34s%s" % (f, a[:32], b[:32], mark))

print("\n%-22s %-34s %-34s" % ("env", LABEL[EPS[0]], LABEL[EPS[1]]))
ea = info[EPS[0]][1].get("env") or {}
eb = info[EPS[1]][1].get("env") or {}
for kk in sorted(set(ea) | set(eb)):
    va, vb = str(ea.get(kk)), str(eb.get(kk))
    mark = "  <<< 不同" if va != vb else ""
    print("%-22s %-34s %-34s%s" % (kk, va[:32], vb[:32], mark))
