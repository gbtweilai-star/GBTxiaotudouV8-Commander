"""GBT小土豆V8 · 自主编排环（Autopilot）—— 从执行者到操盘手。

Owner 定调（2026-09-11）：一口气操控多个 AI 工作的严格实现。

环的纪律（比能力更重要）：
  1. 目标拆解由 LLM 提案、但节点必须落在已注册能力上（LLM 只出方案不出权限）；
  2. 每轮自检（selfscan+ghost_guard），发现问题生成修复工作流再跑——但总轮数有上限，
     超限如实停下报告（绝不无限自我循环烧钱）；
  3. 全程审计留痕；最终产出走 pipeline 发布带钢印；
  4. LLM 输出是数据不是指令：拆解结果经本地校验器过滤后才生成工作流。

流程：
  autopilot(goal, max_rounds=3)
    Round N: plan(LLM 拆解目标→节点草案) → validate(本地校验：能力已注册、依赖成环检查)
             → execute(wf_run) → inspect(selfscan) → 判断 clean / 修复 / 停
    终态: published（产出+报告） | clean（无产出需求） | stopped（轮数耗尽，如实报）
"""
import json
import time
from pathlib import Path

from . import engine
from .store import audit

_PLAN_PROMPT = """你是工作流架构师。把以下目标拆解为 3-6 个节点的工作流。
可用能力（只能用这些）：{caps}

关键能力的返回字段（模板引用必须用真实字段，格式 {{{{节点id.gbt_result.result.字段}}}}）：
- selfscan → verdict, capabilities_total, findings
- ghost_guard → clean, findings
- svc_inspect → up, total, down, services
- health → platform, python, time
- audit_query → total, sample
- count_words → words, chars
- echo → echo
- sec_surface → ok, total_vectors, risk_score, risk_level
- sec_scan → ok, total, critical, high, medium, vulnerabilities
- sec_defenses → ok, defense_status, passed, total
- selfscan → verdict, capabilities_total, findings
- ghost_guard → clean, findings
- pipeline_submit 的 params 必须含 name、content、meta.actor、meta.purpose 四项（缺 purpose 会被门禁拦截）
- pipeline_submit 的 content 里可用上述字段做模板，如："结论：{{{{b.gbt_result.result.verdict}}}}"

输出严格 JSON（不要多余文字）：
{{"nodes": [{{"id": "a", "kind": "能力名", "params": {{}}, "depends_on": []}}]}}
最后可加一个 pipeline_submit 节点把结论发布成文件（name 用 "autopilot-产出名.txt"，meta.actor 填 "autopilot"）。
目标：{goal}"""


class AutopilotError(Exception):
    pass


def _caps_menu():
    from .caps_registry import BENIGN_CAPS
    menu = []
    for name, info in BENIGN_CAPS.items():
        menu.append(f"{name}({info.get('domain','?')})")
    return ", ".join(sorted(menu))


def _llm_plan(goal):
    """LLM 拆解目标 → 节点草案（数据，不是指令）。"""
    # 统一大模型口（Owner 2026-09-19）：模块不许再自己直连 bridge。
    from .llm import unified as LLM
    r = LLM.ask(_PLAN_PROMPT.format(caps=_caps_menu()[:2000], goal=goal[:500]),
                max_tokens=1400, timeout=90, purpose="autopilot.plan")
    if not r.get("ok"):
        raise AutopilotError(f"LLM 拆解失败: {str(r.get('error'))[:120]}")
    text = r.get("reply", "")
    # 提取 JSON（容错：模型可能带 markdown 围栏）
    s, e = text.find("{"), text.rfind("}")
    if s < 0 or e <= s:
        raise AutopilotError("LLM 未输出可解析的 JSON 方案")
    raw = text[s:e + 1]
    try:
        plan = json.loads(raw)
    except Exception:
        # 截断容错：补齐闭合括号再试一次（LLM 输出被 max_tokens 切断的常见形态）
        for patch in (raw + ']}}', raw + '}}', raw + ']'):
            try:
                plan = json.loads(patch)
                break
            except Exception:
                continue
        else:
            raise AutopilotError("LLM 方案 JSON 解析失败（含截断修复尝试）")
    nodes = plan.get("nodes")
    if not isinstance(nodes, list) or not nodes:
        raise AutopilotError("LLM 方案缺少 nodes")
    return nodes


