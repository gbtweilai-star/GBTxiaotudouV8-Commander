# gbt-capability: dynamic-import
"""跨文件调用图（`call_graph`）—— 从 codebase-memory-mcp 提炼、用我们自己的栈重写。

## 它从哪来

2026-09-22，风哥给了 `paysssk-creator/codebase-memory-mcp`（上游 `DeusData/codebase-memory-mcp`，MIT）
让「蒸馏提炼合适自己的能力」。读透它的核心后，**结论是提炼方法与模型、不安装**，三条硬理由：

1. **它自己写明会改写 agent 配置文件** —— 原文：*"This tool reads your codebase and **writes to your
   agent configuration files**. That is what it is designed to do."* 而本机 `.claude`/`.codex`/
   `.gemini`/`.agents` **四个目录都在** ⇒ 它会真去写我们的指令面。**那是门之外的组件。**
2. **它给 Claude Code 装 PreToolUse 钩子拦截 Grep/Glob** ⇒ 插进我们的工具链。
3. **本机一个 C/C++ 编译器都没有**（gcc/clang/cl/make/cmake/zig/tcc 全无），
   它又是纯 C 单二进制 ⇒ "从源码构建"这条路在本机不可行，只剩"下预编译二进制"。

## 提炼了什么（它的图模型 → 我们的实现）

| 它的东西 | 我们这里 |
|---|---|
| 节点 `Module/Class/Function/Method` | ✅ 用 AST 建，限定名 `模块::类.方法` |
| 边 `IMPORTS` | ✅ `import a.b` / `from a.b import c` / 相对导入都解析 |
| 边 `CALLS`（**import-aware 解析**） | ✅ 裸名 / `self.m()` / 模块别名 / 点号链 |
| `trace_path`（BFS，谁调用我/我调用谁） | ✅ `trace(name, depth, direction)` |
| 死代码检测（零调用者，排除入口） | ✅ `dead_code()`，**并加了一道它没有的闸**（见下） |
| `detect_changes`（git diff → 受影响符号） | ✅ `impact(paths)` 反向可达 |
| 持久化 SQLite 图 | ✅ `store/call_graph.sqlite3` |

## 我们比它多做的一道闸（这条最重要）

它的死代码检测是 **AST 零调用者**。**在我们的仓里这会误杀**：我们有大量**按名字派单**的接线
—— `caps_registry.py` 里 `"handler": "browser"` 这种字符串映射、`_READ_ONLY_TENTACLE` 这类名字集合、
`getattr(t, name)`。**这些函数在 AST 上一个调用者都没有，但它们是被调用的。**

所以 `dead_code()` 分两桶，**不把"解析不出来"说成"没人用"**：

- `dead`：AST 无调用者 **且** 全仓没有任何字符串字面量提到这个名字 ⇒ 才敢说是死的
- `suspect`：AST 无调用者 **但** 名字出现在字符串里 ⇒ 可能是**按名派单**，**要人看**，不当判决

## 诚实边界（不许把绿当安心）

1. **动态调用解析不出来**：`getattr`、`importlib`、字符串派单、装饰器注册 —— 一律进 `suspect`。
   输出里始终给 `unresolved_calls` 占比；**这个数高，就说明这张图不完整。**
2. 只解析**我们自己的 .py**；`store/`、`.pylibs/` 按理由跳过（会报出来）。
3. `impact` 是**反向可达**，不是编译器的精确影响面。

开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属
"""

from __future__ import annotations

import argparse
import ast
import json
import sqlite3
import sys
import warnings as _w
from dataclasses import dataclass, field
from pathlib import Path

_SKIP_DIRS = {"__pycache__", ".git", "node_modules", ".pytest_cache", ".mypy_cache"}
_SKIPPED_NOT_SOURCE = {
    "store": "运行时数据（含代码副本），不是源码",
    ".pylibs": "自带第三方依赖树",
    "archived_logs": "历史日志归档",
}
_DB_ENV = "GBT_CALL_GRAPH_DB"
_DEFAULT_DB = Path(__file__).resolve().parents[1] / "store" / "call_graph.sqlite3"

