# gbt-capability: curiosity-engine
# ⛔ 开发者：自由的风 · 永久钢印 · 禁止删除
"""GBT小土豆V8 好奇引擎 — 缺口检测·薄弱点发问。

驱动神经触手的 wonder() 方法，识别系统弱点和待探索方向。
"""
from __future__ import annotations
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

_BRAIN_DIR = Path(__file__).resolve().parent
_KNOWN_MODULES = [
    "penetration_scan", "topology_index", "neural_tentacle",
    "curiosity_engine", "exploration_engine", "cross_validation",
    "tentacle_reasoner", "deep_reasoner", "cognition",
    "intent_broker", "brain_council", "vision_tentacle",
    "market_intelligence", "cap_optimizer",
]


def detect_gaps() -> list[dict]:
    """检测系统缺口并生成优先级问题列表。"""
    questions = []
    missing = [m for m in _KNOWN_MODULES
               if not (_BRAIN_DIR / f"{m}.py").exists()]
    for mod in missing[:5]:
        questions.append({
            "topic": f"脑模块 {mod} 未实现",
            "priority": "P1",
            "suggestion": f"在 gbt_allinone/brain/{mod}.py 中实现",
        })
    try:
        from .. import selfscan
        r = selfscan.scan()
        for area in r.get("coverage_incomplete", []):
            questions.append({
                "topic": f"{area} 覆盖不完整",
                "priority": "P1" if area in ("store", "audit") else "P2",
                "suggestion": f"对 {area} 维度进行全量扫描（当前为抽样）",
            })
    except Exception:
        pass
    return questions


def priority_score(q: dict) -> int:
    """返回优先级数字（P1=1, P2=2）。"""
    return {"P1": 1, "P2": 2}.get(q.get("priority", "P2"), 2)


def ranked_questions() -> list[dict]:
    """按优先级排序返回问题列表。"""
    return sorted(detect_gaps(), key=priority_score)
