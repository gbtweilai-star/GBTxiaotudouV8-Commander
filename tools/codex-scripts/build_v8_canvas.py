# -*- coding: utf-8 -*-
"""构建 V8 画布：从 V7 画布抽 scene，补 8 页缺口域设计稿后重装。"""
import shutil
from pathlib import Path

BASE = next(p for p in Path(__file__).resolve().parents
            if (p / "gbt_allinone").is_dir())   # 修：原 `.parent.parent` 只到 tools/（少一层）
S = BASE / ".scratch"
V7C = BASE / "V7 GBT小土豆V8-无限画布.html"
OUT = BASE / "V8 GBT小土豆V8-无限画布.html"
TPL = BASE / "infinite-canvas-output" / "assets" / "infinite-canvas-template.html"

shutil.copy2(V7C, BASE / "archive" / V7C.name)

t7 = V7C.read_text(encoding="utf-8")
scene = t7[t7.index("  /* ===== scene ===== */"):t7.index("\n  initScene();")]

old = "      ['亿万触手 · 三通道与十域', p13()],"
new = old + """
      ['镜像与晋升 · 对账与巡检', p14()],
      ['大模型通道 · 密钥链', p15()],
      ['心智与记忆 · 状态与脑库', p16()],
      ['情报与观察 · 追踪链', p17()],
      ['安全攻防 · 743 项扫描', p18()],
      ['长程与工具 · 任务与穿透', p19()],
      ['创作与吞噬 · 场景与质量', p20()],
      ['其余域 · 一次盘完', p21()],"""
assert old in scene, "screens 锚点未命中"
scene = scene.replace(old, new, 1)

old_nav = "    var items = ['对话','能力广场','大脑执行层','领域分类','审计台账','语音','蓝牙','万能插','亿万触手','系统体检','设置'];"
new_nav = ("    var items = ['对话','能力广场','大脑执行层','领域分类','审计台账','语音','蓝牙','万能插','亿万触手',\n"
           "                 '镜像与晋升','大模型通道','心智与记忆','情报与观察','安全攻防','长程与工具','创作与吞噬','其余域','系统体检','设置'];")
assert old_nav in scene, "nav 锚点未命中"
scene = scene.replace(old_nav, new_nav, 1)

scene = scene.replace("十一块真面板 · 神经中枢全开", "十九块真面板 · 30 域全覆盖")
scene = scene.replace("'十一块真面板'", "'十九块真面板'")
scene = scene.replace("换成十一块全部接真数的面板（新增语音 / 蓝牙 / 万能插 / 亿万触手）",
                      "补齐到十九块：30 个能力域全部有专属可视化，此前只有名字的 89 项能力全部归位")

