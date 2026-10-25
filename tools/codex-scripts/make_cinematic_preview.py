# -*- coding: utf-8 -*-
"""按 cinematic.css 的真实参数，把氛围层合成成图 —— 用来实际看效果。
不是浏览器截图（本机 headless Chrome 起不来），是逐层按 CSS 数值算出来的等价画面。
"""
import math
import random
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:  # noqa: BLE001
    pass

BASE = next(p for p in Path(__file__).resolve().parents
            if (p / "gbt_allinone").is_dir())   # 修：原 `.parent.parent` 只到 tools/（少一层）
OUT = BASE / "assets" / "brand" / "_preview-cinematic.png"
W, H = 1240, 780

VOID = (4, 7, 15)
PANEL = (8, 17, 31)
PANEL3 = (22, 40, 62)
LINE = (88, 196, 255)
NEON = (42, 212, 240)
NEON2 = (110, 242, 255)
INK = (223, 242, 251)
INK2 = (184, 207, 218)
INK3 = (143, 169, 184)
WARN = (245, 181, 68)


def font(sz, bold=False):
    for name in (("msyhbd.ttc", 0) if bold else ("msyh.ttc", 0),
                 ("Dengb.ttf", 0) if bold else ("Deng.ttf", 0),
                 ("NotoSansSC-VF.ttf", 0), ("simhei.ttf", 0)):
        try:
            f = ImageFont.truetype("C:/Windows/Fonts/" + name[0], sz, index=name[1])
            if f.getmask("影").getbbox():
                return f
        except OSError:
            continue
    return ImageFont.load_default()


def radial(size, cx, cy, radius, color, a0, a1=0.0, stop=0.68):
    """径向渐变层：alpha 从 a0 线性衰减到 0（近似 CSS radial-gradient）。"""
    w, h = size
    img = Image.new("L", (w, h), 0)
    px = img.load()
    for y in range(h):
        dy = y - cy
        for x in range(w):
            d = math.hypot(x - cx, dy) / radius
            if d >= stop:
                continue
            t = d / stop
            px[x, y] = int(255 * (a0 + (a1 - a0) * t))
    layer = Image.new("RGBA", size, color + (0,))
    layer.putalpha(img)
    return layer


