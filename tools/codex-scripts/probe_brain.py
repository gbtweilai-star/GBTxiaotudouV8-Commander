# -*- coding: utf-8 -*-
"""探测「大脑执行层」五维能否真调，拿到真读数就给可视化用（拿不到就如实标注）。
只调只读/自检类：brain_health / brain_route；brain_execute 只喂最安全的 health。
"""
import json
import sys
import time
from pathlib import Path

BASE = next(p for p in Path(__file__).resolve().parents
            if (p / "gbt_allinone").is_dir())   # 修：原 `.parent.parent` 只到 tools/（少一层）
sys.path.insert(0, str(BASE))
OUT = BASE / ".scratch" / "brain_probe.json"

from gbt_allinone import api as API  # noqa: E402

results = {}


def call(kind, payload, safe=True, note=""):
    t0 = time.time()
    try:
        r = API.run_task(kind, payload, safe=safe)
        env = (r or {}).get("gbt_result") or r or {}
        results[kind] = {"ok": True, "ms": int((time.time() - t0) * 1000),
                         "status": env.get("status"), "result": env.get("result"),
                         "error": env.get("error"), "note": note}
    except Exception as exc:  # noqa: BLE001
        results[kind] = {"ok": False, "ms": int((time.time() - t0) * 1000),
                         "error": "%s: %s" % (type(exc).__name__, str(exc)[:300]), "note": note}


call("brain_health", {}, note="健康维：五维自检评分")
call("brain_route", {"goal": "把项目里没接线的能力找出来"}, note="路由维：意图→能力")
call("brain_execute", {"kind": "health"}, note="执行维：直调一个只读能力")
call("brain_verify", {}, note="验证维：需要实机屏幕与 UIA")

OUT.write_text(json.dumps(results, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
for k, v in results.items():
    head = json.dumps(v.get("result"), ensure_ascii=False, default=str)
    print("[%s] ok=%s %sms status=%s" % (k, v.get("ok"), v.get("ms"), v.get("status")))
    print("    result:", head[:420])
    if v.get("error"):
        print("    error :", str(v["error"])[:220])
print("写出:", OUT)
