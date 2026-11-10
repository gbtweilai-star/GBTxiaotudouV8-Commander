# -*- coding: utf-8 -*-
"""执行防线（execution_guard）：蒸馏自 v5 的 execution_guard，**只取"防自己劣根性"的检测器**。

v5 的六个检测器是在"模型手写代码 + 编译器"的形态下防的（折叠读、edit drift、auto-repaired、
compile≠done、verbal evidence、batch edit）。我们的形态是 `run_task` + 编排账本 + 审计，
所以**换成我们账本能证实的四类**：

  ① 完成无证据   —— 写了 add/edit/deploy/完成类动作，evidence 却是空的/占位的
  ② 连续写无验证 —— 连续 ≥3 个写动作之间没有任何 scan/run/verify
  ③ 折叠当完整   —— 结果里带 `…` / `truncated` 却声称"完成/全绿/OK"
  ④ 原地打转     —— 同一 target 连续两次写动作、中间没有验证

op:
    audit {"limit": 200}     # 审账本，返回违规清单
    tail  {"limit": 20}      # 看最近记录
    status                   # 一句话结论
"""
from __future__ import annotations

import json
import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parents[2]
LEDGER = ROOT / "state" / "orchestration-ledger.jsonl"

WRITE_ACTIONS = {"add", "edit", "fix", "deploy", "write", "delete", "run"}
VERIFY_ACTIONS = {"scan", "verify", "test", "check", "audit"}
CLAIM_WORDS = ("完成", "全绿", "通过", "OK", "ok", "✅", "已修复", "已落地")
ELISION_MARKS = ("…", "...", "truncated", "省略", "elided")


def _load(limit: int = 200, entries=None) -> list:
    if entries is not None:
        return list(entries)[-limit:]
    rows = []
    if LEDGER.is_file():
        # 账本是追加日志，历史里可能残留坏字节；严格解码会整本读不了（2026-11-07 实测）。
        # `errors="replace"` 只影响坏行本身：json.loads 失败后照旧 continue，其余行不受影响。
        with LEDGER.open(encoding="utf-8", errors="replace") as fh:
            for line in fh:
                try:
                    rows.append(json.loads(line))
                except Exception:  # noqa: BLE001
                    continue
    return rows[-limit:]


def _placeholder(text) -> bool:
    t = str(text or "").strip()
    return t in ("", "evidence", "detail", "result", "None", "-")


def audit(limit: int = 200, entries=None) -> dict:
    rows = _load(limit, entries)
    violations = []

    def add(kind, severity, idx, fix):
        violations.append({"kind": kind, "severity": severity,
                           "row": idx, "at": rows[idx].get("at"),
                           "action": rows[idx].get("action"),
                           "target": rows[idx].get("target"),
                           "fix": fix})

    # ① 完成无证据
    for i, r in enumerate(rows):
        if str(r.get("action") or "").lower() in WRITE_ACTIONS:
            if _placeholder(r.get("evidence")):
                add("claim_without_evidence", "high", i,
                    "写动作必须带 evidence（文件路径/命令/读数），否则不算完成")

    # ② 连续写无验证
    streak = 0
    for i, r in enumerate(rows):
        a = str(r.get("action") or "").lower()
        if a in VERIFY_ACTIONS:
            streak = 0
        elif a in WRITE_ACTIONS:
            streak += 1
            if streak == 3:      # 只在刚越线时记一次，不逐行刷屏
                add("write_streak_without_verify", "mid", i,
                    "连续 3 个写动作无验证 ⇒ 中间插一次 scan/verify")
    # ③ 折叠当完整
    for i, r in enumerate(rows):
        blob = " ".join(str(r.get(k) or "") for k in ("detail", "result", "evidence"))
        if any(m in blob for m in ELISION_MARKS) and any(w in blob for w in CLAIM_WORDS):
            add("elided_output_as_complete", "high", i,
                "折叠/截断的输出不能当完整证据，需重读/重跑")
    # ④ 原地打转
    for i in range(1, len(rows)):
        a1 = str(rows[i - 1].get("action") or "").lower()
        a2 = str(rows[i].get("action") or "").lower()
        t1, t2 = rows[i - 1].get("target"), rows[i].get("target")
        if (a1 in WRITE_ACTIONS and a2 in WRITE_ACTIONS and t1 == t2):
            prev_same = (i >= 2 and rows[i - 2].get("target") == t1)
            if not prev_same:    # 每一段重复只记一次
                add("same_target_rewrite", "mid", i,
                    "同一目标连续两次写且无验证 ⇒ 先验证再改")

    high = [v for v in violations if v["severity"] == "high"]
    return {"ok": True, "rows": len(rows), "violations": violations,
            "count": len(violations), "high": len(high),
            "verdict": "clean" if not violations else ("violations" if not high else "high_violations"),
            "note": "只审账本可证实的四类；不脑补、不猜动机"}


def tail(limit: int = 20) -> dict:
    rows = _load(limit)
    return {"ok": True, "count": len(rows),
            "rows": [{k: r.get(k) for k in ("at", "action", "target", "result")} for r in rows]}


def status(limit: int = 50) -> dict:
    """默认只看最近 50 条：历史旧账（已发生的）不追溯，只对"当下这轮"负责。"""
    a = audit(limit=int(limit or 50))
    return {"ok": True, "verdict": a["verdict"], "violations": a["count"],
            "high": a["high"], "rows": a["rows"], "window": int(limit or 50),
            "rule": "写动作必须带证据；连续写要插验证；截断不能当完整；同目标别空转",
            "note": "只看最近窗口；历史旧账不追溯"}


def run(op: str = "status", **kw) -> dict:
    op = (op or "status").lower()
    if op == "audit":
        return audit(int(kw.get("limit") or 200), kw.get("entries"))
    if op == "tail":
        return tail(int(kw.get("limit") or 20))
    if op == "status":
        return status()
    return {"ok": False, "error": "execution_guard 不认 op=%s（audit/tail/status）" % op}
