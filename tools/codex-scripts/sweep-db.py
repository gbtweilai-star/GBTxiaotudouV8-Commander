# -*- coding: utf-8 -*-
"""
sweep-db.py — 排查/扫雷事件库访问层（专业配置 · 单一入口）

定位（deploy/cloud-10/db-fleet.json v3 / docs/数据库架构梳理.md）：
  - 本地库 state/sweep-events.db = warm 槽位（db-tidb）开通前的本地位，兼 hot 岗；
  - 冷归档 state/sweep-archive/sweep-events-YYYYMM.db = R2 槽位开通前的本地位；
  - 云库钥匙到位后，分片路由（shard_map）与 SQL 形状不变，只换 endpoint_env。

专业配置（与 deploy/cloud-10/db-fleet.sql §0 同口径）：
  page_size=8192 / journal_mode=WAL / synchronous=NORMAL / cache_size=64MB /
  foreign_keys=ON / busy_timeout=5s / temp_store=MEMORY / mmap_size=256MB

纪律：
  - 运行期 SQL 一律参数绑定（? 占位）；表名只许来自 partition_registry 或服务端计算的月份，
    并过 ^sweep_events_\\d{6}$ 校验——外部输入永远拼不进 SQL。
  - 写入批量 500–2000 行/批（反模式 7：逐行 insert = part 爆炸）。
  - 退休 = ATTACH 摘表归档 + 登记 + DROP TABLE（元数据级）；禁大范围 DELETE（反模式 6）。
  - integrity_check 不 ok = 立即报，不带病服役。

用法：
  python sweep-db.py init [--db PATH]
  python sweep-db.py roll-month [--db PATH]
  python sweep-db.py write < events.jsonl                 # stdin 每行一个 JSON 事件
  python sweep-db.py query q1 --event-type heartbeat --from T --to T
  python sweep-db.py query q2 --target-id X [--after-ts T --after-uid U]
  python sweep-db.py query q3 --tentacle-id X --since T
  python sweep-db.py archive --month 2026-07 [--to DIR]
  python sweep-db.py health
  python sweep-db.py vacuum
  python sweep-db.py selftest
"""
import argparse
import json
import os
import re
import secrets
import shutil
import sqlite3
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8")   # type: ignore[attr-defined]
    except Exception:
        pass

REPO_ROOT = Path(__file__).resolve().parents[2]
DB_DEFAULT = REPO_ROOT / "state" / "sweep-events.db"
ARCHIVE_DIR_DEFAULT = REPO_ROOT / "state" / "sweep-archive"
MONTH_RE = re.compile(r"^\d{4}-\d{2}$")
TABLE_RE = re.compile(r"^sweep_events_\d{6}$")
WRITE_BATCH = 1000
HOT_VIEW_MONTHS = 3
_CROCKFORD = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"


def utcnow_ms() -> str:
    """ISO-8601 UTC 毫秒；字典序=时间序（范围查询不函数包列——反模式 3）。"""
    d = datetime.now(timezone.utc)
    return d.strftime("%Y-%m-%dT%H:%M:%S.") + f"{d.microsecond // 1000:03d}Z"


def ulid() -> str:
    """26 字符 ULID（Crockford base32：48bit 毫秒 + 80bit 随机）。跨分片唯一且可排序。"""
    ts = int(time.time() * 1000)
    head = []
    for _ in range(10):
        head.append(_CROCKFORD[ts & 31]); ts >>= 5
    rnd = secrets.randbits(80)
    tail = []
    for _ in range(16):
        tail.append(_CROCKFORD[rnd & 31]); rnd >>= 5
    return "".join(reversed(head)) + "".join(reversed(tail))


def db_path(args) -> Path:
    p = getattr(args, "db", None) or os.environ.get("GBT_SWEEP_DB") or str(DB_DEFAULT)
    return Path(p)


def archive_dir(args) -> Path:
    return Path(getattr(args, "to", None) or str(ARCHIVE_DIR_DEFAULT))


