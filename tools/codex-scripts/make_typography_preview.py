# -*- coding: utf-8 -*-
"""排版与节奏打磨的前后对照样张。
左＝V15 的真实参数，右＝V16 的真实参数，同一张卡、同一批数据。
不是浏览器截图（本机 headless Chrome 起不来），是按两版 CSS 数值逐项算出来的等价画面。
"""
import math
import random
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
BASE = next(p for p in Path(__file__).resolve().parents
            if (p / "gbt_allinone").is_dir())   # 修：原 `.parent.parent` 只到 tools/（少一层）
OUT = BASE / "assets" / "brand" / "_preview-typography.png"

PANEL = (8, 17, 31)
PANEL2 = (12, 26, 46)
LINE = (88, 196, 255, 36)
NEON = (42, 212, 240)
NEON2 = (110, 242, 255)
INK = (223, 242, 251)
INK2 = (184, 207, 218)
INK3 = (143, 169, 184)
WARN = (245, 181, 68)


def F(sz, weight=400):
    name = {400: "msyh.ttc", 500: "msyh.ttc", 600: "msyhbd.ttc", 700: "msyhbd.ttc"}[weight]
    try:
        return ImageFont.truetype("C:/Windows/Fonts/" + name, sz, index=0)
    except OSError:
        return ImageFont.load_default()


def MONO(sz):
    for n in ("consola.ttf", "CascadiaMono.ttf", "lucon.ttf"):
        try:
            return ImageFont.truetype("C:/Windows/Fonts/" + n, sz)
        except OSError:
            continue
    return F(sz)


def atmosphere(size):
    w, h = size
    img = Image.new("RGBA", size, (4, 7, 15, 255))

    def rad(cx, cy, r, col, a0, stop=0.7):
        lay = Image.new("L", size, 0)
        px = lay.load()
        for y in range(h):
            for x in range(w):
                d = math.hypot(x - cx, y - cy) / r
                if d < stop:
                    px[x, y] = int(255 * a0 * (1 - d / stop))
        l2 = Image.new("RGBA", size, col + (0,))
        l2.putalpha(lay)
        img.alpha_composite(l2)
    rad(-0.2 * w, -0.3 * h, 0.9 * w, NEON, 0.20)
    rad(1.2 * w, 1.3 * h, 0.7 * w, NEON2, 0.15)
    # 网格
    g = Image.new("RGBA", size, (0, 0, 0, 0))
    gd = ImageDraw.Draw(g)
    for x in range(0, w, 40):
        gd.line([(x, 0), (x, h)], fill=(88, 196, 255, 13))
    for y in range(0, h, 40):
        gd.line([(0, y), (w, y)], fill=(88, 196, 255, 13))
    img.alpha_composite(g)
    # 暗角
    vig = Image.new("L", size, 0)
    vp = vig.load()
    for y in range(h):
        for x in range(w):
            d = math.hypot((x - w / 2) / (w * .63), (y - h * .42) / (h * .46))
            vp[x, y] = 0 if d < .72 else int(255 * min(0.28 + (d - .72) * .5, .55))
    img.alpha_composite(Image.merge("RGBA", (Image.new("L", size, 0),) * 3 + (vig,)))
    return img


