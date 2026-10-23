#!/usr/bin/env python -3.14
# -*- coding: utf-8 -*-
"""criterion_bench · 判据质量台架 —— 自动找出「坏判据」

开发者：自由的风 · 守护者：公主土豆 · 禁止删除

## 为什么造这个（主人令 2026-09-25：「把编程技术发挥到极致…不断突破技术层面探索未知」）
本仓 18 轮里反复出现的缺陷**只有一类**：**判据坏了**。已经**修一个补一个修了约 20 次**
（F31/F32/F34/F35/F36/F37/F38/F39 + 自指判据 + 计数项含计数器 + 用 0 冒充…）。
**修单个 bug 是手艺；造一台能发现这一整类的机器才是突破。**
本工具就是那台机器：它把「我踩过的坑」变成**可复跑的检测器**。

## 检测器（**全部 AST 判据** —— 因为"文本判据"本身就是被检测的坑之一）
D1 恒真判据     `all(... for _ in [1])` · `x == x` · `or True` · `if True:`
D2 文本子串判据  `"字面量" in src/txt/text`（自指风险：判据可能匹配到它自己）
D3 用 0 冒充    一个函数里既有 `.get(k, {})`/`len(...)`，**又完全没有「未读到」出路**
D4 死代码       `if False:` · 恒不执行的 `while False:`
D5 判据与自己比  `x == x` / `x != x`（与 D1 同族，单列以便定位）

## 铁律
- **每个检测器都必须有负控**：种一段真缺陷进去，**必须被咬出来**（`selftest` 里逐条验）；
- 还要有**假阳性控制**：一段干净代码**不许被误报**；
- 台架**自己**不许用文本判据（本文件里对源码的扫描全部走 AST）。

用法：
  criterion_bench.py scan                # 扫全仓自检/闸，列坏判据
  criterion_bench.py scan --roots tools  # 指定根
  criterion_bench.py settle              # 立基线（棘轮：以后只许变少不许变多）
  criterion_bench.py check               # 与基线比：变坏 rc=1
  criterion_bench.py selftest
"""
from __future__ import annotations

import argparse
import ast
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / "state" / "criterion-baseline.json"
DEFAULT_ROOTS = ("tools", "tools/codex-scripts", "gbt_allinone/tools")

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# 可能装着源码文本的变量名（用于 D2 的自指风险判断）
TEXTISH = re.compile(r"^(src|txt|text|blob|body|out|s|raw|content|source)$")
# 🔴 **单一来源**：检测器只在这里列一次。
#    原来 `DETECTORS` / `scan_file` / `selftest` 各列一遍 —— **加一个检测器忘了改一处
#    就会静默漏检**（维护隐患）。现在全部从这张表派生，并有一条自检咬「两处是否一致」。


def d7_position_as_existence(tree) -> list:
    """D7 **位置型存在性判据**：拿「**某个位置**」当「**有没有**」用。

    🔴 真案例（2026-09-25，我自己的）：查「`docs/` 页面有没有署名」时，
    我用的是 `Get-Content … -Tail 1 | -match 署名` —— **只查最后一行**，
    而报告里署名在**开头附近**、末行是生成器说明 ⇒ **把「末行不是署名」念成了「没有署名」**，
    差点去改两份**根本没坏**的文件。**位置 ≠ 存在。**

    机检形状（只认"被查的是 `[-1]`"这一种，宁窄不宽）：
      ① `MARK in X[-1]` / `MARK not in X[-1]`
      ② `X[-1].startswith(MARK)` / `X[-1].endswith(MARK)`
    一律记 🟡 **提示**（它可能只是"解析末行"的正当写法）——
    **但它必须被看见**：这类判据一旦被当成"存在性"结论用，就会给出假否定。

    （与 §一百四十四 那条同型：「**在哪里定义**」和「**叫什么名字**」是两件事。）
    """
    out = []
    for n in ast.walk(tree):
        # ① `MARK in X[-1]` / `MARK not in X[-1]`
        if isinstance(n, ast.Compare):
            for op, comp in zip(n.ops, n.comparators):
                if not isinstance(op, (ast.In, ast.NotIn)):
                    continue
                for side in (n.left, comp):
                    if isinstance(side, ast.Subscript) and _index_like(side.slice):
                        out.append((getattr(n, "lineno", 0),
                                    "🟡 位置型存在性：`… in %s[-1]` —— **末行有 ≠ 全文有**"
                                    % _subj_name(side)))
                        break
        # ② `X[-1].startswith/endswith(MARK)`
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) \
                and n.func.attr in ("startswith", "endswith"):
            v = n.func.value
            if isinstance(v, ast.Subscript) and _index_like(v.slice):
                out.append((getattr(n, "lineno", 0),
                            "🟡 位置型存在性：`%s[-1].%s(…)` —— **位置判断答不了「有没有」**"
                            % (_subj_name(v), n.func.attr)))
    return out


def _index_like(sl) -> bool:
    """**尾部位置**：负下标常量（`[-1]` / `[-2]` …）。

    🔴 2026-09-25 **量过信噪比才收窄的**（这一步比推广本身重要）：
      第一版只认 `[-1]` ⇒ **3 处命中**；
      推广成"任意下标常量 + `pop()`" ⇒ **46 处命中**，我抽查 8 条，
      **全是"操作首/末元素"的正当代码**（`lines[-1]` 解析末行、`c[-1].endswith(".py")` 取末项…），
      **不是**"拿位置答存在"。⇒ **噪 > 信，收窄。**
    ⇒ 只留**尾部位置**（负下标）—— 那正是**我真正犯错**的形状：
      从"文件的尾部一片"去回答"整个文件有没有 X"。
      **`[0]`（首元素）与 `pop()` 不收**：前者在正当代码里太常见，后者与"存在性"无关。
    **教训：加广覆盖面之前，先量信噪比；不然"覆盖面变大"会被念成"质量变好"。**
    """
    return (isinstance(sl, ast.UnaryOp) and isinstance(sl.op, ast.USub)
            and isinstance(sl.operand, ast.Constant) and isinstance(sl.operand.value, int))


def _subj_name(node) -> str:
    v = getattr(node, "value", None)
    if isinstance(v, ast.Call) and isinstance(v.func, ast.Attribute):
        return "…" + v.func.attr + "()"
    if isinstance(v, ast.Name):
        return v.id
    return "…"


