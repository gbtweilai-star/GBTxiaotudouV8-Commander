# -*- coding: utf-8 -*-
"""mouth-lab.py — 量真实嘴唇 + 用**她的唇像素**做一个口型原型，和现在那版放一起比。

为什么这么干（2026-10-19 · 主人「查资料再动手」之后）：

Live2D 官方 Motion-sync 文档写得很清楚（docs.live2d.com/en/cubism-editor-manual/motion-sync/）：
  “audio data is converted into a time-series of **visemes**, and mouth motions are generated
   by **blending the corresponding shapes for each viseme pre-defined by the user**”
⇒ 专业做法是：**每个 viseme 先有一张"预定义形状"（美术画的嘴），音频只负责出权重，再混合。**
我之前的做法（一个连续量 jaw 驱动一个几何椭圆）**没有形状表**，所以怎么调都像贴纸。

而形状必须"长在她脸上"。没有美术、也没有图像模型时，唯一诚实的来源就是
**她自己那几平方厘米的唇像素**：把唇区抠出来当素材，内部空腔用**同一块像素里的暗部颜色**填。
颜色与质感天然一致，不会像贴上去的。

本件只做两件事：① 量；② 出静态对比图让人先判断方向，不动运行时。
"""
import json
import os

import numpy as np
from PIL import Image, ImageDraw, ImageFilter
import sys

# ── 编码守门（encoding-guard 要求）：不带 -X utf8 调用时不许静默输出空 ──
for _s in (sys.stdout, sys.stderr):
    if hasattr(_s, "reconfigure"):
        _s.reconfigure(encoding="utf-8", errors="replace")

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
ALB = os.path.join(ROOT, 'holo_pet_w3', 'voice-theater', 'assets', 'dh2d', 'albedo.png')
OUT = os.path.join(ROOT, 'outputs', 'dh-probe')

# 脸区搜索窗（图像像素坐标）
X0, X1, Y0, Y1 = 330, 415, 150, 195


def lip_mask(rgb):
    r, g, b = rgb[..., 0], rgb[..., 1], rgb[..., 2]
    # 唇：偏红、比皮肤暗（皮肤 R≈230 G≈210；唇 R≈180 G≈90）
    m = (r.astype(np.int16) - g.astype(np.int16) > 45) & \
        (r.astype(np.int16) - b.astype(np.int16) > 35) & \
        (g < 175) & (r < 235)
    return m


