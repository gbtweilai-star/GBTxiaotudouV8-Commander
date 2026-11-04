# -*- coding: utf-8 -*-
"""weight_fusion_sd15 — 把两个兼容 SD1.5 UNet 权重做按层加权融合，产出我们自己的本地权重。"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WS = os.path.dirname(ROOT)
PYLIBS = os.path.join(WS, "vendor", "pylibs")
if PYLIBS not in sys.path:
    sys.path.insert(0, PYLIBS)


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for b in iter(lambda: f.read(16 * 1024 * 1024), b""):
            h.update(b)
    return h.hexdigest()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", required=True, help="Realistic Vision / SD1.5 single file")
    ap.add_argument("--other", required=True, help="Tiny-SD diffusers dir")
    ap.add_argument("--out", required=True)
    ap.add_argument("--alpha", type=float, default=0.5)
    ap.add_argument("--prompt", default="a red apple on a wooden table, photo")
    ap.add_argument("--size", type=int, default=256)
    ap.add_argument("--steps", type=int, default=8)
    args = ap.parse_args()
    import torch
    from diffusers import StableDiffusionPipeline

    t0 = time.time()
    print("load base", flush=True)
    if os.path.isdir(args.base):
        base = StableDiffusionPipeline.from_pretrained(args.base, torch_dtype=torch.float32, local_files_only=True)
    else:
        base = StableDiffusionPipeline.from_single_file(args.base, torch_dtype=torch.float32)
    print("load other", flush=True)
    other = StableDiffusionPipeline.from_pretrained(args.other, torch_dtype=torch.float32)
    bu = base.unet.state_dict()
    ou = other.unet.state_dict()
    common = [k for k in bu if k in ou and bu[k].shape == ou[k].shape]
    print("keys base=%d other=%d common=%d" % (len(bu), len(ou), len(common)), flush=True)
    merged = {}
    for k in bu:
        if k in common:
            merged[k] = (1.0 - args.alpha) * bu[k] + args.alpha * ou[k]
        else:
            merged[k] = bu[k]
    base.unet.load_state_dict(merged, strict=True)
    os.makedirs(args.out, exist_ok=True)
    base.save_pretrained(args.out)
    # 记融合证据
    meta = {"base": args.base, "other": args.other, "alpha": args.alpha,
            "common_keys": len(common), "base_keys": len(bu), "other_keys": len(ou),
            "base_sha256": sha256(os.path.join(args.base, "unet", "diffusion_pytorch_model.safetensors")) if os.path.isdir(args.base) else sha256(args.base), "out": args.out,
            "created": time.strftime("%Y-%m-%dT%H:%M:%S")}
    json.dump(meta, open(os.path.join(args.out, "fusion.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=2)
    # 融合权重真出图
    base.to("cpu")
    base.enable_attention_slicing()
    gen = torch.Generator(device="cpu").manual_seed(7)
    t1 = time.time()
    img = base(prompt=args.prompt, num_inference_steps=args.steps,
               guidance_scale=7.0, width=args.size, height=args.size,
               generator=gen).images[0]
    out_png = os.path.join(args.out, "fused-preview.png")
    img.save(out_png)
    meta["preview"] = out_png
    meta["load_s"] = round(t1 - t0, 2)
    meta["generation_s"] = round(time.time() - t1, 2)
    json.dump(meta, open(os.path.join(args.out, "fusion.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=2)
    print(json.dumps(meta, ensure_ascii=False))


if __name__ == "__main__":
    main()


