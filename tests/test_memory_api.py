#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""/api/memory 三 op 实测（recall / write / subscribe）——打完真打 127.0.0.1:8766。

用法：pyembed\python.exe -X utf8 tests\test_memory_api.py [--port 8766]
判据（三条都过才算过）：
  1. write 走同步层，拿到单调 version 与 h/prev/chain；
  2. recall 能查到刚写的那几条，返回 hits 与覆盖率（不是空壳）；
  3. subscribe 连上后，另一次 write 能收到 write 广播（<=5s）。
"""
from __future__ import annotations

import argparse
import json
import sys
import threading
import time
import urllib.parse
import urllib.request

BASE = "http://127.0.0.1:8766/api/memory"
FAILS = []


def _post(payload, timeout=20):
    req = urllib.request.Request(BASE, data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


def _get(**params):
    url = "http://127.0.0.1:8766/api/memory?" + urllib.parse.urlencode(params)
    with urllib.request.urlopen(url, timeout=20) as r:
        return json.loads(r.read().decode("utf-8"))


def check(name, ok, detail):
    print(("[PASS] " if ok else "[FAIL] ") + name + " :: " + json.dumps(detail, ensure_ascii=False))
    if not ok:
        FAILS.append(name)
    return ok


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8766)
    a = ap.parse_args()
    global BASE
    BASE = "http://127.0.0.1:%d/api/memory" % a.port
    t_all = time.time()

    # ① write：同步层拿 version + chain
    w1 = _post({"op": "write", "src": "console", "name": "console-web", "role": "user",
                "text": "记忆统一层：recall 一句查全册，按源分组返回可读片段，测试会话单列不混进正经记忆。"})
    w2 = _post({"op": "write", "src": "console", "name": "console-web", "role": "assistant",
                "text": "同步层把每次写入串成哈希链：h=sha1(prev+payload)，版本号单调递增，verify 能验漂移。"})
    r1 = (w1.get("results") or [{}])[0]
    r2 = (w2.get("results") or [{}])[0]
    check("write #1 version/chain", bool(r1.get("ok") and r1.get("version") and r1.get("chain")
                                        and (r1.get("chain") or [""])[-1] == r1.get("h")
                                        and r1.get("chain_len") == r1.get("version")
                                        and (r1.get("prev") == "" if r1.get("version") == 1 else bool(r1.get("prev")))),
          {"version": r1.get("version"), "chain": (r1.get("chain") or [])[:2],
           "chain_len": r1.get("chain_len"), "prev": r1.get("prev")})
    check("write #2 接在 #1 后面", bool(r2.get("version") == r1.get("version", 0) + 1 and r2.get("prev") == r1.get("h")),
          {"version": r2.get("version"), "prev_eq_h1": r2.get("prev") == r1.get("h"),
           "chain": (r2.get("chain") or [])[-2:], "chain_len": r2.get("chain_len")})

    # ② recall：查到刚写的，给 hits + 覆盖率
    rc = _get(op="recall", q="记忆统一层 哈希链 漂移", k=5)
    cov = rc.get("coverage") or {}
    check("recall hits>0 且覆盖率>0", bool(rc.get("total") and cov.get("rate", 0) > 0),
          {"total": rc.get("total"), "by_src": rc.get("by_src"), "coverage": cov,
           "hit0": (rc.get("hits") or [{}])[0].get("text", "")[:60], "ms": rc.get("ms")})

    # ③ subscribe：连上后另一次 write 能收到广播
    got = {"hello": None, "write": None}

    def sub():
        try:
            with urllib.request.urlopen(BASE + "?op=subscribe", timeout=15) as r:
                for raw in r:
                    line = raw.decode("utf-8", "replace").strip()
                    if not line.startswith("data: "):
                        continue
                    ev = json.loads(line[6:])
                    if ev.get("type") == "hello" and got["hello"] is None:
                        got["hello"] = ev
                    elif ev.get("type") == "write":
                        got["write"] = ev
                        return
        except Exception as e:  # noqa: BLE001
            got["error"] = "%s: %s" % (type(e).__name__, str(e)[:80])

    th = threading.Thread(target=sub, daemon=True)
    th.start()
    time.sleep(0.8)
    w3 = _post({"op": "write", "src": "console", "name": "console-web", "role": "user",
                "text": "订阅者测试：这条写入应当被 subscribe 的 SSE 收到，proof=subscribe-ok。"})
    th.join(timeout=6.0)
    check("subscribe 收到 hello", bool(got.get("hello")), {"hello": got.get("hello")})
    check("subscribe 收到 write 广播", bool(got.get("write")),
          {"event": got.get("write"), "write_version": ((w3.get("results") or [{}])[0]).get("version")})

    # ④ 重复正文不占满召回窗口（2026-11-02 修：dedupe）
    dup = "重复探针：同一句话写两次，recall 只该给它一个名额（proof=dedup）。"
    _post({"op": "write", "src": "console", "name": "console-web", "text": dup})
    _post({"op": "write", "src": "console", "name": "console-web", "text": dup})
    rd = _get(op="recall", q="重复探针 名额", k=5)
    dup_hits = [h for h in (rd.get("hits") or []) if "重复探针" in (h.get("text") or "")]
    dd = rd.get("dedup") or {}
    check("重复正文去重（只占一个名额）",
          len(dup_hits) <= 1 and dd.get("before", 0) >= dd.get("after", 0),
          {"dup_hits": len(dup_hits), "dedup": dd, "total": rd.get("total")})

    # ⑤ 链完整性（供漂移压测复用）
    v = _get(op="verify")
    check("链完整 verify.ok", bool(v.get("ok")), {"checked": v.get("checked"), "head": (v.get("head") or "")[:12]})

    print("[SUMMARY] %s  total=%d  hit_rate=%s  fails=%s  elapsed_ms=%d" % (
        "ALL PASS" if not FAILS else "FAIL",
        rc.get("total"), cov.get("rate"), FAILS, int((time.time() - t_all) * 1000)))
    return 0 if not FAILS else 1


if __name__ == "__main__":
    raise SystemExit(main())
