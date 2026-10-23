# -*- coding: utf-8 -*-
"""把 render/godview/ 六个标签页拼成一张总览图（带标签），便于一眼看全。"""
from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = next(p for p in Path(__file__).resolve().parents
            if (p / "holo_pet_w3").is_dir() and (p / "gbt_allinone").is_dir())
SRC = ROOT / "render" / "godview"
OUT = ROOT / "render" / "总览-上帝视角6页.png"
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ORDER = [
    ("quad_四视图.png", "① 四视图（看自己/任务/环境/账本）"),
    ("tree_工作树.png", "② 工作树（193 节点 · text 兜底引擎）"),
    ("matrix_故障矩阵.png", "③ 故障矩阵（58 点 · 四模态）"),
    ("cockpit_驾驶舱.png", "④ 驾驶舱（只读态）"),
    ("tools_工具.png", "⑤ 工具出口（只读态）"),
    ("pets_数字人.png", "⑥ 数字人 / AI 朋友圈"),
]

imgs = [(SRC / f, cap) for f, cap in ORDER if (SRC / f).exists()]
if not imgs:
    print("没有可拼的图")
    raise SystemExit(1)

CELL_W = 720
BAR = 26
SCALE = CELL_W / imgs[0][0].stat().st_size and CELL_W  # 固定宽
tiles = []
for p, cap in imgs:
    im = Image.open(p).convert("RGB")
    h = int(im.height * (CELL_W / im.width))
    tiles.append((im.resize((CELL_W, h), Image.LANCZOS), cap))

COLS = 2
ROWS = (len(tiles) + COLS - 1) // COLS
cell_h = max(t.height for t, _ in tiles) + BAR
PAD = 14
W = COLS * CELL_W + PAD * (COLS + 1)
H = ROWS * cell_h + PAD * (ROWS + 1)

sheet = Image.new("RGB", (W, H), (8, 10, 20))
d = ImageDraw.Draw(sheet)
try:
    font = ImageFont.truetype("C:/Windows/Fonts/msyh.ttc", 17)
except Exception:
    font = ImageFont.load_default()

for i, (t, cap) in enumerate(tiles):
    r, c = divmod(i, COLS)
    x = PAD + c * (CELL_W + PAD)
    y = PAD + r * (cell_h + PAD)
    d.text((x + 2, y + 3), cap, fill=(245, 176, 65), font=font)
    sheet.paste(t, (x, y + BAR))

sheet.save(OUT, optimize=True)
print("拼图:", OUT.relative_to(ROOT), sheet.size, "%.1f MB" % (OUT.stat().st_size / 1e6))
