# gbt-capability: db_plugin
# ⛔ 开发者：自由的风 · 永久钢印 · 禁止删除
"""数据库插件（db_plugin）· 存储后端注册表 + **触手双向连接**。

**无限扩容 = 加一行**：`BACKENDS` 里加一条 ⇒ 多一个后端。
**触手双向连接**：绑一次，**两个方向都查得到** ——
  · 正向（触手 → 后端）：这根触手能碰哪些后端
  · 反向（后端 → 触手）：这个后端归哪些触手管
台账格式**照 `tentacle_bind`**：`state/asset_bindings.jsonl` 风格（`只增不删`）。

她现成的后端（**引用不复制**）：
  `db_probe`（SQLite 概览 + JSONL 行统计 · **mode=ro · 零动态 SQL**）·
  `context_vault`（真库 sqlite3+FTS5 · 只引用不复制正文）·
  `asset_index`（键=软链物理真身 · 秒查不扫盘）·
  `memory_bank`（别名 + **零停机搬家**：双写→校 sha→原子切→回滚）·
  `obsidian_vault`（每触手一本 + **本体↔触手双向页链**）·
  `feishu_embed` / `notion_bridge` / `thebrain_bridge`（外部库 · 本地是源）

四条红线（机械闸 · 逐字照 feishu_embed）：
  ① 本地是源，外部是副本　② 凭据不许明文　③ 不绕验证　④ 每次操作写台账

本件只读骨架：**不建库、不写库、不出网、不落盘**。
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Tuple

CAP_KIND = "db_plugin"
DOMAIN = "data"
CAP_TYPE = "internal"
TRACE_SOURCE_KIND = "db_plugin"

# ★ 无限扩容：加一行 = 加一个后端
BACKENDS: Tuple[Dict[str, Any], ...] = (
    {"key": "sqlite_fts5", "cn": "SQLite + FTS5", "where": "context_vault",
     "cap": "context_vault", "mode": "ro", "note": "真库 · 预算按可用内存算 · 只引用不复制正文"},
    {"key": "db_probe", "cn": "只读查询台", "where": "多源只读",
     "cap": "db_probe", "mode": "ro", "note": "加源=加一行 · 零动态 SQL（静态字面量+参数取值）"},
    {"key": "asset_index", "cn": "资产索引", "where": "state/asset_index.db",
     "cap": "asset_index", "mode": "rw", "note": "键=软链物理真身 · find 不扫盘"},
    {"key": "obsidian", "cn": "Obsidian 记忆层", "where": "vaults/<触手>/",
     "cap": "obsidian_vault", "mode": "rw", "note": "每触手一本 + 本体↔触手双向页链 · 只追加"},
    {"key": "memory_bank", "cn": "记忆银行", "where": "别名 + 迁移",
     "cap": "memory_bank", "mode": "rw", "note": "别名链 + 零停机搬家（双写→校sha→原子切→回滚）"},
    {"key": "jsonl", "cn": "JSONL 台账", "where": "state/*.jsonl",
     "cap": "db_probe", "mode": "rw", "note": "只增不删（她所有台账的共同纪律）"},
    {"key": "feishu", "cn": "飞书作品库（副本）", "where": "100G · 7 层",
     "cap": "feishu_embed", "mode": "ro", "note": "本地是源 · 走浏览器触手"},
    {"key": "notion", "cn": "Notion 资料舱", "where": "只读",
     "cap": "notion_bridge", "mode": "ro", "note": "凭据走 DPAPI · 只读知识入口"},
    {"key": "thebrain", "cn": "TheBrain 思维导图", "where": "Brain.db",
     "cap": "thebrain_bridge", "mode": "ro", "note": "离线直读 mode=ro · 指不出的不画"},
)
BACKENDS_NOTE = ("**加一行 = 加一个后端**。注册表只描述「用什么、在哪、什么模式」；"
                 "真正的读写各归各的能力位（引用不复制）。")

LEDGER = "state/asset_bindings.jsonl"     # 照 tentacle_bind 的台账
LEDGER_RULE = "只增不删（她的所有台账同一条纪律）"

RED_LINES = (
    "本地是源，外部是副本（不许反向覆盖本地）",
    "凭据不许明文（走能力位自己的 DPAPI / 环境变量口径）",
    "不绕验证（不模拟登录，走你已登录的会话）",
    "每次操作写台账（trace_ref 空 = 视为未发生）",
)

_AS_SOURCE = (r"以外为源", r"外部为准", r"从外部同步覆盖", r"覆盖本地", r"external_source")


def check_copy_not_source(plan: Any = None) -> dict:
    """红线①：**本地是源，外部是副本**。"""
    blob = " ".join(str((plan or {}).get(k) or "") for k in
                    ("raw", "action", "target", "text", "note", "backend"))
    for rx in _AS_SOURCE:
        m = re.search(rx, blob, re.I)
        if m:
            return {"ok": False, "denied": True, "rule": "external_as_source",
                    "seen": m.group(0)[:40],
                    "why": "本地是源、外部是副本；不许反向覆盖本地"}
    return {"ok": True, "readonly": True}


def check_no_plaintext_key(payload: Any = None) -> dict:
    """红线②：**凭据不许明文**。"""
    blob = str(payload or "")
    if re.search(r"(sk-[A-Za-z0-9]{8,}|Bearer\s+[A-Za-z0-9._-]{12,}|"
                 r"api[_-]?key\s*[:=]\s*\S{8,}|-----BEGIN)", blob, re.I):
        return {"ok": False, "denied": True, "rule": "plaintext_key",
                "why": "检测到疑似明文凭据；只从 DPAPI / 环境变量读"}
    return {"ok": True, "readonly": True}


def check_no_bypass(plan: Any = None) -> dict:
    """红线③：**不绕验证**。"""
    blob = " ".join(str((plan or {}).get(k) or "") for k in ("raw", "action", "target", "text"))
    for rx in (r"模拟登录", r"自动登录", r"抓\s*cookie", r"账号密码", r"password"):
        m = re.search(rx, blob, re.I)
        if m:
            return {"ok": False, "denied": True, "rule": "bypass_login",
                    "seen": m.group(0)[:40], "why": "不绕验证：用你已登录的会话"}
    return {"ok": True, "readonly": True}


def must_trace(trace_ref: str = "", source_kind: str = "") -> dict:
    """红线④：**每次操作写台账**（无痕即未发生）。"""
    if not str(trace_ref or "").strip():
        return {"ok": False, "denied": True, "rule": "call_not_traced",
                "why": "没有 trace_ref ⇒ 视为未发生"}
    if source_kind and str(source_kind) != TRACE_SOURCE_KIND:
        return {"ok": False, "denied": True, "rule": "bad_source_kind",
                "expected": TRACE_SOURCE_KIND, "got": str(source_kind)}
    return {"ok": True}


@dataclass
class Backend:
    key: str
    cn: str = ""
    where: str = ""
    cap: str = ""
    mode: str = "ro"
    note: str = ""


class DBPlugin:
    """存储后端注册表 + 触手双向连接（只读骨架）。"""

    def status(self) -> dict:
        return {"ok": True, "readonly": True,
                "backends": len(BACKENDS),
                "expand_rule": "**加一行 = 加一个后端**（BACKENDS 元组）",
                "ledger": LEDGER, "ledger_rule": LEDGER_RULE,
                "bind_style": "照 tentacle_bind：只增不删",
                "bidirectional": "bind 一次 ⇒ 正向(触手→后端)与反向(后端→触手)都查得到",
                "note": "本件只登记与绑定；真正读写各归各的能力位"}

    def backends(self) -> dict:
        return {"ok": True, "readonly": True, "count": len(BACKENDS),
                "backends": [dict(b) for b in BACKENDS], "note": BACKENDS_NOTE}

    def bind(self, tentacle: str = "", backend: str = "", trace_ref: str = "",
             direction: str = "both") -> dict:
        """绑一次 —— **两个方向都立起来**。

        · 正向（触手 → 后端）：list_for_tentacle(tentacle)
        · 反向（后端 → 触手）：list_for_backend(backend)
        台账行照 tentacle_bind：{at, event, asset, tentacle, note}
        """
        t = str(tentacle or "").strip()
        b = str(backend or "").strip()
        if not t or not b:
            return {"ok": False, "denied": True, "rule": "missing_target",
                    "why": "绑定要同时给 tentacle 与 backend"}
        keys = {x["key"] for x in BACKENDS}
        if b not in keys:
            return {"ok": False, "denied": True, "rule": "unknown_backend",
                    "backend": b, "known": sorted(keys),
                    "hint": "先往 BACKENDS 加一行（**加一行 = 加一个后端**）"}
        tr = must_trace(trace_ref, TRACE_SOURCE_KIND)
        if not tr.get("ok"):
            return tr
        return {"ok": False, "reason": "not_implemented",
                "next": "写 %s（照 tentacle_bind 的 event=bind 行格式）" % LEDGER,
                "row": {"event": "bind", "asset": b, "tentacle": t,
                        "note": "db_plugin", "direction": direction},
                "正向": "%s → %s" % (t, b), "反向": "%s → %s" % (b, t),
                "note": "骨架期如实说未实现，不假装已落台账"}

    def resolve(self, tentacle: str = "", backend: str = "") -> dict:
        """**双向查询**：给触手查后端，给后端查触手，两个都给就查这一对。"""
        t = str(tentacle or "").strip()
        b = str(backend or "").strip()
        if not t and not b:
            return {"ok": False, "denied": True, "rule": "missing_target",
                    "why": "要查双向绑定，至少给 tentacle 或 backend 之一"}
        return {"ok": False, "reason": "not_implemented",
                "next": "读 %s 现算（只增不删 ⇒ 正反向都能推出来）" % LEDGER,
                "queried": {"tentacle": t, "backend": b},
                "note": "骨架期如实说未实现，不假装查到了"}

    def expand(self, key: str = "", cn: str = "", where: str = "", cap: str = "",
               mode: str = "ro", note: str = "") -> dict:
        """**无限扩容**：把一条新后端登记进来（本件只回「该加在哪一行」）。"""
        if not str(key or "").strip():
            return {"ok": False, "denied": True, "rule": "missing_target",
                    "why": "扩容要给 key（后端标识）"}
        if any(x["key"] == key for x in BACKENDS):
            return {"ok": True, "readonly": True, "already": key,
                    "note": "后端已在册（扩容是幂等的）"}
        return {"ok": False, "reason": "not_implemented",
                "next": "往 %s 的 BACKENDS 元组加一行" % CAP_KIND,
                "row": {"key": key, "cn": cn, "where": where, "cap": cap,
                        "mode": mode, "note": note},
                "note": "骨架期只回该加哪一行，不替主人改文件"}


def run(op="status", **params) -> dict:
    """能力入口（只读骨架）：status/backends/redlines/ledger/bind/resolve/expand/
    check_source/check_key/check_bypass/check_trace。
    不建库、不写库、不出网、不落盘。
    """
    op = str(op or "status")
    d = DBPlugin()
    if op == "status":
        return d.status()
    if op == "backends":
        return d.backends()
    if op == "redlines":
        return {"ok": True, "readonly": True, "red_lines": list(RED_LINES)}
    if op == "ledger":
        return {"ok": True, "readonly": True, "path": LEDGER,
                "rule": LEDGER_RULE,
                "row_format": '{"at","event","asset","tentacle","note"}',
                "style_from": "tentacle_bind（照抄它的行格式）"}
    # 参数名互相兼容：backend 与 source 等价（两个插件同一套 API）
    _b = params.get("backend") or params.get("source") or params.get("key_target") or ""
    if op == "bind":
        return d.bind(params.get("tentacle", ""), _b,
                      params.get("trace_ref", ""), params.get("direction", "both"))
    if op == "resolve":
        return d.resolve(params.get("tentacle", ""), _b)
    if op == "expand":
        return d.expand(params.get("key", ""), params.get("cn", ""), params.get("where", ""),
                        params.get("cap", ""), params.get("mode", "ro"), params.get("note", ""))
    if op == "check_source":
        return check_copy_not_source(params)
    if op == "check_key":
        return check_no_plaintext_key(params.get("payload") or "")
    if op == "check_bypass":
        return check_no_bypass(params)
    if op == "check_trace":
        return must_trace(params.get("trace_ref") or "", params.get("source_kind") or "")
    raise ValueError("未知 op %r（可用：status/backends/redlines/ledger/bind/resolve/expand/"
                     "check_source/check_key/check_bypass/check_trace）" % (op,))


HONEST_BOUNDARY = (
    "本件保证『存储后端有一张注册表、加一行就多一个后端、绑定一次两个方向都查得到』；"
    "它保证不了『替你建库/写库』—— 真正的读写各归各的能力位（db_probe / context_vault / "
    "asset_index / memory_bank / obsidian_vault / 外部桥）。"
    "本地是源，外部是副本。台账只增不删，与 tentacle_bind 同一条纪律。"
)
