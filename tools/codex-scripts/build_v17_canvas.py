# -*- coding: utf-8 -*-
"""构建 V17 画布：补 5 页（原生浏览器 / 云电脑窗口 / 万能插工具集 / 编排内核 / 严格覆盖审计），53 → 58。"""
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
SRC = BASE / "archive" / "V16 GBT小土豆V8-无限画布.html"
OUT = BASE / "V17 GBT小土豆V8-无限画布.html"
assert SRC.exists(), "archive 里没有 V16 画布"

man = json.loads((S / "v17_manifest.json").read_text(encoding="utf-8"))
N = man["v17"]
BRW, CPC, TLS, KRN, SA = N["browser"], N["cloudpc"], N["tools"], N["kernel"], N["strict_audit"]


def n17(x):
    return "{:,}".format(x)


PAGES = [
    (54, '原生浏览器 · CDP', 'NATIVE BROWSER', [
        ('native_browser.py', '{} 行 · 直连 Chrome DevTools Protocol'.format(n17(BRW['ctrl_lines'])), 1),
        ('第三方依赖', '零 —— 自带最小 RFC6455 客户端（只为本机 CDP）', 1),
        ('操作', '{} 个：status/launch/ensure/list_tabs/create_tab/close_tab/activate_tab'.format(len(BRW['ops'])), 1),
        ('操作', 'navigate/reload/back/forward/screenshot/get_title/get_url/get_text', 1),
        ('操作', 'dom_query/wait_for/click_element/type_text/execute_script/inject_script', 1),
        ('操作', 'get_cookies/set_cookies/privacy_mode/intercept_requests/intercept_stop', 1),
        ('窗口置顶', 'pin_window —— launch/ensure 默认自动执行', 1),
        ('默认落位', BRW['window']['rect_default'], 1),
        ('置顶默认', BRW['window']['topmost_default'], 1),
        ('边界', BRW['window']['boundary'], 1),
        ('browser_cap.py', '{} 行 · 三级后端如实降级'.format(BRW['cap_lines']), 1),
    ], BRW['why']),
    (55, '云电脑独立窗口', 'CLOUD PC WINDOW', [
        ('形态', CPC['window']['form'], 1),
        ('不是 iframe', CPC['window']['not_iframe'], 1),
        ('给谁用', CPC['window']['for_whom'], 1),
        ('事实源', CPC['window']['source_of_truth'], 1),
        ('PROVISION 开通安装', '不可逆 · 花钱 · 必须过门', 0),
        ('CONNECT 连上', '可逆 · 不花钱 · 不必卡门', 1),
        ('STATUS 读数', '可逆 · 不花钱 · 不必卡门（只读）', 1),
        ('SNAPSHOT 快照', '可逆 · 花钱 · 不必卡门（可回滚，但仍留痕）', 1),
        ('RELEASE 释放', '不可逆 · 不花钱 · 必须过门（且必须先给账单读数）', 0),
        ('红线①', CPC['red_lines'][0], 1),
        ('红线②', CPC['red_lines'][1], 1),
        ('红线⑤', CPC['red_lines'][4], 1),
        ('当前凭据', '有' if CPC['current']['credentials_present'] else '无 —— 本骨架不编，未取证不引外部', 0),
    ], CPC['why']),
    (56, '万能插工具集', 'TOOLBOX', [
        ('目录', 'gbt_allinone/tools · {} 文件 / {} 行'.format(TLS['n'], n17(TLS['lines'])), 1),
        ('最大', 'awesome_tools_index.py · 4,125 行（Awesome Tools 蒸馏索引）', 1),
        ('次大', 'h3_video_gen.py · 1,360 行（H3mini 视频生成）', 1),
        ('其余', 'libtv_skill / dd_visualizer / a1art_skill / auto_switch / context_vault', 1),
        ('其余', 'stigmergy / dd_squadron / organ_check / local_brain / cloud_pc', 1),
        ('其余', 'orchestration_kernel / framework_gate / regression_stamp / energy_pool', 1),
        ('为什么漏了', 'V14 用了宽松判据，tools 显示「79% 已覆盖」⇒ 整组没进补漏清单', 0),
    ], TLS['why']),
    (57, '编排内核', 'ORCHESTRATION KERNEL', [
        ('来源', KRN['source'], 1),
        ('BrowserUse', KRN['three'][0][1], 1),
        ('CrewAI', KRN['three'][1][1], 1),
        ('Mastra', KRN['three'][2][1], 1),
        ('第 1 层', KRN['layers'][0], 1),
        ('第 2 层', KRN['layers'][1], 1),
        ('第 3 层', KRN['layers'][2], 1),
        ('真调用点', KRN['teeth'], 1),
        ('内部类型', ' / '.join(c['name'] for c in KRN['classes']), 1),
    ], KRN['why']),
    (58, '严格覆盖审计', 'STRICT COVERAGE', [
        ('方法', SA['method'], 1),
        ('假覆盖', '{} 个文件 / {} 行'.format(n17(SA['false_covered_n']), n17(SA['false_covered_lines'])), 0),
        ('怎么暴露的', SA['why'], 0),
        ('上界说明', SA['caveat'], 0),
        ('最大假覆盖', '审美相关skill/design-skeletons/html-ppt-* 的 deck-stage.js（按模板复制多份）', 0),
        ('最大假覆盖', '.openclaw/tmp/v92_all.js · 1,459 行（另一个钱包项目）', 0),
        ('最大假覆盖', 'gbt_allinone/tools/dd_visualizer.py · 891 行', 0),
        ('本版已补', '原生浏览器 / 云电脑窗口 / 工具集 / 编排内核 —— 5 个面板', 1),
    ], SA['why']),
]

