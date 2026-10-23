# -*- coding: utf-8 -*-
"""构建 V11：补「宿主外壳层」10 个面板 + 上帝视角宿主席位矩阵。
席位 id 全部来自本机官方包的 lib/client.js 真实注册，无一条编造。
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
V10P = BASE / "V10 GBT小土豆V8-可交互原型.html"
V11P = BASE / "V11 GBT小土豆V8-可交互原型.html"
V10ARC = BASE / "archive" / V10P.name

for p in [BASE / "V10 GBT小土豆V8-无限画布.html", V10P]:
    if p.exists():
        shutil.copy2(p, BASE / "archive" / p.name)
        print("归档:", p.name)

SRC = V10P if V10P.exists() else V10ARC
assert SRC.exists(), "找不到 V10 源（既不在根目录也不在 archive）"
print("源:", SRC.name, "(%s)" % ("根目录" if SRC == V10P else "archive"))
src = SRC.read_text(encoding="utf-8")
src = src.replace("可交互原型 V10", "可交互原型 V11")
src = re.sub(r"\bV10\b", "V11", src)
assert "const V11 = " in src, "数据层常量未改名"

# ── 1. 换数据层（花括号配对定位，不靠非贪婪正则） ──
new_json = (S / "v11_manifest.json").read_text(encoding="utf-8").strip()
head = src.index("const V11 = ")
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
src = src[:brace] + "/* V11 · full snapshot + plugin market + project tree + DSH 席位 */" + new_json + src[i + 1:]
print("数据层: %d B → %d B" % (old_len, len(new_json)))

# ── 2. 注入宿主外壳层 10 面板 ──
panels = (S / "panels_v11.js").read_text(encoding="utf-8")
anchor = "  function renderGod() {"
assert anchor in src, "renderGod 锚点未命中"
src = src.replace(anchor, panels.rstrip("\n") + "\n\n" + anchor, 1)

# ── 3. NAV 加一组 ──
old_nav = "    ['系统体检', 'health', M.verdict], ['设置', 'settings', '']\n  ];"
new_nav = ("    ['系统体检', 'health', M.verdict], ['设置', 'settings', ''],\n"
           "    ['外壳与侧栏', 'shell', '11 席'], ['会话头部', 'sesshead', '6 席'],\n"
           "    ['输入区席位', 'composer2', '13 席'], ['对话视图环', 'viewring', '6 席'],\n"
           "    ['工具卡片', 'toolcard', '14 席'], ['权限与提问', 'gateask', '4 包'],\n"
           "    ['子代理与技能', 'subskill', '5 包'], ['右侧栏与预览', 'rightpane', '6 席'],\n"
           "    ['设置中心', 'settingsx', '24 席'], ['外部应用直通', 'openapp', '30 应用']\n  ];")
assert old_nav in src, "NAV 锚点未命中"
src = src.replace(old_nav, new_nav, 1)

# 导航分组标签
old_map = "  $('navList').innerHTML = NAV.map(function (n) {\n    return '<button class=\"navitem\""
new_map = ("  $('navList').innerHTML = NAV.map(function (n) {\n"
           "    return (n[1] === 'shell' ? '<div class=\"sess-group\" style=\"padding:11px 10px 3px\">宿主外壳 · DSH 席面</div>' : '') +\n"
           "      '<button class=\"navitem\"")
assert old_map in src, "NAV 渲染锚点未命中"
src = src.replace(old_map, new_map, 1)

# ── 4. 分发 ──
old_disp = "    if (st.nav === 'market') return panelMarket();\n  }"
new_disp = ("    if (st.nav === 'market') return panelMarket();\n"
            "    if (st.nav === 'shell') return panelShell();\n"
            "    if (st.nav === 'sesshead') return panelSesshead();\n"
            "    if (st.nav === 'composer2') return panelComposer2();\n"
            "    if (st.nav === 'viewring') return panelViewring();\n"
            "    if (st.nav === 'toolcard') return panelToolcard();\n"
            "    if (st.nav === 'gateask') return panelGateask();\n"
            "    if (st.nav === 'subskill') return panelSubskill();\n"
            "    if (st.nav === 'rightpane') return panelRightpane();\n"
            "    if (st.nav === 'settingsx') return panelSettingsX();\n"
            "    if (st.nav === 'openapp') return panelOpenapp();\n  }")
assert old_disp in src, "分发锚点未命中"
src = src.replace(old_disp, new_disp, 1)

# ── 5. 上帝视角插席面矩阵 ──
old_g = "      treeCard() +\n      '<div class=\"grow2\">' +"
new_g = "      treeCard() +\n      slotMatrixCard() +\n      '<div class=\"grow2\">' +"
assert old_g in src, "上帝视角锚点未命中"
src = src.replace(old_g, new_g, 1)

# ── 6. 修 3 个老面板的键名错配（V10 就存在，静态校验抓不到，运行期才炸） ──
#     数据层已改名（pipeline_records / services / lr_progress / lr_tasks），面板还读旧名。
KEYFIX = [
    ("var st = G.mirror_status, scan = G.mirror_scan, svc = G.svc_inspect.services || {};",
     "var st = G.mirror_status, scan = G.mirror_scan, svc = G.services || {};"),
    ("(G.pipeline_status.records || []).length + ' 条</span></div><div class=\"card-b\">' +",
     "G.pipeline_n + ' 条</span></div><div class=\"card-b\">' +"),
    ("(G.pipeline_status.records || []).slice(0, 6).map(function (r) {",
     "(G.pipeline_records || []).slice(0, 6).map(function (r) {"),
    ("esc(G.m.sec_scan.ms) + 'ms · 真扫自有代码</span></div><div class=\"card-b\">' +",
     "esc(G.ms.sec_scan) + 'ms · 真扫自有代码</span></div><div class=\"card-b\">' +"),
    ("esc(G.m.sec_surface.ms) + 'ms</span></div><div class=\"card-b\">' +",
     "esc(G.ms.sec_surface) + 'ms</span></div><div class=\"card-b\">' +"),
    ("var lr = G.lr_status.progress || {}, sc = G.capability_net.seven_columns || {};",
     "var lr = G.lr_progress || {}, sc = G.capability_net.seven_columns || {};"),
    ("(G.lr_status.tasks || []).slice(0, 6).map(function (t) {",
     "(G.lr_tasks || []).slice(0, 6).map(function (t) {"),
]
for old_k, new_k in KEYFIX:
    assert old_k in src, "键名修复锚点未命中: " + old_k[:48]
    src = src.replace(old_k, new_k, 1)
print("键名修复: %d 处" % len(KEYFIX))

# ── 7. 侧栏页脚：更新为真实面板数 + 署名 ──
old_foot = '<div class="nav-foot"><b>GBT小土豆V8</b>七块面板全部接真实读数<br>无留位、无空壳</div>'
new_foot = ('<div class="nav-foot"><b>GBT小土豆V8 · V11</b>'
            '30 面板 / 33 画布页 · 宿主外壳层已补<br>'
            '<span style="font-size:9.5px;color:var(--ink-3)">'
            '开发者：自由的风 · 本署名不可删除、不可篡改归属</span></div>')
assert old_foot in src, "页脚锚点未命中"
src = src.replace(old_foot, new_foot, 1)

V11P.write_text(src, encoding="utf-8")
print("写出:", V11P.name, len(V11P.read_bytes()), "B")
if V10P.exists():
    V10P.unlink()
    print("移除旧版:", V10P.name)
