#!/usr/bin/env python
# -*- coding: utf-8 -*-
# gbt-instrument: 重解析点普查 —— 只读，回答「这棵树是实体，还是别人的一个视图」
# 开发者：自由的风 · GBT小土豆V8
"""重解析点（junction / symlink）普查 —— 只读。

## 为什么要这件东西（第 40 轮，差一步就出人命）

我量到 `vendor/pylibs` 与 `gbt_allinone/.pylibs` **文件数相同、逐字节相同**，
于是判「vendor 是多余副本」。**反了**：`.pylibs` 是 junction，`vendor/pylibs` 才是实体。
按那个结论清盘，等于把唯一那份第三方依赖树删掉 —— numpy / PIL / comtypes 当场全断。

⇒ **「内容相同」推不出「有一份多余」**。先问目录身份，再谈重复。
本器把这条判据变成一次扫描：全仓的 junction / symlink 全部列出来，**且不穿进去**
（穿进去就会把同一个文件数两遍 —— 上一轮的总量就是这么虚高的）。

## 输出怎么读

    [实体]  真实目录，占着磁盘
    [视图]  junction / symlink ⇒ **不占额外磁盘，也不许删**（删了等于删实体）
    视图的 `-> 目标` 就是它的实体落在哪。

用法：
    python tools/codex-scripts/probe-reparse-points.py            # 人读版
    python tools/codex-scripts/probe-reparse-points.py --json      # 机读版
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except (AttributeError, OSError):
    pass

REPARSE = 0x400
SKIP = {".git", "__pycache__", ".trash"}
DANGLING = "(断链：目标不存在，读不到重解析目标)"


def is_view(p: Path, st: os.stat_result) -> bool:
    """重解析点 = 别人的视图。**不穿进去**。"""
    if os.path.islink(p):
        return True
    if hasattr(os.path, "isjunction") and os.path.isjunction(p):
        return True
    return bool(getattr(st, "st_file_attributes", 0) & REPARSE)


def census() -> list[dict]:
    views: list[dict] = []
    stack = [ROOT]
    while stack:
        here = stack.pop()
        try:
            entries = list(os.scandir(here))
        except OSError:
            continue
        for ent in entries:
            if ent.name in SKIP:
                continue
            rel = Path(ent.path).relative_to(ROOT).as_posix()
            try:
                looks_like_dir = ent.is_dir(follow_symlinks=False)
            except OSError:
                looks_like_dir = False
            if not looks_like_dir:
                continue
 # **断链视图**：`scandir` 说它是目录（属性缓存在重解析点上），
            #    可 `lstat` / `isjunction` 一碰就 OSError（目标已被删除）。
            #    这种"一半工具看得见、一半看不见"的路径本身就是分岔源 ——
            #    必须**报出来**。（实测：仓根 `latest_logs` 就是这一个。）
 # 这里原来写的是 `except OSError: continue` —— 静默跳过，
            #       于是 R7 从来没红过，而我以为"全仓没有断链"。
            try:
                st = ent.stat(follow_symlinks=False)
                view = is_view(Path(ent.path), st)
            except OSError:
                views.append({"view": rel, "target": DANGLING, "dangling": True})
                continue
            try:
                if view:
                    views.append({
 # 一律 **正斜杠**：登记表与 glob 都按正斜杠写。
                        #    这里若留着 Windows 反斜杠，比对会**静默不匹配** ——
                        #    量具于是报「没有未交代的视图」，而其实一条都没对上。
                        #    （第 40 轮实测：R6 正对照就是这么被抓出来的。）
                        "view": rel,
                        "target": os.path.realpath(ent.path),
                    })
                    continue            # 🔴 不穿进视图
            except OSError:
                views.append({"view": rel, "target": DANGLING, "dangling": True})
                continue
            stack.append(Path(ent.path))
    return sorted(views, key=lambda v: v["view"].lower())


def main() -> int:
    views = census()
    if "--json" in sys.argv:
        print(json.dumps({"root": str(ROOT), "views": views},
                         ensure_ascii=False, indent=2))
        return 0

    print("重解析点普查（junction / symlink）· 仓根 %s" % ROOT)
    print("=" * 96)
    if not views:
        print("  一个都没有 —— 全仓每一棵树都是实体。")
    for v in views:
        print("  [视图] %-46s -> %s" % (v["view"], v["target"]))
    print("-" * 96)
    print("  视图 %d 个。" % len(views))
    print("  ⚠️ 视图**不占额外磁盘**、也**不许当重复清掉**：删视图 = 删实体入口。")
    print("     判「谁多余」只能在**两个都是实体**时才成立（比 realpath / inode）。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
