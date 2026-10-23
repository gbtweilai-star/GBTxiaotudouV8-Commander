# gbt-capability: penetration-scan
# ⛔ 开发者：自由的风 · 永久钢印 · 禁止删除
"""GBT小土豆V8 穿透扫描层 — L0~L7 全层扫描 + 智能评分 + 修复建议。

与 omni_process.py 对接：
  - quick_scan()        → L0+L1 快速扫描（<3s）
  - run_full_scan(deep) → 全层 L0~L7 + 交叉验证

输出契约：
  {"ok": bool, "health": {"overall": float, "tier": str},
   "total_issues": int, "total_errors": int, "elapsed_ms": float,
   "cross_validation": {...} 可选}
"""
from __future__ import annotations

import json
import time
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

_ROOT = Path(__file__).resolve().parent.parent
_STORE = _ROOT / "store"


def _pkg(name: str):
    """相对导入优先；被 spec_from_file_location 加载（无包上下文）时回落到绝对导入。

    2026-10-04 修（24h 审查实证）：本模块的唯一真实调用方 omni_process.diagnose() 用
    `spec_from_file_location("_pscan_diag", ...)` 加载 ⇒ `__package__=""` ⇒ 原来的
    `from .. import x` 六个扫描层全部 ImportError（被每层 except 吞成假错误、能力归零）。
    这里两条路都试，让「有包」和「无包」两种加载方式都能真跑。
    """
    import importlib
    try:
        return importlib.import_module(f"..{name}", package=__package__ or "")
    except Exception:
        return importlib.import_module(f"gbt_allinone.{name}")


_IMPL_KINDS_CACHE: set | None = None


def _api_implemented_kinds() -> set:
    """从 api.py 抽全部 `kind == "x"` / `kind in (...)` 分支名 —— 「实现存在」的真判据。

    2026-10-04 修：L0 原判据只看 `gbt_allinone/<handler>.py`，实测 216 个能力里
    **193 个 handler 名没有同名文件**（实现分散在 api.py 分支/子包里）⇒ 每次扫描固定
    吐 20 条假问题、健康分被压。改用「能力名 ∈ api 真分支 ∪ 文件存在」后缺口为 0。
    """
    global _IMPL_KINDS_CACHE
    if _IMPL_KINDS_CACHE is not None:
        return _IMPL_KINDS_CACHE
    import ast
    kinds: set = set()
    try:
        tree = ast.parse((_ROOT / "api.py").read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Compare) and isinstance(node.left, ast.Name) and node.left.id == "kind":
                for op, comp in zip(node.ops, node.comparators):
                    if isinstance(op, ast.Eq) and isinstance(comp, ast.Constant) and isinstance(comp.value, str):
                        kinds.add(comp.value)
                    elif isinstance(op, ast.In) and isinstance(comp, (ast.Tuple, ast.List, ast.Set)):
                        for elt in comp.elts:
                            if isinstance(elt, ast.Constant) and isinstance(elt.value, str):
                                kinds.add(elt.value)
    except Exception:
        pass
    _IMPL_KINDS_CACHE = kinds
    return kinds


# ── L0~L7 扫描维度定义 ──────────────────────────────────────────────────────
_SCANNERS = [
    # (level, name, fn, timeout_s)
    ("L0", "文件存在性",      "_scan_files_exist",      10),
    ("L1", "导入连通性",      "_scan_imports",          15),
    ("L2", "路由注册一致性",  "_scan_routing",           5),
    ("L3", "密钥健康度",      "_scan_keys",              5),
    ("L4", "存储完整性",      "_scan_store_json",        10),
    ("L5", "审计异常",        "_scan_audit_anomalies",   5),
    ("L6", "安全面测绘",      "_scan_security_surface",  8),
    ("L7", "架构模块可达",    "_scan_arch_modules",      5),
]


def quick_scan() -> dict:
    """L0+L1+L2 快速扫描，<3s。供 omni_process.diagnose() 调用。"""
    t0 = time.time()
    issues: list[dict] = []
    errors: list[dict] = []
    for level, name, fn, _to in _SCANNERS[:3]:
        try:
            r = globals()[fn]()
            issues.extend(r.get("issues", []))
            errors.extend(r.get("errors", []))
        except Exception as e:
            errors.append({"level": level, "scanner": name, "error": str(e)[:120]})
    elapsed = round((time.time() - t0) * 1000, 1)
    score = _calc_score(issues, errors)
    tier = "A" if score >= 90 else "B" if score >= 70 else "C" if score >= 50 else "D"
    return {
        "ok": len(errors) == 0,
        "health": {"overall": score, "tier": tier},
        "total_issues": len(issues),
        "total_errors": len(errors),
        "elapsed_ms": elapsed,
        "mode": "quick",
        "issues": issues[:20],
        "errors": errors[:10],
    }


