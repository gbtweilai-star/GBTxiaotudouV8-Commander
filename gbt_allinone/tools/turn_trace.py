# -*- coding: utf-8 -*-
# gbt-capability: turn_trace  ⛔ 开发者：自由的风 · GBT小土豆V8 · 永久钢印
"""轮次追踪（turn_trace / Turn Trace）—— 把已有执行账归并成“轮”。

对照上游参考项目的 Turn Trace：只蒸**归并/证据判据**，不搬它的主循环。
输入：已有 JSONL 事件行（编排账/action_gate 等），字段可能不统一；
规则：按 session 分组，**同 session 内间隔 > gap_s 就切新轮**；每轮列步骤/结果/证据；
纯归一化：不生成“用户输入”字段（没有就 null）、不伪造证据、不调模型/不写盘。
"""
from __future__ import annotations

import hashlib
import time
from datetime import datetime

DEFAULT_GAP = 45
MIN_GAP, MAX_GAP = 5, 3600
MAX_TRACES = 200
MAX_STEPS = 100
MAX_DETAIL = 400
FAIL_MARKS = ("error", "fail", "denied", "blocked", "refused", "unavailable", "timeout")


class TraceError(ValueError):
    pass


def _at(value) -> float:
    s = str(value or "").strip()
    if not s:
        return 0.0
    for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M", "%Y-%m-%d %H:%M:%S",
                "%Y-%m-%d %H:%M"):
        try:
            return time.mktime(time.strptime(s, fmt))
        except ValueError:
            continue
    try:
        return float(s)
    except (TypeError, ValueError):
        return 0.0


def _iso(ts: float) -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(ts)) if ts else ""


def normalize(rows, gap_s=DEFAULT_GAP, limit=50) -> dict:
    if not isinstance(rows, list):
        raise TraceError("rows 必须是数组")
    try:
        gap_s = int(gap_s)
        limit = int(limit)
    except (TypeError, ValueError):
        raise TraceError("gap_s/limit 必须是整数")
    if gap_s < MIN_GAP or gap_s > MAX_GAP:
        raise TraceError("gap_s 范围 %d..%d" % (MIN_GAP, MAX_GAP))
    limit = max(1, min(MAX_TRACES, limit))
    steps = []
    for r in rows[:2000]:
        if not isinstance(r, dict):
            continue
        ts = _at(r.get("at") or r.get("ts") or r.get("time"))
        if not ts:
            continue
        detail = str(r.get("detail") or r.get("summary") or r.get("message") or "")
        result = str(r.get("result") or r.get("status") or "").lower()
        steps.append({"at_ts": ts, "at": _iso(ts),
                      "session": str(r.get("session") or r.get("sid") or "")[:40],
                      "source": str(r.get("source") or ("action_gate" if r.get("gate_id") else "orchestration-ledger"))[:40],
                      "actor": str(r.get("actor") or r.get("who") or "?")[:40],
                      "action": str(r.get("action") or r.get("step") or r.get("op") or "")[:60],
                      "target": str(r.get("target") or r.get("name") or "")[:100],
                      "detail": detail[:MAX_DETAIL],
                      "result": result[:40],
                      "evidence": str(r.get("evidence") or r.get("gate_id") or "")[:80],
                      "ok": not any(x in result for x in FAIL_MARKS),
                      "input": (str(r.get("input") or r.get("prompt"))[:MAX_DETAIL]
                                if (r.get("input") or r.get("prompt")) else None)})
    steps.sort(key=lambda s: (s["at_ts"], s["at"]))
    traces = []
    for s in steps:
        if (not traces or traces[-1]["session"] != s["session"]
                or s["at_ts"] - traces[-1]["_last_ts"] > gap_s):
            traces.append({"id": "", "session": s["session"], "start": s["at"],
                           "_start_ts": s["at_ts"], "_last_ts": s["at_ts"],
                           "steps": [], "input": s["input"]})
        tr = traces[-1]
        tr["steps"].append(s)
        tr["_last_ts"] = s["at_ts"]
        if tr["input"] is None and s["input"]:
            tr["input"] = s["input"]
        tr["end"] = s["at"]
    for tr in traces:
        if len(tr["steps"]) > MAX_STEPS:
            tr["steps"] = tr["steps"][:MAX_STEPS]
        fail = sum(1 for s in tr["steps"] if not s["ok"])
        evidence = sum(1 for s in tr["steps"] if s["evidence"])
        tr["duration_s"] = round(max(0.0, tr["_last_ts"] - tr["_start_ts"]), 1)
        tr["count"] = len(tr["steps"])
        tr["fail"] = fail
        tr["evidence_count"] = evidence
        tr["status"] = "review" if fail else "ok"
        tr["id"] = "tr-" + hashlib.sha1(
            (tr["session"] + "|" + tr["start"] + "|" + tr["steps"][0]["at"]).encode()).hexdigest()[:12]
        for k in ("_start_ts", "_last_ts"):
            tr.pop(k, None)
        for s in tr["steps"]:
            s.pop("at_ts", None)
    traces.sort(key=lambda t: (t["start"], t["id"]), reverse=True)
    total = len(traces)
    traces = traces[:limit]
    return {"ok": True, "traces": traces, "count": len(traces), "total": total,
            "gap_s": gap_s, "limit": limit,
            "source": "orchestration-ledger/action_gate（只读归并）"}


