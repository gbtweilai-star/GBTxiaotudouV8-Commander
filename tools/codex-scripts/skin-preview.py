# -*- coding: utf-8 -*-
"""仙侠 × 科技 · 皮肤预览页生成器（第 74 轮 · Owner 令）

## 两条必须先说清的边界

1. 🔴 **不用《仙剑奇侠传》的任何素材**。那是第三方版权图，抠来当皮肤 =
   把别人的东西塞进成品，本仓家规第 2 条不允许。所以这里的画面是
   **本机 PIL 程序化绘制**的（山峦/月/石窟/人物剪影/霓虹），
   **出处无歧义 ⇒ 许可如实写「自有」**。
2. 🔴 本器**只生预览页**，**不动任何现有页面**。落地成客户端插件是下一步，
   等主人挑定方向再做 —— 「先给你看，再动手」是本仓一贯的做法。

## 画的是什么

三档配色，同一套构图（这样比的是**配色**，不是比谁的图好看）：
   A 冷青仙侠 —— 靛蓝夜空 + 青玉光 + 细霓虹
   B 金紫仙门 —— 深紫 + 鎏金 + 暖霓虹
   C 水墨霓虹 —— 墨黑留白 + 品红/青双霓虹

## 跑法

    py -3.14 tools/codex-scripts/skin-preview.py
"""

import base64
import io
import math
import random
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = next(p for p in Path(__file__).resolve().parents if (p / "gbt_allinone").is_dir())
ART_DIR = ROOT / "projects" / "_shared" / "brand" / "skin"
OUT = ROOT / "skin-preview.html"
W, H = 1280, 800
SIGN = "开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属"

# 三档配色：每档给「天上 → 山中 → 人物 → 光」四组色，人物一律是剪影（不画脸 = 不冒充肖像）
PALETTES = {
    "A": {"名": "冷青仙侠", "desc": "靛蓝夜空 · 青玉灵光 · 细霓虹",
          "sky": ((8, 14, 34), (18, 30, 62), (10, 20, 40)),
          "moon": (196, 232, 226), "glow": (86, 224, 214), "ridge": (12, 20, 38),
          "near": (6, 10, 22), "neon": ((88, 226, 214), (126, 168, 255)),
          "ink": (222, 240, 240)},
    "B": {"名": "金紫仙门", "desc": "深紫天幕 · 鎏金殿影 · 暖霓虹",
          "sky": ((22, 10, 38), (56, 22, 74), (26, 12, 40)),
          "moon": (255, 232, 186), "glow": (255, 196, 96), "ridge": (34, 16, 48),
          "near": (14, 8, 24), "neon": ((255, 196, 96), (206, 132, 255)),
          "ink": (255, 238, 208)},
    "C": {"名": "水墨霓虹", "desc": "墨黑留白 · 品红/青双霓虹",
          "sky": ((6, 6, 8), (16, 16, 20), (8, 8, 10)),
          "moon": (240, 240, 244), "glow": (255, 92, 176), "ridge": (18, 18, 22),
          "near": (4, 4, 6), "neon": ((255, 92, 176), (96, 240, 232)),
          "ink": (238, 238, 242)},
}


def _lerp(a, b, t):
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


def _sky(img, p):
    d = ImageDraw.Draw(img)
    c0, c1, c2 = p["sky"]
    for y in range(H):
        t = y / H
        c = _lerp(c0, c1, t / 0.55) if t < 0.55 else _lerp(c1, c2, (t - 0.55) / 0.45)
        d.line([(0, y), (W, y)], fill=c)


def _stars(img, p, rng):
    d = ImageDraw.Draw(img)
    for _ in range(220):
        x, y = rng.randrange(W), rng.randrange(int(H * 0.62))
        r = rng.choice((0, 0, 0, 1))
        a = rng.randint(40, 150)
        d.ellipse([x, y, x + r, y + r], fill=p["moon"] + (a,) if False else _lerp(p["sky"][0], p["moon"], a / 255))


