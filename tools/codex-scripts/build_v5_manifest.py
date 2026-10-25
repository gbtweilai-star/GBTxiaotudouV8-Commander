# -*- coding: utf-8 -*-
"""V5 数据层：V4 真读数 + 大脑执行层五维实测。
产出 .scratch/v5_manifest.json
大脑数据来自真实调用（.scratch/brain_probe*.json），不是示意。
"""
import json
import re
import time
from pathlib import Path

BASE = next(p for p in Path(__file__).resolve().parents
            if (p / "gbt_allinone").is_dir())   # 修：原 `.parent.parent` 只到 tools/（少一层）
OUT = BASE / ".scratch" / "v5_manifest.json"

M = json.loads((BASE / ".scratch" / "v4_manifest.json").read_text(encoding="utf-8"))
P1 = json.loads((BASE / ".scratch" / "brain_probe.json").read_text(encoding="utf-8"))
P2 = json.loads((BASE / ".scratch" / "brain_probe2.json").read_text(encoding="utf-8"))


def R(d, key):
    return (d.get(key) or {}).get("result") or {}


health = R(P1, "brain_health")
execute = R(P1, "brain_execute")
verify = R(P1, "brain_verify")

routes = []
for k, v in P2.items():
    if k.startswith("brain_route|"):
        intent = json.loads(k.split("|", 1)[1])["intent"]
        r = v.get("result") or {}
        routes.append({
            "intent": intent,
            "best": (r.get("best") or {}).get("kind"),
            "best_domain": (r.get("best") or {}).get("domain"),
            "alternatives": [a.get("kind") for a in (r.get("alternatives") or [])],
            "candidates": r.get("candidates"),
            "path": r.get("path"),
            "degraded": bool(r.get("degraded")),
            "degraded_reason": r.get("degraded_reason"),
            "ms": round(float(r.get("elapsed_ms") or 0), 1),
        })

unify = {}
for k, v in P2.items():
    if k.startswith("brain_unify|") and (v.get("result") or {}).get("ok"):
        unify = v["result"]
        break

# 真实审计总量（从 brain_health 的 detail 里取真值，回退到文件行数估算）
audit_total = None
for d in (health.get("dims") or {}).values():
    m = re.search(r"审计\s*(\d+)", str(d.get("detail") or ""))
    if m:
        audit_total = int(m.group(1))
if audit_total is None:
    audit_total = M.get("audit_lines_scanned")

M["brain"] = {
    "probed_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
    "health": {
        "score": health.get("score"), "healthy": health.get("healthy_dims"),
        "total": health.get("total_dims"), "ms": round(float(health.get("elapsed_ms") or 0), 1),
        "dims": [{"key": k, "ok": bool(v.get("ok")), "detail": v.get("detail")}
                 for k, v in (health.get("dims") or {}).items()],
    },
    "routes": routes,
    "execute": {
        "kind": execute.get("kind"), "ok": execute.get("ok"),
        "platform": (execute.get("result") or {}).get("platform"),
        "python": (execute.get("result") or {}).get("python"),
        "at": (execute.get("result") or {}).get("time"),
        "ms": round(float(execute.get("elapsed_ms") or 0), 1),
    },
    "verify": {
        "ok": verify.get("ok"),
        "vision_ok": ((verify.get("checks") or {}).get("vision") or {}).get("ok"),
        "fingerprint": ((verify.get("checks") or {}).get("vision") or {}).get("fingerprint"),
        "size": ((verify.get("checks") or {}).get("vision") or {}).get("size"),
        "ms": round(float(verify.get("elapsed_ms") or 0), 1),
    },
    "unify": {
        "goal": unify.get("goal"), "kind": unify.get("kind"),
        "elapsed_s": unify.get("elapsed_s"),
        "route": unify.get("chain", {}).get("route"),
        "execute": unify.get("chain", {}).get("execute"),
        "verify": unify.get("chain", {}).get("verify"),
        "health": unify.get("chain", {}).get("health"),
        "note": unify.get("note"),
    },
    "audit_total": audit_total,
}

OUT.write_text(json.dumps(M, ensure_ascii=False, indent=1), encoding="utf-8")
print("写出:", OUT)
b = M["brain"]
print("健康维: score=%s %s/%s · %sms" % (b["health"]["score"], b["health"]["healthy"], b["health"]["total"], b["health"]["ms"]))
for d in b["health"]["dims"]:
    print("   -", d["key"], d["ok"], str(d["detail"])[:60])
print("路由维:", [(r["intent"], r["best"], r["candidates"], r["path"], r["degraded"]) for r in b["routes"]])
print("执行维:", b["execute"])
print("验证维:", b["verify"])
print("合一  :", b["unify"]["kind"], b["unify"]["elapsed_s"], "s")
print("审计总量:", b["audit_total"])
