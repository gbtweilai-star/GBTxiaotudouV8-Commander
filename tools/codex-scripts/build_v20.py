# -*- coding: utf-8 -*-
"""构建 V20：AI朋友圈关系场可视化面板。"""
import collections
import re
import shutil
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
BASE = next(p for p in Path(__file__).resolve().parents
            if (p / "gbt_allinone").is_dir())   # 修：原 `.parent.parent` 只到 tools/（少一层）
S = BASE / ".scratch"
V19P = BASE / "V19 GBT小土豆V8-可交互原型.html"
V20P = BASE / "V20 GBT小土豆V8-可交互原型.html"

for n in (V19P.name, "V19 GBT小土豆V8-无限画布.html"):
    p = BASE / n
    if p.exists():
        shutil.copy2(p, BASE / "archive" / n)
        print("归档:", n)

SRC = V19P if V19P.exists() else BASE / "archive" / V19P.name
src = SRC.read_text(encoding="utf-8")
src = src.replace("可交互原型 V19", "可交互原型 V20")
src = re.sub(r"\bV19\b", "V20", src)

new_json = (S / "v20_manifest.json").read_text(encoding="utf-8").strip()
head = src.index("const V20 = ")
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
src = src[:brace] + "/* V20 · + AI朋友圈关系场（星图由真实数据算出） */" + new_json + src[i + 1:]
print("数据层: %.1f KB" % (len(new_json) / 1024))

panels = (S / "panels_v20.js").read_text(encoding="utf-8")
anchor = "  function renderGod() {"
src = src.replace(anchor, panels.rstrip("\n") + "\n\n" + anchor, 1)

# NAV：社交那项改成关系场，并新增
old_nav = "    ['AI朋友圈 · 用户社交', 'social', '6385 agent']\n  ];"
new_nav = ("    ['AI朋友圈 · 关系场', 'socialgraph', '10 好友'],\n"
           "    ['AI朋友圈 · 用户社交', 'social', '6385 agent']\n  ];")
assert old_nav in src, "NAV 锚点未命中"
src = src.replace(old_nav, new_nav, 1)
src = src.replace("    social: '社交 · 实测与接线状态' };",
                  "    socialgraph: '社交 · 关系场可视化', social: '社交 · 实测与接线状态' };", 1)

old_disp = "    if (st.nav === 'social') return panelSocial();\n  }"
new_disp = ("    if (st.nav === 'social') return panelSocial();\n"
            "    if (st.nav === 'socialgraph') return panelSocialGraph();\n  }")
assert old_disp in src
src = src.replace(old_disp, new_disp, 1)

old_g = "      socialCard() +"
assert old_g in src
src = src.replace(old_g, "      socialGraphCard() +\n" + old_g, 1)

old_foot = '<b>GBT小土豆V8 · V20</b>56 面板 / 60 画布页 · 朋友圈与社交已实测入册<br>'
new_foot = '<b>GBT小土豆V8 · V20</b>57 面板 / 61 画布页 · 朋友圈关系场已可视化<br>'
assert old_foot in src, "页脚锚点未命中"
src = src.replace(old_foot, new_foot, 1)

V20P.write_text(src, encoding="utf-8")
_t = V20P.read_text(encoding="utf-8")
_c = collections.Counter()
for _bad, _good in (("5px", "4px"), ("7px", "8px"), ("9px", "8px"),
                    ("11px", "12px"), ("13px", "12px"), ("14px", "16px"), ("15px", "16px")):
    _rx = re.compile(r"(gap:\s*)" + re.escape(_bad))
    _n = len(_rx.findall(_t))
    if _n:
        _t = _rx.sub(lambda m: m.group(1) + _good, _t)
        _c[_bad + "→" + _good] = _n
V20P.write_text(_t, encoding="utf-8")
print("收刻度:", dict(_c) or "无离群值")
print("写出:", V20P.name, "%.1f KB" % (V20P.stat().st_size / 1024))
if V19P.exists():
    V19P.unlink()
    print("移除旧版:", V19P.name)
