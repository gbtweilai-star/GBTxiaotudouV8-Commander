# -*- coding: utf-8 -*-
"""构建 V12 画布：补「工作区源码层」10 页（33 页 → 43 页）。"""
import sys
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:  # noqa: BLE001
    pass

BASE = next(p for p in Path(__file__).resolve().parents
            if (p / "gbt_allinone").is_dir())   # 修：原 `.parent.parent` 只到 tools/（少一层）
S = BASE / ".scratch"
SRC = BASE / "archive" / "V11 GBT小土豆V8-无限画布.html"
OUT = BASE / "V12 GBT小土豆V8-无限画布.html"
TPL = BASE / "infinite-canvas-output" / "assets" / "infinite-canvas-template.html"
assert SRC.exists(), "archive 里没有 V11 画布"

t = SRC.read_text(encoding="utf-8")
scene = t[t.index("  /* ===== scene ===== */"):t.index("\n  initScene();")]

PAGES = [
    (34, '工作区源码总览', 'WORKSPACE', [
        ('文件总数', '23,835 · 1202 MB', 1), ('代码文件', '8,125 · 1,941,784 行', 1),
        ('自有源码', '209,157 行', 1), ('测试', '24,748 行', 1),
        ('vendored 第三方', '1,287,943 行（194 万里的 128 万）', 0),
        ('构建脚手架', '413,736 行（.scratch）', 0),
        ('gbt_allinone', '374 个 .py · 115,021 行', 1),
        ('能力注册表', '140 良性 + 11 禁用 = 151 · 30 域（AST 核对一致）', 1)],
     '递归清点 + AST 解析，不是探针调用 —— 这是 V12 与前 11 版最大的方法差别。'
     '194 万行代码里 128 万行是 vendored（numpy / fastapi / pygments / uiautomation / comtypes），'
     '41 万行是自己造的构建脚手架；真正属于本项目的自有代码 233,905 行（含测试）。'),
    (35, '缺口对账 · 80023 行', 'THE GAP', [
        ('审美相关skill', '76 文件 · 26,114 行', 1), ('情报流水线 last30days', '56 文件 · 20,756 行', 1),
        ('量化与钱包 agent-gvmz', '21 文件 · 11,390 行', 1), ('全息面板桥 holo_pet', '10 文件 · 7,947 行', 1),
        ('五维合一 .cluster', '46 文件 · 7,059 行', 1), ('桌面数字人 potato_pet', '17 文件 · 5,423 行', 1),
        ('设计大脑 caps/design_brain', '1 文件 · 777 行', 1), ('四路账本 holo_pet_w3', '2 文件 · 320 行', 1),
        ('审美大脑 brain', '2 文件 · 237 行', 1),
        ('死代码', 'NotImplementedError 2 处 · TODO 6 处（无成规模占位）', 1),
        ('硬编码密钥', '31 处命中 · 31 处测试假体 · 0 处需复核', 1)],
     '九个板块全部有外部引用或有可执行入口 —— 没有一个是纯孤儿。问题不是「没写完」，是「没接进界面」。'
     '前 11 版用探针拿运行期读数，只能告诉我「注册了几个能力、跑通没有」，'
     '告诉不了我「源码里还有什么没被注册成能力的东西」。改成真读源码，缺口立刻现形。'),
    (36, '全息面板桥 holo_pet', 'HOLO BRIDGE', [
        ('panel_server.py', '3,006 行 / 138.7 KB（全工作区最大自有文件）', 1),
        ('HoloBridge', '55 个方法 · Codex/LLM 降级/心智/GBT 能力适配器', 1),
        ('EventBus', '8 方法 · 线程安全事件总线，保留历史供刷新接回', 1),
        ('MessageDeduper', '6 方法 · 受理侧幂等门', 1),
        ('_Handler', '11 方法 · 静态资源与本地 API，只在 127.0.0.1 起', 1),
        ('research_status.py', '调研信源六态判定（声明/实测/水位分开读）', 1),
        ('research/orchestrator.py', '六环最后一环：按时间按顺序把前五环串起来', 1),
        ('social_platforms.py', '社交发布平台表（纯数据，无 IO）', 1)],
     '自述只做三件事：把静态前端与本地 GLB 送到浏览器；把 Codex App Server 的流式事件/审批/GBT 动态工具'
     '接到面板；把蓝牙与看屏幕统一送回 api.run_task。这是整个工作区最大的单个自有代码文件，'
     '我此前一个面板都没给它。'),
    (37, '桌面数字人 potato_pet', 'DESKTOP HUMAN', [
        ('pet_window.py', '透明、无边框、置顶的 Live2D 形象层', 1),
        ('behavior.py', '「调皮行为引擎」v3', 1),
        ('main.py', '数字人整合入口', 1),
        ('chat_client.py', '多密钥链真大脑 + 离线自我认知应答', 1),
        ('eigenflux_client.py', 'EigenFlux CLI 适配器', 1),
        ('holo_panel.py', '全息悬浮对话面板', 1)],
     '数字人这条线我此前只在「其余域」面板里带过一句，等于没做。'),
    (38, '五维合一 · 脑眼耳嘴手', 'FIVE DIMENSION', [
        ('BrainExecutive', '17 方法 · decompose_task / build_plan / evaluate_feedback / adjust_plan', 1),
        ('DimensionSyncEngine', '9 方法 · 五维同步：register / execute_cycle / get_status', 1),
        ('DeepVision', '9 方法 · 目标检测 / 布局分析 / 色彩提取 / 场景分类', 1),
        ('ocr_engine.py', 'OCR 文字识别', 1), ('sound_detector.py', '声音事件检测', 1),
        ('file_operator.py', '文件操作能力', 1),
        ('dimension_sync.py', '577 行 · 五维同步引擎', 1)],
     '🔴 工作区里有两套五维系统：gbt_allinone 的 brain 是 route/execute/tentacle/vision/audit'
     '（我的「大脑执行层」面板画的是这套）；这套是脑-眼-耳-嘴-手。'
     '它的自述是「解决原有 brain 只做一次性决策、五维串行、没有任务拆解与反馈闭环的痛点」。'
     '我此前只呈现了前一套，且从未说明还有第二套。'),
    (39, '设计大脑 caps/design_brain', 'DESIGN BRAIN', [
        ('do_architect', '建筑外观 3D 效果图', 1), ('do_interior', '室内装修 3D 效果图', 1),
        ('do_renovate', '翻新改造前后对比', 1), ('do_deploy_layout', '部署布局 · 空间规划 3D 图', 1),
        ('do_aesthetic', '审美增强（修过：旧实现恒用默认 warm_luxury）', 1),
        ('do_controlnet_render', '深度估计 + 5 风格批量生成', 1),
        ('do_style_guide', '风格指南 · 列出全部支持风格', 1),
        ('do_prompt_builder', '中文需求 → 专业 3D 渲染 prompt', 1)],
     '777 行 / 22 个顶层函数 / 有可执行入口，位于顶层 caps/ 目录 —— 该目录下唯一的东西。'
     '它有 AI 驱动 3D 真实图片生成的完整链路，我从未覆盖。'),
    (40, '情报流水线 last30days', 'INTEL PIPELINE', [
        ('engine/render.py', '1,723 行 · cluster-first 渲染（包内最大）', 1),
        ('engine/pipeline.py', '1,070 行 · v3.0.0 编排流水线', 1),
        ('engine/planner.py', '713 行 · LLM-first 查询规划 + 危险查询确定性兜底', 1),
        ('engine/github.py', 'GitHub Issues/PRs 搜索', 1),
        ('engine/youtube_yt.py', 'YouTube 搜索与转写（yt-dlp）', 1),
        ('engine/reddit.py · polymarket.py · tiktok.py', '另外三个源引擎', 1),
        ('cli.py', 'v3.0.0 命令行入口', 1),
        ('两阶段补充检索', '抽取实体后再做定向补充 + 薄源重试', 1)],
     '整条流水线 20,756 行。我此前在「情报与观察」面板里只写了七个能力名，源码一行没读。'
     'v3.0.0 的五源引擎是真实检索实现，不是骨架。'),
    (41, '审美技能与骨架', 'AESTHETIC SKILLS', [
        ('审美相关skill', '76 个 .py · 26,114 行（自有代码第二大）', 1),
        ('.md 文件', '469 个（本项目 1507 个 .md 的三成）', 1),
        ('design-skeletons/last30days', 'gbt_allinone 同名流水线的技能化副本', 1),
        ('我对它的了解', '仅限「设计流程要读的那几份规则 md」', 0)],
     '自有代码里第二大的板块。我与它的唯一交集是设计流程要读的规则文件，代码层一行没读过。'),
    (42, '量化与钱包 agent-gvmz-gbtv8', 'QUANT & WALLET', [
        ('CIS v42', '加密快进快出收割系统（两个版本，各 ~37 KB）', 1),
        ('gbt_wallet API', '本地 FastAPI，默认 127.0.0.1:8097', 1),
        ('gwapi_mail / smtp / session', '钱包 / 发票 / 扫描 / 余额 / 技术费单据 / 事件流', 1),
        ('同族散落文件', '顶层 .openclaw/tmp/ 另有 412 个 .py', 0)],
     '涉及真实资金链路。任何冒烟测试都应在镜像房间里跑，不许直连生产 —— 这是生产面红线里的第一条。'),
    (43, '账本与审美脑', 'LEDGER & BRAIN', [
        ('ledger/ledger_store.py', '上帝视角四路账本常驻化（W3 产物 5）', 1),
        ('tests/run_tests.py', '自述「不是孤儿测试」', 1),
        ('brain/aesthetic_brain.py', '设计/文案质量多维度评估', 1),
        ('brain/skill_polish.py', '常用原生技能打磨迭代器 v1', 1)],
     '两块都很小（合计 557 行），但都属于「框架的自我维护层」。'
     '其中 ledger 的文件名里就写着「上帝视角」—— 而我的上帝视角里从来没有它。'),
]

