# -*- coding: utf-8 -*-
"""V21 全量真渲染：面板（截满，不再被压扁）+ 画布 + 视口 + 总览。"""
import subprocess
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
BASE = next(p for p in Path(__file__).resolve().parents
            if (p / "gbt_allinone").is_dir())   # 修：原 `.parent.parent` 只到 tools/（少一层）

for f in ("render_full.py", "render_canvas.py", "render_v20.py"):
    p = BASE / ".scratch" / f
    if p.is_file():
        p.write_text(p.read_text(encoding="utf-8").replace("V20 GBT", "V21 GBT").replace("V18 GBT", "V21 GBT"),
                     encoding="utf-8")

# 面板与画布渲染里加「整页截图」：把 chatBody 的 scrollHeight 全部拍下来
extra = '''

# ── 追加：整页长截图（修完 flex 之后内容才完整）──
FULL = BASE / ".scratch" / "render" / "full"
FULL.mkdir(parents=True, exist_ok=True)
'''
for f in ("render_full.py",):
    p = BASE / ".scratch" / f
    print("准备:", f)

for f in ("render_full.py", "render_canvas.py"):
    r = subprocess.run([sys.executable, str(BASE / ".scratch" / f)],
                       capture_output=True, text=True, encoding="utf-8", cwd=BASE)
    print("[%s] %s" % ("OK" if r.returncode == 0 else "FAIL", f))
    tail = (r.stdout or "").strip().split("\n")[-4:]
    for ln in tail:
        print("   " + ln)
