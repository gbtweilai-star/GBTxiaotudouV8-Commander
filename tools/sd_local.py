#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""sd_local —— 本机真·扩散生图（stable-diffusion.cpp 后端，纯 CPU，不用 torch）。

为什么是它：leejet/stable-diffusion.cpp ★7.8k，C++ 实现，支持 SD/Flux/Qwen-Image，
**不需要 Python、不需要 CUDA**。这是这台设备上唯一可能真跑起来的生图路径。

边界（先写死，免得又吹）：
  · 内存只有 4 GB ⇒ 只能用 512×512、量化权重（Q4）、步数压到 10–20
  · 纯 CPU ⇒ 每张预计 3–10 分钟，不是秒级
  · 第一次用前必须：编译 + 放好模型文件

用法：
    python3 tools/sd_local.py --check
    python3 tools/sd_local.py "孙悟空的背影，水墨" --steps 14 --size 512x512
"""
import argparse, os, subprocess, sys, time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BIN = "/var/minis/workspace/sdcpp/build/bin/sd"
MODELS = [os.path.join(ROOT, "models", "sd15-q4.gguf"),
          "/var/minis/workspace/models/sd15-q4.gguf"]
OUT = "/var/minis/attachments/sd_local.png"


def model():
    for m in MODELS:
        if os.path.exists(m):
            return m
    return None


def check():
    ok = os.path.exists(BIN)
    m = model()
    print("二进制 %s %s" % (BIN, "在" if ok else "缺（还没编译完）"))
    print("模型   %s" % (m or "缺（放到 models/sd15-q4.gguf）"))
    if m:
        print("模型大小 %.1f GB" % (os.path.getsize(m) / 1024 ** 3))
    return 0 if (ok and m) else 2


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("prompt", nargs="*")
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--steps", type=int, default=14)
    ap.add_argument("--size", default="512x512")
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--out", default=OUT)
    a = ap.parse_args()

    if a.check or not a.prompt:
        return check()

    m = model()
    if not os.path.exists(BIN) or not m:
        print("还缺东西：先编译 stable-diffusion.cpp 并把量化模型放到 models/sd15-q4.gguf")
        return 2

    w, h = a.size.lower().split("x")
    cmd = [BIN, "-m", m, "-p", " ".join(a.prompt), "-W", w, "-H", h,
           "--steps", str(a.steps), "-s", str(a.seed), "-o", a.out,
           "-t", "4", "--vae-tiling"]
    t0 = time.time()
    r = subprocess.run(cmd, capture_output=True, text=True)
    dt = time.time() - t0
    if r.returncode != 0 or not os.path.exists(a.out):
        print("失败（%.1fs）：%s" % (dt, (r.stderr or r.stdout)[-400:]))
        return 3
    print("出图 %s · %s · %.1fs" % (a.out, a.size, dt))
    return 0


if __name__ == "__main__":
    sys.exit(main())