DETECTOR_FUNCS = (
    ("D1 恒真判据", lambda tree, text: d1_always_true(tree)),
    ("D2 文本子串判据", lambda tree, text: d2_text_criterion(tree, text)),
    ("D6 自指判据（高危）", lambda tree, text: d6_self_reference(tree, text)),
    ("D3 用0冒充", lambda tree, text: d3_zero_masquerade(tree)),
    ("D4 死代码", lambda tree, text: d4_dead_code(tree)),
    ("D5 判据与自己比", lambda tree, text: d5_self_compare(tree)),
    ("D7 位置型存在性判据", lambda tree, text: d7_position_as_existence(tree)),
)
DETECTORS = tuple(n for n, _ in DETECTOR_FUNCS)


def run_detectors(tree, text: str) -> dict:
    """一次性跑全部检测器 → {检测器名: [(行, 为什么)…]}。"""
    return {name: fn(tree, text) for name, fn in DETECTOR_FUNCS}


# ── 检测器 ─────────────────────────────────────────────────────────────────────
def _lit(node):
    """字面量列表/元组 → 元素列表；否则 None。"""
    if isinstance(node, (ast.List, ast.Tuple)):
        return list(node.elts)
    return None


def d1_always_true(tree) -> list:
    """恒真判据：`all(... for _ in [1])` · `x == x` · `or True` · `if True:`"""
    out = []
    for n in ast.walk(tree):
        # all(...)/any(...) 迭代的是**单元素字面量**且**元素没用到那个循环变量** ⇒ 才恒真
        # 🔴 **第一版漏了后半句** ⇒ 把 `any(k in r for k in ("静帧",))` 误判成恒假
        #    （`media_run.py:398`）—— 那个元素**用到了 `k`**，条件**依赖数据**。
        #    **读代码才发现：这是假阳性，不是框架的缺陷。** 已补"元素是否用到循环变量"。
        if (isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
                and n.func.id in ("all", "any") and n.args
                and isinstance(n.args[0], ast.GeneratorExp)):
            g = n.args[0]
            it = g.generators[0].iter if g.generators else None
            els = _lit(it) if it is not None else None
            tgt = g.generators[0].target if g.generators else None
            tnames = {tgt.id} if isinstance(tgt, ast.Name) else set()
            used = any(isinstance(x, ast.Name) and x.id in tnames for x in ast.walk(g.elt))
            if els is not None and len(els) == 1 and not used:
                out.append((n.lineno, "%s(... for _ in [%s]) —— 迭代的是**单元素字面量**，"
                                      "且**元素没用到循环变量** ⇒ 条件与数据无关 ⇒ 恒%s"
                            % (n.func.id, ast.unparse(els[0])[:20],
                               "真" if n.func.id == "all" else "假")))
        if isinstance(n, ast.BoolOp) and isinstance(n.op, ast.Or):
            if any(isinstance(v, ast.Constant) and v.value is True for v in n.values):
                out.append((n.lineno, "`or True` —— 短路后判据恒真"))
        if isinstance(n, ast.If) and isinstance(n.test, ast.Constant) and n.test.value is True:
            out.append((n.lineno, "`if True:` —— 分支恒执行"))
    return out


def d2_text_criterion(tree, src_text: str) -> list:
    """文本子串判据：`"字面量" in <可能是源码的变量>`（自指风险）。"""
    out = []
    for n in ast.walk(tree):
        if not isinstance(n, ast.Compare):
            continue
        for op, comp in zip(n.ops, n.comparators):
            if not isinstance(op, (ast.In, ast.NotIn)):
                continue
            left, right = n.left, comp
            if not (isinstance(left, ast.Constant) and isinstance(left.value, str)):
                continue
            rname = right.id if isinstance(right, ast.Name) else ""
            if not TEXTISH.match(rname):
                continue
            # 自指铁证：这个字面量在**同一文件**里也作为字面量出现过（很可能是判据自己列的）
            cnt = src_text.count('"%s"' % left.value) + src_text.count("'%s'" % left.value)
            selfref = ("🔴 **自指**：该字面量在本文件里出现 %d 次（判据可能匹配到自己）" % cnt
                       if cnt >= 2 else "（未见自指，但文本判据仍弱：源码里的注释/字符串也会命中）")
            out.append((n.lineno, '`"%s" %s %s` —— 文本判据 %s'
                        % (left.value[:24], "in" if isinstance(op, ast.In) else "not in",
                           rname, selfref)))
    return out


# 「真的在读某个**可能不存在的东西**」的函数名 —— D3 的前提
READISH = ("read_text", "read_bytes", "readlines", "open", "urlopen",
           "loads", "safe_load", "_json", "_load", "load_settings", "load_registry")
# 「未读到」出路的关键字（AST 查字符串常量，不查源码文本）
UNREAD_KEYS = ("未读到", "读不到", "不在", "缺失")


# 「定胜负」的调用名 —— 它的实参就是判据本身
CHECKER_CALLS = ("ck", "_ck", "expect", "require", "assert_")
CHECKER_PREFIX = ("assert", "verify", "check")


def _parents(tree) -> dict:
    par = {}
    for n in ast.walk(tree):
        for c in ast.iter_child_nodes(n):
            par[c] = n
    return par


def _in_deciding_position(node, par) -> bool:
    """这个表达式是不是在**定胜负的位置**：`return` 里 · 或作为检查器函数的实参。

    🔴 **这一格是读代码逼出来的**（§一百一十八）：`stigmergy.py:315` 的
    `"locked_append_text" in src` 恒真是**故意的廉价前置筛**，真正定胜负的是下一行的
    AST 判据 `_uses(src, …)` ⇒ 恒真只让**优化失效**，**结论仍然正确**。
    ⇒ **恒真必须分档**：定胜负的恒真 = 高危；前置筛/守卫的恒真 = 提示。
    """
    cur = node
    while cur in par:
        p = par[cur]
        if isinstance(p, ast.Return):
            return True
        if isinstance(p, ast.Call):
            f = p.func
            nm = (f.attr if isinstance(f, ast.Attribute)
                  else (f.id if isinstance(f, ast.Name) else ""))
            if nm in CHECKER_CALLS or nm.startswith(CHECKER_PREFIX):
                return True
        if isinstance(p, (ast.FunctionDef, ast.AsyncFunctionDef)):
            break
        cur = p
    return False


def _call_name(n) -> str:
    f = n.func if isinstance(n, ast.Call) else None
    if isinstance(f, ast.Attribute):
        return f.attr
    if isinstance(f, ast.Name):
        return f.id
    return ""


