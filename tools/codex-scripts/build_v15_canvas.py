# -*- coding: utf-8 -*-
"""构建 V15 画布：影视氛围层（每一页都加）+ 开场镜头落位。
只加氛围与运动，不动 53 页任何内容、不动品牌标识。
"""
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
SRC = BASE / "archive" / "V14 GBT小土豆V8-无限画布.html"
OUT = BASE / "V15 GBT小土豆V8-无限画布.html"
assert SRC.exists(), "archive 里没有 V14 画布"

src = SRC.read_text(encoding="utf-8")
src = src.replace("无限画布 V14", "无限画布 V15")
src = re.sub(r"\bV14\b", "V15", src)

cine_css = (S / "cinematic.css").read_text(encoding="utf-8")
cine_js = (S / "cinematic.js").read_text(encoding="utf-8")

# ── 1. 氛围样式 ──
assert src.count("</style>") == 1, "style 收口不唯一"
src = src.replace("</style>", "</style>\n<style id=\"cine\">\n" + cine_css + "</style>", 1)

# ── 2. 氛围 DOM：body 第一个子节点（在 #viewport 之前 → 天然被内容盖住）──
old_body = "<body>\n\n<div class=\"canvas-viewport\" id=\"viewport\">"
new_body = ("<body>\n"
            "<div class=\"cine-atmo\" aria-hidden=\"true\">\n"
            "  <i class=\"cine-a\"></i><i class=\"cine-b\"></i><i class=\"cine-c\"></i>\n"
            "</div>\n"
            "<div class=\"cine-v\" aria-hidden=\"true\"></div>\n\n"
            "<div class=\"canvas-viewport\" id=\"viewport\">")
assert old_body in src, "画布 body 锚点未命中"
src = src.replace(old_body, new_body, 1)

# ── 3. 运动编排：必须插在 IIFE 内（开场镜头要用 zoom / panX / panY / updateTransform）──
old_tail = "  updateTransform();\n\n})();"
new_tail = ("  updateTransform();\n\n"
            "  /* ── V15 影视氛围层：面板入场的节奏 + 画布开场镜头落位 ── */\n"
            + cine_js + "\n})();")
assert old_tail in src, "画布 IIFE 收口锚点未命中"
src = src.replace(old_tail, new_tail, 1)

# ── 4. 署名（仍是同一句，版本号更新）──
src = src.replace("V15 · 50 面板 / 53 画布页 · 框架核心层已补",
                  "V15 · 50 面板 / 53 画布页 · 影视氛围层已加")

OUT.write_text(src, encoding="utf-8")
print("写出:", OUT.name, "%.1f KB" % (OUT.stat().st_size / 1024))
print("注入: 样式 %d B · 运动(内联 IIFE) %d B" % (len(cine_css), len(cine_js)))
