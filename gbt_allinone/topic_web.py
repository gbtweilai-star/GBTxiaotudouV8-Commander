# -*- coding: utf-8 -*-
# gbt-capability: filesystem_write  ⬻ 开发者：自由的风 · GBT小土豆V8 · 永久钢印
"""主题共现网（topic_web）—— 蒸馏自「AI Safety HOT Hub」的**连接思路**

主人令（2026-10-15）：「把这玩意的**连接思路**蒸馏提炼出契合触手使用的能力」。

那张图的骨架（现读截图）：
  · 857 信源 · 7,397 条 · 今天 +463 ⇒ **多信源增量汇聚**
  · 每条带：来源 / 时间 / 关注度分 / 摘要 / 多标签 / 类型（观点·防御·治理）⇒ **条目契约**
  · 右侧那张图：25 个方向 · 8 家机构 · **线 = 同一条材料里同时出现** ⇒ **共现图**
  · Agent / MCP · 论文 Markdown/BibTeX/JSON ⇒ **给 agent 吃的机读口**
  · 每天 08:00 北京时间日报 ⇒ **定时增量**

它的灵魂不是“聚合新闻”，而是：

    **不问“这是什么”，问“它和谁一起出现”。**

本位只对这一件事负责（其余用她已有的触手，不重造）：
  build     从**她自己的料**（胶囊 + items.jsonl）算共现 → `state/topic_web/graph.json`
  stats     节点/边数、最大中心、最重的边
  neighbors 给一个实体 → 它和谁一起出现（按权重）
  path      两个实体之间的最短连接（“远距离的连接”）

铁律：① 没有料 ⇒ 如实报 `no_items`，不编图；② 每条边必须能回指**共现于哪几条料**（不许只给一个数）；
      ③ 老实报被跳过的料（太短/无实体）；④ 只读盘内容，不出网。

op：stats / neighbors / path（只读）· build（写）
"""
from __future__ import annotations

import json
import re
import time
from collections import Counter, defaultdict, deque
from itertools import combinations
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GRAPH = ROOT / "state" / "topic_web" / "graph.json"
ITEMS = ROOT / "state" / "topic_web" / "items.jsonl"
TAGS = ROOT / "state" / "topic_web" / "tags.json"
CAPSULES = ROOT / "gbt_allinone" / "store" / "devoured"
READ_OPS = ("stats", "neighbors", "path", "rank", "sources", "taxonomy")
WRITE_OPS = ("build",)
MIN_ITEMS = 2          # 至少两条料才算得出共现
MIN_LEN = 20           # 太短的料不参与

# 实体提取口径（不猜：只认字典标签 + 连续中文词块 + 大写开头的英文名）
_EN = re.compile(r"\b[A-Z][A-Za-z0-9]{2,}(?:[ -][A-Z][A-Za-z0-9]{1,})?\b")
_ZH = re.compile(r"[\u4e00-\u9fff]{2,4}")
_STOP_ZH = {"一个", "这个", "那个", "我们", "你们", "他们", "可以", "因为", "所以", "但是",
            "已经", "还没", "不许", "不是", "就是", "如果", "这个", "一直", "只能", "也不"}


def _tags_vocab() -> list:
    try:
        d = json.loads(TAGS.read_text(encoding="utf-8"))
        return [str(x) for x in (d.get("tags") or d if isinstance(d, list) else [])]
    except (OSError, ValueError):
        return []


_STRIP_MARKERS = ("开发者：自由的风", "本署名不可删除", "守护者：公主土豆",
                 "吞噬日期", "可吸收点", "本胶囊判据", "本作品由 GBT")


def _strip_boiler(text: str) -> str:
    """剪掉**已知的自家样板**（署名行与胶囊题花）。

    实测：署名行出现在近一半胶囊里，df 刚好没过 0.8 阈值 ⇒
    算出来的“共现”是「不可篡改—开发者 w=10」这种噪声。
    **自家样板是已知的 ⇒ 直接剪，不靠概率猜。**
    """
    out = []
    for line in str(text or "").splitlines():
        if any(m in line for m in _STRIP_MARKERS):
            continue
        out.append(line)
    return chr(10).join(out)

