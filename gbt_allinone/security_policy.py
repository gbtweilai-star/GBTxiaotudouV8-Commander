"""GBT小土豆V8 · 安全策略引擎（AI 使用黑客全能力的放行规则）

主人 2026-11-02 定死的三条规则：
  1. **AI 要使用黑客全能力（渗透/扫描/反击类批量动作）→ 必须主人终端确认才放行**；
  2. **例外：遭受攻击时 → 进入"极限并发"攻击模式（边防御边找反击机会），
     此时最高决策 = GBT小土豆V8 自我判断，不需要主人确认**；
  3. **转账 → 任何模式、任何时候必须主人确认**，攻击模式也不能绕过。

落地：
  · 终端确认 = 主人运行 CLI 批准一次（一次性 token、短 TTL、按能力位绑定）；
  · AI 只能"申请确认"（request），不能自己批准（approve 在 CLI/终端侧执行）；
  · 攻击模式有 TTL（默认 10 分钟），进入/退出都写审计；
  · 每次判定写 state/security-policy-audit.jsonl。

开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属
"""
from __future__ import annotations

import json
import os
import secrets
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STATE = ROOT / "state" / "security-policy.json"
AUDIT = ROOT / "state" / "security-policy-audit.jsonl"

# 黑客类能力位（批量/渗透/扫描/反击用途；守卫类不算）
HACKER_DOMAINS = {"security"}
HACKER_PATTERNS = ("pentest", "redteam", "exploit", "payload", "attack", "cross_scan",
                   "sec_scan", "sec_chain", "osint", "bypass", "inject", "exfil", "c2")
# 守卫/自检类不放行闸（它们本来就要常跑）
GUARD_CAPS = {"selfscan", "inventory", "signature_guard", "legacy_guard", "cap_self",
              "execution_guard", "proc_guard", "review_gate", "ghost_guard",
              "truth_scan", "doc_counts", "file_hygiene", "code_audit"}
# 转账类（任何模式都必须主人确认）
TRANSFER_CAPS = {"transfer", "wallet", "pay", "withdraw", "recharge", "refund",
                 "bank_transfer", "settle"}
TRANSFER_PATTERNS = ("transfer", "withdraw", "recharge", "refund", "bank_transfer")

CONFIRM_TTL = 300          # 确认 token 5 分钟
ATTACK_TTL = 600           # 攻击模式默认 10 分钟


def _now() -> float:
    return time.time()


def _iso(t: float | None = None) -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(t or _now()))


def _load() -> dict:
    try:
        return json.loads(STATE.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return {"attack": None, "pending": {}, "confirmations": {}}


def _save(d: dict) -> None:
    STATE.parent.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")


def _audit(event: str, **kw) -> None:
    STATE.parent.mkdir(parents=True, exist_ok=True)
    row = {"at": _iso(), "event": event, **kw}
    with AUDIT.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(row, ensure_ascii=False) + "\n")


def classify(cap: str) -> str:
    """normal / hacker / transfer。"""
    c = str(cap or "").lower()
    if c in TRANSFER_CAPS or any(p in c for p in TRANSFER_PATTERNS):
        return "transfer"
    if c in GUARD_CAPS:
        return "normal"
    if any(p in c for p in HACKER_PATTERNS):
        return "hacker"
    try:
        sys.path.insert(0, str(ROOT))
        from gbt_allinone.caps_registry import BENIGN_CAPS
        dom = (BENIGN_CAPS.get(cap) or {}).get("domain")
        if dom in HACKER_DOMAINS:
            return "hacker"
    except Exception:  # noqa: BLE001
        pass
    return "normal"


def attack_state() -> dict:
    d = _load()
    atk = d.get("attack") or {}
    if atk.get("until") and atk["until"] > _now():
        return {"active": True, **atk}
    return {"active": False, "last": atk or None}


def enter_attack_mode(reason: str, evidence: str = "", ttl: int = ATTACK_TTL,
                      user_report: bool = False) -> dict:
    """受攻击时进入极限并发模式：**必须先举证**（没证据不许说被攻击）。"""
    d = _load()
    # —— 举证门槛 ——
    try:
        from gbt_allinone import attack_evidence as AE
        if evidence:
            AE.add_evidence("user_report" if user_report else "intrusion_alert",
                            "master/terminal", evidence, strong=not user_report)
        for x in AE.detect_signals():
            AE.add_evidence(x["kind"], x.get("source", "detect"), x.get("detail", ""),
                            strong=(x["kind"] in AE.STRONG_KINDS))
        adm = AE.admission()
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "reason": "举证组件不可用：%s" % str(e)[:120]}
    if not adm.get("admitted"):
        _audit("attack_refused", reason="no evidence", reason_text=reason[:200])
        return {"ok": False, "not_admitted": True,
                "reason": adm.get("reason"),
                "explain": adm.get("explain"),
                "hint": adm.get("hint"),
                "rule": "没证据不许说被攻击；攻击模式必须有证据门槛"}
    until = _now() + int(ttl)
    d["attack"] = {"active": True, "reason": reason or "detected attack",
                   "evidence": str(evidence)[:500], "since": _iso(), "until": until,
                   "ttl": int(ttl), "decider": "GBT小土豆V8",
                   "evidence_level": adm.get("level"),
                   "evidence_count": adm.get("count", 0),
                   "evidence_ids": [x.get("sha256") for x in (adm.get("evidence") or [])]}
    _save(d)
    _audit("attack_on", reason=d["attack"]["reason"], ttl=int(ttl),
           evidence=str(evidence)[:300], decider="GBT小土豆V8")
    return {"ok": True, "attack": d["attack"]}


