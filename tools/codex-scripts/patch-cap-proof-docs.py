# -*- coding: utf-8 -*-
"""把「能力自证」三份文档/图里的旧口径改成三路真跑合并后的新口径（CRLF 安全）。

旧：221 通过 / 15 要票 / 26 需参数 / 79 写口未跑（合计 341）
新：286 通过 / 32 要票 / 14 缺输入 / 1 缺依赖 / 8 高危未跑（合计 341）
每处替换都断言命中，没命中就退出（不静默跳过）。
用法：py -3.12 tools/codex-scripts/patch-cap-proof-docs.py
"""
import pathlib
import sys
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        pass

ROOT = pathlib.Path(__file__).resolve().parents[2]
REL = ROOT / "outputs" / "open-source-release"


def load(p):
    return p.read_text(encoding="utf-8").replace("\r\n", "\n")


def save(p, t):
    p.write_text(t, encoding="utf-8", newline="\n")


def sub(t, old, new, tag):
    if old not in t:
        print("!! 没命中：", tag)
        sys.exit(2)
    print("   命中：", tag)
    return t.replace(old, new, 1)


p07 = REL / "docs" / "07-capability-proof.md"
t = load(p07)
t = sub(t,
        "> 全部读数来自 `tools/codex-scripts/probe-caps-live.py` 的一次真跑，机器可读结果在\n"
        "> [`../data/capability-live-test.json`](../data/capability-live-test.json)。",
        "> 读数由**三路真跑**合成（只读位空参真调 / 需参数位带真参真跑 / 写口位隔离 store 真跑），\n"
        "> 由 `tools/codex-scripts/gen-capability-proof.py` 合并成一份账：\n"
        "> [`../data/capability-live-test.json`](../data/capability-live-test.json)（**341 位一位一行，不重叠**）。",
        "页首来源")
t = sub(t,
        "| 只读 且 无需参数 | **真调一次**（空 payload），记耗时/状态 | 这是\"能力属实\"最硬的证据 |\n"
        "| 只读 但 需要业务参数 | **不跑**，标 `needs_params` | 不瞎编参数（瞎编出来的绿是假绿） |\n"
        "| 写盘 / 花钱 / 出网 | **一律不跑**，标 `needs_auth` | 开源测试不越授权门 |",
        "| 只读 且 无需参数 | **真调一次**（空 payload），记耗时/状态；超时上限 90s（慢≠坏） | 这是\"能力属实\"最硬的证据 |\n"
        "| 需参数 | **带人写的样本参数真跑**（不自动猜、不瞎编） | 瞎编参数的绿是假绿；缺参就记 `needs_input` |\n"
        "| 写口 | **隔离 store（临时目录）里真跑**；要票的当场拒；高危 8 位不跑 | 不拿主人的仓库当试验场，也不假装跑过 |",
        "规则表")
t = sub(t, "## 二、读数（一次全量跑，231 秒）", "## 二、读数（三路真跑合成）", "读数标题")
t = sub(t,
        "| 结果 | 位数 | 说明 |\n|---|---:|---|\n"
        "| ✅ 真调通过 | **221** | 其中 4 位是\"慢但通\"（见下节），初测超时、给足时间后全绿 |\n"
        "| 🔒 只读但要票 | **15** | 门如实拒绝，并带回**缺哪个作用域** |\n"
        "| ⚙ 需参数 | **26** | 不瞎编，如实记 |\n"
        "| 🚫 写口未跑 | **79** | 不越授权门 |\n"
        "| ❌ 仍未通 | **0** | — |\n\n"
        "> 合计 221 + 15 + 26 + 79 = **341**，没有\"没归类\"的。",
        "| 结果 | 位数 | 说明 |\n|---|---:|---|\n"
        "| ✅ 真跑通过 | **286** | 只读 236（含 90s 超时下真调）+ 需参数 26（带真参）+ 写口 24（隔离 store）… 逐位见 JSON |\n"
        "| 🔒 要票未跑 | **32** | 门如实拒绝，并带回**缺哪个作用域**；票在主人手里 |\n"
        "| ⚙ 缺输入未跑 | **14** | 缺业务参数（缺 q / text / data / 轮次…），不瞎编 |\n"
        "| 🧩 缺依赖未跑 | **1** | `n8n_wf`：本机 n8n 没起（HTTP 0） |\n"
        "| 🚫 高危未跑 | **8** | 会写生产交付区/起进程/出网/改版本库/渲染大件 |\n"
        "| ❌ 失败 | **0** | — |\n\n"
        "> 合计 286 + 32 + 14 + 1 + 8 = **341**，一位不多一位不少（生成器里写死这个断言，对不上就退出）。",
        "读数表")
