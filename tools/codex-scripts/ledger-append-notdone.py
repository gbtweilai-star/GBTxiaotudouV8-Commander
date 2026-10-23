#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""往台账 `not_done` 追加一条「决定/待办」（只追加、原子替换）。

为什么单独一件：这段字里有 `**`、反引号、中文引号，内联 python 反复被 PowerShell
吃掉引号（P31 一族）。写成文件，一次就对。

用法：
  py -3.14 tools/codex-scripts/ledger-append-notdone.py --spec state/notdone-append.json
spec 形如：{"id":"N15","what":"…","why":"…","where":"…"}
"""
import argparse
import json
import os
import sys
import tempfile

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        pass

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
LEDGER = os.path.join(ROOT, "state", "排查台账.json")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--spec", required=True)
    a = ap.parse_args()
    spec = json.load(open(os.path.join(ROOT, a.spec), encoding="utf-8"))
    led = json.load(open(LEDGER, encoding="utf-8"))
    nd = led.setdefault("not_done", [])
    if any(x.get("id") == spec.get("id") for x in nd):
        print("%s 已在册，未改" % spec.get("id"))
        return 0
    nd.append(spec)
    fd, tmp = tempfile.mkstemp(prefix="ledger-", suffix=".json", dir=os.path.dirname(LEDGER))
    with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(led, fh, ensure_ascii=False, indent=2)
        fh.write("\n")
    os.replace(tmp, LEDGER)
    print("已追加 %s · not_done 现 %d 条" % (spec.get("id"), len(nd)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
