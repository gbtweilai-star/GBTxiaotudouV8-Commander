# -*- coding: utf-8 -*-
"""构建 V7 画布：从 V6 画布里抽出 scene，加「万能插」「亿万触手」两页后重装。"""
import shutil
from pathlib import Path

BASE = next(p for p in Path(__file__).resolve().parents
            if (p / "gbt_allinone").is_dir())   # 修：原 `.parent.parent` 只到 tools/（少一层）
S = BASE / ".scratch"
V6C = BASE / "V6 GBT小土豆V8-无限画布.html"
OUT = BASE / "V7 GBT小土豆V8-无限画布.html"
TPL = BASE / "infinite-canvas-output" / "assets" / "infinite-canvas-template.html"

shutil.copy2(V6C, BASE / "archive" / V6C.name)

t6 = V6C.read_text(encoding="utf-8")
scene = t6[t6.index("  /* ===== scene ===== */"):t6.index("\n  initScene();")]

# 1) 页面清单加两页
old = "      ['蓝牙 · 扫描与控制', p11()],"
new = old + "\n      ['万能插 · 工作流与算子', p12()],\n      ['亿万触手 · 三通道与十域', p13()],"
assert old in scene, "screens 锚点未命中"
scene = scene.replace(old, new, 1)

# 2) 侧栏扩到十一块
old_nav = "    var items = ['对话','能力广场','大脑执行层','领域分类','审计台账','语音','蓝牙','系统体检','设置'];"
new_nav = "    var items = ['对话','能力广场','大脑执行层','领域分类','审计台账','语音','蓝牙','万能插','亿万触手','系统体检','设置'];"
assert old_nav in scene, "nav 锚点未命中"
scene = scene.replace(old_nav, new_nav, 1)

# 3) Row1 文案
scene = scene.replace("九块真面板 · 大脑执行层 + 语音 + 蓝牙", "十一块真面板 · 神经中枢全开")
scene = scene.replace("'九块真面板'", "'十一块真面板'")
scene = scene.replace("换成九块全部接真数的面板（新增语音 / 蓝牙）", "换成十一块全部接真数的面板（新增语音 / 蓝牙 / 万能插 / 亿万触手）")

