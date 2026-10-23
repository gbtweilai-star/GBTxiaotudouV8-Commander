# -*- coding: utf-8 -*-
"""V6 画布：在 V5 场景上加「语音」「蓝牙」两页，重建无限画布。"""
import shutil
from pathlib import Path

BASE = next(p for p in Path(__file__).resolve().parents
            if (p / "gbt_allinone").is_dir())   # 修：原 `.parent.parent` 只到 tools/（少一层）
S = BASE / ".scratch"
TPL = BASE / "infinite-canvas-output" / "assets" / "infinite-canvas-template.html"
OUT = BASE / "V6 GBT小土豆V8-无限画布.html"

# 归档 V5 画布
v5c = BASE / "V5 GBT小土豆V8-无限画布.html"
if v5c.exists():
    shutil.copy2(v5c, BASE / "archive" / v5c.name)

strings = (S / "canvas_strings_v5.js").read_text(encoding="utf-8").replace("V5", "V6")
scene = (S / "canvas_scene_v5.js").read_text(encoding="utf-8")

# 1) 页面清单加两页
old_screens = """    const screens = [
      ['对话 · 空态', p1()],"""
new_screens = """    const screens = [
      ['对话 · 空态', p1()],
      ['语音 · 听想说三段', p10()],
      ['蓝牙 · 扫描与控制', p11()],"""
assert old_screens in scene, "screens 锚点未命中"
scene = scene.replace(old_screens, new_screens, 1)

# 2) Row1 文案更新（九块面板）
scene = scene.replace("七块真面板 · 大脑执行层精细演化", "九块真面板 · 大脑执行层 + 语音 + 蓝牙")
scene = scene.replace("'七块真面板'", "'九块真面板'")
scene = scene.replace("换成七块全部接真数的面板", "换成九块全部接真数的面板（新增语音 / 蓝牙）")

