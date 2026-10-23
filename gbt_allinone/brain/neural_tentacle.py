# gbt-capability: neural-tentacle
# ⛔ 开发者：自由的风 · 永久钢印 · 禁止删除
"""GBT小土豆V8 神经触手 — 脉冲/导航/反思/好奇/探索。

提供五步自主循环：quick_pulse → navigate → reflect → wonder → explore。
与 omni_process.py 的 deep_diagnose 配合，但也可独立运行。
"""
from __future__ import annotations
import sys, time, json
from pathlib import Path
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

_ROOT = Path(__file__).resolve().parent.parent
_STATE_PATH = _ROOT / "store" / "_neural_state.json"


class NeuralTentacle:
    """神经触手主类：脉冲·导航·反思·好奇·探索。"""

    def __init__(self):
        self._state = self._load_state()

    def _load_state(self) -> dict:
        try:
            if _STATE_PATH.exists():
                return json.loads(_STATE_PATH.read_text(encoding="utf-8"))
        except Exception:
            pass
        return {"last_pulse": None, "pulse_count": 0, "weak_points": [], "questions": []}

    def _save_state(self):
        try:
            _STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
            _STATE_PATH.write_text(json.dumps(self._state, ensure_ascii=False), encoding="utf-8")
        except Exception:
            pass

    def quick_pulse(self) -> dict:
        """92ms 增量心跳：跑 penetration_scan quick 模式。"""
        t0 = time.time()
        try:
            from . import penetration_scan as ps
            r = ps.quick_scan()
            elapsed = round((time.time() - t0) * 1000, 1)
            self._state["last_pulse"] = time.strftime("%Y-%m-%dT%H:%M:%S")
            self._state["pulse_count"] = self._state.get("pulse_count", 0) + 1
            self._save_state()
            return {**r, "elapsed_ms": elapsed, "mode": "quick_pulse"}
        except Exception as e:
            return {"ok": False, "error": str(e)[:200], "elapsed_ms": round((time.time()-t0)*1000,1)}

    def navigate(self, query: str = "") -> dict:
        """2ms 能力导航：按关键词查找相关能力。"""
        try:
            from . import topology_index as ti
            if query:
                results = ti.find(query)
                return {"ok": True, "query": query, "results": results[:10]}
            else:
                idx = ti.get()
                return {"ok": True, "domains": list(idx.get("by_domain", {}).keys()),
                        "total": idx.get("total_caps", 0)}
        except Exception as e:
            return {"ok": False, "error": str(e)[:200]}

    def reflect(self) -> dict:
        """101ms 反思穿透：分析近期审计日志中的异常模式。"""
        t0 = time.time()
        try:
            from .. import selfscan
            r = selfscan.scan()
            audit = r.get("sections", {}).get("audit", {})
            anomalies = audit.get("anomalies", 0)
            runtime = audit.get("runtime_faults", 0)
            by_event = audit.get("by_event", {})
            self._state["last_reflect"] = time.strftime("%Y-%m-%dT%H:%M:%S")
            self._save_state()
            return {
                "ok": True, "elapsed_ms": round((time.time()-t0)*1000, 1),
                "anomalies": anomalies, "runtime_faults": runtime,
                "by_event": by_event, "verdict": "clean" if runtime == 0 else "needs_attention"
            }
        except Exception as e:
            return {"ok": False, "error": str(e)[:200]}

    def wonder(self) -> list[dict]:
        """好奇发问：基于当前状态生成待探索问题列表。"""
        try:
            from .. import selfscan
            r = selfscan.scan()
            questions = []
            coverage = r.get("coverage_incomplete", [])
            for area in coverage:
                questions.append({
                    "topic": f"{area} 覆盖不完整",
                    "priority": "P1" if area in ("store", "audit") else "P2",
                    "suggestion": f"对 {area} 维度进行全量扫描（当前为抽样）"
                })
            # Check for missing brain modules
            missing = [m for m in ["topology_index","penetration_scan","curiosity_engine",
                                    "exploration_engine","cross_validation","neural_tentacle",
                                    "tentacle_reasoner","deep_reasoner","cognition",
                                    "intent_broker","brain_council","vision_tentacle",
                                    "market_intelligence","cap_optimizer"]
                       if not (Path(__file__).parent / f"{m}.py").exists()]
            for m in missing[:5]:
                questions.append({
                    "topic": f"脑模块 {m} 未实现",
                    "priority": "P1",
                    "suggestion": f"在 gbt_allinone/brain/{m}.py 中实现"
                })
            return questions
        except Exception as e:
            return [{"topic": "wonder_failed", "error": str(e)[:100]}]

    def explore(self) -> dict:
        """探索发现：遍历未覆盖区域，生成发现报告。"""
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
                "total_discoveries": len(issues) + len(errors)
            }
        except Exception as e:
            return {"ok": False, "error": str(e)[:200]}

    def topology(self) -> dict:
        """46KB 导航图：生成完整能力拓扑。"""
        try:
            from . import topology_index as ti
            return ti.nav()
        except Exception as e:
            return {"ok": False, "error": str(e)[:200]}

    def probe(self, target: str = "active") -> dict:
        """万能探针：针对指定目标深入探测。"""
        probes = {
            "active": lambda: self.quick_pulse(),
            "depth": lambda: self.explore(),
            "reflect": lambda: self.reflect(),
            "navigate": lambda: self.navigate(target),
            "topology": lambda: self.topology(),
        }
        fn = probes.get(target, probes["active"])
        try:
            return fn()
        except Exception as e:
            return {"ok": False, "error": str(e)[:200]}
