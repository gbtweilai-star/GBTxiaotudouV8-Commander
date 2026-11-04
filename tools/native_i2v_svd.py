# -*- coding: utf-8 -*-
"""native_i2v_svd — 本地 Stable Video Diffusion XT 图生视频（CPU fp16）。

用法：
  python tools/native_i2v_svd.py --image in.png --out out.mp4 --frames 14 --size 576x1024

模型目录：vendor/hf/svd-xt-fp16（fp16 分片；不放 ComfyUI）。
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WS = os.path.dirname(ROOT)
PYLIBS = os.path.join(WS, "vendor", "pylibs")
MODEL = os.path.join(WS, "vendor", "hf", "svd-xt-fp16")
FFMPEG = os.path.join(WS, "vendor", "ffmpeg", "bin", "ffmpeg.exe")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--image", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--frames", type=int, default=14)
    ap.add_argument("--width", type=int, default=576)
    ap.add_argument("--height", type=int, default=1024)
    ap.add_argument("--fps", type=int, default=8)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--motion", type=int, default=127)
    ap.add_argument("--steps", type=int, default=25)
    args = ap.parse_args()
    if PYLIBS not in sys.path:
        sys.path.insert(0, PYLIBS)
    import torch
    from diffusers import StableVideoDiffusionPipeline
    from PIL import Image

    t0 = time.time()
    dtype = torch.float16 if torch.cuda.is_available() else torch.float32
    pipe = StableVideoDiffusionPipeline.from_pretrained(
        MODEL, torch_dtype=dtype, local_files_only=True, variant="fp16")
    pipe.to("cpu" if not torch.cuda.is_available() else "cuda")
    pipe.enable_attention_slicing()
    load_s = round(time.time() - t0, 2)
    image = Image.open(args.image).convert("RGB")
    gen = torch.Generator(device="cpu").manual_seed(args.seed)
    t1 = time.time()
    frames = pipe(image, num_frames=args.frames, decode_chunk_size=1,
                  motion_bucket_id=args.motion, noise_aug_strength=0.02,
                  height=args.height, width=args.width, num_inference_steps=args.steps, generator=gen).frames[0]
    gen_s = round(time.time() - t1, 2)
    tmp = args.out + ".frames"
    os.makedirs(tmp, exist_ok=True)
    for i, fr in enumerate(frames):
        fr.save(os.path.join(tmp, "f%03d.png" % i))
    cmd = [FFMPEG, "-y", "-hide_banner", "-loglevel", "error",
           "-framerate", str(args.fps), "-i", os.path.join(tmp, "f%03d.png"),
           "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
           "-pix_fmt", "yuv420p", "-movflags", "+faststart", args.out]
    subprocess.run(cmd, check=True)
    print(json.dumps({"ok": True, "image": args.image, "out": args.out,
                      "frames": len(frames), "size": [args.width, args.height],
                      "fps": args.fps, "load_s": load_s, "generation_s": gen_s,
                      "engine": "StableVideoDiffusionPipeline CPU fp32（本地 SVD-XT）"},
                     ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())



