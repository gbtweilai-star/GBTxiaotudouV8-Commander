# gbt-capability: agent_rig
# ⛔ 开发者：自由的风 · 永久钢印 · 禁止删除
"""编码智能体编队：**把本机已装的 CLI agent 编成并行流水线**（蒸馏自 GitHub 周榜 #02 `stablyai/orca`）。

## 抓取口径（凡抓取必写源·时间·口径）
· **源**：2026-09 第 39 周 GitHub 爆款周榜 #02 `orca`（79k★ · TypeScript）公开介绍：
  「用 **ADE** 并行编排一队 coding Agent · **用你自己的订阅跑任意编码 Agent** · 桌面/移动/VPS 多端 ·
  支持 **worktree 并行任务隔离** · 面向生产级的 Agent 开发环境」。一手仓库本轮**未联网核验**（不出网）。
· **时间**：2026-09-28。· **口径**：只移植架构，代码自写。

## 蒸馏判断：我们缺哪块
| orca 的能力 | 我们的对位 | 结论 |
|---|---|---|
| worktree / 端口 / 身份 / 日志 四隔离 | `tools/tentacle_fleet.py`（触手舰队，四隔离已实测） | **已有，直接复用口径** |
| DAG 并行编排 | `dagrun`（同 Spec 同 hash / 断点续跑） | **已有** |
| **"用你自己的订阅跑任意编码 agent"** | 没有统一入口：codex/claude/codebuddy 各自为政 | **补这块** |
| **一队 agent 的编队计划 + 收结果** | 没有（舰队偏"起 N 根"，不是"把一批活分给不同牌子的 agent"） | **补这块** |

## 三件新东西
1. **`agents`**：盘点可编排的 CLI agent（codex / claude / codebuddy / freebuff），**只读探针 + fail-closed**
   （读不到一律算不可用）；点名每个的**用途边界**（Codex=编程 · Claude=意见建议 · 其余按各自能力位）。
2. **`plan`**：把一批任务分成 N 份 ⇒ 每份一个 **worktree + 端口段 + 隔离 HOME + 独立日志**（口径抄舰队，
   不另立一套）；**只出计划不执行**。
3. **`dispatch`**：真起——**过 `process_execute` 门**；每份写**任务文件 + .cmd**（内容由工具生成、
   不含用户文本拼接），由 OS 起进程（与舰队同一条路，**不把命令交给 shell 拼**）。

**红线**：`dispatch` 缺票**如实拒**（缺什么写 `how_to_grant`）；不代持账号、不批量注册——
"用你自己的订阅"在本仓的落地就是**调用主人已装好并已授权的 CLI**，不是替你去注册。
op=agents / plan / dispatch / status / collect / verify / where
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
_STATE = _ROOT / "state"
_RIG = _STATE / "agent_rig.jsonl"
_PLANS = _STATE / "agent_rig_plans.json"
PORT_BASE, PORT_STEP = 32100, 12      # 与舰队同一段位口径（各份一块端口段，互不抢）
AGENTS = {
    "codex": {"cli": "codex", "role": "编程", "probe": ("codex_status", "status")},
    "claude": {"cli": "claude", "role": "意见建议（不决策）", "probe": ("claude_code", "status")},
    "codebuddy": {"cli": "codebuddy", "role": "杂事（无主项目执行权）", "probe": ("codebuddy", "status")},
    "freebuff": {"cli": "freebuff", "role": "免费默认档", "probe": None},
}


def _log(row: dict) -> None:
    _RIG.parent.mkdir(parents=True, exist_ok=True)
    with open(_RIG, "a", encoding="utf-8") as fh:
        fh.write(json.dumps({"at": time.strftime("%Y-%m-%dT%H:%M:%S"), **row}, ensure_ascii=False) + "\n")


def _gate(scope: str, detail: str) -> dict | None:
    try:
        from .. import auth_gate
        from ..security import policy as _policy
    except ImportError:
        sys.path.insert(0, str(_ROOT))
        import gbt_allinone as _g                            # noqa: F401
        from gbt_allinone import auth_gate                   # type: ignore
        from gbt_allinone.security import policy as _policy  # type: ignore
    if _policy.is_trusted():
        return None
    g = auth_gate.check_and_consume(scope, detail=detail)
    if g.get("ok"):
        return None
    return {"ok": False, "denied": True, "gate": scope, "error": g.get("error"),
            "how_to_grant": g.get("how_to_grant")}


def _probe(kind: str, op: str) -> dict:
    try:
        sys.path.insert(0, str(_ROOT))
        import gbt_allinone as g
        r = g.run_task(kind, {"op": op})
        p = r.get("result", r)
        if isinstance(p, dict) and "result" in p:
            p = p["result"]
        return p or {}
    except Exception as exc:                                  # noqa: BLE001
        return {"_probe_error": f"{type(exc).__name__}: {str(exc)[:80]}"}


def agents(**_kw) -> dict:
    """盘点可编排的编码 agent：可用性**只读探针 + fail-closed**（读不到一律算不可用）。"""
    out = {}
    for name, spec in AGENTS.items():
        if spec["probe"]:
            d = _probe(*spec["probe"])
            avail = bool(d.get("available") or d.get("codex_path") or d.get("found"))
            ev = {k: d.get(k) for k in ("available", "codex_path", "found", "connected")
                  if k in d} or {"探针": "没给读数（多半被门拒）⇒ 按不可用"}
        else:
            from shutil import which
            p = which(spec["cli"]) or which(spec["cli"] + ".cmd")
            avail, ev = bool(p), {"which": p or "未装"}
        out[name] = {**spec, "available": bool(avail), "evidence": ev}
    return {"ok": True, "op": "agents", "agents": out,
            "note": "只读盘点；**能不能真跑**还要看各自的门（process_execute / external_llm）",
            "_口径": "可用性 fail-closed：探针读不到就算不可用，不拿'应该能用'顶替"}


def _plans() -> dict:
    if _PLANS.is_file():
        try:
            return json.loads(_PLANS.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return {}
    return {}


def _save_plans(d: dict) -> None:
    tmp = _PLANS.with_name(_PLANS.name + ".tmp")
    tmp.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")
    os.replace(tmp, _PLANS)


def plan(tasks: str = "", agents_wanted: str = "codex", isolate: bool = True, **_kw) -> dict:
    """把一批任务分成 N 份（**只出计划**）：每份一个 worktree + 端口段 + 隔离 HOME + 独立日志。"""
    items = [x.strip() for x in tasks.split(";") if x.strip()]
    if not items:
        return {"ok": False, "op": "plan", "fail_closed": True,
                "error": "tasks 要给（分号分隔；例：'改 A 文件;跑 B 测试;整理 C 日志'）"}
    names = [x.strip() for x in agents_wanted.split(",") if x.strip()]
    bad = [n for n in names if n not in AGENTS]
    if bad:
        return {"ok": False, "op": "plan", "fail_closed": True,
                "error": f"不认识的 agent：{bad}（可编排：{sorted(AGENTS)}）"}
    if len(names) > len(items):
        names = names[:len(items)]
    pid = "rig-%s" % time.strftime("%Y%m%d-%H%M%S")
    workers = []
    for i, item in enumerate(items):
        agent = names[i % len(names)]
        wdir = _ROOT / ".fleet" / "rig" / pid / ("w%02d" % i)
        workers.append({
            "index": i, "agent": agent, "task": item[:200],
            "worktree": str(wdir / "worktree"), "log": str(wdir / "run.log"),
            "home": str(wdir / "home"), "port_block": [PORT_BASE + i * PORT_STEP,
                                                       PORT_BASE + i * PORT_STEP + PORT_STEP - 1],
            "isolate": bool(isolate),
        })
    doc = {"at": time.strftime("%Y-%m-%dT%H:%M:%S"), "plan_id": pid, "workers": workers,
           "state": "planned", "isolate": bool(isolate),
           "_口径": "四隔离口径抄 tentacle_fleet（worktree/端口段/隔离 HOME/独立日志）；**只出计划**"}
    d = _plans()
    d[pid] = doc
    _save_plans(d)
    _log({"event": "plan", "plan_id": pid, "workers": len(workers), "agents": sorted(set(names))})
    return {"ok": True, "op": "plan", "plan_id": pid, "workers": len(workers),
            "by_agent": {n: sum(1 for w in workers if w["agent"] == n) for n in sorted(set(names))},
            "first": workers[0], "note": "计划已存；真起用 op=dispatch（**要 process_execute 门**）"}


def dispatch(plan_id: str = "", start: bool = False, **_kw) -> dict:
    """真起编队：建 worktree + 写任务文件与 .cmd（**过 `process_execute` 门**）。"""
    if not plan_id.strip():
        return {"ok": False, "op": "dispatch", "fail_closed": True, "error": "要给 plan_id"}
    d = _plans()
    doc = d.get(plan_id)
    if not doc:
        return {"ok": False, "op": "dispatch", "error": f"没有这个计划：{plan_id}"}
    gate = _gate("process_execute", f"agent_rig dispatch {plan_id}（{len(doc['workers'])} 份）")
    if gate:
        return {"ok": False, "op": "dispatch", "plan_id": plan_id, **gate,
                "note": "**缺票不起编队**：编队会真的建 worktree 并起进程 —— 这是要授权的事"}
    made = []
    for w in doc["workers"]:
        wt = Path(w["worktree"])
        wt.parent.mkdir(parents=True, exist_ok=True)
        if not wt.exists():
            # 程序名字面量 + 参数列表（不拼命令，不让 shell 碰用户文本）
            cp = subprocess.run(["git", "worktree", "add", "--detach", str(wt), "HEAD"],
                                cwd=str(_ROOT), capture_output=True, text=True,
                                encoding="utf-8", errors="replace")
            if cp.returncode != 0:
                return {"ok": False, "op": "dispatch", "error": f"worktree 建失败：{cp.stderr[:200]}",
                        "at": w["index"]}
        Path(w["home"]).mkdir(parents=True, exist_ok=True)
        task_file = Path(w["worktree"]).parent / "TASK.txt"
        task_file.write_text(w["task"], encoding="utf-8")          # 任务只进**文件**，不进命令行
        cmd_file = Path(w["worktree"]).parent / "run.cmd"
        cmd_file.write_text(
            "@echo off\r\n"
            "set HOME=%s\r\nset USERPROFILE=%s\r\n"
            "cd /d %s\r\n"
            "echo [rig] agent=%s task-file=TASK.txt > \"%s\"\r\n"
            "rem 真跑由主人/舰队按 agent 各自的入口起（本件只把作业摆好）\r\n"
            % (w["home"], w["home"], w["worktree"], w["agent"], w["log"]), encoding="utf-8")
        w["ready"] = True
        made.append(w["index"])
    doc["state"] = "ready"
    d[plan_id] = doc
    _save_plans(d)
    started = []
    if start:
        for w in doc["workers"]:
            cmd_file = Path(w["worktree"]).parent / "run.cmd"
            try:
                os.startfile(str(cmd_file))                        # noqa: S606
                started.append(w["index"])
            except OSError as exc:
                started.append({"index": w["index"], "error": f"{type(exc).__name__}"})
        doc["state"] = "started"
        d[plan_id] = doc
        _save_plans(d)
    _log({"event": "dispatch", "plan_id": plan_id, "ready": len(made), "started": len(started) if start else 0})
    return {"ok": True, "op": "dispatch", "plan_id": plan_id, "ready": made,
            "started": started, "state": doc["state"],
            "note": "作业已摆好（每份：worktree + TASK.txt + 隔离 HOME + 独立日志）；"
                    "`start=true` 才起进程"}


def status(plan_id: str = "", **_kw) -> dict:
    d = _plans()
    if plan_id:
        doc = d.get(plan_id)
        if not doc:
            return {"ok": False, "op": "status", "error": f"没有这个计划：{plan_id}"}
        rows = []
        for w in doc["workers"]:
            log = Path(w["log"])
            rows.append({"index": w["index"], "agent": w["agent"], "state": doc["state"],
                         "worktree_exists": Path(w["worktree"]).exists(),
                         "log_exists": log.is_file(),
                         "log_tail": (log.read_text(encoding="utf-8", errors="replace")[-200:]
                                      if log.is_file() else "")})
        return {"ok": True, "op": "status", "plan_id": plan_id, "state": doc["state"], "workers": rows}
    return {"ok": True, "op": "status", "plans": len(d),
            "rows": [{"plan_id": k, "state": v.get("state"), "workers": len(v.get("workers") or []),
                      "at": v.get("at")} for k, v in sorted(d.items())]}


def collect(plan_id: str = "", **_kw) -> dict:
    """收结果：每份的**日志尾 + 产物清单**（exit code 由各 agent 自己的入口写，我们不代写）"""
    d = _plans()
    doc = d.get(plan_id) if plan_id else None
    if not doc:
        return {"ok": False, "op": "collect", "error": f"没有这个计划：{plan_id or '（空）'}"}
    out = []
    for w in doc["workers"]:
        wt = Path(w["worktree"])
        arts = []
        if wt.is_dir():
            cp = subprocess.run(["git", "status", "--porcelain"], cwd=str(wt),
                                capture_output=True, text=True, encoding="utf-8", errors="replace")
            arts = [x for x in (cp.stdout or "").splitlines() if x.strip()][:20]
        out.append({"index": w["index"], "agent": w["agent"], "task": w["task"][:80],
                    "changed": len(arts), "changed_sample": arts[:5]})
    return {"ok": True, "op": "collect", "plan_id": plan_id, "workers": out,
            "note": "改动从每份自己的 worktree 里读（合并由人/管线决定，本件不自动合并）"}


def verify(**_kw) -> dict:
    problems = []
    d = _plans()
    for pid, doc in d.items():
        for w in doc.get("workers") or []:
            if w.get("isolate") and not all(w.get(k) for k in ("worktree", "log", "home", "port_block")):
                problems.append(f"{pid}/w{w.get('index')} 缺隔离件（worktree/log/home/port_block）")
    rows = 0
    if _RIG.is_file():
        rows = sum(1 for ln in _RIG.read_text(encoding="utf-8", errors="replace").splitlines() if ln.strip())
    if not rows:
        problems.append("台账是空的（一次都没编过队）")
    src = Path(__file__).read_text(encoding="utf-8")
    # 自检用**运行时构造的正则**，免得 checker 自己那行被自己命中（血账：本仓扫描器互相自报）
    if re.search(r"shell\s*=\s*True", src):
        problems.append("本模块里出现了把命令交给 shell 的写法 ⇒ 编队不许")
    return {"ok": not problems, "op": "verify", "problems": problems,
            "counts": {"plans": len(d), "workers": sum(len(v.get("workers") or []) for v in d.values()),
                       "ledger": rows},
            "_口径": "每份都有四隔离件 · 台账非空 · 不许把命令交给 shell"}


def where(**_kw) -> dict:
    return {"ok": True, "op": "where", "kind": "agent_rig", "tentacle": "agent_rig",
            "entry": "run_task('agent_rig', {...})",
            "ops": ["agents", "plan", "dispatch", "status", "collect", "verify", "where"],
            "distilled_from": "GitHub 周榜 #02 orca（只取架构：一队 agent 并行 + worktree 隔离）",
            "not_copied": "它的 ADE/多端实现未引用；四隔离口径抄 tentacle_fleet，DAG 编排仍走 dagrun",
            "hard_rules": ["plan 只出计划；dispatch 要 process_execute 门",
                           "任务只进文件、不进命令行（不拼命令）",
                           "不代持账号/不批量注册：跑的是主人已装的 CLI"],
            "port_block": [PORT_BASE, PORT_BASE + PORT_STEP * 8]}


def run_op(op: str = "status", **params) -> dict:
    op = (op or "status").lower()
    for name, fn in (("agents", agents), ("plan", plan), ("dispatch", dispatch),
                     ("status", status), ("collect", collect), ("verify", verify), ("where", where)):
        if op == name:
            return fn(**params)
    return {"ok": False, "fail_closed": True,
            "error": f"未知 op:{op}（agents/plan/dispatch/status/collect/verify/where）"}
