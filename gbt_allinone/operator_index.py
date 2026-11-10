# -*- coding: utf-8 -*-
"""operator_index —— 31 个域 428 个能力位的**算子层**（闸门 + 索引）。

它解决的问题
------------
路由此前只有两条路：语义模型（一次生成，慢）或字符 2-gram（快但瞎猜）。
中间那层「先把 428 个选项压到几个」一直缺着 —— 因为大多数能力位在算子层
是空壳，没有可打分的触发词。

本模块把每个能力位配成一条算子记录：
    域 / 处理器 / 安全性 / desc / 触发词 / 领域词表 / 二元组 / 图邻居 / 真实调用数
然后给出一个**会弃权**的闸门：只在高置信时直达，其余一律交回上层。

三条纪律
--------
1. **不猜**：触发词只来自三处**已经存在的人工资产** —— desc 里写好的「常用说法」、
   `llm/route_lexicon` 的人工词表、`data/intent-lexicon.json` 的人工意图词表。
   没有就留空、进待办队列，**不生成、不补写**。
2. **会弃权**：没有策展词 / top1 与 top2 分不开 / 绝对分过低 ⇒ `hit=False`，放行。
   一个「什么都说好」的闸门比没有闸门更危险。
3. **陈旧即失效**：registry 或 wiring 比索引新 ⇒ 不直达（索引不报错，只会悄悄算偏）。

CLI（pyembed 是 isolated 模式，`-m` 不生效，一律走薄壳）：
    python tools/codex-scripts/build-operator-index.py build|check|stats|score "一句话"
"""
from __future__ import annotations

import json
import os
import re
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INDEX = ROOT / "state" / "operator-index.json"
WIRING = ROOT / "state" / "model-pack" / "wiring.json"
LEDGER = ROOT / "state" / "orchestration-ledger.jsonl"
REGISTRY = ROOT / "gbt_allinone" / "caps_registry.py"
GATE_LOG = ROOT / "state" / "operator-log.jsonl"
CURATION = ROOT / "state" / "operator-curation.json"
INTENT_LEXICON = ROOT / "data" / "intent-lexicon.json"

MAX_TOKENS = 400
MAX_PHRASES = 32
DESC_HEAD = 1500

_PHRASE = re.compile(r"常用说法(?:（[^）]{0,40}）)?[：:]\s*(.+?)(?=。|$)", re.S)
_CJK = re.compile(r"[\u4e00-\u9fff]+")
_ASCII = re.compile(r"[A-Za-z][A-Za-z0-9_]{2,}")


def phrases_of(desc: str) -> list:
    m = _PHRASE.search(desc or "")
    if not m:
        return []
    raw = m.group(1).replace("*", "").replace("`", "")
    out = []
    for part in re.split(r"\s*[/／、]\s*", raw):
        p = part.strip().strip("，,、;； ")
        if not p or len(p) > 24 or p in out:
            continue
        out.append(p)
        if len(out) >= MAX_PHRASES:
            break
    return out


def tokens_of(name: str, desc: str) -> list:
    toks = [w.lower() for w in name.split("_") if w]
    head = (desc or "")[:DESC_HEAD]
    toks += [w.lower() for w in _ASCII.findall(head)]
    for run in _CJK.findall(head):
        toks += [run[i:i + 2] for i in range(len(run) - 1)]
    out, seen = [], set()
    for t in toks:
        if t in seen:
            continue
        seen.add(t)
        out.append(t)
        if len(out) >= MAX_TOKENS:
            break
    return out


def _lexicon() -> dict:
    try:
        from .llm.route_lexicon import LEXICON
    except Exception:
        return {}
    out = {}
    for entry in LEXICON:
        pats = [str(x) for x in (entry.get("patterns") or [])]
        for kind in entry.get("kinds") or []:
            bucket = out.setdefault(str(kind), [])
            for pat in pats:
                if pat not in bucket:
                    bucket.append(pat)
    return out


def _curation() -> dict:
    """人工策展覆盖层。读不动就当没有 —— 不许让一个坏文件拖垮整层。"""
    if not CURATION.exists():
        return {}
    try:
        data = json.loads(CURATION.read_text(encoding="utf-8-sig"))
        return {str(k): [str(x) for x in v if str(x).strip()]
                for k, v in (data.get("caps") or {}).items() if v}
    except Exception:
        return {}


def _veto() -> dict:
    """人工否决层：{cap: [说法]} —— 把某个说法从**这一位**上摘掉。

    为什么要「减」这一手：`data/intent-lexicon.json` 里有几处**过短的通用词**，
    子串匹配会让它吃掉整句。实测「我们现在使用的是本地算力」被判成 `cloud_pc`
    （云电脑），就是 `算力` 这两个字干的；「看一眼桌面」被 `vision` 吃掉，
    是 `看一眼` 干的。加词救不了这种病 —— 只能把那个词从该位上摘掉。

    否决只影响本层的打分，**不改 `data/intent-lexicon.json`**（那份表有测试锁着）。
    """
    if not CURATION.exists():
        return {}
    try:
        data = json.loads(CURATION.read_text(encoding="utf-8-sig"))
    except Exception:
        return {}
    return {str(k): [str(x) for x in v if str(x).strip()]
            for k, v in (data.get("veto") or {}).items() if v}


