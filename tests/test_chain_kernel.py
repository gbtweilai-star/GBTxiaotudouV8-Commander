# -*- coding: utf-8 -*-
"""唯一执行路径判据：七步不可跳步、每步有证据、失败会 stop。

跑法：python tests/test_chain_kernel.py
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


def main() -> int:
    from gbt_allinone.tentacle import chain_kernel as CK

    print("[1] status：七步（-1..5）")
    st = CK.run_op("status")
    steps = [s["step"] for s in st.get("steps") or []]
    check("step 列表正确", steps == [-1, 0, 1, 2, 3, 4, 5], steps)
    check("每步都有准入/准出", all(s.get("admission") and s.get("exit") for s in st["steps"]))

    print("[2] gate：单步条件可查")
    g = CK.run_op("gate", step="1")
    check("gate 1 有准出", bool((g.get("gate") or {}).get("exit")), g)

    print("[3] 空目标 ⇒ 停在理解步")
    bad = CK.run_op("run", goal="")
    check("返回 stopped_at=0", bad.get("stopped_at") == 0, bad.get("stopped_at"))
    check("verdict=chain_stopped", bad.get("verdict") == "chain_stopped", bad.get("verdict"))

    print("[4] 正常目标 ⇒ 七步全过（只读模式）")
    r = CK.run_op("run", goal="给框架加一个只读自检入口", approve=False)
    check("chain_ok", r.get("verdict") == "chain_ok", r.get("reason"))
    check("步数=7", len(r.get("steps") or []) == 7, len(r.get("steps") or []))
    check("每步有证据", all(s.get("evidence") for s in r.get("steps") or []))
    check("第2步是只读模式", ((r["steps"][3].get("evidence")) or {}).get("mode") == "read_only",
          r["steps"][3].get("evidence"))

    print()
    if FAILED:
        print("FAILED %d: %s" % (len(FAILED), ", ".join(FAILED)))
        return 1
    print("ALL OK —— 七步不可跳步、每步有证据、失败会 stop")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
