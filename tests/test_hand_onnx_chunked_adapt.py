# -*- coding: utf-8 -*-
"""onnx_chunked + 自适应刚度/接触事件。"""
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
    print("[1] 60帧 / adapt / limit=0.5")
    r = HR.run("onnx_chunked", {"video": vid, "frames": 60, "chunk": 60,
                                "force_limit": 0.5, "stiffness": 100, "external": 0.0,
                                "joint": "index_mcp", "adapt": True, "timeout": 120})
    check("链 ok", r.get("ok") is True, r)
    check("60 move", r.get("moved") == 60, r.get("moved"))
    check("力峰值 ≤0.5", (r.get("force_peak") or 0) <= 0.5 + 1e-6, r.get("force_peak"))
    check("adapt 标记", r.get("adapt") is True)
    check("刚度下降", (r.get("stiffness_end") or 999) < (r.get("stiffness_start") or 0),
          (r.get("stiffness_start"), r.get("stiffness_end")))
    check("有接触事件", bool(r.get("contact_events")), r.get("contact_events"))

    print()
    if FAILED:
        print("FAILED %d: %s" % (len(FAILED), FAILED))
        return 1
    print("ALL PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
