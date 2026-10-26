#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""polish —— 出图后的最后一道打磨（不生成，只调）。

四步，都是"能测"的：
  ① 影调：S 曲线压暗部、提亮部（对比起来，但不发白）
  ② 颜色：轻微加暖 + 一点点饱和（照片味的常用量）
  ③ 锐化：只在 LAB 的 L 通道 USM（不动颜色 ⇒ 没有彩边）
  ④ 颗粒：极细，8% 混入（打散插值糊感，不是加噪点）

用法： python3 tools/polish.py in.jpg --out out.png --scale 1.5
输出会同时给"同尺寸边缘密度"对照，**不靠感觉**。
"""
import argparse, os
from PIL import Image, ImageFilter, ImageChops, ImageEnhance, ImageStat


def scurve(v, k=1.25):
    # 以 128 为中心的 S 曲线
    return max(0, min(255, int(128 + (v - 128) * k - (v - 128) ** 3 / 65536 * (k - 1))))


def polish(src, dst, scale=1.5, contrast=1.12, warmth=1.04, sat=1.06,
           usm=(1.2, 45, 4), grain=2, dark=0.98):
    im = Image.open(src).convert("RGB")
    w0, h0 = im.size
    if scale != 1:
        im = im.resize((int(w0 * scale), int(h0 * scale)), Image.LANCZOS)

    # ① 影调
    g = im.convert("L").point(lambda v: scurve(v, contrast))
    im = Image.merge("RGB", (g, g, g)).convert("RGB") if False else im
    lut = [scurve(v, contrast) for v in range(256)]
    im = Image.merge("RGB", [ch.point(lut) for ch in im.split()])

    # ② 颜色
    r, g2, b = im.split()
    r = r.point(lambda v: min(255, int(v * warmth)))
    b = b.point(lambda v: int(v / warmth))
    im = Image.merge("RGB", (r, g2, b))
    im = ImageEnhance.Color(im).enhance(sat)
    if dark != 1.0:
        im = ImageEnhance.Brightness(im).enhance(dark)

    # ③ 亮度通道锐化（不产生彩边）
    lab = im.convert("LAB")
    L, A, B = lab.split()
    L = L.filter(ImageFilter.UnsharpMask(radius=usm[0], percent=usm[1], threshold=usm[2]))
    im = Image.merge("LAB", (L, A, B)).convert("RGB")

    # ④ 颗粒
    if grain:
        noise = Image.effect_noise(im.size, grain).convert("L")
        n3 = Image.merge("RGB", (noise, noise, noise))
        im = Image.blend(im, ImageChops.add(im, n3, scale=1, offset=-2), 0.08)

    im.save(dst, "PNG")
    return im


def metrics(p, ref_w=627):
    im = Image.open(p).convert("L")
    if im.size[0] != ref_w:
        im = im.resize((ref_w, int(im.size[1] * ref_w / im.size[0])), Image.LANCZOS)
    e = im.filter(ImageFilter.FIND_EDGES)
    edge = sum(1 for v in e.getdata() if v > 40) / (im.size[0] * im.size[1])
    st = ImageStat.Stat(im)
    return {"edge": round(edge, 4), "mean": round(st.mean[0], 1), "std": round(st.stddev[0], 1)}


def crop_pair(a, b, out, box=(0.28, 0.12, 0.66, 0.44), size=430):
    A = Image.open(a).convert("RGB"); B = Image.open(b).convert("RGB")
    def cut(im):
        w, h = im.size
        return im.crop((int(box[0]*w), int(box[1]*h), int(box[2]*w), int(box[3]*h))).resize((size, size), Image.LANCZOS)
    ca, cb = cut(A), cut(B)
    canvas = Image.new("RGB", (size*2+10, size), (8, 10, 14))
    canvas.paste(ca, (0, 0)); canvas.paste(cb, (size+10, 0))
    canvas.save(out, "PNG")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("src"); ap.add_argument("--out"); ap.add_argument("--scale", type=float, default=1.5)
    a = ap.parse_args()
    dst = a.out or a.src.rsplit(".", 1)[0] + "_polish.png"
    polish(a.src, dst, a.scale)
    cp = dst.replace(".png", "_crop.png")
    crop_pair(a.src, dst, cp)
    print("产物 %s · %s" % (dst, Image.open(dst).size))
    print("原图   ", metrics(a.src))
    print("打磨后 ", metrics(dst))
    print("100%% 对照 %s" % cp)