def month_of(ts: str) -> str:
    return ts[:7]


def table_for(month: str) -> str:
    if not MONTH_RE.match(month):
        raise ValueError(f"月份不合法：{month!r}")
    t = "sweep_events_" + month.replace("-", "")
    if not TABLE_RE.match(t):
        raise ValueError(f"表名不合法：{t!r}")
    return t


def connect(path: Path) -> sqlite3.Connection:
    """专业连接：PRAGMA 逐条落，读回断言——配不上就明说，不静默降级。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path), timeout=5.0, isolation_level=None)
    conn.row_factory = sqlite3.Row
    for pragma in ("PRAGMA journal_mode=WAL", "PRAGMA synchronous=NORMAL",
                   "PRAGMA cache_size=-64000", "PRAGMA foreign_keys=ON",
                   "PRAGMA busy_timeout=5000", "PRAGMA temp_store=MEMORY",
                   "PRAGMA mmap_size=268435456"):
        conn.execute(pragma)
    jm = conn.execute("PRAGMA journal_mode").fetchone()[0]
    if str(jm).lower() != "wal":
        raise RuntimeError(f"journal_mode={jm}，预期 WAL——拒绝静默降级")
    return conn


def enforce_page_size(conn, size: int = 8192) -> dict:
    """把库收敛到 8KB 页。⚠️ WAL 下直接 PRAGMA page_size 不生效（读回仍是旧值）：
    必须先切 journal_mode=DELETE → VACUUM 重建 → 切回 WAL。这是实测过的坑。"""
    cur = conn.execute("PRAGMA page_size").fetchone()[0]
    if cur == size:
        return {"page_size": cur, "changed": False}
    conn.execute("PRAGMA journal_mode=DELETE")
    conn.execute(f"PRAGMA page_size={size}")
    conn.execute("VACUUM")
    conn.execute("PRAGMA journal_mode=WAL")
    now = conn.execute("PRAGMA page_size").fetchone()[0]
    if now != size:
        raise RuntimeError(f"page_size 收敛失败：{now} != {size}")
    return {"page_size": now, "changed": True}


def ensure_schema(conn: sqlite3.Connection) -> None:
    conn.execute("""CREATE TABLE IF NOT EXISTS schema_version (
        version INTEGER PRIMARY KEY,
        applied_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
        note TEXT)""")
    conn.execute("""CREATE TABLE IF NOT EXISTS partition_registry (
        month TEXT PRIMARY KEY,
        table_name TEXT NOT NULL UNIQUE,
        first_ts TEXT, last_ts TEXT,
        row_count INTEGER NOT NULL DEFAULT 0,
        status TEXT NOT NULL DEFAULT 'hot',
        archive_path TEXT, archived_at TEXT,
        created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')))""")
    conn.execute("""CREATE TABLE IF NOT EXISTS shard_map (
        shard_id TEXT PRIMARY KEY,
        hash_start TEXT NOT NULL, hash_end TEXT NOT NULL,
        slot TEXT NOT NULL, endpoint_env TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'reserved', note TEXT)""")
    conn.execute("""INSERT OR IGNORE INTO shard_map (shard_id, hash_start, hash_end, slot, endpoint_env, status, note)
        VALUES ('warm-shard-01', '00000000', 'ffffffff', 'local:sweep-events.db', '(none)', 'active',
                '本地位；云槽位钥匙到位后按 T1 切环')""")
    n = conn.execute("SELECT COUNT(*) FROM schema_version").fetchone()[0]
    if n == 0:
        conn.execute("INSERT INTO schema_version (version, note) VALUES (1, 'initial: sweep-db.py')")
    create_month(conn, month_of(utcnow_ms()))


def create_month(conn: sqlite3.Connection, month: str) -> str:
    """建月度分区（DDL 模板只此一份；表名经双重校验，与 db-fleet.sql §1 同形）。"""
    t = table_for(month)
    suf = month.replace("-", "")
    conn.execute("BEGIN IMMEDIATE")
    try:
        conn.execute(f"""CREATE TABLE IF NOT EXISTS {t} (
            id INTEGER PRIMARY KEY,
            event_uid TEXT NOT NULL UNIQUE,
            ts TEXT NOT NULL,
            event_type TEXT NOT NULL,
            tentacle_id TEXT NOT NULL,
            target_id TEXT NOT NULL,
            severity INTEGER NOT NULL DEFAULT 0,
            payload_json TEXT,
            created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')))""")
        conn.execute(f"CREATE INDEX IF NOT EXISTS idx_{suf}_type_ts ON {t} (event_type, ts)")
        conn.execute(f"CREATE INDEX IF NOT EXISTS idx_{suf}_target_ts ON {t} (target_id, ts)")
        conn.execute(f"CREATE INDEX IF NOT EXISTS idx_{suf}_tentacle_ts ON {t} (tentacle_id, ts)")
        conn.execute("INSERT OR IGNORE INTO partition_registry (month, table_name) VALUES (?, ?)", (month, t))
        conn.execute("COMMIT")
    except Exception:
        conn.execute("ROLLBACK"); raise
    return t


def hot_tables(conn: sqlite3.Connection, n: int = HOT_VIEW_MONTHS, include_archived: bool = False):
    """热分区表名清单（旧→新）。SQL 里的表名只许出自这里。"""
    sql = "SELECT table_name FROM partition_registry"
    if not include_archived:
        sql += " WHERE status = 'hot'"
    sql += " ORDER BY month DESC LIMIT ?"
    tables = [r[0] for r in conn.execute(sql, (n,)).fetchall()]
    for t in tables:
        if not TABLE_RE.match(t):
            raise RuntimeError(f"registry 表名不合法：{t!r}")
    return list(reversed(tables))


def union_sql(conn: sqlite3.Connection, n: int = HOT_VIEW_MONTHS) -> str:
    tables = hot_tables(conn, n)
    if not tables:
        return ("SELECT NULL AS id, NULL AS event_uid, NULL AS ts, NULL AS event_type, "
                "NULL AS tentacle_id, NULL AS target_id, NULL AS severity, NULL AS payload_json WHERE 0")
    return " UNION ALL ".join(f"SELECT * FROM {t}" for t in tables)


def refresh_hot_view(conn: sqlite3.Connection) -> list:
    tables = hot_tables(conn)
    body = " UNION ALL ".join(f"SELECT * FROM {t}" for t in tables) if tables else "SELECT 1 WHERE 0"
    conn.execute("BEGIN IMMEDIATE")
    try:
        conn.execute("DROP VIEW IF EXISTS sweep_events_hot")
        conn.execute(f"CREATE VIEW sweep_events_hot AS {body}")
        conn.execute("COMMIT")
    except Exception:
        conn.execute("ROLLBACK"); raise
    return tables


# ---------------------------------------------------------------- 写路径

REQUIRED_FIELDS = ("event_type", "tentacle_id", "target_id")


def write_events(conn: sqlite3.Connection, events) -> dict:
    """批量写入（500–2000/批；按月分事务；登记 row_count/last_ts）。"""
    accepted, rejected = 0, []
    batch, batch_month = [], None
    stats = {}
    for i, ev in enumerate(events):
        try:
            if not isinstance(ev, dict):
                raise ValueError("event 必须是 JSON 对象")
            for f in REQUIRED_FIELDS:
                if not ev.get(f):
                    raise ValueError(f"缺字段 {f}")
            ts = ev.get("ts") or utcnow_ms()
            payload = ev.get("payload_json", ev.get("payload"))
            if isinstance(payload, (dict, list)):
                payload = json.dumps(payload, ensure_ascii=False)
            row = (ulid(), ts, ev["event_type"], str(ev["tentacle_id"]), str(ev["target_id"]),
                   int(ev.get("severity", 0)), payload)
            m = month_of(ts)
            if m != batch_month and batch:
                accepted += _flush(conn, batch_month, batch, stats)
                batch = []
            batch_month = m
            batch.append(row)
        except Exception as e:
            rejected.append({"line": i + 1, "error": str(e)})
    if batch:
        accepted += _flush(conn, batch_month, batch, stats)
    return {"accepted": accepted, "rejected": rejected, "per_month": stats}


def _flush(conn: sqlite3.Connection, month: str, batch, stats: dict) -> int:
    t = table_for(month)
    exists = conn.execute(
        "SELECT 1 FROM partition_registry WHERE month=? AND table_name=?", (month, t)).fetchone()
    if not exists:
        create_month(conn, month)
    conn.execute("BEGIN IMMEDIATE")
    try:
        for k in range(0, len(batch), WRITE_BATCH):
            chunk = batch[k:k + WRITE_BATCH]
            conn.executemany(
                f"INSERT INTO {t} (event_uid, ts, event_type, tentacle_id, target_id, severity, payload_json) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)", chunk)
        max_ts = max(r[1] for r in batch)
        conn.execute(
            "UPDATE partition_registry SET row_count = row_count + ?, last_ts = ? "
            "WHERE month = ? AND (? > IFNULL(last_ts, ''))", (len(batch), max_ts, month, max_ts))
        conn.execute("COMMIT")
    except Exception:
        conn.execute("ROLLBACK")
        raise
    stats[month] = stats.get(month, 0) + len(batch)
    return len(batch)


# ---------------------------------------------------------------- 读路径（Q1–Q3，参数绑定）

def q1(conn, event_type, from_ts, to_ts):
    sql = (f"SELECT event_type, COUNT(*) AS n, COUNT(DISTINCT tentacle_id) AS tentacles, "
           f"SUM(CASE WHEN severity = 2 THEN 1 ELSE 0 END) AS critical "
           f"FROM ({union_sql(conn)}) WHERE event_type = ? AND ts >= ? AND ts < ? GROUP BY event_type")
    return [dict(r) for r in conn.execute(sql, (event_type, from_ts, to_ts))]


def q2(conn, target_id, after_ts=None, after_uid=None, limit=200):
    """目标穿透轨迹；keyset 游标 = (ts, event_uid)，跨分区安全。"""
    if after_ts:
        sql = (f"SELECT ts, event_uid, event_type, tentacle_id, severity, payload_json FROM ({union_sql(conn)}) "
               f"WHERE target_id = ? AND (ts > ? OR (ts = ? AND event_uid > ?)) ORDER BY ts, event_uid LIMIT ?")
        args = (target_id, after_ts, after_ts, after_uid or "", limit)
    else:
        sql = (f"SELECT ts, event_uid, event_type, tentacle_id, severity, payload_json FROM ({union_sql(conn)}) "
               f"WHERE target_id = ? ORDER BY ts, event_uid LIMIT ?")
        args = (target_id, limit)
    return [dict(r) for r in conn.execute(sql, args)]


def q3(conn, tentacle_id, since_ts, limit=100):
    sql = (f"SELECT ts, event_type, target_id FROM ({union_sql(conn)}) "
           f"WHERE tentacle_id = ? AND ts >= ? ORDER BY ts DESC LIMIT ?")
    return [dict(r) for r in conn.execute(sql, (tentacle_id, since_ts, limit))]


# ---------------------------------------------------------------- 归档（ATTACH 摘表，元数据级退休）

def _arch_index_ddl(month: str) -> list:
    """归档库的三把索引。⚠️ SQLite 语法：CREATE INDEX 的表名不许带 schema 限定，
    限定符加在索引名上（CREATE INDEX arch.idx ON t (...)）——加错位置就是 near "." 语法错。
    与 create_month 的三把索引同名同列序，索引口径不分本地/归档。"""
    suf = month.replace("-", "")
    t = table_for(month)
    return [f"CREATE INDEX IF NOT EXISTS arch.idx_{suf}_type_ts ON {t} (event_type, ts)",
            f"CREATE INDEX IF NOT EXISTS arch.idx_{suf}_target_ts ON {t} (target_id, ts)",
            f"CREATE INDEX IF NOT EXISTS arch.idx_{suf}_tentacle_ts ON {t} (tentacle_id, ts)"]


def archive_month(conn, month: str, to_dir: Path) -> dict:
    """把指定月份的整张分区表搬进独立归档库：登记 archived → DROP TABLE。
    顺序：ATTACH（事务外）→ 建表+搬数（一事务）→ 登记+摘表（同一事务）→ DETACH → 行数核对。
    """
    t = table_for(month)
    row = conn.execute("SELECT status, row_count FROM partition_registry WHERE month=?", (month,)).fetchone()
    if not row:
        raise RuntimeError(f"无此分区：{month}")
    if row["status"] != "hot":
        raise RuntimeError(f"{month} 已是 {row['status']}，不重复归档")
    to_dir.mkdir(parents=True, exist_ok=True)
    dest = to_dir / f"sweep-events-{month}.db"
    if dest.exists():
        raise RuntimeError(f"归档目标已存在，拒绝覆盖：{dest}")
    before = row["row_count"]
    idx_ddl = _arch_index_ddl(month)
    conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    conn.execute("ATTACH DATABASE ? AS arch", (str(dest),))
    try:
        conn.execute("BEGIN IMMEDIATE")
        try:
            conn.execute(f"CREATE TABLE arch.{t} ("
                         "id INTEGER PRIMARY KEY, event_uid TEXT NOT NULL UNIQUE, ts TEXT NOT NULL, "
                         "event_type TEXT NOT NULL, tentacle_id TEXT NOT NULL, target_id TEXT NOT NULL, "
                         "severity INTEGER NOT NULL DEFAULT 0, payload_json TEXT, "
                         "created_at TEXT NOT NULL)")
            conn.execute(f"INSERT INTO arch.{t} SELECT id, event_uid, ts, event_type, tentacle_id, target_id, "
                         f"severity, payload_json, created_at FROM main.{t}")
            for stmt in idx_ddl:
                conn.execute(stmt)
            conn.execute("UPDATE main.partition_registry SET status='archived', archive_path=?, "
                         "archived_at=strftime('%Y-%m-%dT%H:%M:%fZ','now') WHERE month=?", (str(dest), month))
            conn.execute(f"DROP TABLE main.{t}")
            conn.execute("COMMIT")
        except Exception:
            conn.execute("ROLLBACK")
            raise
    finally:
        conn.execute("DETACH DATABASE arch")
    # 核对：归档文件行数必须与登记一致——对不上就明说（诚实优先于流程走完）
    ac = sqlite3.connect(f"file:{dest}?mode=ro", uri=True)
    try:
        moved = ac.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
    finally:
        ac.close()
    ok = (moved == before)
    return {"month": month, "archive": str(dest), "rows_registered": before,
            "rows_moved": moved, "match": ok}


# ---------------------------------------------------------------- 运维

def health(conn) -> dict:
    out = {"integrity": conn.execute("PRAGMA integrity_check").fetchone()[0],
           "journal_mode": conn.execute("PRAGMA journal_mode").fetchone()[0],
           "page_size": conn.execute("PRAGMA page_size").fetchone()[0],
           "cache_size": conn.execute("PRAGMA cache_size").fetchone()[0],
           "partitions": [], "indexes": []}
    for r in conn.execute("SELECT month, table_name, row_count, status FROM partition_registry ORDER BY month"):
        if r["status"] == "hot":
            actual = conn.execute(f"SELECT COUNT(*) FROM {r['table_name']}").fetchone()[0]
            out["partitions"].append({"month": r["month"], "table": r["table_name"],
                                      "registered": r["row_count"], "actual": actual,
                                      "drift": actual - r["row_count"], "status": "hot"})
        else:
            # archived：表已摘出主库（元数据级退休），只报登记值与归档路径，不强行 COUNT
            ap = conn.execute("SELECT archive_path FROM partition_registry WHERE month=?", (r["month"],)).fetchone()
            out["partitions"].append({"month": r["month"], "table": r["table_name"],
                                      "registered": r["row_count"], "actual": None,
                                      "drift": None, "status": r["status"],
                                      "archive_path": ap["archive_path"] if ap else None})
    for r in conn.execute("SELECT name, tbl_name FROM sqlite_master WHERE type='index' AND name LIKE 'idx_%'"):
        out["indexes"].append(f"{r['tbl_name']}.{r['name']}")
    out["shard_map"] = [dict(r) for r in conn.execute("SELECT shard_id, slot, status FROM shard_map")]
    return out


def vacuum(conn) -> dict:
    conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    conn.execute("PRAGMA optimize")
    conn.execute("PRAGMA incremental_vacuum")
    return {"freelist_count": conn.execute("PRAGMA freelist_count").fetchone()[0],
            "page_count": conn.execute("PRAGMA page_count").fetchone()[0]}


def backup(path: Path, dest: Path) -> str:
    """整库原子快照（VACUUM INTO）——与按月归档是两回事，别混用。"""
    conn = connect(path)
    try:
        conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        conn.execute("VACUUM INTO ?", (str(dest),))
    finally:
        conn.close()
    return str(dest)


# ---------------------------------------------------------------- 自检

def selftest() -> int:
    tmp = Path(tempfile.mkdtemp(prefix="sweep-db-selftest-"))
    fails = []
    try:
        db = tmp / "t.db"
        conn = connect(db)
        ensure_schema(conn)
        if enforce_page_size(conn)["page_size"] != 8192:
            fails.append("page_size enforce failed")
        evs = [{"event_type": "heartbeat", "tentacle_id": f"t{i}", "target_id": "f%d" % (i % 3),
                "severity": i % 3, "ts": f"2026-09-0{i + 1}T00:00:00.000Z"} for i in range(3)]
        evs += [{"event_type": "finding", "tentacle_id": "t9", "target_id": "f1",
                 "severity": 2, "ts": "2026-10-02T00:00:00.000Z",
                 "payload": {"k": "值"}}]
        r = write_events(conn, evs)
        if r["accepted"] != 4 or r["rejected"]:
            fails.append(f"write: {r}")
        r1 = q1(conn, "heartbeat", "2026-09-01T00:00:00.000Z", "2026-10-01T00:00:00.000Z")
        if not r1 or r1[0]["n"] != 3:
            fails.append(f"q1: {r1}")
        r2 = q2(conn, "f1", limit=10)
        if len(r2) != 2:
            fails.append(f"q2 len={len(r2)}")
        cur = q2(conn, "f1", after_ts=r2[0]["ts"], after_uid=r2[0]["event_uid"], limit=10)
        if len(cur) != 1:
            fails.append(f"q2 cursor: {cur}")
        r3 = q3(conn, "t9", "2026-01-01T00:00:00.000Z")
        if not r3:
            fails.append("q3 empty")
        # 归档 2026-09：搬数 → 登记 → 摘表
        a = archive_month(conn, "2026-09", tmp / "arch")
        if not a["match"] or a["rows_moved"] != 3:
            fails.append(f"archive: {a}")
        left = conn.execute("SELECT COUNT(*) FROM sweep_events_202610").fetchone()[0]
        if left != 1:
            fails.append(f"after archive remaining={left}")
        st = conn.execute("SELECT status FROM partition_registry WHERE month='2026-09'").fetchone()[0]
        if st != "archived":
            fails.append(f"registry status={st}")
        h = health(conn)
        if h["integrity"] != "ok":
            fails.append(f"integrity: {h['integrity']}")
        if h["page_size"] != 8192:
            fails.append(f"page_size: {h['page_size']} != 8192（空库设页应在建表前生效）")
        v = vacuum(conn)
        conn.close()
        print("PASS" if not fails else "FAIL " + " | ".join(fails),
              "| tmp:", tmp)
        return 0 if not fails else 1
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


# ---------------------------------------------------------------- CLI

def _out(obj, as_json):
    print(json.dumps(obj, ensure_ascii=False, indent=2) if as_json else obj)


def main() -> int:
    ap = argparse.ArgumentParser(description="排查/扫雷事件库访问层（专业配置）")
    ap.add_argument("--db", help="库路径（默认 state/sweep-events.db，或 GBT_SWEEP_DB）")
    ap.add_argument("--to", help="归档目录（默认 state/sweep-archive）")
    ap.add_argument("--json", action="store_true", help="JSON 输出")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("init")
    sub.add_parser("roll-month")
    sub.add_parser("health")
    sub.add_parser("vacuum")
    sub.add_parser("selftest")
    p = sub.add_parser("write")
    p.add_argument("file", nargs="?", default="-", help="JSONL 文件，默认 stdin")
    q = sub.add_parser("query")
    q.add_argument("kind", choices=["q1", "q2", "q3"])
    q.add_argument("--event-type"); q.add_argument("--from", dest="from_ts"); q.add_argument("--to", dest="to_ts")
    q.add_argument("--target-id"); q.add_argument("--tentacle-id"); q.add_argument("--since")
    q.add_argument("--after-ts"); q.add_argument("--after-uid"); q.add_argument("--limit", type=int)
    a = sub.add_parser("archive")
    a.add_argument("--month", required=True)
    b = sub.add_parser("backup")
    b.add_argument("dest")
    args = ap.parse_args()

    if args.cmd == "selftest":
        return selftest()
    conn = connect(db_path(args))
    try:
        if args.cmd == "init":
            ensure_schema(conn)
            repaged = enforce_page_size(conn)
            refresh_hot_view(conn)
            _out({"ok": True, "db": str(db_path(args)), "repaged": repaged,
                  "tables": [r[0] for r in conn.execute(
                      "SELECT table_name FROM partition_registry ORDER BY month")]}, args.json)
        elif args.cmd == "roll-month":
            t = create_month(conn, month_of(utcnow_ms()))
            views = refresh_hot_view(conn)
            _out({"ok": True, "partition": t, "hot_view_over": views}, args.json)
        elif args.cmd == "write":
            fh = sys.stdin if args.file == "-" else open(args.file, "r", encoding="utf-8")
            evs = []
            bad = 0
            with fh:
                for ln, line in enumerate(fh, 1):
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        evs.append(json.loads(line))
                    except Exception:
                        bad += 1
                        evs.append({"__parse_error__": ln})
            evs = [e for e in evs if "__parse_error__" not in e]
            res = write_events(conn, evs)
            res["parse_errors"] = bad
            _out(res, args.json)
        elif args.cmd == "query":
            if args.kind == "q1":
                res = q1(conn, args.event_type, args.from_ts, args.to_ts)
            elif args.kind == "q2":
                res = q2(conn, args.target_id, args.after_ts, args.after_uid, args.limit or 200)
            else:
                res = q3(conn, args.tentacle_id, args.since, args.limit or 100)
            _out(res, True)   # 数据命令恒 JSON：给管道/面板消费，不给人眼
        elif args.cmd == "archive":
            _out(archive_month(conn, args.month, archive_dir(args)), True)
        elif args.cmd == "backup":
            _out({"backup": backup(db_path(args), Path(args.dest))}, True)
        elif args.cmd == "health":
            _out(health(conn), True)
        elif args.cmd == "vacuum":
            _out(vacuum(conn), True)
        return 0
    finally:
        for s in (sys.stdout, sys.stderr):
            try:
                s.flush()
            except Exception:
                pass


if __name__ == "__main__":
    import os as _os
    _code = main()
    for _s in (sys.stdout, sys.stderr):
        try:
            _s.flush()
        except Exception:
            pass
    _os._exit(_code if isinstance(_code, int) else 0)
