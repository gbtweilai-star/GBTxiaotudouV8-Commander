# -*- coding: utf-8 -*-
"""为一个「能力中枢」App 生成真实数据层（不是编的：全部来自注册表与体检读数）。

产出 .scratch/caps_manifest.json：
  { meta:{...真实读数...}, domains:[...], caps:[{name,domain,desc,params,hint,arch,status,risk}] }
arch = 面板原型（8 种）；status = live/readonly/gated/gap/disabled
"""
import json
import sys
from collections import defaultdict
from pathlib import Path

BASE = next(p for p in Path(__file__).resolve().parents
            if (p / "gbt_allinone").is_dir())   # 修：原 `.parent.parent` 只到 tools/（少一层）
sys.path.insert(0, str(BASE))
OUT = BASE / ".scratch" / "caps_manifest.json"

from gbt_allinone import api as API          # noqa: E402
from gbt_allinone import caps_registry as CR  # noqa: E402
from gbt_allinone import selfscan as SS      # noqa: E402

# ── 面板原型默认映射（按域）──
DOMAIN_ARCH = {
    "system": "console", "llm": "form", "pipeline": "graph", "engine": "graph",
    "creation": "stage", "recon": "ledger", "tentacle": "stage", "mind": "ledger",
    "data": "table", "security": "gate", "devour": "ledger", "finance": "metrics",
    "longrun": "graph", "tools": "metrics", "video": "stage", "brain": "ledger",
    "device": "stage", "project": "table", "voice": "stage", "automation": "stage",
    "collab": "ledger", "comms": "table", "digital_human": "stage", "framework": "gate",
    "image_video": "stage", "infra": "stage", "integration": "stage", "life": "ledger",
    "social": "graph", "vision": "stage",
}

# ── 逐项修正（按能力名精确覆盖，覆盖不到才用域默认）──
NAME_ARCH = {
    "health": "metrics", "selfscan": "console", "cross_scan": "console",
    "truth_scan": "console", "signature_guard": "console", "file_hygiene": "console",
    "ghost_guard": "console", "alerts": "metrics", "trace_store": "metrics",
    "auth_gate_status": "gate", "gate_visibility": "gate", "hook_registry": "table",
    "inventory": "table", "root_fix": "console", "energy_pool": "metrics",
    "context_vault": "ledger", "shared_resources": "table", "coverage_auditor": "metrics",
    "tentacle_cognition": "console", "wave_probe": "metrics", "orchestration_kernel": "graph",
    "caps_called_audit": "table",
    "llm_chat": "form", "llm_status": "metrics", "think_loop": "graph",
    "autopilot": "graph", "prompt_bridge": "form", "model_key_pool": "table",
    "brain_route": "graph", "brain_execute": "console", "brain_verify": "stage",
    "brain_health": "metrics", "brain_unify": "graph",
    "mirror_scan": "console", "mirror_status": "metrics", "mirror_parity": "table",
    "mirror_plan": "form", "mirror_shape": "graph", "mirror_simulate": "graph",
    "mirror_rehearse": "graph", "mirror_ascend": "gate", "mirror_release": "gate",
    "mirror_rewind": "gate", "one_key_deploy": "gate", "deploy_queue": "table",
    "pipeline_submit": "gate", "pipeline_status": "table", "pipeline_versions": "table",
    "pipeline_rollback": "gate", "svc_inspect": "console",
    "transfer": "table", "wf_define": "form", "wf_run": "graph", "wf_resume": "graph",
    "wf_status": "table", "wf_cache_clear": "console",
    "sched_define": "form", "sched_status": "table", "sched_tick": "console",
    "record_grid": "table", "audit_query": "table", "count_words": "metrics",
    "echo": "console", "account_registry": "table",
    "sec_scan": "console", "sec_surface": "graph", "sec_chain": "graph",
    "sec_defenses": "console", "sec_llm": "form",
    "devour_github": "form", "devour_pulse": "graph", "devour_reflect": "ledger",
    "devour_scan": "metrics",
    "life": "ledger", "mind": "ledger", "brain_vault": "ledger",
    "meta_cognition": "ledger", "director_mood": "metrics", "auto_switch": "graph",
    "local_brain": "console",
    "stigmergy": "ledger", "auto_publish": "graph", "coze_mail": "table",
    "tripo": "stage", "voice": "stage", "voice_orchestra": "stage",
    "browser": "stage", "vision": "stage", "bluetooth": "stage", "bt_control": "stage",
    "tentacle": "stage", "tentacle_manifest": "table", "tentacle_status": "metrics",
    "mcp_call": "console", "mcp_connect": "form", "mcp_tools": "table",
    "desktop_commander": "console",
    "project_context": "table", "platform_profile": "table",
    "topic_watch": "ledger", "trend_watch": "ledger", "osint_scan": "console",
    "film_intel": "ledger", "music_intel": "ledger", "video_intel": "ledger",
    "verification_watch": "ledger",
    "drama": "stage", "create": "form", "code_art": "stage", "emotion_projection": "form",
    "scene_anchor": "ledger", "render_evolution": "graph", "brand_outro": "stage",
    "music_publishing": "ledger",
    "capability_net": "metrics", "projection_card": "table", "awesome_tools_index": "table",
    "h3_video_gen": "stage", "libtv_skill": "stage", "libtv_workflow": "graph",
    "a1art_skill": "stage", "cloud_pc": "stage", "feishu_embed": "stage",
    "absorb_loop": "graph", "dream_replay": "ledger",
    "lr_submit": "form", "lr_tick": "graph", "lr_status": "table", "tactics_advise": "form",
    "quant": "metrics", "quant_backtest": "metrics", "quant_params": "table",
    "quant_strategy": "metrics",
}

