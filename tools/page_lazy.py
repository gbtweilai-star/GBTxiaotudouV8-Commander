# -*- coding: utf-8 -*-
"""按需激活 · 分片索引（内存随答案走，不随语料走）

  建：manifest.json（很小，只有名字→分片映射）+ shards/<hash>.json（每页一片）
  查：只读 manifest + 命中的那几片 ⇒ 最小运行内存
  量：每次查询报「读了几个字节 / 峰值 RSS」

  与 page_bind.py 的关系：那个是整包索引（快但吃内存），本件是分片版（省内存）。
  ���可以并存：整包给批量分析用，分片给"每次运行按需激活"用。

用法：
  python3 tools/page_lazy.py build
  python3 tools/page_lazy.py query <词> [--hops 1]
  python3 tools/page_lazy.py bench          # 对比整包 vs 分片的内存占用
"""
from __future__ import annotations
import json, os, re, sys, time, hashlib, resource
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "state" / "bind"
SHARDS = BASE / "shards"
MANIFEST = BASE / "manifest.json"
ANCHOR = "anchor:scope_root"

SKIP_DIRS = {".git", "node_modules", "__pycache__", ".venv", "build", "dist", "assets", "state", "store"}
CODE_EXT = {".py", ".js", ".mjs", ".ts", ".tsx", ".jsx", ".html", ".css", ".json",
            ".toml", ".yml", ".yaml", ".md", ".sh", ".cff", ".xml", ".txt", ".webmanifest"}
MAX_BYTES = 900_000

RE_IMPORT = re.compile(r"""(?:from\s+([\w\.]+)\s+import|import\s+([\w\.]+)|require\(['"]([^'"]+)['"]\))""")
RE_DEF = re.compile(r"""^\s*(?:def|class|function|const|let)\s+([A-Za-z_]\w+)""", re.M)
RE_WORD = re.compile(r"[A-Za-z_][A-Za-z0-9_\-]{2,}")


def rss_mb() -> float:
    """iSH 上 /proc/self/status 不可读，getrusage 返回 0；用 statm 拿常驻页数。"""
    try:
        with open("/proc/self/statm", encoding="utf-8") as f:
            pages = int(f.read().split()[1])
        return pages * (os.sysconf("SC_PAGE_SIZE") if hasattr(os, "sysconf") else 4096) / 1048576.0
    except Exception:
        pass
    try:
        return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024.0
    except Exception:
        return 0.0


def scan():
    out = []
    for dp, dns, fns in os.walk(ROOT):
        dns[:] = [d for d in dns if d not in SKIP_DIRS]
        for fn in fns:
            p = Path(dp) / fn
            if p.suffix.lower() not in CODE_EXT:
                continue
            try:
                if p.stat().st_size <= MAX_BYTES:
                    out.append(p)
            except OSError:
                pass
    return sorted(out)


def pid_of(p: Path) -> str:
    return str(p.relative_to(ROOT)).replace(os.sep, "/")


def feats(p: Path):
    try:
        txt = p.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return [], set()
    imports = [g.replace(".", "/").split("/")[-1].lower()
               for m in RE_IMPORT.finditer(txt) for g in m.groups() if g]
    words = set(w.lower() for w in RE_WORD.findall(txt))
    words.add(p.stem.lower())
    return RE_DEF.findall(txt)[:120], set(imports) | words


