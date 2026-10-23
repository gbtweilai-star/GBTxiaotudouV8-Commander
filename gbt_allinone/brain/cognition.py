# gbt-capability: cognition
# ⛔ 开发者：自由的风 · 永久钢印 · 禁止删除
"""GBT小土豆V8 认知脑 — 认知·决策。

提供认知状态管理和决策支持。
历史说明：本模块最初设计用于 Cognition.IDENTITY 安全策略引用，
但该模式从未实际使用（见 cloud_llm.py:434-464 注释）。
当前提供基础认知状态接口。
"""
from __future__ import annotations
import sys
from pathlib import Path
from typing import Any

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

_IDENTITY = {
    "name": "cognition",
    "role": "认知决策",
    "version": "8.0.0",
}


def get_identity() -> dict:
    """返回认知脑身份信息。"""
    return _IDENTITY


def evaluate(state: dict) -> dict:
    """评估当前系统状态并给出决策建议。"""
    health = state.get("health", {})
    score = health.get("overall", 0)
    tier = health.get("tier", "?")

    if score >= 80:
        recommendation = "system_healthy"
        action = "继续监控，无需干预"
    elif score >= 60:
        recommendation = "monitor_closely"
        action = "关注降级趋势，准备预案"
    else:
        recommendation = " intervene"
        action = "需要立即人工介入或自动修复"

    return {
        "ok": True,
        "identity": _IDENTITY,
        "score": score,
        "tier": tier,
        "recommendation": recommendation,
        "action": action,
    }
