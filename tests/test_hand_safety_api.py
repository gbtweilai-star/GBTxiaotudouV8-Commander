# -*- coding: utf-8 -*-
"""API 安全闸：pre_clamp=false 必须结构化拒绝，不能崩。"""
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
    from gbt_allinone import api
    vid = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures", "hand-motion-long.mp4")
    print("[1] API 拒绝裸奔")
    r = api.run_task("hand_realtime", {"op": "onnx_chunked", "video": vid, "frames": 10,
                                       "chunk": 10, "force_limit": 0.5, "pre_clamp": False})
    res = (r.get("gbt_result") or {}).get("result") or r
    check("返回 dict", isinstance(res, dict), res)
    check("status=unsafe_rejected", res.get("status") == "unsafe_rejected", res)
    check("带 safety_guard", res.get("safety_guard") is True, res)
    check("不崩（无 payload ValueError）", "dictionary update" not in str(res), res)

    print()
    if FAILED:
        print("FAILED %d: %s" % (len(FAILED), FAILED))
        return 1
    print("ALL PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
