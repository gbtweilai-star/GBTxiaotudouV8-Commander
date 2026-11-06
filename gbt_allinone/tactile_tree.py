# -*- coding: utf-8 -*-
"""触手树 —— 以触手为权重的加权图，接口即项目树的联通拓扑。

为什么存在
----------
原来的 `wiring.json` 是**无权图**：`adj` 是 `set`，四类边（cap / cap_mention /
path / dispatch）平权，重复出现的共现次数在建图时被 `set.add()` 抹掉了。
结果只能回答「通不通」，回答不了「谁更该被点亮」。

本模块把同一份 `outputs/repo-pack/edges.jsonl` 重新读一遍，保留：
  1. **边类型基准**  cap/dispatch=1.0 > path=0.5 > cap_mention=0.15
  2. **共现强度**    Σ base × log1p(该 (a,b) 对出现的次数)
  3. **真实调用**    orchestration-ledger 里该能力位实际被调用的次数（log 缩放）

然后在该加权图上做 personalised-PageRank 式**激活传播**。这是用图传播替代
大模型前向计算的路径：定位种子 → 加权扩散 → 取 top-k，全部是矩阵乘，
不生成一个字。

实测（12 迭代 / 137714 有向边 / 10719 节点）
  numpy 稀疏乘  26.0 ms/次
  纯 Python 降级 364 ms/次   （numpy 缺席时自动退这里，仍在秒级内）
对比 `local_llm.ask` 21.6 s —— 快 830×。

契约
----
run(op="build"|"route"|"spread"|"neighbors"|"stats"|"bench"|"diag", **kw)

失败三态（不许包装成 failed）：
  needs_dependency  numpy 与降级都不可用
  needs_input       查询里定位不到任何种子节点（不假装命中）
  failed            真异常，回执带上游原话
"""

from __future__ import annotations

import functools
import json
import math
import os
import re
import sys
import time
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

EDGES = ROOT / "outputs" / "repo-pack" / "edges.jsonl"
WIRING = ROOT / "state" / "model-pack" / "wiring.json"
PACK_DIR = ROOT / "state" / "model-pack"
TREE_NPZ = PACK_DIR / "tactile-tree.npz"
TREE_META = PACK_DIR / "tactile-tree.meta.json"
USAGE_LEDGER = ROOT / "state" / "orchestration-ledger.jsonl"

# 边类型基准权重：明确点名/真分派 >> 引用文件 >> 只是提到名字
KIND_BASE = {"cap": 1.0, "dispatch": 1.0, "path": 0.5, "cap_mention": 0.15}
WEAK_KINDS = {"cap_mention"}

DEFAULT_ITERS = 12
DEFAULT_DAMPING = 0.85
DEFAULT_TOPK = 8

# 本模块理解的权重口径版本。必须与 tools/codex-scripts/wiring-build.py 的
# WEIGHT_RULE_VERSION 一致 —— 不一致就**不许混用两张图**（比自建更危险）。
# v1 → v2（2026-11-04）：新增目录树层 `tree` 边（KIND_BASE["tree"]=0.4）。
# v2 → v3（2026-11-05）：新增 Python import 层 `import` 边（KIND_BASE["import"]=1.0）。
#   不加这一层时 api.py 与 codex_bridge.py 之间 0 条边 —— import 关系从未被图解析过。
# v3 → v4（2026-11-05）：新增 `impl` 边（cap → 实现文件，KIND_BASE["impl"]=1.2）。
#   不加这一层时能力位到本体只能 2 跳（实现件里不含能力名，派发写在 api.py）。
MY_WEIGHT_RULE = 4

# 进程内缓存（重复调用零成本）
_CACHE = {}

try:                                    # numpy 是加速器，不是依赖
    import numpy as np
    _HAS_NUMPY = True
except Exception:                       # noqa: BLE001
    np = None
    _HAS_NUMPY = False


# --------------------------------------------------------------------------
# 失败三态
# --------------------------------------------------------------------------
def _denied(need: str, why: str, **kw) -> dict:
    return dict(ok=False, status="denied", need=need, why=why, **kw)


def _need_dep(what: str, why: str, **kw) -> dict:
    return dict(ok=False, status="needs_dependency", need=what, why=why, **kw)


def _need_input(why: str, **kw) -> dict:
    return dict(ok=False, status="needs_input", why=why, **kw)


def _failed(err, **kw) -> dict:
    return dict(ok=False, status="failed", error=f"{type(err).__name__}: {err}", **kw)


# --------------------------------------------------------------------------
# 权重来源 3：真实调用次数
# --------------------------------------------------------------------------
def usage_counts(limit: int = 400) -> dict:
    """从编排账本拿每个能力位真实被调用的次数。读不到就返回 {}，不编。"""
    if "usage" in _CACHE:
        return _CACHE["usage"]
    out = {}
    if USAGE_LEDGER.is_file():
        try:
            for line in USAGE_LEDGER.open(encoding="utf-8", errors="replace"):
                if '"target"' not in line:
                    continue
                try:
                    row = json.loads(line)
                except ValueError:
                    continue
                tgt = row.get("target") or row.get("cap")
                if isinstance(tgt, str) and tgt:
                    out[tgt] = out.get(tgt, 0) + 1
        except OSError:
            out = {}
    ranked = sorted(out.items(), key=lambda x: -x[1])[:limit]
    _CACHE["usage"] = dict(ranked)
    return _CACHE["usage"]


# --------------------------------------------------------------------------
# 建图
# --------------------------------------------------------------------------
def _pair_key(a: str, b: str):
    return (a, b) if a < b else (b, a)


# ---- 路径解析规则：**与 tools/codex-scripts/wiring-build.py 同源** ----
# 两处必须同步改，否则同一份 edges.jsonl 会算出两份不同的图。
# 留痕（2026-11-04）：第一版本模块漏了这段，直接 "code:"+dst，得到 10719 节点 /
# page=0 / code=10292 —— 同一文件的不同相对写法被拆成多个节点，权重被稀释，
# 而 wiring.json 的正确值是 4511 节点（code 2768 / page 1158）。
CODE_EXT = {".py", ".js", ".mjs", ".cjs", ".ts", ".tsx", ".jsx",
            ".sh", ".ps1", ".cmd", ".bat"}
PAGE_EXT = {".html", ".htm", ".md", ".txt", ".json", ".jsonl",
            ".csv", ".svg", ".css", ".yml", ".yaml"}