def glow_text(base, xy, text, f, fill, glow, blur=9, times=3):
    g = Image.new("RGBA", base.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(g)
    d.text(xy, text, font=f, fill=glow + (110,))
    g = g.filter(ImageFilter.GaussianBlur(blur))
    for _ in range(times):
        base.alpha_composite(g)
    ImageDraw.Draw(base).text(xy, text, font=f, fill=fill + (255,))


# ── 1. 底色 ──
img = Image.new("RGBA", (W, H), VOID + (255,))

# ── 2. 极光三团（照抄 .cine-a/.cine-b/.cine-c 的真实 alpha：.20 / .15 / .13）──
img.alpha_composite(radial((W, H), -0.22 * W, -0.30 * H, 0.86 * W, NEON, 0.20, 0.075, 0.68))
img.alpha_composite(radial((W, H), 1.18 * W, 1.26 * H, 0.72 * W, NEON2, 0.15, 0.05, 0.70))
img.alpha_composite(radial((W, H), 0.44 * W + 0.52 * W / 2, 0.34 * H + 0.52 * H / 2, 0.26 * W,
                           (58, 120, 220), 0.13, 0.0, 0.66))

# ── 3. 网格（body::before，46px，rgba(88,196,255,.06)）──
grid = Image.new("RGBA", (W, H), (0, 0, 0, 0))
gd = ImageDraw.Draw(grid)
for x in range(0, W, 46):
    gd.line([(x, 0), (x, H)], fill=LINE + (15,), width=1)
for y in range(0, H, 46):
    gd.line([(0, y), (W, y)], fill=LINE + (15,), width=1)
img.alpha_composite(grid)

# ── 4. 暗角（.cine-v）──
vig = Image.new("L", (W, H), 0)
vp = vig.load()
for y in range(H):
    for x in range(W):
        nx, ny = (x - W / 2) / (W * 0.63), (y - H * 0.40) / (H * 0.46)
        d = math.hypot(nx, ny)
        v = 0.0 if d < 0.70 else min(0.42 + (d - 0.70) * 0.55, 0.62)
        vp[x, y] = int(255 * v)
img.alpha_composite(Image.merge("RGBA", (Image.new("L", (W, H), 0),) * 3 + (vig,)))

# ── 5. 卡片：顶部来光 + 边框 + 着色阴影 ──
cx0, cy0, cx1, cy1 = 64, 96, W - 64, 470
sh = Image.new("RGBA", (W, H), (0, 0, 0, 0))
ImageDraw.Draw(sh).rounded_rectangle([cx0, cy0 + 12, cx1, cy1 + 12], 10, fill=(0, 0, 0, 150))
img.alpha_composite(sh.filter(ImageFilter.GaussianBlur(22)))
card = Image.new("RGBA", (W, H), (0, 0, 0, 0))
cd = ImageDraw.Draw(card)
cd.rounded_rectangle([cx0, cy0, cx1, cy1], 10, fill=PANEL + (255,), outline=LINE + (36,), width=1)
cd.line([(cx0 + 6, cy0 + 1), (cx1 - 6, cy0 + 1)], fill=(255, 255, 255, 20), width=1)
img.alpha_composite(card)

# 卡片头：自上而下微光 + 下边线
head = Image.new("RGBA", (W, H), (0, 0, 0, 0))
hd = ImageDraw.Draw(head)
for i in range(34):
    a = int(16 * (1 - i / 34))
    hd.line([(cx0 + 1, cy0 + 1 + i), (cx1 - 1, cy0 + 1 + i)], fill=LINE + (a,))
hd.line([(cx0, cy0 + 34), (cx1, cy0 + 34)], fill=LINE + (36,), width=1)
img.alpha_composite(head)

d = ImageDraw.Draw(img)
d.text((cx0 + 14, cy0 + 11), "大脑执行层 / BRAIN PIPELINE", font=font(11), fill=INK3)
d.text((cx1 - 150, cy0 + 11), "影视氛围层 V15", font=font(11), fill=NEON2)

# 大读数（带发光）
glow_text(img, (cx0 + 14, cy0 + 52), "100.0", font(30, True), INK, NEON, blur=11)
d.text((cx0 + 116, cy0 + 68), "健康分 · 5/5 维", font=font(11), fill=INK3)
glow_text(img, (cx0 + 300, cy0 + 52), "3901", font(30, True), INK, NEON, blur=11)
d.text((cx0 + 382, cy0 + 68), "ms · 全链", font=font(11), fill=INK3)

# 进度条（轨道内凹 + 填充发光）
for i, (lbl, n, den, tone) in enumerate([
        ("路由覆盖", 140, 140, NEON), ("接线完成", 135, 140, NEON),
        ("视觉缺口", 3, 5, WARN)]):
    yy = cy0 + 118 + i * 42
    d.text((cx0 + 14, yy), lbl, font=font(11), fill=INK2)
    d.text((cx1 - 90, yy), "%d/%d" % (n, den), font=font(11), fill=NEON)
    ty = yy + 20
    d.rounded_rectangle([cx0 + 14, ty, cx1 - 14, ty + 4], 2, fill=PANEL3 + (255,))
    d.line([(cx0 + 14, ty), (cx1 - 14, ty)], fill=(0, 0, 0, 90), width=1)
    fw = int((cx1 - 28) * n / den)
    g = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(g).rounded_rectangle([cx0 + 14, ty, cx0 + 14 + fw, ty + 4], 2, fill=tone + (255,))
    img.alpha_composite(g.filter(ImageFilter.GaussianBlur(6)))
    d.rounded_rectangle([cx0 + 14, ty, cx0 + 14 + fw, ty + 4], 2, fill=tone + (255,))

# ── 6. 胶片颗粒（body::after，opacity .05）──
random.seed(7)
noise = Image.new("L", (W, H))
noise.putdata([random.randint(0, 255) for _ in range(W * H)])
grain = Image.merge("RGBA", (noise, noise, noise, Image.new("L", (W, H), 13)))
img.alpha_composite(grain)

img.convert("RGB").save(OUT)
print("样张:", OUT.name, "%.0f KB" % (OUT.stat().st_size / 1024), "  %dx%d" % (W, H))
