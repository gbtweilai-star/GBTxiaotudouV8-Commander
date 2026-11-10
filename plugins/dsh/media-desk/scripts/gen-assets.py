#!/usr/bin/env python3
"""生成示例卡片用的程序化配图与循环视频，输出到 assets/。不依赖任何外部素材。"""
import os
import subprocess
import tempfile

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'assets')
os.makedirs(OUT, exist_ok=True)
SONGTI = '/System/Library/Fonts/Supplemental/Songti.ttc'


def rng(seed):
    return np.random.default_rng(seed)


def fbm(w, h, seed, octaves=5, base=3, falloff=0.55):
    r = rng(seed)
    out = np.zeros((h, w), np.float32)
    amp, total = 1.0, 0.0
    for o in range(octaves):
        cells = base * 2 ** o
        grid = r.random((max(2, int(cells * h / w) + 2), cells + 2)).astype(np.float32)
        img = Image.fromarray(grid).resize((w, h), Image.BICUBIC)
        out += np.asarray(img) * amp
        total += amp
        amp *= falloff
    out /= total
    return (out - out.min()) / (out.max() - out.min() + 1e-6)


def hexc(s):
    s = s.lstrip('#')
    return np.array([int(s[i:i + 2], 16) for i in (0, 2, 4)], np.float32)


def ramp(t, stops):
    t = np.clip(t, 0, 1)[..., None]
    n = len(stops) - 1
    idx = np.clip((t * n).astype(int), 0, n - 1)
    f = t * n - idx
    arr = np.stack([hexc(c) for c in stops])
    return arr[idx[..., 0]] * (1 - f) + arr[idx[..., 0] + 1] * f


def grain(a, seed, amount=7):
    return a + rng(seed).normal(0, amount, a.shape[:2])[..., None]


def vignette(a, strength=0.25):
    h, w = a.shape[:2]
    y, x = np.mgrid[0:h, 0:w]
    d = np.hypot((x - w / 2) / (w / 2), (y - h / 2) / (h / 2))
    return a * (1 - strength * np.clip(d - 0.35, 0, 1)[..., None] ** 1.5)


def save(a, name, quality=86):
    Image.fromarray(np.clip(a, 0, 255).astype(np.uint8)).save(os.path.join(OUT, name + '.jpg'), quality=quality, optimize=True)
    print(name)


def sky(h, w, stops):
    return ramp(np.tile(np.linspace(0, 1, h)[:, None], (1, w)), stops)


def ridges(canvas, seed, layers, colors, top=0.42, bottom=0.98, rough=0.16):
    h, w = canvas.shape[:2]
    r = rng(seed)
    y = np.arange(h)[:, None]
    for i in range(layers):
        k = i / max(1, layers - 1)
        line = fbm(w, 2, int(r.integers(1e6)), octaves=5, base=2 + i)[0]
        crest = h * (top + (bottom - top) * k * 0.75) + (line - 0.5) * h * rough * (1.1 - k * 0.5)
        mask = np.clip(y - crest[None, :], 0, 1)[..., None]
        shade = 1 - np.clip((y - crest[None, :]) / (h * 0.5), 0, 1)[..., None] * 0.22
        canvas = canvas * (1 - mask) + hexc(colors[i]) * shade * mask
    return canvas


def hills(w=900, h=620):
    a = sky(h, w, ['#8fb8d8', '#cfe0e0', '#f4ecd6', '#fbeec9'])
    clouds = fbm(w, h, 11, octaves=6, base=4)
    a = a * (1 - np.clip(clouds - 0.52, 0, 1)[..., None] * 1.4) + 255 * np.clip(clouds - 0.52, 0, 1)[..., None] * 1.4
    a = ridges(a, 12, 5, ['#8fa89a', '#6d9a6e', '#4f8a4e', '#39723d', '#2a5b30'], top=0.46, rough=0.2)
    tex = fbm(w, h, 13, octaves=6, base=20)[..., None]
    a = a * (0.9 + tex * 0.2)
    save(vignette(grain(a, 14, 5), 0.3), 'hills')


