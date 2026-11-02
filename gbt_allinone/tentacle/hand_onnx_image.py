# -*- coding: utf-8 -*-
"""hand_onnx_image — 单图走 OpenCV DNN ONNX 的手部链（不依赖 MediaPipe）。"""
from __future__ import annotations

import time


def run_image(image: str = "", solver: str = "ik", hand: str = "right", **_kw):
    from . import hand_onnx as HO
    from . import hand_retarget as HR
    from . import hand_bridge as HB
    import cv2

    t0 = time.perf_counter()
    img = cv2.imread(str(image or ""))
    if img is None:
        return {"ok": False, "op": "onnx_image", "stage": "vision",
                "error": "读不了图片", "image": image}
    r = HO.detect(img)
    if not r.get("hands"):
        return {"ok": False, "op": "onnx_image", "stage": "vision", "status": "no_hand",
                "error": "图片里没检测到手", "image": image,
                "detect_ms": r.get("ms")}
    lm = r["hands"][0]["landmarks"]
    side = r["hands"][0].get("hand") or hand
    ik = HR.run("ik" if str(solver).lower() != "geometric" else "retarget",
                landmarks=lm, model="generic_20dof", hand=side, unit="rad")
    if not ik.get("ok"):
        return {"ok": False, "op": "onnx_image", "stage": "ik", "error": ik.get("error")}
    c = HB.run("connect", transport="loopback", profile="generic_20dof")
    if not c.get("ok"):
        return {"ok": False, "op": "onnx_image", "stage": "connect", "error": c.get("error")}
    sid = c["session"]
    moved = HB.run("move", session=sid, targets=ik["joints"], dry_run=False)
    state = HB.run("read_state", session=sid)
    HB.run("stop", session=sid); HB.run("disconnect", session=sid)
    return {"ok": bool(moved.get("ok") and state.get("ok")), "op": "onnx_image",
            "image": image, "detected_hand": side, "landmarks": len(lm),
            "solver": solver, "joint_count": len(ik.get("joints") or {}),
            "moved": bool(moved.get("ok")), "read_state_ok": bool(state.get("ok")),
            "detect_ms": r.get("ms"), "ik_ms": ik.get("ik_ms"),
            "seconds": round(time.perf_counter() - t0, 4),
            "boundary": "OpenCV DNN ONNX + loopback；真机需标定"}
