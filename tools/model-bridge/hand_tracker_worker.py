# -*- coding: utf-8 -*-
"""hand_tracker_worker — 常驻手部推理进程（模型只初始化一次）。

协议：stdin/stdout JSON Lines。
  {"cmd":"ping"} -> {"type":"pong"}
  {"cmd":"video","path":"...","stride":1,"max_fps":0} ->
      {"type":"ready"} 一次
      {"type":"frame","i":0,"ts":0.0,"infer_ms":..,"landmarks":[...]} 每帧
      {"type":"done","frames":..}
  {"cmd":"quit"}

由 hand_pipeline.py 拉起；stderr 留给 MediaPipe/absl 日志。
"""
from __future__ import annotations

import json
import os
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PYLIBS = os.path.join(ROOT, "vendor", "pylibs")
if not os.path.isdir(PYLIBS):
    PYLIBS = os.path.join(os.path.dirname(ROOT), "vendor", "pylibs")
if PYLIBS not in sys.path:
    sys.path.insert(0, PYLIBS)
os.environ.setdefault("MPLCONFIGDIR", os.path.join(ROOT, ".scratch", "lead", "mpl"))
os.environ.setdefault("GLOG_minloglevel", "2")


def emit(obj):
    sys.stdout.write(json.dumps(obj, ensure_ascii=False) + "\n")
    sys.stdout.flush()


def main():
    import cv2
    import mediapipe as mp
    hands = mp.solutions.hands.Hands(
        static_image_mode=False, max_num_hands=2, model_complexity=0,
        min_detection_confidence=0.35, min_tracking_confidence=0.35)
    emit({"type": "ready", "mediapipe": getattr(mp, "__version__", "?")})
    try:
        for line in sys.stdin:
            line = line.strip()
            if not line:
                continue
            try:
                cmd = json.loads(line)
            except Exception as e:  # noqa: BLE001
                emit({"type": "error", "error": "bad json: %s" % e}); continue
            op = cmd.get("cmd")
            if op == "quit":
                emit({"type": "bye"}); break
            if op == "ping":
                emit({"type": "pong"}); continue
            if op == "video":
                path = cmd.get("path") or ""
                stride = max(1, int(cmd.get("stride", 1)))
                fps_cap = max(0.0, float(cmd.get("max_fps", 0)))
                cap = cv2.VideoCapture(path)
                if not cap.isOpened():
                    emit({"type": "error", "error": "打不开视频: %s" % path, "path": path}); continue
                i = last_ts = 0
                emitted = 0
                t0 = time.perf_counter()
                while True:
                    ok, frame = cap.read()
                    if not ok:
                        break
                    i += 1
                    ts = cap.get(cv2.CAP_PROP_POS_MSEC) / 1000.0
                    if fps_cap and emitted and (ts - last_ts) < (1.0 / fps_cap):
                        continue
                    if (i - 1) % stride:
                        continue
                    last_ts = ts
                    t = time.perf_counter()
                    res = hands.process(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
                    infer_ms = (time.perf_counter() - t) * 1000.0
                    lm = []
                    if res.multi_hand_landmarks:
                        lm = [[round(float(p.x), 6), round(float(p.y), 6), round(float(p.z), 6)]
                              for p in res.multi_hand_landmarks[0].landmark]
                    emit({"type": "frame", "i": i, "ts": round(ts, 4),
                          "infer_ms": round(infer_ms, 2), "landmarks": lm,
                          "worker_t": round((time.perf_counter() - t0) * 1000.0, 2)})
                    emitted += 1
                cap.release()
                emit({"type": "done", "frames": i, "emitted": emitted,
                      "seconds": round(time.perf_counter() - t0, 3)})
                continue
            emit({"type": "error", "error": "未知 cmd: %r" % op})
    finally:
        try:
            hands.close()
        except Exception:  # noqa: BLE001
            pass


if __name__ == "__main__":
    main()
