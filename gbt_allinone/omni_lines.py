# -*- coding: utf-8 -*-
"""万能插 · 关联线路监控（2026-11-02，主人令：能力不能丢）

口径：「修一个地方，就把这个地方关联的所有线路用触手监控起来，有任何变化第一时间发现。」

做什么：
  1. 扫代码/页面/路由/资产，建**依赖图**：
     py import ↔ 模块文件；html script/link/iframe ↔ 文件；js import()/fetch(/api/…) ↔ 路由；
     loader.load(../assets/…) ↔ 资产；console-server 的 if path == "/api/…" ↔ 路由节点；
  2. 图里每个文件都进监控表（mtime+size），state/omni-lines.json **持久化**图谱与监控根；
  3. 每次采样对比：谁变了 ⇒ 立刻算出它的**关联闭包**（BFS 所有上下游线路），
     把本轮的「变了 → 连带 n 条线路」写进台账，页面/接口第一时间可见；
  4. 能力写进文件，不依赖某次对话：重启后图谱还在，监控继续。
"""
from __future__ import annotations

import json
import re
import time
from collections import deque
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STATE = ROOT / "state"
GRAPH_FILE = STATE / "omni-lines.json"
LOCKF = STATE / ".omni-lines.lock"
CACHE = {"graph": None, "at": 0.0, "stats": {}, "last": {}}
MAX_HISTORY = 120

# 只盯运行路径上的线路；tools/codex-scripts 那种一次性脚本不进图（否则 4000+ 噪音）
CODE_DIRS = ["gbt_allinone", "desktop", "holo_pet_w3/console", "holo_pet_w3/dh-live"]
TOOL_WHITELIST = {"tools/console-server.py", "tools/weights.py"}
STATIC_EXT = {".py", ".js", ".mjs", ".html", ".css", ".json", ".glb"}


def _iter_files():
    out = []
    for d in CODE_DIRS:
        base = ROOT / d
        if not base.is_dir():
            continue
        for p in base.rglob("*"):
            if not p.is_file():
                continue
            if p.suffix.lower() not in STATIC_EXT:
                continue
            if ".git" in p.parts or "__pycache__" in p.parts:
                continue
            if p.stat().st_size > 12 * 1024 * 1024:
                continue
            out.append(p)
    # 额外关键文件
    for rel in tuple(TOOL_WHITELIST) + ("desktop/package.json",):
        p = ROOT / rel
        if p.is_file() and p not in out:
            out.append(p)
    return out


def _rel(p: Path) -> str:
    try:
        return p.resolve().relative_to(ROOT).as_posix()
    except Exception:  # noqa: BLE001
        return str(p)


def _py_imports(text: str, file_rel: str = ""):
    """返回 (绝对导入, 相对导入[(dots, module, names)])。"""
    abs_names = set()
    rel_names = []
    for m in re.finditer(r"(?m)^\s*from\s+([\.\w]+)\s+import\s+([^\n]+)", text):
        mod = m.group(1)
        imps = [x.strip().split(" as ")[0].strip() for x in m.group(2).split(",")]
        if mod.startswith("."):
            rel_names.append((len(mod) - len(mod.lstrip(".")), mod.lstrip("."), imps))
        else:
            abs_names.add(mod)
            for x in imps:
                if x and x != "*":
                    abs_names.add(mod + "." + x)
    for m in re.finditer(r"(?m)^\s*import\s+([^\n]+)", text):
        for x in m.group(1).split(","):
            nm = x.strip().split(" as ")[0].strip()
            if re.match(r"^[A-Za-z_][\w\.]*$", nm):
                abs_names.add(nm)
    return abs_names, rel_names


def _js_refs(text: str):
    refs = set()
    for m in re.finditer(r"""(?:src|href)\s*=\s*["']([^"']+)["']""", text):
        refs.add(("file", m.group(1)))
    for m in re.finditer(r"""import\s*\(\s*["']([^"']+)["']\s*\)""", text):
        refs.add(("file", m.group(1)))
    for m in re.finditer(r"""(?:load|fetch|post)\s*\(\s*["']([^"']+)["']""", text):
        refs.add(("file", m.group(1)))
    for m in re.finditer(r"""/api/[A-Za-z0-9_\-/]+""", text):
        refs.add(("route", m.group(0)))
    # 前端资源相对路径（loader.load("../voice-theater/assets/x.glb")）
    for m in re.finditer(r"""["'](.\.?/[^"']+\.(?:glb|png|jpg|jpeg|webp|css|js))["']""", text):
        refs.add(("file", m.group(1)))
    return refs