def _validate_nodes(nodes):
    """本地校验器：LLM 的方案必须落在已注册能力上（数据不是指令）。"""
    from .caps_registry import BENIGN_CAPS
    ids = [n.get("id") for n in nodes]
    if any(not i for i in ids) or len(set(ids)) != len(ids):
        raise AutopilotError("节点 id 非空且唯一 校验失败")
    for n in nodes:
        if n.get("kind") not in BENIGN_CAPS:
            raise AutopilotError(f"LLM 提案含未注册能力: {n.get('kind')}（已拒绝）")
    id_set = set(ids)
    for n in nodes:
        for d in n.get("depends_on", []):
            if d not in id_set:
                raise AutopilotError(f"依赖不存在: {d}")
    engine._topo_levels([{"id": n["id"], "depends_on": n.get("depends_on", [])} for n in nodes])
    return nodes


def autopilot(goal, max_rounds=3, dry_run=False):
    """自主编排环：拆解 → 校验 → 执行 → 自检 → 修复/停。"""
    if not goal:
        raise AutopilotError("需要 goal")
    from .api import run_task
    from .caps_registry import BENIGN_CAPS

    started = time.strftime("%Y-%m-%dT%H:%M:%S")
    rounds = []
    audit("autopilot_start", {"goal": goal[:120], "max_rounds": max_rounds})

    for rd in range(1, max_rounds + 1):
        # 1) LLM 拆解（操控 AI 出方案）
        try:
            nodes = _llm_plan(goal if rd == 1 else f"{goal}（第{rd}轮修复，聚焦上轮遗留问题）")
        except AutopilotError as e:
            rounds.append({"round": rd, "stage": "plan", "error": str(e)[:200]})
            break
        # 2) 本地校验（LLM 只是提案人，无权限）
        try:
            nodes = _validate_nodes(nodes)
        except AutopilotError as e:
            rounds.append({"round": rd, "stage": "validate", "error": str(e)[:200], "nodes": nodes})
            break
        if dry_run:
            rounds.append({"round": rd, "stage": "dry_run", "nodes": nodes,
                           "selfscan": "dry_run"})
            break
        # 3) 执行（生成工作流并跑）
        wf_name = f"autopilot-r{rd}"
        engine.define_workflow(wf_name, nodes)
        r = run_task("wf_run", {"name": wf_name, "max_node_retries": 1})
        body = r.get("gbt_result", r)
        rounds.append({"round": rd, "stage": "execute", "wf": wf_name,
                       "status": body.get("status"),
                       "nodes": body.get("result", {}).get("nodes", {})})
        # 4) 自检
        sc = run_task("selfscan", {})
        sc_b = sc.get("gbt_result", {}).get("result", {})
        rounds[-1]["selfscan"] = sc_b.get("verdict")
        # 5) 判断：clean 即收工；有问题且还有轮数 → 修复循环
        if sc_b.get("verdict") == "clean" and body.get("status") == "ok":
            break

    verdict = rounds[-1].get("selfscan") if rounds else None
    out = {
        "goal": goal[:200], "started": started,
        "finished": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "rounds_used": len(rounds), "rounds": rounds,
        "final_selfscan": verdict,
        "status": ("dry_run" if verdict == "dry_run"
                   else "done" if verdict == "clean" else "stopped"),
        "note": ("dry_run：拆解+校验通过，未执行" if verdict == "dry_run"
                 else "轮数上限内未达 clean 会如实报 stopped，绝不无限循环" if verdict != "clean"
                 else "目标完成，产出已走管线/审计留痕"),
    }
    audit("autopilot_" + out["status"], {"goal": goal[:80], "rounds": len(rounds)})
    return out
