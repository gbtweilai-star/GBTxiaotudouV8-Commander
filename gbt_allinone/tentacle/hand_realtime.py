# -*- coding: utf-8 -*-
"""hand_realtime — 眼手脑同拍 · 灵巧手 loopback 版。

链路（同一拍，不是三段式）：
  21 点手部流 → hand_retarget（几何）→ hand_bridge loopback.move → read_state
每个 tick 都重算，动作/回读/下一帧在同一控制环；输出 loop_hz / 命令数 / 延迟。

边界：loopback 是仿真手，不驱动真硬件；真机需 register_map + confirm。
"""
from __future__ import annotations

import json
import math
import time

from . import hand_bridge as HB
from . import hand_retarget as HR

__all__ = ["run", "STATUS"]


def _straight():
    lm = [[0.0, 0.0, 0.0] for _ in range(21)]
    lm[1] = [0.006, 0.020, 0.0]
    lm[2] = [0.010, 0.045, 0.0]
    lm[3] = [0.014, 0.065, 0.0]
    lm[4] = [0.018, 0.085, 0.0]
    xs = {"index": -0.020, "middle": 0.0, "ring": 0.020, "pinky": 0.040}
    for name, x in xs.items():
        base = {"index": 5, "middle": 9, "ring": 13, "pinky": 17}[name]
        for k, y in enumerate((0.060, 0.100, 0.130, 0.150)):
            lm[base + k] = [x, y, 0.0]
    return lm


def _curl_index(amount=1.0):
    lm = _straight()
    # 食指沿 +z 弯；amount 0..1
    lm[6] = [-0.020, 0.080 - 0.020 * amount, 0.020 * amount]
    lm[7] = [-0.020, 0.070 - 0.020 * amount, 0.040 * amount]
    lm[8] = [-0.020, 0.050 - 0.010 * amount, 0.050 * amount]
    return lm


def _splay():
    lm = _straight()
    for base, out in ((5, -0.012), (9, 0.0), (13, 0.012), (17, 0.024)):
        for k in range(4):
            lm[base + k][0] += out * (k + 1)
    return lm


def _trajectory(i, n):
    # 0..n: open -> curl index -> splay -> open; 近似 60Hz 手部跟踪流
    t = i / max(1, n - 1)
    if t < 0.33:
        return _curl_index(t / 0.33)
    if t < 0.66:
        return _curl_index(1.0 - (t - 0.33) / 0.33)
    if t < 0.85:
        return _splay()
    return _straight()


def status(**_kw):
    return {"ok": True, "cap": "hand_realtime", "ops": ["status", "loop", "force_loop", "image", "video", "pipeline", "onnx_video", "onnx_threaded", "onnx_chunked", "camera_bridge", "camera_chunks"],
            "mode": "landmarks -> retarget -> loopback.move -> read_state, same tick",
            "transport": "loopback (simulated)", "target_hz": 60,
            "boundary": "loopback（simulated）：仿真手；真机需要 register_map + confirm"}


def loop(payload=None, **_kw):
    payload = payload or {}
    hz = float(payload.get("hz", 60))
    secs = float(payload.get("seconds", 2.0))
    solver = str(payload.get("solver") or "geometric").lower()
    n = max(2, int(hz * secs))
    c = HB.run("connect", transport="loopback", profile="generic_20dof")
    if not c.get("ok"):
        return {"ok": False, "op": "loop", "stage": "connect", "error": c.get("error"), "raw": c}
    sid = c["session"]
    lat, errs = [], []
    moved = 0
    t0 = time.perf_counter()
    try:
        for i in range(n):
            tick = time.perf_counter()
            lm = _trajectory(i, n)
            r = (HR.run("ik", landmarks=lm, model="generic_20dof", unit="rad")
                 if solver == "ik" else
                 HR.run("retarget", landmarks=lm, model="generic_20dof", unit="rad"))
            if not r.get("ok"):
                errs.append(("retarget", r.get("error")))
                continue
            targets = r["joints"]
            m = HB.run("move", session=sid, targets=targets, dry_run=False)
            if not m.get("ok"):
                errs.append(("move", m.get("error")))
                break
            s = HB.run("read_state", session=sid)
            if not s.get("ok"):
                errs.append(("read", s.get("error")))
                break
            moved += 1
            lat.append((time.perf_counter() - tick) * 1000)
            # 控制环按目标频率补睡；动作/回读都在同一 tick
            wait = 1.0 / hz - (time.perf_counter() - tick)
            if wait > 0:
                time.sleep(wait)
    finally:
        HB.run("stop", session=sid)
        HB.run("disconnect", session=sid)
    elapsed = time.perf_counter() - t0
    return {"ok": bool(moved and not errs), "op": "loop", "transport": "loopback",
            "simulated": True, "solver": solver, "session": sid, "ticks": n, "moved": moved,
            "loop_hz": round(moved / max(1e-6, elapsed), 2),
            "latency_ms_mean": round(sum(lat) / len(lat), 2) if lat else None,
            "latency_ms_p95": round(sorted(lat)[int(len(lat) * 0.95)] if lat else 0, 2),
            "errors": errs[:3], "seconds": round(elapsed, 3),
            "boundary": "loopback 仿真；真机需 register_map + confirm"}