def dunes(w=720, h=960):
    a = sky(h, w, ['#2c2a4a', '#7a4b6e', '#d9866b', '#f4c58e'])
    a = ridges(a, 21, 6, ['#b76e5a', '#c98560', '#dc9e6c', '#c67b4f', '#a65d3d', '#7a3f2c'], top=0.5, rough=0.22)
    sun = np.hypot(*(np.mgrid[0:h, 0:w] - np.array([[[h * 0.36]], [[w * 0.68]]])))
    a += np.exp(-(sun / 90) ** 2)[..., None] * np.array([120, 90, 50])
    save(vignette(grain(a, 22, 8), 0.35), 'dunes')


def aurora(w=800, h=800, seed=31, stops=('#f6e7f4', '#d9d8fb', '#b9d6f7', '#cdeee0', '#faf0cf'), name='aurora'):
    n1, n2 = fbm(w, h, seed, octaves=3, base=2), fbm(w, h, seed + 1, octaves=3, base=2)
    y, x = np.mgrid[0:h, 0:w]
    f = np.sin((x / w * 3 + n1 * 5)) * 0.5 + np.cos((y / h * 3 + n2 * 5)) * 0.5
    a = ramp((f + 1) / 2, list(stops))
    save(grain(a, seed + 2, 4), name)


def riso(w=720, h=860):
    r = rng(41)
    a = np.zeros((h, w, 3), np.float32) + hexc('#f4efe2')
    y = 0
    colors = ['#e23d28', '#f5c518', '#f4efe2', '#1f4fa3', '#f5c518', '#e23d28', '#111111', '#f4efe2', '#e23d28', '#f5c518']
    i = 0
    while y < h:
        band = int(r.integers(26, 96))
        a[y:y + band] = hexc(colors[i % len(colors)])
        y += band
        i += 1
    dots = (np.sin(np.mgrid[0:h, 0:w][0] * 0.9) * np.sin(np.mgrid[0:h, 0:w][1] * 0.9)) > 0.72
    a[dots] *= 0.86
    save(grain(a, 42, 10), 'riso')


def topo(w=720, h=720):
    f = fbm(w, h, 51, octaves=4, base=2)
    lines = np.abs(((f * 26) % 1) - 0.5) < 0.05
    a = np.zeros((h, w, 3), np.float32) + hexc('#ece9e1')
    a[lines] = hexc('#22221f')
    img = Image.fromarray(a.astype(np.uint8)).filter(ImageFilter.GaussianBlur(0.5))
    save(grain(np.asarray(img, np.float32), 52, 4), 'topo')


def facade(w=720, h=940):
    a = np.full((h, w, 3), 168, np.float32)
    r = rng(61)
    stain = fbm(w, h, 62, octaves=7, base=4)
    streak = np.asarray(Image.fromarray(fbm(w, 40, 63, octaves=5, base=30).astype(np.float32)).resize((w, h), Image.BICUBIC))
    a *= (0.45 + stain * 0.9)[..., None] * (0.72 + streak * 0.5)[..., None]
    cols, rows = 7, 11
    for ry in range(rows):
        for cx in range(cols):
            x0 = int((cx + 0.2) * w / cols)
            y0 = int((ry + 0.22) * h / rows)
            x1 = int(x0 + w / cols * 0.56)
            y1 = int(y0 + h / rows * 0.6)
            v = float(r.uniform(6, 46))
            a[y0:y1, x0:x1] = v
            a[y1:y1 + 7, x0 - 4:x1 + 4] = 205
            a[y0 + 6:y1 - 2, x0 + 4:x1 - 4] += r.uniform(0, 26)
    save(vignette(grain(a, 64, 13), 0.5), 'facade')


