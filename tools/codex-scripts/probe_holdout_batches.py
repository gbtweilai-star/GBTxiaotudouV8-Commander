# -*- coding: utf-8 -*-
"""把「留出集命中率」这条**承诺过的测量**补齐：一批一批地量，并只测不动。

背景（第 46 轮）：`tentacle/bridge.py` 里写着三批"留出/全新句子"，
旁边有主人定的纪律：
  · 留出集（`HELD_OUT_PHRASES`）："先写死，再动别名表。判据：≥80% 才算 §2.2 收工"
  · 第三批（`HOLDOUT3_PHRASES`）："这批写下来的那一刻就跑，跑出什么报什么，
    **不得据此调任何词表/权重**。一旦为它改过一行，它就废了，必须再写第四批。"
  · 第四批（`HOLDOUT4_PHRASES`）："同样纪律：写完就跑一次…若据此调参，第四批作废。"

而实测（全工作区代码面索引）：**第三、四批全仓没有任何代码读过** ——
只有第一批被 `tools/codex-scripts/probe_semantic_fields_gap.py` 消费。
⇒ 本脚本补上这个缺口：**三批一起量**，输出可复现的读数。

⚠️ **纪律（本脚本只测，一个字都不改词表）**：`bridge.py` 的
`SEMANTIC_FIELDS` / `INTENT_ALIASES` / 权重一律不动 —— 测出来的数字只用于**如实汇报**。
⚠️ **诚实边界**：第三/四批**写下来时没跑过**，今天才第一次跑；
这中间词表被改过很多次（本仓这半个月一直在改），所以今天这个数**不是**
"第一次见的泛化读数"，而是**"当前词表 vs 当年写下的句子"**。
两者含义不同，汇报时必须分开说。
"""
from __future__ import annotations

import argparse
import importlib
import sys
from pathlib import Path

ROOT = next(p for p in Path(__file__).resolve().parents
            if (p / "holo_pet_pilot").is_dir() or (p / "gbt_allinone").is_dir())
sys.path.insert(0, str(ROOT))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

TB = importlib.import_module("gbt_allinone.tentacle.bridge")

SETS = (("留出集(批1)", "HELD_OUT_PHRASES"),
        ("第三批", "HOLDOUT3_PHRASES"),
        ("第四批", "HOLDOUT4_PHRASES"),
        ("种子集", "SEED_PHRASES"))


def measure(attr: str, show_miss: int = 0):
    rows = list(getattr(TB, attr, []) or [])
    hit, misses = 0, []
    for item in rows:
        try:
            sent, want = item[0], item[1]
        except Exception:
            continue
        r = TB.route_method(sent)
        got = (r.get("best") or {}).get("method")
        if got == want:
            hit += 1
        else:
            misses.append((sent, want, got, r.get("confident")))
    print("  %-12s %3d/%3d = %6.1f%%   未命中 %d"
          % (attr, hit, len(rows), 100.0 * hit / max(1, len(rows)), len(misses)))
    for sent, want, got, conf in misses[:show_miss]:
        print("        %-24s 期望=%-20s 实得=%-20s confident=%s"
              % (sent, want, got, conf))
    return {"set": attr, "hit": hit, "total": len(rows), "misses": misses}


def main(argv=None):
    ap = argparse.ArgumentParser(description="三批留出集命中率（只测不动）")
    ap.add_argument("--show-miss", type=int, default=0, help="每批最多列几条未命中")
    a = ap.parse_args(argv)
    print("=" * 96)
    print("留出/全新句子的命中率（**只测不动**：本脚本不改 bridge.py 一个字符）")
    print("=" * 96)
    out = []
    for label, attr in SETS:
        if not hasattr(TB, attr):
            print("  %-12s （没有这个集合）" % label)
            continue
        print("[%s] %s" % (label, attr))
        out.append(measure(attr, show_miss=a.show_miss))
    print()
    print("口径提醒：批 3/4 是**今天第一次跑**，而词表在这中间改过很多次 ⇒")
    print("          这个数 = 『当前词表 vs 当年写下的句子』，不是『第一次见的泛化读数』。")

    # ── 置信度标定（**只量不调**）────────────────────────────────────────────
    # `bridge.route_method` 里 `confident = margin > 0 and any(前四档信号)`，
    # 它自己的注释写着"只如实标注这个答案有多虚"。
    # ⇒ 那就该量一件事：**confident=True 到底能不能预测答对**？
    #    "自信地答错"是本轮最该被看见的一类错报（读者会拿它当确定结论）。
    # ⚠️ 纪律：这里**只统计**。绝不据此改 `bridge.py` 的任何词表/阈值 ——
    #    拿留出集去调阈值，那批句子当场作废（见 bridge.py 里主人定的纪律）。
    print()
    print("=" * 96)
    print("置信度标定（只量不调）：confident=True 时答对的比例")
    print("=" * 96)
    print("  %-12s %-10s %-10s %-10s %s" % ("集合", "自信且对", "自信但错", "不自信且错", "自信时的正确率"))
    for label, attr in SETS:
        if not hasattr(TB, attr):
            continue
        cc = cw = uw = 0
        for row in getattr(TB, attr):
            r = TB.route_method(row[0])
            got = (r.get("best") or {}).get("method")
            ok = (got == row[1])
            if r.get("confident"):
                cc += 1 if ok else 0
                cw += 0 if ok else 1
            elif not ok:
                uw += 1
        tot_c = cc + cw
        print("  %-12s %-10d %-10d %-10d %s"
              % (label, cc, cw, uw,
                 ("%.1f%%" % (100.0 * cc / tot_c)) if tot_c else "（没有自信的样本）"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