def _intent_lexicon() -> dict:
    """`data/intent-lexicon.json` 的人工意图词表 → {cap: {说法: 归一权重}}。

    这份表是**人维护的**（479 个意图 / 1042 条说法，`tests/test_catalog.py` 逐条
    校验能力位名必须存在），不是从 desc 里抽出来的碎片。同一个意图挂多个能力位时，
    表里本来就写了权重（例：genoffice 10 : genoffice_bridge 4）—— 那就是人给的
    先后次序，原样沿用，不重新发明。

    权重按该说法下的最大值归一：意图内第一名恒为 1.0，其余小于 1.0，
    分差就是人的判断，闸门不用再猜。
    """
    if not INTENT_LEXICON.exists():
        return {}
    try:
        data = json.loads(INTENT_LEXICON.read_text(encoding="utf-8-sig"))
    except Exception:
        return {}
    out = {}
    for entry in data.get("intents") or []:
        say = [str(x).strip() for x in (entry.get("say") or []) if str(x).strip()]
        caps = {str(k): float(v or 0) for k, v in (entry.get("caps") or {}).items()}
        if not say or not caps:
            continue
        top = max(caps.values()) or 1.0
        for cap, weight in caps.items():
            bucket = out.setdefault(cap, {})
            norm = max(0.0, min(1.0, weight / top))
            for phrase in say:
                if norm > bucket.get(phrase, -1.0):
                    bucket[phrase] = norm
    return out


def _graph() -> dict:
    if not WIRING.exists():
        return {}
    try:
        return (json.loads(WIRING.read_text(encoding="utf-8")) or {}).get("adj") or {}
    except Exception:
        return {}


def _usage() -> dict:
    used = {}
    if not LEDGER.exists():
        return used
    # 账本是追加写的，历史上出现过非 UTF-8 残片（PowerShell/旧写入器）。
    # 这里只读 usage 权重：坏行替换掉、跳过，**不改账本本身**；否则一次坏字节
    # 会让整个算子索引建不出来（2026-11-07 实测：position 3757 的 0x83）。
    with LEDGER.open(encoding="utf-8", errors="replace") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except Exception:
                continue
            cap = row.get("cap") or row.get("kind") or row.get("name")
            if cap:
                used[cap] = used.get(cap, 0) + 1
    return used


def _siblings(adj: dict) -> dict:
    """同族能力位：{cap: {另一 cap: 共享实现文件数}}。

    `wiring.json` 里**没有 cap→cap 边**（实测 428 个 cap 节点，互连 0 条），
    所以 `adj["cap:x"]` 的点全是 `code:`/`page:` —— 直接取邻居只会得到空列表。
    但两个能力位若由同一批代码实现，它们就是同族；用「共享 code: 节点」补出这层关系。

    一个文件被几十个 cap 共享时没有判别力（`api.py`、`caps_registry.py` 就是这种），
    超过 40 个的一律不参与。
    """
    code2caps = {}
    for node, nbrs in adj.items():
        if not str(node).startswith("cap:"):
            continue
        cap = str(node).split(":", 1)[1]
        for nb in nbrs or []:
            if str(nb).startswith("code:"):
                code2caps.setdefault(str(nb), []).append(cap)
    shared = {}
    for _, caps_ in code2caps.items():
        if len(caps_) < 2 or len(caps_) > 40:
            continue
        uniq = sorted(set(caps_))
        for i, a in enumerate(uniq):
            for b in uniq[i + 1:]:
                shared.setdefault(a, {})
                shared[a][b] = shared[a].get(b, 0) + 1
                shared.setdefault(b, {})
                shared[b][a] = shared[b].get(a, 0) + 1
    return shared


def build() -> dict:
    from . import caps_registry as CR

    caps = CR.BENIGN_CAPS
    adj, used, lex, cur, ilex = _graph(), _usage(), _lexicon(), _curation(), _intent_lexicon()
    vet = _veto()
    sibs = _siblings(adj)
    ops, queue = {}, []

    for name, meta in caps.items():
        desc = str(meta.get("desc") or "")
        phr = phrases_of(desc)
        extra = [x for x in cur.get(name, []) if x not in phr]
        phr = phr + extra
        # 人工意图词表：{说法: 归一权重}。**不并进 phrases** ——
        # 并进去就丢了「同一说法下谁排第一」这个人的判断，多能力位会打平手。
        iex = ilex.get(name, {})
        _vet = vet.get(name) or []
        if _vet:
            phr = [p for p in phr if p not in _vet]
            iex = {p: w for p, w in iex.items() if p not in _vet}
        node = "cap:%s" % name
        nbrs = list(adj.get(node) or [])
        rel = sorted((sibs.get(name) or {}).items(), key=lambda kv: (-kv[1], kv[0]))[:12]
        rec = {
            "cap": name,
            "kind": "cap",
            "name": name,
            "domain": meta.get("domain") or "unknown",
            "handler": meta.get("handler") or "none",
            "safe": bool(meta.get("safe")),
            "desc": desc,
            "phrases": phr,
            "lexicon": lex.get(name, []),
            "curation": cur.get(name, []),
            "iex": iex,
            "veto": _vet,
            "curated": bool(phr or lex.get(name) or iex),
            "tokens": tokens_of(name, desc),
            "graph": {"node": node, "degree": len(nbrs), "in_graph": bool(nbrs),
                      # 同族 = 共享实现文件；按共享数降序。via 写明来源，
                      # 免得下一个人再去 adj 里翻 cap→cap 边（那里一条都没有）。
                      "cap_neighbors": [c for c, _ in rel],
                      "cap_overlap": {c: n for c, n in rel},
                      "via": "shared-code"},
            "usage": used.get(name, 0),
            "requires_params": bool(meta.get("requires_params")),
        }
        ops[name] = rec
        if not rec["curated"]:
            queue.append({"cap": name, "domain": rec["domain"],
                          "degree": len(nbrs), "usage": rec["usage"],
                          "hint": desc[:80]})

    queue.sort(key=lambda r: (-r["degree"], -r["usage"], r["cap"]))

    by_domain = {}
    for rec in ops.values():
        d = by_domain.setdefault(rec["domain"], {"total": 0, "curated": 0})
        d["total"] += 1
        d["curated"] += 1 if rec["curated"] else 0

    return {
        "schema": 1,
        "at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "source": {"registry": "gbt_allinone/caps_registry.py:BENIGN_CAPS",
                   "graph": "state/model-pack/wiring.json",
                   "ledger": "state/orchestration-ledger.jsonl",
                   "intent_lexicon": "data/intent-lexicon.json"},
        "count": len(ops),
        "curated": sum(1 for r in ops.values() if r["curated"]),
        "uncurated": sum(1 for r in ops.values() if not r["curated"]),
        "coverage": {"by_domain": by_domain},
        "note": ("词只来自三处人工资产：desc「常用说法」/ route_lexicon / "
                 "data/intent-lexicon.json；空即如实空，不补写"),
        "operators": ops,
        "queue": queue,
    }


