# -*- coding: utf-8 -*-
"""GBT小土豆V8 · **项目级代码结构四面**（2026-09-23 接，补 `project_context` 的代码面）。

## 为什么要有这件

`project_context` 原先只是**文档检索层**（blueprint / brief / search / status）——
对"专业级编程AI"来说那是**半身**：它知道**文档**写了什么，不知道**代码**长什么样。
本件补上代码结构四面，**全部只读**：

    symbols  符号面 —— 每个文件顶层定义了哪些函数/类；按名字问"它在哪定义"
    deps     依赖面 —— 内部模块之间的 import 边 + 外部三方名（谁依赖谁）
    calls    调用图面 —— **复用现成的 `tools/call_graph.py`**（不重造）
    tests    测试面 —— 每个模块被哪些测试文件**提到**过；哪些一个都没被提到

## 铁律：**不造第五套口径**

  · 遍历一律走 `tools/scan_scope.py` 的 `iter_files`（`SKIP_DIRS` 的单一来源）
    —— 第一版 `call_graph.build(仓根)` 吞了 `store/`/`.scratch/`：**78 秒 / 6615 文件 /
    18 万符号 / 未解析率 0.827**，塞进能力位必超时。按**代码根**建图是 **4.2 秒 / 351 文件**。
  · 调用图一律走 `call_graph` 的 `build/find/callers/callees/trace/dead_code/impact`
    —— 它的 `dead_code` 已经分了 `dead/suspect/as_value` 三桶，**不把"解析不出来"说成"没人用"**。

## 诚实边界（每一面都带出去，不许读成更强的东西）

  · `symbols` 只收**顶层** def/class（方法、嵌套函数**不算**）—— 那是有意的：不是"全符号表"
  · `deps` 只看 **import 语句**（运行期动态导入、字符串里的模块名**不算**）
  · `calls` 的**未解析率**必须一并报出：本仓 `gbt_allinone` 根下 **0.662** ——
    也就是说"谁调用了 X"这类结论**先天带缺口**，`dead_code` 的 `dead` 桶同理
  · `tests` 是"**提到过**"的代理，**不是行覆盖**；没被提到 ≠ 没被测，被提到 ≠ 测得好
"""
from __future__ import annotations

import ast
import json
import re
import time
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]          # 仓根
_PKG = Path(__file__).resolve().parents[1]           # gbt_allinone/（默认代码根）

_SAMPLE = 40
_MAX_FILES = 4000


class CodeStructureError(ValueError):
    """用法/参数类错误（带机读 code）。继承 `ValueError`：框架约定这类错误要抛。"""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


def _scoped_files(root: Path, suffixes=(".py",)) -> list:
    """按**审计器同一套** `SKIP_DIRS` 收集文件（范围口径只留一份实现）。"""
    import sys
    tools = str(_PKG / "tools")
    if tools not in sys.path:
        sys.path.insert(0, tools)
    from scan_scope import iter_files                       # noqa: E402
    out = []
    for p in iter_files(root, suffixes):
        out.append(Path(p))
        if len(out) >= _MAX_FILES:
            break
    return sorted(out)


def _code_root(root=None) -> Path:
    """代码根：默认 `gbt_allinone/`；给了就必须**落在仓内**（与 code_patch 同一条规矩）。"""
    if not root:
        return _PKG
    p = Path(str(root))
    p = (p if p.is_absolute() else (_ROOT / p)).resolve()
    try:
        p.relative_to(_ROOT)
    except ValueError:
        raise CodeStructureError("outside_repo", "代码根不在仓内：%s" % str(p)[:120]) from None
    if not p.is_dir():
        raise CodeStructureError("not_a_dir", "不是目录：%s" % str(p)[:120])
    return p


# ── 面 1：符号 ──────────────────────────────────────────────────────────────
def symbols(root=None, name: str = "", limit: int = _SAMPLE) -> dict:
    base = _code_root(root)
    files = _scoped_files(base)
    by_file, hits, unparsed = {}, [], []
    total = 0
    want = str(name or "").strip()
    for f in files:
        try:
            tree = ast.parse(f.read_text(encoding="utf-8", errors="replace"), filename=str(f))
        except SyntaxError:
            unparsed.append(str(f.relative_to(_ROOT)).replace("\\", "/"))
            continue
        defs = []
        for n in tree.body:
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                kind = "class" if isinstance(n, ast.ClassDef) else "def"
                defs.append((n.name, kind, n.lineno))
                total += 1
                if want and n.name == want:
                    hits.append({"path": str(f.relative_to(_ROOT)).replace("\\", "/"),
                                 "name": n.name, "kind": kind, "line": n.lineno})
        if defs:
            by_file[str(f.relative_to(_ROOT)).replace("\\", "/")] = len(defs)
    top = sorted(by_file.items(), key=lambda kv: -kv[1])[:limit]
    return {"status": "ok", "readonly": True, "face": "symbols",
            "root": str(base.relative_to(_ROOT)).replace("\\", "/"),
            "files": len(files), "symbols_total": total, "unparsed_n": len(unparsed),
            "top_files": [{"path": p, "defs": n} for p, n in top],
            "query": want, "matches": hits if want else [],
            "boundary": "只收**顶层** def/class（方法/嵌套不算）；unparsed 是**未知**不是干净"}


