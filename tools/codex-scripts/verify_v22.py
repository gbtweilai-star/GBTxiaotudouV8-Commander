# -*- coding: utf-8 -*-
"""V22 交付校验 —— **现役两件**的契约 / 红线 / 对比度 / 结构门。只读，不改文件。

为什么要有它（2026-09-22 现读实锤）：
  仓库里躺着 `verify_v3.py` … `verify_v21.py` 一整排"每代一验"的脚本，**但现役是 V22，而 V22 没有验脚本**；
  更糟的是那排脚本**全部按死文件名**（`V21 GBT小土豆V8-可交互原型.html`）—— 文件一改代名，
  `verify_v21.py` 一跑就 `FileNotFoundError` **崩在第二行**。⇒ 现役交付件**长期没有任何内容门**
  （只有路由 200 / 语法能过这类浅检查）。
  本件把"代际无关"的那部分判据（红线 / 对比度 / 结构 / 署名 / 内嵌资源完整性）接过来，做成现役门。

口径说明（避免两种假）：
  · **emoji 分两档**：出现在**标签/属性/图标位** = 违规（fail）；
    只出现在**正文文案**里 = 允许但**逐条列出**（info，不判红）—— 本项目文档里 🔴/✅ 本来就是文本标记，
    一律判红会造出"假红"，一律放过又会造出"假绿"，所以**分开报**。
  · 对比度配对**现读令牌**算：文件里有哪对就算哪对，并把"实际算了哪些对"打印出来 ——
    不许让读者以为验过的比实际多。
  · 版本自述：两件**页内自称 V21**（`title` 里就是 V21）。这不是笔误而是**已知事实**：
    "V22" 是**文件名上的称呼**，内容是 V21 底座上手工演进（没有 `build_v22`）。
    本门不把它判红，但要求 `plugins/gbt-master/README.md` §4.10 **写明这件事**（有出处，才算交代过）。

用法：py -3.14 tools/codex-scripts/verify_v22.py
退出码：0 = 全过；1 = 有失败项；2 = 代际不符（盘上现役不是 V22 两件，本门不适用）。
"""
from __future__ import annotations

import base64
import json
import re
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = next(p for p in Path(__file__).resolve().parents if (p / "gbt_allinone").is_dir())
PROTO = ROOT / "V22 GBT小土豆V8-可交互原型.html"
CANVAS = ROOT / "V22 GBT小土豆V8-无限画布.html"
SIG = "开发者：自由的风"
README = ROOT / "plugins" / "gbt-master" / "README.md"

R: list[tuple[bool, str, str]] = []
INFO: list[str] = []


def chk(name: str, ok: bool, detail: str = "") -> None:
    R.append((bool(ok), name, detail))


# ── 0. 代际守卫：盘上现役必须是 V22 两件 ────────────────────────────────────
actives = sorted(x.name for x in ROOT.glob("V*.html"))
if not (PROTO.exists() and CANVAS.exists()):
    print("🔴 代际不符：盘上现役 V*.html = %s" % ("、".join(actives) or "（没有）"))
    print("   本门验的是 V22 两件；请用与现役同代的那支验脚本（没有就先照本件写一支）。")
    raise SystemExit(2)

p = PROTO.read_text(encoding="utf-8")
c = CANVAS.read_text(encoding="utf-8")


# ── 1b. 嵌数据必须**真的能解析**（2026-09-25 加，带牙）─────────────────────
#   由来（一手）：我改面板快照时拿正则抓"多行对象"的值，只抓到 ` {`，
#   替换后把 `"audit_by_event"` 写成了**孤儿键值** ⇒ 整块嵌数据坏掉。
#   而**这道门当时一声没吭**：
#     · V20/V21 两支里那条「原型无 undefined 字面量」末尾写着 **`or True`** ⇒ 永不判红；
#     · V22 这支**根本没有**这一条。
#   ⇒ 这里补两条**真**判据：① 嵌数据块能被 `json` 解析；② 全块没有裸 `undefined`。
def _blob(text: str, gen: str = ""):
    """取嵌数据块。`gen` 空则**自动认出**那一代的变量名（原型是 `const V21 = `，
    画布可能是别的代/别的名 —— 写死一个名字就会像第一版那样把画布判成"找不到"）。"""
    if gen:
        i = text.find("const %s = " % gen)
    else:
        m = re.search(r"const (V\d+) = ", text)
        i = m.start() if m else -1
    if i < 0:
        return None, "找不到 `const V<n> = `"
    j = text.find("{", i)
    try:
        _, end = json.JSONDecoder().raw_decode(text, j)
        return text[j:end], "OK"
    except ValueError as e:
        return None, str(e)[:120]


