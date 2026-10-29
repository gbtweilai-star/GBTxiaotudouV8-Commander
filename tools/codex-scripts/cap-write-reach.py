#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""写口**可达性**分析（只读静态）：从「api.py 的分派入口」一路 BFS 到写盘调用，回答
「这 41 位里，**真正走得到写盘**的有几个」。

为什么要有它：`caps-write-gate-census.py` 只能判「**该位所在模块**里有写盘原语」（模块级）。
反例已实测：`alerts` 的 `alerts()` 只调 `check_audit()` 就返回，写盘在同模块的 `_autofix()` 里。
⇒ 必须在**函数调用图**上判可达，否则 41 位是虚数。

口径（写死，可复核）：
  ① 入口 = `api.py` 里 `if kind == "<位>":` 分支体中第一处 `mod.func(...)` 或 `from . import mod` 后的调用；
     拿不到就记 `入口未解析`（**不猜**）。
  ② 调用图只覆盖**仓内**：同模块函数调用 `f()`、以及 `mod.f()`（mod 来自 `from . import mod`）；
     **跨到外部库/动态调用一律不追**（记 `未追`）。
  ③ 写盘点沿用 `cap-write-surface.py` 的口径（写原语名 或 open(mode 含 w/a/x/+)）。
  ④ 输出每位：可达 / 不可达（并给"为什么不可达"的最短一步）/ 入口未解析。

