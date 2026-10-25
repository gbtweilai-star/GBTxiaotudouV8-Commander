# -*- coding: utf-8 -*-
"""修 .py 里「字符串内嵌同类引号」并报告 —— 顺带当机械闸用。

今晚同一个错犯了十次：写中文时习惯用 " " 包词，而外层定界符也是 "。
根因：**手比脑子快**。修法：① 中文引号一律 「」 ② 写完必跑本脚本。
"""
import ast
import pathlib
import re
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
targets = sys.argv[1:] or ["gbt_allinone/positions.py"]


def fix_line(line: str) -> str:
    """把一行里「内层成对的中文双引号」换成 「」。

    判据：**任何**含字符串字面量、且字面量内部又出现成对双引号的行。

    ⚠️ 2026-09-22 修：初版只认 `"key": "..."` 字典式，
       结果 `v["x"] = "...'内存充足'..."` 这种**赋值式**一个都没修到
       —— 闸自己有盲区，等于没闸。现在两种形态都认：
         ① `"key": "...."`            （字典/JSON 式）
         ② `xxx = "...."` / `("...." % ...)`（赋值/表达式式）
    """
    st = line
    for pat in (r'^(\s*"[^"]*":\s*)"(.*)",\s*$',          # ① 字典式
                r'^(\s*.*?=\s*)"(.*?)"\s*%?.*$'):          # ② 赋值式
        m = re.match(pat, st)
        if not m:
            continue
        inner = m.group(2)
        if inner.count('"') >= 2:
            fixed, op = [], True
            for ch in inner:
                if ch == '"':
                    fixed.append("「" if op else "」")
                    op = not op
                else:
                    fixed.append(ch)
            tail = st[m.end(2) + 1:]
            return f'{m.group(1)}"{"".join(fixed)}"{tail}'
    return line


total_fixed = 0
for t in targets:
    p = pathlib.Path(t)
    src = p.read_text(encoding="utf-8")
    lines = src.splitlines()
    out, fixed_here = [], []
    for i, ln in enumerate(lines, 1):
        n = fix_line(ln)
        if n != ln:
            fixed_here.append(i)
        out.append(n)
    p.write_text("\n".join(out) + "\n", encoding="utf-8")
    total_fixed += len(fixed_here)
    print(f"  {t}: 修 {len(fixed_here)} 行 {fixed_here[:8]}")

# ── 机械闸：语法过不过 ──
print()
bad = 0
for t in targets:
    try:
        ast.parse(pathlib.Path(t).read_text(encoding="utf-8-sig"))
        print(f"  ✔ {t} 语法 OK")
    except SyntaxError as e:
        bad += 1
        print(f"  ✘ {t} L{e.lineno}: {str(e.text or '').strip()[:90]}")
print(f"\n  共修 {total_fixed} 行 · 语法错 {bad} 处")
sys.exit(1 if bad else 0)