GRAPH_EXCLUDE_PREFIX = (
    "_upstream/", ".agents/", ".scratch/", ".git/", ".pylibs/",
    "outputs/repo-pack/", "outputs/workspace-scan/", "gbt_allinone/store/",
    "node_modules/",
)
_SCHEME = re.compile(r"^[A-Za-z][A-Za-z0-9+.\-]*:")
_JUNK = re.compile(r"[\s\"'`{}()\[\]<>|*?]|^[-+@#]|\.\.\.|^[A-Za-z_]+=")


def _excluded(p: str) -> bool:
    q = str(p or "").replace("\\", "/")
    return any(q.startswith(x) for x in GRAPH_EXCLUDE_PREFIX)


@functools.lru_cache(maxsize=200000)
def _resolve_path(src: str, dst: str) -> str:
    """把 path 边目标解析成仓内真实文件；解析不出返回空（丢弃，不留脏节点）。

    三道闸：① 有 scheme（`https:` / `mailto:`）丢 ② 含空白/引号/括号等"不像路径"
    的字符丢 ③ 必须是盘上真存在的文件（先按仓根，再按 src 同目录）。
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
        return p
    last = p.rsplit("/", 1)[-1]
    ext = ("." + last.rsplit(".", 1)[-1].lower()) if "." in last else ""
    if ext in CODE_EXT:
        return "code:" + p
    if ext in PAGE_EXT:
        return "page:" + p
    return "code:" + p


def _scan_edges():
    """读 edges.jsonl → {(a,b): {kind: count}}。与 wiring-build 同源同规则。"""
    if not EDGES.is_file():
        return None
    pair = defaultdict(lambda: defaultdict(int))
    raw = 0
    dropped = 0
    by_kind = defaultdict(int)
    with EDGES.open(encoding="utf-8", errors="replace") as fh:
        for line in fh:
            try:
                e = json.loads(line)
            except ValueError:
                continue
            src, dst = e.get("src"), e.get("dst")
            if not src or not dst:
                continue
            kind = e.get("kind") or "path"
            if _excluded(str(src)):
                continue
            raw += 1
            by_kind[kind] += 1

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
            pair[_pair_key(a, b)][kind] += 1
    return pair, raw, dict(by_kind), dropped



def _atomic_text(path: Path, text: str) -> None:
    """临时文件 + fsync + os.replace。失败删临时文件，原文件一个字节不动。

    主人令 2026-11-04：「原子替换你又不使用吗？」—— 这条之前只用在
    `wiring.json` 上，`tactile-tree.*` 四个产物全是直接 `write_text`，
    写一半崩就是坏索引（npz 289KB / names 216KB）。
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name("%s.tmp-%d" % (path.name, os.getpid()))
    try:
        with open(tmp, "w", encoding="utf-8", newline="") as fh:
            fh.write(text)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, path)
    except BaseException:
        try:
            tmp.unlink()
        except OSError:
            pass
        raise


def _atomic_npz(path: Path, **arrays) -> None:
    """同名原子写 npz。后缀必须是 `.npz`，否则 numpy 会自动再追加一次。

    ⚠️ 实测教训（2026-11-04）：原子替换保证「要么旧的、要么新的」，
    **保证不了「新的有意义」** —— `np.savez_compressed(rows=None)` 不报错，
    会老老实实把好文件换成一个只剩 `rows=None` 的壳。
    所以先校验再写，别把「没抛异常」当成「写对了」。
    """
    if not arrays:
        raise ValueError("_atomic_npz: 没有要写的数组")
    rows = arrays.get("rows")
    if rows is None or getattr(rows, "size", 0) == 0:
        raise ValueError("_atomic_npz: rows 为空，拒绝覆盖现有图")
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp.npz")
    try:
        np.savez_compressed(str(tmp), **arrays)
        # 读回校验：文件真的存在且读得出 rows
        with np.load(str(tmp)) as z:
            if "rows" not in z or z["rows"].size == 0:
                raise ValueError("_atomic_npz: 落盘后读不回 rows")
        os.replace(tmp, path)
    except BaseException:
        try:
            tmp.unlink()
        except OSError:
            pass
        raise


def _commit_pack(nodes: list, meta: dict, *, arrays=None, py_fallback=None) -> None:
    """**按「先数据、后标记」的顺序原子落盘**。

    顺序不是随意的：`tactile-tree.meta.json` 是提交标记。
    先写 npz / names，最后写 meta —— 于是「meta 存在 ⇒ 全部就绪」成立；
    中途崩了只会留下旧 meta + 新 npz，下次 `_load` 因 sig 不符重建，不会用到半成品。
    反过来先写 meta，就会出现「meta 说好了、npz 还是旧的」，那才是污染。
    """
    if arrays is not None:
        _atomic_npz(TREE_NPZ, **arrays)
    elif py_fallback is not None:
        _atomic_text(TREE_META.with_suffix(".py.json"),
                     json.dumps(py_fallback, ensure_ascii=False))
    _atomic_text(PACK_DIR / "tactile-tree.names.json",
                 json.dumps(nodes, ensure_ascii=False))
    _atomic_text(TREE_META, json.dumps(meta, ensure_ascii=False, indent=1))
    _CACHE.pop("tree", None)