def d3_zero_masquerade(tree) -> list:
    """**D3 用 0 冒充**：读一个**可能不存在**的源，却**通篇没有「未读到」出路** ⇒ 缺失时静默报 0。

    🔴 **判据收紧过一轮**（棘轮当场抓到我自己）：第一版只要求"有 `.get(默认空)`/`len(...)`
    且没有「未读到」" ⇒ 全仓 **412 条**，而且**连纯汇报函数**（不读任何外部源、
    「源缺失」对它们根本不存在）都被误报。现在**加了前提：函数必须真的在读某个可能不存在的东西**。
    """
    out = []
    for fn in [x for x in ast.walk(tree) if isinstance(x, (ast.FunctionDef, ast.AsyncFunctionDef))]:
        nodes = list(ast.walk(fn))
        # 🔴 **前提**：真的在读某个可能不存在的东西 —— 否则「源缺失」这件事不存在
        if not any(isinstance(n, ast.Call) and _call_name(n) in READISH for n in nodes):
            continue
        # 🔴 出路用 **AST 查字符串常量**，不查源码文本（查文本恰好是 D2/D6 要抓的坑）
        if any(isinstance(n, ast.Constant) and isinstance(n.value, str)
               and any(k in n.value for k in UNREAD_KEYS) for n in nodes):
            continue
        risky = []
        for n in nodes:
            if not isinstance(n, ast.Call):
                continue
            if isinstance(n.func, ast.Attribute) and n.func.attr == "get":
                if len(n.args) >= 2 and isinstance(n.args[1], (ast.Dict, ast.List)):
                    risky.append((n.lineno, ".get(k, %s)" % ast.unparse(n.args[1])[:12]))
            if _call_name(n) == "len":
                risky.append((n.lineno, "len(...)"))
        if len(risky) >= 2:
            out.append((fn.lineno, "函数 `%s` **在读可能不存在的源**，却有 %d 处 "
                                   "`.get(默认空)`/`len(...)` 且**通篇没有「未读到」出路** "
                                   "⇒ 源缺失时会静默报 0" % (fn.name, len(risky))))
    return out


def d4_dead_code(tree) -> list:
    out = []
    for n in ast.walk(tree):
        if isinstance(n, ast.If) and isinstance(n.test, ast.Constant) and n.test.value is False:
            out.append((n.lineno, "`if False:` —— 死代码（本仓 §一百零二 清过一处）"))
        if isinstance(n, ast.While) and isinstance(n.test, ast.Constant) and n.test.value is False:
            out.append((n.lineno, "`while False:` —— 死循环体"))
    return out


def d5_self_compare(tree) -> list:
    out = []
    for n in ast.walk(tree):
        if not isinstance(n, ast.Compare) or len(n.ops) != 1:
            continue
        lft, r = n.left, n.comparators[0]
        if isinstance(lft, ast.Name) and isinstance(r, ast.Name) and lft.id == r.id:
            if isinstance(n.ops[0], (ast.Eq, ast.NotEq, ast.Lt, ast.Gt, ast.LtE, ast.GtE)):
                out.append((n.lineno, "`%s %s %s` —— 与自己比" % (lft.id, ast.unparse(n.ops[0]),
                                                              r.id)))
    return out


def _collection_strings(tree) -> dict:
    """收集「作为**集合元素**出现的字符串常量」→ {值: [行号…]}。

    这是自指的**指纹**：判据先把「禁止项」列成一张表，再拿表里的项去搜源码
    ⇒ 搜的字符串就在判据自己的表里 ⇒ **必然匹配到自己**。
    """
    out = {}
    for n in ast.walk(tree):
        if isinstance(n, (ast.List, ast.Tuple, ast.Set)):
            for e in n.elts:
                if isinstance(e, ast.Constant) and isinstance(e.value, str):
                    out.setdefault(e.value, []).append(n.lineno)
    return out


def _src_bound_names(tree) -> set:
    """收集「**由读自己的源码（`__file__`）进来的**」变量名。

    🔴 这一步是 D6 的关键收紧，**收紧了两轮**：
      第一轮：只判"是不是文本判据" ⇒ 275 条噪音；
      第二轮：加上"被搜变量是不是由 read_text 绑定的" ⇒ 13 条，但**高危档 2/2 全是假阳性** ——
              那两处读的是**别人的 `SKILL.md`**（审计别的技能带没带署名），**不是自己的源码**；
      第三轮（现在）：要求读表达式里**出现 `__file__`** ⇒ 才是"在搜自己"。
    **每收紧一轮，都是被真读数逼出来的 —— 不是拍脑袋。**
    """
    out = set()
    for n in ast.walk(tree):
        if not isinstance(n, ast.Assign):
            continue
        call = ast.unparse(n.value)
        if "__file__" not in call:
            continue
        if not any(k in call for k in ("read_text", "read_bytes", "readlines", "read(")):
            continue
        for t in n.targets:
            if isinstance(t, ast.Name):
                out.add(t.id)
    return out


