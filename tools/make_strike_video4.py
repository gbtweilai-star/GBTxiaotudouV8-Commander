#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""make_strike_video2 —— 三处打磨，每一处都对着上一版的真问题：

v1 的病：
  ① 两帧是两个场景（机位/季节/人物都不一致）⇒ 观众看得出拼接
  ② 用白闪盖跳变 ⇒ 廉价
  ③ 无声 ⇒ "力劈"没有重量

v2 的修：
  ① **色彩归一**：把 K2 的 LAB 均值/方差对齐到 K1 ⇒ 两帧看起来是同一场景的同一时段
  ② **甩镜模糊**代替白闪：沿运动方向做多拷贝平均（真运动模糊），跳变藏在模糊里
  ③ **程序化音效**：whoosh（噪声扫频）+ 撞击（低频爆 + 噪声）+ 余震（衰减噪声），ffmpeg 混流
"""
import argparse, math, os, random, struct, subprocess, wave
import numpy as np
from PIL import Image, ImageDraw, ImageFilter

W, H, FPS = 540, 810, 24   # 降到 540：三段式帧数多一倍，720 渲不完
SR = 44100


def load(path, size=(W, H)):
    im = Image.open(path).convert("RGB")
    s = max(size[0] / im.size[0], size[1] / im.size[1])
    im = im.resize((int(im.size[0] * s + 1), int(im.size[1] * s + 1)), Image.LANCZOS)
    x = (im.size[0] - size[0]) // 2; y = (im.size[1] - size[1]) // 2
    return im.crop((x, y, x + size[0], y + size[1]))


def color_match(src, ref, strength=0.5, mode="mean"):
    """让两帧亮度/白平衡接近，但**不动色度轴**。

    v5 的错：LAB 三通道都平移。a（红绿）一挪，灰蓝荒原被推成紫红，且 a/b 撞到极值后
    转回 RGB 就成了满屏紫绿噪斑（第 80/115 帧那些碎块）。
    v6 的修：**只平移 L**；颜色只做有界的通道增益（0.92–1.08），再逐通道裁剪。
    """
    a = np.asarray(src.convert("RGB"), dtype=np.float32)
    b = np.asarray(ref.convert("RGB"), dtype=np.float32)
    # ① 只校明度：在 L 通道平移
    sL = np.asarray(src.convert("L"), dtype=np.float32)
    rL = np.asarray(ref.convert("L"), dtype=np.float32)
    gain = 1.0 + ((rL.mean() - sL.mean()) / 255.0) * strength
    a = a * gain
    # ② 只校白平衡：每通道均值比的**有界**增益
    for c in range(3):
        ms = a[..., c].mean() + 1e-3
        mr = b[..., c].mean() + 1e-3
        g = float(np.clip(1 + (mr / ms - 1) * strength * 0.35, 0.92, 1.08))
        a[..., c] *= g
    return Image.fromarray(np.clip(a, 0, 255).astype(np.uint8), "RGB")


def zoom_shift(im, zoom=1.0, dx=0, dy=0):
    if zoom == 1.0 and not dx and not dy:
        return im
    w, h = im.size
    cw, ch = int(w / zoom), int(h / zoom)
    x = max(0, min(w - cw, (w - cw) // 2 + dx)); y = max(0, min(h - ch, (h - ch) // 2 + dy))
    return im.crop((x, y, x + cw, y + ch)).resize((w, h), Image.LANCZOS)


def whip(im, amount=26, steps=9, horizontal=True):
    """真·运动模糊：沿方向做多次位移拷贝平均（比白闪诚实）。"""
    if amount <= 0:
        return im
    acc = np.zeros((im.size[1], im.size[0], 3), dtype=np.float32)
    for i in range(steps):
        t = (i / (steps - 1) - 0.5) * 2
        dx = int(t * amount) if horizontal else 0
        dy = 0 if horizontal else int(t * amount)
        acc += np.asarray(zoom_shift(im, 1.06, dx, dy), dtype=np.float32)
    return Image.fromarray((acc / steps).astype(np.uint8), "RGB")


def shake(im, amp):
    if amp <= 0:
        return im
    return zoom_shift(im, 1.0 + abs(amp) / 600.0,
                      int(random.uniform(-amp, amp)), int(random.uniform(-amp, amp)))


def speed_lines(base, k, seed=3):
    """速度线：径向短划线，只在甩镜与撞击瞬间出现（经典日式动作片手法）。"""
    if k <= 0:
        return base
    rnd = random.Random(seed)
    lay = Image.new("RGBA", base.size, (0, 0, 0, 0)); d = ImageDraw.Draw(lay)
    cx, cy = base.size[0] * 0.5, base.size[1] * 0.55
    for _ in range(int(26 * k)):
        ang = rnd.uniform(0, 2 * math.pi)
        r0 = rnd.uniform(0.32, 0.55) * base.size[0]
        ln = rnd.uniform(0.08, 0.22) * base.size[0] * k
        d.line([(cx + math.cos(ang) * r0, cy + math.sin(ang) * r0),
                (cx + math.cos(ang) * (r0 + ln), cy + math.sin(ang) * (r0 + ln))],
               fill=(255, 248, 232, int(90 * k)), width=rnd.choice((1, 2)))
    return Image.alpha_composite(base.convert("RGBA"), lay).convert("RGB")


def handheld(im, amp=1.6):
    """手持感：每帧极小的位置噪声（比大幅抖动更像摄影机）。"""
    return zoom_shift(im, 1.0 + amp / 900.0,
                      int(random.uniform(-amp, amp)), int(random.uniform(-amp, amp)))


def dust_ring(base, t, strength=1.0, seed=1):
    rnd = random.Random(seed)
    lay = Image.new("RGBA", base.size, (0, 0, 0, 0)); d = ImageDraw.Draw(lay)
    cx, cy = base.size[0] * 0.5, base.size[1] * 0.62
    for _ in range(48):
        ang = rnd.uniform(math.pi, 2 * math.pi); sp = rnd.uniform(0.35, 1.0)
        r = t * 620 * sp * strength
        x = cx + math.cos(ang) * r * 1.25; y = cy + math.sin(ang) * r * 0.55
        rad = 6 + 26 * t * sp
        a = int(max(0, 130 * (1 - t) * strength))
        d.ellipse([x - rad, y - rad, x + rad, y + rad], fill=(214, 196, 168, a))
    return Image.alpha_composite(base.convert("RGBA"),
                                 lay.filter(ImageFilter.GaussianBlur(2))).convert("RGB")


def audio(out_wav, total=3.6, t_hit=0.85):
    n = int(SR * total); buf = np.zeros(n, dtype=np.float32)
    t = np.arange(n) / SR
    # whoosh：噪声 + 上升包络，在撞击前 0.35s 起
    nz = np.random.RandomState(3).normal(0, 1, n).astype(np.float32)
    k = np.ones(24, dtype=np.float32) / 24
    nz = np.convolve(nz, k, mode="same")
    env = np.clip((t - (t_hit - 0.45)) / 0.45, 0, 1) ** 2
    env *= (t < t_hit)
    # 静音下潜：撞击前 0.12s 把 whoosh 压掉 60% ⇒ 打击感靠"留白"抬起来
    dip = np.clip((t - (t_hit - 0.12)) / 0.12, 0, 1)
    env *= (1 - 0.6 * dip)
    buf += nz * env * 0.5
    # 撞击：低频爆 + 短噪声
    m = t >= t_hit
    tt = t[m] - t_hit
    buf[m] += (np.sin(2 * math.pi * 58 * tt) * np.exp(-tt * 5.5) * 0.9).astype(np.float32)
    buf[m] += (np.random.RandomState(5).normal(0, 1, tt.size).astype(np.float32)
               * np.exp(-tt * 22) * 0.35)
    # 余震：衰减噪声
    buf[m] += (np.random.RandomState(7).normal(0, 1, tt.size).astype(np.float32)
               * np.exp(-tt * 1.6) * 0.12)
    # 两次"混响"抽头（90ms / 210ms），给爆点一点空间
    for dly, g in ((int(0.090 * SR), 0.35), (int(0.210 * SR), 0.18)):
        if n > dly:
            buf[dly:] += buf[:-dly] * g
    buf = np.tanh(buf * 1.1)
    pcm = (buf * 32767 * 0.9).astype(np.int16)
    with wave.open(out_wav, "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR)
        w.writeframes(pcm.tobytes())


def build(k1p, k2p, k3p=None, outdir="/tmp/frames4", total=5.0, hit=0.80):
    k1 = load(k1p)
    k2 = color_match(load(k2p), k1, strength=0.3)
    k3 = color_match(load(k3p), k2, strength=0.5) if k3p else None
    os.makedirs(outdir, exist_ok=True)
    for f in os.listdir(outdir):
        os.remove(os.path.join(outdir, f))
    n = int(total * FPS); random.seed(5)
    for i in range(n):
        t = i / FPS
        hit = 0.80
        if t < hit - 0.10:                        # ① 蓄势：缓慢推近 + 手持微动
            p = t / (hit - 0.10)
            im = handheld(zoom_shift(k1, 1.0 + 0.07 * p), 1.2)
        elif t < hit:                             # ② 甩镜：运动模糊 + 速度线登场
            p = (t - (hit - 0.10)) / 0.10
            im = Image.blend(zoom_shift(k1, 1.07), zoom_shift(k2, 1.12 - 0.12 * p), p)
            im = whip(im, amount=int(40 * p) + 10)
            im = speed_lines(im, 0.55 + 0.45 * p)
            im = shake(im, 10 * p)
        elif t < hit + 0.09:                      # ③ 打击冻结帧（2 帧）：白热 + 最抖
            p = (t - hit) / 0.09
            im = speed_lines(shake(zoom_shift(k2, 1.12 - 0.04 * p), 12), 1.0 - 0.4 * p)
            a = np.asarray(im, dtype=np.float32)
            im = Image.fromarray(np.clip(a + (255 - a) * 0.30 * (1 - p), 0, 255).astype(np.uint8), "RGB")
        elif t < hit + 1.45:                      # ④ 余震：尘环 + 衰减抖动
            p = (t - hit - 0.09) / 1.36
            damp = (1 - p) ** 2
            im = dust_ring(handheld(zoom_shift(k2, 1.04 + 0.03 * (1 - p)), 2.0), min(1.0, p * 1.8), 1.0 - 0.35 * p)
            im = shake(im, 8 * damp)
            im = speed_lines(im, max(0.0, 0.35 - p))
        elif k3 is None:                          # ⑤a 无第三帧：收势
            p = (t - hit - 1.45) / max(0.01, (total - hit - 1.45))
            im = dust_ring(handheld(zoom_shift(k2, 1.07 - 0.07 * p), 1.5), 1.0, 0.28 * (1 - p))
        else:                                     # ⑤b 三段式：化到"尘埃落定"再慢推
            p = (t - hit - 1.45) / max(0.01, (total - hit - 1.45))
            if p < 0.35:                          # 长化合（0.6s 级），读成"时间过去了"
                q = p / 0.35
                im = Image.blend(zoom_shift(k2, 1.04 - 0.02 * q),
                                 zoom_shift(k3, 1.10 - 0.04 * q), q ** 0.8)
                im = dust_ring(im, 1.0, 0.30 * (1 - q))
            else:
                q = (p - 0.35) / 0.65
                im = handheld(zoom_shift(k3, 1.06 - 0.06 * q), 1.4)
        im.save(os.path.join(outdir, "f%04d.png" % i))
    return n


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("k1"); ap.add_argument("k2"); ap.add_argument("k3", nargs="?")
    ap.add_argument("--out", default="/var/minis/attachments/strike_huashan_v6.mp4")
    ap.add_argument("--total", type=float, default=5.0)
    a = ap.parse_args()
    n = build(a.k1, a.k2, a.k3, total=a.total)
    audio("/tmp/strike.wav", a.total)
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-framerate", str(FPS),
                    "-i", "/tmp/frames4/f%04d.png", "-i", "/tmp/strike.wav",
                    "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "19",
                    "-c:a", "aac", "-b:a", "128k", "-shortest",
                    "-movflags", "+faststart", a.out], check=True)
    print("渲染 %d 帧 · 视频 %s · %.0f KB" % (n, a.out, os.path.getsize(a.out) / 1024))
