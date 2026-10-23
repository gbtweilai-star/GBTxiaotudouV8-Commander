#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""把「零作用域·有写口」那批位**逐个摊开**：写到哪、在哪个函数、有没有 op 门（只读，不跑位）。

为什么需要（承接 `caps-write-gate-census.py` 的 41 位风险档）：
  静态分档只说"这门不拦、代码里有写盘原语"。但主人要问的是**写到哪、写什么**。
  本件对每个这样的位：定位它的 handler 模块，AST 找写盘调用点，输出
  （函数名:行号 · 写原语 · 目标表达式原文 · 该函数里有没有 `op` 判断）。
  **一行代码都不执行**，也不写任何业务文件。

用法：py -3.14 tools/codex-scripts/cap-write-surface.py [--json]
"""
import argparse
import ast
import json
import os
import sys

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        pass

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CENSUS = os.path.join(ROOT, "state", "caps_write_gate_census.json")
OUT_MD = os.path.join(ROOT, "outputs", "caps-census", "零作用域写口明细.md")
OUT_JSON = os.path.join(ROOT, "state", "caps_write_surface.json")

WRITE_NAMES = {"write_text", "write_bytes", "rmtree", "move", "remove", "rename", "unlink",
               "makedirs", "truncate"}


def enclosing(tree):
    """行号 → 所在函数名。"""
    spans = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            spans.append((node.lineno, max(getattr(node, "end_lineno", node.lineno), node.lineno),
                          node.name))
    def name_of(line):
        best = None
        for lo, hi, nm in spans:
            if lo <= line <= hi and (best is None or lo > best[0]):
                best = (lo, nm)
        return best[1] if best else "<模块级>"
    return name_of


def guards(tree):
    """函数名 → 里面有没有出现 `op` 的判断（粗判：函数体内有 if 且引用了 op 变量）。"""
    out = {}
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            has = False
            for sub in ast.walk(node):
                if isinstance(sub, (ast.If, ast.IfExp)):
                    for n2 in ast.walk(sub.test):
                        if isinstance(n2, ast.Name) and n2.id == "op":
                            has = True
                if isinstance(sub, ast.Compare):
                    for n2 in ast.walk(sub):
                        if isinstance(n2, ast.Name) and n2.id == "op":
                            has = True
            out[node.name] = has
    return out


def analyze(path):
    src = open(path, encoding="utf-8", errors="replace").read()
    try:
        tree = ast.parse(src)
    except SyntaxError as e:
        return [{"error": "AST 解析失败：%s" % e}]
    nm = enclosing(tree)
    gd = guards(tree)
    hits = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        f = node.func
        name = getattr(f, "id", None) or getattr(f, "attr", None)
        target = None
        matched = False
        # 🔴 2026-10-22 自纠（第 10 次，留痕）：原版把 `hits.append` 写在过滤**外面**，
        #    于是 `resolve` / `frozenset` / `splitlines` / `loads` 全被当成"写盘原语"，
        #    一口气报出 492 个写盘点（其中 420 个"无 op 门"）—— **那是量具自己的假读数**。
        #    现口径：只有**真命中**（写盘原语名，或 open 且 mode 含 w/a/x/+）才记一条。
        if name in WRITE_NAMES:
            tgt = node.func
            if isinstance(tgt, ast.Attribute):
                try:
                    target = ast.unparse(tgt.value)
                except Exception:  # noqa: BLE001
                    target = "?"
            else:
                if node.args:
                    try:
                        target = ast.unparse(node.args[0])
                    except Exception:  # noqa: BLE001
                        target = "?"
            matched = True
        elif name == "open" and len(node.args) >= 2:
            mode = node.args[1]
            if isinstance(mode, ast.Constant) and isinstance(mode.value, str) \
                    and any(ch in mode.value for ch in "wax+"):
                name = "open(%s)" % mode.value
                try:
                    target = ast.unparse(node.args[0])
                except Exception:  # noqa: BLE001
                    target = "?"
                matched = True
        if not matched:
            continue
        fn = nm(node.lineno)
        hits.append({"line": node.lineno, "func": fn, "call": name,
                     "target": (target or "")[:160], "op_guarded": gd.get(fn)})
    return hits


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    if not os.path.isfile(CENSUS):
        print("先跑 caps-write-gate-census.py（缺 %s）" % CENSUS)
        return 2
    cen = json.load(open(CENSUS, encoding="utf-8"))
    risky = [r for r in (cen.get("rows") or [])
             if str(r.get("bucket") or "").startswith("零作用域·模块有写口")]
    rows = []
    cache = {}
    for r in risky:
        p = r.get("handler_file")
        full = os.path.join(ROOT, p) if p else None
        if not full or not os.path.isfile(full):
            rows.append({"cap": r["cap"], "domain": r["domain"], "handler_file": p,
                         "sites": [], "error": "handler 文件读不到"})
            continue
        if full not in cache:
            cache[full] = analyze(full)
        rows.append({"cap": r["cap"], "domain": r["domain"], "handler_file": p,
                     "sites": cache[full][:12]})
    out = {"at": __import__("time").strftime("%Y-%m-%dT%H:%M:%S%z"),
           "risky_count": len(risky), "rows": rows}
    tmp = OUT_JSON + ".tmp"
    with open(tmp, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(out, fh, ensure_ascii=False, indent=1)
        fh.write("\n")
    os.replace(tmp, OUT_JSON)
    if a.json:
        print(json.dumps({"risky_count": len(risky)}, ensure_ascii=False))
        return 0

    os.makedirs(os.path.dirname(OUT_MD), exist_ok=True)
    lines = ["# 零作用域但会写盘：41 位逐个摊开（只读静态分析，未执行任何能力位）", "",
             "> 生成：`py -3.14 tools/codex-scripts/cap-write-surface.py` · %s" % out["at"],
             "> 读法：**`op门=是`** 表示写盘只发生在某个具体 op 分支里（那个 op 可能另外挂了作用域）；"
             "**`op门=否`** 表示这个函数里看不到 op 判断 —— 那才是「门不拦、又会写」的真风险。",
             ""]
    for r in rows:
        lines += ["## `%s`（域 %s）· %s" % (r["cap"], r["domain"], r["handler_file"]), ""]
        if r.get("error"):
            lines += ["- ⚠️ %s" % r["error"], ""]
            continue
        if not r["sites"]:
            lines += ["- （AST 里没找到写盘调用点）", ""]
            continue
        lines += ["| 行 | 函数 | 写原语 | 目标 | op门 |", "|---|---|---|---|---|"]
        for s in r["sites"]:
            lines.append("| %s | `%s` | `%s` | `%s` | %s |"
                         % (s.get("line"), s.get("func"), s.get("call"),
                            (s.get("target") or "").replace("|", "\\|")[:90],
                            "是" if s.get("op_guarded") else "**否**"))
        lines.append("")
    tmp_md = OUT_MD + ".tmp"
    with open(tmp_md, "w", encoding="utf-8", newline="\n") as fh:
        fh.write("\n".join(lines) + "\n")
    os.replace(tmp_md, OUT_MD)
    unguarded = sum(1 for r in rows for s in r.get("sites") or [] if s.get("op_guarded") is False)
    print("风险档 %d 位 → 摊开写盘点 %d 个（其中 **函数内无 op 门** %d 个）"
          % (len(rows), sum(len(r.get("sites") or []) for r in rows), unguarded))
    print("  人读：%s" % OUT_MD)
    return 0


if __name__ == "__main__":
    sys.exit(main())
