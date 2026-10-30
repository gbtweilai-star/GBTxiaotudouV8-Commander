#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""tentacle_dispatch —— 总指挥派触手：一根吃力就加根，内存够就无限派

主人令（2026-10-30 原话）：
「如果一个任务一根触手 LLM 操作起来吃力或者时间长，可以派第二根触手 LLM 协助执行加速，
  只要运行内存足够可以无限制派遣触手干活。」

## 它和压测件的分工（别再造成重复件）
`tentacle_bench` / `fanout_bench` / `tentacle_llm_bench` 回答「本机能同时伸几根」——**只测不干**。
本器回答「这件事现在该派几根、派谁」——**真干活**，并把为什么加根记成账。

## 三档调度（不猜，全按实测）
    ① 起步 1 根
    ② 加根信号（任一成立就加）：
         · 有单元跑了超过 stall_s 还没回来（吃力）
         · 整体速率 < target_rps 且队列里还积着（来不及）
    ③ 上限 = 内存实测：
         cap = (MemFree - reserve_mb) // 每根实测占用
       每根占用不是拍脑袋 —— 是**真起了一根之后量出来的**，且随内存变化重算。

## 怎么保证不重复干
队列是「一个单元一个文件」，worker 靠 **rename 抢占**（原子操作）拿活。
抢到了才跑，抢不到就跳。所以派多少根都不会把同一件事干两遍。

## 口径
· 每根触手都是一条独立车道：独立进程 + 独立文件锁，不共享内存。
· 失败必须分类（timeout / denied / error / empty），不许笼统说"失败"。
· 加根/减根都写 `state/tentacle_dispatch.jsonl`，事后能复盘「当时为什么派了 4 根」。

用法：
    python3 tools/tentacle_dispatch.py --demo            # 自测：40 个单元，看它自己加根
    python3 tools/tentacle_dispatch.py --units u.jsonl --out r.jsonl [--max 16] [--stall 3]
