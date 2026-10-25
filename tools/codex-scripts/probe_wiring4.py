# -*- coding: utf-8 -*-
"""接线全量 · 取对字段名。只读。"""
import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:  # noqa: BLE001
    pass

from gbt_allinone import api  # noqa: E402

res = api.run_task("caps_called_audit", {}, safe=True, probe=True)
d = res.get("result", res)
if "result" in d:
    d = d["result"]

for k in ("total", "wired_count", "orphan_count", "scanned_files", "default_type", "rule"):
    print("%-16s %s" % (k, str(d.get(k))[:190]))
print("cap_types      :", d.get("cap_types"))
print("readonly       :", len(d.get("readonly") or []))
print("external_entries:", len(d.get("external_entries") or []))

unwired = d.get("unwired_by_name") or []
selfref = d.get("self_ref_only") or []
orphans = d.get("orphans") or []
print("\n★ unwired_by_name: %d 个" % len(unwired))
print("★ self_ref_only  : %d 个" % len(selfref))
print("★ orphans        : %d 个" % len(orphans))

rows = api.list_capabilities()
by = {r["name"]: r for r in rows}

print("\n" + "=" * 92)
print("未接线名单（这就是要挨个接上的）")
print("=" * 92)
dom = Counter()
for item in (unwired + selfref):
    k = item if isinstance(item, str) else (item.get("kind") or item.get("name"))
    r = by.get(k, {})
    dom[r.get("domain")] += 1
    extra = "" if isinstance(item, str) else json.dumps(
        {x: y for x, y in item.items() if x not in ("kind", "name")}, ensure_ascii=False)[:90]
    print("  %-26s %-13s %-9s %s" % (k, r.get("domain"), r.get("status"), extra))
    print("        %s" % (r.get("desc") or "")[:104])
print("\n未接线域分布:", dict(dom.most_common()))

print("\n" + "=" * 92)
print("orphans 明细（若有）")
print("=" * 92)
for o in orphans[:40]:
    print("  ", json.dumps(o, ensure_ascii=False)[:170])

json.dump(d, open(Path(__file__).resolve().parent / "wiring_full.json", "w", encoding="utf-8"),
          ensure_ascii=False, indent=1)
print("\n写出: wiring_full.json")
