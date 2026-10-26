#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""make_strike_video —— 用两张静帧做一段"力劈华山"的动作镜头（静帧 + 动效包装）。

诚实边界：**这不是生成式视频**。没有视频模型，所以做法是：
    蓄势帧 → 甩击（快速变焦+抖动+白闪）→ 撞击帧（尘环、碎石、余震）→ 收势
每一步都是几何变换与粒子，能被复算，不靠猜。

用法： python3 tools/make_strike_video.py 蓄势.jpg 撞击.jpg --out /var/minis/attachments/strike.mp4
"""
import argparse, math, os, random, subprocess
import numpy as np
from PIL import Image, ImageDraw, ImageFilter

W, H, FPS = 720, 1080, 24


def load(path, size=(W, H)):
    im = Image.open(path).convert("RGB")
    s = max(size[0] / im.size[0], size[1] / im.size[1])
    im = im.resize((int(im.size[0] * s + 1), int(im.size[1] * s + 1)), Image.LANCZOS)
    x = (im.size[0] - size[0]) // 2
    y = (im.size[1] - size[1]) // 2
    return im.crop((x, y, x + size[0], y + size[1]))


def zoom_shift(im, zoom=1.0, dx=0, dy=0):
    if zoom == 1.0 and not dx and not dy:
        return im
    w, h = im.size
    cw, ch = int(w / zoom), int(h / zoom)
    x = (w - cw) // 2 + dx
    y = (h - ch) // 2 + dy
    x = max(0, min(w - cw, x)); y = max(0, min(h - ch, y))
    return im.crop((x, y, x + cw, y + ch)).resize((w, h), Image.LANCZOS)


def shake(im, amp):
    if amp <= 0:
        return im
    dx = int(random.uniform(-amp, amp)); dy = int(random.uniform(-amp, amp))
    return zoom_shift(im, 1.0 + abs(amp) / 600.0, dx, dy)


def flash(im, k):
    if k <= 0:
        return im
    a = np.asarray(im, dtype=np.float32)
    a = a + (255 - a) * k
    return Image.fromarray(np.clip(a, 0, 255).astype(np.uint8), "RGB")


def dust_ring(base, t, strength=1.0, seed=1):
    """撞击尘环 + 碎石：半径随时间扩张，透明度衰减。"""
    rnd = random.Random(seed)
    lay = Image.new("RGBA", base.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(lay)
    cx, cy = base.size[0] * 0.5, base.size[1] * 0.62
    for i in range(90):
        ang = rnd.uniform(math.pi, 2 * math.pi)
        sp = rnd.uniform(0.35, 1.0)
        r = (t * 620 * sp) * strength
        x = cx + math.cos(ang) * r * 1.25
        y = cy + math.sin(ang) * r * 0.55
        rad = (6 + 26 * t * sp)
        a = int(max(0, 130 * (1 - t) * strength))
        d.ellipse([x - rad, y - rad, x + rad, y + rad], fill=(214, 196, 168, a))
    lay = lay.filter(ImageFilter.GaussianBlur(3))
    return Image.alpha_composite(base.convert("RGBA"), lay).convert("RGB")


def build(k1_path, k2_path, outdir="/tmp/frames", total=3.6):
    k1, k2 = load(k1_path), load(k2_path)      # 传进来的是路径，这里才变成图
    os.makedirs(outdir, exist_ok=True)
    for f in os.listdir(outdir):
        os.remove(os.path.join(outdir, f))
    n = int(total * FPS)
    random.seed(5)
    for i in range(n):
        t = i / FPS
        if t < 0.75:                                   # ① 蓄势：缓慢推近 + 轻微绷紧
            p = t / 0.75
            im = zoom_shift(k1, 1.0 + 0.06 * p)
            im = shake(im, 1.2 * p)
        elif t < 1.00:                                 # ② 甩击：快速变焦 + 强抖 + 白闪
            p = (t - 0.75) / 0.25
            im = Image.blend(zoom_shift(k1, 1.06 + 0.10 * p, int(-14 * p), int(8 * p)),
                             zoom_shift(k2, 1.16 - 0.16 * p), min(1.0, p * 1.6))
            im = shake(im, 16 * p)
            im = flash(im, 0.55 * math.sin(p * math.pi))
        elif t < 2.60:                                 # ③ 撞击：尘环扩张 + 余震衰减
            p = (t - 1.0) / 1.6
            damp = (1 - p) ** 2
            im = zoom_shift(k2, 1.0 + 0.05 * (1 - p))
            im = shake(im, 10 * damp)
            im = dust_ring(im, min(1.0, p * 1.5), strength=1.0 - 0.4 * p)
            if p < 0.16:
                im = flash(im, 0.35 * (1 - p / 0.16))
        else:                                          # ④ 收势：缓慢拉开
            p = (t - 2.6) / (total - 2.6)
            im = zoom_shift(k2, 1.05 - 0.05 * p)
            im = dust_ring(im, 1.0, strength=0.35 * (1 - p))
        im = im.filter(ImageFilter.GaussianBlur(0.0))
        im.save(os.path.join(outdir, "f%04d.png" % i))
    return n


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("k1"); ap.add_argument("k2")
    ap.add_argument("--out", default="/var/minis/attachments/strike_huashan.mp4")
    ap.add_argument("--total", type=float, default=3.6)
    a = ap.parse_args()
    n = build(a.k1, a.k2, total=a.total)
    print("渲染 %d 帧 @%dfps" % (n, FPS))
    cmd = ["ffmpeg", "-y", "-framerate", str(FPS), "-i", "/tmp/frames/f%04d.png",
           "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "20",
           "-movflags", "+faststart", a.out]
    subprocess.run(cmd, check=True, capture_output=True)
    print("视频 %s · %.0f KB" % (a.out, os.path.getsize(a.out) / 1024))
