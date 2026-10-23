#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""把「编码守门」那 4 行补进缺守门的件里（机械操作，先 dry-run 再落盘）。

背景（判据本体：tools/codex-scripts/encoding-guard-check.py）
  闸的口径：会印非 ASCII 的 .py，在入口必须 reconfigure stdout/stderr 为 utf-8，
  否则中文 Windows 控制台（cp936）会抛 UnicodeEncodeError ⇒ stdout 为空 ⇒
  调用方把空读数当成"没结果"（P11 假读数一族）。
  存量 151 件登在基线里不红；**新件再犯必红**（棘轮只缩不长）。

本件只做一件事：给「基线外又没守门」的那批件补上同样的 4 行，补完逐个 py_compile 验证；
编译失败就当场回滚那一个文件（绝不把坏件留在盘上）。

用法：
  py -3.14 tools/codex-scripts/add-encoding-guard.py --dry-run
  py -3.14 tools/codex-scripts/add-encoding-guard.py --apply
"""
import argparse
import json
import os
import py_compile
import re
import subprocess
import sys
import tempfile

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        pass

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
GUARD = (
    "for _s in (sys.stdout, sys.stderr):\n"
    "    try:\n"
    '        _s.reconfigure(encoding="utf-8", errors="replace")\n'
    "    except Exception:  # noqa: BLE001\n"
    "        pass\n"
)
MARK = "_s.reconfigure(encoding=\"utf-8\""


def violators():
    """从闸自己嘴里拿名单（不自己造第二份判据）：走它的 --json，拿**全量 38 个**名字。"""
    r = subprocess.run([sys.executable, "-X", "utf8",
                        os.path.join(ROOT, "tools", "codex-scripts", "encoding-guard-check.py"),
                        "--json"],
                       cwd=ROOT, capture_output=True)
    out = r.stdout.decode("utf-8", "replace")
    i = out.find("{")
    if i < 0:
        return None, []
    j = json.loads(out[i:])
    names = list(j.get("new_bad") or [])
    return len(names), names


def find_insert_index(lines):
    """插到「文件头的 import 段」之后；找不到就插在 shebang/编码行之后。"""
    last_import = None
    in_doc = False
    quote = None
    for i, line in enumerate(lines[:160]):
        s = line.strip()
        if in_doc:
            if quote and quote in s:
                in_doc = False
            continue
        if not s:
            continue
        if s.startswith("#"):
            continue
        if last_import is None:
            for q in ('"""', "'''"):
                if s.startswith(q):
                    if s.count(q) == 1:
                        in_doc = True
                        quote = q
                    break
            else:
                if re.match(r"^(import|from)\s+\S+", line):
                    last_import = i
                elif re.match(r"^[A-Za-z_]", s):
                    break
            continue
        if re.match(r"^(import|from)\s+\S+", line):
            last_import = i
        elif re.match(r"^[A-Za-z_]", s):
            break
    if last_import is not None:
        return last_import + 1
    for i, line in enumerate(lines[:6]):
        if line.startswith("#!") or "coding" in line:
            return i + 1
    return 0


def patch(path):
    full = os.path.join(ROOT, path)
    src = open(full, encoding="utf-8", errors="replace").read()
    if MARK in src:
        return "already"
    lines = src.splitlines(keepends=True)
    idx = find_insert_index(lines)
    need_sys = not re.search(r"(?m)^(import sys|from sys import)", src)
    block = []
    if need_sys:
        block.append("import sys\n")
    if idx > 0 and not lines[idx - 1].endswith("\n"):
        lines[idx - 1] = lines[idx - 1] + "\n"
    block.append(GUARD)
    lines[idx:idx] = block
    new = "".join(lines)
    # 落盘（临时件 → 原子替换，避免半截文件）
    fd, tmp = tempfile.mkstemp(prefix=".encguard-", suffix=".py", dir=os.path.dirname(full))
    with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(new)
    try:
        py_compile.compile(tmp, doraise=True)
    except Exception:  # noqa: BLE001
        os.unlink(tmp)
        return "syntax-fail"
    os.replace(tmp, full)
    return "patched"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    count, names = violators()
    print("闸现报：新增违规 %s 件，名单 %d 个" % (count, len(names)))
    if not names:
        print("名单为空 —— 闸的输出格式变了？按原样如实报，不猜。")
        return 2
    for n in names:
        # 闸只报文件名（它扫的是 tools/codex-scripts 这一层）；补成仓库相对路径再判在不在。
        rel = n if os.sep in n else os.path.join("tools", "codex-scripts", n)
        if not os.path.exists(os.path.join(ROOT, rel)):
            print("  未读到（按原样如实报，不猜）：", n)
            continue
        if not a.apply:
            print("  [dry-run] 将补守门：", rel)
            continue
        r = patch(rel)
        print(("  ✅ %s → %s" % (rel, r)) if r in ("patched", "already") else ("  🔴 %s → %s" % (rel, r)))
    if not a.apply:
        print("\n（dry-run：一字节没动。要落盘加 --apply）")
        return 0
    count2, names2 = violators()
    print("\n复跑闸：新增违规 %s 件" % count2)
    return 0 if count2 == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