# 4) 追加两页
scene += """

  function p12() {
    var WFS = [['ai-orchestration',3],['autopilot-r1',3],['autopilot-r2',3],['autopilot-r3',3],
               ['bo-probe',1],['bo-probe2',1],['gbt_polish_v1',19],['honesty-test',3],['self-polish',4]];
    var SP = [['scan','selfscan',0],['guard','ghost_guard',0],['svc','svc_inspect',0],['publish','pipeline_submit',1]];
    var o = [];
    SP.forEach(function (n, i) {
      var x = 30 + i * 82, y = 22;
      o.push('<rect x="' + x + '" y="' + y + '" width="72" height="30" rx="5" fill="#0c1a2e" stroke="rgba(88,196,255,0.34)"/>');
      o.push('<text x="' + (x + 7) + '" y="' + (y + 13) + '" fill="#dff2fb" font-family="ui-monospace,monospace" font-size="8.5">' + n[0] + '</text>');
      o.push('<text x="' + (x + 7) + '" y="' + (y + 24) + '" fill="rgba(223,242,251,0.54)" font-family="ui-monospace,monospace" font-size="7.5">' + n[1] + '</text>');
    });
    for (var i = 0; i < 3; i++) {
      var x1 = 30 + i * 82 + 36, x2 = 30 + 3 * 82 + 36;
      o.push('<path d="M' + x1 + ' 52 C' + x1 + ' 70,' + x2 + ' 70,' + x2 + ' 84" fill="none" stroke="rgba(88,196,255,0.34)" stroke-width="1.2" stroke-dasharray="4 5"/>');
    }
    o.push('<rect x="' + (30 + 3 * 82) + '" y="84" width="72" height="30" rx="5" fill="#0c1a2e" stroke="#2ad4f0"/>');
    o.push('<text x="' + (30 + 3 * 82 + 7) + '" y="97" fill="#dff2fb" font-family="ui-monospace,monospace" font-size="8.5">publish</text>');
    o.push('<text x="' + (30 + 3 * 82 + 7) + '" y="108" fill="rgba(223,242,251,0.54)" font-family="ui-monospace,monospace" font-size="7.5">pipeline_submit</text>');
    return shell_(bar('万能插') +
      '<div style="flex:1;display:flex;min-height:0;">' + nav7('万能插') +
      '<div style="flex:1;padding:10px;min-width:0;overflow:hidden;">' +
      card('工作流定义 / WORKFLOWS <span style="float:right;">9 个 · 真读数</span>',
        '<div style="display:grid;grid-template-columns:1fr 1fr;gap:5px;">' +
        WFS.map(function (w, i) {
          var on = w[0] === 'self-polish';
          return '<div style="display:flex;gap:6px;align-items:baseline;padding:4px 7px;border:1px solid ' + (on ? '#2ad4f0' : 'rgba(88,196,255,0.14)') + ';border-radius:4px;background:' + (on ? 'rgba(42,212,240,0.08)' : 'transparent') + ';">' +
            '<span style="font-family:ui-monospace,monospace;font-size:9.5px;color:#dff2fb;flex:1;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;">' + w[0] + '</span>' +
            '<span style="font-family:ui-monospace,monospace;font-size:9px;color:rgba(223,242,251,0.54);">' + w[1] + ' 节点</span></div>';
        }).join('') + '</div>') +
      card('依赖图 / DAG <span style="float:right;">self-polish · 4 节点 · 分层并行</span>',
        '<svg viewBox="0 0 380 128" style="width:100%;display:block;">' + o.join('') + '</svg>' +
        '<div style="font-size:9px;color:rgba(223,242,251,0.54);margin-top:5px;">层 = 依赖深度；同层并行；节点下方等宽字为真实 kind。</div>') +
      card('传输算子 14 个 + 真输出',
        '<div style="display:flex;flex-wrap:wrap;gap:5px;">' +
        ['collect','map','pluck','filter','merge','unique','sort','limit','flatten','split','join','rename','wrap','stats'].map(function (t) {
          return '<span style="display:inline-flex;align-items:center;gap:5px;height:22px;padding:0 8px;border:1px solid rgba(88,196,255,0.14);border-radius:100px;font-family:ui-monospace,monospace;font-size:9px;color:rgba(223,242,251,0.74);"><i style="width:5px;height:5px;border-radius:50%;background:#3ddc97;"></i>' + t + '</span>';
        }).join('') + '</div>' +
        '<div style="font-family:ui-monospace,monospace;font-size:9.5px;color:rgba(223,242,251,0.74);background:#04070f;border:1px solid rgba(88,196,255,0.14);border-radius:5px;padding:7px;margin-top:8px;">' +
        'unique [3,1,3,2,1] → [3,1,2]<br>stats&nbsp; [1,2,3,4,5] → len 5 · int</div>') +
      '</div></div>');
  }

  function p13() {
    var DOMS = [['感知域',12],['桌面域',23],['侦察域',12],['记忆域',8],['门禁域',7],['协作域',6],
                ['审计域',9],['表达域',5],['听觉域',4],['位置域',3]];
    var SEC = [['视觉',9],['读屏',6],['点击',6],['键盘',10],['滚动',4],['追溯',3],['剪贴板',4],
               ['弹窗',3],['进程',4],['等待',5],['链式',2],['自诊断',2],['任务指引',6],['位置',2]];
    var GAP = [['手（执行触手）','只会说不会做',4,9],['脑（记忆触手）','没有记忆',3,6],
               ['眼（视觉触手）','看不见自己',0,5],['耳（听觉触手）','单模态（听）',1,2],
               ['口（表达触手）','单模态（说）',4,4],['门（门禁触手）','没有边界',3,4],
               ['网（协作触手）','不会协作',2,3],['镜（审计触手）','不会验证',4,6]];
    return shell_(bar('亿万触手') +
      '<div style="flex:1;display:flex;min-height:0;">' + nav7('亿万触手') +
      '<div style="flex:1;padding:10px;min-width:0;overflow:hidden;">' +
      card('三通道感官 / CHANNELS',
        '<div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:7px;">' +
        [['视觉','DXGI 直读帧缓冲 · 与显示屏同源'],['听觉','WASAPI 回环 · 与扬声器同源'],['操作','cyborg 五维穿透 · UIA 直操作']].map(function (c, i) {
          var on = i === 2;
          return '<div style="border:1px solid ' + (on ? '#2ad4f0' : 'rgba(88,196,255,0.34)') + ';border-radius:6px;background:#0c1a2e;padding:7px 8px;">' +
            '<div style="font-size:10.5px;color:#dff2fb;">' + c[0] + '</div>' +
            '<div style="font-size:8.5px;color:rgba(223,242,251,0.54);margin-top:4px;line-height:1.6;">' + c[1] + '</div></div>';
        }).join('') + '</div>') +
      card('自诊断 + 意图覆盖 <span style="float:right;">眼睛正常 · 89/89 · 100%</span>',
        '<div style="display:grid;grid-template-columns:1fr 1fr;gap:9px;">' +
        '<div>' + st_('#3ddc97','眼睛','正常') + st_('#3ddc97','ctypes','键鼠/窗口') +
        st_('#3ddc97','mss','截图兜底') + st_('#3ddc97','uiautomation','读屏/UIA') + st_('#3ddc97','dxcam','DXGI 硬采') + '</div>' +
        '<div><div style="font-family:ui-monospace,monospace;font-size:20px;color:#6ef2ff;">100<span style="font-size:10px;color:rgba(223,242,251,0.54);">%</span></div>' +
        '<div style="font-size:9px;color:rgba(223,242,251,0.54);margin-top:4px;line-height:1.7;">已覆盖 89/89<br>未覆盖 0 · 幽灵 0<br>总纲 66 方法 · 邻域 10</div></div></div>') +
      card('十域触手分布 / DOMAINS',
        '<div style="display:flex;flex-wrap:wrap;gap:5px;">' + DOMS.map(function (d) {
          return '<span style="display:inline-flex;align-items:center;gap:5px;height:22px;padding:0 8px;border:1px solid rgba(88,196,255,0.14);border-radius:100px;font-family:ui-monospace,monospace;font-size:9px;color:rgba(223,242,251,0.74);"><i style="width:5px;height:5px;border-radius:50%;background:#3ddc97;"></i>' + d[0] + ' ' + d[1] + '</span>';
        }).join('') + '</div>') +
      card('能力分段 14 段 66 项 / SECTIONS',
        '<div style="display:grid;grid-template-columns:1fr 1fr;gap:4px 12px;">' + SEC.map(function (s) {
          return '<div style="display:flex;align-items:center;gap:7px;font-size:10px;color:rgba(223,242,251,0.74);"><span style="width:48px;font-family:ui-monospace,monospace;font-size:9.5px;color:#dff2fb;">' + s[0] + '</span>' +
            '<span style="flex:1;height:3px;border-radius:2px;background:#102339;overflow:hidden;"><i style="display:block;height:100%;width:' + (s[1] * 10) + '%;background:#2ad4f0;"></i></span>' +
            '<span style="font-family:ui-monospace,monospace;font-size:9px;color:rgba(223,242,251,0.54);">' + s[1] + '</span></div>';
        }).join('') + '</div>') +
      card('覆盖审计 · 八短板 / AUDIT <span style="float:right;">8/8 已有</span>',
        GAP.map(function (g) {
          var pct = Math.round(100 * g[2] / g[3]);
          var col = pct >= 80 ? '#2ad4f0' : (pct >= 40 ? '#f5b544' : '#ff7a7a');
          return '<div style="display:flex;align-items:center;gap:7px;font-size:9.5px;color:rgba(223,242,251,0.74);padding:2px 0;">' +
            '<span style="width:74px;font-family:ui-monospace,monospace;font-size:9px;color:#dff2fb;">' + g[0] + '</span>' +
            '<span style="flex:1;height:3px;border-radius:2px;background:#102339;overflow:hidden;"><i style="display:block;height:100%;width:' + pct + '%;background:' + col + ';"></i></span>' +
            '<span style="font-family:ui-monospace,monospace;font-size:9px;color:rgba(223,242,251,0.54);width:32px;text-align:right;">' + g[2] + '/' + g[3] + '</span></div>';
        }).join('') +
        '<div style="font-size:9px;color:rgba(223,242,251,0.54);margin-top:6px;">上报模块 21/39（53.8%）· 结构死角 0 · 取证 docs/触手覆盖矩阵.md</div>') +
      '</div></div>');
  }
"""

