# gbt-capability: brain-council
# ⛔ 开发者：自由的风 · 永久钢印 · 禁止删除
"""GBT小土豆V8 脑委会 — 多脑协同决策。

协调多个脑模块的输出，达成共识决策。
"""
from __future__ import annotations
import sys
from typing import Any

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass


def deliberate(proposals: list[dict], criteria: dict = None) -> dict:
    """多脑提案评审，生成共识决策。

    proposals: [{"brain": name, "proposal": "...", "confidence": float}]
    """
    criteria = criteria or {"weight_health": 0.4, "weight_risk": 0.3, "weight_feasibility": 0.3}

    if not proposals:
        return {"ok": True, "verdict": "no_proposals", "decision": None}

    # 简单加权评分
    scores = []
    for p in proposals:
        brain = p.get("brain", "unknown")
        confidence = p.get("confidence", 0.5)
        # 根据脑模块类型赋予权重
        weight_map = {
            "deep_reasoner": criteria.get("weight_feasibility", 0.3),
            "cognition": criteria.get("weight_health", 0.4),
            "tentacle_reasoner": criteria.get("weight_risk", 0.3),
        }
        weight = weight_map.get(brain, 0.3)
        score = confidence * weight
        scores.append({"brain": brain, "score": score, "proposal": p.get("proposal", "")})

    # 选最高分
    best = max(scores, key=lambda x: x["score"]) if scores else None
    consensus = best["score"] > 0.3 if best else False

    return {
        "ok": True,
        "verdict": "consensus_reached" if consensus else "needs_more_input",
        "decision": best,
        "all_scores": scores,
        "criteria_used": criteria,
    }


def call_council(question: str, brains: list[str] = None) -> dict:
    """召集脑委会讨论问题。"""
    brains = brains or ["deep_reasoner", "cognition", "tentacle_reasoner"]
    proposals = []
    for brain_name in brains:
        try:
            mod = __import__(f"gbt_allinone.brain.{brain_name}", fromlist=[""])
            if hasattr(mod, "reason"):
                r = mod.reason(question)
                proposals.append({
                    "brain": brain_name,
                    "proposal": r.get("reasoning", str(r)),
                    "confidence": 0.7,
                })
            elif hasattr(mod, "evaluate"):
                r = mod.evaluate({"health": {"overall": 60, "tier": "C"}})
                proposals.append({
                    "brain": brain_name,
                    "proposal": r.get("action", str(r)),
                    "confidence": 0.6,
                })
            else:
                proposals.append({
                    "brain": brain_name,
                    "proposal": f"{brain_name} 无具体决策方法",
                    "confidence": 0.3,
                })
        except Exception as e:
            proposals.append({
                "brain": brain_name,
                "proposal": f"调用失败: {str(e)[:50]}",
                "confidence": 0.1,
            })

    return deliberate(proposals)