def run_full_scan(*, deep: bool = False) -> dict:
    """全层 L0~L7 扫描。deep=True 时额外跑交叉验证。"""
    t0 = time.time()
    issues: list[dict] = []
    errors: list[dict] = []
    details: dict[str, dict] = {}

    for level, name, fn, _to in _SCANNERS:
        try:
            r = globals()[fn]()
            issues.extend(r.get("issues", []))
            errors.extend(r.get("errors", []))
            details[level] = r
        except Exception as e:
            errors.append({"level": level, "scanner": name, "error": str(e)[:120]})
            details[level] = {"error": str(e)[:200]}

    cv = None
    if deep:
        cv = _run_cross_validation(details)

    elapsed = round((time.time() - t0) * 1000, 1)
    score = _calc_score(issues, errors)
    tier = "A" if score >= 90 else "B" if score >= 70 else "C" if score >= 50 else "D"
    return {
        "ok": len(errors) == 0,
        "health": {"overall": score, "tier": tier},
        "total_issues": len(issues),
        "total_errors": len(errors),
        "elapsed_ms": elapsed,
        "mode": "full" + ("_deep" if deep else ""),
        "details": details,
        "cross_validation": cv,
    }


def _calc_score(issues: list, errors: list) -> float:
    """0~100 健康分：每错 -10，每问题 -2，下限 0。"""
    s = 100.0 - len(errors) * 10 - len(issues) * 2
    return max(0.0, round(s, 1))


# ── 各层扫描实现 ─────────────────────────────────────────────────────────────
def _scan_files_exist() -> dict:
    """L0: 核心能力位是否真接线（api.py 有分支 或 handler 文件在）。"""
    caps_registry = _pkg("caps_registry")
    ac = caps_registry.all_caps()
    impl = _api_implemented_kinds()
    missing = []
    for info in ac:
        name = info.get("name", "")
        handler = info.get("handler", "") or name
        if not name:
            continue
        if name in impl or _handler_file_exists(handler):
            continue
        missing.append(name)
    return {
        "issues": [{"id": n, "msg": f"未接线: 无 api.py 分支且无 {n} 对应 handler 文件"} for n in missing[:20]],
        "errors": [],
    }


def _handler_file_exists(handler: str) -> bool:
    """检查 handler 对应的 .py 文件是否存在。"""
    parts = handler.replace(".", "/").split("/")
    # 尝试 gbt_allinone/xxx.py 或 gbt_allinone/xxx/__init__.py
    candidates = [
        _ROOT / f"{parts[0]}.py",
        _ROOT / f"{'/'.join(parts)}.py",
        _ROOT / f"{'/'.join(parts)}/__init__.py",
    ]
    return any(p.exists() for p in candidates)


def _scan_imports() -> dict:
    """L1: 全部 handler 能否正常 import。"""
    caps_registry = _pkg("caps_registry")
    import importlib
    ac = caps_registry.all_caps()
    errors = []
    for info in ac:
        handler = info.get("handler", "")
        if not handler:
            continue
        try:
            mod_path = handler.replace(".", "/")
            if not mod_path.startswith("gbt_allinone/"):
                mod_path = f"gbt_allinone/{mod_path}"
            parts = mod_path.replace("/", ".").rsplit(".", 1)
            __import__(parts[0], fromlist=[parts[1] if len(parts) > 1 else ""])
        except Exception as e:
            errors.append({
                "cap": info["name"], "handler": handler,
                "error": f"{type(e).__name__}: {str(e)[:80]}",
            })
    return {"issues": [], "errors": errors[:30]}


def _scan_routing() -> dict:
    """L2: caps_registry 注册 vs api.py 路由 一致性。"""
    selfscan = _pkg("selfscan")
    r = selfscan.scan()
    routing = r.get("sections", {}).get("routing", {})
    issues = []
    if routing.get("unrouted"):
        issues.extend({"id": n, "msg": f"未路由: {n}"} for n in routing["unrouted"][:10])
    if routing.get("ghost_routes"):
        issues.extend({"id": n, "msg": f"幽灵路由: {n}"} for n in routing["ghost_routes"][:10])
    return {"issues": issues, "errors": []}


def _scan_keys() -> dict:
    """L3: LLM 密钥链健康度。"""
    cl = _pkg("llm.cloud_llm")
    r = cl.run(action="status")
    errors = []
    gw = r.get("gateway", {})
    order = gw.get("order", [])
    alive = gw.get("alive", 0)
    if alive < 3:
        errors.append({"msg": f"存活密钥数过低: {alive}/{len(order)}"})
    services = gw.get("service", [])
    if not services:
        errors.append({"msg": "无可用 service provider"})
    return {"issues": [], "errors": errors}