def _build_from_wiring(force: bool = False):
    """从 `wiring.json` 建传播图（**唯一真源**）。不可用时返回 None 让调用方降级。

    返回 None 的三种情况，都会如实标注、不静默：
      · wiring.json 不存在 / 读不出
      · 口径版本与本模块不符（宁可自建，也不把两张不同口径的图混用）
      · wadj / adj 缺失（旧图，无权重）
    """
    if not WIRING.is_file():
        return None
    try:
        st = WIRING.stat()
        wsig = {"size": st.st_size, "mtime": int(st.st_mtime)}
        if not force and TREE_META.is_file() and TREE_NPZ.is_file():
            try:
                old = json.loads(TREE_META.read_text(encoding="utf-8"))
                if old.get("wiring_sig") == wsig and old.get("source") == "wiring.json":
                    return dict(ok=True, status="skipped", why="wiring.json 未变",
                                nodes=old.get("nodes"), edges=old.get("edges"),
                                dirs=old.get("dirs"), source="wiring.json")
            except (ValueError, OSError):
                pass
        src = json.loads(WIRING.read_text(encoding="utf-8"))
    except (ValueError, OSError):
        return None

    wr = src.get("weight_rule") or {}
    if wr.get("version") != MY_WEIGHT_RULE:
        _CACHE["build_note"] = "wiring.json 口径 v%s ≠ 本模块 v%s，退回自建" % (
            wr.get("version"), MY_WEIGHT_RULE)
        return None
    wadj = src.get("wadj") or {}
    if not wadj:
        _CACHE["build_note"] = "wiring.json 没有 wadj（旧图），退回自建"
        return None

    t0 = time.perf_counter()
    nodes = sorted(wadj.keys())
    idx = {n: i for i, n in enumerate(nodes)}
    N = len(nodes)
    if N == 0:
        return None

    # wadj 已经是双向存储（a→b 与 b→a 各一条），直接全收即有向边
    rows, cols, wts = [], [], []
    for a, nb in wadj.items():
        i = idx[a]
        for b, w in nb.items():
            j = idx.get(b)
            if j is None:
                continue
            try:
                wv = float(w)
            except (TypeError, ValueError):
                continue
            if wv > 0:
                rows.append(i); cols.append(j); wts.append(wv)
    if not rows:
        return None

    node_w = [0.0] * N
    usage = usage_counts()
    for cap, cnt in usage.items():
        pos = idx.get("cap:" + cap)
        if pos is not None:
            node_w[pos] = math.log1p(cnt) / 6.0

    if _HAS_NUMPY:
        rows_a = np.asarray(rows, dtype=np.int32)
        cols_a = np.asarray(cols, dtype=np.int32)
        w_a = np.asarray(wts, dtype=np.float64)
        deg = np.zeros(N, dtype=np.float64)
        np.add.at(deg, rows_a, w_a)
        inv = np.where(deg > 0, 1.0 / np.maximum(deg, 1e-12), 0.0)
        p_a = w_a * inv[rows_a]
        arrays = {"rows": rows_a, "cols": cols_a, "p": p_a,
                  "node_w": np.asarray(node_w, dtype=np.float64)}
        py_fallback = None
    else:
        adj_list = [dict() for _ in range(N)]
        wdeg = [0.0] * N
        for r, c, w in zip(rows, cols, wts):
            adj_list[r][c] = w
            wdeg[r] += w
        arrays = None
        py_fallback = {"adj": adj_list, "wdeg": wdeg, "node_w": node_w}

    dirs = sum(1 for n in nodes if n.startswith("dir:"))
    kinds = {
        "cap": sum(1 for n in nodes if n.startswith("cap:")),
        "page": sum(1 for n in nodes if n.startswith("page:")),
        "code": sum(1 for n in nodes if n.startswith("code:")),
        "dir": dirs,
    }
    meta = {
        "at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "source": "wiring.json",
        "wiring_sig": wsig,
        "weight_rule": wr.get("version"),
        "nodes": N,
        "edges": len(rows),
        "dirs": dirs,
        "kinds": kinds,
        "node_w_covered": sum(1 for w in node_w if w > 0),
        "usage_caps": len(usage),
        "backend": "numpy" if _HAS_NUMPY else "python",
        "build_ms": round((time.perf_counter() - t0) * 1000, 1),
    }
    _commit_pack(nodes, meta, arrays=arrays, py_fallback=py_fallback)
    return dict(ok=True, status="built", source="wiring.json",
                nodes=N, edges=len(rows), dirs=dirs,
                weight_rule=wr.get("version"),
                build_ms=meta["build_ms"])


def build(force: bool = False) -> dict:
    """建图并落盘。**优先从 `wiring.json` 建**（与 impact_check 多域监控同一张图）。"""
    t0 = time.perf_counter()
    PACK_DIR.mkdir(parents=True, exist_ok=True)

    # ── 唯一真源优先 ────────────────────────────────────────────────────
    # 曾经这里直接扫 edges.jsonl 自建，结果是两份图漂开：
    #   wiring.json 6305 节点 / 1 个连通分量（有目录树层）
    #   tactile-tree 4516 节点 / 4 个连通分量（无目录树层）
    # 多域监控看的是前者，pulse 用的是后者 —— 用户问"打通了没"就答不了。
    # 现在以 wiring.json 为准，口径版本不符才退回自建（且如实标注）。
    from_wiring = _build_from_wiring(force)
    if from_wiring is not None:
        return from_wiring

    if not EDGES.is_file():
        return _need_dep(
            "repo-pack 边表",
            "没有 %s —— 先跑 py tools/codex-scripts/repo-pack.py refs"
            % EDGES.relative_to(ROOT),
        )

    stat = EDGES.stat()
    sig = {"size": stat.st_size, "mtime": int(stat.st_mtime)}
    if not force and TREE_META.is_file() and TREE_NPZ.is_file():
        try:
            old = json.loads(TREE_META.read_text(encoding="utf-8"))
            if old.get("src_sig") == sig:
                return dict(ok=True, status="skipped", why="边表未变",
                            nodes=old.get("nodes"), edges=old.get("edges"),
                            elapsed_ms=round((time.perf_counter() - t0) * 1000, 1))
        except (ValueError, OSError):
            pass

    scanned = _scan_edges()
    if scanned is None:
        return _need_dep("repo-pack 边表", "读取失败")
    pair, raw, by_kind, dropped = scanned

    # 节点索引（排序保证可复现）
    nodes = set()
    for a, b in pair:
        nodes.add(a)
        nodes.add(b)
    nodes = sorted(nodes)
    if not nodes:
        return _failed(RuntimeError("边表为空，构不出节点"))
    idx = {n: i for i, n in enumerate(nodes)}
    N = len(nodes)

    # 有向边 + 边权
    rows, cols, wts = [], [], []
    for (a, b), kinds in pair.items():
        w = 0.0
        for kd, cnt in kinds.items():
            w += KIND_BASE.get(kd, 0.5) * math.log1p(cnt)
        if w <= 0:
            continue
        i, j = idx[a], idx[b]
        rows.append(i); cols.append(j); wts.append(w)
        rows.append(j); cols.append(i); wts.append(w)

    if not rows:
        return _failed(RuntimeError("没有正权重的边"))

    # 节点权重：真实调用次数
    usage = usage_counts()
    node_w = [0.0] * N
    for cap, cnt in usage.items():
        k = "cap:" + cap
        pos = idx.get(k)
        if pos is not None:
            node_w[pos] = math.log1p(cnt) / 6.0

    if _HAS_NUMPY:
        rows_a = np.asarray(rows, dtype=np.int32)
        cols_a = np.asarray(cols, dtype=np.int32)
        w_a = np.asarray(wts, dtype=np.float64)
        # 行归一化 → 转移概率（每行和 = 1）
        deg = np.zeros(N, dtype=np.float64)
        np.add.at(deg, rows_a, w_a)
        inv = np.where(deg > 0, 1.0 / np.maximum(deg, 1e-12), 0.0)
        p_a = w_a * inv[rows_a]
        arrays = {"rows": rows_a, "cols": cols_a, "p": p_a,
                  "node_w": np.asarray(node_w, dtype=np.float64)}
        py_fallback = None
    else:
        # 降级：存 Python 结构
        adj = [dict() for _ in range(N)]
        wdeg = [0.0] * N
        for r, c, w in zip(rows, cols, wts):
            adj[r][c] = w
            wdeg[r] += w
        arrays = None
        py_fallback = {"adj": [dict(d) for d in adj], "wdeg": wdeg, "node_w": node_w}

    caps = [n for n in nodes if n.startswith("cap:")]
    meta = {
        "at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "src_sig": sig,
        "nodes": N,
        "edges": len(rows),
        "pairs": len(pair),
        "raw_edge_rows": raw,
        "by_kind": by_kind,
        "kinds": {
            "cap": len(caps),
            "page": sum(1 for n in nodes if n.startswith("page:")),
            "code": sum(1 for n in nodes if n.startswith("code:")),
        },
        "node_w_covered": sum(1 for w in node_w if w > 0),
        "usage_caps": len(usage),
        "backend": "numpy" if _HAS_NUMPY else "python",
        "weights": {
            "kind_base": KIND_BASE,
            "node_from": "state/orchestration-ledger.jsonl (real invocation count)",
        },
        "build_ms": round((time.perf_counter() - t0) * 1000, 1),
    }
    _commit_pack(nodes, meta, arrays=arrays, py_fallback=py_fallback)
    return dict(ok=True, status="built", **{k: meta[k] for k in
                ("nodes", "edges", "pairs", "kinds", "node_w_covered",
                 "usage_caps", "backend", "build_ms")})


