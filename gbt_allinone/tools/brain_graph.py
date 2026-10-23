# -*- coding: utf-8 -*-
"""GBT小土豆V8 · 大脑执行层 —— 排布图与连接网络的**数据层**

Owner 2026-09-22：「我要的是那种**逼真和真实执行的感觉**」
Owner 2026-09-22：「整个大脑执行层排布图和连接网络都要可视化呈现出来」

═══ 为什么这个文件只出数据、不出画面 ═══
"逼真"的唯一来源是**数据是真的**。所以本模块的铁律是：
  **图上的每一个节点、每一条边，都必须能在源码/磁盘上指出处；指不出的，不画。**
图上一根线 = 对代码的一处断言。硬编码的图明天就会骗人。

═══ 结构从哪算（全部实测，不猜）═══
  五维   ← `gbt_allinone/brain_exec.py` 的 **AST**（真读函数名，不是抄注释）
  能力   ← `gbt_allinone/caps_registry.py` 的 BENIGN_CAPS（按 handler 对齐）
  底座   ← 磁盘上真实存在的模块文件（带体积）
  边     ← `brain_exec.py` 里 **AST 查到的真实函数调用** + `api.py` 的真实路由

═══ 状态从哪来（"真实执行的感觉"的燃料）═══
  `gbt_allinone/store/audit.jsonl` —— 每次调用都真落一行：
      {"ts":…, "iso":…, "event":"ok|error|denied|…", "meta":{"kind":"…"}}
  实测 294,679 行 / 35 MB。**只追加** ⇒ 可 tail ⇒ 可真·实时。
"""
from __future__ import annotations

import ast
import json
import time
from pathlib import Path

_BASE = Path(__file__).resolve().parent.parent      # gbt_allinone/
_IMPL_VERSION = "1.1"

# 「进了超时还没出」判为**卡**的阈值（秒）。取 20s：正常维调用是毫秒~秒级，
# 超过 20 秒还没落 exit，基本就是真卡住了。宁可判晚一点，也不误报。
_STUCK_S = 20.0

# 五维的中文名（纯粹是显示层，改它不影响任何判定）
_DIM_CN = {
    "route":   ("路由维", "意图 → 能力动态路由"),
    "execute": ("执行维", "单能力直调 / 多能力并行（万能插线程池）"),
    "verify":  ("验证维", "触手肉眼验证现实（视觉指纹 + UIA 穿透读回）"),
    "health":  ("健康维", "五维自检评分（路由/执行/触手/视觉/审计）"),
    "unify":   ("合一维", "route→execute→verify→health 一条链"),
}

# 底座的候选（**存在才算**，不存在就不进图 —— 不许画不存在的东西）
_SOCKET_CANDIDATES = (
    "mind_engine.py", "security/security_brain.py",
    "tentacle/brain/visual_cortex.py", "tools/local_brain.py",
    "tentacle/brain/visual_memory.py", "think_loop.py", "brain_vault.py",
    "tools/brain_deploy.py", "tentacle/brain/gatekeeper.py",
    "tentacle/brain/transmit.py", "tentacle/brain/tentacle_transmission.py",
)


def _read(p: Path) -> str:
    return p.read_text(encoding="utf-8-sig", errors="replace")


def _funcs_and_calls(path: Path) -> tuple:
    """AST 读一个文件：顶层函数名 + **每个函数体内真实调用的名字**。

    为什么走 AST 而不是正则/文本：注释里提到一个函数名不等于调用了它。
    之前能力球的交叉扫就栽在这（把"提到"当成"用了"）。
    """
    src = _read(path)
    tree = ast.parse(src)
    funcs: list = []
    calls: dict = {}
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            funcs.append(node.name)
            names = set()
            for sub in ast.walk(node):
                if isinstance(sub, ast.Call):
                    f = sub.func
                    if isinstance(f, ast.Name):
                        names.add(f.id)
                    elif isinstance(f, ast.Attribute):
                        names.add(f.attr)
            calls[node.name] = sorted(names)
    return funcs, calls


