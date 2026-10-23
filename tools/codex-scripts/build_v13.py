# -*- coding: utf-8 -*-
"""构建 V13：把 App Logo（主人提供）接进原型。
- 侧栏品牌标 / 上帝视角标题标 / 对话空态品牌标 三处
- favicon（标签页图标）
- 内嵌 data URI，保证单文件自包含、离线可开
- 三个真实 DSH 席位（sidebar.brand.mark / sidebar.brand.name / conversation.hero.brand.mark）由缺口转为已实现
"""
import json
import re
import shutil
import sys
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:  # noqa: BLE001
    pass

BASE = next(p for p in Path(__file__).resolve().parents
            if (p / "gbt_allinone").is_dir())   # 修：原 `.parent.parent` 只到 tools/（少一层）
S = BASE / ".scratch"
V12P = BASE / "V12 GBT小土豆V8-可交互原型.html"
V13P = BASE / "V13 GBT小土豆V8-可交互原型.html"
V12ARC = BASE / "archive" / V12P.name

for p in [BASE / "V12 GBT小土豆V8-无限画布.html", V12P]:
    if p.exists():
        shutil.copy2(p, BASE / "archive" / p.name)
        print("归档:", p.name)

SRC = V12P if V12P.exists() else V12ARC
assert SRC.exists(), "找不到 V12 源"
print("源:", SRC.name, "(%s)" % ("根目录" if SRC == V12P else "archive"))
src = SRC.read_text(encoding="utf-8")
src = src.replace("可交互原型 V12", "可交互原型 V13")
src = re.sub(r"\bV12\b", "V13", src)
assert "const V13 = " in src, "数据层常量未改名"

emb = json.loads((S / "logo_embed.json").read_text(encoding="utf-8"))

# ── 1. 换数据层（花括号配对） ──
new_json = (S / "v13_manifest.json").read_text(encoding="utf-8").strip()
head = src.index("const V13 = ")
brace = src.index("{", head)
i, depth, in_str, esc_next = brace, 0, False, False
while i < len(src):
    c = src[i]
    if in_str:
        if esc_next:
            esc_next = False
        elif c == "\\":
            esc_next = True
        elif c == '"':
            in_str = False
    else:
        if c == '"':
            in_str = True
        elif c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                break
    i += 1
assert depth == 0, "数据层花括号未配对"
src = src[:brace] + "/* V13 · full snapshot + DSH 席位 + 工作区源码 + 品牌 Logo */" + new_json + src[i + 1:]

# ── 2. 品牌资源常量（放在数据层之前，全局可见） ──
brand_js = ("/* 品牌 Logo —— 主人提供；透明底 WebP 内嵌，单文件自包含 */\n"
            "const BRAND = {\n"
            "  logo: '" + emb["uri_prototype"] + "',\n"
            "  name: 'GBT小土豆V8',\n"
            "  sourceSha: '" + emb["source_sha256"][:16] + "',\n"
            "  colors: " + json.dumps(emb["colors"], ensure_ascii=False) + "\n"
            "};\n")
anchor_dl = src.index("const V13 = ")   # 必须插在整条声明之前，不能插进注释与对象之间
src = src[:anchor_dl] + brand_js + src[anchor_dl:]
print("品牌常量已注入（logo data URI %d B）" % len(emb["uri_prototype"]))

# ── 3. favicon ──
old_t = "<title>GBT小土豆V8 · 能力中枢 · 可交互原型 V13</title>"
new_t = (old_t + "\n<link rel=\"icon\" type=\"image/png\" href=\"" + emb["uri_favicon"] + "\">")
assert old_t in src, "title 锚点未命中"
src = src.replace(old_t, new_t, 1)

# ── 4. .logo 与 .orb 的样式：从「文字方块 / SVG 图标」改成「Logo 图像」 ──
old_logo_css = (".logo{flex:none;width:30px;height:30px;border-radius:9px;display:grid;place-items:center;"
                "font-family:var(--mono);font-size:10px;font-weight:700;color:var(--neon-2);"
                "background:linear-gradient(160deg,var(--panel-3),var(--panel));"
                "border:1px solid var(--line-hot);box-shadow:var(--glow)}")
new_logo_css = (".logo{flex:none;width:34px;height:34px;display:grid;place-items:center}\n"
                "  .logo img{width:34px;height:34px;object-fit:contain;display:block;"
                "filter:drop-shadow(0 0 8px rgba(42,212,240,.45))}")
assert old_logo_css in src, "logo CSS 锚点未命中"
src = src.replace(old_logo_css, new_logo_css, 1)

old_orb_css = (".hero .orb{width:52px;height:52px;border-radius:16px;border:1px solid var(--line-hot);"
               "display:grid;place-items:center;box-shadow:var(--glow);background:var(--panel)}")
