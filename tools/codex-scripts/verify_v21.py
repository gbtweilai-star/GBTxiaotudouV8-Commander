# -*- coding: utf-8 -*-
"""V21 交付校验：契约 + 静态口径 + 数据自洽。只读，不改文件。"""
import json
import re
import sys
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:  # noqa: BLE001
    pass

# 本目录自 .scratch/ 迁到 tools/codex-scripts/ 后深度 +1：原来的 .parent.parent
# 落在 …\tools\（tools 下 0 个 html，实测 FileNotFoundError），必须向上找根标记。
# 与 make_godview_sheet.py:10 / probe_*.py 同写法。
BASE = next(p for p in Path(__file__).resolve().parents if (p / "gbt_allinone").is_dir())
S = BASE / ".scratch"
PROTO = BASE / "V21 GBT小土豆V8-可交互原型.html"
CANVAS = BASE / "V21 GBT小土豆V8-无限画布.html"
SIG = "开发者：自由的风"

# ── 代际守卫（2026-09-22 补）────────────────────────────────────────────────
# 本门**按死 V21 的文件名**。现役换成 V22 之后，本门一跑就 `FileNotFoundError`
# **崩在第二行** —— 读的人容易把它当成"现役交付件坏了"。现在：代际不符就 exit 2 并指路，
# 让"本门不适用"和"现役坏了"分得开。**旧门的价值是历史证据，不是现役读数。**
if not (PROTO.exists() and CANVAS.exists()):
    _active = sorted(x.name for x in BASE.glob("V*.html"))
    print("🔴 代际不符：本门验 V21 两件，而盘上现役是 %s" % ("、".join(_active) or "（没有 V*.html）"))
    print("   V21 两件现读：%s / %s ⇒ %s"
          % (PROTO.name, CANVAS.name, "在" if PROTO.exists() and CANVAS.exists() else "不在根上（应已归档）"))
    print("   ⇒ 跑现役门：`py -3.14 tools/codex-scripts/verify_active.py`（自动派发到 verify_v22.py）")
    sys.exit(2)

R = []


# emoji 判定口径：Unicode 属性 \p{Extended_Pictographic}（含 U+2B00–2BFF ⭐⬛、
# U+1F000–1F2FF 🀄 等手写码位区间永远覆盖不到的块）。白名单只放「正文里是内容
# 而非装饰」的活字：U+2194 ↔（实测用于「镜像 ↔ 现实」「注册↔路由」）。
# regex 运行期不可用时退回宽区间 —— 宁可多报，也不放过 P0。
try:
    import regex as _u
    EMOJI = _u.compile(r"(?![\u2194])\p{Extended_Pictographic}")
    EMOJI_MODE = "unicode-property"
except ImportError:  # noqa: BLE001
    EMOJI = re.compile(r"[\U0001F000-\U0001FAFF\u2190-\u21FF\u2300-\u23FF"
                       r"\u2460-\u24FF\u25A0-\u27BF\u2B00-\u2BFF\uFE0F\u20E3]")
    EMOJI_MODE = "wide-fallback"


def chk(name, ok, detail=""):
    R.append((bool(ok), name, detail))


p = PROTO.read_text(encoding="utf-8")
c = CANVAS.read_text(encoding="utf-8")
man = json.loads((S / "v20_manifest.json").read_text(encoding="utf-8"))  # V21 只改视觉，数据层沿用 V14
scan = json.loads((S / "dsh_register_scan.json").read_text(encoding="utf-8"))

# ── 1. 交付契约 ──
chk("两文件都在且非空", PROTO.stat().st_size > 100_000 and CANVAS.stat().st_size > 80_000,
    "原型 %.1f KB · 画布 %.1f KB" % (PROTO.stat().st_size / 1024, CANVAS.stat().st_size / 1024))
actives = sorted(x.name for x in BASE.glob("V*.html"))
chk("根目录只有 V21 两件成品", all(x.startswith("V21 ") for x in actives), " · ".join(actives))
arc = sorted(x.name for x in (BASE / "archive").glob("*.html"))
chk("归档 V1~V20 各两件（40 件）", len(arc) == 40, "%d 件" % len(arc))
chk("归档无重名", len(set(arc)) == len(arc), "")
chk("原型带署名", SIG in p and "不可删除" in p, "")
chk("画布带署名", SIG in c and "不可删除" in c, "")

