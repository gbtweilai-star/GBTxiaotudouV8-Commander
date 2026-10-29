# -*- coding: utf-8 -*-
"""生成开源仓门面横幅 `assets/brand/repo-banner.png`（**确定性、可复跑、零外链**）。

口径（每条都有出处，不是随手挑的）：
  · **色只用品牌真值**：`holo_pet_w3/deck3d.css` 现读 ——
      --gbt-gold `#F5B041` · --gbt-cyan `#00E5FF` · --gbt-violet `#7C4DFF`
      --gbt-deep `#03040C` / --gbt-deep-2 `#070A1A` · text `#E8ECF8` · dim `#9AA4C4`
    （品牌三色是白皮书冻结的，**不是自由挑的**）
  · **logo 用仓里现成的**：`assets/brand/logo-potato-256-alpha.png`
  · **数字一律现读**（能力位 / 域 / 用例数），**不许编**（审美规程 §3 P0-5 禁令）
  · 不用外链图床、不用 AI 生成图 —— 避免"AI 味"与脆弱的第三方依赖

用法：
    py -3.14 -X utf8 tools/codex-scripts/make-repo-banner.py
产物：
    assets/brand/repo-banner.png （1280×400）
"""
import io
import json
import os

from PIL import Image, ImageDraw, ImageFilter, ImageFont
import sys

# ── 编码守门（encoding-guard 要求）：不带 -X utf8 调用时不许静默输出空 ──
for _s in (sys.stdout, sys.stderr):
    if hasattr(_s, "reconfigure"):
        _s.reconfigure(encoding="utf-8", errors="replace")

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
W, H = 1280, 400
GOLD, CYAN, VIOLET = (245, 176, 65), (0, 229, 255), (124, 77, 255)
DEEP, DEEP2 = (3, 4, 12), (7, 10, 26)
TEXT, DIM = (232, 236, 248), (154, 164, 196)

FONTS = [
    r"C:\Windows\Fonts\msyhbd.ttc", r"C:\Windows\Fonts\msyh.ttc",
    r"C:\Windows\Fonts\SourceHanSansSC-Bold.otf", r"C:\Windows\Fonts\DengXian Bold.ttf",
    r"C:\Windows\Fonts\simhei.ttf",
]


def font(size):
    for f in FONTS:
        if os.path.isfile(f):
            try:
                return ImageFont.truetype(f, size)
            except OSError:
                continue
    return ImageFont.load_default()


def facts():
    """现读要写进横幅的真实数字（**读不到就不写**，绝不编）。"""
    out = {}
    try:
        atlas = json.load(io.open(os.path.join(ROOT, "state", "skill_atlas.json"), encoding="utf-8"))
        caps = atlas.get("caps") or []
        out["caps"] = len(caps)
        out["domains"] = len({c.get("domain") for c in caps})
    except Exception:  # noqa: BLE001
        pass
    n = 0
    for base in ("gbt_allinone/tests", "tests"):
        d = os.path.join(ROOT, base)
        if not os.path.isdir(d):
            continue
        for fn in os.listdir(d):
            if fn.startswith("test_") and fn.endswith(".py"):
                try:
                    n += io.open(os.path.join(d, fn), encoding="utf-8", errors="replace").read().count("def test_")
                except OSError:
                    pass
    if n:
        out["tests"] = n
    return out


def gradient():
    img = Image.new("RGB", (W, H), DEEP)
    px = img.load()
    for y in range(H):
        t = y / max(1, H - 1)
        row = tuple(int(DEEP[i] + (DEEP2[i] - DEEP[i]) * t) for i in range(3))
        for x in range(W):
            px[x, y] = row
    return img


def glow(img, cx, cy, radius, rgb, alpha):
    """软光晕：画在独立层上高斯模糊后叠加 —— 立体感的一半是光。"""
    lay = Image.new("RGB", (W, H), (0, 0, 0))
    d = ImageDraw.Draw(lay)
    d.ellipse([cx - radius, cy - radius, cx + radius, cy + radius], fill=rgb)
    lay = lay.filter(ImageFilter.GaussianBlur(radius * 0.55))
    return Image.blend(img, Image.blend(img, lay, 1.0), alpha)


def main():
    img = gradient()
    img = glow(img, int(W * 0.10), int(H * 0.80), 300, (0, 60, 90), 0.55)      # 青侧冷光
    img = glow(img, int(W * 0.92), int(H * 0.20), 280, (70, 45, 10), 0.55)      # 金侧暖光
    img = glow(img, int(W * 0.55), int(H * 1.05), 340, (30, 20, 70), 0.45)      # 紫侧底光
    d = ImageDraw.Draw(img)

    # 竖向细栅格（与整体仪器感相配的低对比纹理，不是装饰性 blob）
    for x in range(0, W, 64):
        d.line([(x, 0), (x, H)], fill=(255, 255, 255, 8), width=1)

    # logo（真件，带一圈柔光晕 → 让它"发光"而不是贴纸）
    lp = os.path.join(ROOT, "assets", "brand", "logo-potato-256-alpha.png")
    if os.path.isfile(lp):
        logo = Image.open(lp).convert("RGBA").resize((168, 168), Image.LANCZOS)
        halo = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        hd = ImageDraw.Draw(halo)
        hd.ellipse([96, 116, 96 + 168, 116 + 168], fill=(255, 200, 110, 90))
        halo = halo.filter(ImageFilter.GaussianBlur(46))
        img = Image.alpha_composite(img.convert("RGBA"), halo).convert("RGB")
        d = ImageDraw.Draw(img)
        img.paste(logo, (96, 116), logo)

    x0 = 316
    d.text((x0, 118), "GBT小土豆V8", font=font(62), fill=TEXT)
    d.text((x0 + 3, 196), "独立数字人框架 · 统一接口 · 全行为可审计",
           font=font(27), fill=DIM)
    d.line([(x0, 246), (x0 + 210, 246)], fill=GOLD, width=3)
    d.line([(x0 + 216, 246), (x0 + 330, 246)], fill=CYAN, width=3)
    d.line([(x0 + 336, 246), (x0 + 404, 246)], fill=VIOLET, width=3)

    f = facts()
    bits = []
    if f.get("caps"):
        bits.append("%d 个能力位" % f["caps"])
    if f.get("domains"):
        bits.append("%d 个域" % f["domains"])
    if f.get("tests"):
        bits.append("%d 项测试" % f["tests"])
    bits.append("Python ≥ 3.10 · 核心仅标准库")
    d.text((x0, 272), "  ·  ".join(bits), font=font(22), fill=(206, 214, 236))
    d.text((x0, 312), "开发者：自由的风   ·   本署名不可删除、不可篡改归属",
           font=font(19), fill=(128, 138, 170))

    out = os.path.join(ROOT, "assets", "brand", "repo-banner.png")
    img.save(out, "PNG", optimize=True)
    print("写好 %s（%dx%d · %d 字节）· 数字现读=%s"
          % (os.path.relpath(out, ROOT), W, H, os.path.getsize(out), f))


if __name__ == "__main__":
    main()
