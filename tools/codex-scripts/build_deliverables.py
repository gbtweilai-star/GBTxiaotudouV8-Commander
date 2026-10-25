# -*- coding: utf-8 -*-
"""构建两件交付物：
1) 用 infinite-canvas 模板 + 本项目的 scene，生成 V2 无限画布
2) 把真实能力清单（caps_manifest.json）注入两个 HTML
不覆盖旧版：V1 已在 archive/。
"""
from pathlib import Path

BASE = next(p for p in Path(__file__).resolve().parents
            if (p / "gbt_allinone").is_dir())   # 修：原 `.parent.parent` 只到 tools/（少一层）
TPL = BASE / "infinite-canvas-output" / "assets" / "infinite-canvas-template.html"
STRINGS = BASE / ".scratch" / "canvas_strings.js"
SCENE = BASE / ".scratch" / "canvas_scene.js"
MANIFEST = BASE / ".scratch" / "caps_manifest.json"

CANVAS_OUT = BASE / "V2 GBT小土豆V8-无限画布.html"
PROTO_OUT = BASE / "V2 GBT小土豆V8-可交互原型.html"

BLOCK = "/*__MANIFEST__*/null"

tpl = TPL.read_text(encoding="utf-8")
strings = STRINGS.read_text(encoding="utf-8").rstrip("\n")
scene = SCENE.read_text(encoding="utf-8").rstrip("\n")

# 1) 语言与标题
tpl = tpl.replace('<html lang="en">', '<html lang="zh-CN">', 1)
tpl = tpl.replace("<title></title>",
                  "<title>GBT小土豆V8 · 能力中枢 · 无限画布 V2</title>", 1)

# 1b) 对比度校正：三级/二级文字提到 WCAG 2.2 AA 之上（原 0.32 只有 ~3.4:1）
tpl = tpl.replace("--text-secondary: rgba(232,230,227,0.6);",
                  "--text-secondary: rgba(232,230,227,0.72);", 1)
tpl = tpl.replace("--text-tertiary: rgba(232,230,227,0.32);",
                  "--text-tertiary: rgba(232,230,227,0.52);", 1)

# 2) UI_STRINGS 整体替换
start = tpl.index("  const UI_STRINGS = {")
end = tpl.index("\n  };", start) + len("\n  };")
tpl = tpl[:start] + strings + tpl[end:]

# 3) demo scene → 本项目 scene
marker = "  /* ===== demo scene ===== */"
tail_marker = "\n})();"
s2 = tpl.index(marker)
s3 = tpl.index(tail_marker, s2)
boot = """
  initScene();

  const r = viewport.getBoundingClientRect();
  panX = r.width * 0.04;
  panY = r.height * 0.04;
  updateTransform();
"""
tpl = tpl[:s2] + scene + "\n" + boot + tpl[s3:]

CANVAS_OUT.write_text(tpl, encoding="utf-8")

# 4) 注入真实能力清单
manifest = MANIFEST.read_text(encoding="utf-8").strip()
payload = "/* real registry snapshot */" + manifest

for path in (CANVAS_OUT, PROTO_OUT):
    body = path.read_text(encoding="utf-8")
    if BLOCK not in body:
        print("!! 占位符缺失:", path.name)
        continue
    path.write_text(body.replace(BLOCK, payload, 1), encoding="utf-8")

for path in (CANVAS_OUT, PROTO_OUT):
    txt = path.read_text(encoding="utf-8")
    print("%-40s %8d B  行数 %d  含清单 %s"
          % (path.name, len(txt.encode("utf-8")), txt.count("\n") + 1,
             ("\"caps\"" in txt)))
