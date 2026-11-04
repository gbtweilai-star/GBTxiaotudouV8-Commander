# -*- coding: utf-8 -*-
"""给 immune.py 加两条腿：elevate（提权交付通道）+ patrol（常态核对）。

规矩（2026-11-03 主人令）：
  原子替换无伤修复 —— tmp 写入 → sha256 双校验 → os.replace → 备份 + 回执。
  一次都不用「读出来改完直接覆盖」。

用法：
    python immune-add-elevate.py            # 演习，只报 delta，不落盘
    python immune-add-elevate.py --apply    # 真改
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
BLOCK_SRC = REPO / "tools" / "codex-scripts" / "_immune_add_elevate.block.txt"
BACKUP_DIR = REPO / "state" / "atomic-sync" / "backup"
LEDGER = REPO / "state" / "atomic-sync" / "ledger.jsonl"

# ── 四处改动点（(名字, 原文, 新文)），原文必须恰好出现一次 ──────────
A1_OLD = "import subprocess\r\nimport time"
A1_NEW = "import subprocess\r\nimport sys\r\nimport time"

A2_OLD = ("# ══════════════════════════════════════════════════════════════\r\n"
          "# L3 记账\r\n"
          "# ══════════════════════════════════════════════════════════════")

A3_OLD = '            "record": "免疫史",\r\n        },'
A3_NEW = ("            \"record\": \"免疫史\",\r\n"
          "            \"elevate\": \"生成提权脚本（.ps1+.cmd）：把 admin=True 的项变成人点一次 UAC 就结算的交付物\",\r\n"
          "            \"patrol\": \"常态核对：与上次快照比，报新增/消失；只读不动手\",\r\n"
          "            \"install_patrol\": \"注册/卸载每日核对任务（HKCU 级，默认演习）\",\r\n"
          "        },")

A4_OLD = '"purge": op_purge, "record": op_record}'
A4_NEW = ("\"purge\": op_purge, \"record\": op_record,\r\n"
          "           \"elevate\": op_elevate, \"patrol\": op_patrol,\r\n"
          "           \"install_patrol\": op_install_patrol}")


def sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def read_raw(p: Path) -> str:
    """newline='' 读，保住原始 CRLF —— 用默认读法会把 \r\n 悄悄变成 \n。"""
    with open(p, "r", encoding="utf-8", newline="") as fh:
        return fh.read()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="真改（默认只演习）")
    args = ap.parse_args()

    if not TARGET.exists():
        print("FAIL 找不到 %s" % TARGET)
        return 2
    if not BLOCK_SRC.exists():
        print("FAIL 找不到插入块 %s" % BLOCK_SRC)
        return 2

    raw = read_raw(TARGET)
    before_bytes = raw.encode("utf-8")
    before_sha = sha256_bytes(before_bytes)

    print("=" * 66)
    print("目标 : %s" % TARGET)
    print("大小 : %d B" % len(before_bytes))
    print("CRLF : %d   LF : %d" % (raw.count("\r\n"), raw.count("\n")))
    print("sha  : %s" % before_sha)
    print("=" * 66)

    # ── 幂等：已经改过就别再改 ────────────────────────────────
    if "def op_elevate(" in raw:
        print("SKIP 已经含 op_elevate，本补丁已应用过，不做二次插入")
        return 0

    # ── 闸一：锚点唯一 ────────────────────────────────────────
    block = read_raw(BLOCK_SRC).strip("\r\n").replace("\r\n", "\n").replace("\n", "\r\n")
    if "\r\n\r\n\r\n" in block:
        block = block.replace("\r\n\r\n\r\n", "\r\n\r\n")

    ops = [
        ("A1 import sys", A1_OLD, A1_NEW, raw.count(A1_OLD)),
        ("A2 插入两块新代码", A2_OLD, block + "\r\n" + A2_OLD, raw.count(A2_OLD)),
        ("A3 schema 加三行", A3_OLD, A3_NEW, raw.count(A3_OLD)),
        ("A4 run() 注册三个 op", A4_OLD, A4_NEW, raw.count(A4_OLD)),
    ]
    bad = False
    for name, old, new, cnt in ops:
        flag = "OK  " if cnt == 1 else "FAIL"
        if cnt != 1:
            bad = True
        print("%s %-24s 命中 %d 次   %d B -> %d B" % (flag, name, cnt, len(old), len(new)))
    if bad:
        print("\nABORT 有锚点不是恰好 1 次，一个字节都不写")
        return 3

    # ── 闸二：空改动拒 ────────────────────────────────────────
    after = raw
    for name, old, new, cnt in ops:
        after = after.replace(old, new, 1)

    if after == raw:
        print("ABORT 拼装后与原文件一致（空改动），不落盘")
        return 4

    after_bytes = after.encode("utf-8")
    delta = len(after_bytes) - len(before_bytes)
    print("-" * 66)
    print("新大小 : %d B   (%+d B)" % (len(after_bytes), delta))
    print("新 CRLF: %d   LF : %d   (CRLF 应等于 LF，纯 CRLF)" % (after.count("\r\n"), after.count("\n")))
    if after.count("\r\n") != after.count("\n"):
        print("ABORT 混入了裸 LF，行尾不一致，不落盘")
        return 5
    print("新 sha : %s" % sha256_bytes(after_bytes))

    if not args.apply:
        print("-" * 66)
        print("演习结束。真改加 --apply")
        return 0

    # ── 闸三：备份（可回滚） ──────────────────────────────────
    ts = time.strftime("%Y%m%d-%H%M%S")
    bdir = BACKUP_DIR / ts
    bdir.mkdir(parents=True, exist_ok=True)
    bak = bdir / "immune.py"
    shutil.copy2(TARGET, bak)
    if sha256_bytes(bak.read_bytes()) != before_sha:
        print("ABORT 备份校验不一致，不落盘")
        return 6
    print("-" * 66)
    print("备份 : %s  (%d B, sha 一致)" % (bak, bak.stat().st_size))

    # ── 闸四：原子写（tmp + os.replace） ──────────────────────
    tmp = TARGET.with_suffix(".py.tmp-immune")
    with open(tmp, "wb") as fh:
        fh.write(after_bytes)
        fh.flush()
        os.fsync(fh.fileno())

    if sha256_bytes(tmp.read_bytes()) != sha256_bytes(after_bytes):
        tmp.unlink(missing_ok=True)
        print("ABORT tmp 校验不一致，不替换")
        return 7

    os.replace(tmp, TARGET)
    final_sha = sha256_bytes(TARGET.read_bytes())
    if final_sha != sha256_bytes(after_bytes):
        print("FAIL 替换后 sha 不一致！备份在 %s" % bak)
        return 8
    print("落盘 : os.replace 完成，sha %s" % final_sha)

    # ── 语法闸 ────────────────────────────────────────────────
    try:
        py_compile.compile(str(TARGET), doraise=True)
        print("语法 : OK")
    except Exception as exc:                                 # noqa: BLE001
        print("语法 : FAIL %s" % exc)
        shutil.copy2(bak, TARGET)
        print("已回滚到备份，文件恢复原样")
        return 9

    # ── 回执 ──────────────────────────────────────────────────
    LEDGER.parent.mkdir(parents=True, exist_ok=True)
    with open(LEDGER, "a", encoding="utf-8") as fh:
        fh.write(json.dumps({
            "at": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "tool": "immune-add-elevate.py",
            "target": str(TARGET.relative_to(REPO)),
            "before_sha256": before_sha,
            "after_sha256": final_sha,
            "delta_bytes": delta,
            "backup": str(bak.relative_to(REPO)),
            "changes": [n for n, *_ in ops],
        }, ensure_ascii=False) + "\n")
    print("回执 : %s" % LEDGER)
    print("-" * 66)
    print("完成。回滚命令：")
    print('  copy "%s" "%s"' % (bak, TARGET))
    return 0


if __name__ == "__main__":
    sys.exit(main())
