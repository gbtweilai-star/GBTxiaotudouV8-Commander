# -*- coding: utf-8 -*-
"""**现役那一代的验脚本在哪？** —— 一个入口，按盘上现役自动派发，缺了就明说。

为什么要有它（2026-09-22 现读实锤）：
  仓库按代养着一排 `verify_v3.py … verify_v21.py`，**每支都按死自己那代的文件名**。
  现役换成 V22 之后：
    · `verify_v21.py` 一跑就 `FileNotFoundError`（**崩在第二行**，而不是"告诉你该用哪支"）；
    · **根本没有 `verify_v22.py`** ⇒ 现役交付件长期没有内容门。
  本件把"该跑哪支"这件事变成一条命令：读根目录 `V*.html` 判现役代次 → 有对应验脚本就跑它、
  原样透传退出码；没有就 exit 2 并点名"缺哪支 + 照谁抄"。

顺带报"同伴件"（同一代通常还有运行期校验）：
  `verify_v{N}.py`（静态）· `verify_v{N}_runtime.js`（原型 DOM）· `verify_v{N}_canvas_runtime.js`（画布 DOM）
  —— 缺哪支就列出来（**只报告不判红**：本轮只补了静态那支，运行期那两支还没写）。

用法：py -3.14 tools/codex-scripts/verify_active.py
退出码：透传被派发脚本的退出码；没有验脚本 = 2。
"""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = next(p for p in Path(__file__).resolve().parents if (p / "gbt_allinone").is_dir())
HERE = Path(__file__).resolve().parent

actives = sorted(p.name for p in ROOT.glob("V*.html"))
if not actives:
    print("🔴 根目录没有任何 `V*.html` —— 判不出现役代次。")
    raise SystemExit(2)
gens = sorted({int(m.group(1)) for n in actives for m in [re.match(r"V(\d+) ", n)] if m})
print("盘上现役：%s（代次 %s）" % (" · ".join(actives), "、".join("V%d" % g for g in gens)))
gen = max(gens)

target = HERE / ("verify_v%d.py" % gen)
companions = [("verify_v%d.py" % gen, "静态/契约"),
              ("verify_v%d_runtime.js" % gen, "运行期 · 原型 DOM"),
              ("verify_v%d_canvas_runtime.js" % gen, "运行期 · 画布 DOM")]
have = [(n, why, (HERE / n).exists()) for n, why in companions]
print("同伴件现读：")
for n, why, ok in have:
    print("   %s %-34s %s" % ("✅" if ok else "🔴", n, why))
missing = [n for n, _w, ok in have if not ok]
if missing:
    print("   （缺的这几支本轮**只报告**：静态那支已补；两支运行期还没写。）")

if not target.exists():
    print("-" * 78)
    print("🔴 现役 V%d **没有验脚本**：%s 不存在。" % (gen, target.name))
    print("   修法：照最近一支现役验脚本（如 verify_v22.py）改一版 —— 文件名可以按死本代，")
    print("         但**母本要挑代际无关的判据**（红线 / 对比度 / 结构 / 署名 / 内嵌资源），")
    print("         别把上一代的数字（导航条数、页面数、能力数）直接抄成断言。")
    raise SystemExit(2)

print("-" * 78)
print("派发：%s" % target.name)
print("-" * 78)
r = subprocess.run([sys.executable, str(target)], cwd=str(ROOT))
if r.returncode == 0:
    print("-" * 78)
    print("结论：现役 V%d 的静态验收**通过**（运行期那两支%s）。"
          % (gen, "还缺" if missing else "也在"))
raise SystemExit(r.returncode)
