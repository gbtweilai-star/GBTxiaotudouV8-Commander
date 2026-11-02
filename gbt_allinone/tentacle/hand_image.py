# -*- coding: utf-8 -*-
"""hand_realtime image 入口：本地手部图片 → MediaPipe 21 点 → IK → loopback 手。"""
from __future__ import annotations

import json
import time


def run_image(image: str = "", solver: str = "ik", hand: str = "right", **_kw):
    from . import hand_vision as HV
    from . import hand_retarget as HR
    from . import hand_bridge as HB

    vis = HV.run("image", {"image": image})
    if not vis.get("ok"):
        return {"ok": False, "op": "image", "stage": "vision", "error": vis.get("error"), "raw": vis}
    hands = vis.get("hands") or []
    if not hands:
        return {"ok": False, "op": "image", "stage": "vision", "status": "no_hand",
                "error": "图片里没检测到手", "image": image}
    lm = hands[0]["landmarks"]
    side = hands[0].get("hand") or hand
    ik = HR.run("ik" if str(solver).lower() != "geometric" else "retarget",
                landmarks=lm, model="generic_20dof", hand=side, unit="rad")
    if not ik.get("ok"):
        return {"ok": False, "op": "image", "stage": "ik", "error": ik.get("error"), "ik": ik}
    c = HB.run("connect", transport="loopback", profile="generic_20dof")
    if not c.get("ok"):
        return {"ok": False, "op": "image", "stage": "connect", "error": c.get("error")}
    sid = c["session"]
    moved = HB.run("move", session=sid, targets=ik["joints"], dry_run=False)
    state = HB.run("read_state", session=sid)
    HB.run("stop", session=sid)
    HB.run("disconnect", session=sid)
    return {"ok": bool(moved.get("ok") and state.get("ok")), "op": "image",
            "image": image, "detected_hand": side, "landmarks": len(lm),
            "solver": solver, "joint_count": len(ik.get("joints") or {}),
            "moved": bool(moved.get("ok")), "read_state_ok": bool(state.get("ok")),
            "session": sid, "ik": ik.get("ik"), "warnings": ik.get("warnings"),
            "boundary": "MediaPipe 归一化坐标 + loopback 仿真；真机需标定/register_map/confirm"}