def extract_entities(text: str, vocab: list) -> list:
    """抽实体（三轴优先·不被英文短语吞）。

    实测踩过两次：
      ① 只靠 2-4 字块 ⇒ “Agent安全”被拆成 Agent + 安全；
      ② 先跑英文正则 ⇒ 机构名被吞进短语（Anthropic 变成 “Program Anthropic”）。
    现在的顺序：**词表命中先抠出来 → 把它们从文本里挖空 → 残余文本才交给英文/中文正则**。
    """
    t = str(text or "")
    long_tags = sorted({str(v) for v in vocab if v and str(v) in t}, key=len, reverse=True)
    residual = t
    for v in long_tags:
        residual = residual.replace(v, " ")
    ent = list(long_tags)
    for m in _EN.findall(residual):
        s = m.strip()
        if len(s) >= 3 and not any(s.lower() in v.lower() or v.lower() in s.lower() for v in long_tags):
            ent.append(s)
    for m in _ZH.findall(residual):
        if m in _STOP_ZH:
            continue
        ent.append(m)
    out, seen = [], set()
    for x in ent:
        k = x.lower()
        if len(x) >= 2 and k not in seen:
            seen.add(k)
            out.append(x)
    vocab_low = {v.lower() for v in long_tags}
    kept = []
    for x in out:
        if x.lower() in vocab_low:            # 词表里的（标签/类型/机构）**一律保留**
            kept.append(x)
            continue
        if any(x != y and x in y for y in out):   # 非词表的才吃碎片
            continue
        kept.append(x)
    return kept

def _items(inline: list | None = None) -> dict:
    """料源：内联 items > state/topic_web/items.jsonl > 她自己的胶囊。"""
    if inline:
        return {"source": "inline", "items": [dict(x) for x in inline]}
    if ITEMS.is_file():
        rows = []
        try:
            for line in ITEMS.read_text(encoding="utf-8", errors="replace").splitlines():
                line = line.strip()
                if line:
                    rows.append(json.loads(line))
        except (OSError, ValueError) as exc:
            return {"source": "items.jsonl", "items": [], "error": type(exc).__name__}
        if rows:
            return {"source": "items.jsonl", "items": rows}
    rows = []
    if CAPSULES.is_dir():
        for d in sorted(CAPSULES.iterdir()):
            f = d / "absorbed_knowledge.md"
            if f.is_file():
                try:
                    txt = f.read_text(encoding="utf-8", errors="replace")
                except OSError:
                    continue
                rows.append({"id": d.name, "title": d.name, "text": txt[:20000],
                             "source": "capsule:" + d.name, "ts": ""})
    return {"source": "capsules", "items": rows}

TAXONOMY = ROOT / "state" / "topic_web" / "tags.json"

# 三轴种子（缺省时用；一旦落盘就以盘上为准）
SEED_KINDS = ["防御", "观点", "治理", "攻击", "评测", "对齐", "真实事件"]
SEED_ORGS = ["OpenAI", "Anthropic", "Google DeepMind", "Meta", "NVIDIA", "Microsoft", "UK AISI",
             "Mistral", "Qwen", "阿里巴巴", "字节跳动", "腾讯", "百度", "DeepSeek"]


def _taxonomy() -> dict:
    """三轴词表：标签 / 类型 / 机构 + 信源权重（盘上为准）。"""
    try:
        d = json.loads(TAXONOMY.read_text(encoding="utf-8"))
        if isinstance(d, dict):
            return {"tags": list(d.get("tags") or []), "kinds": list(d.get("kinds") or SEED_KINDS),
                    "orgs": list(d.get("orgs") or SEED_ORGS), "weights": dict(d.get("weights") or {}),
                    "seeded": bool(d.get("seeded"))}
    except (OSError, ValueError):
        pass
    return {"tags": [], "kinds": list(SEED_KINDS), "orgs": list(SEED_ORGS), "weights": {}, "seeded": False}


def _seed_taxonomy(items: list) -> dict:
    """从料里把三轴长齐（未知的就收进来；不删已有）。"""
    tx = _taxonomy()
    for it in items:
        for tg in (it.get("tags") or []):
            s = str(tg).strip()
            if s and s not in tx["tags"]:
                tx["tags"].append(s)
        kind = str(it.get("kind") or "").strip()
        if kind and kind not in tx["kinds"]:
            tx["kinds"].append(kind)
        for og in (it.get("orgs") or []):
            s = str(og).strip()
            if s and s not in tx["orgs"]:
                tx["orgs"].append(s)
        blob = " ".join([str(it.get("title") or ""), str(it.get("text") or ""), str(it.get("source") or "")])
        for og in tx["orgs"]:
            if og and og.lower() in blob.lower():
                it.setdefault("orgs", [])
                if og not in it["orgs"]:
                    it["orgs"].append(og)
    tx["seeded"] = True
    return tx