t = sub(t,
        "**\"只读但要票\"的 15 位不是失败，是结构在生效**：",
        "**\"要票\"那 32 位不是失败，是结构在生效**（下面列出监控账里那 15 位的票种；其余 17 位见 JSON）：",
        "要票说明")
save(p07, t)
print("07 已更新")

# fig-caps 的文案与数值源都改到 v2
pf = ROOT / "tools" / "codex-scripts" / "render-test-figures.py"
t = load(pf)
t = sub(t, '    ok = cnt.get("ok", 0)\n    denied = cnt.get("denied", 0)\n'
           '    need_p = cnt.get("needs_params", 0)\n'
           '    need_a = cnt.get("needs_auth", 0)\n'
           '    slow = cnt.get("timeout", 0) + cnt.get("failed", 0) + cnt.get("exception", 0)',
        '    ok = cnt.get("ok", 0)\n    denied = cnt.get("denied", 0)\n'
        '    need_p = cnt.get("needs_params", 0)\n'
        '    need_a = cnt.get("needs_auth", 0)\n'
        '    dep = cnt.get("needs_dependency", 0)\n'
        '    slow = cnt.get("timeout", 0) + cnt.get("failed", 0) + cnt.get("exception", 0)',
        "fig-caps 取数")
t = sub(t,
        '        ("真调通过", str(ok), "空 payload 真跑", GREEN_L),\n'
        '        ("只读但要票", str(denied), "门如实拒（附作用域）", BLUE),\n'
        '        ("需参数", str(need_p), "不瞎编，如实记", AMBER),\n'
        '        ("写口未跑", str(need_a), "不越授权门", DIM),\n',
        '        ("真跑通过", str(ok), "只读+带参+写口", GREEN_L),\n'
        '        ("要票未跑", str(denied), "缺哪张票说得出", BLUE),\n'
        '        ("缺输入", str(need_p), "不瞎编参数", AMBER),\n'
        '        ("高危未跑", str(need_a), "不拿真仓库试", DIM),\n',
        "fig-caps 卡片")
t = sub(t,
        '    dd.text((28, 232), "其余：慢但通/待修 %d 位（详见 docs/07-capability-proof.md 的逐条根因表）" % slow,\n'
        '            font=font(14), fill=TXT)\n'
        '    dd.text((28, 262), "门后证据 ≠ 失败：被门拒的 15 位正好证明「写口位必须人给票」这条结构在生效。",\n'
        '            font=font(14), fill=DIM)',
        '    dd.text((28, 232), "另：缺依赖 %d 位（n8n 没起）· 失败 %d 位 · 三态合计 %d = %d（生成器断言）"\n'
        '            % (dep, slow, ok + denied + need_p + need_a + dep + slow, total),\n'
        '            font=font(14), fill=TXT)\n'
        '    dd.text((28, 262), "门后证据 ≠ 失败：要票那 %d 位正好证明「危险动作必须人给票」这条结构在生效。" % denied,\n'
        '            font=font(14), fill=DIM)',
        "fig-caps 说明行")
save(pf, t)
print("render-test-figures 已更新")
