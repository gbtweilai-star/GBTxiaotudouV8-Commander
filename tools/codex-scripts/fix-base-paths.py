#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""**一次性的路径迁移**：`tools/codex-scripts/*.py` 里 `.parent.parent` 算错了一层。

由来（2026-09-25 现读实测）：
    `BASE = Path(__file__).resolve().parent.parent`
      · 本文件在 `tools/codex-scripts/` ⇒ `.parent` = `tools/codex-scripts`
      · `.parent.parent` = **`tools/`** ❌ —— 而它们读的是**仓根**的 `V*.html` / `gbt_allinone`
    ⇒ 现读抽样：`build_v8.py` / `build_v19.py` / `build_v20.py` **全部** `FileNotFoundError`
      （死在同一行 `read_text`），`build_hud_manifest.py` **`ModuleNotFoundError: gbt_allinone`**。
    ⇒ **这一整批脚本从"被挪进 codex-scripts/ 的那一天起就跑不动了"**，
      而面板里那份 `2026-09-21` 的快照（写着 `disabled: 11`）也就**再没人能重建**。

修法：统一换成**沿父链找 `gbt_allinone`** 的稳健写法（同目录里已有 33 个脚本这么写，
`verify-distill.py` / `omni.py` / `verify_v22.py` 都在其中）：
    BASE = next(p for p in Path(__file__).resolve().parents if (p / "gbt_allinone").is_dir())

用法：
  python tools/codex-scripts/fix-base-paths.py            # 只报告（dry-run）
  python tools/codex-scripts/fix-base-paths.py --apply    # 落盘
退出码：0 = 没有需要改的；1 = 还有（dry-run 时）；2 = 出错。
"""
from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = next(p for p in Path(__file__).resolve().parents if (p / "gbt_allinone").is_dir())
OLD = "BASE = Path(__file__).resolve().parent.parent"
NEW = ('BASE = next(p for p in Path(__file__).resolve().parents\n'
       '           if (p / "gbt_allinone").is_dir())   # 修：原 `.parent.parent` 只到 tools/（少一层）')
MARK = 'for p in Path(__file__).resolve().parents if (p / "gbt_allinone")'


def scan() -> tuple:
    todo, done = [], []
    for p in sorted(HERE.glob("*.py")):
        t = p.read_text(encoding="utf-8", errors="replace")
        if MARK in t:
            done.append(p.name)
        elif OLD in t:
            todo.append((p, t.count(OLD)))
    return todo, done


def main(argv) -> int:
    apply = "--apply" in argv
    todo, done = scan()
    print("仓根：%s" % ROOT)
    print("已是稳健写法（未动）：%d 个" % len(done))
    print("需要改：%d 个文件 / %d 处" % (len(todo), sum(n for _, n in todo)))
    for p, n in todo:
        print("   · %s（%d 处）" % (p.name, n))
    if not todo:
        return 0
    if not apply:
        print("\n（dry-run：加 --apply 才落盘）")
        return 1
    changed = 0
    for p, _ in todo:
        t = p.read_text(encoding="utf-8")
        p.write_text(t.replace(OLD, NEW), encoding="utf-8")
        changed += 1
    print("\n已改 %d 个文件。" % changed)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