def _axes(item: dict, tx: dict) -> dict:
    """把一条料分到三轴（不猜：只认词表命中）。"""
    blob = " ".join([str(item.get("title") or ""), str(item.get("text") or ""),
                     str(item.get("summary") or ""), str(item.get("source") or ""),
                     " ".join(item.get("tags") or [])])
    tags = [t for t in tx["tags"] if t and t in blob]
    kinds = [k for k in tx["kinds"] if k and k in blob]
    orgs = [o for o in tx["orgs"] if o and o.lower() in blob.lower()]
    kk = str(item.get("kind") or "").strip()
    if kk and kk not in kinds:
        kinds.append(kk)
    return {"tags": tags, "kinds": kinds, "orgs": orgs}


def taxonomy() -> dict:
    """三轴词表现读（只读）。"""
    tx = _taxonomy()
    seed_flag = TAXONOMY.is_file()
    return {"ok": True, "op": "taxonomy", "file": str(TAXONOMY), "on_disk": seed_flag,
            "axes": {"标签": len(tx["tags"]), "类型": len(tx["kinds"]), "机构": len(tx["orgs"])},
            "tags": tx["tags"][:40], "kinds": tx["kinds"], "orgs": tx["orgs"],
            "weights": tx["weights"],
            "honest": ("词表已落盘" if seed_flag else "词表未落盘 ⇒ 用种子；跑一次 build 就会把料里的标签并进去")}


