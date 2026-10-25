# -*- coding: utf-8 -*-
"""构建 V14 画布：补「框架核心层」10 页（43 → 53），保留品牌 Logo 接入。"""
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
SRC = BASE / "archive" / "V13 GBT小土豆V8-无限画布.html"
OUT = BASE / "V14 GBT小土豆V8-无限画布.html"
TPL = BASE / "infinite-canvas-output" / "assets" / "infinite-canvas-template.html"
assert SRC.exists(), "archive 里没有 V13 画布"

emb = json.loads((S / "logo_embed.json").read_text(encoding="utf-8"))
man = json.loads((S / "v14_manifest.json").read_text(encoding="utf-8"))
CORE, COV = man["core"], man["coverage"]

t = SRC.read_text(encoding="utf-8")
scene = t[t.index("  /* ===== scene ===== */"):t.index("\n  initScene();")]

PAGES = [
    (44, '源码覆盖审计', 'COVERAGE AUDIT', [
        ('自有代码总量', '{:,} 行 / {:,} 文件'.format(COV['total_lines'], COV['total_files']), 1),
        ('未进交付件', '{:,} 行（{:.1f}%）'.format(COV['uncovered_lines'],
                                           100 * COV['uncovered_lines'] / COV['total_lines']), 0),
        ('方法', '机器穷举：枚举全部自有代码 → 按目录聚合 → 查模块名是否出现', 1),
        ('判据边界', '「模块名是否出现」是弱判据 —— 真实缺口在此之下', 0),
        ('零覆盖目录', '{} 个整块没进过交付件'.format(len(COV['zero_coverage'])), 0),
        ('本版已补', '102 文件 / 31,000 行（9 组）', 1),
        ('仍未补的大块', '.openclaw/tmp（431 文件 / 22,888 行，多为另一钱包项目的临时文件）', 0),
        ('仍未补的大块', 'gbt_allinone/store（237 文件，多为镜像/时间线生成物）', 0)],
     'V12 那份「未进面板的 9 个板块」是我手挑的目录清单 —— 手挑必漏。'
     '这一版改成机器穷举，缺口立刻从 9 个变成几十个目录、13 万行。'
     '审计脚本自身也踩过两个坑（模块名短于 4 字符被过滤、把 data URI 当名字），已修正。'),
]

GROUP_META = [
    ('api', 45, '统一接口层', 'API CORE'),
    ('security', 46, '授权与安全策略', 'SECURITY POLICY'),
    ('base', 47, '框架底座', 'FRAMEWORK BASE'),
    ('omni', 48, 'omni 触手家族', 'OMNI TENTACLE'),
    ('deploy', 49, '部署层', 'DEPLOY LAYER'),
    ('bridge', 50, '对外桥接', 'BRIDGES'),
    ('skill', 51, '技能库', 'SKILL LIBRARY'),
    ('mirror', 52, '镜像与乾坤底座', 'MIRROR BASE'),
    ('vault', 53, '密钥保险箱', 'KEY VAULT'),
]
for gid, n, zh, en in GROUP_META:
    c = CORE[gid]
    rows = [(m['f'].split('/')[-1], '{:,} 行 · {}'.format(m['lines'], (m['doc'] or '')[:56]), 1)
            for m in c['files'][:11]]
    PAGES.append((n, zh, en, rows, c['what'] + '　【此前从未进面板】' + c['why']))

old = "      ['账本与审美脑', p43()],"
if old not in scene:
    old = "      ['账本与审美脑', p43()],"
assert old in scene, "screens 锚点未命中"
new = old + "\n" + "\n".join("      ['%s', p%d()]," % (zh, n) for n, zh, _, _, _ in PAGES)
scene = scene.replace(old, new, 1)
scene = scene.replace("四十一块面板 · 工作区源码层补齐 · 品牌 Logo 已接入",
                      "五十一块面板 · 框架核心层补齐 · 品牌 Logo 已接入")

