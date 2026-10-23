# gbt-capability: exploration-engine
# ⛔ 开发者：自由的风 · 永久钢印 · 禁止删除
"""GBT小土豆V8 探索引擎 — 遍历·发现·机缘。

驱动神经触手的 explore() 方法，执行深度穿透扫描并生成发现报告。
"""
from __future__ import annotations
import sys

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass


def traverse(target_area: str = "all") -> dict:
    """遍历指定区域，返回发现报告。"""
    try:
        from . import penetration_scan as ps
        r = ps.run_full_scan(deep=True)
        issues = r.get("issues", [])
        errors = r.get("errors", [])
        health = r.get("health", {})
        return {
            "ok": True,
            "health_score": health.get("overall", 0),
            "tier": health.get("tier", "?"),
            "discoveries": [
                {"type": "issue", "detail": i.get("msg", str(i))} for i in issues[:10]
            ] + [
                {"type": "error", "detail": e.get("msg", str(e))} for e in errors[:5]
            ],
            "total_discoveries": len(issues) + len(errors),
        }
    except Exception as e:
        return {"ok": False, "error": str(e)[:200]}


def walk_through(domain: str) -> list[dict]:
    """遍历指定领域的所有能力，找出未连接项。"""
    try:
        from ..caps_registry import BENIGN_CAPS
        from . import topology_index as ti
        idx = ti.get()
        caps_in_domain = idx.get("by_domain", {}).get(domain, [])
        results = []
        for cap_id in caps_in_domain:
            info = idx.get("cap_info", {}).get(cap_id, {})
            handler = info.get("handler", cap_id)
            exists = __import__(f"gbt_allinone.{handler}", fromlist=[""]) is not None
            results.append({"id": cap_id, "handler": handler, "exists": exists})
        return results
    except Exception as e:
        return [{"error": str(e)[:200]}]
