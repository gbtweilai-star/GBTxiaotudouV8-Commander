# gbt-capability: flow_canvas
# ⛔ 开发者：自由的风 · 永久钢印 · 禁止删除
"""工作流画布：**图 → 自包含 SVG 画布页**（蒸馏自 Langflow，只取"看得见"这一面）。

## 抓取口径（本仓规矩：凡抓取必写源·时间·口径）
· **源**：2026-09-28 主人给的周榜卡 `Langflow`（155.3k★ · Python）的公开一句话介绍：
  「拖拖拽拽就把大模型、工具、分支连成应用，不用写代码也能搭出能跑的 AI 工作流（可视化/LLM 应用）」。
  —— 一手仓库与文档本轮**未联网核验**（主人令：不出网花钱的动作），所以只蒸馏**可视化架构**，
  不引用它的拖拽编辑器/组件实现/代码。
· **时间**：2026-09-28。
· **口径**：图数据只走**引擎正规出口**（`engine.list_workflows()` / `state/dag_runs.jsonl`），
  **不偷读** `store/workflows.json`（绕过能力层，口径就散了）；本件**只画不跑**——
  执行仍走 `wf_run`/`dagrun` 的门，本件不执行任何工作流。

## 蒸馏判断：Langflow 的核里我们真缺哪块
| Langflow 的能力 | 我们已有的对位 | 结论 |
|---|---|---|
| 拖拽编辑器（前端交互） | console 工作台页面体系 | **不重造**（那是 UI 工程，不是能力核） |
| 工作流→图的**正规数据出口** | `engine.list_workflows()`（R-H99b 正规出口） | **已有数据，缺"画出来"** |
| 能跑的工作流 | `wf_run` / `dagrun`（走门） | **已有，不重造** |
| 自包含画布页（离线可开） | 无 | **补这块（本件）** |

## 硬规矩
1. **零外链零脚本**：画布页自包含（内联 SVG），离线可开、可审计；不引任何 http(s) 资源。
2. **只画不跑**：本件只读引擎正规出口 + dag 账，渲染成图；执行仍走 `wf_run`/`dagrun` 的门。
3. **写盘只写画布**：产物落 `outputs/flow-canvas/`（产物区），不碰页面登记面
   （console 页账的口径是 holo_pet/assets/*/index.html + 仓根 *.html，不掺花）。
"""
from __future__ import annotations

import json
import time
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
_DAG = _ROOT / "state" / "dag_runs.jsonl"                      # dagrun 运行账（正规账本）
_OUT = _ROOT / "outputs" / "flow-canvas"                        # 画布产物区（产物区，不掺页面登记面）


def from_wf(name: str = "", **_kw) -> dict:
    """工作流定义 → 图。数据走引擎正规出口 `engine.list_workflows()`（不偷读 store）。"""
    from .. import engine as _eng
    r = _eng.list_workflows()
    wfs = r.get("workflows") or []
    if name:
        wfs = [w for w in wfs if w.get("name") == name]
        if not wfs:
            return {"ok": False, "fail_closed": True,
                    "error": "没有这个工作流：%s（现读 %d 个）" % (name, r.get("count"))}
    graphs = []
    for w in wfs:
        nodes = [{"id": n.get("id"), "label": n.get("id"), "kind": n.get("kind"),
                  "fallback": bool(n.get("has_fallback")), "routes": n.get("routes") or 0}
                 for n in (w.get("nodes") or [])]
        edges = [{"from": d, "to": n.get("id")}
                 for n in (w.get("nodes") or []) for d in (n.get("depends_on") or [])]
        graphs.append({"name": w.get("name"), "nodes": nodes, "edges": edges,
                       "node_count": len(nodes), "edge_count": len(edges)})
    return {"ok": True, "op": "from_wf", "graphs": graphs, "count": len(graphs)}


