# -*- coding: utf-8 -*-
"""构建 V16：专业化打磨层（排版系统 + 间距节奏 + 数据工艺 + 表面层级）。
Refinement，只动视觉；结构 / 文案 / 数据 / 逻辑 / Logo 一律不动。
"""
import re
import shutil
import sys
from collections import Counter
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:  # noqa: BLE001
    pass

BASE = next(p for p in Path(__file__).resolve().parents
            if (p / "gbt_allinone").is_dir())   # 修：原 `.parent.parent` 只到 tools/（少一层）
S = BASE / ".scratch"

for n in ("V15 GBT小土豆V8-可交互原型.html", "V15 GBT小土豆V8-无限画布.html"):
    p = BASE / n
    if p.exists():
        shutil.copy2(p, BASE / "archive" / n)
        print("归档:", n)

refine = (S / "refine.css").read_text(encoding="utf-8")


def snap_inline_gaps(src):
    """把内联里「不在 2px 刻度上」的 gap 值收到刻度上。
    刻度：4 / 6 / 8 / 10 / 12 / 16 / 20 / 24 / 32。
    只改离群值（5/7/9/11/14/15），on-scale 的一律不动。"""
    MAP = {"5px": "4px", "7px": "8px", "9px": "8px", "11px": "12px",
           "14px": "16px", "15px": "16px", "13px": "12px", "18px": "20px"}
    total = Counter()
    for bad, good in MAP.items():
        pat = re.compile(r"(gap:\s*)" + re.escape(bad))
        n = len(pat.findall(src))
        if n:
            src = pat.sub(lambda m: m.group(1) + good, src)
            total[bad + "→" + good] = n
    return src, total


# ── 原型 ──
proto = (BASE / "V15 GBT小土豆V8-可交互原型.html").read_text(encoding="utf-8")
proto = proto.replace("可交互原型 V15", "可交互原型 V16")
proto = re.sub(r"\bV15\b", "V16", proto)
assert "const V16 = " in proto

assert proto.count("</style>") == 2, "style 块数异常"
proto = proto.replace("</style>", "</style>\n<style id=\"refine\">\n" + refine + "</style>", 1) if False else proto
# 上面这种替换会命中第一个 </style>，需要精确插到 cinematic 之后
old_cine_end = "</style>\n</head>"
if old_cine_end in proto:
    proto = proto.replace(old_cine_end,
                          "</style>\n<style id=\"refine\">\n" + refine + "</style>\n</head>", 1)
else:
    i = proto.rindex("</style>")
    proto = proto[:i] + "</style>\n<style id=\"refine\">\n" + refine + "</style>" + proto[i + len("</style>"):]

proto, gaps_p = snap_inline_gaps(proto)
proto = proto.replace('<b>GBT小土豆V8 · V16</b>50 面板 / 53 画布页 · 影视氛围层已加<br>',
                      '<b>GBT小土豆V8 · V16</b>50 面板 / 53 画布页 · 排版与节奏已打磨<br>')
out_p = BASE / "V16 GBT小土豆V8-可交互原型.html"
out_p.write_text(proto, encoding="utf-8")
print("写出:", out_p.name, "%.1f KB" % (out_p.stat().st_size / 1024))
print("  内联 gap 收刻度:", dict(gaps_p) or "无")

# ── 画布 ──
canv = (BASE / "V15 GBT小土豆V8-无限画布.html").read_text(encoding="utf-8")
canv = canv.replace("无限画布 V15", "无限画布 V16")
canv = re.sub(r"\bV15\b", "V16", canv)
assert canv.count("</style>") == 2, "画布 style 块数异常"
i = canv.rindex("</style>")
canv = canv[:i] + "</style>\n<style id=\"refine\">\n" + refine + "</style>" + canv[i + len("</style>"):]
canv, gaps_c = snap_inline_gaps(canv)
canv = canv.replace("V16 · 50 面板 / 53 画布页 · 影视氛围层已加",
                    "V16 · 50 面板 / 53 画布页 · 排版与节奏已打磨")
out_c = BASE / "V16 GBT小土豆V8-无限画布.html"
out_c.write_text(canv, encoding="utf-8")
print("写出:", out_c.name, "%.1f KB" % (out_c.stat().st_size / 1024))
print("  内联 gap 收刻度:", dict(gaps_c) or "无")

for n in ("V15 GBT小土豆V8-可交互原型.html", "V15 GBT小土豆V8-无限画布.html"):
    p = BASE / n
    if p.exists():
        p.unlink()
        print("移除旧版:", n)
