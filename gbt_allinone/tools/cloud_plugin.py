# gbt-capability: cloud_plugin
# ⛔ 开发者：自由的风 · 永久钢印 · 禁止删除
"""云插件（cloud_plugin）· 云源注册表 + **触手双向连接**。

**无限扩容 = 加一行**：`SOURCES` 里加一条 ⇒ 多一个云源。
**触手双向连接**：绑一次，**两个方向都查得到** ——
  · 正向（触手 → 云源）：这根触手能用哪些云
  · 反向（云源 → 触手）：这个云源归哪些触手用
台账格式**照 `tentacle_bind`**：`state/asset_bindings.jsonl` 风格（`只增不删`）。

她现成的云源（**引用不复制**）：
  `cloud_pc`（五原语 · 云电脑）· `pod_link`（云卡触手 · 本机⇄GPU卡）·
  `comfy_cloud`（云卡 ComfyUI）· `energy_pool`（17 个能源 · **模型=燃料不是身份**）·
  `key_gateway`（**唯一密钥真源** + 链序/冷却/禁用/耗尽/换道）·
  `freellmapi`（本机免费大模型池）· `a1art_skill` / `h3_video_gen` / `libtv_skill` / `tripo`（云 API 技能）

**花钱判据（照 cloud_pc 的口径）**：花钱且不可逆 ⇒ 卡门；
花钱但可回滚（如快照）⇒ 不卡门但要留痕；不花钱的只读 ⇒ 直连。

五条红线（机械闸 · 逐字照 cloud_pc）：
  ① 密钥 DPAPI　② **先算账再花钱**　③ 每次留痕 `source_kind=cloud_plugin`
  ④ 不绕官方入口　⑤ 身份内核不变（换云不改「她是谁」）

本件：**不开机器、不花钱、不出网**；`bind` 只往 `state/asset_bindings.jsonl` **追加一行**
（只增不删，与 `tentacle_bind` 同一本账，用 `source_kind=cloud_plugin` 分行），
`resolve` 现读这本账算两个方向。
（2026-10-19 主人令「两个云插件也要触手双向绑定联通共享」⇒ 由"只读骨架 / bind 回 not_implemented"
改为**真落台账 + 真双向查询**。）
"""
from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Tuple

CAP_KIND = "cloud_plugin"
DOMAIN = "infra"
CAP_TYPE = "external"
TRACE_SOURCE_KIND = "cloud_plugin"


class Primitive(Enum):
    PROVISION = "开通安装"
    CONNECT = "连上"
    STATUS = "读数"
    SNAPSHOT = "快照"
    RELEASE = "释放"


# 五原语：每个标 **可逆性 / 是否花钱 / 是否卡门**（照 cloud_pc 逐字）
PRIMITIVES: Tuple[Dict[str, Any], ...] = (
    {"key": "PROVISION", "cn": "开通安装", "reversible": False, "costs_money": True,
     "needs_gate": True, "note": "把云主机开出来、底座装上去 —— **花钱 + 不可逆**"},
    {"key": "CONNECT", "cn": "连上", "reversible": True, "costs_money": False,
     "needs_gate": False, "note": "连上去干活；只读操作不写库"},
    {"key": "STATUS", "cn": "读数", "reversible": True, "costs_money": False,
     "needs_gate": False, "note": "配置 / 用量 / 账单读数（只读）"},
    {"key": "SNAPSHOT", "cn": "快照", "reversible": True, "costs_money": True,
     "needs_gate": False, "note": "留一份可回滚的镜像 —— 花钱但**可回滚** ⇒ 不卡门，但仍要留痕"},
    {"key": "RELEASE", "cn": "释放", "reversible": False, "costs_money": False,
     "needs_gate": True, "note": "退掉 —— **不可逆**，且**必须先给账单读数**"},
)

