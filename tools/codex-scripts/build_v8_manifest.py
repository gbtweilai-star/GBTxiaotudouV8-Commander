# -*- coding: utf-8 -*-
"""V8 数据层（精简版）：只保留面板真正要用的字段，避免把整包结果塞进 HTML。"""
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
S = BASE / ".scratch"
M = json.loads((S / "v7_manifest.json").read_text(encoding="utf-8"))
P = json.loads((S / "gap_probe.json").read_text(encoding="utf-8"))


def R(k, *keep, sub=None):
    """取探测结果并只保留白名单字段（避免把整包塞进前端）。"""
    r = (P.get(k) or {}).get("result") or {}
    out = {x: r.get(x) for x in keep} if keep else dict(r)
    if sub:
        for src_key, dst_key, limit in sub:
            v = r.get(src_key)
            if isinstance(v, dict):
                out[dst_key] = dict(list(v.items())[:limit])
            elif isinstance(v, list):
                out[dst_key] = v[:limit]
            else:
                out[dst_key] = v
    return out


def ms(k):
    return (P.get(k) or {}).get("ms")


svc_raw = ((P.get("svc_inspect") or {}).get("result") or {}).get("services") or {}
svc = {k: {"host": v.get("host"), "port": v.get("port"), "up": v.get("up"),
           "optional": v.get("optional")} for k, v in list(svc_raw.items())[:14]}

recs = (((P.get("pipeline_status") or {}).get("result") or {}).get("records") or [])[:8]
recs = [{"name": r.get("name"), "rec_id": str(r.get("rec_id"))[-12:]} for r in recs]

lr = (P.get("lr_status") or {}).get("result") or {}
tasks = [{"task_id": t.get("task_id"), "status": t.get("status"),
          "descr": (t.get("descr") or t.get("desc") or t.get("description") or "")[:40]}
         for t in (lr.get("tasks") or [])[:8]]

M["gaps"] = {
    "probed_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
    "mirror_pipeline": {
        "mirror_status": R("mirror_status", "dimension", "reality", "dimension_vs_reality"),
        "mirror_scan": R("mirror_scan", "passed", "total", "checks"),
        "pipeline_records": recs,
        "pipeline_n": len((((P.get("pipeline_status") or {}).get("result") or {}).get("records") or [])),
        "services": svc,
        "deploy_queue": R("deploy_queue", "total", "by_status"),
        "ghost_guard": R("ghost_guard", "clean", "checked_at"),
        "ms": {k: ms(k) for k in ("mirror_status", "mirror_scan", "pipeline_status",
                                  "svc_inspect", "deploy_queue", "ghost_guard")},
    },
    "llm_channel": {
        "codex_status": R("codex_status", "connected", "codex_path"),
        "llm_status": R("llm_status", "cap", "status", "key_chain"),
        "model_key_pool": R("model_key_pool", "keys_total", "leases_active", "active_by_owner"),
        "prompt_bridge": R("prompt_bridge", "segments", "external_model", "deps"),
        "codex_models_gate": {"denied": bool((P.get("codex_models") or {}).get("denied")),
                              "missing": (P.get("codex_models") or {}).get("missing") or []},
    },
    "mind_memory": {
        "mind": R("mind", "state", "mood", "expression", "presence", "lesson_count", "history_count"),
        "brain_vault": R("brain_vault", "vault", "notes", "wikilinks", "unresolved"),
        "director_mood": R("director_mood", "emotion", "drive", "intensity", "half_life"),
        "meta_cognition": R("meta_cognition", "red_lines"),
        "auto_switch": R("auto_switch", "threshold", "version"),
    },
    "recon": {
        "trend_watch": R("trend_watch", "chain", "gaps"),
        "verification_watch": R("verification_watch", "groups"),
        "topic_watch_err": (P.get("topic_watch") or {}).get("error"),
    },
    "security": {
        "sec_scan": R("sec_scan", "total", "critical", "high", "medium", "low", "distribution"),
        "sec_surface": R("sec_surface", "attack_surface"),
        "ms": {k: ms(k) for k in ("sec_scan", "sec_surface")},
    },
    "longrun_tools": {
        "lr_progress": lr.get("progress") or {},
        "lr_tasks": tasks,
        "capability_net": R("capability_net", "seven_columns"),
        "projection_card": R("projection_card", "readonly_note", "skill"),
        "awesome": R("awesome_tools_index", "core", "kind"),
    },
    "creation_devour": {
        "scene_anchor": R("scene_anchor", "classes"),
        "code_art": R("code_art", "works", "primitives"),
        "devour_scan": R("devour_scan", "gaps"),
        "devour_reflect": R("devour_reflect", "cap_quality_summary", "weak_caps"),
        "brand_outro_err": (P.get("brand_outro") or {}).get("error"),
    },
    "others": {
        "life": R("life", "state", "events", "first_at", "last_at"),
        "gate_visibility": R("gate_visibility", "states"),
        "project_context": R("project_context", "path", "sha256"),
        "quant": {"workspace": ((P.get("quant") or {}).get("result") or {}).get("profile", {}).get("workspace"),
                  "exists": ((P.get("quant") or {}).get("result") or {}).get("profile", {}).get("exists"),
                  "top_level_dirs": (((P.get("quant") or {}).get("result") or {}).get("profile", {})
                                     .get("top_level_dirs") or [])[:8]},
    },
}

(S / "v8_manifest.json").write_text(json.dumps(M, ensure_ascii=False, indent=1), encoding="utf-8")
size = (S / "v8_manifest.json").stat().st_size
g = M["gaps"]
print("写出 v8_manifest.json · %d B" % size)
print("镜像: 维度 %s / 现实 %s (v%s) · scan %s/%s · 服务 %d (up %d) · 记录 %d · 队列 %s · 幽灵 %s" % (
    (g["mirror_pipeline"]["mirror_status"].get("dimension") or {}).get("files"),
    (g["mirror_pipeline"]["mirror_status"].get("reality") or {}).get("files"),
    (g["mirror_pipeline"]["mirror_status"].get("reality") or {}).get("version"),
    g["mirror_pipeline"]["mirror_scan"].get("passed"), g["mirror_pipeline"]["mirror_scan"].get("total"),
    len(g["mirror_pipeline"]["services"]),
    len([1 for v in g["mirror_pipeline"]["services"].values() if v.get("up")]),
    g["mirror_pipeline"]["pipeline_n"], g["mirror_pipeline"]["deploy_queue"].get("total"),
    g["mirror_pipeline"]["ghost_guard"].get("clean")))
print("安全: total %s / crit %s / high %s" % (
    g["security"]["sec_scan"].get("total"), g["security"]["sec_scan"].get("critical"),
    g["security"]["sec_scan"].get("high")))
print("长程: %s · 七栏 %s" % (g["longrun_tools"]["lr_progress"], list(g["longrun_tools"]["capability_net"]["seven_columns"])))
print("其余: life %s · gate %s · quant dirs %d" % (
    g["others"]["life"].get("events"), len(g["others"]["gate_visibility"].get("states") or []),
    len(g["others"]["quant"]["top_level_dirs"])))
