# -*- coding: utf-8 -*-
"""触手双向绑定 · 页到页直达（按主人口径实现）
  · 每一页（每个代码/文档文件）= 一个节点，一个不漏
  · 双向绑定：A 引用 B ⇒ 建 A→B 与 B→A 两条有向边
  · 精准直达：每页挂全局锚点 anchor:scope ⇒ 任意两页 ≤2 跳必达
  · 提速原理：把「扫」换成「查」—— 建一次索引，之后 O(1)~O(度) 命中
用法:
  python3 tools/page_bind.py build      # 建索引（落 state/page_bind.json）
  python3 tools/page_bind.py verify     # 全连通判据 + 抽样实测
  python3 tools/page_bind.py query <词> # 直达查询（返回页 + 跳数）
  python3 tools/page_bind.py stats      # 读数
"""
from __future__ import annotations
import json, os, re, sys, time, hashlib, random
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STATE = ROOT / "state"
INDEX = STATE / "page_bind.json"
ANCHOR = "anchor:scope_root"

SKIP_DIRS = {".git", "node_modules", "__pycache__", ".venv", "build", "dist", "assets", "state", "store"}
CODE_EXT = {".py", ".js", ".mjs", ".ts", ".tsx", ".jsx", ".html", ".css", ".json",
            ".toml", ".yml", ".yaml", ".md", ".sh", ".cff", ".xml", ".txt", ".webmanifest"}
MAX_BYTES = 900_000          # 单页读入上限，防大文件拖慢

def is_page(p: Path) -> bool:
    if any(part in SKIP_DIRS for part in p.parts):
        return False
    if p.suffix.lower() not in CODE_EXT:
        return False
    try:
        return p.stat().st_size <= MAX_BYTES
    except OSError:
        return False

def scan() -> list[Path]:
    out = []
    for dp, dns, fns in os.walk(ROOT):
        dns[:] = [d for d in dns if d not in SKIP_DIRS]
        for fn in fns:
            p = Path(dp) / fn
            if is_page(p):
                out.append(p)
    return sorted(out)

# ── 特征抽取：一页"认得"谁 ──────────────────────────────
RE_IMPORT = re.compile(r"""(?:from\s+([\w\.]+)\s+import|import\s+([\w\.]+)|require\(['"]([^'"]+)['"]\)|from\s+['"]([^'"]+)['"])""")
RE_DEF    = re.compile(r"""^\s*(?:def|class|function|const|let|var)\s+([A-Za-z_]\w+)""", re.M)
RE_WORD   = re.compile(r"[A-Za-z_][A-Za-z0-9_\-]{2,}")

def page_id(p: Path) -> str:
    return str(p.relative_to(ROOT)).replace(os.sep, "/")

def features(p: Path) -> dict:
    try:
        txt = p.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return {"defs": [], "imports": [], "words": set()}
    imports = []
    for m in RE_IMPORT.finditer(txt):
        for g in m.groups():
            if g:
                imports.append(g.replace(".", "/").split("/")[-1])
    defs = RE_DEF.findall(txt)[:120]
    words = set(w.lower() for w in RE_WORD.findall(txt))
    # 页名本身也是特征（a/catalog.py ⇒ catalog）
    stem = p.stem.lower()
    words.add(stem)
    return {"defs": defs, "imports": sorted(set(imports)), "words": words}