def d6_self_reference(tree, src_text: str) -> list:
    """**D6 自指判据**：判据把要搜的字符串**列在自己源码里**，并拿它去搜**源码本身**。

    两档（**分开报，因为严重程度差一个数量级**）：
      🔴 **高危·自指**：被搜的变量是**读文件进来的**（`read_text`/`open`）⇒ **必然匹配到自己**。
      🟡 **提示·表式文本判据**：被搜的是**输入数据/别的进程输出** ⇒ 多半**合法**，列出来复核。

    形状②`any(t in X for t in ("A","B"))`（**本仓真踩过的那个**）· 形状①`"L" in X` 且 L 又是集合元素。
    """
    src_bound = _src_bound_names(tree)
    out = []

    def _tag(rname: str) -> str:
        return ("🔴 **高危·自指**" if rname in src_bound else
                "🟡 提示·表式文本判据") + "（被搜变量 `%s` %s）" % (
                    rname, "由读文件绑定 ⇒ **就是在搜自己的源码**" if rname in src_bound
                    else "不是读文件来的 ⇒ 多半是**输入数据/别的进程输出**，通常合法")

    # ── 形状②：any/all(<Name> in <X> for <Name> in (<字面量表>)) ────────────────
    for n in ast.walk(tree):
        if not isinstance(n, ast.GeneratorExp):
            continue
        el = n.elt
        if not (isinstance(el, ast.Compare) and len(el.ops) == 1
                and isinstance(el.ops[0], (ast.In, ast.NotIn))):
            continue
        r = el.comparators[0]
        rname = r.id if isinstance(r, ast.Name) else ""
        if not TEXTISH.match(rname):
            continue
        it = n.generators[0].iter if n.generators else None
        els = _lit(it) or []
        lits = [e.value for e in els if isinstance(e, ast.Constant) and isinstance(e.value, str)]
        if lits:
            out.append((n.lineno,
                        '%s：`… in %s for … in (%s…)` —— 字符串**列在自己源码里**（%d 个，如 `%s`）'
                        % (_tag(rname), rname,
                           ", ".join('"%s"' % x[:14] for x in lits[:2]), len(lits), lits[0][:20])))
    # ── 形状①：`"L" in <X>`，且 L 又是同一文件里某个集合的元素 ───────────────────
    coll = _collection_strings(tree)
    par3 = _parents(tree)
    for n in ast.walk(tree):
        if not isinstance(n, ast.Compare):
            continue
        for op, comp in zip(n.ops, n.comparators):
            if not isinstance(op, (ast.In, ast.NotIn)):
                continue
            left, right = n.left, comp
            if not (isinstance(left, ast.Constant) and isinstance(left.value, str)):
                continue
            rname = right.id if isinstance(right, ast.Name) else ""
            if not TEXTISH.match(rname):
                continue
            hits = [ln for ln in coll.get(left.value, []) if ln != n.lineno]
            if hits:
                # 🔴 **同一处分档**：形状③也要按位置分档（否则会与形状④重复报高危）
                dec = _in_deciding_position(n, par3)
                tag = ("🔴 **高危·自指**" if dec else "🟡 提示·自指（不定胜负）")
                out.append((n.lineno,
                            '%s：`"%s" in %s`，同一字面量又是集合元素（L%s）'
                            % (tag, left.value[:20], rname, hits[:3])))
    # ── 形状③：同一字符串**常量**在本文件里出现 ≥2 次（一次在判据里、一次在别处）──────
    #    🔴 **这个洞是实测发现的**：我自己新写的判据
    #    `"import edit_core" not in src and "from … import edit_core" not in src`
    #    —— 字面量**直接列在判据里**、**不是集合元素** ⇒ 形状①②都看不见它。
    #    数常量（AST）而不是数源码文本（文本会被注释/文档串骗到）。
    lits_all = {}
    for n in ast.walk(tree):
        if isinstance(n, ast.Constant) and isinstance(n.value, str) and n.value.strip():
            lits_all.setdefault(n.value, []).append(n.lineno)
    for n in ast.walk(tree):
        if not isinstance(n, ast.Compare):
            continue
        for op, comp in zip(n.ops, n.comparators):
            if not isinstance(op, (ast.In, ast.NotIn)):
                continue
            left, right = n.left, comp
            if not (isinstance(left, ast.Constant) and isinstance(left.value, str)):
                continue
            rname = right.id if isinstance(right, ast.Name) else ""
            if not TEXTISH.match(rname):
                continue
            others = [ln for ln in lits_all.get(left.value, []) if ln != n.lineno]
            if others:
                dec = _in_deciding_position(n, par3)
                tag = ("🔴 **高危·自指**" if dec else "🟡 提示·自指（不定胜负）")
                out.append((n.lineno,
                            '%s：`"%s" %s %s`，而**同一字符串常量**在本文件另见 L%s '
                            '⇒ 判据把要搜的字符串**列在自己源码里**'
                            % (tag, left.value[:20],
                               "in" if isinstance(op, ast.In) else "not in",
                               rname, others[:3])))
    # ── 形状④（**最锋利**）：`"L" in <__file__ 绑定变量>` —— **必然恒真** ─────────────
    #    🔴 推理：`src` 就是本文件自己的文本，而字面量 `L` **本身就在这个文件里**
    #    ⇒ `L in src` **必然为真**（`not in` 必然为假）。**不需要出现两次，一次就够。**
    #    这条是实测逼出来的：我新写的 `"import edit_core" not in src` 就是它，
    #    形状①②③**都看不见**（字面量只出现一次、且不在集合里）。
    if src_bound:
        par = _parents(tree)
        for n in ast.walk(tree):
            if not isinstance(n, ast.Compare):
                continue
            for op, comp in zip(n.ops, n.comparators):
                if not isinstance(op, (ast.In, ast.NotIn)):
                    continue
                left, right = n.left, comp
                if not (isinstance(left, ast.Constant) and isinstance(left.value, str)
                        and left.value.strip()):
                    continue
                rname = right.id if isinstance(right, ast.Name) else ""
                if rname not in src_bound:
                    continue
                # 🔴 **分档**：定胜负的位置 ⇒ 高危；前置筛/守卫 ⇒ 提示（优化失效）
                dec = _in_deciding_position(n, par)
                tag = ("🔴 **高危·自指（恒真）**" if dec else
                       "🟡 提示·自指前置筛（恒真但不定胜负）")
                out.append((n.lineno,
                            '%s：`"%s" %s %s`，而 `%s` 是**本文件自己的文本**'
                            ' —— 这个字面量就在文件里 ⇒ 条件**必然%s**；%s'
                            % (tag, left.value[:20],
                               "in" if isinstance(op, ast.In) else "not in",
                               rname, rname, "为真" if isinstance(op, ast.In) else "为假",
                               "**这条就是判据本身 ⇒ 判据是假的**" if dec else
                               "但它只是**前置筛/守卫**，定胜负的是别处 ⇒ **优化失效**，结论未必错")))
    return out


def scan_file(p: Path) -> list:
    try:
        text = p.read_text(encoding="utf-8", errors="replace")
        tree = ast.parse(text)
    except Exception:
        return []
    found = []
    for name, hits in run_detectors(tree, text).items():
        for ln, why in hits:
            found.append({"检测器": name, "文件": str(p.relative_to(ROOT)), "行": ln, "为什么": why})
    return found


def _walk_py(roots) -> list:
    """**只走目录、不解析** —— 产出按真路径去重后的 .py 清单。

    🔴 抽出这一层是为了**性能**：`scan()` 要对每个文件做 AST 解析（327 个文件 ≈ 十几秒），
    而"去重"这件事**根本不需要解析**。把去重单独测，判据不变弱、耗时降一个量级。
    踩过的坑：`DEFAULT_ROOTS` 里同时有 `tools` 与 `tools/codex-scripts`，
    而 `tools.rglob` **已包含**后者 ⇒ 同一文件被扫两遍、计数凭空翻倍
    （首跑报 1196，实为 700）。**要去重，不是"看着差不多就减半"。**
    """
    seen, out = set(), []
    for r in roots:
        d = ROOT / r
        if not d.is_dir():
            continue
        for p in sorted(d.rglob("*.py")):
            if any(t in p.parts for t in ("__pycache__", ".pylibs")):
                continue
            key = str(p.resolve())
            if key in seen:
                continue
            seen.add(key)
            out.append(p)
    return out


def scan(roots) -> list:
    out = []
    for p in _walk_py(roots):
        out += scan_file(p)
    return out


def tally(findings) -> dict:
    t = {k: 0 for k in DETECTORS}
    for f in findings:
        t[f["检测器"]] = t.get(f["检测器"], 0) + 1
    t["合计"] = len(findings)
    return t


