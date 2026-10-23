# -*- coding: utf-8 -*-
"""check_family_binding -- 撞名题面的**答案层教学覆盖**判据。
口径（2026-10-17 依证据定，两次修正后的终版）：
  1. 题面可以跨族共用（v43→v47 实测：改题面会掉分）
  2. 但撞名组里**有位可绑的族**（CAP_OF）7 族）必须在语料里被“族＝X；位＝cap”教过
  3. **无位可绑的族**（? / 身份与纪律 / 判据强化 / 执行纪律 / 挖洞工序）**豁免**（它们没有能力位，教不出“位＝Y”）
"""
from __future__ import annotations
import collections, json, re, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CAP_OF = {"自主渗透编排": "offense_ops", "自适应抓取": "spider_ops",
          "作品解剖展示": "showcase_ops", "技能蒸馏五式": "skill_forge",
          "看视频理解": "video_intel", "节点即触手": "forge_mastery",
          "工作流十式": "workflow_forge"}


def sig(q):
    s = re.sub(r"^【[^】]*】", "", (q or "").strip())
    return re.sub(r"[^0-9A-Za-z一-鿿]", "", s)[:24]


def main():
    corpus = ".scratch/self_knowledge_v48.jsonl"
    if len(sys.argv) > 2 and sys.argv[1] == "--corpus":
        corpus = sys.argv[2]
    rows = [json.loads(l) for l in (ROOT / corpus).read_text(encoding="utf-8").splitlines() if l.strip()]
    by = collections.defaultdict(set)
    for r in rows:
        by[sig(r.get("instruction") or "")].add(r.get("family") or "?")
    collide = {k: v for k, v in by.items() if len(v) > 1}
    taught = set()
    for r in rows:
        fam = r.get("family") or "?"
        out = r.get("output") or ""
        if ("族＝" + fam) in out and (("five-dim.py cap" in out) or ("（本族无专属位）" in out)):
            taught.add(fam)
    need = set()
    for fams in collide.values():
        need |= {f for f in fams if f in CAP_OF}
    exempt = set()
    for fams in collide.values():
        exempt |= {f for f in fams if f not in CAP_OF}
    bad = sorted(f for f in need if f not in taught)
    print("撞名题面 %d 组 · 涉及有位族 %d（已教 %d）· 豁免无位族 %d"
          % (len(collide), len(need), len(need & taught), len(exempt)))
    for f in bad[:8]:
        print("   RED 未教区分: %s" % f)
    return 0 if not bad else 1


if __name__ == "__main__":
    raise SystemExit(main())
