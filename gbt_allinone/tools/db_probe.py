# gbt-capability: db_probe
# ⛔ 开发者：自由的风 · 永久钢印 · 禁止删除
"""本地只读查询台：**SQLite 概览（静态 SQL）+ JSONL 行统计**（蒸馏自 dbx 的"轻量客户端"架构）。

## 抓取口径（凡抓取必写源·时间·口径）
· **源**：2026-10-01 主人给的 GitHub 飙升榜 #3 截图 `t8y2/dbx`（25MB 轻量数据库客户端）。
  README 原文要点：「100+ databases in 25 MB. Desktop, Docker, CLI, built-in AI assistant, and MCP Server」；
  「No Java JRE. No Python venv. No bundled Chromium」；「Connection, plugin, AI, and tunnel credentials
  are encrypted before they are written to dbx.db」；「DBX speaks the Model Context Protocol」。
· **时间**：2026-10-01。Apache-2.0 · Rust · ★23,332（API 现读）。

## 蒸馏判断：dbx 的核里我们真缺哪块
| 它的架构 | 我们已有的对位 | 结论 |
|---|---|---|
| 本地数据变换（表格/转换） | `datakit`（只读：html→md / xlsx→JSON / CSV 合并） | **已有，不重造** |
| 100+ 外部库连接 / 隧道 / 凭据加密 | 无（要驱动 + 凭据 = **主人面**，不擅自装） | **不接**（如实记） |
| MCP 对外 | 本仓有唯一的门（run_task）+ 能力位面 | **不重造**（另造 = 第二个门） |
| **轻量只读概览：本地 SQLite 结构/行数 + JSONL 行统计** | 无 | **补这块** |

## 🔴 设计纪律（两版被安全钩子拦下后改的，改得对）
- 第一版收**自由 SQL**（用户字符串直接 execute）⇒ 被按「SQL 注入」拦。**拦得对**。
- 第二版改成**结构化 + 标识符白名单 + `?` 占位符**，但表名仍要拼进 SQL 串（`"SELECT * FROM %s" % t`）
  ⇒ 仍被拦。**也对**：只要 SQL 串里出现变量，静态检查就无法分辨"校验过"与"没校验"。
- ⇒ 第三版（现版）**一个动态 SQL 都不拼**：
  · 静态 SQL 只出现**字面量**（`SELECT name,type FROM sqlite_master …`）；
  · 要按名取东西一律走**参数**（`WHERE name = ?`，值是参数不是拼接）；
  · 列名从 **DDL 文本**里自己解析；行数从 **`iterdump()` 文本**里自己数（都在 Python 层，不 execute 动态 SQL）。
  · **代价如实说**：不提供"按条件查行/排序"（那要么拼 SQL，要么引 SQL 解析器）；
    需要时请主人给门加分支，或直接用 `jsonl` 那半（本仓多数账本是 JSONL）。

## 硬规矩
1. **零动态 SQL**（静态字面量 + 参数取值；表名不进 SQL 串）。
2. **连接 `mode=ro`**（只读 URI）。
3. **结果不落盘**；表/文件不在 ⇒ 结构化报缺。
"""
from __future__ import annotations

import json
import re
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
_CAP = "db_probe"
_DUMP_MAX_MB = 32                      # iterdump 的体量闸（大了就不 dump，如实说）
_RE_COL = re.compile(r'^\s*"?([A-Za-z_][A-Za-z0-9_]*)"?\s+(.+?)\s*$')


def _split_top(body: str) -> list:
    """**括号感知**切顶层逗号（DDL 里 `PRIMARY KEY (a, b)` 的逗号不算列分隔）。"""
    out, depth, cur = [], 0, []
    for ch in body:
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth = max(0, depth - 1)
        if ch == "," and depth == 0:
            out.append("".join(cur))
            cur = []
        else:
            cur.append(ch)
    if cur:
        out.append("".join(cur))
    return out


def _store_root() -> Path:
    env = __import__("os").getenv("GBT_STORE_DIR")
    if env:
        return Path(env)
    try:
        from gbt_allinone._paths import STORE_DIR
        return Path(STORE_DIR)
    except Exception:  # noqa: BLE001
        return ROOT / "gbt_allinone" / "store"


def _rel(p) -> str:
    try:
        return str(Path(p).relative_to(ROOT))
    except Exception:  # noqa: BLE001
        return str(p)


def _connect_ro(db: str):
    p = Path(db)
    if not p.is_file():
        raise FileNotFoundError("库不在：%r" % str(db)[:120])
    con = sqlite3.connect("file:%s?mode=ro" % p.as_posix(), uri=True)
    con.row_factory = sqlite3.Row
    return con, p


