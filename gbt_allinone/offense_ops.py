# -*- coding: utf-8 -*-
# GBT小土豆V8 永久钢印 · 开发者：自由的风 · 守护者：公主土豆
"""offense_ops —— 自主渗透编排（主人令 2026-10-16：把 pentagi 全部能力蒸成我们的原生能力）

蒸自 **vxControl/pentagi**（MIT · Go · 30.5k 星 · 多智能体自主渗透测试系统）的**思想**，不搬代码：
  多智能体分工（researcher / pentester / coder / reporter）· 工具面（terminal/browser/search/embeddings）
  · 跨任务记忆（向量检索）· 证据链与报告 · self-hosted 自主执行。
**红线（我们的护栏优先于它的自主性）**：
  只打**主人在终端明确授权**的范围；fail-closed；不可回滚动作先问；凭据只报已配/未配；
  发现只报**可复现**的；**不外发**任何目标数据。
op：plan / roles / tools / evidence / memory / gate / check / route（**全只读·零作用域·不出网·不动手**）
"""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOC = ROOT / "docs" / "pentagi-自主渗透-蒸馏.md"
OPS = ("plan", "roles", "tools", "evidence", "memory", "gate", "check", "route")
PHASES = ["侦察（被动优先）", "武器化（清单化）", "利用（只打授权面）", "后渗透（最小必要）", "报告（可复现）"]


def plan(target: str = "", scope: str = "") -> dict:
    t = (target or "").strip()
    if not t:
        return {"ok": False, "reason": "need_target", "how": "给目标；**并给授权范围**（谁授权的、范围边界）"}
    if not (scope or "").strip():
        return {"ok": False, "reason": "need_scope", "how": "**没有授权范围就没有这一步**：先写清授权范围（fail-closed）"}
    return {"ok": True, "op": "plan", "kind": "offense_ops", "target": t, "scope": scope,
            "phases": PHASES,
            "loop": ["计划 → 执行 → 取证 → 复核（每条发现必须可复现）→ 报告 → 复盘"],
            "judges": ["每一步能指回授权范围", "每条发现带复现步骤与影响", "越界即停并如实报"],
            "source": "vxControl/pentagi（MIT · 只蒸思想）", "doc": str(DOC)}


def roles() -> dict:
    return {"ok": True, "op": "roles", "kind": "offense_ops",
            "roles": [
                {"角色": "researcher（侦察）", "干什么": "收集公开信息与资产面", "判据": "每条来源可指回"},
                {"角色": "pentester（利用）", "干什么": "在授权面上验证可复现问题", "判据": "复现步骤 + 影响 + 时间戳"},
                {"角色": "coder（工具）", "干什么": "写脚本/解析/自动化取证", "判据": "脚本可复跑，不硬编码凭据"},
                {"角色": "reporter（报告）", "干什么": "出可复核报告与修复建议", "判据": "结论 → 证据 → 建议三段齐"},
            ],
            "note": "多智能体是**分工**不是**放飞**：每个角色都过同一道授权门（见 op=gate）",
            "source": "vxControl/pentagi（MIT）"}


def tools() -> dict:
    return {"ok": True, "op": "tools", "kind": "offense_ops",
            "surfaces": ["terminal（命令执行）", "browser（页面取证）", "search（公开检索）", "embeddings（跨任务记忆检索）"],
            "local_readback": "本机已配/未配由各自能力位现读（pod_link/browser/sec_*）；**取不到就写未读到**",
            "judges": ["每个动作留痕", "凭据只报已配/未配", "危险动作先问主人"]}


def evidence() -> dict:
    return {"ok": True, "op": "evidence", "kind": "offense_ops",
            "chain": ["时间戳", "命令/请求原文", "响应要点（脱敏）", "复现步骤", "影响范围", "修复建议"],
            "judges": ["**可复现/重现**才算有效发现", "只有影响没有复现步骤 ⇒ 标未验证",
                       "证据不外发；报告里第三方信息脱敏"],
            "standard": "与 sec_* 同口径：定级用平台/标准口径，不自编"}


def memory() -> dict:
    return {"ok": True, "op": "memory", "kind": "offense_ops",
            "what": "跨任务记忆：把目标画像、已试手法、已验证结论入我们自己的库（向量/关键词检索）",
            "rules": ["**不外发**（记忆与上下文永不外发）", "过期读数带 cached/ts",
                      "新增即清旧：同一目标只留一份最新画像", "落点只走我们自己的目录"]}


def gate(action: str = "") -> dict:
    a = (action or "").strip()
    return {"ok": True, "op": "gate", "kind": "offense_ops", "action": a or "（未指定动作）",
            "gates": [
                {"闸": "授权", "判据": "主人在终端明确授权范围；**没有范围不动手**", "fail": "拒绝并报缺什么"},
                {"闸": "不可回滚", "判据": "删除/改写/付款/接管设备类动作先问主人", "fail": "停下等人点头"},
                {"闸": "凭据", "判据": "只用已配凭据；只报已配/未配", "fail": "如实报未配"},
                {"闸": "出网", "判据": "只对授权目标出网；不扫无关资产", "fail": "拒绝"},
                {"闸": "留痕", "判据": "每步进审计账（公理一：无痕即不存在）", "fail": "该步视为未发生"},
            ], "is_instruction": False}


def check() -> dict:
    return {"ok": True, "op": "check", "kind": "offense_ops",
            "rules": ["MIT ⇒ 只蒸思想不搬代码", "**护栏优先于自主性**（pentagi 的自主执行必须在我们的授权门内）",
                      "只在授权范围动手；越界即停", "发现必须可复现；不可复现标未验证",
                      "目标数据不外发；凭据不入档", "本 op 集**全只读**，真动手走各自能力位（sec_* / 触手）"],
            "doc": str(DOC)}


def route(target: str = "") -> dict:
    return {"ok": True, "op": "route", "kind": "offense_ops", "target": (target or "").strip(),
            "map": [{"要什么": "定阶段与范围", "走": "cap offense_ops op=plan"},
                    {"要什么": "分工", "走": "cap offense_ops op=roles"},
                    {"要什么": "工具面现状", "走": "cap offense_ops op=tools + 各能力位现读"},
                    {"要什么": "证据与报告口径", "走": "cap offense_ops op=evidence"},
                    {"要什么": "跨任务记忆", "走": "cap offense_ops op=memory"},
                    {"要什么": "过授权闸", "走": "cap offense_ops op=gate"},
                    {"要什么": "真扫/真打", "走": "sec_surface / sec_scan / sec_chain / code_audit / pentest_distill"}],
            "direct": True}


def run(op: str = "plan", **kw) -> dict:
    o = (op or "plan").strip().lower()
    if o == "plan":
        return plan(kw.get("target") or "", kw.get("scope") or "")
    if o == "roles":
        return roles()
    if o == "tools":
        return tools()
    if o == "evidence":
        return evidence()
    if o == "memory":
        return memory()
    if o == "gate":
        return gate(kw.get("action") or "")
    if o == "check":
        return check()
    if o == "route":
        return route(kw.get("target") or "")
    return {"ok": False, "reason": "unknown_op", "op": o, "known": list(OPS)}
