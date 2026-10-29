#!/usr/bin/env python
# -*- coding: utf-8 -*-
# gbt-instrument: vendor/node_modules 去重器 —— 只搬**逐字节重复且零引用**的包
# 开发者：自由的风 · GBT小土豆V8
"""vendor/node_modules 去重器（默认只出清单；--go 才进回收站）。

## 这件事的由来（第 40 轮 · Owner：「一次性来个大清洗」）

`delivery/20260922-源码分家方案.md` §6.1 的设计是：
    `gbt_allinone/.pylibs/`      → `vendor/pylibs/`      + junction  ✔ 落了
    `holo_pet/node_modules/`     → `vendor/node_modules/` + junction  ✘ **没落**
实测（`probe-reparse-points.py`）：`.pylibs` 那条是 junction，**node_modules 这条不是** ——
`holo_pet/node_modules` 与 `vendor/node_modules` 是**两个各自独立的实体**，
同一套 15 个包在盘上占了两份（约 797 MB）。

## 为什么只动 15 个、偏偏留下 `three`

- **15 个**：与 `holo_pet/node_modules` 里的同名包**逐字节相同**（文件数 + 总字节都相同），
  而且全仓**零引用**（没有任何地方写 `vendor/node_modules/<包名>`）。
- **`three` 必须留**：`tools/codex-scripts/vendor_three.py:28` 写死
  `SRC = ROOT / "vendor" / "node_modules" / "three"` —— 它是**生成器真读的源**。
  两个 `three` 都是 0.180.0 但字节不同（各 1117 文件，30,764,975 vs 30,161,896 B），
  所以**不能**拿 holo_pet 那份去顶 vendor 这份（会改生成结果）。

## 安全性质（这是敢动手的唯一理由）

要搬的每一个包，在 `holo_pet/node_modules/` 里都有**逐字节相同的现役副本**，
而 Node 的解析规则是「就近取」：从 `holo_pet/` 出发先命中 `holo_pet/node_modules`，
**永远走不到** `vendor/node_modules`（那不在任何祖先 `node_modules` 链上）。
⇒ 搬掉它**不可能**让今天能跑的东西跑不起来。要还原：回收站里原样拿回。

用法：
    python tools/codex-scripts/vendor-node-trim.py          # 只出清单
    python tools/codex-scripts/vendor-node-trim.py --go      # 真搬进回收站
"""

from __future__ import annotations

import argparse
import importlib.util
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except (AttributeError, OSError):
    pass

VENDOR = ROOT / "vendor" / "node_modules"
HOLO = ROOT / "holo_pet" / "node_modules"

# 留下：生成器真读的源。理由见文件头，别凭感觉加减。
# `.bin` 也留：它不是包，是 npm 的 bin 垫片目录；清它**收益 0 字节**，
#   却在动"依赖树的结构"。判据要跟收益对齐 —— 没收益的改动不做。
# 理由与名字**绑在一起**给：上一版两件共用一句 reason，
#    于是报表把 `.bin` 也印成"生成器真读的源" —— **读数说谎**（第 40 轮自查抓到）。
KEEP = {
    "three": "生成器真读的源（vendor_three.py:28 写死这个路径）",
    ".bin": "不是包，是 npm bin 垫片目录；清它收益 0 字节，不值得动结构",
}


def _reuse(name: str, fname: str):
    """复用同目录里的既有口径（引用守卫 / 回收站搬运），不另写一份。"""
    path = Path(__file__).resolve().parent / fname
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def weigh(p: Path) -> tuple[int, int]:
    files = total = 0
    stack = [p]
    while stack:
        here = stack.pop()
        try:
            entries = list(os.scandir(here))
        except OSError:
            continue
        for ent in entries:
            try:
                if ent.is_dir(follow_symlinks=False):
                    stack.append(Path(ent.path))
                elif ent.is_file(follow_symlinks=False):
                    files += 1
                    total += ent.stat(follow_symlinks=False).st_size
            except OSError:
                continue
    return files, total


