# -*- coding: utf-8 -*-
"""check_instruction_unique -- 题面唯一性判据：同一题面出现在多族 ⇒ 报红。

真因（v41 实测）：「命令怎么调？」这句题面被看视频/渗透/作品解剖三族共用
  ⇒ 模型只能赌一个答案 ⇒ 必然串族（不是能力问题，是题库设计缺陷）。
用法：py -3.14 tools/train/check_instruction_unique.py --corpus .scratch/xxx.jsonl [--fix-report]
"""
from __future__ import annotations
import argparse, json
from collections import defaultdict
from pathlib import Path


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--corpus", required=True)
    a = ap.parse_args()
    by = defaultdict(set)
    rows = 0
    for ln in Path(a.corpus).read_text(encoding="utf-8").splitlines():
        if not ln.strip():
            continue
        try:
            r = json.loads(ln)
        except Exception:
            continue
        rows += 1
        by[(r.get("instruction") or "").strip()].add(r.get("family") or "?")
    dup = {k: sorted(v) for k, v in by.items() if len(v) > 1}
    print("题面唯一性：总 %d 条 · 不同题面 %d · **跨族重复 %d**" % (rows, len(by), len(dup)))
    for k, v in list(dup.items())[:8]:
        print("   RED 「%s」 -> %s" % (k[:34], v))
    return 0 if not dup else 1


if __name__ == "__main__":
    raise SystemExit(main())
