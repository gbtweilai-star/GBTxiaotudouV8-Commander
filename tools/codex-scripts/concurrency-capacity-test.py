# -*- coding: utf-8 -*-
"""并发容量实测（**把"手有很多只"量成读数**）。

来历：主人 2026-09-22 立规「你要计算出现阶段最大一次性可以同时多少根触手操作这个必须记录」，
登记页 `docs/并发容量登记.md`。2026-10-12 用一次性 scratch 脚本量过一轮（512→4096）；
本件把那轮**升成正式工具**（可复跑、出 JSON、带宿主读数），免得证据只活在某次对话里。

## 口径（写死，防跑偏）

  · 单位动作 = `api.run_task('comfy_native', {'op': 'status'})` —— **一次真实过门的能力位调用**
    （不是空函数），`probe=True` 只是**不写审计台账**，先把"纯调度上限"和"审计写盘成本"分开量；
  · 线程池 = `ThreadPoolExecutor(max_workers=N)`，**一次性开满 N**（这本身是"首次建线程"的成本，
    真跑生产要用 `wf_run` 的分层池）；
  · 每条都记：成功/总 · 墙钟 · 单发中位 · 单发最大 · 调用前后**宿主可用内存**；
  · **失败就是失败**，列样例，不许把失败折叠成"波动"。

## 用法

    py -3.14 -X utf8 tools/codex-scripts/concurrency-capacity-test.py
    py -3.14 -X utf8 tools/codex-scripts/concurrency-capacity-test.py --levels 512,1024,2048,4096
    py -3.14 -X utf8 tools/codex-scripts/concurrency-capacity-test.py --json state/concurrency-last.json
"""
from __future__ import annotations

import argparse
import concurrent.futures as cf
import io
import json
import os
import sys

for _s in (sys.stdout, sys.stderr):                    # 2026-10-15 对齐：输出编码守门（本仓口径）
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


import time

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)


def mem_gb():
    try:
        import psutil
        return round(psutil.virtual_memory().available / 1e9, 2), \
            round(psutil.virtual_memory().percent)
    except Exception:  # noqa: BLE001
        return -1.0, -1


def one(api, i):
    t0 = time.time()
    try:
        r = api.run_task("comfy_native", {"op": "status"}, probe=True)
        ok = bool(r.get("ok", True)) and r.get("status") != "error"
        return ok, (time.time() - t0) * 1000, str(r.get("status"))[:24]
    except Exception as exc:  # noqa: BLE001
        return False, (time.time() - t0) * 1000, type(exc).__name__


def main(argv):
    ap = argparse.ArgumentParser(description="并发容量实测")
    ap.add_argument("--levels", default="512,1024,2048,4096")
    ap.add_argument("--json", default="")
    ap.add_argument("--kind", default="comfy_native", help="单位能力位（默认 comfy_native 的只读 status）")
    args = ap.parse_args(argv)
    levels = [int(x) for x in args.levels.split(",") if x.strip()]

    from gbt_allinone import api

    a0, pct = mem_gb()
    print("本机内存: 可用 %.2f GB（已用 %d%%）" % (a0, pct))
    print("单位动作: api.run_task('%s', {'op':'status'}, probe=True) —— 真实过门，不写审计" % args.kind)
    print("  N    | 成功/总  | 墙钟(ms) | 中位(ms) | 最大(ms) | 内存可用(GB) | 失败样例")
    rows = []
    for n in levels:
        before, _ = mem_gb()
        t0 = time.time()
        with cf.ThreadPoolExecutor(max_workers=n) as ex:
            res = list(ex.map(lambda i: one(api, i), range(n)))
        wall = (time.time() - t0) * 1000
        after, pct2 = mem_gb()
        okn = sum(1 for r in res if r[0])
        ms = sorted(r[1] for r in res)
        bad = [r[2] for r in res if not r[0]][:3]
        row = {"n": n, "ok": okn, "wall_ms": round(wall, 1),
               "median_ms": round(ms[len(ms) // 2], 2) if ms else None,
               "max_ms": round(max(ms), 2) if ms else None,
               "mem_before_gb": before, "mem_after_gb": after, "mem_used_pct": pct2,
               "fail_samples": bad}
        rows.append(row)
        print("  %-4d | %4d/%-4d | %8.0f | %8.1f | %8.1f | %6.2f→%6.2f | %s"
              % (n, okn, n, wall, row["median_ms"] or 0, row["max_ms"] or 0,
                 before, after, bad or "无"), flush=True)

    out = {"at": time.strftime("%Y-%m-%dT%H:%M:%S"), "python": sys.version.split()[0],
           "kind": args.kind, "probe": True, "levels": rows,
           "host_mem_total_gb": round((__import__("psutil").virtual_memory().total / 1e9), 2)
           if _has_psutil() else None}
    if args.json:
        p = args.json if os.path.isabs(args.json) else os.path.join(ROOT, args.json)
        io.open(p, "w", encoding="utf-8", newline="\n").write(
            json.dumps(out, ensure_ascii=False, indent=1))
        print("读数落盘: %s" % os.path.relpath(p, ROOT))
    fails = sum(1 for r in rows for _ in r["fail_samples"])
    print("== 汇总：%d 级 · 最高 %d 根 · 零失败=%s =="
          % (len(rows), max(levels), fails == 0))
    return 0 if fails == 0 else 1


def _has_psutil():
    try:
        import psutil  # noqa: F401
        return True
    except Exception:  # noqa: BLE001
        return False


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
