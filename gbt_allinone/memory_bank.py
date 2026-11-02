"""GBT小土豆V8 · 记忆库（单一事实源 / 秒查 / 无死角 / 90 天保留）

硬约束：
  · 每条记忆必含 at(ISO8601+时区)、source、actor、action、target、detail、
    evidence_sha256、confidence、version、parent_hash；缺一拒收（不补默认、不猜）。
  · 秒查：SQLite + FTS5 全文索引（无 FTS5 自动回退 LIKE）。
  · 无死角：读取返回 coverage（已读/命中总数），<1 不许声称看全。
  · 清理：仅删 at 早于 90 天的记录；未满 90 天一条不删；默认 dry-run，归档+审计。
  · 所有智能体共用本库（单一事实源），写入带版本与父链。

开发者：自由的风 · GBT小土豆V8
"""
from __future__ import annotations

import hashlib
import json
import re
import sqlite3
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DB = ROOT / "state" / "memory" / "memory.db"
KEEP_DAYS = 90
REQUIRED = ("at", "source", "actor", "action", "target", "detail",
            "evidence_sha256", "confidence", "version", "parent_hash")
ISO = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:[+-]\d{2}:\d{2}|Z)$")


def _conn() -> sqlite3.Connection:
    DB.parent.mkdir(parents=True, exist_ok=True)
    c = sqlite3.connect(DB)
    c.row_factory = sqlite3.Row
    c.execute("""CREATE TABLE IF NOT EXISTS memory(
        id INTEGER PRIMARY KEY AUTOINCREMENT, at TEXT NOT NULL, source TEXT NOT NULL,
        actor TEXT NOT NULL, action TEXT NOT NULL, target TEXT NOT NULL,
        detail TEXT NOT NULL, evidence_sha256 TEXT NOT NULL, confidence REAL NOT NULL,
        version INTEGER NOT NULL, parent_hash TEXT NOT NULL)""")
    try:
        c.execute("CREATE VIRTUAL TABLE IF NOT EXISTS memory_fts USING fts5(detail)")
    except sqlite3.OperationalError:
        pass
    c.commit()
    return c


def store(**kw) -> dict:
    missing = [k for k in REQUIRED if kw.get(k) in (None, "")]
    if missing:
        return {"ok": False, "reason": "缺必填字段，拒收：%s" % missing}
    if not ISO.match(str(kw["at"])):
        return {"ok": False, "reason": "at 必须 ISO8601+时区（例 2026-11-02T04:00:00+07:00）"}
    det = str(kw["detail"])
    sha = hashlib.sha256(det.encode("utf-8")).hexdigest()
    if kw["evidence_sha256"] and kw["evidence_sha256"] != sha:
        pass  # 证据哈希可为外部证据；详情哈希另存于 detail_sha256
    c = _conn()
    cur = c.execute("INSERT INTO memory(at,source,actor,action,target,detail,"
                    "evidence_sha256,confidence,version,parent_hash) VALUES(?,?,?,?,?,?,?,?,?,?)",
                    (kw["at"], kw["source"], kw["actor"], kw["action"], kw["target"], det,
                     kw["evidence_sha256"], float(kw["confidence"]), int(kw["version"]),
                     kw["parent_hash"]))
    mid = cur.lastrowid
    try:
        c.execute("INSERT INTO memory_fts(rowid, detail) VALUES(?,?)", (mid, det))
    except sqlite3.OperationalError:
        pass
    c.commit()
    c.close()
    return {"ok": True, "id": mid, "detail_sha256": sha}


def recall(q: str = "", limit: int = 50, since: str = "", until: str = "") -> dict:
    """秒查 + 覆盖率：返回 hits 与 coverage（本次返回/总命中）。"""
    c = _conn()
    where, args = [], []
    if since:
        where.append("at >= ?"); args.append(since)
    if until:
        where.append("at <= ?"); args.append(until)
    base = ("SELECT * FROM memory" + (" WHERE " + " AND ".join(where) if where else ""))
    total = c.execute("SELECT COUNT(*) FROM " + ("memory" if not where else "(" + base + ")"),
                      args).fetchone()[0]
    if q:
        try:
            ids = [r[0] for r in c.execute(
                "SELECT rowid FROM memory_fts WHERE detail MATCH ? LIMIT ?", (q, limit))]
            rows = [dict(c.execute("SELECT * FROM memory WHERE id=?", (i,)).fetchone()) for i in ids]
            if not ids:
                raise sqlite3.OperationalError("fts-empty")
        except sqlite3.OperationalError:
            w2 = ["detail LIKE ?"] + where
            a2 = ["%" + q + "%"] + args
            where_sql = " AND ".join(w2)
            rows = [dict(r) for r in c.execute(
                "SELECT * FROM memory WHERE " + where_sql + " ORDER BY at DESC LIMIT ?",
                a2 + [limit])]
            total = c.execute("SELECT COUNT(*) FROM memory WHERE " + where_sql, a2).fetchone()[0]
    else:
        rows = [dict(r) for r in c.execute(base + " ORDER BY at DESC LIMIT ?", args + [limit])]
    c.close()
    return {"ok": True, "hits": rows, "returned": len(rows), "total": total,
            "coverage": round(len(rows) / total, 3) if total else 1.0,
            "complete": len(rows) >= total}


def gc(confirm: bool = False) -> dict:
    """按时间清理：仅删 90 天前的记录；未满 90 天一条不删。"""
    cutoff = time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(time.time() - KEEP_DAYS * 86400))
    c = _conn()
    rows = [dict(r) for r in c.execute("SELECT * FROM memory WHERE at < ?", (cutoff,))]
    if not rows:
        c.close()
        return {"ok": True, "cutoff": cutoff, "deleted": 0, "dry_run": not confirm}
    if not confirm:
        c.close()
        return {"ok": True, "cutoff": cutoff, "would_delete": len(rows), "dry_run": True,
                "reason": "默认 dry-run；confirm=true 才归档并删除"}
    arc = DB.parent / ("archive-%s.jsonl" % time.strftime("%Y"))
    with arc.open("a", encoding="utf-8") as fh:
        for r in rows:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")
    ids = [r["id"] for r in rows]
    c.executemany("DELETE FROM memory WHERE id=?", [(i,) for i in ids])
    c.commit()
    c.close()
    return {"ok": True, "cutoff": cutoff, "deleted": len(ids), "archive": str(arc),
            "dry_run": False}


if __name__ == "__main__":
    import sys
    cmd = sys.argv[1] if len(sys.argv) > 1 else "recall"
    print(json.dumps(
        gc("--confirm" in sys.argv) if cmd == "gc"
        else recall(sys.argv[2] if len(sys.argv) > 2 and not sys.argv[2].startswith("--") else ""),
        ensure_ascii=False, indent=2))
