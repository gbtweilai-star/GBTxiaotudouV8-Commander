# -*- coding: utf-8 -*-
"""触手并发压测 —— 本机到底能同时伸几根

口径（现跑，不估）：
  · 每根"触手" = 一次完整请求（查索引 / 调原生桥）
  · 从 1 路爬到 64 路，每档跑固定轮次，记：总耗时 / QPS / p50 / p95 / 失败数
  · 失败必须分类记账（超时 / 连接拒绝 / 异常），不许笼统说"失败"

三种模式：
  query  查常驻索引（127.0.0.1:8792）—— 纯 IO + 服务端倒排，最轻
  direct 进程内直接查本地索引 —— 无线程池开销，看纯算力
  native 调 apple-* 原生桥（读类）—— 走系统框架，最重

用法：
  python3 tools/tentacle_bench.py query
  python3 tools/tentacle_bench.py native --max 16
"""
from __future__ import annotations
import json, socket, statistics, subprocess, sys, threading, time, urllib.parse
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PORT = 8792
QS = ["omni_plug", "gguf", "qwen", "capability", "page_route",
      "index_daemon", "disk_index", "page_bind", "api.py", "manifest"]


def _http_get(path, timeout=10):
    s = socket.create_connection(("127.0.0.1", PORT), timeout=timeout)
    try:
        s.sendall(("GET %s HTTP/1.0\r\nHost: x\r\n\r\n" % path).encode())
        b = b""
        while True:
            c = s.recv(65536)
            if not c:
                break
            b += c
    finally:
        s.close()
    return json.loads(b.split(b"\r\n\r\n", 1)[1])


def one_query(i):
    q = QS[i % len(QS)]
    t0 = time.time()
    try:
        r = _http_get("/find?q=%s&limit=3" % urllib.parse.quote(q))
        ok = bool(r.get("ok"))
        return ok, (time.time() - t0) * 1000, None if ok else "not-ok"
    except socket.timeout:
        return False, (time.time() - t0) * 1000, "timeout"
    except ConnectionRefusedError:
        return False, (time.time() - t0) * 1000, "refused"
    except Exception as e:
        return False, (time.time() - t0) * 1000, type(e).__name__


def one_native(i):
    tool, cmd, args = ("apple-device", "info", []) if i % 2 == 0 else ("apple-weather", "", [])
    t0 = time.time()
    try:
        p = subprocess.run(["/usr/local/bin/" + tool] + ([cmd] if cmd else []) + args,
                           capture_output=True, text=True, timeout=25)
        j = json.loads((p.stdout or "").strip() or "{}")
        return bool(j.get("ok")), (time.time() - t0) * 1000, None if j.get("ok") else "not-ok"
    except subprocess.TimeoutExpired:
        return False, (time.time() - t0) * 1000, "timeout"
    except Exception as e:
        return False, (time.time() - t0) * 1000, type(e).__name__


def run_level(n, rounds, fn):
    """n 根并发，每根跑 rounds 次。"""
    lat, errs, done = [], {}, [0]
    lock = threading.Lock()

    def worker(k):
        for j in range(rounds):
            ok, ms, why = fn(k * rounds + j)
            with lock:
                lat.append(ms)
                done[0] += 1
                if not ok:
                    errs[why or "unknown"] = errs.get(why or "unknown", 0) + 1

    ts = [threading.Thread(target=worker, args=(k,), daemon=True) for k in range(n)]
    t0 = time.time()
    for t in ts:
        t.start()
    for t in ts:
        t.join()
    wall = (time.time() - t0) * 1000
    lat.sort()
    p50 = lat[len(lat) // 2] if lat else 0
    p95 = lat[int(len(lat) * 0.95)] if lat else 0
    return {"n": n, "reqs": done[0], "wall_ms": round(wall),
            "qps": round(done[0] / (wall / 1000), 1) if wall else 0,
            "p50": round(p50), "p95": round(p95),
            "max": round(max(lat)) if lat else 0,
            "fail": sum(errs.values()), "errs": errs}


def main() -> int:
    mode = sys.argv[1] if len(sys.argv) > 1 else "query"
    maxn = 64
    if "--max" in sys.argv:
        maxn = int(sys.argv[sys.argv.index("--max") + 1])
    fn = {"query": one_query, "native": one_native}.get(mode)
    if fn is None:
        print("  模式: query | native"); return 2

    levels = [1, 2, 4, 8, 16, 32, 64]
    levels = [x for x in levels if x <= maxn]
    rounds = 8 if mode == "query" else 2

    print("  模式=%s · 每根 %d 次 · 档位 %s" % (mode, rounds, levels))
    print("  %4s %6s %8s %7s %7s %7s %6s  %s" %
          ("并发", "请求", "总耗时ms", "QPS", "p50ms", "p95ms", "失败", "错误分类"))
    rows = []
    for n in levels:
        r = run_level(n, rounds, fn)
        rows.append(r)
        print("  %4d %6d %8d %7.1f %7d %7d %6d  %s" %
              (r["n"], r["reqs"], r["wall_ms"], r["qps"], r["p50"], r["p95"],
               r["fail"], json.dumps(r["errs"], ensure_ascii=False)))
        if r["fail"] > r["reqs"] * 0.5:
            print("       ↑ 失败过半，到此为止")
            break

    ok = [r for r in rows if r["fail"] == 0]
    if ok:
        best = max(ok, key=lambda x: x["qps"])
        print("\n  最大无失败并发: %d 路 · 峰值 QPS %.1f · p95 %d ms"
              % (best["n"], best["qps"], best["p95"]))
    Path(ROOT / "state").mkdir(exist_ok=True)
    (ROOT / "state" / ("tentacle_bench_%s.json" % mode)).write_text(
        json.dumps({"at": time.strftime("%Y-%m-%dT%H:%M:%S"), "mode": mode,
                    "rounds": rounds, "rows": rows}, ensure_ascii=False, indent=1),
        encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
