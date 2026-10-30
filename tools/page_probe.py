#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""page_probe —— 页面自报读数的读取端（2026-10-30）

问题：页面好不好，以前只能"打开看一眼"。这在手机上既慢又不可复核。

做法：页面带 `?_probe=1` 打开时，自己把关键读数 POST 到桥的 `/_probe`，
      桥追加 `state/page_probes.jsonl`。本器读那个账，按页聚合出：
        · 最后一次自报是什么时候（新鲜度）
        · ok / 否
        · 关键读数（tok/s、三角形、像素亮度…）

用法：
    python3 tools/page_probe.py status          # 人读
    python3 tools/page_probe.py status --json   # 机读
    python3 tools/page_probe.py status --max-age 3600   # 只认 1 小时内的
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys
import time

ROOT = pathlib.Path(__file__).resolve().parents[1]
LEDGER = ROOT / "state" / "page_probes.jsonl"


def load() -> list:
    if not LEDGER.is_file():
        return []
    out = []
    for ln in LEDGER.read_text(encoding="utf-8").splitlines():
        ln = ln.strip()
        if not ln:
            continue
        try:
            out.append(json.loads(ln))
        except Exception:                                        # noqa: BLE001
            pass
    return out


def aggregate(max_age: float | None = None) -> dict:
    rows = load()
    now = time.time()
    per = {}
    for r in rows:
        page = r.get("page") or "?"
        try:
            t = time.mktime(time.strptime(r.get("at", ""), "%Y-%m-%dT%H:%M:%S"))
        except Exception:                                        # noqa: BLE001
            continue
        if max_age is not None and now - t > max_age:
            continue
        cur = per.get(page)
        if cur is None or t > cur["_ts"]:
            per[page] = {"page": page, "at": r.get("at"), "ok": bool(r.get("ok")),
                         "readings": r.get("readings") or {}, "_ts": t,
                         "age_s": int(now - t)}
    items = sorted(per.values(), key=lambda x: x["_ts"], reverse=True)
    for it in items:
        it.pop("_ts", None)
    ok_n = sum(1 for x in items if x["ok"])
    return {"pages": items, "total": len(items), "ok": ok_n,
            "fail": len(items) - ok_n, "ledger": str(LEDGER)}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("op", nargs="?", default="status", choices=["status"])
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--max-age", type=float, default=None,
                    help="只认这么多秒内的自报（默认不限）")
    a = ap.parse_args(argv)

    res = aggregate(a.max_age)
    if a.json:
        print(json.dumps(res, ensure_ascii=False, indent=1))
        return 0 if res["total"] else 2

    print("  页面自报账 · %d 页（ok %d / 红 %d）" % (res["total"], res["ok"], res["fail"]))
    if not res["pages"]:
        print("  还没有任何页面自报过。让页面带 ?_probe=1 打开一次。")
        return 2
    for it in res["pages"]:
        mark = "✅" if it["ok"] else "🔴"
        rd = json.dumps(it["readings"], ensure_ascii=False)
        print("   %s %-34s %5ds 前 · %s" % (mark, it["page"][-34:], it["age_s"], rd[:90]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
