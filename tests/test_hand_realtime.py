# -*- coding: utf-8 -*-
"""hand_realtime 判据：同拍 loopback 真跑，不要求硬件。"""
from __future__ import annotations

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

FAILED = []


def check(name, cond, detail=""):
    print(("  ok   " if cond else "  FAIL ") + name + ("" if cond else "  " + str(detail)))
    if not cond:
        FAILED.append(name)


def main() -> int:
    from gbt_allinone.tentacle import hand_realtime as HR

    print("[1] status")
    st = HR.run("status")
    check("status ok", st.get("ok") is True)
    check("loopback 标明仿真", "simulated" in st.get("boundary", "") or "simulated" in str(st.get("transport","")))

    print("[2] 同拍 loop（60Hz × 1s）")
    r = HR.run("loop", {"hz": 60, "seconds": 1.0})
    check("loop ok", r.get("ok") is True, r)
    check("60 tick 全动", r.get("moved") == 60, r.get("moved"))
    check("loop_hz ≥ 30", (r.get("loop_hz") or 0) >= 30, r.get("loop_hz"))
    check("无错误", not r.get("errors"), r.get("errors"))
    check("明确 loopback 仿真", r.get("simulated") is True)
    print("[2b] IK 求解器同拍 loop")
    ri = HR.run("loop", {"hz": 60, "seconds": 1.0, "solver": "ik"})
    check("IK loop ok", ri.get("ok") is True, ri)
    check("IK 60 tick 全动", ri.get("moved") == 60, ri.get("moved"))
    check("IK loop_hz ≥ 30", (ri.get("loop_hz") or 0) >= 30, ri.get("loop_hz"))
    check("IK solver 记录", ri.get("solver") == "ik", ri.get("solver"))

    print("[3] 非 loop op fail-closed")
    check("未知 op 拒绝", HR.run("nope").get("ok") is False)

    print()
    if FAILED:
        print("FAILED %d: %s" % (len(FAILED), FAILED))
        return 1
    print("ALL PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