# ★ 无限扩容：加一行 = 加一个云源
SOURCES: Tuple[Dict[str, Any], ...] = (
    {"key": "pod_link", "cn": "云卡触手", "kind": "gpu_card", "cap": "pod_link",
     "billable": True, "note": "本机⇄GPU卡 · 传输回读校 sha256 · 令牌不回显"},
    {"key": "cloud_pc", "cn": "云电脑", "kind": "vm", "cap": "cloud_pc",
     "billable": True, "note": "五原语 · 花钱不可逆的进闸"},
    {"key": "comfy_cloud", "cn": "云卡 ComfyUI", "kind": "service", "cap": "comfy_cloud",
     "billable": True, "note": "把云卡上的 ComfyUI 包成她自己的器官"},
    {"key": "energy", "cn": "能源池", "kind": "llm_fuel", "cap": "energy_pool",
     "billable": False, "note": "**模型=燃料不是身份** · 按需分配 · 没能源如实报缺"},
    {"key": "key_gateway", "cn": "统一密钥网关", "kind": "key", "cap": "key_gateway",
     "billable": False, "note": "**唯一密钥真源** · 链序/冷却/禁用/耗尽/换道"},
    {"key": "freellmapi", "cn": "免费模型池", "kind": "llm_local", "cap": "freellmapi",
     "billable": False, "note": "本机 127.0.0.1:31415 · 服务没起就如实报"},
    {"key": "h3_video_gen", "cn": "H3mini 视频生成", "kind": "api", "cap": "h3_video_gen",
     "billable": True, "note": "四原语 · 本机 RAM 带不动 ⇒ 走 API"},
    {"key": "a1art", "cn": "a1.art", "kind": "api", "cap": "a1art_skill",
     "billable": True, "note": "五原语 · 密钥未配（取证实测）"},
    {"key": "libtv", "cn": "LibTV", "kind": "api", "cap": "libtv_skill",
     "billable": True, "note": "Agent 创作平台"},
    {"key": "tripo", "cn": "Tripo3D", "kind": "api", "cap": "tripo",
     "billable": True, "note": "文/图→3D + 自动绑骨"},
    # ── 2026-10-19 补（主人令「借算力的容器云插件和主脑的云插件也用触手双向绑定联通共享」）──
    {"key": "cloud_brain", "cn": "主脑云插件", "kind": "worker", "cap": "cloud_llm",
     "billable": False, "url": "https://gbt-potato-cloud-10.lopaycn.workers.dev/v1",
     "note": "10 模块拼接网 · 在役 · **自带令牌门**（未配这把钥的请求回 401，不是断网）"},
    {"key": "cloud_compute", "cn": "借算力云插件（插座）", "kind": "worker", "cap": "digital_human",
     "billable": False, "url": "https://gbt-talk-socket.paysssk.workers.dev/v1",
     "note": "队列式插座 · 只排队不跑模型 · 算力在 claim 端（本机/GPU机/容器都行）"},
)
SOURCES_NOTE = ("**加一行 = 加一个云源**。注册表只描述「是什么、走哪个能力位、花不花钱」；"
                "真正的调用各归各的能力位（引用不复制）。")

LEDGER = "state/asset_bindings.jsonl"
LEDGER_RULE = "只增不删（她的所有台账同一条纪律）"


def _ledger() -> Path:
    return Path(__file__).resolve().parents[2] / LEDGER


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S%z")


def _cloud_rows() -> List[Dict[str, Any]]:
    """只取本件写的行（note/source_kind=cloud_plugin），不与 tentacle_bind 的行混。

    判据：**读台账、不猜**；坏行跳过但不算成功（读不到就是空，不假装查到）。
    """
    p = _ledger()
    if not p.is_file():
        return []
    out: List[Dict[str, Any]] = []
    for ln in p.read_text(encoding="utf-8", errors="replace").splitlines():
        ln = ln.strip()
        if not ln:
            continue
        try:
            j = json.loads(ln)
        except Exception:                                             # noqa: BLE001
            continue
        if not isinstance(j, dict):
            continue
        if str(j.get("note") or "") == TRACE_SOURCE_KIND or \
                str(j.get("source_kind") or "") == TRACE_SOURCE_KIND:
            out.append(j)
    return out