def _scan_store_json() -> dict:
    """L4: store JSON 文件抽样完整性。"""
    store = _STORE
    if not store.exists():
        return {"issues": [], "errors": [{"msg": "store 目录不存在"}]}
    json_files = list(store.rglob("*.json"))
    if not json_files:
        return {"issues": [], "errors": []}
    errors = []
    issues = []
    sample = json_files[:200]
    for p in sample:
        try:
            with open(p, encoding="utf-8") as f:
                json.load(f)
        except json.JSONDecodeError as e:
            errors.append({"file": str(p.relative_to(_ROOT)), "error": str(e)[:80]})
        except Exception:
            pass
    return {"issues": issues, "errors": errors[:20]}


def _scan_audit_anomalies() -> dict:
    """L5: 审计日志近期异常聚合。"""
    selfscan = _pkg("selfscan")
    r = selfscan.scan()
    audit = r.get("sections", {}).get("audit", {})
    runtime = audit.get("runtime_faults", 0)
    if runtime > 0:
        return {"issues": [], "errors": [{"msg": f"runtime 异常: {runtime} 条"}]}
    return {"issues": [], "errors": []}


def _scan_security_surface() -> dict:
    """L6: 安全面基本检测。"""
    try:
        cross_scan = _pkg("cross_scan")
        r = cross_scan.scan()
        errors = []
        issues = []
        if isinstance(r, dict):
            errors = r.get("errors", [])
            issues = r.get("issues", [])
        return {"issues": issues[:10], "errors": errors[:10]}
    except Exception as e:
        return {"issues": [], "errors": [{"msg": f"cross_scan 不可用: {e}"}]}


def _scan_arch_modules() -> dict:
    """L7: AGENTS.md 承诺的脑模块是否就位。"""
    promised = [
        "gbt_allinone.tentacle.omni_tentacle",
        "gbt_allinone.devour",
        "gbt_allinone.chain",
        "gbt_allinone.mirror_space",
        "gbt_allinone.truth_scan",
        "gbt_allinone.cross_scan",
        "gbt_allinone.selfscan",
        "gbt_allinone.tentacle.brain.gatekeeper",
        "gbt_allinone.tentacle.brain.visual_memory",
        "gbt_allinone.tools.pulse",
        "gbt_allinone.llm.cloud_llm",
        "gbt_allinone.llm.key_gateway",
        "gbt_allinone.security.net_guard",
        "gbt_allinone.security.ai_audit",
        "gbt_allinone.security.policy",
    ]
    import importlib
    errors = []
    for mod in promised:
        try:
            importlib.import_module(mod)
        except Exception as e:
            errors.append({"module": mod, "error": f"{type(e).__name__}: {str(e)[:60]}"})
    return {"issues": [], "errors": errors}


def _run_cross_validation(details: dict) -> dict:
    """N触手网格交叉验证（简化版）。"""
    # 统计各层问题共识度
    all_errors = []
    for lvl, d in details.items():
        all_errors.extend(d.get("errors", []))
    all_issues = []
    for lvl, d in details.items():
        all_issues.extend(d.get("issues", []))

    # 去重计数：同一 error.msg 出现多次 → 高置信问题
    msg_counts: dict[str, int] = {}
    for e in all_errors:
        msg = e.get("msg", str(e))[:60]
        msg_counts[msg] = msg_counts.get(msg, 0) + 1
    confirmed = sum(1 for c in msg_counts.values() if c >= 2)
    total = len(all_errors)
    coverage = round(confirmed / max(total, 1) * 100, 1)
    consensus = round(coverage, 1) if total > 0 else 100.0
    return {
        "mesh_coverage_pct": coverage,
        "mesh_confirmed": confirmed,
        "consensus_score": consensus,
        "mesh_false_positives": total - confirmed,
    }


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["quick", "full", "deep"], default="quick")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    if args.mode == "quick":
        r = quick_scan()
    elif args.mode == "deep":
        r = run_full_scan(deep=True)
    else:
        r = run_full_scan(deep=False)

    if args.json:
        print(json.dumps(r, ensure_ascii=False, indent=2))
    else:
        h = r.get("health", {})
        print(f"穿透扫描 [{args.mode}] — 健康分 {h.get('overall')}/100 tier={h.get('tier')}")
        print(f"  问题: {r.get('total_issues', 0)}  错误: {r.get('total_errors', 0)}  耗时: {r.get('elapsed_ms', 0)}ms")
        for e in r.get("errors", [])[:5]:
            print(f"  ✗ {e}")
        for i in r.get("issues", [])[:5]:
            print(f"  ! {i}")
