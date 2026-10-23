# -*- coding: utf-8 -*-
"""触手并发爆发力台架（真跑）：N 路同时调能力位，测成功率/中位/最大/内存。

为什么用 `echo`：它是**纯回显**（不写盘、不出网、不起进程），
测的是"并发调度与审计这条骨架"，不是某个外部依赖的上限。

判读（先写死）：
  · 成功率 < 100% ⇒ 先看是不是线程创建失败/审计写盘抢锁（分开统计，不混成一句"失败"）
  · 内存可用 < 300MB ⇒ 立即停止（不许把机器压死）
产出：outputs/open-source-release/data/concurrency-bench.json
用法：py -3.14 -X utf8 tools/codex-scripts/bench-cap-concurrency.py
"""
from __future__ import annotations

import ctypes
import json
import pathlib
import statistics
import sys
import time
from concurrent.futures import ThreadPoolExecutor
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        pass

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

CAP = "echo"


class MEMORYSTATUSEX(ctypes.Structure):
    _fields_ = [("dwLength", ctypes.c_ulong), ("dwMemoryLoad", ctypes.c_ulong),
                ("ullTotalPhys", ctypes.c_ulonglong), ("ullAvailPhys", ctypes.c_ulonglong),
                ("ullTotalPageFile", ctypes.c_ulonglong), ("ullAvailPageFile", ctypes.c_ulonglong),
                ("ullTotalVirtual", ctypes.c_ulonglong), ("ullAvailVirtual", ctypes.c_ulonglong),
                ("ullAvailExtendedVirtual", ctypes.c_ulonglong)]


def mem() -> dict:
    m = MEMORYSTATUSEX()
    m.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
    ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(m))
    return {"total_gb": round(m.ullTotalPhys / 2**30, 2),
            "avail_gb": round(m.ullAvailPhys / 2**30, 2),
            "used_pct": int(m.dwMemoryLoad)}


def main() -> int:
    from gbt_allinone import api as API

    sizes = [512, 1024, 2048, 4096]
    rows = []
    before = mem()
    print("本机内存：总 %.2f GB · 可用 %.2f GB（已用 %d%%）"
          % (before["total_gb"], before["avail_gb"], before["used_pct"]))

    for n in sizes:
        if mem()["avail_gb"] < 0.3:
            print("⚠ 可用内存 < 0.3GB，停止加压")
            break
        lat, errs, ok = [], 0, 0
        m0 = mem()
        t0 = time.time()

        def one(_i):
            s = time.time()
            try:
                r = API.run_task(CAP, {"text": "ping"})
                good = isinstance(r, dict) and r.get("status") == "ok"
                return good, (time.time() - s) * 1000
            except Exception:                                       # noqa: BLE001
                return False, (time.time() - s) * 1000

        try:
            with ThreadPoolExecutor(max_workers=n) as ex:
                for good, ms in ex.map(one, range(n)):
                    lat.append(ms)
                    if good:
                        ok += 1
                    else:
                        errs += 1
        except Exception as e:                                      # noqa: BLE001
            print("  起 %d 线程失败：%s %s（如实记，不当成功）" % (n, type(e).__name__, str(e)[:100]))
            rows.append({"n": n, "start_error": "%s: %s" % (type(e).__name__, str(e)[:120])})
            continue
        wall = time.time() - t0
        m1 = mem()
        row = {"n": n, "ok": ok, "err": errs, "wall_s": round(wall, 2),
               "median_ms": round(statistics.median(lat), 2) if lat else None,
               "p95_ms": round(sorted(lat)[int(len(lat) * 0.95)] if lat else 0, 2),
               "max_ms": round(max(lat), 2) if lat else None,
               "mem_avail_before": m0["avail_gb"], "mem_avail_after": m1["avail_gb"],
               "mem_delta_gb": round(m1["avail_gb"] - m0["avail_gb"], 2),
               "throughput_per_s": round(n / wall, 1) if wall else None}
        rows.append(row)
        print("N=%-5d 成功 %d/%d · 墙钟 %.2fs · 中位 %.2fms · p95 %.2fms · 最大 %.2fms · 内存可用 %.2f→%.2fGB · %.0f/s"
              % (n, ok, n, wall, row["median_ms"] or 0, row["p95_ms"] or 0,
                 row["max_ms"] or 0, m0["avail_gb"], m1["avail_gb"], row["throughput_per_s"] or 0))

    # 第二轮：同规模复跑（区分"首次建线程成本"与"稳态成本"）
    repeat = []
    for n in (1024, 2048):
        lat, ok = [], 0
        t0 = time.time()

        def one2(_i):
            s = time.time()
            r = API.run_task(CAP, {"text": "ping"})
            return (isinstance(r, dict) and r.get("status") == "ok"), (time.time() - s) * 1000

        with ThreadPoolExecutor(max_workers=n) as ex:
            for good, ms in ex.map(one2, range(n)):
                lat.append(ms)
                ok += int(good)
        wall = time.time() - t0
        repeat.append({"n": n, "ok": ok, "wall_s": round(wall, 2),
                       "median_ms": round(statistics.median(lat), 2)})
        print("复跑 N=%-5d 成功 %d/%d · 墙钟 %.2fs · 中位 %.2fms"
              % (n, ok, n, wall, repeat[-1]["median_ms"]))

    out = {"at": time.strftime("%Y-%m-%dT%H:%M:%S"), "cap": CAP,
           "note": "echo 为纯回显能力位：测并发调度骨架，不测外部依赖上限",
           "memory_before": before, "rows": rows, "repeat": repeat}
    p = ROOT / "outputs/open-source-release/data/concurrency-bench.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print("落盘：", p.relative_to(ROOT))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
