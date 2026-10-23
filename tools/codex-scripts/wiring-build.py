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
BINDINGS = ROOT / "state" / "cap-bindings.json"
OUT = ROOT / "state" / "model-pack" / "wiring.json"

CODE_EXT = {".py", ".js", ".mjs", ".cjs", ".ts", ".tsx", ".jsx", ".sh", ".ps1", ".cmd", ".bat"}
PAGE_EXT = {".html", ".htm", ".md", ".txt", ".json", ".jsonl", ".csv", ".svg", ".css", ".yml", ".yaml"}
WEAK_KINDS = {"cap_mention"}

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


def build() -> tuple:
    if not EDGES.is_file():
        return None, {"ok": False, "error": "missing_edges",
                      "why": "没有 %s —— 先跑 py -3.14 tools/codex-scripts/repo-pack.py refs"
                             % EDGES.relative_to(ROOT)}
    adj = collections.defaultdict(set)
    strong = collections.defaultdict(set)
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
                adj[node].add(b); adj[b].add(node)
                strong[node].add(b); strong[b].add(node)
        by_kind["dispatch"] = dispatch_n

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
                adj[c].add(t); adj[t].add(c)
                strong[c].add(t); strong[t].add(c)
                bind_n += 1
            if row.get("carrier"):
                k = "carrier:" + str(row["carrier"])
                adj[c].add(k); adj[k].add(c)
                strong[c].add(k); strong[k].add(c)
                bind_n += 1
            if row.get("handler"):
                k = "handler:" + str(row["handler"])
                adj[c].add(k); adj[k].add(c)
                strong[c].add(k); strong[k].add(c)
                bind_n += 1

    nodes = set(adj) | {y for v in adj.values() for y in v}
    return {
        "adj": adj, "strong": strong, "nodes": nodes,
        "by_kind": dict(by_kind), "raw_edges": n, "dropped_paths": dropped,
        "bind_edges": bind_n,
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
                old = (o.get("nodes"), o.get("edges"), o.get("at"))
            except ValueError:
                old = None
        if old:
            print("现有 wiring.json：节点 %s · 边(有向) %s · 构建于 %s" % old)
            print("新图（有向 %d）—— 差异请自行判读，--check 不写盘" % (sum(len(v) for v in adj.values())))
        return 0

    OUT.parent.mkdir(parents=True, exist_ok=True)
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
        "note": ("四边图（**保留强弱**）：adj=全边（含 cap_mention 弱边）· strong_adj=真依赖"
                 "（path 引用 + cap 真引用 + 绑定账）· 写手 tools/codex-scripts/wiring-build.py"),
        "builder": "tools/codex-scripts/wiring-build.py",
        "adj": {k: sorted(v) for k, v in adj.items()},
        "strong_adj": {k: sorted(v) for k, v in strong.items()},
    }
    OUT.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    print("已写 %s（%.1f MB）" % (OUT.relative_to(ROOT), OUT.stat().st_size / 1e6))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
