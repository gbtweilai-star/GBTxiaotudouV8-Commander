# -*- coding: utf-8 -*-
"""hand_video 时序：视频时间戳、max_fps 丢帧、处理延迟测量。"""
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
    print("[1] max_fps=10 丢帧/延迟")
    r = HR.run("video", {"video": vid, "solver": "ik", "smooth": 0.6, "max_fps": 10})
    check("链 ok", r.get("ok") is True, r)
    check("输入 30 帧", r.get("frames") == 30, r.get("frames"))
    check("按 10fps 只处理 15 帧", r.get("detected_frames") == 15, r.get("detected_frames"))
    check("丢 15 帧", r.get("dropped_frames") == 15, r.get("dropped_frames"))
    check("max_fps 记录", r.get("max_fps") == 10.0, r.get("max_fps"))
    check("处理延迟有读数", r.get("process_latency_ms_mean") is not None, r)
    check("p95 有读数", r.get("process_latency_ms_p95") is not None, r)
    check("帧年龄有读数", r.get("frame_age_s_mean") is not None, r)
    check("明确离线+仿真", "loopback" in str(r.get("boundary", "")), r.get("boundary"))

    print()
    if FAILED:
        print("FAILED %d: %s" % (len(FAILED), FAILED))
        return 1
    print("ALL PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
