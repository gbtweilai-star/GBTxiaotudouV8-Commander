# -*- coding: utf-8 -*-
"""生成小土豆品牌图标——**直接用她的开源头像**（icons/avatar.png）。

旧版是"GBT/小土豆V8/N caps"文字图标；2026-11-01 主人令：用她自己的头像。

口径：深底 + 顶部绿色圆角条 + 白色 GBT + 绿色 小土豆V8 + 灰色 <N> caps。
输出：icons/icon-512.png · icon-192.png · apple-touch-icon.png · favicon-32.png
用法：python tools/gen-potato-logo.py [--caps 385]
"""
from __future__ import annotations

import argparse
import pathlib
import sys

REPO = pathlib.Path(__file__).resolve().parents[1]
ICONS = REPO / "icons"
sys.path.insert(0, str(REPO))

BG = (11, 17, 30)
GREEN = (46, 204, 113)
GREEN_DARK = (34, 153, 84)
WHITE = (245, 247, 250)
GREY = (150, 158, 170)


def _font(size: int, bold: bool = True):
    from PIL import ImageFont
    cands = [
        r"C:\Windows\Fonts\msyhbd.ttc" if bold else r"C:\Windows\Fonts\msyh.ttc",
        r"C:\Windows\Fonts\simhei.ttf",
        r"C:\Windows\Fonts\arialbd.ttf" if bold else r"C:\Windows\Fonts\arial.ttf",
    ]
    for c in cands:
        try:
            return ImageFont.truetype(c, size)
        except Exception:  # noqa: BLE001
            continue
    return ImageFont.load_default()


def _text_center(draw, xy, text, font, fill, y_center=False):
    box = draw.textbbox((0, 0), text, font=font)
    w, h = box[2] - box[0], box[3] - box[1]
    x, y = xy
    if y_center:
        y = y - h // 2 - box[1]
    draw.text((x - w // 2, y), text, font=font, fill=fill)


def render(size: int, caps: int) -> "Image.Image":
    from PIL import Image, ImageDraw
    img = Image.new("RGB", (size, size), BG)
    d = ImageDraw.Draw(img)
    m = size / 512.0

    # 顶部绿色圆角条
    bar_h = int(56 * m)
    r = int(26 * m)
    d.rounded_rectangle([0, 0, size, bar_h + r], radius=r, fill=GREEN)

    # GBT
    f_gbt = _font(int(150 * m))
    _text_center(d, (size // 2, int(170 * m)), "GBT", f_gbt, WHITE)
    # 小土豆V8
    f_cn = _font(int(96 * m))
    _text_center(d, (size // 2, int(318 * m)), "小土豆V8", f_cn, GREEN)
    # N caps
    f_cap = _font(int(56 * m), bold=False)
    _text_center(d, (size // 2, int(420 * m)), "%d caps" % caps, f_cap, GREY)
    return img


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--caps", type=int, default=0)
    a = ap.parse_args()
    caps = a.caps
    if not caps:
        try:
            from gbt_allinone.caps_registry import BENIGN_CAPS
            caps = len(BENIGN_CAPS)
        except Exception:  # noqa: BLE001
            caps = 385
    ICONS.mkdir(parents=True, exist_ok=True)
    for name, size in (("icon-512.png", 512), ("icon-192.png", 192),
                       ("apple-touch-icon.png", 180), ("favicon-32.png", 32)):
        img = render(size, caps)
        img.save(ICONS / name, "PNG", optimize=True)
        print("写出:", ICONS / name, (ICONS / name).stat().st_size, "B")
    print("caps =", caps)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