# --------------------------------------------------------------------------
# 加载
# --------------------------------------------------------------------------
def _load() -> dict:
    """懒加载加权图。返回 {nodes, idx, backend, ...}"""
    if "tree" in _CACHE:
        return _CACHE["tree"]

    if not TREE_META.is_file():
        raise FileNotFoundError("触手树未建：先跑 tactile_tree.build()")
    meta = json.loads(TREE_META.read_text(encoding="utf-8"))

    if _HAS_NUMPY and TREE_NPZ.is_file():
        z = np.load(TREE_NPZ)
        tree = {
            "meta": meta,
            "backend": "numpy",
            "rows": z["rows"], "cols": z["cols"], "p": z["p"],
            "node_w": z["node_w"],
            "N": int(meta["nodes"]),
        }
    else:
        alt = TREE_META.with_suffix(".py.json")
        if not alt.is_file():
            raise FileNotFoundError("numpy 缺席且没有 Python 降级树：重跑 build()")
        payload = json.loads(alt.read_text(encoding="utf-8"))
        tree = {
            "meta": meta,
            "backend": "python",
            "adj": [dict(d) for d in payload["adj"]],
            "wdeg": payload["wdeg"],
            "node_w": payload["node_w"],
            "N": int(meta["nodes"]),
        }

    # 节点名表：meta 只存数量，名字单独放
    names_file = PACK_DIR / "tactile-tree.names.json"
    if names_file.is_file():
        names = json.loads(names_file.read_text(encoding="utf-8"))
    else:
        raise FileNotFoundError(
            "缺节点名表 tactile-tree.names.json，重跑 build()"
        )
    tree["nodes"] = names
    tree["idx"] = {n: i for i, n in enumerate(names)}
    _CACHE["tree"] = tree
    return tree


def spread(seed: dict, iters: int = DEFAULT_ITERS, damping: float = DEFAULT_DAMPING) -> dict:
    """加权激活传播。seed={节点名: 权重}，返回 {节点名: 激活值}（只回非零）。"""
    tree = _load()
    names, idx = tree["nodes"], tree["idx"]
    N = tree["N"]

    seed_pos = {}
    for k, v in (seed or {}).items():
        pos = idx.get(k)
        if pos is not None and v:
            seed_pos[pos] = float(v)
    if not seed_pos:
        return {}

    if tree["backend"] == "numpy":
        x = np.zeros(N, dtype=np.float64)
        for pos, v in seed_pos.items():
            x[pos] = v
        seed_vec = x.copy()
        rows, cols, p = tree["rows"], tree["cols"], tree["p"]
        inv = 1.0 - damping
        for _ in range(int(iters)):
            contrib = p * x[rows]
            y = np.bincount(cols, weights=contrib, minlength=N)
            x = damping * y + inv * seed_vec
        nz = np.nonzero(x)[0]
        return {names[int(i)]: float(x[i]) for i in nz}

    # 降级：纯 Python
    adj, wdeg = tree["adj"], tree["wdeg"]
    x = {p: v for p, v in seed_pos.items()}
    inv = 1.0 - damping
    for _ in range(int(iters)):
        nxt = defaultdict(float)
        for u, su in x.items():
            d = wdeg[u]
            if d <= 0:
                continue
            for v, w in adj[u].items():
                nxt[v] += su * (w / d) * damping
        for pos, v in seed_pos.items():
            nxt[pos] += v * inv
        x = dict(nxt)
    return {names[p]: v for p, v in x.items() if v}


# --------------------------------------------------------------------------
# 种子定位：原话 → 图节点
# --------------------------------------------------------------------------
# 段锚表：把 `capability_router` 的四类判类落成**图上种子**，不是答案。
# 判类只说"这句话属于哪一类"，最终用哪个位仍由图传播决定 —— 这是
# 「以触手为权重」与「关键词路由」的区别：前者给候选，后者给结论。
ANCHOR_BY_INTENT = {
    "screen": ("cap:body_eye", 1.0),
    "web":    ("cap:browser", 1.0),
    "file":   ("cap:omni_plug", 1.0),
    "image":  ("cap:vision", 1.0),
    "camera": ("cap:see_camera", 1.0),
}

