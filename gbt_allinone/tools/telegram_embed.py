# gbt-capability: telegram_embed
# ⛔ 开发者：自由的风 · 永久钢印 · 禁止删除
"""Telegram 镶嵌窗口（telegram_embed）· 只读骨架。

**形态**：面板上多一张卡（卡⑧「Telegram」），**走浏览器触手操作；Bot API 只作可选支路**。

为什么默认不用 API：Telegram 有官方 **Bot API**，但它要一个 **bot 身份**，
而「你这个号」跟「bot」**不是一回事** —— 用 bot 发不出你本人的人味，
也读不到你的私聊。Web 版走你已登录的会话，才等价于「你自己在操作」。
⇒ **默认走浏览器触手**；有 `TELEGRAM_BOT_TOKEN` 时才把 Bot API 当**可选支路**
（那时它走 Bot API 自己的凭据口径：只从 env/DPAPI 读，不入明文）。

四条红线（做成机械闸 · 逐字照 feishu_embed）：
  ① Telegram 是**副本**，本地是源　② 凭据不许明文　③ **不绕验证**（不模拟登录/不抓 Cookie）
  ④ 每次操作写 `trace_store`（`source_kind="telegram"`）

本骨架只读：**不打开浏览器、不出网、不落盘、不发密钥**。
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List

CAP_KIND = "telegram_embed"
DOMAIN = "integration"
CAP_TYPE = "external"          # 它是面板上的一道「门」
TRACE_SOURCE_KIND = "telegram"


class TelegramAction(Enum):
    OPEN_CHAT = "打开会话"
    OPEN_CHANNEL = "打开频道"
    OPEN_LIST = "会话列表"
    SEARCH = "搜索会话"
    LIST_RECENT = "最近消息"
    SEND_TEXT = "发消息（写）"


@dataclass
class TelegramWindow:
    mode: str = "browser_tentacle"     # **默认用浏览器触手**
    source_of_truth: str = "local"     # **本地是源，Telegram 是副本**
    bot_api_optional: bool = True      # Bot API 是**可选支路**，不是默认
    actions: List[TelegramAction] = field(default_factory=lambda: list(TelegramAction))


# Telegram 网页版（**官方入口 · 已知** ⇒ 登记，但不擅自请求）
TELEGRAM_HOSTS = (
    {"host": "web.telegram.org", "from": "官方 Web 版入口（K/A 两版）"},
    {"host": "t.me", "from": "官方短链（跳会话/频道）"},
)
HOSTS_NOTE = ("`web.telegram.org` 是官方 Web 版；登录态用你浏览器里已有的那条。"
              "Bot API（`api.telegram.org`）**只在配了 TELEGRAM_BOT_TOKEN 时**作为可选支路，"
              "本件**不请求、不验证、不落明文**。")

# 浏览器触手接入点（取证所得 · 引用不复制 · 与 feishu_embed 同一个触手）
BROWSER_TENTACLE = {
    "module": "gbt_allinone/browser_cap.py",
    "entry": "open_url",
    "siblings": ("open_url", "search", "fetch", "automate", "run"),
    "native": "gbt_allinone/native_browser.py（51 个函数）",
}

# 可选支路：Bot API 的凭据口径（只登记口径，不读值）
BOT_API_OPTIONAL = {
    "env": "TELEGRAM_BOT_TOKEN",
    "credential_rule": "只从环境变量 / DPAPI 读；**不入明文、不回显**",
    "why_not_default": "bot 身份 ≠ 你这个号；私聊与本人语气都拿不到",
    "when": "只有主人明确要『以 bot 身份跑自动化』时才走这条",
}

RED_LINES = (
    "Telegram 是副本，本地是源（本地已有多处口径未收口，不能再添一处）",
    "凭据不许明文（默认走浏览器触手 ⇒ 不需要新凭据；Bot API 支路也只从 env/DPAPI 读）",
    "不绕验证（用你已登录的会话，不模拟登录、不抓 Cookie）",
    "每次操作写 trace_store（source_kind=telegram，无痕即未发生）",
)

_BYPASS_LOGIN = (r"模拟登录", r"自动登录", r"扫码登录", r"抓\s*cookie", r"偷\s*cookie",
                 r"cookie\s*提取", r"账号密码", r"password", r"session\s*窃")
_AS_SOURCE = (r"以\s*telegram\s*为源", r"telegram\s*为准", r"从\s*telegram\s*同步覆盖",
              r"覆盖本地", r"telegram_source")


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
    """红线①：**Telegram 是副本，本地是源**（不许把它当真相源）。"""
    blob = " ".join(str((plan or {}).get(k) or "") for k in
                    ("raw", "action", "target", "text", "note"))
    for rx in _AS_SOURCE:
        m = re.search(rx, blob, re.I)
        if m:
            return {"ok": False, "denied": True, "rule": "telegram_as_source",
                    "seen": m.group(0)[:40],
                    "why": "本地是源、Telegram 是副本；不许反向覆盖本地"}
    return {"ok": True, "readonly": True}


def check_no_plaintext_key(payload: Any = None) -> dict:
    """红线②：**凭据不许明文**（含 bot token）。"""
    blob = str(payload or "")
    if re.search(r"(\d{8,12}:[A-Za-z0-9_-]{30,}|"          # Telegram bot token 形状
                 r"sk-[A-Za-z0-9]{8,}|Bearer\s+[A-Za-z0-9._-]{12,}|"
                 r"api[_-]?key\s*[:=]\s*\S{8,}|-----BEGIN)", blob, re.I):
        return {"ok": False, "denied": True, "rule": "plaintext_key",
                "why": "检测到疑似明文凭据（含 bot token 形状）；"
                       "只从 env / DPAPI 读，不许明文过手"}
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


class TelegramEmbed:
    """Telegram 镶嵌窗口（只读骨架）。"""

    def __init__(self) -> None:
        self.window = TelegramWindow()

    def _to_action(self, action: Any) -> TelegramAction:
        if isinstance(action, TelegramAction):
            return action
        s = str(action or "").strip()
        for a in TelegramAction:
            if s in (a.name, a.value):
                return a
        raise ValueError(s)

    def status(self) -> dict:
        return {"ok": True, "readonly": True,
                "mode": self.window.mode,
                "source_of_truth": self.window.source_of_truth,
                "bot_api_optional": self.window.bot_api_optional,
                "credential_needed": False,
                "network_needed": "user_session（你已登录的浏览器会话）",
                "tentacle": dict(BROWSER_TENTACLE),
                "bot_api": dict(BOT_API_OPTIONAL),
                "hosts": [dict(h) for h in TELEGRAM_HOSTS],
                "note": "面板卡⑧：只呈现 + 走浏览器触手打开；Bot API 是**可选支路**不是默认"}

    def open(self, action: Any = None, target: str = "") -> dict:
        """骨架期：**结构就位、真实调用待接**（如实说未实现，不假装打开了）。"""
        try:
            act = self._to_action(action)
        except ValueError:
            return {"ok": False, "denied": True, "rule": "unknown_action",
                    "action": str(action),
                    "known": [a.name for a in TelegramAction]}
        if act in (TelegramAction.OPEN_CHAT, TelegramAction.OPEN_CHANNEL,
                   TelegramAction.SEARCH) and not str(target or "").strip():
            return {"ok": False, "denied": True, "rule": "missing_target",
                    "action": act.value,
                    "why": "打开会话/频道 / 搜索要给出目标（联系人或关键词）"}
        if act is TelegramAction.SEND_TEXT:
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
    """能力入口（只读骨架）：status/actions/redlines/hosts/tentacle/botapi/
    check_bypass/check_source/check_key/check_trace/open。
    不打开浏览器、不出网、不落盘、不发密钥。
    """
    op = str(op or "status")
    if op == "status":
        return TelegramEmbed().status()
    if op == "actions":
        return {"ok": True, "readonly": True,
                "actions": [{"key": a.name, "cn": a.value} for a in TelegramAction]}
    if op == "redlines":
        return {"ok": True, "readonly": True, "red_lines": list(RED_LINES)}
    if op == "hosts":
        return {"ok": True, "readonly": True,
                "hosts": [dict(h) for h in TELEGRAM_HOSTS], "note": HOSTS_NOTE}
    if op == "tentacle":
        return {"ok": True, "readonly": True, **BROWSER_TENTACLE}
    if op == "botapi":
        return {"ok": True, "readonly": True, **BOT_API_OPTIONAL}
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
        return TelegramEmbed().open(params.get("action"), params.get("target") or "")
    raise ValueError("未知 op %r（可用：status/actions/redlines/hosts/tentacle/botapi/"
                     "check_bypass/check_source/check_key/check_trace/open）" % (op,))


HONEST_BOUNDARY = (
    "镶嵌窗口保证『面板上有 Telegram 入口、走浏览器触手操作、不需要新凭据』；"
    "它保证不了 API 级自动化 —— Bot API 要一个 bot 身份，"
    "而『你这个号』跟『bot』不是一回事。"
    "Telegram 是副本，本地是源。发消息是不可逆动作，一律停在授权门前。"
)