APPEND = """

  function p14() {
    return shell_(bar('镜像与晋升') +
      '<div style="flex:1;display:flex;min-height:0;">' + nav7('镜像与晋升') +
      '<div style="flex:1;padding:10px;min-width:0;">' +
      card('镜像 ↔ 现实 / DIMENSION <span style="float:right;">现实版本 26</span>',
        '<div style="display:grid;grid-template-columns:1fr 1fr;gap:11px;">' +
        '<div><div style="font-family:ui-monospace,monospace;font-size:24px;color:#6ef2ff;">19</div><div style="font-size:9px;color:rgba(223,242,251,0.54);">镜像维度 · 文件</div></div>' +
        '<div><div style="font-family:ui-monospace,monospace;font-size:24px;color:#6ef2ff;">19</div><div style="font-size:9px;color:rgba(223,242,251,0.54);">现实 · 文件</div></div></div>' +
        '<div style="margin-top:10px;">' + st_('#3ddc97','差异项','0 项') + st_('#3ddc97','生产晋升','现实零修改') + '</div>') +
      card('镜像体检 / MIRROR SCAN <span style="float:right;">5/5 通过</span>',
        ['non_empty','no_empty_files','signed','entry','no_dual'].map(function (k) {
          return st_('#3ddc97', k, 'ok');
        }).join('')) +
      card('服务巡检 / SERVICES <span style="float:right;">0/14 在跑</span>',
        ['payment_gateway 8081','blockchain_bridge 8082','quant_api','gbt_wallet_api','hcl_control'].map(function (s) {
          return '<div style="display:flex;gap:7px;align-items:baseline;padding:3px 0;font-size:10px;">' +
            '<i style="width:5px;height:5px;border-radius:50%;background:#ff7a7a;"></i>' +
            '<span style="font-family:ui-monospace,monospace;color:#dff2fb;flex:1;">' + s + '</span>' +
            '<span style="font-size:9px;color:rgba(223,242,251,0.54);">down</span></div>';
        }).join('') +
        '<div style="font-size:9px;color:rgba(223,242,251,0.54);margin-top:6px;">发布记录 20 条 · 部署队列 0 · 幽灵守卫 clean</div>') +
      '</div></div>');
  }

  function p15() {
    return shell_(bar('大模型通道') +
      '<div style="flex:1;display:flex;min-height:0;">' + nav7('大模型通道') +
      '<div style="flex:1;padding:10px;min-width:0;">' +
      card('官方 Codex / CODEX <span style="float:right;">未连接</span>',
        st_('#f5b544','连接','未连接') + st_('#3ddc97','可执行体','codex.exe') +
        st_('#3ddc97','并发上限','1') + st_('#3ddc97','空闲回收','600s') +
        '<div style="font-size:9px;color:rgba(223,242,251,0.54);margin-top:6px;">codex_models 实测被拦：缺 external_llm 授权</div>') +
      card('密钥链 / KEY CHAIN <span style="float:right;">7 级</span>',
        ['agnes','deepseek','kimi','openai','custom','anthropic','gemini'].map(function (k, i) {
          return st_('#3ddc97', k, '第 ' + (i + 1) + ' 顺位');
        }).join('') + st_('#3ddc97','通道状态','ready')) +
      card('提示词桥 + 密钥池',
        '<div style="display:flex;flex-wrap:wrap;gap:5px;">' +
        ['【角色设定】','【任务目标】','【技术要求】','【输出约束】'].map(function (s) {
          return '<span style="display:inline-flex;align-items:center;height:22px;padding:0 9px;border:1px solid rgba(88,196,255,0.14);border-radius:100px;font-size:9.5px;color:#dff2fb;">' + s + '</span>';
        }).join('') + '</div>' +
        '<div style="font-size:9px;color:rgba(223,242,251,0.54);margin-top:7px;">纯本地 · 不外呼模型 · 在池密钥 0 · 活跃租借 0</div>') +
      '</div></div>');
  }

  function p16() {
    return shell_(bar('心智与记忆') +
      '<div style="flex:1;display:flex;min-height:0;">' + nav7('心智与记忆') +
      '<div style="flex:1;padding:10px;min-width:0;">' +
      card('心智状态 / MIND <span style="float:right;">awake</span>',
        st_('#3ddc97','状态','awake') + st_('#3ddc97','情绪','安静') +
        st_('#3ddc97','表情','bored') + st_('#3ddc97','在场感','熟悉中')) +
      card('脑库 / BRAIN VAULT <span style="float:right;">Obsidian</span>',
        '<div style="display:grid;grid-template-columns:1fr 1fr;gap:11px;">' +
        '<div><div style="font-family:ui-monospace,monospace;font-size:22px;color:#6ef2ff;">10</div><div style="font-size:9px;color:rgba(223,242,251,0.54);">笔记</div></div>' +
        '<div><div style="font-family:ui-monospace,monospace;font-size:22px;color:#6ef2ff;">25</div><div style="font-size:9px;color:rgba(223,242,251,0.54);">双链</div></div></div>' +
        '<div style="margin-top:9px;">' + st_('#f5b544','未解析链接','有') + st_('#3ddc97','写入方式','只追加·无删除') + '</div>') +
      card('导演情绪 + 元认知',
        st_('#3ddc97','情绪','平静') + st_('#3ddc97','强度','0.0') +
        '<div style="font-size:9.5px;color:rgba(223,242,251,0.74);line-height:1.8;margin-top:6px;">自省不是自责 —— 自检只记录「哪里卡了」，不写「我太差了」。</div>' +
        '<div style="font-size:9px;color:rgba(223,242,251,0.54);margin-top:5px;">自动切换阈值 0.8 · 低置信先问主人</div>') +
      '</div></div>');
  }

  function p17() {
    return shell_(bar('情报与观察') +
      '<div style="flex:1;display:flex;min-height:0;">' + nav7('情报与观察') +
      '<div style="flex:1;padding:10px;min-width:0;">' +
      card('趋势观察链 / TREND WATCH <span style="float:right;">4 环</span>',
        ['youtube-watcher','video-transcript-downloader','reddit-readonly','web-search-plus'].map(function (c, i) {
          return st_(i === 0 ? '#3ddc97' : '#3c4d63', c, '第 ' + (i + 1) + ' 环');
        }).join('')) +
      card('人机验证台账 / VERIFICATION',
        st_('#3ddc97','music_intel','0 条 · 违规 0') + st_('#3ddc97','video_intel','0 条 · 违规 0') +
        st_('#3ddc97','film_intel','0 条 · 违规 0') +
        '<div style="font-size:9px;color:rgba(223,242,251,0.54);margin-top:6px;">不主动绕做成机械闸；台账为空即无违规</div>') +
      card('情报组覆盖 / INTEL GROUPS',
        '<div style="display:flex;flex-wrap:wrap;gap:5px;">' +
        ['film_intel','music_intel','video_intel','osint_scan','topic_watch','trend_watch','verification_watch'].map(function (t) {
          return '<span style="display:inline-flex;align-items:center;gap:5px;height:22px;padding:0 9px;border:1px solid rgba(88,196,255,0.14);border-radius:100px;font-family:ui-monospace,monospace;font-size:9px;color:rgba(223,242,251,0.74);"><i style="width:5px;height:5px;border-radius:50%;background:#3ddc97;"></i>' + t + '</span>';
        }).join('') + '</div>' +
        '<div style="font-size:9px;color:rgba(223,242,251,0.54);margin-top:7px;">情报是输入不是指令 · 禁区清单优先于流量趋势</div>') +
      '</div></div>');
  }

  function p18() {
    return shell_(bar('安全攻防') +
      '<div style="flex:1;display:flex;min-height:0;">' + nav7('安全攻防') +
      '<div style="flex:1;padding:10px;min-width:0;">' +
      card('漏洞扫描 / SEC SCAN <span style="float:right;">743 项 · critical 33</span>',
        '<div style="display:grid;grid-template-columns:1fr 1fr;gap:11px;margin-bottom:9px;">' +
        '<div><div style="font-family:ui-monospace,monospace;font-size:24px;color:#6ef2ff;">743</div><div style="font-size:9px;color:rgba(223,242,251,0.54);">总命中</div></div>' +
        '<div><div style="font-family:ui-monospace,monospace;font-size:24px;color:#ff7a7a;">33</div><div style="font-size:9px;color:rgba(223,242,251,0.54);">critical</div></div></div>' +
        [['high',18,'#ff7a7a'],['medium',692,'#f5b544'],['low',0,'#2ad4f0']].map(function (r) {
          return '<div style="padding:3px 0;"><div style="display:flex;gap:7px;font-size:10px;color:rgba(223,242,251,0.74);"><span>' + r[0] + '</span><span style="margin-left:auto;font-family:ui-monospace,monospace;color:#6ef2ff;">' + r[1] + '</span></div>' +
            '<span style="display:block;height:3px;border-radius:2px;background:#102339;overflow:hidden;margin-top:4px;"><i style="display:block;height:100%;width:' + Math.round(100 * r[1] / 743) + '%;background:' + r[2] + ';"></i></span></div>';
        }).join('')) +
      card('攻击面测绘 / SURFACE <span style="float:right;">9559ms</span>',
        [['入口点',785,900],['文件操作',967,1000],['网络',497,600],['用户输入',264,400]].map(function (r) {
          return '<div style="padding:3px 0;"><div style="display:flex;gap:7px;font-size:10px;color:rgba(223,242,251,0.74);"><span>' + r[0] + '</span><span style="margin-left:auto;font-family:ui-monospace,monospace;color:#6ef2ff;">' + r[1] + '</span></div>' +
            '<span style="display:block;height:3px;border-radius:2px;background:#102339;overflow:hidden;margin-top:4px;"><i style="display:block;height:100%;width:' + Math.round(100 * r[1] / r[2]) + '%;background:' + (r[1] > r[2] * 0.7 ? '#f5b544' : '#2ad4f0') + ';"></i></span></div>';
        }).join('') +
        '<div style="font-size:9px;color:rgba(223,242,251,0.54);margin-top:6px;">OWASP Top 10 + CWE 模式库，扫的是自己</div>') +
      '</div></div>');
  }

  function p19() {
    /* 穿透网七栏：清单 seven_columns 是 7 项（indexed / entry_known / reachable /
       verified(reachable) / verified(readonly) / has_test / penetrate_ready），
       旧版这里手写死数组只有 5 项 —— 标题说「七栏」、屏幕上是 5 行，而
       verify_v8.py:90 只查清单条数，所以全绿。行数从 NET7 算，标题也从 NET7 算，
       别再手写字面量。 */
    var NET7 = [['indexed','170/170','#3ddc97'],['entry_known','24/170','#f5b544'],
      ['reachable','20/151','#ff7a7a'],['verified(reachable)','20/151','#ff7a7a'],
      ['verified(readonly)','9 口 / 6 位','#f5b544'],['has_test','2/151','#ff7a7a'],
      ['penetrate_ready','9 口 / 6 位','#2ad4f0']];   /* 值与 :root 清单 seven_columns 逐字一致 */
    return shell_(bar('长程与工具') +
      '<div style="flex:1;display:flex;min-height:0;">' + nav7('长程与工具') +
      '<div style="flex:1;padding:10px;min-width:0;">' +
      card('长程任务图 / LONGRUN <span style="float:right;">58 项</span>',
        [['done 已完成',33,'#2ad4f0'],['failed 失败',25,'#ff7a7a'],['stalled 停滞',0,'#f5b544'],['pending 待办',0,'#3c4d63']].map(function (r) {
          return '<div style="padding:3px 0;"><div style="display:flex;gap:7px;font-size:10px;color:rgba(223,242,251,0.74);"><span>' + r[0] + '</span><span style="margin-left:auto;font-family:ui-monospace,monospace;color:#6ef2ff;">' + r[1] + '/58</span></div>' +
            '<span style="display:block;height:3px;border-radius:2px;background:#102339;overflow:hidden;margin-top:4px;"><i style="display:block;height:100%;width:' + Math.round(100 * r[1] / 58) + '%;background:' + r[2] + ';"></i></span></div>';
        }).join('')) +
      card('穿透网' + NET7.length + '栏 / CAPABILITY NET',
        NET7.map(function (r) {
          return '<div style="display:flex;gap:7px;align-items:baseline;padding:3px 0;font-size:10px;color:rgba(223,242,251,0.74);">' +
            '<span style="font-family:ui-monospace,monospace;font-size:10px;color:#dff2fb;">' + r[0] + '</span>' +
            '<span style="margin-left:auto;font-family:ui-monospace,monospace;font-size:9.5px;color:' + r[2] + ';">' + r[1] + '</span></div>';
        }).join('')) +
      card('工具 / TOOLS',
        st_('#3ddc97','awesome_tools_index','四原语 · 索引只读') +
        st_('#3ddc97','projection_card','只呈现不执行') +
        '<div style="font-size:9px;color:rgba(223,242,251,0.54);margin-top:6px;">非 LLM 验收 + 重试 + 停滞升级，跨进程可续</div>') +
      '</div></div>');
  }

  function p20() {
    return shell_(bar('创作与吞噬') +
      '<div style="flex:1;display:flex;min-height:0;">' + nav7('创作与吞噬') +
      '<div style="flex:1;padding:10px;min-width:0;">' +
      card('场景锚定 / SCENE ANCHOR <span style="float:right;">8 大类</span>',
        [['失去',['失恋','亲人离世','朋友走散','梦想破碎']],['重逢',['久别','和解','归来']],
         ['成长',['蜕变','代价','选择']]].map(function (c) {
          return '<div style="padding:5px 0;border-bottom:1px dashed rgba(88,196,255,0.14);">' +
            '<div style="font-family:ui-monospace,monospace;font-size:10.5px;color:#6ef2ff;">' + c[0] + '</div>' +
            '<div style="font-size:9.5px;color:rgba(223,242,251,0.54);margin-top:3px;">' + c[1].join(' · ') + '</div></div>';
        }).join('')) +
      card('吞噬与进化 / DEVOUR <span style="float:right;">均分 78</span>',
        '<div style="display:grid;grid-template-columns:repeat(3,1fr);gap:9px;margin-bottom:9px;">' +
        '<div><div style="font-family:ui-monospace,monospace;font-size:19px;color:#6ef2ff;">26</div><div style="font-size:9px;color:rgba(223,242,251,0.54);">已评</div></div>' +
        '<div><div style="font-family:ui-monospace,monospace;font-size:19px;color:#3ddc97;">25</div><div style="font-size:9px;color:rgba(223,242,251,0.54);">强项</div></div>' +
        '<div><div style="font-family:ui-monospace,monospace;font-size:19px;color:#f5b544;">1</div><div style="font-size:9px;color:rgba(223,242,251,0.54);">弱项</div></div></div>' +
        '<span style="display:block;height:4px;border-radius:2px;background:#102339;overflow:hidden;"><i style="display:block;height:100%;width:78%;background:#2ad4f0;"></i></span>' +
        '<div style="margin-top:8px;">' + st_('#f5b544','ledger','域无任何能力') + st_('#f5b544','wallet','域无任何能力') + '</div>') +
      card('代码艺术 + 创作线',
        '<div style="display:flex;flex-wrap:wrap;gap:5px;">' +
        ['INDEX 索引','SEED 种子','CANVAS 画布','LAYER 层','EXPORT 导出'].map(function (t) {
          return '<span style="display:inline-flex;align-items:center;height:22px;padding:0 9px;border:1px solid rgba(88,196,255,0.14);border-radius:100px;font-size:9.5px;color:#dff2fb;">' + t + '</span>';
        }).join('') + '</div>' +
        '<div style="font-size:9px;color:rgba(223,242,251,0.54);margin-top:6px;">作品 0 · 无种子不许导出 · 红线四条</div>') +
      '</div></div>');
  }

  function p21() {
    return shell_(bar('其余域') +
      '<div style="flex:1;display:flex;min-height:0;">' + nav7('其余域') +
      '<div style="flex:1;padding:10px;min-width:0;">' +
      card('生命档案 / LIFE <span style="float:right;">alive</span>',
        '<div style="display:grid;grid-template-columns:repeat(3,1fr);gap:11px;">' +
        '<div><div style="font-family:ui-monospace,monospace;font-size:22px;color:#6ef2ff;">168</div><div style="font-size:9px;color:rgba(223,242,251,0.54);">事件</div></div>' +
        '<div><div style="font-family:ui-monospace,monospace;font-size:11px;color:#dff2fb;">2026-09-11</div><div style="font-size:9px;color:rgba(223,242,251,0.54);">首次</div></div>' +
        '<div><div style="font-family:ui-monospace,monospace;font-size:11px;color:#dff2fb;">2026-09-19</div><div style="font-size:9px;color:rgba(223,242,251,0.54);">最近</div></div></div>') +
      card('框架之门 / GATE VISIBILITY',
        ['已纳入','显式不纳入','未决定'].map(function (s, i) {
          return st_([ '#3ddc97','#3c4d63','#f5b544'][i], s, '');
        }).join('') +
        '<div style="font-size:9px;color:rgba(223,242,251,0.54);margin-top:6px;">可见范围只从 framework_gate 读，不复刻第二份</div>') +
      card('项目上下文 + 量化',
        st_('#3ddc97','蓝图','PROJECT_BLUEPRINT.md') + st_('#3ddc97','工作区','Workspace · 存在') +
        st_('#3ddc97','顶层目录','8 个') +
        '<div style="font-size:9px;color:rgba(223,242,251,0.54);margin-top:6px;">量化四项属外部业务模块，未挂载即如实报缺口</div>') +
      card('媒体与外部域 <span style="float:right;">10 项 · 多为门</span>',
        '<div style="display:flex;flex-wrap:wrap;gap:5px;">' +
        ['video 3','image_video','digital_human','infra','integration','social','comms','collab','automation','vision','finance 4'].map(function (t) {
          return '<span style="display:inline-flex;align-items:center;gap:5px;height:22px;padding:0 9px;border:1px solid rgba(245,181,68,.35);border-radius:100px;font-family:ui-monospace,monospace;font-size:9px;color:#dff2fb;"><i style="width:5px;height:5px;border-radius:50%;background:#f5b544;"></i>' + t + '</span>';
        }).join('') + '</div>' +
        '<div style="font-size:9px;color:rgba(223,242,251,0.54);margin-top:7px;">出口清单写实际出口，不写规划出口 —— 是门就标门，不画假运行台</div>') +
      '</div></div>');
  }
"""
scene += APPEND

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
tpl = tpl.replace("<title></title>", "<title>GBT小土豆V8 · 能力中枢 · 无限画布 V8</title>", 1)
s = tpl.index("  :root {")
e = tpl.index("\n  }", s) + len("\n  }")
tpl = tpl[:s] + TOKENS + tpl[e:]
tpl = tpl.replace("--grid-color: rgba(255,255,255,0.04);", "--grid-color: rgba(88,196,255,0.06);", 1)

strings = (S / "canvas_strings_v5.js").read_text(encoding="utf-8").replace("V5", "V8")
s = tpl.index("  const UI_STRINGS = {")
e = tpl.index("\n  };", s) + len("\n  };")
tpl = tpl[:s] + strings.rstrip("\n") + tpl[e:]

s2 = tpl.index("  /* ===== demo scene ===== */")
s3 = tpl.index("\n})();", s2)
tpl = tpl[:s2] + scene.rstrip("\n") + "\n\n  initScene();\n\n  const r = viewport.getBoundingClientRect();\n" \
      "  panX = r.width * 0.04;\n  panY = r.height * 0.04;\n  updateTransform();\n" + tpl[s3:]
OUT.write_text(tpl, encoding="utf-8")
print("写出:", OUT.name, len(OUT.read_bytes()), "B")
