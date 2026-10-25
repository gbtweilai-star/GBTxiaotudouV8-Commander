# -*- coding: utf-8 -*-
"""探明接线现状：140 个可执行能力里，哪些没接上（routed but not wired）、
5 个接线缺口具体是什么。只读，不改任何文件。"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:  # noqa: BLE001
    pass

from gbt_allinone import api  # noqa: E402

print("=" * 84)
print("接线现状（只读探针，全程走 api.run_task / api.list_capabilities）")
print("=" * 84)

caps = api.list_capabilities()
print("list_capabilities 返回类型:", type(caps).__name__)
if isinstance(caps, dict):
    print("顶层键:", list(caps.keys())[:12])

rows = caps.get("capabilities") if isinstance(caps, dict) else caps
if isinstance(rows, dict):
    rows = [dict(v, name=k) for k, v in rows.items()]
print("能力条目数:", len(rows))

unwired = [r for r in rows if not r.get("wired", True)]
print("\n● 未接线（wired=false）: %d 个" % len(unwired))
for r in unwired:
    print("   %-24s domain=%-14s status=%-10s handler=%s" % (
        r.get("name"), r.get("domain"), r.get("status"), r.get("handler")))

# 按域统计
from collections import Counter  # noqa: E402
dom = Counter(r.get("domain") for r in rows)
print("\n● 域分布:", dict(dom.most_common()))

# 状态分布
print("● 状态分布:", dict(Counter(r.get("status") for r in rows)))

# 逐一试跑 status 类能力，看谁真的能跑
print("\n" + "=" * 84)
print("逐个探活（只调 status/只读类，不碰写操作）")
print("=" * 84)
READ_ONLY = [r["name"] for r in rows if r.get("status") == "readonly"][:80]
ok, fail = [], []
for name in READ_ONLY:
    try:
        res = api.run_task(name, {}, safe=True, probe=True)
        good = isinstance(res, dict) and res.get("ok", True) is not False
        (ok if good else fail).append((name, res if not good else None))
    except Exception as e:  # noqa: BLE001
        fail.append((name, "%s: %s" % (type(e).__name__, e)))
print("只读能力 %d 个：跑通 %d · 失败 %d" % (len(READ_ONLY), len(ok), len(fail)))
for n, e in fail[:30]:
    print("   ✗ %-26s %s" % (n, str(e)[:110]))
