#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""给 F22 遗留清单里**已缺**的件标 `已不存在`（纯记账，不补理由、不改基线）。

背景：2026-10-22 用 `legacy-grouping.py` 量出 223 件里 **221 件仍在役**、**9 件已缺**（holo_pet_w3 下删/改名）。
口径（写死）：
  · 只给**盘上确实不存在**的件加 `status="已不存在"` + `checked_at` + `evidence`；
  · **不给在役件加任何"认账"字样**（那是把活件说成死件，本仓明令禁止）；
  · 原子替换，不动 `items` 的其余字段（`file` / `kind` / `detail` 原样保留）。

用法：py -3.14 tools/codex-scripts/legacy-mark-missing.py [--dry-run]
"""
import argparse
import json
import os
import sys
import tempfile
import time

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        pass

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SRC = os.path.join(ROOT, "state", "framework-passports-legacy.json")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    if not os.path.isfile(SRC):
        print("遗留清单不在：%s" % SRC)
        return 2
    j = json.load(open(SRC, encoding="utf-8"))
    items = j.get("items") or []
    missing, present = [], 0
    for it in items:
        rel = str(it.get("file") or "").replace("/", os.sep)
        if not rel:
            continue
        if os.path.isfile(os.path.join(ROOT, rel)):
            present += 1
            continue
        it["status"] = "已不存在"
        it["checked_at"] = time.strftime("%Y-%m-%dT%H:%M:%S%z")
        it["evidence"] = "os.path.isfile(%s) => False（现读）" % rel
        missing.append(rel)
    j["missing_marked_at"] = time.strftime("%Y-%m-%dT%H:%M:%S%z")
    j["missing_count"] = len(missing)
    j["note"] = ("既有口径不变：这 223 件是**基线前就在役的件**，不补假理由、也不标 accepted-legacy；"
                 "本次只给盘上确实不存在的 %d 件标『已不存在』。" % len(missing))
    print("遗留 %d 件：在役 %d · **已缺 %d**" % (len(items), present, len(missing)))
    for m in missing:
        print("  ❌", m)
    if a.dry_run:
        print("（dry-run：未写盘）")
        return 0
    tmp = SRC + ".tmp"
    with open(tmp, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(j, fh, ensure_ascii=False, indent=1)
        fh.write("\n")
    os.replace(tmp, SRC)
    print("已写回：%s" % SRC)
    return 0


if __name__ == "__main__":
    sys.exit(main())