def sources() -> dict:
    """现读可查的本地源（只读列举）：store/state 下的 *.db/*.jsonl。"""
    roots = [_store_root(), ROOT / "state", ROOT / "gbt_allinone" / "store"]
    seen, dbs, jsonls = set(), [], []
    for r in roots:
        if not r.is_dir():
            continue
        for pat in ("**/*.db", "**/*.sqlite", "**/*.sqlite3"):
            for p in r.glob(pat):
                k = str(p.resolve())
                if k not in seen and p.is_file():
                    seen.add(k)
                    dbs.append({"path": _rel(p), "kb": round(p.stat().st_size / 1024, 1)})
        for p in r.glob("**/*.jsonl"):
            k = str(p.resolve())
            if k not in seen and p.is_file():
                seen.add(k)
                jsonls.append({"path": _rel(p), "kb": round(p.stat().st_size / 1024, 1)})
    dbs.sort(key=lambda x: -x["kb"])
    jsonls.sort(key=lambda x: -x["kb"])
    return {"ok": True, "op": "sources", "sqlite": dbs[:40], "jsonl": jsonls[:40],
            "n_sqlite": len(dbs), "n_jsonl": len(jsonls),
            "_口径": "只列本机（store/state）；外部库连接不在本件范围（要驱动+凭据=主人面）"}


def tables(db: str = "") -> dict:
    """列库里的表/视图（**静态 SQL**：字面量查询，无任何拼接）。"""
    try:
        con, p = _connect_ro(db)
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "fail_closed": True, "error": "%s: %s" % (type(exc).__name__, str(exc)[:120])}
    try:
        rows = con.execute("SELECT name, type, sql FROM sqlite_master "
                           "WHERE type IN ('table', 'view') ORDER BY name").fetchall()
        return {"ok": True, "op": "tables", "db": _rel(p),
                "tables": [{"name": r["name"], "type": r["type"]} for r in rows],
                "_口径": "静态 SQL 字面量（无拼接）；表名不参与任何 SQL 串"}
    finally:
        con.close()


def schema(db: str = "", table: str = "") -> dict:
    """列某表的列：**按名参数化取 DDL**（`WHERE name = ?`），列在 Python 层从 DDL 文本解析。"""
    t = str(table or "").strip()
    if not t:
        return {"ok": False, "fail_closed": True, "error": "缺 table"}
    try:
        con, p = _connect_ro(db)
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "fail_closed": True, "error": "%s: %s" % (type(exc).__name__, str(exc)[:120])}
    try:
        row = con.execute("SELECT sql FROM sqlite_master WHERE name = ?", (t,)).fetchone()
        if not row or not row["sql"]:
            return {"ok": False, "error": "表不存在：%s" % t[:80]}
        ddl = str(row["sql"])
        body = ddl[ddl.find("(") + 1:ddl.rfind(")")] if ("(" in ddl and ddl.rfind(")") > ddl.find("(")) else ddl
        cols = []
        for piece in _split_top(body):
            m = _RE_COL.match(piece.strip())
            if not m:
                continue
            if m.group(1).upper() in ("PRIMARY", "UNIQUE", "CHECK", "FOREIGN", "KEY", "CONSTRAINT"):
                continue
            cols.append({"name": m.group(1), "type": m.group(2).strip()[:40]})
        return {"ok": True, "op": "schema", "db": _rel(p), "table": t,
                "columns": cols, "ddl_chars": len(ddl),
                "_口径": "按名参数化取 DDL（值是参数不是拼接）；列在 Python 层解析 ⇒ 零动态 SQL"}
    finally:
        con.close()


def counts(db: str = "", limit_tables: int = 40) -> dict:
    """每表行数：从 **`iterdump()` 文本**里数 INSERT（Python 层计数，不 execute 动态 SQL）。"""
    try:
        con, p = _connect_ro(db)
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "fail_closed": True, "error": "%s: %s" % (type(exc).__name__, str(exc)[:120])}
    size_mb = p.stat().st_size / 1024 / 1024
    if size_mb > _DUMP_MAX_MB:
        return {"ok": False, "fail_closed": True,
                "error": "库 %.1f MB > 闸 %d MB ⇒ 不 dump（大了就是慢，如实说）" % (size_mb, _DUMP_MAX_MB)}
    try:
        per: dict = {}
        for line in con.iterdump():
            if line.startswith("INSERT INTO "):
                m = re.match(r'INSERT INTO "?([^"\s]+)"?', line)
                if m:
                    per[m.group(1)] = per.get(m.group(1), 0) + 1
        items = sorted(per.items(), key=lambda kv: -kv[1])[:max(1, int(limit_tables))]
        return {"ok": True, "op": "counts", "db": _rel(p), "size_mb": round(size_mb, 2),
                "行数按表": dict(items),
                "_口径": "iterdump 文本计数（Python 层）；空表不出现（0 行表去 tables 看）"}
    finally:
        con.close()


