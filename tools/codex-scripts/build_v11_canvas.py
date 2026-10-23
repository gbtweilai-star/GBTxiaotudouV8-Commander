# -*- coding: utf-8 -*-
"""构建 V11 画布：补「宿主外壳层」10 页（23 页 → 33 页）。
席位数据与本机官方包 lib/client.js 的真实注册一致。
"""
import sys
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:  # noqa: BLE001
    pass

BASE = next(p for p in Path(__file__).resolve().parents
            if (p / "gbt_allinone").is_dir())   # 修：原 `.parent.parent` 只到 tools/（少一层）
S = BASE / ".scratch"
SRC = BASE / "archive" / "V10 GBT小土豆V8-无限画布.html"
OUT = BASE / "V11 GBT小土豆V8-无限画布.html"
TPL = BASE / "infinite-canvas-output" / "assets" / "infinite-canvas-template.html"
assert SRC.exists(), "archive 里没有 V10 画布"

t = SRC.read_text(encoding="utf-8")
scene = t[t.index("  /* ===== scene ===== */"):t.index("\n  initScene();")]

# ── 1. screens 加 10 页 ──
old = "      ['上帝视角 · 项目树', p23()],"
assert old in scene, "screens 锚点未命中"
new = old + "\n" + "\n".join(
    "      ['%s', p%d()]," % (zh, n) for n, zh in [
        (24, '外壳与侧栏 · 11 席'), (25, '会话头部 · 6 席'), (26, '输入区席位 · 13 席'),
        (27, '对话视图环 · 6 席'), (28, '工具卡片 · 14 席'), (29, '权限与提问 · 4 包'),
        (30, '子代理与技能 · 5 包'), (31, '右侧栏与预览 · 6 席'), (32, '设置中心 · 24 席'),
        (33, '外部应用直通 · 30 应用')])
scene = scene.replace(old, new, 1)
scene = scene.replace("二十一块面板 · 项目树进了上帝视角", "三十一块面板 · 宿主外壳层补齐")
scene = scene.replace("'二十一块面板'", "'三十一块面板'")

# ── 1b. 署名：插在 initScene 体内、所有页之后（maxY 此时才有效） ──
trimmed = scene.rstrip()
assert trimmed.endswith("}"), "scene 尾部不是 initScene 的收口花括号"
cut = trimmed.rfind("}")
scene = (trimmed[:cut] +
         "\n\n    /* 署名（不可删除、不可篡改归属） */\n"
         "    addNote(40, maxY() + 34, UI_STRINGS.signatureTag, UI_STRINGS.signature);\n"
         "  }" + scene[len(trimmed):])