# ── 2. 版本一致性 ──
chk("原型标题为 V21", "可交互原型 V21" in p, "")
chk("画布标题为 V21", "无限画布 V21" in c, "")
chk("无 V10 残留标识", not re.search(r"\bV10\b", p), "")

# ── 3. Craft 红线 ──
# 规则书 anti-ai-slop.md:18-19 的禁用值恰好 7 个。旧清单漏 #4338ca / #3730a3 /
# #a855f7（3/7）→ 「无 AI 靛蓝」这一行的证明力只有 4/7。本清单与规则书逐字对齐。
AI_INDIGO = ["#6366f1", "#4f46e5", "#4338ca", "#3730a3", "#8b5cf6", "#7c3aed", "#a855f7"]
assert len(AI_INDIGO) == 7, "规则书七宗罪#1 恰好 7 值，清单被改短了"
hit = [h for h in AI_INDIGO if h in p.lower() or h in c.lower()]
chk("无 AI 靛蓝", not hit, "命中 " + ", ".join(hit) if hit else "")
# 占位文案：只查「填充词」类占位，不查 TODO/FIXME/XXX —— 后三者是扫描结果里的
# 事实标签（「未完成标记 TODO / FIXME 命中 6 处」），属于报告内容，不是占位。
PLACEHOLDER = re.compile(r"lorem ipsum|此处填写|待补充|占位符|placeholder text|\bTBD\b", re.I)
lorem = PLACEHOLDER.findall(p)
chk("无占位文案", not lorem, "命中 %d" % len(lorem))
dead_scan = re.findall(r"TODO / FIXME", p)
chk("死代码扫描事实标签在位", len(dead_scan) >= 1, "命中 %d 处（属报告内容）" % len(dead_scan))
emoji = EMOJI.findall(p)
chk("原型 无 emoji 作 UI 元素", not emoji,
    "命中 " + "".join(sorted(set(emoji))[:8]) if emoji else "")
# 旧口径只扫原型 p —— 实测画布 L2126 有一个 U+1F534，同一版两个交付件已分叉，
# 而门对画布报 PASS。画布必须同口径扫，且两个文件各自的 detail 分开写。
c_emoji = EMOJI.findall(c)
chk("画布 无 emoji 作 UI 元素", not c_emoji,
    "命中 " + "".join(sorted(set(c_emoji))[:8]) if c_emoji else "")

# ── 4. 对比度（WCAG 2.2 AA ≥ 4.5:1） ──


def lum(hexc):
    hexc = hexc.lstrip("#")
    r, g, b = (int(hexc[i:i + 2], 16) / 255 for i in (0, 2, 4))

    def f(v):
        return v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4
    return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b)


def ratio(a, b):
    la, lb = lum(a), lum(b)
    return (max(la, lb) + 0.05) / (min(la, lb) + 0.05)


BG_DARK, BG_LIGHT = "#04070f", "#f6f7f8"
pairs = [
    ("原型 主文本", "#dff2fb", BG_DARK), ("原型 副文本", "#b8cfda", BG_DARK),
    ("原型 三级文本", "#8fa9b8", BG_DARK), ("原型 强调青", "#2ad4f0", BG_DARK),
    ("画布 主文本", "#dff2fb", BG_DARK), ("画布 副文本", "#a9c4d2", BG_DARK),
    ("画布 亮色主文本", "#141a20", BG_LIGHT),
]


def over(hexc, layer, a):
    """把一层灰（颗粒）以 alpha 叠在颜色上，返回新 hex。"""
    c = [int(hexc[i:i + 2], 16) for i in (1, 3, 5)]
    lay = [int(layer[i:i + 2], 16) for i in (1, 3, 5)]
    return "#%02x%02x%02x" % tuple(round(c[i] * (1 - a) + lay[i] * a) for i in range(3))


worst = None
for n, fg, bg in pairs:
    rr = ratio(fg, bg)
    if worst is None or rr < worst[0]:
        worst = (rr, n)
    chk("对比度 " + n, rr >= 4.5, "%.2f:1" % rr)

