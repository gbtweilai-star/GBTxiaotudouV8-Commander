# -*- coding: utf-8 -*-
"""hand_onnx_chunked — 每 N 帧回收一次模型，避免长跑退化。

用法：
  py tools/model-bridge/hand_onnx_chunked.py --video ... --frames 150 --chunk 60

每 chunk：释放 hand_onnx 全局模型 → _load() 重建 → 处理 N 帧。
输出每个 chunk 的耗时/RSS/帧均延迟，以及总计。
"""
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
    ap.add_argument("--frames", type=int, default=150)
    ap.add_argument("--chunk", type=int, default=60)
    args = ap.parse_args()
    import cv2
    import psutil
    from gbt_allinone.tentacle import hand_onnx as HO

    proc = psutil.Process()
    cap = cv2.VideoCapture(args.video)
    chunks = []
    all_ms = []
    i = 0
    t_all = time.perf_counter()
    while i < args.frames:
        # 回收：释放旧模型，重建（等同进程回收的效果）
        HO._palm = None
        HO._pose = None
        t0 = time.perf_counter()
        HO._load()
        load_ms = (time.perf_counter() - t0) * 1000.0
        ms = []
        for _ in range(args.chunk):
            if i >= args.frames:
                break
            ok, frame = cap.read()
            if not ok:
                break
            t = time.perf_counter()
            HO.detect(frame)
            dt = (time.perf_counter() - t) * 1000.0
            ms.append(dt); all_ms.append(dt); i += 1
        chunks.append({"chunk": len(chunks) + 1, "frames": len(ms),
                       "load_ms": round(load_ms, 2),
                       "mean_ms": round(statistics.mean(ms), 2) if ms else None,
                       "p95_ms": round(sorted(ms)[int(len(ms) * 0.95)], 2) if ms else None,
                       "rss_mb": round(proc.memory_info().rss / 1048576.0, 1)})
    cap.release()
    el = time.perf_counter() - t_all
    print(json.dumps({"ok": True, "video": args.video, "frames": i, "chunk": args.chunk,
                      "seconds": round(el, 2), "fps": round(i / max(el, 1e-6), 2),
                      "mean_ms": round(statistics.mean(all_ms), 2) if all_ms else None,
                      "p95_ms": round(sorted(all_ms)[int(len(all_ms) * 0.95)], 2) if all_ms else None,
                      "chunks": chunks, "rss_end_mb": round(proc.memory_info().rss / 1048576.0, 1)},
                     ensure_ascii=False))


if __name__ == "__main__":
    main()

