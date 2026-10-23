# -*- coding: utf-8 -*-
"""万能插 · 云电脑独立窗口（Cloud PC Window）· 只读骨架 v1.0

开发者：自由的风 · 守护者：公主土豆 · 禁止删除

形态（R-H284 主人定）：**面板上加一个独立窗口** —— 给她（数字人）**安装**一台云电脑。
不是 iframe 嵌网页（会撞跨域 + 登录态），是「**卡片 + 触手**」：卡片只呈现，
真要动就走触手，并且**过门**。

本模块**只读**：`provision / connect / snapshot / release` 一律 `not_implemented`
（本地没有云厂商凭据 ⇒ 与「自给自足大脑」的降级策略一致：返回 needs_external_key，
**不影响其他任务**）。
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Sequence

CAP_KIND = "cloud_pc"
DOMAIN = "infra"
CAP_TYPE = "external"
TRACE_SOURCE_KIND = "cloud_pc"

# 五原语 —— 谁花钱、谁不可逆，逐个标出来（不标就会被当成「都一样」）
PRIMITIVES = (
    {"key": "PROVISION", "cn": "开通安装", "reversible": False,
     "costs_money": True, "needs_gate": True,
     "note": "把云主机开出来、把底座装上去 —— **花钱 + 不可逆**"},
    {"key": "CONNECT", "cn": "连上", "reversible": True,
     "costs_money": False, "needs_gate": False,
     "note": "连上去干活；只读操作不写库"},
    {"key": "STATUS", "cn": "读数", "reversible": True,
     "costs_money": False, "needs_gate": False,
     "note": "配置 / 用量 / 账单读数（只读）"},
    {"key": "SNAPSHOT", "cn": "快照", "reversible": True,
     "costs_money": True, "needs_gate": False,
     "note": "留一份可回滚的镜像 —— 花钱但**可回滚**，所以不必卡门，但仍要留痕"},
    {"key": "RELEASE", "cn": "释放", "reversible": False,
     "costs_money": False, "needs_gate": True,
     "note": "退掉 —— **不可逆**，且**必须先给账单读数**"},
)

WINDOW = {
    "form": "面板卡⑦ · 独立窗口（与其他卡同级）",
    "not_iframe": "**不是 iframe 嵌网页**（跨域 + 登录态会撞）—— 是「卡片 + 触手」",
    "for_whom": "给她（数字人）装一台云电脑",
    "source_of_truth": "local",
    "card_shows": ("云主机状态（有没有 / 配置 / 用量 / 账单）",
                   "装到哪一步（安装进度**只呈现读数**，不代跑）",
                   "可回滚点（最近一次快照）"),
    "buttons_go_through": "run_task(\"cloud_pc\", {...}) → 过 auth_gate → 触手",
}

# 五条红线（R-H284 主人立项时定 · 与既有红线同族，不另立口径）
RED_LINES = (
    "密钥只存 DPAPI：云端凭据走密钥池，不许明文落盘、不许进返回值",
    "先算账再花钱：开通 / 释放前必须先给**资源与预算读数**，不许先花钱后算账",
    "每次操作留痕：写 trace_store，source_kind=cloud_pc",
    "不绕官方入口：走云厂商官方 CLI / SDK，不许自己拼请求",
    "身份内核不变：**她住在云上、身份源仍在本地** —— 云端不许改写身份内核",
)

# 现状（先取证，再说话）
CURRENT = {
    "credentials_present": False,
    "credential_note": "盘上无云厂商凭据（本地不存明文，也未见密钥池里有云主机条目）",
    "provider": None,
    "provider_note": "云厂商 / 规格 / 计费口径 **主人未给** ⇒ 本骨架**不编**"
                     "（未取证不引外部）",
    "local_pc_state": "本机可用，但**云电脑 ≠ 本机**：两处读数不许互相顶",
}

_KEYISH = re.compile(r"\b(?:sk|ak|eyJ|lta|LTAI)[-_A-Za-z0-9]{12,}\b")


def check_no_plaintext_key(payload: Any = None) -> dict:
    """带牙用例①：云凭据不走明文（进返回值也不行）。"""
    m = _KEYISH.search(str(payload or ""))
    if m:
        return {"ok": False, "denied": True, "rule": "plaintext_key",
                "masked": m.group(0)[:4] + "****",
                "why": "凭据只走密钥池（DPAPI）；明文一旦进返回值就等于落了两处"}
    return {"ok": True, "readonly": True, "checked": "payload", "hit": 0}


def check_budget_first(budget: Any = None, bill: Any = None,
                       action: str = "provision") -> dict:
    """带牙用例②：**先算账再花钱** —— 红线②。

    判据不是「有没有钱」，是「**有没有先给读数**」：
    没有预算读数、没有账单读数 ⇒ 不许往下走（哪怕动作本身很小）。
    """
    act = str(action or "").strip().lower()
    if act not in ("provision", "release", "snapshot"):
        return {"ok": True, "readonly": True, "action": act,
                "note": "非花钱 / 非不可逆动作 ⇒ 本闸不适用（不扩大化）"}
    miss = []
    if budget is None or (isinstance(budget, str) and not budget.strip()):
        miss.append("budget")
    if bill is None or (isinstance(bill, str) and not bill.strip()):
        miss.append("bill")
    if miss:
        return {"ok": False, "denied": True, "rule": "budget_bill_missing",
                "action": act, "missing": miss,
                "why": "花钱 / 不可逆动作之前必须先有**资源与预算读数**（预算 + 账单）——"
                       "「先花钱后算账」是本模块最贵的一种错"}
    return {"ok": True, "readonly": True, "action": act,
            "budget": budget, "bill": bill, "note": "两读数都在 ⇒ 放行"}


def must_trace(trace_ref: str = "", source_kind: str = "") -> dict:
    """带牙用例③：每次操作留痕（红线③）。"""
    ref = str(trace_ref or "").strip()
    if not ref:
        return {"ok": False, "denied": True, "rule": "call_not_traced",
                "why": "**无痕即未发生** —— 云电脑的每次操作都要写 trace_store"}
    sk = str(source_kind or "").strip()
    if sk != TRACE_SOURCE_KIND:
        return {"ok": False, "denied": True, "rule": "bad_source_kind",
                "source_kind": sk or "（未给）", "expected": TRACE_SOURCE_KIND,
                "why": "写 trace_store 时必须带 source_kind=\"%s\"（否则事后按来源筛不出来）"
                       % TRACE_SOURCE_KIND}
    return {"ok": True, "readonly": True, "trace_ref": ref, "source_kind": sk}


def check_via_official(entry: Optional[str] = None) -> dict:
    """红线④：必须走官方 CLI / SDK，不许自己拼请求。"""
    e = str(entry or "").strip().lower()
    if not e:
        return {"ok": False, "denied": True, "rule": "official_entry_missing",
                "why": "必须指明走的是**哪一条官方入口**（官方 CLI / 官方 SDK）"}
    ok = e.startswith("cli:") or e.startswith("sdk:")
    return {"ok": bool(ok), "readonly": True, "entry": e, "denied": (not ok),
            "rule": None if ok else "self_built_request",
            "why": None if ok else "**自己拼 HTTP 请求 = 绕官方入口** ⇒ 一律拒"}


_IDENTITY_WRITE = re.compile(r"(改写|覆盖|替换|重写|reset|overwrite).{0,8}(身份|人格|identity|内核)")


def check_identity_not_on_cloud(payload: Any = None) -> dict:
    """红线⑤：**她住在云上，身份源仍在本地** —— 云端的载荷不许带身份改写。"""
    text = str(payload or "")
    m = _IDENTITY_WRITE.search(text)
    if m:
        return {"ok": False, "denied": True, "rule": "identity_write_on_cloud",
                "hit": m.group(0)[:24],
                "why": "身份内核的源在本地；云端只跑**副本** ⇒ 不许在云上下身份改写指令"}
    return {"ok": True, "readonly": True, "checked": "payload", "hit": 0}


def _not_implemented(op: str) -> dict:
    return {"ok": False, "denied": True, "rule": "not_implemented", "op": op,
            "requires_external_key": True,
            "reason": "本地无云厂商凭据 ⇒ 本骨架只给形状与闸，**不假装能开通**",
            "next": "主人给凭据（走密钥池）+ 授权出网后，接官方 CLI / SDK"}


def run(op="status", **params) -> dict:
    """能力入口（只读骨架）：status / primitives / window / redlines /
    gate_key / gate_budget / gate_trace / gate_official / gate_identity。"""
    op = str(op or "status")
    if op == "status":
        return {"ok": True, "readonly": True, "kind": CAP_KIND, "domain": DOMAIN,
                "type": CAP_TYPE,
                "primitives": [dict(p) for p in PRIMITIVES],
                "window": dict(WINDOW),
                "red_lines": list(RED_LINES),
                "current": dict(CURRENT),
                "requires_external_key": True,
                "key_present": bool(CURRENT["credentials_present"]),
                "gate_trace": must_trace(TRACE_SOURCE_KIND, TRACE_SOURCE_KIND)}
    if op == "primitives":
        return {"ok": True, "readonly": True, "primitives": [dict(p) for p in PRIMITIVES]}
    if op == "window":
        return {"ok": True, "readonly": True, "window": dict(WINDOW)}
    if op == "redlines":
        return {"ok": True, "readonly": True, "red_lines": list(RED_LINES)}
    if op == "gate_key":
        return check_no_plaintext_key(params.get("payload"))
    if op == "gate_budget":
        return check_budget_first(params.get("budget"), params.get("bill"),
                                  params.get("action") or "provision")
    if op == "gate_trace":
        return must_trace(params.get("trace_ref"), params.get("source_kind"))
    if op == "gate_official":
        return check_via_official(params.get("entry"))
    if op == "gate_identity":
        return check_identity_not_on_cloud(params.get("payload"))
    if op in ("provision", "connect", "snapshot", "release"):
        return _not_implemented(op)
    raise ValueError("未知 op %r（可用：status/primitives/window/redlines/"
                     "gate_key/gate_budget/gate_trace/gate_official/gate_identity/"
                     "provision/connect/snapshot/release）" % (op,))


HONEST_BOUNDARY = (
    "本骨架保证『云电脑窗口的五原语 / 五条红线 / 五个闸』可查、可判；"
    "它**保证不了**「现在就能开通」—— 本地无云厂商凭据、云厂商与规格主人未给 ⇒ "
    "一律 not_implemented + requires_external_key。"
    "另：**云电脑 ≠ 本机**，两处读数不许互相顶（本机可用不代表云上可用）。"
)
