# -*- coding: utf-8 -*-
"""补齐大脑执行层：路由维（intent）与五维合一（brain_unify）。"""
import json
import sys
import time
from pathlib import Path

BASE = next(p for p in Path(__file__).resolve().parents
            if (p / "gbt_allinone").is_dir())   # 修：原 `.parent.parent` 只到 tools/（少一层）
sys.path.insert(0, str(BASE))
OUT = BASE / ".scratch" / "brain_probe2.json"

from gbt_allinone import api as API  # noqa: E402

res = {}


def call(kind, payload):
    t0 = time.time()
    try:
        r = API.run_task(kind, payload, safe=True)
        env = (r or {}).get("gbt_result") or r or {}
        res[kind + "|" + json.dumps(payload, ensure_ascii=False)] = {
            "ms": int((time.time() - t0) * 1000), "status": env.get("status"),
            "result": env.get("result"), "error": env.get("error")}
    except Exception as exc:  # noqa: BLE001
        res[kind + "|" + json.dumps(payload, ensure_ascii=False)] = {
            "ms": int((time.time() - t0) * 1000),
            "error": "%s: %s" % (type(exc).__name__, str(exc)[:200])}


call("brain_route", {"intent": "把项目里没接线的能力找出来"})
call("brain_route", {"intent": "做个镜像预演"})
call("brain_unify", {"goal": "把项目里没接线的能力找出来"})
call("brain_unify", {"intent": "把项目里没接线的能力找出来"})

OUT.write_text(json.dumps(res, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
for k, v in res.items():
    print("== " + k)
    print("   %sms status=%s" % (v.get("ms"), v.get("status")))
    print("   " + json.dumps(v.get("result") or v.get("error"), ensure_ascii=False, default=str)[:600])
print("写出:", OUT)
