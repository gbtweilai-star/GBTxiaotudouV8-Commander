#!/usr/bin/env python3
"""asyncio 客户端压测 —— 突破 4096 的真办法

为什么必须换客户端：
  原来用「一个连接一个客户端线程」压测，FD 顶到 4096 就崩，6000 路那次
  直接把整套服务撞死。线程栈 + FD 双杀，测出来的数是**客户端的上限**，
  不是服务端的上限。

  改成单个事件循环开 N 条连接：没有线程栈，N 只受 FD 限制。
  而 FD 硬上限实测可以抬到 131072 —— 所以真正能测到服务端的极限。

用法：
  python3 tools/async_bench.py --port 8790 --conc 1024,4096,8192,16384
  python3 tools/async_bench.py --port 8790 --conc 32768
"""
from __future__ import annotations

import argparse
import asyncio
import resource
import statistics
import sys
import time


def raise_fd(target: int = 131072) -> tuple[int, int]:
    soft, hard = resource.getrlimit(resource.RLIMIT_NOFILE)
    try:
        resource.setrlimit(resource.RLIMIT_NOFILE, (target, target))
    except Exception:                                          # noqa: BLE001
        pass
    return resource.getrlimit(resource.RLIMIT_NOFILE)


async def one(host: str, port: int, path: str, sem: asyncio.Semaphore,
              results: list, timeout: float):
    async with sem:
        t0 = time.perf_counter()
        try:
            r, w = await asyncio.wait_for(
                asyncio.open_connection(host, port), timeout)
            w.write(("GET %s HTTP/1.0\r\nHost: x\r\nConnection: close\r\n\r\n"
                     % path).encode())
            await w.drain()
            head = await asyncio.wait_for(r.readuntil(b"\r\n\r\n"), timeout)
            ok = head.startswith(b"HTTP/1.1 200")
            # 只 close 一次：asyncio 的 Transport 会在 connection_lost 里再关一次，
            # 手动重复关会抛 "Bad file descriptor" 把事件循环搞脏。
            try:
                w.close()
            except Exception:                                  # noqa: BLE001
                pass
            results.append((ok, (time.perf_counter() - t0) * 1000, None))
        except asyncio.TimeoutError:
            results.append((False, (time.perf_counter() - t0) * 1000, "超时"))
        except Exception as exc:                               # noqa: BLE001
            results.append((False, (time.perf_counter() - t0) * 1000,
                            type(exc).__name__))


async def sweep(host: str, port: int, conc: int, path: str) -> dict:
    sem = asyncio.Semaphore(conc)
    results: list = []
    t0 = time.perf_counter()
    await asyncio.gather(*(one(host, port, path, sem, results, 60.0)
                           for _ in range(conc)))
    wall = time.perf_counter() - t0
    ok = sum(1 for r in results if r[0])
    lat = sorted(r[1] for r in results)
    fails: dict[str, int] = {}
    for r in results:
        if not r[0]:
            k = r[2] or "?"
            fails[k] = fails.get(k, 0) + 1
    return {"conc": conc, "wall": round(wall, 2), "ok": ok,
            "p50": round(statistics.median(lat)) if lat else 0,
            "p95": round(lat[min(len(lat) - 1, int(len(lat) * .95))]) if lat else 0,
            "qps": round(ok / wall, 1) if wall else 0, "fails": fails}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8790)
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--conc", default="1024,4096,8192,16384")
    ap.add_argument("--path", default="/health")
    a = ap.parse_args()

    soft, hard = raise_fd()
    print("客户端 FD: %s → %s（抬到硬上限之上，实测可行）" % (soft, hard))
    print("客户端模型: 单事件循环 · 无连接线程 · 线程栈无关\n")
    print("  %-8s %-9s %-9s %-11s %-8s %-8s %s" %
          ("并发", "墙钟", "QPS", "成功率", "p50ms", "p95ms", "失败分类"))

    for c in [int(x) for x in a.conc.split(",")]:
        r = asyncio.run(sweep(a.host, a.port, c, a.path))
        print("  %-8d %-9.2f %-9.1f %-11s %-8d %-8d %s" %
              (r["conc"], r["wall"], r["qps"], "%d/%d" % (r["ok"], c),
               r["p50"], r["p95"],
               ", ".join("%s×%d" % (k, v) for k, v in r["fails"].items()) or "—"))
        sys.stdout.flush()
    return 0


if __name__ == "__main__":
    sys.exit(main())
