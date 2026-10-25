# -*- coding: utf-8 -*-
"""实测「万能插」与「亿万触手」的真实数据出口，全部走 run_task 正规入口。"""
import json
import sys
import time
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:  # noqa: BLE001
    pass

BASE = next(p for p in Path(__file__).resolve().parents
            if (p / "gbt_allinone").is_dir())   # 修：原 `.parent.parent` 只到 tools/（少一层）
sys.path.insert(0, str(BASE))
OUT = BASE / ".scratch" / "plug_tentacle_probe.json"
from gbt_allinone import api as API  # noqa: E402

res = {}


def call(tag, kind, payload):
    t0 = time.time()
    try:
        r = API.run_task(kind, payload)
        env = (r or {}).get("gbt_result") or r or {}
        res[tag] = {"kind": kind, "payload": payload, "ms": int((time.time() - t0) * 1000),
                    "status": env.get("status"), "result": env.get("result"), "error": env.get("error"),
                    "denied": env.get("denied"), "missing": env.get("missing")}
    except Exception as exc:  # noqa: BLE001
        res[tag] = {"kind": kind, "payload": payload, "ms": int((time.time() - t0) * 1000),
                    "error": "%s: %s" % (type(exc).__name__, str(exc)[:280])}


# 万能插
call("wf_status", "wf_status", {"include_workflows": True})
call("wf_status_plain", "wf_status", {})
call("transfer_unique", "transfer", {"op": "unique", "data": [3, 1, 3, 2, 1]})
call("transfer_stats", "transfer", {"op": "stats", "data": [1, 2, 3, 4, 5]})
call("sched_status", "sched_status", {})

# 亿万触手
call("tentacle_manifest", "tentacle_manifest", {})
call("tentacle_status", "tentacle_status", {})
call("tentacle_caps", "tentacle", {"op": "caps"})
call("coverage_auditor", "coverage_auditor", {})

OUT.write_text(json.dumps(res, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
for k, v in res.items():
    body = json.dumps(v.get("result") or v.get("error"), ensure_ascii=False, default=str)
    print("[%s] %sms status=%s%s" % (k, v.get("ms"), v.get("status"),
                                     " denied=" + str(v.get("missing")) if v.get("denied") else ""))
    print("    " + body[:460])
print("写出:", OUT)
