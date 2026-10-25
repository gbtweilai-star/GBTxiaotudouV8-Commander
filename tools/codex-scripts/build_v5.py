# -*- coding: utf-8 -*-
"""构建 V5 双交付：归档 V4 → 写 V5（画布 + 注入真读数）。"""
import shutil
from pathlib import Path

BASE = next(p for p in Path(__file__).resolve().parents
            if (p / "gbt_allinone").is_dir())   # 修：原 `.parent.parent` 只到 tools/（少一层）
TPL = BASE / "infinite-canvas-output" / "assets" / "infinite-canvas-template.html"
STRINGS = BASE / ".scratch" / "canvas_strings_v5.js"
SCENE = BASE / ".scratch" / "canvas_scene_v5.js"
V5JSON = BASE / ".scratch" / "v5_manifest.json"

V4 = [BASE / "V4 GBT小土豆V8-无限画布.html", BASE / "V4 GBT小土豆V8-可交互原型.html"]
OUT_CANVAS = BASE / "V5 GBT小土豆V8-无限画布.html"
OUT_PROTO = BASE / "V5 GBT小土豆V8-可交互原型.html"
BLOCK = "/*__V5__*/null"

(BASE / "archive").mkdir(exist_ok=True)
for p in V4:
    if p.exists():
        shutil.copy2(p, BASE / "archive" / p.name)
        print("归档:", p.name)

TOKENS = """  :root {
    --bg: #04070f; --bg-subtle: #08111f; --surface: #0c1a2e; --surface-raised: #102339;
    --border: rgba(88,196,255,0.14); --border-hover: rgba(88,196,255,0.34);
    --accent: #2ad4f0; --accent-dim: rgba(42,212,240,0.12);
    --text: #dff2fb; --text-secondary: rgba(223,242,251,0.74); --text-tertiary: rgba(223,242,251,0.54);
    --shadow-sm: 0 0 8px rgba(42,212,240,0.12);
    --shadow-md: 0 0 22px rgba(42,212,240,0.18);
    --shadow-lg: 0 0 40px rgba(42,212,240,0.22);
    --shadow-drag: 0 20px 60px rgba(0,0,0,0.55), 0 0 0 1.5px var(--accent);
    --radius-sm: 4px; --radius-md: 8px; --radius-lg: 12px; --radius-xl: 18px;
    --font-sans: "SF Pro Display", -apple-system, BlinkMacSystemFont, "Segoe UI Variable Display", "Segoe UI", "PingFang SC", "Microsoft YaHei", sans-serif;
    --font-mono: "SF Mono", "JetBrains Mono", "Cascadia Mono", Consolas, "DejaVu Sans Mono", monospace;
    --note-bg: #0c1a2e; --note-border: rgba(42,212,240,0.28);
    --transition-fast: 120ms cubic-bezier(0.25, 0.1, 0.25, 1);
    --transition-normal: 200ms cubic-bezier(0.16, 1, 0.3, 1);
  }"""

tpl = TPL.read_text(encoding="utf-8")
tpl = tpl.replace('<html lang="en">', '<html lang="zh-CN">', 1)
tpl = tpl.replace("<title></title>", "<title>GBT小土豆V8 · 能力中枢 · 无限画布 V5</title>", 1)
s = tpl.index("  :root {")
e = tpl.index("\n  }", s) + len("\n  }")
tpl = tpl[:s] + TOKENS + tpl[e:]
tpl = tpl.replace("--grid-color: rgba(255,255,255,0.04);", "--grid-color: rgba(88,196,255,0.06);", 1)

strings = STRINGS.read_text(encoding="utf-8").rstrip("\n")
s = tpl.index("  const UI_STRINGS = {")
e = tpl.index("\n  };", s) + len("\n  };")
tpl = tpl[:s] + strings + tpl[e:]

scene = SCENE.read_text(encoding="utf-8").rstrip("\n")
s2 = tpl.index("  /* ===== demo scene ===== */")
s3 = tpl.index("\n})();", s2)
tpl = tpl[:s2] + scene + "\n\n  initScene();\n\n  const r = viewport.getBoundingClientRect();\n" \
      "  panX = r.width * 0.04;\n  panY = r.height * 0.04;\n  updateTransform();\n" + tpl[s3:]
OUT_CANVAS.write_text(tpl, encoding="utf-8")

payload = "/* real scan + brain probe snapshot */" + V5JSON.read_text(encoding="utf-8").strip()
body = OUT_PROTO.read_text(encoding="utf-8")
if BLOCK in body:
    OUT_PROTO.write_text(body.replace(BLOCK, payload, 1), encoding="utf-8")
    print("已注入真实读数（含大脑五维）→", OUT_PROTO.name)
else:
    print("!! 原型占位符缺失")

for p in (OUT_CANVAS, OUT_PROTO):
    t = p.read_text(encoding="utf-8")
    print("%-38s %7d B  行 %d" % (p.name, len(p.read_bytes()), t.count("\n") + 1))