def write_atomic(path: Path, obj: dict, key: str = "count") -> None:
    """先落盘 → 读回校验 → 同卷原子替换 → 再读回校验。

    `key` 是这份产物的「有意义」判据：索引看 `count`+`operators`，策展层看 `caps`。
    原子性只保证「要么旧的、要么新的」，保证不了「新的有意义」——
    所以校验必须按产物自己的形状来，不能一把尺子量所有文件。
    """
    def _ok(back) -> bool:
        if back.get(key) != obj.get(key):
            return False
        return bool(back.get("operators")) if key == "count" else True

    tmp = path.with_name("%s.tmp-%d" % (path.name, os.getpid()))
    try:
        with open(tmp, "w", encoding="utf-8", newline="") as fh:
            json.dump(obj, fh, ensure_ascii=False, indent=1)
            fh.flush()
            os.fsync(fh.fileno())
        if not _ok(json.loads(tmp.read_text(encoding="utf-8"))):
            raise RuntimeError("读回校验失败：%s 对不上，拒绝替换" % key)
        os.replace(tmp, path)
    finally:
        if tmp.exists():
            try:
                tmp.unlink()
            except OSError:
                pass
    if not _ok(json.loads(path.read_text(encoding="utf-8"))):
        raise RuntimeError("替换后读回校验失败")


_CACHE = {"key": None, "idx": None}


def load() -> tuple:
    """返回 (index, stale_reason)。stale 时调用方**不许**拿它做直达。

    进程内按 (mtime, size) 缓存：热路径不该每次重读 2 MB 的 JSON。
    缓存键就取文件元信息，索引一换自动失效 —— 不靠手动清缓存。
    """
    if not INDEX.exists():
        return None, "还没有算子索引（先跑 build）"
    try:
        st = INDEX.stat()
        key = (st.st_mtime_ns, st.st_size)
        if _CACHE["key"] != key or _CACHE["idx"] is None:
            _CACHE["idx"] = json.loads(INDEX.read_text(encoding="utf-8"))
            _CACHE["key"] = key
        idx = _CACHE["idx"]
    except Exception as exc:
        return None, "索引读不动：%s" % type(exc).__name__
    built = INDEX.stat().st_mtime
    for src in (REGISTRY, WIRING, CURATION, INTENT_LEXICON):
        if src.exists() and src.stat().st_mtime > built + 1:
            return idx, "索引陈旧：%s 比索引新" % src.name
    return idx, ""


def qgrams(text: str) -> set:
    s = re.sub(r"\s+", "", text or "")
    g = set()
    for run in _CJK.findall(s):
        if len(run) == 1:
            g.add(run)
        for i in range(len(run) - 1):
            g.add(run[i:i + 2])
    return g | {w.lower() for w in _ASCII.findall(s)}


