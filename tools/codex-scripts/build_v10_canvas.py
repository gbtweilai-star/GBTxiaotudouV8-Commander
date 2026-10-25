# -*- coding: utf-8 -*-
"""构建 V10 画布：补「上帝视角 · 项目树」一页。"""
import shutil
from pathlib import Path

BASE = next(p for p in Path(__file__).resolve().parents
            if (p / "gbt_allinone").is_dir())   # 修：原 `.parent.parent` 只到 tools/（少一层）
S = BASE / ".scratch"
V9C = BASE / "V9 GBT小土豆V8-无限画布.html"
OUT = BASE / "V10 GBT小土豆V8-无限画布.html"
TPL = BASE / "infinite-canvas-output" / "assets" / "infinite-canvas-template.html"

shutil.copy2(V9C, BASE / "archive" / V9C.name)
t9 = V9C.read_text(encoding="utf-8")
scene = t9[t9.index("  /* ===== scene ===== */"):t9.index("\n  initScene();")]

old = "      ['插件市场 · 蒸馏件', p22()],"
new = old + "\n      ['上帝视角 · 项目树', p23()],"
assert old in scene, "screens 锚点未命中"
scene = scene.replace(old, new, 1)
scene = scene.replace("二十块真面板 · 30 域 + 插件市场蒸馏件", "二十一块面板 · 项目树进了上帝视角")
scene = scene.replace("'二十块真面板'", "'二十一块面板'")

scene += """

  function p23() {
    var ROWS = [
      [0,'directory','.agents','1 项'], [0,'directory','.git','12 项'],
      [0,'directory','.scratch','4435 项'], [0,'directory','archive','16 项'],
      [1,'directory','V10 GBT小土豆V8-可交互原型.html','—'],
      [0,'directory','gbt_allinone','90 项'], [0,'directory','memory','5 项'],
      [0,'file','AGENTS.md','25288 B'], [0,'file','CHARTER.md','57251 B'],
      [0,'file','SOUL.md','4112 B'], [0,'file','USER.md','1336 B']
    ];
    var ico = { directory: '#2ad4f0', file: 'rgba(223,242,251,0.54)', other: 'rgba(223,242,251,0.3)' };
    return shell_(bar('上帝视角 · 项目树') +
      '<div style="flex:1;padding:10px;min-width:0;">' +
      card('项目树 / PROJECT TREE <span style="float:right;">@deepseek-ai/dsh-api-workspace-files</span>',
        '<div style="display:flex;align-items:center;gap:8px;padding:6px 8px;border-bottom:1px solid rgba(88,196,255,0.14);margin-bottom:6px;">' +
        '<span style="font-family:ui-monospace,monospace;font-size:10.5px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;flex:1;">' +
        '<span style="color:rgba(223,242,251,0.54);">C:\\\\Users\\\\ADMIN\\\\Desktop\\\\</span><span style="color:#dff2fb;">GBT小土豆V8</span></span>' +
        '<span style="font-family:ui-monospace,monospace;font-size:9px;color:rgba(223,242,251,0.54);">70 项 · 目录 49 / 文件 44</span>' +
        '<span style="height:22px;padding:0 9px;border:1px solid rgba(88,196,255,0.14);border-radius:100px;display:grid;place-items:center;font-size:10px;color:rgba(223,242,251,0.74);">重新读取</span></div>' +
        ROWS.map(function (r) {
          var pad = 8 + r[0] * 15;
          return '<div style="display:flex;align-items:center;gap:7px;padding:3px 8px 3px ' + pad + 'px;">' +
            '<i style="width:7px;height:7px;border-radius:2px;background:' + ico[r[1]] + ';flex:none;"></i>' +
            '<span style="font-family:ui-monospace,monospace;font-size:10px;color:' + (r[1] === 'other' ? 'rgba(223,242,251,0.3)' : '#dff2fb') + ';flex:1;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;">' + r[2] + '</span>' +
            '<span style="font-family:ui-monospace,monospace;font-size:9px;color:rgba(223,242,251,0.54);">' + r[3] + '</span></div>';
        }).join('') +
        '<div style="padding:4px 8px;font-family:ui-monospace,monospace;font-size:9px;color:#f5b544;">根层已达上限 40（该目录共 70 项），其余已丢弃并标记 truncated</div>' +
        '<div style="font-size:9.5px;color:rgba(223,242,251,0.54);margin-top:9px;line-height:1.8;">' +
        '规格要点：目录优先 → 名称自然序不分大小写 · dotfiles 与其他条目一样显示 · other 行灰显不可点<br>' +
        '已知限制：只有列目录 —— 无搜索 / 过滤 / 拖拽 / 重命名 / 右键 / 文件监听；<b style="color:#dff2fb;">只有一个根</b>，不能浏览到工作区根之上</div>') +
      card('为什么它得进上帝视角 / WHY HERE',
        '<div style="font-size:10px;color:rgba(223,242,251,0.74);line-height:1.9;">' +
        '上帝视角原本只有能力侧读数（140 能力 / 30 域 / 六维 / 故障），<b style="color:#dff2fb;">看不见代码在哪</b>。' +
        '项目树补上另一半：能力是「能做什么」，项目树是「在哪做」。<br>' +
        '核对过：上一版上帝视角里 <span style="font-family:ui-monospace,monospace;color:#ff7a7a;">workspaceFiles / 项目树 / entries 出现 0 次</span> —— 确实缺，现在补上。</div>') +
      '</div>');
  }
"""

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
tpl = tpl.replace("<title></title>", "<title>GBT小土豆V8 · 能力中枢 · 无限画布 V10</title>", 1)
s = tpl.index("  :root {")
e = tpl.index("\n  }", s) + len("\n  }")
tpl = tpl[:s] + TOKENS + tpl[e:]
tpl = tpl.replace("--grid-color: rgba(255,255,255,0.04);", "--grid-color: rgba(88,196,255,0.06);", 1)
strings = (S / "canvas_strings_v5.js").read_text(encoding="utf-8").replace("V5", "V10")
s = tpl.index("  const UI_STRINGS = {")
e = tpl.index("\n  };", s) + len("\n  };")
tpl = tpl[:s] + strings.rstrip("\n") + tpl[e:]
s2 = tpl.index("  /* ===== demo scene ===== */")
s3 = tpl.index("\n})();", s2)
tpl = tpl[:s2] + scene.rstrip("\n") + "\n\n  initScene();\n\n  const r = viewport.getBoundingClientRect();\n" \
      "  panX = r.width * 0.04;\n  panY = r.height * 0.04;\n  updateTransform();\n" + tpl[s3:]
OUT.write_text(tpl, encoding="utf-8")
print("写出:", OUT.name, len(OUT.read_bytes()), "B")
