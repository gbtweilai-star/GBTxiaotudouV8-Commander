# gbt-capability: shared_resources
# ⛔ 开发者：自由的风 · 永久钢印 · 禁止删除
"""共享资源池 · 虚拟号 + 邮箱（shared_resources）· R-H181 只读骨架。

**虚拟号/邮箱是"资源"，不是"身份"** —— 资源可共享，**账号本身不共享**（合规底座红线）。

机械闸（本模块**内存态、不落盘、不出网**；真值接入是后续独立的刀）：
  ① `lease()` **必须**给 purpose 与 leased_to（每次调用留痕：谁用、何时、为何）；
  ② purpose 出现**批量注册 / 刷号**类字眼 ⇒ 拒绝（不用于恶意注册）；
  ③ purpose 出现**绕过验证**类字眼 ⇒ 拒绝（不绕人机验证）；
  ④ 同一个资源不许同时租给两个 AI；`release()` 后**租约记录保留**（留痕不删）。
"""
from __future__ import annotations

import time

TYPES = ("phone", "email")
STATUSES = ("idle", "leased")

_ABUSE_HINTS = ("批量注册", "刷号", "养号", "小号矩阵", "mass register", "bulk signup", "bot farm")
_BYPASS_HINTS = ("绕过", "破解验证", "bypass", "solve_captcha", "stealth", "伪装成真实用户")

POOL = {"phone": [], "email": []}
LEASES = []
_SEQ = {"n": 0}
MAX_LEASE_S = 1800.0


def _now(now=None) -> float:
    return float(time.time() if now is None else now)


def mask(value: str) -> str:
    """掩码显示：资源值**不许明文外露**（前 3 后 2，其余打码）。"""
    s = str(value or "")
    if len(s) <= 5:
        return "*" * len(s)
    return s[:3] + "*" * max(1, len(s) - 5) + s[-2:]


def add_resource(resource_type: str, value: str, resource_id: str = "") -> dict:
    """往池里加一个资源（内存态）。返回值里只给掩码。"""
    rt = str(resource_type or "").strip().lower()
    if rt not in TYPES:
        raise ValueError("未知资源类型 %r（可用：%s）" % (rt, "/".join(TYPES)))
    val = str(value or "").strip()
    if not val:
        raise ValueError("value 不能为空")
    _SEQ["n"] += 1
    rid = resource_id or ("%s-%02d" % (rt, _SEQ["n"]))
    POOL[rt].append({"resource_id": rid, "type": rt, "value": val, "status": "idle"})
    return {"ok": True, "resource_id": rid, "type": rt, "value": mask(val)}


def _check_purpose(purpose: str) -> list:
    p = str(purpose or "").strip()
    problems = []
    if not p:
        problems.append({"rule": "purpose_required",
                         "why": "每次调用必须留痕：谁用、何时、为何 —— purpose 不许空"})
    low = p.lower()
    if any(h in low for h in _ABUSE_HINTS):
        problems.append({"rule": "abuse_forbidden", "why": "不用于恶意注册（批量/刷号类用途被拒）"})
    if any(h in low for h in _BYPASS_HINTS):
        problems.append({"rule": "bypass_forbidden", "why": "不绕人机验证（走官方 API / 官方 AI / 人机协作）"})
    return problems


def lease(resource_type: str, purpose: str, leased_to: str = "", now=None) -> dict:
    """借一个资源：**必须带 purpose 与 leased_to**（留痕）。池空 / 用途违规 ⇒ 拒绝。"""
    problems = _check_purpose(purpose)
    if not str(leased_to or "").strip():
        problems.append({"rule": "leased_to_required",
                         "why": "必须写明哪个 AI 在用（资源可共享，身份不可混）"})
    if problems:
        return {"ok": False, "denied": True, "problems": problems}
    rt = str(resource_type or "").strip().lower()
    if rt not in TYPES:
        raise ValueError("未知资源类型 %r（可用：%s）" % (rt, "/".join(TYPES)))
    for item in POOL[rt]:
        if item["status"] == "idle":
            at = _now(now)
            _SEQ["n"] += 1
            lid = "lease-%04d" % _SEQ["n"]
            item["status"] = "leased"
            LEASES.append({"lease_id": lid, "resource_id": item["resource_id"], "type": rt,
                           "leased_to": str(leased_to).strip(), "leased_at": at,
                           "purpose": str(purpose).strip(), "released_at": None})
            return {"ok": True, "lease_id": lid, "resource_id": item["resource_id"],
                    "type": rt, "value": mask(item["value"]),
                    "leased_to": str(leased_to).strip(), "purpose": str(purpose).strip(),
                    "max_lease_s": MAX_LEASE_S, "readonly": True}
    return {"ok": False, "denied": True, "reason": "pool_empty",
            "why": "%s 池里没有空闲资源（骨架期池子为空）" % rt}


def release(lease_id: str, now=None) -> dict:
    """归还：资源回池，**租约记录保留**（留痕不删）。"""
    for row in LEASES:
        if row["lease_id"] == lease_id and row["released_at"] is None:
            row["released_at"] = _now(now)
            for item in POOL[row["type"]]:
                if item["resource_id"] == row["resource_id"]:
                    item["status"] = "idle"
            return {"ok": True, "lease_id": lease_id, "resource_id": row["resource_id"],
                    "released_at": row["released_at"], "trail_kept": True}
    return {"ok": False, "reason": "lease_not_found"}


def status() -> dict:
    """只读汇总：池子有几件、几件在租、租给谁（**留痕**）。"""
    pools = {}
    for rt in TYPES:
        items = POOL[rt]
        pools[rt] = {"total": len(items),
                     "idle": sum(1 for i in items if i["status"] == "idle"),
                     "leased": sum(1 for i in items if i["status"] == "leased")}
    active = [dict(r) for r in LEASES if r["released_at"] is None]
    return {
        "ok": True,
        "readonly": True,
        "pools": pools,
        "leases_total": len(LEASES),
        "leases_active": len(active),
        "active_leases": active,
        "max_lease_s": MAX_LEASE_S,
        "note": "资源可共享，身份不共享（一 AI 一号）；骨架期池子为空 —— 空就是空",
    }


def run(op="status", **params) -> dict:
    """能力入口（只读骨架）：status / leases / lease / release / add。

    内存态：**不落盘、不出网**；真值接入是后续独立的刀。
    """
    op = str(op or "status")
    if op == "status":
        return status()
    if op == "leases":
        return {"ok": True, "readonly": True, "leases": [dict(r) for r in LEASES]}
    if op == "lease":
        return lease(params.get("resource_type", ""), params.get("purpose", ""),
                     params.get("leased_to", ""), now=params.get("now"))
    if op == "release":
        return release(params.get("lease_id", ""), now=params.get("now"))
    if op == "add":
        return add_resource(params.get("resource_type", ""), params.get("value", ""),
                            params.get("resource_id", ""))
    raise ValueError("未知 op %r（可用：status/leases/lease/release/add）" % (op,))


HONEST_BOUNDARY = (
    "本骨架只保证『资源怎么借、怎么还、怎么留痕』以及『违规用途进不来』。"
    "它不保证『资源真的可用』—— 真值接入与平台验证在那之外。"
)