_with_blob = 0
for _label, _txt in (("原型", p), ("画布", c)):
    _b, _why = _blob(_txt)
    if _b is None and _why.startswith("找不到"):
        # 现读事实：**画布没有嵌数据块**（它最大的对象字面量只有 UI_STRINGS / center / ico 那种小件）
        # ⇒ 本判据对它**不适用**。写成 INFO 而不是"跳过"：**不适用 ≠ 通过**（本仓口径）。
        INFO.append("%s 没有 `const V<n> = {` 嵌数据块 ⇒ 「嵌数据合法」对它不适用" % _label)
        continue
    _with_blob += 1
    chk("%s 嵌数据是合法 JSON" % _label, _b is not None, _why)
    if _b is not None:
        _bare = re.findall(r'(?<![\w"])undefined(?![\w"])', _b)
        chk("%s 嵌数据无裸 undefined" % _label, not _bare, "命中 %d 处" % len(_bare))
# 防"两边都不适用"变成静默空转：至少得有一件真被查过
chk("至少一件交付物有嵌数据块且被查过", _with_blob >= 1, "实际查到 %d 件" % _with_blob)


# ── 1. 交付契约 ────────────────────────────────────────────────────────────
chk("根目录只有现役 V22 两件", all(x.startswith("V22 ") for x in actives), " · ".join(actives))
chk("两文件都在且够大", PROTO.stat().st_size > 300_000 and CANVAS.stat().st_size > 150_000,
    "原型 %.1f KB · 画布 %.1f KB" % (PROTO.stat().st_size / 1024, CANVAS.stat().st_size / 1024))
chk("原型带署名", SIG in p and "不可删除" in p, "")
chk("画布带署名", SIG in c and "不可删除" in c, "")

gens = [n for n in range(1, 22)
        if any(f.name.startswith("V%d " % n) for f in (ROOT / "archive").glob("*.html"))]
arc = list((ROOT / "archive").glob("*.html"))
chk("归档覆盖 V1~V21 每一代", gens == list(range(1, 22)),
    "缺代：%s" % ([n for n in range(1, 22) if n not in gens] or "无"))
chk("归档件数 = 已归档代 × 2", len(arc) == len(gens) * 2, "%d 件（%d 代）" % (len(arc), len(gens)))
chk("归档无重名", len({f.name for f in arc}) == len(arc), "")

# ── 2. 版本自述的"交代过" ─────────────────────────────────────────────────
t_proto = (re.search(r"<title>(.*?)</title>", p) or [None, ""])[1]
t_canvas = (re.search(r"<title>(.*?)</title>", c) or [None, ""])[1]
INFO.append("页内自称：原型「%s」· 画布「%s」（文件名叫 V22）" % (t_proto, t_canvas))
chk("两件都有 <title> 且带版本号", bool(re.search(r"V\d+", t_proto)) and bool(re.search(r"V\d+", t_canvas)), "")
has_doc = README.exists() and "V22" in README.read_text(encoding="utf-8") and "V21" in README.read_text(encoding="utf-8")
chk("README 写明了 V21/V22 的关系（有出处）", has_doc, "plugins/gbt-master/README.md §4.10")

# ── 3. Craft 红线 ─────────────────────────────────────────────────────────
AI_INDIGO = ["#6366f1", "#4f46e5", "#4338ca", "#3730a3", "#8b5cf6", "#7c3aed", "#a855f7"]
assert len(AI_INDIGO) == 7, "规则书七宗罪#1 恰好 7 值，清单被改短了"
hit = sorted({h for h in AI_INDIGO if h in p.lower() or h in c.lower()})
chk("无 AI 靛蓝（七值逐查，两件都扫）", not hit, "命中 " + ", ".join(hit) if hit else "")
PLACEHOLDER = re.compile(r"lorem ipsum|此处填写|待补充|占位符|placeholder text|\bTBD\b", re.I)
for tag, t in (("原型", p), ("画布", c)):
    ph = PLACEHOLDER.findall(t)
    chk(tag + " 无占位文案", not ph, "命中 %d" % len(ph))

