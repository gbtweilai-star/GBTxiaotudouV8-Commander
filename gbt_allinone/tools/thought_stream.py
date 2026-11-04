# -*- coding: utf-8 -*-
# gbt-capability: thought_stream  ⛔ 开发者：自由的风 · GBT小土豆V8 · 永久钢印
"""思考流 / 行动流（thought_stream）—— 我们自己的只读流归一化。

对照上游参考项目的「实时思考流 / 自主行动流」：只取**事件归一与展示判据**，
不搬它的主循环/SQLite。

输入：已有 JSONL 事件行（`state/orchestration-ledger.jsonl` 等），字段可能不统一；
输出：统一五类事件（thought/action/result/guard/system），带时间/actor/title/detail/来源；
纯归一化：不跑模型、不出网、不写盘；坏行跳过并计数，不伪造事件。
"""
from __future__ import annotations

import hashlib
import re

KINDS = ("thought", "action", "result", "guard", "system")
MAX_ENTRIES = 200
MAX_TEXT = 500
_SECRET_RX = re.compile(
    r"(sk-[A-Za-z0-9_-]{10,}|api[_-]?key\s*[:=]\s*\S+|password\s*[:=]\s*\S+|"
    r"token\s*[:=]\s*[A-Za-z0-9._-]{8,})", re.I)


def _clip(value, n=MAX_TEXT):
    s = str(value or "").replace("\n", " ").strip()
    if _SECRET_RX.search(s):
        s = _SECRET_RX.sub("[redacted]", s)
    return s[:n]


def classify(row) -> str:
    if not isinstance(row, dict):
        return "system"
    explicit = str(row.get("kind") or row.get("type") or "").strip().lower()
    if explicit in KINDS:
        return explicit
    actor = str(row.get("actor") or row.get("who") or "").lower()
    action = str(row.get("action") or row.get("step") or row.get("op") or "").lower()
    result = str(row.get("result") or row.get("status") or row.get("outcome") or "").lower()
    if any(x in result for x in ("denied", "blocked", "refused", "error", "fail", "unavailable")):
        return "guard"
    if any(x in action for x in ("think", "plan", "decide", "reason", "thought", "reflect")):
        return "thought"
    if any(x in actor for x in ("brain", "llm", "planner", "mind", "thought")):
        return "thought"
    if any(x in action for x in ("result", "output", "report", "summary")) or "result" in row:
        return "result" if not row.get("target") else "action"
    if action or row.get("target"):
        return "action"
    return "system"


def normalize(rows, limit=80, kinds=None, now=None) -> dict:
    if not isinstance(rows, list):
        raise ValueError("rows 必须是数组")
    try:
        limit = int(limit)
    except (TypeError, ValueError):
        raise ValueError("limit 必须是整数")
    limit = max(1, min(MAX_ENTRIES, limit))
    wanted = None
    if kinds:
        wanted = {str(k).lower() for k in (kinds if isinstance(kinds, (list, tuple, set)) else [kinds])}
        wanted &= set(KINDS)
    entries, seen, skipped = [], set(), 0
    for i, row in enumerate(rows):
        if not isinstance(row, dict):
            skipped += 1
            continue
        at = _clip(row.get("at") or row.get("ts") or row.get("time") or "", 40)
        kind = classify(row)
        if wanted and kind not in wanted:
            continue
        actor = _clip(row.get("actor") or row.get("who") or "", 40) or "?"
        action = _clip(row.get("action") or row.get("step") or row.get("op") or "", 60)
        target = _clip(row.get("target") or row.get("name") or "", 80)
        detail = _clip(row.get("detail") or row.get("summary") or row.get("message") or "", MAX_TEXT)
        result = _clip(row.get("result") or row.get("status") or "", 40)
        title = (target + (" · " + action if action and target else "")) or action or detail[:60]
        key_src = "|".join([at, kind, actor, title, detail, result])
        key = hashlib.sha256(key_src.encode("utf-8")).hexdigest()[:16]
        if key in seen:
            skipped += 1
            continue
        seen.add(key)
        entries.append({"id": "ts-" + key, "at": at, "kind": kind, "actor": actor,
                        "action": action, "target": target, "title": title,
                        "detail": detail, "result": result,
                        "source": str(row.get("source") or row.get("evidence") or "ledger")})
    entries.sort(key=lambda x: (x["at"], x["id"]))
    total = len(entries)
    entries = entries[-limit:]
    counts = {k: 0 for k in KINDS}
    for e in entries:
        counts[e["kind"]] += 1
    return {"ok": True, "entries": entries, "count": len(entries), "total": total,
            "skipped": skipped, "counts": counts, "limit": limit}