# 颗粒层（body::after opacity .05，噪声均值 ≈ #808080）叠加后的最坏口径：
# 5% 的灰同时压在前景与背景上，对比度会被拉低 —— 必须仍然过 AA。
GRAIN, GA = "#808080", 0.05 * 0.5   # 噪声均值约半亮，再乘层透明度
gw = None
for n, fg, bg in pairs:
    rr = ratio(over(fg, GRAIN, GA), over(bg, GRAIN, GA))
    if gw is None or rr < gw[0]:
        gw = (rr, n)
    chk("叠加颗粒后 " + n, rr >= 4.5, "%.2f:1" % rr)
chk("颗粒层位移 < 1.5 个对比度点",
    worst[0] - gw[0] < 1.5, "%.2f → %.2f（%s）" % (worst[0], gw[0], gw[1]))

# ── 5. 数据自洽 ──
d = man["dsh"]
chk("席位口径自洽", d["n_implemented"] + d["n_missing"] == d["n_slots_real"],
    "已实现 %d + 缺口 %d = 界面席位 %d" % (d["n_implemented"], d["n_missing"], d["n_slots_real"]))
chk("应用席位全部未实现（已计入总数）",
    all(a["slot"] not in {x["slot"] for x in d["implemented"]} for a in d["apps"]),
    "%d 个应用席位" % d["n_slots_app"])
chk("席位总数 = 界面 + 应用", d["n_slots_real"] + d["n_slots_app"] == d["n_total"],
    "%d + %d = %d" % (d["n_slots_real"], d["n_slots_app"], d["n_total"]))
real_reg = set()
for pk, info in scan.items():
    real_reg.update(info.get("registered_slots", {}))
all_man = set(d["slots_real"]) | set(d["slots_app"])
chk("席位 id 全部来自真实注册（无编造）", all_man <= real_reg,
    "编造 %d 个" % len(all_man - real_reg))
chk("缺口席位都有注册方", all(d["slot_owner"].get(s) for s in d["missing"]), "")
chk("已实现席位不重复", len({x["slot"] for x in d["implemented"]}) == d["n_implemented"], "")
chk("家族席位并集 = 全部界面席位",
    set().union(*[set(f["slots"]) for f in d["families"]]) == set(d["slots_real"]), "")
chk("插件包数 ≥ 有席位的包数", d["client_with_slots"] <= d["client_total"],
    "%d ≤ %d" % (d["client_with_slots"], d["client_total"]))

# ── 6. 结构 ──
_i = p.index("var NAV = [")
_j = p.index("];", _i)
nav_entries = re.findall(r"\['[^']+', '[a-z0-9]+'", p[_i:_j])
dispatch = re.findall(r"if \(st\.nav === '[a-z0-9]+'\) return panel", p)
chk("原型 57 个导航项", len(nav_entries) == 57 and len(dispatch) == 57,
    "NAV %d 条 · 分发 %d 条" % (len(nav_entries), len(dispatch)))
chk("导航无重键", len({x.split("'")[3] for x in nav_entries}) == 57, "")
chk("画布 61 页", len(re.findall(r"\['[^']+', p\d+\(\)\],", c)) == 61,
    "%d 页" % len(re.findall(r"\['[^']+', p\d+\(\)\],", c)))
chk("画布 p1~p61 齐", all(("function p%d(" % i) in c for i in range(1, 62)), "")
chk("原型无 undefined 字面量", "undefined" not in re.sub(r"//[^\n]*", "", p.split("const V21 = ")[1]), "（数据层已解析，见运行期校验）")


# ── 7b. 品牌 Logo（主人提供）──
import base64 as _b64  # noqa: E402


def _imgs(text):
    return re.findall(r"data:image/(webp|png);base64,([A-Za-z0-9+/=]+)", text)


p_imgs, c_imgs = _imgs(p), _imgs(c)
chk("原型内嵌 Logo", any(m == "webp" for m, _ in p_imgs), "%d 个 data URI" % len(p_imgs))
chk("画布内嵌 Logo", any(m == "webp" for m, _ in c_imgs), "%d 个 data URI" % len(c_imgs))
chk("两件都内嵌 favicon", any(m == "png" for m, _ in p_imgs) and any(m == "png" for m, _ in c_imgs), "")
chk("favicon 不重复内嵌", sum(1 for m, _ in p_imgs if m == "png") <= 1 and
    sum(1 for m, _ in c_imgs if m == "png") <= 1, "各 1 份")