caps_all = API.list_capabilities(filter_dangerous=False)
caps_ok = [c for c in caps_all if c.get("status") != "disabled"]
disabled = [c for c in caps_all if c.get("status") == "disabled"]
routing = SS.check_routing()
scan = SS.scan(autofix=False)

try:
    r = API.run_task("caps_called_audit", {}, safe=True)
    audit = ((r or {}).get("gbt_result") or {}).get("result") or {}
except Exception:  # noqa: BLE001
    audit = {}
wired_names = {x.get("kind") for x in (audit.get("wired") or [])}
gap_names = sorted({c["name"] for c in caps_ok} - wired_names)

param_req = getattr(CR, "PARAM_REQUIRED", {}) or {}

GATED_DOMAINS = {"security"}
GATED_NAMES = {"one_key_deploy", "mirror_ascend", "mirror_release", "mirror_rewind",
               "pipeline_submit", "pipeline_rollback", "mirror_rehearse",
               "codex_thread_new", "codex_turn_send", "codex_interrupt", "codex_chat",
               "codex_models", "coze_mail", "auto_publish", "devour_github",
               "osint_scan", "sec_llm"}

items = []
for c in sorted(caps_ok, key=lambda x: (x.get("domain") or "", x.get("name") or "")):
    name = c.get("name")
    domain = c.get("domain") or "(未标域)"
    hint = param_req.get(name) or {}
    if name in gap_names:
        status = "gap"
    elif domain in GATED_DOMAINS or name in GATED_NAMES:
        status = "gated"
    elif c.get("safe", True):
        status = "readonly" if not hint else "live"
    else:
        status = "gated"
    items.append({
        "name": name,
        "domain": domain,
        "desc": (c.get("desc") or "").strip(),
        "arch": NAME_ARCH.get(name) or DOMAIN_ARCH.get(domain, "console"),
        "params": list(hint.get("params") or []),
        "hint": hint.get("hint") or "",
        "status": status,
    })

for c in sorted(disabled, key=lambda x: x.get("name") or ""):
    items.append({
        "name": c.get("name"), "domain": "disabled",
        "desc": (c.get("desc") or "").strip(),
        "arch": "gate", "params": [], "hint": "", "status": "disabled",
    })

domains = defaultdict(int)
for it in items:
    domains[it["domain"]] += 1

manifest = {
    "meta": {
        "brand": "GBT小土豆V8",
        "version": "8.0.0",
        "developer": "自由的风",
        "scanned_at": scan.get("checked_at"),
        "python": sys.version.split()[0],
        "total": len(items),
        "executable": len(caps_ok),
        "disabled": len(disabled),
        "domains": len([d for d in domains if d != "disabled"]),
        "routed": routing.get("routed"),
        "registered": routing.get("registered"),
        "unrouted": len(routing.get("unrouted") or []),
        "ghost_routes": len(routing.get("ghost_routes") or []),
        "modules_checked": SS.check_modules().get("checked"),
        "modules_failed": len(SS.check_modules().get("failed") or []),
        "wired": audit.get("wired_count"),
        "audit_total": audit.get("total"),
        "orphans": audit.get("orphan_count"),
        "gap_count": len(gap_names),
        "verdict": scan.get("verdict"),
        "findings": scan.get("findings") or [],
    },
    "domains": [{"name": k, "count": v} for k, v in
                sorted(domains.items(), key=lambda kv: (-kv[1], kv[0]))],
    "caps": items,
}

OUT.write_text(json.dumps(manifest, ensure_ascii=False, indent=1), encoding="utf-8")
print("写出:", OUT)
print("能力条目:", len(items), "| 域:", len(domains))
print("面板原型分布:", dict(sorted(
    {a: sum(1 for i in items if i["arch"] == a) for a in {i["arch"] for i in items}}.items(),
    key=lambda kv: -kv[1])))
print("状态分布:", dict(sorted(
    {s: sum(1 for i in items if i["status"] == s) for s in {i["status"] for i in items}}.items(),
    key=lambda kv: -kv[1])))
print("接线缺口:", gap_names)
