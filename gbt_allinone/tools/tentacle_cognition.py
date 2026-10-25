# gbt-capability: tentacle_cognition
# ⛔ 开发者：自由的风 · 永久钢印 · 禁止删除
"""触手认知包（tentacle_cognition）· R-H195 只读骨架。

每根触手都拥有全部能力 ≠ 每根触手都知道自己要做什么。
前者是能力，后者是认知 —— 认知包是触手启动时由大脑注入的那一份"我该干什么"。

认知包五件：任务上下文 · 角色边界 · 自检三问 · 不确定上报 · 操作留痕。

五条零容忍红线（做成机械闸）：
  ① 未测不按绿（no_readings）② 盲猜即违规（missing_params / missing_context）
  ③ 无痕即未发生（no_trace）④ 无自检不许执行（no_selfcheck）
  ⑤ 能力全息，上下文聚焦（not_focused）

本骨架只读：不写盘、不出网、不执行任何真实触手动作。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

PACK_FIELDS = ("task_id", "goal", "scene", "boundary", "capabilities")
PACK_CN = {"task_id": "任务 ID", "goal": "目标", "scene": "场景", "boundary": "边界",
           "capabilities": "可用能力子集"}

THREE_QUESTIONS = ("what", "why_allowed", "rollback")
QUESTION_CN = {"what": "我要做什么", "why_allowed": "我凭什么做", "rollback": "做错了怎么回滚"}

RED_LINES = (
    "未测不按绿——没有读数，不许标『已完成』",
    "盲猜即违规——缺参 missing_params，缺上下文 missing_context，不许默认值填充",
    "无痕即未发生——没写 trace 的操作，等于没做过",
    "无自检不许执行——三问答不出，拒执行，不许硬做",
    "能力全息，上下文聚焦——只激活相关子集，不许『什么都能干所以什么都想干』",
)

DEFAULT_MAX_DEPTH = 3


@dataclass
class CognitionPack:
    """认知包：大脑注入给触手的那一份"我该干什么"。"""

    task_id: str = ""
    goal: str = ""
    scene: str = ""
    boundary: str = ""
    capabilities: List[str] = field(default_factory=list)
    actor: str = ""
    expected_output: str = ""
    depth: int = 0


def inject(task_id: str, goal: str, scene: str, boundary: str,
           capabilities: Optional[List[str]] = None, actor: str = "",
           expected_output: str = "", depth: int = 0) -> dict:
    """注入认知包（大脑侧）。**五件缺一即拒**（不许无脑启动触手）。"""
    pack = CognitionPack(task_id=str(task_id or "").strip(), goal=str(goal or "").strip(),
                         scene=str(scene or "").strip(), boundary=str(boundary or "").strip(),
                         capabilities=list(capabilities or []), actor=str(actor or "").strip(),
                         expected_output=str(expected_output or "").strip(),
                         depth=int(depth or 0))
    missing = [f for f in PACK_FIELDS if not getattr(pack, f)]
    if missing:
        return {"ok": False, "denied": True, "rule": "missing_context", "missing": missing,
                "why": "认知包缺件（%s）⇒ 不许启动：无脑操作就是从这里开始的"
                       % "/".join(PACK_CN[m] for m in missing)}
    if pack.depth > DEFAULT_MAX_DEPTH:
        return {"ok": False, "denied": True, "rule": "depth_exceeded",
                "why": "拉起深度 %d 超过上限 %d（防递归失控）" % (pack.depth, DEFAULT_MAX_DEPTH)}
    return {"ok": True, "readonly": True, "pack": pack.__dict__, "fields": list(PACK_FIELDS)}


def selfcheck(pack: Any = None, what: str = "", why_allowed: str = "",
              rollback: str = "") -> dict:
    """自检三问（触手侧）：**答不出 ⇒ 拒执行**（红线④）。"""
    answers = {"what": str(what or "").strip(),
               "why_allowed": str(why_allowed or "").strip(),
               "rollback": str(rollback or "").strip()}
    silent = [k for k, v in answers.items() if not v]
    if silent:
        return {"ok": False, "denied": True, "rule": "no_selfcheck", "unanswered": silent,
                "why": "三问答不出（%s）⇒ 停下上报，不许硬做"
                       % "/".join(QUESTION_CN[k] for k in silent)}
    return {"ok": True, "readonly": True, "answers": answers}


def focus(capabilities: List[str], scene: str, activated: List[str]) -> dict:
    """红线⑤：能力**全息**，但当前任务**只激活相关子集**。"""
    all_caps = sorted(set(capabilities or []))
    act = sorted(set(activated or []))
    if not all_caps:
        return {"ok": False, "denied": True, "rule": "missing_context",
                "why": "能力全集为空：认知包没带能力面"}
    if not act:
        return {"ok": False, "denied": True, "rule": "not_focused",
                "why": "没有激活任何能力子集：不许『什么都能干所以什么都想干』"}
    unknown = [c for c in act if c not in all_caps]
    if unknown:
        return {"ok": False, "denied": True, "rule": "unknown_capability",
                "why": "激活了不存在的能力：%s" % ", ".join(unknown)}
    return {"ok": True, "readonly": True, "scene": str(scene or ""), "activated": act,
            "counts": {"all": len(all_caps), "activated": len(act)},
            "note": "全息是底层能力；聚焦是本任务的激活面"}


def preflight(pack: Any, params: Dict[str, Any], required_params: List[str],
              trace_ref: str = "", answers: Optional[Dict[str, str]] = None) -> dict:
    """执行前总闸：**缺参 / 缺痕 / 无自检** ⇒ 一律拒（红线②③④）。"""
    got = dict(params or {})
    missing = [k for k in (required_params or []) if got.get(k) in (None, "", [], {})]
    if missing:
        return {"ok": False, "denied": True, "rule": "missing_params", "missing": missing,
                "why": "缺参不许默认值填充（盲猜即违规）"}
    if not str(trace_ref or "").strip():
        return {"ok": False, "denied": True, "rule": "no_trace",
                "why": "没有 trace_ref：无痕即未发生"}
    ans = dict(answers or {})
    if not all(str(ans.get(k) or "").strip() for k in THREE_QUESTIONS):
        return {"ok": False, "denied": True, "rule": "no_selfcheck",
                "why": "三问没答全：无自检不许执行"}
    return {"ok": True, "readonly": True, "trace_ref": trace_ref,
            "note": "过闸：参数齐 · 有痕 · 三问答毕 —— 可以执行"}


def spawn(target: str, pack: Any, depth: int = 0, expected_output: str = "") -> dict:
    """拉起其他触手：**必须传认知包**（为什么拉 / 要什么 / 预期输出）+ 深度上限。"""
    if not isinstance(pack, (dict, CognitionPack)):
        return {"ok": False, "denied": True, "rule": "missing_context",
                "why": "拉起触手必须传认知包：缺包 = 让它盲猜"}
    body = pack if isinstance(pack, dict) else pack.__dict__
    if not body.get("task_id") or not body.get("goal"):
        return {"ok": False, "denied": True, "rule": "missing_context",
                "why": "认知包缺 task_id/goal"}
    if int(depth or 0) > DEFAULT_MAX_DEPTH:
        return {"ok": False, "denied": True, "rule": "depth_exceeded",
                "why": "深度超过上限 %d" % DEFAULT_MAX_DEPTH}
    if not str(expected_output or "").strip():
        return {"ok": False, "denied": True, "rule": "missing_params",
                "why": "拉起触手必须写清『预期输出』（不然收回来的是它猜的）"}
    return {"ok": True, "readonly": True, "target": str(target or ""),
            "depth": int(depth or 0), "task_id": body.get("task_id")}


def claim_done(readings: Optional[List[str]] = None) -> dict:
    """红线①：**未测不按绿** —— 没有读数就不许标"已完成"。"""
    rows = [r for r in (readings or []) if str(r or "").strip()]
    if not rows:
        return {"ok": False, "denied": True, "rule": "no_readings",
                "why": "没有读数，不许标『已完成』"}
    return {"ok": True, "readonly": True, "readings": rows, "count": len(rows)}


def run(op="redlines", **params) -> dict:
    """能力入口（只读骨架）：redlines / inject / selfcheck。不写盘、不出网、不执行。"""
    op = str(op or "redlines")
    if op == "redlines":
        return {"ok": True, "readonly": True, "red_lines": list(RED_LINES),
                "pack_fields": [{"key": k, "cn": PACK_CN[k]} for k in PACK_FIELDS],
                "questions": [{"key": k, "cn": QUESTION_CN[k]} for k in THREE_QUESTIONS],
                "max_depth": DEFAULT_MAX_DEPTH}
    if op == "inject":
        return inject(params.get("task_id", ""), params.get("goal", ""),
                      params.get("scene", ""), params.get("boundary", ""),
                      params.get("capabilities") or [], params.get("actor", ""),
                      params.get("expected_output", ""), params.get("depth", 0))
    if op == "selfcheck":
        return selfcheck(None, params.get("what", ""), params.get("why_allowed", ""),
                         params.get("rollback", ""))
    raise ValueError("未知 op %r（可用：redlines/inject/selfcheck）" % (op,))


HONEST_BOUNDARY = (
    "本骨架只保证『五件齐、三问答得出、留痕有据、不确定能停』。"
    "它不保证触手真的照做 —— 真正的执行体在各自模块里，本骨架是注入与闸门；"
    "真实 trace 落库（trace_store）尚未接线。"
)