def _server_routes(text: str):
    return sorted(set(re.findall(r"""if\s+path\s*==\s*["'](/api/[^"']+)["']""", text)))


def _resolve(base: Path, ref: str) -> Path | None:
    ref = ref.split("?")[0].split("#")[0]
    if ref.startswith(("http://", "https://", "data:", "javascript:")):
        return None
    cand = (base.parent / ref).resolve()
    return cand if cand.is_file() else None


def build_graph() -> dict:
    files = _iter_files()
    rels = {_rel(p): p for p in files}
    by_name = {}
    for r in rels:
        by_name.setdefault(Path(r).name, []).append(r)
    nodes = {}
    edges = set()

    def node(name: str, kind: str, meta=None):
        nodes[name] = {"kind": kind, **(meta or {})}
        return name

    for r, p in rels.items():
        kind = "py" if p.suffix == ".py" else ("js" if p.suffix in (".js", ".mjs") else
                                              ("html" if p.suffix == ".html" else "asset"))
        node(r, kind)
        try:
            text = p.read_text(encoding="utf-8", errors="replace")
        except Exception:  # noqa: BLE001
            continue
        refs = set()
        if p.suffix == ".py":
            abs_names, rel_names = _py_imports(text, r)
            for imp in abs_names:
                parts = imp.split(".")
                for i in range(len(parts), 0, -1):
                    tail = "/".join(parts[:i]) + ".py"
                    for cand in (ROOT / tail, ROOT / "gbt_allinone" / tail, ROOT / "tools" / tail):
                        if cand.is_file():
                            refs.add(("file", _rel(cand)))
                            break
                else:
                    leaf = parts[-1] + ".py"
                    for cand in by_name.get(leaf, [])[:2]:
                        refs.add(("file", cand))
            # 相对导入：from . import x / from .x import y
            pkg = Path(r).parent.as_posix()
            for dots, mod, imps in rel_names:
                base = pkg
                for _ in range(max(0, dots - 1)):
                    base = str(Path(base).parent.as_posix())
                cands = []
                if mod:
                    cands.append(base + "/" + mod.replace(".", "/") + ".py")
                for nm in imps:
                    if nm and nm != "*":
                        cands.append(base + "/" + (mod.replace(".", "/") + "/" if mod else "") + nm + ".py")
                for c in cands:
                    if (ROOT / c).is_file():
                        refs.add(("file", c))
                    else:
                        leaf = Path(c).name
                        for cc in by_name.get(leaf, [])[:2]:
                            refs.add(("file", cc))
        if p.suffix in (".js", ".html"):
            for typ, ref in _js_refs(text):
                if typ == "route":
                    rid = "route:" + ref
                    if rid not in nodes:
                        node(rid, "route")
                    edges.add((r, rid))
                else:
                    tgt = _resolve(p, ref)
                    if tgt is not None:
                        tr = _rel(tgt)
                        if tr in rels:
                            edges.add((r, tr))
        # 把 py import 解析出的文件真正接到图上（之前只收集没连边）
        for typ, ref in refs:
            if typ == "file" and ref in rels:
                edges.add((r, ref))
        if p.suffix == ".py" and p.name == "console-server.py":
            for route in _server_routes(text):
                rid = "route:" + route
                if rid not in nodes:
                    node(rid, "route")
                edges.add((r, rid))
    # 无向邻接
    adj = {n: set() for n in nodes}
    for a, b in edges:
        if a in adj and b in adj:
            adj[a].add(b)
            adj[b].add(a)
    return {"built_at": time.time(), "nodes": nodes, "edges": sorted([list(e) for e in edges]),
            "adj": {k: sorted(v) for k, v in adj.items()},
            "roots": sorted([r for r in nodes if nodes[r]["kind"] in ("py", "js", "html")])}


def _load_saved():
    try:
        return json.loads(GRAPH_FILE.read_text(encoding="utf-8")).get("graph")
    except Exception:  # noqa: BLE001
        return None


def _save(graph: dict):
    try:
        STATE.mkdir(parents=True, exist_ok=True)
        old = {}
        if GRAPH_FILE.is_file():
            try:
                old = json.loads(GRAPH_FILE.read_text(encoding="utf-8"))
            except Exception:  # noqa: BLE001
                old = {}
        old.update({"saved_at": time.time(), "graph": graph,
                    "note": "关联线路监控台账：修一处→自动监控所有关联线路（2026-11-02 主人令，不得丢）"})
        GRAPH_FILE.write_text(json.dumps(old, ensure_ascii=False), encoding="utf-8")
    except Exception:  # noqa: BLE001
        pass


