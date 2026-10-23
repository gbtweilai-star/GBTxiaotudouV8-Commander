# -*- coding: utf-8 -*-
"""audit-timeline-check · 动作时间线判据（蒸馏自 ifixai-ai/iFixAi）。
每条 JSONL 记录须含 at/actor/action/source；verdict 只许 ok/gap/overreach/untraced。
判据 fail-closed：T1 必填 · T2 无 source 即红 · T3 取不到读数即红 · T4 verdict 合法值。
用法：--check <file> | --selftest
开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属"""
import argparse, json, pathlib, sys

OK_VERDICT = {"ok", "gap", "overreach", "untraced"}

def judge(rows) -> list:
    if rows is None:
        return [("T3 能取到读数", False, "未读到（空/文件不存在不许当绿）")]
    out = [("T3 能取到读数", True, "%d 条" % len(rows))]
    miss = [i for i, r in enumerate(rows) if not all(r.get(k) for k in ("at", "actor", "action"))]
    out.append(("T1 必填 at/actor/action", not miss, ("缺: 第 %s 条" % miss[:5]) if miss else "齐"))
    nosrc = [i for i, r in enumerate(rows) if not r.get("source")]
    out.append(("T2 每条可指回 source", not nosrc, ("缺: 第 %s 条" % nosrc[:5]) if nosrc else "齐"))
    bad = [(i, r.get("verdict")) for i, r in enumerate(rows) if r.get("verdict") and r["verdict"] not in OK_VERDICT]
    out.append(("T4 verdict 合法", not bad, str(bad[:4]) if bad else "齐"))
    return out

def check(path: str) -> int:
    p = pathlib.Path(path)
    rows = None
    if p.is_file():
        rows = []
        for ln in p.read_text(encoding="utf-8", errors="replace").splitlines():
            ln = ln.strip()
            if ln:
                try: rows.append(json.loads(ln))
                except Exception: rows.append({"_bad": ln[:40]})
    res = judge(rows if rows else None)
    for n, ok, det in res:
        print(("  OK   " if ok else "  FAIL ") + n + " — " + str(det))
    red = [n for n, ok, _ in res if not ok]
    print("判据 PASS %d · FAIL %d" % (len(res) - len(red), len(red)))
    return 1 if red else 0

def selftest() -> int:
    ck = []
    def c(n, ok, d=""):
        ck.append(bool(ok)); print(("OK  " if ok else "BAD ") + n + (" — " + str(d)[:50] if d else ""))
    good = [{"at": "2026-10-15T03:00", "actor": "lead", "action": "cap health", "source": "logbook#522", "verdict": "ok"}]
    c("正例·完整时间线全绿", all(x[1] for x in judge(good)))
    c("负例·取不到读数必须红", not judge(None)[0][1])
    c("负例·缺 source 必须红", not [x for x in judge([{"at":"t","actor":"a","action":"b"}]) if x[0].startswith("T2")][0][1])
    c("负例·verdict 非法必须红", not [x for x in judge([{"at":"t","actor":"a","action":"b","source":"s","verdict":"??"}]) if x[0].startswith("T4")][0][1])
    bad = len([x for x in ck if not x])
    print("\naudit-timeline-check selftest: %d/%d" % (len(ck) - bad, len(ck)))
    return 1 if bad else 0

def main(argv=None) -> int:
    for s in (sys.stdout, sys.stderr):
        try: s.reconfigure(encoding="utf-8", errors="replace")
        except Exception: pass
    ap = argparse.ArgumentParser()
    ap.add_argument("--check"); ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args(argv)
    if a.selftest: return selftest()
    return check(a.check or "outputs/audit/timeline.jsonl")

if __name__ == "__main__":
    sys.exit(main())
