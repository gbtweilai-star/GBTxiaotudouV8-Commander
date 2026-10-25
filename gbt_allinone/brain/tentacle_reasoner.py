# gbt-capability: tentacle-reasoner
# ⛔ 开发者：自由的风 · 永久钢印 · 禁止删除
"""GBT小土豆V8 触手推理 — 分类·根因·策略·模式检测。

分析扫描结果，给出分类诊断和行动建议。
"""
from __future__ import annotations
import sys
from typing import Any

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

_SEVERITY_MAP = {
    "file_missing": 3,
    "import_error": 4,
    "routing_mismatch": 3,
    "key_health": 2,
    "store_integrity": 4,
    "audit_anomaly": 3,
    "security_surface": 5,
    "module_unreachable": 3,
}


def classify(issues: list[dict], errors: list[dict]) -> dict:
    """分类问题并给出根因分析。"""
    categories: dict[str, list[str]] = {
        "missing_files": [],
        "import_failures": [],
        "routing_issues": [],
        "key_health": [],
        "integrity_issues": [],
        "security_concerns": [],
        "other": [],
    }
    for issue in issues:
        msg = issue.get("msg", str(issue)).lower()
        if "不存在" in msg or "not found" in msg or "missing" in msg:
            categories["missing_files"].append(issue.get("msg", str(issue)))
        elif "import" in msg:
            categories["import_failures"].append(issue.get("msg", str(issue)))
        elif "路由" in msg or "routing" in msg or "匹配" in msg:
            categories["routing_issues"].append(issue.get("msg", str(issue)))
        elif "key" in msg or "密钥" in msg:
            categories["key_health"].append(issue.get("msg", str(issue)))
        elif "store" in msg or "完整性" in msg or "integrity" in msg:
            categories["integrity_issues"].append(issue.get("msg", str(issue)))
        elif "安全" in msg or "security" in msg:
            categories["security_concerns"].append(issue.get("msg", str(issue)))
        else:
            categories["other"].append(issue.get("msg", str(issue)))

    for err in errors:
        msg = err.get("msg", str(err)).lower()
        if "import" in msg or "attribute" in msg or "type" in msg:
            categories["import_failures"].append(err.get("msg", str(err)))
        else:
            categories["other"].append(err.get("msg", str(err)))

    # 计算风险评分
    severity_scores = [_SEVERITY_MAP.get(c, 2) * len(v) for c, v in categories.items() if v]
    risk_score = sum(severity_scores) / max(1, len(severity_scores))

    return {
        "ok": True,
        "categories": {k: v for k, v in categories.items() if v},
        "category_counts": {k: len(v) for k, v in categories.items() if v},
        "risk_score": round(risk_score, 1),
        "risk_level": "critical" if risk_score >= 4 else "high" if risk_score >= 3 else "medium" if risk_score >= 2 else "low",
    }


def suggest_strategy(classification: dict) -> list[str]:
    """根据分类结果给出修复策略。"""
    strategies = []
    cats = classification.get("categories", {})
    if cats.get("missing_files"):
        strategies.append("补全缺失的 handler 文件或将其登记为 intentionally stub")
    if cats.get("import_failures"):
        strategies.append("检查 import 路径和依赖声明，修复断链")
    if cats.get("routing_issues"):
        strategies.append("对齐 caps_registry 与 api.py 的路由表")
    if cats.get("key_health"):
        strategies.append("检查触手密钥健康状态，必要时轮换")
    if cats.get("integrity_issues"):
        strategies.append("运行 store 修复工具，重建受损台账")
    if cats.get("security_concerns"):
        strategies.append("评估安全风险，必要时收紧权限策略")
    return strategies or ["暂无明确策略，建议人工审查"]
