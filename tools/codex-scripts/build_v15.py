# -*- coding: utf-8 -*-
"""构建 V15：影视氛围层（每一页都加）。
Refinement 模式 —— 结构、IA、文案、数据、Logo 一律不动，只加氛围与运动。
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
V14P = BASE / "V14 GBT小土豆V8-可交互原型.html"
V15P = BASE / "V15 GBT小土豆V8-可交互原型.html"
V14ARC = BASE / "archive" / V14P.name

for p in [BASE / "V14 GBT小土豆V8-无限画布.html", V14P]:
    if p.exists():
        shutil.copy2(p, BASE / "archive" / p.name)
        print("归档:", p.name)

SRC = V14P if V14P.exists() else V14ARC
assert SRC.exists(), "找不到 V14 源"
src = SRC.read_text(encoding="utf-8")
src = src.replace("可交互原型 V14", "可交互原型 V15")
src = re.sub(r"\bV14\b", "V15", src)
assert "const V15 = " in src

cine_css = (S / "cinematic.css").read_text(encoding="utf-8")
cine_js = (S / "cinematic.js").read_text(encoding="utf-8")

# ── 1. 氛围样式表（追加一个独立 style，不动既有 213 条规则）──
anchor = "</style>"
assert src.count(anchor) == 1, "style 收口不唯一"
src = src.replace(anchor, anchor + "\n<style id=\"cine\">\n" + cine_css + "</style>", 1)

# ── 2. 氛围 DOM（body 第一个子节点 → 天然在内容层之下）──
old_body = "<body>\n<div class=\"app\">"
new_body = ("<body>\n"
            "<div class=\"cine-atmo\" aria-hidden=\"true\">\n"
            "  <i class=\"cine-a\"></i><i class=\"cine-b\"></i><i class=\"cine-c\"></i>\n"
            "</div>\n"
            "<div class=\"cine-v\" aria-hidden=\"true\"></div>\n"
            "<div class=\"app\">")
assert old_body in src, "body 锚点未命中"
src = src.replace(old_body, new_body, 1)

# ── 3. 运动编排（独立 script，放在既有主脚本之后 → 首屏渲染已发生，观察器接管后续）──
old_end = "</body>"
assert old_end in src, "body 收口未命中"
src = src.replace(old_end,
                  "<script id=\"cine-motion\">\n" + cine_js + "</script>\n</body>", 1)

# ── 4. 页脚 ──
old_foot = '<b>GBT小土豆V8 · V15</b>50 面板 / 53 画布页 · 框架核心层已补<br>'
new_foot = '<b>GBT小土豆V8 · V15</b>50 面板 / 53 画布页 · 影视氛围层已加<br>'
assert old_foot in src, "页脚锚点未命中"
src = src.replace(old_foot, new_foot, 1)

# ── 5. UI-check 打磨：字号下限抬到 9.5px（UI-check §2「Text that is too small」直接修）
#      stroke-width="7" 是环形数据图的描边，不是图标，不动。
n9 = src.count("font-size:9px")
src = src.replace("font-size:9px", "font-size:9.5px")
n85 = src.count("font-size:8.5px")
src = src.replace("font-size:8.5px", "font-size:9.5px")
print("字号下限: 9px×%d + 8.5px×%d → 9.5px" % (n9, n85))

V15P.write_text(src, encoding="utf-8")
print("写出:", V15P.name, "%.1f KB" % (V15P.stat().st_size / 1024))
if V14P.exists():
    V14P.unlink()
    print("移除旧版:", V14P.name)
print("注入: 样式 %d B · 运动 %d B" % (len(cine_css), len(cine_js)))
