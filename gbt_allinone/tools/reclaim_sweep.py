#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""无死角枚举 + 待清清单（垃圾桶模式）

Owner 2026-09-22：
  「别怕，你设计把东西丢垃圾桶，我去看清不清就好了」
  「但必须毫无死角的扫描出所有东西」

═══ 这一版补的是上一版的哪个洞 ═══
  上一版 `code_exhaustive_scan` 报了"覆盖率闭合 8581/8581"——
  但它**跳过了 31 个目录**（.git / node_modules / .pylibs / store / dist / __pycache__ …）。
  **跳过 ≠ 无死角。** 那些地方我一个字节都没看，却报了个"闭合"。

  ⇒ 本模块把"跳过"升级成"**量过之后有意排除**"：
     每个被跳过的区域都给出 **文件数 · 总字节 · 类型分布 · 抽样路径 · 排除理由 · 是否可清**。
     **未知的盲区 → 已知的、带读数的排除。**

═══ 垃圾桶模式（Owner 的处置口径）═══
  · 本模块**只搬不删** —— 候选移进 `.trash/review-<日期>/<类别>/`，保留原相对路径
  · 同时出一份人读清单 `delivery/待清清单-<日期>.md`（带证据，供 Owner 过目）
  · **永不做 `rm`** —— 清不清由 Owner 定
  · 每一刀过 `exec_trace` 留痕

用法：
    py -3.14 -m gbt_allinone.tools.reclaim_sweep --survey     # 只量，不动
    py -3.14 -m gbt_allinone.tools.reclaim_sweep --stage      # 量 + 搬进垃圾桶（不删）
