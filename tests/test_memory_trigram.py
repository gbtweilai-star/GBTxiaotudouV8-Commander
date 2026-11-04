#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""中文 trigram 索引实测：unicode61 搜不到的子串，trigram 必须能搜到。

用法：pyembed\python.exe -X utf8 tests\test_memory_trigram.py [--port 8766]
判据：
  1. unicode61（老索引）对 3 字子串「试会话」= 0 命中；
  2. trigram 同一子串 >= 1 命中；
  3. /api/memory?op=recall 也能查到（接口真的接上了 trigram，不是只在库里建了表）。
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import pathlib
import sqlite3
import urllib.parse
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parents[1]
FAILS = []


def _load():
    p = ROOT / "tools" / "memory_unify.py"
    spec = importlib.util.spec_from_file_location("memory_unify", p)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def _post(port, payload):
    req = urllib.request.Request("http://127.0.0.1:%d/api/memory" % port,
                                 data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.loads(r.read().decode("utf-8"))


def _get(port, **params):
    url = "http://127.0.0.1:%d/api/memory?" % port + urllib.parse.urlencode(params)
    with urllib.request.urlopen(url, timeout=20) as r:
        return json.loads(r.read().decode("utf-8"))


def check(name, ok, detail):
    print(("[PASS] " if ok else "[FAIL] ") + name + " :: " + json.dumps(detail, ensure_ascii=False))
    if not ok:
        FAILS.append(name)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8766)
    a = ap.parse_args()
    U = _load()
    probe = "试会话"                                  # 3 字子串：中文连续串里的一段

    w = _post(a.port, {"op": "write", "src": "trigram-test", "name": "console-web",
                       "text": "中文 trigram 探针：测试会话单列不混进正经记忆（proof=trigram）。"})
    ok_write = bool((w.get("results") or [{}])[0].get("ok"))
    check("探针写入", ok_write, {"version": (w.get("results") or [{}])[0].get("version")})

    c = sqlite3.connect(str(U.IDX))
    try:
        old = c.execute("select count(*) from mem_fts f join mem m on m.rowid=f.rowid "
                        "where mem_fts match ?", ('"' + probe + '"',)).fetchone()[0]
        tri = c.execute("select count(*) from mem_fts_tri f join mem m on m.rowid=f.rowid "
                        "where mem_fts_tri match ?", ('"' + probe + '"',)).fetchone()[0]
        tri_rows = c.execute("select count(*) from mem_fts_tri").fetchone()[0]
    finally:
        c.close()
    check("unicode61 对 3 字子串=0（证明老索引确实漏）", old == 0, {"unicode61_hits": old})
    check("trigram 同子串>=1", tri >= 1, {"trigram_hits": tri, "tri_index_rows": tri_rows})

    rc = _get(a.port, op="recall", q=probe, k=5)
    hits = rc.get("hits") or []
    hit_ok = any(probe in (h.get("text") or "") for h in hits)
    check("接口 recall 走 trigram 能查到子串", bool(hits) and hit_ok,
          {"total": rc.get("total"), "query": probe,
           "coverage": rc.get("coverage"),
           "fts": (rc.get("index") or {}).get("fts")})

    print("[SUMMARY] %s  fails=%s" % ("ALL PASS" if not FAILS else "FAIL", FAILS))
    return 0 if not FAILS else 1


if __name__ == "__main__":
    raise SystemExit(main())