# ── 2. 追加 10 页 ──
# 数据：[slot id, 注册方, 是否已实现, 实现说明]
PAGES = {
    24: ("外壳与侧栏", "SHELL & SIDEBAR", [
        ("sidebar.brand.mark", "brand-official", 0), ("sidebar.brand.name", "brand-official", 0),
        ("sidebar.panellist", "sidebar", 0), ("sidebar.workspaces", "sidebar / workspace / chat", 1, "项目树（上帝视角）"),
        ("sidebar.footer.action", "sidebar / cordis", 0), ("sidebar.settings", "sidebar / settings-general", 0),
        ("shell.overlay", "layout", 0), ("session.new", "sidebar / workspace", 0),
        ("session.new.label", "sidebar", 0), ("session.hierarchy", "（子代理目录）", 0),
        ("workspace.add", "workspace", 0)],
        "官方侧栏是插槽外壳：品牌行、面板清单、工作区、设置席位、底部署位各自独立注册，任一插件都能往这些位置塞东西。本原型只实现了「工作区」这一格（项目树），其余 10 格是空的 —— 空就是空，不画假内容填。"),
    25: ("会话头部", "SESSION HEADER", [
        ("conversation.session", "conversation", 0), ("conversation.session.header", "conversation", 0),
        ("conversation.session.header.actions", "jobs / schedule / agent-preset", 0),
        ("conversation.session.header.corner", "sidebar-right / open-in-app", 0),
        ("conversation.session.header.lineage", "conversation / subagent", 0),
        ("conversation.session.header.utilities", "session-log-export", 0)],
        "两个插件抢同一个席位是官方允许的：席位是列表，不是单槽。header.actions 被 jobs（后台任务）、schedule（定时提醒）、agent-preset（预置）三家抢注；corner 归右侧栏、lineage 归子代理、utilities 归会话日志导出 —— 互不干扰，这是插槽设计的意义。"),
    26: ("输入区席位", "CONVERSATION INPUT", [
        ("conversation.input.dock", "goal", 0), ("conversation.input.plan", "plan", 0),
        ("conversation.input.model", "model-selection", 0), ("conversation.input.attachments", "attachment", 0),
        ("conversation.input.overlay", "commands / skill / reference / feedback", 0),
        ("conversation.input.left", "cordis-client-runner", 0), ("conversation.input.right", "cordis-client-runner", 0),
        ("conversation.composer", "conversation / approval / subagent / questions", 0),
        ("conversation.composer.bar", "conversation", 0), ("conversation.composer.dock", "chat", 0),
        ("conversation.hero.brand.mark", "conversation", 0), ("conversation.hero.workspace", "workspace", 0),
        ("conversation.message.images", "attachment / chat", 0)],
        "输入区最富：13 个席位。dock 放目标条带（编辑 / 暂停 / 恢复 / 清除），plan 放模式徽章，model 放模型选择，attachments 放草稿附件，overlay 放 / 命令与 @ 引用浮层。本原型一个都没实现 —— 输入框还是一根裸的输入框。"),
    27: ("对话视图环", "VIEW RING", [
        ("conversation.view", "conversation / chat / trajectory", 1, "对话面板"),
        ("main.conversation", "conversation", 1, "对话面板主区"),
        ("conversation.chat.node", "chat / tool / goal / workflow-run / cordis", 1, "消息节点"),
        ("conversation.chat.assistant-actions", "chat / feedback / cordis", 0),
        ("conversation.chat.commandview", "chat / cordis", 0),
        ("conversation.trajectory.images", "trajectory / attachment", 0)],
        "官方把「对话区长什么样」做成可注册的环：插件把视图注册进 conversation.view，用户切换视图，数据源不变。这解释了为什么同一个会话能既显示成聊天流、又显示成事件轨迹表 —— 不是两个页面，是同一个环的两个席位。本原型只有聊天流一个席位。"),
    28: ("工具卡片", "TOOL CARDS", [
        ("tool.call.toolview", "tool / deliverables / skill / cordis", 0),
        ("tool.call.images", "tool / attachment", 0), ("tool.view.cordis", "cordis", 0)] +
        [(("tool.title." + x), "tool", 0) for x in
         ["bash", "code", "edit", "generic", "glob", "grep", "inspect", "pwsh", "read", "search", "write"]],
        "官方给每个内置工具留了独立标题位（11 个），generic 是兜底位。调用树把一轮对话里所有工具调用组合成树，子调用挂父调用，再按工具名 key 分发到各自的卡片渲染器。本原型的工具调用只是文本流：没有树、没有按工具分卡、没有图片画廊。"),
    29: ("权限与提问", "APPROVAL & QUESTIONS", [
        ("conversation.approval.detail", "approval", 0), ("conversation.composer", "user-questions", 0),
        ("settings.permission", "permission-presets", 0),
        ("conversation.chat.assistant-actions", "message-feedback", 0),
        ("conversation.input.overlay", "message-feedback", 0)],
        "官方原话：「通过作用域交互路径响应 Host 权限请求的浏览器批准界面」。关键在作用域 —— 批准的不是「一次操作」，是「一个作用域 + 一个 TTL」。本项目的 auth_gate 就是这个模型：AI 永远不能自己给自己发。提问界面则是接管整个输入框，不是弹窗；plan 复审走同一套卡片。"),
    30: ("子代理与技能", "SUBAGENT & SKILL", [
        ("conversation.session.header.lineage", "subagent", 0),
        ("conversation.composer", "subagent", 0), ("tool.call.toolview", "skill / tool", 0)],
        "子代理三件事全缺：对话目录（谁派生了谁）、续接路由（会话头部 lineage 席位）、@ 引用（把子代理当上下文引进来）。技能同理：/ 触发候选、skill 调用卡片、tool.call.toolview 一个都没有。本环境技能目录 40+ 项，界面上一个都点不到。"),
    31: ("右侧栏与预览", "RIGHT PANE", [
        ("sidebar.right.pane.tab", "sidebar-right / files / documentpreview", 0),
        ("sidebar.right.pane.tab.title", "sidebar-right / files / documentpreview", 0),
        ("sidebar.right.tab.document", "sidebar-documentpreview", 0),
        ("sidebar.right.tab.guide", "sidebar-right", 0),
        ("sidebar.right.tab.menu.item", "sidebar-right", 0), ("rightbar.session", "sidebar-right", 0)],
        "页签是分层的：pane.tab 是页签本体，pane.tab.title 是标题位，tab.document / tab.guide 是两类内容位，menu.item 是页签右键菜单。文档预览有五个渲染器（Markdown / 代码 / 图片 / PDF / HTML）加纯文本兜底，按扩展名选。本原型里点文件名没有任何反应。"),
    32: ("设置中心", "SETTINGS", [
        ("settings.trigger", "settings-general", 0), ("settings.header", "settings-general", 0),
        ("settings.action", "settings-general", 0), ("settings.close", "settings-general", 0),
        ("settings.section", "settings / models / plugins / agent-preset", 0),
        ("settings.general.item", "settings-general / chat / theme / locale / presets", 0),
        ("settings.theme", "theme", 0), ("settings.locale", "locale", 0),
        ("settings.onboarding", "settings-general / models", 0),
        ("settings.models", "settings-models", 0), ("settings.models.provider-card", "settings-models", 0),
        ("settings.models.footer", "settings-models", 0),
        ("settings.plugins", "settings-plugins", 0), ("settings.plugins.tab", "settings-plugins / inventory", 1, "插件市场面板"),
        ("settings.plugin.item", "settings-plugins", 1, "插件市场面板"),
        ("settings.transcript.compact", "chat", 0), ("settings.transcript.normal", "chat", 0),
        ("settings.transcript.title", "chat", 0), ("settings.transcript.description", "chat", 0),
        ("settings.enter.queue", "conversation", 0), ("settings.enter.steer", "conversation", 0),
        ("settings.enter.title", "conversation", 0), ("settings.enter.description", "conversation", 0),
        ("settings.permission", "permission-presets", 0), ("settings.plugin.item", "settings-plugins", 1, "插件市场面板")],
        "官方 dsh-client-ui-settings 自己的定义是「设置命名空间 scope 服务、schema 服务，以及规范设置 slot 类型约定」—— 设置面板本身不含任何设置项，它只提供位置和校验，每一项都由别的插件注册进来。所以本原型那个「设置」面板（主题 / 分布 / 快捷键）其实一个官方席位都没对上。"),
    33: ("外部应用直通", "OPEN IN APP", [
        (("app." + x), "open-in-app", 0) for x in
        ["androidstudio", "cursor", "explorer", "filemanager", "finder", "fork", "ghostty", "github",
         "gitkraken", "goland", "intellij", "iterm", "kitty", "phpstorm", "pycharm", "rider", "rustrover",
         "smartgit", "sourcetree", "sublimemerge", "sublimetext", "terminal", "tower", "vscode",
         "vscodeinsiders", "warp", "webstorm", "windsurf", "xcode", "zed"]],
         "官方描述：「在记住的应用中打开会话 workspace 目录，并列出主机探测到已安装的全部应用」。每个应用一个席位 id，宿主探测到装了才点亮 —— 下面 30 个 id 全部读自官方编译产物的注册表，不是猜的。点「在 X 中打开」= 起一个外部进程，属于 device_control 作用域，本原型不代发授权。"),
}

