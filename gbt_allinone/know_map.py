# -*- coding: utf-8 -*-
# gbt-capability: filesystem_write  ⬻ 开发者：自由的风 · GBT小土豆V8 · 永久钢印
"""理解任何事（know_map）—— 蒸馏自 GitHub Trending #1 「Understand Anything」

它的骨架（现读截图）：**1-SCAN → 2-MAP → 3-TEACH**，四个能力：
  Guided Tours（引导导览）· Semantic Search（语义检索）· Diff Impact（变更影响）· Layer View（分层视图）
它的一句话：「**We do not just map your code. We teach it.**」

它的灵魂：**把任何仓/库/文档变成一张可点、可搜、可问的分层知识图**。
不是“给你一个目录树”，而是“给你一条**从入口开始的学习路线**”。

吾们的适配（不重造，复用已有的）：
  · 结构层  = 目录/文件/模块（自己走盘，零作用域）
  · 逻辑层  = 入口/导入关系（逐行看 import，带 path:line 证据）
  · 知识层  = 文档/胶囊/规则（对接 store/devoured + context_vault）
  · 共现网  = `topic_web`（已在役）· 知识门 = `self_intake`（已在役）

铁律：① 每个节点/边必须能指回**路径**（或 path:line）；② 空目标不算成功；
      ③ 取不到就写「未读到」，不编节点不编边；④ `ask` 是**词面**检索，不冒充语义。

op：status / layers / tour / ask / impact（只读）· scan / build（build 写）
"""
from __future__ import annotations

import json
import re
import time
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MAPS = ROOT / "state" / "know_map"
READ_OPS = ("status", "layers", "tour", "ask", "impact")
WRITE_OPS = ("scan", "build")
CODE_EXT = {".py", ".js", ".ts", ".mjs", ".cjs", ".jsx", ".tsx", ".json", ".ps1", ".cmd", ".bat",
            ".html", ".css", ".md", ".yml", ".yaml", ".toml", ".sql", ".sh"}
DOC_EXT = {".md", ".txt", ".rst"}
ENTRY_NAMES = ("main.py", "app.py", "run.py", "index.html", "start.ps1", "start.cmd", "__main__.py")
SKIP_DIRS = {".git", "__pycache__", "node_modules", ".venv", "venv", "dist", "build", ".mypy_cache",
             ".pytest_cache", ".ruff_cache", "site-packages", ".pylibs", "vendor", "third_party",
             "_upstream", ".cache"}


def _slug(target: str) -> str:
    s = re.sub(r"[^0-9A-Za-z\u4e00-\u9fff]+", "-", str(target or "root"))
    return s.strip("-")[:60] or "root"


def scan(target: str = ".", max_files: int = 20000) -> dict:
    """第 1 步 SCAN（只读）：走盘 + 分类 + 找入口。空目标不算成功。"""
    root = Path(target)
    if not root.exists():
        return {"ok": False, "reason": "target_not_found", "target": str(root)}
    files, dirs, by_ext, entry, docs, code = 0, 0, Counter(), [], [], []
    total_bytes = 0
    skipped = []
    truncated = False
    for p in sorted(root.rglob("*")):
        if files >= int(max_files):
            truncated = True
            break
        if any(part in SKIP_DIRS for part in p.parts):
            continue
        if p.is_dir():
            dirs += 1
            continue
        if not p.is_file():
            continue
        ext = p.suffix.lower()
        if ext not in CODE_EXT and ext != "":
            skipped.append(str(p))
            continue
        files += 1
        by_ext[ext or "(\u65e0后缀)"] += 1
        try:
            total_bytes += p.stat().st_size
        except OSError:
            pass
        rel = str(p.relative_to(root)).replace(chr(92), "/")
        if p.name in ENTRY_NAMES:
            entry.append(rel)
        if ext in DOC_EXT:
            docs.append(rel)
        elif ext in (".py", ".js", ".ts", ".mjs", ".jsx", ".tsx"):
            code.append(rel)
    if files == 0:
        return {"ok": False, "reason": "empty_target", "target": str(root),
                "detail": "目标里一个可读文件都没有 ⇒ 不算成功（不编数）"}
    return {"ok": True, "op": "scan", "target": str(root), "files": files, "dirs": dirs,
            "bytes": total_bytes, "entrypoints": entry[:20], "docs": docs[:40],
            "code_files": code[:60], "by_ext": dict(by_ext.most_common(12)),
            "skipped_non_code": len(skipped), "truncated": truncated,
            "note": "只统计能认的扩展名；其余如实计入 skipped_non_code"}


