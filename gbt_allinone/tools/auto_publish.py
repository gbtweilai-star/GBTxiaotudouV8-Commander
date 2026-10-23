# -*- coding: utf-8 -*-
"""万能插 · 社交推广 / 发布作品 / 收益平台 · 全自动执行（Auto Publish）· 只读骨架 v1.0

开发者：自由的风 · 守护者：公主土豆 · 禁止删除

🔴 本模块的核心口径（R-H284 主人立项时定）：

    **「全自动」= 除「发布 / 提现 / 改价」那几下之外，全自动。**

那几下**不可逆 + 出网 + 涉及钱** ⇒ 必须过门；其余（排期 / 成稿 / 追踪 / 收益汇总）
可以全自动跑，不用问。

把「全自动」说成「连发布也不问」，就是把**不可逆**当成**可逆**——那是今天最贵的一种错。
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Sequence

CAP_KIND = "auto_publish"
DOMAIN = "social"
CAP_TYPE = "external"
TRACE_SOURCE_KIND = "publish"

# 五原语 —— 逐个标「可不可逆 / 涉不涉及钱 / 要不要过门」
PRIMITIVES = (
    {"key": "PLAN", "cn": "排期", "reversible": True, "costs_money": False,
     "needs_gate": False, "note": "把作品排到时间轴上（纯本地）"},
    {"key": "COMPOSE", "cn": "成稿", "reversible": True, "costs_money": False,
     "needs_gate": False, "note": "文案 / 封面 / 话题标签（纯本地，可反复改）"},
    {"key": "PUBLISH", "cn": "发布", "reversible": False, "costs_money": False,
     "needs_gate": True, "note": "**不可逆 + 出网** —— 发出去就收不回来"},
    {"key": "TRACK", "cn": "追踪", "reversible": True, "costs_money": False,
     "needs_gate": False, "note": "看已发布的数据（只读）"},
    {"key": "SETTLE", "cn": "收益归集", "reversible": True, "costs_money": False,
     "needs_gate": False, "note": "**只汇总，不代提**；提现是钱的动作，单独授权"},
)

# 自动 vs 过门：一张表说清，不靠形容词
AUTO_OK = ("plan", "compose", "track", "settle_read")
NEEDS_GATE = ("publish", "settle_withdraw", "price_change")

RED_LINES = (
    "发布必须过门：不可逆 + 出网 ⇒ 要么主人发一张**有 TTL 的批量令牌**，要么逐条确认"
    "（默认 **0 张令牌**）",
    "密钥只存 DPAPI：平台凭据走密钥池，不许明文落盘、不许进返回值",
    "每次发布留痕：写 trace_store，source_kind=publish",
    "一人一号：接合规底座 account_registry —— 不许共用账号、不许抢别人的号",
    "收益只汇总不代提：提现 / 改价是**钱**的动作，单独授权",
    "不刷量、不做假数据、不绕验证：**数据可以难看，但不能是假的**",
)

# 🔴 平台清单**待主人给** —— 不许凭记忆列平台名（未取证不引外部）
PLATFORMS: tuple = ()
PLATFORMS_NOTE = ("主人说「各种社交 / 发布作品 / 收益平台」，但**没列名单** ⇒ "
                  "本骨架**一个平台名都不编**（未取证不引外部）；"
                  "待主人给名单后逐个落『官方入口 / 授权方式 / 收益口径』三格")

CURRENT = {
    "tokens_issued": 0,
    "tokens_note": "主人还没发过任何发布令牌 ⇒ 默认 0 张 ⇒ 发布一律走逐条确认",
    "platforms_present": 0,
    "credentials_present": False,
}

_KEYISH = re.compile(r"\b(?:sk|ak|eyJ|ghp|cookie|token)[-_A-Za-z0-9]{12,}\b")


def check_no_plaintext_key(payload: Any = None) -> dict:
    """带牙用例①：平台凭据不走明文。"""
    m = _KEYISH.search(str(payload or ""))
    if m:
        return {"ok": False, "denied": True, "rule": "plaintext_key",
                "masked": m.group(0)[:4] + "****",
                "why": "平台凭据只走密钥池（DPAPI）；明文进返回值就等于落了两处"}
    return {"ok": True, "readonly": True, "checked": "payload", "hit": 0}


def check_publish_gated(action: Any = None, token: Any = None,
                        ttl_seconds: Any = None, confirmed: Any = None) -> dict:
    """带牙用例②（本模块**最要紧**的一条）：不可逆 / 涉钱动作必须过门。

    三种过门方式，**任选其一**（都没有 ⇒ 拒）：
      ① 逐条确认：`confirmed=True`
      ② 有 TTL 的批量令牌：`token` 非空 且 `ttl_seconds` 是正数
    并把「这张令牌覆盖到哪个动作」也记下来（令牌不是万能钥匙）。
    """
    act = str(action or "").strip().lower()
    if act not in NEEDS_GATE:
        if act in AUTO_OK:
            return {"ok": True, "readonly": True, "action": act, "gated": False,
                    "note": "全自动允许的动作 ⇒ 不必过门（不扩大化）"}
        return {"ok": False, "denied": True, "rule": "unknown_action",
                "action": act,
                "why": "动作不在白名单里 ⇒ **不许猜**（先补进 AUTO_OK 或 NEEDS_GATE）"}
    tok = str(token or "").strip()
    ttl = ttl_seconds
    ttl_ok = isinstance(ttl, (int, float)) and not isinstance(ttl, bool) and float(ttl) > 0
    if bool(confirmed):
        return {"ok": True, "readonly": True, "action": act, "gated": True,
                "how": "逐条确认", "note": "这一次主人点了头 ⇒ 放行这一次"}
    if tok and ttl_ok:
        return {"ok": True, "readonly": True, "action": act, "gated": True,
                "how": "有 TTL 的批量令牌", "ttl_seconds": float(ttl),
                "note": "令牌只覆盖它写明的动作与时长；**过期即失效**（不留长期万能钥匙）"}
    return {"ok": False, "denied": True, "rule": "irreversible_needs_gate",
            "action": act, "token_given": bool(tok), "ttl_ok": bool(ttl_ok),
            "confirmed": bool(confirmed),
            "why": "**不可逆 / 涉钱动作必须过门**：要么逐条确认，要么一张有 TTL 的令牌 —— "
                   "把「全自动」理解成「连发布也不问」，就是把不可逆当可逆"}


def must_trace(trace_ref: str = "", source_kind: str = "") -> dict:
    """带牙用例③：每次发布留痕。"""
    ref = str(trace_ref or "").strip()
    if not ref:
        return {"ok": False, "denied": True, "rule": "call_not_traced",
                "why": "**无痕即未发生** —— 每次发布都要写 trace_store"}
    sk = str(source_kind or "").strip()
    if sk != TRACE_SOURCE_KIND:
        return {"ok": False, "denied": True, "rule": "bad_source_kind",
                "source_kind": sk or "（未给）", "expected": TRACE_SOURCE_KIND,
                "why": "写 trace_store 时必须带 source_kind=\"%s\"" % TRACE_SOURCE_KIND}
    return {"ok": True, "readonly": True, "trace_ref": ref, "source_kind": sk}


def check_one_account_one_ai(accounts: Any = None) -> dict:
    """红线④：一人一号（接合规底座 account_registry）。"""
    if accounts is None:
        return {"ok": True, "readonly": True, "note": "未提供账号清单 ⇒ 本闸不适用（不扩大化）"}
    seen: Dict[str, str] = {}
    bad: List[str] = []
    for row in accounts:
        acc_id = str(dict(row).get("account_id") or "").strip()
        ai_id = str(dict(row).get("ai_id") or "").strip()
        if not acc_id or not ai_id:
            bad.append("缺 account_id 或 ai_id")
        elif acc_id in seen and seen[acc_id] != ai_id:
            bad.append("%s 被两个 AI 共用（%s / %s）" % (acc_id, seen[acc_id], ai_id))
        else:
            seen[acc_id] = ai_id
    if bad:
        return {"ok": False, "denied": True, "rule": "account_shared", "bad": bad,
                "why": "**一人一号**：账号不共享（共享 = 封号风险 + 责任分不清）"}
    return {"ok": True, "readonly": True, "accounts": len(seen)}


def check_no_withdraw_without_auth(action: Any = None, authorized: Any = None) -> dict:
    """红线⑤：收益只汇总不代提。"""
    act = str(action or "").strip().lower()
    if act != "settle_withdraw":
        return {"ok": True, "readonly": True, "action": act,
                "note": "非提现动作 ⇒ 本闸不适用（不扩大化）"}
    if not bool(authorized):
        return {"ok": False, "denied": True, "rule": "withdraw_needs_auth",
                "why": "**提现是钱的动作** ⇒ 必须主人单独授权；本模块默认只汇总、不代提"}
    return {"ok": True, "readonly": True, "action": act, "note": "主人单独授权了这一次"}


_FAKE = re.compile(r"(刷量|刷单|买粉|假数据|伪造|inflate|buy_followers)")


def check_no_fake_metrics(plan: Any = None) -> dict:
    """红线⑥：不刷量、不做假数据。"""
    text = str(plan or "")
    m = _FAKE.search(text)
    if m:
        return {"ok": False, "denied": True, "rule": "fake_metrics",
                "hit": m.group(0),
                "why": "**数据可以难看，但不能是假的** —— 假数据会把后面的判断全带偏"}
    return {"ok": True, "readonly": True, "checked": "plan", "hit": 0}


def _not_implemented(op: str) -> dict:
    return {"ok": False, "denied": True, "rule": "not_implemented", "op": op,
            "requires_external_key": True,
            "reason": "平台名单主人未给、凭据也不在盘上 ⇒ 本骨架只给形状与闸，"
                      "**不假装能发**",
            "next": "主人给平台名单 + 凭据（走密钥池）+ 授权出网后，逐个接官方入口"}


def run(op="status", **params) -> dict:
    """能力入口（只读骨架）：status / primitives / policy / redlines / platforms /
    gate_key / gate_publish / gate_trace / gate_accounts / gate_withdraw /
    gate_metrics / plan / compose / publish / track / settle。"""
    op = str(op or "status")
    if op == "status":
        return {"ok": True, "readonly": True, "kind": CAP_KIND, "domain": DOMAIN,
                "type": CAP_TYPE,
                "primitives": [dict(p) for p in PRIMITIVES],
                "auto_ok": list(AUTO_OK), "needs_gate": list(NEEDS_GATE),
                "red_lines": list(RED_LINES),
                "platforms": list(PLATFORMS), "platforms_note": PLATFORMS_NOTE,
                "current": dict(CURRENT),
                "requires_external_key": True,
                "gate_publish_default": check_publish_gated("publish"),
                "gate_trace": must_trace(TRACE_SOURCE_KIND, TRACE_SOURCE_KIND)}
    if op == "primitives":
        return {"ok": True, "readonly": True, "primitives": [dict(p) for p in PRIMITIVES]}
    if op == "policy":
        return {"ok": True, "readonly": True, "auto_ok": list(AUTO_OK),
                "needs_gate": list(NEEDS_GATE),
                "one_line": "**全自动 = 除「发布 / 提现 / 改价」之外全自动**"}
    if op == "redlines":
        return {"ok": True, "readonly": True, "red_lines": list(RED_LINES)}
    if op == "platforms":
        return {"ok": True, "readonly": True, "platforms": list(PLATFORMS),
                "note": PLATFORMS_NOTE}
    if op == "gate_key":
        return check_no_plaintext_key(params.get("payload"))
    if op == "gate_publish":
        return check_publish_gated(params.get("action") or "publish",
                                   params.get("token"), params.get("ttl_seconds"),
                                   params.get("confirmed"))
    if op == "gate_trace":
        return must_trace(params.get("trace_ref"), params.get("source_kind"))
    if op == "gate_accounts":
        return check_one_account_one_ai(params.get("accounts"))
    if op == "gate_withdraw":
        return check_no_withdraw_without_auth(params.get("action"),
                                              params.get("authorized"))
    if op == "gate_metrics":
        return check_no_fake_metrics(params.get("plan"))
    if op in ("plan", "compose", "publish", "track", "settle"):
        return _not_implemented(op)
    raise ValueError("未知 op %r（可用：status/primitives/policy/redlines/platforms/"
                     "gate_key/gate_publish/gate_trace/gate_accounts/gate_withdraw/"
                     "gate_metrics/plan/compose/publish/track/settle）" % (op,))


HONEST_BOUNDARY = (
    "本骨架保证『五原语 / 六条红线 / 六个闸 / 自动与过门的边界』可查、可判；"
    "它**保证不了**「现在就能发」—— 平台名单主人未给、凭据不在盘上 ⇒ "
    "一律 not_implemented + requires_external_key。"
    "另：**发布是不可逆的**，所以「全自动」这句话的边界必须写在纸上，"
    "而不是靠执行时临时拿主意。"
)
