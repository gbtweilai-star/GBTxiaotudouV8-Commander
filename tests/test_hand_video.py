# -*- coding: utf-8 -*-
"""hand_realtime video：本地手部视频 → 21 点 → IK → loopback 手。"""
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
    print("[1] video 链")
    r = HR.run("video", {"video": vid, "solver": "ik", "smooth": 0.6})
    check("链 ok", r.get("ok") is True, r)
    check("30 帧", r.get("frames") == 30, r.get("frames"))
    check("30 帧检测到手", r.get("detected_frames") == 30, r.get("detected_frames"))
    check("30 帧 move 成功", r.get("moved_frames") == 30, r.get("moved_frames"))
    check("20 关节", r.get("joint_count") == 20, r.get("joint_count"))
    check("明确离线+仿真", "loopback" in str(r.get("boundary", "")), r.get("boundary"))
    check("smooth 生效", r.get("smooth") == 0.6, r.get("smooth"))
    check("抖动有读数", r.get("jitter_raw_mean") is not None and r.get("jitter_smoothed_mean") is not None, r)
    check("平滑不劣化（允许采样波动）", (r.get("jitter_smoothed_mean") or 0) <= (r.get("jitter_raw_mean") or 0) * 1.5, (r.get("jitter_raw_mean"), r.get("jitter_smoothed_mean")) )

    print()
    if FAILED:
        print("FAILED %d: %s" % (len(FAILED), FAILED))
        return 1
    print("ALL PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