# 署名
trimmed = scene.rstrip()
assert trimmed.endswith("}"), "scene 尾部不是收口花括号"
cut = trimmed.rfind("}")
scene = (trimmed[:cut] +
         "\n\n    /* 署名（不可删除、不可篡改归属） */\n"
         "    addNote(40, maxY() + 34, UI_STRINGS.signatureTag, UI_STRINGS.signature);\n"
         "  }" + scene[len(trimmed):])

HELPERS = r"""
  /* ── 框架核心层 · V14 共用小件 ── */
  function corePage_(title, en, rows, note) {
    return shell_(bar(title) +
      '<div style="flex:1;padding:10px;min-width:0;display:flex;flex-direction:column;gap:10px;">' +
      card(en + ' · ' + rows.length + ' 项 <span style="float:right;color:rgba(223,242,251,0.54);">V14 新补</span>',
        rows.map(function (r) {
          return '<div style="display:flex;align-items:flex-start;gap:8px;padding:4px 0;border-bottom:1px solid rgba(88,196,255,0.09);">' +
            '<span style="font-family:var(--font-mono);font-size:10px;color:' + (r[2] ? '#dff2fb' : 'rgba(245,181,68,0.9)') + ';width:150px;flex:none;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;">' + r[0] + '</span>' +
            '<span style="font-size:9.5px;color:rgba(223,242,251,0.66);flex:1;min-width:0;line-height:1.6;">' + r[1] + '</span></div>';
        }).join('')) +
      card('为什么这一层之前是空的 / WHY THIS LAYER WAS MISSING',
        '<div style="font-size:10px;color:rgba(223,242,251,0.74);line-height:1.9;">' + note + '</div>') +
      '</div>');
  }
"""
pagejs = "\n".join(
    "  function p%d() { return corePage_('%s', '%s', %s, '%s'); }" % (
        n, zh, en,
        "[" + ",".join("['%s','%s',%d]" % (a.replace("'", "\\'"), b.replace("'", "\\'"), c)
                       for a, b, c in rows) + "]",
        note.replace("'", "\\'"))
    for n, zh, en, rows, note in PAGES)

scene += "\n\n" + HELPERS + "\n" + pagejs + "\n"

brand_css = (".brandmark{background-image:url(\"" + emb["uri_canvas"] + "\");"
             "background-size:contain;background-repeat:no-repeat;background-position:center;"
             "filter:drop-shadow(0 0 6px rgba(42,212,240,.5));flex:none;display:block}")

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
_old_title = "<title></title>"
_new_title = ("<title>GBT小土豆V8 · 能力中枢 · 无限画布 V14</title>\n"
              "<link rel=\"icon\" type=\"image/png\" href=\"" + emb["uri_favicon"] + "\">")
assert _old_title in tpl, "模板 title 锚点未命中"
tpl = tpl.replace(_old_title, _new_title, 1)
s = tpl.index("  :root {")
e = tpl.index("\n  }", s) + len("\n  }")
tpl = tpl[:s] + TOKENS + tpl[e:]
tpl = tpl.replace("--grid-color: rgba(255,255,255,0.04);", "--grid-color: rgba(88,196,255,0.06);", 1)
tpl = tpl.replace("  .canvas-title {", "  " + brand_css + "\n\n  .canvas-title {", 1)
assert ".brandmark{" in tpl, "brandmark CSS 注入失败"
strings = (S / "canvas_strings_v5.js").read_text(encoding="utf-8").replace("V5", "V14")
strings = strings.replace(
    "  sections: { context: '01 项目背景', designSystem: '02 设计系统', deliverables: '03 设计稿' },",
    "  sections: { context: '01 项目背景', designSystem: '02 设计系统', deliverables: '03 设计稿' },\n"
    "  signatureTag: '开发者',\n"
    "  signature: '开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属 · V14 · 50 面板 / 53 画布页 · 框架核心层已补',")
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
print("页数: 53（原 43 + 框架核心 10）")
