#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""codegraph_native —— 她自己的代码图谱（吞 colbymchenry/codegraph 的方法，不搬它的代码）。

## 为什么不搬代码
上游是 Node/Rust 单文件二进制（`codegraph install` 抓对应平台构建）。
本机是 iSH/aarch64，装不了；而且搬它的代码就违背"蒸馏出契合我们的"。
**只取方法**：符号 · 边 · 文件 · FTS5，一次查询给出定义+片段+调用者。

## 上游的机制（读原文提炼，2026-10-29）
  · SQLite 知识图谱：symbols · edges · files · FTS5 全文检索
  · 预建索引，代码一变自动同步
  · "Surgical Context"：一次调用返回入口点 + 相关符号 + 代码片段
  · "Impact Analysis"：追 callers / callees / 影响半径
  · 收益（它自报）：工具调用 −88% · token −62%

## 我们这版（原生）
  · Python 用 ast 真解析：函数/类/导入/调用
  · JS/HTML 用正则抓：function、require/import、常见调用
  · 存 symbols / edges / files 三张表 + FTS5
  · query(name) → 定义 + 片段 + 调用者 + 被调者
  · impact(name) → 影响半径（向上追 callers）

## 口径
  · 只读源码，不改一个字节
  · 解析不到的如实标（`unparsed`），不假装全索引
  · **不猜语义**：边只认能静态看到的（import / 调用名）
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

ROOT = pathlib.Path(__file__).resolve().parents[1]
DB = ROOT / "gbt_allinone" / "store" / "codegraph" / "graph.sqlite3"

SKIP_DIRS = {"__pycache__", "node_modules", ".git", "_archive", "_upstream",
             "third_party", ".venv-sadtalker", "probe_store"}
PY_EXT = {".py"}
JS_EXT = {".js", ".mjs"}
HTML_EXT = {".html", ".htm"}


def _conn():
    DB.parent.mkdir(parents=True, exist_ok=True)
    c = sqlite3.connect(str(DB))
    try:                                      # iSH：WAL 跨进程不可见，用 DELETE
        c.execute("PRAGMA journal_mode=DELETE")
    except sqlite3.OperationalError:
        pass
    c.execute("CREATE TABLE IF NOT EXISTS files (path TEXT PRIMARY KEY, lang TEXT, bytes INT, "
              "sha TEXT, mtime REAL, symbols INT, edges INT, note TEXT)")
    c.execute("CREATE TABLE IF NOT EXISTS symbols (id INTEGER PRIMARY KEY, name TEXT, kind TEXT, "
              "file TEXT, line INT, sig TEXT, doc TEXT)")
    c.execute("CREATE TABLE IF NOT EXISTS edges (src TEXT, dst TEXT, kind TEXT, file TEXT, line INT)")
    try:
        c.execute("CREATE VIRTUAL TABLE IF NOT EXISTS sym_fts USING fts5(name, doc, tokenize='unicode61')")
    except sqlite3.OperationalError:
        pass
    return c


def _walk():
    for dirpath, dirnames, filenames in os.walk(ROOT):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS and not d.startswith(".")]
        for fn in filenames:
            ext = pathlib.Path(fn).suffix.lower()
            if ext in PY_EXT or ext in JS_EXT or ext in HTML_EXT:
                yield pathlib.Path(dirpath) / fn


def _py_syms(rel: str, src: str, out_s, out_e):
    try:
        tree = ast.parse(src)
    except SyntaxError as exc:
        return "syntax_error: %s" % exc.msg
    calls = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            args = ", ".join(a.arg for a in node.args.args[:6])
            out_s.append((node.name, "function", rel, node.lineno, "(%s)" % args,
                          (ast.get_docstring(node) or "")[:200]))
            for c in ast.walk(node):
                if isinstance(c, ast.Call):
                    f = c.func
                    nm = getattr(f, "id", None) or getattr(f, "attr", None)
                    if nm:
                        calls.append((node.name, nm, "call", rel, getattr(c, "lineno", node.lineno)))
        elif isinstance(node, ast.ClassDef):
            out_s.append((node.name, "class", rel, node.lineno, "", (ast.get_docstring(node) or "")[:200]))
        elif isinstance(node, ast.Import):
            for a in node.names:
                out_e.append(("<file>", a.name, "import", rel, node.lineno))
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                out_e.append(("<file>", node.module, "import", rel, node.lineno))
    out_e.extend(calls)
    return ""


JS_FN = re.compile(r"(?:function\s+([A-Za-z_$][\w$]*)|(?:const|let|var)\s+([A-Za-z_$][\w$]*)\s*=\s*(?:async\s*)?(?:function|\())")
JS_REQ = re.compile(r"(?:require\(|from\s+)['\"]([^'\"]+)['\"]")


def _js_syms(rel: str, src: str, out_s, out_e):
    for m in JS_FN.finditer(src):
        name = m.group(1) or m.group(2)
        line = src[:m.start()].count("\n") + 1
        out_s.append((name, "function", rel, line, "", ""))
    for m in JS_REQ.finditer(src):
        line = src[:m.start()].count("\n") + 1
        out_e.append(("<file>", m.group(1), "import", rel, line))
    return ""


