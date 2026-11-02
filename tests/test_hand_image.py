# -*- coding: utf-8 -*-
"""hand_realtime image 链：本地手图 → MediaPipe 21 点 → IK → loopback 手。"""
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
    img = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures", "hand-21.png")
    print("[1] image 链")
    r = HR.run("image", {"image": img, "solver": "ik"})
    check("链 ok", r.get("ok") is True, r)
    check("检测到 21 点", r.get("landmarks") == 21, r.get("landmarks"))
    check("20 关节", r.get("joint_count") == 20, r.get("joint_count"))
    check("move 成功", r.get("moved") is True, r)
    check("read_state 成功", r.get("read_state_ok") is True, r)
    check("loopback 明示仿真", "loopback" in str(r.get("boundary", "")), r.get("boundary"))
    check("无警告", not r.get("warnings"), r.get("warnings"))

    print()
    if FAILED:
        print("FAILED %d: %s" % (len(FAILED), FAILED))
        return 1
    print("ALL PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
