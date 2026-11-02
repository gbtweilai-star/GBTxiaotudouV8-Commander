# -*- coding: utf-8 -*-
"""hand_camera_chunks — 处理 WinRT 连续录制的 1s chunk，依次过 ONNX + IK + HAL。

PowerShell 先录 chunk-*.mp4；Python 只读已完成文件，避免 Python 直接碰 WinRT。
"""
from __future__ import annotations

import glob
import os
import time


def run_chunks(dir_path: str = "", max_chunks: int = 3, solver: str = "geometric", **_kw):
    from . import hand_onnx as HO
    from . import hand_retarget as HR
    from . import hand_bridge as HB
    import cv2

    files = sorted(glob.glob(os.path.join(dir_path, "chunk-*.mp4")))[:max(1, int(max_chunks))]
    if not files:
        return {"ok": False, "op": "camera_chunks", "status": "needs_input",
                "error": "目录没有 chunk-*.mp4", "dir": dir_path}
    c = HB.run("connect", transport="loopback", profile="generic_20dof")
    if not c.get("ok"):
        return {"ok": False, "op": "camera_chunks", "stage": "connect", "error": c.get("error")}
    sid = c["session"]
    stats = {"chunks": 0, "frames": 0, "detected": 0, "moved": 0, "detect_ms": [], "ik_ms": []}
    t0 = time.perf_counter()
    try:
        for p in files:
            cap = cv2.VideoCapture(p)
            stats["chunks"] += 1
            while True:
                ok, frame = cap.read()
                if not ok:
                    break
                stats["frames"] += 1
                t = time.perf_counter()
                r = HO.detect(frame)
                stats["detect_ms"].append((time.perf_counter() - t) * 1000.0)
                if not r["hands"]:
                    continue
                stats["detected"] += 1
                t = time.perf_counter()
                ik = HR.run("ik" if str(solver).lower() == "ik" else "retarget",
                            landmarks=r["hands"][0]["landmarks"], model="generic_20dof", unit="rad")
                stats["ik_ms"].append((time.perf_counter() - t) * 1000.0)
                if not ik.get("ok"):
                    continue
                if HB.run("move", session=sid, targets=ik["joints"], dry_run=False).get("ok") and \
                   HB.run("read_state", session=sid).get("ok"):
                    stats["moved"] += 1
            cap.release()
    finally:
        HB.run("stop", session=sid)
        HB.run("disconnect", session=sid)
    el = time.perf_counter() - t0
    def avg(x): return round(sum(x) / len(x), 2) if x else None
    return {"ok": stats["moved"] > 0, "op": "camera_chunks", "dir": dir_path,
            "chunks": stats["chunks"], "files": [os.path.basename(x) for x in files],
            "frames": stats["frames"], "detected": stats["detected"], "moved": stats["moved"],
            "detect_ms_mean": avg(stats["detect_ms"]), "ik_ms_mean": avg(stats["ik_ms"]),
            "seconds": round(el, 2), "fps": round(stats["frames"] / max(el, 1e-6), 2),
            "realtime_ok": bool(stats["frames"] / max(el, 1e-6) >= 10 and stats["moved"] >= stats["frames"] * 0.8),
            "boundary": "WinRT 1s chunk + ONNX + loopback；非 MediaFrameReader 实时流"}
