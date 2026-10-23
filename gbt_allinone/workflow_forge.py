# -*- coding: utf-8 -*-
# GBT小土豆V8 永久钢印 · 开发者：自由的风 · 守护者：公主土豆
"""workflow_forge -- 工作流十式（主人令 2026-10-16：skills.sh 累计安装 TOP10 蒸馏）

榜单（2026.10.10）与我们的落法（**不重造**：真执行走既有能力位）：
  1 find-skills 377.5万 → 寻件/推荐/安装口径（复用 capability-audit / skill_atlas / gbt-skill-recon）
  2 grill-me 132.2万 → **连续追问厘清需求**（op grill）
  3 grill-with-docs 113.3万 → 追问 + **术语表/决策文档**（op grill_docs）
  4 improve-codebase-architecture 108.1万 → 结构体检/重构机会（复用 code_audit + gbt-code-taste）
  5 agent-browser 107.8万 → 点/填/抽（复用 browser / native_browser / omni_web）
  6 tdd 105.4万 → **测试-实现-重构环**（op tdd_loop）
  7 setup-matt-pocock-skills 97.4万 → 任务跟踪/标签/文档规则（op setup_rules）
  8 frontend-design 97万 → 视觉风格落地（复用 gbt-aesthetic + 前端族）
  9 handoff 95.4万 → **交接文件（进度+资料位置）**（op handoff）
  10 triage 91.7万 → 问题分类+状态推进（op triage）
op：grill / grill_docs / find_skill / arch_review / browser_ops / tdd_loop / setup_rules / style / handoff / triage / check / route
**全只读·零作用域·不出网**；真动手走既有位，且先过第 37 条（先看后动）。
"""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOC = ROOT / "docs" / "skills-top10-蒸馏.md"
OPS = ("grill", "grill_docs", "find_skill", "arch_review", "browser_ops", "tdd_loop", "setup_rules", "style", "handoff", "triage", "check", "route")


def grill(topic: str = "") -> dict:
    return {"ok": True, "op": "grill", "kind": "workflow_forge", "topic": (topic or "").strip() or "（未给主题）",
            "rule": "**先问清楚再动手**：连续追问直到目标/范围/成功判据/边界四项都有答案",
            "rounds": ["目标：做成什么样子算成？", "范围：哪些做、哪些不做？",
                       "判据：怎么验？谁来验？", "边界：什么情况下停？"],
            "judges": ["每轮只追一个问题，答案能落成一句可核的话", "四项未齐 ⇒ **不进入执行**"],
            "bound": "追问上限 8 轮（防止无限盘问）；未齐则如实报缺哪项", "docs": str(DOC)}


def grill_docs(topic: str = "") -> dict:
    return {"ok": True, "op": "grill_docs", "kind": "workflow_forge", "topic": (topic or "").strip() or "（未给主题）",
            "rule": "追问的同时，把答案固化成**术语表 + 决策记录**（一问一条，带时间与理由）",
            "outputs": ["术语表：术语 → 我们的口径（反例）",
                        "决策记录：决定 · 候选 · 理由 · 时间"],
            "judges": ["每条术语能指回一处代码/文档", "决策记录不可回改（只能追加）"]}


def find_skill(need: str = "") -> dict:
    return {"ok": True, "op": "find_skill", "kind": "workflow_forge", "need": (need or "").strip() or "（未给需求）",
            "rule": "**先现读自己的名册，再看外部**（不重造优先）",
            "steps": ["① 现读：capability-audit / skill_atlas（我们已有什么）",
                      "② ①命中 ⇒ 直接用；未命中 ⇒ 列外部候选",
                      "③ 安装前必过供应链体检（gbt-skill-recon）与主人同意",
                      "④ 安装只落受管目录；新增即清旧"],
            "judges": ["每次都能说出“我们已有的那一个是什么”", "未现读不得推荐"]}


def arch_review(scope: str = "") -> dict:
    return {"ok": True, "op": "arch_review", "kind": "workflow_forge", "scope": (scope or "").strip() or "（未给范围）",
            "rule": "看**结构**不看风格：职责是否单一 · 依赖方向是否单向 · 循环依赖 · 重复实现 · 变更面",
            "outputs": ["发现（带文件行）", "重构机会（收益/风险/代价）", "**不动手**（等主人批）"],
            "reuse": "cap code_audit（真扫）+ gbt-code-taste（可读性）",
            "judges": ["每条发现能指到文件行", "无收益证据的重构建议不许出"]}


def browser_ops(intent: str = "") -> dict:
    return {"ok": True, "op": "browser_ops", "kind": "workflow_forge", "intent": (intent or "").strip() or "（未给意图）",
            "rule": "点/填/抽三件；前提：**先看后动**（第 37 条）——先取快照，再动手",
            "reuse": "cap browser / native_browser / omni_web（真执行）",
            "judges": ["每步留快照（动前一张、动后一张）", "找不到元素就滚动/等稳定，不盲点"]}


