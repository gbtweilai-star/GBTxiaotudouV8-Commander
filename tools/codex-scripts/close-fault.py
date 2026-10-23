#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""结掉一条未清故障：从 open_faults 移进 closed_faults + 记一笔 log。

为什么要有它（本仓纪律）：账里挂着但前提已垮的条目必须**按证据结掉**，
不许留在 open_faults 里让「未清故障前提复核」天天红（rail：已不成立 ⇒ 回台账改账）。

用法：
  py -3.14 tools/codex-scripts/close-fault.py F23 --why "…" --evidence "命令 => 读数"
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

LEDGER = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
                      "state", "排查台账.json")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("fault_id")
    ap.add_argument("--why", required=True, help="为什么现在可以结（一句话）")
    ap.add_argument("--evidence", required=True, help="『命令 => 读数』形式的证据")
    a = ap.parse_args()

    with open(LEDGER, encoding="utf-8") as fh:
        led = json.load(fh)
    faults = led.get("open_faults") or []
    hit = [f for f in faults if str(f.get("id")) == a.fault_id]
    if not hit:
        print("未清故障里没有 %s（可能已结或 id 写错）" % a.fault_id)
        return 1
    item = hit[0]
    led["open_faults"] = [f for f in faults if str(f.get("id")) != a.fault_id]

    closed = dict(item)
    closed["state"] = "已结（%s）· %s" % (time.strftime("%Y-%m-%dT%H:%M:%S"), a.why)
    closed["evidence"] = str(item.get("evidence") or "") + " ｜结案证据：" + a.evidence
    led.setdefault("closed_faults", []).append(closed)

    stamp = time.strftime("%Y-%m-%dT%H:%M:%S%z")
    led.setdefault("log", []).append({
        "at": stamp,
        "what": "结 %s：%s" % (a.fault_id, a.why),
        "text": "结 %s：%s ｜ 证据：%s" % (a.fault_id, a.why, a.evidence),
        "note": "本笔由 tools/codex-scripts/close-fault.py 按证据结案（不代笔理由）",
    })

    fd, tmp = tempfile.mkstemp(prefix="ledger-", suffix=".json", dir=os.path.dirname(LEDGER))
    with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(led, fh, ensure_ascii=False, indent=2)
        fh.write("\n")
    os.replace(tmp, LEDGER)
    print("已结 %s · open_faults %d 条 · closed_faults %d 条"
          % (a.fault_id, len(led["open_faults"]), len(led["closed_faults"])))
    return 0


if __name__ == "__main__":
    sys.exit(main())
