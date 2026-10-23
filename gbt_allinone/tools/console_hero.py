# gbt-capability: console_hero
# ⛔ 开发者：自由的风 · 永久钢印 · 禁止删除
"""主视觉与卡库：让**每一个页面都有视觉感**（主人令 2026-09-28，附 8 张参考图）。

## 读数（按 `gbt-aesthetic` §0：先读题，再动手）
参考图是一套**同一视觉语言**的卡库：深空底 → **一张电影感主视觉** → 小号彩色**类目签**
→ 大号粗体**标题** → 一两行摘要 → 「阅读文章 →」；圆角 14–16px、发丝描边、单一强调色，
主视觉里常有英文技术小字（`GRAPH ENGINEERING / SYSTEM MAP 02`、`The 5C Framework`）。

⇒ 把它落成我们的契约：**每页顶部一条 hero 带**（主视觉 + 类目签 + 大字标题 + 摘要 + CTA）
+ **一页卡库**（全部页面以卡片排开，就是参考图那个版式）。品牌三色**白皮书冻结**（土豆金/赛博青/深空紫），
**不引第四强调色**；§1.5 血账照旧：**数据页字必须正、整页不许摇**——冲击只花在 hero 与签名元素上。

## 主视觉怎么来（诚实说明）
参考图的 3D 是**模型生成的图**。本机 ComfyUI（966 节点）能生成，但在 **CPU** 上每张要等很久
（20 页 × 多张 = 数小时）⇒ 本件先用**程序化主视觉**：确定性 SVG（分层辉光 + 透视网格 + 几何体 +
扫描线），**同名同图**（截图可复现）、**零外部依赖**（无外链图床，过审美禁令 P0-6）。
ComfyUI 版作为**升级路径**：`console_hero.plan_batch()` 出批量生图计划（要 filesystem_write）。

## 六个原型（按页名哈希分配 ⇒ 每页不同、且稳定）
`orb`（球体核心）· `racks`（机柜阵列）· `cubes`（立方体群）· `highway`（光路）·
`graph`（节点图，代理编排那类）· `wave`（声波，音乐那类）
"""
from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]

ARCHETYPES = ("orb", "racks", "cubes", "highway", "graph", "wave")
# 类目签配色：只用品牌三色（不引第四色）
ACCENTS = {"赛博青": "#00E5FF", "土豆金": "#F5B041", "深空紫": "#7C4DFF"}


def _hash(s: str, salt: int = 0) -> int:
    return int(hashlib.sha256(("%s|%d" % (s, salt)).encode()).hexdigest()[:8], 16)


def pick_archetype(seed: str, hint: str = "") -> str:
    """按页名取原型；`hint` 可强制（音乐页给 wave、代理编排给 graph）。"""
    if hint in ARCHETYPES:
        return hint
    return ARCHETYPES[_hash(seed) % len(ARCHETYPES)]


