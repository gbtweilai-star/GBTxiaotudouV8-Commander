# -*- coding: utf-8 -*-
"""交付前自检：两件交付物的结构 / 语法 / 令牌 / 状态 / 反 AI-slop / 数据层。"""
import json
import re
import subprocess
import sys
from pathlib import Path

# 旧版全文没有这一句，而 V8 起的 verify_*.py 都有：GBK 控制台重定向时输出被就地
# 损坏。实证：verify_v3~v7_out.txt 是 UTF-8 但含 590~1089 个 U+FFFD（不可逆），
# verify_v8_out.txt 起为 0 —— 分水岭正是这一行。
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:  # noqa: BLE001
    pass

# 本目录自 .scratch/ 迁到 tools/codex-scripts/ 后深度 +1：原来的 .parent.parent
# 落在 …\tools\（tools 下 0 个 html）。向上找根标记。V2 已发布并归档 ⇒ 走 archive/。
BASE = next(p for p in Path(__file__).resolve().parents if (p / "gbt_allinone").is_dir())
CANVAS = BASE / "V2 GBT小土豆V8-无限画布.html"
PROTO = BASE / "V2 GBT小土豆V8-可交互原型.html"
if not PROTO.exists():
    CANVAS = BASE / "archive" / CANVAS.name
    PROTO = BASE / "archive" / PROTO.name
TMP = BASE / ".scratch"

fails, warns, oks = [], [], []


def ok(m):
    oks.append(m)
    print("  PASS  " + m)


def bad(m):
    fails.append(m)
    print("  FAIL  " + m)


def warn(m):
    warns.append(m)
    print("  WARN  " + m)


def script_of(text):
    i = text.rindex("<script>")
    j = text.rindex("</script>")
    return text[i + len("<script>"):j]


print("=" * 74)
print("交付前自检 · V2 双交付")
print("=" * 74)

print("\n[1] 文件与版本")
for p in (CANVAS, PROTO):
    if p.exists():
        ok("%s 存在 · %d B" % (p.name, len(p.read_bytes())))
    else:
        bad("%s 缺失" % p.name)
if re.search(r"V2 ", CANVAS.name) and re.search(r"V2 ", PROTO.name):
    ok("两文件版本号一致（V2）")
else:
    bad("版本号不一致")
arch = sorted((BASE / "archive").glob("V1*"))
# 原口径写死 len(arch)==2，只对「V1 刚归档」那一天成立。实测 archive/ 已有
# V1~V20 历史（glob 命中 22 件）—— 这一行在 layout 修好、脚本首次真跑起来后
# 才暴露。改为断言 V2 双件的回退快照在位，与版本数无关。
_v1 = [f.name for f in arch if f.name.startswith("V1 ")]
if len(_v1) == 2:
    ok("archive/ 含 V1 双文件快照（可回退）· 历史共 %d 件" % len(arch))
else:
    bad("archive/ 缺 V1 双文件快照：%s" % (_v1 or "无"))

print("\n[2] JS 语法（node --check）")
for p in (CANVAS, PROTO):
    js = script_of(p.read_text(encoding="utf-8"))
    f = TMP / ("_syntax_%s.js" % ("canvas" if p is CANVAS else "proto"))
    f.write_text(js, encoding="utf-8")
    r = subprocess.run(["node", "--check", str(f)], capture_output=True, text=True)
    if r.returncode == 0:
        ok("%s 脚本语法通过（%d 字符）" % (p.name, len(js)))
    else:
        bad("%s 语法错误：%s" % (p.name, (r.stderr or "").strip()[:220]))

print("\n[3] 数据层（真实注册表注入）")
ptext = PROTO.read_text(encoding="utf-8")
m = re.search(r"const CAPS = /\* real registry snapshot \*/(\{.*?\});\n", ptext, re.S)
if not m:
    bad("原型未注入能力清单")
    caps = None
else:
    caps = json.loads(m.group(1))
    meta = caps["meta"]
    ok("清单条目 %d（可执行 %d + 禁用 %d）" % (meta["total"], meta["executable"], meta["disabled"]))
    ok("真实读数：路由 %s/%s · 接线 %s/%s · 体检 %s · 域 %d"
       % (meta["routed"], meta["registered"], meta["wired"], meta["audit_total"], meta["verdict"], meta["domains"]))
    archs = {c["arch"] for c in caps["caps"]}
    if len(archs) == 8:
        ok("8 种面板原型全部被使用：%s" % " ".join(sorted(archs)))
    else:
        bad("面板原型只有 %d 种" % len(archs))
    missing = [c["name"] for c in caps["caps"] if not c.get("arch")]
    if not missing:
        ok("151 项能力全部有面板原型（无缺面板）")
    else:
        bad("无面板的能力：%s" % missing[:8])