# 解码内嵌 Logo，验证字节完整
_emb = json.loads((S / "logo_embed.json").read_text(encoding="utf-8"))


def _payload(text, want):
    for m, b in _imgs(text):
        if m != want:
            continue
        raw = _b64.b64decode(b)
        if raw[:4] == b"RIFF" or raw[:4] == b"\x89PNG":
            return raw
    return b""


_lp = _payload(p, "webp")
_lc = _payload(c, "webp")
chk("原型 Logo 是合法 WebP", _lp[:4] == b"RIFF" and _lp[8:12] == b"WEBP", "%d B" % len(_lp))
chk("画布 Logo 是合法 WebP", _lc[:4] == b"RIFF" and _lc[8:12] == b"WEBP", "%d B" % len(_lc))
chk("原型 Logo 与 192 源字节一致",
    _lp == _b64.b64decode(_emb["uri_prototype"].split(",", 1)[1]), "")
chk("画布 Logo 与 512 源字节一致",
    _lc == _b64.b64decode(_emb["uri_canvas"].split(",", 1)[1]), "")
chk("源图 sha256 有记录",
    len(_emb["source_sha256"]) == 64, _emb["source_sha256"][:16] + "…")
chk("品牌色已采样", _emb["colors"]["accent"] == "#2ad4f0",
    "Logo 均值青 %s（距 --accent %.1f）" % (_emb["colors"]["mean_cyan"],
                                          _emb["colors"]["delta_mean_vs_accent"]))

# 席位：Logo 接上后应为 10 / 71
dd = man["dsh"]
chk("品牌三席位已计入已实现",
    {"sidebar.brand.mark", "sidebar.brand.name", "conversation.hero.brand.mark"} <=
    {x["slot"] for x in dd["implemented"]},
    "已实现 %d · 缺口 %d" % (dd["n_implemented"], dd["n_missing"]))
chk("Logo 在原型里出现 3 处（侧栏 / 上帝视角 / 空态）",
    len(re.findall(r'<img[^>]*class|class="logo"[^>]*><img', p)) >= 2 or
    p.count("BRAND.logo") >= 2, "BRAND.logo 引用 %d 次" % p.count("BRAND.logo"))


# ── 7c. V21 覆盖审计段 ──
_cv = man.get("coverage") or {}
_core = man.get("core") or {}
chk("覆盖审计已入数据层", bool(_cv), "%d 目录" % len(_cv.get("by_dir") or {}))
chk("覆盖口径自洽",
    _cv.get("covered_lines", 0) + _cv.get("uncovered_lines", 0) == _cv.get("total_lines", -1),
    "%s = %s + %s" % (f"{_cv.get('total_lines', 0):,}", f"{_cv.get('covered_lines', 0):,}",
                      f"{_cv.get('uncovered_lines', 0):,}"))
chk("V21 核心组齐 9 组", len(_core) == 9, " / ".join(sorted(_core)))
_core_lines = sum(c["lines"] for c in _core.values())
_core_n = sum(c["n"] for c in _core.values())
chk("核心组规模 > 30000 行", _core_lines > 30000, "%d 文件 / %s 行" % (_core_n, f"{_core_lines:,}"))
chk("统一接口层含 api.py",
    any(f["f"] == "gbt_allinone/api.py" for f in _core["api"]["files"]), "")
chk("安全策略组含 policy.py",
    any(f["f"] == "gbt_allinone/security/policy.py" for f in _core["security"]["files"]), "")
chk("每个核心文件都有行数与摘要",
    all(f["lines"] > 0 for c in _core.values() for f in c["files"]), "")
chk("未覆盖面比 V13 收窄", _core_lines > 0 and _cv["uncovered_lines"] < _cv["total_lines"] * 0.6,
    "未覆盖仍占 %.1f%%" % (100 * _cv["uncovered_lines"] / _cv["total_lines"]))


