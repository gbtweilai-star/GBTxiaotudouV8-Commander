# -*- coding: utf-8 -*-
"""按交付件里的真实 CSS 数值，合成品牌位样张（不是浏览器截图 —— 是无头浏览器起不来时的替代取证）。
数值全部照抄 V13 交付件：侧栏 .logo 34px / .hero .orb 64px / 画布 .brandmark 22px。
"""
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:  # noqa: BLE001
    pass

BASE = next(p for p in Path(__file__).resolve().parents
            if (p / "gbt_allinone").is_dir())   # 修：原 `.parent.parent` 只到 tools/（少一层）
BR = BASE / "assets" / "brand"
logo = Image.open(BR / "logo-potato-512.png").convert("RGBA")

VOID = (4, 7, 15)
PANEL = (8, 17, 31)
PANEL2 = (12, 26, 46)
LINE = (88, 196, 255)
INK = (223, 242, 251)
INK2 = (184, 207, 218)
INK3 = (143, 169, 184)
NEON = (42, 212, 240)


def font(sz, bold=False):
    """CJK 字体优先；msyh.ttc / simsun.ttc 是 TTC 集合，要指定 index。"""
    cands = [("msyhbd.ttc", 0) if bold else ("msyh.ttc", 0),
             ("Dengb.ttf", 0) if bold else ("Deng.ttf", 0),
             ("NotoSansSC-VF.ttf", 0), ("simhei.ttf", 0), ("segoeuib.ttf", 0) if bold else ("segoeui.ttf", 0)]
    for name, idx in cands:
        try:
            f = ImageFont.truetype("C:/Windows/Fonts/" + name, sz, index=idx)
            if f.getmask("中").getbbox():   # 确认真的有中文字形
                return f
        except OSError:
            continue
    return ImageFont.load_default()


def glow(img, radius, color, alpha):
    """在图像不透明区域外扩一圈柔光。"""
    a = img.getchannel("A").point(lambda v: min(255, int(v * alpha)))
    g = Image.new("RGBA", img.size, color + (0,))
    g.putalpha(a)
    g = g.filter(ImageFilter.GaussianBlur(radius))
    out = g.copy()
    out.alpha_composite(img)
    return out


W, H = 980, 470
canvas = Image.new("RGBA", (W, H), VOID + (255,))
d = ImageDraw.Draw(canvas)

# ── 1. 侧栏品牌行（真值：面板底 #08111f，logo 34px，青色 drop-shadow 8px）──
y0 = 24
d.rounded_rectangle([24, y0, W - 24, y0 + 66], 12, fill=PANEL, outline=LINE + (36,), width=1)
d.text((44, y0 + 12), "侧栏品牌行 · .logo 34px", font=font(11), fill=INK3)
lg = logo.resize((34, 34), Image.LANCZOS)
canvas.alpha_composite(glow(lg, 8, NEON, 0.45), (44, y0 + 22))
d.text((90, y0 + 24), "GBT小土豆V8", font=font(14, True), fill=INK)
d.text((90, y0 + 44), "你的全能 AI 助手 · 从想法到落地", font=font(10), fill=INK3)

# ── 2. 画布页眉（真值：bar 高 42，brandmark 22px，右侧「上帝视角」胶囊）──
y1 = y0 + 92
d.rounded_rectangle([24, y1, W - 24, y1 + 42], 10, fill=PANEL, outline=LINE + (36,), width=1)
d.text((W - 24 - 150, y1 - 20), "画布页眉 · .brandmark 22px（43 页统一）", font=font(11), fill=INK3)
bm = logo.resize((22, 22), Image.LANCZOS)
canvas.alpha_composite(glow(bm, 6, NEON, 0.5), (40, y1 + 10))
d.text((72, y1 + 13), "大脑执行层 · 五维链路", font=font(12, True), fill=INK)
pill = [W - 24 - 92, y1 + 10, W - 24 - 12, y1 + 32]
d.rounded_rectangle(pill, 11, fill=(42, 212, 240, 26), outline=LINE + (87,), width=1)
d.text((pill[0] + 12, y1 + 14), "上帝视角", font=font(10), fill=(110, 242, 255))

# ── 3. 对话空态（真值：.hero .orb 64px，青色 drop-shadow 16px）──
y2 = y1 + 76
d.rounded_rectangle([24, y2, W - 24, y2 + 170], 12, fill=PANEL2, outline=LINE + (36,), width=1)
d.text((44, y2 + 10), "对话空态 · .hero .orb 64px", font=font(11), fill=INK3)
ob = logo.resize((64, 64), Image.LANCZOS)
cx = W // 2
canvas.alpha_composite(glow(ob, 16, NEON, 0.52), (cx - 32, y2 + 30))
t1 = "你想让我们在 GBT小土豆V8 中构建什么？"
d.text((cx - d.textlength(t1, font=font(17, True)) / 2, y2 + 104), t1, font=font(17, True), fill=INK)
t2 = "140 项可执行能力 · 30 个能力域 · 20 项需授权 · 5 项接线缺口"
d.text((cx - d.textlength(t2, font=font(11)) / 2, y2 + 132), t2, font=font(11), fill=INK3)

out = BR / "_preview-brand-in-context.png"
canvas.convert("RGB").save(out)
print("样张:", out.name, "%.0f KB" % (out.stat().st_size / 1024))
