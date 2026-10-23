# -*- coding: utf-8 -*-
"""决定内嵌规格：比 PNG vs WebP；并把 Logo 压到本 App 的真实底色上出预览图看效果。"""
import base64
import sys
from pathlib import Path

from PIL import Image

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:  # noqa: BLE001
    pass

BASE = next(p for p in Path(__file__).resolve().parents
            if (p / "gbt_allinone").is_dir())   # 修：原 `.parent.parent` 只到 tools/（少一层）
OUT = BASE / "assets" / "brand"
crop = Image.open(OUT / "logo-potato-512.png").convert("RGBA")

print("── PNG vs WebP（带 alpha）──")
print("  %-6s %12s %12s %12s %12s" % ("尺寸", "PNG", "WebP q92", "WebP q80", "WebP 无损"))
best = {}
for n in (512, 256, 192, 128, 64, 32):
    im = crop.resize((n, n), Image.LANCZOS)
    p_png = OUT / ("logo-potato-%d.png" % n)
    im.save(p_png, "PNG", optimize=True)
    row = [p_png.stat().st_size]
    for q in (92, 80):
        p = OUT / ("logo-potato-%d-q%d.webp" % (n, q))
        im.save(p, "WEBP", quality=q, method=6)
        row.append(p.stat().st_size)
    p = OUT / ("logo-potato-%d-lossless.webp" % n)
    im.save(p, "WEBP", lossless=True, quality=100, method=6)
    row.append(p.stat().st_size)
    best[n] = row
    print("  %-6d %12d %12d %12d %12d" % (n, *row))

print()
print("── 内嵌成本（base64）──")
for n in (192, 128, 64, 32):
    q92 = OUT / ("logo-potato-%d-q92.webp" % n)
    b = len(base64.b64encode(q92.read_bytes()))
    print("  %-4d q92 webp: 文件 %6d B → base64 %7d B" % (n, q92.stat().st_size, b))

# ── 深色底预览：把 Logo 贴在 App 真实底色 #04070f 上 ──
BG = (4, 7, 15, 255)
strip = Image.new("RGBA", (560, 170), BG)
x = 16
for n in (128, 96, 64, 44, 32, 24):
    im = crop.resize((n, n), Image.LANCZOS)
    strip.alpha_composite(im, (x, 16 + (128 - n) // 2))
    x += n + 22
# 侧栏徽标实况：20px 贴在一个圆角tile里
tile = Image.new("RGBA", (22, 22), (18, 48, 73, 255))
mini = crop.resize((18, 18), Image.LANCZOS)
tile.alpha_composite(mini, (2, 2))
strip.alpha_composite(tile, (x, 69))
prev = OUT / "_preview-on-dark.png"
strip.save(prev)
print()
print("深色底预览:", prev.name)
