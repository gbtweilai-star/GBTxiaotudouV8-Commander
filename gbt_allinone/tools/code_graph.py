# -*- coding: utf-8 -*-
# gbt-capability: code_graph
"""代码知识图谱（code_graph）—— 给 AI 的是「文件:行 + 签名 + 调用链」，不是文件正文。

主人令 2026-10-29（蒸馏自 symchenry/codegraph 的机制，不抄代码）：
本能力位**早已在注册表里、也早就有 api 分派**，但 `gbt_allinone/tools/code_graph.py`
这个模块**根本不存在** ⇒ 一调就 `ImportError`（2026-10-31 全仓逐项核对时抓到）。
本文件是把它补上：按注册表里的 desc 逐条落实现。

## 职责（与 desc 一一对应）

| 表 | 存什么 |
|---|---|
| `files` | 文件 → 语言 / mtime / 大小 / sha / 解析精度（exact） |
| `symbols` | 符号 → 名 / 类型 / 文件 / 行 / 签名 / 文档首行 |
| `edges` | 边 → 调用方符号 / 被调名字 / 类型(call/import) / 文件 / 行 |
| `symbols_fts` | FTS5 全文（名 + 签名 + 文档），支持中文检索 |

## op

    index   [path…] [limit N] [force]   建/更新索引（.py 走 ast，exact=1）
    find    q                            按名字/签名/文档找符号
    callers name                         谁调用了它（带 file:line）
    callees name                         它调用了谁
    summary [path]                       目录/文件摘要（符号数、边数）
    stats                                全库读数（文件/符号/边/耗时）

## 三条纪律

1. **不碰第三方与生成代码**：`node_modules` / `.pylibs` / `native_browser` / `mirror_space`
   一律不索引（索引它们只会把 token 浪费在库代码上）。
2. **没读到就说没读到**：解析失败的 .py 记进 `未解析`，**不静默跳过**。
3. **只读原文件**：除 `state/code_graph.sqlite` 外不写任何东西。
"""
from __future__ import annotations

import ast
import hashlib
import json
import os
import pathlib
import re
import sqlite3
import sys
import time

ROOT = pathlib.Path(__file__).resolve().parents[2]
DB = ROOT / "state" / "code_graph.sqlite"
SKIP_DIRS = {"node_modules", ".pylibs", "native_browser", "mirror_space", "__pycache__",
             ".git", "dist", "vendor", "_upstream", "archives", ".scratch", ".trash"}
PY_SUFFIX = {".py"}
JS_SUFFIX = {".js", ".cjs", ".mjs"}

_SCHEMA = """
CREATE TABLE IF NOT EXISTS files (
  path TEXT PRIMARY KEY, lang TEXT, mtime REAL, size INTEGER, sha TEXT, exact INTEGER, at TEXT
);
CREATE TABLE IF NOT EXISTS symbols (
  id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, kind TEXT, file TEXT, line INTEGER,
  signature TEXT, doc TEXT, exact INTEGER
);
CREATE TABLE IF NOT EXISTS edges (
  src TEXT, src_file TEXT, src_line INTEGER, dst TEXT, kind TEXT, file TEXT, line INTEGER
);
CREATE INDEX IF NOT EXISTS idx_sym_name ON symbols(name);
CREATE INDEX IF NOT EXISTS idx_sym_file ON symbols(file);
CREATE INDEX IF NOT EXISTS idx_edge_dst ON edges(dst);
CREATE INDEX IF NOT EXISTS idx_edge_src ON edges(src);
CREATE VIRTUAL TABLE IF NOT EXISTS symbols_fts USING fts5(name, signature, doc, content='');
"""


def _conn() -> sqlite3.Connection:
    DB.parent.mkdir(parents=True, exist_ok=True)
    c = sqlite3.connect(str(DB))
    c.executescript(_SCHEMA)
    return c


