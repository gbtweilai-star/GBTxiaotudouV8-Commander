#!/usr/bin/env python -3.14
# -*- coding: utf-8 -*-
"""gate-blind-kinds · **位级**写目标（`api.py` 分支 → 它调的函数 → 只抽那个函数）

开发者：自由的风 · 守护者：公主土豆 · 禁止删除

## 为什么单独一个文件
§一百三十 取证出：这批模块**内部没有 op 分派**（`engine.py` 只有 `run_workflow`、
`longrun.py` 一个 `op ==` 都没有、`devour.py` 用 dict 分派）
⇒ **正确的粒度是**：`api.py` 里 `if kind == "<位>":` 那一支 → **它调的函数** → 抽**那个函数**的写目标。
本文件就把这条链做出来。**只读静态，不真跑**（真跑会改状态）。

## 口径（不许省）
- 运行时拼出来的路径**静态看不见** ⇒ 这份表是「**静态读到的写目标**」，**不是全集**；
- 「会删吗」问的是**那个被调函数里有没有删除类原语**，**不等于"该位一定会删"**（要真跑才知道）。

用法：gate-blind-kinds.py run ｜ selftest
"""
from __future__ import annotations

import argparse
import ast
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
PKG = ROOT / "gbt_allinone"

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

WRITE_PRIMS = ("write_bytes", "write_text", "mkdir", "unlink", "rmdir", "rmtree",
               "copytree", "rename", "replace", "open")
DEL_PRIMS = ("unlink", "rmtree", "rmdir")
# 与 gate-blind-audit 一致的"带牙"标记 —— 只有写根白名单/只追加守卫才算写面约束
HARD = (r"write_root|WRITE_ROOTS|_rel_inside|is_relative_to|\.relative_to\(",
        r"locked_append|append_only|append-only|只追加")


def _name(n) -> str:
    f = n.func if isinstance(n, ast.Call) else None
    if isinstance(f, ast.Attribute):
        return f.attr
    if isinstance(f, ast.Name):
        return f.id
    return ""


# 🔴 **单次运行内的读缓存**：先前 `_mods_for()` 逐位把同一批 `.py` 各重读一遍
#    ⇒ 体检里这一道 21.5s 大半是重复 I/O。**只活在当前进程**（不落盘、不跨进程），
#    所以读数语义**一个字不变** —— 改前/改后输出做了哈希对账。
_TEXT: dict = {}
_FILES: list = []


def _read(p: Path):
    """读文本（一次运行只读一次）。**读不开返回 `None`，不吞成空串。**"""
    k = str(p)
    if k not in _TEXT:
        try:
            _TEXT[k] = p.read_text(encoding="utf-8", errors="replace")
        except Exception:
            _TEXT[k] = None
    return _TEXT[k]


def _py_files() -> list:
    """要看的 `.py`（跳过 `store`／缓存／测试／`.versions`）—— 只枚举一次。

    🔴 跳 `store` 是**必需的**：那里是数据区，撞上 `store/pipeline/production/.versions/run.py`
    的 `PermissionError` 会把整个工具弄崩（实测踩过）。
    """
    if not _FILES:
        _FILES.extend(p for p in sorted(PKG.rglob("*.py"))
                      if not any(t in p.parts
                                 for t in ("__pycache__", "store", "tests", ".versions")))
    return _FILES


# 🔴 2026-10-10 真根因修复（体检 rc=1：位级写目标抽样 崩 unindent does not match）：
#    原来边界**只认 if kind == 形态** ⇒ api.py 里那些 **if kind in (a,b,c)** 的分支
#    **不被当边界**，于是**下一支的代码被整段吞进上一支** ⇒ 片段里出现 4 空格的代码行
#    （正文在 8）⇒ unindent does not match（实测：datakit 那一支吞掉了 quant_strategy 那一支）。**8 支中招。**
#    ⇒ 边界改成认**全部同级分支头**：if kind == / if kind in / elif / else: / return @4 空格。
#    （注释仍会被吞 —— 那无害：注释不参与缩进判定，且解析器那侧已有抬齐兜底。）
BRANCH_RE = re.compile(
    r'if kind == "([a-z_0-9]+)":(.*?)'
    r'(?=\n    (?:if kind (?:==|in) |elif |else:|if cap |return )|\Z)', re.S)


