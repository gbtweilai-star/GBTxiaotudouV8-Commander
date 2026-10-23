#!/usr/bin/env python
# -*- coding: utf-8 -*-
# gbt-instrument: 仓根树登记闸 —— 分类 + 分岔判据，把「哪一份是权威」变成机检
# 开发者：自由的风 · GBT小土豆V8
"""仓根树登记闸 —— 只读。

## 它解决的那件事

负责人第 N 次说「确保源代码就一份」「整理好分类别在分岔了」。
在这之前，这个问题只能靠**人记得**：谁是权威、谁是视图、谁是上游、谁是草稿。
记得住的时候没事，记不住的时候就会出现**两份都像权威**的树，
而下一个人（或下一个我）会挑错那一份动手。

## 最贵的一条判据（第 40 轮差点付的学费）

我量到 `vendor/pylibs` 与 `gbt_allinone/.pylibs` **文件数相同、逐字节相同**，
判「vendor 是多余副本」。**反了**：`.pylibs` 是 junction，`vendor/pylibs` 才是实体。
按那个结论清盘 = 把唯一那份第三方依赖树删掉，numpy / PIL / comtypes 当场全断。

⇒ 铁律：**「内容相同」推不出「有一份多余」。先问目录身份，再谈重复。**
   本闸因此把「重解析点普查」当成**前置判据**（口径复用 `probe-reparse-points.py`，
   不许另写一份），并且带一条**正对照**：普查必须能看见已知的那条 junction ——
   看不见就说明量具瞎了，本闸直接报红，而不是"没发现重复，全绿"。

## 判据（红 = 必须处理）

    R1  仓根有**未登记**的顶层项      —— 新分岔就是这么长出来的
    R2  登记了但**盘上不在**          —— 登记表过期，会误导下一个人
    R3  有 junction/视图**没写进 forks** —— 「实体 vs 视图」没交代清楚
    R4  forks 里声明 kind=copy 的两条**其实是同一份** —— 登记表说谎
    R5  两条登记树**内容指纹完全相同**却没声明关系 —— 没登记的重复
    R6  普查看不见已知那条 junction   —— **量具自检失败**（正对照）

用法：
    python tools/codex-scripts/tree-registry.py --check     # 过闸（红则退出码 2）
    python tools/codex-scripts/tree-registry.py --table      # 人读分类表
"""

from __future__ import annotations

import argparse
import fnmatch
import hashlib
import importlib.util
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REGISTRY = ROOT / "state" / "tree-registry.json"

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except (AttributeError, OSError):
    pass

SKIP = {".git", "__pycache__", ".trash"}

# 已知必被看见的视图（正对照）。写死一条：普查看不见它 = 量具瞎了。
KNOWN_VIEW = "gbt_allinone/.pylibs"


