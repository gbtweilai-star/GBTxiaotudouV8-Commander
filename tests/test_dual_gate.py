# -*- coding: utf-8 -*-
"""双脑确认判据：两脑都点头才 approved；任一否决 → rejected。

跑法：python tests/test_dual_gate.py
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
    import gbt_allinone as gbt

    def api(op, **kw):
        return gbt.run_task("dual_gate", {"op": op, **kw}, probe=True)["gbt_result"]["result"]

    print("[1] status：规则清单可读")
    st = api("status")
    check("有 amount_limit", isinstance(st.get("amount_limit"), (int, float)), st)

    print("[2] 正常只读动作 → 两脑通过")
    r = api("check", kind="selfscan", payload={})
    check("both_approved", r.get("both_approved") is True, r)
    check("verdict approved", r.get("verdict") == "approved", r.get("verdict"))

    print("[3] 转账缺收款人 → 推理脑否决")
    r2 = api("check", kind="transfer", payload={"amount": 100})
    check("被否决", r2.get("both_approved") is False, r2)
    notes = " ".join((r2.get("reasoning") or {}).get("notes") or [])
    check("原因提到收款人", "收款人" in notes, notes)

    print("[4] 转账超上限 → 推理脑否决")
    r3 = api("check", kind="transfer", payload={"amount": 10 ** 9, "to": "x"})
    check("被否决", r3.get("both_approved") is False, r3)
    check("提到超上限", "超上限" in " ".join((r3.get("reasoning") or {}).get("notes") or []), r3)

    print("[5] 不存在的能力位 → 编程脑否决")
    r4 = api("check", kind="no_such_cap_xyz", payload={})
    check("被否决", r4.get("both_approved") is False, r4)
    check("提到存在", "不存在" in " ".join((r4.get("programming") or {}).get("notes") or []), r4)

    print("[6] 落点不存在 → 编程脑否决")
    r5 = api("check", kind="selfscan", payload={"path": "no/such/file_xyz.txt"})
    check("被否决", r5.get("both_approved") is False, r5)
    check("提到落点", "落点" in " ".join((r5.get("programming") or {}).get("notes") or []), r5)

    print()
    if FAILED:
        print("FAILED %d: %s" % (len(FAILED), ", ".join(FAILED)))
        return 1
    print("ALL OK —— 双脑各出一份裁决，任一否决即 rejected")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