def rank(idx: dict, text: str, topk: int = 8) -> dict:
    q = str(text or "").strip()
    qg = qgrams(q)
    rows = []
    for name, op in idx["operators"].items():
        toks = set(op["tokens"])
        cov = (len(qg & toks) / len(qg)) if qg else 0.0
        phr = op.get("phrases") or []
        # 精确命中一条策展词 = 最强证据（1.0 分档）；子串命中次之（0.35 档）。
        # 只给 0.25 会让「截个屏」这种查不到二元组覆盖的句子被绝对分门槛拦下 —— 那是自伤。
        exact = any(q and q == p for p in phr)
        # 子串档只认「词」，不认「概念」：desc 的「常用说法」是正则从散文里抠出来的，
        # 抠出 1~2 字的东西（控件 / 量化 / 原生 / 按钮 / 边界 / 加载）是**术语**不是指令，
        # 它出现在任何长句里都会把整句判给该位。2026-11-05 实测：45 条子串发火里
        # 21 条是 2 字 desc 词，逐条看过全是产品说明文，没有一条是指令；同一批里
        # 真正的指令一条没丢（帮我截屏 / 看屏幕 / 照片里有几只猫 / 拍一张 / 还是它吗）。
        # 人工策展词不受此限：那是按「一句话怎么说」写的，2 字（截屏 / 截图）照样算。
        cur = op.get("curation") or []
        sub_hit = any(p and (p in q or q in p)
                      and (p in cur or len(re.sub(r"\s+", "", p)) >= 3)
                      for p in phr)
        hit = exact or sub_hit
        lex_hit = any(p and p in q for p in op.get("lexicon") or [])
        # 人工意图词表：同一说法下各能力位的权重就是人排的先后。
        # 精确相等按 0.95 × 归一权重计（略低于 desc 的精确命中 1.00 ——
        # 「desc 里直接写明的说法」仍占先）；子串命中再打五折。
        iex = op.get("iex") or {}
        iex_w = iex.get(q, 0.0) if q else 0.0
        if not iex_w and q:
            subs = [w for p, w in iex.items() if p and (p in q or q in p)]
            iex_w = 0.5 * max(subs) if subs else 0.0
        # 精确相等(1.00) 必须压过「子串+二元组覆盖」——否则 ocr 的「截图转文字」
        # 会靠覆盖抢走纯「截图」，那是把两个动作当成一个。
        strength = max(1.00 if exact else (0.35 if sub_hit else 0.0),
                       0.95 * iex_w)
        score = (0.45 * cov + strength
                 + (0.15 if lex_hit else 0.0) + (0.05 if op["curated"] else 0.0))
        rows.append({"cap": name, "kind": op.get("kind", "cap"),
                     "name": op.get("name", name),
                     "domain": op["domain"], "score": round(score, 4),
                     "coverage": round(cov, 4),
                     "phrase_hit": bool(hit or lex_hit or iex_w),
                     "curated": op["curated"],
                     "source": ("desc" if hit else "lexicon" if lex_hit
                                else "intent" if iex_w else None)})
    rows.sort(key=lambda r: -r["score"])
    top = rows[:topk]
    margin = (top[0]["score"] - top[1]["score"]) if len(top) > 1 else 0.0

    if not top or top[0]["score"] <= 0:
        esc, why = True, "没有任何算子命中"
    elif not top[0]["curated"]:
        esc, why = True, "top-1 没有策展触发词，证据不足"
    elif not top[0].get("phrase_hit"):
        # 「这位有词」≠「这句话命中了它的词」。只靠二元组覆盖中标，
        # 是「像」不是「是」—— 实测会让 vision 用覆盖抢走「看一眼桌面」。
        esc, why = True, "top-1 只靠二元组覆盖，没命中触发词"
    elif margin < 0.08:
        esc, why = True, "top-1 与 top-2 分不开"
    elif top[0]["score"] < 0.35:
        esc, why = True, "绝对分过低，只是有点像"
    else:
        esc, why = False, "top-1 有策展词且与次名拉开"
    return {"query": q, "top": top, "margin": round(margin, 4),
            "escalate": esc, "why": why}


def gate(text: str, topk: int = 5) -> dict:
    """闸门：hit=True 才允许直达；其余一律交回上层（失败即放行）。"""
    try:
        idx, stale = load()
        if idx is None:
            return {"ok": True, "hit": False, "why": stale}
        if stale:
            return {"ok": True, "hit": False, "why": stale}
        r = rank(idx, text, topk)
        return {"ok": True, "hit": (not r["escalate"]), **r}
    except Exception as exc:  # noqa: BLE001
        return {"ok": True, "hit": False,
                "why": "闸门异常即放行：%s" % type(exc).__name__}