# 入口/约定名：这些**天然没有调用者**，不该进死代码
_ENTRY_OK = {"__init__", "__main__", "__enter__", "__exit__", "__call__", "__repr__",
             "__str__", "__eq__", "__hash__", "__len__", "__iter__", "__next__",
             "run", "main", "apply", "handler", "register", "setup", "teardown",
             "setUp", "tearDown", "test_", "do_GET", "do_POST", "do_OPTIONS"}


@dataclass
class Symbol:
    qual: str          # 模块::类.方法
    module: str
    name: str
    kind: str          # function | method | class
    lineno: int
    path: str


@dataclass
class Graph:
    symbols: dict = field(default_factory=dict)
    calls: list = field(default_factory=list)        # (caller_qual, callee_qual, raw)
    imports: list = field(default_factory=list)      # (module, imported_module)
    unresolved: list = field(default_factory=list)   # (caller_qual, raw, why)
    resolved_by_unique: list = field(default_factory=list)  # 第二遍："全仓同名且唯一"认下的
    files: int = 0
    unparsed: list = field(default_factory=list)
    skipped: dict = field(default_factory=dict)
    strings: set = field(default_factory=set)        # 全仓字符串字面量（用于按名派单的交叉核对）
    # 以**值**形式被引用过的名字（不是被调用）。
    # 为什么必须有：`app.on("run", on_run)`、`functools.partial(f)`、装饰器注册这类写法，
    # 函数**没有被调用**但**确实在用**。首轮只看调用，把这类判成了"死代码" —— 那是误杀。
    referenced: set = field(default_factory=set)


def _iter_py(root: Path, g: Graph):
    for p in sorted(root.rglob("*.py")):
        parts = set(p.parts)
        if parts & _SKIP_DIRS:
            continue
        hit = next((d for d in _SKIPPED_NOT_SOURCE if d in parts), None)
        if hit:
            n, _why = g.skipped.get(hit, (0, _SKIPPED_NOT_SOURCE[hit]))
            g.skipped[hit] = (n + 1, _SKIPPED_NOT_SOURCE[hit])
            continue
        yield p


def _mod_name(root: Path, p: Path) -> str:
    rel = p.relative_to(root).with_suffix("")
    parts = [x for x in rel.parts if x != "__init__"]
    return ".".join(parts) if parts else "__init__"