def structure() -> dict:
    """算出大脑执行层的**结构图**（节点 + 有向边），全部有据可查。"""
    be = _BASE / "brain_exec.py"
    if not be.is_file():
        return {"ok": False, "error": "brain_exec.py 不存在 —— 不编一张图出来"}

    dim_funcs, dim_calls = _funcs_and_calls(be)

    # ── 五维节点：只认 brain_exec 里**真实存在**的那五个 ──
    dims = []
    for name in ("route", "execute", "verify", "health", "unify"):
        if name not in dim_funcs:
            continue
        cn, desc = _DIM_CN[name]
        dims.append({"id": "dim:" + name, "layer": "core", "name": name,
                     "kind": "dimension", "cn": cn, "desc": desc})

    # ── 能力节点：从注册表按 handler 对齐（真对齐，对不上就不连）──
    caps_by_dim: dict = {}
    try:
        from ..caps_registry import BENIGN_CAPS
    except Exception as e:                                          # noqa: BLE001
        BENIGN_CAPS = {}
        caps_err = f"{type(e).__name__}"
    else:
        caps_err = ""
    for kind, meta in sorted((BENIGN_CAPS or {}).items()):
        # 2026-10-17：共享实现模块改记 `impl`；`handler` 已是**分派键真名**。
        # 这里画的是"能力 → 实现"边，所以优先读 impl，老条目（handler 即实现名）继续兜底。
        h = str((meta or {}).get("impl") or (meta or {}).get("handler") or "")
        if h in dim_funcs or h == "brain_" + h:
            caps_by_dim.setdefault(h, []).append(kind)

    # ── 底座节点：**磁盘上真存在**才进 ──
    sockets = []
    for rel in _SOCKET_CANDIDATES:
        p = _BASE / rel
        if p.is_file():
            sockets.append({"id": "base:" + rel, "layer": "substrate",
                            "name": Path(rel).name, "kind": "module",
                            "path": "gbt_allinone/" + rel.replace("\\", "/"),
                            "bytes": p.stat().st_size})

    # ── 边：全部来自 **AST 查到的真实调用** ──
    edges = []
    _seen = set()

    def _add(a: str, b: str, kind: str, evidence: str) -> None:
        key = (a, b)
        if key in _seen:            # 去重：同一条边不许从两条路径各画一遍
            return
        _seen.add(key)
        edges.append({"from": "dim:" + a, "to": "dim:" + b,
                      "kind": kind, "evidence": evidence})

    for fn, called in dim_calls.items():
        for other in ("route", "execute", "verify", "health", "unify"):
            if other != fn and other in called:
                _add(fn, other, "calls", f"brain_exec.{fn}() 里真调了 {other}()")
    # 注册表声称的链 unify→route→execute→verify→health：
    # **只在 AST 也认的情况下**才画；认不出就如实记进 chain_evidence，不补假线。
    chain = [("unify", "route"), ("route", "execute"), ("execute", "verify"), ("verify", "health")]
    chain_evidence = []
    for a, b in chain:
        if (a, b) in _seen:
            chain_evidence.append({"pair": f"{a}→{b}", "source": "AST 实调",
                                   "drawn": True})
        else:
            chain_evidence.append({
                "pair": f"{a}→{b}", "source": "**源码未查到实调**", "drawn": False,
                "note": f"注册表把五维写成'一条链'，但 brain_exec.{a}() 里没查到调 {b}()"})

    # ── 注册表里的脑能力（同层）──
    peer = []
    for kind, meta in sorted((BENIGN_CAPS or {}).items()):
        if kind.startswith("brain_") or kind in ("think_loop", "autopilot", "llm_chat",
                                                 "mind", "tentacle", "local_brain"):
            if kind.startswith("brain_") and kind.split("brain_", 1)[1] in dim_funcs:
                continue                                    # 五维本身已经建过节点
            peer.append({"id": "cap:" + kind, "layer": "peer", "name": kind,
                         "kind": "capability", "domain": (meta or {}).get("domain", "?"),
                         "desc": str((meta or {}).get("desc") or "")[:60]})

    return {
        "ok": True,
        "version": _IMPL_VERSION,
        "computed_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "source_of_truth": {
            "dimensions": "gbt_allinone/brain_exec.py (AST)",
            "capabilities": "gbt_allinone/caps_registry.py (BENIGN_CAPS)",
            "substrate": "磁盘实存文件",
            "state": "gbt_allinone/store/audit.jsonl (只追加)",
        },
        "layers": [
            {"id": "core", "title": "五维合一脑", "nodes": dims},
            {"id": "peer", "title": "同层能力", "nodes": peer},
            {"id": "substrate", "title": "底座支撑", "nodes": sockets},
        ],
        "edges": edges,
        "chain_evidence": chain_evidence,
        "caps_by_dim": caps_by_dim,
        "caps_registry_error": caps_err,
        "counts": {"dimensions": len(dims), "peer": len(peer),
                   "substrate": len(sockets), "edges": len(edges)},
    }


