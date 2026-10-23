# -*- coding: utf-8 -*-
# ⬻ 开发者：自由的风 · GBT小土豆V8 · 永久钢印
"""软件命令化（cli_ify）—— 深度蒸馏自 HKUDS/CLI-Anything

上游原文现读（raw.githubusercontent.com/HKUDS/CLI-Anything/main/README.md，HTTP 200，80,551 字）后补齐的三块：
  ① **The Agent-Software Gap**：智能体推理强、**用真业务软件很差**；现有办法三个坑：脆弱的 UI 自动化 ·
    能力残缺的 API · **焦住版重写（会丢掉 90% 功能）** ⇒ 我们的口径：**包壳，不重写**。
  ② **7 相流水线**：Analyze（扫源码、把 GUI 动作对到 API）→ Design（命令组/状态模型/输出格式）
    → Implement（CLI + REPL + JSON 输出 + undo/redo）→ Plan Tests（TEST.md）→ Write Tests → Docs → Publish。
  ③ **CLI-Hub 注册表**：社区 CLI 的浏览/安装/更新/卸载/启动 —— 我们对应的是本仓 `state/cli-surfaces.json` 登记表。

本位只做**只读判与出计划**（不写盘），因此**零作用域**：
  gate     三档选型判定（已有 CLI / 只有 API / 只有 GUI）+ 判据
  plan     六步计划（与上游 7 相流水线对齐）
  registry 读登记表 + 统计 + 缺证据清单
  check    C1~C4 判据（本位自实现，不 shell-out）
  gap      说清为什么不自己重写（对接 Agent-Software Gap 口径）
"""
from __future__ import annotations

import json
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REG = ROOT / "state" / "cli-surfaces.json"
READ_OPS = ("status", "gate", "plan", "registry", "check", "gap")
WRITE_OPS = ()
VALID_STATUS = ("cli", "api-wrapped", "gui-only", "planned")


def gate(name: str = "", has_cli=None, has_api=None, has_gui=None) -> dict:
    """三档选型闸（先判再动）—— 三个信号一个都没给 ⇒ fail-closed。"""
    if has_cli is None and has_api is None and has_gui is None:
        return {"ok": False, "reason": "need_signals",
                "detail": "至少告诉我：该软件有没有 CLI / API / GUI（不许凭印象判）"}
    if has_cli:
        r, why = "cli", "已有 CLI ⇒ **直接用**：省时省钱、可复跑、可判据；不许上 GUI"
    elif has_api:
        r, why = "api-wrapped", "只有 API ⇒ **包成 CLI 面**（走六步）；不重写实现"
    elif has_gui:
        r, why = "gui-only", "只有 GUI ⇒ 才走触手/浏览器，并在登记表标「只能 GUI」"
    else:
        r, why = "planned", "三个都没有 ⇒ 先不动，当成一条**待办入口**登记"
    return {"ok": True, "op": "gate", "software": name, "route": r, "why": why,
            "signals": {"has_cli": bool(has_cli), "has_api": bool(has_api), "has_gui": bool(has_gui)},
            "judge": "py -3.14 tools/codex-scripts/cli-surface-check.py",
            "rule": "包壳，不重写（重写会丢 90% 功能）"}


def plan(name: str = "", route: str = "api-wrapped") -> dict:
    """命令化六步 × 上游 7 相流水线对照表。"""
    if not str(name or "").strip():
        return {"ok": False, "reason": "need_name"}
    steps = [
        {"n": 1, "ours": "探接口", "upstream": "Analyze",
         "do": "--help / API 文档 / 进程参数，**现读不猜**；GUI 动作对到 API",
         "evidence": "<tool> --help 的回执"},
        {"n": 2, "ours": "定命令面", "upstream": "Design",
         "do": "<tool> <verb> <args>；动词短、可组合；定状态模型与输出格式（JSON 优先）",
         "evidence": "verbs 清单"},
        {"n": 3, "ours": "包成能力位/插座", "upstream": "Implement",
         "do": "走 omni_plug 的 process/api 插座，**不必新模块**；有必要才加 REPL / undo",
         "evidence": "能力位名 或 插座名"},
        {"n": 4, "ours": "登记", "upstream": "Publish（本地对应登记表）",
         "do": "写进 state/cli-surfaces.json：name/entry/verbs/evidence/status",
         "evidence": "state/cli-surfaces.json 里的那一条"},
        {"n": 5, "ours": "接路由", "upstream": "Docs",
         "do": "让「人一句话 → 哪条命令」有落点（写进能力页/業务路由）",
         "evidence": "路由条目"},
        {"n": 6, "ours": "挂判据", "upstream": "Plan Tests / Write Tests",
         "do": "--help 可跑 + 至少一条真用例可复跑；判据食物就是 evidence",
         "evidence": "C1~C4 全绿的回执"},
    ]
    return {"ok": True, "op": "plan", "software": name, "route": route, "steps": steps,
            "upstream_7phase": ["Analyze", "Design", "Implement", "Plan Tests", "Write Tests", "Docs", "Publish"],
            "note": "上游 7 相 → 我们 6 步（Plan Tests / Write Tests 合并为第 6 步；Publish 落到第 4 步登记）",
            "registry": str(REG)}


