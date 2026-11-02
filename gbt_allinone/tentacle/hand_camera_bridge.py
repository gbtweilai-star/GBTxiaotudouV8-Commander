# -*- coding: utf-8 -*-
"""hand_camera_bridge — 读 PowerShell WinRT 帧桥写出的 latest/frame JPEG，跑 ONNX + IK/HAL。

原因：Python 子进程直接调 WinRT 会 AggregateException；PowerShell 能抓帧。
本模块只读帧文件，不直接碰相机。
"""
from __future__ import annotations

import glob
import os
import time


def run_frames(frames_dir: str = "", frames: int = 5, solver: str = "geometric", **_kw):
    from . import hand_onnx as HO
    from . import hand_retarget as HR
    from . import hand_bridge as HB
    import cv2

    files = sorted(glob.glob(os.path.join(frames_dir, "frame-*.jpg")))
    if not files:
        latest = os.path.join(frames_dir, "latest.jpg")
        files = [latest] if os.path.isfile(latest) else []
    if not files:
        return {"ok": False, "op": "camera_bridge", "status": "needs_input",
                "error": "帧目录没有 frame-*.jpg / latest.jpg", "dir": frames_dir}
    files = files[:max(1, int(frames))]
    c = HB.run("connect", transport="loopback", profile="generic_20dof")
    if not c.get("ok"):
        return {"ok": False, "op": "camera_bridge", "stage": "connect", "error": c.get("error")}
    sid = c["session"]
    read = detected = moved = 0
    detect_ms, ik_ms = [], []
    t0 = time.perf_counter()
    try:
        for p in files:
            img = cv2.imread(p)
            if img is None:
                continue
            read += 1
            t = time.perf_counter()
            r = HO.detect(img)
            detect_ms.append((time.perf_counter() - t) * 1000.0)
            if not r["hands"]:
                continue
            detected += 1
            t = time.perf_counter()
            ik = HR.run("ik" if str(solver).lower() == "ik" else "retarget",
                        landmarks=r["hands"][0]["landmarks"], model="generic_20dof", unit="rad")
            ik_ms.append((time.perf_counter() - t) * 1000.0)
            if not ik.get("ok"):
                continue
            if HB.run("move", session=sid, targets=ik["joints"], dry_run=False).get("ok") and \
               HB.run("read_state", session=sid).get("ok"):
                moved += 1
    finally:
        HB.run("stop", session=sid)
        HB.run("disconnect", session=sid)
    el = time.perf_counter() - t0
    return {"ok": moved > 0, "op": "camera_bridge", "dir": frames_dir,
            "files": len(files), "read": read, "detected": detected, "moved": moved,
            "detect_ms_mean": round(sum(detect_ms) / len(detect_ms), 2) if detect_ms else None,
            "ik_ms_mean": round(sum(ik_ms) / len(ik_ms), 2) if ik_ms else None,
            "seconds": round(el, 3), "fps": round(read / max(el, 1e-6), 2),
            "realtime_ok": bool(moved >= max(1, len(files)) * 0.8),
            "boundary": "PowerShell WinRT 帧桥 + ONNX + loopback；真机需标定"}
