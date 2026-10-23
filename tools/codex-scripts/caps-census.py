#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""全量能力位静态普查（只读，不执行任何能力位）。

口径（三处各自声明，本脚本只做**并集与差集**，不发明新判据）：
  1. caps_registry.BENIGN_CAPS       —— 名字 / 域 / handler / safe
  2. security.policy.evaluate()      —— 空参静态作用域（门看得见的）
  3. preflight.is_side_effect()      —— 会改状态的（含门看不见的 _STATE_CHANGING_KINDS）

产出的关键表：**零作用域但会改状态**（门看不见的写口）—— 这一格是本仓历史教训
（`wf_cache_clear` 真清缓存、`devour_reflect` 真写盘）的唯一可机检来源。

用法：
  python tools/codex-scripts/caps-census.py [--out <path>] [--md <path>]
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from gbt_allinone import caps_registry as R          # noqa: E402
from gbt_allinone import preflight                    # noqa: E402
from gbt_allinone.security import policy              # noqa: E402

PROBES = [
    ("空参", {}),
    ("op=status", {"op": "status"}),
    ("fix=true", {"fix": True}),
    ("restore=true", {"restore": True}),
    ("op=apply", {"op": "apply"}),
    ("op=write", {"op": "write"}),
]

# 动作扫描词表：`policy.evaluate()` 是**按 op/action 分支**判定作用域的，
# 只探固定几个 action 会把「只在 write 动作上收口」的位读成"零作用域"。
# 所以每个位都过一遍常用动作动词，把**动作→作用域**的完整矩阵扫出来。
ACTION_SWEEP = [
    "status", "list", "get", "info", "plan", "verify", "authorize", "revoke",
    "add", "remove", "delete", "start", "stop", "restart", "run", "exec", "call",
    "capture", "purge", "dump", "baseline", "record", "send", "reply", "register",
    "mark", "read", "write", "apply", "rollback", "patch", "deploy", "release",
    "submit", "tick", "clear", "create", "update", "sync", "push", "pull",
    "open", "click", "type", "scan", "audit", "fix", "restore", "shape",
    "rehearse", "simulate", "parity", "gate", "enter", "snapshot", "observe",
    "export", "import", "query", "search", "fetch", "download", "upload",
    "connect", "disconnect", "invoke", "take", "creds", "settle", "publish",
    "collect", "emit", "parse", "profile", "draft", "vocab", "presets",
]

# 第二张词表：**各域自己的动作词**。通用动词扫不到它们，会把「只在 tts 上收口」
# 的位误读成"整位零作用域"（第一版就是这么把 `voice` 读错的）。
DOMAIN_ACTIONS = [
    "tts", "speak", "say", "asr", "transcribe", "clone", "dubbing", "synthesize",
    "capture_screen", "screenshot", "get_cookies", "native", "deep", "controller",
    "cdp", "automate", "fetch", "ascend", "rewind", "namespace", "release_all",
    "versions", "rollback_to", "shape", "plan", "simulate", "rehearse", "parity",
    "inbox", "read_mail", "mark", "draft_mail", "send_mail",
    "profile_scan", "draft_record", "emit_record", "verify_record",
    "deposit", "forage", "decay", "read_field",
    "eye", "see", "vision_snapshot", "screen_size", "screenshot_diff",
    "read_text", "list_windows", "process_list", "active_window", "window_list",
    "monitor", "detect", "ocr", "manifest", "app_running",
    "execute", "verify_plan", "health", "unify", "route", "reflect", "pulse",
    "scan_field", "tick_all", "upgrade", "escalate", "advise",
    "shape_bytes", "rehearse_bytes", "account_list",
]

ACTION_SWEEP = list(dict.fromkeys(ACTION_SWEEP + DOMAIN_ACTIONS))