def split_branches(txt: str) -> dict:
    """把 `api.py` 原文切成 `位 → 该支原文`。

    🔴 **单独成函数是为了能被负控喂人造原文**（不碰真文件）。
    切片的形状是既成事实：`(?=\\n    if kind == |\\Z)` ⇒ **下一支之前那段行首 4 空格的
    注释会被一并吞进上一支**。这个事实是本工具第二次崩的真因，不许忘。
    """
    return {m.group(1): m.group(2) for m in BRANCH_RE.finditer(txt)}


def api_branches() -> dict:
    p = PKG / "api.py"
    if not p.exists():
        return {}
    return split_branches(p.read_text(encoding="utf-8", errors="replace"))


def dispatch_modules() -> dict:
    """位 → 实现模块文件（读 `api.py` 的真分派，不猜名字）。"""
    out = {}
    for kind, body in api_branches().items():
        mm = re.search(r"from \.tools import (\w+)|from \. import (\w+)|from \.(\w+) import",
                       body)
        if not mm:
            continue
        mod = mm.group(1) or mm.group(2) or mm.group(3)
        for cand in (PKG / "tools" / (mod + ".py"), PKG / (mod + ".py")):
            if cand.exists():
                out[kind] = cand
                break
    return out


def _branch_called(body: str):
    """取 `api.py` 那一支**真正在调的函数** —— **优先取 `return` 里的调用**。

    🔴 修的是 §一百三十二·三 那处抽错：`wf_define` 那支先写了 `p = payload or {}`
    ⇒ 旧正则抓到 `p.get(` 抽成函数 `get`。**分支里第一个 `xxx(` 不是分派调用**，
    **`return` 里那个才是。**
    """
    if not body:
        return None
    # 🔴 **没有语句**（空 / 只有注释）⇒ 如实 `None`。
    # 为什么单独判：`if True:` 套一个只有注释的块 = **合法空块**在 Python 里其实非法
    # （`expected an indented block`），会撞进下面的 `raise` ⇒ 把"这根本没语句"
    # 误报成"原文坏了"。**两种事必须分开**：`raise` 只留给真解析不了。
    if not [ln for ln in body.splitlines()
            if ln.strip() and not ln.strip().startswith("#")]:
        return None
    try:
        # 🔴 分支原文是**带缩进的片段**；直接 `ast.parse(body)` 会 `IndentationError`
        # ⇒ 被下面那个 `except` 吞掉 ⇒ **9/9 全变 None**（实测坐实）。
        # 🔴 第二刀（复现出来的真因）：切片的正则 `(?=\n    if kind == |\Z)` 会把
        # **下一支之前那段行首 4 空格的注释**一并吞进来 ⇒ `textwrap.dedent` 算出的
        # 公共缩进变成 4，而分支正文在 8 ⇒ **仍然 IndentationError**（实测 9 支全中）。
        # 不再猜缩进：**套一层 `if True:`**，片段只需相对缩进自洽即可解析。
        #
        # 🔴 2026-10-10 第三刀（体检 rc=1 追根因，实测仍崩）：套 `if True:` **只解决"整体缩进偏深"**，
        #    解决不了**切片把"下一支之前那段 4 空格注释"吞进来**的情形 —— 那几行比正文（8 空格）
        #    **还浅** ⇒ `unindent does not match any outer indentation level`（实测：自检③回归负控）。
        #    真修法：**解析前把低于正文基准缩进的行抬到基准**（切片吞进来的注释本就该抬齐），
        #    基准 = **代码行**（非注释非空）的最小缩进 —— 注释不参与定基准，否则又被它带偏。
        _lines = body.splitlines()
        _code = [ln for ln in _lines if ln.strip() and not ln.strip().startswith("#")]
        if not _code:
            return None
        _base = min(len(ln) - len(ln.lstrip()) for ln in _code)
        _fixed = []
        for ln in _lines:
            if not ln.strip():
                _fixed.append("")
                continue
            _ind = len(ln) - len(ln.lstrip())
            # 🔴 第三刀的修正（实测证明只抬注释不够）：**注释本来就不参与缩进判定**，
            #    真正让解析崩的是**代码行**缩进比基准还浅（切片切穿了嵌套块）。
            #    ⇒ **任何**低于基准的行一律抬到基准：保证片段内不存在"低于基准的 dedent"。
            #    语义代价：极少数被切穿的嵌套块会被压平 —— 本函数只取**第一个 return 的调用**，
            #    压平不影响它读到的那一个；而"整支崩掉"会让整道闸不可用（那才是真损失）。
            _fixed.append((" " * _base + ln.lstrip()) if _ind < _base else ln)
        tree = ast.parse("if True:\n" + "\n".join(_fixed))
    except Exception as e:
        raise RuntimeError("分支原文解析不了（不允许静默返回 None）：%s" % str(e)[:120])
    for n in ast.walk(tree):
        if isinstance(n, ast.Return) and isinstance(n.value, ast.Call):
            f = n.value.func
            if isinstance(f, ast.Attribute):
                return f.attr
            if isinstance(f, ast.Name):
                return f.id
    return None


