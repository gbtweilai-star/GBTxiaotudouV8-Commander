#!/usr/bin/env python3
"""多进程扇出 · 实冲四位数并发

为什么必须扇出：
  单进程是 thread-per-request，实测 512 路就顶天（1024 路开始 TimeoutError，
  2048 路 can't start new thread）。线程模型的天花板不是内存，是"一个连接一个线程"。

扇出口径（跟框架设计一致：每根触手挂自己那条车道）：
  起 N 个**独立进程**，各自一个 HTTP 端口，各跑各的线程池。
  客户端按 lane = i % N 自己选端口 —— 不需要中心调度器（那会成为新瓶颈）。

量两件事，分开量，不混：
  A. 闸容量：打本地 /health（不走 LLM），看纯服务端能扛多少并发
  B. 真请求：走 /v1/chat/completions，看总吞吐与失败分类

用法：
  python3 tools/fanout_bench.py --lanes 6 --conc 256,512,1024,2048
  python3 tools/fanout_bench.py --stop          # 收掉所有扇出实例
"""
from __future__ import annotations

import argparse
import json
import os
import pathlib
import resource
import socket
import statistics
import subprocess
import sys
import threading
import time

ROOT = pathlib.Path(__file__).resolve().parents[1]
BASE_PORT = 8801
LOG = ROOT / "logs"


def up(port: int, timeout: float = 1.5) -> bool:
    s = socket.socket()
    s.settimeout(timeout)
    try:
        s.connect(("127.0.0.1", port))
        return True
    except OSError:
        return False
    finally:
        s.close()


def start_lanes(n: int) -> list[int]:
    LOG.mkdir(parents=True, exist_ok=True)
    ports = []
    for i in range(n):
        p = BASE_PORT + i
        ports.append(p)
        if up(p):
            continue
        with open(LOG / ("fanout_%d.log" % p), "wb") as fh:
            subprocess.Popen(
                [sys.executable, "-u", str(ROOT / "runtime" / "model_bridge.py"),
                 "--port", str(p)],
                cwd=str(ROOT), stdout=fh, stderr=fh, start_new_session=True)
    t0 = time.time()
    while time.time() - t0 < 100:
        if all(up(p) for p in ports):
            return ports
        time.sleep(2)
    return [p for p in ports if up(p)]


def stop_lanes() -> None:
    subprocess.run(["pkill", "-f", "model_bridge.py --port 88"], check=False)
    print("  已收掉扇出实例（8801+）")


def http_get(port: int, path: str = "/health", timeout: float = 40.0):
    s = socket.socket()
    s.settimeout(timeout)
    try:
        s.connect(("127.0.0.1", port))
        s.sendall(("GET %s HTTP/1.0\r\nHost: x\r\nConnection: close\r\n\r\n"
                   % path).encode())
        b = b""
        while True:
            c = s.recv(65536)
            if not c:
                break
            b += c
        ok = b.startswith(b"HTTP/1.") and b" 200" in b.split(b"\r\n")[0]
        return ok, b
    except OSError as e:
        return False, type(e).__name__.encode()
    finally:
        s.close()


def sweep(ports: list[int], conc: int, path: str) -> dict:
    rs = []
    lock = threading.Lock()

    def worker(i: int):
        p = ports[i % len(ports)]
        t0 = time.perf_counter()
        ok, body = http_get(p, path)
        dt = (time.perf_counter() - t0) * 1000
        with lock:
            rs.append((ok, dt,
                       None if ok else (body[:40].decode("latin-1")
                                        if isinstance(body, bytes) else str(body))))

    t0 = time.perf_counter()
    ths = [threading.Thread(target=worker, args=(i,)) for i in range(conc)]
    for t in ths:
        t.start()
    for t in ths:
        t.join()
    wall = time.perf_counter() - t0
    lat = sorted(r[1] for r in rs)
    fails: dict[str, int] = {}
    for r in rs:
        if not r[0]:
            k = (r[2] or "?")[:28]
            fails[k] = fails.get(k, 0) + 1
    return {"conc": conc, "wall": round(wall, 2),
            "ok": sum(1 for r in rs if r[0]),
            "p50": round(statistics.median(lat)) if lat else 0,
            "p95": round(lat[min(len(lat) - 1, int(len(lat) * .95))]) if lat else 0,
            "fails": fails}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--lanes", type=int, default=6)
    ap.add_argument("--conc", default="256,512,1024,2048")
    ap.add_argument("--path", default="/health")
    ap.add_argument("--stop", action="store_true")
    a = ap.parse_args()

    if a.stop:
        stop_lanes()
        return 0

    soft, hard = resource.getrlimit(resource.RLIMIT_NOFILE)
    resource.setrlimit(resource.RLIMIT_NOFILE, (hard, hard))
    threading.stack_size(512 * 1024)
    print("客户端 FD: %s → %s | 线程栈 512 KB" % (soft, hard))

    print("\n=== 启动 %d 条车道（独立进程）===" % a.lanes)
    ports = start_lanes(a.lanes)
    print("  就绪端口: %s → 共 %d 条" % (ports, len(ports)))

    concs = [int(x) for x in a.conc.split(",")]
    print("\n=== 扇出并发爬坡（path=%s）===" % a.path)
    print("  %-6s %-8s %-8s %-10s %-8s %s" %
          ("总并发", "每道", "墙钟", "成功率", "p95ms", "失败分类"))
    rows = []
    for c in concs:
        r = sweep(ports, c, a.path)
        r["per_lane"] = round(c / len(ports), 1)
        rows.append(r)
        print("  %-6d %-8.1f %-8.2f %-10s %-8d %s" %
              (c, r["per_lane"], r["wall"], "%d/%d" % (r["ok"], c), r["p95"],
               ", ".join("%s×%d" % (k, v) for k, v in r["fails"].items()) or "—"))

    print("\n=== 结论 ===")
    ok_rows = [r for r in rows if r["ok"] > 0]
    if ok_rows:
        best = max(ok_rows, key=lambda r: r["ok"])
        print("  最多成功并发: %d 路（%d 条车道 · 每道约 %.0f 路）"
              % (best["ok"], len(ports), best["per_lane"]))
        zf = [r for r in rows if r["ok"] == r["conc"]]
        print("  零失败最高档: %s" % (("%d 路" % max(r["conc"] for r in zf)) if zf else "无"))
    (LOG / "fanout_report.json").write_text(
        json.dumps({"ports": ports, "rows": rows}, ensure_ascii=False, indent=2),
        encoding="utf-8")
    print("\n  报告: logs/fanout_report.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
