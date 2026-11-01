# -*- coding: utf-8 -*-
"""旧物守卫判据：项目里不许有旧代码/旧面板/重复物。

四条：
  ① status 能跑且给出 verdict（clean / legacy_found）
  ② 六类都出现在 categories 里（口径齐全）
  ③ 造一个 *.bak 能被抓出来
  ④ clean 能删掉它，且删完 sync-backup/state-tmp 归零

跑法：python tests/test_legacy_guard.py
"""
from __future__ import annotations

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

FAILED = []


def check(name, cond, detail=""):
    print(("  ok   " if cond else "  FAIL ") + name + ("" if cond else "  " + str(detail)))
    if not cond:
        FAILED.append(name)


def main() -> int:
    from gbt_allinone.tentacle import legacy_guard as LG

    print("[1] status 能跑")
    st = LG.run("status")
    check("有 verdict", st.get("verdict") in ("clean", "legacy_found"), st.get("verdict"))

    print("[2] 六类口径齐全")
    cats = (st.get("categories") or {})
    need = {"sync-backup", "old-worktree", "old-panel-archive",
            "backup-files", "dup-doc-numbers", "state-tmp"}
    check("六类都在", need <= set(cats), sorted(cats))

    print("[3] 造物能抓")
    probe = os.path.join(ROOT, "_legacy_probe.bak")
    with open(probe, "w", encoding="utf-8") as fh:
        fh.write("old copy\n")
    s2 = LG.run("scan")
    hit = [p for p in (s2.get("paths") or {}).get("backup-files", []) if "_legacy_probe" in p]
    check("抓到 .bak", bool(hit), (s2.get("paths") or {}).get("backup-files")[:3])

    print("[4] clean 能删")
    LG.clean(include_tmp=True)
    check("探针已删", not os.path.exists(probe), probe)
    s3 = LG.run("status")
    c3 = s3.get("categories") or {}
    check("sync-backup 归零", (c3.get("sync-backup") or {}).get("files", 0) == 0, c3.get("sync-backup"))
    check("state-tmp 归零", (c3.get("state-tmp") or {}).get("files", 0) == 0, c3.get("state-tmp"))

    print()
    if FAILED:
        print("FAILED %d: %s" % (len(FAILED), ", ".join(FAILED)))
        return 1
    print("ALL OK —— 旧物六类可查、可抓、可清（重复文档只报不删）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