t = SRC.read_text(encoding="utf-8")
scene = t[t.index("  /* ===== scene ===== */"):t.index("\n  initScene();")]

old = "      ['密钥保险箱', p53()],"
assert old in scene, "screens 锚点未命中"
new = old + "\n" + "\n".join("      ['%s', p%d()]," % (zh, n) for n, zh, _, _, _ in PAGES)
scene = scene.replace(old, new, 1)
scene = scene.replace("五十一块面板 · 框架核心层补齐 · 品牌 Logo 已接入",
                      "五十六块面板 · 浏览器与云电脑已补 · 品牌 Logo 已接入")

trimmed = scene.rstrip()
assert trimmed.endswith("}"), "scene 尾部不是收口花括号"
cut = trimmed.rfind("}")
scene = (trimmed[:cut] +
         "\n\n    /* 署名（不可删除、不可篡改归属） */\n"
         "    addNote(40, maxY() + 34, UI_STRINGS.signatureTag, UI_STRINGS.signature);\n"
         "  }" + scene[len(trimmed):])

pagejs = "\n".join(
    "  function p%d() { return corePage_('%s', '%s', %s, '%s'); }" % (
        n, zh, en,
        "[" + ",".join("['%s','%s',%d]" % (a.replace("'", "\\'"), b.replace("'", "\\'"), c)
                       for a, b, c in rows) + "]",
        note.replace("'", "\\'"))
    for n, zh, en, rows, note in PAGES)
scene += "\n\n" + pagejs + "\n"

t = t.replace("无限画布 V16", "无限画布 V17")
import re as _re  # noqa: E402
t = _re.sub(r"\bV16\b", "V17", t)
t = t.replace("V17 · 50 面板 / 53 画布页 · 排版与节奏已打磨",
              "V17 · 55 面板 / 58 画布页 · 原生浏览器与云电脑已补")

# 用新 scene 替换旧 scene（V11 重建后已没有 "demo scene" 标记，
# 直接按 /* ===== scene ===== */ 到 initScene(); 的区间做替换）
a = t.index("  /* ===== scene ===== */")
b = t.index("\n  initScene();")
t = t[:a] + scene.rstrip("\n") + t[b:]

OUT.write_text(t, encoding="utf-8")
print("写出:", OUT.name, "%.1f KB" % (OUT.stat().st_size / 1024))
print("页数: 58（原 53 + 5）")