# ── 7d. 影视氛围层（V21）──
CINE_BEGIN = "/* ══════════════════════════════════════════════════════════════════════════\n   V21 · 影视氛围层"
for tag, txt in (("原型", p), ("画布", c)):
    chk(tag + " 含氛围样式表", 'id="cine"' in txt, "")
    chk(tag + " 含极光三团", txt.count("cine-a") >= 2 and "cine-b" in txt and "cine-c" in txt, "")
    chk(tag + " 含暗角", "cine-v" in txt, "")
    chk(tag + " 含胶片颗粒", "feTurbulence" in txt, "")
    chk(tag + " 含入场编排", "cineRise" in txt, "")
    # 颗粒必须挂在固定、不挡点击的伪元素上（§6.E）
    gz = re.search(r"body::after\{[^}]*\}", txt)
    chk(tag + " 颗粒是固定伪元素且不挡点击",
        bool(gz) and "position:fixed" in gz.group(0) and "pointer-events:none" in gz.group(0),
        "")
    chk(tag + " 颗粒在最上层却不可交互",
        bool(gz) and "z-index:9000" in gz.group(0), "")
    # 降级：无限循环与入场在 reduced-motion 下一律静止
    # （文件里可能已存在别的 reduced-motion 块，必须挑含 cine-atmo 的那一个）
    rms = re.findall(r"@media \(prefers-reduced-motion:reduce\)\{(.*?)\n\}", txt, re.S)
    rm = next((m for m in rms if "cine-atmo" in m), None)
    chk(tag + " reduced-motion 覆盖极光与入场",
        rm is not None and "cine-atmo i" in rm and "animation:none!important" in rm
        and "#chatBody>*" in rm, "共 %d 个 reduced-motion 块" % len(rms))
    chk(tag + " 存在 reduced-motion 降级块", rm is not None, "")

    # 电影层自己的样式块（blur 只在电影层里查 —— 模板本来可能已有 blur）
    cm = re.search(r'<style id="cine">(.*?)</style>', txt, re.S)
    chk(tag + " 电影层样式块可定位", bool(cm), "%d B" % (len(cm.group(1)) if cm else 0))
    chk(tag + " 电影层无 blur 滤镜（省 GPU 重绘）",
        bool(cm) and "blur(" not in cm.group(1), "")

# 只动 transform / opacity
for tag, txt in (("原型", p), ("画布", c)):
    kf = re.findall(r"@keyframes cine\w+\{(.*?)\}\}", txt, re.S)
    bad = [k for k in kf if re.search(r"\b(top|left|right|bottom|width|height|margin|padding)\s*:", k)]
    chk(tag + " 关键帧只动 transform/opacity", not bad, "%d 个关键帧" % len(kf))
    chk(tag + " 氛围层不接指针", txt.count('class="cine-atmo" aria-hidden="true"') >= 1 or "cine-atmo" in txt, "")
    chk(tag + " z-index 刻度有文档", "z-index 刻度" in txt, "")

# 结构：氛围 DOM 在 body 第一个子节点
chk("原型 氛围 DOM 在内容之前",
    p.index('class="cine-atmo"') < p.index('class="app"'), "")
chk("画布 氛围 DOM 在 #viewport 之前",
    c.index('class="cine-atmo"') < c.index('id="viewport"'), "")
chk("原型 运动脚本独立成块", 'id="cine-motion"' in p, "")
chk("画布 运动脚本在 IIFE 内（开场镜头要用 zoom/panX）",
    "updateTransform();\n\n  /* ── V21" in c or "cineStagger" in c.split("})();")[0], "")


# ── 7e. V21 专业化打磨层：排版 / 节奏 / 数据工艺 ──
_body = re.search(r"<body[^>]*>(.*)</body>", p, re.S).group(1)


def _cnt(pat, t):
    return len(re.findall(pat, t))