def _sha(p: pathlib.Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()[:16]


def _walk(paths: list[str], limit: int = 0):
    roots = [pathlib.Path(p) if os.path.isabs(p) else ROOT / p for p in paths] or [ROOT]
    n = 0
    for r in roots:
        if r.is_file():
            yield r
            n += 1
        else:
            for dirpath, dirnames, filenames in os.walk(r):
                dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS and not d.startswith(".")]
                for fn in filenames:
                    p = pathlib.Path(dirpath) / fn
                    if p.suffix not in PY_SUFFIX | JS_SUFFIX:
                        continue
                    yield p
                    n += 1
                    if limit and n >= limit:
                        return


def _sig(node: ast.AST) -> str:
    try:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            args = [a.arg for a in node.args.args]
            return "%s(%s)" % (node.name, ", ".join(args))
        if isinstance(node, ast.ClassDef):
            return "class %s" % node.name
    except Exception:  # noqa: BLE001
        pass
    return getattr(node, "name", "")


def _doc(node: ast.AST) -> str:
    try:
        d = ast.get_docstring(node) or ""
        return " ".join(d.split())[:200]
    except Exception:  # noqa: BLE001
        return ""


def _parse_py(p: pathlib.Path) -> dict:
    src = p.read_text(encoding="utf-8-sig", errors="replace")   # 容忍 BOM（实测踩过：BOM 会让 ast 直接 SyntaxError）
    tree = ast.parse(src, filename=str(p))
    rel = str(p.relative_to(ROOT)).replace("\\", "/")
    syms, edges, imports = [], [], []
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            syms.append({"name": node.name,
                         "kind": "class" if isinstance(node, ast.ClassDef) else "function",
                         "file": rel, "line": node.lineno,
                         "signature": _sig(node), "doc": _doc(node)})
        elif isinstance(node, (ast.Import, ast.ImportFrom)):
            mods = ([a.name for a in node.names] if isinstance(node, ast.Import)
                    else [node.module or ""])
            for m in mods:
                if m:
                    imports.append({"dst": m, "file": rel, "line": node.lineno})
    # 调用边：按「最内层函数」归属
    funcs = [n for n in ast.walk(tree)
             if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]
    for f in funcs:
        for node in ast.walk(f):
            if isinstance(node, ast.Call):
                fn = node.func
                name = fn.id if isinstance(fn, ast.Name) else (
                    fn.attr if isinstance(fn, ast.Attribute) else "")
                if name:
                    edges.append({"src": f.name, "src_file": rel, "src_line": f.lineno,
                                  "dst": name, "kind": "call", "file": rel, "line": node.lineno})
    return {"rel": rel, "symbols": syms, "edges": edges, "imports": imports, "exact": 1}


def _parse_js(p: pathlib.Path) -> dict:
    """JS 粗解析（正则）：只认 function 声明与 obj.method = function，标 exact=0。"""
    src = p.read_text(encoding="utf-8", errors="replace")
    rel = str(p.relative_to(ROOT)).replace("\\", "/")
    syms, edges = [], []
    for m in re.finditer(r"^\s*(?:async\s+)?function\s+([A-Za-z_$][\w$]*)\s*\(([^)]*)\)", src, re.M):
        line = src[: m.start()].count("\n") + 1
        syms.append({"name": m.group(1), "kind": "function", "file": rel, "line": line,
                     "signature": "%s(%s)" % (m.group(1), m.group(2).strip()), "doc": ""})
    for m in re.finditer(r"([A-Za-z_$][\w$]*)\s*\(([^)]{0,80})\)\s*[;{]", src):
        line = src[: m.start()].count("\n") + 1
        edges.append({"src": "(module)", "src_file": rel, "src_line": line,
                      "dst": m.group(1), "kind": "call", "file": rel, "line": line})
    return {"rel": rel, "symbols": syms, "edges": edges, "imports": [], "exact": 0}


