"""长程任务监督器：用租约、心跳、检查点和有界重试保证任务可续作。

本模块只管理调度状态，不创建守护进程、不执行外部命令、不绕过生产授权。
外部调度器周期性调用 tick，工作者通过 claim/heartbeat/complete_step 推进。
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
import re
from typing import Any

from .._paths import STORE_DIR, verify_store_binding
from ..safe_io import FileLock, atomic_write_json, load_json


ROOT = STORE_DIR / "long_runs"
TASK_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,79}$")
TERMINAL = {"completed", "blocked", "cancelled"}

REVENUE_VIDEO_CYCLE = (
    {"key": "opportunity", "role": "首席商业机会分析师", "deliverable": "可验证需求与竞争窗口"},
    {"key": "economics", "role": "内容收益策略师", "deliverable": "收益假设、成本上限与停止线"},
    {"key": "research", "role": "首席情报研究员", "deliverable": "可追溯事实包与授权素材清单"},
    {"key": "script", "role": "长篇视频总编剧", "deliverable": "章节化剧本、钩子与留存节点"},
    {"key": "storyboard", "role": "视觉叙事与分镜导演", "deliverable": "镜头表、连续性规则与生成提示"},
    {"key": "assets", "role": "AI 视觉制片主管", "deliverable": "来源可追溯的视频、图像与动画素材"},
    {"key": "audio", "role": "声音导演与混音工程师", "deliverable": "配音、音乐、音效与响度读数"},
    {"key": "edit", "role": "资深长片剪辑师", "deliverable": "成片、字幕、章节点与导出清单"},
    {"key": "quality", "role": "独立媒体质量审计官", "deliverable": "事实、版权、音画、留存与安全复核"},
    {"key": "publish_learn", "role": "发布归因与增长经理", "deliverable": "主人审批包、发布记录、收益归因与下轮实验"},
)


def _now(value: str = "") -> datetime:
    if value:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return parsed.astimezone(timezone.utc)
    return datetime.now(timezone.utc)


def _iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _path(task_id: str) -> Path:
    task_id = str(task_id or "").strip()
    if not TASK_ID.fullmatch(task_id):
        raise ValueError("task_id 只允许 1-80 位字母、数字、下划线或连字符")
    return ROOT / f"{task_id}.json"


def _read(task_id: str) -> dict:
    state = load_json(_path(task_id), None)
    if not isinstance(state, dict):
        raise KeyError(f"长线任务不存在: {task_id}")
    return state


def _update(task_id: str, mutator) -> dict:
    verify_store_binding()
    target = _path(task_id)
    target.parent.mkdir(parents=True, exist_ok=True)
    with FileLock(target.with_suffix(".lock")):
        state = load_json(target, None)
        if not isinstance(state, dict):
            raise KeyError(f"长线任务不存在: {task_id}")
        result = mutator(state)
        atomic_write_json(target, state)
        return result if isinstance(result, dict) else state


def create(task_id: str, objective: str, steps: list, *, room_id: str = "",
           heartbeat_seconds: int = 60, lease_seconds: int = 180,
           max_retries: int = 5, now: str = "") -> dict:
    verify_store_binding()
    target = _path(task_id)
    objective = str(objective or "").strip()
    if not objective or len(objective) > 2000:
        raise ValueError("objective 必须为 1-2000 字符")
    if not isinstance(steps, list) or not steps or len(steps) > 200:
        raise ValueError("steps 必须包含 1-200 个步骤")
    if not 10 <= int(heartbeat_seconds) <= 3600:
        raise ValueError("heartbeat_seconds 必须在 10-3600 之间")
    if not 30 <= int(lease_seconds) <= 86400:
        raise ValueError("lease_seconds 必须在 30-86400 之间")
    if not 0 <= int(max_retries) <= 20:
        raise ValueError("max_retries 必须在 0-20 之间")
    normalized = []
    for index, item in enumerate(steps, 1):
        title = str(item.get("title") if isinstance(item, dict) else item).strip()
        if not title or len(title) > 300:
            raise ValueError(f"第 {index} 个步骤无效")
        normalized.append({"id": f"step-{index:03d}", "title": title, "state": "pending",
                           "attempt": 0, "evidence": [], "completed_at": ""})
    timestamp = _iso(_now(now))
    state = {
        "schema": "gbt-long-run/v1", "task_id": task_id, "objective": objective,
        "room_id": str(room_id or f"long-run-{task_id}"), "state": "planned",
        "steps": normalized, "current_step": normalized[0]["id"],
        "worker_id": "", "lease_expires_at": "", "heartbeat_at": "",
        "heartbeat_seconds": int(heartbeat_seconds), "lease_seconds": int(lease_seconds),
        "max_retries": int(max_retries), "next_retry_at": "", "checkpoint": {},
        "progress": {}, "last_error": "", "created_at": timestamp,
        "updated_at": timestamp, "owner_action_required": False,
        "production_authorization": "required_at_release",
    }
    target.parent.mkdir(parents=True, exist_ok=True)
    with FileLock(target.with_suffix(".lock")):
        if target.exists():
            raise FileExistsError(f"长线任务已存在: {task_id}")
        atomic_write_json(target, state)
    return {"ok": True, "task": state}


def claim(task_id: str, worker_id: str, *, lease_seconds: int = 0, now: str = "") -> dict:
    worker_id = str(worker_id or "").strip()
    if not TASK_ID.fullmatch(worker_id):
        raise ValueError("worker_id 格式无效")
    timestamp = _now(now)

    def mutate(state):
        if state["state"] in TERMINAL or state["state"] == "paused":
            return {"ok": False, "denied": True, "reason": f"任务状态为 {state['state']}"}
        expires = _now(state["lease_expires_at"]) if state.get("lease_expires_at") else None
        if state.get("worker_id") and state["worker_id"] != worker_id and expires and expires > timestamp:
            return {"ok": False, "denied": True, "reason": "租约仍由其他工作者持有"}
        duration = int(lease_seconds or state["lease_seconds"])
        if not 30 <= duration <= 86400:
            raise ValueError("lease_seconds 必须在 30-86400 之间")
        state.update(worker_id=worker_id, state="running", heartbeat_at=_iso(timestamp),
                     lease_expires_at=_iso(timestamp + timedelta(seconds=duration)),
                     updated_at=_iso(timestamp), owner_action_required=False)
        return {"ok": True, "task": state}
    return _update(task_id, mutate)


def _owned(state: dict, worker_id: str, timestamp: datetime) -> None:
    if state.get("worker_id") != worker_id:
        raise PermissionError("工作者不持有当前租约")
    if not state.get("lease_expires_at") or _now(state["lease_expires_at"]) <= timestamp:
        raise TimeoutError("租约已过期，请先执行 recover 或 claim")


def heartbeat(task_id: str, worker_id: str, *, progress: dict | None = None,
              checkpoint_ref: str = "", evidence: list | None = None, now: str = "") -> dict:
    timestamp = _now(now)

    def mutate(state):
        _owned(state, worker_id, timestamp)
        state["heartbeat_at"] = _iso(timestamp)
        state["lease_expires_at"] = _iso(timestamp + timedelta(seconds=state["lease_seconds"]))
        state["updated_at"] = _iso(timestamp)
        if isinstance(progress, dict):
            state["progress"] = progress
        if checkpoint_ref:
            state["checkpoint"] = {"ref": str(checkpoint_ref), "evidence": list(evidence or []),
                                   "step_id": state["current_step"], "at": _iso(timestamp)}
            state["state"] = "checkpointed"
        else:
            state["state"] = "running"
        return {"ok": True, "task": state}
    return _update(task_id, mutate)


def complete_step(task_id: str, worker_id: str, step_id: str, *, evidence: list,
                  now: str = "") -> dict:
    timestamp = _now(now)
    if not isinstance(evidence, list) or not evidence:
        raise ValueError("完成步骤必须提供非空 evidence")

    def mutate(state):
        _owned(state, worker_id, timestamp)
        step = next((item for item in state["steps"] if item["id"] == step_id), None)
        if not step:
            raise KeyError(f"步骤不存在: {step_id}")
        if step["state"] == "completed":
            return {"ok": True, "idempotent": True, "task": state}
        if state["current_step"] != step_id:
            raise ValueError("只能完成当前步骤")
        step.update(state="completed", evidence=list(evidence), completed_at=_iso(timestamp))
        pending = next((item for item in state["steps"] if item["state"] != "completed"), None)
        state["current_step"] = pending["id"] if pending else ""
        state["state"] = "running" if pending else "completed"
        state["updated_at"] = _iso(timestamp)
        if not pending:
            state["worker_id"] = ""
            state["lease_expires_at"] = ""
        return {"ok": True, "task": state}
    return _update(task_id, mutate)


def fail(task_id: str, worker_id: str, error: str, *, retryable: bool = True,
         now: str = "") -> dict:
    timestamp = _now(now)

    def mutate(state):
        _owned(state, worker_id, timestamp)
        step = next(item for item in state["steps"] if item["id"] == state["current_step"])
        step["attempt"] += 1
        state["last_error"] = str(error or "unknown error")[:2000]
        exhausted = not retryable or step["attempt"] > state["max_retries"]
        if exhausted:
            state.update(state="blocked", owner_action_required=True, next_retry_at="")
        else:
            delay = min(3600, 30 * (2 ** (step["attempt"] - 1)))
            state.update(state="waiting_retry", next_retry_at=_iso(timestamp + timedelta(seconds=delay)))
        state["worker_id"] = ""
        state["lease_expires_at"] = ""
        state["updated_at"] = _iso(timestamp)
        return {"ok": not exhausted, "retryable": not exhausted, "task": state}
    return _update(task_id, mutate)


def recover(task_id: str, worker_id: str, *, now: str = "") -> dict:
    state = _read(task_id)
    timestamp = _now(now)
    if state["state"] in TERMINAL or state["state"] == "paused":
        return {"ok": False, "denied": True, "reason": f"任务状态为 {state['state']}"}
    if state.get("lease_expires_at") and _now(state["lease_expires_at"]) > timestamp:
        return {"ok": False, "denied": True, "reason": "租约尚未过期"}
    if not state.get("checkpoint"):
        return _update(task_id, lambda item: _block_without_checkpoint(item, timestamp))
    return claim(task_id, worker_id, now=now)


def _block_without_checkpoint(state: dict, timestamp: datetime) -> dict:
    state.update(state="blocked", owner_action_required=True,
                 last_error="租约过期且无可恢复检查点", updated_at=_iso(timestamp))
    return {"ok": False, "denied": True, "reason": state["last_error"], "task": state}


def tick(task_id: str, *, now: str = "") -> dict:
    """只读续作决策；由外部调度器执行返回的 action。"""
    state = _read(task_id)
    timestamp = _now(now)
    if state["state"] in TERMINAL or state["state"] == "paused":
        action = "none"
    elif state["state"] == "waiting_retry":
        action = "claim" if _now(state["next_retry_at"]) <= timestamp else "wait_retry"
    elif state.get("lease_expires_at") and _now(state["lease_expires_at"]) <= timestamp:
        action = "recover" if state.get("checkpoint") else "escalate_owner"
    elif state.get("worker_id"):
        action = "continue"
    else:
        action = "claim"
    return {"ok": True, "readonly": True, "task_id": task_id, "state": state["state"],
            "action": action, "current_step": state.get("current_step", ""),
            "owner_action_required": state.get("owner_action_required", False)}


def status(task_id: str = "") -> dict:
    if task_id:
        return {"ok": True, "readonly": True, "task": _read(task_id)}
    tasks = []
    if ROOT.exists():
        for path in sorted(ROOT.glob("*.json")):
            state = load_json(path, None)
            if isinstance(state, dict):
                tasks.append({key: state.get(key) for key in
                              ("task_id", "objective", "state", "current_step", "updated_at",
                               "owner_action_required")})
    return {"ok": True, "readonly": True, "tasks": tasks}


def revenue_video_blueprint() -> dict:
    """只读长视频收益循环；收益是方向，证据、质量和主人授权是硬门。"""
    return {
        "ok": True,
        "readonly": True,
        "objective": "合法、可持续、可归因的长视频收益",
        "cycle": [dict(item) for item in REVENUE_VIDEO_CYCLE],
        "gates": ["需求证据", "单项成本上限", "事实核验", "版权清单",
                  "音画技术读数", "独立复核", "主人发布授权", "收益归因"],
        "optimization_metrics": ["每千次有效观看收益", "单分钟有效观看成本",
                                 "观看完成率", "转化率", "净收益", "复购或回访率"],
        "never_auto": ["伪造收益", "未授权素材", "绕过平台规则", "未经主人批准发布"],
    }


def revenue_video_mindmap() -> dict:
    """固定工作流的思维导图触发契约，可由 UI 编译为 DAG。"""
    branches = [
        ("trigger", "触发", ["定时扫描", "机会阈值", "主人委托", "数据异常"]),
        ("plan", "策划", ["需求证据", "收益假设", "成本上限", "停止条件"]),
        ("produce", "长视频生产", ["事实研究", "长篇剧本", "分镜", "视觉素材", "声音", "剪辑"]),
        ("audit", "独立审计", ["事实", "版权", "音画质量", "平台合规", "收益假设复核"]),
        ("release", "发布", ["镜像排练", "主人授权", "发布", "回滚点"]),
        ("learn", "归因复盘", ["有效观看", "转化", "净收益", "失败原因", "下轮实验"]),
    ]
    nodes = [{"id": "goal", "parent": "", "type": "goal", "label": "可归因长视频收益"}]
    for key, label, leaves in branches:
        nodes.append({"id": key, "parent": "goal", "type": "branch", "label": label})
        for index, leaf in enumerate(leaves, 1):
            nodes.append({"id": f"{key}-{index}", "parent": key, "type": "step", "label": leaf})
    return {
        "ok": True, "readonly": True, "schema": "gbt-trigger-mindmap/v1", "nodes": nodes,
        "compile_contract": {
            "required_fields": ["trigger", "role", "input", "output", "evidence", "on_failure"],
            "branch_policy": "只有条件节点可以分支；执行节点必须有唯一岗位和独立房间",
            "cycle_policy": "只允许复盘节点回到触发节点，且必须开启新轮次",
            "release_policy": "发布分支必须经过独立审计和主人授权",
        },
    }


def run(op: str = "status", **params: Any) -> dict:
    handlers = {"create": create, "claim": claim, "heartbeat": heartbeat,
                "complete_step": complete_step, "fail": fail, "recover": recover,
                "tick": tick, "status": status, "revenue_video_blueprint": revenue_video_blueprint,
                "revenue_video_mindmap": revenue_video_mindmap}
    handler = handlers.get(op)
    if not handler:
        return {"ok": False, "error": f"unknown op: {op}"}
    return handler(**params)
