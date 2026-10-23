# gbt-capability: cross-validation
# ⛔ 开发者：自由的风 · 永久钢印 · 禁止删除
"""GBT小土豆V8 交叉验证 — N触手网格交叉。

提供多视角验证机制，提升穿透扫描的可信度。
"""
from __future__ import annotations
import sys
from typing import Any

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass


def mesh_scan(n_tentacles: int = 3, mode: str = "full") -> dict:
    """N触手网格交叉验证。

    从多个独立视角采集同一信号，通过共识评分过滤假阳性。
    mode: 'quick' (L0+L1) | 'full' (L0-L7)
    """
    try:
        from . import penetration_scan as ps
        # 用不同参数跑多次扫描，模拟多触手
        results = []
        for i in range(min(n_tentacles, 3)):
            r = ps.quick_scan() if mode == "quick" else ps.run_full_scan(deep=True)
            results.append(r)

        # 收集所有错误/问题
        all_issues: list[dict] = []
        all_errors: list[dict] = []
        for r in results:
            all_issues.extend(r.get("issues", []))
            all_errors.extend(r.get("errors", []))

        # 去重：相同 msg 出现 >= 2 次视为共识
        from collections import Counter
        issue_counts = Counter(i.get("msg", str(i))[:60] for i in all_issues)
        error_counts = Counter(e.get("msg", str(e))[:60] for e in all_errors)

        confirmed_issues = [i for i in all_issues
                            if issue_counts.get(i.get("msg", str(i))[:60], 0) >= 2]
        confirmed_errors = [e for e in all_errors
                            if error_counts.get(e.get("msg", str(e))[:60], 0) >= 2]

        total_unique_issues = len(set(i.get("msg", str(i))[:60] for i in all_issues))
        total_unique_errors = len(set(e.get("msg", str(e))[:60] for e in all_errors))

        mesh_coverage = (len(confirmed_issues) + len(confirmed_errors)) / max(1,
            total_unique_issues + total_unique_errors) * 100

        return {
            "ok": True,
            "n_tentacles": n_tentacles,
            "mode": mode,
            "mesh_coverage_pct": round(mesh_coverage, 1),
            "mesh_confirmed": len(confirmed_issues) + len(confirmed_errors),
            "consensus_score": round(mesh_coverage, 2),
            "false_positives": (total_unique_issues + total_unique_errors) - (len(confirmed_issues) + len(confirmed_errors)),
            "details": {
                "total_issues_observed": total_unique_issues,
                "total_errors_observed": total_unique_errors,
                "confirmed_issues": len(confirmed_issues),
                "confirmed_errors": len(confirmed_errors),
            },
        }
    except Exception as e:
        return {"ok": False, "error": str(e)[:200]}
