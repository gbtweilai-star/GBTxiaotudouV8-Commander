#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""omni_audit —— 万能插「所有能力」的可复跑自审（2026-10-30）

主人要一句确认：**万能插的所有能力是不是都跑通并固化了**。
这种问题不能靠嘴答，得有一条命令能重复给出同样的账。

它跑两层：
  ① 只读 op：status / sockets / energy / selftest / discover
  ② 六类插座 plug+run：process · file · api · ai · web · app

判定分四态（不许含糊）：
  ok           真回包且业务成功
  needs_ticket 门在工作（要人发票）——**不是坏**，是设计
  platform_na  平台没有这个能力（iOS 无桌面/窗口）
  fail         其它失败

用法：
    python3 tools/omni_audit.py           # 人读
    python3 tools/omni_audit.py --json    # 机读
    python3 tools/omni_audit.py --ticket  # 以「有票」身份复跑（GBT_AUTONOMOUS=1）
"""
from __future__ import annotations

import argparse
import json
import os
import pathlib
import sys
import time

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

PLATFORM_HINTS = ("desktop", "窗口", "眼+手", "0 个窗口")
TICKET_HINTS = ("需要人工授权", "human authorization", "requires human")


def _call(pl: dict, tmo=60):
    from gbt_allinone.api import run_task
    t0 = time.time()
    try:
        r = run_task("omni_plug", pl)
        res = (r.get("gbt_result") or r).get("result") or {}
        return r.get("status"), res, round((time.time() - t0) * 1000)
    except Exception as exc:                                      # noqa: BLE001
        return "EXC", {"err": "%s: %s" % (type(exc).__name__, str(exc)[:60])}, \
               round((time.time() - t0) * 1000)


def _verdict(status: str, res: dict) -> tuple:
    why = str(res.get("reason") or res.get("error") or res.get("err") or "")
    if status == "denied" or any(k in why for k in TICKET_HINTS):
        return "needs_ticket", why
    if any(k in why for k in PLATFORM_HINTS):
        return "platform_na", why
    if res.get("ok") is True:
        return "ok", ("http=%s" % res.get("http")) if res.get("http") else ""
    if res.get("ok") is False:
        return "fail", why
    return ("ok" if status == "ok" else "fail"), why


SOCKETS = [
    ("process", "python3 -c print(6*7)", "run"),
    ("file", "README.md", "read"),
    ("api", "https://example.com", "get"),
    ("ai", "https://api.deepseek.com/v1", "chat"),
    ("web", "https://example.com", "open"),
    ("app", "list_windows", "see"),
]
OPS = ("status", "sockets", "energy", "selftest", "discover")


def run_audit() -> dict:
    rows = []

    for op in OPS:
        st, res, ms = _call({"op": op})
        note = ""
        if op == "discover":
            s = res.get("接口插座") or {}
            note = "候选 %s / 活 %s" % (s.get("candidates"), s.get("alive"))
            ok = bool(s.get("candidates"))
            rows.append({"what": "op:" + op, "verdict": "ok" if ok else "fail",
                         "ms": ms, "note": note})
            continue
        if op == "selftest":
            ok = res.get("ok") is True
        elif op == "status":
            ok = bool(res.get("插座类型"))
            note = ",".join(res.get("插座类型") or [])
        else:
            ok = res.get("ok") is not False
        rows.append({"what": "op:" + op, "verdict": "ok" if ok else "fail", "ms": ms, "note": note})

    for kind, tgt, do in SOCKETS:
        pl = {"op": "run", "socket": kind, "target": tgt, "do": do}
        if kind == "ai":
            pl["args"] = {"model": "deepseek-flash", "prompt": "Say OK only."}
        st, res, ms = _call(pl)
        v, why = _verdict(st, res)
        rows.append({"what": "socket:" + kind + "/" + do, "verdict": v, "ms": ms,
                     "note": (why or "")[:80]})

    tally = {}
    for r in rows:
        tally[r["verdict"]] = tally.get(r["verdict"], 0) + 1
    return {"at": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "ticket_mode": os.environ.get("GBT_AUTONOMOUS") in ("1", "true", "yes", "on"),
            "rows": rows, "tally": tally,
            "usable": tally.get("ok", 0),
            "blocked_by_ticket": tally.get("needs_ticket", 0),
            "platform_na": tally.get("platform_na", 0),
            "failed": tally.get("fail", 0)}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--ticket", action="store_true", help="以有票身份复跑（GBT_AUTONOMOUS=1）")
    a = ap.parse_args(argv)
    if a.ticket:
        os.environ["GBT_AUTONOMOUS"] = "1"

    d = run_audit()
    if a.json:
        print(json.dumps(d, ensure_ascii=False, indent=1))
        return 0 if d["failed"] == 0 else 1

    print("  万能插自审 · %s · 有票=%s" % (d["at"], d["ticket_mode"]))
    for r in d["rows"]:
        mark = {"ok": "✅", "needs_ticket": "🔑", "platform_na": "⬜", "fail": "🔴"}[r["verdict"]]
        print("   %s %-22s %6sms  %-12s %s" % (mark, r["what"], r["ms"], r["verdict"], r["note"]))
    print("  ── 汇总 ──")
    print("   可用 %d · 需票 %d · 平台不支持 %d · 失败 %d"
          % (d["usable"], d["blocked_by_ticket"], d["platform_na"], d["failed"]))
    return 0 if d["failed"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