class _Collector(ast.NodeVisitor):
    def __init__(self, module: str, path: str, g: Graph):
        self.module = module
        self.path = path
        self.g = g
        self.stack: list[str] = []       # 类名栈
        self.fn_stack: list[str] = []    # 函数限定名栈
        # 本模块的导入绑定：短名 -> 全限定名
        self.aliases: dict[str, str] = {}
        # 本模块顶层导入的模块全名
        self.imported_modules: set[str] = set()

    # ── 收集导入绑定 ──
    def visit_Import(self, node: ast.Import):
        """`import a.b` 与 `import a.b as m` **绑定的名字不同**，必须分开处理。

        实测教训（2026-09-22 首轮）：把两者都当别名，`pkg.a.alpha()` 会被拼成
        `pkg.a` + `.` + `a.alpha` = `pkg.a.a.alpha` —— **直接解析错**。
          · `import a.b`      ⇒ 绑顶层名 `a`；原文点号路径本身就是对的，**不设别名**
          · `import a.b as m` ⇒ 绑 `m` ⇒ `m.f()` 要还原成 `a.b.f`
        """
        for a in node.names:
            self.imported_modules.add(a.name)
            if a.asname:
                self.aliases[a.asname] = a.name
            self.g.imports.append((self.module, a.name))
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom):
        base = ("." * (node.level or 0)) + (node.module or "")
        if not base.startswith("."):
            self.imported_modules.add(node.module or "")
            self.g.imports.append((self.module, node.module or ""))
        for a in node.names:
            if a.name == "*":
                continue
            self.aliases[(a.asname or a.name)] = (base + "." + a.name) if base else a.name
        self.generic_visit(node)

    # ── 收集定义 ──
    def _define(self, node, kind: str):
        cls = ".".join(self.stack)
        short = ("%s.%s" % (cls, node.name)) if cls else node.name
        qual = "%s::%s" % (self.module, short)
        self.g.symbols[qual] = Symbol(qual=qual, module=self.module, name=node.name,
                                      kind=kind, lineno=node.lineno, path=self.path)
        return qual

    def visit_ClassDef(self, node: ast.ClassDef):
        self._define(node, "class")
        self.stack.append(node.name)
        self.generic_visit(node)
        self.stack.pop()

    def visit_FunctionDef(self, node):  # noqa: N802
        self._fn(node, "method" if self.stack else "function")

    def visit_AsyncFunctionDef(self, node):  # noqa: N802
        self._fn(node, "method" if self.stack else "function")

    def _fn(self, node, kind: str):
        qual = self._define(node, kind)
        self.fn_stack.append(qual)
        # 默认值里的调用也算
        for d in list(node.args.defaults) + [x for x in node.args.kw_defaults if x]:
            self.visit(d)
        for child in node.body:
            self.visit(child)
        self.fn_stack.pop()

    # ── 收集调用点 ──
    def visit_Call(self, node: ast.Call):
        if self.fn_stack:
            caller = self.fn_stack[-1]
            raw = self._dotted(node.func)
            callee, why = self._resolve(raw)
            if callee:
                self.g.calls.append((caller, callee, raw))
            else:
                self.g.unresolved.append((caller, raw, why))
        self.generic_visit(node)

    def visit_Constant(self, node: ast.Constant):
        if isinstance(node.value, str) and 0 < len(node.value) <= 120:
            self.g.strings.add(node.value)
        self.generic_visit(node)

    def visit_Name(self, node: ast.Name):
        """记下**以值形式被引用**的名字（Load 上下文）。

        `on_run` 单独出现（当参数传走、放进列表、做装饰器目标）时它不是 Call，
        但它**在被用**。死代码检测必须知道这件事，否则会误杀回调。
        """
        if isinstance(node.ctx, ast.Load):
            self.g.referenced.add(node.id)
        self.generic_visit(node)

    @staticmethod
    def _dotted(node) -> str:
        if isinstance(node, ast.Name):
            return node.id
        if isinstance(node, ast.Attribute):
            base = _Collector._dotted(node.value)
            return ("%s.%s" % (base, node.attr)) if base else node.attr
        return ""

    def _to_qual(self, dotted: str) -> str | None:
        """点号路径 → 我们的限定名（`模块::名`）。**只在仓里真有这个符号时才认。**

        为什么要有这一步：`from pkg.a import alpha` 的绑定是点号串 `pkg.a.alpha`，
        而符号表里的键是 `pkg.a::alpha` —— 不换算就生成一条**指向不存在节点**的边，
        `callers` 会全空。实测踩过（2026-09-22 首轮，跨文件查询全是空）。
        """
        parts = dotted.split(".")
        for i in range(len(parts) - 1, 0, -1):
            cand = ".".join(parts[:i]) + "::" + ".".join(parts[i:])
            if cand in self.g.symbols:
                return cand
        return None

    def _resolve(self, raw: str) -> tuple[str | None, str]:
        """把调用点解析成限定名。**解析不出来就如实说为什么，不猜。**"""
        if not raw:
            return None, "非名字调用（如 lambda/下标）"
        head, _, rest = raw.partition(".")
        # self.m() / cls.m() → 同类方法。
        # ⚠️ **rest 里有点号就不是方法名**（`self._pending.clear()`）：属性上没有类型信息，
        #    追不到。首轮没拦这个，造出 6,217 条 `类._pending.clear` 这种**悬空边**
        #    —— 边"有"，节点不存在，查询全空还没人发现。现在由 `dangling_edges` 兜底自查。
        if head in ("self", "cls"):
            if not self.stack:
                return None, "self/cls 出现在类外"
            if "." in rest:
                return None, "self.<属性>.<方法> —— 属性上没有类型信息，追不到"
            # 沿类栈由内向外找（支持嵌套类）。**找不到就如实说找不到，绝不许编一个限定名出来。**
            # 实测教训（2026-09-22）：触手是 9 个 mixin 合成的，A mixin 里写 `self.m()` 而
            # `m` 定义在 B mixin 上 —— 我只在所在类里找，找不到就返回 `A.m`（不存在），
            # 一次造出 5,841 条悬空边。同理 `self.send_response` 是 stdlib 基类的，也该是 unresolved。
            for i in range(len(self.stack), 0, -1):
                cand = "%s::%s.%s" % (self.module, ".".join(self.stack[:i]), rest)
                if cand in self.g.symbols:
                    return cand, ""
            return None, ("self.%s 不在本类（可能是别的 mixin 或基类）"
                          "—— 交第二遍按「全仓同名唯一」认" % rest)
        # 导入别名：import a.b as m; m.f()  /  from X import y;  y()
        if head in self.aliases:
            dotted = self.aliases[head] + (("." + rest) if rest else "")
            q = self._to_qual(dotted)
            if q:
                return q, ""
            return None, "导入绑定 %s 换算后仓里没有这个符号（可能是第三方）" % dotted
        # 本模块内的函数/类（**含遮蔽内建的情形**：本模块 def len 之后 len() 就是它）
        local = "%s::%s" % (self.module, raw)
        if local in self.g.symbols:
            return local, ""
        # 当前类的方法（裸名）
        if self.stack:
            m = "%s::%s.%s" % (self.module, ".".join(self.stack), raw)
            if m in self.g.symbols:
                return m, ""
        # 点号路径直接换算（`import pkg.a; pkg.a.f()`）
        if rest:
            q = self._to_qual(raw)
            if q:
                return q, ""
            return None, "点号链无法追（对象方法，AST 追不到类型）"
        return None, "裸名未在本模块或导入绑定里找到"