def _moon(img, p, cx, cy, r):
    """月亮 + 两层辉光（辉光靠模糊图层做，不是硬画一圈）。"""
    gl = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(gl).ellipse([cx - r * 2.6, cy - r * 2.6, cx + r * 2.6, cy + r * 2.6],
                               fill=p["moon"] + (58,))
    gl = gl.filter(ImageFilter.GaussianBlur(58))
    img.alpha_composite(gl)
    d = ImageDraw.Draw(img)
    d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=p["moon"] + (238,))
 # 第一版在月面正中画了个内圆 ⇒ 看着像**甜甜圈**。改成**偏心的淡淡阴影**（像月海）。
    d.ellipse([cx - r * 0.72, cy - r * 0.85, cx + r * 0.05, cy - r * 0.10],
              fill=_lerp(p["moon"], p["sky"][1], 0.10) + (70,))
    d.ellipse([cx + r * 0.15, cy + r * 0.10, cx + r * 0.70, cy + r * 0.62],
              fill=_lerp(p["moon"], p["sky"][1], 0.10) + (54,))


def _ridges(img, p, rng, base_y, amp, color, seed_pts=9):
    """山脊：折线 + 竖直填充（剪影），多层叠出纵深。"""
    d = ImageDraw.Draw(img)
    pts = [(0, base_y + rng.randint(-amp, amp))]
    for i in range(1, seed_pts + 1):
        x = W * i / seed_pts
        y = base_y + rng.randint(-amp, amp)
        pts.append((x, y))
    pts.append((W, base_y + rng.randint(-amp, amp)))
    d.polygon(pts + [(W, H), (0, H)], fill=color + (255,))


def _pagoda(img, p, x, base_y, scale):
    """塔/殿剪影：几层收分的檐 + 塔身。科技那面靠霓虹描边点出来。"""
    d = ImageDraw.Draw(img)
    col = p["near"] + (255,)
    tiers, w = 4, 96 * scale
    y = base_y
    for i in range(tiers):
        ww = w * (1 - i * 0.19)
        d.polygon([(x - ww, y), (x + ww, y), (x + ww * 0.72, y - 16 * scale),
                   (x - ww * 0.72, y - 16 * scale)], fill=col)
 # PIL 的 rectangle 要求 y1 ≥ y0（我第一版写成 [y-16, y-42] ⇒ 报
        #    「y1 must be greater than or equal to y0」）—— 上下要**升序**给。
        d.rectangle([x - ww * 0.42, y - 42 * scale, x + ww * 0.42, y - 16 * scale], fill=col)
        y -= 42 * scale
    d.line([(x, y), (x, y - 34 * scale)], fill=col, width=max(2, int(4 * scale)))
    d.ellipse([x - 7 * scale, y - 48 * scale, x + 7 * scale, y - 34 * scale],
              fill=p["glow"] + (200,))