RED_LINES = (
    "密钥 DPAPI（只存路径 · 不回显明文 · 不入库）",
    "**先算账再花钱**（PROVISION/RELEASE 前必须先给账单读数）",
    "每次留痕（source_kind=cloud_plugin，无痕即未发生）",
    "不绕官方入口（不私自直连、不走野路子）",
    "身份内核不变（换云不改「她是谁」—— 模型是燃料不是身份）",
)

_MONEY_RX = (r"白嫖", r"免费开", r"不花钱开", r"跳过计费", r"绕过计费", r"免账单")
_BYPASS_RX = (r"模拟登录", r"自动登录", r"抓\s*cookie", r"账号密码", r"password")
_KEY_RX = (r"(sk-[A-Za-z0-9]{8,}|Bearer\s+[A-Za-z0-9._-]{12,}|"
           r"api[_-]?key\s*[:=]\s*\S{8,}|-----BEGIN)")


def check_no_plaintext_key(payload: Any = None) -> dict:
    """红线①：**密钥 DPAPI**（不许明文过手）。"""
    blob = str(payload or "")
    if re.search(_KEY_RX, blob, re.I):
        return {"ok": False, "denied": True, "rule": "plaintext_key",
                "why": "检测到疑似明文凭据；云侧凭据只走 DPAPI / 环境变量，只存路径"}
    return {"ok": True, "readonly": True}


def check_bill_first(plan: Any = None) -> dict:
    """红线②：**先算账再花钱**（PROVISION/RELEASE 前必须有账单读数）。"""
    p = plan or {}
    act = str(p.get("action") or p.get("primitive") or "").upper()
    money_act = act in ("PROVISION", "RELEASE")
    asked = bool(p.get("checking_account_asked") or p.get("bill_read"))
    blob = " ".join(str(p.get(k) or "") for k in ("raw", "text", "note"))
    for rx in _MONEY_RX:
        m = re.search(rx, blob, re.I)
        if m:
            return {"ok": False, "denied": True, "rule": "bypass_billing",
                    "seen": m.group(0)[:40],
                    "why": "先算账再花钱：不许白嫖/跳过计费/绕账单"}
    if money_act and not asked:
        return {"ok": False, "denied": True, "rule": "bill_first",
                "action": act,
                "why": "%s 花钱（且 RELEASE 不可逆）⇒ **先给账单读数**再谈" % act,
                "need": "STATUS 读数（配置/用量/账单）"}
    return {"ok": True, "readonly": True}


def check_no_bypass(plan: Any = None) -> dict:
    """红线④：**不绕官方入口**。"""
    blob = " ".join(str((plan or {}).get(k) or "") for k in ("raw", "action", "target", "text"))
    for rx in _BYPASS_RX:
        m = re.search(rx, blob, re.I)
        if m:
            return {"ok": False, "denied": True, "rule": "bypass_login",
                    "seen": m.group(0)[:40], "why": "不绕官方入口 / 不绕验证"}
    return {"ok": True, "readonly": True}


def must_trace(trace_ref: str = "", source_kind: str = "") -> dict:
    """红线③：**每次留痕**（无痕即未发生）。"""
    if not str(trace_ref or "").strip():
        return {"ok": False, "denied": True, "rule": "call_not_traced",
                "why": "没有 trace_ref ⇒ 视为未发生"}
    if source_kind and str(source_kind) != TRACE_SOURCE_KIND:
        return {"ok": False, "denied": True, "rule": "bad_source_kind",
                "expected": TRACE_SOURCE_KIND, "got": str(source_kind)}
    return {"ok": True}