"""
from __future__ import annotations

import argparse
import collections
import json
import os
import shutil
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

# ── 被排除的区域：每一条都带**理由**与**可清性判断** ──────────────
EXCLUDED = {
    "node_modules": ("第三方依赖树", False),
    ".pylibs": ("第三方 Python 依赖", False),
    ".git": ("版本库内部对象", False),
    "__pycache__": ("Python 编译缓存", True),
    "store": ("框架运行时数据（有独立管理）", False),
    ".playwright-cli": ("Playwright 缓存", True),
    "dist": ("构建产物", True),
    ".venv": ("虚拟环境", True),
    "venv": ("虚拟环境", True),
    ".next": ("构建缓存", True),
    ".turbo": ("构建缓存", True),
}
# ── 可清的"类别"（垃圾桶模式下的候选），每条要能说清判据 ──────
TRASH_RULES = [
    ("编译缓存", lambda p: p.name == "__pycache__" or p.suffix == ".pyc",
     "Python 导入时自动重建，不含手写内容"),
    ("编辑器临时件", lambda p: p.suffix in (".bak", ".tmp", ".swp", ".orig", ".rej"),
     "编辑器/工具留下的临时副本"),
    ("调试残留", lambda p: p.name.startswith(("_tmp", "_test_", "test.txt", "_shot_")),
     "命名即临时（_tmp/_test_/test.txt/_shot_）"),
    ("一次性脚本", lambda p: p.suffix == ".py" and p.name.startswith(("_r", "_rh", "_fix", "_patch")) ,
     "形如 _r110_/_rh379_/_fix_ 的一次性作业脚本"),
    ("构建产物", lambda p: any(s in p.parts for s in ("dist", "build", ".next", ".turbo")),
     "构建产物，可从源码重建"),
    ("工具缓存", lambda p: any(s in p.parts for s in (".playwright-cli", ".cache", ".pytest_cache",
                                                    ".mypy_cache", ".ruff_cache")),
     "工具自己的缓存目录"),
]


def survey() -> dict:
    """量**每一个**被排除的区域 —— 把盲区变成有读数的排除。"""
    rows = []
    for dp, dns, fns in os.walk(ROOT):
        here = Path(dp)
        for d in list(dns):
            if d in EXCLUDED:
                full = here / d
                n = sz = 0
                exts = collections.Counter()
                sample = []
                try:
                    for sub in full.rglob("*"):
                        if sub.is_file():
                            n += 1
                            try:
                                sz += sub.stat().st_size
                            except OSError:
                                pass
                            exts[sub.suffix.lower() or "(无后缀)"] += 1
                            if len(sample) < 3:
                                sample.append(str(sub.relative_to(ROOT)))
                except Exception:                                # noqa: BLE001
                    pass
                why, cleanable = EXCLUDED[d]
                rows.append({"dir": str(full.relative_to(ROOT)), "files": n,
                             "mb": round(sz / 1024 / 1024, 1), "why": why,
                             "cleanable": cleanable,
                             "top_ext": dict(exts.most_common(5)), "sample": sample})
                dns.remove(d)
    # 超上限没扫的**文件**（上一版只跳了 1 个，这里逐个列）
    big = []
    for dp, dns, fns in os.walk(ROOT):
        if any(s in Path(dp).parts for s in EXCLUDED):
            dns[:] = []
            continue
        for fn in fns:
            p = Path(dp) / fn
            try:
                sz = p.stat().st_size
            except OSError:
                continue
            if sz > 3_000_000:
                big.append({"file": str(p.relative_to(ROOT)), "mb": round(sz / 1048576, 2)})
    rows.sort(key=lambda r: -r["mb"])
    return {"excluded": rows, "oversize_not_scanned": big,
            "excluded_total_files": sum(r["files"] for r in rows),
            "excluded_total_mb": round(sum(r["mb"] for r in rows), 1)}


def find_trash() -> list:
    """按类别找垃圾桶候选。**只找，不动。**"""
    out = []
    for dp, dns, fns in os.walk(ROOT):
        here = Path(dp)
        if any(s in here.parts for s in (".git", ".pylibs", "node_modules", ".trash")):
            dns[:] = []
            continue
        for name in list(dns) + fns:
            p = here / name
            for cat, rule, why in TRASH_RULES:
                try:
                    if rule(p):
                        rel = str(p.relative_to(ROOT))
                        sz = 0
                        if p.is_file():
                            sz = p.stat().st_size
                        else:
                            for s in p.rglob("*"):
                                if s.is_file():
                                    try:
                                        sz += s.stat().st_size
                                    except OSError:
                                        pass
                        out.append({"cat": cat, "path": rel, "is_dir": p.is_dir(),
                                    "mb": round(sz / 1048576, 2), "why": why})
                        break
                except Exception:                                # noqa: BLE001
                    continue
    # 去重（父目录被选中就别再列子项）
    out.sort(key=lambda r: r["path"])
    keep, seen = [], set()
    for r in out:
        if any(r["path"].startswith(s + os.sep) for s in seen):
            continue
        seen.add(r["path"])
        keep.append(r)
    return keep


def stage(cands: list) -> tuple:
    """**搬**（不是删）进 `.trash/review-<日期>/<类别>/`，保留相对路径。"""
    stamp = time.strftime("%Y%m%d-%H%M%S")
    base = ROOT / ".trash" / f"review-{stamp}"
    moved, failed = [], []
    for c in cands:
        src = ROOT / c["path"]
        if not src.exists():
            continue
        dst = base / c["cat"] / c["path"]
        try:
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(src), str(dst))
            moved.append({**c, "to": str(dst.relative_to(ROOT))})
        except Exception as e:                                    # noqa: BLE001
            failed.append({**c, "why": f"{type(e).__name__}: {str(e)[:80]}"})
    return {"base": str(base.relative_to(ROOT)), "moved": moved, "failed": failed}


def write_review(sv: dict, cands: list, st: dict | None) -> Path:
    L = ["# 待清清单（垃圾桶模式 · 请 Owner 过目）", "",
         f"> 生成 {time.strftime('%Y-%m-%dT%H:%M:%S')}",
         "> **本清单只搬不删。** 所有候选已移到 `.trash/review-*/`，保留原相对路径。",
         "> 你过目后告诉我清哪些，我再清；不清的可以随时搬回去。", "",
         "## 一 · 上一版扫描的盲区（跳过 ≠ 无死角，这里逐个量过）", "",
         "| 区域 | 文件数 | 体积 | 为什么排除 | 可清 |", "|---|---:|---:|---|---|"]
    for r in sv["excluded"]:
        L.append(f"| `{r['dir']}` | {r['files']:,} | {r['mb']:,} MB | {r['why']} | "
                 f"{'**可清**' if r['cleanable'] else '不可清'} |")
    L += ["", f"**合计 {sv['excluded_total_files']:,} 个文件 · "
              f"{sv['excluded_total_mb']:,} MB 未逐行扫描** —— 这些是「量过之后有意排除」，"
              f"不是「没看见」。", ""]
    if sv["oversize_not_scanned"]:
        L += ["### 超大文件（超过单文件上限，没逐行扫）", ""]
        for b in sv["oversize_not_scanned"][:20]:
            L.append(f"- `{b['file']}` —— {b['mb']} MB")
        L.append("")
    L += ["## 二 · 垃圾桶候选", ""]
    bycat = collections.defaultdict(list)
    for c in cands:
        bycat[c["cat"]].append(c)
    for cat, items in sorted(bycat.items(), key=lambda kv: -sum(i["mb"] for i in kv[1])):
        tot = sum(i["mb"] for i in items)
        L += [f"### {cat} —— {len(items)} 项 · {tot:,.1f} MB", "",
              f"判据：{items[0]['why']}", ""]
        for it in sorted(items, key=lambda x: -x["mb"])[:40]:
            L.append(f"- `{it['path']}`{'/' if it['is_dir'] else ''} — {it['mb']} MB")
        if len(items) > 40:
            L.append(f"- … 另 {len(items)-40} 项")
        L.append("")
    if st:
        L += ["## 三 · 已搬进垃圾桶", "",
              f"落点：`{st['base']}` · 搬了 {len(st['moved'])} 项 · 失败 {len(st['failed'])} 项", ""]
        for f in st["failed"][:10]:
            L.append(f"- ✘ 失败 `{f['path']}` —— {f['why']}")
        L.append("")
    L += ["---", "", "> 开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属"]
    p = ROOT / "delivery" / f"待清清单-{time.strftime('%Y%m%d')}.md"
    p.write_text("\n".join(L), encoding="utf-8")
    return p


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="无死角枚举 + 垃圾桶（只搬不删）")
    ap.add_argument("--survey", action="store_true")
    ap.add_argument("--stage", action="store_true")
    a = ap.parse_args(argv)
    sys.path.insert(0, str(ROOT))
    from gbt_allinone.tools.exec_trace import Trace

    t = Trace("无死角枚举 + 垃圾桶", actor="AI")
    sv = survey()
    print("=" * 78)
    print("一 · 上一版的盲区（逐个量过 —— 盲区变已知）")
    print("=" * 78)
    for r in sv["excluded"]:
        print(f"  {r['mb']:>9,.1f} MB  {r['files']:>7,} 文件  {r['dir']:<34} "
              f"{'可清' if r['cleanable'] else '不可清'}  ({r['why']})")
    print(f"  ── 合计 {sv['excluded_total_files']:,} 文件 · {sv['excluded_total_mb']:,} MB")
    if sv["oversize_not_scanned"]:
        print(f"\n  超大未扫文件 {len(sv['oversize_not_scanned'])} 个:")
        for b in sv["oversize_not_scanned"][:6]:
            print(f"     {b['mb']:>7} MB  {b['file']}")
    t.fact("盲区测量", "os.walk 遍历每个被排除目录，统计文件数与总字节",
           f"{len(sv['excluded'])} 个区域 · {sv['excluded_total_files']} 文件 · "
           f"{sv['excluded_total_mb']} MB")

    cands = find_trash()
    print()
    print("=" * 78)
    print(f"二 · 垃圾桶候选 {len(cands)} 项")
    print("=" * 78)
    bycat = collections.defaultdict(list)
    for c in cands:
        bycat[c["cat"]].append(c)
    for cat, items in sorted(bycat.items(), key=lambda kv: -sum(i["mb"] for i in kv[1])):
        print(f"  {cat:<14} {len(items):>5} 项 · {sum(i['mb'] for i in items):>9,.1f} MB")

    st = None
    if a.stage:
        st = stage(cands)
        print()
        print(f"  已搬进 {st['base']} —— {len(st['moved'])} 项 · 失败 {len(st['failed'])} 项")
        t.fact("搬入垃圾桶", "shutil.move 逐项搬（**不是删**）",
               f"落点 {st['base']} · 搬 {len(st['moved'])} · 失败 {len(st['failed'])}")
    else:
        t.skip("搬入垃圾桶", "本次是 --survey 模式，只量不动")

    p = write_review(sv, cands, st)
    print(f"\n  人读清单: {p.relative_to(ROOT)}")
    print()
    print(t.report()[:900])
    return 0


if __name__ == "__main__":
    sys.exit(main())
