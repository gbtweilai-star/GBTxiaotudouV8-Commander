# -*- coding: utf-8 -*-
"""cli-surface-check · 命令面登记表判据（蒸馏自 HKUDS/CLI-Anything）。
登记表：state/cli-surfaces.json —— 列表，每项 {name, entry, verbs:[], evidence, status}。
status 只许 cli / api-wrapped / gui-only。
判据（fail-closed）：C1 表可读（缺则红）· C2 必填字段 · C3 必须有 evidence · C4 status 合法值。
用法：py -3.14 tools/codex-scripts/cli-surface-check.py [--check|--selftest]
开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属
"""
from __future__ import annotations
import argparse, json, pathlib, sys, tempfile

ROOT = pathlib.Path(__file__).resolve().parents[2]
TABLE = ROOT / "state" / "cli-surfaces.json"
OK_STATUS = {"cli", "api-wrapped", "gui-only"}

def judge(rows) -> list:
    out = []
    if rows is None:
        return [("C1 登记表可读", False, "未读到 " + str(TABLE))]
    if not isinstance(rows, list):
        return [("C1 登记表是列表", False, "类型=%s" % type(rows).__name__)]
    out.append(("C1 登记表可读", True, "%d 条" % len(rows)))
    miss = [str(r.get("name") or "?") for r in rows
            if not r.get("name") or not r.get("entry") or not r.get("verbs")]
    out.append(("C2 必填字段(name/entry/verbs)", not miss, "缺: " + str(miss[:6]) if miss else "齐"))
    noev = [str(r.get("name") or "?") for r in rows if not r.get("evidence")]
    out.append(("C3 每条有 evidence", not noev, "缺: " + str(noev[:6]) if noev else "齐"))
    bad = [(str(r.get("name") or "?"), r.get("status")) for r in rows if r.get("status") not in OK_STATUS]
    out.append(("C4 status 合法", not bad, str(bad[:6]) if bad else "齐"))
    return out

def check() -> int:
    rows = None
    if TABLE.is_file():
        try: rows = json.loads(TABLE.read_text(encoding="utf-8"))
        except Exception as e: print("  C1 红：表坏了 " + str(e)[:60])
    res = judge(rows)
    for n, ok, det in res:
        print(("  OK   " if ok else "  FAIL ") + n + " — " + str(det))
    red = [n for n, ok, _ in res if not ok]
    print("判据 PASS %d · FAIL %d" % (len(res) - len(red), len(red)))
    return 1 if red else 0

def selftest() -> int:
    ck = []
    def c(n, ok, d=""):
        ck.append(bool(ok)); print(("OK  " if ok else "BAD ") + n + (" — " + str(d)[:50] if d else ""))
    good = [{"name": "git", "entry": "git", "verbs": ["status"], "evidence": "git status", "status": "cli"}]
    c("正例·合法表全绿", all(x[1] for x in judge(good)))
    c("负例·缺表必须红", not judge(None)[0][1])
    c("负例·缺 evidence 必须红", not [x for x in judge([{"name":"a","entry":"a","verbs":["v"],"status":"cli"}]) if x[0].startswith("C3")][0][1])
    c("负例·status 非法必须红", not [x for x in judge([{"name":"a","entry":"a","verbs":["v"],"evidence":"e","status":"??"}]) if x[0].startswith("C4")][0][1])
    bad = len([x for x in ck if not x])
    print("\ncli-surface-check selftest: %d/%d" % (len(ck) - bad, len(ck)))
    return 1 if bad else 0

def main(argv=None) -> int:
    for s in (sys.stdout, sys.stderr):
        try: s.reconfigure(encoding="utf-8", errors="replace")
        except Exception: pass
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true"); ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args(argv)
    return selftest() if a.selftest else check()

if __name__ == "__main__":
    sys.exit(main())
