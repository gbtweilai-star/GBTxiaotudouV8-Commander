# -*- coding: utf-8 -*-
"""codepage —— 代码页索引：把「每个代码每一页」变成可直达的索引

主人令（2026-11-04）：「她这个速度不能使用我们的触手双向绑定每一页，
覆盖每一个代码每一页可以和所有页面互通，实现精准直达脉冲提速」。

—— 为什么不能靠模型逐页读 ——
本机实测：零系统提示 1.4 秒/次。代码库实测 **4014 个 .py / 52.46 MB / 约 115 万行**。
1.4 秒 × 4014 = **约 94 分钟**，而且这还是理想情况（模型只做分类、不生成）。
「逐页绑定」在物理上就不成立 —— 不是调优问题，是量级问题。

—— 所以改成「一次建索引，之后毫秒直达」——
  ① 建：扫一遍所有 .py，用 `ast` 抽出文件/类/函数 + docstring 首句 → 落一份紧凑索引
  ② 查：内存倒排索引（关键词 → 条目），**不启动模型、不逐页读文件**
  ③ 直达：回 `文件:行号` + 可选原文片段，调用方拿到就能跳

速度对照（同一台机器）：
  逐页问模型    ~1400 ms/页   × 4014 页 ≈ 94 分钟
  索引直达      ~1~3 ms/次    （建索引一次性，约 10~30 秒）

—— 覆盖范围（如实分层，不混为一谈）——
  core    `gbt_allinone/` `tools/` `packs/`  —— 她自己的器官，符号级索引
  vendor  `vendor/pylibs/`（numpy 等第三方）—— 只做文件级，不假装是自己的代码
  state   `state/proactive/work/...`（工作副本）—— 文件级标记为副本，避免和主本重复抢答
  注：「覆盖每一个」≠「每个都一样重」，但**每一个都能被查到**。
"""
from __future__ import annotations

import ast
import json
import math
import os
import re
import time

_INDEX_NAME = os.path.join("state", "codepage_index.json")
_TIERS = (
    ("gbt_allinone", "core"),
    ("tools", "core"),
    ("packs", "core"),
    ("tests", "core"),
    ("vendor", "vendor"),
    ("state", "state"),
)
_SKIP_DIRS = {"__pycache__", "pyembed", "site-packages", ".git", "node_modules",
              ".pytest_cache", ".mypy_cache"}
_STOP = set("的了在是我有个把这那一下吗呢吧啊就都也还")

# 同义词归一：字面索引天生吃亏的地方在这里补 —— 人喊「本地模型」，代码里写的是
# 「本机算力 / local_llm」，字面永远对不上。这是一张**小而有界**的表，不追求全。
_SYN = {
    "本地": "本机", "本机": "本地",
    "模型": "llm", "llm": "模型",
    "图像": "图片", "图片": "图像",
    "文字": "文本", "文本": "文字",
    "入口": "接口", "接口": "入口",
    "报错": "错误", "错误": "报错",
    "配置": "config", "config": "配置",
}


def _expand(terms: set) -> set:
    """把查询词按同义表扩一层（只扩查询侧，索引侧不动，避免污染）。"""
    out = set(terms)
    for t in list(terms):
        alt = _SYN.get(t)
        if alt:
            out.add(alt)
    return out


def _root() -> str:
    """payload 根：本文件在 `payload/gbt_allinone/` 下，上退两级。"""
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _index_path() -> str:
    return os.path.join(_root(), _INDEX_NAME)


def _tier(rel: str) -> str:
    head = rel.replace("\\", "/").split("/")[0]
    for name, tier in _TIERS:
        if head == name:
            return tier
    return "other"


def _doc_first(node) -> str:
    """docstring 首行 —— 索引里只留这一句，够定位，不吃体积。"""
    try:
        d = ast.get_docstring(node) or ""
        line = d.strip().splitlines()[0].strip() if d.strip() else ""
        return line[:120]
    except Exception:                                              # noqa: BLE001
        return ""


