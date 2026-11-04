# -*- coding: utf-8 -*-
"""把 C:\\Users\\ADMIN 硬编码改为运行时解析（payload 根 / 用户家目录）。

只改「真当值用的路径字面量」：
  · 跳过 测试夹具/探针里的故意假路径（tests/、verify_loader_scope*、quickscan_evolve）
  · 跳过 docstring 里记录的路径证据
  · 遇到 Path(<字面量>) 时连外层 Path( 一起换掉，避免写出 Path(Path(__file__)...)
用法：
  python _fix_admin_paths.py            # 干跑，只报告
  python _fix_admin_paths.py --apply    # 实改
"""
import ast
import io
import re
import shutil
import sys
import tempfile
import tokenize
from pathlib import Path

PAYLOAD = Path(__file__).resolve().parent
SKIP_PARTS = {"outputs", "state", "_gbt_bak_archive", "pyembed", "node_modules", ".git", "__pycache__"}
SKIP_NAMES = {"verify_loader_scope.py", "verify_loader_scope2.py", "quickscan_evolve.py"}
TRIVIA = (tokenize.COMMENT, tokenize.NL, tokenize.NEWLINE, tokenize.INDENT, tokenize.DEDENT)
ADMIN_RE = re.compile(r"(?i)^c:[/\\]+users[/\\]+admin(?:[/\\](.*))?$")
DOTSLASH_RE = re.compile(r"(?i)^/c:/users/admin(?:/(.*))?$")
PATH_CALL_RE = re.compile(r"(?:pathlib\.)?Path\(\s*$")
# 源码里的字面量可能是 r"C:\Users\ADMIN" 也可能写成 "C:\\Users\\ADMIN"，
# 所以判存在必须走正则，不能直接比单个反斜杠
ADMIN_IN_TOKEN = re.compile(r"(?i)users[/\\]{1,4}admin")


def starts_statement(idx, toks):
    i = idx - 1
    while i >= 0 and toks[i].type in TRIVIA:
        i -= 1
    if i < 0:
        return True
    return toks[i].type in (tokenize.NEWLINE, tokenize.INDENT, tokenize.DEDENT)


def pick_path_name(src):
    if re.search(r"^\s*from\s+pathlib\s+import\s+[^\n]*\bPath\b", src, re.M):
        return "Path"
    if re.search(r"^\s*import\s+pathlib", src, re.M):
        return "pathlib.Path"
    return '__import__("pathlib").Path'


def build(value, depth, pn):
    """返回 (表达式, 类别)；不该改则 None。表达式一律是 Path 对象。"""
    v = value.strip()
    m = ADMIN_RE.match(v)
    dotted = False
    if not m:
        m = DOTSLASH_RE.match(v)
        dotted = bool(m)
    if not m:
        return None
    rest = (m.group(1) or "").replace("/", "\\")
    parts = [p for p in rest.split("\\") if p]
    if parts[:2] == ["Desktop", "GBT小土豆V8"]:
        expr, kind, segs = f"{pn}(__file__).resolve().parents[{depth}]", "repo", parts[2:]
    elif parts[:3] == ["Desktop", "GBT小土豆V8桌面版", "payload"]:
        expr, kind, segs = f"{pn}(__file__).resolve().parents[{depth}]", "repo", parts[3:]
    else:
        expr, kind, segs = f"{pn}.home()", "home", parts
    for s in segs:
        expr += f' / "{s}"'
    if dotted:
        # 原值形如 "/C:/.../AGENTS.md"：前导斜杠 + 正斜杠，两样都要还原
        return f'"/" + str({expr}).replace("\\\\", "/")', kind + ":url"
    return expr, kind


def process(p: Path, depth: int, write: bool):
    src = p.read_text(encoding="utf-8")
    if "admin" not in src.lower():
        return []
    try:
        toks = list(tokenize.generate_tokens(io.StringIO(src).readline))
    except Exception as e:  # noqa: BLE001
        return [(0, f"TOKENIZE_FAIL {e}", False)]
    lines = src.splitlines(keepends=True)
    pn, edits, report = None, [], []
    for idx, t in enumerate(toks):
        if t.type != tokenize.STRING:
            continue
        if not ADMIN_IN_TOKEN.search(t.string):
            continue
        if starts_statement(idx, toks):
            report.append((t.start[0], "SKIP docstring", False))
            continue
        if t.start[0] != t.end[0]:
            report.append((t.start[0], "SKIP multiline", False))
            continue
        try:
            value = ast.literal_eval(t.string)
        except Exception:
            report.append((t.start[0], "SKIP unparsable", False))
            continue
        if not isinstance(value, str):
            continue
        srow, scol = t.start
        erow, ecol = t.end
        wrap = PATH_CALL_RE.search(lines[srow - 1][:scol])
        if pn is None:
            pn = pick_path_name(src)
        built = build(value, depth, pn)
        if not built:
            report.append((srow, f"SKIP no-match {value[:36]}", False))
            continue
        expr, kind = built
        if wrap and not kind.endswith(":url"):
            tail = re.match(r"\s*\)", lines[erow - 1][ecol:])
            if tail:
                scol, ecol = wrap.start(), ecol + tail.end()
            else:
                expr = f"str({expr})"
        elif not kind.endswith(":url"):
            expr = f"str({expr})"
        edits.append(((srow, scol), (erow, ecol), expr))
        report.append((srow, f"{kind} -> {expr}", True))
    if not edits or not write:
        return report
    for (sr, sc), (er, ec), expr in sorted(edits, key=lambda e: (e[0][0], e[0][1]), reverse=True):
        line = lines[sr - 1]
        lines[sr - 1] = line[:sc] + expr + line[ec:]
    p.write_text("".join(lines), encoding="utf-8")
    return report


def candidates():
    for p in sorted(PAYLOAD.rglob("*.py")):
        rel = p.relative_to(PAYLOAD)
        if any(part in SKIP_PARTS for part in rel.parts):
            continue
        if p.name in SKIP_NAMES or "tests" in rel.parts or p.name.startswith("_"):
            continue
        try:
            src = p.read_text(encoding="utf-8", errors="replace")
        except Exception:
            continue
        if not ADMIN_IN_TOKEN.search(src):
            continue
        yield p, rel, len(rel.parts) - 1


def main():
    apply = "--apply" in sys.argv
    nf = ne = 0
    for p, rel, depth in candidates():
        if apply:
            rep = process(p, depth, True)
        else:
            tmp = Path(tempfile.gettempdir()) / f"dry_{abs(hash(str(rel)))}.py"
            shutil.copy2(p, tmp)
            rep = process(tmp, depth, True)
            tmp.unlink(missing_ok=True)
        changed = [r for r in rep if r[2]]
        if not changed and not rep:
            continue
        if changed:
            nf += 1
            ne += len(changed)
        if not apply or changed:
            print(f"\n## {rel}  depth={depth}")
            for ln, msg, ok in rep:
                print(f"  {ln:>5}  {'>>' if ok else '  '} {msg}")
    print(f"\n{'APPLIED' if apply else 'DRY-RUN'}: {nf} files / {ne} path literals")


if __name__ == "__main__":
    main()