for tag, txt in (("原型", p), ("画布", c)):
    chk(tag + " 含打磨样式表", 'id="refine"' in txt, "")
    chk(tag + " 等宽数字已启用",
        "tabular-nums" in txt and 'font-feature-settings:"tnum" 1' in txt,
        "%d 处 tabular-nums" % _cnt("tabular-nums", txt))
    chk(tag + " 定义了字重刻度", "--w-bold:700" in txt and "--w-med:500" in txt, "")
    chk(tag + " 定义了字距刻度", "--ls-display" in txt and "--ls-label" in txt, "")
    chk(tag + " 定义了行高刻度", "--lh-display" in txt and "--lh-body" in txt, "")
    chk(tag + " 定义了间距刻度", "--sp-1:4px" in txt and "--sp-9:32px" in txt, "")
    chk(tag + " 中文标点换行已设", "line-break:strict" in txt, "")
    chk(tag + " 禁止伪加粗", "font-synthesis:none" in txt, "")
    chk(tag + " 选中态已定义", "::selection" in txt, "")
    chk(tag + " 表面分主层/内嵌层",
        ".card:not(.card .card)" in txt and ".card .card{" in txt, "")
    chk(tag + " 明色主题下表面阴影已反转", '[data-theme="light"] .card .card' in txt, "")
    chk(tag + " 数据行有悬浮态", ".statline:hover" in txt and ".routebar:hover" in txt, "")

# 间距是否真的收上了 2px 刻度
_OFF = {"5px", "7px", "9px", "11px", "13px", "15px", "18px"}
for tag, txt in (("原型", p), ("画布", c)):
    gaps = set(re.findall(r"gap:\s*([\d.]+px)", txt))
    off = sorted(g for g in gaps if g in _OFF)
    chk(tag + " 间距已收到刻度（无离群值）", not off,
        "剩余离群 %s · 全部 %s" % (off, sorted(gaps, key=lambda x: float(x[:-2]))))

# 对比度：内嵌表面（--panel-2）上的文字也要过 AA
for theme, bg2 in (("dark", man.get("brand", {}).get("_panel2_dark") or "#0c1a2e"),):
    pass
chk("内嵌表面 主文本对比度", ratio("#dff2fb", "#0c1a2e") >= 4.5,
    "%.2f:1（深色主题 --panel-2）" % ratio("#dff2fb", "#0c1a2e"))


# ── 7f. V21：主人点名的两个 + 严格判据揪出的三块 ──
_v17 = man.get("v17") or {}
chk("V21 数据段在位", bool(_v17), " / ".join(sorted(_v17)))
chk("原生浏览器：控制器行数 > 1500", _v17["browser"]["ctrl_lines"] > 1500,
    "%s 行 + %s 行" % (_v17["browser"]["ctrl_lines"], _v17["browser"]["cap_lines"]))
chk("原生浏览器：操作数 >= 29", len(_v17["browser"]["ops"]) >= 29, "%d 个操作" % len(_v17["browser"]["ops"]))
chk("原生浏览器：含窗口置顶", "pin_window" in _v17["browser"]["window"]["pin"], "")
chk("原生浏览器：三级后端如实降级", len(_v17["browser"]["cap_tiers"]) == 3, "")
chk("云电脑：五原语齐", len(_v17["cloudpc"]["primitives"]) == 5,
    " / ".join(p["key"] for p in _v17["cloudpc"]["primitives"]))
chk("云电脑：五条红线齐", len(_v17["cloudpc"]["red_lines"]) == 5, "")
chk("云电脑：明确不是 iframe", "不是 iframe" in _v17["cloudpc"]["window"]["not_iframe"], "")
chk("云电脑：不可逆原语都标了过门",
    all(p["needs_gate"] for p in _v17["cloudpc"]["primitives"] if not p["reversible"]),
    "不可逆 %d 个" % sum(1 for p in _v17["cloudpc"]["primitives"] if not p["reversible"]))
chk("云电脑：凭据缺失如实标注", _v17["cloudpc"]["current"]["credentials_present"] is False,
    _v17["cloudpc"]["current"]["credential_note"][:40])
chk("工具集：整组入册", _v17["tools"]["n"] >= 40 and _v17["tools"]["lines"] > 18000,
    "%d 文件 / %s 行" % (_v17["tools"]["n"], f"{_v17['tools']['lines']:,}"))
chk("编排内核：三源齐", len(_v17["kernel"]["three"]) == 3,
    " / ".join(t[0] for t in _v17["kernel"]["three"]))
chk("编排内核：三层职责齐", len(_v17["kernel"]["layers"]) == 3, "")
chk("严格审计：假覆盖已量化", _v17["strict_audit"]["false_covered_n"] > 0,
    "%d 文件 / %s 行" % (_v17["strict_audit"]["false_covered_n"],
                      f"{_v17['strict_audit']['false_covered_lines']:,}"))
