# -*- coding: utf-8 -*-
"""V7 数据层：V6 + 万能插（工作流引擎）与亿万触手（66 项 + 十域 + 覆盖审计）真读数。"""
import json
import re
import time
from pathlib import Path

BASE = next(p for p in Path(__file__).resolve().parents
            if (p / "gbt_allinone").is_dir())   # 修：原 `.parent.parent` 只到 tools/（少一层）
S = BASE / ".scratch"
M = json.loads((S / "v6_manifest.json").read_text(encoding="utf-8"))
P = json.loads((S / "plug_tentacle_probe.json").read_text(encoding="utf-8"))


def R(tag):
    return (P.get(tag) or {}).get("result") or {}


# ── 万能插 ──
wf = R("wf_status")
man = (R("tentacle_manifest") or {}).get("manifest") or ""
st = (R("tentacle_status") or {}).get("diagnose") or {}
cov = (R("tentacle_status") or {}).get("coverage") or {}
audit = R("coverage_auditor")

sections = [{"name": m.group(1).strip(), "count": int(m.group(2))}
            for m in re.finditer(r"###\s*([^\n(]+)\((\d+)\)", man)]

tri = []
for line in man.splitlines():
    s = line.strip()
    for key, icon in (("视觉", "eye"), ("听觉", "ear"), ("操作", "hand")):
        if s.startswith({"视觉": "\U0001f441", "听觉": "\U0001f442", "操作": "\U0001f590"}[key]):
            body = re.sub(r"^[^\s]+\s*", "", s)
            tri.append({"channel": key, "icon": icon, "text": body})
if not tri:
    tri = [{"channel": "视觉", "icon": "eye", "text": "DXGI 直读显卡帧缓冲 = 与显示屏同源（vision_buffer 大脑影院）"},
           {"channel": "听觉", "icon": "ear", "text": "WASAPI 回环 = 与扬声器同源（audio_buffer 听觉影院）"},
           {"channel": "操作", "icon": "hand", "text": "cyborg 五维合一穿透 = UIA 直操作无视遮挡"}]

M["plug"] = {
    "probed_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
    "workflow_count": wf.get("count"),
    "workflows": [{"name": w.get("name"), "node_count": w.get("node_count"),
                   "nodes": [{"id": n.get("id"), "kind": n.get("kind"),
                              "depends_on": n.get("depends_on") or [],
                              "cache": bool(n.get("cache"))} for n in (w.get("nodes") or [])]}
                  for w in (wf.get("workflows") or [])],
    "runs": [{"run_id": r.get("run_id"), "workflow": r.get("workflow"), "status": r.get("status"),
              "nodes": r.get("nodes"), "elapsed_s": r.get("elapsed_s"), "at": r.get("finished_at")}
             for r in (wf.get("runs") or [])[:10]],
    "operators": ["collect", "map", "pluck", "filter", "merge", "unique", "sort", "limit",
                  "flatten", "split", "join", "rename", "wrap", "stats"],
    "real_runs": {
        "unique": R("transfer_unique"),
        "stats": R("transfer_stats"),
    },
    "schedules": (R("sched_status") or {}).get("count"),
    "data_outlet": "wf_status(include_workflows=True) —— engine.py:541 list_workflows() 是给可视化准备的正规出口",
}

M["tentacle"] = {
    "headline": man.splitlines()[0] if man else "",
    "channels": tri,
    "sections": sections,
    "sections_total": sum(s["count"] for s in sections),
    "manifest_chars": len(man),
    "diagnose": {
        "ok": st.get("ok"), "eye_error": st.get("eye_error"),
        "manifest_methods": st.get("manifest_methods"), "neighborhoods": st.get("neighborhoods"),
        "checked_at": st.get("checked_at"),
        "deps": [{"name": k, "ok": bool(v.get("ok")), "role": v.get("role")}
                 for k, v in (st.get("deps") or {}).items()],
    },
    "coverage": {
        "domains": cov.get("total_domains"), "real_methods": cov.get("real_methods"),
        "denominator": cov.get("denominator"), "denominator_source": cov.get("denominator_source"),
        "covered": cov.get("covered_actions"), "uncovered": cov.get("uncovered_count"),
        "ghosts": len(cov.get("ghosts_in_map") or []),
        "pct": cov.get("intent_coverage_pct"),
        "by_domain": cov.get("coverage") or {},
    },
    "audit": {
        "matrix": audit.get("matrix") or [],
        "by_group": audit.get("coverage_by_group"),
        "modules": audit.get("reportable_modules"),
        "gaps": audit.get("known_gaps") or [],
        "as_of": audit.get("as_of"),
    },
    "caps_gate": {"denied": bool((P.get("tentacle_caps") or {}).get("denied")),
                  "missing": (P.get("tentacle_caps") or {}).get("missing") or [],
                  "how_to_grant": ((P.get("tentacle_caps") or {}).get("result") or {}).get("how_to_grant") or []},
}

(S / "v7_manifest.json").write_text(json.dumps(M, ensure_ascii=False, indent=1), encoding="utf-8")
pl, te = M["plug"], M["tentacle"]
print("写出 v7_manifest.json")
print("万能插: 工作流 %s 个 · 运行记录 %s 条 · 算子 %d 个 · 定时任务 %s 个"
      % (pl["workflow_count"], len(pl["runs"]), len(pl["operators"]), pl["schedules"]))
for w in pl["workflows"]:
    print("   - %-18s %d 节点" % (w["name"], w["node_count"]))
print("   transfer unique 真输出:", json.dumps(pl["real_runs"]["unique"], ensure_ascii=False))
print("触手: %s" % te["headline"])
print("   三通道:", " / ".join(c["channel"] for c in te["channels"]))
print("   分段 %d 段合计 %d 项 · 依赖 %d 项 · 邻域 %d"
      % (len(te["sections"]), te["sections_total"], len(te["diagnose"]["deps"]), te["diagnose"]["neighborhoods"] or 0))
print("   覆盖: %s/%s = %s%% · 未覆盖 %s · 幽灵 %s"
      % (te["coverage"]["covered"], te["coverage"]["denominator"], te["coverage"]["pct"],
         te["coverage"]["uncovered"], te["coverage"]["ghosts"]))
print("   八短板: %s" % " | ".join("%s %s/%s" % (r["key"], r["reportable_modules"], r["expected_modules"])
                                for r in te["audit"]["matrix"]))