def layout(struct: dict | None = None) -> dict:
    """**Sugiyama 式分层布局** —— 给节点算坐标，页面只管画。

    为什么不用力导向：执行层是**有向有序**的（route→execute→verify→health），
    力导向会把它揉成一团、先后全看不出。DAG 的专业解法就是分层：
        ① 分层（按真实拓扑的依赖深度，不是审美分区）
        ② 层内**重心法（barycenter）**排序 —— 减少连线交叉
        ③ 定坐标（层给 y，层内给 x，宽度按子树权重分配）

    布局只用**真实存在的边**；`chain_evidence` 里 drawn=false 的边不参与 —— 
    不存在的边若参与布局，坐标就会去迁就一条假线。
    """
    st = struct or structure()
    if not st.get("ok"):
        return {"ok": False, "error": "没有结构就没法布局"}

    layers = {l["id"]: list(l["nodes"]) for l in st["layers"]}
    edges = [e for e in st.get("edges") or []]
    ids = {n["id"] for l in layers.values() for n in l}

    # ① 分层：unify 是真实拓扑的根（它直接调四个维），所以 core 内部再分两小层
    def _depth(nid: str) -> int:
        # 有入边且入边源是维度的，排在下一层；unify 无入边 ⇒ 第 0 层
        return 0
    core = layers.get("core", [])
    incoming = {}
    for e in edges:
        incoming.setdefault(e["to"], []).append(e["from"])
    core_depth = {n["id"]: (0 if not incoming.get(n["id"]) else 1) for n in core}

    rows = [
        ("r0", [n for n in core if core_depth[n["id"]] == 0]),
        ("r1", [n for n in core if core_depth[n["id"]] == 1]),
        ("r2", layers.get("peer", [])),
        ("r3", layers.get("substrate", [])),
    ]

    # ② 层内重心法：用**上一层相连节点**的平均位置排序（连不上的排后面）
    order_prev = {n["id"]: i for i, n in enumerate(rows[0][1])}
    placed = dict(order_prev)
    for rid, nodes in rows[1:]:
        def bary(n):
            srcs = [f for f in incoming.get(n["id"], []) if f in placed]
            return (sum(placed[s] for s in srcs) / len(srcs)) if srcs else 1e9
        nodes.sort(key=lambda n: (bary(n), n["id"]))
        for i, n in enumerate(nodes):
            placed[n["id"]] = i

    # ③ 坐标：层给 y，层内均分 x；返回归一化 0..1，页面按画布放大
    out_rows = []
    total_w = max(1, max((len(ns) for _, ns in rows), default=1))
    for ri, (rid, nodes) in enumerate(rows):
        w = len(nodes)
        row = []
        for i, n in enumerate(nodes):
            x = (i + 0.5) / max(1, w)
            # 窄层在宽层下居中：按最大层宽做一次居中补偿，避免"挤在左边"
            x = 0.5 + (x - 0.5) * (w / total_w)
            row.append({"id": n["id"], "name": n.get("name"),
                        "layer": n.get("layer"), "kind": n.get("kind"),
                        "x": round(x, 5), "y": round((ri + 0.5) / len(rows), 5),
                        "row": rid, "col": i,
                        "meta": {k: v for k, v in n.items()
                                 if k not in ("id", "layer", "kind")}})
        out_rows.append({"row": rid, "count": w, "nodes": row})

    # 边的两端坐标（省得页面再去查）
    pos = {n["id"]: (n["x"], n["y"]) for r in out_rows for n in r["nodes"]}
    laid_edges = []
    for e in edges:
        a, b = pos.get(e["from"]), pos.get(e["to"])
        if not a or not b:
            continue
        laid_edges.append({**e, "x1": a[0], "y1": a[1], "x2": b[0], "y2": b[1]})

    return {"ok": True, "algorithm": "sugiyama-layered(barycenter)",
            "rows": out_rows, "edges": laid_edges,
            "counts": {"rows": len(out_rows), "nodes": len(pos), "edges": len(laid_edges)},
            "why_not_force": "执行层有向有序；力导向会揉乱先后，分层才看得出链路"}


