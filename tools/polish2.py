#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""polish2 —— 第二轮打磨：局部对比（clarity）+ 分离色调 + 边缘感知锐化。

与 polish.py 的区别：那一版是全图一刀切；这一版**分区域**做事，避免把背景也一起提锐。

三个动作都可测：
  ① 局部对比：L' = L + a·(L − blur(L))，a 小（0.22），只推中间调 ⇒ 立体不发灰
  ② 分离色调：暗部推冷（+B）、亮部推暖（+R）⇒ 电影常用的"冷暗暖亮"
  ③ 边缘感知锐化：锐化量按边缘强度加权 ⇒ 平滑处不放大噪点

用法： python3 tools/polish2.py in.jpg --out out.png --scale 1.5
"""
import argparse
from PIL import Image, ImageFilter, ImageChops, ImageEnhance, ImageStat
import numpy as np


def local_contrast(L, radius=28, amount=0.22, midtone_only=True):
    a = np.asarray(L, dtype=np.float32)
    blur = np.asarray(L.filter(ImageFilter.GaussianBlur(radius)), dtype=np.float32)
    hi = a - blur
    if midtone_only:
        # 中间调权重：两端压低，避免高光死白、暗部起灰
        w = np.clip(1.0 - np.abs(a / 255.0 - 0.5) * 2.0, 0.15, 1.0)
        hi *= w
    out = np.clip(a + hi * amount, 0, 255).astype(np.uint8)
    return Image.fromarray(out, "L")


def split_tone(im, shadow=(0.0, 0.0, 1.0), highlight=(1.0, 0.35, 0.0),
               strength=0.05, pivot=118):
    a = np.asarray(im, dtype=np.float32)
    lum = a.mean(axis=2, keepdims=True)
    t = np.clip((lum - pivot) / 120.0, -1, 1)
    warm = np.clip(t, 0, 1) * strength * 255
    cool = np.clip(-t, 0, 1) * strength * 255
    warm2 = warm[..., 0] if warm.ndim == 3 else warm
    cool2 = cool[..., 0] if cool.ndim == 3 else cool
    a[..., 0] = np.clip(a[..., 0] + warm2 * highlight[0] - cool2 * shadow[0], 0, 255)
    a[..., 2] = np.clip(a[..., 2] + warm2 * highlight[2] - cool2 * shadow[2], 0, 255)
    return Image.fromarray(np.clip(a, 0, 255).astype(np.uint8), "RGB")


def edge_aware_sharpen(L, amount=0.55, radius=1.1, thresh=8):
    a = np.asarray(L, dtype=np.float32)
    blur = np.asarray(L.filter(ImageFilter.GaussianBlur(radius)), dtype=np.float32)
    edge = np.abs(a - blur)
    mask = np.clip((edge - thresh) / 40.0, 0, 1)
    out = np.clip(a + (a - blur) * amount * mask, 0, 255).astype(np.uint8)
    return Image.fromarray(out, "L")


def run(src, dst, scale=1.5, lc=0.22, tone=0.05, sharp=0.55, grain=2):
    im = Image.open(src).convert("RGB")
    if scale != 1:
        im = im.resize((int(im.size[0] * scale), int(im.size[1] * scale)), Image.LANCZOS)
    lab = im.convert("LAB")
    L, A, B = lab.split()
    L = local_contrast(L, amount=lc)
    L = edge_aware_sharpen(L, amount=sharp)
    im = Image.merge("LAB", (L, A, B)).convert("RGB")
    im = split_tone(im, strength=tone)
    im = ImageEnhance.Color(im).enhance(1.05)
    if grain:
        n = Image.effect_noise(im.size, grain).convert("L")
        n3 = Image.merge("RGB", (n, n, n))
        im = Image.blend(im, ImageChops.add(im, n3, scale=1, offset=-2), 0.06)
    im.save(dst, "PNG")
    return im


def stats(p, ref_w=627):
    im = Image.open(p).convert("L")
    if im.size[0] != ref_w:
        im = im.resize((ref_w, int(im.size[1] * ref_w / im.size[0])), Image.LANCZOS)
    a = np.asarray(im, dtype=np.float32)
    blur = np.asarray(im.filter(ImageFilter.GaussianBlur(3)), dtype=np.float32)
    hf = float(np.abs(a - blur).mean())            # 高频能量≈可见细节
    e = im.filter(ImageFilter.FIND_EDGES)
    edge = sum(1 for v in e.getdata() if v > 40) / (im.size[0] * im.size[1])
    st = ImageStat.Stat(im)
    return {"边": round(edge, 4), "高频": round(hf, 2), "均值": round(st.mean[0], 1),
            "标准差": round(st.stddev[0], 1)}


def crop_pair(a, b, out, box=(0.28, 0.10, 0.66, 0.42), size=430):
    A = Image.open(a).convert("RGB"); B = Image.open(b).convert("RGB")
    def cut(im):
        w, h = im.size
        return im.crop((int(box[0]*w), int(box[1]*h), int(box[2]*w), int(box[3]*h))).resize((size, size), Image.LANCZOS)
    ca, cb = cut(A), cut(B)
    c = Image.new("RGB", (size*2+10, size), (8, 10, 14))
    c.paste(ca, (0, 0)); c.paste(cb, (size+10, 0)); c.save(out, "PNG")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("src"); ap.add_argument("--out"); ap.add_argument("--scale", type=float, default=1.5)
    ap.add_argument("--lc", type=float, default=0.22); ap.add_argument("--sharp", type=float, default=0.55)
    a = ap.parse_args()
    dst = a.out or a.src.rsplit(".", 1)[0] + "_p2.png"
    run(a.src, dst, a.scale, a.lc, 0.05, a.sharp)
    cp = dst.replace(".png", "_crop.png")
    crop_pair(a.src, dst, cp)
    print("产物 %s · %s" % (dst, Image.open(dst).size))
    print("原图  ", stats(a.src))
    print("打磨二", stats(dst))
    print("对照  %s" % cp)