HELPERS = r"""
  /* ── 宿主外壳层 · V11 共用小件 ── */
  function slotRows_(slots) {
    return slots.map(function (s) {
      var done = !!s[2];
      return '<div style="display:flex;align-items:center;gap:8px;padding:4px 0;border-bottom:1px solid rgba(88,196,255,0.09);">' +
        '<i style="width:6px;height:6px;border-radius:50%;background:' + (done ? '#2ad4f0' : 'rgba(255,122,122,0.75)') + ';flex:none;"></i>' +
        '<span style="font-family:var(--font-mono);font-size:10.5px;color:' + (done ? '#dff2fb' : 'rgba(223,242,251,0.72)') + ';flex:1;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;">' + s[0] + '</span>' +
        '<span style="font-family:var(--font-mono);font-size:9px;color:rgba(223,242,251,0.34);max-width:26%;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;text-align:right;">' + s[1] + '</span>' +
        '<span style="font-family:var(--font-mono);font-size:9px;color:' + (done ? '#2ad4f0' : 'rgba(223,242,251,0.38)') + ';width:74px;text-align:right;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;">' + (done ? (s[3] || '已实现') : '未实现') + '</span></div>';
    }).join('');
  }
  function slotPage_(title, en, slots, note) {
    var done = slots.filter(function (s) { return !!s[2]; }).length;
    return shell_(bar(title) +
      '<div style="flex:1;padding:10px;min-width:0;display:flex;flex-direction:column;gap:10px;">' +
      card(en + ' · ' + slots.length + ' 席位 <span style="float:right;color:' + (done ? '#2ad4f0' : 'rgba(255,122,122,0.8)') + ';">已实现 ' + done + ' / ' + slots.length + '</span>',
        '<div style="max-height:322px;overflow:auto;">' + slotRows_(slots) + '</div>') +
      card('为什么这一层之前是空的 / WHY THIS LAYER WAS MISSING',
        '<div style="font-size:10px;color:rgba(223,242,251,0.74);line-height:1.9;">' + note + '</div>') +
      '</div>');
  }
"""