# 摄像头词表（**补 capability_router 的缺口，不改它的四类契约**）
# 留痕（2026-11-04）：AGENTS.md 4.1 记的 see_camera L1 血账依赖
# `router.py` + `intent_extracted.json`，而这两个文件在本树**不存在**，
# 所以「打开摄像头拍一张」被判成"四类都没命中 ⇒ 交给对话模型"。
# 四类（screen/web/file/image）里本来就没有"看真实世界"，硬塞进 screen 会
# 让「拍照」走去截屏。所以补在这里，与图同源，不动别人模块的形状。
CAMERA_WORDS = ("摄像头", "相机", "拍照", "拍一张", "拍个照", "拍下", "拍个",
                "camera", "镜头")
# 泛词必须配"看"类动词才认，否则「整理房间」会被误会成要看四周
CAMERA_PLACE = ("房间", "外面", "周围", "眼前", "窗外", "四周", "现场")
_CAM_VERB = re.compile(r"看|望|瞄|瞧|拍|扫")
_CAM_PLACE_RX = re.compile("|".join(CAMERA_PLACE))


def _anchor_seeds(q: str) -> tuple:
    """四类判类 + 摄像头词表 → 锚点种子。判不出来就返回空，不猜。"""
    out, notes = {}, []
    low = (q or "").lower()

    cam = [w for w in CAMERA_WORDS if w in low]
    if not cam and _CAM_VERB.search(low) and _CAM_PLACE_RX.search(low):
        cam = ["看+空间词"]
    if cam:
        out["cap:see_camera"] = 1.0
        notes.append("camera 词命中(%s)" % "/".join(cam[:3]))

    try:
        from gbt_allinone import capability_router as _cr
        r = _cr.classify(q)
        it = (r.get("intent") or "").strip()
        if it in ANCHOR_BY_INTENT:
            node, w = ANCHOR_BY_INTENT[it]
            out.setdefault(node, w)
            notes.append("判类=%s(%.2f)" % (it, float(r.get("confidence") or 0)))
    except Exception:                                   # noqa: BLE001
        # 判类器缺席不该让整条路塌掉：字面命中仍然有效
        notes.append("判类器不可用，仅用字面")
    return out, notes


def seed_from_query(q: str, *, use_router: bool = True) -> tuple:
    """把一句原话映射成种子节点。返回 (seeds, notes)。

    三级取证，从严到松：
      1. 字面证据（能力位名 / 文件名 / 页面路径）—— 命中了就**不再**扩散
      2. 段锚（capability_router 判类 + 摄像头词表）
      3. 一跳邻居扩展（只对 1~3 个种子的精确命中做，防止稀释）

    猜不出来就返回空 —— 由调用方报 needs_input，不假装命中。
    """
    if not q or not q.strip():
        return {}, ["空查询"]
    tree = _load()
    names = tree["nodes"]
    idx = tree["idx"]
    text = q.strip()
    low = text.lower()
    seeds, notes = {}, []

    # 1) 能力位：长名优先，避免 body 抢 body_eye/body_see
    cap_names = sorted(
        (n[4:] for n in names if n.startswith("cap:")),
        key=len, reverse=True,
    )
    hit_caps = []
    for cn in cap_names:
        if cn.lower() in low:
            # 已被更长的命中吃掉就跳过
            if any(cn != h and cn in h for h in hit_caps):
                continue
            hit_caps.append(cn)
    for cn in hit_caps:
        seeds["cap:" + cn] = 1.0
    if hit_caps:
        notes.append("cap 命中 %d" % len(hit_caps))

    # 2) 代码/页面：按 basename 与相对路径后缀匹配
    if not seeds:
        for n in names:
            if n.startswith("cap:"):
                continue
            rel = n.split(":", 1)[1]
            base = rel.rsplit("/", 1)[-1]
            if base and base.lower() in low and len(base) > 4:
                seeds[n] = seeds.get(n, 0.0) + 1.0
        if seeds:
            notes.append("文件命中 %d" % len(seeds))

    # 3) 段锚：字面一条都没命中时，才让判类器说话
    if not seeds and use_router:
        a, n2 = _anchor_seeds(text)
        seeds.update(a)
        notes += n2

    # 4) 图上再走一跳：命中的节点自身邻居降权加入
    if seeds and len(seeds) <= 3:
        extra = {}
        if tree["backend"] == "numpy":
            pass
        else:
            adj = tree["adj"]
            for n in list(seeds):
                pos = idx.get(n)
                if pos is None:
                    continue
                for v, w in list(adj[pos].items())[:6]:
                    nm = names[v]
                    if nm != n:
                        extra[nm] = max(extra.get(nm, 0.0), 0.25)
        for k, v in extra.items():
            seeds.setdefault(k, v)
        if extra:
            notes.append("一跳扩展 +%d" % len(extra))

    return seeds, notes


# --------------------------------------------------------------------------
# 路由
# --------------------------------------------------------------------------
def route(query: str = "", target: str = "", topk: int = DEFAULT_TOPK,
          iters: int = DEFAULT_ITERS, damping: float = DEFAULT_DAMPING,
          kind: str = "cap", use_router: bool = True) -> dict:
    """原话 / 直接指定节点 → 传播 → top-k。

    target 可给 `cap:xxx` / `code:path` / `page:path` / 裸能力位名。
    """
    tree = _load()
    names, idx = tree["nodes"], tree["idx"]

    seeds, notes = {}, []
    if target:
        t = target if ":" in target else "cap:" + target
        if t in idx:
            seeds[t] = 1.0
            notes.append("target 精确")
        else:
            # 退一步：basename 匹配
            base = target.rsplit("/", 1)[-1]
            for n in names:
                if n.endswith("/" + base) or n.rsplit(":", 1)[-1] == base:
                    seeds[n] = 1.0
            if seeds:
                notes.append("target basename 命中 %d" % len(seeds))
    if not seeds:
        seeds, notes2 = seed_from_query(query, use_router=use_router)
        notes += notes2

    if not seeds:
        return _need_input(
            "定位不到种子节点：原话里没有能力位名 / 文件名 / 页面路径",
            query=query, how="给 op=route 传 target='cap:xxx' 或换用能对上名字的说法",
        )

    t0 = time.perf_counter()
    act = spread(seeds, iters=iters, damping=damping)
    prop_ms = (time.perf_counter() - t0) * 1000

    nw = tree["node_w"]
    ranked = []
    for n, v in act.items():
        if kind and not n.startswith(kind + ":"):     # kind="" ⇒ 不过滤（locate 要 page/code）
            continue
        pos = idx.get(n)
        w = float(nw[pos]) if pos is not None else 0.0
        ranked.append((n.split(":", 1)[1], v * (1.0 + w), v, w))
    ranked.sort(key=lambda x: -x[1])

    total = sum(x[2] for x in ranked) or 1.0
    return dict(
        ok=True,
        status="ok",
        query=query,
        target=target,
        seeds=sorted(seeds),
        notes=notes,
        iters=iters,
        top=[{"node": n, "score": round(s, 6), "activation": round(a, 6),
              "usage_w": round(w, 4), "share": round(a / total, 4)}
             for n, s, a, w in ranked[:topk]],
        reached=len(act),
        prop_ms=round(prop_ms, 3),
    )


