# -*- coding: utf-8 -*-
"""hand_onnx_chunked_proc — 真进程回收：每个 chunk 起独立子进程。"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PYLIBS = os.environ.get("GBT_PYLIBS") or os.path.join(ROOT, "vendor", "pylibs")
if not os.path.isdir(PYLIBS):
    PYLIBS = os.path.join(os.path.dirname(ROOT), "vendor", "pylibs")
WORKER = os.path.join(ROOT, "tools", "model-bridge", "hand_onnx_chunk_worker.py")
PY = sys.executable


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--video", required=True)
    ap.add_argument("--frames", type=int, default=150)
    ap.add_argument("--chunk", type=int, default=60)
    args = ap.parse_args()
    env = dict(os.environ)
    env["GBT_PYLIBS"] = PYLIBS
    chunks = []
    t_all = time.perf_counter()
    done = 0
    while done < args.frames:
        n = min(args.chunk, args.frames - done)
        r = subprocess.run([PY, "-B", "-X", "utf8", WORKER, "--video", args.video,
                            "--start", str(done), "--count", str(n)],
                           capture_output=True, text=True, timeout=300, env=env)
        line = (r.stdout or "").strip().splitlines()[-1] if (r.stdout or "").strip() else "{}"
        try:
            d = json.loads(line)
        except Exception:  # noqa: BLE001
            d = {"ok": False, "error": line[-200:]}
        d["chunk"] = len(chunks) + 1
        chunks.append(d)
        if not d.get("ok"):
            break
        done += int(d.get("frames") or 0)
    el = time.perf_counter() - t_all
    all_frames = sum(int(c.get("frames") or 0) for c in chunks)
    print(json.dumps({"ok": done >= args.frames, "op": "chunked_proc", "frames": all_frames,
                      "requested": args.frames, "chunk": args.chunk,
                      "seconds": round(el, 2), "fps": round(all_frames / max(el, 1e-6), 2),
                      "chunks": chunks}, ensure_ascii=False))


if __name__ == "__main__":
    main()