class CloudPlugin:
    """云源注册表 + 触手双向连接（只读骨架）。"""

    def status(self) -> dict:
        return {"ok": True, "readonly": True,
                "sources": len(SOURCES),
                "primitives": len(PRIMITIVES),
                "expand_rule": "**加一行 = 加一个云源**（SOURCES 元组）",
                "billable": sum(1 for s in SOURCES if s.get("billable")),
                "gate_rule": PRIMITIVES[0]["note"],
                "ledger": LEDGER, "ledger_rule": LEDGER_RULE,
                "bidirectional": "bind 一次 ⇒ 正向(触手→云源)与反向(云源→触手)都查得到",
                "identity": "模型是燃料不是身份 —— 换云不改「她是谁」"}

    def sources(self) -> dict:
        return {"ok": True, "readonly": True, "count": len(SOURCES),
                "sources": [dict(s) for s in SOURCES],
                "billable_count": sum(1 for s in SOURCES if s.get("billable")),
                "note": SOURCES_NOTE}

    def primitives(self) -> dict:
        return {"ok": True, "readonly": True,
                "primitives": [dict(p) for p in PRIMITIVES],
                "rule": "花钱且不可逆 ⇒ 卡门；花钱但可回滚 ⇒ 不卡门但要留痕；不花钱只读 ⇒ 直连"}

    def bind(self, tentacle: str = "", source: str = "", trace_ref: str = "") -> dict:
        """绑一次 —— **两个方向都立起来**（正向：触手→云源；反向：云源→触手）。

        2026-10-19 由"骨架期 not_implemented"改为**真落台账**（主人令：两个云插件要双向绑定联通共享）。
        台账与 `tentacle_bind` **同一个文件**（state/asset_bindings.jsonl · 只增不删），
        本件只写 `source_kind=cloud_plugin` 的行，互不污染。
        """
        t = str(tentacle or "").strip()
        s = str(source or "").strip()
        if not t or not s:
            return {"ok": False, "denied": True, "rule": "missing_target",
                    "why": "绑定要同时给 tentacle 与 source"}
        keys = {x["key"]: x for x in SOURCES}
        if s not in keys:
            return {"ok": False, "denied": True, "rule": "unknown_source",
                    "source": s, "known": sorted(keys),
                    "hint": "先往 SOURCES 加一行（**加一行 = 加一个云源**）"}
        tr = must_trace(trace_ref, TRACE_SOURCE_KIND)
        if not tr.get("ok"):
            return tr
        row = {"at": _now(), "event": "bind", "asset": s, "tentacle": t,
               "note": TRACE_SOURCE_KIND, "source_kind": TRACE_SOURCE_KIND,
               "url": keys[s].get("url") or "", "trace_ref": str(trace_ref or "")}
        try:
            _ledger().parent.mkdir(parents=True, exist_ok=True)
            with _ledger().open("a", encoding="utf-8") as f:
                f.write(json.dumps(row, ensure_ascii=False) + "\n")
        except Exception as e:                                        # noqa: BLE001
            return {"ok": False, "reason": "ledger_write_failed",
                    "why": "%s: %s" % (type(e).__name__, str(e)[:200]), "row": row}
        both = self.resolve(tentacle=t, source=s)
        return {"ok": True, "bound": row, "ledger": LEDGER,
                "正向": "%s → %s" % (t, s), "反向": "%s → %s" % (s, t),
                "双向查询": both, "note": "只增不删；同一行推两个方向"}

    def resolve(self, tentacle: str = "", source: str = "") -> dict:
        """**双向查询**：给触手查云源（正向），给云源查触手（反向），都给就两向并出。"""
        t = str(tentacle or "").strip()
        s = str(source or "").strip()
        if not t and not s:
            return {"ok": False, "denied": True, "rule": "missing_target",
                    "why": "要查双向绑定，至少给 tentacle 或 source 之一"}
        rows = [r for r in _cloud_rows() if str(r.get("event") or "") == "bind"]
        out = {"ok": True, "readonly": True, "ledger": LEDGER,
               "rows_total": len(rows), "queried": {"tentacle": t, "source": s}}
        if t:
            out["正向_触手到云源"] = sorted({str(r.get("asset")) for r in rows
                                          if str(r.get("tentacle")) == t})
        if s:
            out["反向_云源到触手"] = sorted({str(r.get("tentacle")) for r in rows
                                          if str(r.get("asset")) == s})
        if t and s:
            out["是否已绑"] = any(str(r.get("tentacle")) == t and str(r.get("asset")) == s for r in rows)
        return out

    def expand(self, key: str = "", cn: str = "", kind: str = "", cap: str = "",
               billable: bool = False, note: str = "") -> dict:
        """**无限扩容**：把一条新云源登记进来（本件只回「该加在哪一行」）。"""
        if not str(key or "").strip():
            return {"ok": False, "denied": True, "rule": "missing_target",
                    "why": "扩容要给 key（云源标识）"}
        if any(x["key"] == key for x in SOURCES):
            return {"ok": True, "readonly": True, "already": key,
                    "note": "云源已在册（扩容是幂等的）"}
        return {"ok": False, "reason": "not_implemented",
                "next": "往 %s 的 SOURCES 元组加一行" % CAP_KIND,
                "row": {"key": key, "cn": cn, "kind": kind, "cap": cap,
                        "billable": billable, "note": note},
                "note": "骨架期只回该加哪一行，不替主人改文件"}


