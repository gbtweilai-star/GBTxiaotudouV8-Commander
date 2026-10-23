#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""规程缺口**补法排序**（D3 的决策依据）—— 只读。

已有 `spec-gap-scan.py` 回答「缺哪些位」（149 位 / 30 域）。但"先补哪个"需要第二个信号：
**这个位到底有人用吗**。本件从审计账（`gbt_allinone/store/audit.jsonl`，1.18M 行）现数
每个 kind 的**真调用次数**，再与缺口清单做差集，输出一张"省力顺序"表：

  影响大（被真调用过）+ 便宜（该域缺得少） → 先补
  影响小（从没被调用）+ 贵（该域缺很多）     → 后补

口径写死：
  · 调用次数只数 `event == "call"`（不看 ok / denied —— "有没有人试过"才是需求信号）；
  · 一次流式扫描，不把 205MB 读进内存；
  · 缺口来自 `state/spec-gap-scan.json`（必须先跑过 spec-gap-scan）。

用法：py -3.14 tools/codex-scripts/spec-gap-priority.py [--top 40]
"""
import argparse
import json
import os
import sys
import time

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        pass

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SCAN = os.path.join(ROOT, "state", "spec-gap-scan.json")
AUDIT = os.path.join(ROOT, "gbt_allinone", "store", "audit.jsonl")
OUT_MD = os.path.join(ROOT, "outputs", "spec-gap", "补法顺序.md")
OUT_JSON = os.path.join(ROOT, "state", "spec-gap-priority.json")


def count_calls():
    n, kinds, other, err = 0, {}, {}, None
    try:
        with open(AUDIT, encoding="utf-8", errors="replace") as f:
            for ln in f:
                if '"call"' not in ln:
                    continue
                n += 1
                try:
                    j = json.loads(ln)
                except ValueError:
                    continue
                k = (j.get("meta") or {}).get("kind")
                # 🔴 2026-10-22 第一次跑就炸（留痕）：审计里有些行的 `meta.kind` 是**对象**
                #    （不是字符串）⇒ 直接当 dict 键会 TypeError。不是"审计坏了"，是读数形状不齐。
                #    口径：只认字符串 kind；非字符串的记进 `other` 计数，不静默丢。
                if isinstance(k, str) and k:
                    kinds[k] = kinds.get(k, 0) + 1
                elif k is not None:
                    other[k if isinstance(k, (int, float)) else str(type(k).__name__)] = 1
    except OSError as e:
        err = str(e)
    return n, kinds, other, err


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--top", type=int, default=40)
    a = ap.parse_args()
    if not os.path.isfile(SCAN):
        print("先跑 spec-gap-scan.py（缺 %s）" % SCAN)
        return 2
    scan = json.load(open(SCAN, encoding="utf-8"))
    t0 = time.time()
    n_call, calls, other, err = count_calls()
    if err:
        print("审计读不到：%s ⇒ 只按域缺口排（无影响信号）" % err)

    rows = []
    for r in scan.get("rows") or []:
        for cap in r.get("missing") or []:
            rows.append({"cap": cap, "domain": r["domain"], "domain_gap": r["missing_count"],
                         "domain_caps": r["caps"], "calls": calls.get(cap, 0)})
    # 排序：先按"被真调用过"（降序），再按该域缺得少（升序=便宜），最后按名字
    rows.sort(key=lambda x: (-x["calls"], x["domain_gap"], x["cap"]))
    used = [x for x in rows if x["calls"] > 0]
    untouched = [x for x in rows if x["calls"] == 0]
    out = {
        "at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "audit_call_lines": n_call, "audit_kinds": len(calls),
        "gap_total": len(rows), "gap_used": len(used), "gap_untouched": len(untouched),
        "elapsed_s": round(time.time() - t0, 1),
        "top": rows[:a.top],
        "domains": {},
    }
    by_dom = {}
    for x in rows:
        d = by_dom.setdefault(x["domain"], {"gap": 0, "used": 0, "calls": 0})
        d["gap"] += 1
        if x["calls"]:
            d["used"] += 1
            d["calls"] += x["calls"]
    out["domains"] = by_dom
    os.makedirs(os.path.dirname(OUT_JSON), exist_ok=True)
    tmp = OUT_JSON + ".tmp"
    with open(tmp, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(out, fh, ensure_ascii=False, indent=1)
        fh.write("\n")
    os.replace(tmp, OUT_JSON)

    os.makedirs(os.path.dirname(OUT_MD), exist_ok=True)
    lines = ["# 规程缺口 · 补法顺序（D3 决策依据）", "",
             "> 生成：`py -3.14 tools/codex-scripts/spec-gap-priority.py` · %s" % out["at"],
             "> 影响信号：审计账里 `event=call` 的**真调用次数**（%d 条 call 记录 / %d 个 kind）；"
             % (n_call, len(calls)),
             "> 缺口总数 **%d**：其中**被真调用过** **%d**，**从没被调用** %d。"
             % (out["gap_total"], out["gap_used"], out["gap_untouched"]),
             "", "## 先补这些（被真调用过，按调用次数降序）", "",
             "| 能力位 | 域 | 调用次数 | 该域缺口 |", "|---|---|---|---|"]
    for x in used[:max(a.top, 60)]:
        lines.append("| `%s` | %s | %d | %d/%d |"
                     % (x["cap"], x["domain"], x["calls"], x["domain_gap"], x["domain_caps"]))
    lines += ["", "## 逐域：缺口 vs 其中被用过的", "",
              "| 域 | 缺口 | 其中被调用过 | 这些位的调用次数合计 |", "|---|---|---|---|"]
    for d, v in sorted(by_dom.items(), key=lambda kv: (-kv[1]["used"], -kv[1]["gap"])):
        lines.append("| %s | %d | **%d** | %d |" % (d, v["gap"], v["used"], v["calls"]))
    if untouched:
        lines += ["", "## 从没被调用过的缺口（%d 位：后补，或标「不需要规程」）" % len(untouched), ""]
        lines.append("、".join("`%s`" % x["cap"] for x in untouched[:120]))
    tmp_md = OUT_MD + ".tmp"
    with open(tmp_md, "w", encoding="utf-8", newline="\n") as fh:
        fh.write("\n".join(lines) + "\n")
    os.replace(tmp_md, OUT_MD)

    print("缺口 %d 位 · 被真调用过 **%d** · 从没调用 %d（审计 %d 条 call / %d kind，扫 %.1fs）"
          % (out["gap_total"], out["gap_used"], out["gap_untouched"], n_call, len(calls), out["elapsed_s"]))
    for x in used[:12]:
        print("  先补：%-24s 域=%-12s 调用=%d" % (x["cap"], x["domain"], x["calls"]))
    print("  人读：%s" % OUT_MD)
    return 0


if __name__ == "__main__":
    sys.exit(main())
