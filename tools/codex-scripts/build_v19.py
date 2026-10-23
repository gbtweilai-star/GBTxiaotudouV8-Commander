# -*- coding: utf-8 -*-
"""构建 V19：加「AI朋友圈 · 用户社交」面板（数据实测自 eigenflux CLI 与源码）。"""
import collections
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
V18P = BASE / "V18 GBT小土豆V8-可交互原型.html"
V19P = BASE / "V19 GBT小土豆V8-可交互原型.html"

for n in (V18P.name, "V18 GBT小土豆V8-无限画布.html"):
    p = BASE / n
    if p.exists():
        shutil.copy2(p, BASE / "archive" / n)
        print("归档:", n)

SRC = V18P if V18P.exists() else BASE / "archive" / V18P.name
src = SRC.read_text(encoding="utf-8")
src = src.replace("可交互原型 V18", "可交互原型 V19")
src = re.sub(r"\bV18\b", "V19", src)
assert "const V19 = " in src

# ① 数据层
new_json = (S / "v19_manifest.json").read_text(encoding="utf-8").strip()
head = src.index("const V19 = ")
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
assert depth == 0
src = src[:brace] + "/* V19 · + AI朋友圈（EigenFlux）实况 + 用户社交 + 门状态 */" + new_json + src[i + 1:]
print("数据层: %.1f KB" % (len(new_json) / 1024))

# ② 面板
panels = (S / "panels_v19.js").read_text(encoding="utf-8")
anchor = "  function renderGod() {"
assert anchor in src
src = src.replace(anchor, panels.rstrip("\n") + "\n\n" + anchor, 1)

# ③ NAV：放进「其余域」之后、插件市场之前的一份独立分组
old_nav = "    ['严格覆盖审计', 'v17strict', '9.6 万行']\n  ];"
new_nav = ("    ['严格覆盖审计', 'v17strict', '9.6 万行'],\n"
           "    ['AI朋友圈 · 用户社交', 'social', '6385 agent']\n  ];")
assert old_nav in src
src = src.replace(old_nav, new_nav, 1)

old_grp = "    v17browser: 'V19 · 补漏（浏览器 / 云电脑 / 工具 / 内核）' };"
new_grp = ("    v17browser: 'V19 · 补漏（浏览器 / 云电脑 / 工具 / 内核）',\n"
           "    social: '社交 · 实测与接线状态' };")
assert old_grp in src
src = src.replace(old_grp, new_grp, 1)

old_disp = "    if (st.nav === 'v17strict') return panelV17Strict();\n  }"
new_disp = ("    if (st.nav === 'v17strict') return panelV17Strict();\n"
            "    if (st.nav === 'social') return panelSocial();\n  }")
assert old_disp in src
src = src.replace(old_disp, new_disp, 1)

# ④ 上帝视角插朋友圈卡
old_g = "      capSourceCard() +"
assert old_g in src
src = src.replace(old_g, "      socialCard() +\n" + old_g, 1)

# ⑤ 页脚
old_foot = '<b>GBT小土豆V8 · V19</b>55 面板 / 58 画布页 · 能力广场改为源码驱动<br>'
new_foot = '<b>GBT小土豆V8 · V19</b>56 面板 / 60 画布页 · 朋友圈与社交已实测入册<br>'
assert old_foot in src, "页脚锚点未命中"
src = src.replace(old_foot, new_foot, 1)

V19P.write_text(src, encoding="utf-8")

# ⑥ 收刻度
_t = V19P.read_text(encoding="utf-8")
_c = collections.Counter()
for _bad, _good in (("5px", "4px"), ("7px", "8px"), ("9px", "8px"),
                    ("11px", "12px"), ("13px", "12px"), ("14px", "16px"), ("15px", "16px")):
    _rx = re.compile(r"(gap:\s*)" + re.escape(_bad))
    _n = len(_rx.findall(_t))
    if _n:
        _t = _rx.sub(lambda m: m.group(1) + _good, _t)
        _c[_bad + "→" + _good] = _n
V19P.write_text(_t, encoding="utf-8")
print("收刻度:", dict(_c) or "无离群值")
print("写出:", V19P.name, "%.1f KB" % (V19P.stat().st_size / 1024))
if V18P.exists():
    V18P.unlink()
    print("移除旧版:", V18P.name)
