#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""只读：GPU 现货 + 模板 env 结构（定位 F25 到底是"没容量"还是"卷/模板问题"）。"""
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
WANT = {"NVIDIA GeForce RTX 4090", "NVIDIA RTX A5000", "NVIDIA L4", "NVIDIA L40S", "NVIDIA A40"}


def key():
    t = open(CRED, encoding="utf-8").read() if os.path.isfile(CRED) else ""
    m = re.search(r"GBT_POTATO_API_KEY:[ \t]*(?:ref:)?[ \t]*[\"']?([A-Za-z0-9_\-]{16,})", t)
    return m.group(1) if m else os.environ.get("GBT_POTATO_API_KEY")


def get(url, k, to=30):
    req = urllib.request.Request(url, headers={"Authorization": "Bearer " + k,
                                               "User-Agent": "gbt-stock/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=to) as r:
            return r.status, r.read(200000).decode("utf-8", "replace")
    except Exception as e:  # noqa: BLE001
        return type(e).__name__, str(e)[:200]


k = key()
if not k:
    print("拿不到钥")
    sys.exit(2)

st, txt = get("https://rest.runpod.io/v1/gpus", k)
print("GPU 目录 status=%s · %d 字节" % (st, len(txt)))
try:
    data = json.loads(txt)
except ValueError:
    print("读不到 JSON：", txt[:200])
    data = []
rows = data if isinstance(data, list) else (data.get("data") or data.get("items") or [])
print("总型号 %d" % len(rows))
seen = 0
for g in rows:
    name = str(g.get("displayName") or g.get("id") or "")
    if name not in WANT:
        continue
    seen += 1
    print("  %-28s id=%-10s stock=%s secure=%s community=%s"
          % (name, g.get("id"),
             g.get("stockStatus") or g.get("availability"),
             g.get("secureCloud"), g.get("communityCloud")))
if seen == 0:
    print("  ⚠️ 5 个目标型号在 /v1/gpus 里一个都没匹配上（可能是字段名不同，下面打一条原样样本）")
    if rows:
        print("  样本键：", sorted(rows[0].keys()))
        print("  样本：", json.dumps(rows[0], ensure_ascii=False)[:400])

st2, txt2 = get("https://rest.runpod.io/v1/templates/e4iwgiqa7t", k)
print("\n模板 e4iwgiqa7t status=%s" % st2)
try:
    t = json.loads(txt2)
    print("  键：", sorted(t.keys()))
    print("  env:", json.dumps(t.get("env"), ensure_ascii=False)[:300])
    print("  image:", t.get("imageName") or t.get("image"))
    print("  containerDiskInGb:", t.get("containerDiskInGb"))
except ValueError:
    print("  读不到：", txt2[:200])
