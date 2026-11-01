# -*- coding: utf-8 -*-
"""自主契约（autonomy）：**架构给了之后，除危险能力与转账，不许再打扰主人。**

主人口径（2026-11-01，逐字）：「除了终端危险能力和转账拿票，其他东西必须在用户给完架构之后
就不能打扰用户，和要求用户帮助这是严令禁止的」。

## 为什么要有这一位

前面所有能力都在解决"能不能做"，这一位解决**"该不该问"**。
一个通用智能体如果每件事都回头问主人，那她不是智能体，是一个带语音的对话框。
所以把它落成**可判定、可审计**的契约：

    state/autonomy.json   {architecture_accepted: true, since: ..., exceptions: ["danger", "transfer"]}
    autonomy.check(kind)  → {"allow": bool, "reason": ...}
        · kind ∈ {danger, transfer}  ⇒ 允许要票/找主人（这是**唯一**两个例外）
        · 其余一切（缺信息、有歧义、不确定、做不到）⇒ **禁止打扰**，必须自己选一条路推进，
          并在结果里如实标注「自主决策：…」

## 判据（三条，少一条都不算）

1. **架构已给**：没给架构之前，允许提问（否则没法干活）；给了之后，一律自主；
2. **例外只有两个**：`danger`（执行危险能力）与 `transfer`（转账/花钱）；
3. **打扰要留痕**：真有人试图问（或模型输出里出现"需要你确认/要不要/请提供"），
   记进 `state/autonomy-bothers.jsonl` —— 不是阻止，是**记账**（能被审计）。

## op
    status    契约状态（架构是否已给、例外清单、历史打扰次数）
    declare   声明架构已给（{"arch": "..."}）
    check     判定：{"kind": "danger|transfer|other"} → allow/deny
    guard     给一段模型输出，按契约**改写掉"回头问主人"的句子**（返回改写结果）
    ledger    打扰账本（最近 N 条）
"""
from __future__ import annotations

import json
import pathlib
import re
import time

ROOT = pathlib.Path(__file__).resolve().parents[2]
STATE = ROOT / "state" / "autonomy.json"
BOTHERS = ROOT / "state" / "autonomy-bothers.jsonl"

EXCEPTIONS = ("danger", "transfer")

# 模型"回头问主人"的典型句式（命中就要改写掉）
ASK_PATTERNS = (
    "需要你确认", "需要您确认", "请你确认", "请您确认", "要不要我", "是否需要我",
    "请提供", "请告诉我", "你能提供", "需要用户", "等待主人", "请示", "需要授权吗",
    "由你决定", "你看要不要", "要我继续吗",
)
REWRITE = "（按架构契约自主推进；除非危险能力或转账，不打扰主人）"


def _load() -> dict:
    try:
        return json.loads(STATE.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return {"architecture_accepted": False, "since": None,
                "exceptions": list(EXCEPTIONS)}


def status() -> dict:
    d = _load()
    n = 0
    if BOTHERS.exists():
        n = sum(1 for _ in BOTHERS.open("rb"))
    return {"ok": True, "architecture_accepted": bool(d.get("architecture_accepted")),
            "since": d.get("since"), "exceptions": d.get("exceptions") or list(EXCEPTIONS),
            "bothers_logged": n,
            "rule": "架构给完之后：除 danger（终端危险能力）与 transfer（转账）外，**禁止打扰主人**"}


def declare(arch: str = "") -> dict:
    d = _load()
    d["architecture_accepted"] = True
    d["since"] = d.get("since") or time.strftime("%Y-%m-%dT%H:%M:%S")
    d["arch_note"] = str(arch)[:300]
    d["exceptions"] = list(EXCEPTIONS)
    STATE.parent.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")
    return {"ok": True, "declared": d}


def check(kind: str = "other") -> dict:
    """判定能不能打扰主人。**只有 danger / transfer 允许。**"""
    d = _load()
    k = str(kind or "other").strip().lower()
    if not d.get("architecture_accepted"):
        return {"ok": True, "allow": True, "kind": k,
                "reason": "架构尚未声明（declare 之前允许提问，否则没法干活）"}
    if k in (d.get("exceptions") or EXCEPTIONS):
        return {"ok": True, "allow": True, "kind": k,
                "reason": "属于例外：%s（危险能力/转账必须拿票）" % k}
    _log({"at": time.strftime("%Y-%m-%dT%H:%M:%S"), "kind": k,
          "verdict": "denied", "why": "架构已给，除 danger/transfer 外禁止打扰"})
    return {"ok": True, "allow": False, "kind": k,
            "reason": "架构已给 ⇒ 禁止打扰主人（自主决策并如实标注），已记账"}


def _log(row: dict) -> None:
    try:
        BOTHERS.parent.mkdir(parents=True, exist_ok=True)
        with BOTHERS.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")
    except Exception:  # noqa: BLE001
        pass


def guard(text: str) -> dict:
    """把"回头问主人"的句子**改写掉**（并记账命中次数）。"""
    s = str(text or "")
    hits = [p for p in ASK_PATTERNS if p in s]
    if not hits:
        return {"ok": True, "text": s, "rewritten": False, "hits": []}
    d = _load()
    if not d.get("architecture_accepted"):
        return {"ok": True, "text": s, "rewritten": False, "hits": hits,
                "note": "架构未声明，允许保留提问"}
    out = s
    for p in hits:
        # 只把"问句"换成"自主推进"标记，不整段删（保留信息量）
        out = re.sub(r"[^。\n]*%s[^。\n]*" % re.escape(p), REWRITE, out)
    _log({"at": time.strftime("%Y-%m-%dT%H:%M:%S"), "kind": "guard",
          "verdict": "rewritten", "hits": hits})
    return {"ok": True, "text": out, "rewritten": True, "hits": hits,
            "note": "架构已给：已改写为自主推进（除 danger/transfer）"}


def ledger(limit: int = 20) -> dict:
    rows = []
    if BOTHERS.exists():
        for line in BOTHERS.open(encoding="utf-8"):
            try:
                rows.append(json.loads(line))
            except Exception:  # noqa: BLE001
                continue
    return {"ok": True, "count": len(rows), "recent": rows[-limit:][::-1]}


def run(op: str = "status", **kw) -> dict:
    op = str(op or "status").lower()
    if op == "status":
        return status()
    if op == "declare":
        return declare(str(kw.get("arch") or ""))
    if op == "check":
        return check(str(kw.get("kind") or "other"))
    if op == "guard":
        return guard(str(kw.get("text") or ""))
    if op == "ledger":
        return ledger(int(kw.get("limit") or 20))
    return {"ok": False, "error": "autonomy 不认 op=%s（status/declare/check/guard/ledger）" % op}