# 5) 装配
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
tpl = tpl.replace("<title></title>", "<title>GBT小土豆V8 · 能力中枢 · 无限画布 V7</title>", 1)
s = tpl.index("  :root {")
e = tpl.index("\n  }", s) + len("\n  }")
tpl = tpl[:s] + TOKENS + tpl[e:]
tpl = tpl.replace("--grid-color: rgba(255,255,255,0.04);", "--grid-color: rgba(88,196,255,0.06);", 1)

strings = (S / "canvas_strings_v5.js").read_text(encoding="utf-8").replace("V5", "V7")
s = tpl.index("  const UI_STRINGS = {")
e = tpl.index("\n  };", s) + len("\n  };")
tpl = tpl[:s] + strings.rstrip("\n") + tpl[e:]

s2 = tpl.index("  /* ===== demo scene ===== */")
s3 = tpl.index("\n})();", s2)
tpl = tpl[:s2] + scene.rstrip("\n") + "\n\n  initScene();\n\n  const r = viewport.getBoundingClientRect();\n" \
      "  panX = r.width * 0.04;\n  panY = r.height * 0.04;\n  updateTransform();\n" + tpl[s3:]
OUT.write_text(tpl, encoding="utf-8")
print("写出:", OUT.name, len(OUT.read_bytes()), "B")
