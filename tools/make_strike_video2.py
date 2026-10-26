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

W, H, FPS = 720, 1080, 24
SR = 44100


def load(path, size=(W, H)):
    im = Image.open(path).convert("RGB")
    s = max(size[0] / im.size[0], size[1] / im.size[1])
    im = im.resize((int(im.size[0] * s + 1), int(im.size[1] * s + 1)), Image.LANCZOS)
    x = (im.size[0] - size[0]) // 2; y = (im.size[1] - size[1]) // 2
    return im.crop((x, y, x + size[0], y + size[1]))


def color_match(src, ref, strength=0.3, mode="mean"):
    """让两帧"同色温"，但**不抹平各自的明暗关系**。

    v2 的错：把 σ 也一起对齐（LAB 逐通道），结果一张柔和晨雾全景被高对比逆光剪影拉着走 ⇒ 变紫红。
    v3 的修：默认只校均值（白平衡/曝光），σ 不动；要动 σ 得显式 mode="full" 且 strength 很小。
    """
    s = np.asarray(src.convert("LAB"), dtype=np.float32)
    r = np.asarray(ref.convert("LAB"), dtype=np.float32)
    out = s.copy()
    for c in range(3):
        ms, ss = s[..., c].mean(), s[..., c].std() + 1e-3
        mr, sr_ = r[..., c].mean(), r[..., c].std() + 1e-3
        if mode == "full":
            out[..., c] = (s[..., c] - ms) * (1 + (sr_ / ss - 1) * strength) + ms + (mr - ms) * strength
        else:
            out[..., c] = s[..., c] + (mr - ms) * strength      # 只平移，不缩放
    return Image.fromarray(np.clip(out, 0, 255).astype(np.uint8), "LAB").convert("RGB")


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


def dust_ring(base, t, strength=1.0, seed=1):
    rnd = random.Random(seed)
    lay = Image.new("RGBA", base.size, (0, 0, 0, 0)); d = ImageDraw.Draw(lay)
    cx, cy = base.size[0] * 0.5, base.size[1] * 0.62
    for _ in range(90):
        ang = rnd.uniform(math.pi, 2 * math.pi); sp = rnd.uniform(0.35, 1.0)
        r = t * 620 * sp * strength
        x = cx + math.cos(ang) * r * 1.25; y = cy + math.sin(ang) * r * 0.55
        rad = 6 + 26 * t * sp
        a = int(max(0, 130 * (1 - t) * strength))
        d.ellipse([x - rad, y - rad, x + rad, y + rad], fill=(214, 196, 168, a))
    return Image.alpha_composite(base.convert("RGBA"),
                                 lay.filter(ImageFilter.GaussianBlur(3))).convert("RGB")


def audio(out_wav, total=3.6, t_hit=0.85):
    n = int(SR * total); buf = np.zeros(n, dtype=np.float32)
    t = np.arange(n) / SR
    # whoosh：噪声 + 上升包络，在撞击前 0.35s 起
    nz = np.random.RandomState(3).normal(0, 1, n).astype(np.float32)
    k = np.ones(24, dtype=np.float32) / 24
    nz = np.convolve(nz, k, mode="same")
    env = np.clip((t - (t_hit - 0.45)) / 0.45, 0, 1) ** 2
    env *= (t < t_hit)
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
    buf = np.tanh(buf * 1.1)
    pcm = (buf * 32767 * 0.9).astype(np.int16)
    with wave.open(out_wav, "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR)
        w.writeframes(pcm.tobytes())


def build(k1p, k2p, outdir="/tmp/frames2", total=3.6, hit=0.85):
    k1 = load(k1p); k2 = color_match(load(k2p), k1, strength=0.3)
    os.makedirs(outdir, exist_ok=True)
    for f in os.listdir(outdir):
        os.remove(os.path.join(outdir, f))
    n = int(total * FPS); random.seed(5)
    for i in range(n):
        t = i / FPS
        if t < hit - 0.25:                        # ① 蓄势
            p = t / (hit - 0.25)
            im = shake(zoom_shift(k1, 1.0 + 0.07 * p), 1.2 * p)
        elif t < hit:                             # ② 甩镜（运动模糊，不是白闪）
            p = (t - (hit - 0.25)) / 0.25
            im = Image.blend(zoom_shift(k1, 1.07 + 0.06 * p),
                             zoom_shift(k2, 1.12 - 0.12 * p), p)
            im = whip(im, amount=int(34 * (1 - abs(p - 0.5) * 2)) + 6)
            im = shake(im, 14 * p)
        elif t < hit + 1.55:                      # ③ 撞击 + 余震
            p = (t - hit) / 1.55; damp = (1 - p) ** 2
            im = dust_ring(shake(zoom_shift(k2, 1.0 + 0.05 * (1 - p)), 9 * damp),
                           min(1.0, p * 1.6), 1.0 - 0.4 * p)
        else:                                     # ④ 收势
            p = (t - hit - 1.55) / (total - hit - 1.55)
            im = dust_ring(zoom_shift(k2, 1.05 - 0.05 * p), 1.0, 0.3 * (1 - p))
        im.save(os.path.join(outdir, "f%04d.png" % i))
    return n


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("k1"); ap.add_argument("k2")
    ap.add_argument("--out", default="/var/minis/attachments/strike_huashan_v3.mp4")
    ap.add_argument("--total", type=float, default=3.6)
    a = ap.parse_args()
    n = build(a.k1, a.k2, total=a.total)
    audio("/tmp/strike.wav", a.total)
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-framerate", str(FPS),
                    "-i", "/tmp/frames2/f%04d.png", "-i", "/tmp/strike.wav",
                    "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "19",
                    "-c:a", "aac", "-b:a", "128k", "-shortest",
                    "-movflags", "+faststart", a.out], check=True)
    print("渲染 %d 帧 · 视频 %s · %.0f KB" % (n, a.out, os.path.getsize(a.out) / 1024))