def hero_svg(kind: str = "orb", seed: str = "page", accent: str = "#00E5FF",
             sub: str = "GBT SYSTEM MAP") -> str:
    """确定性主视觉（同名同图）。

    ⚠️ 血账（2026-09-28 第二轮）：第一版主体**太小**、画面 80% 是空黑 —— 一眼看去像"小挂件"，
    不是参考图那种**被填满的场景**（§3 死法①：太小）。修法四条：
      ① 主体放大 2–3 倍；② 加**透视地面 + 地平线**把空间撑起来（静止的纵深）；
      ③ 辉光更大更强（光是立体感的一半）；④ 叠**扫描线 + 暗角**做仪器质感。
    """
    h = _hash(seed, 7)
    rnd = [(h >> (i % 24)) % 100 for i in range(16)]
    glow = "".join(
        f"<radialGradient id='g{i}' cx='{25 + (rnd[i] * 3) % 55}%' cy='{30 + (rnd[i + 1] * 2) % 45}%' r='72%'>"
        f"<stop offset='0' stop-color='{accent}' stop-opacity='{0.42 - i * 0.11:.2f}'/>"
        f"<stop offset='1' stop-color='{accent}' stop-opacity='0'/></radialGradient>"
        for i in range(3))
    # 透视地面：从地平线放射的纵深线 + 横向渐密的层线（把"空"填成"空间"）
    hz = 300
    rad = "".join(
        f"<line x1='600' y1='{hz}' x2='{-700 + i * 290}' y2='520' "
        f"stroke='{accent}' stroke-opacity='.10'/>" for i in range(9))
    lay = "".join(
        f"<line x1='0' y1='{hz + int(220 * (i / 6) ** 1.7)}' x2='1200' "
        f"y2='{hz + int(220 * (i / 6) ** 1.7)}' stroke='{accent}' "
        f"stroke-opacity='{0.05 + i * 0.012:.2f}'/>" for i in range(1, 7))
    floor = f"<g class='floor'>{rad}{lay}<line x1='0' y1='{hz}' x2='1200' y2='{hz}' " \
            f"stroke='{accent}' stroke-opacity='.18'/></g>"
    body = ""
    if kind == "orb":
        r = 150 + rnd[0] % 60
        body = (f"<circle cx='600' cy='252' r='{r}' fill='none' stroke='{accent}' stroke-opacity='.6' "
                f"stroke-width='2'/>"
                f"<circle cx='600' cy='252' r='{int(r * 0.8)}' fill='url(#g0)'/>"
                f"<circle cx='600' cy='252' r='{int(r * 0.46)}' fill='{accent}' fill-opacity='.10'/>"
                f"<ellipse cx='600' cy='252' rx='{int(r * 2.1)}' ry='{int(r * 0.5)}' fill='none' "
                f"stroke='{accent}' stroke-opacity='.34' stroke-width='1.5'/>"
                f"<ellipse cx='600' cy='252' rx='{int(r * 1.6)}' ry='{int(r * 0.34)}' fill='none' "
                f"stroke='#F5B041' stroke-opacity='.28'/>"
                f"<ellipse cx='600' cy='252' rx='{int(r * 2.6)}' ry='{int(r * 0.64)}' fill='none' "
                f"stroke='#7C4DFF' stroke-opacity='.20'/>"
                f"<circle cx='600' cy='252' r='11' fill='{accent}'/>")
    elif kind == "racks":
        for i in range(9):
            x = 60 + i * 128
            hh = 190 + (rnd[i] % 130)
            body += (f"<rect x='{x}' y='{hz + 8 - hh}' width='104' height='{hh}' rx='9' "
                     f"fill='#0C121C' stroke='{accent}' stroke-opacity='.42'/>")
            for j in range(1, 7):
                y = hz + 8 - hh + j * (hh // 7)
                body += (f"<rect x='{x + 13}' y='{y}' width='78' height='7' rx='3' "
                         f"fill='{accent}' fill-opacity='{0.20 + (rnd[(i + j) % 16] % 45) / 100:.2f}'/>")
    elif kind == "cubes":
        for i in range(11):
            x, y, s = 90 + (rnd[i % 16] % 1020), 90 + (rnd[(i + 3) % 16] % 230), 64 + (rnd[(i + 5) % 16] % 74)
            body += (f"<g transform='translate({x},{y})'>"
                     f"<path d='M0,{s} L{s},{-s * 0.5} L{s * 2},{s} L{s},{-s * 2.5} Z' "
                     f"fill='none' stroke='{accent}' stroke-opacity='.62' stroke-width='1.5'/>"
                     f"<path d='M0,{s} L{s},{s * 2.5} L{s * 2},{s} L{s},{-s * 0.5} Z' "
                     f"fill='{accent}' fill-opacity='.09' stroke='{accent}' stroke-opacity='.32'/></g>")
    elif kind == "highway":
        body = (f"<path d='M60,510 L560,{hz} L660,{hz} L360,510 Z' fill='url(#g0)'/>"
                f"<path d='M60,510 L560,{hz}' stroke='{accent}' stroke-opacity='.62' stroke-width='5'/>"
                f"<path d='M360,510 L660,{hz}' stroke='#F5B041' stroke-opacity='.55' stroke-width='5'/>"
                f"<path d='M210,510 L610,{hz}' stroke='{accent}' stroke-opacity='.28' stroke-width='2'/>"
                f"<rect x='520' y='{hz - 46}' width='230' height='92' rx='12' fill='#0C121C' "
                f"stroke='{accent}' stroke-opacity='.5'/>"
                f"<rect x='545' y='{hz - 22}' width='180' height='12' rx='6' fill='{accent}' "
                f"fill-opacity='.5'/>")
    elif kind == "graph":
        pts = [(140 + (rnd[i % 16] * 8) % 940, 80 + (rnd[(i + 2) % 16] * 3) % 260) for i in range(12)]
        for i, (x, y) in enumerate(pts):
            if i:
                x0, y0 = pts[max(0, i - 3)]
                body += (f"<line x1='{x0}' y1='{y0}' x2='{x}' y2='{y}' stroke='{accent}' "
                         f"stroke-opacity='.30' stroke-width='1.6'/>")
        for i, (x, y) in enumerate(pts):
            rr = 13 + (i % 3) * 6
            body += (f"<circle cx='{x}' cy='{y}' r='{rr}' fill='{accent}' fill-opacity='.72'/>"
                     f"<circle cx='{x}' cy='{y}' r='{rr * 2.4:.0f}' fill='url(#g0)'/>")
    else:  # wave
        pts = " ".join("%d,%d" % (60 + i * 88, 230 + ((rnd[i % 16] % 200) - 100)) for i in range(14))
        body = (f"<polyline points='{pts}' fill='none' stroke='{accent}' stroke-opacity='.8' "
                f"stroke-width='4'/>"
                f"<polyline points='{pts}' transform='translate(0,86)' fill='none' "
                f"stroke='#F5B041' stroke-opacity='.42' stroke-width='2.5'/>"
                f"<polyline points='{pts}' transform='translate(0,-86)' fill='none' "
                f"stroke='#7C4DFF' stroke-opacity='.30'/>")
    return f"""<svg viewBox="0 0 1200 520" preserveAspectRatio="xMidYMid slice"
  style="width:100%;height:100%;display:block" role="img" aria-label="{kind} 主视觉">
  <defs>{glow}
    <pattern id="scan" width="4" height="4" patternUnits="userSpaceOnUse">
      <rect width="4" height="1" fill="#ffffff" fill-opacity=".022"/></pattern>
    <radialGradient id="vig" cx="50%" cy="46%" r="72%">
      <stop offset="60%" stop-color="#000" stop-opacity="0"/>
      <stop offset="100%" stop-color="#000" stop-opacity=".55"/></radialGradient>
  </defs>
  <rect width="1200" height="520" fill="#070A11"/>
  <rect width="1200" height="520" fill="url(#g0)"/>
  <rect width="1200" height="520" fill="url(#g1)"/>
  {floor}{body}
  <rect width="1200" height="520" fill="url(#scan)"/>
  <rect width="1200" height="520" fill="url(#vig)"/>
  <text x="34" y="46" fill="{accent}" fill-opacity=".78" font-size="16"
        font-family="ui-monospace,monospace" letter-spacing="2.6">{sub}</text>
  <rect x="0" y="512" width="1200" height="8" fill="{accent}" fill-opacity=".38"/>
</svg>"""


def hero_band(title: str, subtitle: str, chip: str = "工作台", chip_accent: str = "赛博青",
              kind: str = "", seed: str = "", sub: str = "GBT SYSTEM MAP",
              ctas: list | None = None, height: str = "300px") -> str:
    """一条 hero 带（参考图的版式：主视觉 + 类目签 + 大字标题 + 摘要 + CTA）。"""
    accent = ACCENTS.get(chip_accent, "#00E5FF")
    k = pick_archetype(seed or title, kind)
    buttons = "".join(
        f"<a class='hbtn{' solid' if i == 0 else ''}' href='{c.get('href', '#')}'>{c['label']}</a>"
        for i, c in enumerate(ctas or []))
    return f"""<section class="hero">
  <div class="hmedia" style="height:{height}">{hero_svg(k, seed or title, accent, sub)}</div>
  <div class="hbody">
    <span class="hchip" style="color:{accent};border-color:{accent}44">{chip}</span>
    <h1 class="htitle">{title}</h1>
    <p class="hsub">{subtitle}</p>
    <div class="hctas">{buttons}</div>
  </div>
</section>"""


HERO_CSS = """
.hero{display:grid;grid-template-columns:minmax(0,1.15fr) minmax(0,1fr);gap:22px;
  align-items:center;margin-bottom:22px}
.hmedia{border-radius:16px;overflow:hidden;border:1px solid rgba(0,229,255,.12);
  box-shadow:0 0 0 1px rgba(0,229,255,.05), 0 18px 60px -28px rgba(0,229,255,.35),
             0 30px 80px -40px rgba(4,10,28,.95)}
.hbody{display:flex;flex-direction:column;gap:10px}
.hchip{align-self:flex-start;border:1px solid;border-radius:999px;padding:4px 11px;
  font-size:12px;letter-spacing:.06em;background:rgba(255,255,255,.02)}
.htitle{font-size:clamp(26px,2.6vw,42px);line-height:1.12;font-weight:800;margin:0;
  letter-spacing:.01em;background:linear-gradient(92deg,#E9E9F2 8%,#00E5FF 46%,#F5B041 92%);
  -webkit-background-clip:text;background-clip:text;color:transparent}
.hsub{color:var(--dim);font-size:14px;line-height:1.6;margin:0;max-width:60ch}
.hctas{display:flex;gap:10px;flex-wrap:wrap;margin-top:4px}
.hbtn{border:1px solid rgba(0,229,255,.28);border-radius:999px;padding:8px 16px;
  font-size:13px;color:var(--cyan);background:rgba(0,229,255,.04)}
.hbtn.solid{background:#E9E9F2;color:#0B0B14;border-color:#E9E9F2;font-weight:600}
@media (max-width:900px){.hero{grid-template-columns:1fr}}
/* 卡片（卡库用，照参考图的版式） */
.cards{display:grid;grid-template-columns:repeat(auto-fill,minmax(320px,1fr));gap:20px}
.pcard{border:1px solid rgba(0,229,255,.10);border-radius:16px;overflow:hidden;
  background:linear-gradient(180deg,#12121E,#0E0E18);display:flex;flex-direction:column}
.pcard .pmedia{height:180px;overflow:hidden;border-bottom:1px solid rgba(0,229,255,.08)}
.pcard .pbody{padding:14px 16px 16px;display:flex;flex-direction:column;gap:8px;flex:1}
.pcat{font-size:11px;letter-spacing:.06em}
.ptitle{font-size:17px;font-weight:700;line-height:1.28;margin:0}
.psum{color:var(--dim);font-size:12.5px;line-height:1.55;margin:0;
  display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden}
.pgo{margin-top:auto;color:var(--cyan);font-size:12.5px;padding-top:6px}
"""


def plan_batch(pages: list | None = None, preset: str = "720p/12步") -> dict:
    """ComfyUI 升级路径：出**批量生图计划**（不执行；执行要 filesystem_write 授权）。
    为什么要有它：程序化主视觉是"今天就能有"的版本；真 3D 渲染图要 CPU 慢慢跑 —— 想升级就有这张单。"""
    pages = pages or []
    jobs = [{"page": p, "prompt": f"isometric cyber instrument panel, {pick_archetype(p)} motif, "
                                  f"deep space background, teal glow, no text, product hero",
             "preset": preset, "model": "本机 ComfyUI（checkpoints 2 个）"} for p in pages]
    return {"ok": True, "op": "plan_batch", "jobs": jobs, "count": len(jobs),
            "at": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "gate": "真跑要 filesystem_write（落图）+ ComfyUI 在跑（CPU ⇒ 每张数分钟）",
            "honest": "本件现在**没跑过**批量生图（没授权）；这是计划，不是已完成"}
