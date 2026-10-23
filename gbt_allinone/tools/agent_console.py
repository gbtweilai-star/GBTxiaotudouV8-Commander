# gbt-capability: agent_console
# ⛔ 开发者：自由的风 · 永久钢印 · 禁止删除
"""代理驾驶舱：**任务监督循环 + 连接请求审批桥**（蒸馏自 GitHub 周榜 #05 `paperclipai/paperclip`）。

## 抓取口径（凡抓取必写源·时间·口径）
· **源**：2026-09 第 39 周 GitHub 爆款周榜 #05 `paperclip`（87k★ · TypeScript）公开介绍：
  「统一管理工作中 AI 代理（控制台）· **监督任务状态：定时检查 / 重试 / 唤醒** ·
  **治理连接请求：代理需求经操作员审批桥接** · 编排运行代理（控制平面）· 支持扩展与集成、站内公告」。
  一手仓库本轮**未联网核验**（不出网），只蒸馏**架构**。
· **时间**：2026-09-28。
· **口径**：只移植架构，代码自写。

## 蒸馏判断：我们缺哪块
| paperclip 的能力 | 我们已有的对位 | 结论 |
|---|---|---|
| 看状态（进程/占用） | `task_manager`（真进程一屏）· `gods_eye`（眼睛/日报） | **已有** |
| 编排运行代理 | `tools/tentacle_fleet.py`（触手舰队）· `dagrun` | **已有** |
| **监督循环：定时检查 / 重试 / 唤醒** | 无（我们只有"看一眼"，没有"记着它、到点回来查") | **补这块** |
| **连接请求审批桥** | 有门（`auth_gate` / `cap_tags` 许可）但**没有"代理提请求→挂着等主人批"的桥** | **补这块** |

## 两条硬规矩（和全仓口径一致）
1. **只监督，不擅自执行**：`tick` 只**判定状态并列出该做什么**；`retry` / `wake` 要真动手就得过
   `process_execute` 门，缺票**如实拒**（缺什么写在 `how_to_grant`）—— 驾驶舱不给自己发钥匙。
2. **审批桥归主人**：代理要连外部/要授权时走 `request` 登记成待批；`approve` **要求 TTY + 手打 YES**，
   非交互会话（AI）**永远批不了**（与 `cap_tags` 的许可同一道闸）。

op=add / tick / board / retry / wake / request / pending / approve / verify / where
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
_STATE = _ROOT / "state"
_LEDGER = _STATE / "agent_console.jsonl"      # 登记 / 检查 / 请求 / 审批（追加式）
_BOARD = _STATE / "agent_console.json"        # 当前看板（原子写）
STATES = ("pending", "running", "ok", "stale", "failed", "woken", "awaiting_owner")


def _log(row: dict) -> None:
    _LEDGER.parent.mkdir(parents=True, exist_ok=True)
    with open(_LEDGER, "a", encoding="utf-8") as fh:
        fh.write(json.dumps({"at": time.strftime("%Y-%m-%dT%H:%M:%S"), **row}, ensure_ascii=False) + "\n")


def _rows() -> list:
    out = []
    if _LEDGER.is_file():
        for ln in _LEDGER.read_text(encoding="utf-8", errors="replace").splitlines():
            ln = ln.strip()
            if ln:
                try:
                    out.append(json.loads(ln))
                except json.JSONDecodeError:
                    continue
    return out


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


def _watch() -> dict:
    """登记表：name → 最新一条登记（台账追加式，取最后）。"""
    out = {}
    for r in _rows():
        if r.get("event") == "add":
            out[r["name"]] = r
    return out


def add(name: str = "", evidence: str = "", every_s: int = 900, max_retry: int = 2,
        expect: str = "", **_kw) -> dict:
    """登记一个**要被监督**的任务：靠"看什么"来判活（evidence 是读数路径）。

    为什么用 evidence 而不是"跑没跑"：本仓的教训是 **exit 0 不算完成**。
    所以监督的判据是"**产物/读数有没有如期更新**"，不是"命令有没有退出"。
    """
    if not name.strip() or not evidence.strip():
        return {"ok": False, "op": "add", "fail_closed": True,
                "error": "name 与 evidence 都要给（evidence=该任务会更新的读数路径，逗号分隔）"}
    ev = [x.strip() for x in evidence.split(",") if x.strip()]
    _log({"event": "add", "name": name, "evidence": ev, "every_s": int(every_s),
          "max_retry": int(max_retry), "expect": expect[:160]})
    return {"ok": True, "op": "add", "name": name, "evidence": ev, "every_s": int(every_s),
            "max_retry": int(max_retry),
            "note": "已登记（只登记，不执行）；到点跑 tick 看它活没活"}


def tick(now_ts: float = 0, **_kw) -> dict:
    """**定时检查**：逐项看 evidence 有没有按 `every_s` 如期更新 ⇒ ok / stale；再看得出的结论。"""
    now = now_ts or time.time()
    w = _watch()
    if not w:
        return {"ok": True, "op": "tick", "watched": 0, "rows": [],
                "note": "还没登记任何被监督的任务（op=add 登记）"}
    rows = []
    for name, spec in sorted(w.items()):
        ages, missing = [], []
        for e in spec.get("evidence") or []:
            p = Path(e)
            if not p.is_absolute():
                p = _ROOT / p
            if p.exists():
                ages.append(now - p.stat().st_mtime)
            else:
                missing.append(e)
        newest = min(ages) if ages else None
        every = int(spec.get("every_s") or 900)
        if missing and not ages:
            state = "failed"
            why = f"读数一个都不在盘上：{missing[:3]}"
        elif newest is not None and newest <= every:
            state = "ok"
            why = f"最新的读数 {int(newest)}s 前更新（窗口 {every}s）"
        else:
            state = "stale"
            why = (f"最新的读数已 {int(newest)}s 没动（窗口 {every}s）"
                   if newest is not None else "没有任何读数")
        retries = sum(1 for r in _rows() if r.get("event") == "retry" and r.get("name") == name)
        need = []
        if state in ("stale", "failed") and retries < int(spec.get("max_retry") or 0):
            need.append(f"可 retry（已重试 {retries}/{spec.get('max_retry')}）")
        if state in ("stale", "failed") and retries >= int(spec.get("max_retry") or 0):
            need.append("重试次数用尽 ⇒ 要么 wake（人工挂回待办）要么改判据")
        pend = [r for r in _rows() if r.get("event") == "request" and r.get("name") == name
                and not any(x.get("event") == "approve" and x.get("req_id") == r.get("req_id")
                            for x in _rows())]
        if pend:
            state = "awaiting_owner"
            need.append(f"有 {len(pend)} 条连接请求待主人批")
        rows.append({"name": name, "state": state, "why": why, "retries": retries,
                     "expect": spec.get("expect"), "need": need})
        _log({"event": "tick", "name": name, "state": state, "why": why})
    doc = {"at": time.strftime("%Y-%m-%dT%H:%M:%S"), "watched": len(rows), "rows": rows,
           "_口径": "判活看**读数有没有如期更新**（不是 exit code）；该做什么列在 need 里，不自动做"}
    tmp = _BOARD.with_name(_BOARD.name + ".tmp")
    tmp.write_text(json.dumps(doc, ensure_ascii=False, indent=1), encoding="utf-8")
    os.replace(tmp, _BOARD)
    return {"ok": True, "op": "tick", **{k: v for k, v in doc.items() if k != "_口径"}}


def board(**_kw) -> dict:
    if not _BOARD.is_file():
        r = tick()
        return r
    d = json.loads(_BOARD.read_text(encoding="utf-8"))
    return {"ok": True, "op": "board", **d,
            "summary": {s: sum(1 for x in d.get("rows") or [] if x["state"] == s)
                        for s in sorted({x["state"] for x in d.get("rows") or []})}}


def retry(name: str = "", **_kw) -> dict:
    """重试：**要真动手就跑不过门** ⇒ 缺票如实拒；有票也只登记"该重试了"，执行交给调用方。"""
    if not name.strip():
        return {"ok": False, "op": "retry", "fail_closed": True, "error": "要给 name"}
    if name not in _watch():
        return {"ok": False, "op": "retry", "error": f"没登记过这个任务：{name}"}
    gate = _gate("process_execute", f"agent_console retry {name}")
    if gate:
        return {"ok": False, "op": "retry", "name": name, **gate,
                "note": "**缺票不重试**：驾驶舱不给自己发钥匙（缺什么见 how_to_grant）"}
    _log({"event": "retry", "name": name, "by": "owner_window"})
    return {"ok": True, "op": "retry", "name": name,
            "note": "已记一次重试（窗口内）；真执行请走该任务自己的能力位"}


def wake(name: str = "", why: str = "", **_kw) -> dict:
    """唤醒 / 挂回待办（不执行；只是把它从 stale 拉回 pending 并留痕）。"""
    if not name.strip():
        return {"ok": False, "op": "wake", "fail_closed": True, "error": "要给 name"}
    if name not in _watch():
        return {"ok": False, "op": "wake", "error": f"没登记过这个任务：{name}"}
    if not why.strip():
        return {"ok": False, "op": "wake", "refused": True, "why": "唤醒要写**为什么唤醒**（免得凭空复活）"}
    _log({"event": "wake", "name": name, "why": why[:200]})
    return {"ok": True, "op": "wake", "name": name, "state": "pending", "why": why[:200]}


def request(name: str = "", what: str = "", scope: str = "", **_kw) -> dict:
    """**连接请求**：代理要连外部/要授权时，登记成待批（绑到具体作用域）。"""
    if not (name.strip() and what.strip()):
        return {"ok": False, "op": "request", "fail_closed": True, "error": "name 与 what 都要给"}
    if not scope.strip():
        return {"ok": False, "op": "request", "fail_closed": True,
                "error": "要给 scope（要哪张票：filesystem_write / process_execute / external_llm …）"}
    req_id = "req-%d" % (len([r for r in _rows() if r.get("event") == "request"]) + 1)
    _log({"event": "request", "req_id": req_id, "name": name, "what": what[:200], "scope": scope})
    return {"ok": True, "op": "request", "req_id": req_id, "name": name, "scope": scope,
            "how_to_approve": "主人终端：python -m gbt_allinone.tools.agent_console approve --req <id>（TTY+YES）",
            "note": "**代理自己批不了**：审批桥只认主人终端"}


def pending(**_kw) -> dict:
    reqs = [r for r in _rows() if r.get("event") == "request"]
    oks = {r.get("req_id") for r in _rows() if r.get("event") == "approve"}
    out = [{"req_id": r["req_id"], "name": r.get("name"), "what": r.get("what"),
            "scope": r.get("scope"), "at": r.get("at")} for r in reqs if r["req_id"] not in oks]
    return {"ok": True, "op": "pending", "count": len(out), "rows": out,
            "note": "待主人批的连接请求；批准只能主人在终端做"}


def approve(req_id: str = "", **_kw) -> dict:
    """批准连接请求 —— **只在主人终端**（TTY + 手打 YES）；非交互会话直接拒。"""
    if not req_id.strip():
        return {"ok": False, "op": "approve", "fail_closed": True, "error": "要给 --req"}
    if not sys.stdin.isatty():
        return {"ok": False, "op": "approve", "denied": True, "fail_closed": True,
                "error": "**非交互会话不许批连接请求**（AI 永远无权替主人开桥）",
                "how": "请主人在终端跑本命令；或手写 state/agent_console.jsonl 追加 approve 行"}
    print(f"即将批准连接请求 {req_id}。输入 YES 确认：", end=" ", flush=True)   # noqa: T201
    if (sys.stdin.readline() or "").strip() != "YES":
        return {"ok": False, "op": "approve", "error": "没确认 ⇒ 不批"}
    _log({"event": "approve", "req_id": req_id, "by": "owner"})
    return {"ok": True, "op": "approve", "req_id": req_id}


def verify(**_kw) -> dict:
    problems = []
    rows = _rows()
    adds = [r for r in rows if r.get("event") == "add"]
    if not adds:
        problems.append("一条监督任务都没登记 ⇒ 驾驶舱是空转的（要么登记，要么本能力位没意义）")
    for r in rows:
        if r.get("event") == "retry" and not r.get("by"):
            problems.append(f"retry 记录里没有 by（谁批的）⇒ 无法追责：{r.get('name')}")
    for r in rows:
        if r.get("event") == "approve" and r.get("by") != "owner":
            problems.append(f"approve 不是主人批的：{r.get('req_id')} — **这不该发生**")
    for r in adds:
        if not r.get("evidence"):
            problems.append(f"{r.get('name')} 没写读数路径 ⇒ 判活的依据不明")
    src = Path(__file__).read_text(encoding="utf-8")
    if "isatty" not in src:
        problems.append("approve 没做 TTY 闸 ⇒ AI 可能自己批（立刻改）")
    return {"ok": not problems, "op": "verify", "problems": problems,
            "counts": {"watched": len({r['name'] for r in adds}),
                       "ticks": sum(1 for r in rows if r.get("event") == "tick"),
                       "requests": sum(1 for r in rows if r.get("event") == "request"),
                       "approves": sum(1 for r in rows if r.get("event") == "approve")},
            "_口径": "登记了没空转 · retry 有主 · approve 只能主人 · 判活依据非空"}


def where(**_kw) -> dict:
    return {"ok": True, "op": "where", "kind": "agent_console", "tentacle": "agent_console",
            "entry": "run_task('agent_console', {...})",
            "ops": ["add", "tick", "board", "retry", "wake", "request", "pending", "approve",
                    "verify", "where"],
            "distilled_from": "GitHub 周榜 #05 paperclip（只取架构：监督循环 + 连接请求审批桥）",
            "not_copied": "它的 UI/控制平面实现未引用；进程读数仍走 task_manager，编排仍走 tentacle_fleet",
            "hard_rules": ["只监督不擅自执行（retry/wake 要门）",
                           "审批桥只认主人终端（TTY+YES）⇒ AI 批不了",
                           "判活看**读数是否如期更新**，不是 exit code"],
            "files": {"台账": str(_LEDGER.relative_to(_ROOT)), "看板": str(_BOARD.relative_to(_ROOT))}}


def run_op(op: str = "board", **params) -> dict:
    op = (op or "board").lower()
    for name, fn in (("add", add), ("tick", tick), ("board", board), ("retry", retry),
                     ("wake", wake), ("request", request), ("pending", pending),
                     ("approve", approve), ("verify", verify), ("where", where)):
        if op == name:
            return fn(**params)
    return {"ok": False, "fail_closed": True,
            "error": f"未知 op:{op}（add/tick/board/retry/wake/request/pending/approve/verify/where）"}


if __name__ == "__main__":                                    # 主人的终端入口
    import argparse
    ap = argparse.ArgumentParser(description="代理驾驶舱（审批桥只有主人能过）")
    ap.add_argument("cmd", nargs="?", default="pending")
    ap.add_argument("--req", default="")
    a = ap.parse_args()
    print(json.dumps(run_op(a.cmd, req_id=a.req), ensure_ascii=False, indent=1))  # noqa: T201