# 🔴 **指纹**：一条命中的**稳定身份** = 检测器 + 文件 + 代码片段。
#    为什么要它（2026-09-24 实测踩出来的）：棘轮原来只存**分类计数**，
#    我改完代码后 D1 少了 1 条，**归因不了**（是"删了坏判据"还是"检测器漏了"？）。
#    于是我按 `为什么` 全文做逐条对差 ⇒ **报了 49 条"消失" + 48 条"新增"**，
#    而真值只有 1 处变化 —— 因为**检测器把提示语措辞改了**（"表式文本判据" → "自指（不定胜负）"），
#    于是**每一条**的 `为什么` 都"变了"。**逐条对差被措辞一改就全废。**
#    ⇒ 身份必须取**不受措辞影响**的那部分：文件 + 检测器 + 代码片段。
_SNIP = re.compile(r"`([^`]+)`")
_DIGITS = re.compile(r"\d+")


def 指纹(x: dict) -> str:
    """稳定身份：`检测器|文件|代码片段`（措辞怎么改都不变）。

    🔴 取片段取**最长**那个反引号跨度，不是第一个 —— 实测：老提示语里第一个反引号是
    **变量名**（`` `out` ``），新提示语里第一个就是**代码片段**（`` `"🔴" in out` ``）：
    取"第一个"会因措辞改动而**换片段** ⇒ 又造成假差异（实测 27 消失 / 42 新增）。
    片段比变量名长 ⇒ **取最长**对两种措辞都落到同一段。
    🔴 没有反引号时（如 D3 的「却有 15 处」，数字会随代码变）⇒ **把数字抹成 `#`**：
    这条命中的身份是"哪个函数哪一类"，**不是"当时数出几处"**。
    """
    why = str(x.get("为什么") or "")
    spans = [s.strip() for s in _SNIP.findall(why) if s.strip()]
    if spans:
        snip = max(spans, key=len)
    else:
        snip = what = why.split("——")[0].split("**")[0].strip()
        snip = what
    snip = _DIGITS.sub("#", snip)
    snip = " ".join(snip.split())
    return "%s|%s|%s" % (x.get("检测器"), x.get("文件"), snip[:80])


def _named_diff(now: list, base: list, cap: int = 12) -> dict:
    """**点名**对差（按指纹）——只报真变化，不被措辞改动静默放大。"""
    nb = {}
    for x in base or []:
        nb[指纹(x)] = nb.get(指纹(x), 0) + 1
    nn = {}
    for x in now or []:
        nn[指纹(x)] = nn.get(指纹(x), 0) + 1
    gone = sorted(k for k in nb if nb[k] > nn.get(k, 0))
    new = sorted(k for k in nn if nn[k] > nb.get(k, 0))
    return {"消失": gone[:cap], "消失条数": len(gone),
            "新增": new[:cap], "新增条数": len(new),
            "口径": "按**指纹**（检测器|文件|代码片段）对差 ⇒ **检测器改措辞不会造成假差异**"}


# ── 命令 ───────────────────────────────────────────────────────────────────────
def cmd_scan(a) -> int:
    roots = tuple(a.roots.split(",")) if a.roots else DEFAULT_ROOTS
    f = scan(roots)
    print(json.dumps({"扫的根": list(roots), "逐条": f, "合计": tally(f),
                      "读法": "这些是**待人工确认**的嫌疑，不是判决 —— "
                      "台架只负责把可疑形状指出来（含行号），判不判由人/后续复核定"},
                     ensure_ascii=False, indent=1))
    return 0


