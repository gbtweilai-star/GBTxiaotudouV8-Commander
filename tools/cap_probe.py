#!/usr/bin/env python3
"""单能力探活（供多域监控当**可杀子进程**用）

为什么要有它：
  多域监控原来用 ThreadPoolExecutor + result(timeout=)，而 Python 线程**取消了**。
  超时只是调用方不等了，挂死的工作线程仍在跑并永久占住 worker ⇒ 几个之后
  线程池耗尽、整个监控死锁（实测 security 域挂住不动、日志 4 分钟不写）。
  改成子进程：超时可以直接 kill，进程死了资源就全还回来。

输出：一行 JSON 到 stdout；退出码 0。父进程按 JSON 判 ok/denied/failed。
"""
from __future__ import annotations

import json
import sys
import time
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main() -> int:
    if len(sys.argv) < 2:
        print(json.dumps({"result": "failed", "why": "缺能力位名"}))
        return 0
    name = sys.argv[1]
    t0 = time.perf_counter()
    try:
        from gbt_allinone.api import run_task
        r = run_task(name, {})
    except Exception as exc:                                  # noqa: BLE001
        print(json.dumps({"result": "exception",
                          "why": "%s: %s" % (type(exc).__name__, str(exc)[:160]),
                          "ms": round((time.perf_counter() - t0) * 1000)}))
        return 0
    ms = round((time.perf_counter() - t0) * 1000)
    if not isinstance(r, dict):
        print(json.dumps({"result": "ok", "ms": ms}))
        return 0
    gr = r.get("gbt_result") or {}
    res = gr.get("result") or r.get("result") or {}
    blob = json.dumps(res if isinstance(res, (dict, list)) else str(res),
                      ensure_ascii=False)[:600]
    status = str(gr.get("status") or r.get("status") or "")
    if status == "denied" or "需要人工授权" in blob:
        out = "denied"
    elif res.get("ok") is False or r.get("ok") is False:
        out = "failed"
    else:
        out = "ok"
    print(json.dumps({"result": out, "ms": ms, "why": blob[:240],
                      "status": status}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