def _imports_of(path: Path, root: Path) -> list:
    """逐行看 import（先拆行，不用反斜杠正则）→ [( 目标相对路径, path:line )]。

    实测踩过（2026-10-15）：旧版把 `from . import x` 拼成 `root/ + ".py"`\uff0c
    结果**所有相对导入都指向 `__init__.py`** —— 边指错了比没边更坏。
    现在：相对导入先算所在包（点数 - 1 层），**解不开就不建边**（不编），且不自环。
    """
    out = []
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return out
    pat = re.compile(r"^(from|import) +(\.+[A-Za-z0-9_.]*|[A-Za-z0-9_.]+)")
    try:
        pkg = path.parent.relative_to(root)
    except ValueError:
        pkg = Path("")
    me = str(path.relative_to(root)).replace(chr(92), "/") if path != root else ""
    for i, line in enumerate(lines[:4000], 1):
        m = pat.match(line.strip())
        if not m:
            continue
        spec = m.group(2)
        if spec.startswith("."):
            dots = len(spec) - len(spec.lstrip("."))
            rest = spec.lstrip(".")
            here = pkg
            for _ in range(max(0, dots - 1)):
                here = here.parent
            mod = rest.split(".")[0] if rest else ""
            if mod:
                cands = [root / here / (mod + ".py"), root / here / mod / "__init__.py"]
            else:
                cands = [root / here / "__init__.py"]
        else:
            mod = spec.split(".")[0]
            cands = [root / (mod + ".py"), root / mod / "__init__.py"]
        for cand in cands:
            if not cand.is_file():
                continue
            try:
                rel = str(cand.relative_to(root)).replace(chr(92), "/")
            except ValueError:
                continue
            if rel != me:
                out.append((rel, "%s:%d" % (me, i)))
            break
    return out

def _mentions(doc: Path, root: Path, basenames: dict) -> list:
    """文档里提到了哪些在役文件→ [( 目标路径, doc:line )]。"""
    out, seen = [], set()
    try:
        lines = doc.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return out
    for i, line in enumerate(lines[:3000], 1):
        for tok in re.findall(r"[A-Za-z0-9_.]+", line):
            tgt = basenames.get(tok)
            if tgt and (tgt, i) not in seen:
                seen.add((tgt, i))
                out.append((tgt, "%s:%d" % (str(doc).replace(chr(92), "/"), i)))
    return out[:200]


def build(target: str = ".", slug: str = "", max_files: int = 20000) -> dict:
    """第 2 步 MAP（写盘）：三层图（结构 / 逻辑 / 知识），**每条边带证据**。"""
    s = scan(target, max_files)
    if not s.get("ok"):
        return s
    root = Path(s["target"])
    nodes, dirs_seen = [], set()
    for rel in s["code_files"] + s["docs"]:
        parts = rel.split("/")
        for k in range(1, len(parts)):
            d = "/".join(parts[:k])
            if d and d not in dirs_seen:
                dirs_seen.add(d)
                nodes.append({"id": d, "layer": "结构", "kind": "dir", "evidence": d})
        p = root / rel
        ext = p.suffix.lower()
        layer = "知识" if ext in DOC_EXT else "结构"
        nodes.append({"id": rel, "layer": layer, "kind": "doc" if layer == "知识" else "file",
                      "evidence": rel, "bytes": p.stat().st_size if p.is_file() else 0})
    basenames = {}
    for _rel in s["code_files"]:
        basenames[Path(_rel).name] = _rel
    edges, imp_n, men_n = [], 0, 0
    for rel in s["code_files"]:
        if not rel.endswith(".py"):
            continue
        for tgt, ev in _imports_of(root / rel, root):
            edges.append({"a": rel, "b": tgt, "rel": "导入", "evidence": ev})
            imp_n += 1
    for rel in s["docs"]:
        for tgt, ev in _mentions(root / rel, root, basenames):
            edges.append({"a": rel, "b": tgt, "rel": "提及", "evidence": ev})
            men_n += 1
    by_layer = Counter(n["layer"] for n in nodes)
    graph = {"at": time.strftime("%Y-%m-%dT%H:%M:%S"), "target": s["target"], "slug": _slug(slug or s["target"]),
             "scan": {k: s[k] for k in ("files", "dirs", "bytes", "entrypoints", "by_ext", "truncated", "skipped_non_code")},
             "nodes": nodes[:4000], "edges": edges[:6000],
             "counts": {"nodes": len(nodes), "edges": len(edges), "导入边": imp_n, "提及边": men_n},
             "layers": dict(by_layer), "partial": bool(s["truncated"]),
             "honest": "每条边都带 evidence（路径 或 path:line）；读不到的不建节点"}
    if len(nodes) == 0:
        return {"ok": False, "reason": "no_nodes", "target": s["target"]}
    MAPS.mkdir(parents=True, exist_ok=True)
    out = MAPS / (graph["slug"] + ".json")
    out.write_text(json.dumps(graph, ensure_ascii=False, indent=1), encoding="utf-8")
    layers = {}
    for n in nodes:
        layers.setdefault(n["layer"], 0)
        layers[n["layer"]] += 1
    return {"ok": True, "op": "build", "map": str(out), "slug": graph["slug"],
            "nodes": len(graph["nodes"]), "edges": len(graph["edges"]), "layers": layers,
            "partial": bool(s["truncated"]),
            "entrypoints": s["entrypoints"], "scan_files": s["files"],
            "top_edges": [{"a": e["a"], "b": e["b"], "rel": e["rel"], "evidence": e["evidence"]}
                          for e in edges[:5]]}