def _scan_file(path: str, rel: str):
    """一个文件的页条目 + 符号条目。解析失败如实记，不静默丢。"""
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            src = f.read()
    except OSError as exc:
        return None, [], "读失败: %s" % str(exc)[:80]

    lines = src.count("\n") + 1
    try:
        tree = ast.parse(src)
    except SyntaxError:
        page = [rel, lines, len(src), _tier(rel), ""]
        return page + ["syntax_error"], [], "语法错误"

    # 模块级 docstring 必须收 —— 实测漏了它，「视觉入口」就找不到 vision_eye.py：
    # 那个文件的能力说明全写在模块头上，函数本身只有 parse/find 这种通用名。
    _md = (ast.get_docstring(tree) or "").strip().splitlines()
    page = [rel, lines, len(src), _tier(rel), _md[0][:200] if _md else ""]

    syms = []
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            syms.append([node.name, rel, node.lineno, "def", _doc_first(node)])
        elif isinstance(node, ast.ClassDef):
            syms.append([node.name, rel, node.lineno, "class", _doc_first(node)])
            # 类里的方法：只收一层，够用且不膨胀
            for sub in node.body:
                if isinstance(sub, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    syms.append(["%s.%s" % (node.name, sub.name), rel, sub.lineno,
                                 "method", _doc_first(sub)])
    return page, syms, None


def _replica_base(rel: str):
    """`state/proactive/work/g-1/<X>` → `<X>`；不是工作副本则 None。"""
    parts = rel.replace("/", "\\").split("\\")
    try:
        i = parts.index("g-1")
    except ValueError:
        return None
    return "\\".join(parts[i + 1:])


def build(progress: bool = False) -> dict:
    """全量重建索引。一次性动作；之后查询是毫秒级。

    ── 2026-11-04 加：跳过「有主本对应的工作副本」──
    实测证据（200 条客观评估集）：
      含副本    top1 76.0% / top3 80.0% / MRR 0.781 / 46.6ms / 索引 5.9MB / 4013 页
      过滤后    top1 79.0% / top3 80.5% / MRR 0.797 / 28.1ms / 索引 3.4MB / 2355 页
    归因：6 条 top-1 错误是 `state/proactive/work/g-1/` 下的同名副本抢答主本
    （如 bounty.py 期望 gbt_allinone/bounty.py，实得 state/.../g-1/gbt_allinone/bounty.py）。
    副本占索引 44%，内容与主本重复 —— 不该抢主本的位置。

    ⚠️ 只跳「有主本对应」的，**孤本必须留下**：
    实测 1765 个副本里 1662 个(94.2%)有主本，103 个是孤本
    （如 state/immune/purge_aclui_worm.py 就是真身，不是副本）。
    无差别排除 state 会丢这 103 个。
    """
    t0 = time.time()
    root = _root()

    # ① 先只收路径（不解析），用于判断「有没有主本」
    all_rel = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in _SKIP_DIRS]
        for fn in filenames:
            if fn.endswith(".py"):
                all_rel.append(os.path.relpath(os.path.join(dirpath, fn), root))
    core_set = {r for r in all_rel if _tier(r) == "core"}
    skip = {r for r in all_rel
            if _tier(r) == "state" and _replica_base(r) in core_set}
    keep = [r for r in all_rel if r not in skip]

    # ② 只解析留下的
    files, syms, bad = [], [], []
    n = 0
    for rel in keep:
        page, s, err = _scan_file(os.path.join(root, rel), rel)
        n += 1
        if page:
            files.append(page)
            syms.extend(s)
        if err:
            bad.append([rel, err])
        if progress and n % 500 == 0:
            print("  ...%d 个文件" % n)

    data = {"built": time.strftime("%Y-%m-%dT%H:%M:%S"), "root": root,
            "files": files, "syms": syms, "bad": bad[:200],
            "skipped_replicas": len(skip),
            "counts": {"files": len(files), "syms": len(syms), "bad": len(bad),
                       "skipped_replicas": len(skip)}}

    p = _index_path()
    os.makedirs(os.path.dirname(p), exist_ok=True)
    tmp = p + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, separators=(",", ":"))
    os.replace(tmp, p)

    data["ok"] = True
    data["elapsed_ms"] = int((time.time() - t0) * 1000)
    data["index"] = p
    data["size_kb"] = int(os.path.getsize(p) / 1024)
    data.pop("files", None)      # 建完不回灌整份数据，省 token
    data.pop("syms", None)
    return data


