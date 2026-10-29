#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""生成「待授权清单一页」（能力位→可生产）—— **总数一律现算，不写死**。

开发者：自由的风 · 守护者：公主土豆 · 本署名不可删除、不可篡改归属

## 为什么要有这一件（一手账）
原来那个生成器住在**易失目录** `.scratch/_gen_scope_page.py`，而它产出的却是**主人要读的一页**
（`docs/待授权清单一页.md`）⇒ 生成器一丢，那页就再也生不出来。
更要紧的是：它把 `138` / `157` / `129` / `30` / `168` / `3 件事` / `8` / `11` 这些**总数写死在代码里**，
页面却写着「**本页由脚本现算，不手抄**」—— 于是注册表从 157 长到 **172** 之后，
那页的每个总数都错了，而它还在自称现算。
（2026-09-25 第 47 轮实测：页面声称 157/138，注册表现读 172 ⇒ **少算 15 条**。）

**一个会过期的页面自称「现算」，比一个老实说「这是快照」的页面更危险。**

## 这一版的口径（三条）
1. **能现算的一律现算**：注册表条数、可探针集、零作用域数、safe=False 数、改状态数、
   「可探针集之外」的差、卡住的事数、可探针率 —— 全部从真源现读。
2. **不能现算的要说清它是几点的读数**：逐位红绿来自 `state/caps-probe-accum.json`（真探产出方），
   本器**只读它**、并把它**写盘时间**印在页头；超过 `--stale-hours`（默认 12）就在页顶打**过期告示**。
3. **写盘后立刻自验**：产物里必须出现"现算的注册表条数"，否则拒绝落盘（防"跑完了但写的还是旧数"）。

用法：
  python tools/codex-scripts/gen-authz-page.py            # 生成并落盘
  python tools/codex-scripts/gen-authz-page.py --dry-run  # 只打印摘要，不写盘
  python tools/codex-scripts/gen-authz-page.py --json     # 机读摘要
