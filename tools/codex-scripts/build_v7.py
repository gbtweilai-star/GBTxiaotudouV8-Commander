# -*- coding: utf-8 -*-
"""构建 V7：V6 基础上加「万能插」「亿万触手」两块真面板。归档 V6 → 写 V7。"""
import re
import shutil
from pathlib import Path

BASE = next(p for p in Path(__file__).resolve().parents
            if (p / "gbt_allinone").is_dir())   # 修：原 `.parent.parent` 只到 tools/（少一层）
S = BASE / ".scratch"
V6P = BASE / "V6 GBT小土豆V8-可交互原型.html"
V7P = BASE / "V7 GBT小土豆V8-可交互原型.html"

for p in [BASE / "V6 GBT小土豆V8-无限画布.html", V6P]:
    if p.exists():
        shutil.copy2(p, BASE / "archive" / p.name)
        print("归档:", p.name)

src = V6P.read_text(encoding="utf-8")
src = src.replace("可交互原型 V6", "可交互原型 V7")
src = re.sub(r"\bV6\b", "V7", src)

new_json = (S / "v7_manifest.json").read_text(encoding="utf-8").strip()
src, n = re.subn(r"const V7 = /\* real scan \+ brain \+ device snapshot \*/\{.*?\};\n",
                 "const V7 = /* real scan + brain + device + plug + tentacle snapshot */" + new_json + ";\n",
                 src, count=1, flags=re.S)
assert n == 1, "数据层替换失败"

old_nav = """    ['语音', 'voice', 'TTS 待授权'], ['蓝牙', 'bluetooth', '已修复'],"""
new_nav = """    ['语音', 'voice', 'TTS 待授权'], ['蓝牙', 'bluetooth', '已修复'],
    ['万能插', 'plug', '9 工作流'], ['亿万触手', 'tentacle', '66 项'],"""
assert old_nav in src, "导航锚点未命中"
src = src.replace(old_nav, new_nav, 1)

anchor = "  /* ── 上帝视角 ── */"
assert anchor in src
src = src.replace(anchor, (S / "panels_v7.js").read_text(encoding="utf-8").rstrip("\n") + "\n\n" + anchor, 1)

old_disp = "    if (st.nav === 'bluetooth') return panelBluetooth();"
new_disp = old_disp + "\n    if (st.nav === 'plug') return panelPlug();\n    if (st.nav === 'tentacle') return panelTentacle();"
assert old_disp in src, "分发锚点未命中"
src = src.replace(old_disp, new_disp, 1)

# st 里加 wf 选择位
src = src.replace("dist: 'field', godLoaded: false }", "dist: 'field', godLoaded: false, wf: null }", 1)

V7P.write_text(src, encoding="utf-8")
print("写出:", V7P.name, len(V7P.read_bytes()), "B")