"""
from __future__ import annotations

import json
import os
import pathlib
import queue
import shutil
import subprocess
import sys
import time

ROOT = pathlib.Path(__file__).resolve().parents[1]
LOG = ROOT / "state" / "tentacle_dispatch.jsonl"
RESERVE_MB = int(os.environ.get("GBT_DISPATCH_RESERVE_MB") or 220)


def mem_free_mb() -> int:
    try:
        for ln in open("/proc/meminfo", encoding="utf-8"):
            if ln.startswith("MemFree:"):
                return int(ln.split()[1]) // 1024
    except Exception:                                             # noqa: BLE001
        pass
    return 0


def _rss_mb(pid: int) -> float:
    try:
        st = open("/proc/%d/statm" % pid).read().split()
        return int(st[1]) * 4096 / 1048576
    except Exception:                                             # noqa: BLE001
        return 0.0


def _log(rec: dict) -> None:
    try:
        LOG.parent.mkdir(parents=True, exist_ok=True)
        with open(LOG, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
    except Exception:                                             # noqa: BLE001
        pass


# ── worker：抢活就跑 ────────────────────────────────────────────────────────
def worker_main(args: list) -> int:
    qdir = pathlib.Path(args[0])
    odir = pathlib.Path(args[1])
    odir.mkdir(parents=True, exist_ok=True)
    while True:
        # 抢活：rename 是原子的，抢到才算我的
        claimed = None
        for p in sorted(qdir.glob("*.todo")):
            tgt = p.with_suffix(".run")
            try:
                os.rename(p, tgt)
                claimed = tgt
                break
            except OSError:
                continue
        if claimed is None:
            return 0
        try:
            unit = json.loads(claimed.read_text(encoding="utf-8"))
        except Exception:                                         # noqa: BLE001
            claimed.replace(claimed.with_suffix(".bad"))
            continue
        t0 = time.time()
        # 自测单元：给固定成本的活，用来量**调度本身**的加速比，
        # 不掺能力位的真实耗时（那是个变量，量不出调度好坏）。
        if unit.get("sleep"):
            time.sleep(float(unit["sleep"]))
            rec = {"unit": unit.get("id"), "status": "ok", "ok": True,
                   "ms": round((time.time() - t0) * 1000), "synthetic": True}
            (odir / ("%s.json" % unit.get("id"))).write_text(
                json.dumps(rec, ensure_ascii=False), encoding="utf-8")
            claimed.unlink(missing_ok=True)
            continue
        try:
            sys.path.insert(0, str(ROOT))
            from gbt_allinone.api import run_task
            # 2026-10-30：单任务硬超时。有些位会挂很久（网络/外部服务），
            # 不设上限会让整批派发被一个位拖死（实测心跳一轮 14 分钟跑不完）。
            _to = float(unit.get("timeout") or 8.0)
            try:
                import signal as _sig

                def _alarm(_s, _f):
                    raise TimeoutError("unit timeout %.0fs" % _to)
                _old = _sig.signal(_sig.SIGALRM, _alarm)
                _sig.setitimer(_sig.ITIMER_REAL, _to)
                try:
                    r = run_task(unit.get("kind") or "health", unit.get("payload") or {})
                finally:
                    _sig.setitimer(_sig.ITIMER_REAL, 0)
                    _sig.signal(_sig.SIGALRM, _old)
            except TimeoutError as _te:
                r = {"status": "timeout", "error": str(_te)}
            st = r.get("status") or "?"
            rec = {"unit": unit.get("id"), "status": st, "ok": st not in ("denied", "error", "timeout"),
                   "ms": round((time.time() - t0) * 1000),
                   "sample": str(r.get("result") or {})[:200]}
        except Exception as exc:                                  # noqa: BLE001
            rec = {"unit": unit.get("id"), "status": "error", "ok": False,
                   "ms": round((time.time() - t0) * 1000),
                   "error": "%s: %s" % (type(exc).__name__, str(exc)[:100])}
        try:
            (odir / ("%s.json" % unit.get("id"))).write_text(
                json.dumps(rec, ensure_ascii=False), encoding="utf-8")
        except Exception:                                         # noqa: BLE001
            pass
        claimed.unlink(missing_ok=True)


# ── dispatcher：一根起步，吃力就加根 ───────────────────────────────────────
def dispatch(units: list, *, max_workers: int = 16, stall_s: float = 4.0,
             target_rps: float = 0.4, verbose: bool = True) -> dict:
    run_id = str(int(time.time() * 1000))
    base = pathlib.Path("/tmp/dispatch_%s" % run_id)
    qdir, odir = base / "queue", base / "done"
    qdir.mkdir(parents=True, exist_ok=True)
    for i, u in enumerate(units):
        u = dict(u)
        u.setdefault("id", "u%03d" % i)
        (qdir / ("%s.todo" % u["id"])).write_text(
            json.dumps(u, ensure_ascii=False), encoding="utf-8")

    procs, per_worker_mb, rss_samples = [], 0.0, []
    history, t_start = [], time.time()
    total = len(units)
    last_done, last_t = 0, t_start

    # 2026-10-30 实测：worker 里的 SIGALRM 打不断**阻塞在 C 层**的调用
    # （socket recv 之类），于是单个单元能把整批拖死（实测 290/291 卡住 15 分钟）。
    # 派发器这边补一道**硬杀**：某批跑超 KILL_AFTER 秒就把 worker 全清掉，记一笔再收尾。
    KILL_AFTER = 120.0

    def spawn() -> bool:
        nonlocal per_worker_mb
        p = subprocess.Popen([sys.executable, "-u", str(pathlib.Path(__file__).resolve()),
                              "--worker", str(qdir), str(odir)],
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        procs.append(p)
        time.sleep(0.6)
        r = _rss_mb(p.pid)
        if r > 1:
            rss_samples.append(r)
            per_worker_mb = sum(rss_samples) / len(rss_samples)
        history.append({"at": time.strftime("%H:%M:%S"), "act": "spawn",
                        "workers": len(procs), "per_worker_mb": round(per_worker_mb, 1),
                        "mem_mb": mem_free_mb()})
        return True

    def cap() -> int:
        free = mem_free_mb()
        if per_worker_mb <= 0:
            return min(max_workers, 2)
        n = int(max(1, (free - RESERVE_MB) // per_worker_mb))
        return max(1, min(max_workers, n))

    spawn()
    while True:
        time.sleep(0.5)
        done = len(list(odir.glob("*.json")))
        running = len(list(qdir.glob("*.run")))
        left = len(list(qdir.glob("*.todo")))
        if verbose:
            print("   [%s] 完成 %d/%d · 在跑 %d · 待领 %d · 车道 %d"
                  % (time.strftime("%H:%M:%S"), done, total, running, left, len(procs)),
                  flush=True)
        if done >= total or (left == 0 and running == 0):
            break
        if time.time() - t_start > KILL_AFTER and (total - done) <= 2:
            # 只剩个别卡死单元：清掉 worker，按已完成数收尾（如实记 stuck）
            for p_ in procs:
                try: p_.kill()
                except Exception: pass
            history.append({"at": time.strftime("%H:%M:%S"), "act": "kill_stuck",
                            "done": done, "total": total})
            break
        now = time.time()
        dt = now - last_t
        rate = (done - last_done) / dt if dt > 0.3 else 0.0
        idle_workers = len(procs) - running
        # 加根信号：吃力（有 run 超过 stall）或来不及（速率低且还有待领）
        stalled = running >= len(procs) and (now - t_start) > stall_s and rate < 1e-6
        slow = rate < target_rps and left > 0
        if (stalled or slow) and idle_workers <= 0 and len(procs) < cap():
            spawn()
        last_done, last_t = done, now
        if left == 0 and running > 0 and len(procs) < cap():
            pass          # 已全在跑，等它们回来

    for p in procs:
        try:
            p.wait(timeout=30)
        except Exception:                                         # noqa: BLE001
            p.kill()
    elapsed = time.time() - t_start

    results, by_status = [], {}
    for f in sorted(odir.glob("*.json")):
        try:
            r = json.loads(f.read_text(encoding="utf-8"))
        except Exception:                                         # noqa: BLE001
            continue
        results.append(r)
        by_status[r.get("status")] = by_status.get(r.get("status"), 0) + 1

    out = {"run": run_id, "units": total, "done": len(results), "results": results,
           "workers_used": len(procs), "elapsed_s": round(elapsed, 1),
           "per_worker_mb": round(per_worker_mb, 1),
           "rps": round(len(results) / elapsed, 2) if elapsed else None,
           "by_status": by_status, "history": history,
           "mem_free_mb": mem_free_mb()}
    shutil.rmtree(base, ignore_errors=True)
    _log(out)
    return out


def demo(verbose: bool = True) -> dict:
    """自测：40 个只读单元，看它会不会自己加根、加了几根、为什么。"""
    kinds = ["health", "asset_index", "memory_manager", "source_registry_health"]
    units = []
    for i in range(40):
        k = kinds[i % len(kinds)]
        units.append({"id": "u%03d" % i, "kind": k, "payload": {}})
    return dispatch(units, max_workers=6, stall_s=3.0, target_rps=2.0, verbose=verbose)


def main(argv: list) -> int:
    if "--worker" in argv:
        i = argv.index("--worker")
        return worker_main(argv[i + 1:i + 3])
    if "--demo" in argv:
        r = demo()
        print("   ── 派发结果 ──")
        print("   单元 %d · 完成 %d · 车道 %d · 用时 %.1fs · %.2f 单元/秒"
              % (r["units"], r["done"], r["workers_used"], r["elapsed_s"], r["rps"] or 0))
        print("   每根实测占用 %.1f MB · 内存剩 %d MB" % (r["per_worker_mb"], r["mem_free_mb"]))
        print("   状态分布 %s" % r["by_status"])
        print("   加根轨迹 %s" % [h["act"] for h in r["history"]])
        return 0
    uf = None
    for flag in ("--units",):
        if flag in argv:
            uf = argv[argv.index(flag) + 1]
    if not uf:
        print(__doc__)
        return 2
    units = [json.loads(l) for l in open(uf, encoding="utf-8") if l.strip()]
    mx = int(argv[argv.index("--max") + 1]) if "--max" in argv else 16
    st = float(argv[argv.index("--stall") + 1]) if "--stall" in argv else 4.0
    r = dispatch(units, max_workers=mx, stall_s=st)
    print(json.dumps({k: v for k, v in r.items() if k != "history"},
                     ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
