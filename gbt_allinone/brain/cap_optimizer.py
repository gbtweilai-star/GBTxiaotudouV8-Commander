# gbt-capability: cap-optimizer
# ⛔ 开发者：自由的风 · 永久钢印 · 禁止删除
"""GBT小土豆V8 能力自优化脑 — 重复检测·强弱对比·自动替换。

分析和优化能力注册表的效率和覆盖度。
"""
from __future__ import annotations
import sys
from typing import Any

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass


def detect_duplicates(registry: dict = None) -> list[dict]:
    """检测重复或冗余的能力定义。"""
    if registry is None:
        try:
            from ..caps_registry import BENIGN_CAPS
            registry = BENIGN_CAPS
        except ImportError:
            return []

    # 按 handler 分组
    by_handler: dict[str, list[str]] = {}
    for cap_id, info in registry.items():
        handler = info.get("handler", cap_id)
        by_handler.setdefault(handler, []).append(cap_id)

    duplicates = []
    for handler, cap_ids in by_handler.items():
        if len(cap_ids) > 1:
            duplicates.append({
                "handler": handler,
                "duplicates": cap_ids,
                "suggestion": f"合并重复handler: {handler}",
            })
    return duplicates


def compare_strength(cap_a: str, cap_b: str, registry: dict = None) -> dict:
    """对比两个能力的强弱。"""
    if registry is None:
        try:
            from ..caps_registry import BENIGN_CAPS
            registry = BENIGN_CAPS
        except ImportError:
            return {"ok": False, "error": "无法加载注册表"}

    a = registry.get(cap_a, {})
    b = registry.get(cap_b, {})
    if not a or not b:
        return {"ok": False, "error": "能力不存在"}

    # 简单对比：根据 desc 长度和 handler 存在性
    a_score = len(a.get("desc", "")) + (10 if a.get("handler") else 0)
    b_score = len(b.get("desc", "")) + (10 if b.get("handler") else 0)

    winner = cap_a if a_score > b_score else cap_b
    return {
        "ok": True,
        "cap_a": cap_a,
        "cap_b": cap_b,
        "score_a": a_score,
        "score_b": b_score,
        "winner": winner,
        "recommendation": f"优先使用 {winner}",
    }


def optimize(registry: dict = None) -> dict:
    """执行能力优化分析。"""
    if registry is None:
        try:
            from ..caps_registry import BENIGN_CAPS
            registry = BENIGN_CAPS
        except ImportError:
            return {"ok": False, "error": "无法加载注册表"}

    duplicates = detect_duplicates(registry)
    total_caps = len(registry)
    redundant = sum(len(d["duplicates"]) - 1 for d in duplicates)

    return {
        "ok": True,
        "total_caps": total_caps,
        "duplicate_groups": len(duplicates),
        "redundant_caps": redundant,
        "duplicate_details": duplicates,
        "optimization_score": round((total_caps - redundant) / max(1, total_caps) * 100, 1),
    }
