#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""strike_video —— 静帧 → 动作镜头的唯一入口（v1~v6 的合并版）。

演化史（每一版对着上一版的真问题，别删）：
  v1 白闪盖跳变、无声                → 廉价
  v2 色彩方差对齐（LAB 三通道）        → 灰蓝荒原被推成紫红
  v3 只校均值                          → 恢复自然，但 2 帧不够叙事
  v4 加甩镜模糊/打击冻结帧/速度线/音效  → 节奏成立
  v5 三段式（蓄势/撞击/落定）           → **LAB a/b 平移撞极值 ⇒ 满屏紫绿噪斑**
  v6 只平移 L、色度不动                 → 噪斑消失（本版）

用法：
    python3 tools/strike_video.py K1.jpg K2.jpg [K3.jpg] --out x.mp4
    python3 tools/strike_video.py K1.jpg K2.jpg --size 540x810 --total 3.6 --no-audio


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
from PIL import Image, ImageDraw, ImageFilter, ImageChops

W, H, FPS = 540, 810, 24
import builtins as _bi
SR = 44100



VIG = None


def _vignette_mask(size, strength=0.55):
    """暗角只算一次，后面复用（每帧算会慢）。"""
    global VIG
    if VIG is not None and VIG.size == size:
        return VIG
    w, h = size
    y, x = np.mgrid[0:h, 0:w].astype(np.float32)
    cx, cy = w / 2.0, h / 2.0
    r = np.sqrt(((x - cx) / cx) ** 2 + ((y - cy) / cy) ** 2)
    m = np.clip(1.0 - strength * np.clip(r - 0.55, 0, None) ** 1.6, 0.35, 1.0)
    VIG = Image.fromarray((m * 255).astype(np.uint8), "L")
    return VIG


def grade(im, warm=0.04, contrast=1.06, vig=0.55, grain=2):
    """统一调色（LUT 版）：对比用查表、冷暖用通道点乘、暗角用缓存掩膜、颗粒用现成噪声。

    为什么重写：numpy 逐像素版实测 5.4 s/帧，120 帧渲不完；LUT 版同样效果，帧成本降到 1/4。
    """
    lut = [max(0, min(255, int(((v / 255.0 - 0.5) * contrast + 0.5) * 255))) for v in range(256)]
    im = im.point(lut * 3)                                  # 对比
    r, g, b = im.split()
    r = r.point(lambda v: min(255, int(v * (1 + warm))))
    b = b.point(lambda v: min(255, int(v * (1 - warm * 0.4))))
    im = Image.merge("RGB", (r, g, b))                       # 暖亮冷暗（近似）
    if vig:
        im = Image.composite(im, Image.new("RGB", im.size, (0, 0, 0)),
                             _vignette_mask(im.size, vig))
    if grain:
        n = Image.effect_noise(im.size, grain).convert("L")
        n3 = Image.merge("RGB", (n, n, n))
        im = Image.blend(im, ImageChops.add(im, n3, scale=1, offset=-2), 0.05)
    return im


def letterbox(im, ratio=2.0):
    """遮幅：上下加黑边（2.0:1）。不为好看，是为了**藏住三段构图差异**。"""
    w, h = im.size
    vis = int(w / ratio)
    if vis >= h:
        return im
    bar = (h - vis) // 2
    out = Image.new("RGB", (w, h), (0, 0, 0))
    out.paste(im.crop((0, bar, w, bar + vis)), (0, bar))
    return out


def dutch(im, deg):
    """荷兰角：撞击瞬间轻微歪一点，冲击感更强。"""
    if abs(deg) < 0.05:
        return im
    return im.rotate(deg, resample=Image.BICUBIC, expand=False, fillcolor=(0, 0, 0))


def load(path, size=None):
    size = size or (W, H)      # 默认值必须在这里取，函数定义时取会锁死旧尺寸
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


def whip(im, amount=26, steps=6, horizontal=True):
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
    for _ in range(26):
        ang = rnd.uniform(math.pi, 2 * math.pi); sp = rnd.uniform(0.35, 1.0)
        r = t * 620 * sp * strength
        x = cx + math.cos(ang) * r * 1.25; y = cy + math.sin(ang) * r * 0.55
        rad = 6 + 26 * t * sp
        a = int(max(0, 130 * (1 - t) * strength))
        d.ellipse([x - rad, y - rad, x + rad, y + rad], fill=(214, 196, 168, a))
    return Image.alpha_composite(base.convert("RGBA"),
                                 lay.filter(ImageFilter.GaussianBlur(1))).convert("RGB")


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
    # 低频底噪：整段铺一层 42Hz + 84Hz 的慢起伏，给"要劈下去"的压迫感
    swell = 0.10 + 0.10 * np.clip(t / max(t_hit, 0.01), 0, 1)
    buf += (np.sin(2 * math.pi * 42 * t) * swell).astype(np.float32)
    buf += (np.sin(2 * math.pi * 84 * t) * swell * 0.4).astype(np.float32)
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
            im = dutch(im, -1.6 * (1 - p))
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
        im = grade(im, vig=0.55 if i > 6 else 0.35)
        im = letterbox(im, 2.0)
        im.save(os.path.join(outdir, "f%04d.png" % i))
    return n


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("k1"); ap.add_argument("k2"); ap.add_argument("k3", nargs="?")
    ap.add_argument("--out", default="/var/minis/attachments/strike_huashan_v6.mp4")
    ap.add_argument("--total", type=float, default=5.0)
    ap.add_argument("--size", default="540x810")
    ap.add_argument("--fps", type=int, default=24)
    ap.add_argument("--no-audio", action="store_true")
    a = ap.parse_args()
    _bi.W, _bi.H, _bi.FPS = [int(x) for x in a.size.lower().split("x")] + [a.fps]
    W, H, FPS = _bi.W, _bi.H, _bi.FPS
    n = build(a.k1, a.k2, a.k3, total=a.total)
    audio("/tmp/strike.wav", a.total) if not a.no_audio else None
    src = ["-i", "/tmp/frames4/f%04d.png"] + ([] if a.no_audio else ["-i", "/tmp/strike.wav"])
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-framerate", str(FPS)] + src + [
                    "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "19",
                    "-c:a", "aac", "-b:a", "128k", "-shortest",
                    "-movflags", "+faststart", a.out], check=True)
    print("渲染 %d 帧 · 视频 %s · %.0f KB" % (n, a.out, os.path.getsize(a.out) / 1024))
