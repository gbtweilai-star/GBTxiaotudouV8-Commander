# -*- coding: utf-8 -*-
"""hf_range_download — HuggingFace 大文件分块并发下载（Range），用于本地权重。"""
from __future__ import annotations

import concurrent.futures
import os
import sys
import time

WS = r"C:\Users\Lenovo E14 Gen 5\Documents\deepseek-harness\default-workspace\GBTxiaotudouV8-Commander"
sys.path.insert(0, os.path.join(WS, "vendor", "pylibs"))
import requests  # noqa: E402

URL = ("https://huggingface.co/SG161222/Realistic_Vision_V5.1_noVAE/"
       "resolve/main/unet/diffusion_pytorch_model.safetensors")
OUT = os.path.join(WS, "vendor", "hf", "rv51-diffusers", "unet",
                   "diffusion_pytorch_model.safetensors")
TOTAL = 3438167536
CHUNK = 32 * 1024 * 1024
WORKERS = 8


def fetch(session, start, end, path):
    for attempt in range(8):
        try:
            r = session.get(URL, headers={"Range": "bytes=%d-%d" % (start, end)},
                            timeout=180, stream=True)
            if r.status_code not in (200, 206):
                raise RuntimeError("HTTP %s" % r.status_code)
            data = r.content
            if r.status_code == 206 and len(data) != end - start + 1:
                raise RuntimeError("short")
            with open(path, "wb") as f:
                f.write(data)
            return len(data)
        except Exception:
            time.sleep(1 + attempt)
    raise RuntimeError("chunk failed")


def main():
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    if os.path.isfile(OUT) and os.path.getsize(OUT) == TOTAL:
        print("skip")
        return
    cdir = OUT + ".chunks"
    os.makedirs(cdir, exist_ok=True)
    ranges = [(i, min(i + CHUNK - 1, TOTAL - 1)) for i in range(0, TOTAL, CHUNK)]
    print("chunks", len(ranges), flush=True)
    done = 0
    with concurrent.futures.ThreadPoolExecutor(max_workers=WORKERS) as ex:
        futs = [ex.submit(fetch, requests.Session(), s, e, os.path.join(cdir, "%05d" % i))
                for i, (s, e) in enumerate(ranges)]
        for f in concurrent.futures.as_completed(futs):
            done += f.result()
            if done // (256 * 1024 * 1024) != (done - CHUNK) // (256 * 1024 * 1024):
                print("progress", done // 1048576, "MB", flush=True)
    with open(OUT, "wb") as o:
        for i, _ in enumerate(ranges):
            with open(os.path.join(cdir, "%05d" % i), "rb") as f:
                while True:
                    b = f.read(8 * 1024 * 1024)
                    if not b:
                        break
                    o.write(b)
    print("done", os.path.getsize(OUT), flush=True)


if __name__ == "__main__":
    main()
