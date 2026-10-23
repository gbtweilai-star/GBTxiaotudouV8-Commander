# -*- coding: utf-8 -*-
"""生成 PWA 图标（192 / 512 / apple-touch 180），给 iPhone「添加到主屏幕」与 Android「安装应用」用。

产物：outputs/open-source-release/icons/icon-192.png · icon-512.png · apple-touch-icon.png
用法：py -3.12 -X utf8 tools/codex-scripts/render-pwa-icons.py
"""
from __future__ import annotations

import pathlib

from PIL import Image, ImageDraw, ImageFont
import sys
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        pass

ROOT = pathlib.Path(__file__).resolve().parents[2]
OUT = ROOT / "outputs" / "open-source-release" / "icons"
BG = (10, 13, 18)
GREEN = (63, 185, 80)
TXT = (235, 240, 248)
DIM = (150, 163, 180)


def font(size: int):
    for name in ("msyh.ttc", "simhei.ttf", "consola.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except Exception:                                     # noqa: BLE001
            continue
    return ImageFont.load_default()


def make(size: int) -> Image.Image:
    s = 4                                   # 4 倍超采样后缩，边缘才干净
    img = Image.new("RGB", (size * s, size * s), BG)
    dr = ImageDraw.Draw(img)
    W = size * s
    # 圆角底 + 顶部绿条
    dr.rounded_rectangle([0, 0, W - 1, W - 1], radius=int(W * 0.22), fill=BG)
    dr.rounded_rectangle([0, 0, W - 1, int(W * 0.14)], radius=int(W * 0.22), fill=GREEN)
    big = font(int(W * 0.30))
    t = "GBT"
    tw = dr.textlength(t, font=big)
    dr.text(((W - tw) / 2, W * 0.28), t, font=big, fill=TXT)
    small = font(int(W * 0.17))
    t2 = "小土豆V8"
    tw2 = dr.textlength(t2, font=small)
    dr.text(((W - tw2) / 2, W * 0.63), t2, font=small, fill=GREEN)
    t3 = "341 caps"
    f3 = font(int(W * 0.10))
    tw3 = dr.textlength(t3, font=f3)
    dr.text(((W - tw3) / 2, W * 0.83), t3, font=f3, fill=DIM)
    return img.resize((size, size), Image.LANCZOS)


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    for size, name in ((192, "icon-192.png"), (512, "icon-512.png"), (180, "apple-touch-icon.png")):
        p = OUT / name
        make(size).save(p)
        print("已渲染 →", p, "·", p.stat().st_size, "bytes ·", "%dx%d" % (size, size))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