def index(base: Path) -> dict:
    """{包名: (文件数, 字节)}。作用域包（@scope/x）按 `@scope/x` 记一名。"""
    out = {}
    if not base.is_dir():
        return out
    for ent in os.scandir(base):
        if not ent.is_dir(follow_symlinks=False):
            continue
        if ent.name.startswith("@"):
            for sub in os.scandir(ent.path):
                if sub.is_dir(follow_symlinks=False):
                    out["%s/%s" % (ent.name, sub.name)] = weigh(Path(sub.path))
        else:
            out[ent.name] = weigh(Path(ent.path))
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description="vendor/node_modules 去重（进回收站）")
    ap.add_argument("--go", action="store_true", help="真搬（默认只出清单）")
    a = ap.parse_args()

    v, h = index(VENDOR), index(HOLO)
    print("=" * 92)
    print("vendor/node_modules 去重 · 判据=与 holo_pet/node_modules 逐字节相同 + 零引用")
    print("=" * 92)
    print("  vendor 包 %d 个 · holo_pet 包 %d 个" % (len(v), len(h)))
    if not v or not h:
        print("  🔴 有一侧读不到 —— 停手（不许在看不见对照的情况下搬东西）")
        return 2

    cr = _reuse("gbt_clean_residue", "clean_residue.py")
    print("  正在建引用底账…", flush=True)
    refs = cr.referenced_names()

    plan, keep = [], []
    for name in sorted(v):
        files, size = v[name]
        if name in KEEP:
            keep.append((name, files, size, KEEP[name]))
            continue
        if name not in h:
            keep.append((name, files, size, "holo_pet 侧没有同名包 ⇒ 不可再生，留"))
            continue
        if h[name] != (files, size):
            keep.append((name, files, size, "与 holo_pet 侧**不一致**（%d/%d）⇒ 不是重复，留"
                         % h[name]))
            continue
        g = cr.guard(name, refs)
        if g:
            keep.append((name, files, size, g))
            continue
        plan.append((name, files, size))

    print("-" * 92)
    print("  留下（逐条给理由）：")
    for name, files, size, why in keep:
        print("      %-34s %5d 文件 %8.2f MB  %s" % (name, files, size / 1048576, why))
    print("-" * 92)
    tot = sum(s for _n, _f, s in plan)
    print("  将搬走 %d 个包 · %.1f MB：" % (len(plan), tot / 1048576))
    for name, files, size in plan:
        print("      %-34s %5d 文件 %8.2f MB" % (name, files, size / 1048576))

    if not a.go:
        print("-" * 92)
        print("  （未动盘。要真搬请加 --go）")
        return 0

    if not plan:
        print("  没有可搬的。")
        return 0

    targets = []
    for name, _f, _s in plan:
        if "/" in name:
            scope, _, leaf = name.partition("/")
            targets.append(VENDOR / scope / leaf)
        else:
            targets.append(VENDOR / name)

    print("-" * 92)
    print("  正在送往回收站（%d 项）…" % len(targets), flush=True)
    ok, bad, skip = cr._recycle_batch(targets)
    _x = ("· 其中 %d 项随父目录一并搬走（**不是失败**）" % skip) if skip else ""
    print("  ✅ 计划 %d 项 → 实搬 %d 项 %s · 失败 %d 项" % (len(targets), ok, _x, len(bad)))
    for b in bad[:20]:
        print("      BAD %s" % b)

    # 搬完必须自证：留下的 `three` 还在，生成器的源没被动。
    still = index(VENDOR)
    print("-" * 92)
    print("  搬后 vendor 包：%s" % ", ".join(sorted(still)) or "(空)")
    print("  %s `three` 仍在（生成器源完好）" % ("✅" if "three" in still else "🔴"))
    print("  下一步自证：py -3.14 tools/codex-scripts/vendor_three.py --check")
    return 0 if not bad and "three" in still else 2


if __name__ == "__main__":
    sys.exit(main())
