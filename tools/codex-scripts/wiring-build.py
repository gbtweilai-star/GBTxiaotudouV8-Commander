# -*- coding: utf-8 -*-
"""wiring-build.py —— `state/model-pack/wiring.json` 的**写手**（以前没有写手，只有 .scratch 一次性脚本）。

## 为什么补这一件（2026-10-19 当场查出来的洞）
`impact_check` 读的 `state/model-pack/wiring.json` 是 `.scratch/_persist_graph.py` 从
`.scratch/wiring_full.json` 一次性折出来的 —— **它没有生产者**。这正是本仓 P9 那一型
（「账没有写手必烂」）：仓一变，图就悄悄过期，而 `impact_check` 还会拿着旧世界给读数，
读起来和真的没区别。

## 顺带修掉第二个洞（这是我上一轮自己标的「未验」）
旧图把边**拍平**了：`page 提到 cap:create 这个名字` 与 `code import 某模块` 长得一模一样。
于是 `--top` 排出来的是「谁被提到得最多」（cap:create 2619），不是「谁真被依赖」。
而 `outputs/repo-pack/edges.jsonl` 里**本来就有 kind**（`path` / `cap` / `cap_mention`，
由 `repo-pack.py refs` 写出）—— 是折图那一步把类型丢了。本件保留类型：

    strong 边 = path 引用 + cap 真引用 + 绑定账（tent/carrier/handler）
    weak   边 = cap_mention（页面/文档里只是**提到**这个能力名）

产出两份邻接：
    adj        全边（影响面「能波及到哪」用这个，宁可宽）
    strong_adj 只含强边（「改完必须真验」用这个，才是真依赖）

## 判据（非零退出 = 图不可用）
- edges.jsonl 不存在 / 一条边都没读到 ⇒ 红
- 节点数 < 100 ⇒ 红（形状明显不对，别拿它当图）
- 连通分量 > 1 且最大分量占比 < 90% ⇒ 报出来（不红，但必须看见）

用法：
  py -3.14 tools/codex-scripts/wiring-build.py
  py -3.14 tools/codex-scripts/wiring-build.py --check    # 只比对新旧规模，不写盘
"""
from __future__ import annotations

import argparse
import collections
import json
import math
import os
import re
import sys
import time
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    if hasattr(_s, "reconfigure"):
        _s.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parents[2]
EDGES = ROOT / "outputs" / "repo-pack" / "edges.jsonl"
FILES = ROOT / "outputs" / "repo-pack" / "files.jsonl"
BINDINGS = ROOT / "state" / "cap-bindings.json"
OUT = ROOT / "state" / "model-pack" / "wiring.json"

CODE_EXT = {".py", ".js", ".mjs", ".cjs", ".ts", ".tsx", ".jsx", ".sh", ".ps1", ".cmd", ".bat"}
PAGE_EXT = {".html", ".htm", ".md", ".txt", ".json", ".jsonl", ".csv", ".svg", ".css",
            ".yml", ".yaml", ".toml", ".ini", ".cfg", ".xml"}
TREE_EXT = CODE_EXT | PAGE_EXT | {
    # 目录树层的收录范围要**更宽**：CODE_EXT/PAGE_EXT 是给 `_node_for_path` 做分类用的，
    # 而"只要是文件就没有不可以接的"（主人令）—— 少一种后缀就是少一批连通节点。
    ".sql", ".java", ".rb", ".go", ".rs", ".c", ".h", ".hpp", ".cc", ".cpp",
    ".vue", ".svelte", ".kt", ".swift", ".php", ".pl", ".lua", ".r", ".m", ".mm",
    ".cs", ".fs", ".scala", ".dart", ".ex", ".exs", ".erl", ".hs", ".clj",
    ".zig", ".nim", ".asm", ".s", ".in", ".env", ".dockerignore", ".editorconfig",
    ".gitignore", ".gitattributes", ".properties", ".gradle", ".lock", ".patch", ".diff",
}
WEAK_KINDS = {"cap_mention"}

# ── 权重口径（**唯一定义处** · 2026-11-04 主人令「以触手当权重」）─────────────
# 之前 `adj` 是 `set`，83529 行原始边里重复出现的**共现次数**被 `set.add()` 抹掉，
# 四类边平权 ⇒ 图只能答"通不通"，答不了"谁更该被点亮"。
# 现在一次扫描同时产出：无权 `adj`（向后兼容，impact_check 在用）+ 加权 `wadj`。
#
# 口径写进产物（`weight_rule` 字段），读端校验版本；**改公式必须同时 bump 版本**，
# 否则旧权重会配新边 —— 那种错不报错，只是悄悄算偏。
# v2 → v3（2026-11-05）：新增 Python import 层 `import` 边（KIND_BASE["import"]=1.0）。
# 血账：edges.jsonl 只有 path/cap/cap_mention 三类，**全是"文本提及"**，从来没解析过
# import。于是 api.py 里明明写着 `from . import codex_bridge as _CB`，图里 api.py 与
# codex_bridge.py 之间却是 0 条边 —— 只能靠 cap 位 2 跳绕过去，权重被低估。
# v3 → v4（2026-11-05）：新增 `impl` 边（cap → 实现文件，KIND_BASE["impl"]=1.2）。
# 依据：cap↔code 此前只靠"文件里出现能力名"建立，可实现文件往往**不含**能力名
# （codex_bridge.py 里没有 "codex_tools" 四个字，派发写在 api.py）。结果 7 个 codex
# 能力位到本体永远是 2 跳。现在从 api.py 的 `if kind == "x"` 分支静态挖实现模块。
WEIGHT_RULE_VERSION = 4
KIND_BASE = {"cap": 1.0, "dispatch": 1.0, "import": 1.0, "impl": 1.2, "path": 0.5,
             "cap_mention": 0.15, "bind": 1.2, "tree": 0.4}
