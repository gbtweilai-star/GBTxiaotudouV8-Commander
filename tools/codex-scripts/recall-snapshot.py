# -*- coding: utf-8 -*-
"""recall-20.json 生成器 —— `pulse_core.verify` 判「精准直达」的唯一依据。

## 为什么要这个脚本

`pulse_core._direct()` 读 `state/commander/recall-20.json`；那文件此前不存在，
于是 `verify` 的「精准直达」永远是 `ok: false`（`recall_at_k = {}`）——
不是没接线，是**从没被召回率证明过**。

第一次是我手写的，那不可复现。这个脚本把生成过程固定下来：
数据源永远是 `commander-coverage.py --recall-only --k N` 的真实输出。

## 两个数必须分清（写在这里，别只写在脑子里）

  recall-only  = 候选池**有没有**把真名兜住  → 是**上限**
  model 模式   = 权重**真选对没有**          → 才是泛化命中率

本文件只记录前者，并在 `measure` 字段里明确标注"上限，不是泛化命中率"。
把上限当成命中率写进验收，就是在骗自己。

用法：
    py tools/codex-scripts/commander-coverage.py --recall-only --k 20 \
        --json state/commander/recall-only.json
    py tools/codex-scripts/recall-snapshot.py --k 20
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SRC = os.path.join(ROOT, "state", "commander", "recall-only.json")
DST = os.path.join(ROOT, "state", "commander", "recall-20.json")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="从 recall-only 结果生成 recall-20.json")
    ap.add_argument("--k", type=int, default=20)
    ap.add_argument("--src", default=SRC)
    ap.add_argument("--dst", default=DST)
    a = ap.parse_args(argv)

    if not os.path.isfile(a.src):
        print(json.dumps({"ok": False, "status": "needs_input",
                          "why": "没有 %s —— 先跑 commander-coverage.py --recall-only"
                                 % os.path.relpath(a.src, ROOT)},
                         ensure_ascii=False, indent=1))
        return 1

    d = json.loads(open(a.src, encoding="utf-8").read())
    total, hit = d.get("total"), d.get("hit")
    if not isinstance(total, int) or not isinstance(hit, int) or total <= 0:
        print(json.dumps({"ok": False, "status": "failed",
                          "why": "源文件缺 total/hit：%r / %r" % (total, hit)},
                         ensure_ascii=False, indent=1))
        return 1
    # k 必须对得上，否则"recall@20"是假的
    src_k = d.get("k")
    if src_k is not None and int(src_k) != a.k:
        print(json.dumps({"ok": False, "status": "failed",
                          "why": "源文件 k=%s 与请求 k=%d 不符 —— 换名字会骗人"
                                 % (src_k, a.k)}, ensure_ascii=False, indent=1))
        return 1

    out = {
        "total": total,
        "hit": hit,
        "rate": round(hit / total, 4),
        "k": a.k,
        "measured_at": d.get("at") or time.strftime("%Y-%m-%dT%H:%M:%S"),
        "measured_by": "tools/codex-scripts/commander-coverage.py --recall-only --k %d" % a.k,
        "space": {"method": d.get("method"), "cap": d.get("cap")},
        "misses": [
            {"space": m.get("space"), "name": m.get("name"), "dom": m.get("dom"),
             "intent": m.get("intent"), "picked": m.get("picked")}
            for m in (d.get("misses") or [])
        ],
        "measure": ("同表生成（别名/desc 即召回语料）⇒ **可达性上限**，"
                    "不是泛化命中率"),
        "note": ("本文件是 pulse_core.verify 判「精准直达」的依据。"
                 "真实泛化命中率要跑 model 模式（commander-coverage 全量，逐项过权重），"
                 "落 state/commander/coverage-rows.jsonl。两者不可互相替代。"),
    }
    os.makedirs(os.path.dirname(a.dst), exist_ok=True)
    tmp = a.dst + ".tmp-%d" % os.getpid()
    with open(tmp, "w", encoding="utf-8") as fh:
        fh.write(json.dumps(out, ensure_ascii=False, indent=1) + "\n")
        fh.flush()
        os.fsync(fh.fileno())
    os.replace(tmp, a.dst)          # 原子替换，与 wiring.json 同一口径

    print(json.dumps({"ok": True, "status": "written",
                      "total": total, "hit": hit, "rate": out["rate"], "k": a.k,
                      "dst": os.path.relpath(a.dst, ROOT)},
                     ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