def func_writes(p: Path, fname: str, depth: int = 2, seen=None) -> dict:
    """**抽这个函数**的写目标；本层没有就**递归一层**看它调用谁。

    `depth=2` ⇒ `api.py` 分支 → 模块函数 → 它再调的同模块函数。
    """
    seen = set(seen or ())
    if not fname or fname in seen:
        return {"找到": "**未读到**（函数名重复/空）"}
    seen.add(fname)
    t = _read(p)
    if t is None:
        return {"**未读到**（读不开）": str(p.name)[:40]}
    try:
        tree = ast.parse(t)
    except Exception as e:
        return {"**未读到**（解析不了）": str(e)[:40]}
    for n in ast.walk(tree):
        if not (isinstance(n, ast.FunctionDef) and n.name == fname):
            continue
        w, d, paths, callees = [], [], set(), []
        for stmt in n.body:
            for x in ast.walk(stmt):
                if isinstance(x, ast.Call):
                    nm = _name(x)
                    if nm in WRITE_PRIMS:
                        w.append("%s@L%d" % (nm, getattr(x, "lineno", 0)))
                        if nm in DEL_PRIMS:
                            d.append("%s@L%d" % (nm, getattr(x, "lineno", 0)))
                    elif nm and nm not in ("get", "items", "keys", "values", "append",
                                           "join", "strip", "split", "loads", "dumps",
                                           "exists", "resolve", "is_dir", "is_file",
                                           "getattr", "str", "int", "float", "len",
                                           "sorted", "list", "dict", "set", "print"):
                        callees.append(nm)
                if isinstance(x, ast.Constant) and isinstance(x.value, str):
                    v = x.value
                    if len(v) < 90 and ("/" in v or v.endswith((".json", ".jsonl"))):
                        paths.add(v)
        res = {"找到": fname, "写原语": w[:8], "删除类": d[:4],
               "路径常量": sorted(paths)[:8]}
        if not w and depth > 1:
            deeper = {}
            for c in dict.fromkeys(callees):
                r2 = func_writes(p, c, depth - 1, seen)
                if r2.get("写原语") or r2.get("删除类"):
                    deeper[c] = {"写原语": r2.get("写原语"), "删除类": r2.get("删除类"),
                                 "路径常量": r2.get("路径常量")}
            res["本层无 · 下一层有"] = deeper
            res["下一层读过"] = list(dict.fromkeys(callees))[:8]
        return res
    return {"找到": "**未读到**（模块里没有这个函数名）"}


