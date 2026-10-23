# -*- coding: utf-8 -*-
"""构建 V18 画布：加一页「能力 → 源码」（58 → 59）。"""
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
SRC = BASE / "archive" / "V17 GBT小土豆V8-无限画布.html"
OUT = BASE / "V18 GBT小土豆V8-无限画布.html"
assert SRC.exists(), "archive 里没有 V17 画布"

man = json.loads((S / "v18_manifest.json").read_text(encoding="utf-8"))
CS = man["capsrc"]

rows = [
    ('已登记能力', '%d 个（caps_registry.BENIGN_CAPS）' % CS['total'], 1),
    ('实现模块', '%d 个（去重）· 由 api.py 路由分支反查' % CS['n_modules'], 1),
    ('模块行数', '{:,} 行'.format(sum(r.get('module_lines') or 0 for r in CS['caps'])), 1),
    ('实测跑通', '%d 个' % CS['by_state']['ok'], 1),
    ('卡授权门', '%d 个 —— 授权只能主人在终端发放' % CS['by_state']['gated'], 0),
    ('需给参数', '%d 个 —— 有实现，如实报缺什么' % CS['by_state']['needs_params'], 0),
]
for m, v in list(CS['modules'].items())[:14]:
    rows.append((str(m).replace('gbt_allinone/', ''),
                 '%d 能力 · %s 行' % (len(v['caps']), '{:,}'.format(v['lines'])), 1))

PAGES = [(59, '能力 → 源码', 'CAP → SOURCE', rows,
          '原先的「能力广场」是我转述的能力清单；这一版改成源码驱动：'
          '登记项来自 caps_registry，实现模块由 api.py 的路由分支反查，'
          'op 表与模块自述直读源码，状态是 140 个能力逐个真调的实测结果。'
          '每条都能追到具体文件与行数，不再有转述环节。')]

t = SRC.read_text(encoding="utf-8")
scene = t[t.index("  /* ===== scene ===== */"):t.index("\n  initScene();")]

old = "      ['严格覆盖审计', p58()],"
assert old in scene, "screens 锚点未命中"
new = old + "\n" + "\n".join("      ['%s', p%d()]," % (zh, n) for n, zh, _, _, _ in PAGES)
scene = scene.replace(old, new, 1)
scene = scene.replace("五十六块面板 · 浏览器与云电脑已补 · 品牌 Logo 已接入",
                      "五十六块面板 · 能力广场改为源码驱动 · 品牌 Logo 已接入")

trimmed = scene.rstrip()
cut = trimmed.rfind("}")
scene = (trimmed[:cut] +
         "\n\n    /* 署名（不可删除、不可篡改归属） */\n"
         "    addNote(40, maxY() + 34, UI_STRINGS.signatureTag, UI_STRINGS.signature);\n"
         "  }" + scene[len(trimmed):])

pagejs = "\n".join(
    "  function p%d() { return corePage_('%s', '%s', %s, '%s'); }" % (
        n, zh, en,
        "[" + ",".join("['%s','%s',%d]" % (a.replace("'", "\\'"), b.replace("'", "\\'"), c)
                       for a, b, c in rws) + "]",
        note.replace("'", "\\'"))
    for n, zh, en, rws, note in PAGES)
scene += "\n\n" + pagejs + "\n"

import re as _re  # noqa: E402
t = t.replace("无限画布 V17", "无限画布 V18")
t = _re.sub(r"\bV17\b", "V18", t)
t = t.replace("V18 · 50 面板 / 58 画布页 · 原生浏览器与云电脑已补",
              "V18 · 55 面板 / 59 画布页 · 能力广场改为源码驱动")
a = t.index("  /* ===== scene ===== */")
b = t.index("\n  initScene();")
t = t[:a] + scene.rstrip("\n") + t[b:]

OUT.write_text(t, encoding="utf-8")
print("写出:", OUT.name, "%.1f KB" % (OUT.stat().st_size / 1024))
print("页数: 59（原 58 + 1）")
