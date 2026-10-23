"""GBT小土豆V8 · 推演环（think_loop）——完整心智循环能力。

设计来源（Owner 定调 2026-09-11）：按 AI 的完整心智模型设计——
下达任务 → 自己理解需求 → 调用工具 → 自我纠错 → 反向延伸 → 反思进取 → 整理结果。
吸收 Copilot Learn / Manus / Agent 的精髓，但全部落在 V8 自己的纪律上：
LLM 只有提案权，无执行权；推演在镜像维度，现实只收成品。

七步（每步都有真实执行与留痕）：
  1. 理解    LLM 复述任务 + 澄清要点（防理解偏差——只出理解，不出代码）
  2. 推演    方案在镜像维度 dry-run（不碰现实；假设/模拟全在这里）
  3. 执行    万能插真跑（调用工具）
  4. 纠错    失败自动诊断（哪一步错、为什么、怎么改）→ 改方案重试
  5. 反向延伸 结果反向推演（这个结果还能引出什么？哪里最脆弱？）
  6. 反思    领悟提炼落盘（polish_insights——反思进取）
  7. 整理    结构化结果 + 审计留痕

入口：run_task("think_loop", {"goal": "..."})
"""
import json
import time

from . import _paths
from .store import audit


class ThinkLoopError(Exception):
    pass


def _llm(prompt, max_tokens=600, timeout=60):
    # 🔴 2026-09-25 收口（主人令：「所有的运行读取 GBT小土豆V8 大模型」）：
    #    原来**直连** `llm.bridge.chat` —— 而统一口自己写着「框架内所有模块必须经此口调用模型；
    #    模块自己 import bridge **视为漂移**」（`llm/unified.py::status` 的原话）。
    #    改走 `llm.unified.ask`：**返回与 `bridge.chat` 同形**（ok/reply/provider/model），
    #    另多两样：`drift`（落到别家会**如实报**，不静默降级）与审计落点（只落元数据、不落正文）。
    #    两态复验见 `tools/codex-scripts/gbt-model-align.py doors`：绕过 1 → 0。
    from .llm import unified as LLM
    r = LLM.ask(prompt, max_tokens=max_tokens, timeout=timeout, purpose="think_loop")
    if r.get("ok") and str(r.get("reply", "")).strip():
        return r["reply"].strip()
    return None


# ── 七步各自实现 ──

def _step_understand(goal):
    """1) 理解需求：LLM 复述任务要点（防偏差）。失败则原样返回（理解降级为原文）。"""
    reply = _llm(
        f"用不超过 5 行复述这个任务要达成什么、关键约束是什么、怎样算完成（只复述理解，不写方案不写代码）：\n{goal[:600]}",
        max_tokens=300, timeout=45)
    if not reply:
        return {"ok": True, "understanding": goal[:300], "degraded": "LLM 不可用，按原文理解"}
    return {"ok": True, "understanding": reply[:800]}


def _step_simulate(goal, understanding):
    """2) 推演：在镜像维度生成方案草案（autopilot dry_run——只拆解校验，不执行）。"""
    from .autopilot import autopilot
    r = autopilot(goal, max_rounds=1, dry_run=True)
    plan_rounds = r.get("rounds", [])
    plan = plan_rounds[0] if plan_rounds else {}
    return {"ok": plan.get("stage") == "dry_run",
            "plan": plan.get("nodes", []),
            "note": "方案已推演（未执行——现实只收成品）" if plan.get("stage") == "dry_run"
            else f"推演形态: {plan.get('stage', '?')}"}


def _step_execute(goal):
    """3) 执行：万能插真跑（autopilot 实跑 = 调用工具 + 自检）。"""
    from .autopilot import autopilot
    r = autopilot(goal, max_rounds=3)
    return {"ok": r.get("status") == "done", "autopilot": r}


def _step_correct(goal, exec_result):
    """4) 自我纠错：失败时诊断根因并给出修正方向（LLM 提案，人/上层定夺）。"""
    if exec_result.get("ok"):
        return {"ok": True, "needed": False, "note": "一次通过，无需纠错"}
    ap = exec_result.get("autopilot", {})
    rounds = ap.get("rounds", [])
    errors = []
    for rd in rounds:
        if rd.get("error"):
            errors.append(f"R{rd.get('round')}: {rd['error'][:120]}")
        if rd.get("status") not in ("ok", None):
            errors.append(f"R{rd.get('round')}: 执行状态 {rd.get('status')}")
    diag = _llm(
        f"任务「{goal[:200]}」执行失败了。失败信息：{json.dumps(errors, ensure_ascii=False)[:600]}。"
        f"请诊断：1) 最可能的根因（一句话）2) 修正方向（一句话）3) 下一步建议（一句话）。",
        max_tokens=300, timeout=45)
    return {"ok": True, "needed": True, "errors": errors,
            "diagnosis": diag or "LLM 不可用——按错误清单人工判断",
            "note": "诊断只是提案，修正由下一轮执行验证"}