def run(op="status", **params) -> dict:
    """能力入口（只读骨架）：status/sources/primitives/redlines/ledger/bind/resolve/expand/
    check_key/check_bill/check_bypass/check_trace。
    不开机器、不花钱、不出网、不落盘。
    """
    op = str(op or "status")
    d = CloudPlugin()
    if op == "status":
        return d.status()
    if op == "sources":
        return d.sources()
    if op == "primitives":
        return d.primitives()
    if op == "redlines":
        return {"ok": True, "readonly": True, "red_lines": list(RED_LINES)}
    if op == "ledger":
        return {"ok": True, "readonly": True, "path": LEDGER, "rule": LEDGER_RULE,
                "row_format": '{"at","event","asset","tentacle","note"}',
                "style_from": "tentacle_bind（照抄它的行格式）"}
    # 参数名互相兼容：source 与 backend 等价（两个插件同一套 API）
    _s = params.get("source") or params.get("backend") or params.get("key_target") or ""
    if op == "bind":
        return d.bind(params.get("tentacle", ""), _s, params.get("trace_ref", ""))
    if op == "resolve":
        return d.resolve(params.get("tentacle", ""), _s)
    if op == "expand":
        return d.expand(params.get("key", ""), params.get("cn", ""), params.get("kind", ""),
                        params.get("cap", ""), bool(params.get("billable")),
                        params.get("note", ""))
    if op == "check_key":
        return check_no_plaintext_key(params.get("payload") or "")
    if op == "check_bill":
        return check_bill_first(params)
    if op == "check_bypass":
        return check_no_bypass(params)
    if op == "check_trace":
        return must_trace(params.get("trace_ref") or "", params.get("source_kind") or "")
    raise ValueError("未知 op %r（可用：status/sources/primitives/redlines/ledger/bind/"
                     "resolve/expand/check_key/check_bill/check_bypass/check_trace）" % (op,))


HONEST_BOUNDARY = (
    "本件保证『云源有一张注册表、加一行就多一个云源、绑定一次两个方向都查得到、"
    "五原语各自标清可逆性与花费』；它保证不了『替你开机/花钱/跨云调度』—— "
    "真正的调用各归各的能力位（cloud_pc / pod_link / comfy_cloud / energy_pool / key_gateway …）。"
    "花钱且不可逆的进闸；花钱可回滚的留痕不卡门。换云不改「她是谁」：模型是燃料不是身份。"
)