WEIGHT_FORMULA = "sum(KIND_BASE[kind] * log1p(count[kind]))"

# 分派比较（**补齐已知抽取缺口** · 2026-10-19）：
# repo-pack 的强边正则只认 `cap x` / `run_task("x")` / `"kind": "x"` / `kind = "x"`，
# **不认 `if kind == "x":`** —— 而本仓的派发件（api.py 等）恰恰全是这种写法。
# 后果实测：`code:gbt_allinone/api.py` 强边只有 67 条，而它真的派发 300+ 个能力位。
# 所以这里自己补一遍分派模式（只读仓内 code: 件，单件 ≤2MB），补出来的边按 kind="dispatch" 计。
DISPATCH_PATTERNS = (
    re.compile(r"""kind\s*==\s*["']([a-z][a-z0-9_]{1,40})["']"""),
    re.compile(r"""kind\s+in\s*\(([^)]{1,400})\)"""),
    re.compile(r"""run_task\(\s*["']([a-z][a-z0-9_]{1,40})["']"""),
    re.compile(r"""["']kind["']\s*:\s*["']([a-z][a-z0-9_]{1,40})["']"""),
    re.compile(r"""kind\s*=\s*["']([a-z][a-z0-9_]{1,40})["']"""),
)
DISPATCH_EXT = (".py", ".js", ".mjs", ".cjs")
DISPATCH_MAX = 2 << 20
_QUOTED = re.compile(r"""["']([a-z][a-z0-9_]{1,40})["']""")

# import 补边（v3）：只认 Python，走 AST 不猜字符串。别名 `as` 不影响结果 ——
# 我们连的是**模块**，不是符号；`from . import codex_bridge as _CB` 与
# `import gbt_allinone.codex_bridge` 产出同一条边。只连图内已有的 .py 节点，
# 不新增节点（新增节点会改 nodes 计数，_verify_payload 会拦）。
IMPORT_EXT = (".py",)
IMPORT_MAX = 2 << 20


# 图的范围（**显式写死，不靠猜**）：这张图回答"改我们自己的东西会撞到谁"，
# 所以第三方树与一次性草稿不进图 —— 它们不是我们的依赖面，进来只会把分量打散。
# 留痕（2026-10-19）：不加这个清单时全量重建出 44,154 节点 / 945 个分量（最大 90.8%），
# 小的那些基本全落在 _upstream / .agents 这类别人的树里。
GRAPH_EXCLUDE_PREFIX = (
    "_upstream/", ".agents/", ".scratch/", ".git/", ".pylibs/",
    "outputs/repo-pack/", "outputs/workspace-scan/", "gbt_allinone/store/",
    "node_modules/",
)


def _excluded(p: str) -> bool:
    q = str(p or "").replace("\\", "/")
    return any(q.startswith(x) for x in GRAPH_EXCLUDE_PREFIX)



_SCHEME = re.compile(r"^[A-Za-z][A-Za-z0-9+.\-]*:")
_JUNK = re.compile(r"[\s\"'`{}()\[\]<>|*?]|^[-+@#]|\.\.\.|^[A-Za-z_]+=")


def _resolve_path(src: str, dst: str) -> str:
    """把 edges.jsonl 里的 `path` 边目标**真解析成仓内文件**；解析不出来就返回空（丢弃）。

    留痕（2026-10-19 实测）：旧图是 `.scratch` 里一次性折出来的"精选子集"；我第一版直接从
    edges.jsonl 全量重建，得到 **109,549 节点**（旧图 6301），因为 `path` 边把
    `https:` / `mailto:` / `localhost` / 代码片段里的 `...,to` 全当成了仓内路径。
    ⇒ 现在三条闸：① 有 scheme（`xxx:`）一律丢 ② 含空白/引号/括号/通配等"不像路径"的字符丢
    ③ 必须是**盘上真存在**的文件（先按仓根解析，再按 src 同目录解析）。宁可少一条边，也不留脏节点。
    """
    d = str(dst or "").strip().replace("\\", "/")
    if not d or len(d) > 300:
        return ""
    if _SCHEME.match(d) or "://" in d:
        return ""
    if _JUNK.search(d) or d.startswith("/") or d.startswith("~"):
        return ""
    cands = [d]
    src_dir = os.path.dirname(str(src or "").replace("\\", "/"))
    if src_dir:
        cands.append(os.path.normpath(src_dir + "/" + d).replace("\\", "/"))
    for c in cands:
        if (ROOT / c).is_file():
            return c
    return ""


