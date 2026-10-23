# -*- coding: utf-8 -*-
"""接线缺口逐个真调：它们是不是真的没实现，还是只是没有被内部调用。只读。"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:  # noqa: BLE001
    pass

from gbt_allinone import api  # noqa: E402

d = api.run_task("caps_called_audit", {}, safe=True, probe=True)
d = d.get("result", d)
if "result" in d:
    d = d["result"]
print("total=%s wired=%s orphan=%s scanned_files=%s"
      % (d.get("total"), d.get("wired_count"), d.get("orphan_count"), d.get("scanned_files")))
print("readonly(类型):", type(d.get("readonly")).__name__, d.get("readonly"))
print("rule:", d.get("rule"))
un = d.get("unwired_by_name")
print("\nunwired_by_name 类型:", type(un).__name__, "值:", json.dumps(un, ensure_ascii=False)[:400])
sr = d.get("self_ref_only")
print("self_ref_only 类型:", type(sr).__name__, "值:", json.dumps(sr, ensure_ascii=False)[:400])

rows = api.list_capabilities()
by = {r["name"]: r for r in rows}
names = d.get("cap_types") or {}
print("\n" + "=" * 92)
print("入口型（external）能力逐个真调 —— 看是「有实现」还是「真缺口」")
print("=" * 92)
for name in names:
    r = by.get(name, {})
    print("\n── %s ── domain=%s status=%s params=%s"
          % (name, r.get("domain"), r.get("status"), r.get("params_hint") or r.get("params")))
    print("   说明: %s" % (r.get("desc") or "")[:150])
    for kw in ({},):
        try:
            res = api.run_task(name, kw, safe=True, probe=True)
            body = res.get("result", res)
            if isinstance(body, dict) and "result" in body:
                body = body["result"]
            txt = json.dumps(body, ensure_ascii=False)
            print("   调用: ok=%s  %s" % (res.get("ok"), txt[:420]))
        except Exception as e:  # noqa: BLE001
            print("   调用: 抛错 %s: %s" % (type(e).__name__, str(e)[:200]))
