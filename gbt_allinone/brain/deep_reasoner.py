# gbt-capability: deep-reasoner
# ⛔ 开发者：自由的风 · 永久钢印 · 禁止删除
"""GBT小土豆V8 深度推理脑 — 意图识别·深度推理·协同决策。

处理复杂任务分解、意图分析和多步推理。
"""
from __future__ import annotations
import sys
from typing import Any

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass


def recognize_intent(text: str) -> dict:
    """识别用户意图类型。"""
    intents = {
        "diagnose": ["诊断", "扫描", "检查", "health", "status", "穿透"],
        "fix": ["修复", "修", "解决", "fix", "repair"],
        "create": ["创建", "新建", "生成", "create", "build", "new"],
        "deploy": ["部署", "上线", "deploy", "publish"],
        "query": ["查", "问", "query", "搜索", "找", "what", "how"],
        "analyze": ["分析", "研究", "analyze", "research"],
        "manage": ["管理", "配置", "管理", "manage", "config"],
    }
    text_lower = text.lower()
    matched = []
    for intent, keywords in intents.items():
        if any(kw in text_lower for kw in keywords):
            matched.append(intent)
    return {
        "ok": True,
        "intents": matched[:3],
        "primary": matched[0] if matched else "general",
        "text": text,
    }


def decompose(task: str, depth: int = 3) -> list[dict]:
    """将任务分解为子步骤。"""
    steps = []
    # 基于关键词的简单分解规则
    decompose_rules = {
        "诊断": [{"action": "quick_pulse", "desc": "执行快速健康检查"},
                 {"action": "reflect", "desc": "分析审计日志"},
                 {"action": "explore", "desc": "深度探索问题区域"}],
        "修复": [{"action": "classify", "desc": "分类问题"},
                 {"action": "strategy", "desc": "制定修复策略"},
                 {"action": "execute", "desc": "执行修复"}],
        "创建": [{"action": "plan", "desc": "规划结构"},
                 {"action": "implement", "desc": "实现代码"},
                 {"action": "verify", "desc": "验证功能"}],
    }
    for keyword, step_list in decompose_rules.items():
        if keyword in task:
            steps.extend(step_list)
            break
    if not steps:
        steps = [{"action": "analyze", "desc": f"分析任务: {task}"}]
    return steps[:depth]


def reason(task: str) -> dict:
    """深度推理入口：意图识别 + 任务分解。"""
    intent = recognize_intent(task)
    steps = decompose(task)
    return {
        "ok": True,
        "intent": intent,
        "steps": steps,
        "reasoning": f"识别意图 [{intent['primary']}]，分解为 {len(steps)} 个子步骤",
    }