def _load_probe():
    """复用重解析点普查的**同一份口径**（不许在这里另写一个 isjunction 判断）。"""
    path = Path(__file__).resolve().parent / "probe-reparse-points.py"
    spec = importlib.util.spec_from_file_location("gbt_reparse_probe", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def top_entries() -> list[str]:
    """只登记**目录**：本闸管的是「一棵树」。散落文件的重复归 dup-pages / clean_residue。"""
    out = []
    for ent in os.scandir(ROOT):
        if ent.name in SKIP:
            continue
        if ent.is_dir(follow_symlinks=False):
            out.append(ent.name)
    return sorted(out)


def fingerprint(p: Path) -> tuple[str, int]:
    """(内容指纹, 文件数)。相对路径 + 大小 的有序摘要（不看时间，不看 inode）。

    🔴 **必须跳过视图**：穿进 junction 会把同一批文件算两遍 ——
    上一轮的"总计 5363 MB"就是这么虚高的（实体 700 MB 被算成了 1400 MB）。
    """
    h = hashlib.sha256()
    if p.is_file():
        h.update(b"F")
        h.update(p.name.encode("utf-8", "replace"))
        h.update(str(_size(p)).encode())
        return h.hexdigest()[:16], 1
    stack = [p]
    rows = []
    probe = _load_probe()
    while stack:
        here = stack.pop()
        try:
            entries = list(os.scandir(here))
        except OSError:
            continue
        for ent in entries:
            if ent.name in SKIP:
                continue
            try:
                st = ent.stat(follow_symlinks=False)
                if ent.is_dir(follow_symlinks=False):
                    if probe.is_view(Path(ent.path), st):
                        continue                     # 不穿视图
                    stack.append(Path(ent.path))
                else:
                    rows.append((str(Path(ent.path).relative_to(p)).replace("\\", "/"),
                                 st.st_size))
            except OSError:
                continue
    for rel, size in sorted(rows):
        h.update(rel.encode("utf-8", "replace"))
        h.update(str(size).encode())
    return h.hexdigest()[:16], len(rows)


def _size(p: Path) -> int:
    try:
        return p.stat().st_size
    except OSError:
        return 0


def load_registry() -> dict:
    if not REGISTRY.is_file():
        return {}
    try:
        return json.loads(REGISTRY.read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        print("  🔴 登记表读不动：%s" % e)
        return {}


def check() -> int:
    reg = load_registry()
    if not reg:
        print("  🔴 没有登记表：%s" % REGISTRY)
        return 2
    trees = {t["path"]: t for t in reg.get("trees", [])}
    forks = reg.get("forks", [])
    red: list[str] = []

    print("=" * 88)
    print("仓根树登记闸 · 登记 %d 条 · 已声明关系 %d 条" % (len(trees), len(forks)))
    print("=" * 88)
    print("  正在做重解析点普查（前置判据）…", flush=True)
    probe = _load_probe()
    views = {v["view"]: v["target"] for v in probe.census()}

    # ── R6 正对照：普查必须看得见已知那条 junction ──
    if KNOWN_VIEW not in views:
        red.append("R6 量具自检失败：普查没看见已知视图 `%s` —— 它瞎了，"
                   "此时「没发现重复」不算证据" % KNOWN_VIEW)
    else:
        print("  ✓ R6 正对照：普查看见了 `%s` -> %s" % (KNOWN_VIEW, views[KNOWN_VIEW]))

    # ── R7 断链视图：目标没了的 junction/symlink ──
    #    这种路径"一半工具说在、一半说不在" —— 是分岔源，必须清掉。
    for v in sorted(views):
        if "(断链" in str(views[v]):
            red.append("R7 断链视图：`%s`（目标不存在）—— 一半工具看得见、一半看不见，"
                       "清掉它（回收站）" % v)

    # ── R1 / R2 ──
    real = top_entries()
    for name in real:
        if name not in trees:
            red.append("R1 未登记：仓根 `%s`（新分岔通常从这里长出来）" % name)
    for name in sorted(trees):
        if name not in real:
            red.append("R2 登记了但盘上不在：`%s`（登记表过期，会误导下一个人）" % name)

    # ── R3 每条视图都要在 forks 里交代 ──
    # 两类声明：① 逐条 fork（一条视图一个）；② view_families（**一族**视图，
    # 例如 24 条 `remotion-*` 技能junction —— 同一件事重复 24 遍只会让人不去读它）。
    declared_views = set()
    for f in forks:
        for side in ("a", "b"):
            v = f.get(side, {}).get("view")
            if v:
                declared_views.add(v)
    families = reg.get("view_families", [])
    for v in sorted(views):
        if v in declared_views:
            continue
        if any(fnmatch.fnmatch(v, fam.get("glob", "")) for fam in families):
            continue
        red.append("R3 视图没交代：`%s` -> `%s`（没说清它是实体还是别人的视图）"
                   % (v, views[v]))

    # ── R4 声明 copy 的，不许其实是同一份 ──
    for f in forks:
        if f.get("kind") != "copy":
            continue
        rels = [f["a"].get("path"), f["b"].get("path")]
        if any(r in views for r in rels):
            red.append("R4 登记说谎：`%s` 声明为两份副本，实际其中一份是视图"
                       % " vs ".join(str(r) for r in rels))

    # ── R5 内容指纹撞车（只在两条都是实体时才成立）──
    # ⚠️ 空树不比：本仓有四棵**约定空目录**（.autoclaw / .backups / data / .gbt），
    #    它们的内容指纹天然相同 —— 拿"同为 0 个文件"报重复是量具自己在造噪声。
    fps: dict[str, list[str]] = {}
    for name, t in trees.items():
        p = ROOT / name
        if not p.is_dir() or name in views:
            continue
        if t.get("class") in ("上游语料", "第三方依赖(实体)"):
            continue                     # 别人的树不参与指纹比对（份额大、且不由我们管）
        fp, n = fingerprint(p)
        if n == 0:
            continue                     # 空树：没有内容可重复
        fps.setdefault(fp, []).append(name)
    for fp, names in sorted(fps.items()):
        if len(names) > 1:
            red.append("R5 未登记的重复内容：%s（指纹 %s）—— 要么合并，要么写进 forks"
                       % (" / ".join("`%s`" % n for n in names), fp))

    # ── R8 「已经判过、不许动」的东西必须都还在 ──
    # 为什么单列一条：本仓最贵的浪费不是删错，是**把已经判过的事再判一遍** ——
    # 而重判的人（下一个我）看不到当初那句"留"，于是又清一次。
    # 第 40 轮实测：我准备清的 `.scratch/render` / `ai_duanju_audit` / `_traces` /
    # `_v22_diff` / `.scratch/archive`，**Owner 与历次记录早就写了"留"**，
    # 只是散在 memory / delivery / PROJECT_BLUEPRINT 的正文里，没有一处机检。
    # ⚠️ R8 只登记**盘上确实存在的成品/证据**：代码按需创建的空落点（如
    #    `.scratch/_dsh_home`）不在其列 —— 把"会按需创建"写成"必须存在"，
    #    等于给下一个人造一条假红。（第 40 轮自查：我正是这么写错的。）
    missing = 0
    for item in reg.get("protected", []):
        p = ROOT / item.get("path", "")
        if not p.exists():
            missing += 1
            red.append("R8 已判过「留」的东西不见了：`%s`（%s）—— 谁动的？"
                       % (item.get("path"), item.get("source", "?")))
    if reg.get("protected") and not missing:
        # 🔴 这行**只在零缺失时**才印：上一版只要表非空就印「都在」，
        #    于是同一次输出里既说"13 件都在"又点名一件不见了 —— 读数自相矛盾。
        print("  ✓ R8 已判过「留」的 %d 件都在（判据见登记表 protected）"
              % len(reg["protected"]))

    print("-" * 88)
    if not red:
        print("  ✅ 全绿：%d 棵树全部登记 · %d 条视图全部交代 · 无未登记重复"
              % (len(trees), len(views)))
        return 0
    for r in red:
        print("  🔴 %s" % r)
    print("-" * 88)
    print("  红 %d 条。" % len(red))
    return 2


def table() -> int:
    reg = load_registry()
    if not reg:
        print("没有登记表。")
        return 2
    print("=" * 100)
    print("仓根树分类表（%s）" % reg.get("updated", "?"))
    print("=" * 100)
    print("  %-22s %-12s %-10s %s" % ("路径", "分类", "文件数", "消费方 / 理由"))
    print("-" * 100)
    for t in reg.get("trees", []):
        p = ROOT / t["path"]
        n = "-"
        if p.is_dir():
            n = str(sum(1 for _ in p.rglob("*") if _.is_file())) if p.is_dir() else "0"
        print("  %-22s %-12s %-10s %s" % (t["path"][:22], t.get("class", "?"),
                                          n, t.get("why", "")[:60]))
    if reg.get("forks"):
        print("-" * 100)
        print("  已声明的关系：")
        for f in reg["forks"]:
            print("      [%s] %s ⇄ %s\n            %s"
                  % (f.get("kind"), f["a"].get("path"), f["b"].get("path"),
                     f.get("verdict", "")))
    if reg.get("pending_owner"):
        print("-" * 100)
        print("  等 Owner 一句话的：")
        for x in reg["pending_owner"]:
            print("      · %s" % x)
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="仓根树登记闸（只读）")
    ap.add_argument("--check", action="store_true", help="过闸")
    ap.add_argument("--table", action="store_true", help="人读分类表")
    a = ap.parse_args()
    if a.table:
        return table()
    return check()


if __name__ == "__main__":
    sys.exit(main())
