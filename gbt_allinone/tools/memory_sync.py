#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""memory_sync —— 记忆写入的同步层（版本号 + 哈希链），给 /api/memory 的 write 用。

## 为什么单开这一层
记忆不能"随手 insert 一行"就算写完：
  · 多线程/多进程同时写 → 必须拿到**单调版本号**（version），否则并发写重号；
  · 写进去的东西要能被验伤 → 每条记 **h = sha1(prev_h + payload)**，串成**哈希链**；
  · 写入后要能被 recall 到 → 同步投影进 memory_unify 的统一索引（副本，src=memory_sync）。

## 三个返回物（/api/memory write 就是拿这几个）
  · version : 本次写入的版本号（从 1 起，单调 +1）
  · chain   : 到本版本为止的链尾（最多 8 个 h，chain_len 是总长）
  · h/prev  : 本条与上一条的哈希，链断了 verify() 立刻报出来

## 纪律
  · 本文件只写自己的库（gbt_allinone/store/memory_sync/chain.sqlite3），
    对 memory_unify 的库只做**追加投影**（insert or ignore），不改它已有行；
  · verify() 只读，不改任何东西 —— 漂移检测必须是只读的。
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import pathlib
import sqlite3
import threading
import time

ROOT = pathlib.Path(__file__).resolve().parents[2]
SYNC_DIR = ROOT / "gbt_allinone" / "store" / "memory_sync"
DB = SYNC_DIR / "chain.sqlite3"
_LOCK = threading.Lock()
_PROJ_LOCK = threading.Lock()   # 投影串行：并发 write 时不让两线程同时写统一库
_UNIFY = None


def _unify():
    """按路径加载 tools/memory_unify.py（不 import gbt_allinone 包，避免拖进整条 api）。"""
    global _UNIFY
    if _UNIFY is None:
        p = ROOT / "tools" / "memory_unify.py"
        spec = importlib.util.spec_from_file_location("memory_unify", p)
        m = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(m)
        _UNIFY = m
    return _UNIFY


def _conn() -> sqlite3.Connection:
    SYNC_DIR.mkdir(parents=True, exist_ok=True)
    c = sqlite3.connect(str(DB), timeout=10)
    c.execute("PRAGMA journal_mode=DELETE")
    c.execute("PRAGMA busy_timeout=8000")
    c.execute("CREATE TABLE IF NOT EXISTS writes ("
              "version INTEGER PRIMARY KEY, h TEXT NOT NULL, prev TEXT, at TEXT, "
              "src TEXT, name TEXT, role TEXT, tag TEXT, text TEXT)")
    c.execute("CREATE TABLE IF NOT EXISTS meta (k TEXT PRIMARY KEY, v TEXT)")
    return c


def _get_meta(c, k: str, default: str = "") -> str:
    row = c.execute("select v from meta where k=?", (k,)).fetchone()
    return row[0] if row else default


def _set_meta(c, k: str, v) -> None:
    c.execute("insert into meta (k,v) values (?,?) "
              "on conflict(k) do update set v=excluded.v", (k, str(v)))