def live_state(limit: int = 400) -> dict:
    """真实执行状态 —— 从 audit.jsonl **尾部**读最近若干条真事件。

    只读尾部（不整文件读 35 MB）：从文件末尾往回找够 limit 行的位置。
    """
    p = _BASE / "store" / "audit.jsonl"
    if not p.is_file():
        return {"ok": False, "error": "audit.jsonl 不存在 —— 没有真实事件，就不编状态"}
    size = p.stat().st_size
    block = 256 * 1024
    data = b""
    with p.open("rb") as f:
        pos = size
        while pos > 0 and data.count(b"\n") <= limit:
            step = min(block, pos)
            pos -= step
            f.seek(pos)
            data = f.read(step) + data
    lines = [l for l in data.split(b"\n") if l.strip()][-limit:]
    events = []
    for raw in lines:
        try:
            events.append(json.loads(raw.decode("utf-8", "replace")))
        except Exception:                                           # noqa: BLE001
            continue
    if not events:
        return {"ok": True, "count": 0, "events": [], "note": "有文件但没有可解析事件"}

    # 按 kind 汇总最近状态（这就是图上节点的"灯"）
    latest: dict = {}
    tally: dict = {}
    for e in events:
        meta = e.get("meta") or {}
        kind = str(meta.get("kind") or meta.get("cap") or "")
        if not kind:
            continue
        ev = str(e.get("event") or "")
        tally[kind] = tally.get(kind, 0) + 1
        if ev in ("ok", "error", "denied"):
            latest[kind] = {"event": ev, "ts": e.get("ts"), "iso": e.get("iso")}
    # ── 进出配对（span）⇒ 维状态：忙 / 卡 / 成 / 败 ──
    # 这是「真实执行的感觉」的核心。**忙与卡只能由真实的进/出事件推出**：
    #   进了没出      ⇒ busy（真在跑）
    #   进了超时没出   ⇒ stuck（真卡住）
    #   出了          ⇒ ok / fail（带真实耗时 ms）
    # 没有进事件时**不许编一个"忙"** —— 宁可它不亮。
    now = time.time()
    open_spans: dict = {}
    dims_state: dict = {}
    for e in events:
        ev = str(e.get("event") or "")
        meta = e.get("meta") or {}
        d = meta.get("dim")
        if not d:
            continue
        if ev == "brain_enter":
            open_spans[d] = e.get("ts") or now
        elif ev == "brain_exit":
            open_spans.pop(d, None)
            dims_state[d] = {"state": "ok" if meta.get("ok") else "fail",
                             "ms": meta.get("ms"), "iso": e.get("iso"),
                             "error": str(meta.get("error") or "")[:80]}
    for d, t0 in open_spans.items():
        age = max(0.0, now - float(t0 or now))
        dims_state[d] = {"state": "stuck" if age > _STUCK_S else "busy",
                         "age_s": round(age, 1), "since": t0}

    return {"ok": True, "count": len(events),
            "first_iso": events[0].get("iso"), "last_iso": events[-1].get("iso"),
            "latest_by_kind": latest, "tally": tally,
            "dims_state": dims_state,
            "spans_open": sorted(open_spans),
            "events": events[-40:]}


if __name__ == "__main__":
    import sys
    which = sys.argv[1] if len(sys.argv) > 1 else "structure"
    if which == "layout":
        out = layout()
    elif which == "live":
        out = live_state()
    else:
        out = structure()
    print(json.dumps(out, ensure_ascii=False, indent=1))
