# -*- coding: utf-8 -*-
"""hand_onnx_chunk_worker — 单 chunk 推理子进程（用于进程回收）。"""
from __future__ import annotations

import argparse
import json
import os
import statistics
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PYLIBS = os.environ.get("GBT_PYLIBS") or os.path.join(ROOT, "vendor", "pylibs")
if not os.path.isdir(PYLIBS):
    PYLIBS = os.path.join(os.path.dirname(ROOT), "vendor", "pylibs")
if PYLIBS not in sys.path:
    sys.path.insert(0, PYLIBS)
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--video", required=True)
    ap.add_argument("--start", type=int, default=0)
    ap.add_argument("--count", type=int, default=60)
    ap.add_argument("--landmarks-out", default="")
    args = ap.parse_args()
    import cv2
    from gbt_allinone.tentacle import hand_onnx as HO


    cap = cv2.VideoCapture(args.video)
    if args.start:
        cap.set(cv2.CAP_PROP_POS_FRAMES, args.start)
    t0 = time.perf_counter()
    HO._load()
    load_ms = (time.perf_counter() - t0) * 1000.0
    ms = []
    frames_out = []
    for _ in range(args.count):
        ok, frame = cap.read()
        if not ok:
            break
        t = time.perf_counter()
        r = HO.detect(frame)
        ms.append((time.perf_counter() - t) * 1000.0)
        if args.landmarks_out and r.get("hands"):
            frames_out.append({"landmarks": r["hands"][0]["landmarks"]})
    cap.release()
    if args.landmarks_out:
        with open(args.landmarks_out, "w", encoding="utf-8") as f:
            json.dump(frames_out, f, ensure_ascii=False)
    print(json.dumps({"ok": bool(ms), "start": args.start, "frames": len(ms), "landmarks_file": args.landmarks_out,
                      "load_ms": round(load_ms, 2),
                      "mean_ms": round(statistics.mean(ms), 2) if ms else None,
                      "p95_ms": round(sorted(ms)[int(len(ms) * 0.95)], 2) if ms else None,
                      "seconds": round(time.perf_counter() - t0, 2)}, ensure_ascii=False))


if __name__ == "__main__":
    main()

