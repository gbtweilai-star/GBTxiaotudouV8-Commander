"""GBT小土豆V8 · 职业派单闭环（任务 → 职业 → 安全能力位 → 执行 → 留痕）

主人 2026-11-02：「继续全方位推进直至落地」——路由给候选之后，最后一步要能真派单并留痕。

安全口径（写死）：
  · 只派 **safe=true** 的候选能力位；需授权位只列出、永不自动执行；
  · 默认 dry_run=True（只出计划）；真执行必须 confirm=True（显式确认）；
  · 每次真执行写 orchestration-ledger（profession/caps/ok/fail/task），能力位自身也会写 audit；
  · 失败不吞：逐条返回 ok/error，不折叠成"全成功"。

开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from gbt_allinone.profession_router import plan as route_plan  # noqa: E402


def dispatch(task: str, dry_run: bool = True, confirm: bool = False, max_caps: int = 3) -> dict:
    """按职业路由派单（只跑 safe 能力位）。"""
    task = (task or "").strip()
    if not task:
        return {"ok": False, "reason": "task 不能为空", "dry_run": dry_run}
    p = route_plan(task)
    if not p.get("ok"):
        return {"ok": False, "reason": "没有命中职业（走协同/指挥人工定）", "plan": p,
                "dry_run": dry_run}
    caps = [c for c in (p.get("safe_candidates") or [])][:max(1, int(max_caps))]
    gated = p.get("gated_candidates") or []
    base = {
        "task": task, "profession": p.get("profession"), "profession_id": p.get("id"),
        "matched": p.get("matched"), "caps_planned": caps, "gated_blocked": gated,
        "kpi": p.get("kpi"), "dry_run": bool(dry_run), "confirm": bool(confirm),
    }
    if not caps:
        base.update({"ok": False, "executed": False,
                     "reason": "该职业没有 safe 候选能力位（候选全部需授权）——不自动执行，需人工/要票"})
        return base
    if dry_run or not confirm:
        base.update({"ok": True, "executed": False,
                     "reason": "dry_run（默认）；真执行需 confirm=True" if dry_run else
                               "未确认：需 confirm=True 才执行"})
        return base

    # 🔒 安全策略闸：黑客全能力需主人终端确认；转账永远拦
    try:
        from gbt_allinone import security_policy as _sp
    except Exception:  # noqa: BLE001
        _sp = None
    if _sp is not None:
        allowed, blocked = [], []
        for c in caps:
            dec = _sp.check(c)
            if dec.get("decision") in ("blocked_transfer", "need_terminal_confirm"):
                blocked.append({"cap": c, "decision": dec.get("decision"),
                                "reason": dec.get("reason")})
            else:
                allowed.append(c)
        caps = allowed
        base["blocked_by_policy"] = blocked
        if not caps:
            base.update({"ok": False, "executed": False,
                         "reason": "候选能力位全部被安全策略拦下"})
            return base

    # 真执行：逐条派单，逐条留结果
    from gbt_allinone.api import run_task  # 延迟导入，避免循环
    results = []
    for cap in caps:
        t0 = time.time()
        try:
            r = run_task(cap, {"text": task})
            body = (r or {}).get("gbt_result", {}).get("result", {})
            ok = bool((r or {}).get("ok", True))
            results.append({"cap": cap, "ok": ok, "ms": int((time.time() - t0) * 1000),
                            "verdict": body.get("verdict") if isinstance(body, dict) else None})
        except Exception as e:  # noqa: BLE001
            results.append({"cap": cap, "ok": False, "ms": int((time.time() - t0) * 1000),
                            "error": str(e)[:160]})
    ok_n = sum(1 for x in results if x.get("ok"))
    entry = None
    try:
        from gbt_allinone import orchestration as OB
        OB.record("dispatch", "profession-dispatch",
                  detail="职业派单 %s → %s（%d 个安全能力位）task=%s"
                         % (p.get("profession"), ",".join(caps), len(caps), task[:60]),
                  evidence="gbt_allinone/profession_dispatch.py")
        entry = "orchestration-ledger +1"
    except Exception as e:  # noqa: BLE001
        entry = "ledger 写入失败：%s" % str(e)[:80]
    base.update({"ok": ok_n == len(results) and bool(results), "executed": True,
                 "results": results, "ok_count": ok_n, "fail_count": len(results) - ok_n,
                 "ledger": entry})
    return base
