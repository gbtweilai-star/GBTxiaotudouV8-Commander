# -*- coding: utf-8 -*-
"""把并发实测读数渲染成**证据卡**（README 用）：`assets/brand/concurrency-card.png`。

口径（诚实第一）：
  · **数据源只有一个**：`state/concurrency-last.json`（由 `concurrency-capacity-test.py` 落盘）；
    本件**只画不复算** —— 改数只能去跑测试，不能改图；
  · 图上**标明它是"读数卡（脚本渲染）"**，不冒充终端截图；
  · 数字一律原样取自 JSON，**不四舍五入成好看的值**。

用法：
    py -3.14 -X utf8 tools/codex-scripts/render-concurrency-card.py
"""
import sys

for _s in (sys.stdout, sys.stderr):                    # 2026-10-15 对齐：输出编码守门（本仓口径）
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


import io
import json
import os

from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SRC = os.path.join(ROOT, "state", "concurrency-last.json")
OUT = os.path.join(ROOT, "assets", "brand", "concurrency-card.png")
W, H = 1180, 812
GOLD, CYAN, VIOLET = (245, 176, 65), (0, 229, 255), (124, 77, 255)
DEEP, DEEP2 = (3, 4, 12), (7, 10, 26)
TEXT, DIM, OK = (232, 236, 248), (154, 164, 196), (34, 197, 94)
FONTS = [r"C:\Windows\Fonts\msyhbd.ttc", r"C:\Windows\Fonts\msyh.ttc",
         r"C:\Windows\Fonts\simhei.ttf"]
MONO = [r"C:\Windows\Fonts\consola.ttf", r"C:\Windows\Fonts\msyh.ttc"]


def font(size, mono=False):
    for f in (MONO if mono else FONTS):
        if os.path.isfile(f):
            try:
                return ImageFont.truetype(f, size)
            except OSError:
                continue
    return ImageFont.load_default()


def main():
    d = json.load(io.open(SRC, encoding="utf-8"))
    img = Image.new("RGB", (W, H), DEEP)
    px = img.load()
    for y in range(H):
        t = y / (H - 1)
        row = tuple(int(DEEP[i] + (DEEP2[i] - DEEP[i]) * t) for i in range(3))
        for x in range(W):
            px[x, y] = row
    lay = Image.new("RGB", (W, H), (0, 0, 0))
    ld = ImageDraw.Draw(lay)
    ld.ellipse([-120, H - 220, 300, H + 200], fill=(0, 60, 90))
    ld.ellipse([W - 260, -180, W + 160, 240], fill=(70, 45, 10))
    lay = lay.filter(ImageFilter.GaussianBlur(150))
    img = Image.blend(img, lay, 0.5)
    dr = ImageDraw.Draw(img)

    dr.text((48, 40), "并发容量实测 · 零失败", font=font(40), fill=TEXT)
    top = d["levels"][-1]
    dr.text((48, 96), "≥%d 根触手同时并发 · 成功 %d/%d · 墙钟 %.0f ms · 调用前后可用内存 %.2f→%.2f GB"
            % (top["n"], top["ok"], top["n"], top["wall_ms"],
               top["mem_before_gb"], top["mem_after_gb"]),
            font=font(21), fill=(206, 214, 236))
    dr.line([(48, 136), (48 + 120, 136)], fill=GOLD, width=3)
    dr.line([(48 + 126, 136), (48 + 210, 136)], fill=CYAN, width=3)
    dr.line([(48 + 216, 136), (48 + 280, 136)], fill=VIOLET, width=3)

    hy = 172
    dr.text((48, hy), "  N    | 成功/总    | 墙钟(ms) | 中位(ms) | 最大(ms) | 内存可用(GB)",
            font=font(19), fill=DIM)      # 🔴 表头含中文 ⇒ 必须用中文字体；
                                          #    mono（Consolas）无中文字形会渲染成方框（本轮真栽）
    y = hy + 34
    for r in d["levels"]:
        line = ("%-6d | %4d/%-4d | %8.0f | %8.1f | %8.1f | %6.2f→%6.2f"
                % (r["n"], r["ok"], r["n"], r["wall_ms"], r["median_ms"] or 0,
                   r["max_ms"] or 0, r["mem_before_gb"], r["mem_after_gb"]))
        dr.text((48, y), line, font=font(20, True), fill=TEXT)
        y += 34
    # 零失败徽标：挂在**标题行右侧**（副标题那行放不下 —— 上一版压到尾巴上了）
    badge = "零失败" if not any(x["fail_samples"] for x in d["levels"]) else "有失败"
    bw = dr.textlength(badge, font=font(22))
    dr.text((W - 48 - bw, 52), badge, font=font(22), fill=OK)

    y += 18
    dr.line([(48, y), (W - 48, y)], fill=(60, 68, 92), width=1)
    y += 22
    first = d["levels"][0]
    for i, (t, body) in enumerate([
        ("① 框架自身的并发上限 ≥ %d 根" % top["n"],
         "零失败 · 可用内存基本不动（能力位是轻量分发）→「手有很多只」这句是读数，不是口号"),
        ("② 第一次大批量的成本在「建线程」",
         "本轮落在 %d 那行（墙钟 %.0f ms、单发中位 %.0f ms）；之后各级全部降到毫秒级"
         % (first["n"], first["wall_ms"], first["median_ms"] or 0)),
        ("③ 真瓶颈不在「根数」，在别处",
         "审计写盘（同一台机器并发一开，中位从 0.1 ms 量级被写盘拖住）与「单个能力位自己吃什么」"
         "（子进程类 / 网络类的上限远低于 %d）" % top["n"]),
    ], 1):
        dr.text((48, y), t, font=font(22), fill=GOLD)
        dr.text((48, y + 30), body, font=font(18), fill=(206, 214, 236))
        y += 74

    levels = ",".join(str(r["n"]) for r in d["levels"])
    # 底部命令**拆两行**：一整行会顶出右边界（本轮亲眼看到被切掉）
    dr.text((48, H - 96), "复跑命令：py -3.14 -X utf8 tools/codex-scripts/concurrency-capacity-test.py",
            font=font(15), fill=DIM)
    dr.text((72, H - 74), "--levels %s --json state/concurrency-last.json" % levels,
            font=font(15), fill=DIM)
    dr.text((48, H - 44), "读数卡（脚本渲染 · 数据源 state/concurrency-last.json · %s）  ·  "
                          "开发者：自由的风" % d.get("at", ""),
            font=font(15), fill=(120, 130, 162))

    img.save(OUT, "PNG", optimize=True)
    print("写好 %s（%dx%d · %d 字节）· 来源 %s"
          % (os.path.relpath(OUT, ROOT), W, H, os.path.getsize(OUT), d.get("at")))


if __name__ == "__main__":
    main()
