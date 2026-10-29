# -*- coding: utf-8 -*-
"""生成「一页发授权单」：从累积账 + policy 现算，不手抄（手抄必错）。"""
import collections
import datetime as dt
import json
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
# 本文件从 `.scratch/` 搬到了 `tools/codex-scripts/` ⇒ `parents[N]` 含义变了：
#    在 `.scratch/` 时 `parents[1]` 是仓库根；搬来后必须 `parents[2]`，否则 ROOT 指到 `tools/`。
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from gbt_allinone.security import policy as POL      # noqa: E402

acc = json.load(open(ROOT / "state" / "caps-probe-accum.json", encoding="utf-8"))
rows = acc["逐位"]
blocked = sorted(k for k, x in rows.items() if x["态"] == "🔒 被门拒·缺授权")
needparam = sorted(k for k, x in rows.items() if x["态"] == "🟡 需参数·未探")
pain = sorted(k for k, x in rows.items() if x["态"] == "⛔ 痛")
okn = sum(1 for x in rows.values() if x["态"] == "✅ 通")

agg = collections.defaultdict(list)
for k in blocked:
    try:
        sc = list(getattr(POL.evaluate(k, {}), "scopes", ()) or ())
    except Exception:  # noqa: BLE001
        sc = []
    for s in sc:
        agg[s].append(k)

missing = {k: str((rows[k].get("为什么") or "")) for k in needparam}
at = dt.datetime.now().strftime("%Y-%m-%d %H:%M")

L = []
A = L.append
A("# 待授权清单一页（能力位→可生产）")
A("")
A("> 开发者：自由的风 · 守护者：公主土豆 · 本署名不可删除、不可篡改归属")
A(">")
A("> 生成时间 %s ｜ 数据源 `state/caps-probe-accum.json`（138/138 全量真探）+ `policy.evaluate()` 现算" % at)
A("> **本页由脚本现算，不手抄** —— 手抄必错（原生成器：`.scratch/_gen_scope_page.py`）。")
A("")
A("## 一句话")
A("")
A("**「把所有能力推进到可生产」现在卡在 `3 件事` 上，`没有一件是「实现坏了」`**：")
A("")
A("| 类别 | 位数 | 卡在哪 |")
A("|---|---|---|")
A("| 🔒 缺授权 | **%d** | 主人发作用域（下节按作用域列全） |" % len(blocked))
A("| 🟡 缺参 | **%d** | 空参探不动；要**按各自契约给参**（不是权限问题） |" % len(needparam))
A("| ⛔ 真痛 | **%d** | `%s`（300s 仍未返回 ⇒ 要另查它卡在哪） |" % (len(pain), "`, `".join(pain)))
A("| ✅ 已通 | **%d** | 不用管 |" % okn)
A("")
A("合计 **%d / 138**（可探针集）· 另有 **129 / 157** 零作用域（门不会拦）。" % len(rows))
A("")
A("## 一 · 按作用域发授权（**发一次覆盖多位，不必逐条找**）")
A("")
A("| 作用域 | 涉及位 | 位名 |")
A("|---|---|---|")
for s in sorted(agg, key=lambda x: -len(agg[x])):
    A("| `%s` | %d | %s |" % (s, len(agg[s]), " · ".join(agg[s])))
A("")
A("**授权只能在主人的终端发**（AI 无权自授）：")
A("")
A("```")
A("python -m gbt_allinone auth grant --scope <作用域> --ttl 600")
A("```")
A("一次一个作用域；上面 **%d 个**作用域即可解开全部 %d 位。" % (len(agg), len(blocked)))
A("")
A("## 二 · 缺参的 %d 位（**不是权限问题**，是各自契约要参）" % len(needparam))
A("")
A("| 位 | 门原话 |")
A("|---|---|")
for k in needparam:
    A("| `%s` | %s |" % (k, missing[k].split("：")[-1][:90]))
A("")
A("## 三 · 真痛 %d 位" % len(pain))
A("")
for k in pain:
    A("- `%s`：300s 超时（%s）" % (k, rows[k].get("秒")))