def _node_for_path(p: str) -> str:
    p = str(p or "").replace("\\", "/").strip()
    if not p:
        return ""
    if ":" in p.split("/")[0]:
        return p                          # 已经是带前缀的节点名
    ext = ("." + p.rsplit(".", 1)[-1].lower()) if "." in p.rsplit("/", 1)[-1] else ""
    if ext in CODE_EXT:
        return "code:" + p
    if ext in PAGE_EXT:
        return "page:" + p
    return "code:" + p                    # 未知后缀按代码件（宁可归错类，也不丢节点）


def _dir_chain(p: str) -> list:
    """文件路径 → 目录链，由深到浅，末项是 `dir:.`（仓根）。

    `gbt_allinone/docs/A.md` → ['dir:gbt_allinone/docs', 'dir:gbt_allinone', 'dir:.']
    """
    parts = [x for x in str(p or "").replace("\\", "/").split("/") if x][:-1]
    return ["dir:" + ("/".join(parts[:i]) or ".") for i in range(len(parts), -1, -1)]


# ── 权重 ────────────────────────────────────────────────────────────────────
def _pk(a: str, b: str) -> tuple:
    """无向边主键（排序后），保证 (a,b) 与 (b,a) 落同一个桶。"""
    return (a, b) if a <= b else (b, a)


def _edge_weight(kinds: dict) -> float:
    """边权 = Σ KIND_BASE[kind] × log1p(count)。口径见 WEIGHT_RULE_VERSION。"""
    w = 0.0
    for k, n in kinds.items():
        if n > 0:
            w += KIND_BASE.get(k, 0.5) * math.log1p(n)
    return w