def main():
    im = Image.open(ALB).convert('RGB')
    a = np.asarray(im).astype(np.int16)
    win = a[Y0:Y1, X0:X1]
    m = lip_mask(win)

    ys, xs = np.nonzero(m)
    if len(xs) < 50:
        raise SystemExit('唇区没量到（阈值不对）')
    # 逐列取唇的上/下沿与最暗点（口缝）
    cols = {}
    for x in range(m.shape[1]):
        yy = np.nonzero(m[:, x])[0]
        if len(yy) >= 2:
            col = win[:, x]
            lum = col.sum(axis=1)
            dark = yy[np.argmin(lum[yy])]
            cols[x] = (int(yy.min()) + Y0, int(yy.max()) + Y0, int(dark) + Y0, len(yy))
    keys = sorted(cols)
    xs_abs = [k + X0 for k in keys]
    top = [cols[k][0] for k in keys]
    bot = [cols[k][1] for k in keys]
    seam = [cols[k][2] for k in keys]

    # 中线（唇最宽处）
    mid_i = int(np.argmax([cols[k][3] for k in keys]))
    cx = xs_abs[mid_i]
    seam_y = int(np.median(seam))
    lip_top = int(np.percentile(top, 12))
    lip_bot = int(np.percentile(bot, 88))

    # 色板：全部**从她的像素里采**
    def med(maskpx):
        v = maskpx.reshape(-1, 3)
        return [int(np.median(v[:, i])) for i in range(3)]
    lip_px = win[m]
    dark_px = win[(m) & (win.sum(axis=2) < np.percentile(win[m].sum(axis=1), 18))]
    skin_px = a[Y0:Y1, X0:X1][~m]

    # 唇的"形状"：把每列的唇上下沿做成一条轮廓（这才是她真正的嘴形，不是椭圆）
    contour = [[int(x), int(t), int(b), int(s)] for x, t, b, s in zip(xs_abs, top, bot, seam)]

    meta = {
        'ok': True,
        'win': [X0, X1, Y0, Y1],
        'lip_px': int(m.sum()),
        'x_span': [int(min(xs_abs)), int(max(xs_abs))],
        'y_span': [lip_top, lip_bot],
        'center_x': cx,
        'seam_y': seam_y,
        'palette': {
            'lip': med(lip_px),
            'lip_dark(口缝)': med(dark_px) if len(dark_px) else med(lip_px),
            'skin_hi(牙色参考)': [int(np.percentile(skin_px[:, i], 96)) for i in range(3)],
            'skin': med(skin_px),
        },
        'contour_n': len(contour),
        'note': '轮廓是逐列量出来的（她真实的嘴形），不是我用椭圆假定的',
    }

    # ── 静态原型：半开 / 大开，两种做法并排比
    jaw_hi = 0.85
    crops = []

    def base_crop():
        return im.crop((X0 - 6, Y0 - 10, X1 + 6, Y1 + 14)).copy()

    crops.append(('原图（闭）', base_crop()))

    # (A) 现在这版：几何椭圆 + 牙带（把真实唇盖住）
    src = base_crop().convert('RGBA')
    w, h = src.size
    ov = Image.new('RGBA', (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(ov)
    mx, my = cx - (X0 - 6), seam_y - (Y0 - 10)
    hw, hh = 30, 9
    d.ellipse([mx - hw, my - hh, mx + hw, my + hh], fill=tuple(meta['palette']['lip_dark(口缝)']) + (235,))
    d.rectangle([mx - hw * .6, my - hh, mx + hw * .6, my - hh * .25],
                fill=tuple(meta['palette']['skin_hi(牙色参考)']) + (230,))
    crops.append(('A 现在这版（椭圆+牙带）', Image.alpha_composite(src, ov)))

    # (B) 从她的唇像素衍化：下唇整体下移，缝里露出她自己唇暗部的颜色
    arr = np.asarray(base_crop().convert('RGB')).copy()
    H, W = arr.shape[:2]
    my_off = seam_y - (Y0 - 10)
    shift = int(round(14 * jaw_hi))
    lip_c = np.array(meta['palette']['lip'], np.float32)
    dark_c = np.array(meta['palette']['lip_dark(口缝)'], np.float32)
    seam_row = arr[my_off].astype(np.float32)
    out = arr.copy()
    # 下唇（my_off 以下、唇区内）按抛物线权重下移
    lipw = 30
    for y in range(my_off + 1, min(H, my_off + 16)):
        k = (y - my_off) / 12.0
        for x in range(max(0, mx - lipw), min(W, mx + lipw)):
            u = (x - mx) / float(lipw)
            if abs(u) > 1:
                continue
            f = k * (1.0 - u * u) ** 0.7
            sy = int(round(y - shift * f))
            if 0 <= sy < H:
                out[y, x] = arr[sy, x]
    # 缝里填"她自己的口腔色"（唇暗部再压暗一点）+ 一条极窄的牙
    for y in range(my_off - 1, my_off + shift + 2):
        for x in range(max(0, mx - lipw), min(W, mx + lipw)):
            u = (x - mx) / float(lipw)
            if abs(u) > 0.96:
                continue
            v = (y - (my_off - 1)) / float(shift + 3)
            if v < 0 or v > 1:
                continue
            if out[y, x].sum() > dark_c.sum() * 1.35:      # 只在"更亮=皮肤"的地方填
                base = dark_c * (1.0 - 0.35 * v)
                if v < 0.16:                                # 上沿一条牙
                    base = np.array(meta['palette']['skin_hi(牙色参考)'], np.float32) * 0.92
                out[y, x] = base
    crops.append(('B 从她的唇像素衍化', Image.fromarray(out)))

    # 拼图：每个 5 倍
    tiles = []
    for name, c in crops:
        c = c.resize((c.width * 5, c.height * 5), Image.LANCZOS)
        d2 = ImageDraw.Draw(c)
        d2.text((6, 6), name, fill=(255, 220, 80))
        tiles.append(c)
    w0, h0 = tiles[0].size
    sheet = Image.new('RGB', (w0 * len(tiles), h0), (0, 0, 0))
    for i, t in enumerate(tiles):
        sheet.paste(t, (i * w0, 0))
    sheet.save(os.path.join(OUT, 'mouth-ab.png'))

    meta['ab_png'] = os.path.join(OUT, 'mouth-ab.png')
    print('<<<GBT-MOUTH-LAB>>>')
    print(json.dumps(meta, ensure_ascii=False, indent=1))


if __name__ == '__main__':
    main()
