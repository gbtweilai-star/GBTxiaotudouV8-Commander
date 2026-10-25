# -*- coding: utf-8 -*-
"""取接线全量：wired / orphan 两张清单 + 每个 orphan 的域与说明。只读。"""
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
data = res.get("result", res)
if "result" in data:
    data = data["result"]
print("字段:", sorted(data.keys()))
wired = data.get("wired") or []
orphan = data.get("orphan") or []
entries = data.get("entries") or []
print("\n已接线 wired: %d" % len(wired))
print("孤儿 orphan: %d" % len(orphan))
print("其他 entries: %d" % len(entries))
for k in ("total", "n_wired", "n_orphan", "summary", "note"):
    if k in data:
        print("%s = %s" % (k, str(data[k])[:200]))

print("\n" + "=" * 88)
print("孤儿能力逐个（未接线 —— 这就是要挨个接上的名单）")
print("=" * 88)
rows = api.list_capabilities()
by = {r["name"]: r for r in rows}
dom = Counter()
for o in orphan[:80]:
    k = o.get("kind") or o.get("name")
    r = by.get(k, {})
    dom[r.get("domain")] += 1
    print("  %-26s %-14s called_by=%s  %s" % (
        k, r.get("domain"), o.get("called_by"), (r.get("desc") or "")[:66]))
print("\n孤儿域分布:", dict(dom.most_common()))

json.dump({"wired": wired, "orphan": orphan, "entries": entries},
          open(Path(__file__).resolve().parent / "wiring_full.json", "w", encoding="utf-8"),
          ensure_ascii=False, indent=1)
print("\n写出: wiring_full.json")