# ── 面 2：依赖 ──────────────────────────────────────────────────────────────
def deps(root=None, limit: int = _SAMPLE) -> dict:
    base = _code_root(root)
    files = _scoped_files(base)
    local_tops = _local_tops(base)
    internal_edges, external, unparsed = [], {}, []
    for f in files:
        try:
            tree = ast.parse(f.read_text(encoding="utf-8", errors="replace"), filename=str(f))
        except SyntaxError:
            unparsed.append(str(f.relative_to(_ROOT)).replace("\\", "/"))
            continue
        rel = str(f.relative_to(_ROOT)).replace("\\", "/")
        for n in ast.walk(tree):
            mods = []
            if isinstance(n, ast.Import):
                mods = [a.name for a in n.names]
            elif isinstance(n, ast.ImportFrom):
                if n.level:                                   # 相对导入 = 内部
                    internal_edges.append({"from": rel, "to": ("." * n.level) + (n.module or "")})
                    continue
                mods = [n.module or ""]
            for m in mods:
                if not m:
                    continue
                top = m.split(".")[0]
                # 自家人 = 包名本身，或代码根下的顶层包/模块名（两种情况都算内部边）
                if top == "gbt_allinone" or top in local_tops:
                    internal_edges.append({"from": rel, "to": m})
                else:
                    external[top] = external.get(top, 0) + 1
    ext = sorted(external.items(), key=lambda kv: -kv[1])[:limit]
    return {"status": "ok", "readonly": True, "face": "deps",
            "root": str(base.relative_to(_ROOT)).replace("\\", "/"),
            "files": len(files), "internal_edges_n": len(internal_edges),
            "internal_edges_sample": internal_edges[:limit],
            "external_top": [{"name": n, "count": c} for n, c in ext],
            "unparsed_n": len(unparsed),
            "boundary": "只看 **import 语句**；运行期动态导入与字符串里的模块名**不算**"}


def _local_tops(base: Path) -> set:
    """代码根下的顶层包/模块名（用来判"裸名 import 是不是自家人"）。"""
    out = set()
    try:
        for c in base.iterdir():
            if c.is_dir() and (c / "__init__.py").is_file():
                out.add(c.name)
            elif c.suffix == ".py":
                out.add(c.stem)
    except OSError:
        pass
    return out


def _plain(obj, depth: int = 0):
    """把 `call_graph` 的**活对象**（`Symbol` / `Edge` …）转成**纯数据**。

    🔴 为什么必须转（本轮实测抓到）：`CG.find()` 返回的是 `Symbol` 实例，
    **不可 JSON 序列化** ⇒ 能力位的返回体、审计落盘、面板渲染**全都会炸**。
    这是"不要把活对象当普通 JSON 交出去"的典型违例 —— 边界上必须自己建成最小数据对象。
    """
    if depth > 6:
        return str(obj)[:200]
    if obj is None or isinstance(obj, (bool, int, float, str)):
        return obj
    if isinstance(obj, dict):
        return {str(k): _plain(v, depth + 1) for k, v in obj.items()}
    if isinstance(obj, (list, tuple, set)):
        return [_plain(v, depth + 1) for v in obj]
    if hasattr(obj, "__dict__"):                       # Symbol / Edge 这类数据类
        return {k: _plain(v, depth + 1) for k, v in vars(obj).items()}
    if hasattr(obj, "_asdict"):                        # namedtuple
        return {k: _plain(v, depth + 1) for k, v in obj._asdict().items()}
    return str(obj)[:200]


def _cap(obj, n: int = 60):
    """按类型封顶，**不假设返回的是 list**。

    🔴 本轮实测：`CG.callers()` 返回的是 **dict**（不是 list），
    我直接写 `_plain(...)[:60]` ⇒ `KeyError: slice(None, 60, None)` 当场炸。
    教训：**别人家的返回形状要现读，不许按印象切**。
    """
    if isinstance(obj, list):
        return obj[:n]
    if isinstance(obj, dict):
        return {k: (_cap(v, n) if isinstance(v, (list, dict)) else v) for k, v in obj.items()}
    return obj


