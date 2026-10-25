# -*- coding: utf-8 -*-
"""缺口域真调探测：看哪些缺口能力能给出真数据（决定面板能画到什么程度）。"""
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
OUT = BASE / ".scratch" / "gap_probe.json"
from gbt_allinone import api as API  # noqa: E402

res = {}


def call(tag, kind, payload=None):
    t0 = time.time()
    try:
        r = API.run_task(kind, payload or {})
        env = (r or {}).get("gbt_result") or r or {}
        res[tag] = {"kind": kind, "ms": int((time.time() - t0) * 1000),
                    "status": env.get("status"), "denied": env.get("denied"),
                    "missing": env.get("missing"), "error": env.get("error"),
                    "result": env.get("result")}
    except Exception as exc:  # noqa: BLE001
        res[tag] = {"kind": kind, "ms": int((time.time() - t0) * 1000),
                    "error": "%s: %s" % (type(exc).__name__, str(exc)[:200])}


# 镜像 / 管线（最大缺口）
for k, p in [("mirror_status", {}), ("mirror_scan", {}), ("pipeline_status", {}),
             ("svc_inspect", {}), ("deploy_queue", {"op": "status"}), ("ghost_guard", {})]:
    call(k, k, p)
# llm 未覆盖
for k, p in [("codex_status", {}), ("codex_models", {}), ("llm_status", {}),
             ("model_key_pool", {}), ("prompt_bridge", {"op": "status"})]:
    call(k, k, p)
# 心智
for k, p in [("mind", {}), ("brain_vault", {"op": "status"}), ("local_brain", {}),
             ("meta_cognition", {}), ("director_mood", {}), ("auto_switch", {})]:
    call(k, k, p)
# 情报 / 创作 / 安全 / 吞噬
for k, p in [("topic_watch", {}), ("trend_watch", {}), ("verification_watch", {}),
             ("scene_anchor", {}), ("code_art", {}), ("brand_outro", {}),
             ("sec_scan", {}), ("sec_surface", {}),
             ("devour_scan", {}), ("devour_reflect", {})]:
    call(k, k, p)
# 工具 / 长程 / 门 / 项目 / 生命 / 量化
for k, p in [("capability_net", {}), ("projection_card", {}), ("awesome_tools_index", {}),
             ("lr_status", {}), ("gate_visibility", {}), ("project_context", {}),
             ("life", {}), ("quant", {})]:
    call(k, k, p)

OUT.write_text(json.dumps(res, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
print("%-22s %-8s %-10s %s" % ("能力", "耗时", "状态", "返回摘要"))
for k, v in res.items():
    st = v.get("status") or ("denied" if v.get("denied") else ("ERR" if v.get("error") else "?"))
    body = json.dumps(v.get("result") or v.get("error") or v.get("missing"), ensure_ascii=False, default=str)
    print("%-22s %-8s %-10s %s" % (k, str(v.get("ms")) + "ms", st, body[:120]))
print("写出:", OUT)