def _h(version: int, at: str, src: str, name: str, role: str, tag: str, text: str) -> str:
    payload = json.dumps({"v": version, "at": at, "src": src, "name": name,
                          "role": role, "tag": tag, "text": text},
                         ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha1(payload.encode("utf-8")).hexdigest()


def _tail(c: sqlite3.Connection, upto: int, n: int = 8) -> list:
    lo = max(1, upto - n + 1)
    rows = c.execute("select h from writes where version between ? and ? order by version",
                     (lo, upto)).fetchall()
    return [r[0] for r in rows]


def write(text: str, src: str = "console", name: str = "console-web",
          role: str = "user", tag: str = "real", at: str = "") -> dict:
    """追加一条记忆：先落链库（拿 version/chain），再投影进统一索引。"""
    text = str(text or "")
    if not text.strip():
        return {"ok": False, "error": "text empty"}
    at = at or time.strftime("%Y-%m-%dT%H:%M:%S")
    with _LOCK:
        c = _conn()
        try:
            c.execute("BEGIN IMMEDIATE")
            row = c.execute("select version, h from writes order by version desc limit 1").fetchone()
            prev_version, prev = (row[0], row[1]) if row else (0, "")
            version = prev_version + 1
            h = _h(version, at, src, name, role, tag, text)
            c.execute("insert into writes (version,h,prev,at,src,name,role,tag,text) "
                      "values (?,?,?,?,?,?,?,?,?)",
                      (version, h, prev, at, src, name, role, tag, text))
            c.execute("COMMIT")
            chain = _tail(c, version)
            chain_len = version
        finally:
            c.close()
    indexed = index_into_unify()
    return {"ok": True, "version": version, "h": h, "prev": prev,
            "chain": chain, "chain_len": chain_len, "at": at,
            "src": src, "name": name, "tag": tag,
            "ref": "memchain#version=%d" % version,
            "indexed": bool(indexed.get("ok")),
            "index_added": indexed.get("added")}


def index_into_unify(limit: int = 0) -> dict:
    """增量投影：只投"游标之后"的新写入，游标与投影**在同一个事务里**。

    2026-11-02 两次实测教训（都是"索引漂移"）：
      ① 先读 rows、再读全局 max(version) ⇒ 中间有别的写提交时游标被推过漏投的那条，
         那条永远补不回来（实测 sync 346 vs index 344）；
      ② 只用"条数比对 + 全量重扫"会在并发下把 O(新条数) 拖回 O(全表)。
    ⇒ 用 ATTACH 把统一库挂到链库连接上，一个 BEGIN IMMEDIATE 内：
      取增量 → 投 → 对账（idx 条数 == 已投最后版本）→ 推游标 → COMMIT。
      DELETE journal 下多库事务是原子的；对账发现缺口就从 0 对齐重投一次。
    """
    U = _unify()
    U._conn().close()                      # 确保统一库的 mem/mem_fts/mem_fts_tri 已建
    added = 0
    with _PROJ_LOCK:
        c = _conn()
        ok = False
        reason = ""
        try:
            c.execute("ATTACH DATABASE ? AS uni", (str(U.IDX),))
            forced0 = False
            for _attempt in range(3):
                c.execute("BEGIN IMMEDIATE")
                try:
                    cursor = 0 if forced0 else int(_get_meta(c, "projected_version", "0") or 0)
                    rows = c.execute(
                        "select version,h,at,src,name,role,tag,text from writes where version > ? "
                        "order by version" + (" limit %d" % int(limit) if limit else ""),
                        (cursor,)).fetchall()
                    for version, h, at, src, name, role, tag, text in rows:
                        if c.execute("select 1 from uni.mem where h=?", (h,)).fetchone():
                            continue
                        c.execute("insert into uni.mem (h,src,ref,name,at,role,text,tag) "
                                  "values (?,?,?,?,?,?,?,?)",
                                  (h, "memory_sync", "memchain#version=%d" % version,
                                   name or "console", at, role or "user", text or "", tag or "real"))
                        rowid = c.execute("select last_insert_rowid()").fetchone()[0]
                        c.execute("insert into uni.mem_fts (rowid, text) values (?, ?)",
                                  (rowid, text or ""))
                        try:
                            c.execute("insert into uni.mem_fts_tri (rowid, text) values (?, ?)",
                                      (rowid, text or ""))
                        except sqlite3.OperationalError:
                            pass
                        added += 1
                    last = rows[-1][0] if rows else cursor
                    # 不变量：统一库里 memory_sync 的条数 == 已投到的最后版本号。
                    # 版本从 1 连续分配、提交顺序 == 版本顺序 ⇒ 两个数必须相等；不等就是有漏。
                    # （比逐条 NOT EXISTS 对账便宜得多：O(1) 次扫描，不是 O(写数 × 索引数)）
                    idx_n = c.execute(
                        "select count(*) from uni.mem where src='memory_sync'").fetchone()[0]
                    if idx_n == last:
                        if rows:
                            _set_meta(c, "projected_version", last)
                        c.execute("COMMIT")
                        ok = True
                        break
                    if forced0 and idx_n > last:   # 索引里有链库没有的旧行（链库被重置过？）
                        c.execute("ROLLBACK")
                        reason = "统一索引多出 %d 条（链库被重置？需重建索引）" % (idx_n - last)
                        break
                    c.execute("ROLLBACK")
                    forced0 = True                # 有漏 ⇒ 从 0 对齐重投一次
                except Exception:
                    c.execute("ROLLBACK")
                    raise
        finally:
            try:
                c.execute("DETACH DATABASE uni")
            except Exception:  # noqa: BLE001
                pass
            c.close()
    return {"ok": bool(ok), "added": added,
            "reason": reason or ("" if ok else "投影对账仍有缺口（verify 会看到 index 落后）")}


def version() -> dict:
    c = _conn()
    try:
        row = c.execute("select version,h,at from writes order by version desc limit 1").fetchone()
        n = c.execute("select count(*) from writes").fetchone()[0]
    finally:
        c.close()
    return {"version": row[0] if row else 0, "h": row[1] if row else "",
            "at": row[2] if row else "", "count": n}


def recent(limit: int = 20) -> list:
    c = _conn()
    try:
        rows = c.execute("select version,h,prev,at,src,name,role,tag,text from writes "
                         "order by version desc limit ?", (int(limit),)).fetchall()
    finally:
        c.close()
    return [{"version": r[0], "h": r[1], "prev": r[2], "at": r[3], "src": r[4],
             "name": r[5], "role": r[6], "tag": r[7], "text": (r[8] or "")[:200]}
            for r in rows]


def verify() -> dict:
    """只读验链：h 重算是否一致、prev 是否接得上。漂移压测就靠它出数。"""
    c = _conn()
    try:
        rows = c.execute("select version,h,prev,at,src,name,role,tag,text from writes "
                         "order by version").fetchall()
    finally:
        c.close()
    prev_h, prev_v = "", 0
    for version, h, prev, at, src, name, role, tag, text in rows:
        if version != prev_v + 1:
            return {"ok": False, "checked": prev_v, "broken_at": version,
                    "reason": "版本号不连续（%s 后面是 %s）" % (prev_v, version)}
        if prev != prev_h:
            return {"ok": False, "checked": prev_v, "broken_at": version,
                    "reason": "prev 接不上（期望 %s…，实际 %s…）" % (prev_h[:12], (prev or "")[:12])}
        if _h(version, at, src, name, role, tag, text) != h:
            return {"ok": False, "checked": prev_v, "broken_at": version,
                    "reason": "h 重算不一致（正文/字段被改过）"}
        prev_h, prev_v = h, version
    return {"ok": True, "checked": prev_v, "head": prev_h, "count": len(rows)}


def stats() -> dict:
    c = _conn()
    try:
        total = c.execute("select count(*) from writes").fetchone()[0]
        by_src = c.execute("select src, count(*) from writes group by src").fetchall()
    finally:
        c.close()
    return {"total": total, "by_src": {a: b for a, b in by_src}, "db": str(DB.relative_to(ROOT))}