# emoji 分档：**图标位**判红，**正文位**只列。
# 第一版口径太粗（"标签后 12 字内出现 emoji"）⇒ 把 `→`/`←`/`↔`/`⇒`/`①` 这些
#    **正文标点与序号**全算成图标，原型命中 1、画布命中 6 —— **假红**（第 10 次"门自己错"）。
# 正确口径两条：
#   ① 只认**图形类 emoji**（pictographic：U+1F000–1FAFF / U+2600–27BF / U+2B00–2BFF / U+FE0F），
#      **不把箭头、序号、几何符号算进去**（它们在正文里就是标点）；
# ② 只有**元素全部文本就是 emoji**（如 `<span></span>`）或**属性值里带 emoji**
#      （alt/title/aria-label/placeholder/content）才算"当图标用"。
PICTO = ("\U0001F000-\U0001FAFF\u2600-\u27BF\u2B00-\u2BFF\uFE0F")
STRIP_TAGS = re.compile(r"<[^>]+>")


def icon_emoji(t: str) -> list[str]:
    hits = []
    # ① 元素文本整体就是 emoji（去掉空白后 1–3 个 emoji、无其他字符）
    for m in re.finditer(r">([^<>]{1,8})<", t):
        txt = m.group(1).strip()
        if not txt:
            continue
        if re.fullmatch("[%s]{1,3}" % PICTO, txt):
            hits.append(txt)
    # ② 属性值里带 emoji（图标位/无障碍标签）
    for m in re.finditer(r'(?:alt|title|aria-label|placeholder|content)\s*=\s*"([^"]{0,40})"', t):
        if re.search("[%s]" % PICTO, m.group(1)):
            hits.append(m.group(1)[:24])
    return hits


for tag, t in (("原型", p), ("画布", c)):
    icon_hits = icon_emoji(t)
    emo = re.findall("[%s]" % PICTO, t)
    chk(tag + " 无 emoji 作图标/UI 元素", not icon_hits,
        "命中 %d：%s" % (len(icon_hits), " / ".join(icon_hits[:4])) if icon_hits else "")
    if emo:
        kinds = {}
        for e in emo:
            kinds[e] = kinds.get(e, 0) + 1
        INFO.append("%s 正文里的图形 emoji 标记：%s（共 %d 处，属**文本标记**不判红；"
                    "要判红就得连文档里的 🔴/✅ 一起改，先如实列出）"
                    % (tag, " ".join("%s×%d" % kv for kv in sorted(kinds.items())), len(emo)))

# ── 4. 对比度（现读令牌；只算命中的对） ─────────────────────────────────────


def lum(hexc: str) -> float:
    hexc = hexc.lstrip("#")
    r, g, b = (int(hexc[i:i + 2], 16) / 255 for i in (0, 2, 4))

    def f(v):
        return v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4
    return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b)


def ratio(a: str, b: str) -> float:
    la, lb = lum(a), lum(b)
    return (max(la, lb) + 0.05) / (min(la, lb) + 0.05)


def tok(t: str, name: str) -> str | None:
    m = re.search(re.escape(name) + r"\s*:\s*(#[0-9a-fA-F]{6})\s*;", t)
    return m.group(1) if m else None


def over(hexc: str, layer: str, a: float) -> str:
    cc = [int(hexc[i:i + 2], 16) for i in (1, 3, 5)]
    ll = [int(layer[i:i + 2], 16) for i in (1, 3, 5)]
    return "#%02x%02x%02x" % tuple(round(cc[i] * (1 - a) + ll[i] * a) for i in range(3))


PAIRS = [
    ("画布 主文本 / 底", "canvas", "--text", "#dff2fb", "--bg", "#04070f"),
    ("画布 主文本 / 次底", "canvas", "--text", "#dff2fb", "--bg-subtle", "#08111f"),
    ("画布 强调 / 底", "canvas", "--accent", "#2ad4f0", "--bg", "#04070f"),
    ("原型 主文本 / 面板", "proto", "--text", "#dff2fb", "--panel", "#08111f"),
    ("原型 主文本 / 面板2", "proto", "--text", "#dff2fb", "--panel-2", "#0c1a2e"),
    ("原型 强调 / 面板", "proto", "--accent", "#2ad4f0", "--panel", "#08111f"),
]
checked = []
worst = None
for label, who, fg_tok, fg_fb, bg_tok, bg_fb in PAIRS:
    t = c if who == "canvas" else p
    fg = tok(t, fg_tok) or fg_fb
    bg = tok(t, bg_tok) or bg_fb
    rr = ratio(fg, bg)
    checked.append("%s(%s/%s %.2f)" % (label, fg, bg, rr))
    if worst is None or rr < worst[0]:
        worst = (rr, label)
    chk("对比度 " + label, rr >= 4.5, "%.2f:1（%s 上 %s）" % (rr, bg, fg))