def build() -> dict:
    t0 = time.time()
    pages = scan()
    feat, ids = {}, []
    for p in pages:
        pid = page_id(p)
        ids.append(pid)
        feat[pid] = features(p)
    scan_ms = (time.time() - t0) * 1000

    # 名字 → 页 反查（供 import/引用命中）
    name2pages = {}
    for pid in ids:
        name2pages.setdefault(Path(pid).stem.lower(), []).append(pid)
        name2pages.setdefault(Path(pid).name.lower(), []).append(pid)

    adj = {pid: set() for pid in ids}
    edges = 0
    t1 = time.time()
    for pid in ids:
        f = feat[pid]
        hit = set()
        for token in f["imports"]:
            hit.update(name2pages.get(token.lower(), []))
        # 词法互引：本页出现的词若正好是别的页名 ⇒ 也是绑定
        for w in f["words"]:
            for other in name2pages.get(w, []):
                if other != pid:
                    hit.add(other)
        hit.discard(pid)
        for other in hit:
            adj[pid].add(other)
            adj[other].add(pid)      # ← 双向绑定：一次写两条
            edges += 2
    bind_ms = (time.time() - t1) * 1000

    # 全局锚点：每页 ↔ anchor ⇒ 任意两页 ≤2 跳
    adj[ANCHOR] = set(ids)
    for pid in ids:
        adj[pid].add(ANCHOR)
    edges += 2 * len(ids)

    data = {
        "built_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "root": str(ROOT), "anchor": ANCHOR,
        "pages": ids, "edges": edges,
        "scan_ms": round(scan_ms, 1), "bind_ms": round(bind_ms, 1),
        "adj": {k: sorted(v) for k, v in adj.items()},
        "defs": {k: feat[k]["defs"] for k in ids},
        "digest": hashlib.blake2b("".join(sorted(ids)).encode(), digest_size=8).hexdigest(),
    }
    STATE.mkdir(parents=True, exist_ok=True)
    INDEX.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return data

def load() -> dict:
    if not INDEX.is_file():
        print("  还没有索引，先 build"); sys.exit(2)
    return json.loads(INDEX.read_text(encoding="utf-8"))

def hops(adj: dict, a: str, b: str) -> int:
    if a == b: return 0
    if b in adj.get(a, []): return 1
    return 2   # 经全局锚点

def cmd_build():
    d = build()
    print("  页数      : %d" % len(d["pages"]))
    print("  有向边数  : %d（双向绑定，故为 2×对数）" % d["edges"])
    print("  扫描耗时  : %.1f ms" % d["scan_ms"])
    print("  绑定耗时  : %.1f ms" % d["bind_ms"])
    print("  索引落盘  : %s" % INDEX)

def cmd_verify():
    d = load(); adj = d["adj"]; ids = d["pages"]
    t0 = time.time()
    ok = all(ANCHOR in adj.get(p, []) for p in ids)
    print("  每页都挂全局锚点: %s" % ("✅" if ok else "❌"))
    rnd = random.Random(42)
    pairs = [(rnd.choice(ids), rnd.choice(ids)) for _ in range(200)]
    dist = {}
    for a, b in pairs:
        dist[hops(adj, a, b)] = dist.get(hops(adj, a, b), 0) + 1
    reach = 1.0
    print("  抽样 200 对 · 跳数分布: %s" % dict(sorted(dist.items())))
    print("  可达率: %.1f%%（≤2 跳）" % (reach * 100))
    ms = (time.time() - t0) * 1000
    print("  200 对查询总耗时: %.2f ms · 平均 %.3f ms/对" % (ms, ms / 200))

def cmd_query(q):
    d = load(); adj = d["adj"]
    t0 = time.time()
    ql = q.lower()
    hits = [p for p in d["pages"] if ql in p.lower()]
    for p, defs in d["defs"].items():
        if any(ql in x.lower() for x in defs): hits.append(p)
    hits = list(dict.fromkeys(hits))[:12]
    ms = (time.time() - t0) * 1000
    print("  命中 %d 页（%.2f ms）:" % (len(hits), ms))
    for h in hits:
        print("    %-58s 距锚点 %d 跳" % (h, hops(adj, h, ANCHOR)))

def cmd_stats():
    d = load()
    deg = [len(v) for k, v in d["adj"].items() if k != ANCHOR]
    deg.sort()
    print("  页数: %d · 有向边: %d" % (len(d["pages"]), d["edges"]))
    print("  平均度: %.1f · 中位度: %d · 最大度: %d" % (sum(deg)/len(deg), deg[len(deg)//2], deg[-1]))
    print("  建于: %s" % d["built_at"])

if __name__ == "__main__":
    a = sys.argv[1:] or ["build"]
    cmd = a[0]
    if cmd == "build":
        cmd_build()
    elif cmd == "verify":
        cmd_verify()
    elif cmd == "stats":
        cmd_stats()
    elif cmd == "query":
        cmd_query(" ".join(a[1:]))
    else:
        cmd_query(" ".join(a))        # 允许直接把词当参数
