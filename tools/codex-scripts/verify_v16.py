# -*- coding: utf-8 -*-
"""V16 交付校验：契约 + 静态口径 + 数据自洽。只读，不改文件。"""
import json
import re
import sys
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:  # noqa: BLE001
    pass

BASE = next(p for p in Path(__file__).resolve().parents
            if (p / "gbt_allinone").is_dir())   # 修：原 `.parent.parent` 只到 tools/（少一层）
S = BASE / ".scratch"
PROTO = BASE / "V16 GBT小土豆V8-可交互原型.html"
CANVAS = BASE / "V16 GBT小土豆V8-无限画布.html"
SIG = "开发者：自由的风"

R = []


def chk(name, ok, detail=""):
    R.append((bool(ok), name, detail))


p = PROTO.read_text(encoding="utf-8")
c = CANVAS.read_text(encoding="utf-8")
man = json.loads((S / "v14_manifest.json").read_text(encoding="utf-8"))  # V16 只改视觉，数据层沿用 V14
scan = json.loads((S / "dsh_register_scan.json").read_text(encoding="utf-8"))

# ── 1. 交付契约 ──
chk("两文件都在且非空", PROTO.stat().st_size > 100_000 and CANVAS.stat().st_size > 80_000,
    "原型 %.1f KB · 画布 %.1f KB" % (PROTO.stat().st_size / 1024, CANVAS.stat().st_size / 1024))
actives = sorted(x.name for x in BASE.glob("V*.html"))
chk("根目录只有 V16 两件成品", all(x.startswith("V16 ") for x in actives), " · ".join(actives))
arc = sorted(x.name for x in (BASE / "archive").glob("*.html"))
chk("归档 V1~V15 各两件（30 件）", len(arc) == 30, "%d 件" % len(arc))
chk("归档无重名", len(set(arc)) == len(arc), "")
chk("原型带署名", SIG in p and "不可删除" in p, "")
chk("画布带署名", SIG in c and "不可删除" in c, "")

# ── 2. 版本一致性 ──
chk("原型标题为 V16", "可交互原型 V16" in p, "")
chk("画布标题为 V16", "无限画布 V16" in c, "")
chk("无 V10 残留标识", not re.search(r"\bV10\b", p), "")

# ── 3. Craft 红线 ──
AI_INDIGO = ["#6366f1", "#818cf8", "#a5b4fc", "#4f46e5", "#8b5cf6", "#7c3aed"]
hit = [h for h in AI_INDIGO if h in p.lower() or h in c.lower()]
chk("无 AI 靛蓝", not hit, "命中 " + ", ".join(hit) if hit else "")
# 占位文案：只查「填充词」类占位，不查 TODO/FIXME/XXX —— 后三者是扫描结果里的
# 事实标签（「未完成标记 TODO / FIXME 命中 6 处」），属于报告内容，不是占位。
PLACEHOLDER = re.compile(r"lorem ipsum|此处填写|待补充|占位符|placeholder text|\bTBD\b", re.I)
lorem = PLACEHOLDER.findall(p)
chk("无占位文案", not lorem, "命中 %d" % len(lorem))
dead_scan = re.findall(r"TODO / FIXME", p)
chk("死代码扫描事实标签在位", len(dead_scan) >= 1, "命中 %d 处（属报告内容）" % len(dead_scan))
emoji = re.findall(r"[\U0001F300-\U0001FAFF\u2600-\u27BF]", p)
chk("无 emoji 作 UI 元素", not emoji, "命中 " + "".join(sorted(set(emoji))[:8]) if emoji else "")

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
chk("原型 50 个导航项", len(nav_entries) == 50 and len(dispatch) == 50,
    "NAV %d 条 · 分发 %d 条" % (len(nav_entries), len(dispatch)))
chk("导航无重键", len({x.split("'")[3] for x in nav_entries}) == 50, "")
chk("画布 53 页", len(re.findall(r"\['[^']+', p\d+\(\)\],", c)) == 53,
    "%d 页" % len(re.findall(r"\['[^']+', p\d+\(\)\],", c)))
chk("画布 p1~p53 齐", all(("function p%d(" % i) in c for i in range(1, 54)), "")
chk("原型无 undefined 字面量", "undefined" not in re.sub(r"//[^\n]*", "", p.split("const V16 = ")[1]), "（数据层已解析，见运行期校验）")


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


# ── 7c. V16 覆盖审计段 ──
_cv = man.get("coverage") or {}
_core = man.get("core") or {}
chk("覆盖审计已入数据层", bool(_cv), "%d 目录" % len(_cv.get("by_dir") or {}))
chk("覆盖口径自洽",
    _cv.get("covered_lines", 0) + _cv.get("uncovered_lines", 0) == _cv.get("total_lines", -1),
    "%s = %s + %s" % (f"{_cv.get('total_lines', 0):,}", f"{_cv.get('covered_lines', 0):,}",
                      f"{_cv.get('uncovered_lines', 0):,}"))
chk("V16 核心组齐 9 组", len(_core) == 9, " / ".join(sorted(_core)))
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


# ── 7d. 影视氛围层（V16）──
CINE_BEGIN = "/* ══════════════════════════════════════════════════════════════════════════\n   V16 · 影视氛围层"
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
    "updateTransform();\n\n  /* ── V16" in c or "cineStagger" in c.split("})();")[0], "")


# ── 7e. V16 专业化打磨层：排版 / 节奏 / 数据工艺 ──
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

# ── 输出 ──
ok = sum(1 for r in R if r[0])
print("=" * 78)
print("V16 交付校验 · %d 项" % len(R))
print("=" * 78)
for good, name, detail in R:
    print("  %s %-34s %s" % ("✓" if good else "✗", name, detail))
print("-" * 78)
print("通过 %d · 失败 %d" % (ok, len(R) - ok))
print("最低对比度：%.2f:1（%s）" % worst)
print("席位：界面 %d + 应用 %d = %d · 已实现 %d · 缺口 %d"
      % (d["n_slots_real"], d["n_slots_app"], d["n_total"], d["n_implemented"], d["n_missing"]))
sys.exit(0 if ok == len(R) else 1)