def build():
    t0 = time.time()
    pages = [pid_of(p) for p in scan()]
    fmap = {}
    for p in scan():
        fmap[pid_of(p)] = feats(p)

    # 名字 → 页
    name2 = {}
    for pid in pages:
        name2.setdefault(Path(pid).stem.lower(), []).append(pid)
        name2.setdefault(Path(pid).name.lower(), []).append(pid)

    adj = {pid: set() for pid in pages}
    for pid, (_defs, words) in fmap.items():
        for w in words:
            for other in name2.get(w, ()):
                if other != pid:
                    adj[pid].add(other)
                    adj[other].add(pid)         # 双向
    for pid in pages:
        adj[pid].add(ANCHOR)
    adj[ANCHOR] = set(pages)

    SHARDS.mkdir(parents=True, exist_ok=True)
    for old in SHARDS.glob("*.json"):
        old.unlink()
    shard_of = {}
    for pid in pages:
        h = hashlib.blake2b(pid.encode(), digest_size=8).hexdigest()
        shard_of[pid] = h + ".json"
        (SHARDS / (h + ".json")).write_text(json.dumps({
            "id": pid, "neighbors": sorted(adj[pid]), "defs": fmap[pid][0],
        }, ensure_ascii=False), encoding="utf-8")

    # 🔴 2026-10-24 内存瘦身（主人：「内存和算力都要花在刀刃上」）：
    #    实测 manifest 400,513 B 里 name2 占 54%、shard_of 占 28% —— 而这两样
    #    **都完全可推导**（shard 名 = blake2b(页名)[:16]+".json"；name2 由 pages 现算）。
    #    存进盘再每次全量读回内存 = 把钱花在刀背上 ⇒ 只存 pages。
    MANIFEST.write_text(json.dumps({
        "built_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "anchor": ANCHOR, "count": len(pages), "pages": pages,
    }, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    return {"pages": len(pages), "ms": round((time.time() - t0) * 1000, 1),
            "manifest_kb": round(MANIFEST.stat().st_size / 1024, 1),
            "shards": len(shard_of)}


def shard_name(pid: str) -> str:
    return hashlib.blake2b(pid.encode(), digest_size=8).hexdigest() + ".json"


def load_manifest(need_names: bool = False) -> dict:
    """读瘦身后的 manifest，**按需**推导 shard_of / name2。
       need_names=False ⇒ 不建 name2（省下最大那块的构建时间与内存）。"""
    d = json.loads(MANIFEST.read_text(encoding="utf-8"))
    pages = d.get("pages") or []
    d["shard_of"] = {p: shard_name(p) for p in pages}      # 现算，O(n) 但只算名字
    if need_names:
        n2 = {}
        for pid in pages:
            n2.setdefault(Path(pid).stem.lower(), []).append(pid)
            n2.setdefault(Path(pid).name.lower(), []).append(pid)
        d["name2"] = n2
    else:
        d["name2"] = {}
    return d


def query(q: str, hops: int = 1):
    t0 = time.time()
    read = [0]
    man = load_manifest(need_names=True)
    read[0] += MANIFEST.stat().st_size
    ql = q.lower()

    seeds = [p for p in man["pages"] if ql in p.lower()]
    for name, pids in man["name2"].items():
        if ql in name:
            seeds += pids
    seeds = list(dict.fromkeys(seeds))[:8]

    loaded, out = set(), []
    frontier = list(seeds)
    for depth in range(hops + 1):
        nxt = []
        for pid in frontier:
            if pid in loaded or pid not in man["shard_of"]:
                continue
            f = SHARDS / man["shard_of"][pid]
            if not f.is_file():
                continue
            d = json.loads(f.read_text(encoding="utf-8"))
            read[0] += f.stat().st_size
            loaded.add(pid)
            out.append((pid, depth, len(d.get("neighbors", []))))
            nxt += d.get("neighbors", [])
        frontier = nxt
        if not frontier:
            break
    ms = (time.time() - t0) * 1000
    return {"hits": out, "ms": round(ms, 2), "bytes_read": read[0],
            "shards_loaded": len(loaded), "total_shards": man["count"]}


def cmd_build():
    r = build()
    print("  页数        : %d" % r["pages"])
    print("  分片数      : %d" % r["shards"])
    print("  manifest    : %.1f KB" % r["manifest_kb"])
    print("  建索引耗时  : %.1f ms" % r["ms"])


def cmd_query(q, hops=1):
    r = query(q, hops)
    print("  命中 %d 页 · %.2f ms" % (len(r["hits"]), r["ms"]))
    for pid, d, deg in r["hits"][:10]:
        print("    [%d跳] %-52s 度=%d" % (d, pid, deg))
    print("  ── 按需激活读数 ──")
    print("    读了 %d 字节（%.1f KB）· 只加载 %d/%d 片（%.1f%%）"
          % (r["bytes_read"], r["bytes_read"] / 1024, r["shards_loaded"],
             r["total_shards"], 100.0 * r["shards_loaded"] / max(1, r["total_shards"])))
    print("    峰值 RSS: %.1f MB" % rss_mb())


def cmd_bench():
    full = ROOT / "state" / "page_bind.json"
    print("  ── 整包索引（page_bind.py）──")
    if full.is_file():
        print("    文件大小: %.1f KB" % (full.stat().st_size / 1024))
        t = time.time(); d = json.loads(full.read_text(encoding="utf-8"))
        print("    载入耗时: %.1f ms · 常驻峰值 RSS: %.1f MB" % ((time.time() - t) * 1000, rss_mb()))
        del d
    print("  ── 分片索引（本件）──")
    r = query("route", 1)
    print("    读入: %.1f KB（%.1f%% of 全量）· 耗时 %.2f ms · 峰值 RSS %.1f MB"
          % (r["bytes_read"] / 1024,
             100.0 * r["bytes_read"] / max(1, full.stat().st_size if full.is_file() else 1),
             r["ms"], rss_mb()))


if __name__ == "__main__":
    a = sys.argv[1:] or ["build"]
    if a[0] == "build":
        cmd_build()
    elif a[0] == "query":
        h = 1
        if "--hops" in a:
            h = int(a[a.index("--hops") + 1]); a = [x for x in a if x != "--hops" and x != str(h)]
        cmd_query(" ".join(a[1:]), h)
    elif a[0] == "bench":
        cmd_bench()
    else:
        cmd_query(" ".join(a), 1)
