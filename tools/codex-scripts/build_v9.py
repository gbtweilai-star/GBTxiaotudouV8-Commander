# -*- coding: utf-8 -*-
"""构建 V9：V8 基础上加「插件市场（蒸馏件）」面板。归档 V8 → 写 V9。"""
import re
import shutil
from pathlib import Path

BASE = next(p for p in Path(__file__).resolve().parents
            if (p / "gbt_allinone").is_dir())   # 修：原 `.parent.parent` 只到 tools/（少一层）
S = BASE / ".scratch"
V8P = BASE / "V8 GBT小土豆V8-可交互原型.html"
V9P = BASE / "V9 GBT小土豆V8-可交互原型.html"

for p in [BASE / "V8 GBT小土豆V8-无限画布.html", V8P]:
    if p.exists():
        shutil.copy2(p, BASE / "archive" / p.name)
        print("归档:", p.name)

src = V8P.read_text(encoding="utf-8")
src = src.replace("可交互原型 V8", "可交互原型 V9")
src = re.sub(r"\bV8\b", "V9", src)

new_json = (S / "v9_manifest.json").read_text(encoding="utf-8").strip()
src, n = re.subn(r"const V9 = /\* full snapshot incl\. gap domains \*/\{.*?\};\n",
                 lambda m: "const V9 = /* full snapshot + plugin market */" + new_json + ";\n",
                 src, count=1, flags=re.S)
assert n == 1, "数据层替换失败"

old_nav = "    ['创作与吞噬', 'create', '12 项'], ['其余域', 'others', '14 项'],"
new_nav = old_nav + "\n    ['插件市场', 'market', '蒸馏件'],"
assert old_nav in src, "导航锚点未命中"
src = src.replace(old_nav, new_nav, 1)

anchor = "  /* ── 上帝视角 ── */"
src = src.replace(anchor, (S / "panels_v9.js").read_text(encoding="utf-8").rstrip("\n") + "\n\n" + anchor, 1)

old_disp = "    if (st.nav === 'others') return panelOthers();"
new_disp = old_disp + "\n    if (st.nav === 'market') return panelMarket();"
assert old_disp in src, "分发锚点未命中"
src = src.replace(old_disp, new_disp, 1)

V9P.write_text(src, encoding="utf-8")
print("写出:", V9P.name, len(V9P.read_bytes()), "B")