def _stat(p: Path) -> dict:
    try:
        st = p.stat()
        return {"mtime": round(st.st_mtime, 3), "size": st.st_size}
    except Exception:  # noqa: BLE001
        return {"mtime": 0, "size": 0}


def _closure(adj: dict, start: str, limit: int = 400) -> list:
    if start not in adj:
        return []
    seen = {start}
    q = deque([start])
    out = []
    while q and len(seen) < limit:
        cur = q.popleft()
        for nb in adj.get(cur, []):
            if nb in seen:
                continue
            seen.add(nb)
            out.append(nb)
            q.append(nb)
    return out


def ensure_graph(force: bool = False) -> dict:
    g = CACHE.get("graph")
    if g is None:
        g = _load_saved()
        CACHE["graph"] = g
    age = time.time() - CACHE.get("at", 0)
    if force or g is None or age > 120:
        g = build_graph()
        CACHE["graph"] = g
        CACHE["at"] = time.time()
        _save(g)
        CACHE["stats"] = {}
    return g


def _watch_files(graph: dict) -> list:
    out = []
    critical = {
        "tools/console-server.py", "desktop/main.js", "holo_pet_w3/console/app.js",
        "holo_pet_w3/console/index.html", "holo_pet_w3/console/skin-cube.css",
        "holo_pet_w3/console/omni-monitor.js", "holo_pet_w3/dh-live/dh-live.js",
        "holo_pet_w3/dh-live/index.html", "gbt_allinone/omni_plug.py",
        "gbt_allinone/omni_monitor.py", "gbt_allinone/omni_lines.py",
        "gbt_allinone/dh_tentacle.py", "gbt_allinone/dh_omni_loop.py",
        "gbt_allinone/voice_cap.py", "gbt_allinone/security/policy.py",
    }
    hot = set()
    for a, b in graph["edges"]:
        for x in (a, b):
            if graph["nodes"].get(x, {}).get("kind") in ("py", "js", "html"):
                hot.add(x)
    for n in list(critical | hot):
        p = ROOT / n
        if p.is_file():
            out.append((n, p))
    for extra in ("state/app-settings.json", "state/asset_bindings.json",
                  "state/moments.json", "state/hd/rerig/dh-tentacle-rerig.glb"):
        p = ROOT / extra
        if p.is_file():
            out.append((extra, p))
    return out


def sample(force_graph: bool = False) -> dict:
    g = ensure_graph(force=force_graph)
    prev = CACHE.get("stats") or {}
    cur = {}
    changed = []
    for name, p in _watch_files(g):
        cur[name] = _stat(p)
        if name in prev and cur[name] != prev[name]:
            rel = _closure(g["adj"], name)
            changed.append({"path": name, "from": prev[name], "to": cur[name],
                            "related_count": len(rel), "related": rel[:20]})
    CACHE["stats"] = cur
    now = time.time()
    out = {"watched": len(cur), "edges": len(g["edges"]), "nodes": len(g["nodes"]),
           "routes": sum(1 for k in g["nodes"] if g["nodes"][k]["kind"] == "route"),
           "changed": changed, "at": round(now, 3),
           "history": len(CACHE.get("last", {}).get("events", []))}
    if changed:
        old = _load_saved() or {}
        evs = old.get("events") or []
        evs.extend({"at": out["at"], "changed": changed})
        out["history"] = len(evs)
        old["events"] = evs[-MAX_HISTORY:]
        old["saved_at"] = now
        try:
            GRAPH_FILE.write_text(json.dumps(old, ensure_ascii=False), encoding="utf-8")
        except Exception:  # noqa: BLE001
            pass
    CACHE["last"] = {"events": (_load_saved() or {}).get("events") or []}
    return out


def info() -> dict:
    g = ensure_graph()
    st = sample()
    return {"ok": True, "graph": {"nodes": st["nodes"], "edges": st["edges"],
                                  "routes": st["routes"], "watched": st["watched"],
                                  "built_at": g.get("built_at")},
            "changed": st["changed"], "history": st["history"],
            "graph_file": str(GRAPH_FILE),
            "note": "修一处 → 自动把关联线路全部监控（闭包算法），变化进台账；能力已持久化"}