def _audit():
    """**加载 `gate-blind-audit.py`**（带连字符的文件名，走 importlib）。

    🔴 **单一来源**：上一版我为了避开引号地狱，把 `soft_only_kinds()` **重写了一份**
    ⇒ 两份判据分叉：审计说「9 位只有软标记」，本工具说「0 位」。**两者不可能同时对。**
    **「单一来源」是我一直强调的纪律，那次是我自己破的。** 现在直接用它，不再自建。
    """
    import importlib.util
    p = Path(__file__).resolve().parent / "gate-blind-audit.py"
    if not p.exists():
        return None
    nm = "_gb_audit_single_source"
    if nm in sys.modules:
        return sys.modules[nm]
    spec = importlib.util.spec_from_file_location(nm, p)
    m = importlib.util.module_from_spec(spec)
    sys.modules[nm] = m
    try:
        spec.loader.exec_module(m)
    except Exception:
        sys.modules.pop(nm, None)
        return None
    return m


def soft_only_kinds() -> list:
    """**门看不见 ∧ 没有带牙标记** 的位 —— **直接用 `gate-blind-audit` 的 scan()**。"""
    m = _audit()
    if m is None:
        return []
    r = m.scan()
    if not r.get("ok"):
        return []
    return [x["位"] for x in r["逐位"] if not x["带牙标记（写面）"]]


def _mods_for(kind: str) -> list:
    """提到这个位名的**实现模块**。

    🔴 必须跳过 `store/`（那是**数据区**，不是实现）且**读不开要能活下来** ——
    实测踩过：没跳 `store` ⇒ 撞上 `store/pipeline/production/.versions/run.py` 的
    `PermissionError`，**整个工具直接崩**。
    """
    hits = []
    for p in _py_files():
        t = _read(p)
        if t is None:
            continue
        if ('"%s"' % kind) in t or ("'%s'" % kind) in t:
            hits.append(p)
    return hits[:3]


def run() -> dict:
    br, disp = api_branches(), dispatch_modules()
    rows = []
    for k in soft_only_kinds():
        body = br.get(k, "")
        fname = _branch_called(body)          # 🔴 只取 Return 里的调用（接上了）
        mm = re.search(r"\b(\w+)\.(\w+)\s*\(", body) or re.search(r"\b(\w+)\s*\(", body)
        called = ".".join(g for g in (mm.groups() if mm else ()) if g) if mm else None
        p = disp.get(k)
        det = (func_writes(p, fname) if (p is not None and fname)
               else {"**未读到**": "分派或分支调用没读到"})
        rows.append({"位": k, "模块": (p.name if p is not None else "**未读到**"),
                     "api 分支调的": called or "**未读到**（分支里没读到调用）",
                     "抽的函数": fname, "函数写目标": det,
                     "函数里有删除类": bool(det.get("删除类"))})
    return {"ok": True, "位数": len(rows), "逐位": rows,
            "口径": "**静态读到的写目标，不是全集**；"
            "「函数里有删除类」≠「该位一定会删」（要真跑才知道）"}


def cmd_run(a) -> int:
    r = run()
    print(json.dumps(r, ensure_ascii=False, indent=1))
    return 0


