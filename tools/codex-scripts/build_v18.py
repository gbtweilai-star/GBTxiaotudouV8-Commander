# -*- coding: utf-8 -*-
"""构建 V18：能力广场改为「源码驱动」（140 能力逐条追到实现模块与 op 表）。"""
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
V17P = BASE / "V17 GBT小土豆V8-可交互原型.html"
V18P = BASE / "V18 GBT小土豆V8-可交互原型.html"
V17ARC = BASE / "archive" / V17P.name

for n in (V17P.name, "V17 GBT小土豆V8-无限画布.html"):
    p = BASE / n
    if p.exists():
        shutil.copy2(p, BASE / "archive" / n)
        print("归档:", n)

SRC = V17P if V17P.exists() else V17ARC
assert SRC.exists(), "找不到 V17 源"
src = SRC.read_text(encoding="utf-8")
src = src.replace("可交互原型 V17", "可交互原型 V18")
src = re.sub(r"\bV17\b", "V18", src)
assert "const V18 = " in src

# ① 换数据层
new_json = (S / "v18_manifest.json").read_text(encoding="utf-8").strip()
head = src.index("const V18 = ")
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
src = src[:brace] + "/* V18 · + 能力→源码反查（三份真相合并） */" + new_json + src[i + 1:]
print("数据层: %.1f KB" % (len(new_json) / 1024))

# ② 注入源码驱动面板
panels = (S / "panels_v18.js").read_text(encoding="utf-8")
anchor = "  function renderGod() {"
assert anchor in src
src = src.replace(anchor, panels.rstrip("\n") + "\n\n" + anchor, 1)

# ③ 能力广场改成源码驱动（保留原 key 'square' 与导航标签，只换实现）
old_disp = "    if (st.nav === 'square') return panelSquare();"
new_disp = "    if (st.nav === 'square') return panelCapSrc();   /* V18：原手写版换成源码驱动版 */"
assert old_disp in src
src = src.replace(old_disp, new_disp, 1)
src = src.replace("['能力广场', 'square', String(V18.caps.length)]",
                  "['能力广场', 'square', V18.capsrc.total + ' · 源码驱动']", 1)

# ④ 上帝视角插源码覆盖卡
old_g = "      wsCoverCard() +"
assert old_g in src
src = src.replace(old_g, "      capSourceCard() +\n" + old_g, 1)

# ⑤ 页脚
old_foot = '<b>GBT小土豆V8 · V18</b>55 面板 / 58 画布页 · 原生浏览器与云电脑已补<br>'
new_foot = '<b>GBT小土豆V8 · V18</b>55 面板 / 58 画布页 · 能力广场改为源码驱动<br>'
assert old_foot in src, "页脚锚点未命中"
src = src.replace(old_foot, new_foot, 1)

V18P.write_text(src, encoding="utf-8")

# ⑥ 收刻度（新面板里若抄进离群 gap，一并收到 2px 刻度）
import collections  # noqa: E402
_t = V18P.read_text(encoding="utf-8")
_c = collections.Counter()
for _bad, _good in (("5px", "4px"), ("7px", "8px"), ("9px", "8px"),
                    ("11px", "12px"), ("13px", "12px"), ("14px", "16px"), ("15px", "16px")):
    _rx = re.compile(r"(gap:\s*)" + re.escape(_bad))
    _n = len(_rx.findall(_t))
    if _n:
        _t = _rx.sub(lambda m: m.group(1) + _good, _t)
        _c[_bad + "→" + _good] = _n
V18P.write_text(_t, encoding="utf-8")
print("收刻度:", dict(_c) or "无离群值")
print("写出:", V18P.name, "%.1f KB" % (V18P.stat().st_size / 1024))
if V17P.exists():
    V17P.unlink()
    print("移除旧版:", V17P.name)
