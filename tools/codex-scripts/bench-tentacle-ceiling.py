# -*- coding: utf-8 -*-
"""极限触手 · 并发天花板台架（真跑，往上压到起不动为止）。

和 `bench-cap-concurrency.py` 的区别：**它只压到 4096**，这个继续往上压，并且把三件事分开记：

  1. **起不动的那个点**：线程创建失败（`can't start new thread` / RuntimeError）—— 这是硬天花板；
  2. **内存天花板**：可用内存 < 0.35GB 立即停（不许把主人的机器压死）；
  3. **吞吐最优区间**：同一批任务用「小池子」跑（默认 256 并发），算真实吞吐 ——
     并发数 ≠ 吞吐，4096 根同时在线时中位延迟 10.9s，吞吐只有 ~260/s。

口径（写死，先声明再跑）：
  · 只调 `echo`（纯回显，不写盘/不出网/不起进程）⇒ 测的是**调度骨架**，不是外部依赖；
  · 成功 = 回执 `status == "ok"`；起不动/超时/异常分别计数，**不混成一句"失败"**；
  · 任何 N 只要不是 100% 成功，**就不写进"最高多少根"这个结论**。

产物：outputs/open-source-release/data/concurrency-ceiling.json
用法：py -3.14 -X utf8 tools/codex-scripts/bench-tentacle-ceiling.py
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
LADDER = [1024, 2048, 4096, 6144, 8192, 12288, 16384, 20000]
POOL_THROUGHPUT = [(256, 4096), (64, 4096)]        # (并发数, 任务数)
MEM_FLOOR_GB = 0.35


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

    before = mem()
    print("本机：总 %.2f GB · 可用 %.2f GB（已用 %d%%）" % (before["total_gb"], before["avail_gb"],
                                                          before["used_pct"]))
    rows, ceiling = [], None

    for n in LADDER:
        avail = mem()["avail_gb"]
        if avail < MEM_FLOOR_GB:
            rows.append({"n": n, "skipped": "可用内存 %.2fGB < %.2fGB 门槛，主动停" % (avail, MEM_FLOOR_GB)})
            print("N=%-5d 跳过：可用内存 %.2fGB 已低于门槛" % (n, avail))
            break
        lat, ok, err, first_err = [], 0, 0, None
        m0 = mem()
        t0 = time.time()

        def one(_i):
            s = time.perf_counter()
            try:
                r = API.run_task(CAP, {"text": "ping"})
                good = isinstance(r, dict) and r.get("status") == "ok"
                return good, (time.perf_counter() - s) * 1000, None
            except Exception as exc:                               # noqa: BLE001
                return False, (time.perf_counter() - s) * 1000, "%s: %s" % (type(exc).__name__,
                                                                           str(exc)[:90])

        try:
            with ThreadPoolExecutor(max_workers=n) as ex:
                for good, ms, exc in ex.map(one, range(n)):
                    lat.append(ms)
                    if good:
                        ok += 1
                    else:
                        err += 1
                        first_err = first_err or exc
        except Exception as exc:                                   # noqa: BLE001
            rows.append({"n": n, "start_error": "%s: %s" % (type(exc).__name__, str(exc)[:120])})
            print("N=%-5d 起不动：%s %s" % (n, type(exc).__name__, str(exc)[:90]))
            break

        wall = time.time() - t0
        m1 = mem()
        row = {"n": n, "ok": ok, "err": err, "first_error": first_err,
               "wall_s": round(wall, 2),
               "median_ms": round(statistics.median(lat), 1) if lat else None,
               "p95_ms": round(sorted(lat)[int(len(lat) * 0.95)], 1) if lat else None,
               "max_ms": round(max(lat), 1) if lat else None,
               "mem_avail_before": m0["avail_gb"], "mem_avail_after": m1["avail_gb"],
               "mem_delta_gb": round(m1["avail_gb"] - m0["avail_gb"], 2),
               "throughput_per_s": round(n / wall, 1) if wall else None}
        rows.append(row)
        print("N=%-5d 成功 %d/%d · 墙钟 %.2fs · 中位 %.0fms · p95 %.0fms · 内存 %.2f→%.2fGB · %.0f/s"
              % (n, ok, n, wall, row["median_ms"] or 0, row["p95_ms"] or 0,
                 m0["avail_gb"], m1["avail_gb"], row["throughput_per_s"] or 0))
        if ok == n and not err:
            ceiling = n
        else:
            print("      ⚠ 未全成功（err=%d 首例=%s）⇒ 天花板到此为止，不写进结论" % (err, first_err))
            break

    # 吞吐最优区间：并发数 ≠ 吞吐
    pools = []
    for workers, tasks in POOL_THROUGHPUT:
        if mem()["avail_gb"] < MEM_FLOOR_GB:
            break
        lat, ok = [], 0
        t0 = time.time()
        with ThreadPoolExecutor(max_workers=workers) as ex:
            for good, ms in ex.map(lambda _i: (isinstance(API.run_task(CAP, {"text": "ping"}), dict),
                                              0.0), range(tasks)):
                ok += int(good)
        wall = time.time() - t0
        pools.append({"workers": workers, "tasks": tasks, "ok": ok,
                      "wall_s": round(wall, 2), "throughput_per_s": round(tasks / wall, 1)})
        print("池 %-4d 并发 × %d 任务：成功 %d · 墙钟 %.2fs · %.0f/s"
              % (workers, tasks, ok, wall, tasks / wall))

    doc = {"at": time.strftime("%Y-%m-%dT%H:%M:%S"), "schema": "concurrency-ceiling-v1",
           "cap": CAP, "note": "echo 纯回显：测调度骨架，不测外部依赖上限",
           "memory_before": before, "mem_floor_gb": MEM_FLOOR_GB,
           "max_all_ok": ceiling,
           "ladder": rows, "pool_throughput": pools,
           "verdict": ("最高 N=%s 全部成功" % ceiling) if ceiling else "没有一档全成功"}
    p = ROOT / "outputs/open-source-release/data/concurrency-ceiling.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(doc, ensure_ascii=False, indent=1), encoding="utf-8")
    print("\n结论：%s" % doc["verdict"])
    print("落盘：", p.relative_to(ROOT))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
