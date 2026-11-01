# -*- coding: utf-8 -*-
"""把 README/docs 里的"当前能力位计数"同步成注册表现读数。

用法：
    python tools/sync-cap-counts.py --check     # 只看差多少（默认）
    python tools/sync-cap-counts.py --apply     # 就地改写
"""
from __future__ import annotations

import argparse
import pathlib
import sys

REPO = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from gbt_allinone.tentacle import doc_counts as DC  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="只看差多少（默认）")
    ap.add_argument("--apply", action="store_true", help="就地改写")
    a = ap.parse_args()
    r = DC.check(apply=a.apply)
    print("真源（注册表现读）: %d 位" % r["current"])
    print("不一致: %d 处 / %d 个文件" % (r["count"], len(r["files"])))
    for s in r["stale"]:
        print("  %-34s L%-4d 旧值 %-10s %s" % (s["file"], s["line"], s["old"], s["text"]))
    if a.apply:
        print("已改写:", ", ".join(r["changed_files"]) or "（无）")
        r2 = DC.check(apply=False)
        print("复核: %s（剩 %d 处）" % (r2["verdict"], r2["count"]))
        return 0 if r2["count"] == 0 else 2
    if r["count"]:
        print("\n怎么修: python tools/sync-cap-counts.py --apply")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
