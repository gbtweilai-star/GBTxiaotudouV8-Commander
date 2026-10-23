# -*- coding: utf-8 -*-
"""看清 list_capabilities 的真实字段，并定位「接线缺口」的口径出处。只读。"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:  # noqa: BLE001
    pass

from gbt_allinone import api  # noqa: E402

rows = api.list_capabilities()
print("样本 3 条：")
for r in rows[:3]:
    print("  ", json.dumps(r, ensure_ascii=False)[:400])

fields = sorted({k for r in rows for k in r})
print("\n全部字段:", fields)

print("\n" + "=" * 84)
print("自扫描（selfscan）—— 接线口径的真实出处")
print("=" * 84)
try:
    s = api.run_task("selfscan", {}, safe=True, probe=True)
    print(json.dumps(s, ensure_ascii=False, indent=1)[:2600])
except Exception as e:  # noqa: BLE001
    print("selfscan 失败:", type(e).__name__, e)

for k in ("caps_called_audit", "gate_visibility", "framework_gate"):
    print("\n--- %s ---" % k)
    try:
        r = api.run_task(k, {}, safe=True, probe=True)
        print(json.dumps(r, ensure_ascii=False, indent=1)[:1200])
    except Exception as e:  # noqa: BLE001
        print("  失败:", type(e).__name__, str(e)[:200])
