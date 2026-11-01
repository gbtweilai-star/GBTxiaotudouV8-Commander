# -*- coding: utf-8 -*-
"""跑到落地（blueprint.land）—— 无人值守也用这个。

主人 2026-11-01：「从架构蓝图用户确认之后就开始执行直到项目落地，中途除非用户打断
要不然严禁停下，自己内部沟通写作执行到项目落地」。

用法：
    python tools/blueprint-land.py --id <蓝图id>              # 跑到落地（最多 6 轮）
    python tools/blueprint-land.py --arch "..." --approve     # 现场造蓝图并直接过目后跑
    python tools/blueprint-land.py --id X --max-rounds 20     # 慢任务多轮
    python tools/blueprint-land.py --list                     # 列出所有蓝图与进度

行为：
  · 已完成的任��**不重跑**（读 runs.jsonl）；
  · 失败就下一轮重试（只重试失败项）；
  · 只剩"需要票"的任务（危险能力/转账）时**才**停下并说明；
  · 每轮都写编码账本；退出码 0=落地，1=未落地/需票。
"""
from __future__ import annotations

import argparse
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--id", default="")
    ap.add_argument("--arch", default="")
    ap.add_argument("--goal", default="")
    ap.add_argument("--approve", action="store_true", help="造完蓝图直接过目（主人已确认）")
    ap.add_argument("--max-rounds", type=int, default=6)
    ap.add_argument("--list", action="store_true")
    args = ap.parse_args()

    from gbt_allinone.tentacle import blueprint as BP

    if args.list:
        st = BP.status("")
        print(json.dumps(st, ensure_ascii=False, indent=1))
        return 0

    bid = args.id
    if not bid and args.arch:
        m = BP.make(args.arch, args.goal)
        if not m.get("ok"):
            print(json.dumps(m, ensure_ascii=False))
            return 1
        bid = m["id"]
        print("蓝图：", bid, "任务数：", m.get("tasks"),
              "（架构专项：", m.get("arch_tasks"), "）")
        if args.approve:
            print("过目：", json.dumps(BP.approve(bid), ensure_ascii=False))
    if not bid:
        print("要么 --id，要么 --arch")
        return 2

    L = BP.land(bid, max_rounds=args.max_rounds)
    print(json.dumps(L, ensure_ascii=False, indent=1))
    return 0 if L.get("landed") else 1


if __name__ == "__main__":
    raise SystemExit(main())