# 3) 追加两页实现（函数声明会提升，位置随意）
scene += """

  function p10() {
    var CH = [['听 · ASR','缺后端','#ff7a7a','GBT_ASR_BASE_URL / GBT_ASR_API_KEY'],
              ['想 · 大脑','通','#3ddc97','brain_unify 全链 24.2s'],
              ['说 · TTS','待授权','#f5b544','缺 audio_output']];
    return shell_(bar('语音') +
      '<div style="flex:1;display:flex;min-height:0;">' + nav7('语音') +
      '<div style="flex:1;padding:10px;min-width:0;overflow:hidden;">' +
      card('语音对话三段 / LISTEN · THINK · SPEAK',
        CH.map(function (c) {
          return '<div style="display:grid;grid-template-columns:74px 1fr auto;gap:8px;align-items:center;font-size:10.5px;color:rgba(223,242,251,0.74);padding:5px 0;border-bottom:1px dashed rgba(88,196,255,0.14);">' +
            '<span style="font-family:ui-monospace,monospace;font-size:10.5px;color:#dff2fb;">' + c[0] + '</span>' +
            '<span><i style="display:inline-block;width:6px;height:6px;border-radius:50%;background:' + c[2] + ';margin-right:6px;"></i>' + c[1] +
            '<span style="color:rgba(223,242,251,0.54);margin-left:8px;font-size:9.5px;">' + c[3] + '</span></span>' +
            '<span style="font-family:ui-monospace,monospace;font-size:9.5px;color:' + c[2] + ';">' + (c[1] === '通' ? '通' : (c[1] === '待授权' ? '待授权' : '缺件')) + '</span></div>';
        }).join('') +
        '<div style="font-size:9.5px;color:rgba(223,242,251,0.54);margin-top:8px;line-height:1.7;">听 + 想 + 说 三段全通才叫语音对话。现在想得通、说被拦、听缺件。</div>') +
      card('说 · TTS / 听 · ASR',
        '<div style="display:grid;grid-template-columns:1fr 1fr;gap:9px;">' +
        '<div><div style="font-family:ui-monospace,monospace;font-size:11px;color:#6ef2ff;">win-sapi</div>' +
        '<div style="font-size:9.5px;color:rgba(223,242,251,0.54);margin-top:4px;line-height:1.7;">后端可用<br>真调返回 denied<br>缺 audio_output</div></div>' +
        '<div><div style="font-family:ui-monospace,monospace;font-size:11px;color:#ff7a7a;">needs_dependency</div>' +
        '<div style="font-size:9.5px;color:rgba(223,242,251,0.54);margin-top:4px;line-height:1.7;">ASR 后端未配置<br>缺 URL / KEY<br>配好才算能听</div></div></div>' +
        '<div style="font-family:ui-monospace,monospace;font-size:9px;color:rgba(223,242,251,0.54);margin-top:8px;background:#04070f;border:1px solid rgba(88,196,255,0.14);border-radius:5px;padding:7px;word-break:break-all;">python -m gbt_allinone auth grant --scope audio_output --ttl 600</div>') +
      card('语音技能中枢 / 17 项实测',
        '<div style="display:flex;flex-wrap:wrap;gap:5px;">' +
        ['Whisper','Qwen3-ASR','VibeVoice-ASR','VoxCPM 2','Kokoro-82M','sherpa-onnx','CosyVoice'].map(function (s) {
          return '<span style="display:inline-flex;align-items:center;gap:5px;height:24px;padding:0 9px;border:1px solid rgba(245,181,68,.35);border-radius:100px;font-family:ui-monospace,monospace;font-size:9.5px;color:#dff2fb;">' +
            '<i style="width:5px;height:5px;border-radius:50%;background:#f5b544;"></i>' + s + '</span>';
        }).join('') + '</div>' +
        '<div style="font-size:9.5px;color:rgba(223,242,251,0.54);margin-top:8px;line-height:1.7;">本机只跑得动 2 项 → 未升格为独立 tab。出口清单写实际出口，不写规划出口。</div>') +
      '</div></div>');
  }

  function p11() {
    var DEV = [['70:F8:2E:50:4E:B5',-43,95],['49:99:3E:A4:F6:FF',-45,92],
               ['5D:1D:B1:8A:39:73',-77,38],['44:30:24:C6:EA:B2',-82,30],['68:5C:CB:67:48:1D',-82,30]];
    return shell_(bar('蓝牙') +
      '<div style="flex:1;display:flex;min-height:0;">' + nav7('蓝牙') +
      '<div style="flex:1;padding:10px;min-width:0;overflow:hidden;">' +
      card('适配器 / ADAPTER',
        st_('#3ddc97', 'BLE 后端', 'bleak') + st_('#3ddc97', '经典蓝牙栈', 'win-bluetooth-stack') +
        '<div style="font-size:9.5px;color:rgba(223,242,251,0.54);margin-top:7px;line-height:1.7;">本轮已修复：装 bleak 3.0.2 + 9 个 winrt 包后，scan 由缺件转为真跑通。</div>') +
      card('附近 BLE 设备 / SCAN <span style="float:right;">实测 5 台 · 5231ms</span>',
        DEV.map(function (d) {
          return '<div style="display:grid;grid-template-columns:1fr 56px;gap:8px;align-items:center;padding:5px 0;border-bottom:1px dashed rgba(88,196,255,0.14);">' +
            '<span><span style="font-family:ui-monospace,monospace;font-size:10px;color:#dff2fb;">' + d[0] + '</span>' +
            '<span style="display:block;height:3px;border-radius:2px;background:#102339;overflow:hidden;margin-top:4px;"><i style="display:block;height:100%;width:' + d[2] + '%;background:#2ad4f0;"></i></span></span>' +
            '<span style="font-family:ui-monospace,monospace;font-size:9.5px;color:rgba(223,242,251,0.54);text-align:right;">' + d[1] + ' dBm</span></div>';
        }).join('') +
        '<div style="display:flex;gap:7px;align-items:center;margin-top:9px;"><span style="height:24px;padding:0 10px;border:1px solid rgba(88,196,255,0.34);border-radius:100px;display:grid;place-items:center;font-size:10px;color:#6ef2ff;">重新扫描</span>' +
        '<span style="font-size:9.5px;color:rgba(223,242,251,0.54);">原型回放真实快照</span></div>') +
      card('连接与读写 / CONTROL <span style="float:right;">需授权</span>',
        st_('#f5b544', 'device_control', '未发放') +
        '<div style="font-family:ui-monospace,monospace;font-size:9px;color:rgba(223,242,251,0.54);margin-top:7px;background:#04070f;border:1px solid rgba(88,196,255,0.14);border-radius:5px;padding:7px;word-break:break-all;">python -m gbt_allinone auth grant --scope device_control --ttl 600</div>' +
        '<div style="font-size:9.5px;color:rgba(223,242,251,0.54);margin-top:7px;line-height:1.7;">脑层协议库 8 条：Tuya / Xiaomi / HomeKit / HID / NUS / Apple Continuity / Battery / Device Info。</div>') +
      '</div></div>');
  }
"""

# 3b) nav7 扩成九块
old_nav7 = "    var items = ['对话','能力广场','大脑执行层','领域分类','审计台账','系统体检','设置'];"
new_nav7 = "    var items = ['对话','能力广场','大脑执行层','领域分类','审计台账','语音','蓝牙','系统体检','设置'];"
assert old_nav7 in scene, "nav7 锚点未命中"
scene = scene.replace(old_nav7, new_nav7, 1)

# 4) 组装画布
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
tpl = tpl.replace("<title></title>", "<title>GBT小土豆V8 · 能力中枢 · 无限画布 V6</title>", 1)
s = tpl.index("  :root {")
e = tpl.index("\n  }", s) + len("\n  }")
tpl = tpl[:s] + TOKENS + tpl[e:]
tpl = tpl.replace("--grid-color: rgba(255,255,255,0.04);", "--grid-color: rgba(88,196,255,0.06);", 1)
s = tpl.index("  const UI_STRINGS = {")
e = tpl.index("\n  };", s) + len("\n  };")
tpl = tpl[:s] + strings.rstrip("\n") + tpl[e:]

s2 = tpl.index("  /* ===== demo scene ===== */")
s3 = tpl.index("\n})();", s2)
tpl = tpl[:s2] + scene.rstrip("\n") + "\n\n  initScene();\n\n  const r = viewport.getBoundingClientRect();\n" \
      "  panX = r.width * 0.04;\n  panY = r.height * 0.04;\n  updateTransform();\n" + tpl[s3:]
OUT.write_text(tpl, encoding="utf-8")
print("写出:", OUT.name, len(OUT.read_bytes()), "B")