pagejs = "\n".join(
    "  function p%d() { return slotPage_('%s', '%s', %s, '%s'); }" % (
        n, zh, en,
        "[" + ",".join(
            "['%s','%s'%s]" % (s[0], s[1], (",1,'%s'" % s[3]) if len(s) > 3 else "")
            for s in slots) + "]",
        note.replace("'", "\\'"))
    for n, (zh, en, slots, note) in sorted(PAGES.items()))

scene += "\n\n" + HELPERS + "\n" + pagejs + "\n"

# ── 3. 从模板重建 ──
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
tpl = tpl.replace("<title></title>", "<title>GBT小土豆V8 · 能力中枢 · 无限画布 V11</title>", 1)
s = tpl.index("  :root {")
e = tpl.index("\n  }", s) + len("\n  }")
tpl = tpl[:s] + TOKENS + tpl[e:]
tpl = tpl.replace("--grid-color: rgba(255,255,255,0.04);", "--grid-color: rgba(88,196,255,0.06);", 1)
strings = (S / "canvas_strings_v5.js").read_text(encoding="utf-8").replace("V5", "V11")
strings = strings.replace(
    "  sections: { context: '01 项目背景', designSystem: '02 设计系统', deliverables: '03 设计稿' },",
    "  sections: { context: '01 项目背景', designSystem: '02 设计系统', deliverables: '03 设计稿' },\n"
    "  signatureTag: '开发者',\n"
    "  signature: '开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属 · V11 · 30 面板 / 33 画布页',")
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
print("页数: 33（原 23 + 宿主外壳 10）")