def tdd_loop(task: str = "") -> dict:
    return {"ok": True, "op": "tdd_loop", "kind": "workflow_forge", "task": (task or "").strip() or "（未给任务）",
            "rule": "**红-绿-重构**：先写一个会失败的测试 → 最小实现让它绿 → 再重构",
            "steps": ["① 测试（可跑、会红）", "② 最小实现（只为绿）", "③ 重构（保持绿）", "④ 回归印章（四元组口径）"],
            "judges": ["**没有先红的测试不算 TDD**", "每一步都能独立回放（试不通不进下一步）", "不为测试而测试（断言要有意义）"]}


def setup_rules(project: str = "") -> dict:
    return {"ok": True, "op": "setup_rules", "kind": "workflow_forge", "project": (project or "").strip() or "（未给项目）",
            "rule": "把**任务跟踪/标签/文档规则**一次性定死，避免每次重商量",
            "outputs": ["状态字典（待办/进行/阻塞/待验/完成）", "标签集（域 · 类型 · 风险）",
                        "文档规则（谁写、写哪、更新时机）"],
            "judges": ["状态与标签有机器判据", "与本仓既有台账/日志不冲突"]}


def style(target: str = "") -> dict:
    return {"ok": True, "op": "style", "kind": "workflow_forge", "target": (target or "").strip() or "（未给目标）",
            "rule": "先定**视觉契约**（色/字/间距/圆角/动效）再落地；**不得 AI 味**",
            "reuse": "gbt-aesthetic（审美三轴 + 审计器）+ 前端族",
            "judges": ["对比度/行高/圆角一致性可量", "过 audit_aesthetic.py（P0 为 0）"]}


def handoff(state: str = "") -> dict:
    return {"ok": True, "op": "handoff", "kind": "workflow_forge", "state": (state or "").strip() or "（未给现状）",
            "rule": "**交接文件 = 现状 + 资料位置 + 下一步**，让接手的人不用问任何问题",
            "sections": ["做到哪了（带读数）", "资料在哪（路径 + 关键文件）",
                         "未完成与阻塞（带原因）", "下一步（可直接执行的命令）", "钢印"],
            "judges": ["接手人能不问问题直接开工", "读数带时间戳"]}


def triage(items: str = "") -> dict:
    return {"ok": True, "op": "triage", "kind": "workflow_forge", "items": (items or "").strip() or "（未给清单）",
            "rule": "分类四档：**阻塞当前** · **阻塞下一步** · **可推迟** · **不做**；每项带状态与负责人",
            "judges": ["每项有明确下一动作与截止", "不下“可以考虑”这类模棱两可"],
            "outputs": ["清单（分档）", "状态推进建议", "需主人拍板的项"]}


def check() -> dict:
    return {"ok": True, "op": "check", "kind": "workflow_forge",
            "rules": ["**不重造**：真执行走既有位（browser / code_audit / gbt-aesthetic 等）",
                      "**先看后动**（第 37 条）：本件全只读，动手前必须有已批蓝图",
                      "**未现读不得推荐**（find_skill）", "**不下模棱两可**（triage）",
                      "上限：grill ≤ 8 轮（防无限盘问）"], "docs": str(DOC)}


def route(task: str = "") -> dict:
    return {"ok": True, "op": "route", "kind": "workflow_forge", "task": (task or "").strip(),
            "map": [{"要什么": "需求不清", "走": "op=grill / grill_docs"},
                    {"要什么": "找能力/技能", "走": "op=find_skill"},
                    {"要什么": "看代码结构", "走": "op=arch_review (+code_audit)"},
                    {"要什么": "网页点填抽", "走": "op=browser_ops (+browser)"},
                    {"要什么": "写代码", "走": "op=tdd_loop"},
                    {"要什么": "项目规则", "走": "op=setup_rules"},
                    {"要什么": "界面好看", "走": "op=style (+gbt-aesthetic)"},
                    {"要什么": "交接/换人", "走": "op=handoff"},
                    {"要什么": "问题堆了", "走": "op=triage"}], "direct": True}


def run(op: str = "route", **kw) -> dict:
    o = (op or "route").strip().lower()
    fns = {"grill": grill, "grill_docs": grill_docs, "find_skill": find_skill, "arch_review": arch_review,
           "browser_ops": browser_ops, "tdd_loop": tdd_loop, "setup_rules": setup_rules, "style": style,
           "handoff": handoff, "triage": triage}
    if o == "check":
        return check()
    if o == "route":
        return route(kw.get("task") or kw.get("topic") or "")
    fn = fns.get(o)
    if not fn:
        return {"ok": False, "reason": "unknown_op", "op": o, "known": list(OPS)}
    key = {"grill": "topic", "grill_docs": "topic", "find_skill": "need", "arch_review": "scope",
           "browser_ops": "intent", "tdd_loop": "task", "setup_rules": "project", "style": "target",
           "handoff": "state", "triage": "items"}[o]
    return fn(kw.get(key) or "")