new_orb_css = (".hero .orb{width:64px;height:64px;display:grid;place-items:center}\n"
               "  .hero .orb img{width:64px;height:64px;object-fit:contain;display:block;"
               "filter:drop-shadow(0 0 16px rgba(42,212,240,.52))}")
assert old_orb_css in src, "orb CSS 锚点未命中"
src = src.replace(old_orb_css, new_orb_css, 1)

# ── 5. 两处静态品牌标（侧栏 + 上帝视角）──
old_mark = '<span class="logo" aria-hidden="true">GBT</span>'
n_mark = src.count(old_mark)
assert n_mark == 2, "品牌标锚点数异常: %d" % n_mark
src = src.replace(old_mark, '<span class="logo" aria-hidden="true"><img alt="" width="34" height="34"></span>')

# 运行时给它们补 src（data URI 只在 BRAND 里存一份，不重复内嵌）
old_init = "  renderSessions(); renderComposer(); renderPanel(); syncSend();"
new_init = ("  /* 品牌 Logo：静态位补 src（data URI 只存一份，不重复内嵌）*/\n"
            "  Array.prototype.forEach.call(document.querySelectorAll('.logo img'), function (im) {\n"
            "    im.src = BRAND.logo;\n"
            "  });\n"
            "  renderSessions(); renderComposer(); renderPanel(); syncSend();")
assert old_init in src, "初始化锚点未命中"
src = src.replace(old_init, new_init, 1)

# ── 6. 对话空态品牌标（真实席位 conversation.hero.brand.mark）──
old_orb = ("      '<span class=\"orb\" aria-hidden=\"true\"><svg viewBox=\"0 0 24 24\" fill=\"none\" "
           "stroke=\"currentColor\" stroke-width=\"1.6\" width=\"22\" height=\"22\" style=\"color:var(--neon-2)\">' +\n"
           "      '<rect x=\"3\" y=\"3\" width=\"7\" height=\"7\" rx=\"1.5\"/><rect x=\"14\" y=\"3\" width=\"7\" height=\"7\" rx=\"1.5\"/>' +\n"
           "      '<rect x=\"3\" y=\"14\" width=\"7\" height=\"7\" rx=\"1.5\"/><rect x=\"14\" y=\"14\" width=\"7\" height=\"7\" rx=\"1.5\"/></svg></span>' +\n")
new_orb = ("      '<span class=\"orb\" aria-hidden=\"true\"><img src=\"' + BRAND.logo + '\" alt=\"\" "
           "width=\"64\" height=\"64\"></span>' +\n")
assert old_orb in src, "空态 orb 锚点未命中"
src = src.replace(old_orb, new_orb, 1)

# ── 7. 面板文案：三个席位已由缺口转为已实现 ──
FIX = [
    ("head('外壳与侧栏', { tag: 'shell · sidebar', meta: '11 席位 · 已实现 1' });",
     "head('外壳与侧栏', { tag: 'shell · sidebar', meta: '11 席位 · 已实现 3' });"),
    ("head('输入区席位', { tag: 'conversation.input', meta: '13 席位 · 已实现 0' });",
     "head('输入区席位', { tag: 'conversation.input', meta: '13 席位 · 已实现 1' });"),
    ("'任一插件都能往这些位置塞东西。本原型只实现了「工作区」这一格（项目树），' +\n"
     "      '其余 10 格目前是空的 —— 空就是空，不画假内容填。</p></div></div>' +",
     "'任一插件都能往这些位置塞东西。本原型实现了三格：品牌标（App Logo）、品牌名、工作区（项目树）；' +\n"
     "      '其余 8 格是空的 —— 空就是空，不画假内容填。<br>' +\n"
     "      '注：sidebar.brand.mark 官方留给了「官方品牌填充」，按本项目归属换成本项目的 Logo —— ' +\n"
     "      '这正是那个席位存在的意义。</p></div></div>' +"),
]
for a, b in FIX:
    assert a in src, "面板文案锚点未命中: " + a[:44]
    src = src.replace(a, b, 1)
print("面板文案修正: %d 处" % len(FIX))

# ── 8. 页脚 ──
old_foot = '<div class="nav-foot"><b>GBT小土豆V8 · V13</b>40 面板 / 43 画布页 · 工作区源码层已补<br>'
new_foot = '<div class="nav-foot"><b>GBT小土豆V8 · V13</b>40 面板 / 43 画布页 · 品牌 Logo 已接入<br>'
assert old_foot in src, "页脚锚点未命中"
src = src.replace(old_foot, new_foot, 1)

V13P.write_text(src, encoding="utf-8")
print("写出:", V13P.name, "%.1f KB" % (V13P.stat().st_size / 1024))
if V12P.exists():
    V12P.unlink()
    print("移除旧版:", V12P.name)