old = "      ['外部应用直通 · 30 应用', p33()],"
assert old in scene, "screens 锚点未命中"
new = old + "\n" + "\n".join("      ['%s', p%d()]," % (zh, n) for n, zh, _, _, _ in PAGES)
scene = scene.replace(old, new, 1)
scene = scene.replace("三十一块面板 · 宿主外壳层补齐", "四十一块面板 · 工作区源码层补齐")
scene = scene.replace("'三十一块面板'", "'四十一块面板'")

# 署名：仍在 initScene 体内、所有页之后
trimmed = scene.rstrip()
assert trimmed.endswith("}"), "scene 尾部不是 initScene 的收口花括号"
cut = trimmed.rfind("}")
scene = (trimmed[:cut] +
         "\n\n    /* 署名（不可删除、不可篡改归属） */\n"
         "    addNote(40, maxY() + 34, UI_STRINGS.signatureTag, UI_STRINGS.signature);\n"
         "  }" + scene[len(trimmed):])

HELPERS = r"""
  /* ── 工作区源码层 · V12 共用小件 ── */
  function wsPage_(title, en, rows, note) {
    var ok = rows.filter(function (r) { return !!r[2]; }).length;
    return shell_(bar(title) +
      '<div style="flex:1;padding:10px;min-width:0;display:flex;flex-direction:column;gap:10px;">' +
      card(en + ' · ' + rows.length + ' 项 <span style="float:right;color:rgba(223,242,251,0.54);">已核 ' + ok + ' / ' + rows.length + '</span>',
        rows.map(function (r) {
          return '<div style="display:flex;align-items:flex-start;gap:8px;padding:5px 0;border-bottom:1px solid rgba(88,196,255,0.09);">' +
            '<i style="width:6px;height:6px;border-radius:50%;margin-top:5px;flex:none;background:' + (r[2] ? '#2ad4f0' : 'rgba(245,181,68,0.85)') + ';"></i>' +
            '<span style="font-family:var(--font-mono);font-size:10.5px;color:' + (r[2] ? '#dff2fb' : 'rgba(245,181,68,0.9)') + ';flex:1;min-width:0;">' + r[0] + '</span>' +
            '<span style="font-size:10px;color:rgba(223,242,251,0.6);max-width:48%;text-align:right;">' + r[1] + '</span></div>';
        }).join('')) +
      card('为什么这一层之前是空的 / WHY THIS LAYER WAS MISSING',
        '<div style="font-size:10px;color:rgba(223,242,251,0.74);line-height:1.9;">' + note + '</div>') +
      '</div>');
  }
"""
pagejs = "\n".join(
    "  function p%d() { return wsPage_('%s', '%s', %s, '%s'); }" % (
        n, zh, en,
        "[" + ",".join("['%s','%s',%d]" % (a.replace("'", "\\'"), b.replace("'", "\\'"), c)
                       for a, b, c in rows) + "]",
        note.replace("'", "\\'"))
    for n, zh, en, rows, note in PAGES)

scene += "\n\n" + HELPERS + "\n" + pagejs + "\n"

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
tpl = tpl.replace("<title></title>", "<title>GBT小土豆V8 · 能力中枢 · 无限画布 V12</title>", 1)
s = tpl.index("  :root {")
e = tpl.index("\n  }", s) + len("\n  }")
tpl = tpl[:s] + TOKENS + tpl[e:]
tpl = tpl.replace("--grid-color: rgba(255,255,255,0.04);", "--grid-color: rgba(88,196,255,0.06);", 1)
strings = (S / "canvas_strings_v5.js").read_text(encoding="utf-8").replace("V5", "V12")
strings = strings.replace(
    "  sections: { context: '01 项目背景', designSystem: '02 设计系统', deliverables: '03 设计稿' },",
    "  sections: { context: '01 项目背景', designSystem: '02 设计系统', deliverables: '03 设计稿' },\n"
    "  signatureTag: '开发者',\n"
    "  signature: '开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属 · V12 · 40 面板 / 43 画布页',")
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
print("页数: 43（原 33 + 工作区源码 10）")
