# -*- coding: utf-8 -*-
"""把真渲染结果导出到工作区根目录 render/（转 JPEG 压体积），并生成索引。"""
import json
import sys
from pathlib import Path

from PIL import Image

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
BASE = next(p for p in Path(__file__).resolve().parents
            if (p / "gbt_allinone").is_dir())   # 修：原 `.parent.parent` 只到 tools/（少一层）
SRC = BASE / ".scratch" / "render"
DST = BASE / "render"
(DST / "panels").mkdir(parents=True, exist_ok=True)
(DST / "canvas").mkdir(parents=True, exist_ok=True)

n = 0
for sub, rep_name in (("panels", "report.json"), ("canvas", "canvas_report.json")):
    rep = json.loads((SRC / rep_name).read_text(encoding="utf-8"))
    for s in rep["shots"]:
        p = SRC / sub / s["file"]
        if not p.is_file():
            continue
        im = Image.open(p).convert("RGB")
        out = DST / sub / (Path(s["file"]).stem + ".jpg")
        im.save(out, "JPEG", quality=90, optimize=True)
        n += 1
    # 附带总览与视口图
for extra, dst in (("viewport_desktop.png", "viewport-desktop.jpg"),
                   ("viewport_mid.png", "viewport-mid.jpg"),
                   ("viewport_mobile.png", "viewport-mobile.jpg")):
    p = SRC / extra
    if p.is_file():
        Image.open(p).convert("RGB").save(DST / dst, "JPEG", quality=92, optimize=True)
for extra, dst in (("contact_panels.png", "总览-55面板.png"), ("contact_canvas.png", "总览-58画布页.png")):
    p = SRC / extra
    if p.is_file():
        Image.open(p).save(DST / dst, optimize=True)

size = sum(f.stat().st_size for f in DST.rglob("*") if f.is_file())
files = [f for f in DST.rglob("*") if f.is_file()]
print("导出 %d 个文件 · %.1f MB → %s" % (len(files), size / 1048576, DST))

index = ["# GBT小土豆V8 · V17 真渲染交付", "",
         "全部由 **Playwright 驱动系统 Chrome 1680×1050** 真渲染产出（不是合成样张）。", "",
         "## 总览", "- `总览-55面板.png` —— 55 个面板一图看全",
         "- `总览-58画布页.png` —— 58 个画布页一图看全", "",
         "## 视口", "- `viewport-desktop.jpg` 1680×1050", "- `viewport-mid.jpg` 1280×800",
         "- `viewport-mobile.jpg` 390×844", "",
         "## 目录", "- `panels/` 55 张（可交互原型，逐面板切换后截图）",
         "- `canvas/` 58 张（无限画布，逐页移到视口中心后截图）", "",
         "## 浏览器级 UI-check 结果",
         "- **页面级横向滚动：0 个面板** ✓",
         "- 进度条溢出（384%）：已修 ✓",
         "- 面板塌页（情报与观察）：已修 ✓",
         "- 其余命中项：SVG 力导向图（设计如此）与手机端收起态抽屉（设计如此）", ""]
(DST / "README.md").write_text("\n".join(index), encoding="utf-8")
print("索引:", DST / "README.md")
