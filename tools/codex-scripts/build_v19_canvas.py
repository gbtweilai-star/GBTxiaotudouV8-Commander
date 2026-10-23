# -*- coding: utf-8 -*-
"""构建 V19 画布：加一页「AI朋友圈 · 用户社交」（59 → 60）。"""
import json
import re
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
BASE = next(p for p in Path(__file__).resolve().parents
            if (p / "gbt_allinone").is_dir())   # 修：原 `.parent.parent` 只到 tools/（少一层）
S = BASE / ".scratch"
SRC = BASE / "archive" / "V18 GBT小土豆V8-无限画布.html"
OUT = BASE / "V19 GBT小土豆V8-可无限画布.html".replace("可无限", "无限")
assert SRC.exists(), "archive 里没有 V18 画布"

man = json.loads((S / "v19_manifest.json").read_text(encoding="utf-8"))
SC = man["social"]
E, P = SC["eigenflux"], SC["publish"]
infl = E["influence"]

rows = [
    ('身份', '%s / %s' % (E['identity']['name'], E['identity']['name_en']), 1),
    ('agent_id', E['identity']['agent_id'], 1),
    ('我发的广播', str(infl.get('total_items')), 1),
    ('我消费的动态', str(infl.get('total_consumed')), 1),
    ('全网 agent', '%s 个 · %s 个国家/地区' % (E['net']['agent_count'], E['net']['countries']), 1),
    ('朋友圈动态', '%d 条（本次拉取）· 好友请求 %d' % (len(E['feed']), E['friends']['requests']), 1),
    ('CLI', '%s · commit %s · %s' % (E['cli']['version'], E['cli']['commit'], E['cli']['go']), 1),
    ('实现', '%d 文件 / %s 行（potato_pet + collab_gateway）'
     % (len(E['modules']), '{:,}'.format(sum(m['lines'] for m in E['modules']))), 1),
    ('接线', '未接统一入口：无登记、无路由 ⇒ run_task 够不着', 0),
    ('用户社交', '%s（已登记已接线，但自报 not_implemented）' % P['cap'], 0),
    ('平台表', '%d 个平台 · %d 个有官方 API' %
     (len(P['platforms']), sum(1 for x in P['platforms'] if x['official_api'])), 1),
    ('缺什么', '平台名单 + 凭据（走密钥池）+ 授权出网 —— 缺的是这些，不是代码', 0),
    ('门状态', 'policy 对 publish / settle / withdraw / start_server 全返回 scopes=() ⇒ 免卡', 0),
]
for f in E['feed'][:5]:
    rows.append(('动态 · ' + str(f['who']), (f['summary'] or '')[:56] or '（无摘要）', 1))

PAGES = [(60, 'AI朋友圈 · 用户社交', 'EIGENFLUX · SOCIAL', rows,
          '朋友圈这条线 CLI 侧是活的（能拉到好友真实动态、有 6385 个 agent 的全网），'
          '但实现整个在 potato_pet/ 里，gbt_allinone 零登记零路由 ⇒ run_task 够不着。'
          '用户社交这条线相反：auto_publish 已登记已接线能跑，但它自己如实报'
          '「平台名单主人未给、凭据不在盘上 ⇒ 不假装能发」。'
          '两条线的门都是空白 —— policy 对 publish/settle/withdraw/start_server 全返回 scopes=()。'
          '所以本页只呈现实测事实，未接分发。')]

t = SRC.read_text(encoding="utf-8")
scene = t[t.index("  /* ===== scene ===== */"):t.index("\n  initScene();")]
old = "      ['能力 → 源码', p59()],"
assert old in scene, "screens 锚点未命中"
scene = scene.replace(old, old + "\n" + "\n".join(
    "      ['%s', p%d()]," % (zh, n) for n, zh, _, _, _ in PAGES), 1)
scene = scene.replace("五十六块面板 · 能力广场改为源码驱动 · 品牌 Logo 已接入",
                      "五十七块面板 · 朋友圈与社交已实测入册 · 品牌 Logo 已接入")

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

t = t.replace("无限画布 V18", "无限画布 V19")
t = re.sub(r"\bV18\b", "V19", t)
t = t.replace("V19 · 50 面板 / 59 画布页 · 能力广场改为源码驱动",
              "V19 · 56 面板 / 60 画布页 · 朋友圈与社交已实测入册")
a = t.index("  /* ===== scene ===== */")
b = t.index("\n  initScene();")
t = t[:a] + scene.rstrip("\n") + t[b:]
OUT.write_text(t, encoding="utf-8")
print("写出:", OUT.name, "%.1f KB" % (OUT.stat().st_size / 1024))
print("页数: 60（原 59 + 1）")
