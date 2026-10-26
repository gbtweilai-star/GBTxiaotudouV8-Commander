#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""upscale_hi —— 把小图做到"看着清晰"：放大 + 亮度通道锐化 + 补颗粒 + 100% 对照。

为什么不是简单 LANCZOS：插值会糊边、还会把 JPEG 块放大成糊斑。
所以三步走：① LANCZOS 放大 ② 只在 LAB 的 L 通道做 USM（不动颜色，避免彩边）
③ 加极细颗粒（把"糊"打散成"细节感"，这是印刷业的常规做法）。
"""
import argparse, os
from PIL import Image, ImageFilter, ImageChops, ImageStat

def upscale(src, dst, width=2048, usm=(1.4, 55, 6), grain=3):
    im = Image.open(src).convert("RGB")
    w0, h0 = im.size
    scale = width / w0
    big = im.resize((width, int(h0 * scale)), Image.LANCZOS)

    lab = big.convert("LAB")
    L, A, B = lab.split()
    L = L.filter(ImageFilter.UnsharpMask(radius=usm[0], percent=usm[1], threshold=usm[2]))
    big = Image.merge("LAB", (L, A, B)).convert("RGB")

    if grain:
        import random
        random.seed(7)
        # 🔴 上一版用 ImageChops.add 把整体提亮、并叠满噪点；改成**只混 8%**，
        #    只为打散插值糊感，不改变影调。
        noise = Image.effect_noise(big.size, grain).convert("L")
        n3 = Image.merge("RGB", (noise, noise, noise))
        big = Image.blend(big, ImageChops.add(big, n3, scale=1, offset=-2), 0.08)

    big.save(dst, "PNG")
    return (w0, h0), big.size, os.path.getsize(dst)

def edge_density(p, ref_w=665):
    """清晰度必须**同尺寸比**：否则放大图边缘被拉散，数字会失真（上一版就吃了这个亏）。"""
    im = Image.open(p).convert("L")
    if im.size[0] != ref_w:
        im = im.resize((ref_w, int(im.size[1] * ref_w / im.size[0])), Image.LANCZOS)
    e = im.filter(ImageFilter.FIND_EDGES)
    return round(sum(1 for v in e.getdata() if v > 40) / (im.size[0] * im.size[1]), 4)

def crop_pair(src, dst, out, box_rel=(0.30, 0.18, 0.62, 0.46), size=420):
    a = Image.open(src).convert("RGB"); b = Image.open(dst).convert("RGB")
    def cut(im):
        w, h = im.size
        box = (int(box_rel[0]*w), int(box_rel[1]*h), int(box_rel[2]*w), int(box_rel[3]*h))
        return im.crop(box).resize((size, size), Image.LANCZOS)
    ca, cb = cut(a), cut(b)
    canvas = Image.new("RGB", (size*2 + 12, size), (10, 12, 18))
    canvas.paste(ca, (0, 0)); canvas.paste(cb, (size + 12, 0))
    canvas.save(out, "PNG")
    return out

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("src"); ap.add_argument("--out"); ap.add_argument("--width", type=int, default=2048)
    a = ap.parse_args()
    dst = a.out or a.src.replace(".jpg", "_hi.png")
    before, after, kb = upscale(a.src, dst, a.width)
    crop = crop_pair(a.src, dst, dst.replace("_hi.png", "_crop.png"))
    print("放大 %s → %s · %.0f KB" % (before, after, kb/1024))
    print("边缘密度 原图 %.4f → 高清 %.4f" % (edge_density(a.src), edge_density(dst)))
    print("100%% 对照：%s" % crop)
