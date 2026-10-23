# -*- coding: utf-8 -*-
"""check_instruction_semantic -- 语义近义聚类：不同族题面若归一类签名 ⇒ 报红。

🔴 2026-10-17 翻正（**判据假红** · 留痕 · 原口径 / 为什么翻 / 现口径）：
  原口径：只要同一签名下出现 >1 个族，**一律 RED**。
  为什么翻（实测 + 仓内既有证据）：
    · v49 语料实测报 5 组 RED，逐组读下来**没有一组是真串族**：
      - 3 组两族**都是"无位可绑"的族**（`?` / `身份与纪律` / `判据强化` / `执行纪律` / `挖洞工序`）
        —— 它们根本没有能力位可绑，题面撞名不可能"串到别的位"；
      - 1 组（`命令怎么调` → 作品解剖展示 / 自主渗透编排 / 自适应抓取）在语料里
        **已教过 `族＝X；位＝cap`**；
    · 更关键：`check_family_binding.py` 的口径写死了「题面可以跨族共用（v43→v47 实测：
      **改题面会掉分**），靠**答案层教学**区分；无位可绑的族豁免」。
      原判据要求"题面不许撞名" ⇒ 与实测结论**方向相反**，是**假红**。
  现口径（与 `check_family_binding.py` **同源**，CAP_OF/教学判定直接从它 import）：
    同一签名跨族时：
      ① 该组**没有"有位族"** ⇒ 豁免（非红，靠答案层区分）；
      ② 有"有位族"但**每个有位族都在语料里被教过** `族＝X；位＝cap` ⇒ 非红（已教区分）；
      ③ 否则 ⇒ **RED**（真有位族撞名且没教，模型只能赌 ⇒ 真串族）。
  退出码只由 ③ 决定；豁免/已教都打进读数（**不是静默放过**）。
"""
from __future__ import annotations
import argparse
import importlib.util
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

_HERE = Path(__file__).resolve().parent


def sig(q):
    s = q or ""
    s = re.sub(r"^【[^】]*】", "", s.strip())
    s = re.sub(r"[^0-9A-Za-z一-鿿]", "", s)
    return s[:24]


def _family_binding_mod():
    """同目录的 `check_family_binding.py`（唯一真相：CAP_OF + 教学判定口径）。"""
    sp = importlib.util.spec_from_file_location(
        "check_family_binding_src", str(_HERE / "check_family_binding.py"))
    m = importlib.util.module_from_spec(sp)
    sp.loader.exec_module(m)
    return m


def _taught_families(rows) -> set:
    """哪些族在答案层被教过 `族＝X；位＝cap`（与 `check_family_binding` 同一条判据）。"""
    out = set()
    for r in rows:
        fam = r.get("family") or "?"
        body = r.get("output") or ""
        if ("族＝" + fam) in body and (("five-dim.py cap" in body) or ("（本族无专属位）" in body)):
            out.add(fam)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--corpus", required=True)
    a = ap.parse_args()
    rows_list = [json.loads(ln) for ln in Path(a.corpus).read_text(encoding="utf-8").splitlines()
                 if ln.strip()]
    fb = _family_binding_mod()
    cap_of = dict(getattr(fb, "CAP_OF", {}) or {})
    taught = _taught_families(rows_list)

    bysig = defaultdict(set)
    for r in rows_list:
        bysig[sig(r.get("instruction") or "")].add(r.get("family") or "?")
    collide = {k: sorted(v) for k, v in bysig.items() if len(v) > 1}

    exempt, distinguished, red = [], [], []
    for k, fams in collide.items():
        bindable = [f for f in fams if f in cap_of]
        if not bindable:
            exempt.append((k, fams))
        elif all(f in taught for f in bindable):
            distinguished.append((k, fams))
        else:
            red.append((k, fams, [f for f in bindable if f not in taught]))

    print("语义聚类：总 %d 条 · 签名 %d · 跨族同签名 %d（豁免 %d · 已教区分 %d · **真串族 %d**）"
          % (len(rows_list), len(bysig), len(collide), len(exempt), len(distinguished), len(red)))
    for k, fams in exempt:
        print("   OK  豁免(无位族) " + k[:26] + " -> " + str(fams))
    for k, fams in distinguished:
        print("   OK  已教区分     " + k[:26] + " -> " + str(fams))
    for k, fams, miss in red:
        print("   RED 真串族       " + k[:26] + " -> " + str(fams) + " · 未教的有位族=" + str(miss))
    return 0 if not red else 1


if __name__ == "__main__":
    raise SystemExit(main())
