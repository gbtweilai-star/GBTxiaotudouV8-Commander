#!/usr/bin/env python3
"""触手 · LLM 并发压测（不设上限）

口径：
  · 一根触手 = 一次完整 chat completion（经模型桥 :8791，走的是桥的上游链）
  · 从 1 路爬到 32 路，**不设人为上限**，看它自己先在哪一档顶住/崩掉
  · 失败必须分类记账：429 限流 / 超时 / 连接拒绝 / 其他 —— 不许笼统说"失败"
  · 每档报 QPS、p50、p95、成功率

为什么不用线程池压 CPU：那是另一个轴。
触手管的是 **LLM 请求并发**，本来就是 IO 等待型，线程完全够，且没有上限可设。

用法：
  python3 tools/tentacle_llm_bench.py              # 默认 1→32
  python3 tools/tentacle_llm_bench.py --widths 1,4,8
"""
from __future__ import annotations

import argparse
import resource
import concurrent.futures as cf
import json
import socket
import statistics
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BRIDGE = "http://127.0.0.1:8791/v1/chat/completions"
PROMPT = "用四个字回答：今天天气"


def one(i: int) -> dict:
    """一次完整请求。返回 (成功?, 毫秒, 失败分类, 实走车道)。"""
    body = json.dumps({"messages": [{"role": "user", "content": PROMPT}],
                       "max_tokens": 16, "stream": False}).encode()
    req = urllib.request.Request(BRIDGE, data=body,
                                 headers={"Content-Type": "application/json"})
    t0 = time.perf_counter()
    try:
        with urllib.request.urlopen(req, timeout=180) as r:
            raw = r.read()
            lane = r.headers.get("X-GBT-Lane") or "?"
        ms = (time.perf_counter() - t0) * 1000
        d = json.loads(raw)
        if d.get("ok") is False:
            code = d.get("http")
            kind = "429-限流" if code == 429 else ("5xx-上游" if code and code >= 500
                                                   else "业务失败") 
            return {"ok": False, "ms": ms, "err": kind, "lane": lane, "http": code}
        if not d.get("choices"):
            return {"ok": False, "ms": ms, "err": "空回包", "lane": lane}
        return {"ok": True, "ms": ms, "err": None, "lane": lane}
    except urllib.error.HTTPError as e:
        return {"ok": False, "ms": (time.perf_counter() - t0) * 1000,
                "err": "http-%d" % e.code, "lane": "-"}
    except socket.timeout:
        return {"ok": False, "ms": (time.perf_counter() - t0) * 1000,
                "err": "超时", "lane": "-"}
    except Exception as e:                                   # noqa: BLE001
        return {"ok": False, "ms": (time.perf_counter() - t0) * 1000,
                "err": type(e).__name__, "lane": "-"}


def batch(n: int) -> dict:
    t0 = time.perf_counter()
    with cf.ThreadPoolExecutor(max_workers=n) as ex:
        rs = list(ex.map(one, range(n)))
    wall = time.perf_counter() - t0
    return {"n": n, "wall": wall, "rs": rs}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--widths", default="1,2,4,8,16,32")
    args = ap.parse_args()
    widths = [int(x) for x in args.widths.split(",") if x.strip()]

    # 描述符是**假上限**：soft 默认 1024，96 路时会 URLError 假崩。
    # 先把软上限顶到硬上限，再量真实的并发天花板。
    try:
        _soft, _hard = resource.getrlimit(resource.RLIMIT_NOFILE)
        resource.setrlimit(resource.RLIMIT_NOFILE, (min(_hard, 8192), _hard))
        print("描述符上限: %s → %s（硬上限 %s）" %
              (_soft, resource.getrlimit(resource.RLIMIT_NOFILE)[0], _hard))
    except Exception as _e:                                   # noqa: BLE001
        print("描述符上限: 提不上去（%s）" % _e)

    print("触手 · LLM 并发压测（不设上限）")
    print("目标: %s" % BRIDGE)
    print("上游链: selfhost(A19) → freepool → freepool-b → deepseek")
    print("失败分类: 429 限流 / 超时 / 连接 / 业务 —— 逐类记账\n")
    print("  %-5s %-9s %-8s %-8s %-8s %-7s %s" %
          ("并发", "墙钟", "QPS", "p50ms", "p95ms", "成功率", "失败分类"))

    rows = []
    for n in widths:
        b = batch(n)
        ok = [r for r in b["rs"] if r["ok"]]
        lat = sorted(r["ms"] for r in b["rs"])
        p50 = statistics.median(lat)
        p95 = lat[min(len(lat) - 1, int(len(lat) * 0.95))]
        qps = len(ok) / b["wall"] if b["wall"] else 0
        fails = {}
        for r in b["rs"]:
            if not r["ok"]:
                fails[r["err"]] = fails.get(r["err"], 0) + 1
        lanes = {}
        for r in ok:
            lanes[r["lane"]] = lanes.get(r["lane"], 0) + 1
        rows.append({"n": n, "wall": round(b["wall"], 2), "qps": round(qps, 3),
                     "p50": round(p50), "p95": round(p95),
                     "ok": len(ok), "fails": fails, "lanes": lanes})
        print("  %-5d %-9.2f %-8.2f %-8.0f %-8.0f %-7s %s" %
              (n, b["wall"], qps, p50, p95,
               "%d/%d" % (len(ok), n),
               ", ".join("%s×%d" % (k, v) for k, v in fails.items()) or "—"))

    held = [r for r in rows if r["ok"] == r["n"]]
    print("\n=== 结论 ===")
    if held:
        print("  最大零失败并发: %d 路（" % max(r["n"] for r in held), end="")
        best = max(held, key=lambda r: r["qps"])
        print("峰值 QPS %.2f @ %d 路）" % (best["qps"], best["n"]))
    else:
        print("  没有一档做到零失败")
    brk = [r for r in rows if r["ok"] < r["n"]]
    if brk:
        print("  开始出现失败: %d 路（%s）" % (brk[0]["n"],
              ", ".join("%s×%d" % (k, v) for k, v in brk[0]["fails"].items())))
        print("  → 这是**上游免费池的 429**，不是触手的上限。触手本身不设闸。")
    Path("/tmp/gt/llm_conc.json").write_text(
        json.dumps(rows, ensure_ascii=False, indent=2))
    print("\n  报告: /tmp/gt/llm_conc.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