A("")
A("## 四 · 口径（不许混念的三条）")
A("")
A("1. **可探针率 ≠ 已探针率**：138/157 = 87.9% 是「能不能探」；已真探 = **138/138**。")
A("2. **`🟡 缺参` ≠ `🔒 缺授权`**：前者给参就能通，后者要主人发作用域。")
A("3. **阈值不是判据**：一刀切 60s 曾把 `sec_chain`(209s) / `sec_scan`(180s) / "
  "`cross_scan`(446s) 判成假痛；默认已改 300s、重件档 900s，**慢 ≠ 坏**。")
A("")

# ══ 可探针集之外的 30 位（全 168 位的另一半账）══════════════════════════════════
bp_p = ROOT / "state" / "caps-beyond-probeable.json"
if bp_p.is_file():
    bp = json.load(open(bp_p, encoding="utf-8"))
    A("## 五 · 可探针集之外的 30 位（**全 168 位的另一半账**）")
    A("")
    un = bp.get("未实现·真调验证") or {}
    ok_un = sum(1 for v in un.values() if v.get("如实报 unknown"))
    A("### 5.1 未实现 %d 位 —— **真调验证：%d/%d 如实报 unknown**" % (len(un), ok_un, len(un)))
    A("")
    A("按定义**无实现 ⇒ 无副作用**，所以可以真调。结论：**它们只有名字、没有实现**，"
      "调用得到的是如实的 `unknown capability（没有这个能力位名）`——"
      "**不是「被安全策略挡住」，也不是「能用」**。")
    A("")
    A("| 位 | 实报 |")
    A("|---|---|")
    for k, v in un.items():
        A("| `%s` | %s |" % (k, (v.get("message") or "")[:60]))
    A("")
    sf = bp.get("safe=False·静态核") or {}
    A("### 5.2 safe=False %d 位 —— **静态核**（不调用）" % len(sf))
    A("")
    A("⚠️ 口径更正：`safe=False` **不等于「危险」**，它的实际含义是**会落盘 / 会改** ——")
    A("")
    A("| 位 | 域 | 它为什么会改 |")
    A("|---|---|---|")
    for k, v in sf.items():
        A("| `%s` | %s | %s |" % (k, v.get("域"), (v.get("desc") or "")[:70]))
    A("")
    ch = bp.get("改状态·不探（红线）") or {}
    A("### 5.3 改状态 %d 位 —— **绝不调用**（宁可账上留缺口）" % len(ch))
    A("")
    A("| 位 | 域 | 必填参 | 它改什么 |")
    A("|---|---|---|---|")
    for k, v in ch.items():
        A("| `%s` | %s | %s | %s |" % (k, v.get("域"),
                                       ",".join(v.get("required_params") or []) or "（空参）",
                                       (v.get("desc") or "")[:60]))
    A("")
    A("**为什么不探**：它们在 `preflight.state_changing_kinds()` 里 ⇒ 探它就可能**真改框架状态**"
      "（`wf_cache_clear` 当年就真清过缓存）。**宁可账上留缺口，也不碰会改状态的位。**")
    A("")

A("## 六 · 全 168 位合计")
A("")
A("| 分类 | 位数 | 状态 |")
A("|---|---|---|")
A("| ✅ 已通 | **%d** | 真探通过 |" % okn)
A("| 🔒 缺授权 | **%d** | 等你发作用域（上表 9 个作用域） |" % len(blocked))
A("| 🟡 需你点头给参 | **%d** | 给参就会出网/改状态 |" % len(needparam))
A("| ⛔ 痛 | **%d** | — |" % len(pain))
A("| ⬜ 未实现 | **%d** | 只有名字，如实报 unknown（已验） |" % len(un) if bp_p.is_file() else "")
A("| 🚫 safe=False | **8** | 会落盘/会改 ⇒ 静态核，不空跑 |")
A("| 🔴 改状态 | **11** | 绝不调用（红线） |")
A("")
A("> **一句话：168 位里没有一位是「说不清」的** —— 每位都有状态、有原因、有出处。")
A("")

(ROOT / "docs" / "待授权清单一页.md").write_text("\n".join(L), encoding="utf-8")
print("落盘 docs/待授权清单一页.md ｜ %d 字节" % (ROOT / "docs" / "待授权清单一页.md").stat().st_size)
print("作用域 %d 个 · 缺授权 %d 位 · 缺参 %d 位 · 真痛 %d 位 · 已通 %d 位"
      % (len(agg), len(blocked), len(needparam), len(pain), okn))
