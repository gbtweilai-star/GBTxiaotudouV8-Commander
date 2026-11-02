# -*- coding: utf-8 -*-
"""hand_onnx_chunked：真进程回收 + 手部 IK/HAL 长视频链。"""
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
    print("[1] 150帧 / chunk60：进程回收 + IK/HAL")
    r = HR.run("onnx_chunked", {"video": vid, "frames": 150, "chunk": 60, "timeout": 120})
    check("链 ok", r.get("ok") is True, r)
    check("150 帧", r.get("frames") == 150, r.get("frames"))
    check("150 手帧", r.get("hand_frames") == 150, r.get("hand_frames"))
    check("150 IK", r.get("ik_ok") == 150, r.get("ik_ok"))
    check("150 move", r.get("moved") == 150, r.get("moved"))
    check("3 chunks", len(r.get("chunks") or []) == 3, r.get("chunks"))
    check("fps ≥10", (r.get("fps") or 0) >= 10, r.get("fps"))
    check("realtime_ok", r.get("realtime_ok") is True, r)

    print()
    if FAILED:
        print("FAILED %d: %s" % (len(FAILED), FAILED))
        return 1
    print("ALL PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