def sea(w=900, h=600):
    a = sky(h, w, ['#dfe6ea', '#e9e4dc', '#c7d3d8', '#7f9aa8', '#3f5e70', '#1e3442'])
    s = np.asarray(Image.fromarray(rng(71).random((h // 6, 8)).astype(np.float32)).resize((w, h), Image.BICUBIC))
    a *= 0.9 + (s * 0.2)[..., None] * (np.linspace(0, 1, h)[:, None, None] > 0.45)
    save(grain(a, 72, 5), 'sea')


def bokeh_frame(w, h, t=0.0, seed=81):
    r = rng(seed)
    a = sky(h, w, ['#080b18', '#10152b', '#1a1636', '#2b1737'])
    img = Image.fromarray(np.clip(a, 0, 255).astype(np.uint8)).convert('RGB')
    over = Image.new('RGB', (w, h))
    d = ImageDraw.Draw(over)
    palette = ['#ffb347', '#ff5e62', '#4fc3f7', '#ffe082', '#ba68c8', '#80cbc4']
    for _ in range(46):
        px = r.uniform(0, 1)
        py = r.uniform(0.25, 1)
        rad = r.uniform(10, 48)
        c = hexc(palette[r.integers(len(palette))]) * r.uniform(0.3, 0.8)
        speed = r.integers(1, 3)
        x = ((px + t * speed) % 1.2 - 0.1) * w
        y = py * h
        d.ellipse([x - rad, y - rad, x + rad, y + rad], fill=tuple(int(v) for v in c))
    over = over.filter(ImageFilter.GaussianBlur(2.2))
    return np.clip(np.asarray(img, np.float32) + np.asarray(over, np.float32), 0, 255)


def emboss(w=760, h=760, en=False):
    n = fbm(w, h, 91, octaves=2, base=2)
    img = Image.new('L', (w, h), 0)
    d = ImageDraw.Draw(img)
    if en:
        font = ImageFont.truetype('/System/Library/Fonts/Supplemental/Didot.ttc', 280, index=0)
        d.text((w / 2, h / 2), 'Idea', fill=255, font=font, anchor='mm')
    else:
        font = ImageFont.truetype(SONGTI, 240, index=0)
        for i, ch in enumerate('灵感'):
            d.text((90 + i * 290, 240 + i * 60), ch, fill=255, font=font)
    mask = np.asarray(img.filter(ImageFilter.GaussianBlur(5)), np.float32) / 255
    gy, gx = np.gradient(mask + n * 0.6)
    light = gx * -4.5 + gy * -4.5
    a = (178 + light[..., None] * 340 + fbm(w, h, 92, octaves=7, base=30)[..., None] * 36) * np.array([0.98, 0.98, 1.0])
    save(grain(a, 93, 5), 'emboss-en' if en else 'emboss')


def ink(w=720, h=960):
    a = np.zeros((h, w, 3), np.float32) + hexc('#efeadd')
    r = rng(101)
    y = np.arange(h)[:, None]
    for i in range(5):
        k = i / 4
        line = fbm(w, 2, int(r.integers(1e6)), octaves=6, base=2 + i)[0]
        crest = h * (0.2 + k * 0.52) + (line - 0.5) * h * 0.34
        depth = np.clip((y - crest[None, :]) / (h * (0.2 + 0.1 * k)), 0, 1)
        mist = (1 - depth) ** 2.2 * (0.28 + k * 0.62)
        tex = fbm(w, h, int(r.integers(1e6)), octaves=6, base=12)
        alpha = np.clip(mist * (0.62 + tex * 0.76), 0, 1)[..., None] * (y >= crest[None, :])[..., None]
        a = a * (1 - alpha) + hexc('#21262a') * alpha
    d = np.hypot(*(np.mgrid[0:h, 0:w] - np.array([[[h * 0.16]], [[w * 0.74]]])))
    a = np.where((d < 44)[..., None], hexc('#bb3a2c'), a)
    save(grain(a, 102, 4), 'ink')


def collage(w=780, h=620):
    img = Image.new('RGB', (w, h), '#e9e7e2')
    d = ImageDraw.Draw(img)
    d.ellipse([410, 40, 720, 350], fill='#2f6b4f')
    d.pieslice([40, 180, 420, 560], 180, 360, fill='#f0a13a')
    d.rectangle([340, 340, 640, 560], fill='#e0562e')
    d.ellipse([500, 400, 600, 500], fill='#f6d6e4')
    for i in range(8):
        d.arc([60 + i * 16, 60 + i * 16, 300 - i * 16, 300 - i * 16], 0, 360, fill='#141414', width=3)
    d.rectangle([60, 470, 260, 490], fill='#3148c9')
    d.rectangle([60, 505, 180, 525], fill='#141414')
    save(grain(np.asarray(img, np.float32), 111, 7), 'collage')


def still(w=720, h=860):
    a = sky(h, w, ['#efe5d6', '#e8dac5', '#d8c5a8'])
    y, x = np.mgrid[0:h, 0:w]
    win = ((x + y * 0.45) % 240 < 150) & (y < h * 0.72)
    a = a + win[..., None] * np.array([18, 15, 8])
    a = np.asarray(Image.fromarray(np.clip(a, 0, 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(9)), np.float32).copy()
    table = y > h * 0.72
    a[table] = (hexc('#5b3a29') * (0.72 + fbm(w, h, 121, octaves=5, base=9)[..., None] * 0.5))[table]
    cx, cy, rad = w * 0.5, h * 0.62, 150
    dist = np.hypot(x - cx, (y - cy))
    shadow = np.exp(-(((x - cx - 110) / 230) ** 2 + ((y - (h * 0.78)) / 34) ** 2))[..., None]
    a = a * (1 - shadow * 0.62)
    ball = dist < rad
    light = np.clip(1 - np.hypot(x - cx + 60, y - cy + 70) / (rad * 1.9), 0, 1)[..., None]
    a[ball] = (hexc('#c8542c') * 0.42 + hexc('#ffc27a') * light * 1.0)[ball]
    save(grain(a, 122, 7), 'still')


def stairs(w=720, h=720):
    a = np.zeros((h, w, 3), np.float32) + 228
    y, x = np.mgrid[0:h, 0:w]
    u = (x + y) / (w + h)
    steps = (u * 13).astype(int) % 2
    tone = 48 + 150 * ((u * 13) % 1)
    a = np.where(steps[..., None] == 0, tone[..., None], 232 - tone[..., None] * 0.28)
    side = x > w * (0.25 + 0.5 * (y / h))
    a = np.where(side[..., None], a * 0.28 + 6, a)
    save(grain(np.repeat(a, 3, axis=2), 131, 9), 'stairs')


def poster(w=720, h=960):
    img = Image.new('RGB', (w, h), '#101114')
    d = ImageDraw.Draw(img)
    big = ImageFont.truetype(SONGTI, 300, index=0)
    small = ImageFont.truetype(SONGTI, 34, index=0)
    d.text((48, 40), '慢', fill='#f1ece1', font=big)
    d.text((340, 340), '写', fill='#e7502d', font=big)
    d.line([48, 760, 672, 760], fill='#f1ece1', width=1)
    d.text((48, 790), '把一个念头养成一篇长文', fill='#f1ece1', font=small)
    save(grain(np.asarray(img, np.float32), 141, 6), 'poster', quality=90)


def poster_en(w=720, h=960):
    img = Image.new('RGB', (w, h), '#101114')
    d = ImageDraw.Draw(img)
    big = ImageFont.truetype('/System/Library/Fonts/Supplemental/Didot.ttc', 196, index=0)
    small = ImageFont.truetype('/System/Library/Fonts/Supplemental/Didot.ttc', 36, index=0)
    d.text((44, 60), 'Slow', fill='#f1ece1', font=big)
    d.text((44, 330), 'writing', fill='#e7502d', font=big)
    d.line([48, 760, 672, 760], fill='#f1ece1', width=1)
    d.text((48, 790), 'Growing one thought into a long read', fill='#f1ece1', font=small)
    save(grain(np.asarray(img, np.float32), 141, 6), 'poster-en', quality=90)


def encode(frames_fn, name, w, h, n=96, fps=24):
    with tempfile.TemporaryDirectory() as tmp:
        for i in range(n):
            f = frames_fn(i / n)
            Image.fromarray(np.clip(f, 0, 255).astype(np.uint8)).save(f'{tmp}/{i:04d}.png', compress_level=1)
            if i == 0:
                save(f, name + '-poster')
        subprocess.run(['ffmpeg', '-v', 'error', '-y', '-framerate', str(fps), '-i', f'{tmp}/%04d.png', '-c:v', 'libx264', '-crf', '27', '-preset', 'veryslow',
                        '-pix_fmt', 'yuv420p', '-movflags', '+faststart', os.path.join(OUT, name + '.mp4')], check=True)
    print(name, 'mp4')


def video_aurora():
    w, h = 540, 720
    n1, n2 = fbm(w, h, 201, octaves=3, base=2), fbm(w, h, 202, octaves=3, base=2)
    y, x = np.mgrid[0:h, 0:w]
    stops = ['#050814', '#142a55', '#1aa58c', '#c6f5b4', '#5a2ca0', '#050814']

    def frame(t):
        a = 2 * np.pi * t
        f = np.sin(x / w * 2.4 + n1 * 6 + np.sin(a) * 1.4) * 0.5 + np.cos(y / h * 2.6 + n2 * 6 + np.cos(a) * 1.4) * 0.5
        return grain(ramp((f + 1) / 2, stops), int(t * 1000), 3)
    encode(frame, 'v-aurora', w, h)


def video_tide():
    w, h = 720, 540
    y, x = np.mgrid[0:h, 0:w]
    n = fbm(w, h, 211, octaves=3, base=4)

    def frame(t):
        a = 2 * np.pi * t
        depth = y / h
        wave = np.sin(depth * depth * 62 - a * 2 + n * 7 + np.sin(x / 120 + a) * 1.2)
        foam = np.clip(wave - 0.82, 0, 1) * 5.2
        base = ramp(depth, ['#f5d5ae', '#88bfc4', '#2f7f93', '#0f4a61'])
        return grain(base + foam[..., None] * 170 * (depth[..., None] > 0.18), int(t * 1000), 3)
    encode(frame, 'v-tide', w, h)


def video_bus():
    w, h = 720, 480

    def frame(t):
        return grain(bokeh_frame(w, h, t), int(t * 1000), 4)
    encode(frame, 'v-bus', w, h)


def video_ink():
    w, h = 600, 600
    y, x = np.mgrid[0:h, 0:w]
    n1, n2 = fbm(w, h, 221, octaves=4, base=2), fbm(w, h, 222, octaves=4, base=2)
    d = np.hypot(x - w / 2, y - h / 2) / (w / 2)

    def frame(t):
        a = 2 * np.pi * t
        grow = 0.7 + 0.09 * np.sin(a)
        f = d + (n1 - 0.5) * (0.75 + 0.16 * np.sin(a)) + (n2 - 0.5) * (0.4 + 0.12 * np.cos(a))
        m = 1 - np.clip((f - grow * 0.6) / 0.26, 0, 1)
        return grain(hexc('#f0ece2') * (1 - m[..., None]) + hexc('#141519') * m[..., None], int(t * 1000), 3)
    encode(frame, 'v-ink', w, h)


if __name__ == '__main__':
    hills(); dunes(); aurora()
    aurora(seed=35, stops=('#fbe3d6', '#f6c8cf', '#e4c6ef', '#c9d9f7', '#f8ead0'), name='blush')
    riso(); topo(); facade(); sea()
    save(grain(bokeh_frame(720, 900), 82, 5), 'night')
    emboss(); ink(); collage(); still(); stairs(); poster(); poster_en(); emboss(en=True)
    video_aurora(); video_tide(); video_bus(); video_ink()