用法：py -3.14 tools/codex-scripts/cap-write-reach.py [--json]
"""
import argparse
import ast
import json
import os
import re
import sys
from collections import deque

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        pass

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PKG = os.path.join(ROOT, "gbt_allinone")
CENSUS = os.path.join(ROOT, "state", "caps_write_gate_census.json")
OUT = os.path.join(ROOT, "state", "caps_write_reach.json")
OUT_MD = os.path.join(ROOT, "outputs", "caps-census", "写口可达性.md")

WRITE_NAMES = {"write_text", "write_bytes", "rmtree", "move", "remove", "rename", "unlink",
               "makedirs", "truncate"}
MAX_DEPTH = 6
MAX_NODES = 4000


def is_write_call(node):
    f = node.func
    name = getattr(f, "id", None) or getattr(f, "attr", None)
    if name in WRITE_NAMES:
        return name
    if name == "open" and len(node.args) >= 2:
        m = node.args[1]
        if isinstance(m, ast.Constant) and isinstance(m.value, str) \
                and any(ch in m.value for ch in "wax+"):
            return "open(%s)" % m.value
    return None


class Mod:
    def __init__(self, name, path):
        self.name = name
        self.path = path
        self.src = open(path, encoding="utf-8", errors="replace").read()
        try:
            self.tree = ast.parse(self.src)
        except SyntaxError:
            self.tree = None
        self.imports = {}          # 别名 → 模块名（仓内）
        self.funcs = {}            # 函数名 → node
        if self.tree:
            for n in ast.walk(self.tree):
                if isinstance(n, ast.ImportFrom) and n.level == 1 and n.module:
                    for a in n.names:
                        self.imports[a.asname or a.name] = n.module
                elif isinstance(n, ast.ImportFrom) and n.level == 1 and not n.module:
                    for a in n.names:
                        self.imports[a.asname or a.name] = a.name
                elif isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    self.funcs[n.name] = n
                elif isinstance(n, ast.ImportFrom) and n.module and n.level == 0 \
                        and n.module.startswith("gbt_allinone"):
                    for a in n.names:
 # 2026-10-22 第一次跑就炸（留痕）：`from gbt_allinone import api` 这种
                        #    n.module 就是 "gbt_allinone" 本身，split 后取 [1] 会 IndexError。
                        #    不是"仓坏了"，是我的取法不覆盖"直接导入包根"的形状。
                        rel = n.module.split(".", 1)
                        self.imports[a.asname or a.name] = rel[1] if len(rel) > 1 else a.name

    def local_writes(self, fn_name):
        """该函数体内（不含更深层被调函数）的写盘点。"""
        n = self.funcs.get(fn_name)
        if not n:
            return []
        hits = []
        for sub in ast.walk(n):
            if isinstance(sub, ast.Call):
                w = is_write_call(sub)
                if w:
                    hits.append((sub.lineno, w))
        return hits

    def callees(self, fn_name):
        n = self.funcs.get(fn_name)
        if not n:
            return []
        out = []
        for sub in ast.walk(n):
            if isinstance(sub, ast.Call):
                f = sub.func
                if isinstance(f, ast.Name) and f.id in self.funcs:
                    out.append((self.name, f.id))
                elif isinstance(f, ast.Attribute):
                    base = getattr(f.value, "id", None)
                    if base in self.imports:
                        out.append((self.imports[base], f.attr))
        return out


class World:
    def __init__(self):
        self.mods = {}
        for f in sorted(os.listdir(PKG)):
            if f.endswith(".py"):
                name = f[:-3]
                try:
                    self.mods[name] = Mod(name, os.path.join(PKG, f))
                except OSError:
                    continue

    def get(self, name):
        return self.mods.get(name.split(".")[0])


def entry_of(api_src, kind):
    """从 api.py 取该位的入口 (模块, 函数)。只认第一处 `x.y(` 或 `y(` 调用。"""
    m = re.search(r'(?m)^    if kind == "%s":\s*$' % re.escape(kind), api_src)
    if not m:
        return None, "api.py 无分支"
    body = api_src[m.end():]
    nxt = re.search(r'(?m)^    if kind == "', body)
    body = body[:nxt.start()] if nxt else body
    imps = dict((a.split(" as ")[-1].strip(), a.split(" as ")[0].strip())
                for a in re.findall(r"from \. import ([A-Za-z0-9_, ]+)", body)[:1][0].split(",")) \
        if re.findall(r"from \. import ([A-Za-z0-9_, ]+)", body) else {}
    # 常见两种形状：`from . import X` + `return X.f(...)`；或 `from .security.x import Y` + `Y().f(...)`
    call = re.search(r'(?:return\s+)?([A-Za-z_][A-Za-z0-9_]*)\.([A-Za-z_][A-Za-z0-9_]*)\(', body)
    if call:
        base, fn = call.group(1), call.group(2)
        mod = imps.get(base, base)
        return (mod.split(".")[-1], fn), None
    return None, "入口未解析（分支体里没有 mod.func( 形状）"


def reach(world, mod_name, fn, seen=None, depth=0):
    """BFS/DFS：返回 (可达的写盘点列表, 访问过的节点数, 断点原因)。"""
    if depth > MAX_DEPTH:
        return [], 0, "超出深度上限 %d" % MAX_DEPTH
    seen = seen or set()
    key = (mod_name, fn)
    if key in seen or len(seen) > MAX_NODES:
        return [], 0, None
    seen.add(key)
    m = world.get(mod_name)
    if not m or not m.tree:
        return [], 0, "模块/语法读不到：%s" % mod_name
    hits = m.local_writes(fn)
    if hits:
        return [{"mod": mod_name, "func": fn, "line": ln, "call": w} for ln, w in hits], 1, None
    total = 1
    for cm, cf in m.callees(fn):
        sub, n, why = reach(world, cm, cf, seen, depth + 1)
        total += n
        if sub:
            return sub, total, None
        if why and why.startswith("模块"):
            continue
    return [], total, None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    if not os.path.isfile(CENSUS):
        print("先跑 caps-write-gate-census.py")
        return 2
    cen = json.load(open(CENSUS, encoding="utf-8"))
    risky = [r for r in (cen.get("rows") or [])
             if str(r.get("bucket") or "").startswith("零作用域·模块有写口")]
    api_src = open(os.path.join(PKG, "api.py"), encoding="utf-8").read()
    world = World()
    rows = []
    for r in risky:
        ent, why = entry_of(api_src, r["cap"])
        if not ent:
            rows.append({"cap": r["cap"], "domain": r["domain"], "entry": None,
                         "reachable": None, "why": why, "sites": [], "visited": 0})
            continue
        mod, fn = ent
        sites, visited, why2 = reach(world, mod, fn)
        rows.append({"cap": r["cap"], "domain": r["domain"], "entry": "%s.%s" % (mod, fn),
                     "reachable": bool(sites), "why": why2, "sites": sites[:6], "visited": visited})
    n_reach = sum(1 for r in rows if r["reachable"] is True)
    n_unres = sum(1 for r in rows if r["reachable"] is None)
    n_no = sum(1 for r in rows if r["reachable"] is False)
    out = {"at": __import__("time").strftime("%Y-%m-%dT%H:%M:%S%z"),
           "risky_total": len(rows), "reachable": n_reach, "not_reachable": n_no,
           "entry_unresolved": n_unres, "rows": rows,
           "note": "可达=从分派入口沿仓内调用图能走到写盘调用；跨库/动态调用不追（记未追）"}
    tmp = OUT + ".tmp"
    with open(tmp, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(out, fh, ensure_ascii=False, indent=1)
        fh.write("\n")
    os.replace(tmp, OUT)
    if a.json:
        print(json.dumps({k: v for k, v in out.items() if k != "rows"}, ensure_ascii=False, indent=2))
        return 0
    os.makedirs(os.path.dirname(OUT_MD), exist_ok=True)
    lines = ["# 写口**可达性**（从分派入口到写盘，只读静态）", "",
             "> 生成：`py -3.14 tools/codex-scripts/cap-write-reach.py` · %s" % out["at"],
             "> 口径：入口取 `api.py` 该位分支里的第一处 `mod.func(`；只追**仓内**同模块/`from . import` 调用；"
             "跨库与动态调用**不追**。",
             "", "## 汇总（41 位）", "",
             "| 结论 | 位数 |", "|---|---|",
             "| **可达写盘**（真风险） | **%d** |" % n_reach,
             "| 不可达（模块里有写口，但入口走不到） | %d |" % n_no,
             "| 入口未解析（不猜） | %d |" % n_unres, "",
             "## 可达的那些（真风险，逐个附路径）", ""]
    for r in rows:
        if r["reachable"]:
            lines.append("- `%s`（%s）入口 `%s` → 写盘：%s"
                         % (r["cap"], r["domain"], r["entry"],
                            "、".join("`%s:%s` %s" % (s["mod"], s["line"], s["call"]) for s in r["sites"])))
    lines += ["", "## 不可达的（模块级有写口，但入口走不到 —— 这一批从风险名单里划掉）", ""]
    lines.append("、".join("`%s`" % r["cap"] for r in rows if r["reachable"] is False) or "（无）")
    if n_unres:
        lines += ["", "## 入口未解析（需要人看一眼 api.py 的分派形状）", ""]
        lines.append("、".join("`%s`" % r["cap"] for r in rows if r["reachable"] is None))
    tmp_md = OUT_MD + ".tmp"
    with open(tmp_md, "w", encoding="utf-8", newline="\n") as fh:
        fh.write("\n".join(lines) + "\n")
    os.replace(tmp_md, OUT_MD)
    print("写口可达性：41 位 → **可达 %d** · 不可达 %d · 入口未解析 %d" % (n_reach, n_no, n_unres))
    for r in rows:
        if r["reachable"]:
            print("  可达：%-18s 入口 %-28s → %s" % (r["cap"], r["entry"],
                                                "、".join("%s:%s %s" % (s["mod"], s["line"], s["call"]) for s in r["sites"][:2])))
    print("  人读：%s" % OUT_MD)
    return 0


if __name__ == "__main__":
    sys.exit(main())