_CACHE: dict = {"mtime": None, "data": None, "inv": None}


def _load() -> dict:
    """载入索引 + 现建倒排（不落盘，避免体积翻倍）。带 mtime 失效。"""
    p = _index_path()
    if not os.path.exists(p):
        return {"ok": False, "reason": "索引还没建：先跑 codepage build",
                "hint": "api.run_task('codepage', {'op':'build'})"}
    mt = os.path.getmtime(p)
    if _CACHE["mtime"] == mt and _CACHE["data"] is not None:
        return _CACHE["data"]

    with open(p, "r", encoding="utf-8") as f:
        data = json.load(f)
    data["ok"] = True

    # 倒排：词 → 条目下标；files 与 syms 分开两本，查询时各取所需
    f_inv, s_inv = {}, {}
    for i, row in enumerate(data.get("files") or []):
        # ⚠️ 2026-11-04 修：这里原来只索引 `_terms(row[0])`（纯路径），
        # 而评分时用的是 `_terms(rel) | _terms(mdoc)` —— 两边口径不一致，
        # 导致「docstring 权重」是**永远走不到的死代码**：查询词只出现在模块说明里时，
        # 该文件压根进不了候选集。实测后果：37 条(18.5%) 召回失败，top=4000 也捞不回来。
        # 对齐后：前50召回 81.5% → 100%；倒排词表 3148 → 16277。
        for w in _terms(row[0]) | _terms(row[4] if len(row) > 4 else ""):
            f_inv.setdefault(w, set()).add(i)
    for i, row in enumerate(data.get("syms") or []):
        for w in _terms(row[0]) | _terms(row[4] or ""):
            s_inv.setdefault(w, set()).add(i)

    _CACHE.update({"mtime": mt, "data": data, "inv": (f_inv, s_inv)})

    # 每页符号数 —— 用于规模抑制：api.py 有几千个符号，任何泛词都能在里面撞到，
    # 不打折的话它会把真正对应的模块永远挤下去（实测「视觉入口」被它抢了两次）。
    cnt: dict = {}
    for row in data.get("syms") or []:
        cnt[row[1]] = cnt.get(row[1], 0) + 1
    _CACHE["sym_cnt"] = cnt

    # 每页的固定词集（文件名 + 模块说明）预切一次 —— 实测不预切的话，
    # 每次查询都在循环里重切 4000 多次，耗时从 8ms 涨到 45ms。
    _CACHE["page_terms"] = {row[0]: (_terms(row[0]) | _terms(row[4] if len(row) > 4 else ""))
                            for row in data.get("files") or []}

    # 符号词集同样预切 —— 查询热路径上只做集合交集，不再切词
    _CACHE["sym_terms"] = [_terms(r[0]) | _terms(r[4] or "")
                           for r in (data.get("syms") or [])]
    return data


def _terms(text: str) -> set:
    """切词：ASCII 按标识符拆（驼峰也拆），中文按 2-gram。只用于倒排，不追求语言学正确。"""
    text = str(text or "")
    out = set()
    for w in re.findall(r"[A-Za-z_][A-Za-z0-9_]*", text):
        lw = w.lower()
        if len(lw) >= 2:
            out.add(lw)
        # 驼峰 / 下划线拆开
        for part in re.split(r"[_\W]+|(?<=[a-z])(?=[A-Z])", w):
            if len(part) >= 2:
                out.add(part.lower())
    for seg in re.findall(r"[\u4e00-\u9fff]+", text):
        for i in range(len(seg) - 1):
            g = seg[i:i + 2]
            if g not in _STOP:
                out.add(g)
        if len(seg) <= 4:
            out.add(seg)
    return out


