# -*- coding: utf-8 -*-
"""hand_realtime force_loop：力限幅 + 导纳同拍（loopback 仿真）。"""
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

    print("[1] 力限幅同拍")
    r = HR.run("force_loop", {"hz": 60, "seconds": 1.0, "force_limit": 10,
                              "stiffness": 100, "external": 0.3,
                              "joint": "index_mcp", "solver": "ik"})
    check("force_loop ok", r.get("ok") is True, r)
    check("60 tick", r.get("ticks") == 60, r.get("ticks"))
    check("60 moved", r.get("moved") == 60, r.get("moved"))
    check("力峰值 ≤ 限值", (r.get("force_peak") or 0) <= 10 + 1e-6, r.get("force_peak"))
    check("有预限幅", (r.get("pre_clamped") or 0) > 0, r.get("pre_clamped"))
    check("loop_hz ≥ 30", (r.get("loop_hz") or 0) >= 30, r.get("loop_hz"))
    check("明确仿真", r.get("simulated") is True)
    check("无错误", not r.get("errors"), r.get("errors"))

    print()
    if FAILED:
        print("FAILED %d: %s" % (len(FAILED), FAILED))
        return 1
    print("ALL PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
