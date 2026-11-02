# -*- coding: utf-8 -*-
"""hand_vision 判据：本地 MediaPipe 在位；摄像头不可用时 fail-closed，不伪造。"""
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
    from gbt_allinone.tentacle import hand_vision as HV

    print("[1] status")
    st = HV.run("status")
    check("status ok", st.get("ok") is True, st)
    check("mediapipe 在位", bool(st.get("mediapipe")), st)
    check("opencv 在位", bool(st.get("opencv")), st)
    check("camera 字段是 bool", isinstance(st.get("camera"), bool), st)

    print("[2] 摄像头 fail-closed")
    r = HV.run("camera", {"seconds": 0.5})
    if st.get("camera"):
        check("camera ok 或 no_hand", r.get("ok") is True or r.get("status") in (None, "no_hand"), r)
    else:
        check("camera 不可用 → needs_camera", r.get("status") == "needs_camera", r)
        check("不伪造帧", r.get("ok") is False, r)

    print("[3] 未知 op")
    check("未知 op 拒绝", HV.run("nope").get("ok") is False)

    print()
    if FAILED:
        print("FAILED %d: %s" % (len(FAILED), FAILED))
        return 1
    print("ALL PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