print("\n[4] 无限画布三层架构")
ctext = CANVAS.read_text(encoding="utf-8")
for label, key in (("Row 1 项目背景", "01 项目背景"), ("Row 2 设计系统", "02 设计系统"), ("Row 3 设计稿", "03 设计稿")):
    ok("%s 标注存在" % label) if key in ctext else bad("%s 缺失" % label)
for q in ("是什么", "给谁用", "解决什么问题"):
    ok("Row 1 回答「%s」" % q) if q in ctext else bad("Row 1 缺「%s」" % q)
pages = re.findall(r"\['[^']+',\s*p\d\(\)\]", ctext)
ok("Row 3 页面数 %d（含跳转引导线）" % len(pages)) if len(pages) >= 6 else bad("Row 3 页面过少：%d" % len(pages))
_pal_miss = [tok for tok in ("#c89b6c", "#111110", "#1e1e1d", "#7fa07a", "#cf9b3f", "#c9635a")
             if tok not in ctext]
# 旧版这里是「循环里可能 bad(...)，紧接着无条件 ok(...)」：真有缺 token 时报告会
# 同时打印 FAIL 和 PASS，汇总行也就不可信。ok 必须收进 else。
if _pal_miss:
    bad("色板 token 缺失：%s" % " ".join(_pal_miss))
else:
    ok("Row 2 六个色板 token 与设计系统一致")
if "addColorSwatch" in ctext or "swatch-circle" in ctext:
    ok("Row 2 使用色板组件")
else:
    bad("Row 2 无色板")

print("\n[5] 可交互原型硬性要求")
if re.search(r"max-width|clamp\(|@media", ptext):
    ok("响应式兜底存在（max-width / clamp / media query）")
else:
    bad("无可交互原型的响应式兜底")
if not re.search(r"width:\s*390px", ptext):
    ok("未写死 390px 外轮廓")
else:
    warn("出现写死 390px")
for bp in ("max-width:1023px", "max-width:767px"):
    ok("断点 %s 已定义" % bp) if bp in ptext else bad("缺断点 %s" % bp)
clicks = len(re.findall(r"addEventListener\('click'", ptext))
ok("可点击绑定 %d 处（≥2）" % clicks) if clicks >= 2 else bad("可点击元素不足")
if "aria-pressed" in ptext and "state-btn" in ptext:
    ok("状态切换存在（状态演示 + 筛选 chips 双组 aria-pressed）")
else:
    bad("缺状态切换")
states = ["populated", "loading", "empty", "error", "edge"]
if all(("'" + s + "'") in ptext for s in states):
    ok("五态齐备：加载 / 空 / 错误 / 填充 / 边界")
else:
    bad("状态不齐")
for sel in ("focus-visible", "aria-label", "role=\"alert\"", "aria-current"):
    ok("无障碍：%s" % sel) if sel in ptext else warn("缺无障碍：%s" % sel)

print("\n[6] 对比度（WCAG 2.2 AA：正文 4.5:1 / 大字 3:1 / 组件 3:1）")


def _lin(c):
    c = c / 255.0
    return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4


def lum(rgb):
    r, g, b = rgb
    return 0.2126 * _lin(r) + 0.7152 * _lin(g) + 0.0722 * _lin(b)


def ratio(fg, bg):
    a, b = lum(fg), lum(bg)
    hi, lo = max(a, b), min(a, b)
    return (hi + 0.05) / (lo + 0.05)


def over(alpha, base, bg):
    return tuple(alpha * base[i] + (1 - alpha) * bg[i] for i in range(3))


BG = (0x11, 0x11, 0x10)
TEXT = (0xE8, 0xE6, 0xE3)
pairs = [
    ("正文 #e8e6e3", TEXT, 4.5),
    ("二级文字 0.72", over(0.72, TEXT, BG), 4.5),
    ("三级文字 0.52", over(0.52, TEXT, BG), 4.5),
    ("语义 ok #7fa07a", (0x7F, 0xA0, 0x7A), 4.5),
    ("语义 warn #cf9b3f", (0xCF, 0x9B, 0x3F), 4.5),
    ("语义 danger #c9635a", (0xC9, 0x63, 0x5A), 4.5),
    ("语义 info #6f8fae", (0x6F, 0x8F, 0xAE), 4.5),
    ("强调色 #c89b6c", (0xC8, 0x9B, 0x6C), 4.5),
    ("主按钮字 深底 #1a1512 on 强调", (0x1A, 0x15, 0x12), 4.5),
]
for name, fg, floor in pairs:
    bg = (0xC8, 0x9B, 0x6C) if name.startswith("主按钮字") else BG
    r = ratio(fg, bg)
    (ok if r >= floor else bad)("%s → %.2f:1（≥%.1f）" % (name, r, floor))
