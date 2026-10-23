#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""把 `verify_v11..v21` 里那 **11 条「永远不会红」的判据**改成真的能红。

由来（一手，2026-09-25）：
    `tools/codex-scripts/audit-dead-judgments.py` 现读点出 **11 个同族命中**：
        chk("原型无 undefined 字面量", "undefined" not in re.sub(…, p.split("const V21 = ")[1].split("\n  }")[0]) or True, …)
    两个毛病叠在一起：
      · 末尾 **`or True`** ⇒ 表达式恒真，**从出生起就不可能红**；
      · 它只取 `split("\n  }")[0]`，**只看了一小截**（嵌数据有一万多行）。
    ⇒ 我上一轮把面板嵌数据写坏时，这些门一声没吭 —— 这就是根。

修法（两处，逐文件同一刀）：
  1. 删掉 `or True`；
  2. 把"只看一小截"换成**从 `const V<n> = ` 之后到底**（不再 split 截断）。
  3. 顺手把 `re.sub(r"//[^\n]*", "", …)` 保留（剥行注释是对的，别把那条也扔了）。

用法：
  python tools/codex-scripts/fix-dead-undefined-check.py            # dry-run
  python tools/codex-scripts/fix-dead-undefined-check.py --apply
退出码：0 = 没有需要改的 或 已改；1 = dry-run 时还有待改。
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = next(p for p in Path(__file__).resolve().parents if (p / "gbt_allinone").is_dir())
HERE = Path(__file__).resolve().parent

PAT = re.compile(
    r'"undefined" not in re\.sub\(r"//\[\^\\n\]\*", "", (?P<var>[A-Za-z_][\w]*)\.split\("const (?P<gen>V\d+) = "\)\[1\]\.split\("\\n  \}"\)\[0\]\) or True'
)


def main(argv) -> int:
    apply = "--apply" in argv
    todo = []
    for p in sorted(HERE.glob("verify_v*.py")):
        t = p.read_text(encoding="utf-8", errors="replace")
        for m in PAT.finditer(t):
            todo.append((p, m.group(0), m.group("var"), m.group("gen")))
    print("找到 %d 处（应在 verify_v11..v21 里）" % len(todo))
    for p, hit, var, gen in todo:
        print("   · %s" % p.name)
    if not todo:
        return 0
    if not apply:
        print("\n（dry-run：加 --apply 才落盘）")
        return 1
    changed = 0
    for p, hit, var, gen in todo:
        t = p.read_text(encoding="utf-8")
        new = ('"undefined" not in re.sub(r"//[^\\n]*", "", %s.split("const %s = ")[1])'
               % (var, gen))
        t2 = t.replace(hit, new)
        if t2 != t:
            p.write_text(t2, encoding="utf-8")
            changed += 1
    print("\n已改 %d 个文件。" % changed)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