# 第三张表（2026-09-25 补）：**字段门**。前两张表只扫 `op`，而 `policy.evaluate()` 里
# 有一整类分支是**看 payload 字段**开门的：
#     `mirror_plan` 只有 `p.get("plan")` 才挂 filesystem_write（光看 op 永远是零作用域）；
#     `mirror_shape` 看 `path`；`signature_guard` 看 `restore`；`inventory`/`file_hygiene` 看 `fix`；
#     `browser` 的 `native` 看 `action`；`_needs_private_network()` 看 `url`/`target`/`base_url`/`repo`。
# 不扫这一层，就会把"字段一给就要授权"的位**读成免卡** —— 这正是我上一版普查的盲区。
FIELD_PROBES = {
    "plan": {"plan": {"probe": True}},
    "path": {"path": "gbt_allinone/README.md"},
    "restore": {"restore": True},
    "fix": {"fix": True},
    "review": {"review": True},
    "refine_rounds": {"refine_rounds": 1},
    "include_values": {"include_values": True},
    "tool": {"tool": "write_file"},
    "target": {"target": "probe.example"},
    "private_url": {"url": "http://127.0.0.1:9/probe"},
    "public_url": {"url": "https://example.com/probe"},
    "repo": {"repo": "https://example.com/a/b.git"},
    "text": {"text": "probe"},
    "force": {"force": True},
}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="output/blueprint-audit/caps-census.json")
    ap.add_argument("--md", default="docs/能力位全量普查.md")
    args = ap.parse_args()

    state_changing = preflight.state_changing_kinds()
    rows = []
    for kind, meta in sorted(R.BENIGN_CAPS.items()):
        meta = meta if isinstance(meta, dict) else {}
        domain = meta.get("domain")
        handler = meta.get("handler")
        decision = policy.evaluate(kind, {})
        scopes = list(decision.scopes or ())
        se = preflight.is_side_effect(kind, {}, decision)

        probe_map = {}
        for label, payload in PROBES:
            d = policy.evaluate(kind, payload)
            probe_map[label] = {
                "scopes": list(d.scopes or ()),
                "risk": d.risk,
                "side_effect": preflight.is_side_effect(kind, payload, d),
            }

        sweep = {}
        for act in ACTION_SWEEP:
            d = policy.evaluate(kind, {"op": act})
            sc = list(d.scopes or ())
            if sc or preflight.is_side_effect(kind, {"op": act}, d):
                sweep[act] = {"scopes": sc, "side_effect": preflight.is_side_effect(kind, {"op": act}, d)}

        field_sweep = {}
        for label, payload in FIELD_PROBES.items():
            d = policy.evaluate(kind, payload)
            sc = list(d.scopes or ())
            if sc or preflight.is_side_effect(kind, payload, d):
                field_sweep[label] = {
                    "payload_keys": sorted(payload),
                    "scopes": sc,
                    "side_effect": preflight.is_side_effect(kind, payload, d),
                }

        rows.append({
            "kind": kind,
            "domain": domain,
            "handler": handler,
            "safe": bool(meta.get("safe")),
            "handler_missing": not handler,
            "scopes_empty": scopes,
            "scopes_empty_count": len(scopes),
            "risk_empty": decision.risk,
            "side_effect_empty": bool(se),
            "state_changing_kind": kind in state_changing,
            "probes": probe_map,
            "action_sweep": sweep,
            "field_sweep": field_sweep,
            "gated_actions": sorted(sweep),
            "gated_fields": sorted(field_sweep),
            "ungated_all_actions": not sweep,
            "param_required": list((R.PARAM_REQUIRED.get(kind) or {}).get("params") or []),
            "enabled": kind not in set(R.DISABLED_CAPS),
            "unimplemented": kind in set(R.UNIMPLEMENTED_CAPS),
        })

    by_domain: dict[str, dict] = {}
    for r in rows:
        b = by_domain.setdefault(r["domain"] or "?", {"total": 0, "zero_scope": 0,
                                                      "side_effect": 0, "zero_scope_but_writes": 0,
                                                      "param_required": 0})
        b["total"] += 1
        if r["scopes_empty_count"] == 0:
            b["zero_scope"] += 1
        if r["side_effect_empty"]:
            b["side_effect"] += 1
        if r["scopes_empty_count"] == 0 and r["side_effect_empty"]:
            b["zero_scope_but_writes"] += 1
        if r["param_required"]:
            b["param_required"] += 1

    blind = [r for r in rows if r["scopes_empty_count"] == 0 and r["side_effect_empty"]]
    need_param = [r for r in rows if r["param_required"]]
    no_handler = [r for r in rows if r["handler_missing"]]
    ungated = [r for r in rows if r["ungated_all_actions"]]
    # 🔴 本表要抓的那一类：**只看 op / 空参都读不出门，一给字段门就出现**。
    #    （上一版普查就是在这里把 `mirror_plan` 读成免卡的。）
    field_only = [r for r in rows if r["gated_fields"] and not r["gated_actions"]]
    # 「两个轴都扫过还是零作用域」—— 这才是能说的那句话。
    # 只报 `ungated_all_actions` 会**读过头**：那 6 个字段门位混在里面（见 7.x 的更正）。
    no_gate_any = [r for r in rows if not r["gated_actions"] and not r["gated_fields"]]

    report = {
        "total_kinds": len(rows),
        "domains": len(by_domain),
        "blind_write_ports": [r["kind"] for r in blind],
        "blind_write_ports_count": len(blind),
        "param_required_count": len(need_param),
        "handler_missing": [r["kind"] for r in no_handler],
        "ungated_all_actions": [r["kind"] for r in ungated],
        "ungated_all_actions_count": len(ungated),
        "field_only_gates": [r["kind"] for r in field_only],
        "field_only_gates_count": len(field_only),
        "no_gate_on_any_axis": [r["kind"] for r in no_gate_any],
        "no_gate_on_any_axis_count": len(no_gate_any),
        "field_probe_count": len(FIELD_PROBES),
        "action_sweep_size": len(ACTION_SWEEP),
        "by_domain": by_domain,
        "rows": rows,
    }

    out = ROOT / args.out
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    md = ROOT / args.md
    md.parent.mkdir(parents=True, exist_ok=True)
    lines = []
    lines.append("# 能力位全量静态普查（只读 · 不执行）\n")
    lines.append("> 生成器：`tools/codex-scripts/caps-census.py` ｜ 数据：`%s`\n" % args.out)
    lines.append("> 口径：名字取自 `caps_registry.BENIGN_CAPS`；作用域取自 `security.policy.evaluate()`；")
    lines.append("> 会改状态取自 `preflight.is_side_effect()`。三处各自声明，本表只做并集/差集。\n")
    lines.append("\n## 总账\n")
    lines.append("- 能力位总数：**%d**" % report["total_kinds"])
    lines.append("- 覆盖域数：**%d**" % report["domains"])
    lines.append("- 🔴 **零作用域但会改状态**（门看不见的写口）：**%d** 位" % report["blind_write_ports_count"])
    lines.append("- 必填参数位：**%d** 位" % report["param_required_count"])
    lines.append("- 无 handler 的位：**%d** 位" % len(no_handler))
    lines.append("- 动作扫描：**%d** 个动作动词 × 全部能力位（找出只在写动作上收口的位）"
                 % report["action_sweep_size"])
    lines.append("- 扫全部动作都**零作用域**的位：**%d** 位（门对这些位的任何动作都不收口）"
                 % report["ungated_all_actions_count"])
    lines.append("\n## 逐域\n")
    lines.append("| 域 | 位数 | 零作用域 | 会改状态 | 🔴零作用域但会写 | 有必填参数 |")
    lines.append("|---|---|---|---|---|---|")
    for name, b in sorted(by_domain.items(), key=lambda kv: (-kv[1]["zero_scope_but_writes"], kv[0])):
        lines.append("| `%s` | %d | %d | %d | **%d** | %d |" % (
            name, b["total"], b["zero_scope"], b["side_effect"], b["zero_scope_but_writes"],
            b["param_required"]))
    lines.append("\n## 🔴 零作用域但会改状态（门盲区清单）\n")
    for r in blind:
        lines.append("- `%s`（域 `%s`）%s" % (r["kind"], r["domain"], preflight_note(r)))
    lines.append("\n## 必填参数位\n")
    for r in need_param:
        lines.append("- `%s`：%s" % (r["kind"], "、".join(r["param_required"])))
    lines.append("\n## 动作→作用域矩阵（只列**有收口**的位）\n")
    lines.append("> 读法：`位 → 动作=作用域`。**没列到的动作就是零作用域**。")
    lines.append("> 这张表是用来抓「只在写动作上收口」的位的——只探空参会把它读成『零作用域』。\n")
    for r in rows:
        if not r["gated_actions"]:
            continue
        groups: dict[str, list[str]] = {}
        for act in r["gated_actions"]:
            info = r["action_sweep"][act]
            label = "+".join(info["scopes"]) if info["scopes"] else "（无作用域但会改状态）"
            groups.setdefault(label, []).append(act)
        if len(groups) == 1 and len(r["gated_actions"]) >= len(ACTION_SWEEP) * 0.5:
            label, acts = next(iter(groups.items()))
            lines.append("- `%s`（域 `%s`）：**全部动作** → %s" % (r["kind"], r["domain"], label))
            continue
        pairs = []
        for label, acts in sorted(groups.items(), key=lambda kv: -len(kv[1])):
            if len(acts) > 6:
                pairs.append("**其余 %d 个动作**=%s" % (len(acts), label))
            else:
                pairs.append("%s=%s" % ("/".join(acts), label))
        lines.append("- `%s`（域 `%s`）：%s" % (r["kind"], r["domain"], " · ".join(pairs)))
    lines.append("\n## 🔴 字段门矩阵（**只看 op 读不出门**的那一类）\n")
    lines.append("> 为什么单列：`policy.evaluate()` 有一整类分支是**看 payload 字段**开门的。")
    lines.append("> 只扫 `op` == 把「字段一给就要授权」的位读成**免卡**。")
    lines.append("> 现读：**%d** 位的门只在字段上出现（扫 %d 个字段探针）。\n"
                 % (report["field_only_gates_count"], report["field_probe_count"]))
    lines.append("| 能力位 | 域 | 触发字段 → 作用域 |")
    lines.append("|---|---|---|")
    for r in field_only:
        pairs = []
        for f in r["gated_fields"]:
            info = r["field_sweep"][f]
            label = "+".join(info["scopes"]) if info["scopes"] else "（无作用域但会改状态）"
            pairs.append("`%s`=%s" % (f, label))
        lines.append("| `%s` | `%s` | %s |" % (r["kind"], r["domain"], " · ".join(pairs)))
    lines.append("\n## 字段探针也会开门的位（字段门 + 动作门都有）\n")
    for r in rows:
        if not (r["gated_fields"] and r["gated_actions"]):
            continue
        pairs = []
        for f in r["gated_fields"]:
            info = r["field_sweep"][f]
            label = "+".join(info["scopes"]) if info["scopes"] else "（无作用域但会改状态）"
            pairs.append("`%s`=%s" % (f, label))
        lines.append("- `%s`（域 `%s`）：%s" % (r["kind"], r["domain"], " · ".join(pairs)))
    lines.append("\n## 扫全部动作都零作用域的位（门完全不收口）\n")
    lines.append("> 🔴 **先读这一句**：本节旧标题写的是「扫全部动作都零作用域 = %d 位」，"
                 "**那个说法读过头了** ——" % report["ungated_all_actions_count"])
    lines.append("> 补上字段门扫描后，其中 **%d 位其实有门**（只挂在 payload 字段上，见上一节）。"
                 % report["field_only_gates_count"])
    lines.append("> **真正的『两个轴都扫过还是零作用域』= %d 位。**"
                 % report["no_gate_on_any_axis_count"])
    lines.append("> ⚠️ 读法两条：① 这**不等于**『可以随便调』——只说明 `policy.evaluate()` "
                 "在我扫的这 %d 个动作下都不加作用域；" % report["action_sweep_size"])
    lines.append("> ② 词表是**枚举**出来的，不是从实现里推出来的 ⇒ 某个位若有我没想到的动作词，"
                 "这里会漏（第一版就是这么把 `voice` 漏读的：只在 `tts`/`speak` 上收口，"
                 "通用动词一个都没收）。**这是覆盖上界，不是证明。**")
    lines.append("> 其中会改状态的位见上一节「门盲区清单」。\n")
    for r in ungated:
        flag = " 🔴会改状态" if r["side_effect_empty"] or r["state_changing_kind"] else ""
        lines.append("- `%s`（域 `%s`）%s" % (r["kind"], r["domain"], flag))
    md.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(json.dumps({
        "ok": True,
        "total_kinds": report["total_kinds"],
        "domains": report["domains"],
        "blind_write_ports": report["blind_write_ports"],
        "param_required_count": report["param_required_count"],
        "handler_missing": report["handler_missing"],
        "out": str(out),
        "md": str(md),
    }, ensure_ascii=False, indent=2))
    return 0


def preflight_note(row: dict) -> str:
    if row["state_changing_kind"]:
        return "（在 `preflight._STATE_CHANGING_KINDS` 显式声明）"
    return "（靠 payload 里的开关触发，空参时是只读外观）"


if __name__ == "__main__":
    raise SystemExit(main())
