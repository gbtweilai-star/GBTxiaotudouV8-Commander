# -*- coding: utf-8 -*-
"""App Logo 处理 · 第二版。
第一版错在 cv2.floodFill 未加 FIXED_RANGE —— 容差按邻居递推，渐变一路啃进本体。
本版改为：候选背景 = (近白 OR 低饱和高亮) → 取「与边界连通」的连通域 → 其余为前景。
这样既去掉白底，也去掉底下的灰色投影，且不会吃掉土豆（土豆是饱和的棕黄色）。
"""
import base64
import io
import sys
from pathlib import Path

import cv2
import numpy as np
from PIL import Image

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:  # noqa: BLE001
    pass

BASE = next(p for p in Path(__file__).resolve().parents
            if (p / "gbt_allinone").is_dir())   # 修：原 `.parent.parent` 只到 tools/（少一层）
SRC = Path.home() / ".dsh" / "attachments" / "v1" / "objects" / "c7" / \
    "c7b9017c8eacbb5ac6f60f6f0b85bea57cbc8b7b31bd2022c1cb053044e898b1"
OUT = BASE / "assets" / "brand"
OUT.mkdir(parents=True, exist_ok=True)

raw = SRC.read_bytes()
img = Image.open(io.BytesIO(raw)).convert("RGB")
arr = np.array(img)
h, w = arr.shape[:2]

hsv = cv2.cvtColor(arr, cv2.COLOR_RGB2HSV)
S, V = hsv[:, :, 1], hsv[:, :, 2]
mn = arr.min(axis=2)

# 候选背景：近白（保留原判据）或 低饱和且很亮（灰色投影）
cand = ((mn > 232) | ((S < 44) & (V > 165))).astype(np.uint8)
print("候选背景占比: %.1f%%" % (100 * cand.mean()))

# 只保留与边界连通的候选 → 真正的背景
n_lab, labels = cv2.connectedComponents(cand, connectivity=4)
border_labels = set(labels[0, :]) | set(labels[-1, :]) | set(labels[:, 0]) | set(labels[:, -1])
border_labels.discard(0)
bg = np.isin(labels, list(border_labels))
print("连通到边界的背景: %.1f%%  (连通域 %d 个，贴边 %d 个)"
      % (100 * bg.mean(), n_lab - 1, len(border_labels)))

alpha = np.where(bg, 0, 255).astype(np.uint8)

# 边缘羽化：只在 alpha 边界处把硬边换成模糊值
soft = cv2.GaussianBlur(alpha, (5, 5), 0)
edge = cv2.Canny(alpha, 50, 150)
edge = cv2.dilate(edge, np.ones((3, 3), np.uint8), 1)
alpha = np.where(edge > 0, soft, alpha)

# 边界像素去白边（把半透明的边缘往本色拉，避免白晕）
rgba = np.dstack([arr, alpha]).astype(np.uint8)
full = Image.fromarray(rgba, "RGBA")

box = full.getchannel("A").point(lambda v: 255 if v > 10 else 0).getbbox()
print("内容包围盒:", box, "占比 %.1f%%" % (100 * (box[2] - box[0]) * (box[3] - box[1]) / (h * w)))

pad = int(max(box[2] - box[0], box[3] - box[1]) * 0.03)
lft, t, r, b = max(box[0] - pad, 0), max(box[1] - pad, 0), min(box[2] + pad, w), min(box[3] + pad, h)
side = max(r - lft, b - t)
crop = Image.new("RGBA", (side, side), (0, 0, 0, 0))
crop.paste(full.crop((lft, t, r, b)), ((side - (r - lft)) // 2, (side - (b - t)) // 2))
print("正方形化:", crop.size)

for n in (512, 256, 128, 64, 32):
    p = OUT / ("logo-potato-%d.png" % n)
    crop.resize((n, n), Image.LANCZOS).save(p, "PNG", optimize=True)
    print("  logo-potato-%-4d  %7d B   base64 %7d B" % (n, p.stat().st_size,
          len(base64.b64encode(p.read_bytes()))))

# App 图标：圆角方 + 白底（品牌观感），iOS squircle 近似
side_i, radius = 512, int(512 * 0.2237)
mm = np.zeros((side_i, side_i), np.uint8)
cv2.rectangle(mm, (radius, 0), (side_i - radius, side_i), 255, -1)
cv2.rectangle(mm, (0, radius), (side_i, side_i - radius), 255, -1)
for cx, cy in [(radius, radius), (side_i - radius, radius),
               (radius, side_i - radius), (side_i - radius, side_i - radius)]:
    cv2.circle(mm, (cx, cy), radius, 255, -1)
tile = Image.new("RGBA", (side_i, side_i), (255, 255, 255, 255))
inner = crop.resize((int(side_i * 0.92),) * 2, Image.LANCZOS)
tile.paste(inner, ((side_i - inner.width) // 2, (side_i - inner.height) // 2), inner)
tile.putalpha(Image.fromarray(mm, "L"))
pi = OUT / "icon-potato-512.png"
tile.save(pi, "PNG", optimize=True)
print("  icon-potato-512   %7d B   base64 %7d B" % (pi.stat().st_size,
      len(base64.b64encode(pi.read_bytes()))))
for n in (32, 64):
    p = OUT / ("favicon-potato-%d.png" % n)
    crop.resize((n, n), Image.LANCZOS).save(p, "PNG", optimize=True)
    print("  favicon-potato-%-3d %6d B" % (n, p.stat().st_size))
