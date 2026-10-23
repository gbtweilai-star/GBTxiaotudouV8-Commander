# gbt-capability: impact_check
# ⛔ 开发者：自由的风 · 永久钢印 · 禁止删除
"""影响面检查（impact_check）—— 改一处之前，先把与它相连的所有地方点出来。

主人令 2026-10-19（逐字）：「修改一个地方的时候要分出触手关注跟这个修复的地方相连的所有地方，
确保你修改其他地方不会被连带故障，这也是防止这么修故障一直在的意思。」
主人同日再一句：「你先看多域监控是什么别又理解错了」「改一处之前，先分出触手盯住与它相连的
所有地方，确保不会连带故障，防止『越修越坏』。」

## 这一位是干什么的（先把边界钉死，别跟 selfscan 混）
- **本位 = 影响面（blast radius）**：读 `state/model-pack/wiring.json` 的邻接图，回答
  「动 X 会连带动到谁、改完必须逐一验证哪几个」。
- **不是** `selfscan`（那是框架五维自检：路由/模块/存储/审计/桩缺口），也**不是** `health`。
  两者回答的问题不同：selfscan 问「框架自己有没有病」，本位问「**我要动的这一刀，刀口有多宽**」。

## 图是什么（现读，不手写）
`state/model-pack/wiring.json` → `{adj: {node: [neighbor, ...]}}`，节点前缀即类型：
`code:` 代码件 · `page:` 页面 · `cap:` 能力位 · `tent:` 触手 · `carrier:` 承载 · `handler:` 处理器。
现读规模（每次调用现场数，不抄注释）：6301 节点 / 951536 有向边（≈475768 无向边）/ 单连通分量。

## ops（读面，全部纯读免门；不写盘、不出网、不起进程）
- `status`  —— 图的规模、连通性、构建时间（**取不到就如实报 missing，不编 0**）
- `impact`  —— `target`（单个，或 `targets` 列表）＋ `depth`（默认 2）⇒ 影响面构成 +
               **1 跳必验清单**（这是"改完必须逐一验证"的那张单子）
- `risky`   —— `n`（默认 8）⇒ 按**真实刀口**排最危险的件：数它的 1 跳里有多少
               `code:`/`page:`/`cap:` 邻居（不是数它在别人注释里被提了几次）
- `where`   —— 这一位的落点

## 三条纪律（本仓血账）
1. **目标不在图里 ⇒ 如实说"不在图里"，不许返回空集当"没影响"**（空集会被念成"很安全"，
   这是最贵的一种假绿：`normalize` 拼错一个前缀就能造出它）。
2. **`depth` 超过 3 ⇒ 拒**：全图 6301 节点，深度一大就等于"什么都能影响"，那张单子没法验。
3. **本位只报影响面，不代跑验证**：验证要由调用方拿着 1 跳清单逐个真跑（走动的是
   `tentacle_arm move` / 各判据）。本位把"调了"当"到了"是另一种假绿。
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    if hasattr(_s, "reconfigure"):
        _s.reconfigure(encoding="utf-8", errors="replace")

OPS = ("status", "impact", "risky", "where")
MAX_DEPTH = 3
_ROOT = Path(__file__).resolve().parents[2]
_WIRING = _ROOT / "state" / "model-pack" / "wiring.json"
_KINDS = ("page", "code", "cap", "tent", "carrier", "handler")
_EXT_CODE = (".py", ".js", ".ts", ".mjs", ".cjs")
_EXT_PAGE = (".html", ".htm")
_EXT_DATA = (".json", ".jsonl", ".md", ".csv")

_CACHE: dict = {"key": None, "adj": None, "strong": None}


def _load() -> tuple:
    """现读邻接图。缓存键 = (mtime, size)，图一变就重读（不拿旧图算新刀口）。"""
    if not _WIRING.exists():
        return None, {"ok": False, "error": "missing", "why": "不存在: state/model-pack/wiring.json"}
    try:
        st = _WIRING.stat()
    except OSError as e:
        return None, {"ok": False, "error": "unreadable", "why": str(e)}
    key = (st.st_mtime_ns, st.st_size)
    if _CACHE["key"] == key and _CACHE["adj"] is not None:
        return _CACHE, None
    try:
        raw = json.loads(_WIRING.read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        return None, {"ok": False, "error": "parse_failed", "why": "%s: %s" % (type(e).__name__, e)}
    adj = raw.get("adj") if isinstance(raw, dict) else None
    if not isinstance(adj, dict):
        return None, {"ok": False, "error": "bad_shape",
                      "why": "wiring.json 里没有 adj 字典（顶层键: %s）"
                             % (sorted(raw)[:8] if isinstance(raw, dict) else type(raw).__name__)}
    strong = raw.get("strong_adj") if isinstance(raw, dict) else None
    _CACHE.update({"key": key, "adj": adj,
                   "strong": strong if isinstance(strong, dict) else None,
                   "meta": raw})
    return _CACHE, None


def normalize(s: str) -> str:
    """路径/名字 ⇒ 图里的节点名。**已带合法前缀的原样返回**（不二次加前缀）。"""
    s = str(s or "").strip().replace("\\", "/")
    if ":" in s:
        head = s.split(":", 1)[0]
        if head in _KINDS:
            return s
    low = s.lower()
    if low.endswith(_EXT_PAGE):
        return "page:" + s
    if low.endswith(_EXT_CODE):
        return "code:" + s
    if low.endswith(_EXT_DATA):
        return "page:" + s          # 数据/文档件在图里归到 page: 前缀下（与量具同口径）
    return "cap:" + s


def impact(adj: dict, node: str, depth: int) -> set:
    """广度优先取 depth 跳内的全部可达节点（不含自身）。"""
    seen = {node}
    frontier = {node}
    for _ in range(max(0, int(depth))):
        nxt = set()
        for n in frontier:
            for m in adj.get(n, ()):
                if m not in seen:
                    nxt.add(m)
        seen |= nxt
        frontier = nxt
        if not frontier:
            break
    return seen - {node}


def _components(adj: dict) -> dict:
    """连通分量（**无向**口径：出边 ∪ 反向边）。

    留痕（2026-10-19）：第一版只按 adj 的出边数分量，把"只被指向、自己不指向别人"的节点
    算成孤岛，得出的分量数是假的。wiring.json 存的是出边，连通性必须把反向边补进来才算。
    """
    und: dict = {n: set() for n in adj}
    for u, vs in adj.items():
        for v in vs:
            und.setdefault(v, set())
            und[u].add(v)
            und[v].add(u)
    seen = set()
    sizes = []
    for start in und:
        if start in seen:
            continue
        stack = [start]
        seen.add(start)
        n = 0
        while stack:
            cur = stack.pop()
            n += 1
            for nb in und.get(cur, ()):
                if nb not in seen:
                    seen.add(nb)
                    stack.append(nb)
        sizes.append(n)
    sizes.sort(reverse=True)
    incoming_only = len({m for v in adj.values() for m in v} - set(adj))
    return {"nodes_total_undirected": len(und),
            "components": len(sizes),
            "largest": sizes[0] if sizes else 0,
            "largest_share": round((sizes[0] / len(und) * 100), 1) if und else 0.0,
            "incoming_only_nodes": incoming_only}


def _op_status(adj: dict) -> dict:
    st = _WIRING.stat()
    comp = _components(adj)
    kinds: dict = {}
def _op_status(adj: dict, meta: dict | None = None) -> dict:
    meta = meta or {}
    st = _WIRING.stat()
    comp = _components(adj)
    kinds: dict = {}
    for n in adj:
        k = n.split(":", 1)[0] if ":" in n else "(无前缀)"
        kinds[k] = kinds.get(k, 0) + 1
    return {"ok": True, "op": "status",
            "graph": "state/model-pack/wiring.json",
            "builder": meta.get("builder") or "（图里没写 builder —— 可能是旧图，无写手）",
            "nodes": len(adj),
            "edges_directed": sum(len(v) for v in adj.values()),
            "strong_edges": meta.get("strong_edges"),
            "edges_by_kind": meta.get("edges_by_kind"),
            "graph_components": meta.get("components"),
            "built_at": __import__("datetime").datetime.fromtimestamp(st.st_mtime).isoformat(timespec="seconds"),
            "bytes": st.st_size,
            "node_kinds": dict(sorted(kinds.items(), key=lambda kv: -kv[1])),
            **comp}


def _op_impact(state: dict, target=None, targets=None, depth: int = 2) -> dict:
    adj = state["adj"]
    strong = state.get("strong") or {}
    raw = list(targets) if isinstance(targets, (list, tuple)) else ([target] if target else [])
    raw = [str(x) for x in raw if str(x or "").strip()]
    if not raw:
        return {"ok": False, "op": "impact", "error": "missing_param",
                "why": "op=impact 必填 target（或 targets 列表）",
                "how": '{"op":"impact","target":"code:gbt_allinone/api.py","depth":2}'}
    if not isinstance(depth, int) or depth < 1:
        return {"ok": False, "op": "impact", "error": "bad_param",
                "why": "depth 必须是正整数（收到 %r）" % (depth,)}
    if depth > MAX_DEPTH:
        return {"ok": False, "op": "impact", "error": "depth_too_large",
                "why": "depth>%d 等于『什么都能影响』，那张单子没法验 —— 请拆刀口" % MAX_DEPTH,
                "got": depth}

    nodes = [normalize(x) for x in raw]
    missing = [n for n in nodes if n not in adj]
    if len(missing) == len(nodes):
        return {"ok": False, "op": "impact", "error": "not_in_graph",
                "why": "目标全部不在图里（前缀拼错或该件未被索引）—— **不许把空集当『没影响』**",
                "targets": nodes, "graph_nodes": len(adj),
                "hint": "合法前缀: %s ｜ 例: code:gbt_allinone/api.py" % "/".join(_KINDS)}

    hit = [n for n in nodes if n in adj]
    one = set()
    for n in hit:
        one |= impact(adj, n, 1)
    deep = set()
    for n in hit:
        deep |= impact(adj, n, depth)
    deep |= one

    # 强边口径：只算 `path` 引用 + `cap` 真引用 + 绑定账；**不含 cap_mention（页面里"提到"这个名字）**。
    strong_one = set()
    for n in hit:
        strong_one |= impact(strong, n, 1)

    composition = {}
    for x in deep:
        k = x.split(":", 1)[0] if ":" in x else "(无前缀)"
        composition[k] = composition.get(k, 0) + 1
    must_verify = sorted(one)
    return {"ok": True, "op": "impact",
            "targets": hit,
            "missing_targets": missing,
            "depth": depth,
            "impact_nodes": len(deep),
            "composition": dict(sorted(composition.items(), key=lambda kv: -kv[1])),
            "must_verify_1hop": must_verify,
            "must_verify_count": len(must_verify),
            "must_verify_strong_1hop": sorted(strong_one),
            "must_verify_strong_count": len(strong_one),
            "两种口径": {
                "全边": "含 cap_mention（某页/某文档只是**提到**这个能力名）—— 影响'谁会被波及'，宁可宽",
                "强边": "只含 path 引用 + cap 真引用(`cap x` / `run_task(\"x\")` / `\"kind\": \"x\"` / "
                        "`kind = \"x\"`) + 绑定账 —— 回答'谁的代码真的依赖它'",
                "已知口径": "`if kind == \"x\":` 这种**分派比较**由 wiring-build 自己补边（kind=dispatch）——"
                            "补前 api.py 强边只有 67，补后 400/400 全是强边。补边只读 code: 件，单件 ≤2MB",
            },
            "verdict": ("刀口宽：全边 1 跳 %d 个，其中真依赖 %d 个" % (len(must_verify), len(strong_one)))
                       if must_verify else "1 跳无邻居（孤立件）—— 空单子不等于安全，先确认它该不该有边"}


def _op_risky(state: dict, n: int = 8, kind: str = "") -> dict:
    adj = state["adj"]
    strong = state.get("strong") or {}
    try:
        n = int(n)
    except (TypeError, ValueError):
        return {"ok": False, "op": "risky", "error": "bad_param", "why": "n 必须是整数（收到 %r）" % (n,)}
    n = max(1, min(n, 50))
    prefix = (kind or "").strip()
    rows = []
    for node in adj:
        if prefix:
            if not node.startswith(prefix if prefix.endswith(":") else prefix + ":"):
                continue
        elif not node.startswith(("code:", "cap:")):
            continue
        nb = impact(adj, node, 1)
        sb = impact(strong, node, 1) if strong else set()
        files = sum(1 for x in nb if x.startswith(("code:", "page:")))
        caps = sum(1 for x in nb if x.startswith("cap:"))
        rows.append({"node": node, "strong": len(sb), "total": len(nb),
                     "files": files, "caps": caps})
    # 2026-10-19 改口径：**按强边排**。原先把 cap_mention 也算进去，榜首永远是
    # 「cap:create 2619」这种"被提到最多"的位，不是"真被依赖"的位 —— 那是错尺（P1）。
    rows.sort(key=lambda r: (-r["strong"], -r["total"], r["node"]))
    return {"ok": True, "op": "risky", "n": n,
            "ranking": "**强边** 1 跳邻居数降序（真实依赖；同分看全边数）",
            "total_rank_kept": True,
            "caveat": "强边 = path 引用 + cap 真引用 + **分派比较(kind==/kind in/run_task)** + 绑定账，"
                      "**不含 cap_mention**（页面只是提到名字）。分派边由 wiring-build 自己补（repo-pack "
                      "的正则不认 `if kind == \"x\":`）—— 补前 api.py 强边 67，补后 400。",
            "top": rows[:n],
            "scanned": len(rows)}


def _op_where() -> dict:
    return {"ok": True, "op": "where",
            "module": "gbt_allinone/tools/impact_check.py",
            "graph": "state/model-pack/wiring.json",
            "builder": "tools/codex-scripts/repo-pack.py（pack 时产出 wiring.json）",
            "scratch_twin": ".scratch/impact-check.py（同一套逻辑的早期脚本，保留作对照）",
            "cli": 'py -3.14 tools/codex-scripts/five-dim.py cap impact_check '
                   '\'{"op":"impact","target":"code:gbt_allinone/api.py"}\' --stdin'}


def run_op(op: str = "status", **params) -> dict:
    """统一入口（api.py 分派到这里）。未知 op ⇒ 带原因拒绝，不静默回落。"""
    op = str(op or "status").strip() or "status"
    if op not in OPS:
        return {"ok": False, "error": "unknown_op", "op": op, "ops": list(OPS),
                "why": "impact_check 没有这个 op —— 拒绝而不是悄悄当 status"}
    if op == "where":
        return _op_where()
    state, err = _load()
    if state is None:
        return {"ok": False, "op": op, "error": err.get("error", "load_failed"),
                "why": err.get("why", "")}
    if op == "status":
        return _op_status(state["adj"], state.get("meta") or {})
    if op == "impact":
        return _op_impact(state, target=params.get("target"),
                          targets=params.get("targets"), depth=params.get("depth", 2))
    return _op_risky(state, n=params.get("n", 8), kind=params.get("kind", ""))


def main(argv=None) -> int:
    import argparse
    ap = argparse.ArgumentParser(description="影响面检查（impact_check）")
    ap.add_argument("op", nargs="?", default="status", choices=list(OPS))
    ap.add_argument("--target", default=None)
    ap.add_argument("--depth", type=int, default=2)
    ap.add_argument("--n", type=int, default=8)
    ap.add_argument("--kind", default="")
    a = ap.parse_args(argv)
    out = run_op(a.op, target=a.target, depth=a.depth, n=a.n, kind=a.kind)
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0 if out.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
