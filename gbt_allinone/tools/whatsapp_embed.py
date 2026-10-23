# gbt-capability: whatsapp_embed
# ⛔ 开发者：自由的风 · 永久钢印 · 禁止删除
"""WhatsApp 镶嵌窗口（whatsapp_embed）· 只读骨架。

**形态**：面板上多一张卡（卡⑦「WhatsApp」），**走浏览器触手操作，不走 API**。

为什么不用 API：WhatsApp 的官方 API（Cloud API）走的是 **Business 账号 + 独立号码**，
不是「你这个号」；而且要吃凭据 + 出网。走浏览器触手 ⇒ 用**你已登录的会话**
⇒ 不需要 DPAPI、不需要新凭据、不碰你的号。

四条红线（做成机械闸 · 逐字照 feishu_embed）：
  ① WhatsApp 是**副本**，本地是源　② 凭据不许明文　③ **不绕验证**（不模拟登录/不抓 Cookie）
  ④ 每次操作写 `trace_store`（`source_kind="whatsapp"`）

本骨架只读：**不打开浏览器、不出网、不落盘、不发密钥**。
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List

CAP_KIND = "whatsapp_embed"
DOMAIN = "integration"
CAP_TYPE = "external"          # 它是面板上的一道「门」
TRACE_SOURCE_KIND = "whatsapp"


class WhatsAppAction(Enum):
    OPEN_CHAT = "打开会话"
    OPEN_LIST = "会话列表"
    SEARCH = "搜索会话"
    LIST_RECENT = "最近消息"
    SEND_TEXT = "发消息（写）"


@dataclass
class WhatsAppWindow:
    mode: str = "browser_tentacle"     # **用浏览器触手，不用 API**
    source_of_truth: str = "local"     # **本地是源，WhatsApp 是副本**
    actions: List[WhatsAppAction] = field(default_factory=lambda: list(WhatsAppAction))


# WhatsApp 网页版（**官方入口 · 已知** ⇒ 登记，但不擅自请求）
WHATSAPP_HOSTS = (
    {"host": "web.whatsapp.com", "from": "官方 Web 版入口"},
    {"host": "wa.me", "from": "官方短链（跳会话）"},
)
HOSTS_NOTE = ("`web.whatsapp.com` 是官方 Web 版入口；**登录态用你浏览器里已有的那条**，"
              "本件**不登入、不抓 Cookie、不请求**。")

# 浏览器触手接入点（取证所得 · 引用不复制 · 与 feishu_embed 同一个触手）
BROWSER_TENTACLE = {
    "module": "gbt_allinone/browser_cap.py",
    "entry": "open_url",
    "siblings": ("open_url", "search", "fetch", "automate", "run"),
    "native": "gbt_allinone/native_browser.py（51 个函数）",
}

RED_LINES = (
    "WhatsApp 是副本，本地是源（本地已有多处口径未收口，不能再添一处）",
    "凭据不许明文（走浏览器触手 ⇒ 本来就不需要新凭据）",
    "不绕验证（用你已登录的会话，不模拟登录、不抓 Cookie）",
    "每次操作写 trace_store（source_kind=whatsapp，无痕即未发生）",
)

_BYPASS_LOGIN = (r"模拟登录", r"自动登录", r"扫码登录", r"抓\s*cookie", r"偷\s*cookie",
                 r"cookie\s*提取", r"账号密码", r"password", r"session\s*窃")
_AS_SOURCE = (r"以\s*whatsapp\s*为源", r"whatsapp\s*为准", r"从\s*whatsapp\s*同步覆盖",
              r"覆盖本地", r"whatsapp_source")


def check_no_bypass(plan: Any = None) -> dict:
    """红线③：**不绕验证**（不模拟登录、不扫码代登、不抓 Cookie）。"""
    blob = " ".join(str((plan or {}).get(k) or "") for k in
                    ("raw", "action", "target", "text"))
    for rx in _BYPASS_LOGIN:
        m = re.search(rx, blob, re.I)
        if m:
            return {"ok": False, "denied": True, "rule": "bypass_login",
                    "seen": m.group(0)[:40],
                    "why": "不绕验证：用你已登录的浏览器会话；"
                           "模拟登录 / 扫码代登 / 抓 Cookie 一律拒"}
    return {"ok": True, "readonly": True}


def check_copy_not_source(plan: Any = None) -> dict:
    """红线①：**WhatsApp 是副本，本地是源**（不许把它当真相源）。"""
    blob = " ".join(str((plan or {}).get(k) or "") for k in
                    ("raw", "action", "target", "text", "note"))
    for rx in _AS_SOURCE:
        m = re.search(rx, blob, re.I)
        if m:
            return {"ok": False, "denied": True, "rule": "whatsapp_as_source",
                    "seen": m.group(0)[:40],
                    "why": "本地是源、WhatsApp 是副本；不许反向覆盖本地"}
    return {"ok": True, "readonly": True}


def check_no_plaintext_key(payload: Any = None) -> dict:
    """红线②：**凭据不许明文**。"""
    blob = str(payload or "")
    if re.search(r"(sk-[A-Za-z0-9]{8,}|Bearer\s+[A-Za-z0-9._-]{12,}|"
                 r"api[_-]?key\s*[:=]\s*\S{8,}|-----BEGIN)", blob, re.I):
        return {"ok": False, "denied": True, "rule": "plaintext_key",
                "why": "检测到疑似明文凭据；本方案不需要新凭据，"
                       "真要也不许明文过手（走 DPAPI / 环境变量）"}
    return {"ok": True, "readonly": True}


def must_trace(trace_ref: str = "", source_kind: str = "") -> dict:
    """红线④：**每次操作写 trace_store**（无痕即未发生）。"""
    if not str(trace_ref or "").strip():
        return {"ok": False, "denied": True, "rule": "call_not_traced",
                "why": "没有 trace_ref ⇒ 视为未发生"}
    if str(source_kind or "") != TRACE_SOURCE_KIND:
        return {"ok": False, "denied": True, "rule": "bad_source_kind",
                "expected": TRACE_SOURCE_KIND, "got": str(source_kind)}
    return {"ok": True}


class WhatsAppEmbed:
    """WhatsApp 镶嵌窗口（只读骨架）。"""

    def __init__(self) -> None:
        self.window = WhatsAppWindow()

    def _to_action(self, action: Any) -> WhatsAppAction:
        if isinstance(action, WhatsAppAction):
            return action
        s = str(action or "").strip()
        for a in WhatsAppAction:
            if s in (a.name, a.value):
                return a
        raise ValueError(s)

    def status(self) -> dict:
        return {"ok": True, "readonly": True,
                "mode": self.window.mode,
                "source_of_truth": self.window.source_of_truth,
                "credential_needed": False,
                "network_needed": "user_session（你已登录的浏览器会话）",
                "tentacle": dict(BROWSER_TENTACLE),
                "hosts": [dict(h) for h in WHATSAPP_HOSTS],
                "note": "面板卡⑦：只呈现 + 走浏览器触手打开；**本刀不改面板**"}

    def open(self, action: Any = None, target: str = "") -> dict:
        """骨架期：**结构就位、真实调用待接**（如实说未实现，不假装打开了）。"""
        try:
            act = self._to_action(action)
        except ValueError:
            return {"ok": False, "denied": True, "rule": "unknown_action",
                    "action": str(action),
                    "known": [a.name for a in WhatsAppAction]}
        if act in (WhatsAppAction.OPEN_CHAT, WhatsAppAction.SEARCH) \
                and not str(target or "").strip():
            return {"ok": False, "denied": True, "rule": "missing_target",
                    "action": act.value,
                    "why": "打开会话 / 搜索要给出目标（联系人或关键词）"}
        if act is WhatsAppAction.SEND_TEXT:
            return {"ok": False, "denied": True, "rule": "needs_gate",
                    "action": act.value,
                    "why": "发消息是**不可逆 + 出网**动作 ⇒ 停在主人的授权门前",
                    "gate": "deploy_publish 或主人手发（本骨架不提供绕过路径）"}
        return {"ok": False, "reason": "not_implemented",
                "next": "接浏览器触手（原生优先）：%s.%s"
                        % (BROWSER_TENTACLE["module"], BROWSER_TENTACLE["entry"]),
                "action": act.value, "target": str(target or ""),
                "credential_needed": False,
                "note": "骨架期如实说未实现，不假装已打开"}


def run(op="status", **params) -> dict:
    """能力入口（只读骨架）：status/actions/redlines/hosts/tentacle/
    check_bypass/check_source/check_key/check_trace/open。
    不打开浏览器、不出网、不落盘、不发密钥。
    """
    op = str(op or "status")
    if op == "status":
        return WhatsAppEmbed().status()
    if op == "actions":
        return {"ok": True, "readonly": True,
                "actions": [{"key": a.name, "cn": a.value} for a in WhatsAppAction]}
    if op == "redlines":
        return {"ok": True, "readonly": True, "red_lines": list(RED_LINES)}
    if op == "hosts":
        return {"ok": True, "readonly": True,
                "hosts": [dict(h) for h in WHATSAPP_HOSTS], "note": HOSTS_NOTE}
    if op == "tentacle":
        return {"ok": True, "readonly": True, **BROWSER_TENTACLE}
    if op == "check_bypass":
        return check_no_bypass(params)
    if op == "check_source":
        return check_copy_not_source(params)
    if op == "check_key":
        return check_no_plaintext_key(params.get("payload") or "")
    if op == "check_trace":
        return must_trace(params.get("trace_ref") or "",
                          params.get("source_kind") or "")
    if op == "open":
        return WhatsAppEmbed().open(params.get("action"), params.get("target") or "")
    raise ValueError("未知 op %r（可用：status/actions/redlines/hosts/tentacle/"
                     "check_bypass/check_source/check_key/check_trace/open）" % (op,))


HONEST_BOUNDARY = (
    "镶嵌窗口保证『面板上有 WhatsApp 入口、走浏览器触手操作、不需要新凭据』；"
    "它保证不了 API 级自动化 —— 官方 API 走 Business 账号 + 独立号码，"
    "跟『你这个号』不是一回事，且需要凭据 + 出网。"
    "WhatsApp 是副本，本地是源。发消息是不可逆动作，一律停在授权门前。"
)
