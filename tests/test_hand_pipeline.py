# -*- coding: utf-8 -*-
"""hand_pipeline 判据：常驻 worker + 三线程；若仍 >100ms 必须明确报不适合实时。"""
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
    vid = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures", "hand-motion.mp4")
    print("[1] 常驻 worker + 线程流水")
    r = HR.run("pipeline", {"video": vid, "stride": 1, "timeout": 120})
    check("pipeline ok", r.get("ok") is True, r)
    check("worker 常驻", r.get("worker") == "persistent", r.get("worker"))
    check("30 帧", r.get("worker_frames") == 30, r.get("worker_frames"))
    check("30 IK", r.get("ik_done") == 30, r.get("ik_done"))
    check("30 HAL", r.get("hal_done") == 30, r.get("hal_done"))
    check("有 init_ms", r.get("init_ms") is not None, r)
    check("有 infer p95", r.get("infer_ms_p95") is not None, r)
    check("有 pipeline_fps", r.get("pipeline_fps") is not None, r)
    check("实时判据字段", isinstance(r.get("realtime_ok"), bool), r)
    if not r.get("realtime_ok"):
        check("明确 verdict", "不适合实时" in str(r.get("verdict", "")), r.get("verdict"))

    print()
    if FAILED:
        print("FAILED %d: %s" % (len(FAILED), FAILED))
        return 1
    print("ALL PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