def neighbors(node: str, limit: int = 20) -> dict:
    """加权邻居：谁和它连得最紧。"""
    tree = _load()
    names, idx = tree["nodes"], tree["idx"]
    pos = idx.get(node if ":" in node else "cap:" + node)
    if pos is None:
        return _need_input("图里没有这个节点", node=node)

    if tree["backend"] == "numpy":
        rows, cols, p = tree["rows"], tree["cols"], tree["p"]
        mask = rows == pos
        pairs = [(names[int(cols[i])], float(p[i])) for i in np.nonzero(mask)[0]]
    else:
        adj = tree["adj"]
        pairs = [(names[v], float(w)) for v, w in adj[pos].items()]

    pairs.sort(key=lambda x: -x[1])
    return dict(ok=True, status="ok", node=names[pos],
                degree=len(pairs),
                top=[{"node": n, "weight": round(w, 6)} for n, w in pairs[:limit]])


def stats() -> dict:
    if not TREE_META.is_file():
        return _need_dep("触手树", "还没建：跑 op=build")
    meta = json.loads(TREE_META.read_text(encoding="utf-8"))
    tree = _load()
    return dict(ok=True, status="ok", **meta,
                backend_now=tree["backend"],
                numpy_available=_HAS_NUMPY)


def bench(rounds: int = 30) -> dict:
    """延迟基准：证明「秒级」不是口号。"""
    tree = _load()
    names = tree["nodes"]
    caps = [n for n in names if n.startswith("cap:")]
    if not caps:
        return _failed(RuntimeError("图里没有 cap 节点"))
    lat = []
    rounds = max(1, int(rounds))
    for i in range(rounds):
        s = {caps[i % len(caps)]: 1.0}
        t0 = time.perf_counter()
        spread(s, DEFAULT_ITERS, DEFAULT_DAMPING)
        lat.append((time.perf_counter() - t0) * 1000)
    lat.sort()
    n = len(lat)
    return dict(
        ok=True, status="ok",
        backend=tree["backend"], numpy=_HAS_NUMPY,
        rounds=n, iters=DEFAULT_ITERS,
        p50_ms=round(lat[n // 2], 3),
        p95_ms=round(lat[min(n - 1, int(n * 0.95))], 3),
        min_ms=round(lat[0], 3),
        max_ms=round(lat[-1], 3),
        nodes=tree["N"],
        compare={"local_llm_ask_s": 21.6},
        speedup_vs_llm=round(21600.0 / max(lat[n // 2], 1e-6), 1),
    )


def _peek_weight_rule() -> dict:
    """只读 `wiring.json` 文件头，取权重口径版本 —— 不加载 9.3 MB 图。

    用途：`diag` 里比对「wiring.json 的口径」与「本模块的口径」是否一致。
    两处一旦漂开（一边 v1 一边 v2），算出来的权重不可比，而且**不会报错**。
    """
    try:
        with open(WIRING, "rb") as fh:
            head = fh.read(8192).decode("utf-8", "replace")
        m = re.search(r'"weight_rule"\s*:\s*\{[^}]{0,600}?"version"\s*:\s*(\d+)', head)
        if not m:
            m = re.search(r'"version"\s*:\s*(\d+)', head)
        return {"found": True, "version": int(m.group(1)) if m else None}
    except OSError as e:
        return {"found": False, "why": "%s: %s" % (type(e).__name__, e)}


def diag() -> dict:
    wr = _peek_weight_rule()
    mine = MY_WEIGHT_RULE
    drift = None
    if wr.get("found") and wr.get("version") is not None:
        drift = (wr["version"] != mine)
    tree_src = None
    if TREE_META.is_file():
        try:
            tree_src = json.loads(TREE_META.read_text(encoding="utf-8")).get("source")
        except (ValueError, OSError):
            tree_src = None
    return dict(
        ok=True, status="ok",
        edges_file=str(EDGES.relative_to(ROOT)) if EDGES.is_file() else None,
        edges_exists=EDGES.is_file(),
        tree_npz=TREE_NPZ.is_file(),
        tree_meta=TREE_META.is_file(),
        tree_source=tree_src,             # "wiring.json" = 与多域监控同一张图
        numpy=_HAS_NUMPY,
        backend="numpy" if _HAS_NUMPY else "python",
        usage_ledger=USAGE_LEDGER.is_file(),
        wiring_exists=WIRING.is_file(),
        wiring_weight_rule=wr,
        my_weight_rule=mine,
        weight_rule_drift=drift,          # True = 两份图口径不一致，权重不可比
    )


# --------------------------------------------------------------------------
# 统一契约
# --------------------------------------------------------------------------
def hint(query: str = "", topk: int = 5, min_share: float = 0.12,
         min_ratio: float = 5.0) -> dict:
    """给对话链用的**候选提示**：不执行、不写盘、不越权。

    ## `confident` 的用途边界（**写死，不许扩大**）

    `confident=True` **只**表示「这次候选值得写进 prompt 或回给前端」。
    它**不**表示「可以据此直接执行能力位」。

    理由（2026-11-04 实测）：
      · 我的负样本全部落在 `needs_input`，压根进不到阈值这一层 ——
        所以"0 误伤"不是阈值的功劳，拿它当"可以放心执行"的证据是假的。
      · `ratio` 在图上几乎不筛东西：9 个正样本最小 ratio 也有 10.71，
        因为激活传播的 top2 掉得很快。真正的信号是 `share`。
      · `wiring-build.py 坏了` 这种从 `code:` 节点起跳的正确命中，
        share 只有 0.126 —— 阈值压低是为了不误杀它，代价是筛得更松。

    所以阈值定在 0.12 / 5.0：覆盖全部正确样本，宁可松。
    要拿来执行，必须先有单独的只读白名单 + 授权设计，不许用这个字段凑合。

    判据（两条同时成立才算 confident）：
      · top1 份额 ≥ min_share
      · top1 / top2 ≥ min_ratio
    """
    t0 = time.perf_counter()
    r = route(query=query, topk=topk)
    ms = (time.perf_counter() - t0) * 1000
    if not r.get("ok"):
        return dict(ok=False, status=r.get("status"), why=r.get("why"),
                    query=query, latency_ms=round(ms, 2))

    top = r["top"]
    if not top:
        return dict(ok=False, status="needs_input", why="传播后没有 cap 节点",
                    query=query, latency_ms=round(ms, 2))

    s1 = top[0]["score"]
    s2 = top[1]["score"] if len(top) > 1 else 0.0
    share = top[0]["share"]
    ratio = (s1 / s2) if s2 > 0 else float("inf")
    confident = bool(share >= min_share and ratio >= min_ratio)

    return dict(
        ok=True, status="ok",
        query=query,
        seeds=r.get("seeds") or [],
        notes=r.get("notes") or [],
        top=top,
        confident=confident,
        judge={"share": round(share, 4), "ratio": (round(ratio, 2) if ratio != float("inf") else None),
               "min_share": min_share, "min_ratio": min_ratio},
        latency_ms=round(ms, 2),
    )


# 脉冲直达白名单：命中这些能力位（且 op 只读）时，可以**跳过 LLM 直接执行**。
# 主人令 2026-11-04：「运行不要按照原来的跑法，必须按照触手关联互通来实现精准直达脉冲提速」。
#
# 为什么必须白名单：`hint` 只能证明"这句话最像在说这个能力位"，证明不了
# "现在执行它安全"。写盘 / 发消息 / 删文件那一类，一律不许走直达 ——
# 走直达就等于用一次 16ms 的图查询替代整套门禁，那是拿安全换速度。
# 白名单里只放**纯读、不写盘、不出网、不起进程**的 op。
PULSE_CAPS = {
    "impact_check": {
        "ops": ("status", "impact", "risky", "where", "recent"),
        "needs": {"impact": "path", "risky": None, "status": None,
                  "where": None, "recent": None},
    },
    "tactile_tree": {
        "ops": ("stats", "diag", "route", "neighbors", "hint"),
        "needs": {"stats": None, "diag": None, "route": "path",
                  "neighbors": "path", "hint": None},
    },
}


def _find_paths_in(text: str) -> list:
    """从原话里抽文件路径。只认字面出现、且盘上真存在的路径。

    复用 `capability_router` 的抽取器（同仓同一口径），抽不到就返回空 ——
    抽不到路径时 `impact` 这种 op 必须拒绝，不许拿"猜"补参数。
    """
    try:
        from gbt_allinone import capability_router as _cr
        got = _cr._find_paths(text)                    # noqa: SLF001
        return [p for p in (got or [])]
    except Exception:                                  # noqa: BLE001
        return []


def _params_for(cap: str, need: str, query: str) -> tuple:
    """按白名单要求的参数类型抽参。返回 (params, why)。抽不到 params=None。"""
    if need is None:
        return {}, ""
    if need == "path":
        paths = _find_paths_in(query)
        if not paths:
            return None, "这句话里没有可识别的文件路径"
        return {"target": "code:" + paths[0].replace("\\", "/").lstrip("./")}, ""
    return None, "白名单要求了未知的参数类型 %r" % need


def pulse(query: str = "", cap: str = "", op: str = "") -> dict:
    """**脉冲直达**：一次图查询（~17ms）+ 一次只读执行，绕过 LLM（21.6s）。

    与 `hint` 的区别：`hint` 只给候选，`pulse` 判**能不能直接执行**。
    三条硬条件，缺一即拒：
      ① `hint` 必须 confident
      ② 命中的能力位必须在 `PULSE_CAPS` 白名单里
      ③ 该 op 需要的参数必须能从原话里**字面**抽到
    拒绝时返回 `denied` / `needs_input`，**不许降级成"试着执行一下"**。
    """
    t0 = time.perf_counter()
    h = hint(query=query, topk=5)
    if not h.get("ok") or not h.get("confident"):
        return dict(ok=False, status="needs_input",
                    why="触手树不敢定：%s" % (h.get("why") or "置信度不足"),
                    judge=h.get("judge"), latency_ms=round((time.perf_counter() - t0) * 1000, 2))

    node = cap or (h["top"][0]["node"] if h.get("top") else "")
    if node not in PULSE_CAPS:
        return dict(ok=False, status="denied",
                    why="能力位 %r 不在只读白名单，走直达就等于跳过门禁" % node,
                    candidate=node,
                    whitelist=sorted(PULSE_CAPS),
                    latency_ms=round((time.perf_counter() - t0) * 1000, 2))

    spec = PULSE_CAPS[node]
    # op 选择：**别默认取第一个**，也别在"缺参数"时偷换 op。
    # 实测教训：「impact_check 看一下」曾静默降级成 `status` 并返回 ok=True，
    # 于是用户问"影响面"却拿到"报个状态" —— 成功返回一个没被问的东西，比报错更坏。
    # 规则：句子里有影响面意图词，或者带路径 ⇒ impact（缺 target 就 needs_input）。
    low_q = (query or "").lower()
    _impact_words = ("影响", "impact", "影响面", "会撞", "连带", "波及")
    use_op = op
    if not use_op:
        if "impact" in spec["ops"] and (
                any(w in low_q for w in _impact_words) or _find_paths_in(query)):
            use_op = "impact"
        elif "hint" in spec["ops"] and node == "tactile_tree":
            use_op = "hint"
        else:
            use_op = spec["ops"][0]
    if use_op not in spec["ops"]:
        return dict(ok=False, status="denied",
                    why="op %r 不在 %s 的白名单里" % (use_op, node),
                    allowed=list(spec["ops"]),
                    latency_ms=round((time.perf_counter() - t0) * 1000, 2))

    params, why = _params_for(node, spec["needs"].get(use_op), query)
    if params is None:
        return dict(ok=False, status="needs_input",
                    why="参数抽不到，不猜：%s" % why,
                    candidate=node, op=use_op,
                    latency_ms=round((time.perf_counter() - t0) * 1000, 2))

    return dict(ok=True, status="ready",
                cap=node, op=use_op, params=params,
                via="tactile-pulse",
                seeds=h.get("seeds") or [],
                judge=h.get("judge"),
                route_ms=round((time.perf_counter() - t0) * 1000, 2))


def locate(query: str = "", topk: int = 5, lines: int = 3) -> dict:
    """**整页脉冲**：一次查询给出「哪一页 · 第几行」，**不读整页**。

    主人令 2026-11-04：「你没有做触手覆盖每一页整页脉冲推进，这样时间浪费在
    读取页面信息了」。

    在这之前的 `route` 只到文件级：它说"去 page:xxx.md"，然后调用方还得
    `open()` 整页再找 —— 4769 个页面文件、109.4 MB，那才是慢的地方。

    两级推进，两级都不读整页：
      ① 触手图（6305 节点，~17ms）→ 定位到 page/code 节点
      ② `codepage` 倒排索引（21416 符号，~20ms）→ 定位到页内行号
    ①+② 全程只读内存里的索引；只有最后要原文时才按 offset 取那几行。
    """
    t0 = time.perf_counter()
    # ① 图定位：不过滤 kind，page/code/cap 一起排。
    #    注意：**图定位失败不阻断** —— codepage 是倒排索引，不需要种子。
    #    原写法在 route 报 needs_input 时直接 return，于是"脉冲直达是怎么实现的"
    #    这种没有能力位名的句子永远查不到 —— 而那正是最该查的句子。
    r = route(query=query, topk=max(topk * 4, 20), kind="")
    graph_ok = bool(r.get("ok"))
    files = [x["node"] for x in (r.get("top") or [])
             if x["node"].startswith(("page:", "code:"))] if graph_ok else []
    graph_ms = (time.perf_counter() - t0) * 1000

    # ② 页内索引：拿到行号，不打开文件（codepage 字段：file / line / symbol / kind）
    hits = []
    cp_ms = 0.0
    try:
        from gbt_allinone import codepage as _cp
        t1 = time.perf_counter()
        got = _cp.find(query, top=max(topk * 3, 8))
        cp_ms = (time.perf_counter() - t1) * 1000
        if got.get("ok"):
            want = {f.split(":", 1)[1].replace("\\", "/") for f in files}
            for e in (got.get("hits") or []):
                rel = str(e.get("file") or e.get("rel") or "").replace("\\", "/")
                if not rel:
                    continue
                # 要么命中图定位到的那几页，要么（图没定位到时）就全收
                if want and not any(rel == w or rel.endswith(w) or w.endswith(rel) for w in want):
                    continue
                hits.append({"page": rel, "symbol": e.get("symbol"),
                             "line": e.get("line"), "kind": e.get("kind"),
                             "score": e.get("score"), "doc": e.get("doc")})
    except Exception as e:                              # noqa: BLE001
        cp_ms = -1.0
        hits.append({"error": "%s: %s" % (type(e).__name__, str(e)[:80])})

    ms = (time.perf_counter() - t0) * 1000
    return dict(
        ok=True, status="ok",
        query=query,
        pages=files[:topk],
        hits=hits[:topk],
        # 逐段计时：哪一级慢一眼看得出来，不用靠猜
        graph_ms=round(graph_ms, 2),
        codepage_ms=round(cp_ms, 2),
        latency_ms=round(ms, 2),
        read_files=0,                     # 定位过程读了几个文件 —— 恒为 0，这是重点
        how="① 图定位(~17ms/6305节点) → ② 页内倒排(~20ms/21416符号)；都不 open 整页",
    )


OPS = {"build", "route", "spread", "neighbors", "stats", "bench", "diag",
       "hint", "pulse", "locate"}


def run(op: str = "stats", **kw) -> dict:
    op = (op or "stats").strip().lower()
    try:
        if op == "build":
            return build(force=bool(kw.get("force")))
        if op == "route":
            return route(
                query=kw.get("query") or "",
                target=kw.get("target") or "",
                topk=int(kw.get("topk") or DEFAULT_TOPK),
                iters=int(kw.get("iters") or DEFAULT_ITERS),
                damping=float(kw.get("damping") or DEFAULT_DAMPING),
                kind=kw.get("kind") or "cap",
                use_router=bool(kw.get("use_router", True)),
            )
        if op == "spread":
            seeds = kw.get("seeds") or {}
            if isinstance(seeds, str):
                seeds, _ = seed_from_query(seeds)
            act = spread(seeds, int(kw.get("iters") or DEFAULT_ITERS),
                         float(kw.get("damping") or DEFAULT_DAMPING))
            top = sorted(act.items(), key=lambda x: -x[1])[:int(kw.get("topk") or DEFAULT_TOPK)]
            if not act:
                return _need_input("传播无激活：种子不在图里", seeds=list(seeds))
            return dict(ok=True, status="ok", reached=len(act),
                        top=[{"node": n, "activation": round(v, 6)} for n, v in top])
        if op == "neighbors":
            return neighbors(kw.get("node") or kw.get("target") or "",
                             int(kw.get("limit") or 20))
        if op == "stats":
            return stats()
        if op == "bench":
            return bench(int(kw.get("rounds") or 30))
        if op == "diag":
            return diag()
        if op == "hint":
            return hint(
                kw.get("query") or "",
                int(kw.get("topk") or 5),
                float(kw.get("min_share", 0.12)),
                float(kw.get("min_ratio", 5.0)),
            )
        if op == "pulse":
            # 注意：`op` 在这里已经是 "pulse"，能力位自己的 op 用 target_op 传
            return pulse(
                query=kw.get("query") or "",
                cap=kw.get("cap") or "",
                op=kw.get("target_op") or "",
            )
        if op == "locate":
            return locate(
                query=kw.get("query") or "",
                topk=int(kw.get("topk") or 5),
            )
        return _need_input("未知 op：%s" % op, ops=sorted(OPS))
    except FileNotFoundError as e:
        return _need_dep("触手树文件", str(e))
    except Exception as e:                              # noqa: BLE001
        return _failed(e, op=op)


if __name__ == "__main__":
    import pprint
    pprint.pprint(run(sys.argv[1] if len(sys.argv) > 1 else "diag"))