# ── 原子写（主人令 2026-11-04：「使用原子替换别把权重搞污染了」）────────────────
# 旧写法 `OUT.write_text(...)` 会先 truncate 再写：窗口期内文件是空的，
# 中途崩溃就留一个截断的 JSON，`impact_check` 下次读直接炸。
# 而且"旧权重配新边"不报错、只是悄悄算偏 —— 比崩溃更阴。
# 这里四道闸：写前自校验 → 备份旧件 → 临时文件 + fsync + os.replace → 读回校验。
def _atomic_write_text(path: Path, text: str) -> None:
    """同目录临时文件 + fsync + os.replace。Windows 同卷 replace 是原子的。

    失败时删掉临时文件，原文件**一个字节都不动**。
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name("%s.tmp-%d-%d" % (path.name, os.getpid(), int(time.time() * 1000)))
    try:
        with open(tmp, "w", encoding="utf-8", newline="") as fh:
            fh.write(text)
            fh.flush()
            os.fsync(fh.fileno())          # 先落到盘，再改名
        os.replace(tmp, path)              # 原子替换
    except BaseException:
        try:
            tmp.unlink()
        except OSError:
            pass
        raise


def _verify_payload(d: dict, expect_nodes: int, expect_und: int) -> list:
    """写前/写后同一套校验。返回问题清单，空 = 合格。"""
    bad = []
    if d.get("nodes") != expect_nodes:
        bad.append("节点数 %r != 期望 %d" % (d.get("nodes"), expect_nodes))
    if d.get("edges") != expect_und:
        bad.append("无向边 %r != 期望 %d" % (d.get("edges"), expect_und))
    adj = d.get("adj") or {}
    sadj = d.get("strong_adj") or {}
    wadj = d.get("wadj") or {}
    if len(adj) != expect_nodes:
        bad.append("adj 键数 %d != %d" % (len(adj), expect_nodes))
    # 加权图必须与无权图**同边集**，否则就是两张不同的图拼在一起
    real_und = sum(len(v) for v in adj.values()) // 2
    if real_und != expect_und:
        bad.append("adj 实算无向边 %d != %d" % (real_und, expect_und))
    if len(wadj) != len(adj):
        bad.append("wadj 键数 %d != adj %d（加权图与无权图不同源）" % (len(wadj), len(adj)))
    # 逐点比对邻接：wadj 的邻居集合必须等于 adj
    mismatch = 0
    for k, nbrs in adj.items():
        wn = wadj.get(k)
        if wn is None:
            mismatch += 1
            continue
        if set(wn) != set(nbrs):
            mismatch += 1
    if mismatch:
        bad.append("%d 个节点的 wadj 邻居与 adj 不一致" % mismatch)
    # 权重必须是正有限数
    badw = 0
    for k, wn in wadj.items():
        for nb, w in wn.items():
            if not isinstance(w, (int, float)) or not (w > 0) or w != w or w == float("inf"):
                badw += 1
    if badw:
        bad.append("%d 条边权不是正有限数" % badw)
    # 强边必须是全边的子集
    extra = sum(1 for k, v in sadj.items() if k in adj and not set(v) <= set(adj[k]))
    if extra:
        bad.append("%d 个强边节点的邻居不在全边里" % extra)
    return bad


def build() -> tuple:
    if not EDGES.is_file():
        return None, {"ok": False, "error": "missing_edges",
                      "why": "没有 %s —— 先跑 py -3.14 tools/codex-scripts/repo-pack.py refs"
                             % EDGES.relative_to(ROOT)}
    adj = collections.defaultdict(set)
    strong = collections.defaultdict(set)
    kcnt = collections.defaultdict(collections.Counter)   # (a,b) -> {kind: 次数}
    by_kind = collections.Counter()
    n = 0
    dropped = 0
    t0 = time.time()
    with EDGES.open(encoding="utf-8") as fh:
        for line in fh:
            try:
                e = json.loads(line)
            except ValueError:
                continue
            src, dst, kind = e.get("src"), e.get("dst"), e.get("kind", "path")
            if not src or not dst:
                continue
            if _excluded(src):
                continue
            a = _node_for_path(src)
            if kind in ("cap", "cap_mention"):
                b = "cap:" + str(dst)
            else:
                r = _resolve_path(src, dst)
                if not r or _excluded(r):
                    dropped += 1
                    continue
                b = _node_for_path(r)
            if not a or not b or a == b:
                continue
            n += 1
            by_kind[kind] += 1
            kcnt[_pk(a, b)][kind] += 1          # ← 共现次数（旧版被 set.add() 抹掉）
            adj[a].add(b)
            adj[b].add(a)
            if kind not in WEAK_KINDS:
                strong[a].add(b)
                strong[b].add(a)

    # 分派比较补边（见 DISPATCH_PATTERNS 的留痕）：只读 code: 件，把 kind==/kind in/run_task 认成强边
    dispatch_n = 0
    try:
        sys.path.insert(0, str(ROOT))
        from gbt_allinone.caps_tables import all_caps
        cap_names = {c.get("name") for c in all_caps() if c.get("name")}
    except Exception:                                          # noqa: BLE001
        cap_names = set()
    if cap_names:
        for node in list(adj):
            if not node.startswith("code:"):
                continue
            rel = node[5:]
            if os.path.splitext(rel)[1].lower() not in DISPATCH_EXT:
                continue
            p = ROOT / rel
            try:
                if p.stat().st_size > DISPATCH_MAX:
                    continue
                text = p.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            found = set()
            for pat in DISPATCH_PATTERNS:
                for m in pat.finditer(text):
                    g = m.group(1)
                    if g in cap_names:
                        found.add(g)
                    else:                                          # kind in (...) 这种给的是名字列表
                        found |= {x for x in _QUOTED.findall(g) if x in cap_names}
            for cn in found:
                if node not in strong or ("cap:" + cn) not in strong[node]:
                    dispatch_n += 1
                b = "cap:" + cn
                kcnt[_pk(node, b)]["dispatch"] += 1
                adj[node].add(b); adj[b].add(node)
                strong[node].add(b); strong[b].add(node)
        by_kind["dispatch"] = dispatch_n

    # ── import 补边（v3 · 留痕见 KIND_BASE["import"]）────────────────────────
    # 与 dispatch 补边同构：只读图内 code: 件、只连**已存在**的节点、统一走
    # kcnt/adj/strong 三条路 —— 于是 _verify_payload 的三条硬校验
    # （wadj 与 adj 同边集 · 强边⊆全边 · 权为正有限）自动成立。
    #
    # 为什么必须补：edges.jsonl 只有 path / cap / cap_mention，"文本提及"建不出
    # 代码依赖。实测 2272 个 .py 可解析出 2292 条 import 关系，其中 2234 条图里没有；
    # `code:gbt_allinone/api.py` → `code:gbt_allinone/codex_bridge.py` 就是其中最典型的一条
    # （api.py:2240 `from . import codex_bridge as _CB`，图里此前 0 条边）。
    import_n = 0
    py_nodes = [nd for nd in list(adj)
                if nd.startswith("code:") and nd.endswith(IMPORT_EXT)]
    mod2node = {}                      # 模块全名 -> code: 节点（impl 段共用）
    for nd in py_nodes:
        rel_nd = nd[5:].replace("\\", "/")
        mod2node[rel_nd[:-3].replace("/", ".")] = nd
    if py_nodes:
        import ast as _ast

        def _abs_mod(rel_file: str, level: int, module) -> str:
            """相对导入 → 绝对模块名。level=1 指当前包（`from . import x`）。"""
            parts = [x for x in os.path.dirname(rel_file).replace("\\", "/").split("/") if x]
            up = level - 1
            if up > 0:
                parts = parts[: len(parts) - up]
            base = ".".join(parts)
            if module:
                return (base + "." + module).strip(".") if base else module
            return base

        for rel_node in py_nodes:
            rel_nd = rel_node[5:].replace("\\", "/")
            try:
                fp = ROOT / rel_nd
                if fp.stat().st_size > IMPORT_MAX:
                    continue
                tree = _ast.parse(fp.read_text(encoding="utf-8", errors="replace"))
            except (OSError, SyntaxError, ValueError, UnicodeError):
                continue
            targets = set()
            for sub in _ast.walk(tree):
                if isinstance(sub, _ast.ImportFrom):
                    if sub.level and sub.level > 0:
                        base = _abs_mod(rel_nd, sub.level, sub.module)
                        cands = [base] if sub.module else []
                    else:
                        base = sub.module or ""
                        cands = [base]
                    for al in sub.names:
                        cands.append((base + "." + al.name).strip("."))
                    for c in cands:
                        t = mod2node.get(c)
                        if t and t != rel_node:
                            targets.add(t)
                elif isinstance(sub, _ast.Import):
                    for al in sub.names:
                        t = mod2node.get(al.name)
                        if t and t != rel_node:
                            targets.add(t)
            for t in targets:
                if t not in adj.get(rel_node, ()):
                    import_n += 1
                kcnt[_pk(rel_node, t)]["import"] += 1
                adj[rel_node].add(t); adj[t].add(rel_node)
                strong[rel_node].add(t); strong[t].add(rel_node)
        by_kind["import"] = import_n

    # ── cap → 实现文件 补边（v4 · 能力位到本体的唯一真映射）─────────────────
    # 为什么不能靠 cap-bindings.json：该文件不存在，而 BENIGN_CAPS 的 handler 字段
    # 只是能力名的复读（handler="codex_tools"），全表没有 module/file/path 字段。
    # 照现有 bind 段去建，只会凭空造出 427 个 handler: 节点，且它们**到不了任何 code: 节点**
    # —— 节点变多、通路不变，那是把图做假。
    #
    # 真映射只能从派发件静态挖：api.py 里 `if kind == "x":` 分支体内 import 的模块
    # 就是该位的实现。实测 427 个位里 405 个可解析，得 417 条 cap→code 边。
    # 口径：一条 import 只归属**它所在 if 链**上的能力名，不继承兄弟分支 ——
    # 否则 `if kind in (A,B): import X` 后面跟 `if kind == "C": import Y` 会把 Y 也
    # 算给 A/B，权重虚高（比漏连更糟：它会让人以为改 Y 必查 A）。
    impl_n = 0
    if py_nodes:
        DISPATCH_FILE = "gbt_allinone/api.py"
        _tree = None
        if (ROOT / DISPATCH_FILE).exists():
            try:
                _tree = _ast.parse((ROOT / DISPATCH_FILE).read_text(
                    encoding="utf-8", errors="replace"))
            except (OSError, SyntaxError, ValueError, UnicodeError):
                _tree = None
        if _tree is not None:
            def _caps_in_test(t):
                """从 if 条件抽能力名：kind == "x" / kind in (...) / 布尔组合。"""
                out = set()
                if isinstance(t, _ast.Compare):
                    for op, comp in zip(t.ops, t.comparators):
                        if isinstance(op, _ast.Eq) and isinstance(comp, _ast.Constant) \
                                and isinstance(comp.value, str):
                            out.add(comp.value)
                        elif isinstance(op, _ast.In) and isinstance(
                                comp, (_ast.Tuple, _ast.List, _ast.Set)):
                            for e in comp.elts:
                                if isinstance(e, _ast.Constant) and isinstance(e.value, str):
                                    out.add(e.value)
                elif isinstance(t, _ast.BoolOp):
                    for v in t.values:
                        out |= _caps_in_test(v)
                elif isinstance(t, _ast.UnaryOp):
                    out |= _caps_in_test(t.operand)
                return out

            def _import_targets(stmt):
                got = set()
                if isinstance(stmt, _ast.ImportFrom):
                    if stmt.level and stmt.level > 0:
                        base = "gbt_allinone" + ("." + stmt.module if stmt.module else "")
                    else:
                        base = stmt.module or ""
                    if base:
                        got.add(base)
                    for al in stmt.names:
                        got.add((base + "." + al.name).strip("."))
                elif isinstance(stmt, _ast.Import):
                    got |= {al.name for al in stmt.names}
                return got

            _pairs = set()
            # 排序：主件优先（备份副本/镜像/归档排后面），同层取短路径。
            # 为什么：`tools/control_loop.py` 会同时匹配
            # `state/atomic-sync/backup/2026.../tools/control_loop.py`，
            # 连到备份副本等于「改主件时监控不提示」—— 看着接上了，其实接错了。
            _path_nodes = sorted(
                ((nd, nd[5:].replace("\\", "/")) for nd in py_nodes),
                key=lambda x: ("state/" in x[1] or ".archive/" in x[1]
                               or "/backup" in x[1] or "/mirror/" in x[1], len(x[1])))

            def _path_suffix(expr):
                """把 Path 拼接里的字符串常量抽出来，拼成相对路径后缀。

                `_P(__file__).resolve().parents[1] / "tools" / "x.py"` -> `tools/x.py`
                """
                parts, cur = [], expr
                while isinstance(cur, _ast.BinOp) and isinstance(cur.op, _ast.Div):
                    if isinstance(cur.right, _ast.Constant) and isinstance(cur.right.value, str):
                        parts.append(cur.right.value)
                    cur = cur.left
                parts.reverse()
                return "/".join(parts)

            def _dyn_targets(call, caps):
                """三种**动态派发**的目标 —— 按参数形态认，不按函数名（别名太多）。

                它们都是 `if kind ==` 分支体，但体内没有 import，只有调用：

                  ① `_im("." + kind, __package__)`           模块名 = 能力名
                  ② `spec_from_file_location(name, Path/"x.py")`  路径在字面常量里
                  ③ `_external_capability("quant_tech", kind)`    外部业务模块

                来历（2026-11-05）：只认 import 时，22 个位挖不到 —— 其中 vision 5 位走 ①，
                hook_enforcer/tentacle_bind 等 8 位走 ②，quant 4 位走 ③。
                剩下 echo/count_words/health/audit_query 是**纯 api.py 内联**，
                实现就在派发件本身，2 跳是正确的，不该硬连。
                """
                out = set()
                args = call.args
                if not args:
                    return out
                a0 = args[0]
                # ① "." + kind
                if (isinstance(a0, _ast.BinOp) and isinstance(a0.op, _ast.Add)
                        and isinstance(a0.left, _ast.Constant) and a0.left.value == "."
                        and isinstance(a0.right, _ast.Name) and a0.right.id == "kind"):
                    for _c in caps:
                        out.add("MOD:gbt_allinone." + _c)
                    return out
                # ③ 常量模块名 + kind 作第二参
                if (len(args) >= 2 and isinstance(a0, _ast.Constant)
                        and isinstance(a0.value, str)
                        and isinstance(args[1], _ast.Name) and args[1].id == "kind"):
                    out.add("MOD:gbt_allinone." + a0.value)
                    return out
                # ② 第二个参数是 Path 拼接
                if len(args) >= 2:
                    suffix = _path_suffix(args[1])
                    if suffix:
                        out.add("PATH:" + suffix)
                return out

            def _link_path(sfx, caps):
                """把路径后缀接到图里**唯一主件**上（只认主件，不连备份副本）。

                为什么要抽出来：内联调用参数、路径先存变量，两种写法都得走同一条连接规则 ——
                复制两遍就会出现「一处认主件、一处认副本」这种最难查的偏。
                """
                for _nd, _rel in _path_nodes:
                    if _rel.endswith(sfx):
                        for _c in caps:
                            _pairs.add((_c, _nd))
                        return

            def _visit_impl(node, caps):
                if isinstance(node, (_ast.Import, _ast.ImportFrom)):
                    if caps:
                        for _m in _import_targets(node):
                            _tgt = mod2node.get(_m)
                            if _tgt:
                                for _c in caps:
                                    _pairs.add((_c, _tgt))
                    return
                if caps and isinstance(node, _ast.Call):
                    for _m in _dyn_targets(node, caps):
                        if _m.startswith("PATH:"):
                            _link_path(_m[5:], caps)
                        else:
                            _tgt = mod2node.get(_m[4:])
                            if _tgt:
                                for _c in caps:
                                    _pairs.add((_c, _tgt))
                # ④ 路径**先存变量、再传给 loader**（2026-11-05 补）：
                #
                #   `_rg_path = Path(__file__).resolve().parents[1] / "tools" / "codex-scripts" / "x.py"`
                #   `spec_from_file_location(n, _rg_path)`
                #
                # 此时 `_dyn_targets` 拿到的第二参数是 `ast.Name`，`_path_suffix` 抽不出东西。
                # 血账：`review_gate` 正是这种写法，于是它与真实实现
                # `tools/codex-scripts/terminal-review.py` 之间 **0 条边**，被误判成孤儿位
                # （而同批的 hook_enforcer / omission_detector 路径内联在调用里，② 形态能认，
                #  它们早有强边 —— 「孤儿」这个结论当时错在没区分这两种写法）。
                if caps and isinstance(node, _ast.Assign):
                    _sfx4 = _path_suffix(node.value)
                    if _sfx4.endswith(".py"):
                        _link_path(_sfx4, caps)
                if isinstance(node, _ast.If):
                    inner = caps | _caps_in_test(node.test)
                    for _s in node.body:
                        _visit_impl(_s, inner)
                    for _s in node.orelse:
                        _visit_impl(_s, caps)      # else 分支不吃 test 条件
                    return
                for _ch in _ast.iter_child_nodes(node):
                    _visit_impl(_ch, caps)

            _visit_impl(_tree, frozenset())
            for _cn, _tn in _pairs:
                _c = "cap:" + _cn
                if _c not in adj:
                    continue                       # 只连已在图里的能力位，不新增节点
                if _tn not in adj.get(_c, ()):
                    impl_n += 1
                kcnt[_pk(_c, _tn)]["impl"] += 1
                adj[_c].add(_tn); adj[_tn].add(_c)
                strong[_c].add(_tn); strong[_tn].add(_c)
        by_kind["impl"] = impl_n

    # 绑定账：能力位 ↔ 触手域 / 载体 / handler（这三条是真绑定，算强边）
    bind_n = 0
    if BINDINGS.is_file():
        try:
            cb = json.loads(BINDINGS.read_text(encoding="utf-8"))
        except ValueError:
            cb = {}
        for row in (cb.get("caps") or []):
            cn = row.get("name")
            if not cn:
                continue
            c = "cap:" + str(cn)
            for td in (row.get("tentacle_domains") or []):
                t = "tent:" + str(td)
                kcnt[_pk(c, t)]["bind"] += 1
                adj[c].add(t); adj[t].add(c)
                strong[c].add(t); strong[t].add(c)
                bind_n += 1
            if row.get("carrier"):
                k = "carrier:" + str(row["carrier"])
                kcnt[_pk(c, k)]["bind"] += 1
                adj[c].add(k); adj[k].add(c)
                strong[c].add(k); strong[k].add(c)
                bind_n += 1
            if row.get("handler"):
                k = "handler:" + str(row["handler"])
                kcnt[_pk(c, k)]["bind"] += 1
                adj[c].add(k); adj[k].add(c)
                strong[c].add(k); strong[k].add(c)
                bind_n += 1

    # ── 目录树层（2026-11-04 主人令：「触手树也就是你们认为的项目树」）──────────
    # 为什么必须有这一层：上面所有边都是**引用边**（A 里提到 B），
    # 于是一个"没被任何人引用"的文件就一条边都没有 —— 实测 616 个文本文件因此缺图，
    # 覆盖率只有 77%，还留下 4 个连通分量、13 个掉队节点。
    # 主人令：「只要是文件就没有不可以接的」。
    # 接法不是硬塞边，而是补上**目录层级**：文件 → 直接父目录 → … → 根。
    # 这同时给你真正的东西：图第一次有了"树"，可以按项目结构导航，而不只是按引用跳。
    tree_files = 0
    if FILES.is_file():
        tree_pairs = set()
        for line in FILES.open(encoding="utf-8"):
            try:
                r = json.loads(line)
            except ValueError:
                continue
            p = r.get("path") or ""
            if not p or _excluded(p):
                continue
            if (r.get("ext") or "") not in TREE_EXT:
                continue
            node = _node_for_path(p)
            chain = _dir_chain(p)          # [深 ... 根]
            if not chain:
                continue
            tree_pairs.add((node, chain[0]))
            for i in range(len(chain) - 1):
                tree_pairs.add((chain[i], chain[i + 1]))
            tree_files += 1
        for a, b in tree_pairs:
            if a == b:
                continue
            kcnt[_pk(a, b)]["tree"] += 1
            adj[a].add(b); adj[b].add(a)   # 只进全边，**不进 strong**（结构归属 ≠ 真依赖）

    nodes = set(adj) | {y for v in adj.values() for y in v}
    return {
        "adj": adj, "strong": strong, "nodes": nodes, "kcnt": kcnt,
        "by_kind": dict(by_kind), "raw_edges": n, "dropped_paths": dropped,
        "bind_edges": bind_n, "tree_files": tree_files,
        "elapsed": time.time() - t0,
    }, None


def _components(adj: dict) -> tuple:
    seen, sizes = set(), []
    for start in adj:
        if start in seen:
            continue
        stack, cnt = [start], 0
        seen.add(start)
        while stack:
            cur = stack.pop()
            cnt += 1
            for nb in adj.get(cur, ()):
                if nb not in seen:
                    seen.add(nb)
                    stack.append(nb)
        sizes.append(cnt)
    sizes.sort(reverse=True)
    return len(sizes), (sizes[0] if sizes else 0), (sizes[0] if sizes else 0) / max(1, sum(sizes))


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="wiring.json 写手（保留边的强弱类型）")
    ap.add_argument("--check", action="store_true", help="只比对新旧规模，不写盘")
    a = ap.parse_args(argv)

    data, err = build()
    if data is None:
        print(json.dumps(err, ensure_ascii=False, indent=2))
        return 1
    adj, strong, nodes = data["adj"], data["strong"], data["nodes"]
    nodes_total = len(nodes)
    if nodes_total < 100:
        print(json.dumps({"ok": False, "error": "graph_too_small",
                          "why": "只读到 %d 个节点，形状明显不对" % nodes_total},
                         ensure_ascii=False, indent=2))
        return 1

    und_edges = sum(len(v) for v in adj.values()) // 2
    strong_edges = sum(len(v) for v in strong.values()) // 2
    comps, largest, share = _components({k: list(v) for k, v in adj.items()})
    kinds = dict(collections.Counter(k.split(":", 1)[0] for k in nodes))

    print("读边 %d 条（%s）+ 绑定 %d 条 · 用时 %.1fs"
          % (data["raw_edges"], " · ".join("%s %d" % kv for kv in sorted(data["by_kind"].items())),
             data["bind_edges"], data["elapsed"]))
    print("节点 %d · 无向边 %d（其中强边 %d / 弱边 %d）"
          % (nodes_total, und_edges, strong_edges, und_edges - strong_edges))
    print("节点构成：%s" % " · ".join("%s %d" % kv for kv in sorted(kinds.items(), key=lambda x: -x[1])))
    print("连通性：分量 %d · 最大分量 %d（%.1f%%）" % (comps, largest, share * 100))

    if a.check:
        old = None
        if OUT.is_file():
            try:
                o = json.loads(OUT.read_text(encoding="utf-8"))
                old = (o.get("nodes"), o.get("edges"), o.get("at"),
                       o.get("weight_rule", {}).get("version"))
            except ValueError:
                old = None
        if old:
            print("现有 wiring.json：节点 %s · 边(有向) %s · 构建于 %s · 权重口径 v%s"
                  % old)
            print("新图（有向 %d）—— 差异请自行判读，--check 不写盘" % (sum(len(v) for v in adj.values())))
        return 0

    # ── 加权图：与无权图**同边集**，只是每条边多一个权 ─────────────────────
    kcnt = data["kcnt"]
    wadj = collections.defaultdict(dict)
    wmin, wmax, wsum = None, None, 0.0
    for (x, y), kinds_cnt in kcnt.items():
        w = _edge_weight(kinds_cnt)
        if w <= 0:
            continue
        wv = round(w, 6)
        wadj[x][y] = wv
        wadj[y][x] = wv
        wsum += wv
        wmin = wv if wmin is None else min(wmin, wv)
        wmax = wv if wmax is None else max(wmax, wv)

    # 边表指纹：**防"旧权重配新边"**。那种错不报错，只是悄悄算偏。
    try:
        _st = EDGES.stat()
        src_sig = {"file": "outputs/repo-pack/edges.jsonl",
                   "size": _st.st_size, "mtime": int(_st.st_mtime)}
    except OSError:
        src_sig = None

    payload = {
        "at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "nodes": nodes_total,
        "edges": und_edges,
        "edges_directed": sum(len(v) for v in adj.values()),
        "strong_edges": strong_edges,
        "edges_by_kind": data["by_kind"],
        "kinds": kinds,
        "components": comps,
        "largest_share": round(share * 100, 1),
        "note": ("四边图（**保留强弱 + 带权**）：adj=全边（含 cap_mention 弱边）· "
                 "strong_adj=真依赖（path 引用 + cap 真引用 + import AST + impl 实现映射 "
                 "+ dispatch 分派 + 绑定账）· "
                 "wadj=逐边权重（口径见 weight_rule，读端须校验 version 与 src_sig）· "
                 "写手 tools/codex-scripts/wiring-build.py"),
        "builder": "tools/codex-scripts/wiring-build.py",
        "src_sig": src_sig,
        "weight_rule": {
            "version": WEIGHT_RULE_VERSION,
            "kind_base": KIND_BASE,
            "formula": WEIGHT_FORMULA,
            "note": ("边权 = Σ KIND_BASE[kind] × log1p(该 (a,b) 对出现次数)。"
                     "次数来自 edges.jsonl 的重复行 —— 旧版 set.add() 会把它抹掉。"
                     "v3 起含 import 边（AST 解析，KB=1.0）：代码级真依赖不再缺席，"
                     "别名 `as _CB` 不影响结果。"
                     "v4 起含 impl 边（cap → 实现文件，KB=1.2）：从派发件 api.py 的"
                     "`if kind == \"x\"` 分支静态挖出实现模块，能力位到本体不再只能 2 跳。"),
            "stats": {"min": wmin, "max": wmax,
                      "sum": round(wsum, 3),
                      "edges": sum(len(v) for v in wadj.values()) // 2},
        },
        "adj": {k: sorted(v) for k, v in adj.items()},
        "strong_adj": {k: sorted(v) for k, v in strong.items()},
        "wadj": {k: dict(sorted(v.items())) for k, v in sorted(wadj.items())},
    }

    # ── 写前自校验：不合格就不碰盘 ────────────────────────────────────────
    bad = _verify_payload(payload, nodes_total, und_edges)
    if bad:
        print(json.dumps({"ok": False, "error": "payload_invalid",
                          "why": "写前校验没过，**未写盘**，现有 wiring.json 一个字节没动",
                          "problems": bad[:10]}, ensure_ascii=False, indent=2))
        return 1

    text = json.dumps(payload, ensure_ascii=False)

    # ── 备份 → 原子替换 → 读回校验 → 失败回滚 ────────────────────────────
    OUT.parent.mkdir(parents=True, exist_ok=True)
    prev = OUT.with_name(OUT.name + ".prev")
    had_prev = OUT.is_file()
    if had_prev:
        _atomic_write_text(prev, OUT.read_text(encoding="utf-8"))

    _atomic_write_text(OUT, text)

    try:
        back = json.loads(OUT.read_text(encoding="utf-8"))
        bad2 = _verify_payload(back, nodes_total, und_edges)
    except (ValueError, OSError) as e:
        bad2 = ["读回失败：%s: %s" % (type(e).__name__, e)]

    if bad2:
        print(json.dumps({"ok": False, "error": "readback_invalid", "problems": bad2[:10],
                          "rollback": ("已从 wiring.json.prev 回滚" if had_prev
                                       else "无旧件可回滚，请人工处理")},
                         ensure_ascii=False, indent=2))
        if had_prev:
            _atomic_write_text(OUT, prev.read_text(encoding="utf-8"))
        return 1

    print("已写 %s（%.1f MB）· 带权 %d 无向边 · 权重 %.3f~%.3f · 口径 v%d"
          % (OUT.relative_to(ROOT), OUT.stat().st_size / 1e6,
             sum(len(v) for v in wadj.values()) // 2,
             wmin or 0, wmax or 0, WEIGHT_RULE_VERSION))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