def exit_attack_mode(note: str = "") -> dict:
    d = _load()
    d["attack"] = None
    _save(d)
    _audit("attack_off", note=note)
    return {"ok": True, "attack": None}


def request_confirm(cap: str, reason: str = "") -> dict:
    """AI 侧只能申请确认（生成一次性 token），批准必须在终端。"""
    d = _load()
    tok = secrets.token_urlsafe(12)
    d.setdefault("pending", {})[tok] = {"cap": str(cap), "reason": str(reason)[:300],
                                        "requested_at": _iso(), "expires": _now() + CONFIRM_TTL}
    _save(d)
    _audit("request", cap=cap, reason=str(reason)[:200], token=tok)
    return {"ok": True, "token": tok, "cap": cap,
            "terminal_command": "python tools/confirm-security.py approve %s" % tok,
            "expires_in": CONFIRM_TTL,
            "note": "把上面命令交给主人，在终端执行后才放行"}


def approve(token: str, note: str = "") -> dict:
    """终端侧批准（主人执行）。"""
    d = _load()
    pend = (d.get("pending") or {}).get(token)
    if not pend:
        return {"ok": False, "reason": "没有这个待确认 token"}
    if pend.get("expires", 0) < _now():
        return {"ok": False, "reason": "token 已过期"}
    d["pending"].pop(token, None)
    d.setdefault("confirmations", {})[token] = {
        "cap": pend["cap"], "approved_at": _iso(),
        "expires": _now() + CONFIRM_TTL, "used": False, "note": note}
    _save(d)
    _audit("approve", cap=pend["cap"], token=token)
    return {"ok": True, "cap": pend["cap"], "token": token,
            "note": "已批准（一次性，绑定该能力位，5 分钟内有效）"}


def deny(token: str, note: str = "") -> dict:
    d = _load()
    pend = (d.get("pending") or {}).pop(token, None)
    _save(d)
    _audit("deny", token=token, cap=(pend or {}).get("cap"), note=note)
    return {"ok": bool(pend), "denied": (pend or {}).get("cap")}


def _consume(cap: str) -> str | None:
    d = _load()
    for tok, rec in list((d.get("confirmations") or {}).items()):
        if rec.get("used"):
            continue
        if rec.get("cap") != cap:
            continue
        if rec.get("expires", 0) < _now():
            continue
        rec["used"] = True
        rec["used_at"] = _iso()
        _save(d)
        _audit("consume", cap=cap, token=tok)
        return tok
    return None


def check(cap: str) -> dict:
    """放行判定。返回 decision: allow / need_terminal_confirm / blocked_transfer / attack_self_decision。"""
    kind = classify(cap)
    atk = attack_state()
    if kind == "transfer":
        return {"cap": cap, "kind": "transfer", "decision": "blocked_transfer",
                "reason": "转账必须主人终端确认——任何模式（含受攻击）都不例外"}
    if kind == "hacker":
        if atk.get("active"):
            _audit("allow_attack", cap=cap, reason=atk.get("reason"),
                   decider="GBT小土豆V8")
            return {"cap": cap, "kind": "hacker", "decision": "attack_self_decision",
                    "reason": "受攻击中：极限并发模式，由 GBT小土豆V8 自我决策"}
        tok = _consume(cap)
        if tok:
            return {"cap": cap, "kind": "hacker", "decision": "allow",
                    "reason": "主人已终端确认", "token": tok}
        return {"cap": cap, "kind": "hacker", "decision": "need_terminal_confirm",
                "reason": "黑客全能力必须主人终端确认才放行"}
    return {"cap": cap, "kind": "normal", "decision": "allow", "reason": "普通能力位"}


def status() -> dict:
    d = _load()
    atk = attack_state()
    pend = d.get("pending") or {}
    confs = {k: v for k, v in (d.get("confirmations") or {}).items()
             if not v.get("used") and v.get("expires", 0) > _now()}
    return {"ok": True,
            "attack_mode": atk,
            "pending_confirmations": [{"token": k, "cap": v.get("cap"),
                                       "expires_in": int(v.get("expires", 0) - _now())}
                                      for k, v in pend.items()],
            "active_confirmations": [{"token": k, "cap": v.get("cap"),
                                      "expires_in": int(v.get("expires", 0) - _now())}
                                     for k, v in confs.items()],
            "rules": ["黑客全能力：主人终端确认才放行",
                      "受攻击时：极限并发，GBT小土豆V8 自我决策",
                      "转账：任何模式都必须主人确认"],
            "audit": str(AUDIT)}


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["status", "check", "request", "approve", "deny",
                                    "attack-on", "attack-off"])
    ap.add_argument("arg", nargs="?")
    ap.add_argument("--reason", default="")
    ap.add_argument("--evidence", default="")
    ap.add_argument("--ttl", type=int, default=ATTACK_TTL)
    a = ap.parse_args()
    if a.cmd == "status":
        out = status()
    elif a.cmd == "check":
        out = check(a.arg or "")
    elif a.cmd == "request":
        out = request_confirm(a.arg or "", a.reason)
    elif a.cmd == "approve":
        out = approve(a.arg or "")
    elif a.cmd == "deny":
        out = deny(a.arg or "")
    elif a.cmd == "attack-on":
        out = enter_attack_mode(a.reason or "detected attack", a.evidence, a.ttl)
    else:
        out = exit_attack_mode(a.reason)
    print(json.dumps(out, ensure_ascii=False, indent=2))