def build(root: str | Path) -> Graph:
    root = Path(root).expanduser().resolve()
    g = Graph()
    for p in _iter_py(root, g):
        rel = str(p.relative_to(root))
        try:
            text = p.read_text(encoding="utf-8", errors="replace")
            with _w.catch_warnings():
                _w.simplefilter("ignore")
                tree = ast.parse(text)
        except (SyntaxError, ValueError, OSError) as e:
            g.unparsed.append("%s: %s: %s" % (rel, type(e).__name__, str(e)[:70]))
            continue
        g.files += 1
        _Collector(_mod_name(root, p), rel, g).visit(tree)
    _second_pass(g)
    return g


def _second_pass(g: Graph) -> None:
    """第二遍：用「**全仓同名且唯一**」这条**可靠**规则再解析一批。

    为什么这条不算猜：如果整个仓里叫这个名字的符号**只有一个**，那么任何对它的
    调用就只可能指向它 —— 这是**唯一解**，不是启发式。

    三条不许越的线：
      · **多解一律不认**（重名就留在 unresolved，交给 `dead_code` 的 suspect 桶）
      · **Python 内建名不认**（`len`/`print` 之类；否则会给内建乱接主人）
      · 解析出来的边**单独计数**（`resolved_by_unique`），与 import-aware 那批**分开报**，
        这样"哪一批是靠唯一性认的"永远看得见。
    """
    import builtins as _b
    by_name: dict[str, set] = {}
    by_tail2: dict[str, set] = {}          # `类.方法` 两段式
    for s in g.symbols.values():
        by_name.setdefault(s.name, set()).add(s.qual)
        tail = s.qual.split("::", 1)[-1].split(".")
        if len(tail) >= 2:
            by_tail2.setdefault(".".join(tail[-2:]), set()).add(s.qual)
    builtin_names = set(dir(_b))

    still: list = []
    for caller, raw, why in g.unresolved:
        segs = raw.split(".")
        last = segs[-1]
        hit: set = set()
        if last in builtin_names or len(segs) < 1:
            still.append((caller, raw, why))
            continue
        # ① 先试两段式 `类.方法`（更具体）
        if len(segs) >= 2:
            hit = by_tail2.get(".".join(segs[-2:]), set())
        # ② 两段式不唯一 ⇒ 退回裸名
        if len(hit) != 1:
            hit = by_name.get(last, set())
        if len(hit) == 1:
            g.resolved_by_unique.append((caller, next(iter(hit)), raw))
        else:
            why2 = why if len(hit) == 0 else "全仓有 %d 个同名符号 ⇒ 多解，不认" % len(hit)
            still.append((caller, raw, why2))
    g.unresolved = still


