# -*- coding: utf-8 -*-
"""全盘索引 · 扫一次，之后全靠查（主人的「全量自捡 · 秒级响应」）

  口径（先说清，免得被念歪）：
    · 扫全盘在本机实测 51 秒（44,269 文件 / 866 文件/秒）—— 不是"几秒"。
    · 但快的不该是"扫"，是"查"：付一次 51 秒，之后每次命中都是毫秒。
    · 本件只记 path/size/mtime，**不读文件内容**（这才能 51 秒扫完）。
      要内容级检索再用 page_lazy.py 的分片索引。

用法：
  python3 tools/disk_index.py build      # 扫一次，落 state/disk_index.json(.gz)
  python3 tools/disk_index.py find <词>  # 按路径/文件名瞬时查
  python3 tools/disk_index.py big [N]    # 最大的 N 个文件
  python3 tools/disk_index.py stats      # 读数
"""
from __future__ import annotations
import gzip, json, os, sys, time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "state" / "disk_index.json.gz"
SKIP = {"proc", "sys", "dev", "run"}


def scan(base="/"):
    t0 = time.time()
    rows, dirs = [], 0
    for dp, dns, fns in os.walk(base, topdown=True):
        rel = dp.lstrip("/").split("/")[0]
        if rel in SKIP:
            dns[:] = []
            continue
        dirs += 1
        for fn in fns:
            p = os.path.join(dp, fn)
            try:
                st = os.lstat(p)
            except OSError:
                continue
            rows.append((p, st.st_size, int(st.st_mtime)))
    return rows, dirs, (time.time() - t0) * 1000


def build():
    rows, dirs, ms = scan("/")
    t1 = time.time()
    data = {"built_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "files": len(rows), "dirs": dirs, "scan_ms": round(ms, 0),
            "rows": rows}
    raw = json.dumps(data, ensure_ascii=False, separators=(",", ":")).encode()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(OUT, "wb", compresslevel=6) as f:
        f.write(raw)
    return {"files": len(rows), "dirs": dirs, "scan_s": round(ms / 1000, 2),
            "write_ms": round((time.time() - t1) * 1000, 0),
            "index_kb": round(OUT.stat().st_size / 1024, 1),
            "raw_kb": round(len(raw) / 1024, 1)}


def load():
    if not OUT.is_file():
        print("  还没建索引：python3 tools/disk_index.py build"); sys.exit(2)
    t0 = time.time()
    with gzip.open(OUT, "rb") as f:
        d = json.loads(f.read())
    d["_load_ms"] = (time.time() - t0) * 1000
    return d


def cmd_build():
    r = build()
    print("  文件: %d · 目录: %d" % (r["files"], r["dirs"]))
    print("  扫描: %.2f 秒" % r["scan_s"])
    print("  写盘: %.0f ms · 索引 %.1f KB（原始 %.1f KB，gzip 压缩）"
          % (r["write_ms"], r["index_kb"], r["raw_kb"]))


def cmd_find(q):
    d = load()
    ql = q.lower()
    t0 = time.time()
    hits = [(p, s, m) for p, s, m in d["rows"] if ql in p.lower()]
    ms = (time.time() - t0) * 1000
    hits.sort(key=lambda x: -x[1])
    print("  命中 %d 个（索引载入 %.0f ms + 查找 %.2f ms）"
          % (len(hits), d["_load_ms"], ms))
    for p, s, m in hits[:12]:
        print("    %9.1f KB  %s" % (s / 1024, p))


def cmd_big(n=10):
    d = load()
    rows = sorted(d["rows"], key=lambda x: -x[1])[:int(n)]
    print("  最大的 %d 个文件:" % len(rows))
    for p, s, m in rows:
        print("    %9.1f MB  %s" % (s / 1048576, p))


def cmd_stats():
    d = load()
    tot = sum(r[1] for r in d["rows"])
    print("  建于      : %s" % d["built_at"])
    print("  文件/目录 : %d / %d" % (d["files"], d["dirs"]))
    print("  总字节    : %.2f GB" % (tot / 1073741824))
    print("  扫全盘耗时: %.2f 秒（只付一次）" % (d["scan_ms"] / 1000))
    print("  载入索引  : %.0f ms（每次查询的固定成本）" % d["_load_ms"])


if __name__ == "__main__":
    a = sys.argv[1:] or ["stats"]
    {"build": cmd_build, "stats": cmd_stats}.get(
        a[0], lambda: cmd_find(" ".join(a[1:])) if a[0] == "find"
        else (cmd_big(a[1] if len(a) > 1 else 10) if a[0] == "big" else cmd_find(" ".join(a))))()