def cmd_settle(a) -> int:
    """立基线。**必须能记原因** —— 否则重立基线等于把回退盖掉。

    🔴 **棘轮的真实局限（必须写下来）**：它**分不清**下面两件事 ——
      ① 新写了坏判据（**该红**）
      ② 检测器改进了、发现了更多既有形状（**不该红，是好事**）
    所以 `settle` 支持 `--note`，**把"为什么这次数字变了"写进基线文件**：
    没有原因的重立基线 = 隐藏回退，**有原因的才是升级**。
    """
    roots = tuple(a.roots.split(",")) if a.roots else DEFAULT_ROOTS
    f = scan(roots)
    t = tally(f)
    BASE.parent.mkdir(parents=True, exist_ok=True)
    BASE.write_text(json.dumps({"at": __import__("time").strftime("%Y-%m-%dT%H:%M:%S"),
                                "扫的根": list(roots), "计数": t,
                                "这次为什么重立基线": a.note or "**未写原因**（下次要写）",
                                "逐条": f}, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps({"立基线": t, "原因": a.note or "**未写原因**",
                      "落盘": str(BASE.relative_to(ROOT))}, ensure_ascii=False, indent=1))
    print("🔴 棘轮：**以后只许变少，不许变多**（变多 = 新写的判据又坏了）")
    return 0


def _ratchet(now: dict, base: dict, findings=None) -> dict:
    """**变坏要点得出名**，不是只报"多了 2 条"。

    🔴 2026-09-24 增补：原来只报计数差。我改完代码后 D1 少 1 条、**归因不了** ——
    一个只会说"少了一条"的棘轮，让人**没法判断那一条是"修好了"还是"检测器漏了"**。
    现在按**指纹**点名（措辞改动不会造成假差异，见 `指纹`）。
    """
    old = base.get("计数") or {}
    worse, better = [], []
    for k in DETECTORS + ("合计",):
        o, n = old.get(k, 0), now.get(k, 0)
        if n > o:
            worse.append({"类": k, "基线": o, "现在": n, "多": n - o})
        elif n < o:
            better.append({"类": k, "基线": o, "现在": n, "少": o - n})
    r = {"基线": base.get("at"), "变坏": worse, "变好": better, "现计数": now,
         "判决": "🔴 **判据质量变坏了**" if worse else "✅ 没有变坏"}
    if findings is not None:
        r["点名对差（按指纹）"] = _named_diff(findings, base.get("逐条") or [])
    return r


def cmd_gate(a) -> int:
    """**一次扫描供两用**：自检 + 棘轮。

    🔴 为什么要合并：原来 checkup 里跑 `selftest` 与 `check` 两条命令，
    各扫全仓一遍（每遍 AST 解析 327 个文件）⇒ 总耗时 39.1s。
    合并后**只解析一遍**。**优化的前提是判据不变弱** —— 自检条数与扫描条数都必须一致，
    下面把这两项一起报出来，方便对账。
    """
    one = scan(DEFAULT_ROOTS)                     # ← 全仓只解析这一次
    lines, bad, _ = _checks(pre_scan=one)
    if not BASE.exists():
        print(json.dumps({"自检": {"条数": len(lines), "通过": len(lines) - bad, "不通过": bad},
                          "棘轮": {"ok": False, "为什么": "没有基线 ⇒ 先跑 settle"}},
                         ensure_ascii=False, indent=1))
        return 3
    r = _ratchet(tally(one), json.loads(BASE.read_text(encoding="utf-8")), findings=one)
    print(json.dumps({"自检": {"条数": len(lines), "通过": len(lines) - bad, "不通过": bad},
                      "本次扫描条数": len(one),
                      "棘轮": r}, ensure_ascii=False, indent=1))
    if bad:
        print("🔴 自检有 %d 项不过" % bad)
        return 1
    if r["变坏"]:
        print("🔴 判据质量变坏了：%s" % r["变坏"])
        return 1
    print("✅ 一次扫描：自检 %d 条全过 · 棘轮没变坏 · 全仓 %d 条" % (len(lines), len(one)))
    return 0


def cmd_check(a) -> int:
    roots = tuple(a.roots.split(",")) if a.roots else DEFAULT_ROOTS
    if not BASE.exists():
        print(json.dumps({"ok": False, "为什么": "没有基线 ⇒ 先跑 settle"}, ensure_ascii=False))
        return 3
    base = json.loads(BASE.read_text(encoding="utf-8"))
    one = scan(roots)
    r = _ratchet(tally(one), base, findings=one)
    print(json.dumps(r, ensure_ascii=False, indent=1))
    return 1 if r["变坏"] else 0


PLANT = {
    "D1 恒真判据": "def f(xs):\n    return all(x for _ in [1])\n",
    "D2 文本子串判据": 'def f(src):\n    return "forbidden(" in src\n',
    # 🔴 这是本仓**真踩过**的形状：判据把禁止项列成一张表，再拿表里的项去搜**自己读进来的源码**
    "D6 自指判据（高危）":
        ("def f():\n"
         "    src = Path(__file__).read_text()\n"
         "    return not any(t in src for t in (\"write_bytes(\", \"mkdir(\"))\n"),
    "D3 用0冒充": ("def f(p):\n"
                "    d = json.loads(p.read_text())\n"
                "    a = d.get('x', {})\n"
                "    b = len(a)\n"
                "    return b\n"),
    "D4 死代码": "def f():\n    if False:\n        return 1\n    return 2\n",
    "D5 判据与自己比": "def f(y):\n    return y == y\n",
    # 🔴 2026-09-25：这条负控是**被自检逼出来的** ——
    #    我给台架加了 D7 却忘了加负控，自检当场红：「检测器 7 个 ｜ 负控 6 个 ｜ 缺负控: ['D7 …']」。
    #    形状取自**我自己真犯的那次**（拿"最后一行"答"有没有署名"）。
    # 🔴 负控必须与判据**同宽**：我一度把 `lines[0]` 也写进来，但判据**收窄后不收 `[0]`**
    #    ⇒ 那行是**永远咬不到的死重量**，还会让人以为 `[0]` 被覆盖了。**删掉它。**
    "D7 位置型存在性判据": ('def f(lines):\n'
                    '    return "本署名不可删除" in lines[-1]\n'),
}
CLEAN = ("def f(d):\n"
         "    if d is None:\n"
         "        return '**未读到**'\n"
         "    return {'n': len(d), 'why': '读到 %d 项' % len(d)}\n")
# D6 的**假阳性**控制：合法文本判据 —— 字面量**不在**任何集合里 ⇒ 不该判自指
FP_TEXT = 'def f(txt):\n    return "TODO" in txt\n'
# D6 的**档次**控制：被搜的是**输入数据**（不是读进来的源码）⇒ 只能算 🟡 提示，不许报 🔴 高危
FP_TIER = ('def f(body):\n'
           '    return any(t in body for t in ("我是 AI", "新人类"))\n')
# D6 的**读别人文件**控制：读的是**别人的文件**（不是 `__file__`）⇒ 只能 🟡，不许报 🔴
#   🔴 这条是**实测发现的假阳性**：首跑"高危"档 2/2 全是这个形状
#      （`audit-skill-roots.py` / `make-delivery-ledger.py` 读别人的 `SKILL.md` 审计署名）
FP_OTHER = ('def f(sk):\n'
            '    body = sk.read_text()\n'
            '    return any(t in body for t in ("GBT小土豆", "自由的风"))\n')
# D3 的**纯汇报函数**控制：不读任何外部源 ⇒ 「源缺失」不存在 ⇒ **不许报 D3**
#   🔴 这条也是**实测发现的假阳性**：棘轮抓到我自己新写的 `cmd_gate`/`_checks` 被误报
FP_PURE = ('def report(items):\n'
           '    return {"n": len(items), "m": len([x for x in items]), '
           '"k": len(set(items))}\n')
# D1 的**用到循环变量**控制：`any(k in r for k in ("静帧",))` 条件**依赖数据** ⇒ 不许报恒真/恒假
#   🔴 实测假阳性：我第一版 D1 漏查"元素是否用到循环变量"，误告了 `media_run.py:398`
FP_LOOPVAR = ('def f(r):\n'
              '    return any(k in r for k in ("静帧",))\n')
# D6 的**前置筛**控制：恒真但**不定胜负**（真判据是别处）⇒ 只能 🟡，不许报 🔴
#   🔴 实测逼出来的（§一百一十八）：`stigmergy.py:315` 就是"故意的廉价前置筛"
FP_PREFILTER = ('def judge():\n'
                '    src = Path(__file__).read_text()\n'
                '    _u = (uses_name(src, "locked_append_text")'
                ' if "locked_append_text" in src else False)\n'
                '    return _u is True\n')


def inert_plant_lines(want: str, code: str) -> list:
    """负控里「**长得像判据、却咬不到**」的行。

    🔴 **v1 的判据太粗，已被数据打回**：v1 定义成「去掉这行，命中数不变 ⇒ 死重量」。
    实测它报了 3 处 **假死重量**：`D6 → src = Path(__file__).read_text()`、
    `D3 → return b`、`D4 → …` —— 这些行**是正当的**（有的行是依赖/收尾，本来就不该被单独咬）。
    ⇒ **"别的行已经咬到了" ≠ "这行永远咬不到"**，两者必须分开。

    **v2 定义（收窄到"我真正犯的那个错"）**：只挑**判据形状**的行
    （含 ` in ` / `not in ` / `.startswith(` / `.endswith(`），把它**单独**放进一个最小函数里喂给检测器；
    **若单独也咬不到 ⇒ 那就是「长得像判据、但判据看不见它」** ⇒ 报。
    这正好抓 `"署名" in lines[0]`（我收窄判据后留在负控里的那行），**不冤** `src = …` 这种依赖行。
    """
    fn = dict(DETECTOR_FUNCS).get(want)
    if fn is None:
        return []
    marks = (" in ", "not in ", ".startswith(", ".endswith(")
    out = []
    for ln in code.splitlines():
        s = ln.strip()
        if not s or not ln.startswith((" ", "\t")):
            continue
        if not any(m in s for m in marks):
            continue                      # 不是判据形状 ⇒ 不管它（依赖/收尾行）
        probe = "def _probe():\n    " + s + "\n"
        try:
            tree = ast.parse(probe)
        except Exception:  # noqa: BLE001
            continue
        try:
            if not fn(tree, probe):
                out.append(ln)
        except Exception:  # noqa: BLE001
            continue
    return out


def _checks(pre_scan=None):
    """全部自检项 → (逐条, 不通过数)。

    `pre_scan` 传入已算好的扫描结果时**不再重扫**（`gate` 用它把两次全仓扫描省成一次）。
    """
    lines, bad = [], 0
    state = {"scan": pre_scan}

    def ck(name, cond, detail):
        nonlocal bad
        bad += 0 if cond else 1
        lines.append("%s %s — %s" % ("✓" if cond else "✗", name, detail))

    # ① **每个检测器都必须有负控**：种真缺陷，必须被咬出来
    for want, code in PLANT.items():
        tree = ast.parse(code)
        res = run_detectors(tree, code)
        names = [k for k, v in res.items() if v]
        ck("**负控·%s 必须咬得住**" % want, want in names,
           "咬出: %s（共 %d 处）" % (names or "无", sum(len(v) for v in res.values())))
    # ①b 🔴 **单一来源自检**：检测器表与负控表必须齐 —— 加了检测器却没加负控 ⇒ 报红
    ck("**每个检测器都有负控**（加了检测器却忘了加负控 ⇒ 这里红）",
       set(PLANT) == set(DETECTORS),
       "检测器 %d 个 ｜ 负控 %d 个 ｜ 缺负控: %s" % (len(DETECTORS), len(PLANT),
                                         sorted(set(DETECTORS) - set(PLANT)) or "无"))
    # ①c 🔴 **负控必须与判据同宽**（2026-09-25 我手工犯过、现在机检）：
    #     我把 D7 的判据收窄成"只认尾部负下标"，**负控里却还留着 `lines[0]`** ——
    #     那行**永远咬不到**，还会让人以为 `[0]` 被覆盖了。
    #     **机检定义**：把负控里某一行去掉，若命中数**不变** ⇒ 那行是**死重量**。
    inert_all = []
    for want, code in PLANT.items():
        inert_all += ["%s → `%s`" % (want, ln.strip())
                      for ln in inert_plant_lines(want, code)]
    ck("**负控与判据同宽**（负控里不许有永远咬不到的死重量）", not inert_all,
       "死重量: %s" % (inert_all or "无"))
    # ①d 🔴 **这条控制本身会不会咬**（不然它自己就是假绿）：
    #     把 D7 收窄前那种"宽负控"（多塞一行 `lines[0]`）喂进去 ⇒ **必须**被点名。
    _wide = ('def f(lines):\n'
             '    a = "署名" in lines[0]\n'
             '    return a or "署名" in lines[-1]\n')
    _w = inert_plant_lines("D7 位置型存在性判据", _wide)
    ck("**负控·同宽控制本身会咬**（塞一行咬不到的判据进去 ⇒ 必须被点名）", bool(_w),
       "死重量 = %s" % ([x.strip() for x in _w] or "无（那这条控制就是假的）"))
    # ② **假阳性控制**：干净代码不许被误报
    t = ast.parse(CLEAN)
    clean_hits = [h for v in run_detectors(t, CLEAN).values() for h in v]
    ck("**假阳性控制：干净代码不许被误报**", not clean_hits,
       "误报 %d 处：%s" % (len(clean_hits), clean_hits[:2]))
    # ②b 🔴 **D6 假阳性控制**：合法的文本判据（字面量**不在**集合里）不许被误报成自指
    fp_tree = ast.parse(FP_TEXT)
    d6_fp = d6_self_reference(fp_tree, FP_TEXT)
    ck("**D6 假阳性控制：合法文本判据不许被误报成自指**", not d6_fp,
       "误报 %d 处：%s" % (len(d6_fp), d6_fp[:1]))
    # ②c 🔴 **D6 档次控制**：被搜的是**输入数据** ⇒ 只能 🟡，**不许报 🔴 高危**
    #     （首跑 13 条里大多数就是这种 —— 不区分档次，D6 就是个噪音器）
    ft_tree = ast.parse(FP_TIER)
    d6_ft = d6_self_reference(ft_tree, FP_TIER)
    ck("**D6 档次控制：搜「输入数据」不许报高危**（只能 🟡 提示）",
       bool(d6_ft) and all("🟡" in w for _, w in d6_ft) and not any("🔴" in w for _, w in d6_ft),
       (d6_ft[0][1][:72] if d6_ft else "**没报出来**（那也不行）"))
    # ②d 🔴 **D6 读别人文件控制**：读**别人的文件**（非 `__file__`）不许报高危
    #     （这是实测抓到的假阳性：高危档 2/2 全错在这个形状上）
    fo_tree = ast.parse(FP_OTHER)
    d6_fo = d6_self_reference(fo_tree, FP_OTHER)
    ck("**D6 控制：读「别人的文件」不许报高危**（只能 🟡 提示）",
       bool(d6_fo) and all("🟡" in w for _, w in d6_fo) and not any("🔴" in w for _, w in d6_fo),
       (d6_fo[0][1][:72] if d6_fo else "**没报出来**（那也不行）"))
    # ②e 🔴 **D3 纯汇报函数控制**：不读外部源 ⇒ 「源缺失」不存在 ⇒ 不许报 D3
    #     （这是棘轮抓到的我自己的假阳性：`cmd_gate`/`_checks`/`cmd_selftest`）
    fp2_tree = ast.parse(FP_PURE)
    d3_fp = d3_zero_masquerade(fp2_tree)
    ck("**D3 控制：纯汇报函数不许报「用 0 冒充」**（它不读任何外部源）",
       not d3_fp, "误报 %d 处：%s" % (len(d3_fp), d3_fp[:1]))
    # ②f 🔴 **D1 控制：元素用到循环变量 ⇒ 条件依赖数据 ⇒ 不许报恒真/恒假**
    #     （实测假阳性：误告 `media_run.py:398` 的 `any(k in r for k in ("静帧",))`）
    lv_tree = ast.parse(FP_LOOPVAR)
    d1_lv = d1_always_true(lv_tree)
    ck("**D1 控制：用到循环变量的 any/all 不许报恒真**（条件依赖数据）",
       not d1_lv, "误报 %d 处：%s" % (len(d1_lv), d1_lv[:1]))
    # ②g 🔴 **D6 分档控制**：恒真但只是**前置筛**（不定胜负）⇒ 只能 🟡，不许报 🔴
    #     （实测：`stigmergy.py:315` 是故意的廉价前置筛，真判据是别处的 AST 调用）
    pf_tree = ast.parse(FP_PREFILTER)
    d6_pf = d6_self_reference(pf_tree, FP_PREFILTER)
    ck("**D6 分档控制：前置筛的恒真只能 🟡**（不许报高危）",
       bool(d6_pf) and all("🟡" in w for _, w in d6_pf) and not any("🔴" in w for _, w in d6_pf),
       (d6_pf[0][1][:70] if d6_pf else "**没报出来**（那也不行）"))
    # ③ 自指控制：本文件**自己**不许被 D2/D6 咬（台架不许用文本判据）
    mine = Path(__file__).read_text(encoding="utf-8")
    my_tree = ast.parse(mine)
    my_d2 = d2_text_criterion(my_tree, mine)
    my_d6 = d6_self_reference(my_tree, mine)
    ck("**台架自己不使用文本判据**（扫自己，D2/D6 应为 0）", not my_d2 and not my_d6,
       "D2 命中 %d 处 ｜ D6 命中 %d 处" % (len(my_d2), len(my_d6)))
    # ④ 真扫一遍：读数必须与 tally 一致（有 pre_scan 就复用，**不重扫**）
    f = state["scan"] if state["scan"] is not None else scan(DEFAULT_ROOTS)
    ck("**真扫读数自洽**（逐条数 == 合计）", tally(f)["合计"] == len(f),
       "合计 %d" % len(f))
    # ⑤ 🔴 负控：**重叠根不许重复计数**
    #    判据要**随数据变**：`tools` 的 rglob 已包含 `tools/codex-scripts`，
    #    所以「单根」与「根+子根」的条数**必须相等**。
    #    （第一版判据写成 `len(keys)==len(set((文件,行,检测器)))` —— **那是坏判据**：
    #     同一行上两个不同表达式会给出同一个三元组，合法重复被误判成没去重。）
    #    ⚡ 用 `_walk_py`（**不解析**）测去重机制 —— 判据不变弱，耗时降一个量级。
    a1, a2 = _walk_py(("tools",)), _walk_py(("tools", "tools/codex-scripts"))
    ck("**负控：重叠根不许重复计数**（加子根后文件数必须不变）",
       len(a1) == len(a2) and len(a1) > 0,
       "单根 tools = %d 个 .py ｜ 再加 tools/codex-scripts = %d 个" % (len(a1), len(a2)))
    # ⑥ 🔴 **指纹必须不被措辞影响**（本节这条是实测踩出来的）：
    #    同一条命中，只把提示语**换个说法**，指纹必须**不变**；
    #    否则逐条对差会像上次那样凭空报出 49 条"消失" + 48 条"新增"。
    it_a = {"检测器": "D2 文本子串判据", "文件": "x.py", "行": 10,
            "为什么": "`\"forbidden(\" in src` —— 文本判据 （未见自指，但文本判据仍弱）"}
    it_b = {"检测器": "D2 文本子串判据", "文件": "x.py", "行": 99,
            "为什么": "🟡 提示·自指（不定胜负）：`\"forbidden(\" in src`，而同一字符串常量在本文件另见 L[3]"}
    ck("**指纹：措辞改了、行号挪了 ⇒ 指纹不变**（逐条对差才不会被措辞改动静默放大）",
       指纹(it_a) == 指纹(it_b), "%s ｜ %s" % (指纹(it_a), 指纹(it_b)))
    it_c = {"检测器": "D2 文本子串判据", "文件": "x.py",
            "为什么": "`\"another(\" in src` —— 文本判据"}
    ck("**指纹：代码片段不同 ⇒ 指纹必须不同**（别把两条不同的命中合成一条）",
       指纹(it_a) != 指纹(it_c), "%s vs %s" % (指纹(it_a), 指纹(it_c)))
    # 🔴 **指纹：措辞把"变量名"提前了也不许换片段**（实测真坑）
    it_d = {"检测器": "D6 自指判据（高危）", "文件": "y.py",
            "为什么": "🟡 提示·表式文本判据（被搜变量 `out` 不是读文件来的）：`\"🔴\" in out`，而…"}
    it_e = {"检测器": "D6 自指判据（高危）", "文件": "y.py",
            "为什么": "🟡 提示·自指（不定胜负）：`\"🔴\" in out`，而…"}
    ck("**指纹：老措辞把变量名放在前一个反引号里 ⇒ 仍要认成同一条**（取最长片段）",
       指纹(it_d) == 指纹(it_e), "%s\n      vs %s" % (指纹(it_d), 指纹(it_e)))
    # ⑦ 🔴 **点名对差要真点名**：基线里多一条、现在没有 ⇒ 「消失」里必须点到它
    named = _named_diff([it_a], [it_a, it_c])
    ck("**点名对差：真消失的那条被点到名**（不是只报个数）",
       named["消失条数"] == 1 and 指纹(it_c) in named["消失"],
       "消失=%s 新增=%s" % (named["消失"], named["新增"]))
    ck("**点名对差：措辞改动不许造成假差异**",
       _named_diff([it_b], [it_a])["消失条数"] == 0,
       "同一命中的两种写法对差 = %s" % _named_diff([it_b], [it_a])["消失"])
    return lines, bad, f


def cmd_selftest(a) -> int:
    lines, bad, _ = _checks()
    print(json.dumps({"自检": {"条数": len(lines), "通过": len(lines) - bad, "不通过": bad},
                      "逐条": lines}, ensure_ascii=False, indent=1))
    return 0 if bad == 0 else 1


def main() -> int:
    ap = argparse.ArgumentParser(description="判据质量台架：自动找坏判据（AST 判据 + 负控）")
    ap.add_argument("--roots", default="")
    ap.add_argument("--note", default="", help="settle 专用：这次为什么重立基线（**必写**）")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("scan").set_defaults(func=cmd_scan)
    sub.add_parser("settle").set_defaults(func=cmd_settle)
    sub.add_parser("check").set_defaults(func=cmd_check)
    sub.add_parser("selftest").set_defaults(func=cmd_selftest)
    sub.add_parser("gate").set_defaults(func=cmd_gate)
    a = ap.parse_args()
    return a.func(a)


if __name__ == "__main__":
    raise SystemExit(main())
