# -*- coding: utf-8 -*-
"""hand_onnx_worker — 常驻 ONNX 手部推理进程（模型只加载一次）。

stdin/stdout JSONL 协议同 hand_tracker_worker.py：
  {"cmd":"video","path":...,"stride":1,"max_fps":0}
  → {"type":"ready"} / {"type":"frame","i":..,"ts":..,"infer_ms":..,"landmarks":[...]} / {"type":"done"}
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
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)


def emit(obj):
    sys.stdout.write(json.dumps(obj, ensure_ascii=False) + "\n")
    sys.stdout.flush()


def main():
    from gbt_allinone.tentacle import hand_onnx as HO
    import cv2
    # 预热模型（只加载一次）
    t = time.perf_counter()
    HO._load()
    init_ms = (time.perf_counter() - t) * 1000.0
    emit({"type": "ready", "backend": "opencv-dnn-onnx", "init_ms": round(init_ms, 2)})
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
                emit({"type": "error", "error": "打不开视频", "path": path}); continue
            i = emitted = 0
            last_ts = 0.0
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
                r = HO.detect(frame)
                emit({"type": "frame", "i": i, "ts": round(ts, 4),
                      "infer_ms": r.get("infer_ms"), "landmarks": (r["hands"][0]["landmarks"] if r["hands"] else []),
                      "worker_t": round((time.perf_counter() - t0) * 1000.0, 2)})
                emitted += 1
            cap.release()
            emit({"type": "done", "frames": i, "emitted": emitted,
                  "seconds": round(time.perf_counter() - t0, 3)})
            continue
        emit({"type": "error", "error": "未知 cmd: %r" % op})


if __name__ == "__main__":
    main()
