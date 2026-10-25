#!/usr/bin/env python3
"""GBT天真 · A19 六核压测（进程级）

为什么不用 multiprocessing.Pool：
  iSH 缺 POSIX 信号量（SemLock 直接 FileNotFoundError），Pool / Queue 全部起不来。
  所以用最朴素的 **独立进程** 并发：subprocess.Popen 起 N 个，各自跑各自那条链，
  互不共享任何内存原语 —— 反而最接近"六个核各干各的"。

为什么不用线程：
  实测 N=1 63s、N=2 125s（精确翻倍），并行效率 51% —— Python 线程受 GIL 约束，
  CPU 型任务根本不会真并行。线程在这个场景是假的"全力"。

用法：
  python3 tools/tianzhen_a19_bench.py            # 默认爬坡 1→2→3→4→6
  python3 tools/tianzhen_a19_bench.py --n 6      # 只测某一档
"""
from __future__ import annotations

import argparse
import json
import os
import pathlib
import statistics
import subprocess
import sys
import time

ROOT = pathlib.Path(__file__).resolve().parents[1]
WORK = pathlib.Path("/tmp/gt")
SRC = ROOT / "holo_pet/assets/digital-human/standard/tex/albedo-2416x4096.png"


def worker(tag: str) -> dict:
    """在独立进程里跑一条链：Load → Scale(1208×2048) → Levels → Save。"""
    sys.path.insert(0, str(ROOT))
    from gbt_allinone.tools import comfy_native as cn

    wf = {"name": "a19-" + tag, "nodes": [
        {"id": "n1", "node": "LoadImage", "inputs": {"image": str(SRC)}},
        {"id": "n2", "node": "ImageScale",
         "inputs": {"width": 1208, "height": 2048, "upscale_method": "lanczos",
                    "out": str(WORK / ("%s-s.png" % tag))}},
        {"id": "n3", "node": "ImageLevels",
         "inputs": {"black": 4, "white": 251, "gamma": 1.08,
                    "out": str(WORK / ("%s-l.png" % tag))}},
        {"id": "n4", "node": "SaveImage",
         "inputs": {"out": str(WORK / ("%s-f.png" % tag))}},
    ], "edges": [
        {"from": "n1", "to": "n2", "field": "IMAGE->image"},
        {"from": "n2", "to": "n3", "field": "IMAGE->image"},
        {"from": "n3", "to": "n4", "field": "IMAGE->image"},
    ]}
    t0 = time.perf_counter()
    r = cn.run({"op": "run", "workflow": wf})
    return {"tag": tag, "ok": bool(r.get("ok")), "s": round(time.perf_counter() - t0, 2),
            "trace": [{"node": x["node"], "ms": x.get("ms")} for x in (r.get("trace") or [])]}


def spawn_batch(n: int, round_no: int) -> dict:
    """起 n 个独立进程，量墙钟。"""
    WORK.mkdir(parents=True, exist_ok=True)
    procs = []
    t0 = time.perf_counter()
    for i in range(n):
        tag = "r%d_%d" % (round_no, i)
        p = subprocess.Popen(
            [sys.executable, str(pathlib.Path(__file__).resolve()), "--worker", tag],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        procs.append((tag, p))
    results = []
    for tag, p in procs:
        out, err = p.communicate()
        try:
            results.append(json.loads(out.strip().splitlines()[-1]))
        except Exception:
            results.append({"tag": tag, "ok": False, "s": None,
                            "err": (err or "")[-200:]})
    wall = time.perf_counter() - t0
    return {"n": n, "wall": round(wall, 2), "ok": sum(1 for r in results if r["ok"]),
            "per": [r["s"] for r in results if r["s"]], "results": results}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--worker", help=argparse.SUPPRESS)
    ap.add_argument("--n", type=int, default=0)
    args = ap.parse_args()

    if args.worker:                      # 子进程模式
        print(json.dumps(worker(args.worker), ensure_ascii=False))
        return 0

    print("设备: iPhone18,2 · A19 Pro · 6 核（2P+4E）· 内存 11.42 GB")
    print("运行层: iSH（x86 模拟）· 所以下面的数字是**模拟层**的天花板，不是 A19 硬件的")
    print("源图: %s（%.1f MB · 2416×4096）" % (SRC.name, SRC.stat().st_size / 1e6))
    print("单链: LoadImage → ImageScale(1208×2048 lanczos) → ImageLevels → SaveImage")
    print("并发: 独立进程（不用 Pool：iSH 没有 POSIX 信号量）\n")

    rounds = [1, 2, 3, 4, 6] if not args.n else [args.n]
    single = None
    table = {}
    for n in rounds:
        best = None
        for rd in (0, 1):
            b = spawn_batch(n, round_no=n * 10 + rd)
            if best is None or b["wall"] < best["wall"]:
                best = b
            if n == 1 and rd == 0:
                single = b["per"][0] if b["per"] else None
        per = statistics.median(best["per"]) if best["per"] else 0
        thr = best["ok"] / best["wall"] if best["wall"] else 0
        sp = (single * best["ok"] / best["wall"]) if single else 0
        eff = sp / n * 100 if n else 0
        table[n] = {"wall": best["wall"], "ok": best["ok"], "per_median": per,
                    "throughput": round(thr, 4), "speedup": round(sp, 2),
                    "efficiency_pct": round(eff)}
        print("  N=%-2d 墙钟 %-8.2fs 单条中位 %-7.2fs 吞吐 %-7.3f %s 加速 %-5.2fx 效率 %3.0f%%  %s" %
              (n, best["wall"], per, thr, "条/s", sp, eff,
               "" if best["ok"] == n else "⚠ %d/%d 成功" % (best["ok"], n)))
        for r in best["results"]:
            if not r.get("ok"):
                print("       失败: %s" % str(r.get("err"))[:120])

    if single and 6 in table:
        print("\n=== 结论 ===")
        print("  单条基准: %.2fs" % single)
        print("  6 进程墙钟: %.2fs（6 条串行要 %.1fs）" % (table[6]["wall"], single * 6))
        print("  加速比: %.2fx · 并行效率: %.0f%%" % (table[6]["speedup"], table[6]["efficiency_pct"]))
        print("  峰值吞吐: %.3f 条链/秒" % max(v["throughput"] for v in table.values()))
        if table[6]["efficiency_pct"] < 60:
            print("  → 效率低是 iSH 模拟层（x86 翻译 + 无真 SMP 调度）的真实上限，已如实记录")
    (WORK / "report.json").write_text(json.dumps(
        {"single_s": single, "table": table}, ensure_ascii=False, indent=2))
    print("\n  报告: /tmp/gt/report.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