def jsonl(path: str = "", where: str = "", limit: int = 20) -> dict:
    """JSONL 行统计/筛选：`where` 形如 `key=value`（子串匹配）；坏行单独计数（不静默吞）。"""
    p = Path(path) if path else None
    if p is None or not p.is_file():
        return {"ok": False, "fail_closed": True, "error": "缺 path 或文件不在：%r" % str(path)[:120]}
    data, bad = [], 0
    for line in p.read_text(encoding="utf-8", errors="replace").splitlines():
        if not line.strip():
            continue
        try:
            data.append(json.loads(line))
        except Exception:  # noqa: BLE001
            bad += 1
    keys: dict = {}
    for r in data:
        if isinstance(r, dict):
            for k in r:
                keys[k] = keys.get(k, 0) + 1
    hits = data
    w = str(where or "").strip()
    if w and "=" in w:
        k, v = w.split("=", 1)
        hits = [r for r in data if isinstance(r, dict)
                and str(v).lower() in json.dumps(r.get(k.strip()), ensure_ascii=False).lower()]
    return {"ok": True, "op": "jsonl", "file": _rel(p), "rows": len(data), "坏行": bad,
            "字段出现次数": dict(sorted(keys.items(), key=lambda kv: -kv[1])[:20]),
            "筛选": w or "（无）", "命中": len(hits),
            "样例": hits[:max(1, min(200, int(limit)))],
            "_口径": "只读统计；坏行单独计数（不静默吞）"}


def where(**_kw) -> dict:
    return {"ok": True, "op": "where", "kind": _CAP, "tentacle": _CAP,
            "entry": "run_task('db_probe', {...})",
            "ops": ["sources", "tables", "schema", "counts", "jsonl", "where"],
            "distilled_from": "2026-10-01 主人给的飙升榜 #3 t8y2/dbx（25MB 轻量数据库客户端）"
                              "——只取**轻量只读概览**架构（源枚举 + 结构 + 行数 + 行统计）",
            "not_copied": "外部库连接/隧道/凭据加密 不接（=主人面）；MCP 对外不重造；本地数据变换已有 datakit",
            "hard_rules": ["🔴 **零动态 SQL**（两版被安全钩子按『SQL 注入』拦下 ⇒ 改为：静态字面量 SQL + "
                           "参数化取值 + DDL/iterdump 在 Python 层解析）",
                           "连接 mode=ro；结果不落盘",
                           "不提供『按条件查行/排序』（那要么拼 SQL 要么引解析器）—— 要就说，请主人给门加分支",
                           "jsonl 那半可自由筛选（纯 Python，不经 SQL）"],
            "contract": [
                {"op": "sources", "params": "—", "returns": "可查的本地 sqlite/jsonl 源"},
                {"op": "tables", "params": "db", "returns": "表/视图（静态 SQL）"},
                {"op": "schema", "params": "db + table", "returns": "列（参数化取 DDL + Python 解析）"},
                {"op": "counts", "params": "db + [limit_tables]", "returns": "每表行数（iterdump 计数）"},
                {"op": "jsonl", "params": "path + [where=key=value] + [limit]", "returns": "行统计+筛选样例"},
            ]}


def run_op(op: str = "sources", **params) -> dict:
    op = (op or "sources").lower()
    for n, fn in (("sources", sources), ("tables", tables), ("schema", schema),
                  ("counts", counts), ("jsonl", jsonl), ("where", where)):
        if op == n:
            return fn(**params)
    return {"ok": False, "fail_closed": True,
            "error": "未知 op:%s（sources/tables/schema/counts/jsonl/where）" % op}


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(description="本地只读查询台（dbx 蒸馏 · 零动态 SQL）")
    ap.add_argument("cmd", nargs="?", default="sources")
    ap.add_argument("--db", default="")
    ap.add_argument("--table", default="")
    ap.add_argument("--path", default="")
    ap.add_argument("--where", default="")
    ap.add_argument("--limit", type=int, default=50)
    a = ap.parse_args()
    print(json.dumps(run_op(a.cmd, db=a.db, table=a.table, path=a.path, where=a.where, limit=a.limit),
                     ensure_ascii=False, indent=1))
