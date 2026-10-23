# -*- coding: utf-8 -*-
"""深挖 route_method 为什么把「看看现在有哪些窗口」判给 focus_window。

不推理，把前 6 名的**打分八档**逐项摊开：
  (方向, 语义场宾语, 具体度, 整词, 动作词, 2-gram, 公共子串, 方法名)
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = next(p for p in Path(__file__).resolve().parents
            if (p / "holo_pet_w3").is_dir() and (p / "gbt_allinone").is_dir())
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "gbt_allinone" / "tentacle"))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import importlib  # noqa: E402

TB = importlib.import_module("gbt_allinone.tentacle.bridge")

INTENTS = [
    "看看现在有哪些窗口",
    "列出当前所有窗口",
    "看看有哪些进程",
    "读一下屏幕上的文字",
]

for intent in INTENTS:
    r = TB.route_method(intent)
    b = r.get("best") or {}
    print("=" * 90)
    print("意图：%s" % intent)
    print("  命中：%s（邻域 %s）confident=%s margin=%s tie_by_name=%s"
          % (b.get("method"), b.get("neighborhood"), r.get("confident"),
             r.get("margin"), r.get("tie_by_name")))
    print("  八档打分：dir=%s field=%s specific=%s strong=%s verb=%s grams=%s lcs=%s"
          % (b.get("dir"), b.get("field"), b.get("specific"), b.get("strong"),
             b.get("verb"), b.get("grams"), b.get("lcs")))
    print("  备选：%s" % [(a.get("method"), a.get("field")) for a in (r.get("alternatives") or [])])

    # 复算：把候选与分数摊开（按 route_method 同一口径）
    low = intent.lower()
    words = set(intent.lower().split()) | TB._grams(intent)
    owner = {}
    for dom, info in TB.TENTACLE_NEIGHBORHOOD_MAP.items():
        for m in info["powered_by"]:
            owner.setdefault(m, dom)
    rows = []
    for m in sorted(set(owner) | set(TB.INTENT_ALIASES)):
        alias = TB.INTENT_ALIASES.get(m, "")
        face = " ".join([m, TB.dom_name(owner.get(m, "")), alias])
        hits = len(words & (TB._grams(face) | set(face.lower().split())))
        strong_f, weak_f = TB._field_tokens(m)
        field_hits = sum(1 for w in strong_f if w in low)
        verb_hits = sum(1 for w in weak_f if len(w) >= 2 and w in low)
        if not (hits or field_hits):
            continue
        matched = [w for w in alias.split() if len(w) >= 2 and w in low]
        rows.append({"m": m, "field": field_hits, "specific": max((len(w) for w in matched), default=0),
                     "strong": len(matched), "verb": verb_hits, "grams": hits,
                     "alias": alias, "matched": matched, "dom": owner.get(m, "?")})
    rows.sort(key=lambda d: (-d["field"], -d["specific"], -d["strong"],
                             -d["verb"], -d["grams"], d["m"]))
    print("  前 6 名（复算）：")
    for d in rows[:6]:
        print("     %-24s field=%d spec=%d strong=%d verb=%d gram=%d | alias=%r matched=%s"
              % (d["m"], d["field"], d["specific"], d["strong"], d["verb"], d["grams"],
                 d["alias"][:34], d["matched"]))

print("\n" + "=" * 90)
print("字段词表（_field_tokens）：为什么 list_windows 进不来")
for m in ("list_windows", "focus_window", "see", "window_list", "act_window"):
    sf, wf = TB._field_tokens(m)
    alias = TB.INTENT_ALIASES.get(m, "")
    print("  %-20s strong=%-28s weak=%-24s alias=%r" % (m, sf, wf, alias[:30]))