def force_loop(payload=None, **_kw):
    """力限幅 + 导纳同拍：先动，再读仿真接触力；超限则按 (limit/k) 退让。

    仅 loopback 虚拟接触，不是真手力传感器。
    """
    payload = payload or {}
    hz = float(payload.get("hz", 60))
    secs = float(payload.get("seconds", 2.0))
    solver = str(payload.get("solver") or "ik").lower()
    joint = str(payload.get("joint") or "index_mcp")
    external = float(payload.get("external", 0.3))
    stiffness = float(payload.get("stiffness", 100.0))
    limit = abs(float(payload.get("force_limit", 10.0)))
    n = max(2, int(hz * secs))
    c = HB.run("connect", transport="loopback", profile="generic_20dof")
    if not c.get("ok"):
        return {"ok": False, "op": "force_loop", "stage": "connect", "error": c.get("error")}
    sid = c["session"]
    lat, errs, forces, adjustments = [], [], [], 0
    pre_clamped = 0
    moved = 0
    t0 = time.perf_counter()
    try:
        # 虚拟接触参数：先定刚度（真机需传感器标定）
        HB.run("compliance", session=sid, stiffness=stiffness, damping=0.05)
        for i in range(n):
            tick = time.perf_counter()
            lm = _trajectory(i, n)
            r = (HR.run("ik", landmarks=lm, model="generic_20dof", unit="rad")
                 if solver == "ik" else
                 HR.run("retarget", landmarks=lm, model="generic_20dof", unit="rad"))
            if not r.get("ok"):
                errs.append(("retarget", r.get("error")))
                continue
            targets = r["joints"]
            # 先按虚拟接触预判，不先撞上去再退：q <= external + limit/k
            if joint in targets:
                pred = stiffness * (float(targets[joint]) - external)
                if abs(pred) > limit:
                    targets[joint] = max(-1.2, min(1.8, external + (limit / max(stiffness, 1e-9)) * (1.0 if pred >= 0 else -1.0)))
                    pre_clamped += 1
            m = HB.run("move", session=sid, targets=targets, dry_run=False)
            if not m.get("ok"):
                errs.append(("move", m.get("error")))
                break
            ct = HB.run("contact", session=sid, joint=joint, external=external, stiffness=stiffness)
            f = float(ct.get("force") or 0.0)
            forces.append(f)
            if abs(f) > limit:
                # 导纳退让：目标 = 外部位置 + sign(force)*limit/k
                safe = external + (limit / max(stiffness, 1e-9)) * (1.0 if f >= 0 else -1.0)
                lo = -1.2; hi = 1.8
                safe = max(lo, min(hi, safe))
                targets[joint] = safe
                m2 = HB.run("move", session=sid, targets=targets, dry_run=False)
                if not m2.get("ok"):
                    errs.append(("force_move", m2.get("error")))
                    break
                ct2 = HB.run("contact", session=sid, joint=joint, external=external, stiffness=stiffness)
                forces.append(float(ct2.get("force") or 0.0))
                adjustments += 1
            s = HB.run("read_state", session=sid)
            if not s.get("ok"):
                errs.append(("read", s.get("error")))
                break
            moved += 1
            lat.append((time.perf_counter() - tick) * 1000)
            wait = 1.0 / hz - (time.perf_counter() - tick)
            if wait > 0:
                time.sleep(wait)
    finally:
        HB.run("stop", session=sid)
        HB.run("disconnect", session=sid)
    elapsed = time.perf_counter() - t0
    peak = max((abs(x) for x in forces), default=0.0)
    return {"ok": bool(moved and not errs and peak <= limit + 1e-6), "op": "force_loop",
            "transport": "loopback", "simulated": True, "solver": solver, "joint": joint,
            "force_limit": limit, "stiffness": stiffness, "external": external,
            "ticks": n, "moved": moved, "adjustments": adjustments, "pre_clamped": pre_clamped,
            "force_peak": round(peak, 3), "loop_hz": round(moved / max(1e-6, elapsed), 2),
            "latency_ms_mean": round(sum(lat) / len(lat), 2) if lat else None,
            "errors": errs[:3], "seconds": round(elapsed, 3),
            "boundary": "虚拟弹簧接触；真机需力传感器/厂商力控接口，不伪造"}


