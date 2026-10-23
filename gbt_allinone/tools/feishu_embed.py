# gbt-capability: feishu_embed
# ⛔ 开发者：自由的风 · 永久钢印 · 禁止删除
"""飞书镶嵌窗口（feishu_embed）· R-H239 只读骨架。

**形态**：面板上多一张卡（卡⑥「飞书」），**走浏览器触手操作，不走 API**。

为什么不用 API：凭据读不出（沙箱身份读不了 DPAPI）+ 出网受限 ⇒ API 路径跑不通；
走浏览器触手 ⇒ 用**你已登录的会话** ⇒ 不需要 DPAPI、不需要新密钥。

四条红线（做成机械闸）：
  ① 飞书是**副本**，本地是源　② 凭据不许明文　③ **不绕验证**（不模拟登录/不抓 Cookie）
  ④ 每次操作写 `trace_store`（`source_kind="feishu"`）

本骨架只读：**不打开浏览器、不出网、不落盘、不发密钥**。
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List

CAP_KIND = "feishu_embed"
DOMAIN = "integration"
CAP_TYPE = "external"          # 它是面板上的一道「门」
TRACE_SOURCE_KIND = "feishu"


class FeishuAction(Enum):
    OPEN_WIKI = "打开知识库"
    OPEN_DOC = "打开文档"
    OPEN_BASE = "打开多维表格"
    SEARCH = "搜索"
    LIST_RECENT = "最近文档"


@dataclass
class FeishuWindow:
    mode: str = "browser_tentacle"     # **用浏览器触手，不用 API**
    source_of_truth: str = "local"     # **本地是源，飞书是副本**
    actions: List[FeishuAction] = field(default_factory=lambda: list(FeishuAction))


# 飞书网页版（**主人提供 · 盘上未见** ⇒ 只登记、不擅自验证）
FEISHU_HOSTS = (
    {"host": "resonate.feishu.cn", "from": "主人提供"},
    {"host": "my.feishu.cn", "from": "主人提供"},
    {"host": "kjpt2h5ekoxy.jp.larksuite.com", "from": "主人提供"},
)
HOSTS_NOTE = ("三处 host **均由主人提供**；盘上**未抓到** feishu/larksuite URL ⇒ "
              "状态为「主人提供 · 盘上未见」，**不擅自验证、不擅自请求**。")

# 浏览器触手接入点（取证所得 · 引用不复制）
BROWSER_TENTACLE = {
    "module": "gbt_allinone/browser_cap.py",
    "entry": "open_url",
    "siblings": ("open_url", "search", "fetch", "automate", "run"),
    "native": "gbt_allinone/native_browser.py（51 个函数）",
}

RED_LINES = (
    "飞书是副本，本地是源（三处知识库未收口，飞书不能再添第四处）",
    "凭据不许明文（走浏览器触手 ⇒ 本来就不需要新凭据）",
    "不绕验证（用你已登录的会话，不模拟登录、不抓 Cookie）",
    "每次操作写 trace_store（source_kind=feishu，无痕即未发生）",
)

_BYPASS_LOGIN = (r"模拟登录", r"自动登录", r"抓\s*cookie", r"偷\s*cookie",
                 r"cookie\s*提取", r"账号密码", r"password")
_AS_SOURCE = (r"以飞书为源", r"飞书为准", r"从飞书同步覆盖", r"覆盖本地",
              r"feishu_source")


def check_no_bypass(plan: Any = None) -> dict:
    """红线③：**不绕验证**（不模拟登录、不抓 Cookie）。"""
    blob = " ".join(str((plan or {}).get(k) or "") for k in
                    ("raw", "action", "target", "text"))
    for rx in _BYPASS_LOGIN:
        m = re.search(rx, blob, re.I)
        if m:
            return {"ok": False, "denied": True, "rule": "bypass_login",
                    "seen": m.group(0)[:40],
                    "why": "不绕验证：用你已登录的浏览器会话；"
                           "模拟登录 / 抓 Cookie 一律拒"}
    return {"ok": True, "readonly": True}


def check_copy_not_source(plan: Any = None) -> dict:
    """红线①：**飞书是副本，本地是源**（不许把飞书当真相源）。"""
    blob = " ".join(str((plan or {}).get(k) or "") for k in
                    ("raw", "action", "target", "text"))
    for rx in _AS_SOURCE:
        m = re.search(rx, blob, re.I)
        if m:
            return {"ok": False, "denied": True, "rule": "feishu_as_source",
                    "seen": m.group(0)[:40],
                    "why": "本地是真相源、飞书做镜像/外发；"
                           "把飞书当源 = 给知识库口径再添一处（已有三处未收口）"}
    return {"ok": True, "readonly": True, "source_of_truth": "local"}


def check_no_plaintext_key(payload: Any = None) -> dict:
    """红线②：**凭据不许明文**（走浏览器触手本就不需要凭据）。"""
    m = re.search(r"\b(?:sk|ak|lt|ghp|cli_)[-_A-Za-z0-9]{12,}\b", str(payload or ""))
    if m:
        return {"ok": False, "denied": True, "rule": "plaintext_key",
                "seen": m.group(0)[:10],
                "why": "凭据不许明文；本方案走浏览器触手，压根不需要新凭据"}
    return {"ok": True, "readonly": True, "credential_needed": False}


def must_trace(trace_ref: str = "", source_kind: str = "") -> dict:
    """红线④：**每次操作写 trace_store**（source_kind=feishu）。"""
    ref = str(trace_ref or "").strip()
    if not ref:
        return {"ok": False, "denied": True, "rule": "call_not_traced",
                "why": "每次打开/操作飞书都要留痕（调用级）；无痕即未发生"}
    sk = str(source_kind or "").strip()
    if sk != TRACE_SOURCE_KIND:
        return {"ok": False, "denied": True, "rule": "bad_source_kind",
                "source_kind": sk or "（未给）", "expected": TRACE_SOURCE_KIND,
                "why": "留痕必须带 source_kind=%s（否则事后按来源筛不出）"
                       % TRACE_SOURCE_KIND}
    return {"ok": True, "readonly": True, "trace_ref": ref, "source_kind": sk}


class FeishuEmbed:
    """镶嵌窗口（骨架）：**只登记动作与路由形状，不真打开浏览器**。"""

    def __init__(self) -> None:
        self.window = FeishuWindow()

    @staticmethod
    def _to_action(a: Any):
        """**name 与 value 都认**（实测踩过：只认 value ⇒ "OPEN_WIKI" 会被判未知）。"""
        if isinstance(a, FeishuAction):
            return a
        s = str(a or "").strip()
        for m in FeishuAction:
            if s == m.name or s == m.value:
                return m
        raise ValueError(s)

    def status(self) -> dict:
        return {"ok": True, "readonly": True,
                "mode": self.window.mode,
                "source_of_truth": self.window.source_of_truth,
                "credential_needed": False,
                "network_needed": "user_session（你已登录的浏览器会话）",
                "tentacle": dict(BROWSER_TENTACLE),
                "hosts": [dict(h) for h in FEISHU_HOSTS],
                "note": "面板卡⑥：只呈现 + 走浏览器触手打开；**本刀不改面板**"}

    def open(self, action: Any = None, target: str = "") -> dict:
        """骨架期：**结构就位、真实调用待接**（如实说未实现，不假装打开了）。"""
        try:
            act = self._to_action(action)
        except ValueError:
            return {"ok": False, "denied": True, "rule": "unknown_action",
                    "action": str(action),
                    "known": [a.name for a in FeishuAction]}
        if act in (FeishuAction.OPEN_WIKI, FeishuAction.OPEN_DOC,
                   FeishuAction.OPEN_BASE) and not str(target or "").strip():
            return {"ok": False, "denied": True, "rule": "missing_target",
                    "action": act.value,
                    "why": "打开类动作要给出目标（知识库/文档/表格）"}
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
        return FeishuEmbed().status()
    if op == "actions":
        return {"ok": True, "readonly": True,
                "actions": [{"key": a.name, "cn": a.value} for a in FeishuAction]}
    if op == "redlines":
        return {"ok": True, "readonly": True, "red_lines": list(RED_LINES)}
    if op == "hosts":
        return {"ok": True, "readonly": True,
                "hosts": [dict(h) for h in FEISHU_HOSTS], "note": HOSTS_NOTE}
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
        return FeishuEmbed().open(params.get("action"), params.get("target") or "")
    raise ValueError("未知 op %r（可用：status/actions/redlines/hosts/tentacle/"
                     "check_bypass/check_source/check_key/check_trace/open）" % (op,))


HONEST_BOUNDARY = (
    "镶嵌窗口保证『面板上有飞书入口、走浏览器触手操作、不需要新凭据』；"
    "它保证不了 API 级自动化 —— API 路径需要凭据 + 出网，当前两者都受限。"
    "飞书是副本，本地是源。三处 host 由主人提供、盘上未验证。"
)