def _load() -> dict:
    try:
        d = json.loads(REG.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    if isinstance(d, list):
        return {"surfaces": d}
    return d if isinstance(d, dict) else {}


def registry() -> dict:
    """读登记表（只读）—— 缺不报空绿：文件不在就如实报「未读到」。"""
    if not REG.is_file():
        return {"ok": False, "reason": "registry_not_found", "registry": str(REG),
                "detail": "登记表未读到 ⇒ **不当空表绿**；先建再填"}
    d = _load()
    rows = d.get("surfaces") or d.get("items") or []
    if not isinstance(rows, list):
        rows = []
    by_status = {}
    for r in rows:
        k = str((r or {}).get("status") or "?")
        by_status[k] = by_status.get(k, 0) + 1
    return {"ok": True, "op": "registry", "registry": str(REG), "count": len(rows),
            "by_status": by_status, "at": d.get("at"), "surfaces": rows[:40],
            "honest": "只读；数字现算不写死"}


def check() -> dict:
    """C1~C4 判据（本位自实现，不 shell-out）。"""
    d = _load()
    rows = d.get("surfaces") or d.get("items") or []
    bad = []
    if not REG.is_file():
        bad.append({"c": "C1", "why": "登记表未读到（不许当空表绿）"})
    elif not rows:
        bad.append({"c": "C1", "why": "登记表是空的"})
    for r in rows if isinstance(rows, list) else []:
        r = r or {}
        nm = str(r.get("name") or "").strip()
        if not nm or not str(r.get("entry") or "").strip() or not (r.get("verbs") or []):
            bad.append({"c": "C2", "why": "缺 name/entry/verbs: %s" % (nm or "(无名)")})
        if not str(r.get("evidence") or "").strip():
            bad.append({"c": "C3", "why": "缺 evidence（可复跑命令或判据文件）: %s" % nm})
        if str(r.get("status") or "") not in VALID_STATUS:
            bad.append({"c": "C4", "why": "status 越界: %s → %s" % (nm, r.get("status"))})
    return {"ok": not bad, "op": "check", "registry": str(REG), "checked": len(rows) if isinstance(rows, list) else 0,
            "violations": bad[:40], "violation_count": len(bad),
            "valid_status": list(VALID_STATUS),
            "judge_script": "py -3.14 tools/codex-scripts/cli-surface-check.py",
            "selftest": "py -3.14 tools/codex-scripts/cli-surface-check.py --selftest"}


def gap(name: str = "") -> dict:
    """为什么**不自己重写**（对接上游 Agent-Software Gap）。"""
    return {"ok": True, "op": "gap", "software": name,
            "gap": "智能体推理强、**用真业务软件很差**",
            "three_bad_fixes": ["脆弱的 UI 自动化", "能力残缺的 API", "焦位版重写（会丢 90% 功能）"],
            "our_rule": "包壳，不重写；先问“它自己有没有 CLI”",
            "route": gate(name, has_cli=None, has_api=None, has_gui=None).get("reason") and "未知（先探再说）"}


def status() -> dict:
    return {"ok": True, "op": "status", "registry": str(REG), "registry_exists": REG.is_file(),
            "ops": list(READ_OPS), "writes": list(WRITE_OPS),
            "note": "本位**只读**（零作用域）；登记表得由写渠道去写"}


def run(op: str = "status", **kw) -> dict:
    o = (op or "status").strip().lower()
    if o == "status":
        return status()
    if o == "gate":
        return gate(kw.get("name") or kw.get("software") or "", kw.get("has_cli"), kw.get("has_api"), kw.get("has_gui"))
    if o == "plan":
        return plan(kw.get("name") or kw.get("software") or "", kw.get("route") or "api-wrapped")
    if o == "registry":
        return registry()
    if o == "check":
        return check()
    if o == "gap":
        return gap(kw.get("name") or "")
    return {"ok": False, "reason": "unknown_op", "op": o, "known": list(READ_OPS),
            "detail": "未知 op 只回错（fail-closed）"}

