# -*- coding: utf-8 -*-
"""immune.py 补一处：把 scan_programdata 的 fix 名 recycle_manual 归一成 recycle。

原因：elevate 的 ps1 只认 delete_task / del_reg / kill / recycle，
      recycle_manual 会落到 default 分支被 SKIP —— 也就是扫得到却清不掉，
      正是 \Skype 那 43 天的同一个病。

用法：python immune-fix-recycle.py [--apply]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import py_compile
import shutil
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
TARGET = REPO / "gbt_allinone" / "immune.py"
BACKUP_DIR = REPO / "state" / "atomic-sync" / "backup"
LEDGER = REPO / "state" / "atomic-sync" / "ledger.jsonl"

OLD = ('            "kind": f.get("kind") or "",\r\n'
       '            "fix": f.get("fix") or "",')
NEW = ('            "kind": f.get("kind") or "",\r\n'
       '            # scan_programdata 用 recycle_manual 表示「送回收站但需提权」；\r\n'
       '            # ps1 侧只认 recycle，这里归一 —— 否则落入 default 被 SKIP，\r\n'
       '            # 就重演「扫得到却清不掉」。\r\n'
       '            "fix": "recycle" if (f.get("fix") or "") == "recycle_manual"\r\n'
       '                   else (f.get("fix") or ""),')


def sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()

    with open(TARGET, "r", encoding="utf-8", newline="") as fh:
        raw = fh.read()
    before = raw.encode("utf-8")
    before_sha = sha(before)

    print("目标 :", TARGET)
    print("大小 :", len(before), "B")
    print("sha  :", before_sha)

    if '"recycle" if (f.get("fix") or "") == "recycle_manual"' in raw:
        print("SKIP 已归一过，不重复改")
        return 0

    cnt = raw.count(OLD)
    print("锚点命中 :", cnt, "次")
    if cnt != 1:
        print("ABORT 锚点不是恰好 1 次，不写")
        return 3

    after = raw.replace(OLD, NEW, 1)
    after_b = after.encode("utf-8")
    print("新大小 :", len(after_b), "B  (%+d)" % (len(after_b) - len(before)))
    print("CRLF/LF:", after.count("\r\n"), "/", after.count("\n"))
    if after.count("\r\n") != after.count("\n"):
        print("ABORT 行尾混了裸 LF")
        return 5

    if not args.apply:
        print("演习结束。真改加 --apply")
        return 0

    ts = time.strftime("%Y%m%d-%H%M%S")
    bdir = BACKUP_DIR / ts
    bdir.mkdir(parents=True, exist_ok=True)
    bak = bdir / "immune.py"
    shutil.copy2(TARGET, bak)
    if sha(bak.read_bytes()) != before_sha:
        print("ABORT 备份校验不一致")
        return 6
    print("备份 :", bak)

    tmp = TARGET.with_suffix(".py.tmp-recycle")
    with open(tmp, "wb") as fh:
        fh.write(after_b)
        fh.flush()
        os.fsync(fh.fileno())
    if sha(tmp.read_bytes()) != sha(after_b):
        tmp.unlink(missing_ok=True)
        print("ABORT tmp 校验不一致")
        return 7

    os.replace(tmp, TARGET)
    final = sha(TARGET.read_bytes())
    if final != sha(after_b):
        print("FAIL 替换后 sha 不一致，备份在", bak)
        return 8
    print("落盘 : os.replace 完成，sha", final)

    try:
        py_compile.compile(str(TARGET), doraise=True)
        print("语法 : OK")
    except Exception as exc:                                 # noqa: BLE001
        print("语法 : FAIL", exc)
        shutil.copy2(bak, TARGET)
        print("已回滚")
        return 9

    LEDGER.parent.mkdir(parents=True, exist_ok=True)
    with open(LEDGER, "a", encoding="utf-8") as fh:
        fh.write(json.dumps({
            "at": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "tool": "immune-fix-recycle.py",
            "target": str(TARGET.relative_to(REPO)),
            "before_sha256": before_sha,
            "after_sha256": final,
            "backup": str(bak.relative_to(REPO)),
            "changes": ["_elevate_payload: recycle_manual -> recycle"],
        }, ensure_ascii=False) + "\n")
    print("回执 :", LEDGER)
    print("完成。回滚：copy \"%s\" \"%s\"" % (bak, TARGET))
    return 0


if __name__ == "__main__":
    sys.exit(main())
