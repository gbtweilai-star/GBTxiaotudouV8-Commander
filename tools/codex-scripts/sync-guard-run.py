# gbt-capability: sync_guard
# 开发者：自由的风 · 永久钢印 · 禁止删除
"""sync-guard-run.py — 一行跑巡检（给 sync-guard-patrol.ps1 / 计划任务用）。

用法：
  py -B -X utf8 tools/codex-scripts/sync-guard-run.py <repo_root> [delivery] [--with-sched]
退出码：ALIGNED=0，DRIFT=1（计划任务里就是红/绿）。
--with-sched：巡检完顺手跑一次 sched_tick（到期工作流执行），共用同一个心跳。
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

raw = sys.argv[1:]
flags = {a for a in raw if a.startswith("--")}
args = [a for a in raw if not a.startswith("--")]
root = str(Path(args[0]).resolve()) if args else str(Path(__file__).resolve().parents[2])
delivery = args[1] if len(args) > 1 else ""
sys.path.insert(0, root)
from gbt_allinone import api  # noqa: E402

payload = {"op": "patrol", "record": True, "notify": True}
if delivery:
    payload["delivery"] = delivery
r = api.run_task("sync_guard", payload)
inner = (r.get("gbt_result") or {}).get("result") or {}
out = {"ok": inner.get("ok"), "verdict": inner.get("verdict"),
       "alerts": inner.get("alerts"), "record": inner.get("record"),
       "notified": inner.get("notified"), "pushed": inner.get("pushed"),
       "reading": inner.get("reading")}
try:
    sr = api.run_task("sched_tick", {})
    s = (sr.get("gbt_result") or {}).get("result") or sr or {}
    out["sched"] = {"ran": s.get("ran"), "count": s.get("count")}
except Exception as e:  # noqa: BLE001
    out["sched"] = {"error": "%s: %s" % (type(e).__name__, str(e)[:120])}
print(json.dumps(out, ensure_ascii=False, indent=1))
sys.exit(0 if inner.get("verdict") == "ALIGNED" else 1)
