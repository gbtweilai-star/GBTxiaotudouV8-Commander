# -*- coding: utf-8 -*-
"""唯一执行路径（chain_kernel）：**不可跳步**的七步链 + 每步证据 + 准入准出。

主人 2026-11-01：「看看我另外一个开源仓库里面有没有好东西，必须挨个仔细查看不能有遗漏」
—— V5（GBT-Framework）最值钱的东西不是 192 个 cap，而是它的**执行纪律**：
`UNIFIED_PATH.md` + `pipeline.md` + `gates.md`：Step -1→6 唯一通道，每步有准入/准出，
每步必须产出证据才能进下一步；架构里缺这一步，能力再多也会乱跑。

本件把它落成能力位（第 377 位）：

    op=run     {"goal": "...", "approve": false}   # 跑七步链；approve=true 才真派工
    op=status                                      # 七步与门禁条件
    op=gate    {"step": "1"}                       # 单步准入/准出条件

纪律：
  · **不可跳步**：某步没有证据 ⇒ 整链 fail-closed，`stopped_at` 告诉你停在哪；
  · **不伪造证据**：证据全是真调用返回的读数（读不到就如实失败）；
  · **默认不派工**：`approve=false` 时第 2 步只做只读面扫描，不执行蓝图任务。
"""
from __future__ import annotations

import json
import time

ROOT_STEP = [
    {"step": -1, "name": "邻域感知", "admission": "任务启动信号",
     "exit": "selfscan/body_sense/pulse_core 三项都拿到读数"},
    {"step": 0, "name": "理解", "admission": "邻域读数齐",
     "exit": "目标非空且已记录原文"},
    {"step": 1, "name": "计划", "admission": "目标已记录",
     "exit": "蓝图生成成功且任务数 > 0（不自动过目）"},
    {"step": 2, "name": "执行", "admission": "计划已生成",
     "exit": "approve=true 时蓝图全部通过；否则只读面扫描有读数"},
    {"step": 3, "name": "验证", "admission": "执行面有证据",
     "exit": "signature_guard / truth_scan / inventory 三项都不报错"},
    {"step": 4, "name": "固化", "admission": "验证通过",
     "exit": "编排账本已记账 且 cap_self 三数一致"},
    {"step": 5, "name": "报告", "admission": "固化完成",
     "exit": "七步证据齐全，结论写回"},
]


def _cap(kind, payload=None):
    from .. import api as _api
    try:
        env = _api.run_task(kind, payload or {}, probe=True)
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "error": "%s: %s" % (type(e).__name__, str(e)[:120])}
    gr = env.get("gbt_result") or {}
    res = gr.get("result") if isinstance(gr.get("result"), dict) else {}
    verdict = str(res.get("verdict") or "").lower()
    ok = bool(env.get("ok")) and res.get("ok") is not False and verdict not in (
        "bad", "fail", "failed", "error", "foreign_found", "drift", "missing")
    return {"ok": ok, "result": res, "verdict": verdict or res.get("verdict")}


def _step_record(step, name, evidence, passed, detail=""):
    return {"step": step, "name": name, "passed": bool(passed),
            "evidence": evidence, "detail": str(detail)[:300],
            "at": time.strftime("%Y-%m-%dT%H:%M:%S")}