def build(limit: int = 0) -> dict:
    c = _conn()
    c.execute("DELETE FROM files"); c.execute("DELETE FROM symbols")
    c.execute("DELETE FROM edges"); c.execute("DELETE FROM sym_fts")
    n_files = n_sym = n_edge = 0
    unparsed = []
    files = list(_walk())
    if limit:
        files = files[:limit]
    for f in files:
        try:
            src = f.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        rel = str(f.relative_to(ROOT))
        ext = f.suffix.lower()
        s, e = [], []
        note = ""
        if ext in PY_EXT:
            note = _py_syms(rel, src, s, e) or ""
        elif ext in JS_EXT or ext in HTML_EXT:
            note = _js_syms(rel, src, s, e) or ""
        if note:
            unparsed.append({"file": rel, "why": note})
        lang = "py" if ext in PY_EXT else ("js" if ext in JS_EXT else "html")
        c.execute("insert or replace into files (path,lang,bytes,sha,mtime,symbols,edges,note) "
                  "values (?,?,?,?,?,?,?,?)",
                  (rel, lang, len(src.encode("utf-8")),
                   hashlib.sha1(src.encode("utf-8")).hexdigest()[:16], f.stat().st_mtime,
                   len(s), len(e), note))
        for row in s:
            cur = c.execute("insert into symbols (name,kind,file,line,sig,doc) values (?,?,?,?,?,?)", row)
            c.execute("insert into sym_fts (rowid,name,doc) values (?,?,?)",
                      (cur.lastrowid, row[0], row[5] or ""))
        for row in e:
            c.execute("insert into edges (src,dst,kind,file,line) values (?,?,?,?,?)", row)
        n_files += 1; n_sym += len(s); n_edge += len(e)
    c.commit(); c.close()
    return {"ok": True, "files": n_files, "symbols": n_sym, "edges": n_edge,
            "unparsed": len(unparsed), "unparsed_sample": unparsed[:5],
            "db": str(DB.relative_to(ROOT))}


def query(name: str, limit: int = 6) -> dict:
    """一次查询：符号定义 + 代码片段 + 调用者 + 被调者。"""
    c = _conn()
    rows = []
    try:
        rows = c.execute(
            "select s.name,s.kind,s.file,s.line,s.sig,s.doc from sym_fts f "
            "join symbols s on s.id=f.rowid where sym_fts match ? order by rank limit ?",
            (name, limit)).fetchall()
    except sqlite3.OperationalError:
        pass
    if not rows:
        rows = c.execute("select name,kind,file,line,sig,doc from symbols where name like ? "
                         "limit ?", ("%" + name + "%", limit)).fetchall()
    if not rows:
        rows = c.execute("select name,kind,file,line,sig,doc from symbols "
                         "where file like ? limit ?", ("%" + name + "%", limit)).fetchall()
    out = []
    for nm, kind, f, line, sig, doc in rows:
        snippet = ""
        fp = ROOT / f
        if fp.is_file():
            try:
                ls = fp.read_text(encoding="utf-8", errors="replace").split("\n")
                snippet = "\n".join(ls[max(0, line - 1): line + 7])
            except OSError:
                pass
        callers = [r[0] for r in c.execute(
            "select distinct src from edges where dst=? limit 8", (nm,)).fetchall()]
        callees = [r[0] for r in c.execute(
            "select distinct dst from edges where src=? and kind!='import' limit 12",
            (nm,)).fetchall()]
        out.append({"name": nm, "kind": kind, "file": f, "line": line, "sig": sig,
                    "doc": (doc or "")[:160], "callers": callers, "callees": callees,
                    "snippet": snippet})
    c.close()
    return {"ok": bool(out), "query": name, "count": len(out), "hits": out}


def impact(name: str, depth: int = 3) -> dict:
    """影响半径：向上追谁调它（改动前该看谁）。"""
    c = _conn()
    seen, frontier, layers = {name}, {name}, []
    for _ in range(depth):
        nxt = set()
        for n in frontier:
            for r in c.execute("select distinct src from edges where dst=?", (n,)).fetchall():
                if r[0] not in seen and r[0] != "<file>":
                    nxt.add(r[0])
        if not nxt:
            break
        layers.append(sorted(nxt))
        seen |= nxt
        frontier = nxt
    c.close()
    return {"ok": True, "symbol": name, "radius": len(seen) - 1, "layers": layers}


def stats() -> dict:
    c = _conn()
    f = c.execute("select count(*) from files").fetchone()[0]
    s = c.execute("select count(*) from symbols").fetchone()[0]
    e = c.execute("select count(*) from edges").fetchone()[0]
    by = c.execute("select lang,count(*) from files group by lang").fetchall()
    bad = c.execute("select count(*) from files where note!=''").fetchone()[0]
    c.close()
    return {"files": f, "symbols": s, "edges": e,
            "by_lang": {a: b for a, b in by}, "unparsed_files": bad,
            "db": str(DB.relative_to(ROOT)) if DB.is_file() else None}


def main() -> int:
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--build", action="store_true")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--query", default="")
    ap.add_argument("--impact", default="")
    ap.add_argument("--stats", action="store_true")
    a = ap.parse_args()
    if a.build:
        print(json.dumps(build(a.limit), ensure_ascii=False, indent=1))
        print(json.dumps(stats(), ensure_ascii=False, indent=1))
        return 0
    if a.stats:
        print(json.dumps(stats(), ensure_ascii=False, indent=1)); return 0
    if a.query:
        print(json.dumps(query(a.query), ensure_ascii=False, indent=1)); return 0
    if a.impact:
        print(json.dumps(impact(a.impact), ensure_ascii=False, indent=1)); return 0
    ap.print_help(); return 0


if __name__ == "__main__":
    raise SystemExit(main())
