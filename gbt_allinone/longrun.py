"""GBT小土豆V8 · 长程任务层（无人值守 × 长程编程的大脑执行层）。

对齐旧大脑（orchestrator.TaskGraph/Judge + autonomous_loop 相位环）的成熟设计，
全部落在 V8 统一接口上：

- 任务图持久化 store/tasks.json —— 跨进程可续：进程死了，任务图还在，
  下一轮 tick 从断点接着跑（这是与 engine 进程内爆发式执行的本质区别）；
- Judge 非LLM验收 —— "完成"由验收标准判定（status_ok/contains:/file_exists:/no_error），
  不由模型自说自话；
- 指纹停滞检测 —— 同样的执行结果连续出现 3 次 → stalled，触发察言观色层的诚实上报；
- 重试上限 —— attempts < max_attempts 才重试，超限 failed，如实报告不硬撑。

与万能插引擎的分工：
  engine  = 单个工作流的 DAG 并行（秒~分钟级，进程内，带检查点）
  longrun = 跨进程长任务图（小时~天级，检查点天然落盘）
  schedule= 谁来推动（定时 tick 任一层，实现全自动无人值守）
"""
import hashlib
import json
import time
from pathlib import Path

_STORE = __import__("gbt_allinone._paths", fromlist=["STORE_DIR"]).STORE_DIR
_TASKS = _STORE / "tasks.json"

_PRIORITY = {"high": 0, "medium": 1, "low": 2}


class LongrunError(Exception):
    pass


def _load() -> dict:
    if _TASKS.exists():
        try:
            return json.loads(_TASKS.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {"next_id": 1, "tasks": []}


def _save(data: dict):
    _STORE.mkdir(parents=True, exist_ok=True)
    _TASKS.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def submit(description: str, kind: str, params=None, priority: str = "medium",
           depends_on=None, acceptance=None, max_attempts: int = 3) -> dict:
    """提交一个长程任务。acceptance 为非LLM验收标准列表（空 = 仅要求 status_ok）。"""
    from .caps_registry import BENIGN_CAPS
    from .store import audit
    if not description:
        raise LongrunError("需要 description")
    if kind not in BENIGN_CAPS:
        raise LongrunError(f"能力未注册: {kind}（只能编排已注册能力）")
    if priority not in _PRIORITY:
        raise LongrunError("priority 必须是 high/medium/low")
    data = _load()
    nid = int(data.get("next_id", 1))
    tid = f"T{nid:04d}"
    task = {
        "task_id": tid,
        "description": description,
        "kind": kind,
        "params": params or {},
        "priority": priority,
        "depends_on": list(depends_on or []),
        "acceptance": list(acceptance or ["status_ok"]),
        "max_attempts": max(1, int(max_attempts)),
        "attempts": 0,
        "status": "pending",
        "fingerprints": [],
        "last_error": "",
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
    }
    data.setdefault("tasks", []).append(task)
    data["next_id"] = nid + 1
    _save(data)
    audit("longrun_submit", {"task_id": tid, "kind": kind, "priority": priority})
    return {"ok": True, "task_id": tid}


def _pick(data: dict):
    """优先级 + 创建时间排序，取第一个依赖已满足的待办。"""
    tasks = data.get("tasks", [])
    for t in sorted(tasks, key=lambda x: (_PRIORITY.get(x.get("priority"), 1),
                                          x.get("created_at", ""))):
        if t.get("status") != "pending":
            continue
        deps_ok = all(any(o.get("task_id") == d and o.get("status") == "done"
                          for o in tasks) for d in t.get("depends_on", []))
        if deps_ok:
            return t
    return None


def _judge(result, acceptance: list):
    """非LLM验收：唯一"完成"判定。返回 (ok, reason)。"""
    body = result.get("gbt_result", result) if isinstance(result, dict) else {}
    # 授权门拒绝如实传导为失败：denied 意味着操作根本没执行，不能算任务成功
    _inner = body.get("result") if isinstance(body.get("result"), dict) else {}
    if _inner.get("denied") or body.get("denied"):
        return False, "人工授权门拒绝（未授权操作）"
    status_ok = body.get("status") == "ok"
    if not acceptance or acceptance == ["status_ok"]:
        return status_ok, "" if status_ok else f"执行状态: {body.get('status')}"
    blob = json.dumps(result, ensure_ascii=False).lower()
    for c in acceptance:
        c = str(c)
        if c == "status_ok":
            if not status_ok:
                return False, f"执行状态: {body.get('status')}"
        elif c.startswith("contains:"):
            kw = c.split(":", 1)[1].lower()
            if kw not in blob:
                return False, f"缺少关键词: {kw}"
        elif c.startswith("file_exists:"):
            import os
            p = c.split(":", 1)[1]
            if not os.path.exists(p):
                return False, f"文件不存在: {p}"
        elif c == "no_error":
            if body.get("status") == "error" or '"error"' in blob[:400]:
                return False, "结果包含错误"
        else:
            return False, f"未知验收标准: {c}"
    return True, "全部验收标准满足"


def tick(max_tasks: int = 1) -> dict:
    """推进任务图：取下一待办 → 执行 → Judge 验收 → 完成/重试/停滞/超限失败。"""
    from .api import run_task
    from .store import audit
    from . import tactics

    data = _load()
    ran = []
    for _ in range(max(1, int(max_tasks))):
        t = _pick(data)
        if t is None:
            break
        r = run_task(t["kind"], t.get("params") or {})
        ok, why = _judge(r, t.get("acceptance"))
        t["attempts"] = int(t.get("attempts", 0)) + 1

        if ok:
            t["status"] = "done"
            t["last_error"] = ""
            t.pop("escalation", None)
        else:
            fp = hashlib.sha256(json.dumps(r, ensure_ascii=False, sort_keys=True)
                                .encode("utf-8")).hexdigest()[:12]
            t.setdefault("fingerprints", []).append(fp)
            repeats = sum(1 for f in t["fingerprints"] if f == fp)
            if repeats >= 3:
                # 同样的结果第三次出现：硬撑没有意义，升级（三律3）
                t["status"] = "stalled"
                t["last_error"] = why
                t["escalation"] = tactics.escalate(t, {"fingerprint": fp, "repeats": repeats})
            elif t["attempts"] >= int(t.get("max_attempts", 3)):
                t["status"] = "failed"
                t["last_error"] = why
                t["escalation"] = tactics.escalate(t, {"attempts": t["attempts"]})
            else:
                t["status"] = "pending"  # 留待下一轮重试
                t["last_error"] = why
        audit("longrun_" + t["status"], {"task_id": t["task_id"], "attempts": t["attempts"]})
        ran.append({"task_id": t["task_id"], "status": t["status"],
                    "attempts": t["attempts"], "why": why[:120]})
        _save(data)

    return {"ran": ran, "progress": progress()}


def progress() -> dict:
    tasks = _load().get("tasks", [])
    done = sum(1 for t in tasks if t.get("status") == "done")
    failed = sum(1 for t in tasks if t.get("status") == "failed")
    stalled = sum(1 for t in tasks if t.get("status") == "stalled")
    return {"total": len(tasks), "done": done, "failed": failed,
            "stalled": stalled, "pending": len(tasks) - done - failed - stalled}


def status(task_id=None) -> dict:
    data = _load()
    tasks = data.get("tasks", [])
    if task_id:
        t = next((x for x in tasks if x.get("task_id") == task_id), None)
        if t is None:
            raise LongrunError(f"任务不存在: {task_id}")
        return t
    return {"progress": progress(), "tasks": tasks}
