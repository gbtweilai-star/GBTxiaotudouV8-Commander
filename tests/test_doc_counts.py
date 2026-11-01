# -*- coding: utf-8 -*-
"""能力位计数判据：README/docs 里的"当前数"必须等于注册表现读。

跑法：python tests/test_doc_counts.py
"""
from __future__ import annotations

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

FAILED = []


def check(name, cond, detail=""):
    print(("  ok   " if cond else "  FAIL ") + name + ("" if cond else "  " + str(detail)[:300]))
    if not cond:
        FAILED.append(name)


def main() -> int:
    from gbt_allinone.tentacle import doc_counts as DC

    print("[1] 真源可读")
    n = DC.current_count()
    check("注册表 > 300", n > 300, n)
    safe, unsafe = DC.split_counts()
    check("只读 + 写口 = 总数", safe + unsafe == n, (safe, unsafe, n))

    print("[2] 文档当前数一致（不一致会列出文件/行/旧值）")
    r = DC.check(apply=False)
    check("verdict clean", r.get("verdict") == "clean", r.get("stale"))
    check("0 处不一致", r.get("count") == 0, r.get("count"))

    print("[3] 历史口径不被误改（含 快照/当时/评估 的行应保留旧数）")
    import pathlib
    mc = (ROOT_PATH := pathlib.Path(ROOT)) / "docs" / "01-model-card.md"
    txt = mc.read_text(encoding="utf-8")
    check("341 快照说明还在", "341 位" in txt, "docs/01 丢了 341 历史说明")
    check("当时口径 348 还在", "348" in txt, "docs/01 丢了 348 历史说明")

    print()
    if FAILED:
        print("FAILED %d: %s" % (len(FAILED), ", ".join(FAILED)))
        return 1
    print("ALL OK —— 现读数唯一、历史口径保留")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