def run(goal: str = "", approve: bool = False, blueprint_id: str = "") -> dict:
    goal = str(goal or "").strip()
    steps = []

    # Step -1 邻域感知
    selfscan = _cap("selfscan")
    body = _cap("body_sense", {"op": "status"})
    pulse = _cap("pulse_core", {"op": "status"})
    ev = {"selfscan": selfscan.get("verdict") or ("ok" if selfscan["ok"] else "fail"),
          "body_sense": "ok" if body["ok"] else "fail",
          "pulse_core": "ok" if pulse["ok"] else "fail"}
    ok = selfscan["ok"] and body["ok"] and pulse["ok"]
    steps.append(_step_record(-1, "邻域感知", ev, ok))
    if not ok:
        return _fail(steps, -1, "邻域读数缺失")

    # Step 0 理解
    ok = len(goal) >= 2
    steps.append(_step_record(0, "理解", {"goal": goal[:200], "chars": len(goal)}, ok))
    if not ok:
        return _fail(steps, 0, "目标为空或过短")

    # Step 1 计划
    m = _cap("blueprint", {"op": "make", "arch": goal})
    bid = (m.get("result") or {}).get("id") or blueprint_id
    tasks = (m.get("result") or {}).get("tasks") or 0
    ok = bool(m["ok"] and bid and tasks > 0)
    steps.append(_step_record(1, "计划", {"blueprint": bid, "tasks": tasks}, ok))
    if not ok:
        return _fail(steps, 1, "蓝图没生成出任务")

    # Step 2 执行
    if approve and bid:
        # 真派工前先过双脑：任否决不派工（fail-closed）
        dg = _cap("dual_gate", {"op": "check", "kind": "blueprint",
                                "payload": {"op": "dispatch", "id": bid}})
        dg_res = dg.get("result") or {}
        if not dg_res.get("both_approved"):
            steps.append(_step_record(2, "执行", {"mode": "dispatch_refused",
                                                  "dual_gate": dg_res.get("verdict"),
                                                  "reasoning": (dg_res.get("reasoning") or {}).get("notes"),
                                                  "programming": (dg_res.get("programming") or {}).get("notes")},
                                      False, "双脑未都点头，拒绝派工"))
            return _fail(steps, 2, "双脑确认未通过")
        _cap("blueprint", {"op": "approve", "id": bid})
        d = _cap("blueprint", {"op": "dispatch", "id": bid})
        res = d.get("result") or {}
        ev2 = {"mode": "dispatch", "blueprint": bid, "done": res.get("done"),
               "failed": res.get("failed"), "landed": res.get("landed")}
        ok = bool(d["ok"] and res.get("landed"))
    else:
        ro = []
        for kind, payload in (("inventory", {}), ("legacy_guard", {"op": "status"}),
                              ("trunk_cover", {"op": "status"})):
            r = _cap(kind, payload)
            ro.append({"cap": kind, "verdict": r.get("verdict") or ("ok" if r["ok"] else "fail")})
        ev2 = {"mode": "read_only", "checks": ro,
               "note": "approve=false：只做只读面扫描，不执行蓝图任务"}
        # 旧物(legacy_found)是"该清"的提醒，不阻断执行；异物(foreign_found)/失败才阻断
        ok = all(c["verdict"] not in ("fail", "foreign_found") for c in ro)
    steps.append(_step_record(2, "执行", ev2, ok))
    if not ok:
        return _fail(steps, 2, "执行面没通过")

    # Step 3 验证
    sig = _cap("signature_guard", {"scope": "all"})
    truth = _cap("truth_scan")
    inv = _cap("inventory")
    guard = _cap("execution_guard", {"op": "status"})
    ev3 = {"signature": sig.get("verdict") or ("ok" if sig["ok"] else "fail"),
           "truth_scan": truth.get("verdict") or ("ok" if truth["ok"] else "fail"),
           "inventory": inv.get("verdict") or ("ok" if inv["ok"] else "fail"),
           "execution_guard": {"verdict": (guard.get("result") or {}).get("verdict"),
                               "violations": (guard.get("result") or {}).get("count"),
                               "high": (guard.get("result") or {}).get("high"),
                               "note": "只记数不阻断（历史账本里的旧违规不追溯）"}}
    ok = sig["ok"] and truth["ok"] and inv["ok"]
    steps.append(_step_record(3, "验证", ev3, ok))
    if not ok:
        return _fail(steps, 3, "验证没通过")

    # Step 4 固化
    recorded = False
    try:
        from .. import orchestration as OB
        OB.record("run", "chain_kernel",
                  detail="七步链 goal=%s blueprint=%s approve=%s" % (goal[:60], bid, approve),
                  evidence="state/orchestration-ledger.jsonl")
        recorded = True
    except Exception:
        recorded = False
    cs = _cap("cap_self", {"op": "verify"})
    counts = (cs.get("result") or {}).get("counts") or {}
    consistent = len(set(counts.values())) == 1 if counts else False
    ev4 = {"ledger_recorded": recorded, "cap_self": counts, "consistent": consistent}
    ok = recorded and consistent
    steps.append(_step_record(4, "固化", ev4, ok))
    if not ok:
        return _fail(steps, 4, "固化没完成")

    # Step 5 报告
    passed = sum(1 for s in steps if s["passed"])
    steps.append(_step_record(5, "报告", {"steps": len(steps) + 1, "passed": passed}, True))
    return {"ok": True, "verdict": "chain_ok", "goal": goal, "blueprint": bid,
            "approve": bool(approve), "steps": steps,
            "note": "七步全过；每步证据见 steps[].evidence"}


def _fail(steps, step, why):
    return {"ok": False, "verdict": "chain_stopped", "stopped_at": step,
            "reason": why, "steps": steps,
            "note": "不可跳步：本步无证据/不通过 ⇒ 整链停在这里"}


def status() -> dict:
    return {"ok": True, "steps": ROOT_STEP, "count": len(ROOT_STEP),
            "rule": "不可跳步；每步必须有证据才能进下一步"}


def gate(step) -> dict:
    try:
        want = int(step)
    except Exception:
        return {"ok": False, "error": "user_error: step 要整数（-1..5）"}
    for s in ROOT_STEP:
        if s["step"] == want:
            return {"ok": True, "gate": s}
    return {"ok": False, "error": "user_error: 没有这一步：%s" % step}


def run_op(op: str = "status", **kw) -> dict:
    op = (op or "status").lower()
    if op == "run":
        return run(str(kw.get("goal") or ""), bool(kw.get("approve")),
                   str(kw.get("blueprint_id") or ""))
    if op == "status":
        return status()
    if op == "gate":
        return gate(kw.get("step"))
    return {"ok": False, "error": "chain_kernel 不认 op=%s（run/status/gate）" % op}