# ── 面 3：调用图（**复用 call_graph，不重造**）───────────────────────────────
def calls(root=None, name: str = "", what: str = "callers",
          depth: int = 3, do_dead: bool = False) -> dict:
    base = _code_root(root)
    from . import call_graph as CG
    t0 = time.time()
    g = CG.build(str(base))
    st = CG.stats(g)
    out = {"status": "ok", "readonly": True, "face": "calls",
           "root": str(base.relative_to(_ROOT)).replace("\\", "/"),
           "elapsed_ms": int((time.time() - t0) * 1000),
           "stats": {k: st.get(k) for k in ("files", "unparsed", "symbols",
                                            "calls_total", "unresolved_ratio")},
           # 🔴 这条必须跟着结果一起走：未解析率三成以上时，"谁没调用谁"是**有缺口**的结论
           "boundary": "未解析率见 stats.unresolved_ratio（本仓 gbt_allinone 根下约 0.66）—— "
                       "『没人调用』这类结论**先天带缺口**，不许读成死代码证明"}
    if do_dead:
        d = CG.dead_code(g)
        out["dead_code"] = {"dead_n": len(d.get("dead") or []),
                            "suspect_n": len(d.get("suspect") or []),
                            "as_value_n": len(d.get("as_value") or []),
                            "note": d.get("note")}
    if name:
        if what == "callers":
            out["callers"] = _cap(_plain(CG.callers(g, name)))
        elif what == "callees":
            out["callees"] = _cap(_plain(CG.callees(g, name)))
        elif what == "trace":
            out["trace"] = _cap(_plain(CG.trace(g, name, int(depth))), 120)
        elif what == "find":
            out["find"] = _cap(_plain(CG.find(g, name)))
        else:
            raise CodeStructureError("bad_what",
                                     "what 只认 callers/callees/trace/find，收到 %s" % what)
    return out


# ── 面 4：测试 ──────────────────────────────────────────────────────────────
_TEST_FILE_RE = re.compile(r"^test_.*\.py$")


def tests(root=None, limit: int = _SAMPLE) -> dict:
    base = _code_root(root)
    srcs = [p for p in _scoped_files(base) if not _TEST_FILE_RE.match(p.name)]
    tf = [p for p in _scoped_files(_ROOT, (".py", ".cjs"))
          if _TEST_FILE_RE.match(p.name) or p.parent.name == "tests"]
    # 🔴 一次分词，别对每个模块在全部测试文件上重跑正则：
    #    第一版是 `re.search(模块名, 每个测试文件全文)` —— 266 模块 × 101 文件 = 2.7 万次
    #    大字符串正则，实测 **10.7s**。改成"每个测试文件只分词一次"后降到亚秒级。
    tokens_of: dict = {}
    for p in tf:
        try:
            txt = p.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        tokens_of[p] = set(re.findall(r"[A-Za-z_][A-Za-z0-9_]{2,}", txt))
    mentioned, unmentioned, skipped = {}, [], []
    seen_stems: dict = {}
    for s in srcs:
        stem = s.stem
        seen_stems[stem] = seen_stems.get(stem, 0) + 1
        if stem.startswith("_") or len(stem) < 3:
            skipped.append(str(s.relative_to(_ROOT)).replace("\\", "/"))
            continue
        who = [str(t.relative_to(_ROOT)).replace("\\", "/")
               for t, toks in tokens_of.items() if stem in toks]
        if who:
            mentioned[str(s.relative_to(_ROOT)).replace("\\", "/")] = who
        else:
            unmentioned.append(str(s.relative_to(_ROOT)).replace("\\", "/"))
    # 🔴 计数**按文件**，不按 stem（本轮实测抓到）：第一版 `mentioned` 以 **stem 为键**，
    #    同名文件（如两处 `call_graph.py`）会被折叠 ⇒ `提到 + 没提到 + 跳过 != 源文件数`
    #    （实测 167+78+16=261 ≠ 266，差 5）。**计数不平就是读数坏了**，不是"四舍五入"。
    dup_stems = sorted(k for k, n in seen_stems.items() if n > 1)
    return {"status": "ok", "readonly": True, "face": "tests",
            "root": str(base.relative_to(_ROOT)).replace("\\", "/"),
            "source_modules_n": len(srcs), "test_files_n": len(tokens_of),
            "mentioned_n": len(mentioned), "unmentioned_n": len(unmentioned),
            "skipped_n": len(skipped),
            "duplicate_stems_n": len(dup_stems),
            "unmentioned_sample": unmentioned[:limit],
            "boundary": "这是**提到过**的代理，**不是行覆盖**："
                        "没被提到 ≠ 没被测，被提到 ≠ 测得好；"
                        "skipped 是名字过短/下划线开头的（没参与统计，不是「干净」）"}


def structure(root=None, limit: int = _SAMPLE) -> dict:
    """三面速览（符号/依赖/测试）—— **刻意不含调用图**：那一面 4.2s，按需单独调。"""
    return {"status": "ok", "readonly": True, "face": "structure",
            "symbols": {k: v for k, v in symbols(root, limit=6).items()
                        if k in ("files", "symbols_total", "unparsed_n", "top_files")},
            "deps": {k: v for k, v in deps(root, limit=8).items()
                     if k in ("files", "internal_edges_n", "external_top", "unparsed_n")},
            "tests": {k: v for k, v in tests(root, limit=8).items()
                      if k in ("source_modules_n", "test_files_n", "mentioned_n",
                               "unmentioned_n", "unmentioned_sample")},
            "how_to_get_calls": "py -3.14 -c \"from gbt_allinone.tools import code_structure as C;"
                                "import json;print(json.dumps(C.calls(what='find',name='run_task'),"
                                "ensure_ascii=False))\"",
            "boundary": "三面都只读；调用图面单独调（4.2s / 351 文件），不在速览里"}