def _figure(img, p, x, base_y, s):
    """仙侠人物**剪影**（不画脸 —— 剪影不是肖像，也就不涉及肖像权）。

    宽袖 + 长发 + 飘带，三样就能让人一眼认出"仙侠"。

    ⚠️ 第一版画坏了（我 `read_image` 亲眼看的）：飘带的宽度给到 `5*s` 且弧太长
    ⇒ 看着像**两条蜘蛛腿**；袖子是两片尖三角。改：飘带**细**（宽 2）、**短**、
    贴身后扬；袖子改成**圆润的垂坠**而不是尖角；整体收小一点。
    """
 # 第二版仍然读不出"仙侠"：暗剪影贴在暗山脊上 = 一团（我又 read_image 看了一次）。
    #    ⇒ 改画法：先在本层画**纯黑**，再整层合成两次 ——
    #    先一层**模糊的轮廓光**（偏移一点点），再压上本体。**有边光才立得起来。**
    lay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(lay)
    col = (0, 0, 0, 255)
    # 长裙（收分的梯形，落地略散）
    d.polygon([(x - 15 * s, base_y - 92 * s), (x + 15 * s, base_y - 92 * s),
               (x + 46 * s, base_y - 2 * s), (x - 46 * s, base_y - 2 * s)], fill=col)
    # 上襦
    d.polygon([(x - 16 * s, base_y - 152 * s), (x + 16 * s, base_y - 152 * s),
               (x + 20 * s, base_y - 88 * s), (x - 20 * s, base_y - 88 * s)], fill=col)
    # 宽袖：**垂坠的圆角**（不是尖三角）
    for sgn in (-1, 1):
        d.polygon([(x + sgn * 14 * s, base_y - 150 * s),
                   (x + sgn * 34 * s, base_y - 144 * s),
                   (x + sgn * 46 * s, base_y - 116 * s),
                   (x + sgn * 40 * s, base_y - 92 * s),
                   (x + sgn * 20 * s, base_y - 96 * s)], fill=col)
    # 头 + 长发（发是往下垂的，不是一团）
    hx, hy, r = x, base_y - 168 * s, 11 * s
    d.ellipse([hx - r, hy - r, hx + r, hy + r], fill=col)
    d.polygon([(hx - r * 1.15, hy - r * 0.85), (hx + r * 1.15, hy - r * 0.85),
               (hx + r * 1.05, hy + 62 * s), (hx - r * 1.05, hy + 62 * s)], fill=col)
    d.ellipse([hx - r * 1.5, hy - r * 1.4, hx + r * 1.5, hy + r * 0.3], fill=col)
    # 飘带：**细而短**，一上一下两条，贴身往后扬
    for k, (sgn, rise) in enumerate(((-1, 26), (1, 14))):
        pts = []
        for i in range(16):
            t = i / 15
            pts.append((x + sgn * (18 + 66 * t) * s,
                        base_y - (118 + rise * math.sin(t * 2.4)) * s + (34 * t) * s))
        d.line(pts, fill=col, width=max(2, int(2.4 * s)), joint="curve")
    # 轮廓光：模糊后的 alpha 当遮罩，染成灵光色，偏左上一点点 ⇒ 有边光才立得起来
    a = lay.filter(ImageFilter.GaussianBlur(5)).getchannel("A").point(lambda v: int(v * 0.9))
    glow = Image.new("RGBA", (W, H), p["glow"] + (255,))
    glow.putalpha(a)
    img.alpha_composite(glow, (-4, -3))
    img.alpha_composite(lay)


def _neon(img, p, rng, horizon):
    """科技那面：地平线网格 + 几条电路走向的发光折线。"""
    gl = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    dg = ImageDraw.Draw(gl)
    c = p["neon"]
 # 第一版网格 alpha 只给 46 又画在深色近山上 ⇒ **肉眼几乎看不见**（我 read_image 亲眼看出来的）。
    #    改：地平线打一条亮的，网格提亮，纵向线只留近处几根。
    dg.line([(0, horizon), (W, horizon)], fill=c[1] + (150,), width=2)
    for i in range(10):
        y = horizon + int((H - horizon) * (i / 9.0) ** 1.6)
        dg.line([(0, y), (W, y)], fill=c[0] + (96,), width=1)
    for i in range(-7, 8):
        x0 = W / 2 + i * 130
        dg.line([(x0, H), (W / 2 + i * 14, horizon)], fill=c[1] + (72,), width=1)
    for _ in range(6):
        x, y = rng.randrange(0, W), rng.randrange(horizon - 60, H)
        pts = [(x, y)]
        for _ in range(4):
            x += rng.choice((-1, 1)) * rng.randint(30, 90)
            y += rng.choice((-1, 1)) * rng.randint(14, 40)
            pts.append((x, y))
        dg.line(pts, fill=c[1] + (150,), width=2, joint="curve")
    gl = gl.filter(ImageFilter.GaussianBlur(2.2))
    img.alpha_composite(gl)
    img.alpha_composite(gl)          # 叠两遍 = 更像发光


def _petals(img, p, rng):
    d = ImageDraw.Draw(img)
    for _ in range(60):
        x, y = rng.randrange(W), rng.randrange(H)
        r = rng.randint(2, 5)
        d.ellipse([x, y, x + r * 2, y + r], fill=p["glow"] + (rng.randint(40, 120),))


