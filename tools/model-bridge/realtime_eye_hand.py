# -*- coding: utf-8 -*-
"""realtime_eye_hand.py — 眼手脑同一拍：采集线程持续看，控制环边看边动。

不是 see -> 子进程 -> click 的两段式；这里：
  - 采集线程 mss 连续抓屏（ring/latest，不阻塞动作）
  - 控制环只读"最新一帧"，算误差，小步移动，立刻再取下一帧
  - 动作期间采集不停；所有动作都是闭环微步，不是一次盲点

用法：
  python realtime_eye_hand.py --target red --seconds 6 --dry-run
  python realtime_eye_hand.py --target red --seconds 6 --gain .35 --max-step 60
输出 JSON：fps、动作次数、平均视觉延迟、最终误差、是否收敛。
"""
from __future__ import annotations

import argparse
import json
import threading
import time

import mss
import numpy as np
import pyautogui

pyautogui.FAILSAFE = True
pyautogui.PAUSE = 0.0


class Grabber(threading.Thread):
    def __init__(self, monitor: int = 1):
        super().__init__(daemon=True)
        self.monitor = monitor
        self.lock = threading.Lock()
        self.latest = None
        self.stamp = 0.0
        self.seq = 0
        self.fps = 0.0
        self.running = True

    def run(self):
        with mss.mss() as s:
            mon = s.monitors[self.monitor]
            self.left, self.top = mon["left"], mon["top"]
            self.w, self.h = mon["width"], mon["height"]
            n, t0 = 0, time.perf_counter()
            while self.running:
                raw = s.grab(mon)
                arr = np.frombuffer(raw.bgra, dtype=np.uint8).reshape(self.h, self.w, 4)
                rgb = arr[:, :, :3][:, :, ::-1].copy()
                now = time.perf_counter()
                with self.lock:
                    self.latest, self.stamp = rgb, now
                    self.seq += 1
                n += 1
                if now - t0 >= 1.0:
                    self.fps = n / (now - t0)
                    n, t0 = 0, now

    def frame(self):
        with self.lock:
            return self.latest, self.stamp, self.seq

    def stop(self):
        self.running = False


def detect_red(frame: np.ndarray, step: int = 2):
    """Red target centroid in screen coords; no cv2, pure numpy."""
    small = frame[::step, ::step]
    r, g, b = small[:, :, 0], small[:, :, 1], small[:, :, 2]
    mask = (r > 180) & (g < 95) & (b < 95)
    ys, xs = np.nonzero(mask)
    if len(xs) < 30:
        return None
    return float(xs.mean() * step), float(ys.mean() * step), float(len(xs))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--target", default="red")
    ap.add_argument("--seconds", type=float, default=6.0)
    ap.add_argument("--gain", type=float, default=0.35)
    ap.add_argument("--max-step", type=float, default=60.0)
    ap.add_argument("--deadband", type=float, default=8.0)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--monitor", type=int, default=1)
    args = ap.parse_args()

    g = Grabber(args.monitor)
    g.start()
    time.sleep(1.5)
    if g.latest is None:
        print(json.dumps({"ok": False, "error": "抓不到屏幕"}, ensure_ascii=False))
        return 2

    t0 = time.perf_counter()
    actions = 0
    lat = []
    errs = []
    final = None
    last_seq = -1
    while time.perf_counter() - t0 < args.seconds:
        frame, stamp, seq = g.frame()
        if frame is None or seq == last_seq:
            time.sleep(0.001)
            continue
        last_seq = seq
        det = detect_red(frame) if args.target == "red" else None
        if not det:
            time.sleep(0.005)
            continue
        tx, ty, area = det
        px, py = pyautogui.position()
        # 屏幕坐标 = monitor 原点 + 图像坐标
        sx, sy = g.left + tx, g.top + ty
        ex, ey = sx - px, sy - py
        err = float((ex * ex + ey * ey) ** 0.5)
        errs.append(err)
        lat.append((time.perf_counter() - stamp) * 1000.0)
        final = {"target": [round(sx, 1), round(sy, 1)], "cursor": [px, py],
                 "error_px": round(err, 2), "area": round(area)}
        if err <= args.deadband:
            # 已到位；仍持续看，不盲动
            time.sleep(0.004)
            continue
        if not args.dry_run:
            k = args.gain
            dx = max(-args.max_step, min(args.max_step, ex * k))
            dy = max(-args.max_step, min(args.max_step, ey * k))
            pyautogui.moveRel(dx, dy, duration=0)
        actions += 1
        time.sleep(0.004)

    g.stop()
    actions_fps = actions / max(1e-6, (time.perf_counter() - t0))
    out = {"ok": True, "dry_run": args.dry_run, "target": args.target,
           "seconds": args.seconds, "capture_fps": round(g.fps, 2),
           "actions": actions, "action_rate_hz": round(actions_fps, 2),
           "vision_latency_ms_mean": round(float(np.mean(lat)), 2) if lat else None,
           "vision_latency_ms_p95": round(float(np.percentile(lat, 95)), 2) if lat else None,
           "final": final, "min_error_px": round(min(errs), 2) if errs else None,
           "converged": bool(final and final["error_px"] <= max(args.deadband * 2, 16)),
           "note": "capture 线程持续跑；动作是小步闭环，不是 see 子进程后再 click"}
    print(json.dumps(out, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