def _score(entry_terms: set, q_terms: set, q_lens: int, extra_terms=None) -> float:
    """命中按**词长加权**，并给**共现**额外奖励。

    只数命中个数会被泛词淹没（router.py 踩过同款坑）：
    「视觉入口」里「入口」这种词到处都有，单个命中不能胜出；
    必须两个词都落在同一页，才说明真的是它。
    """
    hit = set(entry_terms & q_terms)
    ex = set((extra_terms or set()) & q_terms)
    allhit = hit | ex
    if not allhit:
        return 0.0
    base = sum(len(w) for w in allhit) / float(max(q_lens, 1))
    base *= (1.0 + 0.35 * (len(allhit) - 1))    # 共现：2 词都中 ⇒ ×1.35
    return base


def find(query: str, top: int = 8, tier: str = "") -> dict:
    """关键词 → 直达代码页。回 `文件:行号`，命中 core 优先。"""
    q = str(query or "").strip()
    if not q:
        return {"ok": False, "reason": "需要 query：要找什么"}
    data = _load()
    if not data.get("ok"):
        return data

    f_inv, s_inv = _CACHE["inv"]

    # ⓿ 喊名字直达：查询词本身就是符号名/文件名 ⇒ 不评分，直接给。
    #    「精准直达」的本义就是这个 —— 说出名字就该到那一页，不该在相似度里排队。
    ql = q.lower()
    direct = []
    for name, rel, line, kind, doc in (data.get("syms") or []):
        if name.lower() == ql:
            direct.append({"score": 9.9, "kind": kind, "symbol": name,
                           "page": "%s:%d" % (rel, line), "file": rel, "line": line,
                           "tier": _tier(rel), "doc": doc})
    for row in (data.get("files") or []):
        stem = os.path.splitext(os.path.basename(row[0]))[0]
        if stem.lower() == ql:
            direct.append({"score": 9.8, "kind": "page", "symbol": stem,
                           "page": row[0], "file": row[0], "line": 1, "tier": row[3],
                           "doc": (row[4] if len(row) > 4 else "")})
    if direct:
        direct.sort(key=lambda r: (-r["score"], r["page"]))
        return {"ok": True, "query": q, "count": len(direct[:top]),
                "total_hits": len(direct), "direct": True,
                "best": direct[0], "hits": direct[:top]}

    q_terms = _expand(_terms(q))
    if not q_terms:
        return {"ok": False, "reason": "query 里没有可用词（全是虚词？）"}
    q_lens = sum(len(w) for w in q_terms)

    # 文件 → 模块 docstring（一次建好，别在循环里扫 4013 条）
    mod_docs = {row[0]: (row[4] if len(row) > 4 else "") for row in (data.get("files") or [])}
    page_terms = _CACHE.get("page_terms") or {}
    sym_cnt = _CACHE.get("sym_cnt") or {}
    sym_terms = _CACHE.get("sym_terms") or []

    # ① 符号级（更精确）—— 名字直接命中权重最高
    hits = []
    for w in q_terms:
        for i in s_inv.get(w, ()):
            hits.append(i)
    seen, rows = set(), []
    for i in set(hits):
        name, rel, line, kind, doc = data["syms"][i]
        if tier and _tier(rel) != tier:
            continue
        et = sym_terms[i] if i < len(sym_terms) else (_terms(name) | _terms(doc))
        # 模块名 + 模块说明也是「这一页在干什么」的证据（预切好的，直接取）
        extra = page_terms.get(rel) or set()
        sc = _score(et, q_terms, q_lens, extra)
        if q.lower() in name.lower():
            sc += 1.0                    # 名字里直接含查询词 —— 比文档里含重要得多
        if _tier(rel) == "core":
            sc += 0.25                   # 自己的代码优先于 vendor / 工作副本
        # 规模抑制：符号越多的页，单条命中的信息量越小
        n = sym_cnt.get(rel, 1)
        sc *= 1.0 / (1.0 + math.log(1.0 + n / 40.0))
        rows.append({"score": round(sc, 3), "kind": kind, "symbol": name,
                     "page": "%s:%d" % (rel, line), "file": rel, "line": line,
                     "tier": _tier(rel), "doc": doc})

    # ② 文件级补漏（模块没有对应函数名时，整页仍要能找到）
    fhits = []
    for w in q_terms:
        for i in f_inv.get(w, ()):
            fhits.append(i)
    for i in set(fhits):
        row = data["files"][i]
        rel, lines, size, tr = row[0], row[1], row[2], row[3]
        mdoc = row[4] if len(row) > 4 else ""
        if tier and tr != tier:
            continue
        sc = _score(_terms(rel) | _terms(mdoc), q_terms, q_lens) * 0.6
        if q.lower() in rel.lower():
            sc += 0.8
        if tr == "core":
            sc += 0.25
        rows.append({"score": round(sc, 3), "kind": "page", "symbol": os.path.basename(rel),
                     "page": rel, "file": rel, "line": 1, "tier": tr,
                     "doc": "%d 行 / %d B%s" % (lines, size, (" · " + mdoc[:60]) if mdoc else "")})

    rows.sort(key=lambda r: (-r["score"], r["page"]))
    out = rows[:max(1, int(top))]
    return {"ok": True, "query": q, "count": len(out), "total_hits": len(rows),
            "best": out[0] if out else None, "hits": out,
            "ms": None}


