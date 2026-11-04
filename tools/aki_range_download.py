# -*- coding: utf-8 -*-
"""aki_range_download — GitHub release 大文件分块并发下载（Range）。"""
from __future__ import annotations

import concurrent.futures
import hashlib
import os
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WS = os.environ.get("GBT_WS") or r"C:\Users\Lenovo E14 Gen 5\Documents\deepseek-harness\default-workspace\GBTxiaotudouV8-Commander"
sys.path.insert(0, os.path.join(WS, "vendor", "pylibs"))
import requests  # noqa: E402

BASE = "https://github.com/shuiyue-cmyk/ComfyUI-aki-mirror/releases/download/v3.2"
PARTS = [
    ("ComfyUI-aki-v3.2.7z.part001", 1992294400,
     "7BC7C21174488355EB549471E7DF028114482A2F80296A1DEF2A1AEFA74E3FB5"),
    ("ComfyUI-aki-v3.2.7z.part002", 1004315871,
     "A5549F9A24546B876B00A0CDE9A0CC09CEF73713AB43501F8054AC6C7FBD049D"),
]
OUT = os.path.join(WS, "vendor", "aki-v3.2")
CHUNK = 32 * 1024 * 1024
WORKERS = 8


def fetch(session, url, start, end, path):
    for attempt in range(8):
        try:
            r = session.get(url, headers={"Range": "bytes=%d-%d" % (start, end)},
                            timeout=120, stream=True)
            if r.status_code not in (200, 206):
                raise RuntimeError("HTTP %s" % r.status_code)
            data = r.content
            if len(data) < (end - start + 1) and r.status_code == 206:
                raise RuntimeError("short range %d" % len(data))
            with open(path, "wb") as f:
                f.write(data)
            return len(data)
        except Exception:
            time.sleep(1 + attempt)
    raise RuntimeError("chunk failed %d-%d" % (start, end))


def main():
    os.makedirs(OUT, exist_ok=True)
    for name, total, sha in PARTS:
        url = BASE + "/" + name
        final = os.path.join(OUT, name)
        if os.path.isfile(final) and os.path.getsize(final) == total:
            print("skip", name)
            continue
        cdir = os.path.join(OUT, "." + name + ".chunks")
        os.makedirs(cdir, exist_ok=True)
        ranges = [(i, min(i + CHUNK - 1, total - 1)) for i in range(0, total, CHUNK)]
        print(name, "chunks", len(ranges), flush=True)
        done = 0
        with concurrent.futures.ThreadPoolExecutor(max_workers=WORKERS) as ex:
            futs = []
            for i, (s, e) in enumerate(ranges):
                p = os.path.join(cdir, "%05d" % i)
                futs.append(ex.submit(fetch, requests.Session(), url, s, e, p))
            for f in concurrent.futures.as_completed(futs):
                done += f.result()
                if len(futs) and done % (256 * 1024 * 1024) < CHUNK:
                    print("  progress %d/%d MB" % (done // 1048576, total // 1048576), flush=True)
        with open(final, "wb") as out:
            for i, _ in enumerate(ranges):
                with open(os.path.join(cdir, "%05d" % i), "rb") as f:
                    while True:
                        b = f.read(8 * 1024 * 1024)
                        if not b:
                            break
                        out.write(b)
        h = hashlib.sha256()
        with open(final, "rb") as f:
            for b in iter(lambda: f.read(8 * 1024 * 1024), b""):
                h.update(b)
        got = h.hexdigest().upper()
        print(name, os.path.getsize(final), "sha", got, "ok", got == sha, flush=True)


if __name__ == "__main__":
    main()