def verify() -> dict:
    checks = []

    def ck(name, cond, got=None):
        checks.append({"name": name, "ok": bool(cond), "got": got})

    rows = [
        {"at": "2026-11-02T10:00:00", "actor": "gate", "action": "run", "target": "world_forge",
         "detail": "{'op':'schema'}", "result": "ok"},
        {"at": "2026-11-02T10:00:01", "actor": "brain", "action": "plan", "detail": "先做 P0"},
        {"at": "2026-11-02T10:00:02", "actor": "gate", "action": "run", "target": "browser",
         "result": "denied", "detail": "缺授权"},
        {"at": "2026-11-02T10:00:03", "kind": "result", "detail": "报告已出"},
        "bad-row",
    ]
    r = normalize(rows, limit=80)
    ck("坏行跳过", r["skipped"] == 1 and r["count"] == 4, (r["skipped"], r["count"]))
    kinds = {e["kind"] for e in r["entries"]}
    ck("分类含 action/thought/guard/result", {"action", "thought", "guard", "result"} <= kinds, kinds)
    ck("计数正确", r["counts"]["action"] == 1 and r["counts"]["thought"] == 1
       and r["counts"]["guard"] == 1 and r["counts"]["result"] == 1, r["counts"])
    check_red = normalize([{"kind": "action", "detail": "api_key=sk-" + "A" * 20,
                            "action": "run", "at": "t"}])
    ck("凭据脱敏", "sk-" + "A" * 20 not in str(check_red["entries"]))
    ck("limit 截断", normalize(rows, limit=2)["count"] == 2)
    ck("kinds 过滤", normalize(rows, kinds=["guard"])["count"] == 1)
    ck("空 rows", normalize([], limit=10)["count"] == 0)
    ck("rows 非数组拒", _raises(lambda: normalize("x")))
    ck("limit 非法拒", _raises(lambda: normalize([], limit="x")))
    ck("系统兜底", normalize([{"foo": "bar"}], limit=5)["entries"][0]["kind"] == "system")
    ck("schema 可达", set(run("schema")["kinds"]) == set(KINDS))
    ck("normalize 可跑", run("normalize", rows=rows, limit=3)["ok"])
    ck("未知 op 拒", _raises(lambda: run("teleport")))
    ck("detail 截断", len(normalize([{"kind": "thought", "detail": "字" * 900}],
                                    limit=1)["entries"][0]["detail"]) == MAX_TEXT)
    return {"ok": all(c["ok"] for c in checks), "checks": len(checks),
            "failed": [c for c in checks if not c["ok"]],
            "sha": hashlib.sha256(str(checks).encode()).hexdigest()[:12]}


def _raises(fn) -> bool:
    try:
        fn()
        return False
    except ValueError:
        return True


def run(op="schema", **params):
    op = str(op or "schema").lower()
    if op == "schema":
        return {"ok": True, "kinds": list(KINDS), "max_entries": MAX_ENTRIES,
                "max_text": MAX_TEXT, "note": "只读归一化；坏行跳过；凭据脱敏"}
    if op == "normalize":
        try:
            return normalize(params.get("rows") or [], params.get("limit") or 80,
                             params.get("kinds"))
        except ValueError as e:
            return {"ok": False, "error": "user_error: %s" % e}
    if op == "verify":
        return verify()
    raise ValueError("未知 op: %s（schema/normalize/verify）" % op)