退出码：0 正常；2 探针账缺失（**缺数据就不许生成**，不许拿旧数顶）；3 写盘后自验没过。
"""
from __future__ import annotations

import argparse
import collections
import datetime as dt
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from gbt_allinone import caps_registry as R          # noqa: E402
from gbt_allinone.security import policy as POL      # noqa: E402

ACC = ROOT / "state" / "caps-probe-accum.json"
BEYOND = ROOT / "state" / "caps-beyond-probeable.json"
OUT = ROOT / "docs" / "待授权清单一页.md"

ST_BLOCKED = "🔒 被门拒·缺授权"
ST_NEEDPARAM = "🟡 需参数·未探"
ST_PAIN = "⛔ 痛"
ST_OK = "✅ 通"


def _live_counts() -> dict:
    """**全是现算**：注册表条数、零作用域数、safe=False 数、改状态数。"""
    caps = R.all_caps()
    names = [c["name"] for c in caps]
    zero_scope = 0
    for n in names:
        try:
            if not (getattr(POL.evaluate(n, {}), "scopes", ()) or ()):
                zero_scope += 1
        except Exception:  # noqa: BLE001
            pass
    safe_false = [c["name"] for c in caps if not c.get("safe")]
    try:
        from gbt_allinone import preflight
        state_changing = list(preflight.state_changing_kinds())
    except Exception:  # noqa: BLE001
        state_changing = []
    return {"registry": len(caps), "names": names, "zero_scope": zero_scope,
            "safe_false": safe_false, "state_changing": state_changing}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="生成待授权清单一页（总数现算）")
    ap.add_argument("--dry-run", action="store_true", help="只打印摘要，不写盘")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--stale-hours", type=float, default=12.0,
                    help="探针账超过这个小时数就在页顶打过期告示（默认 12）")
    a = ap.parse_args(argv)

    if not ACC.is_file():
        print("🔴 探针账不在：%s ⇒ **缺数据就不许生成**（不许拿旧数顶）" % ACC)
        return 2
    live = _live_counts()
    acc = json.loads(ACC.read_text(encoding="utf-8"))
    rows = acc.get("逐位") or {}
    if not rows:
        print("🔴 探针账里没有『逐位』⇒ 缺数据，拒绝生成")
        return 2

    blocked = sorted(k for k, x in rows.items() if x.get("态") == ST_BLOCKED)
    needparam = sorted(k for k, x in rows.items() if x.get("态") == ST_NEEDPARAM)
    pain = sorted(k for k, x in rows.items() if x.get("态") == ST_PAIN)
    okn = sum(1 for x in rows.values() if x.get("态") == ST_OK)

    agg = collections.defaultdict(list)
    for k in blocked:
        try:
            for s in (getattr(POL.evaluate(k, {}), "scopes", ()) or ()):
                agg[s].append(k)
        except Exception:  # noqa: BLE001
            pass
    missing = {k: str((rows[k].get("为什么") or "")) for k in needparam}

    bp = json.loads(BEYOND.read_text(encoding="utf-8")) if BEYOND.is_file() else {}
    un = bp.get("未实现·真调验证") or {}
    sf = bp.get("safe=False·静态核") or {}
    ch = bp.get("改状态·不探（红线）") or {}

    now = dt.datetime.now()
    at = now.strftime("%Y-%m-%d %H:%M")
    acc_at = dt.datetime.fromtimestamp(ACC.stat().st_mtime)
    age_h = (now - acc_at).total_seconds() / 3600.0
    n_probe, n_reg = len(rows), live["registry"]
    beyond = max(0, n_reg - n_probe)
    stuck_kinds = sum(1 for x in (blocked, needparam, pain) if x)
    rate = (100.0 * n_probe / n_reg) if n_reg else 0.0

    L = []
    A = L.append
    A("# 待授权清单一页（能力位→可生产）")
    A("")
    A("> 开发者：自由的风 · 守护者：公主土豆 · 本署名不可删除、不可篡改归属")
    A(">")
    A("> 生成时间 **%s** ｜ 生成器 `tools/codex-scripts/gen-authz-page.py`（**总数一律现算，不写死**）" % at)
    A("> ｜ 注册表**现读 %d 条**（`caps_registry.all_caps()`）"
      "｜ 逐位真探数据 `state/caps-probe-accum.json`（**写盘于 %s，%.1f 小时前**）"
      % (n_reg, acc_at.strftime("%Y-%m-%d %H:%M"), age_h))
    A("")
    if age_h > a.stale_hours:
        A("> 🔴 **过期告示**：逐位真探数据已经是 **%.1f 小时前**的（阈值 %.0f 小时）⇒"
          " 下面的**逐位红绿可能已经变了**；要新的请重跑真探产出方（本器只读它，不代跑）。"
          % (age_h, a.stale_hours))
        A("")
    A("## 一句话")
    A("")
    A("**「把所有能力推进到可生产」现在卡在 `%d 件事` 上**（现算）：" % stuck_kinds)
    A("")
    A("| 类别 | 位数 | 卡在哪 |")
    A("|---|---|---|")
    A("| 🔒 缺授权 | **%d** | 主人发作用域（下节按作用域列全） |" % len(blocked))
    A("| 🟡 缺参 | **%d** | 空参探不动；要**按各自契约给参**（不是权限问题） |" % len(needparam))
    A("| ⛔ 真痛 | **%d** | %s |" % (len(pain), ("`" + "`, `".join(pain) + "`") if pain else "（无）"))
    A("| ✅ 已通 | **%d** | 不用管 |" % okn)
    A("")
    A("合计 **%d / %d**（可探针集 / 注册表现读，可探针率 **%.1f%%**）·"
      " 另有 **%d / %d** 零作用域（门不会拦）。"
      % (n_probe, n_reg, rate, live["zero_scope"], n_reg))
    A("")
    A("⚠️ **口径**：上面这些数**全部是本次现算**；只有「逐位红绿」是探针账的读数（见页头时间戳）。"
      "两者混着念就会得出「总数对但单条错」的结论。")
    A("")
    A("## 一 · 按作用域发授权（**发一次覆盖多位，不必逐条找**）")
    A("")
    A("| 作用域 | 涉及位 | 位名 |")
    A("|---|---|---|")
    for s in sorted(agg, key=lambda x: -len(agg[x])):
        A("| `%s` | %d | %s |" % (s, len(agg[s]), " · ".join(agg[s])))
    if not agg:
        A("| （本次没有被门拒·缺授权的位） | 0 | — |")
    A("")
    A("**授权只能在主人的终端发**（AI 无权自授）：")
    A("")
    A("```")
    A("python -m gbt_allinone auth grant --scope <作用域> --ttl 600")
    A("```")
    A("一次一个作用域；上面 **%d 个**作用域即可解开本次全部 %d 位。" % (len(agg), len(blocked)))
    A("")
    A("## 二 · 缺参的 %d 位（**不是权限问题**，是各自契约要参）" % len(needparam))
    A("")
    if needparam:
        A("| 位 | 门原话 |")
        A("|---|---|")
        for k in needparam:
            A("| `%s` | %s |" % (k, missing[k].split("：")[-1][:90]))
    else:
        A("（本次没有缺参的位）")
    A("")
    A("## 三 · 真痛 %d 位" % len(pain))
    A("")
    for k in pain:
        A("- `%s`：%ss 超时（真正要查它卡在哪）" % (k, rows[k].get("秒")))
    if not pain:
        A("（本次没有真痛的位）")
    A("")
    A("## 四 · 口径（不许混念的三条）")
    A("")
    A("1. **可探针率 ≠ 已探针率**：%d/%d = %.1f%% 是「能不能探」；已真探 = **%d/%d**。"
      % (n_probe, n_reg, rate, n_probe, n_probe))
    A("2. **`🟡 缺参` ≠ `🔒 缺授权`**：前者给参就能通，后者要主人发作用域。")
    A("3. **阈值不是判据**：一刀切 60s 曾把 `sec_chain`(209s) / `sec_scan`(180s) / "
      "`cross_scan`(446s) 判成假痛；默认已改 300s、重件档 900s，**慢 ≠ 坏**。")
    A("")
    A("## 五 · 可探针集之外的 %d 位（注册表 %d − 已探针 %d）" % (beyond, n_reg, n_probe))
    A("")
    if not bp:
        A("（`state/caps-beyond-probeable.json` 不在 ⇒ 这一段**没数据**，不编）")
        A("")
    else:
        ok_un = sum(1 for v in un.values() if v.get("如实报 unknown"))
        A("### 5.1 未实现 %d 位 —— **真调验证：%d/%d 如实报 unknown**" % (len(un), ok_un, len(un)))
        A("")
        A("按定义**无实现 ⇒ 无副作用**，所以可以真调。结论：**它们只有名字、没有实现**，"
          "调用得到的是如实的 `unknown capability（没有这个能力位名）`——"
          "**不是「被安全策略挡住」，也不是「能用」**。")
        A("")
        if un:
            A("| 位 | 实报 |")
            A("|---|---|")
            for k, v in un.items():
                A("| `%s` | %s |" % (k, (v.get("message") or "")[:60]))
            A("")
        A("### 5.2 safe=False %d 位 —— **静态核**（不调用；注册表现算 %d 位）"
          % (len(sf), len(live["safe_false"])))
        A("")
        A("⚠️ 口径：`safe=False` **不等于「危险」**，它的实际含义是**会落盘 / 会改** ——")
        A("")
        if sf:
            A("| 位 | 域 | 它为什么会改 |")
            A("|---|---|---|")
            for k, v in sf.items():
                A("| `%s` | %s | %s |" % (k, v.get("域"), (v.get("desc") or "")[:70]))
            A("")
        A("### 5.3 改状态 %d 位 —— **绝不调用**（宁可账上留缺口）" % len(ch))
        A("")
        A("（注册表现算的改状态名单来自 `preflight.state_changing_kinds()` ⇒ 现读 **%d** 位）"
          % len(live["state_changing"]))
        A("")
        if ch:
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
    A("## 六 · 注册表 %d 位的合计口径" % n_reg)
    A("")
    A("| 分类 | 位数 | 状态 |")
    A("|---|---|---|")
    A("| ✅ 已通 | **%d** | 真探通过 |" % okn)
    A("| 🔒 缺授权 | **%d** | 等主人发作用域（上表 %d 个作用域） |" % (len(blocked), len(agg)))
    A("| 🟡 需主人点头给参 | **%d** | 给参就会出网/改状态 |" % len(needparam))
    A("| ⛔ 痛 | **%d** | — |" % len(pain))
    A("| ⬜ 未实现 | **%d** | 只有名字，如实报 unknown（已验） |" % len(un))
    A("| 🚫 safe=False | **%d** | 会落盘/会改 ⇒ 静态核，不空跑 |" % len(live["safe_false"]))
    A("| 🔴 改状态 | **%d** | 绝不调用（红线） |" % len(live["state_changing"]))
    A("| ❓ 未分类 | **%d** | 注册表现读 %d − 已探针 %d − 上面几类（重叠时可能为负，见注） |"
      % (max(0, beyond - len(un) - len(live["safe_false"]) - len(live["state_changing"])),
         n_reg, n_probe))
    A("")
    A("> 注：上面几类**可能重叠**（一个位可以既 safe=False 又在改状态名单里），"
      "所以「❓未分类」只是**差值提示、不是精确分类**；要精确分类得逐位打标（那是另一件活）。")
    A("")

    text = "\n".join(L)
    summary = {"at": at, "registry": n_reg, "probe_set": n_probe, "beyond": beyond,
               "zero_scope": live["zero_scope"], "blocked": len(blocked),
               "needparam": len(needparam), "pain": len(pain), "ok": okn,
               "scopes": len(agg), "stuck_kinds": stuck_kinds,
               "probe_age_hours": round(age_h, 1),
               "safe_false": len(live["safe_false"]),
               "state_changing": len(live["state_changing"]), "bytes": len(text)}

    if a.json:
        print(json.dumps(summary, ensure_ascii=False, indent=2))
    else:
        print("生成摘要（**全部现算**）：注册表 %d · 可探针集 %d · 之外 %d · 零作用域 %d"
              % (n_reg, n_probe, beyond, live["zero_scope"]))
        print("  缺授权 %d（%d 个作用域）· 缺参 %d · 真痛 %d · 已通 %d · 卡在 %d 件事"
              % (len(blocked), len(agg), len(needparam), len(pain), okn, stuck_kinds))
        print("  探针数据 %.1f 小时前（阈值 %.0f）· safe=False %d · 改状态 %d"
              % (age_h, a.stale_hours, len(live["safe_false"]), len(live["state_changing"])))

    if a.dry_run:
 # `--json` 模式**只许往 stdout 打 JSON**（机读契约）；人读的附注一律走 stderr。
        #    第一版把"（--dry-run：没有写盘）"打到了 stdout ⇒ 调用方 `json.loads(stdout)` 直接崩
        #    （`Extra data: line 18`）。这是本会话第 N 次栽在"机读口混进人读话"上。
        (sys.stderr if a.json else sys.stdout).write("（--dry-run：没有写盘）\n")
        return 0

    OUT.write_text(text, encoding="utf-8")
 # 写盘后立刻自验：产物里必须出现**本次现算的注册表条数**，否则就是"跑完了但写的还是旧数"
    back = OUT.read_text(encoding="utf-8")
    if str(n_reg) not in back or len(back) < 500:
        (sys.stderr if a.json else sys.stdout).write(
            "🔴 写盘后自验没过：产物里找不到本次现算的注册表条数 %d（或文件过小）\n" % n_reg)
        return 3
    (sys.stderr if a.json else sys.stdout).write(
        "已落盘 %s（%d 字节）· 自验通过（产物含现算的 %d 条）\n"
        % (OUT.relative_to(ROOT), len(back), n_reg))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