def onnx_video(payload=None, **_kw):
    """ONNX 快速视觉链：OpenCV DNN 34ms/帧 + 几何重定向 + loopback。

    与 MediaPipe 链分开：MediaPipe 在本机 CPU 上 p95>700ms；ONNX 用 OpenCV DNN。
    IK 可选，但 IK 单帧 >100ms 会拖垮实时；默认 geometric。
    """
    payload = payload or {}
    from . import hand_onnx as HO
    import cv2
    path = str(payload.get("video") or payload.get("path") or "")
    solver = str(payload.get("solver") or "geometric").lower()
    max_fps = float(payload.get("max_fps", 0) or 0)
    cap = cv2.VideoCapture(path)
    if not cap.isOpened():
        return {"ok": False, "op": "onnx_video", "status": "needs_input", "error": "打不开视频"}
    c = HB.run("connect", transport="loopback", profile="generic_20dof")
    if not c.get("ok"):
        cap.release()
        return {"ok": False, "op": "onnx_video", "stage": "connect", "error": c.get("error")}
    sid = c["session"]
    frames = detected = moved = dropped = 0
    total, detect_ms, ik_ms, hal_ms = [], [], [], []
    last_ts = 0.0
    t0 = time.perf_counter()
    try:
        while True:
            ok, frame = cap.read()
            if not ok:
                break
            frames += 1
            ts = cap.get(cv2.CAP_PROP_POS_MSEC) / 1000.0
            if max_fps and (ts - last_ts) < (1.0 / max_fps):
                dropped += 1
                continue
            last_ts = ts
            t = time.perf_counter()
            r = HO.detect(frame)
            detect_ms.append(r.get("infer_ms") or 0.0)
            if not r["hands"]:
                total.append((time.perf_counter() - t) * 1000.0)
                continue
            lm = r["hands"][0]["landmarks"]
            detected += 1
            t_ik = time.perf_counter()
            ik = HR.run("ik" if solver == "ik" else "retarget",
                        landmarks=lm, model="generic_20dof", unit="rad")
            ik_ms.append((time.perf_counter() - t_ik) * 1000.0)
            if not ik.get("ok"):
                total.append((time.perf_counter() - t) * 1000.0)
                continue
            t_h = time.perf_counter()
            m = HB.run("move", session=sid, targets=ik["joints"], dry_run=False)
            s = HB.run("read_state", session=sid)
            hal_ms.append((time.perf_counter() - t_h) * 1000.0)
            if m.get("ok") and s.get("ok"):
                moved += 1
            total.append((time.perf_counter() - t) * 1000.0)
    finally:
        cap.release()
        HB.run("stop", session=sid)
        HB.run("disconnect", session=sid)
    el = time.perf_counter() - t0
    p95 = round(sorted(total)[int(len(total) * 0.95)], 2) if total else None
    fps = round(moved / max(el, 1e-6), 2)
    return {"ok": bool(moved), "op": "onnx_video", "frames": frames,
            "detected_frames": detected, "moved_frames": moved, "dropped_frames": dropped,
            "solver": solver, "detect_ms_mean": round(sum(detect_ms) / len(detect_ms), 2) if detect_ms else None,
            "detect_ms_p95": round(sorted(detect_ms)[int(len(detect_ms) * 0.95)], 2) if detect_ms else None,
            "ik_ms_mean": round(sum(ik_ms) / len(ik_ms), 2) if ik_ms else None,
            "hal_ms_mean": round(sum(hal_ms) / len(hal_ms), 2) if hal_ms else None,
            "frame_ms_p95": p95, "fps": fps, "seconds": round(el, 3),
            "realtime_ok": bool(p95 is not None and p95 <= 100 and fps >= 10),
            "verdict": "达到实时判据（ONNX，p95≤100ms & fps≥10）"
                       if (p95 is not None and p95 <= 100 and fps >= 10)
                       else "未达实时判据",
            "boundary": "OpenCV DNN ONNX + 几何重定向 + loopback 仿真；真机需标定"}