def verify() -> dict:
    checks = []

    def ck(name, cond, got=None):
        checks.append({"name": name, "ok": bool(cond), "got": got})

    rows = [
        {"at": "2026-11-03T10:00:00", "session": "s1", "actor": "gate", "action": "run",
         "target": "a", "result": "ok", "detail": "one"},
        {"at": "2026-11-03T10:00:10", "session": "s1", "actor": "gate", "action": "run",
         "target": "b", "result": "denied", "detail": "two", "evidence": "gate-1"},
        {"at": "2026-11-03T10:02:00", "session": "s1", "actor": "gate", "action": "run",
         "target": "c", "result": "ok", "detail": "three"},
        {"at": "2026-11-03T10:02:10", "session": "s2", "actor": "brain", "action": "plan",
         "detail": "other session"},
    ]
    r = normalize(rows, gap_s=45)
    ck("按间隔切轮", r["count"] == 3, r["count"])
    ck("同 session 合并", any(t["session"] == "s1" and t["count"] == 2 for t in r["traces"]))
    ck("失败标 review", any(t["status"] == "review" for t in r["traces"]))
    ck("证据计数", any(t["evidence_count"] == 1 for t in r["traces"]))
    ck("时间倒序", r["traces"][0]["start"] >= r["traces"][-1]["start"])
    ck("id 形态", all(t["id"].startswith("tr-") for t in r["traces"]))
    ck("无输入不伪造", all(t["input"] is None for t in r["traces"]))
    ck("limit 截断", normalize(rows, gap_s=10, limit=1)["count"] == 1)
    ck("坏行跳过", normalize(["x", {"at": "bad"}], gap_s=45)["count"] == 0)
    ck("gap 下限拒", _raises(lambda: normalize(rows, gap_s=1)))
    ck("gap 非数字拒", _raises(lambda: normalize(rows, gap_s="x")))
    ck("rows 非数组拒", _raises(lambda: normalize("x")))
    ck("空 rows", normalize([])["count"] == 0)
    ck("session 字段", normalize(rows)[ "traces"][0]["session"] in ("s1", "s2"))
    ck("schema 可达", "gap_default" in run("schema") and "max_traces" in run("schema"))
    ck("未知 op 拒", _raises(lambda: run("teleport")))
    return {"ok": all(c["ok"] for c in checks), "checks": len(checks),
            "failed": [c for c in checks if not c["ok"]],
            "sha": hashlib.sha256(str(checks).encode()).hexdigest()[:12]}


def _raises(fn) -> bool:
    try:
        fn()
        return False
    except (TraceError, ValueError):
        return True


def run(op="schema", **params):
    op = str(op or "schema").lower()
    if op == "schema":
        return {"ok": True, "gap_default": DEFAULT_GAP, "gap_range": [MIN_GAP, MAX_GAP],
                "max_traces": MAX_TRACES, "max_steps": MAX_STEPS,
                "note": "按 session+间隔归并；不伪造输入/证据；只读"}
    if op == "normalize":
        try:
            return normalize(params.get("rows") or [], params.get("gap_s") or DEFAULT_GAP,
                             params.get("limit") or 50)
        except TraceError as e:
            return {"ok": False, "error": "user_error: %s" % e}
    if op == "verify":
        return verify()
    raise ValueError("未知 op: %s（schema/normalize/verify）" % op)
