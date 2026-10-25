# -*- coding: utf-8 -*-
"""构建 V8：V7 基础上补齐八块缺口面板（镜像/大模型/心智/情报/安全/长程工具/创作吞噬/其余域）。"""
import re
import shutil
from pathlib import Path

BASE = next(p for p in Path(__file__).resolve().parents
            if (p / "gbt_allinone").is_dir())   # 修：原 `.parent.parent` 只到 tools/（少一层）
S = BASE / ".scratch"
V7P = BASE / "V7 GBT小土豆V8-可交互原型.html"
V8P = BASE / "V8 GBT小土豆V8-可交互原型.html"

for p in [BASE / "V7 GBT小土豆V8-无限画布.html", V7P]:
    if p.exists():
        shutil.copy2(p, BASE / "archive" / p.name)
        print("归档:", p.name)

src = V7P.read_text(encoding="utf-8")
src = src.replace("可交互原型 V7", "可交互原型 V8")
src = re.sub(r"\bV7\b", "V8", src)

new_json = (S / "v8_manifest.json").read_text(encoding="utf-8").strip()
src, n = re.subn(r"const V8 = /\* real scan \+ brain \+ device \+ plug \+ tentacle snapshot \*/\{.*?\};\n",
                 lambda m: "const V8 = /* full snapshot incl. gap domains */" + new_json + ";\n",
                 src, count=1, flags=re.S)
assert n == 1, "数据层替换失败"

old_nav = """    ['万能插', 'plug', '9 工作流'], ['亿万触手', 'tentacle', '66 项'],"""
new_nav = """    ['万能插', 'plug', '9 工作流'], ['亿万触手', 'tentacle', '66 项'],
    ['镜像与晋升', 'mirror', '18 项'], ['大模型通道', 'llm', '18 项'],
    ['心智与记忆', 'mind', '8 项'], ['情报与观察', 'recon', '7 项'],
    ['安全攻防', 'security', '5 项'], ['长程与工具', 'longrun', '7 项'],
    ['创作与吞噬', 'create', '12 项'], ['其余域', 'others', '14 项'],"""
assert old_nav in src, "导航锚点未命中"
src = src.replace(old_nav, new_nav, 1)

anchor = "  /* ── 上帝视角 ── */"
assert anchor in src
src = src.replace(anchor, (S / "panels_v8.js").read_text(encoding="utf-8").rstrip("\n") + "\n\n" + anchor, 1)

old_disp = "    if (st.nav === 'tentacle') return panelTentacle();"
new_disp = old_disp + """
    if (st.nav === 'mirror') return panelMirror();
    if (st.nav === 'llm') return panelLLM();
    if (st.nav === 'mind') return panelMind();
    if (st.nav === 'recon') return panelRecon();
    if (st.nav === 'security') return panelSecurity();
    if (st.nav === 'longrun') return panelLongrun();
    if (st.nav === 'create') return panelCreate();
    if (st.nav === 'others') return panelOthers();"""
assert old_disp in src, "分发锚点未命中"
src = src.replace(old_disp, new_disp, 1)

V8P.write_text(src, encoding="utf-8")
print("写出:", V8P.name, len(V8P.read_bytes()), "B")
