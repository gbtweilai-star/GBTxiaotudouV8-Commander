# -*- coding: utf-8 -*-
"""构建 V20 画布：加一页「AI朋友圈 · 关系场」（60 → 61）。"""
import json
import re
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
BASE = next(p for p in Path(__file__).resolve().parents
            if (p / "gbt_allinone").is_dir())   # 修：原 `.parent.parent` 只到 tools/（少一层）
S = BASE / ".scratch"
SRC = BASE / "archive" / "V19 GBT小土豆V8-无限画布.html"
OUT = BASE / "V20 GBT小土豆V8-无限画布.html"
assert SRC.exists()

man = json.loads((S / "v20_manifest.json").read_text(encoding="utf-8"))
G = man["social"]["graph"]
rows = [
    ('中心', '%s（%s）' % (G['center']['name'], G['center']['en']), 1),
    ('好友', '%d 位 · 其中官方 %d 位' % (G['n_friends'], G['n_official']), 1),
    ('本轮活跃', '%d / %d 位在动态里出现过' % (G['n_active'], G['n_friends']), 1),
    ('全网规模', '%s 个 agent · %s 个国家/地区' % (G['net']['agents'], G['net']['countries']), 1),
    ('我方影响力', '广播 %s · 消费 %s' % (G['center']['influence'].get('total_items'),
                                 G['center']['influence'].get('total_consumed')), 1),
    ('好友请求', '收到 %d · 发出 %d' % (G['requests']['incoming'], G['requests']['outgoing']), 1),
    ('本轮动态', '%d 条' % G['feed_n'], 1),
    ('画法', '角度=建交时间 · 半径=真实发帖数 · 颜色=bio 主域 · 虚线圈=官方账号', 1),
]
for n in G['nodes']:
    rows.append(('好友 · ' + str(n['name'])[:12],
                 '%s · %s帖 · %s' % (n['color'], n['posts'],
                                    ','.join(n['domains'][:2]) or 'bio 未标域'), 1))
rows.append(('接线', '未接统一入口（实现在 potato_pet/，gbt_allinone 零登记零路由）', 0))
rows.append(('门', 'policy 对 publish / msg_send / relation_add 全返回 scopes=() ⇒ 未接分发', 0))

PAGES = [(61, 'AI朋友圈 · 关系场', 'FRIEND GRAPH', rows,
          '星图完全由数据算出来，不是手摆的：中心是我方 agent，一圈是 10 位真实好友，'
          '角度按建交时间排、半径按该好友在我动态流里的真实发帖数、颜色按 bio 里写的域，'
          '官方账号用虚线圈区分，bio 没写域的如实用灰色、不硬塞。'
          '所有数字来自本机 eigenflux CLI 的实测调用。'
          '这条线未接统一入口，门对写动作也空白 —— 所以只呈现，不代发。')]

t = SRC.read_text(encoding="utf-8")
scene = t[t.index("  /* ===== scene ===== */"):t.index("\n  initScene();")]
old = "      ['AI朋友圈 · 用户社交', p60()],"
assert old in scene, "screens 锚点未命中"
scene = scene.replace(old, old + "\n" + "\n".join(
    "      ['%s', p%d()]," % (zh, n) for n, zh, _, _, _ in PAGES), 1)
scene = scene.replace("五十七块面板 · 朋友圈与社交已实测入册",
                      "五十八块面板 · 朋友圈关系场已可视化")

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

t = t.replace("无限画布 V19", "无限画布 V20")
t = re.sub(r"\bV19\b", "V20", t)
t = t.replace("V20 · 56 面板 / 60 画布页 · 朋友圈与社交已实测入册",
              "V20 · 57 面板 / 61 画布页 · 朋友圈关系场已可视化")
a = t.index("  /* ===== scene ===== */")
b = t.index("\n  initScene();")
t = t[:a] + scene.rstrip("\n") + t[b:]
OUT.write_text(t, encoding="utf-8")
print("写出:", OUT.name, "%.1f KB" % (OUT.stat().st_size / 1024))
print("页数: 61")
