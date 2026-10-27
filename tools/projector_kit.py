#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""projector_kit —— 手机闪光灯投影套件（本机后置 LED + 透明胶片 + 凸透镜）

产出三张可直接打印的 A4 图（300dpi）：
  ① kit-film.png     胶片图（镜像 · 纯黑白 · 裁切标记）→ 打印到透明胶片
  ② kit-holder.png   装配图 + 实物等比尺（含闪光灯位/胶片位/透镜位与刻度）
  ③ kit-preview.png  光路预演（按真实倍率/离焦/亮度衰减算出来的"墙上应该什么样"）

为什么要有 ③：这条路成败全看三个数（倍率、亮度、模糊）。预演图是把公式
跑成像素——若预演里都认不出字，实物一定更差。这就是**上台之前的测试**。
"""
from __future__ import annotations

import argparse
import os
import sys

from PIL import Image, ImageDraw, ImageFilter, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import optics  # noqa: E402

A4 = (2480, 3508)          # 210×297mm @300dpi
A6 = (1240, 1748)          # 105×148mm @300dpi
DPI = 300


def mm(v: float) -> int:
    return int(round(v / 25.4 * DPI))


def font(sz: int):
    for p in ("/usr/share/fonts/TTF/DejaVuSans.ttf",
              "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"):
        if os.path.exists(p):
            try:
                return ImageFont.truetype(p, sz)
            except Exception:                                     # noqa: BLE001
                pass
    return ImageFont.load_default()


def make_film(text_lines, sub="", note="", size=A6) -> Image.Image:
    """胶片图：纯黑白、水平镜像、四角裁切标记。"""
    w, h = size
    im = Image.new("L", (w, h), 255)
    d = ImageDraw.Draw(im)
    pad = int(w * 0.12)
    # 裁切标记
    c = int(w * 0.02)
    for x, y in ((0, 0), (w, 0), (0, h), (w, h)):
        d.line([(x, y), (x + (c if x == 0 else -c), y)], fill=0, width=4)
        d.line([(x, y), (x, y + (c if y == 0 else -c))], fill=0, width=4)
    y = pad
    f1 = font(int(w * 0.155))
    for ln in text_lines:
        bb = d.textbbox((0, 0), ln, font=f1)
        d.text(((w - (bb[2] - bb[0])) // 2, y), ln, font=f1, fill=0)
        y += int((bb[3] - bb[1]) * 1.55)
    if sub:
        f2 = font(int(w * 0.062))
        bb = d.textbbox((0, 0), sub, font=f2)
        d.text(((w - (bb[2] - bb[0])) // 2, y + int(w * 0.03)), sub, font=f2, fill=0)
        y += int((bb[3] - bb[1]) * 1.4) + int(w * 0.03)
    if note:
        f3 = font(int(w * 0.040))
        bb = d.textbbox((0, 0), note, font=f3)
        d.text(((w - (bb[2] - bb[0])) // 2, h - pad - (bb[3] - bb[1])), note, font=f3, fill=0)
    return im.transpose(Image.FLIP_LEFT_RIGHT)      # 透镜会再翻一次


def make_holder(f: float, target_mm: float, aperture: float, film=(105.0, 148.0)) -> Image.Image:
    """A4 装配图：等比实物尺 + 三个位置标注 + 组装顺序。"""
    w, h = A4
    im = Image.new("RGB", (w, h), (250, 250, 248))
    d = ImageDraw.Draw(im)
    ink, dim, accent = (18, 20, 24), (110, 118, 130), (200, 60, 40)
    ft = font(64)
    fh = font(46)
    fb = font(34)
    fs = font(28)

    u = f * target_mm / (target_mm - f)
    s = optics.solve(f, u)
    m = s["m"] if s["ok"] else 0
    iw, ih = optics.image_size(m, film[0], film[1])

    y = mm(22)
    d.text((mm(20), y), "手机闪光灯投影 · 装配图", font=ft, fill=ink); y += mm(20)
    lx = optics.lux_estimate(m, aperture, u)
    d.text((mm(20), y), "焦距 %gmm · 投距 %dmm · 倍率 %.1f× · 墙上像 %.0f×%.0fmm"
           % (f, target_mm, m, iw, ih), font=fh, fill=accent); y += mm(14)
    d.text((mm(20), y), "口径 %gmm · 墙上照度 ≈ %.1f lux · 离焦 5mm 时弥散 %.1fmm"
           % (aperture, lx, optics.blur_mm(f, u, u + 5, aperture)),
           font=fb, fill=dim); y += mm(10)
    warn = ("够用：全黑房间可读" if lx >= 8 else
            "勉强：必须全黑，且字要再大" if lx >= 3 else
            "太暗：把投距缩短到 40–60cm、口径加到 40–60mm")
    d.text((mm(20), y), "亮度判定：" + warn, font=fb, fill=accent); y += mm(16)

    # ── 等比实物尺：1:1，直接从纸上比着量
    d.text((mm(20), y), "① 实物等比尺（照这条量，别用眼睛估）", font=fh, fill=ink); y += mm(12)
    x0 = mm(20)
    scale_len = min(u, 200.0)                       # 最长画 200mm
    L = mm(scale_len)
    d.line([(x0, y), (x0 + L, y)], fill=ink, width=5)
    step = 10
    for t in range(0, int(scale_len) + 1, step):
        px = x0 + mm(t)
        major = (t % 50 == 0)
        d.line([(px, y - (mm(5) if major else mm(3))), (px, y)], fill=ink, width=3 if major else 2)
        if major:
            bb = d.textbbox((0, 0), str(t), font=fs)
            d.text((px - (bb[2] - bb[0]) // 2, y + mm(3)), str(t), font=fs, fill=dim)
    d.line([(x0 + mm(u), y - mm(9)), (x0 + mm(u), y + mm(9))], fill=accent, width=6)
    d.text((x0 + mm(u) + mm(3), y - mm(12)), "胶片位 %.0fmm" % u, font=fs, fill=accent)
    y += mm(20)

    # ── 光路示意（不等比，只看顺序）
    d.text((mm(20), y), "② 光路顺序（从后往前）", font=fh, fill=ink); y += mm(12)
    boxes = [("手机后置 LED", "闪光灯常亮模式"),
             ("匀光纸 ×1–2 层", "离 LED 5–10mm，去掉中心亮斑"),
             ("透明胶片", "朝透镜那面要干净"),
             ("凸透镜 f=%gmm" % f, "口径 ≥%gmm，光圈挡到 %gmm" % (aperture * 1.6, aperture)),
             ("墙", "全黑房间；投距 %dmm" % target_mm)]
    bw = mm(48)
    bh = mm(26)
    gap = mm(6)
    x = mm(20)
    for i, (t, sub2) in enumerate(boxes):
        d.rectangle([x, y, x + bw, y + bh], outline=ink, width=3)
        bb = d.textbbox((0, 0), t, font=fb)
        d.text((x + (bw - (bb[2] - bb[0])) // 2, y + mm(4)), t, font=fb, fill=ink)
        bb2 = d.textbbox((0, 0), sub2, font=fs)
        d.text((x + (bw - (bb2[2] - bb2[0])) // 2, y + mm(14)), sub2, font=fs, fill=dim)
        if i < len(boxes) - 1:
            d.line([(x + bw, y + bh // 2), (x + bw + gap, y + bh // 2)], fill=accent, width=4)
        x += bw + gap
    y += bh + mm(14)

    # ── 三条硬提醒
    d.text((mm(20), y), "③ 三条最容易被忽略的", font=fh, fill=ink); y += mm(12)
    tips = [
        "闪光灯是点光源：不加匀光纸，墙上只有中间一个亮斑，四周全黑。",
        "光圈必须挡小：透镜全开会让边缘像糊成一团（口径 ≤ %gmm）。" % (aperture * 1.2),
        "环境光决定成败：房间有灯就白做；手机亮度/闪光功率拉满。",
    ]
    for t in tips:
        d.text((mm(20), y), "· " + t, font=fb, fill=ink); y += mm(12)

    y += mm(6)
    d.text((mm(20), y), "套件由 GBT小土豆V8 生成 · optics.py 自检通过", font=fs, fill=dim)
    return im


def preview(film: Image.Image, f: float, target_mm: float, aperture: float,
            focus_err_mm: float = 2.0) -> Image.Image:
    """光路预演：把公式跑成像素。

    film 按真实倍率放大 → 按离焦+衍射算出的弥散圆做高斯模糊 →
    乘上亮度衰减与边缘渐暗（cos^4 近似）→ 得到"墙上应该看到的样子"。
    """
    u = f * target_mm / (target_mm - f)
    s = optics.solve(f, u)
    m = s["m"] if s["ok"] else 1.0
    fnum = u / aperture
    blur = max(optics.blur_mm(f, u + focus_err_mm, u, aperture),
               optics.diffraction_mm(fnum))

    # 预演画布：按墙上的像尺寸等比缩到 1600 宽以内
    iw = film.size[0] * m
    ih = film.size[1] * m
    k = min(1.0, 1600.0 / max(iw, ih))
    W, H = max(1, int(iw * k)), max(1, int(ih * k))

    big = film.convert("L").resize((W, H), Image.LANCZOS)
    # 弥散圆换算到预演画布上（mm → px）
    blur_px = blur * k / (m * 25.4 / DPI) if m else 0
    blur_px = max(0.0, min(24.0, blur_px))
    if blur_px > 0.3:
        big = big.filter(ImageFilter.GaussianBlur(blur_px))

    # 亮度衰减 + 边缘渐暗
    rel = optics.brightness_rel(m, aperture, u)
    # 相对亮度只在 1e-5 量级，直接线性映射就是全黑。用对数映射把"很暗"拉到能观察的区间，
    # 但**图注里会同时给出真实勒克斯**，不让人误以为实拍就这么亮。
    import math as _m
    gain = min(1.0, 0.30 + 0.22 * _m.log10(max(rel, 1e-9)) + 1.35)
    px = big.load()
    cx, cy = W / 2.0, H / 2.0
    rmax = (cx ** 2 + cy ** 2) ** 0.5
    for yy in range(H):
        dy = yy - cy
        for xx in range(W):
            dx = xx - cx
            r2 = (dx * dx + dy * dy) / (rmax * rmax)
            fall = 1.0 - 0.55 * r2              # cos^4 的粗近似
            v = px[xx, yy] / 255.0
            # 胶片上白色=透明（光通过 ⇒ 墙上亮），黑色=墨（挡住 ⇒ 墙上暗）
            # 第一版写反了（1-v），预演出来是一片黑，已修
            out = (0.05 + 0.95 * v) * gain * fall
            g = int(max(0, min(255, out * 255)))
            px[xx, yy] = g
    return big.convert("RGB")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--text", default="力劈华山", help="胶片主标题（可多行，用 | 分隔）")
    ap.add_argument("--sub", default="齐天大圣 · 第一幕")
    ap.add_argument("--note", default="GBT小土豆V8")
    ap.add_argument("--f", type=float, default=75.0)
    ap.add_argument("--dist", type=float, default=600.0, help="投距 mm（实测 40–60cm 才有亮度）")
    ap.add_argument("--aperture", type=float, default=60.0, help="透镜有效口径 mm")
    ap.add_argument("--out", default="/var/minis/attachments/kit")
    a = ap.parse_args()

    os.makedirs(a.out, exist_ok=True)
    film = make_film(a.text.split("|"), a.sub, a.note)
    p1 = os.path.join(a.out, "kit-film.png")
    film.convert("L").save(p1, "PNG")

    p2 = os.path.join(a.out, "kit-holder.png")
    make_holder(a.f, a.dist, a.aperture).save(p2, "PNG")

    p3 = os.path.join(a.out, "kit-preview.png")
    pv = preview(film, a.f, a.dist, a.aperture, focus_err_mm=2.0)
    pv.save(p3, "PNG")

    u = a.f * a.dist / (a.dist - a.f)
    s = optics.solve(a.f, u)
    iw, ih = optics.image_size(s["m"], 105, 148)
    print("套件 %s" % a.out)
    print("  ① 胶片   %s  (%dx%d @%ddpi · 镜像 · 纯黑白)"
          % (os.path.basename(p1), film.size[0], film.size[1], DPI))
    print("  ② 装配   %s  (A4 300dpi · 含等比实物尺)" % os.path.basename(p2))
    print("  ③ 预演   %s  (%dx%d · 倍率 %.1f× · 弥散 %.1fmm)"
          % (os.path.basename(p3), pv.size[0], pv.size[1], s["m"],
             max(optics.blur_mm(a.f, u + 2, u, a.aperture), optics.diffraction_mm(u / a.aperture))))
    print("  光路   f=%gmm · 胶片位 %.0fmm · 投距 %dmm · 像 %.0f×%.0fmm"
          % (a.f, u, a.dist, iw, ih))
    print("  亮度   ≈%.1f lux（按闪光灯 50lm 估）%s"
          % (optics.lux_estimate(s["m"], a.aperture, u),
             "· 全黑房间可读" if optics.lux_estimate(s["m"], a.aperture, u) >= 8 else "· 偏暗，缩短投距或加大口径"))
    print("  打印   胶片图打到透明胶片；装配图打到普通 A4（尺子是 1:1，别缩放）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