def save(g: Graph, db: str | Path | None = None) -> Path:
    path = Path(db or _DEFAULT_DB)
    path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(str(path))
    con.execute("PRAGMA journal_mode=WAL")
    con.executescript("""
        DROP TABLE IF EXISTS symbols; DROP TABLE IF EXISTS calls;
        DROP TABLE IF EXISTS imports; DROP TABLE IF EXISTS unresolved;
        CREATE TABLE symbols (qual TEXT PRIMARY KEY, module TEXT, name TEXT,
                              kind TEXT, lineno INT, path TEXT);
        CREATE TABLE calls (caller TEXT, callee TEXT, raw TEXT, via TEXT);
        CREATE TABLE imports (module TEXT, imported TEXT);
        CREATE TABLE unresolved (caller TEXT, raw TEXT, why TEXT);
        CREATE INDEX ix_calls_callee ON calls(callee);
        CREATE INDEX ix_calls_caller ON calls(caller);
    """)
    con.executemany("INSERT INTO symbols VALUES (?,?,?,?,?,?)",
                    [(s.qual, s.module, s.name, s.kind, s.lineno, s.path)
                     for s in g.symbols.values()])
    # `via` 把"这条边靠哪一遍认下的"永久留在库里 —— 将来复核时能只看 import-aware 那批
    con.executemany("INSERT INTO calls VALUES (?,?,?,?)",
                    [(c, t, raw, "import_aware") for c, t, raw in g.calls]
                    + [(c, t, raw, "unique_name") for c, t, raw in g.resolved_by_unique])
    con.executemany("INSERT INTO imports VALUES (?,?)", g.imports)
    con.executemany("INSERT INTO unresolved VALUES (?,?,?)", g.unresolved)
    con.commit()
    con.close()
    return path


def stats(g: Graph) -> dict:
    tot = len(g.calls) + len(g.resolved_by_unique) + len(g.unresolved)
    # 完整性自查：**悬空边** = callee 不在符号表里。实测教训（首轮跨文件 bug）：
    # 曾经生成过一批 `pkg.a.alpha` 这种点号形式的边 —— 边"有"，但节点不存在，
    # `callers` 全空而没人发现。这个数**必须能被看见**。
    known = set(g.symbols)
    dangling = [e for e in all_edges(g) if e[1] not in known]
    return {"files": g.files, "unparsed": len(g.unparsed), "symbols": len(g.symbols),
            "calls_import_aware": len(g.calls),
            "calls_by_unique_name": len(g.resolved_by_unique),
            "calls_unresolved": len(g.unresolved),
            "calls_total": tot,
            "unresolved_ratio": round(len(g.unresolved) / tot, 4) if tot else 0.0,
            "dangling_edges": len(dangling),
            "dangling_sample": sorted({(c, t) for c, t, _ in dangling})[:5],
            "imports": len(g.imports), "strings": len(g.strings),
            "skipped": {k: v[0] for k, v in g.skipped.items()}}


def all_edges(g: Graph):
    """已解析的全部边（两遍合起来）。查询都走这里，避免只看到第一遍。"""
    return list(g.calls) + list(g.resolved_by_unique)


