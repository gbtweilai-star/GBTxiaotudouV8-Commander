# -*- coding: utf-8 -*-
"""执行防线判据：四类"自己骗自己"必须能抓到，账本干净时必须判 clean。

跑法：python tests/test_execution_guard.py
"""
from __future__ import annotations

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

FAILED = []


def check(name, cond, detail=""):
    print(("  ok   " if cond else "  FAIL ") + name + ("" if cond else "  " + str(detail)[:200]))
    if not cond:
        FAILED.append(name)


def rows(*specs):
    out = []
    for i, (action, target, detail, result, evidence) in enumerate(specs):
        out.append({"at": "2026-11-01T00:00:%02d" % i, "action": action, "target": target,
                    "detail": detail, "result": result, "evidence": evidence})
    return out


def main() -> int:
    from gbt_allinone.tentacle import execution_guard as EG

    print("[1] 干净账本 → clean")
    good = rows(("edit", "a.py", "改了一行", "ok", "gbt_allinone/a.py"),
                ("scan", "a.py", "扫过", "clean", "state/x.json"))
    r = EG.run("audit", entries=good)
    check("verdict clean", r.get("verdict") == "clean", r.get("violations"))

    print("[2] 写动作无证据 → high")
    bad1 = rows(("edit", "b.py", "改完", "ok", "evidence"))
    r1 = EG.run("audit", entries=bad1)
    kinds = [v["kind"] for v in r1.get("violations") or []]
    check("抓到 claim_without_evidence", "claim_without_evidence" in kinds, kinds)
    check("severity high", r1.get("high", 0) >= 1, r1.get("high"))

    print("[3] 连续 3 写无验证 → mid")
    bad2 = rows(("add", "x", "1", "ok", "state/x"),
                ("edit", "y", "2", "ok", "state/y"),
                ("fix", "z", "3", "ok", "state/z"))
    r2 = EG.run("audit", entries=bad2)
    kinds2 = [v["kind"] for v in r2.get("violations") or []]
    check("抓到 write_streak_without_verify", "write_streak_without_verify" in kinds2, kinds2)

    print("[4] 折叠当完整 → high")
    bad3 = rows(("run", "c.py", "输出 …257ln elided 但已完成", "完成", "state/c.json"))
    r3 = EG.run("audit", entries=bad3)
    kinds3 = [v["kind"] for v in r3.get("violations") or []]
    check("抓到 elided_output_as_complete", "elided_output_as_complete" in kinds3, kinds3)

    print("[5] 同目标连写 → mid")
    bad4 = rows(("edit", "same.py", "a", "ok", "state/a"),
                ("edit", "same.py", "b", "ok", "state/b"))
    r4 = EG.run("audit", entries=bad4)
    kinds4 = [v["kind"] for v in r4.get("violations") or []]
    check("抓到 same_target_rewrite", "same_target_rewrite" in kinds4, kinds4)

    print("[6] status 可读")
    st = EG.run("status")
    check("有 verdict", st.get("verdict") in ("clean", "violations", "high_violations"), st.get("verdict"))

    print()
    if FAILED:
        print("FAILED %d: %s" % (len(FAILED), ", ".join(FAILED)))
        return 1
    print("ALL OK —— 四类劣根性都能抓，干净账本不误报")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
