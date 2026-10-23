# -*- coding: utf-8 -*-
"""构建 V13 画布：接入 App Logo。
- 每页标题栏的品牌徽标（原 20px 文字方块 GBT → Logo 图像）
- favicon
- 设计系统行新增「品牌 · App Logo」规范卡（尺寸档 / 净空 / 底色适配 / 禁止项）
"""
import json
import sys
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:  # noqa: BLE001
    pass

BASE = next(p for p in Path(__file__).resolve().parents
            if (p / "gbt_allinone").is_dir())   # 修：原 `.parent.parent` 只到 tools/（少一层）
S = BASE / ".scratch"
SRC = BASE / "archive" / "V12 GBT小土豆V8-无限画布.html"
OUT = BASE / "V13 GBT小土豆V8-无限画布.html"
TPL = BASE / "infinite-canvas-output" / "assets" / "infinite-canvas-template.html"
assert SRC.exists(), "archive 里没有 V12 画布"

emb = json.loads((S / "logo_embed.json").read_text(encoding="utf-8"))
t = SRC.read_text(encoding="utf-8")
scene = t[t.index("  /* ===== scene ===== */"):t.index("\n  initScene();")]

# ── 1. 品牌资源：走 CSS 类，data URI 在文件里只存一份 ──
#    （早先把 src=BRAND.logo 写进每页字符串，43 页会在 DOM 里重复 43 份 × 75 KB）
brand_css = (".brandmark{background-image:url(\"" + emb["uri_canvas"] + "\");"
             "background-size:contain;background-repeat:no-repeat;background-position:center;"
             "filter:drop-shadow(0 0 6px rgba(42,212,240,.5));flex:none;display:block}")

# ── 3. 每页标题栏的品牌徽标：文字方块 → Logo ──
old_badge = ("'<span style=\"width:20px;height:20px;border-radius:6px;background:linear-gradient(160deg,#123049,#0a1e30);"
             "border:1px solid rgba(88,196,255,0.34);display:grid;place-items:center;font-family:ui-monospace,monospace;"
             "font-size:7.5px;color:#6ef2ff;\">GBT</span>' +")
new_badge = ("'<span class=\"brandmark\" aria-hidden=\"true\" style=\"width:22px;height:22px;\"></span>' +")
assert old_badge in scene, "画布徽标锚点未命中"
scene = scene.replace(old_badge, new_badge, 1)

# ── 4. 设计系统行新增品牌规范卡 ──
old_row = ("    const r3Start = maxY([colorCard, typeCard, compCard], 90);\n"
           "    addSection(r3Start, UI_STRINGS.sections.deliverables);")
new_row = """    /* ── 品牌 · App Logo（主人 2026-07-14 提供）── */
    const brandY = maxY([colorCard, typeCard, compCard], 24);
    const lg = function (n, label) {
      return '<div style="display:flex;flex-direction:column;align-items:center;gap:6px;">' +
        '<div style="width:' + (n + 16) + 'px;height:' + (n + 16) + 'px;border-radius:10px;background:#04070f;' +
        'border:1px solid rgba(88,196,255,0.14);display:grid;place-items:center;">' +
        '<span class="brandmark" aria-hidden="true" style="width:' + n + 'px;height:' + n + 'px;"></span></div>' +
        '<span style="font-family:var(--font-mono);font-size:9px;color:rgba(223,242,251,0.54);">' + label + '</span></div>';
    };
    const swL = function (hex, name, note) {
      return '<div style="display:flex;align-items:center;gap:9px;">' +
        '<span style="width:26px;height:26px;border-radius:6px;background:' + hex + ';flex:none;' +
        'border:1px solid rgba(255,255,255,0.14);"></span>' +
        '<div style="min-width:0;"><div style="font-size:10.5px;color:#dff2fb;">' + name + '</div>' +
        '<div style="font-family:var(--font-mono);font-size:9px;color:rgba(223,242,251,0.54);">' + hex + ' · ' + note + '</div></div></div>';
    };
    const brandCard = addDesignSystemCard(100, brandY, 1250, null, 'brand', {
      title: '品牌 · App Logo（主人提供）',
      html: '<div style="display:flex;gap:22px;align-items:flex-start;flex-wrap:wrap;">' +
        '<div style="display:flex;gap:14px;align-items:flex-end;">' +
          lg(96, '96 · 画布展示') + lg(48, '48') + lg(34, '34 · 侧栏') + lg(22, '22 · 页眉') + lg(16, '16 · 最小') +
        '</div>' +
        '<div style="display:flex;flex-direction:column;gap:9px;min-width:190px;">' +
          swL('#75d5db', 'Logo 青（均值）', '取自护目镜与电路发光，占不透明像素 7.4%') +
          swL('#bffdfb', 'Logo 高光青', '发光峰值') +
          swL('#b98950', '土豆皮', '主体色，占不透明像素约 51%') +
          swL('#2ad4f0', 'UI 强调色 --accent', '保持不动：与 Logo 青同族但更沉，并列不冲突') +
        '</div>' +
        '<div style="flex:1;min-width:250px;display:flex;flex-direction:column;gap:8px;">' +
          '<div style="font-size:10.5px;color:#dff2fb;">处理</div>' +
          '<div style="font-size:10px;color:rgba(223,242,251,0.74);line-height:1.85;">' +
          '源图 640×640 JPEG（47,465 B）→ 连通域抠白：候选背景 =（近白）或（低饱和高亮），' +
          '只保留与四边连通的连通域 ⇒ 去掉白底与灰色投影，土豆本体不受影响，边缘 3px 羽化。<br>' +
          '第一版用 cv2.floodFill 漏加 FIXED_RANGE，容差按邻居递推把本体啃掉了（只剩暗部），已弃用。</div>' +
          '<div style="font-size:10.5px;color:#dff2fb;margin-top:4px;">净空与禁止</div>' +
          '<div style="font-size:10px;color:rgba(223,242,251,0.74);line-height:1.85;">' +
          '净空 ≥ 徽标短边 25%；最小 16px（再小护目镜细节糊成一团，改用图标版）。<br>' +
          '禁止：拉伸变形 · 加描边或投影以外的效果 · 换底色 · 与其它图形重叠 · 旋转。</div>' +
        '</div></div>'
    });

""" + old_row
assert old_row in scene, "设计系统行锚点未命中"
scene = scene.replace(old_row, new_row, 1)
scene = scene.replace("const r3Start = maxY([colorCard, typeCard, compCard], 90);",
                      "const r3Start = maxY([colorCard, typeCard, compCard, brandCard], 90);", 1)

