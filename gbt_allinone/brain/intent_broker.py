# gbt-capability: intent-broker
# ⛔ 开发者：自由的风 · 永久钢印 · 禁止删除
"""GBT小土豆V8 意图代理脑 — 意图路由到能力链。

将用户意图匹配到最佳能力组合，协调多步执行。
"""
from __future__ import annotations
import sys
from typing import Any

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass


def route(intent: str, context: dict = None) -> dict:
    """将意图路由到能力链。"""
    context = context or {}
    # 简单路由规则：根据意图关键词匹配能力
    routing_map = {
        "诊断": ["penetration_scan", "reflect"],
        "修复": ["tentacle_reasoner", "deep_reasoner"],
        "探索": ["exploration_engine", "curiosity_engine"],
        "导航": ["topology_index", "navigate"],
        "决策": ["deep_reasoner", "cognition"],
    }
    intent_lower = intent.lower()
    matched_chains = []
    for key, chain in routing_map.items():
        if key in intent_lower:
            matched_chains.append(chain)
    if not matched_chains:
        matched_chains = [["deep_reasoner", "penetration_scan"]]

    return {
        "ok": True,
        "intent": intent,
        "routed_chains": matched_chains,
        "primary_chain": matched_chains[0],
        "context": context,
    }


def execute_chain(chain: list[str], params: dict = None) -> list[dict]:
    """执行能力链。"""
    params = params or {}
    results = []
    for cap_name in chain:
        try:
            module_path = f"gbt_allinone.brain.{cap_name}"
            mod = __import__(module_path, fromlist=[""])
            if hasattr(mod, "reason"):
                results.append({"cap": cap_name, "result": mod.reason(params)})
            elif hasattr(mod, "route"):
                results.append({"cap": cap_name, "result": mod.route(params.get("intent", ""), params)})
            else:
                results.append({"cap": cap_name, "result": {"ok": True, "note": "no specific method"}})
        except Exception as e:
            results.append({"cap": cap_name, "error": str(e)[:100]})
    return results