def find(g: Graph, name: str) -> list[Symbol]:
    """按短名或限定名找符号。短名可命中多个（同名不同模块）—— **全给出来，不替人挑**。"""
    if "::" in name:
        return [g.symbols[name]] if name in g.symbols else []
    return [s for s in g.symbols.values() if s.name == name]


def callers(g: Graph, name: str) -> dict:
    hits = find(g, name)
    if not hits:
        return {"ok": False, "error": "找不到符号：%s（先 search 一下确切名字）" % name}
    out = []
    for s in hits:
        who = sorted({c for c, t, _ in all_edges(g) if t == s.qual})
        out.append({"symbol": s.qual, "path": s.path, "lineno": s.lineno, "callers": who})
    return {"ok": True, "count": sum(len(o["callers"]) for o in out), "results": out}


def callees(g: Graph, name: str) -> dict:
    hits = find(g, name)
    if not hits:
        return {"ok": False, "error": "找不到符号：%s" % name}
    return {"ok": True, "results": [
        {"symbol": s.qual, "callees": sorted({t for c, t, _ in all_edges(g) if c == s.qual})}
        for s in hits]}


def trace(g: Graph, name: str, depth: int = 3, direction: str = "both") -> dict:
    """BFS 追链。**每一跳都带 raw（原文写法）**，方便人核对解析对不对。"""
    hits = find(g, name)
    if not hits:
        return {"ok": False, "error": "找不到符号：%s" % name}
    start = hits[0].qual
    adj: dict[str, list] = {}
    for c, t, raw in all_edges(g):
        if direction in ("both", "out"):
            adj.setdefault(c, []).append((t, raw, "out"))
        if direction in ("both", "in"):
            adj.setdefault(t, []).append((c, raw, "in"))
    seen, frontier, levels = {start}, [start], []
    for d in range(int(depth)):
        nxt = []
        for n in frontier:
            for t, raw, dr in adj.get(n, []):
                if t in seen:
                    continue
                seen.add(t)
                nxt.append(t)
                levels.append({"depth": d + 1, "direction": dr, "from": n, "to": t, "raw": raw})
        frontier = nxt
        if not frontier:
            break
    return {"ok": True, "start": start, "depth": int(depth), "reached": len(seen) - 1,
            "hops": levels}


def dead_code(g: Graph) -> dict:
    """零调用者的符号，**分三桶** —— 不把"解析不出来"或"以值被用"说成"没人用"。

    · `dead`    ：AST 无调用者 **且** 没被当值引用 **且** 名字不出现在任何字符串里 ⇒ 才敢说死
    · `suspect` ：名字出现在字符串里 ⇒ 可能**按名派单**（我们仓大量如此）
    · `as_value`：被当值引用过（回调 / 装饰器 / partial）⇒ **在用，只是没被"调用"**
    """
    called = {t for _, t, _ in all_edges(g)}
    used_strings = g.strings
    dead, suspect, as_value = [], [], []
    for s in g.symbols.values():
        if s.kind == "class":
            continue
        if s.name in _ENTRY_OK or s.name.startswith("test_") or s.name.startswith("_"):
            continue
        if s.qual in called:
            continue
        row = {"symbol": s.qual, "path": s.path, "lineno": s.lineno}
        if s.name in used_strings:
            suspect.append(row)
        elif s.name in g.referenced:
            row["why"] = "以值被引用（回调/装饰器/partial 之类）—— 在用，不是死"
            as_value.append(row)
        else:
            dead.append(row)
    return {"ok": True, "dead": dead, "suspect": suspect, "as_value": as_value,
            "note": "suspect = 名字在字符串里（可能按名派单）；as_value = 被当值传出去；"
                    "两桶**都要人看，不是判决**"}


