# -*- coding: utf-8 -*-
"""check_family_discrimination -- 族判别判据：看模型答的是不是**本族**。
用法：--answers <jsonl> --cap <本族位> [--others a,b,c]
统计：本族命中 / 他族串入 / 两者都无（未名）。
"""
from __future__ import annotations
import argparse, json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ALL_CAPS = ["offense_ops", "spider_ops", "showcase_ops", "skill_forge", "video_intel", "forge_mastery", "workflow_forge"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--answers", required=True)
    ap.add_argument("--cap", required=True)
    ap.add_argument("--others", default="")
    a = ap.parse_args()
    others = [x.strip() for x in a.others.split(",") if x.strip()] or [c for c in ALL_CAPS if c != a.cap]
    rows = [json.loads(l) for l in (ROOT / a.answers).read_text(encoding="utf-8").splitlines() if l.strip()]
    own = wrong = none = 0
    wrong_hits = []
    for r in rows:
        ans = (r.get("a") or r.get("answer") or r.get("output") or r.get("text") or "")
        has_own = a.cap in ans
        has_other = [o for o in others if o in ans]
        if has_own and not has_other:
            own += 1
        elif has_other and not has_own:
            wrong += 1
            wrong_hits.append((has_other, ans[:80]))
        elif has_own and has_other:
            own += 1
            wrong_hits.append((["混"] + has_other, ans[:80]))
        else:
            none += 1
    n = len(rows)
    print("本族 %s：共 %d 题 · **本族命中 %d** · 他族串入 %d · 未名 %d"
          % (a.cap, n, own, wrong, none))
    for o, t in wrong_hits[:4]:
        print("   串族样本:", o, "->", t.replace(chr(10), " "))
    return 0 if wrong == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
