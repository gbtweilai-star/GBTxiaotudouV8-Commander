# -*- coding: utf-8 -*-
"""onnx_chunked + 力限幅：长视频链里同时做进程回收、IK、力限。"""
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
    vid = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures", "hand-motion-long.mp4")
    print("[1] 60帧 / force_limit=0.5")
    r = HR.run("onnx_chunked", {"video": vid, "frames": 60, "chunk": 60,
                                "force_limit": 0.5, "stiffness": 100,
                                "external": 0.0, "joint": "index_mcp", "timeout": 120})
    check("链 ok", r.get("ok") is True, r)
    check("60 帧", r.get("frames") == 60, r.get("frames"))
    check("60 move", r.get("moved") == 60, r.get("moved"))
    check("力峰值 ≤ limit", (r.get("force_peak") or 0) <= 0.5 + 1e-6, r.get("force_peak"))
    check("有预限幅", (r.get("pre_clamped") or 0) > 0, r.get("pre_clamped"))
    check("realtime_ok", r.get("realtime_ok") is True, r)

    print()
    if FAILED:
        print("FAILED %d: %s" % (len(FAILED), FAILED))
        return 1
    print("ALL PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
