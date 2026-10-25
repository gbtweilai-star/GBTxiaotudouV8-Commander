# -*- coding: utf-8 -*-
"""把真渲染出来的截图拼成总览缩略图（contact sheet），便于一眼看全。"""
import json
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
BASE = next(p for p in Path(__file__).resolve().parents
            if (p / "gbt_allinone").is_dir())   # 修：原 `.parent.parent` 只到 tools/（少一层）
R = BASE / ".scratch" / "render"


def font(sz, bold=False):
    for n in (("msyhbd.ttc", 0) if bold else ("msyh.ttc", 0), ("Deng.ttf", 0), ("simhei.ttf", 0)):
        try:
            f = ImageFont.truetype("C:/Windows/Fonts/" + n[0], sz, index=n[1])
            if f.getmask("总").getbbox():
                return f
        except OSError:
            continue
    return ImageFont.load_default()


def sheet(src_dir, report, out, cols=6, tw=330, title=""):
    shots = report["shots"]
    if not shots:
        print("无截图:", src_dir)
        return
    th = int(tw * 0.625)          # 16:10 缩略
    pad, lab = 10, 22
    rows = (len(shots) + cols - 1) // cols
    head = 46 if title else 0
    W = cols * (tw + pad) + pad
    H = head + rows * (th + lab + pad) + pad
    img = Image.new("RGB", (W, H), (8, 12, 20))
    d = ImageDraw.Draw(img)
    if title:
        d.text((pad + 4, 14), title, font=font(20, True), fill=(223, 242, 251))
    for i, s in enumerate(shots):
        p = src_dir / s["file"]
        if not p.is_file():
            continue
        c, r = i % cols, i // cols
        x = pad + c * (tw + pad)
        y = head + pad + r * (th + lab + pad)
        im = Image.open(p).convert("RGB")
        # 等比缩放到 tw×th 内，居中放到深色底上
        sc = min(tw / im.width, th / im.height)
        im2 = im.resize((max(1, int(im.width * sc)), max(1, int(im.height * sc))), Image.LANCZOS)
        tile = Image.new("RGB", (tw, th), (4, 7, 15))
        tile.paste(im2, ((tw - im2.width) // 2, (th - im2.height) // 2))
        img.paste(tile, (x, y))
        d.rectangle([x - 1, y - 1, x + tw, y + th], outline=(30, 60, 92))
        d.text((x + 2, y + th + 4), s.get("label", "")[:30], font=font(12), fill=(150, 180, 200))
    img.save(out)
    print("总览:", out.name, "%dx%d" % (W, H), "%.1f MB" % (out.stat().st_size / 1048576))


rep = json.loads((R / "report.json").read_text(encoding="utf-8"))
sheet(R / "panels", rep, R / "contact_panels.png", cols=6, tw=330,
      title="GBT小土豆V8 · 可交互原型 V17 · 55 面板真渲染总览（Chrome 1680×1050）")

cpath = R / "canvas_report.json"
if cpath.is_file():
    crep = json.loads(cpath.read_text(encoding="utf-8"))
    crep["shots"] = [{"file": "00_overview.png", "label": "全景"}] + crep["shots"]
    sheet(R / "canvas", crep, R / "contact_canvas.png", cols=6, tw=330,
          title="GBT小土豆V8 · 无限画布 V17 · 58 页真渲染总览（Chrome 1680×1050）")
