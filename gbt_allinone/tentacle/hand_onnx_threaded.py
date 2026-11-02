# -*- coding: utf-8 -*-
"""hand_onnx_threaded — 同进程 ONNX + 三线程（采集 / 推理 / IK+HAL）。

为什么同进程：
  ONNX 常驻子进程实测 infer 419ms（IPC/进程调度拖垮）；同进程单链 34ms。
  这里保留“模型只加载一次 + tracker 复用”，但把采集、推理、IK/HAL 分线程。

流水：
  capture 线程 → frame_q → detect 线程 → lm_q → IK/HAL 线程 → loopback
"""
from __future__ import annotations

import queue
import threading
import time


def run_video(path: str = "", solver: str = "geometric", qsize: int = 8, warmup: int = 3,
              adaptive: bool = True, max_age_ms: float = 120.0, **_kw):
    from . import hand_onnx as HO
    from . import hand_retarget as HR
    from . import hand_bridge as HB
    import cv2

    cap = cv2.VideoCapture(path)
    if not cap.isOpened():
        return {"ok": False, "op": "onnx_threaded", "status": "needs_input", "error": "打不开视频"}
    c = HB.run("connect", transport="loopback", profile="generic_20dof")
    if not c.get("ok"):
        cap.release()
        return {"ok": False, "op": "onnx_threaded", "stage": "connect", "error": c.get("error")}
    sid = c["session"]
    frame_q = queue.Queue(maxsize=max(1, int(qsize)))
    lm_q = queue.Queue(maxsize=max(1, int(qsize)))
    stats = {"frames": 0, "detected": 0, "moved": 0, "dropped": 0, "detect_ms": [], "ik_ms": [],
             "hal_ms": [], "e2e_ms": [], "errors": []}
    t0 = time.perf_counter()

    def put_latest(q, item):
        # 自适应：正常不丢；只有队列满，或队首帧年龄超 deadline 才丢旧帧
        if adaptive:
            while q.qsize() and (q.qsize() >= max(1, int(qsize)) or
                                 (time.perf_counter() - q.queue[0][1]) * 1000.0 > float(max_age_ms)):
                try:
                    q.get_nowait(); stats["dropped"] += 1
                except queue.Empty:
                    break
        try:
            q.put_nowait(item)
        except queue.Full:
            try:
                q.get_nowait(); stats["dropped"] += 1
            except queue.Empty:
                pass
            try:
                q.put_nowait(item)
            except queue.Full:
                pass

    def capture():
        try:
            while True:
                ok, frame = cap.read()
                if not ok:
                    break
                stats["frames"] += 1
                put_latest(frame_q, (frame, time.perf_counter()))
        finally:
            frame_q.put(None)

    def detect():
        try:
            while True:
                item = frame_q.get()
                if item is None:
                    break
                frame, t_enq = item
                t = time.perf_counter()
                r = HO.detect(frame)
                stats["detect_ms"].append((time.perf_counter() - t) * 1000.0)
                if r["hands"]:
                    stats["detected"] += 1
                    put_latest(lm_q, (r["hands"][0]["landmarks"], t_enq))
        finally:
            lm_q.put(None)

    def ik_hal():
        try:
            while True:
                item = lm_q.get()
                if item is None:
                    break
                lm, t_enq = item
                t = time.perf_counter()
                ik = HR.run("ik" if str(solver).lower() == "ik" else "retarget",
                            landmarks=lm, model="generic_20dof", unit="rad")
                stats["ik_ms"].append((time.perf_counter() - t) * 1000.0)
                if not ik.get("ok"):
                    continue
                t = time.perf_counter()
                m = HB.run("move", session=sid, targets=ik["joints"], dry_run=False)
                s = HB.run("read_state", session=sid)
                stats["hal_ms"].append((time.perf_counter() - t) * 1000.0)
                if m.get("ok") and s.get("ok"):
                    stats["moved"] += 1
                stats["e2e_ms"].append((time.perf_counter() - t_enq) * 1000.0)
        finally:
            HB.run("stop", session=sid)
            HB.run("disconnect", session=sid)

    th_c = threading.Thread(target=capture, daemon=True)
    th_d = threading.Thread(target=detect, daemon=True)
    th_h = threading.Thread(target=ik_hal, daemon=True)
    th_c.start(); th_d.start(); th_h.start()
    th_c.join(); th_d.join(); th_h.join()
    cap.release()
    el = time.perf_counter() - t0
    def avg(x): return round(sum(x) / len(x), 2) if x else None
    def p95(x): return round(sorted(x)[int(len(x) * 0.95)], 2) if x else None
    e2e = stats["e2e_ms"]
    steady = e2e[int(max(0, warmup)):]
    e2e95 = p95(e2e)
    steady95 = p95(steady)
    fps = round(stats["moved"] / max(el, 1e-6), 2)
    coverage = round(stats["moved"] / max(1, stats["frames"]), 3)
    ok_rt = bool(steady95 is not None and steady95 <= 100 and fps >= 10 and coverage >= 0.8)
    return {"ok": bool(stats["moved"]), "op": "onnx_threaded", "threads": 3,
            "frames": stats["frames"], "detected_frames": stats["detected"],
            "moved_frames": stats["moved"], "dropped_frames": stats["dropped"],
            "detect_ms_mean": avg(stats["detect_ms"]), "detect_ms_p95": p95(stats["detect_ms"]),
            "ik_ms_mean": avg(stats["ik_ms"]), "hal_ms_mean": avg(stats["hal_ms"]),
            "e2e_ms_p95": e2e95, "e2e_ms_p95_steady": steady95,
            "warmup": int(max(0, warmup)), "fps": fps, "coverage": coverage,
            "adaptive": bool(adaptive), "max_age_ms": float(max_age_ms), "seconds": round(el, 3),
            "realtime_ok": ok_rt,
            "verdict": "达到实时判据（latest-frame + 三线程）"
                       if ok_rt else "未达实时判据（延迟/帧率/覆盖率至少一项不达标）",
            "boundary": "同进程 OpenCV DNN ONNX + 几何重定向 + loopback 仿真；真机需标定"}