# ── 5. 署名 ──
trimmed = scene.rstrip()
assert trimmed.endswith("}"), "scene 尾部不是收口花括号"
cut = trimmed.rfind("}")
scene = (trimmed[:cut] +
         "\n\n    /* 署名（不可删除、不可篡改归属） */\n"
         "    addNote(40, maxY() + 34, UI_STRINGS.signatureTag, UI_STRINGS.signature);\n"
         "  }" + scene[len(trimmed):])

# ── 6. 计数文案 ──
scene = scene.replace("四十一块面板 · 工作区源码层补齐", "四十一块面板 · 工作区源码层补齐 · 品牌 Logo 已接入")
scene = scene.replace("'四十一块面板'", "'四十一块面板'")

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
# title + favicon
_old_title = "<title></title>"
_new_title = ("<title>GBT小土豆V8 · 能力中枢 · 无限画布 V13</title>\n"
              "<link rel=\"icon\" type=\"image/png\" href=\"" + emb["uri_favicon"] + "\">")
assert _old_title in tpl, "模板 title 锚点未命中"
tpl = tpl.replace(_old_title, _new_title, 1)
# 品牌常量：放在 UI_STRINGS 之后、viewport 之前
_vp = "  const viewport = document.getElementById('viewport');"
assert _vp in tpl, "模板 viewport 锚点未命中"
print("画布：brandmark CSS %d B + favicon %d B 已写入模板" % (len(brand_css), len(emb["uri_favicon"])))
s = tpl.index("  :root {")
e = tpl.index("\n  }", s) + len("\n  }")
tpl = tpl[:s] + TOKENS + tpl[e:]
tpl = tpl.replace("--grid-color: rgba(255,255,255,0.04);", "--grid-color: rgba(88,196,255,0.06);", 1)
# 品牌 Logo 走 CSS 类：data URI 在文件里只存一份，页面上只放空 span
tpl = tpl.replace("  .canvas-title {", "  " + brand_css + "\n\n  .canvas-title {", 1)
assert ".brandmark{" in tpl, "brandmark CSS 注入失败"
strings = (S / "canvas_strings_v5.js").read_text(encoding="utf-8").replace("V5", "V13")
strings = strings.replace(
    "  sections: { context: '01 项目背景', designSystem: '02 设计系统', deliverables: '03 设计稿' },",
    "  sections: { context: '01 项目背景', designSystem: '02 设计系统', deliverables: '03 设计稿' },\n"
    "  signatureTag: '开发者',\n"
    "  signature: '开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属 · V13 · 40 面板 / 43 画布页 · 品牌 Logo 已接入',")
assert "signatureTag" in strings, "署名串注入失败"
s = tpl.index("  const UI_STRINGS = {")
e = tpl.index("\n  };", s) + len("\n  };")
tpl = tpl[:s] + strings.rstrip("\n") + tpl[e:]
s2 = tpl.index("  /* ===== demo scene ===== */")
s3 = tpl.index("\n})();", s2)
tpl = tpl[:s2] + scene.rstrip("\n") + "\n\n  initScene();\n\n  const r = viewport.getBoundingClientRect();\n" \
      "  panX = r.width * 0.04;\n  panY = r.height * 0.04;\n  updateTransform();\n" + tpl[s3:]
OUT.write_text(tpl, encoding="utf-8")
print("写出:", OUT.name, "%.1f KB" % (OUT.stat().st_size / 1024))
print("品牌规范卡已加入设计系统行；43 页标题栏徽标全部换成 Logo")