def render(tag):
    p = PALETTES[tag]
    rng = random.Random(20260923 + ord(tag))
    img = Image.new("RGBA", (W, H), (0, 0, 0, 255))
    _sky(img, p)
    _stars(img, p, rng)
    _moon(img, p, int(W * 0.76), int(H * 0.20), 58)
    horizon = int(H * 0.70)
    _ridges(img, p, rng, int(H * 0.60), 34, _lerp(p["ridge"], p["glow"], 0.10))
    _pagoda(img, p, int(W * 0.16), int(H * 0.66), 1.05)
    _ridges(img, p, rng, int(H * 0.72), 26, p["ridge"])
    _neon(img, p, rng, horizon)
    _figure(img, p, int(W * 0.32), int(H * 0.955), 1.15)
    _petals(img, p, rng)
    # 顶部压暗，给标题留可读区
    sh = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(sh).rectangle([0, 0, W, 150], fill=(0, 0, 0, 120))
    img.alpha_composite(sh.filter(ImageFilter.GaussianBlur(30)))
    return img.convert("RGB")


def main():
    ART_DIR.mkdir(parents=True, exist_ok=True)
    print("=" * 74)
    print("仙侠 × 科技 · 皮肤预览生成")
    print("=" * 74)
    print("  素材来源：**本机 PIL 程序化绘制**（不取用任何第三方素材）⇒ 许可：自有")
    print("  人物：**剪影**（不画脸 —— 剪影不是肖像）")
    _, arts = [], []
    for tag in ("A", "B", "C"):
        p = PALETTES[tag]
        im = render(tag)
        fp = ART_DIR / ("skin-%s.png" % tag)
        im.save(fp, "PNG", optimize=True)
        b = io.BytesIO()
        im.resize((W // 2, H // 2), Image.LANCZOS).quantize(colors=160).save(
            b, "PNG", optimize=True)
        b64 = base64.b64encode(b.getvalue()).decode("ascii")
        arts.append((tag, p, b64, fp.stat().st_size, len(b.getvalue())))
        print("  %s %-8s 落盘 %-28s %6.0f KB ｜ 内嵌缩图 %5.0f KB"
              % (tag, p["名"], fp.relative_to(ROOT).as_posix(), fp.stat().st_size / 1024,
                 len(b.getvalue()) / 1024))

    parts = ["""<!doctype html><html lang="zh-CN"><head><meta charset="utf-8">
<title>GBT小土豆V8 · 仙侠×科技 皮肤预览</title><style>
*{box-sizing:border-box}body{margin:0;background:#07090F;color:#E8EEF7;
font:13.5px/1.7 "Segoe UI","Microsoft YaHei",system-ui,sans-serif}
.wrap{max-width:1280px;margin:0 auto;padding:26px 22px 56px}
h1{font-size:22px;margin:0 0 6px;letter-spacing:.5px}
.sub{color:#93A3B8;font-size:12.5px;margin-bottom:18px}
.note{border:1px solid #2A3A2E;background:rgba(63,185,80,.06);border-radius:8px;
padding:11px 13px;font-size:12.5px;margin:14px 0 22px}
.note b{color:#8FD46A}
.card{border:1px solid #1E3A5F;border-radius:14px;overflow:hidden;margin:20px 0;
position:relative;min-height:430px}
.bg{position:absolute;inset:0;background-size:cover;background-position:center;
filter:saturate(1.04)}
.veil{position:absolute;inset:0;background:linear-gradient(180deg,rgba(4,8,16,.72),rgba(4,8,16,.88))}
.inner{position:relative;padding:20px 22px}
.tag{display:inline-block;font-size:11px;padding:3px 10px;border-radius:999px;
border:1px solid rgba(255,255,255,.28);margin-right:8px}
.ttl{font-size:17px;font-weight:600;letter-spacing:.4px}
.desc{color:#B9C7D8;font-size:12.5px;margin-top:4px}
.mock{display:grid;grid-template-columns:1.35fr 1fr;gap:14px;margin-top:16px}
@media(max-width:900px){.mock{grid-template-columns:1fr}}
.pane{border:1px solid rgba(255,255,255,.14);border-radius:10px;padding:12px 14px;
background:rgba(10,16,28,.62);backdrop-filter:blur(6px)}
.pane h4{margin:0 0 9px;font-size:12.5px;color:#9FB3C8;font-weight:600;letter-spacing:.6px}
.bub{border-radius:10px;padding:8px 11px;margin:7px 0;font-size:12.5px;max-width:92%}
.me{margin-left:auto;background:linear-gradient(135deg,var(--a),var(--b));color:#06101C;
font-weight:600}
.ai{background:rgba(255,255,255,.07);border:1px solid rgba(255,255,255,.12)}
.grid3{display:grid;grid-template-columns:1fr 1fr;gap:8px}
.tile{border:1px solid rgba(255,255,255,.13);border-radius:8px;padding:8px 10px;
font-size:12px;background:rgba(255,255,255,.04)}
.tile b{display:block;color:var(--a);font-size:12.5px;margin-bottom:2px}
.code{font-family:Consolas,monospace;font-size:11.5px;color:#CFE3F5;
background:rgba(0,0,0,.36);border-radius:8px;padding:9px 11px;line-height:1.65;
border:1px solid rgba(255,255,255,.1);white-space:pre;overflow:auto}
.sw{display:flex;gap:7px;margin-top:11px;flex-wrap:wrap}
.sw i{width:26px;height:26px;border-radius:7px;display:block;border:1px solid rgba(255,255,255,.24)}
.sig{color:#7E8CA0;font-size:11.5px;margin-top:26px;text-align:center}
</style></head><body><div class="wrap">
<h1>GBT小土豆V8 · 仙侠 × 科技 · 皮肤预览</h1>
<div class="sub">三档配色同一套构图 —— 比的是<b>配色</b>，不是比谁的图好看。挑一档，我再落地到客户端插件。</div>
<div class="note"><b>素材来源（必须先说）</b>：画面是<b>本机 PIL 程序化绘制</b>的 ——
山峦 / 月 / 石窟塔影 / 人物剪影 / 霓虹网格，<b>没有取用《仙剑奇侠传》或任何第三方素材</b>，
许可如实写「自有」。人物是<b>剪影</b>（不画脸），所以也不涉及肖像。<br>
<b>本页只是预览</b>：没有改动任何现有页面；落地成插件是下一步。</div>"""]
    for tag, p, b64, disk, emb in arts:
        a, b = p["neon"]
        sws = "".join('<i style="background:rgb(%d,%d,%d)"></i>' % c
                      for c in (p["sky"][0], p["sky"][1], p["moon"], p["glow"], a, b))
        parts.append("""
<div class="card" style="--a:rgb(%d,%d,%d);--b:rgb(%d,%d,%d)">
 <div class="bg" style="background-image:url('data:image/png;base64,%s')"></div>
 <div class="veil"></div><div class="inner">
  <span class="tag">方向 %s</span><span class="ttl">%s</span>
  <div class="desc">%s</div>
  <div class="sw">%s</div>
  <div class="mock">
   <div class="pane"><h4>编程对话面板</h4>
    <div class="bub me">把这个模块的测试补齐，跑一遍给我看</div>
    <div class="bub ai">已补 12 条判据，覆盖边界与拒绝路径。<code>pytest</code> <b>100 passed</b>。</div>
    <div class="bub me">顺便把 lint 过一遍</div>
    <div class="bub ai">ruff 无告警；mypy 尚未安装 ⇒ <b>未验</b>，不冒充通过。</div>
   </div>
   <div class="pane"><h4>面板栅格</h4>
    <div class="grid3">
     <div class="tile"><b>三方向工作流</b>18 格 · 有货 6</div>
     <div class="tile"><b>试听台</b>-14.00 LUFS</div>
     <div class="tile"><b>能力球</b>158 项</div>
     <div class="tile"><b>上帝视角</b>12/12</div>
    </div>
    <div class="code">$ py -3.14 tools/codex-scripts/media_flow.py
汇总：有货 6 · 仅彩排 9 · 空 3
验收判据：3 条问题（P0 1）</div>
   </div>
  </div>
 </div></div>""" % (a[0], a[1], a[2], b[0], b[1], b[2], b64, tag, p["名"], p["desc"], sws))
    parts.append('<div class="sig">%s</div></div></body></html>' % SIGN)
    OUT.write_text("".join(parts), encoding="utf-8")
    print("\n  预览页：%s（%.2f MB · 自包含 · 内嵌三档缩图）"
          % (OUT.relative_to(ROOT).as_posix(), OUT.stat().st_size / 1e6))
    print("  看它  ：http://127.0.0.1:3080/gbt-master/fs/skin-preview.html")
    print("  ⚠️ 未做：**没有改动任何现有页面**；落地成客户端插件待主人挑定方向。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