def goto(symbol: str, context: int = 0) -> dict:
    """按符号名精确定位，可选带出上下文源码 —— 「直达这一页的这一行」。"""
    s = str(symbol or "").strip()
    if not s:
        return {"ok": False, "reason": "需要 symbol：函数/类名"}
    data = _load()
    if not data.get("ok"):
        return data
    exact = [r for r in (data.get("syms") or []) if r[0] == s]
    if not exact:
        exact = [r for r in (data.get("syms") or []) if r[0].lower() == s.lower()]
    if not exact:
        return {"ok": False, "reason": "没有这个符号: %s" % s,
                "hint": "先用 op=find 搜关键词"}

    root = data.get("root") or _root()
    out = []
    for name, rel, line, kind, doc in exact[:5]:
        row = {"symbol": name, "kind": kind, "page": "%s:%d" % (rel, line),
               "file": rel, "line": line, "tier": _tier(rel), "doc": doc}
        if context:
            try:
                with open(os.path.join(root, rel), "r", encoding="utf-8",
                          errors="replace") as f:
                    lines = f.readlines()
                a = max(0, line - 1 - context)
                b = min(len(lines), line - 1 + context + 1)
                row["code"] = "".join(lines[a:b])
            except OSError as exc:
                row["code_error"] = str(exc)[:80]
        out.append(row)
    return {"ok": True, "symbol": s, "count": len(out), "hits": out, "best": out[0]}


def stats() -> dict:
    """索引现况：覆盖了多少页、多少符号、各层占比、索引体积。"""
    data = _load()
    if not data.get("ok"):
        return data
    files = data.get("files") or []
    syms = data.get("syms") or []
    tiers = {}
    for row in files:
        tiers[row[3]] = tiers.get(row[3], 0) + 1
    p = _index_path()
    return {"ok": True, "built": data.get("built"),
            "files": len(files), "syms": len(syms),
            "tiers": tiers,
            "bad": len(data.get("bad") or []),
            "index_kb": int(os.path.getsize(p) / 1024) if os.path.exists(p) else 0,
            "index": p,
            "note": "core=她自己的器官；vendor=第三方库；state=工作副本（会与主本重复，查询已让 core 优先）"}


def run(op: str = "stats", **kw) -> dict:
    o = str(op or "stats").strip()
    if o in ("build", "rebuild", "index"):
        return build(progress=bool(kw.get("progress")))
    if o in ("find", "search", "goto_page"):
        return find(kw.get("query") or kw.get("q") or kw.get("text") or "",
                    int(kw.get("top") or 8), str(kw.get("tier") or ""))
    if o in ("goto", "sym", "symbol"):
        return goto(kw.get("symbol") or kw.get("name") or "",
                    int(kw.get("context") or 0))
    if o in ("stats", "status"):
        return stats()
    return {"ok": False, "reason": "未知 op: %s" % o,
            "supported": ["build", "find", "goto", "stats"]}