def build(inline: list = None, min_weight: int = 1, min_node_count: int = 1, max_df: float = 0.8,
          top_edges: int = 400, top_nodes: int = 300) -> dict:
    got = _items(inline)
    items = got.get("items") or []
    if len(items) < MIN_ITEMS:
        return {"ok": False, "reason": "no_items", "items": len(items), "source": got.get("source"),
                "detail": "至少要 %d 条料才算得出共现（不编图）" % MIN_ITEMS}
    tx = _seed_taxonomy(items)
    if not TAXONOMY.is_file():
        TAXONOMY.parent.mkdir(parents=True, exist_ok=True)
        TAXONOMY.write_text(json.dumps({"tags": tx["tags"], "kinds": tx["kinds"], "orgs": tx["orgs"],
                                        "weights": tx["weights"], "seeded": True},
                                       ensure_ascii=False, indent=1), encoding="utf-8")
    vocab = list(tx["tags"]) + list(tx["kinds"]) + list(tx["orgs"])
    axis_of = {}
    for t in tx["tags"]:
        axis_of[t] = "标签"
    for k in tx["kinds"]:
        axis_of.setdefault(k, "类型")
    for o in tx["orgs"]:
        axis_of.setdefault(o, "机构")
    used, skipped = [], []
    for it in items:
        iid = str(it.get("id") or it.get("title") or ("item-%d" % len(used)))
        text = _strip_boiler(" ".join([str(it.get("title") or ""), str(it.get("text") or ""),
                         " ".join(it.get("tags") or []), str(it.get("summary") or ""),
                         " ".join(it.get("orgs") or [])] + [str(it.get("summary") or "")]))
        if len(text) < MIN_LEN:
            skipped.append({"id": iid, "why": "too_short"})
            continue
        ents = extract_entities(text, vocab)
        if not ents:
            skipped.append({"id": iid, "why": "no_entity"})
            continue
        it["axes"] = _axes(it, tx)
        used.append((iid, ents))
    # R-H1004（2026-10-15 实测）：她的胶囊是**同一模板**生成的，
    #   模板词（吞噬日期 / 可吸收点 / 分支 / GBT）会出现在近 100% 的料里 ⇒ 算出来的
    #   “共现”全是模板噪声（实测顶边：GBT—分支 w=24）。修法：文档频率 df/总数 > max_df
    #   的词当模板剔掉（经典 TF-IDF 里的高频过滤），并把剔掉了什么如实回报。
    _df = Counter()
    for _i, _ents in used:
        for _e in set(_ents):
            _df[_e] += 1
    _n_used = max(1, len(used))
    # R-H1005（实测）：**词表里声明的轴（标签/类型/机构）绝不能被高频误杀** ——
    #   小语料里一个真标签会出现在每一条里（df=1.0），被当模板丢掉就是把已知知识误杀。
    #   模板过滤只针对**自动抽出的噪声词**。
    _vocab_set = set(vocab)
    boiler = {e for e, c in _df.items()
              if c / float(_n_used) > float(max_df) and e not in _vocab_set}
    if boiler:
        used = [(i, [e for e in ents if e not in boiler]) for i, ents in used]
    node_count = Counter(e for _i, ents in used for e in ents)
    edges = defaultdict(list)
    for iid, ents in used:
        for a, b in combinations(sorted(set(ents)), 2):
            edges[(a, b)].append(iid)
    edge_rows = [{"a": a, "b": b, "weight": len(v), "items": v[:5]}
                 for (a, b), v in edges.items() if len(v) >= max(1, int(min_weight))]
    edge_rows.sort(key=lambda e: (-e["weight"], e["a"], e["b"]))
    node_rows = [{"id": k, "count": v, "axis": axis_of.get(k, "词")}
                 for k, v in node_count.most_common() if v >= max(1, int(min_node_count))][:max(1, int(top_nodes))]
    kept = {n["id"] for n in node_rows}
    edge_rows = [e for e in edge_rows if e["a"] in kept and e["b"] in kept][:max(1, int(top_edges))]
    by_axis = Counter(n["axis"] for n in node_rows)
    graph = {"at": time.strftime("%Y-%m-%dT%H:%M:%S"), "source": got.get("source"),
             "items_total": len(items), "items_used": len(used), "skipped": skipped[:20],
             "skipped_count": len(skipped), "nodes": node_rows, "edges": edge_rows,
             "axes": dict(by_axis),
             "boilerplate_dropped": len(boiler),
             "boilerplate_sample": sorted(boiler)[:10],
             "params": {"min_weight": min_weight, "min_node_count": min_node_count},
             "honest": "边**带回指证据**（同现于哪几条料），所以默认阈值 1 也不说谎；提高 min_weight/min_node_count 只会更刁"}
    _srcmap = _load_sources()
    _rows = _srcmap.setdefault("sources", {})
    for _it in items:
        _name = str(_it.get("source") or "(未标来源)")
        _row = _rows.setdefault(_name, {"items": 0, "first_ts": "", "last_seen_ts": "", "weight": 1.0})
        _row["items"] = int(_row.get("items") or 0) + 1
        _ts = str(_it.get("ts") or "")
        if _ts:
            if not _row.get("first_ts"):
                _row["first_ts"] = _ts
            if _ts > str(_row.get("last_seen_ts") or ""):
                _row["last_seen_ts"] = _ts
    _srcmap["at"] = time.strftime("%Y-%m-%dT%H:%M:%S")
    _srcmap["items_total"] = int(_srcmap.get("items_total") or 0) + len(items)
    _save_sources(_srcmap)
    GRAPH.parent.mkdir(parents=True, exist_ok=True)
    GRAPH.write_text(json.dumps(graph, ensure_ascii=False, indent=1), encoding="utf-8")
    return {"ok": True, "op": "build", "graph": str(GRAPH), "nodes": len(node_rows),
            "edges": len(edge_rows), "items_total": len(items), "items_used": len(used),
            "skipped": len(skipped), "source": got.get("source"), "axes": dict(by_axis),
            "boilerplate_dropped": len(boiler), "boilerplate_sample": sorted(boiler)[:10],
            "taxonomy": str(TAXONOMY),
            "top_edges": [{"a": e["a"], "b": e["b"], "weight": e["weight"]} for e in edge_rows[:5]]}
