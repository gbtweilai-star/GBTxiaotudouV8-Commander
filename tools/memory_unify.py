#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""memory_unify —— 把她的记忆统一成一册（一个索引，跨源可查）。

## 为什么需要
实测她现在的记忆散在四处，各查各的：
  · ring_context   对话全史（SQLite FTS5，1986 条，但大半是测试会话）
  · context_vault  索引层（几乎空：docs 1 条 / postings 3 条 —— 建了没用起来）
  · devoured       吞进来的知识胶囊（2 个）
  · state/*.jsonl  事件账（context_guard / duty_patrol …）

⇒ 问一句"我之前说过什么"，得知道去哪个库查。这不是记忆，这是四个抽屉。

## 统一层做什么（不搬数据）
  ① 只读遍历各源，**建一份统一索引**（自己的 sqlite，不碰原库）
  ② 每条带 `src` / `ref` / `name` / `at`，可指回原处
  ③ recall(q) 一句查全册，按源分组返回
  ④ 测试会话**单列**（tag=test），默认不混进正经记忆

## 铁律
  · **不搬正文**：统一库只存索引与指针，原文仍在原库（避免两处漂移）
  · **不删原库**：只读遍历，一个字节都不改
  · **测试噪音不冒充记忆**：按 name 规则标 test，账上看得见
"""
from __future__ import annotations

import json
import os
import pathlib
import re
import sqlite3
import sys
import time

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

IDX = ROOT / "gbt_allinone" / "store" / "memory_unify" / "unified.sqlite3"
RING = ROOT / "gbt_allinone" / "store" / "ring_context" / "ring.db"
VAULT = ROOT / "gbt_allinone" / "store" / "context_vault" / "index.sqlite3"
DEVOURED = ROOT / "gbt_allinone" / "store" / "devoured"
STATE = ROOT / "state"

# 测试会话名（我这一场建的）：这些不进"正经记忆"，单列 tag=test
TEST_NAME = re.compile(
    r"^(acc_ring|acc_guard|reg\d|rg\d|dbg|duptest|xproc|unl|unl2|final|page-test|"
    r"probe|v\d{6,}|m\d{6,}|g\d{6,}|w\d{6,}|xproc\d|ba_|guardtest|reg[A-Z])")


def _conn():
    IDX.parent.mkdir(parents=True, exist_ok=True)
    c = sqlite3.connect(str(IDX))
    # 与 ring_context 同理：iSH 的 mmap 每进程私有，WAL 跨进程不可见 ⇒ 用 DELETE
    try:
        c.execute("PRAGMA journal_mode=DELETE")
    except sqlite3.OperationalError:
        pass
    c.execute("CREATE TABLE IF NOT EXISTS mem ("
              "h TEXT PRIMARY KEY, src TEXT, ref TEXT, name TEXT, at TEXT, "
              "role TEXT, text TEXT, tag TEXT)")
    try:
        c.execute("CREATE VIRTUAL TABLE IF NOT EXISTS mem_fts USING fts5(text, tokenize='unicode61')")
    except sqlite3.OperationalError:
        pass
    return c


def _hash(*parts) -> str:
    import hashlib
    return hashlib.sha1("\x00".join(str(x) for x in parts).encode("utf-8")).hexdigest()[:20]


def survey() -> dict:
    """盘点：各源多少条、多大。"""
    out = {}
    if RING.is_file():
        c = sqlite3.connect(str(RING))
        rows = c.execute("select name, count(*) from turns group by name").fetchall()
        c.close()
        out["ring_context"] = {
            "file": str(RING.relative_to(ROOT)),
            "turns": sum(r[1] for r in rows),
            "sessions": len(rows),
            "test_sessions": [r[0] for r in rows if TEST_NAME.match(str(r[0] or ""))],
            "real_sessions": [r[0] for r in rows if not TEST_NAME.match(str(r[0] or ""))],
        }
    if VAULT.is_file():
        c = sqlite3.connect(str(VAULT))
        try:
            n = c.execute("select count(*) from docs").fetchone()[0]
        except Exception:                                     # noqa: BLE001
            n = 0
        c.close()
        out["context_vault"] = {"file": str(VAULT.relative_to(ROOT)), "docs": n}
    if DEVOURED.is_dir():
        cap = [d.name for d in DEVOURED.iterdir() if d.is_dir()]
        out["devoured"] = {"dir": str(DEVOURED.relative_to(ROOT)), "capsules": cap}
    if STATE.is_dir():
        ev = [f.name for f in STATE.glob("*.jsonl")]
        out["state_events"] = {"files": ev}
    return out


def index(sources: tuple = ("ring", "devoured")) -> dict:
    """建统一索引。只读各源，不改原库。"""
    c = _conn()
    added = {"ring": 0, "devoured": 0}
    rows = []

    if "ring" in sources and RING.is_file():
        r = sqlite3.connect(str(RING))
        for seq, at, role, content, name in r.execute(
                "select seq, at, role, content, name from turns"):
            nm = str(name or "default")
            tag = "test" if TEST_NAME.match(nm) else "real"
            rows.append((_hash("ring", seq, nm), "ring_context",
                         "ring.db#seq=%s" % seq, nm, at, role, str(content or ""), tag))
        r.close()

    if "devoured" in sources and DEVOURED.is_dir():
        for d in DEVOURED.iterdir():
            f = d / "absorbed_knowledge.md"
            if not f.is_file():
                continue
            txt = f.read_text(encoding="utf-8", errors="replace")[:200000]
            rows.append((_hash("devoured", d.name), "devoured",
                         str(f.relative_to(ROOT)), d.name,
                         time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(f.stat().st_mtime)),
                         "knowledge", txt, "real"))

    for row in rows:
        cur = c.execute("select 1 from mem where h=?", (row[0],)).fetchone()
        if cur:
            continue
        c.execute("insert into mem (h,src,ref,name,at,role,text,tag) values (?,?,?,?,?,?,?,?)", row)
        c.execute("insert into mem_fts (rowid, text) values ((select rowid from mem where h=?), ?)",
                  (row[0], row[6]))
        added[row[1] if row[1] in added else "ring"] += 1
    c.commit()
    c.close()
    return {"ok": True, "added": added, "index": str(IDX.relative_to(ROOT))}


def recall(q: str, k: int = 10, include_test: bool = False) -> dict:
    """一句查全册。默认**不含**测试噪音。"""
    c = _conn()
    tag_clause = "" if include_test else " and m.tag='real'"
    try:
        rows = c.execute(
            "select m.src, m.ref, m.name, m.at, m.role, m.text, m.tag from mem_fts f "
            "join mem m on m.rowid=f.rowid where mem_fts match ?" + tag_clause +
            " order by rank limit ?", (q, k)).fetchall()
    except sqlite3.OperationalError:
        rows = c.execute(
            "select src, ref, name, at, role, text, tag from mem "
            "where text like ?" + (" and tag='real'" if not include_test else "") +
            " order by at desc limit ?", ("%" + q + "%", k)).fetchall()
    if not rows:                                              # 词面兜底：拆词再查
        toks = [t for t in re.split(r"\s+", q.strip()) if len(t) >= 2]
        seen, got = set(), []
        for t in toks:
            try:
                rr = c.execute(
                    "select m.src, m.ref, m.name, m.at, m.role, m.text, m.tag from mem_fts f "
                    "join mem m on m.rowid=f.rowid where mem_fts match ?" + tag_clause +
                    " order by rank limit ?", (t, k)).fetchall()
            except sqlite3.OperationalError:
                rr = []
            for x in rr:
                if x[1] not in seen:
                    seen.add(x[1])
                    got.append(x)
        rows = got
    c.close()
    hits = [{"src": r[0], "ref": r[1], "name": r[2], "at": r[3],
             "role": r[4], "text": (r[5] or "")[:300], "tag": r[6]} for r in rows]
    by = {}
    for h in hits:
        by.setdefault(h["src"], []).append(h)
    return {"ok": True, "query": q, "total": len(hits),
            "by_src": {k2: len(v) for k2, v in by.items()}, "hits": hits}


def stats() -> dict:
    c = _conn()
    tot = c.execute("select count(*) from mem").fetchone()[0]
    bysrc = c.execute("select src, tag, count(*) from mem group by src, tag").fetchall()
    c.close()
    return {"total": tot,
            "by_src_tag": [{"src": a, "tag": b, "n": n} for a, b, n in bysrc]}


def main() -> int:
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--survey", action="store_true")
    ap.add_argument("--index", action="store_true")
    ap.add_argument("--stats", action="store_true")
    ap.add_argument("--recall", default="")
    ap.add_argument("--include-test", action="store_true")
    a = ap.parse_args()
    if a.survey:
        print(json.dumps(survey(), ensure_ascii=False, indent=1))
        return 0
    if a.index:
        print(json.dumps(index(), ensure_ascii=False))
        print(json.dumps(stats(), ensure_ascii=False))
        return 0
    if a.stats:
        print(json.dumps(stats(), ensure_ascii=False, indent=1))
        return 0
    if a.recall:
        print(json.dumps(recall(a.recall, include_test=a.include_test), ensure_ascii=False, indent=1))
        return 0
    ap.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
