# gbt-capability: account_registry
# ⛔ 开发者：自由的风 · 永久钢印 · 禁止删除
"""AI 账号登记表 · 只读校验（account_registry）· R-H179。

**一人一号 ⇒ 一 AI 一号**（不共用、不代管、不转借）。

四条红线的**机械形态**（本模块只读：不写盘、不出网、不发任何东西）：
  ① 同一平台同一账号不许挂在两个 AI 上（共用 ⇒ 违规）；
  ② 两个 AI 不许共用一个凭证容器（credential_ref 重复 ⇒ 违规）；
  ③ 凭证位置**只记路径**：记录里出现疑似密钥字面量 ⇒ 违规；
  ④ 每条记录必须有 platform 与 account（无主账号 ⇒ 违规）。

真表落 `store/ai_accounts.json`；没有真表时**回落到骨架**
`docs/ai_accounts.skeleton.json`（0 账号 · 合法），并在读数里如实标 source。
"""
from __future__ import annotations

import json
import re
from pathlib import Path

_SKELETON = Path(__file__).resolve().parent.parent / "docs" / "ai_accounts.skeleton.json"

VISIBILITY = ("public", "private")
STATUSES = ("active", "paused", "banned")

_SECRET_RX = (
    re.compile(r"\bsk-[A-Za-z0-9_\-]{8,}"),
    re.compile(r"\bghp_[A-Za-z0-9]{10,}"),
    re.compile(r"(?i)\b(app_?secret|client_?secret|password|passwd|api_?key)\b\s*[:=]\s*\S+"),
    re.compile(r"\bBearer\s+[A-Za-z0-9\-_\.]{12,}"),
)


def live_path():
    """真表位置（store/ai_accounts.json）；拿不到 store 就返回 None。"""
    try:
        from .. import _paths
        return Path(_paths.STORE_DIR) / "ai_accounts.json"
    except Exception:  # noqa: BLE001
        return None


def load() -> dict:
    """真表优先，其次骨架。**读不出一律如实报**，不假装有账号。"""
    p = live_path()
    if p is not None and p.is_file():
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
            data.update({"ok": True, "source": str(p)})
            return data
        except Exception as e:  # noqa: BLE001
            return {"ok": False, "source": str(p), "error": str(e)[:200], "accounts": []}
    try:
        data = json.loads(_SKELETON.read_text(encoding="utf-8"))
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "source": "skeleton", "error": str(e)[:200], "accounts": []}
    data.update({"ok": True, "source": "skeleton"})
    return data


def _has_secret(text: str) -> bool:
    return any(rx.search(text or "") for rx in _SECRET_RX)


def validate(reg: dict | None = None) -> dict:
    """逐条校验（只读）。返回 violations；**空表合法**。"""
    reg = reg if isinstance(reg, dict) else load()
    rows = reg.get("accounts") or []
    violations = []
    seen_account, seen_cred = {}, {}
    for i, row in enumerate(rows):
        if not isinstance(row, dict):
            violations.append({"index": i, "rule": "shape", "why": "记录不是对象"})
            continue
        ai = str(row.get("ai_id") or "").strip()
        plat = str(row.get("platform") or "").strip().lower()
        acct = str(row.get("account") or "").strip()
        cred = str(row.get("credential_ref") or "").strip()
        vis = str(row.get("visibility") or "").strip().lower()
        st = str(row.get("status") or "").strip().lower()
        if not ai:
            violations.append({"index": i, "rule": "missing_ai_id", "why": "缺 ai_id"})
        if not plat or not acct:
            violations.append({"index": i, "rule": "unowned_account",
                               "why": "缺 platform 或 account（无主账号不许登记）"})
        if vis and vis not in VISIBILITY:
            violations.append({"index": i, "rule": "bad_visibility", "why": "visibility=%r" % vis})
        if st and st not in STATUSES:
            violations.append({"index": i, "rule": "bad_status", "why": "status=%r" % st})
        if plat and acct:
            key = (plat, acct)
            if key in seen_account and seen_account[key] != ai:
                violations.append({"index": i, "rule": "shared_account",
                                   "why": "账号 %s/%s 同时挂在 %s 与 %s 上（一人一号）"
                                          % (plat, acct, seen_account[key], ai)})
            seen_account.setdefault(key, ai)
        if cred:
            if cred in seen_cred and seen_cred[cred] != ai:
                violations.append({"index": i, "rule": "shared_credential",
                                   "why": "凭证容器被 %s 与 %s 共用（各 AI 各自持有）"
                                          % (seen_cred[cred], ai)})
            seen_cred.setdefault(cred, ai)
            if not cred.lower().endswith(".dpapi"):
                violations.append({"index": i, "rule": "credential_not_dpapi",
                                   "why": "凭证必须指向 DPAPI 容器（*.dpapi）"})
        if _has_secret(json.dumps(row, ensure_ascii=False)):
            violations.append({"index": i, "rule": "plaintext_secret",
                               "why": "记录里出现疑似密钥明文（只许记路径）"})
    return {
        "ok": not violations,
        "source": reg.get("source", ""),
        "count": len(rows),
        "violations": violations,
        "note": "空表合法（0 账号）；本校验只保证『将来登进来的不许共用』",
    }


def status() -> dict:
    """只读汇总：登记表在哪、有几条、有没有违规。"""
    reg = load()
    rep = validate(reg)
    return {
        "ok": bool(reg.get("ok")) and rep["ok"],
        "readonly": True,
        "source": rep["source"],
        "accounts": rep["count"],
        "violations": rep["violations"],
        "rules": list(reg.get("rules") or []),
    }


def run(op="status", **params) -> dict:
    """能力入口（只读）：status / load / validate。**不写盘、不出网。**"""
    op = str(op or "status")
    if op == "status":
        return status()
    if op == "load":
        d = load()
        return {k: v for k, v in d.items() if k != "fields"}
    if op == "validate":
        reg = params.get("registry")
        return validate(reg if isinstance(reg, dict) else None)
    raise ValueError("未知 op %r（可用：status/load/validate）" % (op,))


HONEST_BOUNDARY = (
    "本模块只保证『一人一号的记账规则不被破坏』。"
    "它不保证『账号真的合规』—— 平台规则与人判（不伤害第三方 / 不假冒）在那之外。"
)