def from_dag(limit: int = 5, **_kw) -> dict:
    """dag 运行账 → 图（每次 run 一个节点，带 done/failed 读数）。"""
    if not _DAG.is_file():
        return {"ok": True, "op": "from_dag", "graphs": [], "count": 0,
                "note": "还没有 dag 运行记录（不编）"}
    rows = []
    for ln in _DAG.read_text(encoding="utf-8", errors="replace").splitlines()[-int(limit):]:
        ln = ln.strip()
        if not ln:
            continue
        try:
            rows.append(json.loads(ln))
        except json.JSONDecodeError:
            continue
    nodes, edges = [], []
    for r in rows:
        rid = str(r.get("dag") or "?")
        nodes.append({"id": rid, "label": "dag %s" % rid[:12], "kind": "dag_run",
                      "done": r.get("done"), "failed": len(r.get("failed") or [])})
        for f in (r.get("failed") or []):
            edges.append({"from": rid, "to": "fail:%s" % f})
            nodes.append({"id": "fail:%s" % f, "label": "失败 %s" % f, "kind": "failed_node"})
    return {"ok": True, "op": "from_dag",
            "graphs": [{"name": "dag_runs", "nodes": nodes, "edges": edges}], "count": 1}


def _svg(graph: dict) -> str:
    """图 → 内联 SVG（分层布局：按依赖深度排 x，按序排 y）。零外链、零脚本。"""
    nodes, edges = graph.get("nodes") or [], graph.get("edges") or []
    depth = {n["id"]: 0 for n in nodes}
    for _ in range(len(nodes) + 1):                    # 迭代定深（有环就停在原地，不炸）
        changed = False
        for e in edges:
            a, b = e.get("from"), e.get("to")
            if a in depth and b in depth and depth[b] < depth[a] + 1:
                depth[b] = depth[a] + 1
                changed = True
        if not changed:
            break
    by_d: dict = {}
    for n in nodes:
        by_d.setdefault(depth.get(n["id"], 0), []).append(n)
    W = max(320, 220 * (max(by_d, default=0) + 1) + 80)
    H = max(160, 90 * max((len(v) for v in by_d.values()), default=1) + 60)
    pos = {}
    for d in sorted(by_d):
        for i, n in enumerate(by_d[d]):
            pos[n["id"]] = (40 + d * 220, 40 + i * 90)
    parts = ['<svg xmlns="http://www.w3.org/2000/svg" width="%d" height="%d" '
             'viewBox="0 0 %d %d" font-family="sans-serif">' % (W, H, W, H)]
    for e in edges:
        a, b = pos.get(e.get("from")), pos.get(e.get("to"))
        if a and b:
            parts.append('<line x1="%d" y1="%d" x2="%d" y2="%d" stroke="#7C4DFF" stroke-width="2"/>'
                         % (a[0] + 130, a[1] + 22, b[0], b[1] + 22))
    for n in nodes:
        x, y = pos.get(n["id"], (40, 40))
        color = "#F5B041" if n.get("kind") == "failed_node" else "#00E5FF"
        label = str(n.get("label"))[:16]
        sub = ("done=%s failed=%s" % (n.get("done"), n.get("failed"))
               ) if n.get("kind") == "dag_run" else str(n.get("kind") or "")
        parts.append('<rect x="%d" y="%d" width="130" height="44" rx="8" fill="#141428" '
                     'stroke="%s" stroke-width="2"/>' % (x, y, color))
        parts.append('<text x="%d" y="%d" fill="#EDEDF5" font-size="12">%s</text>'
                     % (x + 8, y + 19, label))
        parts.append('<text x="%d" y="%d" fill="#8A8AA3" font-size="10">%s</text>'
                     % (x + 8, y + 35, sub[:24]))
    parts.append('</svg>')
    return "".join(parts)


