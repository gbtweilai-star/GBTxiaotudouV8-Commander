# -*- coding: utf-8 -*-
"""把逐帧渲染图拼成一条（验收动画用）。
用法: python tools/codex-scripts/compose-strip.py <角色/动作名> <时间列表逗号分隔> <输出名>
例:   python tools/codex-scripts/compose-strip.py walk "0.00,0.28,0.55,0.83" 动画条-walk.png
读的是 render/帧-<名>-<时间>.png（由 shot-glb.py 逐帧渲染产生）"""
import pathlib
import sys
from PIL import Image, ImageDraw

WS = pathlib.Path(r"C:\Users\ADMIN\Desktop\GBT小土豆V8")
R = WS / "render"

name, times, outname = sys.argv[1], sys.argv[2].split(','), sys.argv[3]
ims = []
for t in times:
    p = R / f"帧-{name}-{t}.png"
    if not p.exists():
        raise SystemExit(f"缺帧文件: {p}")
    ims.append(Image.open(p).convert("RGB"))
h = 520
ims = [im.resize((int(im.width * h / im.height), h), Image.LANCZOS) for im in ims]
w = ims[0].width
sheet = Image.new("RGB", (w * len(ims), h + 34), (18, 22, 34))
d = ImageDraw.Draw(sheet)
for i, (im, t) in enumerate(zip(ims, times)):
    sheet.paste(im, (i * w, 34))
    d.text((i * w + 8, 10), f"{name} t={t}s", fill=(0, 229, 255))
    d.line([i * w, 34, i * w, h + 34], fill=(124, 77, 255), width=1)
out = R / outname
sheet.save(out)
print("saved:", out, sheet.size)
