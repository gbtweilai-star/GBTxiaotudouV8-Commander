# -*- coding: utf-8 -*-
"""构建 V6：V5 基础上加「语音」「蓝牙」两块真面板。归档 V5 → 写 V6。"""
import re
import shutil
from pathlib import Path

BASE = next(p for p in Path(__file__).resolve().parents
            if (p / "gbt_allinone").is_dir())   # 修：原 `.parent.parent` 只到 tools/（少一层）
S = BASE / ".scratch"
V5P = BASE / "V5 GBT小土豆V8-可交互原型.html"
V6P = BASE / "V6 GBT小土豆V8-可交互原型.html"
V6JSON = S / "v6_manifest.json"
PANELS = S / "panels_v6.js"

V5 = [BASE / "V5 GBT小土豆V8-无限画布.html", V5P]
(BASE / "archive").mkdir(exist_ok=True)
for p in V5:
    if p.exists():
        shutil.copy2(p, BASE / "archive" / p.name)
        print("归档:", p.name)

src = V5P.read_text(encoding="utf-8")

# 1) 版本与变量名
src = src.replace("可交互原型 V5", "可交互原型 V6")
src = re.sub(r"\bV5\b", "V6", src)

# 2) 换数据（保留已注入的 JSON 位置）
new_json = V6JSON.read_text(encoding="utf-8").strip()
src = re.sub(r"const V6 = /\* real scan \+ brain probe snapshot \*/\{.*?\};\n",
             "const V6 = /* real scan + brain + device snapshot */" + new_json + ";\n",
             src, count=1, flags=re.S)

# 3) 导航加两块（放在「系统体检」之前，设备类聚在一起）
old_nav = """    ['审计台账', 'audit', String(V6.activity.length)], ['系统体检', 'health', M.verdict],
    ['设置', 'settings', '']"""
new_nav = """    ['审计台账', 'audit', String(V6.activity.length)],
    ['语音', 'voice', 'TTS 待授权'], ['蓝牙', 'bluetooth', '已修复'],
    ['系统体检', 'health', M.verdict], ['设置', 'settings', '']"""
assert old_nav in src, "导航锚点未命中"
src = src.replace(old_nav, new_nav, 1)

# 4) 插入两块面板实现（放在上帝视角之前）
anchor = "  /* ── 上帝视角 ── */"
assert anchor in src, "面板插入锚点未命中"
src = src.replace(anchor, PANELS.read_text(encoding="utf-8").rstrip("\n") + "\n\n" + anchor, 1)

# 5) 分发
old_disp = "    if (st.nav === 'settings') return panelSettings();"
new_disp = old_disp + "\n    if (st.nav === 'voice') return panelVoice();\n    if (st.nav === 'bluetooth') return panelBluetooth();"
assert old_disp in src, "分发锚点未命中"
src = src.replace(old_disp, new_disp, 1)

V6P.write_text(src, encoding="utf-8")
print("写出:", V6P.name, len(V6P.read_bytes()), "B")
