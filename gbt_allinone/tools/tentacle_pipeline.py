"""触手自动化流水线 · 四层七步只读判定。

本模块只读：不写盘、不出网、不执行触手动作。它把“隔离、汇报、排练、
终审、回滚”做成可查询、可测试的机械规则。
"""
from __future__ import annotations

AXIOMS = (
    {"no": 1, "key": "isolation_before_collaboration", "name": "隔离先于协作"},
    {"no": 2, "key": "report_before_aggregation", "name": "汇报先于汇总"},
    {"no": 3, "key": "rehearsal_before_publish", "name": "排练先于发布"},
)

LAYERS = (
    {"level": "L1", "name": "触手", "role": "沙盒隔离执行、各司其职、自检"},
    {"level": "L2", "name": "束长", "role": "束内调度、中间汇总、向上汇报"},
    {"level": "L3", "name": "总控", "role": "任务拆解、触手调度、全局一致性检查"},
    {"level": "L4", "name": "大脑", "role": "门禁、审计、终审、发布授权"},
)

STEPS = (
    "拆解", "沙盒", "执行", "自检", "汇报", "排练", "终审发布",
)

SHORT_BOARDS = (
    {"key": "scope_escape", "short": "越界执行", "fix": "沙盒白名单"},
    {"key": "false_report", "short": "汇报失真", "fix": "汇报必须带证据"},
    {"key": "hollow_dry_run", "short": "排练走过场", "fix": "dry-run 必须产读数"},
    {"key": "report_break", "short": "汇报断链", "fix": "心跳看护"},
    {"key": "review_overwrite", "short": "终审越权", "fix": "终审只判不改"},
    {"key": "no_rollback", "short": "发布无回滚", "fix": "发布带回滚点"},
)

RED_LINES = (
    {"key": "no_scope_escape", "name": "触手不许越界"},
    {"key": "evidence_required", "name": "汇报必须带证据"},
    {"key": "dry_run_must_have_readings", "name": "排练必须产读数"},
    {"key": "review_judges_only", "name": "终审只判不改"},
    {"key": "rollback_required", "name": "发布必须带回滚点"},
)

UPWARD = ("L1", "L2", "L3", "L4")
DOWNWARD = tuple(reversed(UPWARD))


def route_allowed(source: str, target: str, *, direction: str = "report") -> dict:
    if direction not in ("report", "auth"):
        return {"ok": False, "denied": True, "why": "未知流转方向"}
    chain = UPWARD if direction == "report" else DOWNWARD
    src = str(source or "").strip().upper()
    dst = str(target or "").strip().upper()
    if src not in chain or dst not in chain:
        return {"ok": False, "denied": True, "why": "未知层级"}
    allowed = chain.index(dst) == chain.index(src) + 1
    return {
        "ok": allowed,
        "denied": not allowed,
        "source": src,
        "target": dst,
        "direction": direction,
        "why": "只允许相邻层级单向流转" if not allowed else "相邻层级方向正确",
    }


def report_valid(report: dict) -> dict:
    if not isinstance(report, dict):
        return {"ok": False, "denied": True, "missing": [], "invalid": ["report"]}
    missing = []
    for key in ("self_check", "readings", "evidence"):
        if not report.get(key):
            missing.append(key)
    invalid = []
    if report.get("self_check") is not True:
        invalid.append("self_check")
    if not dry_run_valid(report.get("readings"))["ok"]:
        invalid.append("readings")
    evidence = report.get("evidence")
    if not isinstance(evidence, str) or not evidence.strip():
        invalid.append("evidence")
    return {
        "ok": not missing and not invalid,
        "denied": bool(missing or invalid),
        "missing": missing,
        "invalid": invalid,
        "validation_scope": "structure_only",
        "evidence_verified": False,
        "rule": "无证据汇报等于未完成",
    }


def dry_run_valid(readings: dict | None) -> dict:
    import math

    valid = isinstance(readings, dict) and bool(readings)
    invalid = []
    if valid:
        for name, value in readings.items():
            if (not isinstance(name, str) or not name.strip()
                    or not (value is True or (
                        type(value) in (int, float)
                        and (type(value) is int or math.isfinite(value))))):
                invalid.append(str(name))
    valid = valid and not invalid
    return {
        "ok": valid,
        "denied": not valid,
        "readings": readings,
        "invalid": invalid,
        "validation_scope": "structure_only",
        "rule": "没读数的 dry-run 不算排练",
    }


def publish_ready(*, review_ok: bool = False, rollback: str = "",
                  authorization: str = "") -> dict:
    missing = []
    if not review_ok:
        missing.append("review_ok")
    if not rollback:
        missing.append("rollback")
    if not authorization:
        missing.append("authorization")
    return {
        "ok": not missing,
        "denied": bool(missing),
        "missing": missing,
        "rule": "终审通过 + 回滚点 + 主人授权 才能发布",
    }


def readouts() -> dict:
    """只读取证口：报告当前仓已有的隔离/排练锚点。"""
    return {
        "ok": True,
        "readonly": True,
        "workspace_isolated": "deployment_rehearsal.py: workspace_isolated",
        "dry_run": "checkpoint / deployment_rehearsal / mirror / room rehearsal",
        "rollback": "mirror_space timelines + room_space passports",
        "known_gap": "汇报协议仍需逐能力统一为 self_check + readings + evidence",
    }


def run(op="status", **params):
    if op == "status":
        return {
            "ok": True,
            "readonly": True,
            "layers": list(LAYERS),
            "steps": list(STEPS),
            "axioms": list(AXIOMS),
            "red_lines": list(RED_LINES),
        }
    if op == "boards":
        return {"ok": True, "readonly": True, "short_boards": list(SHORT_BOARDS)}
    if op == "route":
        return route_allowed(params.get("source", ""), params.get("target", ""),
                             direction=params.get("direction", "report"))
    if op == "report":
        return report_valid(params.get("report", {}))
    if op == "dry_run":
        return dry_run_valid(params.get("readings", {}))
    if op == "publish":
        return publish_ready(
            review_ok=bool(params.get("review_ok")),
            rollback=str(params.get("rollback") or ""),
            authorization=str(params.get("authorization") or ""),
        )
    if op == "readouts":
        return readouts()
    return {"ok": False, "error": f"unknown op: {op}"}
