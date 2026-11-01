# -*- coding: utf-8 -*-
"""双脑确认（dual_gate）：蒸馏自 v5 `dual_brain_gate.py` 的"两脑都点头才执行"。

v5 的做法：推理脑（意图/风险/必要性）+ 编程脑（技术方案/参数/路径）都确认才算批准，
**任一脑不点头 = 作废**，而且是"宪法级"规则。

我们**不搬它的类体系**（本仓已有 `security/policy.py` 作用域门 + `auth_gate` 票 + 审计），
只取"两道独立确认"这一层，补在**危险动作之前**：

  推理脑（我们的版本）：
    · 决策来自 policy.evaluate 的作用域（G1 黑客 / G2 付款 / G3 生产）——
      **真要票的就必须有票**（由 auth_gate 判，这里只读懂不懂"该不该"）；
    · 金额/数量异常（转账类：amount 超上限、收款人缺失）；
    · 危险动词与作用域不匹配（例如"只读"名义却带写参数）。
  编程脑（我们的版本）：
    · 能力位真的存在（registry）；
    · 必填参数齐（transfer 要 amount+to；deploy 要 target …）；
    · 落点路径存在（有 path 参数时必须真实存在，不猜）；
    · 明显自相矛盾（dry_run=true 却带 force=true）。

op:
    check  {"kind": "...", "payload": {...}}   # 两脑各出一份裁决 + 总结论
    status                                      # 规则清单
"""
from __future__ import annotations

import os
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[2]

# 金额上限（转账类）：超过就要主人亲自点头，双脑不替她兜
AMOUNT_LIMIT = float(os.environ.get("GBT_DUAL_AMOUNT_LIMIT") or 100000.0)
DANGER_KINDS = {"transfer", "wallet", "pay", "payment"}


def _scopes(kind: str, payload: dict) -> list:
    try:
        from ..security import policy as P
        d = P.evaluate(kind, payload)
        return list(d.scopes or [])
    except Exception:  # noqa: BLE001
        return []


def reasoning_check(kind: str, payload: dict) -> dict:
    notes, passed = [], True

    k = str(kind or "").lower()
    p = dict(payload or {})
    scopes = _scopes(k, p)
    if scopes:
        notes.append("需要票的作用域：%s（由 auth_gate 落实，双脑不代替发票）" % ", ".join(scopes))

    # 金额异常（转账类）
    if k in DANGER_KINDS or any(s in scopes for s in ("external_llm", "data_export")):
        amt = p.get("amount") or p.get("value") or 0
        try:
            amt = float(amt)
        except Exception:  # noqa: BLE001
            amt = 0.0
        if amt <= 0:
            passed = False
            notes.append("金额缺失/非法：%r" % (p.get("amount"),))
        elif amt > AMOUNT_LIMIT:
            passed = False
            notes.append("金额 %.2f 超上限 %.2f ⇒ 双脑不替她兜，须主人亲自点头" % (amt, AMOUNT_LIMIT))
        if k in DANGER_KINDS and not (p.get("to") or p.get("recipient") or p.get("account")):
            passed = False
            notes.append("收款人缺失（to/recipient/account 至少一个）")

    # 危险动词与作用域不匹配：要求 dry_run 的却带 force
    if p.get("force") and p.get("dry_run"):
        passed = False
        notes.append("自相矛盾：force=true 且 dry_run=true")

    return {"ok": passed, "brain": "reasoning", "scopes": scopes,
            "notes": notes, "verdict": "approve" if passed else "reject"}


def programming_check(kind: str, payload: dict) -> dict:
    notes, passed = [], True
    k = str(kind or "").strip()
    p = dict(payload or {})

    # ① 能力位存在
    try:
        from ..caps_registry import BENIGN_CAPS
        exists = k in BENIGN_CAPS or k in ("run_task",)
    except Exception:  # noqa: BLE001
        exists = True
    if not exists:
        passed = False
        notes.append("能力位不存在：%s" % k)

    # ② 必填参数
    required = {"transfer": ("amount", "to"), "deploy": ("target",),
                "mcp_call": ("server", "tool"), "cap_pack": ("name",)}
    miss = [f for f in required.get(k, ()) if not p.get(f) and not p.get({"to": "recipient"}.get(f, f))]
    if miss:
        passed = False
        notes.append("缺必填参数：%s" % ", ".join(miss))

    # ③ 落点路径存在（有 path 参数时）
    path = p.get("path") or p.get("file")
    if path:
        try:
            pa = pathlib.Path(str(path))
            if not pa.is_absolute():
                pa = ROOT / pa
            if not pa.exists():
                passed = False
                notes.append("落点不存在：%s" % pa)
        except Exception:  # noqa: BLE001
            passed = False
            notes.append("路径非法：%r" % path)

    return {"ok": passed, "brain": "programming", "notes": notes,
            "verdict": "approve" if passed else "reject"}


def check(kind: str = "", payload=None) -> dict:
    kind = str(kind or "").strip()
    payload = dict(payload or {})
    if not kind:
        return {"ok": False, "error": "user_error: 需要 kind"}
    r = reasoning_check(kind, payload)
    g = programming_check(kind, payload)
    both = bool(r.get("ok") and g.get("ok"))
    out = {"ok": True, "kind": kind, "both_approved": both,
           "verdict": "approved" if both else "rejected",
           "reasoning": r, "programming": g,
           "rule": "两脑都点头才执行；任一否决 = 不执行（v5 宪法级规则的蒸馏）"}
    if both:
        try:
            from .execution_guard import audit as EG_AUDIT  # noqa: F401  (保持同一套账本口径)
        except Exception:  # noqa: BLE001
            pass
        try:
            from .. import orchestration as OB
            OB.record("verify", "dual_gate", detail="双脑确认通过 kind=%s" % kind,
                      evidence="tentacle/dual_gate.py")
        except Exception:  # noqa: BLE001
            pass
    return out


def status() -> dict:
    return {"ok": True, "amount_limit": AMOUNT_LIMIT,
            "danger_kinds": sorted(DANGER_KINDS),
            "rules": {
                "reasoning": ["作用域要票（auth_gate 落实）", "金额上限", "收款人必填",
                              "force 与 dry_run 互斥"],
                "programming": ["能力位必须存在", "必填参数齐", "落点路径必须存在"],
            },
            "note": "双脑只做'该不该/干不干得成'的判断；发票仍然只有主人能发"}


def run(op: str = "status", **kw) -> dict:
    op = (op or "status").lower()
    if op == "check":
        return check(str(kw.get("kind") or ""), kw.get("payload"))
    if op == "status":
        return status()
    return {"ok": False, "error": "dual_gate 不认 op=%s（check/status）" % op}