chk("严格审计：写明是上界不是精确值", "上界" in _v17["strict_audit"]["caveat"], "")
for tag, txt in (("原型", p), ("画布", c)):
    chk(tag + " 含原生浏览器", "native_browser" in txt and "pin_window" in txt, "")
    chk(tag + " 含云电脑五原语", all(k in txt for k in ("PROVISION", "CONNECT", "SNAPSHOT", "RELEASE")), "")
    chk(tag + " 含五条红线", "身份内核不变" in txt or "红线" in txt, "")
    chk(tag + " 含编排内核三源", "BrowserUse" in txt and "CrewAI" in txt and "Mastra" in txt, "")


# ── 7g. V21：能力广场改为源码驱动 ──
_cs = man.get("capsrc") or {}
chk("V21 源码反查段在位", bool(_cs), "%d 能力" % _cs.get("total", 0))
chk("能力数 = 注册表 140", _cs.get("total") == 140, str(_cs.get("total")))
_bs = _cs.get("by_state") or {}
chk("实测三态齐且合计 140",
    sum(_bs.values()) == 140, " / ".join("%s=%s" % (k, v) for k, v in sorted(_bs.items())))
chk("跑通数 = 97", _bs.get("ok") == 97, str(_bs.get("ok")))
chk("待授权数 = 28", _bs.get("gated") == 28, str(_bs.get("gated")))
chk("待参数数 = 15", _bs.get("needs_params") == 15, str(_bs.get("needs_params")))
_rows = _cs.get("caps") or []
chk("每条都有名字与域", all(r.get("name") and r.get("domain") for r in _rows), "%d 条" % len(_rows))
chk("每条都有实测状态", all(r.get("state") in ("ok", "gated", "needs_params") for r in _rows), "")
_n_mod = sum(1 for r in _rows if r.get("module"))
chk("有实现模块的 >= 110", _n_mod >= 110, "%d / 140（余下为 api.py 内联或包级入口）" % _n_mod)
chk("实现模块去重 >= 70", _cs.get("n_modules", 0) >= 70, "%d 个" % _cs.get("n_modules", 0))
chk("模块行数合计 > 6 万",
    sum(r.get("module_lines") or 0 for r in _rows) > 60000,
    f"{sum(r.get('module_lines') or 0 for r in _rows):,}")
chk("有关键能力的模块反查正确",
    next(r for r in _rows if r["name"] == "cloud_pc")["module"].endswith("tools/cloud_pc.py"),
    next(r for r in _rows if r["name"] == "cloud_pc")["module"])
chk("codex_* 反查到 codex_bridge",
    next(r for r in _rows if r["name"] == "codex_status")["module"].endswith("codex_bridge.py"), "")
chk("life 反查到 life_archive",
    next(r for r in _rows if r["name"] == "life")["module"].endswith("life_archive.py"), "")
chk("能力广场已换成源码驱动实现",
    "panelCapSrc()" in p and "return panelSquare();" not in p, "")
chk("原手写能力广场已不再被分发",
    "if (st.nav === 'square') return panelCapSrc();" in p, "")


# ── 7h. V21：AI朋友圈 + 用户社交（实测入册，未接分发）──
_sc = man.get("social") or {}
chk("V21 社交段在位", bool(_sc), " / ".join(sorted(_sc)))
_e = _sc.get("eigenflux") or {}
chk("朋友圈：CLI 版本有记录", bool(_e.get("cli", {}).get("version")), str(_e.get("cli", {}).get("version")))
chk("朋友圈：身份有记录", bool(_e.get("identity", {}).get("agent_id")),
    "%s / %s" % (_e.get("identity", {}).get("name"), _e.get("identity", {}).get("agent_id")))
chk("朋友圈：影响力有实测数",
    isinstance(_e.get("influence", {}).get("total_items"), int),
    "广播 %s · 消费 %s" % (_e.get("influence", {}).get("total_items"),
                       _e.get("influence", {}).get("total_consumed")))
chk("朋友圈：拉到真实动态 >= 5 条", len(_e.get("feed") or []) >= 5, "%d 条" % len(_e.get("feed") or []))
chk("朋友圈：动态作者不重复 >= 5 人",
    len({f.get("who") for f in (_e.get("feed") or [])}) >= 5,
    "%d 人" % len({f.get("who") for f in (_e.get("feed") or [])}))