def _step_extend(goal, exec_result):
    """5) 反向延伸：从结果反推（还能做什么 / 哪里最脆弱）。"""
    ap = exec_result.get("autopilot", {})
    summary = json.dumps(ap.get("rounds", [])[-1:], ensure_ascii=False)[:500]
    reply = _llm(
        f"任务「{goal[:150]}」已完成到「{ap.get('status', '?')}」状态。最后一步摘要：{summary}。"
        f"反向推演：1) 这个结果还能自然引出哪 2 件下一步工作？2) 当前实现最脆弱的一环是什么？各一句话。",
        max_tokens=300, timeout=45)
    return {"ok": True, "extension": reply or "LLM 不可用——反向延伸降级为跳过"}


def _step_reflect(goal, steps_so_far):
    """6) 反思进取：领悟提炼落盘（polish_insights 永久资产）。"""
    ok_count = sum(1 for s in steps_so_far if s.get("ok"))
    insight = {
        "no": None,   # 自动续号
        "title": f"推演环反思：{goal[:40]}",
        "detail": f"七步走完 {ok_count}/{len(steps_so_far)} 步成功。"
                  f"理解→推演→执行→纠错→延伸的完整心智循环在本次任务中的实际路径已留审计。",
        "evidence": f"goal={goal[:60]}",
    }
    try:
        p = _paths.STORE_DIR / "polish_insights.json"
        data = json.loads(p.read_text(encoding="utf-8")) if p.exists() else {"insights": []}
        nums = [i.get("no", 0) for i in data.get("insights", []) if isinstance(i.get("no"), int)]
        insight["no"] = (max(nums) + 1) if nums else 1
        data.setdefault("insights", []).append(insight)
        p.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        return {"ok": True, "insight_no": insight["no"], "saved": True}
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "error": str(e)[:80], "note": "反思失败不阻塞主流程"}


def _step_deliver(goal, steps):
    """7) 整理结果：结构化汇总。"""
    return {"ok": True, "delivered_at": time.strftime("%Y-%m-%dT%H:%M:%S")}


# ── 主环 ──

def think_loop(goal, max_rounds=1):
    """完整心智循环：理解 → 推演 → 执行 → 纠错 → 反向延伸 → 反思 → 整理。"""
    if not goal:
        raise ThinkLoopError("需要 goal：任务描述")
    started = time.strftime("%Y-%m-%dT%H:%M:%S")
    audit("think_loop_start", {"goal": goal[:120]})

    steps = []

    # 1) 理解
    s1 = _step_understand(goal)
    steps.append({"step": "understand", **s1})
    audit("think_loop_step", {"step": "understand", "ok": s1.get("ok")})

    # 2) 推演（镜像维度：方案成形但不执行）
    s2 = _step_simulate(goal, s1.get("understanding"))
    steps.append({"step": "simulate", **s2})
    audit("think_loop_step", {"step": "simulate", "ok": s2.get("ok")})

    # 3) 执行（真跑）
    s3 = _step_execute(goal)
    steps.append({"step": "execute", "ok": s3.get("ok"),
                  "status": s3.get("autopilot", {}).get("status"),
                  "rounds_used": s3.get("autopilot", {}).get("rounds_used")})
    audit("think_loop_step", {"step": "execute", "ok": s3.get("ok")})

    # 4) 自我纠错（失败时诊断；如未过且允许，带诊断重试一轮执行）
    s4 = _step_correct(goal, s3)
    if s4.get("needed") and max_rounds > 1:
        s3b = _step_execute(f"{goal}（参考诊断修正：{str(s4.get('diagnosis', ''))[:150]}）")
        steps.append({"step": "execute_retry", "ok": s3b.get("ok"),
                      "status": s3b.get("autopilot", {}).get("status")})
        s3 = s3b
        s4 = {"ok": True, "needed": True, "retried": True,
              "final": s3b.get("ok"), "diagnosis": s4.get("diagnosis")}
    steps.append({"step": "correct", **s4})
    audit("think_loop_step", {"step": "correct", "ok": s4.get("ok")})

    # 5) 反向延伸
    s5 = _step_extend(goal, s3)
    steps.append({"step": "extend", "ok": s5.get("ok", True),
                  "extension": s5.get("extension", "")[:400]})
    audit("think_loop_step", {"step": "extend", "ok": True})

    # 6) 反思进取（领悟落盘）
    s6 = _step_reflect(goal, steps)
    steps.append({"step": "reflect", **s6})

    # 7) 整理结果
    s7 = _step_deliver(goal, steps)
    steps.append({"step": "deliver", **s7})

    ok_steps = sum(1 for s in steps if s.get("ok"))
    out = {
        "goal": goal[:200], "started": started,
        "finished": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "steps": len(steps), "ok_steps": ok_steps,
        "executed_ok": s3.get("ok"),
        "final_status": s3.get("autopilot", {}).get("status"),
        "detail": steps,
        "status": "done" if s3.get("ok") else "completed_with_errors",
    }
    audit("think_loop_done", {"goal": goal[:80], "ok_steps": f"{ok_steps}/{len(steps)}",
                               "executed_ok": s3.get("ok")})
    return out
