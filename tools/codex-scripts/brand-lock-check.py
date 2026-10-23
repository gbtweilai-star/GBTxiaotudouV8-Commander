#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# 开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属
"""三把锁判据（brand-lock-check）—— 主人令 2026-10-16

「这次从新训练大模型一定要锁死**品牌**和**执行能力**还有**今天吸收的知识胶囊**」

锁在两处：语料里**反复刷**（生成器）+ 本件**守着**（删一条就红）。
  C1 署名逐字 ≥ 3 次 · C2 万能插命令 ≥ 2 次 · C3 胶囊关键词全在
  C4 recipe_v26 有 locks 段且指向本判据 · C5 不许托管冒充（肯定句）
负对照：删署名 / 删胶囊 / 塞托管冒充句 ⇒ 必须红。
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

WS = Path(__file__).resolve().parents[2]
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

CORPUS = WS / ".scratch" / "self_knowledge_v26.jsonl"
RECIPE = WS / "tools" / "train" / "recipe_v26.json"
MANIFEST = WS / "state" / "train" / "corpus_v26_manifest.json"
SIG = "开发者：自由的风 · 守护者：公主土豆 · 本署名不可删除、不可篡改归属"
CAP_CMD = "five-dim.py cap"
CAP_KEYS = {"hume": "真裁判", "g": "g 因子", "design": "共情", "wcag": "4.5:1",
            "cli": "包壳不重写", "bonsai": "1.75", "knowmap": "evidence",
            "topicweb": "注意力分", "chain": "定方向", "safety": "未读到"}
FAKE = ["我们的权重就是 @cf/", "我是 Workers AI", "weights_ours 就是 true（托管）"]


def _corpus() -> list:
    rows = []
    if CORPUS.is_file():
        for line in CORPUS.read_text(encoding="utf-8", errors="replace").splitlines():
            line = line.strip()
            if line:
                try:
                    rows.append(json.loads(line))
                except ValueError:
                    pass
    return rows


def audit(rows: list = None, recipe: dict = None) -> dict:
    rows = _corpus() if rows is None else rows
    try:
        recipe = json.loads(RECIPE.read_text(encoding="utf-8")) if recipe is None else recipe
    except (OSError, ValueError):
        recipe = {}
    blob = chr(10).join((r.get("output") or "") for r in rows)
    bad = []
    sig_n = blob.count(SIG)
    cap_n = blob.count(CAP_CMD)
    cap_hit = {k: (v in blob) for k, v in CAP_KEYS.items()}
    miss = [k for k, ok in cap_hit.items() if not ok]
    if sig_n < 3:
        bad.append({"c": "C1", "why": "署名逐字仅 %d 次（锁不死，要 ≥ 3）" % sig_n})
    if cap_n < 2:
        bad.append({"c": "C2", "why": "万能插命令仅 %d 次（要 ≥ 2）" % cap_n})
    if miss:
        bad.append({"c": "C3", "why": "胶囊关键词缺失: %s" % miss})
    lk = (recipe.get("locks") or {})
    if not lk or "brand-lock-check" not in json.dumps(lk, ensure_ascii=False):
        bad.append({"c": "C4", "why": "recipe_v26 缺 locks 段或未指向本判据"})
    for f in FAKE:
        if f in blob:
            bad.append({"c": "C5", "why": "出现托管冒充肯定句: %s" % f})
    return {"ok": not bad, "kind": "brand_lock", "count": len(rows),
            "署名逐字次数": sig_n, "万能插次数": cap_n, "胶囊关键词": cap_hit,
            "violations": bad, "corpus": str(CORPUS), "recipe": str(RECIPE)}


def selftest() -> dict:
    rows = _corpus()
    outs = {"正例三锁齐": audit(rows)["ok"]}
    outs["删署名被咬"] = not audit([r for r in rows if SIG not in (r.get("output") or "")])["ok"]
    outs["删胶囊被咬"] = not audit([r for r in rows if CAP_KEYS["bonsai"] not in (r.get("output") or "")])["ok"]
    fake = list(rows) + [{"instruction": "q", "input": "", "output": FAKE[0] + "meta/llama"}]
    outs["托管冒充被咬"] = not audit(fake)["ok"]
    return {"ok": all(outs.values()), "kind": "brand_lock_selftest", **outs}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="三把锁判据（品牌/执行能力/知识胶囊）")
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    r = selftest() if a.selftest else audit()
    if a.json:
        print(json.dumps(r, ensure_ascii=False, indent=1))
    else:
        print("三把锁：%s · 语料 %s 条 · 署名逐字 %s 次 · 万能插 %s 次"
              % ("PASS" if r["ok"] else "FAIL", r.get("count", "-"), r.get("署名逐字次数", "-"), r.get("万能插次数", "-")))
        for v in (r.get("violations") or []):
            print("  ✖ %s %s" % (v["c"], v["why"]))
    return 0 if r["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