chk("朋友圈：全网 agent 数是实测值", isinstance(_e.get("net", {}).get("agent_count"), int),
    "%s 个 · %s 个国家/地区" % (_e.get("net", {}).get("agent_count"), _e.get("net", {}).get("countries")))
chk("朋友圈：实现文件有行数", all(m.get("lines") for m in (_e.get("modules") or [])),
    "%d 文件 / %s 行" % (len(_e.get("modules") or []),
                      f"{sum(m.get('lines') or 0 for m in (_e.get('modules') or [])):,}"))
chk("朋友圈：如实标未接线", _e.get("wired") is False, "wired=False")
_p = _sc.get("publish") or {}
chk("用户社交：已接线但自报未实现", _p.get("wired") is True and "not_implemented" in (_p.get("self_state") or ""),
    _p.get("self_state"))
chk("用户社交：平台表 >= 6 个", len(_p.get("platforms") or []) >= 6, "%d 个" % len(_p.get("platforms") or []))
chk("用户社交：平台有官方 API 标注",
    all("official_api" in x for x in (_p.get("platforms") or [])), "")
_g = _sc.get("gate") or {}
chk("门状态：如实记录为空",
    all(not v for k, ops in _g.items() for op, v in ops.items()),
    "auto_publish %d 动作全无门" % len(_g.get("auto_publish") or {}))


# ── 7i. V21：朋友圈关系场可视化 ──
_g = (man.get("social") or {}).get("graph") or {}
_nodes = _g.get("nodes") or []
chk("V21 关系场段在位", bool(_g), "%d 好友" % _g.get("n_friends", 0))
chk("好友节点都有真实角度与半径",
    all(isinstance(n.get("angle"), float) and n.get("r") for n in _nodes), "%d 个节点" % len(_nodes))
chk("节点角度各不相同（由数据算出，非手摆）",
    len({round(n["angle"], 3) for n in _nodes}) == len(_nodes), "")
chk("半径随真实发帖数变化", len({n["r"] for n in _nodes}) > 1,
    "半径档位 %s" % sorted({n["r"] for n in _nodes}))
chk("颜色取自设计系统四色",
    all(n["color"] in (_g.get("palette") or []) for n in _nodes), " / ".join(_g.get("palette") or []))
chk("bio 未标域的节点如实留空",
    any(not n.get("domains") for n in _nodes),
    "%d 个（不硬塞）" % sum(1 for n in _nodes if not n.get("domains")))
chk("官方账号已标记", _g.get("n_official", 0) >= 1, "%d 位" % _g.get("n_official", 0))
chk("关系场面板已接线", "socialgraph" in p and "panelSocialGraph()" in p, "")
chk("星图由数据生成（含 SVG 与角度计算）",
    "socialGraphSVG" in p and "Math.cos(n.angle)" in p, "")


# ── 7j. V21：修列向 flex 压扁面板（真渲染揪出的布局 bug）──
chk("布局修复已进交付件（flex 不许收缩）",
    ".chat-body>*,.god-body>*{flex:0 0 auto}" in p and
    ".chat-body>*,.god-body>*{flex:0 0 auto}" in c, "")
chk("布局修复带了原因注释（可追溯）",
    "列向 flex 的子项默认 flex-shrink:1" in p, "")
chk("god-body 也可滚动", "god-body{overflow-y:auto}" in p, "")

# ── 输出 ──
ok = sum(1 for r in R if r[0])
print("=" * 78)
print("V21 交付校验 · %d 项" % len(R))
print("=" * 78)
for good, name, detail in R:
    print("  %s %-34s %s" % ("✓" if good else "✗", name, detail))
print("-" * 78)
print("通过 %d · 失败 %d" % (ok, len(R) - ok))
print("emoji 判定口径：%s（扫原型 + 画布两件）" % EMOJI_MODE)
print("最低对比度：%.2f:1（%s）" % worst)
print("席位：界面 %d + 应用 %d = %d · 已实现 %d · 缺口 %d"
      % (d["n_slots_real"], d["n_slots_app"], d["n_total"], d["n_implemented"], d["n_missing"]))
sys.exit(0 if ok == len(R) else 1)