def _load(slug: str = "") -> dict:
    if not MAPS.is_dir():
        return {}
    if slug:
        f = MAPS / (_slug(slug) + ".json")
        if not f.is_file():
            hit = [x for x in sorted(MAPS.glob("*.json")) if _slug(slug) in x.stem]
            f = hit[0] if hit else f
    else:
        files = sorted(MAPS.glob("*.json"), key=lambda x: x.stat().st_mtime, reverse=True)
        f = files[0] if files else Path("")
    try:
        return json.loads(f.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def status() -> dict:
    if not MAPS.is_dir():
        return {"ok": False, "reason": "no_maps", "dir": str(MAPS),
                "detail": "还没建过图 ⇒ 先跑 build"}
    rows = []
    for f in sorted(MAPS.glob("*.json"), key=lambda x: x.stat().st_mtime, reverse=True):
        try:
            g = json.loads(f.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        rows.append({"slug": g.get("slug"), "target": g.get("target"), "at": g.get("at"),
                     "nodes": g.get("counts", {}).get("nodes"), "edges": g.get("counts", {}).get("edges"),
                     "layers": g.get("layers")})
    return {"ok": bool(rows), "op": "status", "maps": rows[:12], "count": len(rows),
            "reason": None if rows else "no_maps"}


def layers(slug: str = "") -> dict:
    g = _load(slug)
    if not g:
        return {"ok": False, "reason": "no_map"}
    deg = Counter()
    for e in g.get("edges") or []:
        deg[e["a"]] += 1
        deg[e["b"]] += 1
    out = {}
    for n in g.get("nodes") or []:
        out.setdefault(n["layer"], []).append((deg.get(n["id"], 0), n["id"]))
    view = {}
    for k, v in out.items():
        v.sort(reverse=True)
        view[k] = {"count": len(v), "top": [{"id": i, "degree": d} for d, i in v[:8]]}
    return {"ok": True, "op": "layers", "slug": g.get("slug"), "target": g.get("target"),
            "layers": view,
            "honest": "层只分 结构/知识 两类；逻辑边在 edges 里（带 path:line）"}


def tour(slug: str = "", limit: int = 12) -> dict:
    g = _load(slug)
    if not g:
        return {"ok": False, "reason": "no_map"}
    steps = []
    entry = (g.get("scan") or {}).get("entrypoints") or []
    if entry:
        steps.append({"step": 1, "title": "从入口进来", "why": "这些是启动位",
                      "evidence": entry[:5]})
    if not entry:
        deg0 = Counter()
        for _e in g.get("edges") or []:
            deg0[_e["a"]] += 1
            deg0[_e["b"]] += 1
        top0 = [i for i, _d in deg0.most_common(5)]
        if top0:
            steps.append({"step": 1, "title": "从最被依赖的那个开始",
                          "why": "没有显式入口 ⇒ 按被引用次数排序（不编入口）",
                          "evidence": top0})
    near = [e for e in (g.get("edges") or []) if e["a"] in entry and e["rel"] == "导入"]
    if near:
        steps.append({"step": len(steps) + 1, "title": "入口引入了谁",
                      "why": "逻辑层第一层依赖",
                      "evidence": [e["evidence"] for e in near[:6]]})
    docs = [e for e in (g.get("edges") or []) if e["rel"] == "提及"]
    if docs:
        steps.append({"step": len(steps) + 1, "title": "文档里是怎么说的",
                      "why": "知识层对应",
                      "evidence": [e["evidence"] for e in docs[:6]]})
    for lay, info in (layers(slug).get("layers") or {}).items():
        steps.append({"step": len(steps) + 1, "title": "看一眼 %s 层" % lay,
                      "why": "共 %d 个节点" % info["count"],
                      "evidence": [t["id"] for t in info["top"][:5]]})
        if len(steps) >= int(limit):
            break
    return {"ok": bool(steps), "op": "tour", "slug": g.get("slug"), "target": g.get("target"),
            "steps": steps[:int(limit)], "reason": None if steps else "no_steps"}


def ask(slug: str = "", query: str = "", limit: int = 8) -> dict:
    g = _load(slug)
    if not g:
        return {"ok": False, "reason": "no_map"}
    q = str(query or "").strip().lower()
    if not q:
        return {"ok": False, "reason": "need_query"}
    toks = [x for x in re.split("[^0-9A-Za-z]+", q) if len(x) >= 2]
    hits = []
    for n in g.get("nodes") or []:
        low = str(n["id"]).lower()
        score = sum(1 for t in toks if t in low)
        if score:
            hits.append({"what": n["id"], "layer": n["layer"], "score": score,
                         "evidence": n.get("evidence")})
    for e in g.get("edges") or []:
        blob = (str(e["a"]) + " " + str(e["b"]) + " " + str(e.get("evidence"))).lower()
        score = sum(1 for t in toks if t in blob)
        if score:
            hits.append({"what": "%s --%s--> %s" % (e["a"], e["rel"], e["b"]), "layer": "逻辑",
                         "score": score, "evidence": e.get("evidence")})
    hits.sort(key=lambda x: -x["score"])
    vault = {}
    try:
        from .tools.context_vault import VaultStore
        vault = VaultStore().search(" ".join(toks), budget_bytes=0, max_items=5)
    except Exception:
        vault = {}
    return {"ok": True, "op": "ask", "slug": g.get("slug"), "query": query,
            "hits": hits[:max(1, int(limit))], "hit_count": len(hits),
            "vault": [{"source_ref": h.get("source_ref"), "score": h.get("score")}
                      for h in (vault.get("hits") or [])][:5],
            "honest": "这是**词面**检索（不冒充语义）；条条能指回 evidence"}


def impact(slug: str = "", changed=None, limit: int = 12) -> dict:
    g = _load(slug)
    if not g:
        return {"ok": False, "reason": "no_map"}
    if isinstance(changed, str):
        changed = [x.strip() for x in changed.replace(";", ",").split(",") if x.strip()]
    changed = [str(x).replace(chr(92), "/") for x in (changed or [])]
    if not changed:
        return {"ok": False, "reason": "need_changed", "detail": "给一个或几个变动路径"}
    hit_ids, out = set(), []
    for c in changed:
        for n in g.get("nodes") or []:
            if n["id"] == c or n["id"].endswith("/" + c.rsplit("/", 1)[-1]):
                hit_ids.add(n["id"])
    for e in g.get("edges") or []:
        if e["a"] in hit_ids or e["b"] in hit_ids:
            out.append({"a": e["a"], "b": e["b"], "rel": e["rel"], "evidence": e["evidence"]})
    return {"ok": True, "op": "impact", "slug": g.get("slug"), "changed": changed,
            "matched_nodes": sorted(hit_ids)[:20], "affected": out[:max(1, int(limit))],
            "affected_count": len(out),
            "honest": "只算图里有证据的那些连接；图外说不了就不说"}


def run(op: str = "status", **kw) -> dict:
    o = (op or "status").strip().lower()
    if o == "status":
        return status()
    if o == "scan":
        return scan(kw.get("target") or ".", int(kw.get("max_files", 20000) or 20000))
    if o == "build":
        return build(kw.get("target") or ".", kw.get("slug") or "", int(kw.get("max_files", 20000) or 20000))
    if o == "layers":
        return layers(kw.get("slug") or "")
    if o == "tour":
        return tour(kw.get("slug") or "", int(kw.get("limit", 12) or 12))
    if o == "ask":
        return ask(kw.get("slug") or "", kw.get("query") or "", int(kw.get("limit", 8) or 8))
    if o == "impact":
        return impact(kw.get("slug") or "", kw.get("changed"), int(kw.get("limit", 12) or 12))
    return {"ok": False, "reason": "unknown_op", "op": o, "known": list(READ_OPS) + list(WRITE_OPS),
            "detail": "未知 op 只回错（fail-closed）"}


