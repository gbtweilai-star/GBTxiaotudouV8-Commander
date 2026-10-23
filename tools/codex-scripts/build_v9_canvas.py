# -*- coding: utf-8 -*-
"""构建 V9 画布：从 V8 画布抽 scene，补「插件市场」一页后重装。"""
import shutil
from pathlib import Path

BASE = next(p for p in Path(__file__).resolve().parents
            if (p / "gbt_allinone").is_dir())   # 修：原 `.parent.parent` 只到 tools/（少一层）
S = BASE / ".scratch"
V8C = BASE / "V8 GBT小土豆V8-无限画布.html"
OUT = BASE / "V9 GBT小土豆V8-无限画布.html"
TPL = BASE / "infinite-canvas-output" / "assets" / "infinite-canvas-template.html"

shutil.copy2(V8C, BASE / "archive" / V8C.name)
t8 = V8C.read_text(encoding="utf-8")
scene = t8[t8.index("  /* ===== scene ===== */"):t8.index("\n  initScene();")]

old = "      ['其余域 · 一次盘完', p21()],"
new = old + "\n      ['插件市场 · 蒸馏件', p22()],"
assert old in scene, "screens 锚点未命中"
scene = scene.replace(old, new, 1)

old_nav = "                 '镜像与晋升','大模型通道','心智与记忆','情报与观察','安全攻防','长程与工具','创作与吞噬','其余域','系统体检','设置'];"
new_nav = "                 '镜像与晋升','大模型通道','心智与记忆','情报与观察','安全攻防','长程与工具','创作与吞噬','其余域','插件市场','系统体检','设置'];"
assert old_nav in scene, "nav 锚点未命中"
scene = scene.replace(old_nav, new_nav, 1)

scene = scene.replace("十九块真面板 · 30 域全覆盖", "二十块真面板 · 30 域 + 插件市场蒸馏件")
scene = scene.replace("'十九块真面板'", "'二十块真面板'")

scene += """

  function p22() {
    var C = [['dshmarket',88,'#3ddc97','可装','社区精选推荐 · 依赖仅 2 · 仓库同源'],
             ['@w2112515/dsh-plugin-marketplace',75,'#f5b544','需复核','不在精选列表'],
             ['dsh-market-plus',55,'#ff7a7a','不建议','仓库属主与包名/维护者均不符'],
             ['aiko-dsh-market',39,'#ff7a7a','不建议','无仓库 + 描述逐字克隆']];
    return shell_(bar('插件市场') +
      '<div style="flex:1;display:flex;min-height:0;">' + nav7('插件市场') +
      '<div style="flex:1;padding:10px;min-width:0;">' +
      card('本机插件全景 / LOCAL <span style="float:right;">只读扫描</span>',
        '<div style="display:grid;grid-template-columns:repeat(3,1fr);gap:11px;">' +
        '<div><div style="font-family:ui-monospace,monospace;font-size:22px;color:#6ef2ff;">484</div><div style="font-size:9px;color:rgba(223,242,251,0.54);">包总数</div></div>' +
        '<div><div style="font-family:ui-monospace,monospace;font-size:22px;color:#6ef2ff;">65</div><div style="font-size:9px;color:rgba(223,242,251,0.54);">带 dsh 清单</div></div>' +
        '<div><div style="font-family:ui-monospace,monospace;font-size:22px;color:#6ef2ff;">240</div><div style="font-size:9px;color:rgba(223,242,251,0.54);">官方 scope</div></div></div>' +
        '<div style="margin-top:10px;">' + st_('#3ddc97','清单类型','client 55 / bundle 6 / migration 3 / configTrees 1') +
        st_('#3ddc97','profile 声明','web → dsh-base + dsh-web-app') + '</div>') +
      card('候选包五维审查 / VETTING REPORT',
        C.map(function (c) {
          return '<div style="display:grid;grid-template-columns:1fr 44px 66px;gap:8px;align-items:center;padding:6px 0;border-bottom:1px dashed rgba(88,196,255,0.14);">' +
            '<span><span style="font-family:ui-monospace,monospace;font-size:10px;color:#dff2fb;">' + c[0] + '</span>' +
            '<span style="display:block;font-size:9px;color:rgba(223,242,251,0.54);margin-top:2px;">' + c[4] + '</span></span>' +
            '<span style="font-family:ui-monospace,monospace;font-size:15px;color:' + c[2] + ';text-align:right;">' + c[1] + '</span>' +
            '<span style="font-size:9px;color:' + c[2] + ';text-align:right;">' + c[3] + '</span></div>';
        }).join('') +
        '<div style="font-size:9px;color:rgba(223,242,251,0.54);margin-top:7px;">维度：来源可信 / 依赖面 / 脚本面 / 仓库一致性 / 仿冒风险</div>') +
      card('安装门 / GATE <span style="float:right;">绝不裸装</span>',
        st_('#f5b544','前置授权','deploy_publish（主人终端发放）') +
        st_('#3ddc97','审计留痕','store.audit 追加一条') +
        st_('#3ddc97','本原型','不执行安装') +
        '<div style="font-family:ui-monospace,monospace;font-size:9px;color:rgba(223,242,251,0.54);margin-top:6px;background:#04070f;border:1px solid rgba(88,196,255,0.14);border-radius:5px;padding:7px;word-break:break-all;">dsh plugin --profile web add &lt;pkg&gt;</div>') +
      card('仿冒警示 / WARNING',
        '<div style="display:flex;gap:8px;font-size:9.5px;color:rgba(223,242,251,0.74);line-height:1.8;">' +
        '<span style="color:#f5b544;">!</span><span>npm 上 <b style="color:#dff2fb">dsh-market</b> 这个包名 404，真名是 <b style="color:#dff2fb">dshmarket</b>。' +
        '搜错一个连字符就可能装到 39 分的克隆包。规矩：装前先出报告，报告不过不进环境。</span></div>') +
      '</div></div>');
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
tpl = tpl.replace("<title></title>", "<title>GBT小土豆V8 · 能力中枢 · 无限画布 V9</title>", 1)
s = tpl.index("  :root {")
e = tpl.index("\n  }", s) + len("\n  }")
tpl = tpl[:s] + TOKENS + tpl[e:]
tpl = tpl.replace("--grid-color: rgba(255,255,255,0.04);", "--grid-color: rgba(88,196,255,0.06);", 1)
strings = (S / "canvas_strings_v5.js").read_text(encoding="utf-8").replace("V5", "V9")
s = tpl.index("  const UI_STRINGS = {")
e = tpl.index("\n  };", s) + len("\n  };")
tpl = tpl[:s] + strings.rstrip("\n") + tpl[e:]
s2 = tpl.index("  /* ===== demo scene ===== */")
s3 = tpl.index("\n})();", s2)
tpl = tpl[:s2] + scene.rstrip("\n") + "\n\n  initScene();\n\n  const r = viewport.getBoundingClientRect();\n" \
      "  panX = r.width * 0.04;\n  panY = r.height * 0.04;\n  updateTransform();\n" + tpl[s3:]
OUT.write_text(tpl, encoding="utf-8")
print("写出:", OUT.name, len(OUT.read_bytes()), "B")