def run(op="status", payload=None, **kw):
    op = str(op).lower()
    if op == "loop":
        return loop(payload, **kw)
    if op == "force_loop":
        return force_loop(payload, **kw)
    if op == "onnx_video":
        return onnx_video(payload, **kw)
    if op == "camera_watch":
        from .hand_camera_watch import run_watch
        p = payload or {}
        return run_watch(str(p.get("dir", "")), seconds=float(p.get("seconds", 5)), poll=float(p.get("poll", 0.3)), max_chunks=int(p.get("max_chunks", 20)), solver=str(p.get("solver", "geometric")))
    if op == "camera_chunks":
        from .hand_camera_chunks import run_chunks
        p = payload or {}
        return run_chunks(str(p.get("dir", p.get("chunks_dir", ""))), max_chunks=int(p.get("max_chunks", 3)), solver=str(p.get("solver", "geometric")))
    if op == "camera_bridge":
        from .hand_camera_bridge import run_frames
        p = payload or {}
        return run_frames(str(p.get("dir", p.get("frames_dir", ""))), frames=int(p.get("frames", 5)), solver=str(p.get("solver", "geometric")))
    if op == "onnx_chunked":
        from .hand_onnx_chunked_chain import run_video
        p = payload or {}
        return run_video(str(p.get("video", p.get("path", ""))), frames=int(p.get("frames", 150)), chunk=int(p.get("chunk", 60)), solver=str(p.get("solver", "geometric")), timeout=float(p.get("timeout", 300)), force_limit=float(p.get("force_limit", 0) or 0), stiffness=float(p.get("stiffness", 100)), external=float(p.get("external", 0.3)), joint=str(p.get("joint", "index_mcp")), adapt=bool(p.get("adapt", False)), k_min=float(p.get("k_min", 10)), k_max=float(p.get("k_max", 200)), compliance_every=int(p.get("compliance_every", 10)), debounce=int(p.get("debounce", 2)), dense_frames=int(p.get("dense_frames", 3)), feedforward=bool(p.get("feedforward", False)), rate_threshold=float(p.get("rate_threshold", 5)), external_amp=float(p.get("external_amp", 0)), external_period=int(p.get("external_period", 20)), pre_clamp=bool(p.get("pre_clamp", True)))
    if op == "onnx_threaded":
        from .hand_onnx_threaded import run_video
        p = payload or {}
        return run_video(str(p.get("video", p.get("path", ""))), solver=str(p.get("solver", "geometric")), qsize=int(p.get("qsize", 8)))
    if op == "video":
        from .hand_video import run_video
        p = payload or {}
        return run_video(path=str(p.get("video", p.get("path", ""))), solver=str(p.get("solver", "ik")), stride=int(p.get("stride", 1)), smooth=float(p.get("smooth", 0.0)), max_fps=float(p.get("max_fps", 0.0)), proc_width=int(p.get("proc_width", 0)), roi=bool(p.get("roi", False)))
    if op == "pipeline":
        from .hand_pipeline import _run
        p = payload or {}
        return _run(str(p.get("video", p.get("path", ""))), stride=int(p.get("stride", 1)), max_fps=float(p.get("max_fps", 0)), timeout=float(p.get("timeout", 180)))
    if op == "onnx_image":
        from .hand_onnx_image import run_image as _onnx_image
        p = payload or {}
        return _onnx_image(image=str(p.get("image", "")), solver=str(p.get("solver", "ik")), hand=str(p.get("hand", "right")))
    if op == "image":
        from .hand_image import run_image
        p = payload or {}
        return run_image(image=str(p.get("image", "")), solver=str(p.get("solver", "ik")),
                         hand=str(p.get("hand", "right")))
    if op == "status":
        return status(**kw)
    return {"ok": False, "status": "user_error", "error": "未知 op：%s（status/loop/force_loop/image）" % op}






















