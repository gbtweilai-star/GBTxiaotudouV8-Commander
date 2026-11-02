# -*- coding: utf-8 -*-
"""hand_camera_watch — 监视 WinRT 录制目录，自动处理新出现的 chunk。

WinRT 录制仍由 PowerShell 负责；本模块只轮询目录，把新 chunk 送 ONNX/IK/HAL。
"""
from __future__ import annotations

import glob
import os
import time


def run_watch(dir_path: str = "", seconds: float = 5.0, poll: float = 0.3,
              max_chunks: int = 20, solver: str = "geometric", **_kw):
    from . import hand_onnx as HO
    from . import hand_retarget as HR
    from . import hand_bridge as HB
    import cv2

    if not dir_path or not os.path.isdir(dir_path):
        return {"ok": False, "op": "camera_watch", "status": "needs_input",
                "error": "目录不存在", "dir": dir_path}
    seen, files_done = set(), []
    frames = detected = moved = 0
    detect_ms, ik_ms = [], []
    t0 = time.perf_counter()
    c = HB.run("connect", transport="loopback", profile="generic_20dof")
    if not c.get("ok"):
        return {"ok": False, "op": "camera_watch", "stage": "connect", "error": c.get("error")}
    sid = c["session"]
    try:
        while time.perf_counter() - t0 < float(seconds) and len(files_done) < int(max_chunks):
            pending = [p for p in sorted(glob.glob(os.path.join(dir_path, "chunk-*.mp4")))
                       if p not in seen]
            if not pending:
                time.sleep(max(0.05, float(poll)))
                continue
            for p in pending:
                seen.add(p)
                cap = cv2.VideoCapture(p)
                while True:
                    ok, frame = cap.read()
                    if not ok:
                        break
                    frames += 1
                    t = time.perf_counter()
                    r = HO.detect(frame)
                    detect_ms.append((time.perf_counter() - t) * 1000.0)
                    if not r.get("hands"):
                        continue
                    detected += 1
                    t = time.perf_counter()
                    ik = HR.run("ik" if str(solver).lower() != "geometric" else "retarget",
                                landmarks=r["hands"][0]["landmarks"], model="generic_20dof", unit="rad")
                    ik_ms.append((time.perf_counter() - t) * 1000.0)
                    if not ik.get("ok"):
                        continue
                    if HB.run("move", session=sid, targets=ik["joints"], dry_run=False).get("ok") and \
                       HB.run("read_state", session=sid).get("ok"):
                        moved += 1
                cap.release()
                files_done.append(os.path.basename(p))
    finally:
        HB.run("stop", session=sid); HB.run("disconnect", session=sid)
    el = time.perf_counter() - t0
    def avg(x): return round(sum(x) / len(x), 2) if x else None
    return {"ok": moved > 0, "op": "camera_watch", "dir": dir_path,
            "files": files_done, "frames": frames, "detected": detected, "moved": moved,
            "detect_ms_mean": avg(detect_ms), "ik_ms_mean": avg(ik_ms),
            "seconds": round(el, 2), "fps": round(frames / max(el, 1e-6), 2),
            "realtime_ok": bool(frames / max(el, 1e-6) >= 10 and moved >= frames * 0.8),
            "boundary": "外部 WinRT 录 chunk + 目录监视 + ONNX；非 MediaFrameReader"}