# 颗粒层（body::after 5% 灰）叠加后最坏
GRAIN, GA = "#808080", 0.05 * 0.5
gw = None
for label, who, fg_tok, fg_fb, bg_tok, bg_fb in PAIRS:
    t = c if who == "canvas" else p
    fg = over(tok(t, fg_tok) or fg_fb, GRAIN, GA)
    bg = over(tok(t, bg_tok) or bg_fb, GRAIN, GA)
    rr = ratio(fg, bg)
    if gw is None or rr < gw[0]:
        gw = (rr, label)
    chk("叠加颗粒后 " + label, rr >= 4.5, "%.2f:1" % rr)
chk("颗粒层位移 < 1.5 个对比度点", worst[0] - gw[0] < 1.5, "%.2f → %.2f（%s）" % (worst[0], gw[0], gw[1]))
INFO.append("对比度实际算过的对：%s" % " · ".join(checked))

# ── 5. 结构 ───────────────────────────────────────────────────────────────
i = p.index("var NAV = [")
j = p.index("];", i)
nav = re.findall(r"\['[^']+', '[a-z0-9]+", p[i:j])
disp = re.findall(r"if \(st\.nav === '[a-z0-9]+'\) return panel", p)
chk("原型 NAV 与分发条数一致", len(nav) == len(disp) and len(nav) > 0, "NAV %d · 分发 %d" % (len(nav), len(disp)))
chk("原型 导航无重键", len({x.split("'")[3] for x in nav}) == len(nav), "%d 键" % len(nav))
pages = re.findall(r"\['[^']+', p(\d+)\(\)\],", c)
nums = sorted(int(x) for x in pages)
chk("画布 页号连续（p1..pN）", nums == list(range(1, len(nums) + 1)) and len(nums) > 0,
    "%d 页 · p%s..p%s" % (len(nums), nums[0] if nums else "?", nums[-1] if nums else "?"))
for tag, t in (("原型", p), ("画布", c)):
    chk(tag + " 含氛围层 cine", 'id="cine"' in t, "")
    chk(tag + " 含打磨层 refine", 'id="refine"' in t, "")
    chk(tag + " 等宽数字已启用", "tabular-nums" in t, "")
    chk(tag + " 中文标点换行已设", "line-break:strict" in t, "")
    chk(tag + " 禁止伪加粗", "font-synthesis:none" in t, "")
    chk(tag + " 选中态已定义", "::selection" in t, "")
    gz = re.search(r"body::after\{[^}]*\}", t)
    chk(tag + " 颗粒是固定伪元素且不挡点击",
        bool(gz) and "position:fixed" in gz.group(0) and "pointer-events:none" in gz.group(0), "")

# ── 6. 内嵌资源完整性 ─────────────────────────────────────────────────────


def imgs(t: str):
    return re.findall(r"data:image/(webp|png);base64,([A-Za-z0-9+/=]+)", t)


for tag, t in (("原型", p), ("画布", c)):
    got = imgs(t)
    webp = [base64.b64decode(b) for m, b in got if m == "webp"]
    png = [base64.b64decode(b) for m, b in got if m == "png"]
    chk(tag + " 内嵌 Logo 是合法 WebP",
        bool(webp) and all(w[:4] == b"RIFF" and w[8:12] == b"WEBP" for w in webp), "%d 份" % len(webp))
    chk(tag + " 内嵌 favicon 是合法 PNG",
        bool(png) and all(g[:4] == b"\x89PNG" for g in png), "%d 份" % len(png))
    chk(tag + " favicon 不重复内嵌", len(png) <= 1, "%d 份" % len(png))

# ── 输出 ──────────────────────────────────────────────────────────────────
ok = sum(1 for r in R if r[0])
print("=" * 84)
print("V22 交付校验 · %d 项（现役 %s）" % (len(R), " / ".join(actives)))
print("=" * 84)
for good, name, detail in R:
    print("  %s %-36s %s" % ("✓" if good else "✗", name, detail))
print("-" * 84)
for line in INFO:
    print("  · " + line)
print("-" * 84)
print("通过 %d · 失败 %d" % (ok, len(R) - ok))
print("最低对比度：%.2f:1（%s）· 叠加颗粒后最低：%.2f:1（%s）" % (worst[0], worst[1], gw[0], gw[1]))
print("结构：原型 NAV %d 条 · 画布 %d 页" % (len(nav), len(nums)))
raise SystemExit(0 if ok == len(R) else 1)