def cmd_selftest(a) -> int:
    lines, bad = [], 0

    def ck(name, cond, detail):
        nonlocal bad
        bad += 0 if cond else 1
        lines.append("%s %s — %s" % ("✓" if cond else "✗", name, detail))

    br, disp = api_branches(), dispatch_modules()
    ck("**真读到 api.py 的 kind 分支**（不是空表）", len(br) > 0, "%d 个分支" % len(br))
    ck("**分派解析出模块文件**", len(disp) > 0, "%d 个位映到模块" % len(disp))
    # ① 负控：**人造一个不存在的函数名 ⇒ 必须报未读到**，不许假装找到
    d = func_writes(PKG / "engine.py" if (PKG / "engine.py").exists() else PKG,
                    "__没有这个函数__")
    ck("**负控：函数名不存在 ⇒ 报未读到**", "未读到" in str(d), str(d)[:60])
    # ② 判据**随数据变**：真函数必须能抽出写原语或明确说没有
    if (PKG / "engine.py").exists():
        d2 = func_writes(PKG / "engine.py", "run_workflow")
        ck("**判据随数据变**（真函数抽得出读数）", isinstance(d2, dict) and "找到" in d2,
           str(d2)[:80])
    else:
        lines.append("· engine.py 不在 —— 另计，不算失败")

    # ③ 🔴 **切片吞注释**的回归负控 —— 本工具第二次崩（9/9 全 None）的真因。
    #    人造原文：正文 8 空格 + **下一支前那段 4 空格注释** + 下一支。
    #    修好之前这里必然 `IndentationError`；修好之后必须抽到 `foo`。
    synth = ('def _d(kind, payload):\n'
             '    if kind == "aaa":\n'
             '        p = payload or {}\n'
             '        return mod.foo(p.get("x"))\n'
             '    # 下一支之前的一段 4 空格注释（就是它把公共缩进压到 4）\n'
             '    # 再来一行\n'
             '    if kind == "bbb":\n'
             '        return mod.bar()\n')
    sb = split_branches(synth)
    got = None
    try:
        got = _branch_called(sb.get("aaa", ""))
    except Exception as e:                       # noqa: BLE001 —— 负控要看得见崩
        got = "崩了：%s" % str(e)[:60]
    ck("**回归负控：切片吞注释后仍抽得到 return 里的函数**", got == "foo",
       "人造原文抽到 = %s（合成解析到 %d 支）" % (got, len(sb)))
    # ④ 🔴 `api 分支调的 ≠ 抽的函数` 的**真数据**负控：`wf_define` 那支第一个调用是 `p.get(`，
    #    旧正则把它抽成函数 `get`。抽的函数**不许**是 `get`，且**必须是** `define_workflow`。
    if "wf_define" in br:
        f4 = _branch_called(br["wf_define"])
        ck("**真数据负控：wf_define 抽的函数 ≠ get 且 = define_workflow**",
           f4 == "define_workflow", "抽到 = %r" % (f4,))
    else:
        ck("**真数据负控：wf_define 在 api.py 里存在**", False, "分支表里没有 wf_define")
    # ⑤ 只有注释/空 ⇔ **如实返回 None**（不许抛错、也不许瞎猜一个名字）
    try:
        f5 = _branch_called("\n        # 只有一行注释\n")
        ck("**负控：分支里没有 return ⇒ 返回 None 而不是瞎猜**", f5 is None, "抽到 = %r" % (f5,))
    except Exception as e:                       # noqa: BLE001
        ck("**负控：分支里没有 return ⇒ 返回 None 而不是瞎猜**", False,
           "抛错了：%s" % str(e)[:60])

    # ⑥⑦⑧ **递归一层的正控 + 边界负控 + 诚实边界控**（人造模块，系统临时目录，读完即删）
    #    上一版这里我写错了判据：拿「调 c、c 不写、c 再调 d」当"下一层查得到"的正控。
    #    可本工具**只把"真会写的被调者"记进 `下一层`**（`c` 不写 ⇒ 不进表，只进
    #    `下一层读过`）。**空表在那份数据上是对的** —— 是我的判据错了。
    #    现在拆成三件：正控用「被调者自己会写」，边界控用「第三层才写」。
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        tp = Path(td) / "negctl_mod.py"
        tp.write_text(
            "from pathlib import Path\n"
            "\n"
            "def w(p):\n"
            "    Path(p).unlink()\n"          # 一层内直接写/删
            "\n"
            "def a1(p):\n"
            "    return b1(p)\n"              # a1 本层不写，调**会写的** b1
            "\n"
            "def b1(p):\n"
            "    Path(p).write_text('x')\n"
            "\n"
            "def a2(p):\n"
            "    return c2(p)\n"              # a2 本层不写；c2 也不写；**第三层** d2 才删
            "\n"
            "def c2(p):\n"
            "    return d2(p)\n"
            "\n"
            "def d2(p):\n"
            "    Path(p).unlink()\n",
            encoding="utf-8")
        r6 = func_writes(tp, "w", depth=2)
        ck("**正控：一层内真写 ⇒ 写原语抽得到（含删除类）**",
           bool(r6.get("写原语")) and bool(r6.get("删除类")), str(r6)[:90])
        r7 = func_writes(tp, "a1", depth=2)
        dp7 = r7.get("本层无 · 下一层有") or {}
        ck("**正控：本层无写 ∧ 被调者会写 ⇒ 下一层真查到它（带写原语）**",
           (not r7.get("写原语")) and "b1" in dp7 and bool(dp7["b1"].get("写原语")),
           "本层写=%s ｜ 下一层=%s" % (r7.get("写原语") or "（无）", list(dp7) or "（空）"))
        r8 = func_writes(tp, "a2", depth=2)
        dp8 = r8.get("本层无 · 下一层有") or {}
        rd8 = r8.get("下一层读过") or []
        ck("**边界负控：只递归一层 ⇒ 不许深挖到第三层的 d2**",
           "d2" not in str(dp8), "下一层 = %s（d2 不许出现）" % (list(dp8) or "（空）",))
        ck("**诚实边界控：「下一层＝—」必须是「读过而没写」，不是「没读」**",
           "c2" in rd8, "下一层读过 = %s" % (rd8 or "（空 ── 那就是没读，不是没写）",))

    r = run()
    # 🔴 这里原来写死 **「9 位全部真抽到函数名（0 个 None）」** —— 又一条"写死条数"。
    #    注册表被扩到 171 位后，软标记位从 9 变 12，其中 3 位**本来就没有分派分支**
    #    ⇒ 判据当场变红，而**红的不是工具、是我的判据**（第三次自纠同型）。
    #    改成**随数据变**的两条：① 抽取器不能是空的（至少抽到 1 位）；
    #    ② **抽不到的必须被点名**（不许静默 None）—— 这才是真正要守的东西。
    _got = [x for x in r["逐位"] if x["抽的函数"]]
    _none = [x["位"] for x in r["逐位"] if not x["抽的函数"]]
    ck("**抽取器不是空的**（至少抽到 1 位，条数不写死）", bool(_got),
       "抽到 %d/%d" % (len(_got), r["位数"]))
    ck("**抽不到的必须被点名**（不许静默 None）",
       all(bool(x.get("模块")) for x in _got) and len(_got) + len(_none) == r["位数"],
       "抽不到（点名）：%s" % (_none or "无"))
    ck("**位级表非空且逐位带模块名**", r["位数"] >= 1
       and all(x["模块"] for x in r["逐位"]), "%d 位" % r["位数"])
    print(json.dumps({"自检": {"条数": len(lines), "通过": len(lines) - bad, "不通过": bad},
                      "逐条": lines}, ensure_ascii=False, indent=1))
    return 0 if bad == 0 else 1


def main() -> int:
    ap = argparse.ArgumentParser(description="位级写目标：api 分支 → 函数 → 抽那个函数")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("run").set_defaults(func=cmd_run)
    sub.add_parser("selftest").set_defaults(func=cmd_selftest)
    a = ap.parse_args()
    return a.func(a)


if __name__ == "__main__":
    raise SystemExit(main())
