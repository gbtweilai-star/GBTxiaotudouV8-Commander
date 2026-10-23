#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""给 `owner_decisions` 里的某几条**标注实测解答**（不删、不改写原问题）。

为什么要这个：决策清单会越长越糊。有些条目其实已经被**测量**回答了（比如"注册表要不要收
room_*/qiankun"——实测 305 个 kind 全在册，前提不成立），还挂在那儿等于让主人替量具做选择。
本件只在条目上加 `answered_by_measurement` 字段，保留原问题原文（历史不丢）。

用法：py -3.14 tools/codex-scripts/decision-annotate.py --spec state/decisions-annotate.json
spec 形如：{"D13": {"answered_by_measurement": "…", "evidence": "…"}}
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
LEDGER = os.path.join(ROOT, "state", "排查台账.json")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--spec", required=True)
    a = ap.parse_args()
    spec = json.load(open(os.path.join(ROOT, a.spec), encoding="utf-8"))
    led = json.load(open(LEDGER, encoding="utf-8"))
    done = []
    for d in (led.get("owner_decisions") or []):
        ann = spec.get(str(d.get("id")))
        if not ann:
            continue
        d.update(ann)
        d["annotated_at"] = time.strftime("%Y-%m-%dT%H:%M:%S%z")
        done.append(str(d.get("id")))
    if not done:
        print("没有匹配的条目")
        return 1
    led.setdefault("log", []).append({
        "at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "what": "决策清单降噪：按实测标注 " + "、".join(done),
        "text": "原问题保留；新增 answered_by_measurement / evidence / annotated_at 三个字段",
        "note": "tools/codex-scripts/decision-annotate.py（原子替换）",
    })
    fd, tmp = tempfile.mkstemp(prefix="ledger-", suffix=".json", dir=os.path.dirname(LEDGER))
    with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(led, fh, ensure_ascii=False, indent=2)
        fh.write("\n")
    os.replace(tmp, LEDGER)
    print("已标注：%s" % "、".join(done))
    return 0


if __name__ == "__main__":
    sys.exit(main())
