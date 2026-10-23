"""GBT小土豆V8 · 定时触发器（无人值守自主部署的最后一块）。

立场：wf_define 编排 + pipeline_submit 收尾已可手动跑通全链路；
本模块补上"何时跑"——按间隔自动触发工作流，无需任何人工点按钮。

模型：
  schedules.json: {name: {workflow, every_seconds, enabled, last_run_ts, last_status, ...}}
  tick(): 扫描全部到期调度 → 执行工作流（结果由引擎落盘 wf_runs）→ 更新调度状态 → 落审计
  run_forever(): 常驻循环（无人值守模式），间隔可调。

纪律：
  - 到期判定用单调推进的 last_run_ts，错过不补跑（防雪崩），下轮自然追上；
  - 工作流执行失败如实记录到调度条目（last_status=error + last_error），不吞不瞒。
"""
import json
import time
from pathlib import Path

_STORE = __import__("gbt_allinone._paths", fromlist=["STORE_DIR"]).STORE_DIR
_SCHED_FILE = _STORE / "schedules.json"


class SchedError(Exception):
    pass


def _load() -> dict:
    if _SCHED_FILE.exists():
        try:
            return json.loads(_SCHED_FILE.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}


def _save(data: dict):
    _STORE.mkdir(parents=True, exist_ok=True)
    _SCHED_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def define_schedule(name: str, workflow: str, every_seconds: int, enabled: bool = True) -> dict:
    """定义/覆盖一个定时调度。工作流必须已定义（wf_define），间隔必须为正。"""
    if not name:
        raise SchedError("需要 name")
    from . import engine
    if not engine.workflow_exists(workflow):
        raise SchedError(f"工作流不存在: {workflow}（先 wf_define）")
    try:
        every = int(every_seconds)
    except (TypeError, ValueError):
        raise SchedError("every_seconds 必须是整数")
    if every <= 0:
        raise SchedError("every_seconds 必须 > 0")
    data = _load()
    data[name] = {
        "workflow": workflow,
        "every_seconds": every,
        "enabled": bool(enabled),
        "defined_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "last_run_ts": 0,
        "last_status": "never",
    }
    _save(data)
    return {"ok": True, "name": name, "workflow": workflow, "every_seconds": every}


def remove_schedule(name: str) -> dict:
    data = _load()
    if name not in data:
        raise SchedError(f"调度不存在: {name}")
    data.pop(name)
    _save(data)
    return {"ok": True, "removed": name}


def set_enabled(name: str, enabled: bool) -> dict:
    data = _load()
    if name not in data:
        raise SchedError(f"调度不存在: {name}")
    data[name]["enabled"] = bool(enabled)
    _save(data)
    return {"ok": True, "name": name, "enabled": bool(enabled)}


def tick() -> dict:
    """扫描全部到期调度并执行。可被 API / 常驻循环 / 计划任务任意一方驱动。"""
    from . import engine
    from .store import audit

    data = _load()
    now = time.time()
    ran = []
    for name, s in data.items():
        if not s.get("enabled", True):
            continue
        if now - float(s.get("last_run_ts", 0)) < float(s.get("every_seconds", 0)):
            continue
        try:
            r = engine.run_workflow(s["workflow"])
            s["last_run_ts"] = now
            s["last_run_at"] = time.strftime("%Y-%m-%dT%H:%M:%S")
            s["last_status"] = r["status"]
            s["last_run_id"] = r["run_id"]
            ran.append({"schedule": name, "workflow": s["workflow"],
                        "status": r["status"], "run_id": r["run_id"]})
        except Exception as e:  # noqa: BLE001
            s["last_run_ts"] = now
            s["last_status"] = "error"
            s["last_error"] = str(e)[:200]
            ran.append({"schedule": name, "status": "error", "error": str(e)[:200]})
    _save(data)
    audit("sched_tick", {"ran": len(ran)})
    return {"ran": ran, "count": len(ran)}


def status(name=None) -> dict:
    data = _load()
    if name:
        if name not in data:
            raise SchedError(f"调度不存在: {name}")
        return {name: data[name]}
    return {"schedules": data, "count": len(data)}


def run_forever(interval: int = 30):
    """无人值守常驻循环：每 interval 秒 tick 一次。Ctrl+C 可停。"""
    from .store import audit
    audit("sched_forever_start", {"interval": interval})
    while True:
        try:
            tick()
        except Exception as e:  # noqa: BLE001
            audit("sched_forever_error", {"reason": str(e)[:200]})
        time.sleep(max(5, int(interval)))
