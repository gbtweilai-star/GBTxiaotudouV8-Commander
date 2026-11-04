#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""记忆漂移压测：并发写 → 版本/哈希链/索引/recall 四路对账，外加「篡改必须被 verify 抓出来」。

用法：pyembed\python.exe -X utf8 tests\stress_memory_drift.py [--port 8766] [--threads 8] [--per 8]
判据（全过才算过）：
  1. 并发写：版本号无重号、无断号；
  2. 哈希链：每条 prev == 上一条 h，verify() ok；
  3. 索引不漂：同步层条数 == 统一索引 memory_sync 条数（投影无漏）；
  4. recall 还能查到压测词；
  5. 漂移检测器本身是真的：把一份**副本**改一个字，verify 必须红；原库必须绿。
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import pathlib
import sqlite3
import tempfile
import threading
import time
import urllib.parse
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parents[1]
FAILS = []


def _load_by_path(name, rel):
    p = ROOT / rel
    spec = importlib.util.spec_from_file_location(name, p)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def check(name, ok, detail):
    print(("[PASS] " if ok else "[FAIL] ") + name + " :: " + json.dumps(detail, ensure_ascii=False))
    if not ok:
        FAILS.append(name)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8766)
    ap.add_argument("--threads", type=int, default=8)
    ap.add_argument("--per", type=int, default=8)
    a = ap.parse_args()
    base = "http://127.0.0.1:%d/api/memory" % a.port
    results, lock = [], threading.Lock()

    def worker(tid, n):
        local = []
        for i in range(n):
            payload = {"op": "write", "src": "stress", "name": "console-web",
                       "text": "漂移压测 #%d-%d：并发写入的版本与哈希链必须一一对得上。" % (tid, i)}
            req = urllib.request.Request(base, data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
                                         headers={"Content-Type": "application/json"})
            try:
                with urllib.request.urlopen(req, timeout=30) as r:
                    d = json.loads(r.read().decode("utf-8"))
                local.append(((d.get("results") or [{}])[0], None))
            except Exception as e:  # noqa: BLE001
                local.append((None, "%s: %s" % (type(e).__name__, str(e)[:120])))
        with lock:
            results.extend(local)

    t0 = time.time()
    ths = [threading.Thread(target=worker, args=(t, a.per)) for t in range(a.threads)]
    for t in ths:
        t.start()
    for t in ths:
        t.join()
    elapsed = time.time() - t0
    total = a.threads * a.per

    oks = [r for r, err in results if r and r.get("ok")]
    errs = [err for _, err in results if err]
    check("并发写全部成功", len(oks) == total and not errs,
          {"wanted": total, "ok": len(oks), "errors": errs[:3]})

    versions = [r["version"] for r in oks]
    uniq = sorted(set(versions))
    dups = len(versions) - len(uniq)
    gaps = (uniq[-1] - uniq[0] + 1) - len(uniq) if uniq else -1
    check("版本无重号/无断号", dups == 0 and gaps == 0,
          {"range": [uniq[0] if uniq else None, uniq[-1] if uniq else None],
           "count": len(uniq), "dups": dups, "gaps": gaps})

    by_v = {r["version"]: r for r in oks}
    broken = [v for v in uniq if v - 1 in by_v and by_v[v].get("prev") != by_v[v - 1].get("h")]
    check("哈希链 prev 逐条接上", not broken, {"checked": len(uniq) - 1, "broken": broken[:3]})

    try:
        with urllib.request.urlopen(base + "?op=verify", timeout=30) as r:
            vrf = json.loads(r.read().decode("utf-8"))
    except Exception as e:  # noqa: BLE001
        vrf = {"ok": False, "error": str(e)[:120]}
    check("verify 全链完整", bool(vrf.get("ok")), {"checked": vrf.get("checked"),
                                                   "head": (vrf.get("head") or "")[:12]})

    with urllib.request.urlopen(base + "?op=stats", timeout=30) as r:
        st = json.loads(r.read().decode("utf-8"))
    sync_total = (st.get("sync_stats") or {}).get("total")
    idx = (st.get("index") or {}).get("by_src_tag") or []
    idx_sync = sum(x.get("n", 0) for x in idx if x.get("src") == "memory_sync")
    check("索引不漂（同步层 == 统一索引）", sync_total == idx_sync,
          {"sync_total": sync_total, "index_memory_sync": idx_sync,
           "fts": (st.get("index") or {}).get("fts")})

    q = "漂移压测"
    with urllib.request.urlopen(base + "?op=recall&" + urllib.parse.urlencode(
            {"q": q, "k": 50}), timeout=30) as r:
        rc = json.loads(r.read().decode("utf-8"))
    cov = rc.get("coverage") or {}
    check("压测后 recall 仍命中", bool(rc.get("total")) and cov.get("rate", 0) >= 0.5,
          {"total": rc.get("total"), "by_src": rc.get("by_src"), "coverage": cov})

    # 漂移检测器自身是不是真的：改副本，verify 必须红；原库必须绿
    M = _load_by_path("memory_sync", "gbt_allinone/tools/memory_sync.py")
    src = M.DB
    tmp = pathlib.Path(tempfile.mkdtemp()) / "chain_copy.sqlite3"
    s = sqlite3.connect(str(src))
    d = sqlite3.connect(str(tmp))
    s.backup(d)
    d.execute("update writes set text = text || '·篡改' "
              "where version = (select max(version) from writes)")
    d.commit()
    s.close()
    d.close()
    M.DB = tmp
    bad = M.verify()
    M.DB = src
    good = M.verify()
    check("篡改副本被 verify 抓出", (bad.get("ok") is False) and bool(bad.get("broken_at")),
          {"copy_ok": bad.get("ok"), "broken_at": bad.get("broken_at"),
           "reason": bad.get("reason")})
    check("原库仍然绿", bool(good.get("ok")), {"checked": good.get("checked")})

    print("[SUMMARY] %s  writes=%d  threads=%d  elapsed_ms=%d  rps=%.1f  dups=%d  gaps=%d  "
          "sync==index: %s  recall_hits=%s  cov=%s  tamper_caught=%s  fails=%s" % (
              "ALL PASS" if not FAILS else "FAIL", total, a.threads, int(elapsed * 1000),
              total / elapsed if elapsed else 0, dups, gaps, sync_total == idx_sync,
              rc.get("total"), cov.get("rate"), bad.get("ok") is False, FAILS))
    return 0 if not FAILS else 1


if __name__ == "__main__":
    raise SystemExit(main())