def impact(g: Graph, paths) -> dict:
    """给改动的文件，反向可达出受影响的符号（`detect_changes` 的蒸馏版）。"""
    if isinstance(paths, str):
        paths = [paths]
    touched = {s.qual for s in g.symbols.values()
               if any(str(p).replace("\\", "/") in s.path.replace("\\", "/") for p in paths)}
    radj: dict[str, set] = {}
    for c, t, _ in all_edges(g):
        radj.setdefault(t, set()).add(c)
    seen, frontier = set(touched), list(touched)
    while frontier:
        nxt = []
        for n in frontier:
            for up in radj.get(n, ()):
                if up not in seen:
                    seen.add(up)
                    nxt.append(up)
        frontier = nxt
    affected = sorted(seen - touched)
    return {"ok": True, "changed_files": list(paths), "touched_symbols": sorted(touched),
            "affected_callers": affected[:200], "affected_count": len(affected)}


def report(g: Graph) -> str:
    s = stats(g)
    L = ["# CALL GRAPH REPORT", "",
         "| 项 | 值 |", "|---|---|",
         "| 解析文件 | %d |" % s["files"],
         "| **未解析文件** | **%d** |" % s["unparsed"],
         "| 符号 | %d |" % s["symbols"],
         "| 调用边 · import-aware 认下 | %d |" % s["calls_import_aware"],
         "| 调用边 · 「全仓同名唯一」认下 | %d |" % s["calls_by_unique_name"],
         "| **调用点（解析不出）** | **%d** |" % s["calls_unresolved"],
         "| **解析率缺口（两遍之后）** | **%.1f%%** |" % (s["unresolved_ratio"] * 100),
         "| 导入边 | %d |" % s["imports"], ""]
    if s["unresolved_ratio"] > 0.35:
        L += ["> ⚠️ **解析不出的调用点占比 %.0f%%** —— 这张图**不完整**，"
              "`dead_code` 的结论要打折看。\n" % (s["unresolved_ratio"] * 100)]
    if g.unparsed:
        L += ["## 未解析的文件（**没被看过**）", ""] + ["- `%s`" % u for u in g.unparsed[:30]]
    if g.skipped:
        L += ["", "## 按理由跳过的目录", "", "| 目录 | 文件数 | 理由 |", "|---|---|---|"]
        for d, (n, why) in sorted(g.skipped.items()):
            L += ["| `%s` | %d | %s |" % (d, n, why)]
    L += ["", "> 开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属"]
    return "\n".join(L)


def _cli() -> int:
    ap = argparse.ArgumentParser(description="跨文件调用图（零依赖）")
    ap.add_argument("root", help="代码根（通常 gbt_allinone）")
    ap.add_argument("--db", default="")
    ap.add_argument("--save", action="store_true", help="落库")
    ap.add_argument("--stats", action="store_true")
    ap.add_argument("--report", default="")
    ap.add_argument("--callers", default="")
    ap.add_argument("--callees", default="")
    ap.add_argument("--trace", default="")
    ap.add_argument("--depth", type=int, default=3)
    ap.add_argument("--dead", action="store_true")
    a = ap.parse_args()

    g = build(a.root)
    if a.save:
        print("saved:", save(g, a.db or None))
    if a.report:
        Path(a.report).write_text(report(g), encoding="utf-8")
        print("report:", a.report)
    if a.callers:
        print(json.dumps(callers(g, a.callers), ensure_ascii=False, indent=1))
    if a.callees:
        print(json.dumps(callees(g, a.callees), ensure_ascii=False, indent=1))
    if a.trace:
        print(json.dumps(trace(g, a.trace, a.depth), ensure_ascii=False, indent=1))
    if a.dead:
        d = dead_code(g)
        print(json.dumps({"dead": len(d["dead"]), "suspect": len(d["suspect"]),
                          "as_value": len(d["as_value"]),
                          "sample_dead": d["dead"][:10]}, ensure_ascii=False, indent=1))
    if a.stats or not any([a.save, a.report, a.callers, a.callees, a.trace, a.dead]):
        print(json.dumps(stats(g), ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(_cli())
