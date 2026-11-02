# -*- coding: utf-8 -*-
"""hand_realtime onnx_video：本地 OpenCV DNN ONNX 实时判据。"""
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
    from gbt_allinone.tentacle import hand_onnx as HO
    from gbt_allinone.tentacle import hand_realtime as HR
    vid = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures", "hand-motion.mp4")

    print("[1] ONNX 模型")
    st = HO.run("status")
    check("status ok", st.get("ok") is True, st)
    check("两模型在位", len(st.get("models") or []) == 2, st.get("models"))

    print("[2] ONNX 视频实时判据")
    r = HR.run("onnx_video", {"video": vid, "solver": "geometric"})
    check("链 ok", r.get("ok") is True, r)
    check("30 帧检测", r.get("detected_frames") == 30, r.get("detected_frames"))
    check("30 帧 move", r.get("moved_frames") == 30, r.get("moved_frames"))
    check("detect mean < 100ms", (r.get("detect_ms_mean") or 999) < 100, r.get("detect_ms_mean"))
    check("frame p95 ≤ 100ms", (r.get("frame_ms_p95") or 999) <= 100, r.get("frame_ms_p95"))
    check("fps ≥ 10", (r.get("fps") or 0) >= 10, r.get("fps"))
    check("realtime_ok", r.get("realtime_ok") is True, r)
    check("verdict 达实时", "达到实时" in str(r.get("verdict", "")), r.get("verdict"))

    print()
    if FAILED:
        print("FAILED %d: %s" % (len(FAILED), FAILED))
        return 1
    print("ALL PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
