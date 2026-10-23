# -*- coding: utf-8 -*-
"""把一次**真跑**的 demo stdout 回放成 15 秒 GIF（README 用）。

不是"合成一段好看的终端"：本脚本**只回放** `outputs/demo-gif/demo-run-raw.txt`，
那个文件是 `py -3.14 demo.py "我要把 Markdown 变成 PPT"` 的真实输出（2>&1 原样落盘）。
帧里自报"实跑回放"，不冒充录屏。

产物：outputs/open-source-release/assets/demo.gif（+ 预览帧 demo-lastframe.png）
用法：py -3.12 -X utf8 tools/codex-scripts/render-demo-gif.py
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
RAW = ROOT / "outputs" / "demo-gif" / "demo-run-raw.txt"
REL = ROOT / "outputs" / "open-source-release" / "assets"
OUT_GIF = REL / "demo.gif"
OUT_PNG = ROOT / "outputs" / "demo-gif" / "demo-lastframe.png"

W, H = 980, 600
PAD = 26
BAR = 44
FPS = 6
SECONDS = 15
BG = (10, 13, 18)
BAR_BG = (22, 28, 37)
TXT = (223, 230, 240)
DIM = (132, 146, 164)
GREEN = (88, 200, 120)
BLUE = (110, 168, 254)
AMBER = (240, 178, 76)
LINE_H = 21
FONT_SIZE = 15

# 字体里没有这些字形（渲染出来是豆腐块）⇒ 只为显示换写法，**不动文字本身**。
GLYPH = {"⚠️": "注意：", "⚠": "注意：", "✓": "OK ", "✅": "OK ", "⇒": "=>", "→": "->"}


def font(size: int = FONT_SIZE):
    for name in ("msyh.ttc", "simhei.ttf", "consola.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except Exception:                                     # noqa: BLE001
            continue
    return ImageFont.load_default()


def display(line: str) -> str:
    for bad, good in GLYPH.items():
        line = line.replace(bad, good)
    return line


def wrap(draw: ImageDraw.ImageDraw, line: str, f, width: int) -> list[str]:
    """按像素宽硬折行（中文没有空格，不能按词折）。"""
    out, cur = [], ""
    for ch in line:
        if draw.textlength(cur + ch, font=f) <= width:
            cur += ch
        else:
            out.append(cur)
            cur = ch
    out.append(cur)
    return out


def color_of(line: str):
    if line.startswith("①") or line.startswith("②") or line.startswith("③") or line.startswith("④"):
        return BLUE
    if "⚠️" in line or "✓" in line:
        return GREEN
    if line.strip().startswith("[1000.0]") or line.strip().startswith("[400.0]"):
        return AMBER
    if line.startswith("   py ") or line.startswith("   python "):
        return GREEN
    if line.startswith("   341") or line.startswith("   由 "):
        return DIM
    return TXT


def main() -> int:
    if not RAW.is_file():
        print("缺原始输出：%s（先跑 py -3.14 demo.py \"我要把 Markdown 变成 PPT\" 2>&1 > 该文件）" % RAW)
        return 1
    raw_lines = [ln.rstrip() for ln in RAW.read_text(encoding="utf-8", errors="replace").splitlines()]
    plain = [display(ln) for ln in raw_lines if ln.strip()] or ["（空输出）"]

    f = font()
    probe = ImageDraw.Draw(Image.new("RGB", (10, 10)))
    width = W - 2 * PAD
    lines: list[str] = []
    for ln in plain:
        if probe.textlength(ln, font=f) <= width:
            lines.append(ln)
        else:                                   # 长行按像素折，别让它冲出画面
            lines.extend(wrap(probe, ln, f, width))

    # 逐行累计字符流：按"打字机"逐字揭示，整段恰好铺满 15 秒
    total_chars = sum(len(ln) + 1 for ln in lines)
    frames = FPS * SECONDS
    per_frame = max(1, total_chars // frames + 1)
    height = min(H, BAR + PAD * 2 + LINE_H * len(lines) + 6)

    imgs = []
    for fi in range(frames + 1):
        shown = per_frame * fi
        img = Image.new("RGB", (W, height), BG)
        dr = ImageDraw.Draw(img)
        dr.rectangle([0, 0, W, BAR], fill=BAR_BG)
        for i, c in enumerate(((240, 95, 88), (245, 190, 80), (95, 200, 110))):
            dr.ellipse([18 + i * 22, 16, 30 + i * 22, 28], fill=c)
        dr.text((96, 13), "python demo.py \"我要把 Markdown 变成 PPT\"", font=font(14), fill=DIM)
        dr.text((W - 236, 13), "实跑回放 · stdout 原样", font=font(13), fill=DIM)

        y = BAR + PAD
        used = 0
        last_x, last_y = PAD, y
        for ln in lines:
            take = max(0, min(len(ln), shown - used))
            shown_line = ln[:take]
            dr.text((PAD, y), shown_line, font=f, fill=color_of(ln))
            last_x, last_y = PAD + int(dr.textlength(shown_line, font=f)), y
            used += len(ln) + 1
            y += LINE_H
            if used > shown:
                break
            if y > height - PAD - LINE_H:
                break
        if fi < frames:
            dr.rectangle([last_x + 2, last_y + 2, last_x + 11, last_y + 17], fill=GREEN)
        imgs.append(img)

    REL.mkdir(parents=True, exist_ok=True)
    imgs[-1].save(OUT_PNG)
    pal = [im.convert("P", palette=Image.ADAPTIVE, colors=40) for im in imgs]
    pal[0].save(OUT_GIF, save_all=True, append_images=pal[1:], duration=int(1000 / FPS),
                loop=0, optimize=True, disposal=2)
    print("已渲染 →", OUT_GIF, "·", round(OUT_GIF.stat().st_size / 1024, 1), "KB ·",
          "%d 帧 / %ds · %dx%d" % (len(imgs), SECONDS, W, H))
    print("末帧 →", OUT_PNG)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
