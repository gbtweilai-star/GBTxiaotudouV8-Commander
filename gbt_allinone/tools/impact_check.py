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
现读规模一律以 `op=status` 为准（**本位不抄数字** —— 抄一次就过期一次：
2026-11-05 这行还写着 6301 节点，实际已是 6306，图重建三次它错了三次）。

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
2. **`depth` 超过 3 ⇒ 拒**：全图规模见 `op=status`，深度一涨就等于"什么都能影响"，那张单子没法验。
3. **本位只报影响面，不代跑验证**：验证要由调用方拿着 1 跳清单逐个真跑（走动的是
   `tentacle_arm move` / 各判据）。本位把"调了"当"到了"是另一种假绿。
"""
from __future__ import annotations

import json
import os
import re
import sys
import time
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    if hasattr(_s, "reconfigure"):
        _s.reconfigure(encoding="utf-8", errors="replace")

OPS = ("status", "impact", "risky", "where", "recent")
MAX_DEPTH = 3
_ROOT = Path(__file__).resolve().parents[2]
_WIRING = _ROOT / "state" / "model-pack" / "wiring.json"
_KINDS = ("page", "code", "cap", "tent", "carrier", "handler")
# ⚠️ 这两组扩展名**必须与 tools/codex-scripts/wiring-build.py:52-53 一字不差**。
#   图里的节点名是那份脚本产出的；我这边若换成另一套口径，就会「路径判错前缀
#   ⇒ in_graph 恒 false ⇒ 影响面恒 0」。2026-11-04 实测踩到：改 .txt / .png / .toml
#   全报"0 处受影响"，而图里明明有对应节点 —— 那不是"很安全"，是量具坏了。
#   对拍：gbt_allinone.tests.test_impact_node_prefix（改这里它就红）。
_EXT_CODE = (".py", ".js", ".mjs", ".cjs", ".ts", ".tsx", ".jsx", ".sh", ".ps1", ".cmd", ".bat")
_EXT_PAGE = (".html", ".htm", ".md", ".txt", ".json", ".jsonl", ".csv", ".svg", ".css", ".yml", ".yaml")
# 兜底判据：文件名末尾带扩展名 ⇒ 它是「文件」，不是「能力位」
_FILEISH_RE = re.compile(r"\.[a-z0-9]{1,8}$")

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
    """路径/名字 ⇒ 图里的节点名。**已带合法前缀的原样返回**（不二次加前缀）。

    兜底口径与 wiring-build 对齐：
      · 有扩展名且不在两组里 ⇒ ``code:``（未知后缀按代码件，与 builder 一致）
      · 没有扩展名 ⇒ ``cap:``（传进来的是能力位名，如 omni_plug / route_ledger）
    """
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
    # 🔴 2026-11-04 修：原先这里无条件 `return "cap:" + s`，把 .txt / .png / .toml
    #   这些文件全塞进"能力位"命名空间，而图里它们是 code:/page: —— 两边对不上，
    #   in_graph 恒 false、影响面恒 0。对"改一处看一圈"来说，这就是把量具读数抹平。
    if _FILEISH_RE.search(low.rsplit("/", 1)[-1]):
        return "code:" + s
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

    # 强边口径（v4）：`path` 引用 + `cap` 真引用 + **分派比较(kind==/kind in/run_task)**
    #   + **import AST** + **impl 实现映射** + 绑定账；**不含 cap_mention（页面里"提到"这个名字）**。
    #   与 `op=risky` 的 caveat、本函数 return 里的「两种口径」是同一口径 —— 三处必须同步改，
    #   否则文本自相矛盾（2026-11-05 就因为只改了两处、还把一处写坏，整个位 import 不了）。
    strong_one = set()
    for n in hit:
        strong_one |= impact(strong, n, 1)

    composition = {}
    for x in deep:
        k = x.split(":", 1)[0] if ":" in x else "(无前缀)"
        composition[k] = composition.get(k, 0) + 1
    # `must_verify_1hop` **故意不排除副本**（2026-11-05 取证结案，别再改）：
    # 消费方 `tools/codex-scripts/impact.py:121` 打印的就是「改完必须逐一验证」的清单，
    # 副本也真的要跟 —— 排除掉就等于漏验。
    #
    # 这和 `risky` 不同，因为**两个 op 回答的不是同一个问题**：
    #   · `risky`       = 改哪最危险 → 副本/派生物是噪音（单列 copies / derived）
    #   · `must_verify` = 改完要验谁 → 副本是要验的实体（留着，一个都不能少）
    # 用途不同就不该硬拉齐口径。
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
                "强边": "含 path 引用 + cap 真引用（`cap x` / `run_task(\"x\")` / `\"kind\": \"x\"` / `kind = \"x\"`）"
                        " + **分派比较(kind==/kind in/run_task)** + **import AST** + **impl 实现映射** + 绑定账"
                        " —— 回答'谁的代码真的依赖它'。v4 口径，与 `op=risky` 的 caveat 逐字对齐",
                "已知口径": "`if kind == \"x\":` 这种**分派比较**由 wiring-build 自己补边（kind=dispatch）——"
                            "补前 api.py 强边 67（历史值，不会再变）；**补后多少看 `op=status` 的 strong_edges**"
                            " —— 本处不预存，图每重建一次它就变（2026-11-05 这行原写 400/400，"
                            "加完 import/impl 两层后已是 930，错了三次）。补边只读 code: 件，单件 ≤2MB",
            },
            "verdict": ("刀口宽：全边 1 跳 %d 个，其中真依赖 %d 个" % (len(must_verify), len(strong_one)))
                       if must_verify else "1 跳无邻居（孤立件）—— 空单子不等于安全，先确认它该不该有边"}


def _is_copy(node: str) -> bool:
    """这个节点是不是**历史副本**（镜像 / 备份 / 归档），而不是代码本体。

    来历（2026-11-05）：口径收紧到"按强边排"之后，`risky` 榜首正确变成
    `code:gbt_allinone/api.py`（强边 930），但 Top15 里紧跟着 8 个是
    `state/mirror/stage/…/security/policy.py`、`state/atomic-sync/backup/…/api.py`
    —— 同一个文件的历史快照。它们会跟着主件一起出现在每次影响面里，
    **噪音盖过信号**，「最危险」变成「最吵」。

    副本不是不重要：改主件后镜像要跟。但它不该和本体抢同一张榜，
    所以 `risky` 单列 `copies`，`top` 只放本体。
    """
    p = node[5:] if node.startswith("code:") else node
    return any(s in p for s in (
        "state/mirror/",
        "state/atomic-sync/backup/",
        ".archive/",
        "/backup/",
        "/stage/",
    ))



# 派生物：由脚本生成、改它会被覆盖 —— 和副本一样不该跟源码抢榜位，但成因不同。
# 判据用**文件头标记**（生成器自己写的那行），不用路径白名单：路径会变，标记不会。
_DERIVED_DIRS = ("state/", "data/", "outputs/", "docs/")
_DERIVED_EXT = (".js", ".json", ".md", ".css", ".html", ".svg", ".txt", ".csv", ".tsv")
_DERIVED_MARKS = ("自动生成", "勿手改", "auto-generated", "autogenerated",
                  "DO NOT EDIT", "generated by", "由脚本生成")


def _is_derived(node: str) -> bool:
    """这个节点是**派生物**（脚本生成、改了会被覆盖），而不是手写源码。

    来历（2026-11-05）：口径收紧后 `risky` 榜第二是 `code:state/console-data.js`
    （强边 777），可它是 `tools/gen-console-data.py` 的产物，文件头明写
    「自动生成，勿手改」。谁照着榜单去"修最危险的件"，改的就是它 ——
    白改，下次跑生成器就没了。

    和 `_is_copy` 是**同类干扰、不同成因**：副本是同一份文件的历史快照
    （改主件后镜像要跟）；派生物是源码的产物（改源码后要重跑生成器）。
    两者都不该和源码混在一张榜里，所以分别单列、不合并。

    先过路径/扩展名两道闸再读盘 —— 全图 2900 个 code 节点里只有 2 个候选
    （`state/console-data.js` 与 mirror 下那份 `gsap.min.js`），代价约等于零。
    """
    if not node.startswith("code:"):
        return False
    p = node[5:]
    if not p.startswith(_DERIVED_DIRS) or not p.endswith(_DERIVED_EXT):
        return False
    try:
        with open(p, encoding="utf-8", errors="replace") as fh:
            head = fh.read(300)
    except OSError:
        return False
    return any(m in head for m in _DERIVED_MARKS)


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
                     "files": files, "caps": caps, "copy": _is_copy(node),
                     "derived": _is_derived(node)})
    # 2026-10-19 改口径：**按强边排**。原先把 cap_mention 也算进去，榜首永远是
    # 「cap:create 2619」这种"被提到最多"的位，不是"真被依赖"的位 —— 那是错尺（P1）。
    #
    # 2026-11-05 再改：**副本不与本体抢榜位**。口径收紧后榜首果然变成 api.py（强边 930），
    # 但紧接着 Top15 里 8 个是 `state/mirror/stage/…/security/policy.py`、
    # `state/atomic-sync/backup/…/api.py` 这类历史副本 —— 改主件时监控会同时报一堆副本，
    # **噪音盖过信号**，「最危险」变成「最吵」。副本不是不重要（主件改了镜像要跟），
    # 但它不该和本体混在一张榜里，所以单列 `copies`。
    rows.sort(key=lambda r: (-r["strong"], -r["total"], r["copy"],
                          r["derived"], r["node"]))
    # 副本（历史快照）与派生物（生成产物）分开单列：两者都不该跟源码抢榜位，
    # 但**跟进动作不同** —— 改主件后副本要跟、派生物要重跑生成器。
    main = [r for r in rows if not r["copy"] and not r["derived"]]
    copies = [r for r in rows if r["copy"]]
    derived = [r for r in rows if r["derived"] and not r["copy"]]
    return {"ok": True, "op": "risky", "n": n,
            "ranking": "**强边** 1 跳邻居数降序（真实依赖；同分看全边数；**副本与派生物单列**）",
            "total_rank_kept": True,
            "caveat": "强边 = path 引用 + cap 真引用 + **分派比较(kind==/kind in/run_task)** + "
                      "**import AST** + **impl 实现映射** + 绑定账，**不含 cap_mention**"
                      "（页面只是提到名字）。分派边由 wiring-build 自己补（repo-pack "
                      "的正则不认 `if kind == \"x\":`）—— 补前 api.py 强边 67（历史值）；**补后多少看 `op=status` 的 strong_edges**，此处不预存。"
                      "`top` 只含**本体**（不含 state/mirror、state/atomic-sync/backup、"
                      ".archive 下的副本）；副本在 `copies` 里单列，别把它当独立风险件。"
                      "派生物（自动生成、勿手改的产物）在 `derived` 里单列 —— "
                      "**改它没有用，要改生成它的脚本再重跑**。",
            "top": main[:n],
            "copies": copies[:max(3, n // 5)],
            "derived": derived[:max(3, n // 5)],
            "main_scanned": len(main),
            "copies_scanned": len(copies),
            "derived_scanned": len(derived),
            "scanned": len(rows)}


def _peek_builder() -> str:
    """只读文件头 4 KB 取 `builder` 字段。

    `where` 是"我在哪、我是什么"的自述，**不该为此加载 9.3 MB 图** ——
    所以不走 `_load()`，直接读文件头（payload 里 builder 在 adj 之前，落在前 ~2 KB）。
    找不到就退回写死的正确值，宁可写死也不报错。
    """
    try:
        with open(_WIRING, "rb") as fh:
            head = fh.read(4096).decode("utf-8", "replace")
        m = re.search(r'"builder"\s*:\s*"([^"]{1,200})"', head)
        if m:
            return m.group(1)
    except OSError:
        pass
    return "tools/codex-scripts/wiring-build.py"


def _op_where() -> dict:
    # 修正（2026-11-04）：此处曾自称 builder 是 `repo-pack.py（pack 时产出 wiring.json）`，
    # **是错的** —— repo-pack 只产 `outputs/repo-pack/edges.jsonl`（原始边表），
    # 真正写 `state/model-pack/wiring.json` 的是 `tools/codex-scripts/wiring-build.py`。
    # 现在从图文件里读，不再写死，免得再漂。
    return {"ok": True, "op": "where",
            "module": "gbt_allinone/tools/impact_check.py",
            "graph": "state/model-pack/wiring.json",
            "builder": _peek_builder(),
            "source_edges": "outputs/repo-pack/edges.jsonl（由 repo-pack.py refs 产出）",
            "scratch_twin": ".scratch/impact-check.py（同一套逻辑的早期脚本，保留作对照）",
            "cli": 'py -3.14 tools/codex-scripts/five-dim.py cap impact_check '
                   '\'{"op":"impact","target":"code:gbt_allinone/api.py"}\' --stdin'}


def _to_node(target: str) -> str:
    """万能插留痕里的**绝对路径** ⇒ 图里的节点名（去 payload 前缀再 normalize）。

    ⚠️ 2026-11-04 实测踩到的坑：target 经过 JSON 转义后可能是 `C:\\Users\\...`
    （字面双反斜杠），直接 `replace("\\\\", "/")` 会得到 `C://Users//...`，
    与图节点永远对不上 ⇒ in_graph 恒 false、impact_count 恒 0。
    所以先折叠多重反斜杠，再把重复斜杠压成单个，最后才比前缀。
    """
    s = str(target or "")
    while "\\\\" in s:
        s = s.replace("\\\\", "\\")
    s = s.replace("\\", "/")
    while "//" in s:
        s = s.replace("//", "/")
    root = str(_ROOT).replace("\\", "/")
    while "//" in root:
        root = root.replace("//", "/")
    root = root.rstrip("/")
    if s.lower().startswith(root.lower()):
        s = s[len(root):].lstrip("/")
    return normalize(s)


def _ledger_path() -> Path:
    """留痕路径（读写两侧共用一套解析）。

    🔴 2026-11-04 补 `GBT_IMPACT_LEDGER` 覆盖：
    `state/*/` 被 .gitignore 忽略，但**判据跑起来照样往生产留痕里写**。
    实测那一天：`state/omni-impact.jsonl` 133 行里大半是跑测试造出来的
    （`__绝对不存在的插座__`、连发三条 `status`）—— 真实动作被噪音淹掉，
    读 `recent` 的人根本分不清哪条是人干的。

    所以测试必须设 `GBT_IMPACT_LEDGER` 指到临时文件。
    读写两侧都走这个函数，否则会出现「一个写 A、一个写 B」。
    """
    env = (os.environ.get("GBT_IMPACT_LEDGER") or "").strip()
    if env:
        return Path(env)
    return _ROOT / "state" / "omni-impact.jsonl"


def _say(op: str, out: dict, t0: float, **kw) -> None:
    """**多域监控自己的留痕**（2026-11-04 补）。

    血账：本位 `OPS` 里从来没有"写"这件事 —— 写侧只有 `omni_plug._sync_impact`。
    于是**监控查过什么、什么时候查的，一条都不记**；`recent` 里全是万能插的动作。
    主人当场问「我怎么感觉你多域监控没开」—— **他的感觉是对的**：
    一个只读、不留痕的监控，从外部**看不出它在跑**。

    留痕原则（别让它自己变成新故障点）：
      · 只记 `impact` / `risky` 这类**真算过影响面**的 op。
        `status` / `where` / `recent` 是纯读，记了只会往流水里灌噪音。
      · 只追加一行 + fsync，**不加载图** —— 图 10.7 MB，
        每次查询都读它就等于把监控变成新的卡点（这正是原设计把写侧拆出去的初衷）。
      · 失败**绝不**挡主流程，但必须 stderr 留痕（静默失败是本仓最恨的一种）。
    """
    try:
        row = {
            "ts": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "action": "impact",              # 读侧字段：与万能插的动作区分开
            "op": op,
            "who": "impact_check",           # 谁记的（读文件时一眼能分清）
            "target": str(kw.get("target") or kw.get("targets") or "")[:300],
            "depth": kw.get("depth"),
            "ok": bool(out.get("ok")),
            "error": (str(out.get("error") or "")[:200] or None),
            "ms": int((time.time() - t0) * 1000),
            "impact_nodes": out.get("impact_nodes"),
        }
        p = _ledger_path()
        p.parent.mkdir(parents=True, exist_ok=True)
        with p.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")
            fh.flush()
            os.fsync(fh.fileno())
    except Exception as e:                                        # noqa: BLE001
        try:
            print("[impact_check] 留痕失败：%s: %s" % (type(e).__name__, str(e)[:120]),
                  file=sys.stderr)
        except Exception:                                         # noqa: BLE001
            pass


def _op_recent(state: dict, n: int = 10) -> dict:
    """**万能插 × 多域监控的读取口**：最近万能插动作，以及各自会撞到谁。

    主人令 2026-11-04「多域监控必须和万能插同步执行」的落实：
      · 写侧（omni_plug._sync_impact）只追加一行，**不加载图**；
      · 读侧（这里）才拿邻接图算受影响面。
    这样执行永远不被 4.3MB 的图拖慢 —— 否则监控自己就成了新的故障点。
    """
    n = max(1, min(int(n or 10), 100))
    p = _ledger_path()
    if not p.is_file():
        return {"ok": True, "op": "recent", "count": 0,
                "why": "还没有万能插动作留痕（state/omni-impact.jsonl 不存在）"}
    rows = []
    try:
        with p.open(encoding="utf-8") as f:
            for ln in f:
                ln = ln.strip()
                if not ln:
                    continue
                try:
                    rows.append(json.loads(ln))
                except Exception:                                  # noqa: BLE001
                    continue
    except Exception as exc:                                       # noqa: BLE001
        return {"ok": False, "op": "recent",
                "error": "%s: %s" % (type(exc).__name__, str(exc)[:120])}

    adj = state.get("adj") or {}
    # 2026-11-06：修复前的万能插把 `op=status` 也写成空 target 行。读侧过滤，
    # 不改写历史（原流水仍是证据），但 `recent` 只展示真动作/真检查。
    def _empty_read(r):
        act = str(r.get("action") or r.get("op") or "").strip().lower()
        return (act in ("status", "where", "recent")
                and not str(r.get("target") or "").strip()
                and not str(r.get("socket") or "").strip())
    rows = [r for r in rows if not _empty_read(r)]
    out = []
    for r in reversed(rows[-n:]):
        node = _to_node(r.get("target") or "")
        in_graph = node in adj
        reach = sorted(impact(adj, node, 2)) if in_graph else []
        out.append({"ts": r.get("ts"), "socket": r.get("socket"),
                    "action": r.get("action") or r.get("op"),
                    "ok": r.get("ok"),
                    "error": r.get("error"),
                    "ms": r.get("ms"), "target": r.get("target"),
                    "node": node, "in_graph": in_graph,
                    "impact_count": len(reach), "impact_sample": reach[:8],
                    "reason": r.get("reason")})
    return {"ok": True, "op": "recent", "count": len(out),
            "graph_nodes": len(adj),
            "note": "impact_count = 这一刀 2 跳内可达的节点数；0 且 in_graph=false 说明该目标不在图里（新文件/非仓库件）",
            "rows": out}


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
    if op == "recent":
        return _op_recent(state, n=params.get("n", 10))
    if op == "impact":
        # 🔴 用 `time.time()` 而不是 `perf_counter()`：`_say` 里算的是
        # `time.time() - t0`，两者基线不同会得出天文数字（实测 `ms: 1793770680699`）。
        # 要换就两处一起换 —— 这也正是"两个时钟混用"的经典形态。
        _t0 = time.time()
        _out = _op_impact(state, target=params.get("target"),
                          targets=params.get("targets"), depth=params.get("depth", 2))
        # 只给"真算过影响面"的 op 留痕（status/where/recent 是纯读，记了只有噪音）
        _say("impact", _out, _t0, target=params.get("target"),
             targets=params.get("targets"), depth=params.get("depth", 2))
        return _out
    if op == "risky":
        _t0 = time.time()
        _out = _op_risky(state, n=params.get("n", 8), kind=params.get("kind", ""))
        _say("risky", _out, _t0, target=params.get("kind") or "")
        return _out
    # 🔴 2026-11-05 修（AST 对账查出来的）：原来这最后一段**就是兜底**，直接返回 risky。
    #   后果：OPS 里以后新增一个 op 却忘了写分支，它会**静默变成 risky** ——
    #   返回值结构看着正常、口径全错，而且没有任何报错。这比崩掉难查得多。
    #   现在显式收口：走到这里说明「OPS 声明了但没实现」，如实拒绝。
    return {"ok": False, "op": op, "error": "op_in_OPS_but_no_branch",
            "why": "OPS 声明了这个 op 却没有实现分支 —— 拒绝，而不是悄悄当 risky"}


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
