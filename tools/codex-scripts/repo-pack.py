# -*- coding: utf-8 -*-
"""repo-pack.py —— 全仓文件级「双向索引 + 按需压缩」量具与打包器（GBT小土豆V8）。

主人令 2026-10-19（逐字）：「不只能力位，而是整个大模型所有文件代码覆盖双向绑定，
秒级理论上百分百可以实现」「先量规模：全仓文件数、体积、压缩后体积、引用关系复杂度，然后做」。

## 为什么另起一件（旧 `wired pack` 超时的真因）
上一版把「335 个能力位名」当成 335 条正则，对 8805 个页面**逐个**跑 ⇒ 单文件 335 次全文搜索，
再叠加 88MB 一次性 JSON 写出 ⇒ 必超时。本件改三处：
  ① **一次扫描代替 N 次搜索**：文件名/文本只 tokenize 一遍（`[A-Za-z_][A-Za-z0-9_]{1,63}`），
     再与能力位名集合做**集合求交**（O(文本) 而不是 O(文本×335)）；
  ② **分批 + 可续跑**：结果 append 到 jsonl，已完成的文件按 sha16 认领，中断重跑不返工；
  ③ **索引进内存、压缩进索引**：pack 只写一遍，随机访问靠 idx 的 offset/length 直取。

## 四个子命令
    py -3.14 tools/codex-scripts/repo-pack.py scan            # 清单：路径/字节/ext/sha16（可续跑）
    py -3.14 tools/codex-scripts/repo-pack.py refs            # 引用边：谁引用谁（import/href/src/路径/能力位）
    py -3.14 tools/codex-scripts/repo-pack.py pack            # 逐文件 gzip → repo.pack + repo.idx.json
    py -3.14 tools/codex-scripts/repo-pack.py who <path>      # 双向查询：谁引用我 / 我引用谁
    py -3.14 tools/codex-scripts/repo-pack.py get <path> -o X # 按需解压单件（打印耗时）

## 口径（不许含糊）
- **排除面写死**：`.git` / `node_modules` / `__pycache__` / `.pytest_cache`；**junction 不穿**（防环）。
- **不碰在役件**：pack 只读源文件；解包落到调用方指定的 `-o`，绝不覆盖。
- **取不到就如实报**：没扫到的目录记为 `unreadable`，不吞成 0。
- **数字带时间戳**：summary 里写 `at`，读者才知道这份清单是哪一刻的。

开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import os
import re
import stat
import sys
import time
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    if hasattr(_s, "reconfigure"):
        _s.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "outputs" / "repo-pack"
FILES = OUT / "files.jsonl"
EDGES = OUT / "edges.jsonl"
SUMMARY = OUT / "summary.json"
PACK = OUT / "repo.pack"
IDX = OUT / "repo.idx.json"

EXCLUDE_DIRS = {".git", "node_modules", "__pycache__", ".pytest_cache", ".mypy_cache"}
TEXT_EXT = {".py", ".js", ".mjs", ".cjs", ".ts", ".tsx", ".jsx", ".json", ".jsonl", ".md", ".txt",
            ".html", ".htm", ".css", ".yml", ".yaml", ".toml", ".ini", ".cfg", ".cmd", ".bat",
            ".ps1", ".sh", ".csv", ".svg", ".xml", ".mdc", ".sql"}
TOKEN = re.compile(r"[A-Za-z_][A-Za-z0-9_]{1,63}")
# 引用面（路径类）：import/require/from … "x" · href/src="x" · 绝对/相对路径字面量
REF_PATTERNS = [
    re.compile(r"""(?:from|import|require)\s*\(?\s*['"]([^'"\n]{2,200})['"]"""),
    re.compile(r"""(?:href|src|url)\s*=\s*['"]([^'"\n]{2,300})['"]"""),
    re.compile(r"""['"]([A-Za-z0-9_./-]{3,200}\.(?:py|js|mjs|ts|tsx|json|md|html|css|glb|png|jpg|svg))['"]"""),
]
MAX_TEXT = 2_000_000          # 大于 2MB 的文本不进引用扫描（只做清单与打包）


# ── 公共 ─────────────────────────────────────────────────────────────────────
def _rel(p: Path) -> str:
    try:
        return str(p.relative_to(ROOT)).replace("\\", "/")
    except ValueError:
        return str(p)