def index(paths: list[str] | None = None, limit: int = 0, force: bool = False) -> dict:
    t0 = time.time()
    c = _conn()
    files_n = syms_n = edges_n = 0
    skipped = 0
    failed = []
    try:
        for p in _walk(list(paths or []), limit=limit):
            try:
                rel = str(p.relative_to(ROOT)).replace("\\", "/")
            except ValueError:
                rel = str(p)
            st = p.stat()
            row = c.execute("SELECT mtime, size FROM files WHERE path=?", (rel,)).fetchone()
            if row and not force and abs(row[0] - st.st_mtime) < 1e-6 and row[1] == st.st_size:
                skipped += 1
                continue
            try:
                rec = _parse_py(p) if p.suffix in PY_SUFFIX else _parse_js(p)
            except SyntaxError as e:
                failed.append({"file": rel, "error": "SyntaxError: %s" % str(e)[:80]})
                continue
            except Exception as e:  # noqa: BLE001
                failed.append({"file": rel, "error": "%s: %s" % (type(e).__name__, str(e)[:80])})
                continue
            c.execute("DELETE FROM symbols WHERE file=?", (rel,))
            c.execute("DELETE FROM edges WHERE src_file=?", (rel,))
            c.execute("DELETE FROM symbols_fts WHERE rowid IN (SELECT id FROM symbols WHERE file=?)", (rel,))
            for s in rec["symbols"]:
                cur = c.execute(
                    "INSERT INTO symbols(name,kind,file,line,signature,doc,exact) VALUES(?,?,?,?,?,?,?)",
                    (s["name"], s["kind"], s["file"], s["line"], s["signature"], s["doc"], rec["exact"]))
                c.execute("INSERT INTO symbols_fts(rowid,name,signature,doc) VALUES(?,?,?,?)",
                          (cur.lastrowid, s["name"], s["signature"], s["doc"]))
            for e in rec["edges"]:
                c.execute("INSERT INTO edges(src,src_file,src_line,dst,kind,file,line) VALUES(?,?,?,?,?,?,?)",
                          (e["src"], e["src_file"], e["src_line"], e["dst"], e["kind"], e["file"], e["line"]))
            for im in rec["imports"]:
                c.execute("INSERT INTO edges(src,src_file,src_line,dst,kind,file,line) VALUES(?,?,?,?,?,?,?)",
                          ("(module)", rel, im["line"], im["dst"], "import", rel, im["line"]))
            c.execute("INSERT OR REPLACE INTO files(path,lang,mtime,size,sha,exact,at) VALUES(?,?,?,?,?,?,?)",
                      (rel, "py" if p.suffix in PY_SUFFIX else "js", st.st_mtime, st.st_size,
                       _sha(p), rec["exact"], time.strftime("%Y-%m-%dT%H:%M:%S")))
            files_n += 1
            syms_n += len(rec["symbols"])
            edges_n += len(rec["edges"]) + len(rec["imports"])
        c.commit()
        tot = {k: c.execute("SELECT COUNT(*) FROM %s" % k).fetchone()[0]
               for k in ("files", "symbols", "edges")}
    finally:
        c.close()
    return {"ok": True, "op": "index", "db": str(DB),
            "本次": {"files": files_n, "symbols": syms_n, "edges": edges_n,
                     "skipped_unchanged": skipped},
            "全库": tot, "未解析": failed[:20], "未解析数": len(failed),
            "s": round(time.time() - t0, 1)}


def find(q: str = "", limit: int = 20) -> dict:
    q = str(q or "").strip()
    if not q:
        return {"ok": False, "error": "需要 q（名字片段）"}
    c = _conn()
    try:
        rows = c.execute(
            "SELECT name,kind,file,line,signature,exact FROM symbols WHERE name LIKE ? "
            "ORDER BY CASE WHEN name=? THEN 0 ELSE 1 END, length(name) LIMIT ?",
            ("%" + q + "%", q, int(limit))).fetchall()
        if not rows:
            try:
                rows = c.execute(
                    "SELECT s.name,s.kind,s.file,s.line,s.signature,s.exact FROM symbols_fts f "
                    "JOIN symbols s ON s.id=f.rowid WHERE symbols_fts MATCH ? LIMIT ?",
                    (q, int(limit))).fetchall()
            except Exception:  # noqa: BLE001
                rows = []
    finally:
        c.close()
    return {"ok": True, "op": "find", "q": q, "count": len(rows),
            "hits": [{"name": r[0], "kind": r[1], "file": r[2], "line": r[3],
                      "signature": r[4], "exact": bool(r[5])} for r in rows]}