def card(img, x, y, w, h, *, pad_b, pad_h, hpad, title="大盘读数 / METRICS",
         rows=None, big=None, gap_rows, lh_rows, w_title, w_val, ls_label,
         ls_display, lh_display, big_weight, hover_row=None, radius=10):
    """注意：PIL 在 RGBA 图上直接画半透明是「替换像素」而不是混合，
    而且最后 convert("RGB") 会丢掉 alpha 让半透明像素变成满色。
    所以凡是有透明度的笔画，都必须先画在独立图层上再 alpha_composite。"""
    d = ImageDraw.Draw(img)

    # ① 投影（独立图层）
    sh = Image.new("RGBA", img.size, (0, 0, 0, 0))
    ImageDraw.Draw(sh).rounded_rectangle([x, y + 14, x + w, y + h + 14], radius, fill=(0, 0, 0, 150))
    img.alpha_composite(sh.filter(ImageFilter.GaussianBlur(20)))

    # ② 卡面 + 描边（独立图层）
    face = Image.new("RGBA", img.size, (0, 0, 0, 0))
    fd = ImageDraw.Draw(face)
    fd.rounded_rectangle([x, y, x + w, y + h], radius, fill=PANEL + (255,),
                         outline=(88, 196, 255, 36), width=1)
    img.alpha_composite(face)

    # ③ 顶部来光 + 卡头微光 + 分隔线（独立图层）
    deco = Image.new("RGBA", img.size, (0, 0, 0, 0))
    dd = ImageDraw.Draw(deco)
    dd.line([(x + 6, y + 1), (x + w - 6, y + 1)], fill=(255, 255, 255, 22), width=1)
    band = int(hpad * 2.6)
    for i in range(band):
        a = int(15 * (1 - i / band) ** 2)     # 二次衰减，收得更快，不糊成一条亮带
        dd.line([(x + 1, y + 1 + i), (x + w - 1, y + 1 + i)], fill=(88, 196, 255, a))
    dd.line([(x, y + hpad * 2 + 10), (x + w, y + hpad * 2 + 10)], fill=(88, 196, 255, 36), width=1)
    img.alpha_composite(deco)

    d.text((x + pad_h, y + hpad), title, font=F(11, w_title), fill=INK3)

    # ④ 大读数（光晕独立图层）
    if big:
        bx = x + pad_b
        ty = y + hpad * 2 + 22
        for label, val, unit in big:
            gl = Image.new("RGBA", img.size, (0, 0, 0, 0))
            ImageDraw.Draw(gl).text((bx, ty), val, font=F(24, big_weight), fill=NEON + (110,))
            img.alpha_composite(gl.filter(ImageFilter.GaussianBlur(10)))
            d.text((bx, ty), val, font=F(24, big_weight), fill=INK)
            d.text((bx + d.textlength(val, font=F(24, big_weight)) + 8, ty + 12), unit, font=F(10), fill=INK3)
            bx += 168
        ty += int(24 * lh_display) + 12
    else:
        ty = y + hpad * 2 + 30

    # ⑤ 数据行（悬浮底也走独立图层）
    for i, (name, value, ok) in enumerate(rows or []):
        ry = ty
        if hover_row is not None and i == hover_row:
            hv = Image.new("RGBA", img.size, (0, 0, 0, 0))
            ImageDraw.Draw(hv).rounded_rectangle(
                [x + pad_b - 8, ry - 3, x + w - pad_b + 8, ry + 17], 6, fill=(42, 212, 240, 26))
            img.alpha_composite(hv)
        d.text((x + pad_b, ry), name, font=F(11), fill=INK2)
        vf = MONO(11)
        vw = d.textlength(value, font=vf)
        d.text((x + w - pad_b - vw, ry), value, font=vf, fill=INK)
        if not ok:
            d.ellipse([x + pad_b - 7, ry + 4, x + pad_b - 1, ry + 10], fill=WARN)
        ty += gap_rows + int(11 * lh_rows)


ROWS = [("路由覆盖", "140 / 140", 1), ("接线完成", "135 / 140", 1),
        ("视觉缺口", "3 / 5", 0), ("模块齐备", "37 / 37", 1), ("审计窗口", "500 条", 1)]
BIG = [("健康分", "100.0", "5/5 维"), ("全链耗时", "3901", "ms")]

W, H = 1180, 560
img = atmosphere((W, H))
d = ImageDraw.Draw(img)

CW = 520
# ── 左：V15 真实参数 ──
card(img, 46, 74, CW, 400,
     pad_b=11, pad_h=11, hpad=9, gap_rows=4, lh_rows=1.6,
     w_title=600, w_val=600, ls_label=.13, ls_display=0, lh_display=1.0,
     big_weight=600, rows=ROWS, big=BIG, radius=10)
d.text((46, 40), "打磨前 · V15", font=F(13, 600), fill=INK2)
d.text((46, 488), "字重只有一档（600）· 行高 1.6 · 间距 11 种随手值 · 卡片无主次",
       font=F(10.5), fill=INK3)

# ── 右：V16 真实参数 ──
card(img, W - 46 - CW, 74, CW, 400,
     pad_b=12, pad_h=12, hpad=8, gap_rows=10, lh_rows=1.38,
     w_title=500, w_val=500, ls_label=.14, ls_display=-.022, lh_display=1.05,
     big_weight=700, rows=ROWS, big=BIG, hover_row=1, radius=10)
d.text((W - 46 - CW, 40), "打磨后 · V16", font=F(13, 600), fill=NEON2)
d.text((W - 46 - CW, 488), "字重 400/500/600/700 四级 · 行高 1.38 密排 · 间距全收 2px 刻度 · 数据行带悬浮态",
       font=F(10.5), fill=INK3)

# 中间提示
mx = 46 + CW + 14
d.line([(mx, 90), (mx, 480)], fill=(88, 196, 255, 40), width=1)

# 颗粒
random.seed(11)
noise = Image.new("L", (W, H))
noise.putdata([random.randint(0, 255) for _ in range(W * H)])
img.alpha_composite(Image.merge("RGBA", (noise, noise, noise, Image.new("L", (W, H), 13))))

img.convert("RGB").save(OUT)
print("样张:", OUT.name, "%.0f KB" % (OUT.stat().st_size / 1024))
