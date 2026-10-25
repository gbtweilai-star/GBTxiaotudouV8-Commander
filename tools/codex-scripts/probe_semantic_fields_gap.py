# -*- coding: utf-8 -*-
"""量两个数：① SEMANTIC_FIELDS 的空洞率 ② 留出集命中率（当前基线）。

⚠️ 纪律：`HELD_OUT_PHRASES` 是**留出集**（写它时"还没有针对它们调过任何词"）。
本脚本只**测**、不改词表；测出来的数字用于判断"结构性空洞"有多大，
**不许拿留出集里的句子去反推该加什么词** —— 那叫过拟合，基准就废了。
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = next(p for p in Path(__file__).resolve().parents
            if (p / "holo_pet_w3").is_dir() and (p / "gbt_allinone").is_dir())
sys.path.insert(0, str(ROOT))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import importlib  # noqa: E402

TB = importlib.import_module("gbt_allinone.tentacle.bridge")

# ① 词表空洞：能把方法名认出来的"全集" = 邻域表 ∪ 别名表
owner = {}
for dom, info in TB.TENTACLE_NEIGHBORHOOD_MAP.items():
    for m in info["powered_by"]:
        owner.setdefault(m, dom)
universe = sorted(set(owner) | set(TB.INTENT_ALIASES) | set(TB.SEMANTIC_FIELDS))

empty, with_alias, with_alias_but_empty = [], [], []
for m in universe:
    sf, wf = TB._field_tokens(m)
    if not sf and not wf:
        empty.append(m)
        if TB.INTENT_ALIASES.get(m, "").strip():
            with_alias_but_empty.append(m)

print("=" * 92)
print("① 语义场词表空洞")
print("  方法全集（邻域 ∪ 别名 ∪ 语义场）：%d" % len(universe))
print("  SEMANTIC_FIELDS 有条目：%d" % len(TB.SEMANTIC_FIELDS))
print("  **语义场为空**的方法：%d（%.1f%%）" % (len(empty), 100.0 * len(empty) / max(1, len(universe))))
print("  其中**有别名却没语义场**的：%d  ← 别名在，但语义场这条路走不通" % len(with_alias_but_empty))
print("  有空语义场的方法（前 40）：")
for m in empty[:40]:
    al = TB.INTENT_ALIASES.get(m, "")
    print("     %-26s alias=%r" % (m, al[:40]))

# ② 留出集命中率（只测不动）
ho = TB.HELD_OUT_PHRASES
hit = miss = 0
misses = []
for sent, want in ho:
    r = TB.route_method(sent)
    got = (r.get("best") or {}).get("method")
    if got == want:
        hit += 1
    else:
        miss += 1
        misses.append((sent, want, got, r.get("confident")))
print("\n" + "=" * 92)
print("② 留出集命中率（当前基线，只测不动）")
print("  %d/%d = %.1f%%" % (hit, len(ho), 100.0 * hit / max(1, len(ho))))
print("  未命中 %d 条：" % len(misses))
for sent, want, got, conf in misses:
    print("     %-22s 期望=%-22s 实得=%-22s confident=%s" % (sent, want, got, conf))
