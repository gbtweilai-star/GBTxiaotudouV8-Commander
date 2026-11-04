# -*- coding: utf-8 -*-
"""hand_onnx_profile — 长跑退化定位：单帧耗时 + RSS + 线程数 + 分段统计。

用法：
  py tools/model-bridge/hand_onnx_profile.py --video ... --frames 60
输出 JSON；每 10 帧打印一行进度。
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
    ap.add_argument("--frames", type=int, default=60)
    args = ap.parse_args()
    import cv2
    import psutil
    from gbt_allinone.tentacle import hand_onnx as HO

    proc = psutil.Process()
    cap = cv2.VideoCapture(args.video)
    rows = []
    t_all = time.perf_counter()
    while len(rows) < args.frames:
        ok, frame = cap.read()
        if not ok:
            break
        t = time.perf_counter()
        r = HO.detect(frame)
        ms = (time.perf_counter() - t) * 1000.0
        rows.append({"i": len(rows) + 1, "ms": ms, "rss_mb": proc.memory_info().rss / 1048576.0,
                     "threads": proc.num_threads(), "hands": len(r["hands"]),
                     "cpu": proc.cpu_percent(interval=None)})
        if len(rows) % 10 == 0:
            print("progress", len(rows), "ms", round(ms, 2), "rss", round(rows[-1]["rss_mb"], 1), flush=True)
    cap.release()
    el = time.perf_counter() - t_all
    ms = [r["ms"] for r in rows]
    n = len(rows)
    seg = max(1, n // 3)
    def stats(xs):
        return {"n": len(xs), "mean": round(statistics.mean(xs), 2),
                "median": round(statistics.median(xs), 2),
                "p95": round(sorted(xs)[int(len(xs) * 0.95)], 2),
                "max": round(max(xs), 2)}
    out = {"ok": True, "video": args.video, "frames": n, "seconds": round(el, 2),
           "fps": round(n / max(el, 1e-6), 2),
           "first": stats(ms[:seg]), "middle": stats(ms[seg:2 * seg]), "last": stats(ms[2 * seg:]),
           "rss_start_mb": round(rows[0]["rss_mb"], 1), "rss_end_mb": round(rows[-1]["rss_mb"], 1),
           "threads_start": rows[0]["threads"], "threads_end": rows[-1]["threads"],
           "all": stats(ms),
           "per_frame": rows}
    print(json.dumps(out, ensure_ascii=False))


if __name__ == "__main__":
    main()