def callers(name: str = "", limit: int = 30) -> dict:
    name = str(name or "").strip()
    if not name:
        return {"ok": False, "error": "需要 name"}
    c = _conn()
    try:
        rows = c.execute("SELECT DISTINCT src, src_file, src_line, line FROM edges "
                         "WHERE dst=? AND kind='call' ORDER BY src_file, line LIMIT ?",
                         (name, int(limit))).fetchall()
    finally:
        c.close()
    return {"ok": True, "op": "callers", "name": name, "count": len(rows),
            "callers": [{"caller": r[0], "file": r[1], "caller_line": r[2], "line": r[3]}
                        for r in rows]}


def callees(name: str = "", limit: int = 50) -> dict:
    name = str(name or "").strip()
    if not name:
        return {"ok": False, "error": "需要 name"}
    c = _conn()
    try:
        rows = c.execute("SELECT DISTINCT dst, file, line FROM edges "
                         "WHERE src=? AND kind='call' ORDER BY line LIMIT ?",
                         (name, int(limit))).fetchall()
    finally:
        c.close()
    return {"ok": True, "op": "callees", "name": name, "count": len(rows),
            "callees": [{"callee": r[0], "file": r[1], "line": r[2]} for r in rows]}


def summary(path: str = "") -> dict:
    pref = str(path or "").strip().strip("/")
    c = _conn()
    try:
        like = pref + "%" if pref else "%"
        files = c.execute("SELECT COUNT(*) FROM files WHERE path LIKE ?", (like,)).fetchone()[0]
        syms = c.execute("SELECT COUNT(*) FROM symbols WHERE file LIKE ?", (like,)).fetchone()[0]
        edges = c.execute("SELECT COUNT(*) FROM edges WHERE src_file LIKE ?", (like,)).fetchone()[0]
        top = c.execute("SELECT file, COUNT(*) n FROM symbols WHERE file LIKE ? "
                        "GROUP BY file ORDER BY n DESC LIMIT 10", (like,)).fetchall()
    finally:
        c.close()
    return {"ok": True, "op": "summary", "path": pref or "(全库)",
            "files": files, "symbols": syms, "edges": edges,
            "symbols_per_file_top": [{"file": r[0], "symbols": r[1]} for r in top]}


def stats() -> dict:
    c = _conn()
    try:
        files = c.execute("SELECT COUNT(*) FROM files").fetchone()[0]
        syms = c.execute("SELECT COUNT(*) FROM symbols").fetchone()[0]
        edges = c.execute("SELECT COUNT(*) FROM edges").fetchone()[0]
        exact = c.execute("SELECT COUNT(*) FROM files WHERE exact=1").fetchone()[0]
        last = c.execute("SELECT at FROM files ORDER BY at DESC LIMIT 1").fetchone()
    finally:
        c.close()
    return {"ok": True, "op": "stats", "db": str(DB), "files": files, "symbols": syms,
            "edges": edges, "exact_files": exact, "coarse_files": files - exact,
            "last_index_at": last[0] if last else None,
            "口径": "exact=1 是 ast 精确解析；exact=0 是 JS 正则粗解析（如实标）"}


def run_op(op: str = "stats", **kw) -> dict:
    op = str(op or "stats").lower()
    if op == "index":
        return index(kw.get("paths") or [], limit=int(kw.get("limit") or 0),
                     force=bool(kw.get("force")))
    if op == "find":
        return find(kw.get("q") or kw.get("name") or "", limit=int(kw.get("limit") or 20))
    if op == "callers":
        return callers(kw.get("name") or kw.get("q") or "", limit=int(kw.get("limit") or 30))
    if op == "callees":
        return callees(kw.get("name") or kw.get("q") or "", limit=int(kw.get("limit") or 50))
    if op == "summary":
        return summary(kw.get("path") or "")
    if op == "stats":
        return stats()
    return {"ok": False, "error": "code_graph 不认 op=%s（index/find/callers/callees/summary/stats）" % op}