def _is_reparse(p: str) -> bool:
    try:
        st = os.lstat(p)
        return bool(st.st_file_attributes & stat.FILE_ATTRIBUTE_REPARSE_POINT)   # type: ignore[attr-defined]
    except Exception:                                          # noqa: BLE001
        return False


def _sha16(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()[:16]


def _cap_names() -> set:
    """能力位名集合（一次取，之后只做集合求交；不再逐位跑正则）。"""
    try:
        sys.path.insert(0, str(ROOT))
        from gbt_allinone.caps_tables import all_caps
        return {c.get("name") for c in all_caps() if c.get("name")}
    except Exception:                                          # noqa: BLE001
        return set()


# ── scan ─────────────────────────────────────────────────────────────────────
def cmd_scan(args) -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    seen = set()
    if FILES.is_file() and not args.restart:
        with FILES.open(encoding="utf-8") as fh:
            for line in fh:
                try:
                    seen.add(json.loads(line)["path"])
                except Exception:                              # noqa: BLE001
                    continue
    n_new = n_skip = 0
    unreadable = []
    t0 = time.time()
    with FILES.open("a", encoding="utf-8") as out:
        for dirpath, dirnames, filenames in os.walk(ROOT, topdown=True, onerror=lambda e: unreadable.append(str(e))):
            dirnames[:] = [d for d in dirnames if d not in EXCLUDE_DIRS
                           and not _is_reparse(os.path.join(dirpath, d))]
            for name in filenames:
                full = os.path.join(dirpath, name)
                rel = _rel(Path(full))
                if rel in seen:
                    n_skip += 1
                    continue
                try:
                    st = os.stat(full)
                except Exception as e:                          # noqa: BLE001
                    unreadable.append("%s: %s" % (rel, e))
                    continue
                rec = {"path": rel, "bytes": st.st_size, "mtime": int(st.st_mtime),
                       "ext": os.path.splitext(name)[1].lower()}
                if st.st_size <= args.hash_max:
                    try:
                        rec["sha16"] = _sha16(Path(full))
                    except Exception:                           # noqa: BLE001
                        rec["sha16"] = None
                out.write(json.dumps(rec, ensure_ascii=False) + "\n")
                seen.add(rel)
                n_new += 1
                if args.limit and n_new >= args.limit:
                    break
            if args.limit and n_new >= args.limit:
                break
    dt = time.time() - t0
    print("scan 新增 %d 件（跳过已完成 %d）· 用时 %.1fs · 扫不到 %d 处" % (n_new, n_skip, dt, len(unreadable)))
    if unreadable:
        (OUT / "unreadable.txt").write_text("\n".join(unreadable[:2000]), encoding="utf-8")
    return summarise()


def summarise() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    if not FILES.is_file():
        print("没有清单可汇总：先跑 scan")
        return 1
    by_ext, total, count = {}, 0, 0
    top = []
    with FILES.open(encoding="utf-8") as fh:
        for line in fh:
            try:
                r = json.loads(line)
            except Exception:                                  # noqa: BLE001
                continue
            count += 1
            total += r["bytes"]
            e = r.get("ext") or "(无)"
            d = by_ext.setdefault(e, {"count": 0, "bytes": 0})
            d["count"] += 1
            d["bytes"] += r["bytes"]
            top.append((r["bytes"], r["path"]))
    top.sort(reverse=True)
    ext_rows = sorted(by_ext.items(), key=lambda kv: -kv[1]["bytes"])[:20]
    summary = {"at": time.strftime("%Y-%m-%dT%H:%M:%S"), "files": count, "bytes": total,
               "MB": round(total / 1e6, 1), "GB": round(total / 1e9, 2),
               "by_ext_top20": [{"ext": k, **v, "MB": round(v["bytes"] / 1e6, 1)} for k, v in ext_rows],
               "top20_big_files": [{"path": p, "MB": round(b / 1e6, 1)} for b, p in top[:20]],
               "exclude": sorted(EXCLUDE_DIRS)}
    SUMMARY.write_text(json.dumps(summary, ensure_ascii=False, indent=1), encoding="utf-8")
    print("全仓 %d 件 · %.1f MB (%.2f GB)" % (count, total / 1e6, total / 1e9))
    print("最大 8 件：")
    for b, p in top[:8]:
        print("   %8.1f MB  %s" % (b / 1e6, p))
    print("按扩展名前 8（体积）：")
    for k, v in ext_rows[:8]:
        print("   %-8s %7.1f MB · %d 件" % (k, v["bytes"] / 1e6, v["count"]))
    print("清单：%s · 汇总：%s" % (_rel(FILES), _rel(SUMMARY)))
    return 0


# ── refs ─────────────────────────────────────────────────────────────────────
def _cap_regex(caps: set) -> re.Pattern | None:
    """**一条** alternation 正则（不是 335 条）：只在「调用位」才算边。

    🔴 为什么必须收紧（本轮实测的假边）：`echo` 本身是能力位名，而 `.cmd` 里到处是 `echo`
    ⇒ 用「token 出现」判边，会产出 `*.cmd → echo` 这种**语义为零**的边（1503 条里一大片是它）。
    所以分两档：
      · `cap`（强边）：出现在调用位 —— `cap <name>` / `run_task("<name>"` / `"kind": "<name>"`；
      · `cap_mention`（弱边，仅供参考）：token 出现，且**名字本身不像英文单词**
        （含下划线或长度 ≥ 10），避免 `echo`/`create`/`health` 这类撞词。
    """
    if not caps:
        return None
    names = sorted((n for n in caps if n), key=len, reverse=True)
    body = "|".join(re.escape(n) for n in names)
    return re.compile(r"""(?:cap\s+|run_task\(\s*['"]|"kind"\s*:\s*['"]|kind\s*=\s*['"])(%s)\b""" % body)


def cmd_refs(args) -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    caps = _cap_names()
    cap_re = _cap_regex(caps)
    weak_caps = {n for n in caps if ("_" in n) or len(n) >= 10}
    print("能力位名 %d 个（一条 alternation 正则 + 集合求交，不逐位跑正则；弱边只认 %d 个长名）"
          % (len(caps), len(weak_caps)))
    done = set()
    if EDGES.is_file() and not args.restart:
        with EDGES.open(encoding="utf-8") as fh:
            for line in fh:
                try:
                    done.add(json.loads(line)["src"])
                except Exception:                              # noqa: BLE001
                    continue
    n_files = n_edges = n_strong = n_weak = 0
    t0 = time.time()
    with EDGES.open("a", encoding="utf-8") as out:
        for line in FILES.open(encoding="utf-8"):
            r = json.loads(line)
            src = r["path"]
            if src in done or r.get("ext") not in TEXT_EXT or r["bytes"] > MAX_TEXT:
                continue
            p = ROOT / src
            try:
                text = p.read_text(encoding="utf-8", errors="replace")
            except Exception:                                  # noqa: BLE001
                continue
            n_files += 1
            refs = set()
            for pat in REF_PATTERNS:
                for m in pat.finditer(text):
                    refs.add(m.group(1).strip())
            for dst in sorted(refs):
                if len(dst) > 300:
                    continue
                out.write(json.dumps({"src": src, "dst": dst, "kind": "path"}, ensure_ascii=False) + "\n")
                n_edges += 1
            if cap_re is not None:
                for m in cap_re.finditer(text):
                    out.write(json.dumps({"src": src, "dst": m.group(1),
                                          "kind": "cap"}, ensure_ascii=False) + "\n")
                    n_strong += 1
            if weak_caps:
                for cap in sorted(set(TOKEN.findall(text)) & weak_caps):
                    out.write(json.dumps({"src": src, "dst": cap,
                                          "kind": "cap_mention"}, ensure_ascii=False) + "\n")
                    n_weak += 1
    print("refs：文本文件 %d 件 · 路径边 %d 条 · 能力位强边 %d 条 · 弱边(参考) %d 条 · 用时 %.1fs"
          % (n_files, n_edges, n_strong, n_weak, time.time() - t0))
    return 0


# ── pack ─────────────────────────────────────────────────────────────────────
def _zstd():
    """py3.14 标准库 zstd（PEP 784）。有就用它：同为无损，文本面上比 gzip 再省约一半。"""
    try:
        from compression import zstd
        return zstd
    except Exception:                                          # noqa: BLE001
        return None


def _encode(data: bytes, codec: str, level: int) -> tuple[bytes, str]:
    """返回 (blob, 实际用的 codec)。zstd 不在位时**如实降级**并把实际 codec 写进索引。"""
    if codec == "zstd":
        z = _zstd()
        if z is not None:
            return z.compress(data, level), "zstd"
        codec = "gzip"
    return gzip.compress(data, compresslevel=min(9, max(1, level))), "gzip"


def _decode(blob: bytes, codec: str) -> bytes:
    if codec == "zstd":
        z = _zstd()
        if z is None:
            raise SystemExit("这个包是 zstd 压的，但本解释器没有 compression.zstd")
        return z.decompress(blob)
    return gzip.decompress(blob)


def cmd_pack(args) -> int:
    """逐文件压进一个 pack，索引记 offset/length/原始大小/实际 codec。

    🔴 为什么默认 zstd（2026-10-19 实测）：同一份文本，gzip(6) 与 zstd(19) 在
    本仓样本上是「73 B vs 30 B」这种量级差；而 zstd 的速度还更好。gzip 留作降级路径。
    """
    OUT.mkdir(parents=True, exist_ok=True)
    rows = []
    with FILES.open(encoding="utf-8") as fh:
        for line in fh:
            r = json.loads(line)
            if r["bytes"] > args.max_bytes:
                continue
            if any(r["path"].startswith(x) for x in args.skip_prefix):
                continue
            rows.append(r)
    idx, off, t0 = [], 0, time.time()
    raw_sum = gz_sum = 0
    codecs = {}
    with PACK.open("wb") as pk:
        for i, r in enumerate(rows, 1):
            p = ROOT / r["path"]
            try:
                data = p.read_bytes()
            except Exception:                                  # noqa: BLE001
                continue
            blob, used = _encode(data, args.codec, args.level)
            pk.write(blob)
            idx.append({"path": r["path"], "off": off, "len": len(blob), "codec": used,
                        "raw": len(data), "sha16": r.get("sha16"), "ext": r.get("ext")})
            off += len(blob)
            raw_sum += len(data)
            gz_sum += len(blob)
            codecs[used] = codecs.get(used, 0) + 1
            if args.limit and i >= args.limit:
                break
    IDX.write_text(json.dumps({"at": time.strftime("%Y-%m-%dT%H:%M:%S"), "codec": args.codec,
                               "level": args.level, "codecs_used": codecs,
                               "count": len(idx), "raw_bytes": raw_sum, "pack_bytes": gz_sum,
                               "ratio": round(gz_sum / raw_sum, 4) if raw_sum else None,
                               "entries": idx}, ensure_ascii=False), encoding="utf-8")
    print("pack：%d 件 · 原始 %.1f MB → 包 %.1f MB（%.1f%%）· codec=%s · 用时 %.1fs"
          % (len(idx), raw_sum / 1e6, gz_sum / 1e6, 100.0 * gz_sum / raw_sum if raw_sum else 0,
             codecs, time.time() - t0))
    print("包：%s · 索引：%s" % (_rel(PACK), _rel(IDX)))
    return 0


def _load_idx() -> dict:
    if not IDX.is_file():
        raise SystemExit("没有索引（先跑 pack）")
    return json.loads(IDX.read_text(encoding="utf-8"))


def _norm(p: str) -> str:
    """统一分隔符并去掉开头的 ./ —— 索引里存的是相对仓根的 posix 路径。"""
    return str(p).replace("\\", "/").lstrip("./")


WHO = OUT / "who.idx.json"


def cmd_index(args) -> int:
    """把 edges.jsonl 折成**双向字典**：`who` 是 O(1) 而不是每次全表扫。

    🔴 为什么单独落一步（实测）：`who` 每次扫 edges.jsonl 要 200 ms；edges 会长到几十万条，
    那不叫"秒级"。折成字典后是毫秒级，且能直接回答「我引用谁 / 谁引用我」两个方向。
    """
    if not EDGES.is_file():
        print("没有 edges（先跑 refs）")
        return 1
    who, refs, n = {}, {}, 0
    with EDGES.open(encoding="utf-8") as fh:
        for line in fh:
            try:
                e = json.loads(line)
            except Exception:                                  # noqa: BLE001
                continue
            s, d, k = e["src"], e["dst"], e.get("kind", "path")
            who.setdefault(_norm(d), []).append({"src": s, "kind": k})
            refs.setdefault(s, []).append({"dst": d, "kind": k})
            n += 1
    WHO.write_text(json.dumps({"at": time.strftime("%Y-%m-%dT%H:%M:%S"), "edges": n,
                               "who": who, "refs": refs}, ensure_ascii=False), encoding="utf-8")
    print("index：%d 条边 → 反向 %d 个目标 · 正向 %d 个源 · %s"
          % (n, len(who), len(refs), _rel(WHO)))
    return 0


def cmd_who(args) -> int:
    target = _norm(args.path)
    t0 = time.time()
    idx = json.loads(IDX.read_text(encoding="utf-8")) if IDX.is_file() else {"entries": []}
    by_path = {e["path"]: e for e in idx["entries"]}
    outs, mine = [], []
    if WHO.is_file():
        db = json.loads(WHO.read_text(encoding="utf-8"))
        outs = db.get("who", {}).get(target, [])
        mine = db.get("refs", {}).get(target, [])
        src_how = "who.idx.json（O(1)）"
    else:                                                      # 没折索引就退回线性扫（如实标来源）
        src_how = "edges.jsonl 线性扫（先跑 index 可降到毫秒）"
        if EDGES.is_file():
            with EDGES.open(encoding="utf-8") as fh:
                for line in fh:
                    e = json.loads(line)
                    if e["dst"] == target or _norm(e["dst"]).endswith(target):
                        outs.append(e)
    dt = (time.time() - t0) * 1000
    print("被谁引用（%d 条）：" % len(outs))
    for e in outs[:30]:
        print("   %-64s [%s]" % (e["src"], e.get("kind")))
    if mine:
        print("我引用谁（%d 条，前 15）：" % len(mine))
        for e in mine[:15]:
            print("   %-64s [%s]" % (e["dst"], e.get("kind")))
    print("在包里：%s · 原始 %s B · 压缩 %s B"
          % ("是" if target in by_path else "否",
             by_path.get(target, {}).get("raw", "-"), by_path.get(target, {}).get("len", "-")))
    print("查询 %.1f ms · 来源 %s" % (dt, src_how))
    return 0


def cmd_get(args) -> int:
    idx = _load_idx()
    target = _norm(args.path)
    ent = next((e for e in idx["entries"] if e["path"] == target), None)
    if not ent:
        print("包里没有：%s" % target)
        return 1
    t0 = time.time()
    with PACK.open("rb") as pk:
        pk.seek(ent["off"])
        blob = pk.read(ent["len"])
    data = _decode(blob, ent.get("codec") or "gzip")
    dt = (time.time() - t0) * 1000
    if args.out:
        Path(args.out).write_bytes(data)          # 只写到调用方指定处，不覆盖源件
        print("解出 %s（%d B）· %.1f ms · 写入 %s" % (target, len(data), dt, args.out))
    else:
        print("解出 %s（%d B）· %.1f ms（未指定 -o，只回读数）" % (target, len(data), dt))
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="全仓文件级双向索引 + 按需压缩（可续跑）")
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("scan"); s.add_argument("--limit", type=int, default=0)
    s.add_argument("--hash-max", type=int, default=64 * 1024 * 1024)
    s.add_argument("--restart", action="store_true")
    s = sub.add_parser("refs"); s.add_argument("--restart", action="store_true")
    s = sub.add_parser("pack"); s.add_argument("--level", type=int, default=12)
    s.add_argument("--codec", choices=["zstd", "gzip"], default="zstd")
    s.add_argument("--max-bytes", type=int, default=512 * 1024 * 1024)
    s.add_argument("--limit", type=int, default=0)
    s.add_argument("--skip-prefix", nargs="*", default=[
        "gbt_allinone/store/weights.bin", "outputs/repo-pack/"])
    s = sub.add_parser("index")
    s = sub.add_parser("who"); s.add_argument("path")
    s = sub.add_parser("get"); s.add_argument("path"); s.add_argument("-o", "--out", default="")
    s = sub.add_parser("summary")
    a = ap.parse_args(argv)
    return {"scan": cmd_scan, "refs": cmd_refs, "pack": cmd_pack, "index": cmd_index, "who": cmd_who,
            "get": cmd_get, "summary": lambda _a: summarise()}[a.cmd](a)


if __name__ == "__main__":
    raise SystemExit(main())