def log_gate(text: str, g: dict, ms=None, src: str = "route") -> None:
    """每次闸门判断落一条。**永不抛异常** —— 观测是旁路，不许拖垮路由。"""
    try:
        top = (g.get("top") or [{}])[0] or {}
        row = {"ts": time.strftime("%Y-%m-%dT%H:%M:%S"),
               "query": str(text or "")[:300],
               "hit": bool(g.get("hit")),
               "why": g.get("why"),
               "margin": g.get("margin"),
               "top1": top.get("cap"),
               "score": top.get("score"),
               "ms": round(float(ms), 1) if ms is not None else None,
               "src": str(src or "route")}
        with open(GATE_LOG, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")
    except Exception:
        pass


def hint_note(text: str, topk: int = 2, gate_result=None,
              max_chars: int = 200, min_score: float = 1.0) -> dict:
    """把「428 个能力位」压成一行候选，交给对话模型 —— 只提示，不给执行权。

    为什么单独一个函数：gate 的返回是给人和台账看的（带分数、来源、why），
    整段塞进 prompt 太吵，而且本机 1.16 tok/s —— 多一个字都是钱。
    模型只需要知道「可能是哪几个」；要不要执行、能不能执行，不归这句话管。

    gate_result 允许调用方把已经算过的判定传进来，避免同一句话算两遍。
    预算装不下就返回空串：宁可不提示，也不塞半句话。
    """
    try:
        idx, _stale = load()
        g = gate_result if gate_result is not None else gate(text, topk=topk)
        if not (g or {}).get("hit"):
            return {"ok": True, "hit": False, "note": "", "caps": [],
                    "why": (g or {}).get("why") or "未命中"}
        top0 = ((g or {}).get("top") or [{}])[0] or {}
        # 只往 prompt 里塞「整句就等于一条策展说法」的强证据。
        # 为什么比 gate 更严：gate 弃权/命中都是给路由看的（还有别的车道兜底），
        # 而提示是直接写进模型脑子里的 —— 塞错一条比不塞更坏。
        # 实测：841 句主人原话里 gate 会发火 161 次，但强证据只有 12 次，
        # 剩下 149 次是「说法被包在长句里」（"未生成视频"→comfy_cloud 这种）。
        if float(top0.get("score") or 0.0) < float(min_score):
            return {"ok": True, "hit": False, "note": "", "caps": [],
                    "why": "只有弱证据（%.2f < %.2f），不往提示里塞"
                           % (float(top0.get("score") or 0.0), float(min_score))}
        rows = [r for r in ((g or {}).get("top") or []) if r.get("cap")]
        rows = rows[:max(1, int(topk))]
        if not rows:
            return {"ok": True, "hit": False, "note": "", "caps": [], "why": "没有候选"}
        total = int((idx or {}).get("count") or 0)
        if not total:
            total = len(((idx or {}).get("operators") or {}))
        head = "（本机算子闸门把 %d 个能力位压到这几个：" % total
        tail = "。这只是一条提示，不确定就照常回答，不要硬套。）"
        for n in range(len(rows), 0, -1):
            names = [str(r["cap"]) for r in rows[:n]]
            note = head + " / ".join(names) + tail
            if len(note) <= int(max_chars):
                return {"ok": True, "hit": True, "note": note,
                        "caps": names, "why": g.get("why")}
        return {"ok": True, "hit": True, "note": "", "caps": [],
                "why": "预算 %d 字装不下，宁可不提示" % int(max_chars)}
    except Exception as exc:  # noqa: BLE001
        return {"ok": True, "hit": False, "note": "", "caps": [],
                "why": "提示生成失败即不提示：%s" % type(exc).__name__}


def _pct(values, q):
    if not values:
        return None
    vals = sorted(values)
    i = min(len(vals) - 1, max(0, int(round(q * (len(vals) - 1)))))
    return vals[i]


def stats() -> dict:
    """闸门读数：命中率 / 弃权原因 / 耗时分布。没数据就如实说没数据。"""
    if not GATE_LOG.exists():
        return {"ok": True, "total": 0, "log": str(GATE_LOG),
                "note": "还没有数据：闸门要真跑过才积累"}
    rows = []
    with GATE_LOG.open(encoding="utf-8", errors="replace") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except Exception:
                continue
    if not rows:
        return {"ok": True, "total": 0, "log": str(GATE_LOG),
                "note": "还没有数据：闸门要真跑过才积累"}

    route_rows = [r for r in rows if (r.get("src") or "route") == "route"]
    manual = len(rows) - len(route_rows)
    hits = sum(1 for r in route_rows if r.get("hit"))
    by_why, miss_top = {}, {}
    for r in route_rows:
        if r.get("hit"):
            continue
        key = str(r.get("why") or "unknown")
        by_why[key] = by_why.get(key, 0) + 1
        cap = r.get("top1")
        if cap:
            miss_top[cap] = miss_top.get(cap, 0) + 1
    ms = [r["ms"] for r in route_rows if isinstance(r.get("ms"), (int, float))]
    total = len(route_rows)
    return {
        "ok": True,
        "total": total,
        "manual_records": manual,
        "hit": hits,
        "miss": total - hits,
        "hit_rate_pct": round(100.0 * hits / total, 1) if total else None,
        "by_why": dict(sorted(by_why.items(), key=lambda kv: -kv[1])),
        "top_miss_caps": sorted(miss_top.items(), key=lambda kv: -kv[1])[:10],
        "ms_p50": _pct(ms, 0.50),
        "ms_p95": _pct(ms, 0.95),
        "log": str(GATE_LOG),
        "note": ("hit_rate 只统计**真路由**（src=route）；手动 --record 的样本"
                 "单列在 manual_records，不混进命中率"),
    }


def _write_curation(caps: dict) -> None:
    """只动策展覆盖层。保留原有 note/schema，原子替换 + 读回校验。"""
    payload = {"schema": 1, "caps": caps}
    if CURATION.exists():
        try:
            old = json.loads(CURATION.read_text(encoding="utf-8-sig"))
            if old.get("note"):
                payload["note"] = old["note"]
            if old.get("veto"):
                payload["veto"] = old["veto"]
        except Exception:
            pass
    payload.setdefault("note", "人工策展覆盖层：只写该位 desc 能直接支撑的说法")
    write_atomic(CURATION, payload, key="caps")


def curate(cap: str, phrases, apply: bool = False) -> dict:
    """加词前先对打全表：抢不过别人、或与次名分不开，就**拒绝写入**。

    这条纪律是拿真金换来的：不加对打就写「截图」进 body_see，会被 ocr 的
    「截图转文字」靠二元组覆盖抢走 —— 词加进去了，路由反而更糟。
    """
    idx, stale = load()
    if idx is None:
        return {"ok": False, "error": stale}
    ops = idx["operators"]
    if cap not in ops:
        return {"ok": False, "error": "没有这个能力位：%s" % cap}
    new = [str(p).strip() for p in (phrases or []) if str(p).strip()]
    if not new:
        return {"ok": False, "error": "没有给出说法"}

    trial_ops = dict(ops)
    trial_ops[cap] = dict(ops[cap])
    trial_ops[cap]["phrases"] = list(ops[cap].get("phrases") or []) + new
    trial_ops[cap]["curated"] = True
    trial = {"operators": trial_ops}

    verdicts, bad = [], []
    for phrase in new:
        # ① 先看这词现在归谁 —— 已被别人稳稳占住就不许硬抢
        # topk=1 时 margin 恒为 0，会被判成「分不开」⇒ 占用检查永远不触发。必须看前两名。
        prev = rank(idx, phrase, topk=2)
        owner = ((prev["top"] or [{}])[0] or {}).get("cap")
        if owner and owner != cap and not prev.get("escalate"):
            row = {"phrase": phrase, "ok": False, "top1": owner,
                   "why": "已被 %s 占住；要改归属先 rm 那边的词" % owner}
            verdicts.append(row)
            bad.append(row)
            continue
        # ② 再看加上之后能不能稳赢
        r = rank(trial, phrase, topk=3)
        top = (r["top"] or [{}])[0]
        ok = (top.get("cap") == cap and (r.get("margin") or 0) >= 0.08)
        row = {"phrase": phrase, "ok": ok, "top1": top.get("cap"),
               "score": top.get("score"), "margin": r.get("margin"), "why": r.get("why")}
        verdicts.append(row)
        if not ok:
            bad.append(row)

    result = {"ok": not bad, "cap": cap, "phrases": new, "verdicts": verdicts,
              "applied": False}
    if bad:
        result["error"] = "有说法抢不过或被分不开，未写入"
        result["conflicts"] = bad
        return result
    if not apply:
        result["note"] = "只对打、未写入（加 --apply 才落盘）"
        return result

    cur = _curation()
    bucket = cur.setdefault(cap, [])
    for phrase in new:
        if phrase not in bucket:
            bucket.append(phrase)
    _write_curation(cur)
    write_atomic(INDEX, build())
    result["applied"] = True
    result["curation"] = cur.get(cap)
    return result


def uncurate(cap: str, phrases=None) -> dict:
    """撤词 / 清空该位的策展层（不动 desc 里的「常用说法」）。"""
    cur = _curation()
    if cap not in cur:
        return {"ok": False, "error": "策展层里没有这个位：%s" % cap}
    if phrases:
        drop = {str(p).strip() for p in phrases}
        cur[cap] = [p for p in cur[cap] if p not in drop]
        if not cur[cap]:
            cur.pop(cap, None)
    else:
        cur.pop(cap, None)
    _write_curation(cur)
    write_atomic(INDEX, build())
    return {"ok": True, "cap": cap, "remaining": cur.get(cap, []), "applied": True}


def _write_veto(veto_map: dict) -> None:
    """只动否决层。保留原有 caps/note，原子替换 + 读回校验。"""
    payload = {"schema": 1, "caps": {}, "veto": dict(veto_map or {})}
    if CURATION.exists():
        try:
            old = json.loads(CURATION.read_text(encoding="utf-8-sig"))
            if old.get("caps"):
                payload["caps"] = old["caps"]
            if old.get("note"):
                payload["note"] = old["note"]
        except Exception:
            pass
    payload.setdefault("note", "人工策展覆盖层：caps=加词，veto=摘掉过宽的词")
    write_atomic(CURATION, payload, key="veto")


def veto(cap: str, phrases, apply: bool = False) -> dict:
    """把某个说法从这一位上**摘掉**（不改词表，只改本层怎么看它）。

    前提钉死：该位现在必须真的有这个说法 —— 否决一个不存在的东西只是自欺。
    摘之前/之后各打一次分，把「谁接了手」写进回执，方便判断摘对了没有。
    """
    idx, stale = load()
    if idx is None:
        return {"ok": False, "error": stale}
    ops = idx.get("operators") or {}
    if cap not in ops:
        return {"ok": False, "error": "没有这个能力位：%s" % cap}
    have = set(ops[cap].get("phrases") or []) | set(ops[cap].get("iex") or {})
    want = [str(x).strip() for x in (phrases or []) if str(x).strip()]
    if not want:
        return {"ok": False, "error": "没有给出说法"}
    missing = [x for x in want if x not in have]
    if missing:
        return {"ok": False, "error": "该位现在没有这些说法，否决没有对象",
                "missing": missing, "have_sample": sorted(have)[:12]}

    trial_ops = dict(ops)
    trial_ops[cap] = dict(ops[cap])
    drop = set(want)
    trial_ops[cap]["phrases"] = [x for x in (ops[cap].get("phrases") or []) if x not in drop]
    trial_ops[cap]["iex"] = {k: v for k, v in (ops[cap].get("iex") or {}).items()
                             if k not in drop}
    if not (trial_ops[cap]["phrases"] or trial_ops[cap]["iex"]):
        trial_ops[cap]["curated"] = False
    trial = {"operators": trial_ops}

    def _own_score(res: dict, target: str):
        """这一位在那句话上的分数。不在前几名里就是 0 —— 那也说明它没证据。"""
        for row in (res.get("top") or []):
            if row.get("cap") == target:
                return row.get("score")
        return 0.0

    effect = []
    for phrase in want:
        a = rank(idx, phrase, topk=8)
        b = rank(trial, phrase, topk=8)
        effect.append({"phrase": phrase,
                       "before": ((a["top"] or [{}])[0] or {}).get("cap"),
                       "before_hit": bool((a["top"] or [{}])[0] or {}) and not a.get("escalate"),
                       "before_score": _own_score(a, cap),
                       "after": ((b["top"] or [{}])[0] or {}).get("cap"),
                       "after_hit": bool((b["top"] or [{}])[0] or {}) and not b.get("escalate"),
                       "after_score": _own_score(b, cap),
                       "after_why": b.get("why")})

    result = {"ok": True, "cap": cap, "phrases": want, "effect": effect, "applied": False}
    if not apply:
        result["note"] = "只试算、未写入（加 --apply 才落盘）"
        return result
    v = _veto()
    bucket = v.setdefault(cap, [])
    for phrase in want:
        if phrase not in bucket:
            bucket.append(phrase)
    _write_veto(v)
    write_atomic(INDEX, build())
    result["applied"] = True
    result["veto"] = v.get(cap)
    return result


def unveto(cap: str, phrases=None) -> dict:
    """撤销否决（说法回到该位）。不动 desc 与词表。"""
    v = _veto()
    if cap not in v:
        return {"ok": False, "error": "否决层里没有这个位：%s" % cap}
    if phrases:
        drop = {str(x).strip() for x in phrases}
        v[cap] = [x for x in v[cap] if x not in drop]
        if not v[cap]:
            v.pop(cap, None)
    else:
        v.pop(cap, None)
    _write_veto(v)
    write_atomic(INDEX, build())
    return {"ok": True, "cap": cap, "remaining": v.get(cap, []), "applied": True}


_QUOTED = re.compile(r"[「“]([^」”]{4,60})[」”]")


def _quoted_sentences() -> list:
    """从 `AGENTS.md` 与 `docs/*.md` 里取**主人自己写下的原话**（引号里的句子）。

    为什么要这一份：1042 条词表评测是「把它的词原样喂回去、看它认不认得」，
    接近循环论证。真话里的语序、口语、上下句都不在词表里 —— 那才是闸门将来
    要面对的输入。这份留出集不是造出来的，是仓里本来就有的。
    """
    srcs = [ROOT / "AGENTS.md"] + sorted((ROOT / "docs").rglob("*.md"))
    seen, out = set(), []
    for path in srcs:
        if not path.exists():
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except Exception:
            continue
        for m in _QUOTED.finditer(text):
            q = m.group(1).strip()
            if q in seen or not _CJK.search(q):
                continue
            if chr(10) in q or chr(13) in q:
                continue
            seen.add(q)
            out.append({"q": q, "from": str(path.relative_to(ROOT))})
    return out


def heldout(top: int = 20) -> dict:
    """真实句式上的发火读数。**不做判断，只报数** —— 对错要人看。

    分档口径（这就是两档证据的分界）：
      · `exact`：整句就等于一条策展词（score >= 1.0）—— 强证据；
      · `substring`：触发词被包在长句里（score < 1.0）—— 弱证据，
        也是实测里误判的来源（「别一直要我提醒你」→ reminder）。
    """
    items = _quoted_sentences()
    fired, bands = [], {"exact": 0, "substring": 0}
    for it in items:
        g = gate(it["q"])
        if not g.get("hit"):
            continue
        row = ((g.get("top") or [{}])[0] or {})
        score = float(row.get("score") or 0.0)
        band = "exact" if score >= 1.0 else "substring"
        bands[band] += 1
        fired.append({"q": it["q"], "from": it["from"], "cap": row.get("cap"),
                      "score": score, "band": band,
                      "source": row.get("source"), "margin": g.get("margin")})
    fired.sort(key=lambda r: -r["score"])
    n = len(items)
    return {"ok": True, "sentences": n, "fired": len(fired),
            "fire_pct": round(100.0 * len(fired) / n, 1) if n else None,
            "bands": bands,
            "sample": fired[:max(0, int(top))],
            "note": ("这是**弱标签**留出集：只量「会不会发火」和「发火时证据有多强」，"
                     "判对判错要人看。exact 档≈词表评测那个 99%，substring 档才是真句式的真相。")}


def seeds_report() -> dict:
    """12 条验收种子上的两套对账：算子闸门（能力位） vs route_method（触手方法）。

    两者**不是竞品**，是两个命名空间各自的守门人。这张表用来看谁该接哪一半，
    而不是拿一边的分数去改另一边的算法（那会造出第三处口径）。
    """
    try:
        from .tentacle import bridge as TB
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": "触手桥读不动：%s" % type(exc).__name__}
    from . import brain_exec as BE
    from .caps_registry import BENIGN_CAPS
    rows = []
    for q, want in TB.SEED_PHRASES:
        g = gate(q, topk=2)   # topk=1 时 margin 恒为 0，会永远弃权
        # `want` 是**方法名**，gate 答的是**能力位名**：两套名字空间不重叠，
        # 直接比大小只会得出「命中 3 / 正确 0」这种假失败。不可比就标 None。
        comparable = want in BENIGN_CAPS
        mf = BE._method_lane(q)
        got = ((g.get("top") or [{}])[0] or {}).get("cap")
        rm = TB.route_method(q)
        rows.append({
            "seed": q, "want": want,
            "gate_hit": bool(g.get("hit")), "gate_top1": got,
            "gate_comparable": comparable,
            "gate_ok": (bool(g.get("hit")) and got == want) if comparable else None,
            "method_top1": (rm.get("best") or {}).get("method"),
            "method_confident": bool(rm.get("confident")),
            "method_margin": rm.get("margin"),
            "method_ok": (rm.get("best") or {}).get("method") == want,
            "fast_method": ((mf or {}).get("best") or {}).get("method"),
            "fast_ok": bool(mf) and ((mf.get("best") or {}).get("method") == want),
        })
    fired = [r for r in rows if r["fast_method"]]
    conf = [r for r in rows if r["method_confident"]]
    conf_ok = [r for r in conf if r["method_ok"]]
    return {
        "ok": True,
        "seeds": len(rows),
        # 这 12 条是**方法空间**的验收种子；gate 只覆盖能力位空间，
        # 所以 hit=0 是预期（它该弃权），不是失败。
        "gate": {"hit": sum(1 for r in rows if r["gate_hit"]),
                 "correct": sum(1 for r in rows if r["gate_ok"] is True),
                 "wrong": sum(1 for r in rows if r["gate_ok"] is False),
                 "comparable": sum(1 for r in rows if r["gate_comparable"]),
                 "note": ("这 12 条是**方法空间**种子，能力位空间不可比 ⇒ "
                          "comparable=0 时 hit/correct 只作参考，不算失败")},
        "method_fast": {"fired": len(fired),
                        "correct": sum(1 for r in fired if r["fast_ok"]),
                        "gate": "read_only_whitelist",
                        "whitelist_size": len(BE._METHOD_FAST_SAFE)},
        "method": {"confident": len(conf),
                   "confident_correct": len(conf_ok),
                   "confident_precision_pct": (round(100.0 * len(conf_ok) / len(conf), 1)
                                               if conf else None)},
        "rows": rows,
        "note": ("gate 覆盖能力位、route_method 覆盖触手方法；两边名字空间不重叠。"
                 "快车道只放**只读方法白名单**（2026-11-05 晚修）：原先按"
                 "「观测类邻域」放行，实测漏掉 domain_type / domain_act / "
                 "clipboard_write / vision_stream_record 共 5 条真动作 —— "
                 "邻域回答的是「归哪个任务域」，不是「动不动手」。"),
    }


def main(argv=None) -> int:
    argv = list(sys.argv if argv is None else argv)
    op = (argv[1] if len(argv) > 1 else "check").strip().lower()
    if op == "build":
        obj = build()
        write_atomic(INDEX, obj)
        print("已写 %s | %d 个算子 | 已策展 %d | 待补 %d"
              % (INDEX, obj["count"], obj["curated"], obj["uncurated"]))
        return 0
    if op == "check":
        idx, stale = load()
        if idx is None:
            print("不可用：", stale)
            return 1
        if stale:
            print("注意：", stale)
        by = idx["coverage"]["by_domain"]
        print("operators=%d curated=%d uncurated=%d"
              % (idx["count"], idx["curated"], idx["uncurated"]))
        for d in sorted(by, key=lambda x: (-by[x]["total"], x)):
            t, c = by[d]["total"], by[d]["curated"]
            print("  %-14s %3d / %3d  %5.0f%%" % (d, c, t, 100.0 * c / t if t else 0.0))
        print("queue head:")
        for row in idx["queue"][:10]:
            print("  %-28s %-12s degree=%d" % (row["cap"], row["domain"], row["degree"]))
        return 0
    if op in ("add", "rm", "veto", "unveto"):
        if len(argv) < 4:
            print('用法：%s %s <cap> "说法1" ["说法2" ...] [--apply]'
                  % (argv[0], op))
            return 2
        cap, phrases = argv[2], argv[3:]
        apply = "--apply" in phrases
        phrases = [p for p in phrases if not p.startswith("--")]
        if op == "add":
            out = curate(cap, phrases, apply=apply)
        elif op == "rm":
            out = uncurate(cap, phrases if phrases else None)
        elif op == "veto":
            out = veto(cap, phrases, apply=apply)
        else:
            out = unveto(cap, phrases if phrases else None)
        print(json.dumps(out, ensure_ascii=False, indent=1))
        return 0 if out.get("ok") else 1
    if op == "heldout":
        n = 20
        for a in argv[2:]:
            if a.isdigit():
                n = int(a)
        print(json.dumps(heldout(n), ensure_ascii=False, indent=1))
        return 0
    if op == "seeds":
        print(json.dumps(seeds_report(), ensure_ascii=False, indent=1))
        return 0
    if op == "stats":
        print(json.dumps(stats(), ensure_ascii=False, indent=1))
        return 0
    if op == "score":
        args = [a for a in argv[2:] if not a.startswith("--")]
        if not args:
            print('用法：score "一句话" [--record]')
            return 2
        _t = time.perf_counter()
        r = gate(args[0])
        want_record = "--record" in argv
        if want_record:
            log_gate(args[0], r, (time.perf_counter() - _t) * 1000, src="manual")
        r["logged"] = want_record
        if not want_record:
            r["note"] = "干跑不落账；要计入命中率加 --record，或走真路由 brain_route"
        print(json.dumps(r, ensure_ascii=False, indent=1))
        return 0
    print('用法：build | check | stats | seeds | heldout [N] | score "一句话" | '
          'add <cap> "说法" [--apply] | rm <cap> ["说法"] | '
          'veto <cap> "说法" [--apply] | unveto <cap> ["说法"]')
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