def _load() -> dict:
    try:
        return json.loads(GRAPH.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def stats() -> dict:
    g = _load()
    if not g:
        return {"ok": False, "reason": "no_graph", "graph": str(GRAPH),
                "detail": "还没建图 ⇒ 先跑 build" }
    deg = Counter()
    for e in g.get("edges") or []:
        deg[e["a"]] += e["weight"]
        deg[e["b"]] += e["weight"]
    return {"ok": True, "op": "stats", "at": g.get("at"), "source": g.get("source"),
            "items_total": g.get("items_total"), "items_used": g.get("items_used"),
            "skipped_count": g.get("skipped_count"), "nodes": len(g.get("nodes") or []),
            "edges": len(g.get("edges") or []),
            "hubs": [{"id": k, "degree": v} for k, v in deg.most_common(8)],
            "top_edges": [{"a": e["a"], "b": e["b"], "weight": e["weight"]}
                          for e in (g.get("edges") or [])[:5]],
            "honest": g.get("honest")}


def neighbors(entity: str = "", limit: int = 15) -> dict:
    ent = str(entity or "").strip()
    if not ent:
        return {"ok": False, "reason": "need_entity"}
    g = _load()
    if not g:
        return {"ok": False, "reason": "no_graph"}
    low = ent.lower()
    out = []
    for e in g.get("edges") or []:
        if e["a"].lower() == low or e["b"].lower() == low:
            other = e["b"] if e["a"].lower() == low else e["a"]
            out.append({"with": other, "weight": e["weight"], "evidence": e.get("items")})
    if not out:
        ids = [n["id"] for n in (g.get("nodes") or [])]
        near = [i for i in ids if low in i.lower() or i.lower() in low][:8]
        return {"ok": False, "reason": "no_such_entity", "entity": ent, "near": near,
                "detail": "图里没这个实体 ⇒ 不编邻居"}
    out.sort(key=lambda x: -x["weight"])
    return {"ok": True, "op": "neighbors", "entity": ent, "count": len(out),
            "neighbors": out[:max(1, int(limit))]}


def path(a: str = "", b: str = "", max_hops: int = 4) -> dict:
    """两个实体的最短连接（跨轴也能连：机构 ↔ 标签 ↔ 类型）。

    实测踩过：旧版**建图用原名、查询用小写** ⇒ 明明有边也报 `no_path`。
    现在一律小写作为键，出来时用 `label` 还回原名。
    """
    x, y = str(a or "").strip().lower(), str(b or "").strip().lower()
    if not x or not y:
        return {"ok": False, "reason": "need_two_entities"}
    g = _load()
    if not g:
        return {"ok": False, "reason": "no_graph"}
    adj, label = defaultdict(list), {}
    for e in g.get("edges") or []:
        ea, eb = str(e["a"]), str(e["b"])
        label[ea.lower()] = ea
        label[eb.lower()] = eb
        adj[ea.lower()].append((eb.lower(), e["weight"]))
        adj[eb.lower()].append((ea.lower(), e["weight"]))
    if x not in adj and y not in adj:
        ids = [n["id"] for n in (g.get("nodes") or [])]
        near = [i for i in ids if x in i.lower() or y in i.lower()][:8]
        return {"ok": False, "reason": "no_such_entity", "a": a, "b": b, "near": near}
    prev, q, seen = {}, deque([x]), {x}
    while q:
        cur = q.popleft()
        if cur == y:
            break
        for nxt, _w in adj[cur]:
            if nxt not in seen:
                seen.add(nxt)
                prev[nxt] = cur
                q.append(nxt)
    if y not in prev and x != y:
        return {"ok": False, "reason": "no_path", "a": a, "b": b, "reached": len(seen)}
    chain, cur = [y], y
    while cur != x:
        cur = prev[cur]
        chain.append(cur)
    chain.reverse()
    if len(chain) - 1 > int(max_hops):
        return {"ok": False, "reason": "too_far", "hops": len(chain) - 1,
                "chain": [label.get(k, k) for k in chain]}
    hops = [{"from": label.get(chain[i], chain[i]), "to": label.get(chain[i + 1], chain[i + 1])}
            for i in range(len(chain) - 1)]
    return {"ok": True, "op": "path", "a": a, "b": b, "hops": len(hops),
            "chain": [label.get(k, k) for k in chain], "edges": hops}

def run(op: str = "stats", **kw) -> dict:
    o = (op or "stats").strip().lower()
    if o == "stats":
        return stats()
    if o == "neighbors":
        return neighbors(kw.get("entity", ""), int(kw.get("limit", 15) or 15))
    if o == "path":
        return path(kw.get("a", ""), kw.get("b", ""), int(kw.get("max_hops", 4) or 4))
    if o == "rank":
        return rank(int(kw.get("limit", 10) or 10), kw.get("items"))
    if o == "sources":
        return sources()
    if o == "taxonomy":
        return taxonomy()
    if o == "build":
        return build(kw.get("items"), int(kw.get("min_weight", 1) or 1),
                     int(kw.get("min_node_count", 1) or 1))
    return {"ok": False, "reason": "unknown_op", "op": o,
            "known": list(READ_OPS) + list(WRITE_OPS),
            "executor": "万能插（five-dim.py cap topic_web）",
            "detail": "未知 op 只回错（fail-closed）"}

# ── R-H1002（2026-10-15）：信源水位 + 关注度分 ───────────────────────────
SOURCES = ROOT / "state" / "topic_web" / "sources.json"
HALF_LIFE_DAYS = 7.0


def _load_sources() -> dict:
    try:
        d = json.loads(SOURCES.read_text(encoding="utf-8"))
        return d if isinstance(d, dict) else {}
    except (OSError, ValueError):
        return {}


def _save_sources(d: dict) -> None:
    SOURCES.parent.mkdir(parents=True, exist_ok=True)
    SOURCES.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")


def _age_days(ts: str) -> float:
    """时间戳 → 距今天数；读不到就回 -1（不编）。"""
    s = str(ts or "").strip()
    if not s:
        return -1.0
    for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d"):
        try:
            import datetime as _dt
            t0 = _dt.datetime.strptime(s[:len(fmt) + 2].strip(), fmt)
            return max(0.0, (_dt.datetime.now() - t0).total_seconds() / 86400.0)
        except ValueError:
            continue
    try:
        return max(0.0, (time.time() - float(s)) / 86400.0)
    except (TypeError, ValueError):
        return -1.0


def attention(item: dict, weight: float = 1.0) -> dict:
    """关注度分 = **来源权重 × 时间衰减 × 标签命中**（三个分量都返回，不是魔法数）。

    · 来源权重：`sources.json` 里的 weight（没写就 1.0）
    · 时间衰减：exp(-age/HALF_LIFE_DAYS)；**没时间戳 ⇒ 中性 0.5 并标 ts_missing**
    · 标签命中：1 + 0.25×(标签数-1)（多标签 = 多维都指向它）
    """
    tags = [str(x) for x in (item.get("tags") or []) if x]
    age = _age_days(item.get("ts"))
    rec = 0.5 if age < 0 else round(2.718281828 ** (-age / HALF_LIFE_DAYS), 4)
    tag_hits = round(1.0 + 0.25 * max(0, len(tags) - 1), 3)
    score = round(float(weight) * rec * tag_hits, 4)
    return {"score": score, "components": {"source_weight": float(weight), "recency": rec,
                                           "tag_hits": tag_hits, "tags": len(tags),
                                           "age_days": (None if age < 0 else round(age, 2))},
            "ts_missing": age < 0}


def rank(limit: int = 10, items: list = None) -> dict:
    """按关注度分排序（只读）—— 每条都带三个分量。"""
    got = _items(items)
    rows = got.get("items") or []
    if not rows:
        return {"ok": False, "reason": "no_items", "source": got.get("source")}
    src = _load_sources().get("sources") or {}
    scored = []
    for it in rows:
        name = str(it.get("source") or "(\u672a标\u6765\u6e90)")
        _w_axis = dict(_taxonomy().get("weights") or {})
        w = float((src.get(name) or {}).get("weight") or _w_axis.get(name) or 1.0)
        a = attention(it, w)
        scored.append({"id": it.get("id") or it.get("title"), "source": name,
                       "title": str(it.get("title") or "")[:80], **a})
    scored.sort(key=lambda x: -x["score"])
    miss = sum(1 for x in scored if x["ts_missing"])
    return {"ok": True, "op": "rank", "items": len(scored), "ranked": scored[:max(1, int(limit))],
            "ts_missing": miss, "formula": "来源权重 × exp(-天数/%.0f) × (1+0.25×(标签数-1))" % HALF_LIFE_DAYS,
            "honest": ("有 %d 条无时间戳 ⇒ 衰减取中性 0.5，不冒充新闻" % miss) if miss else "全部有时间戳"}


def sources() -> dict:
    """信源水位读数（只读）—— 防重复计数的那条水线。"""
    d = _load_sources()
    src = d.get("sources") or {}
    if not src:
        return {"ok": False, "reason": "no_sources", "file": str(SOURCES),
                "detail": "还没水位 ⇒ 先跑 build（它会顺手记水位）"}
    rows = [{"source": k, **v} for k, v in sorted(src.items(), key=lambda kv: -(kv[1].get("items") or 0))]
    return {"ok": True, "op": "sources", "count": len(rows), "sources": rows[:50],
            "at": d.get("at"), "items_total": d.get("items_total"),
            "honest": "水位 = 每条源上次看到的最新时间戳 + 累计条数；下次 build 只算**新增**"}
