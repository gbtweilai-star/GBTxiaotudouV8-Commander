# -*- coding: utf-8 -*-
"""构建 V12：补「工作区源码层」10 个面板 + 上帝视角源码覆盖卡。
数字来自递归清点 + AST 解析，不是探针。
"""
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
V11P = BASE / "V11 GBT小土豆V8-可交互原型.html"
V12P = BASE / "V12 GBT小土豆V8-可交互原型.html"
V11ARC = BASE / "archive" / V11P.name

for p in [BASE / "V11 GBT小土豆V8-无限画布.html", V11P]:
    if p.exists():
        shutil.copy2(p, BASE / "archive" / p.name)
        print("归档:", p.name)

SRC = V11P if V11P.exists() else V11ARC
assert SRC.exists(), "找不到 V11 源"
print("源:", SRC.name, "(%s)" % ("根目录" if SRC == V11P else "archive"))
src = SRC.read_text(encoding="utf-8")
src = src.replace("可交互原型 V11", "可交互原型 V12")
src = re.sub(r"\bV11\b", "V12", src)
assert "const V12 = " in src, "数据层常量未改名"

# ── 1. 换数据层（花括号配对） ──
new_json = (S / "v12_manifest.json").read_text(encoding="utf-8").strip()
head = src.index("const V12 = ")
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
old_len = i + 1 - brace
src = src[:brace] + "/* V12 · full snapshot + DSH 席位 + 工作区源码清点 */" + new_json + src[i + 1:]
print("数据层: %d 字符 → %d 字符" % (old_len, len(new_json)))

# ── 2. 注入工作区源码层 10 面板 ──
panels = (S / "panels_v12.js").read_text(encoding="utf-8")
anchor = "  function renderGod() {"
assert anchor in src, "renderGod 锚点未命中"
src = src.replace(anchor, panels.rstrip("\n") + "\n\n" + anchor, 1)

# ── 3. NAV 加一组 ──
old_nav = "    ['设置中心', 'settingsx', '24 席'], ['外部应用直通', 'openapp', '30 应用']\n  ];"
new_nav = ("    ['设置中心', 'settingsx', '24 席'], ['外部应用直通', 'openapp', '30 应用'],\n"
           "    ['工作区源码总览', 'wsover', '全量清点'], ['缺口对账', 'wsgap', '8 万行'],\n"
           "    ['全息面板桥', 'wsholo', '3006 行'], ['桌面数字人', 'wspotato', '5423 行'],\n"
           "    ['五维合一', 'wsfive', '脑眼耳嘴手'], ['设计大脑', 'wsdesign', '777 行'],\n"
           "    ['情报流水线', 'wsrecon30', '20756 行'], ['审美技能', 'wsaesth', '26114 行'],\n"
           "    ['量化与钱包', 'wsquant', '11390 行'], ['账本与审美脑', 'wsledger', '557 行']\n  ];")
assert old_nav in src, "NAV 锚点未命中"
src = src.replace(old_nav, new_nav, 1)

# 导航分组：改成查表，支持两组
old_map = ("    return (n[1] === 'shell' ? '<div class=\"sess-group\" style=\"padding:11px 10px 3px\">宿主外壳 · DSH 席面</div>' : '') +\n"
           "      '<button class=\"navitem\"")
new_map = ("    return (GRP[n[1]] ? '<div class=\"sess-group\" style=\"padding:11px 10px 3px\">' + GRP[n[1]] + '</div>' : '') +\n"
           "      '<button class=\"navitem\"")
assert old_map in src, "NAV 渲染锚点未命中"
src = src.replace(old_map, new_map, 1)
old_st = "  var st = { nav: 'chat', sess: null,"
new_st = ("  var GRP = { shell: '宿主外壳 · DSH 席面', wsover: '工作区源码 · 全量清点' };\n"
          "  var st = { nav: 'chat', sess: null,")
assert old_st in src, "st 锚点未命中"
src = src.replace(old_st, new_st, 1)

# ── 4. 分发 ──
old_disp = "    if (st.nav === 'openapp') return panelOpenapp();\n  }"
new_disp = ("    if (st.nav === 'openapp') return panelOpenapp();\n"
            "    if (st.nav === 'wsover') return panelWsOverview();\n"
            "    if (st.nav === 'wsgap') return panelWsGap();\n"
            "    if (st.nav === 'wsholo') return panelWsHolo();\n"
            "    if (st.nav === 'wspotato') return panelWsPotato();\n"
            "    if (st.nav === 'wsfive') return panelWsFive();\n"
            "    if (st.nav === 'wsdesign') return panelWsDesign();\n"
            "    if (st.nav === 'wsrecon30') return panelWsRecon30();\n"
            "    if (st.nav === 'wsaesth') return panelWsAesth();\n"
            "    if (st.nav === 'wsquant') return panelWsQuant();\n"
            "    if (st.nav === 'wsledger') return panelWsLedger();\n  }")
assert old_disp in src, "分发锚点未命中"
src = src.replace(old_disp, new_disp, 1)

# ── 5. 上帝视角插源码覆盖卡 ──
old_g = "      treeCard() +\n      slotMatrixCard() +"
new_g = "      treeCard() +\n      slotMatrixCard() +\n      wsCoverCard() +"
assert old_g in src, "上帝视角锚点未命中"
src = src.replace(old_g, new_g, 1)

# ── 6. 页脚 ──
old_foot = ('<div class="nav-foot"><b>GBT小土豆V8 · V12</b>'
            '30 面板 / 33 画布页 · 宿主外壳层已补<br>')
new_foot = ('<div class="nav-foot"><b>GBT小土豆V8 · V12</b>'
            '40 面板 / 43 画布页 · 工作区源码层已补<br>')
assert old_foot in src, "页脚锚点未命中"
src = src.replace(old_foot, new_foot, 1)

V12P.write_text(src, encoding="utf-8")
print("写出:", V12P.name, "%.1f KB" % (V12P.stat().st_size / 1024))
if V11P.exists():
    V11P.unlink()
    print("移除旧版:", V11P.name)
