# -*- coding: utf-8 -*-
"""生成 V11 数据层：v10_manifest.json + 新增 dsh 键（真实读到的官方客户端插件与 slot 席位）。
dsh 段全部来自 .scratch/dsh_surface_scan.json 与 dsh_register_scan.json，无一条手写。
"""
import json
from collections import defaultdict
from pathlib import Path

S = Path(__file__).resolve().parent
BASE = S.parent

v10 = json.loads((S / "v10_manifest.json").read_text(encoding="utf-8"))
surf = json.loads((S / "dsh_surface_scan.json").read_text(encoding="utf-8"))
reg = json.loads((S / "dsh_register_scan.json").read_text(encoding="utf-8"))

# 描述表：包名 → README 前置元数据描述
DESC = {p["name"]: p["desc"] for p in surf["covered"] + surf["missing"]}

# 本原型当前真正实现了的席位（人工核对，保守）
IMPLEMENTED = {
    "conversation.view": "对话面板 · 视图容器",
    "conversation.chat.node": "对话面板 · 消息节点",
    "main.conversation": "对话面板 · 主区",
    "sidebar.workspaces": "上帝视角 · 项目树",
    "settings.plugins": "插件市场面板",
    "settings.plugins.tab": "插件市场面板",
    "settings.plugin.item": "插件市场面板",
}

# slot → 注册它的包
slot_owner = defaultdict(list)
for pkg, info in reg.items():
    for sl in info.get("registered_slots", {}):
        slot_owner[sl].append(pkg)

real_slots = sorted(s for s in slot_owner if not s.startswith("app."))
app_slots = sorted(s for s in slot_owner if s.startswith("app."))

# 家族分组（按 slot id 前两段）
fam = defaultdict(list)
for s in real_slots:
    parts = s.split(".")
    fam[".".join(parts[:2]) if len(parts) > 2 else s].append(s)

FAMILY_ZH = {
    "sidebar.brand": "侧栏品牌行", "sidebar.footer": "侧栏底部署位", "sidebar.panellist": "侧栏面板清单",
    "sidebar.right": "右侧栏页签", "sidebar.settings": "侧栏设置席位", "sidebar.workspaces": "侧栏工作区",
    "shell.overlay": "外壳浮层", "main.conversation": "主对话区",
    "session.new": "新建会话", "session.hierarchy": "会话层级", "workspace.add": "添加工作区",
    "rightbar.session": "右栏会话态",
    "conversation.session": "会话头", "conversation.input": "输入区席位", "conversation.composer": "输入栏",
    "conversation.hero": "空态引导", "conversation.view": "视图容器", "conversation.chat": "对话流",
    "conversation.message": "消息附件", "conversation.trajectory": "轨迹附件",
    "conversation.approval": "批准详情",
    "tool.call": "工具调用", "tool.title": "工具标题", "tool.view": "工具视图",
    "settings.section": "设置分区", "settings.general": "通用项", "settings.models": "模型设置",
    "settings.plugins": "插件设置", "settings.theme": "主题", "settings.locale": "语言",
    "settings.permission": "权限预设", "settings.transcript": "会话记录", "settings.enter": "回车行为",
    "settings.trigger": "设置入口", "settings.header": "设置头部", "settings.action": "设置动作",
    "settings.close": "设置关闭", "settings.onboarding": "首次引导",
}

families = [{"key": k, "zh": FAMILY_ZH.get(k, k), "slots": sorted(v)} for k, v in sorted(fam.items())]
families.sort(key=lambda f: -len(f["slots"]))

plugins = []
for pkg, info in sorted(reg.items()):
    slots = sorted(s for s in info.get("registered_slots", {}) if not s.startswith("app."))
    if not slots:
        continue
    plugins.append({
        "name": pkg,
        "desc": (DESC.get(pkg) or "")[:150],
        "inject": info.get("inject", []),
        "slots": slots,
        "n_slots": len(slots),
    })
plugins.sort(key=lambda p: -p["n_slots"])

apps = []
APP_ZH = {
    "cursor": "Cursor", "vscode": "VS Code", "vscodeinsiders": "VS Code Insiders",
    "windsurf": "Windsurf", "zed": "Zed", "sublimetext": "Sublime Text",
    "intellij": "IntelliJ IDEA", "goland": "GoLand", "pycharm": "PyCharm",
    "webstorm": "WebStorm", "phpstorm": "PhpStorm", "rider": "Rider",
    "rustrover": "RustRover", "androidstudio": "Android Studio", "xcode": "Xcode",
    "explorer": "文件资源管理器", "finder": "访达", "filemanager": "文件管理器",
    "terminal": "终端", "iterm": "iTerm2", "warp": "Warp", "kitty": "kitty",
    "ghostty": "Ghostty", "github": "GitHub Desktop", "gitkraken": "GitKraken",
    "fork": "Fork", "tower": "Tower", "smartgit": "SmartGit", "sourcetree": "Sourcetree",
    "sublimemerge": "Sublime Merge",
}
for s in app_slots:
    aid = s[4:]
    apps.append({"id": aid, "slot": s, "zh": APP_ZH.get(aid, aid)})

implemented = sorted(IMPLEMENTED)
missing = [s for s in real_slots if s not in IMPLEMENTED]

v10["dsh"] = {
    "scanned_at": surf["scanned_at"],
    "source": "本机 @deepseek-ai/* 包的 package.json(dsh 清单) + lib/client.js 编译产物",
    "official_total": surf["total_official"],
    "by_kind": surf["by_kind"],
    "client_total": surf["client_total"],
    "client_with_slots": len(plugins),
    "slots_real": real_slots,
    "slots_app": [a["slot"] for a in apps],
    "n_slots_real": len(real_slots),
    "n_slots_app": len(apps),
    "n_total": len(real_slots) + len(apps),
    "implemented": [{"slot": s, "how": IMPLEMENTED[s]} for s in implemented],
    "missing": missing,
    "n_implemented": len(implemented),
    "n_missing": len(missing),
    "families": families,
    "plugins": plugins,
    "apps": apps,
    "slot_owner": {s: sorted(slot_owner[s]) for s in real_slots},
}

out = S / "v11_manifest.json"
out.write_text(json.dumps(v10, ensure_ascii=False, indent=1), encoding="utf-8")
print("写出:", out.name, out.stat().st_size, "B")
print("官方包 %d · 客户端面 %d · 有 slot 注册的 %d" % (v10["dsh"]["official_total"],
      v10["dsh"]["client_total"], len(plugins)))
print("真实席位 %d（+应用席位 %d）= %d" % (len(real_slots), len(apps), v10["dsh"]["n_total"]))
print("已实现 %d · 未实现 %d" % (len(implemented), len(missing)))
print("家族 %d 个：" % len(families))
for f in families:
    print("   %-26s %2d  %s" % (f["key"], len(f["slots"]), f["zh"]))
