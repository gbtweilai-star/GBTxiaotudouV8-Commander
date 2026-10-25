#!/usr/bin/env python
# -*- coding: utf-8 -*-
# gbt-instrument: 重份源码普查器 —— 只读，回答「同一份源码在盘上有几处」
# 开发者：自由的风 · GBT小土豆V8
"""重份源码普查 —— 只读。

存在的理由：负责人问「确保源代码就一份」。这个问题不能靠印象回答，
必须先把盘上所有**可能是源码树**的落点列出来，逐个给出文件数/字节数，
再判哪一个被真实消费（在 sys.path 上 / 被 package.json 引用 / 被测试断言）。

本器**不改盘**（只读遍历）。判断留给使用者，动作留给 clean_residue。

用法：
    python tools/codex-scripts/dup-source-inventory.py            # 人读版
    python tools/codex-scripts/dup-source-inventory.py --json     # 机读版
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

# 为什么要在开头就锁 UTF-8：Windows 控制台默认 cp936，中文路径打出来是乱码，
# 重定向进文件更糟 —— 读回来的人分不清哪一行是哪个目录，等于读数不可信。
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except (AttributeError, OSError):     # 老解释器/被重定向到不支持的对象
    pass

# 只看这些名字的目录：它们才是「一棵源码/依赖树」的候选
INTERESTING = {
    "node_modules", "pylibs", "vendor", "holo_pet_w3", "holo_pet_w25", "holo_pet",
    "_upstream", ".pylibs", "dist", "build", "release", "out", "archive",
    "mirror_space", "shadow-repo",
}

SKIP_INTO = {".git", "__pycache__", ".trash"}


def _safe_size(f: Path) -> int:
    try:
        return f.stat().st_size
    except OSError:
        return 0


def weigh(path: Path) -> tuple[int, int]:
    """(文件数, 总字节)。只读遍历，遇 OSError 就地跳过并计数为 0 字节。"""
    files = 0
    total = 0
    stack = [path]
    while stack:
        here = stack.pop()
        try:
            entries = list(os.scandir(here))
        except OSError:
            continue
        for ent in entries:
            try:
                if ent.is_dir(follow_symlinks=False):
                    if ent.name in SKIP_INTO:
                        continue
                    stack.append(Path(ent.path))
                elif ent.is_file(follow_symlinks=False):
                    files += 1
                    total += ent.stat(follow_symlinks=False).st_size
            except OSError:
                continue
    return files, total


def top_level() -> list[Path]:
    out = []
    for ent in sorted(os.scandir(ROOT), key=lambda e: e.name.lower()):
        if not ent.is_dir(follow_symlinks=False):
            continue
        if ent.name in SKIP_INTO:
            continue
        out.append(Path(ent.path))
    return out


def deep_hits(max_depth: int = 3) -> list[Path]:
    """在整仓里找名字像「依赖树/源码树副本」的目录（深度受限）。"""
    hits: list[Path] = []
    len(ROOT.parts)
    stack = [(ROOT, 0)]
    while stack:
        here, depth = stack.pop()
        if depth >= max_depth:
            continue
        try:
            entries = list(os.scandir(here))
        except OSError:
            continue
        for ent in entries:
            if not ent.is_dir(follow_symlinks=False):
                continue
            if ent.name in SKIP_INTO:
                continue
            p = Path(ent.path)
            if ent.name in INTERESTING:
                hits.append(p)
                continue          # 命中的树不再往里钻（免得把 vendor 里面再列一遍）
            if depth + 1 < max_depth:
                stack.append((p, depth + 1))
    return sorted(hits, key=lambda p: str(p).lower())


def main() -> int:
    ap = argparse.ArgumentParser(description="重份源码普查（只读）")
    ap.add_argument("--json", action="store_true", help="输出 JSON")
    ap.add_argument("--depth", type=int, default=3, help="向下找树的深度（默认 3）")
    ap.add_argument("--breakdown", default="", help="只拆某一棵树的第一层（相对仓根）")
    ap.add_argument("--top", type=int, default=0, help="只列最大的前 N 条（0 = 全列）")
    args = ap.parse_args()

    if args.breakdown:
        base = ROOT / args.breakdown
        if not base.is_dir():
            print("不是目录：%s" % base)
            return 2
        rows = []
        for ent in sorted(os.scandir(base), key=lambda e: e.name.lower()):
            p = Path(ent.path)
            if p.is_dir():
                files, size = weigh(p)
            else:
                files, size = 1, _safe_size(p)
            rows.append({"path": "%s/%s" % (args.breakdown, ent.name),
                         "files": files, "bytes": size, "where": "breakdown"})
        rows.sort(key=lambda r: -r["bytes"])
        total_files = sum(r["files"] for r in rows)
        total_bytes = sum(r["bytes"] for r in rows)
        if args.top:
            rows = rows[:args.top]
        if args.json:
            print(json.dumps({"root": str(ROOT), "trees": rows,
                              "all_files": total_files, "all_bytes": total_bytes},
                             ensure_ascii=False, indent=2))
            return 0
        print("拆解：%s（合计 %d 文件 · %.1f MB）"
              % (args.breakdown, total_files, total_bytes / 1048576.0))
        for r in rows:
            print("%-58s %9d %12.1f" % (r["path"], r["files"],
                                        r["bytes"] / 1048576.0))
        return 0

    rows = []
    for p in top_level():
        files, size = weigh(p)
        rows.append({"path": str(p.relative_to(ROOT)), "files": files, "bytes": size,
                     "where": "top"})
    for p in deep_hits(args.depth):
        files, size = weigh(p)
        rows.append({"path": str(p.relative_to(ROOT)), "files": files, "bytes": size,
                     "where": "deep"})

    # 去重：deep 可能把 top 里的树再报一次
    seen = set()
    uniq = []
    for r in rows:
        if r["path"] in seen:
            continue
        seen.add(r["path"])
        uniq.append(r)

    uniq.sort(key=lambda r: -r["bytes"])
    if args.json:
        print(json.dumps({"root": str(ROOT), "trees": uniq}, ensure_ascii=False, indent=2))
        return 0

    print("仓根：%s" % ROOT)
    print("%-58s %9s %12s  %s" % ("相对路径", "文件数", "MB", "层级"))
    print("-" * 92)
    for r in uniq:
        print("%-58s %9d %12.1f  %s"
              % (r["path"], r["files"], r["bytes"] / 1048576.0, r["where"]))
    print("-" * 92)
    print("合计：%d 棵树 · %d 文件 · %.1f MB"
          % (len(uniq), sum(r["files"] for r in uniq),
             sum(r["bytes"] for r in uniq) / 1048576.0))
    return 0


if __name__ == "__main__":
    sys.exit(main())