print("\n[7] 反 AI-slop")
EMOJI = re.compile("[\U0001F300-\U0001FAFF\u2600-\u27BF\uFE0F]")
for p in (CANVAS, PROTO):
    t = p.read_text(encoding="utf-8")
    hits = EMOJI.findall(t)
    if hits:
        bad("%s 含 emoji %s" % (p.name, set(hits)))
    else:
        ok("%s 无 emoji 作为界面元素" % p.name)
# 规则书 anti-ai-slop.md:18-19 的禁用值恰好 7 个；旧清单 5 个，漏 #4338ca / #3730a3。
AI_INDIGO = ("#6366f1", "#4f46e5", "#4338ca", "#3730a3", "#8b5cf6", "#7c3aed", "#a855f7")
_indigo = [tok for tok in AI_INDIGO if tok in ptext or tok in ctext]
# 旧版同样是「循环里可能 bad(...)，紧接着无条件 ok(...)」—— 见 verify_out.txt:59
# 那行 PASS 就是这条无条件 ok 的落盘。ok 收进 else。
if _indigo:
    bad("出现 AI 默认靛紫：%s" % " ".join(_indigo))
else:
    ok("无 AI 默认靛紫（规则书全 7 值实测）")
# 旧检查是单个字面量 "linear-gradient(135deg"：实测交付物 0 条匹配该字面量，
# 于是这行 PASS 是空转的 —— 任何角度的两段渐变都能穿过。改成解析全部渐变，
# 取首尾 stop 求值（var() 回查 :root），只对「首尾色相跨族」的两段渐变报警。
_roots = {}
for _m in re.finditer(r":root\s*\{([^}]*)\}", ptext + ctext):
    for _k, _v in re.findall(r"(--[\w-]+)\s*:\s*([^;]+)", _m.group(1)):
        _roots.setdefault(_k, _v.strip().split()[0])


def _hx(c):
    c = c.strip()
    m = re.fullmatch(r"var\((--[\w-]+)\)", c)
    if m:
        return _hx(_roots.get(m.group(1), ""))
    m = re.fullmatch(r"#([0-9a-fA-F]{6})", c)
    return tuple(int(m.group(1)[i:i + 2], 16) for i in (0, 2, 4)) if m else None


def _hue(rgb):
    r, g, b = (v / 255 for v in rgb)
    mx, mn = max(r, g, b), min(r, g, b)
    if mx == mn:
        return None
    d = mx - mn
    h = (60 * ((g - b) / d) if mx == r else
         60 * ((b - r) / d) + 120 if mx == g else 60 * ((r - g) / d) + 240)
    return h % 360


_grads, _two, _trust = [], 0, []
for _g in re.findall(r"linear-gradient\(([^()]*(?:\([^()]*\)[^()]*)*)\)", ptext + ctext):
    _parts = [s.strip() for s in _g.split(",") if s.strip()]
    # 首段若是方向（135deg / to right / 180deg），剥掉；剩下的才是色标
    if _parts and re.fullmatch(r"(to\s+[\w\s]+|-?[\d.]+(deg|rad|turn)|[\d.]+%)", _parts[0]):
        _parts = _parts[1:]
    _grads.append(_g)
    if len(_parts) != 2:
        continue
    _a, _b = _hx(_parts[0].split()[0]), _hx(_parts[-1].split()[0])
    if _a is None or _b is None:
        continue
    _ha, _hb = _hue(_a), _hue(_b)
    if _ha is None or _hb is None:
        continue
    _d = min(abs(_ha - _hb), 360 - abs(_ha - _hb))
    _two += 1
    # 规则书禁止的三族：purple→blue / blue→cyan / indigo→pink。色相大致落在
    # 250-300（紫/靛）与 180-250（蓝/青）之间且两端跨族。同色相 ramp 不算（不报）。
    if _d >= 25 and ((250 <= _ha <= 300 and 180 <= _hb <= 250)
                     or (250 <= _hb <= 300 and 180 <= _ha <= 250)):
        _trust.append(_g)
if _trust:
    bad("出现 trust 渐变：%s" % _trust[:3])
else:
    ok("无两段式 trust 渐变（实测 linear-gradient %d 条，其中两段色标 %d 条）" % (len(_grads), _two))
if "lorem ipsum" in ptext.lower() or "Lorem ipsum" in ctext:
    bad("出现 lorem ipsum")
else:
    ok("无 lorem ipsum / 无占位废话")
emoji_ok = "allowed" if "标签允许" in ctext else ""
print("\n[7] 结果")
print("  PASS %d · WARN %d · FAIL %d" % (len(oks), len(warns), len(fails)))
if fails:
    print("  失败项：")
    for f in fails:
        print("   - " + f)
sys.exit(1 if fails else 0)
