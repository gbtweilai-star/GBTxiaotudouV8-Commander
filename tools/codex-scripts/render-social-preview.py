# -*- coding: utf-8 -*-
"""渲染 GitHub 社交预览图 1280×640（仓库 Settings → Social preview 上传用）。

原则（照本仓 P7）：**先看再交** —— 渲染完必须亲眼看一遍：字有没有豆腐块、有没有被裁掉、
在缩到 600px 宽时还读不读得出来。

产物：outputs/open-source-release/assets/social-preview.png
用法：py -3.12 -X utf8 tools/codex-scripts/render-social-preview.py
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
OUT = ROOT / "outputs" / "open-source-release" / "assets" / "social-preview.png"

W, H = 1280, 640
BG = (9, 12, 17)
CARD = (18, 24, 33)
LINE = (34, 44, 58)
TXT = (235, 240, 248)
DIM = (150, 163, 180)
GREEN = (63, 185, 80)
BLUE = (88, 166, 255)
AMBER = (240, 178, 76)


def font(size: int, mono: bool = False):
    names = ("consola.ttf", "CascadiaMono.ttf") if mono else ("msyh.ttc", "simhei.ttf")
    for name in names:
        try:
            return ImageFont.truetype(name, size)
        except Exception:                                     # noqa: BLE001
            continue
    return ImageFont.load_default()


def main() -> int:
    img = Image.new("RGB", (W, H), BG)
    dr = ImageDraw.Draw(img)

    # 左侧竖条 + 顶部细线：给缩略图一点结构感
    dr.rectangle([0, 0, 10, H], fill=GREEN)
    dr.line([(10, 0), (W, 0)], fill=LINE, width=2)

    dr.text((56, 54), "GBT小土豆V8 · 总指挥大模型", font=font(58), fill=TXT)
    dr.text((58, 132), "把自然语言落到 341 位能力上 · 写盘 / 花钱 / 出网一律先过人闸 · 每次调用都留审计",
            font=font(26), fill=DIM)

    # 三块硬读数
    blocks = [
        ("341", "位原生能力 · 30 个域", GREEN),
        ("99.10%", "335 题基准 PASS45", BLUE),
        ("0", "失败（341 位逐位真跑）", AMBER),
    ]
    x = 58
    for value, label, color in blocks:
        dr.rounded_rectangle([x, 214, x + 372, 398], radius=16, fill=CARD, outline=LINE, width=2)
        dr.text((x + 28, 240), value, font=font(72), fill=color)
        dr.text((x + 28, 336), label, font=font(24), fill=DIM)
        x += 396

    # 一条命令
    dr.rounded_rectangle([58, 442, W - 58, 528], radius=14, fill=CARD, outline=LINE, width=2)
    dr.text((84, 458), "python demo.py", font=font(28, mono=True), fill=GREEN)
    dr.text((318, 458), '"我要把 Markdown 变成 PPT"', font=font(28), fill=TXT)
    dr.text((84, 496), "零依赖 · 不需要 GPU · 不需要模型权重 · 秒回「该调哪一位、要什么票」",
            font=font(21), fill=DIM)

    dr.text((58, 566), "单门执行 run_task(kind, payload) · 授权 · 审计 · 钢印 都在这一处",
            font=font(22), fill=TXT)
    dr.text((58, 600), "开发者：自由的风 · Apache-2.0 · 本署名不可删除、不可篡改归属", font=font(18), fill=(120, 132, 148))
    tail = "github.com/gbtweilai-star"
    tail_font = font(18, mono=True)
    tail_w = dr.textlength(tail, font=tail_font)
    dr.text((W - 58 - tail_w, 600), tail, font=tail_font, fill=(120, 132, 148))

    OUT.parent.mkdir(parents=True, exist_ok=True)
    img.save(OUT)
    print("已渲染 →", OUT, "·", OUT.stat().st_size, "bytes ·", "%dx%d" % img.size)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