def render(source: str = "wf", name: str = "", limit: int = 5, **_kw) -> dict:
    """图 → 自包含画布页（零外链零脚本，离线可开），落 `outputs/flow-canvas/index.html`。**只画不跑**。"""
    g = from_dag(limit) if source == "dag" else from_wf(name)
    if not g.get("ok"):
        return g
    blocks = ['<h1>GBT 工作流画布</h1>',
              '<p class="src">源：engine.list_workflows() / state/dag_runs.jsonl · 生成于 %s · '
              '本页零外链零脚本（离线可开）· 只画不跑（执行走 wf_run/dagrun 的门）</p>'
              % time.strftime("%Y-%m-%d %H:%M")]
    for gr in (g.get("graphs") or []):
        blocks.append('<h2>%s</h2>%s' % (gr.get("name"), _svg(gr)))
    html = ("<!doctype html><html><head><meta charset='utf-8'>"
            "<title>GBT 工作流画布</title><style>"
            "body{background:#0B0B14;color:#EDEDF5;font-family:sans-serif;margin:24px}"
            "h1{color:#F5B041}h2{color:#00E5FF;margin-top:28px}"
            ".src{color:#8A8AA3;font-size:12px}</style></head><body>%s</body></html>"
            % "".join(blocks))
    _OUT.mkdir(parents=True, exist_ok=True)
    page = _OUT / "index.html"
    page.write_text(html, encoding="utf-8")
    return {"ok": True, "op": "render", "source": g.get("op"),
            "graphs": len(g.get("graphs") or []),
            "page": str(page.relative_to(_ROOT)), "bytes": page.stat().st_size,
            "口径": "零外链零脚本（离线可开）· 只画不跑（执行走 wf_run/dagrun 的门）"}


def where(**_kw) -> dict:
    return {"ok": True, "op": "where", "kind": "flow_canvas", "tentacle": "flow_canvas",
            "entry": "run_task('flow_canvas', {...})",
            "ops": ["from_wf", "from_dag", "render", "where"],
            "distilled_from": "2026-09-28 主人给的周榜卡 Langflow（155.3k★ · Python）——只取可视化架构",
            "not_copied": "不引它的拖拽编辑器/组件实现；图数据只走引擎正规出口"
                          "（engine.list_workflows / dag_runs.jsonl），执行仍走 wf_run/dagrun 的门"
                          "——本件只做『看得见』",
            "hard_rules": ["零外链零脚本（画布页离线可开、可审计）",
                           "只画不跑：不执行任何工作流",
                           "产物只落 outputs/flow-canvas/（不掺页面登记面）"],
            "files": {"画布产物": str(_OUT.relative_to(_ROOT)), "dag 账": str(_DAG.relative_to(_ROOT))},
            "contract": [
                {"op": "from_wf", "params": "[name]", "returns": "工作流图（nodes/edges）"},
                {"op": "from_dag", "params": "[limit]", "returns": "dag 运行图（带 done/failed）"},
                {"op": "render", "params": "source=wf|dag [name limit]", "returns": "画布页 + graph"},
            ]}


def run_op(op: str = "from_wf", **params) -> dict:
    op = (op or "from_wf").lower()
    for name, fn in (("from_wf", from_wf), ("from_dag", from_dag), ("render", render),
                     ("where", where)):
        if op == name:
            return fn(**params)
    return {"ok": False, "fail_closed": True,
            "error": f"未知 op:{op}（from_wf/from_dag/render/where）"}


if __name__ == "__main__":                                    # 主人的终端入口
    import argparse
    ap = argparse.ArgumentParser(description="工作流画布（Langflow 架构蒸馏 · 只画不跑）")
    ap.add_argument("cmd", nargs="?", default="render")
    ap.add_argument("--source", default="wf")
    ap.add_argument("--name", default="")
    a = ap.parse_args()
    if a.cmd == "render":
        print(json.dumps(run_op("render", source=a.source, name=a.name),
                         ensure_ascii=False, indent=1))
    else:
        print(json.dumps(run_op(a.cmd), ensure_ascii=False, indent=1))
