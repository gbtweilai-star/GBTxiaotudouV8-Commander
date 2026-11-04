# -*- coding: utf-8 -*-
"""hand_pipeline — 常驻推理进程 + 复用 tracker + 线程/帧池。

结构：
  采集/推理子进程（hand_tracker_worker.py，模型只初始化一次）
        │ JSONL: landmarks + infer_ms
        ▼
  推理读线程 ──► ik_q ──► IK 线程 ──► hal_q ──► 手 HAL 线程（loopback）
  
目标：验证“模型常驻 + tracker 复用 + 分级线程”后的吞吐/延迟；
若仍 >100ms，明确 realtime_ok=false，不拿低 fps 冒充实时。
"""
from __future__ import annotations

import json
import os
import queue
import subprocess
import sys
import threading
import time

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
WORKER_MP = os.path.join(ROOT, "tools", "model-bridge", "hand_tracker_worker.py")
WORKER_ONNX = os.path.join(ROOT, "tools", "model-bridge", "hand_onnx_worker.py")
PY = sys.executable


def _run(path: str, stride: int = 1, max_fps: float = 0.0, timeout: float = 180.0, backend: str = "mediapipe"):
    from . import hand_bridge as HB
    from . import hand_retarget as HR

    env = dict(os.environ)
    env["MPLCONFIGDIR"] = os.path.join(ROOT, ".scratch", "lead", "mpl")
    env["GLOG_minloglevel"] = "2"
    worker = WORKER_ONNX if str(backend).lower() == "onnx" else WORKER_MP
    p = subprocess.Popen([PY, "-B", "-X", "utf8", worker], stdin=subprocess.PIPE,
                         stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True,
                         encoding="utf-8", bufsize=1, env=env)
    ready = {}
    t_start = time.perf_counter()
    # 等 ready（模型初始化）
    for _ in range(600):
        line = p.stdout.readline()
        if not line:
            break
        try:
            msg = json.loads(line)
        except Exception:  # noqa: BLE001
            continue
        if msg.get("type") == "ready":
            ready = msg
            break
    init_ms = (time.perf_counter() - t_start) * 1000.0
    if not ready:
        try:
            p.kill()
        except Exception:  # noqa: BLE001
            pass
        return {"ok": False, "op": "pipeline", "stage": "worker_ready", "error": "worker 未就绪"}

    ik_q, hal_q = queue.Queue(), queue.Queue()
    stats = {"worker_frames": 0, "ik_done": 0, "hal_done": 0, "errors": [],
             "infer_ms": [], "ik_ms": [], "hal_ms": [], "e2e_ms": []}
    done = threading.Event()

    def read_worker():
        try:
            for line in p.stdout:
                try:
                    msg = json.loads(line)
                except Exception:  # noqa: BLE001
                    continue
                typ = msg.get("type")
                if typ == "frame":
                    stats["worker_frames"] += 1
                    stats["infer_ms"].append(msg.get("infer_ms"))
                    if msg.get("landmarks"):
                        ik_q.put(msg)
                elif typ == "done":
                    done.set()
                elif typ == "error":
                    stats["errors"].append(msg.get("error"))
        finally:
            ik_q.put(None)

    def ik_worker():
        while True:
            msg = ik_q.get()
            if msg is None:
                hal_q.put(None)
                return
            t = time.perf_counter()
            r = HR.run("ik", landmarks=msg["landmarks"], model="generic_20dof", unit="rad")
            dt = (time.perf_counter() - t) * 1000.0
            stats["ik_ms"].append(dt)
            if r.get("ok"):
                stats["ik_done"] += 1
                msg["joints"] = r["joints"]
                msg["ik_ms"] = dt
                hal_q.put(msg)

    def hal_worker():
        c = HB.run("connect", transport="loopback", profile="generic_20dof")
        if not c.get("ok"):
            stats["errors"].append("hal connect: %s" % c.get("error"))
            hal_q.put(None)
            return
        sid = c["session"]
        try:
            while True:
                msg = hal_q.get()
                if msg is None:
                    return
                t = time.perf_counter()
                m = HB.run("move", session=sid, targets=msg["joints"], dry_run=False)
                s = HB.run("read_state", session=sid)
                dt = (time.perf_counter() - t) * 1000.0
                stats["hal_ms"].append(dt)
                if m.get("ok") and s.get("ok"):
                    stats["hal_done"] += 1
                    stats["e2e_ms"].append((time.perf_counter() - t_start) * 1000.0)
        finally:
            HB.run("stop", session=sid)
            HB.run("disconnect", session=sid)
            hal_q.put(None)

    th_read = threading.Thread(target=read_worker, daemon=True)
    th_ik = threading.Thread(target=ik_worker, daemon=True)
    th_hal = threading.Thread(target=hal_worker, daemon=True)
    th_ik.start(); th_hal.start(); th_read.start()

    # 下发视频命令
    p.stdin.write(json.dumps({"cmd": "video", "path": path, "stride": int(stride),
                              "max_fps": float(max_fps)}, ensure_ascii=False) + "\n")
    p.stdin.flush()
    done.wait(timeout=timeout)
    try:
        p.stdin.write(json.dumps({"cmd": "quit"}) + "\n"); p.stdin.flush()
    except Exception:  # noqa: BLE001
        pass
    th_read.join(timeout=5)
    th_ik.join(timeout=5)
    th_hal.join(timeout=5)
    try:
        p.wait(timeout=5)
    except Exception:  # noqa: BLE001
        p.kill()
    el = time.perf_counter() - t_start
    def avg(x): return round(sum(x) / len(x), 2) if x else None
    def p95(x): return round(sorted(x)[int(len(x) * 0.95)], 2) if x else None
    infer_p95 = p95(stats["infer_ms"]) or 99999
    fps = round(stats["hal_done"] / max(el, 1e-6), 2)
    return {"ok": bool(stats["hal_done"]), "op": "pipeline", "worker": "persistent",
            "init_ms": round(init_ms, 2), "worker_frames": stats["worker_frames"],
            "ik_done": stats["ik_done"], "hal_done": stats["hal_done"],
            "infer_ms_mean": avg(stats["infer_ms"]), "infer_ms_p95": p95(stats["infer_ms"]),
            "ik_ms_mean": avg(stats["ik_ms"]), "hal_ms_mean": avg(stats["hal_ms"]),
            "pipeline_fps": fps, "seconds": round(el, 2),
            "realtime_ok": bool(infer_p95 <= 100 and fps >= 10),
            "verdict": ("本机 CPU 不适合实时手势（infer p95 >100ms / fps<10）"
                        if not (infer_p95 <= 100 and fps >= 10) else "达到实时判据"),
            "errors": stats["errors"][:5],
            "boundary": "常驻 worker + tracker 复用 + 三线程；loopback 仿真，真机需标定"}


