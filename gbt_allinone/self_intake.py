# -*- coding: utf-8 -*-
# gbt-capability: filesystem_write  ⬻ 开发者：自由的风 · GBT小土豆V8 · 永久钢印
"""未命中即取源 · 自递归改进（self_intake）

主人令（2026-10-15，逐字）：「要让她知道**在她的知识库未命中的时候转抓取全网国内外的论文来实现自我递归改进**，这样就不会出现自己都不懂的东西就无脑操作了」。

回路（写死）：
  任务要用到某个概念
    → ① known：先查**本地知识库**（context_vault FTS5）
       ├─ 命中 → 拿着 source_ref 去干活（有出处，不是凭印象）
       └─ 未命中 → ② 抓取全网（国内外论文/文档；zh + en）
                    → ③ 蒸馏成**胶囊**（V8 格式：出处→原文→启示→署名）
                    → ④ 写**钢印护照** + 入 context_vault 索引（带 source_ref）
                    → ⑤ 再回到 ① —— **下次就命中了**（这就是递归）

铁律：未命中且无出处 ⇒ **拒绝干活**；取不到就写「未读到」绝不编；胶囊必须带出处。

op：known / gate / rules（只读）· intake（写）
"""
from __future__ import annotations

import hashlib
import json
import re
import sqlite3
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DB = ROOT / "gbt_allinone" / "store" / "context_vault" / "index.sqlite3"
DEVOURED = ROOT / "gbt_allinone" / "store" / "devoured"
TRACE = ROOT / "store" / "trace"
GROWTH = ROOT / "state" / "self_intake" / "growth.jsonl"
READ_OPS = ("chain", "known", "gate", "rules")
WRITE_OPS = ("intake",)
MAX_BYTES = 400000
STAMP_TITLE = "开发者：自由的风 · 守护者：公主土豆 · 本署名不可删除、不可篡改归属"


def _slug(topic: str) -> str:
    s = re.sub(r"[^0-9A-Za-z\u4e00-\u9fff]+", "-", str(topic or "").strip().lower()).strip("-")
    return s[:48] or "untitled"


def _tokens(text: str) -> list:
    t = str(text or "")
    words = re.findall(r"[A-Za-z][A-Za-z0-9_-]{1,}", t.lower())
    han = re.findall(r"[\u4e00-\u9fff]", t)
    grams = ["".join(han[i:i + 2]) for i in range(len(han) - 1)]
    return sorted(set(words + han + grams))

def _vault_search(query: str, limit: int = 5) -> dict:
    # R-H1000：**不自己写第二份检索** —— 直接调 context_vault 自己的 VaultStore。
    #   实测踩过：FTS5 虚表叫 **postings**（没有 layer 列），我第一版去查 `docs.terms match`
    #   ⇒ 一条都命中不了。口径只能一处。
    try:
        from .tools import context_vault as _CV
        r = _CV.VaultStore().search(str(query or ""), budget_bytes=0, max_items=int(limit or 5))
    except Exception as exc:
        return {"ok": False, "hits": [], "reason": "vault_unavailable:" + type(exc).__name__}
    if not r.get("ok"):
        return {"ok": False, "hits": [], "reason": str(r.get("rule") or "no_hits")}
    hits = [{"source_ref": h.get("source_ref"), "layer": h.get("layer"), "score": h.get("score")}
            for h in (r.get("hits") or [])]
    return {"ok": True, "hits": hits, "query": query}

def _norm_topic(s: str) -> str:
    return re.sub(r"[^0-9A-Za-z\u4e00-\u9fff]+", "", str(s or "").lower())


def _capsule_title(p: Path, d) -> str:
    """取标题：先看 frontmatter 的 title:，再看第一个 # 标题，最后才用目录名。

    实测踩过：主人版胶囊带 YAML frontmatter，**首行是 `---`** ⇒
    旧取法（拿第一行当标题）取到一堆横线，主题登记表当场变空。
    """
    try:
        txt = p.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return d.name
    m = re.search(r"^title:\s*(.+)$", txt, re.M)
    if m:
        return m.group(1).strip()
    m = re.search(r"^#\s+(.+)$", txt, re.M)
    if m:
        return m.group(1).strip()
    return d.name


def _registered_topics() -> list:
    out = []
    if DEVOURED.is_dir():
        for d in sorted(DEVOURED.iterdir()):
            f = d / "absorbed_knowledge.md"
            if not f.is_file():
                continue
            try:
                _body = f.read_text(encoding="utf-8", errors="replace")[:4000]
            except OSError:
                _body = ""
            out.append({"slug": d.name, "title": _capsule_title(f, d), "capsule": str(f),
                        "body": _body})
    if GROWTH.is_file():
        try:
            for line in GROWTH.read_text(encoding="utf-8", errors="replace").splitlines():
                j = json.loads(line)
                out.append({"slug": j.get("slug"), "title": j.get("topic"),
                            "capsule": j.get("capsule")})
        except (OSError, ValueError):
            pass
    return out


def _direction(topic: str) -> dict:
    """取源**方向**：本地未命中时，先看这个概念**跟什么连在一起**（取 topic_web 图）。

    为什么要有这一步：“未命中 ⇒ 取源”如果没方向，就是**满网乱抓**；
    有了邻居，取源就带着**同现过的词**去问。取不到图就回空表（不编方向）。
    """
    try:
        from . import topic_web as _TW
        g = _TW._load()
    except Exception:
        return {}
    if not g:
        return {}
    toks = [x for x in _tokens(_norm_topic(topic)) if len(x) >= 2]
    if not toks:
        return {}
    anchors = []
    for n in (g.get("nodes") or []):
        nid = str(n.get("id") or "")
        low = nid.lower()
        if any(t in low or low in t for t in toks):
            anchors.append(n)
    if not anchors:
        return {}
    detail = []
    for a in anchors[:3]:
        nb = _TW.neighbors(a["id"], 5)
        detail.append({"anchor": a["id"], "axis": a.get("axis"),
                       "neighbors": [{"with": x["with"], "weight": x["weight"]}
                                     for x in (nb.get("neighbors") or [])]})
    terms = sorted({x["with"] for row in detail for x in row["neighbors"]})[:8]
    return {"anchors": [a["id"] for a in anchors[:3]], "detail": detail,
            "suggest_terms": terms,
            "note": "先问这些邻居（**有方向的取源**），不要满网乱抓"}

def known(topic: str = "") -> dict:
    t = str(topic or "").strip()
    if not t:
        return {"ok": False, "reason": "need_topic"}
    toks = [x for x in _tokens(_norm_topic(t)) if len(x) >= 2]
    if not toks:
        return {"ok": False, "known": False, "reason": "topic_too_short", "topic": t}
    best = None
    # R-H1006（2026-10-15 实测）：**先标题、后正文**，不一锅炖。
    #   病一：任取一个最长词当守卫 ⇒ “高智商 g因子”被取到‘商因’（标题里没有）全灭。
    #   病二：正文也算命中 ⇒ “高智商”竟命中了设计思维那份（它正文里提到过），串味。
    #   修法：① 守卫改成“**最长词里至少有一个命中**”（不抽单个）；
    #        ② **标题+slug 优先**，标题没中才回退到正文。
    toks_set = set(toks)
    _maxlen = max(len(x) for x in toks)

    def _score(hay: str):
        present = [x for x in toks if x in hay]
        cover = len(present) / len(toks)
        longest_ok = any(len(x) == _maxlen and x in hay for x in toks)
        return cover, present, longest_ok

    best = None
    for _pass in ("title", "body"):            # 标题先，正文后（两轮）
        for row in _registered_topics():
            hay = _norm_topic(str(row.get("title")) + " " + str(row.get("slug")))
            if _pass == "body":
                hay = _norm_topic(str(row.get("title")) + " " + str(row.get("slug")) + " " + str(row.get("body") or ""))
            if not hay:
                continue
            cover, present, longest_ok = _score(hay)
            if cover >= 0.6 and longest_ok:
                if best is None or cover > best[0] or (cover == best[0] and _pass == "title"):
                    best = (cover, row, present, _pass)
        if best:
            break
    if best:
        cover, row, present, _p = best
        return {"ok": True, "known": True, "topic": t, "basis": "registered_topic",
                "source_ref": row.get("capsule"), "matched": row.get("title"),
                "coverage": round(cover, 2), "matched_terms": present[:6], "matched_in": _p,
                "next_action": None}
    v = _vault_search(t)
    _dir = _direction(t)
    _out = {"ok": True, "known": False, "topic": t, "next_action": "intake",
            "hints": v.get("hits") or [], "vault_ok": bool(v.get("ok")),
            "rule": "本地未命中 ⇒ 不许无脑操作，转抓取全网取源",
            "hints_note": "下面只是**词面相似的提示**，不构成“知道”"}
    if _dir:
        _out["direction"] = _dir
    return _out


# 三胶囊联动（主人令 2026-10-15）：高智商定方向 → 设计思维定流程 → 美学定标准
CHAIN = [
    {"step": 1, "name": "高智商定方向", "capsule_id": "high-iq-g-factor",
     "keys": ["高智商", "g因子", "g factor"],
     "rule": "先判这活要不要高 g（统合力而非单项强）、要不要“平均高 + 一个极高”"},
    {"step": 2, "name": "设计思维定流程", "capsule_id": "design-thinking-dschool",
     "keys": ["设计思维", "d.school", "design thinking"],
     "rule": "共情 → 定义 → 构思 → 原型 → 测试"},
    {"step": 3, "name": "美学定标准", "capsule_id": "hume-aesthetics",
     "keys": ["休谟", "hume", "品味"],
     "rule": "strong sense + delicate sentiment + practice + comparison + no prejudice"},
]


def chain(topic: str = "") -> dict:
    """三胶囊联动检查（只读）—— **缺一件就不算齐**（fail-closed，不编“已齐”）。"""
    rows = _registered_topics()
    steps = []
    for spec in CHAIN:
        hit = None
        for row in rows:
            hay = _norm_topic(str(row.get("title")) + " " + str(row.get("slug")))
            if any(_norm_topic(k) in hay for k in spec["keys"]):
                hit = row
                break
        steps.append({"step": spec["step"], "name": spec["name"], "capsule_id": spec["capsule_id"],
                      "rule": spec["rule"], "present": bool(hit),
                      "capsule": (hit or {}).get("capsule"),
                      "matched": (hit or {}).get("title")})
    missing = [s["capsule_id"] for s in steps if not s["present"]]
    return {"ok": not missing, "op": "chain", "topic": str(topic or ""), "steps": steps,
            "missing": missing,
            "closure": ("三胶囊齐备 ⇒ 可按“方向→流程→标准”跑" if not missing else
                        "缺件，不许声称联动可用；先取源入册"),
            "next_action": (None if not missing else "intake"),
            "executor": "万能插（five-dim.py cap self_intake）"}

def gate(topic: str = "", source_ref: str = "") -> dict:
    t = str(topic or "").strip()
    if not t:
        return {"ok": False, "reason": "need_topic"}
    k = known(t)
    if k.get("known"):
        return {"ok": True, "basis": "local_kb", "topic": t, "hits": k.get("hits"),
                "detail": "本地知识库命中 ⇒ 可以干活（带出处）"}
    ref = str(source_ref or "").strip()
    if ref:
        p = (ROOT / ref) if not Path(ref).is_absolute() else Path(ref)
        if p.is_file():
            return {"ok": True, "basis": "source_ref", "topic": t, "source_ref": ref,
                    "detail": "本地未命中，但**已指定出处且在盘** ⇒ 可以干活（要引用）"}
        return {"ok": False, "denied": True, "rule": "source_ref_missing", "topic": t,
                "source_ref": ref, "detail": "给了出处但盘上没这件"}
    hint = "cap self_intake {" + chr(34) + "op" + chr(34) + ":" + chr(34) + "intake" + chr(34) + "," + chr(34) + "topic" + chr(34) + ":" + chr(34) + t + chr(34) + "," + chr(34) + "urls" + chr(34) + ":[...]}"
    _dir = _direction(t)
    return {"ok": False, "denied": True, "rule": "no_knowledge_no_source", "topic": t,
            "direction": (_dir or None),
            "detail": "**本地未命中、也没有出处 ⇒ 不许无脑操作**。先取源：",
            "how": hint, "next_action": "intake"}


def rules() -> dict:
    return {"ok": True, "op": "rules",
            "loop": ["known（先查本地知识库）",
                     "intake（未命中则抓取全网取源：国内外论文/文档）",
                     "distill（蒸馏成 V8 胶囊：出处→原文→启示）",
                     "stamp（写钢印护照 + 入 context_vault 索引）",
                     "known（再查 ⇒ 这次命中）"],
            "iron_laws": ["未命中且无出处 ⇒ 拒绝干活",
                          "取不到就写「未读到」，绝不编内容顶上",
                          "胶囊必须带出处；入库必须带 source_ref"],
            "growth_log": str(GROWTH).replace(chr(92), "/")}

def _clean_html(raw: str) -> str:
    t = re.sub(r"<script[\s\S]*?</script>", " ", raw or "", flags=re.I)
    t = re.sub(r"<style[\s\S]*?</style>", " ", t, flags=re.I)
    t = re.sub(r"<[^>]+>", " ", t)
    t = re.sub(r"&nbsp;|&#160;", " ", t)
    return re.sub(r"\s+", " ", t).strip()


def _fetch(url: str) -> dict:
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "GBT-V8-self-intake/1.0"})
        with urllib.request.urlopen(req, timeout=25) as resp:
            raw = resp.read(MAX_BYTES).decode("utf-8", "replace")
            code = getattr(resp, "status", 200)
        return {"ok": True, "url": url, "status": code, "text": _clean_html(raw), "bytes": len(raw)}
    except Exception as exc:
        return {"ok": False, "url": url, "error": "fetch_failed:" + type(exc).__name__,
                "detail": str(exc)[:160]}


def intake(topic: str = "", urls: list = None, files: list = None, note: str = "", lang: str = "") -> dict:
    t = str(topic or "").strip()
    if not t:
        return {"ok": False, "reason": "need_topic"}
    got, failed = [], []
    for u in (urls or []):
        u = str(u).strip()
        if not u:
            continue
        r = _fetch(u)
        (got if r.get("ok") else failed).append(r)
    for f in (files or []):
        p = (ROOT / f) if not Path(f).is_absolute() else Path(f)
        if p.is_file():
            got.append({"ok": True, "url": str(f), "status": "local",
                        "text": p.read_text(encoding="utf-8", errors="replace")[:MAX_BYTES]})
        else:
            failed.append({"ok": False, "url": str(f), "error": "file_missing"})
    if not got:
        return {"ok": False, "reason": "no_source_fetched", "topic": t, "failed": failed,
                "detail": "一个源都没取到 ⇒ **如实报未读到，不编内容**"}
    slug = _slug(t)
    d = DEVOURED / slug
    d.mkdir(parents=True, exist_ok=True)
    lines = ["# 胶囊 · " + t, "",
             "> 吞噬日期：" + time.strftime("%Y-%m-%d") + " ｜ 来源：未命中后取源（self_intake） ｜ 语言：" + (lang or "auto"),
             ">", "> " + STAMP_TITLE, "", "---", "", "## 一、取到的源", ""]
    for g in got:
        lines.append("- `" + str(g.get("url")) + "`（" + str(len(g.get("text") or "")) + " 字符）")
    if failed:
        lines += ["", "**未读到**（如实列出，不编）："]
        for f in failed:
            lines.append("- `" + str(f.get("url")) + "` ⇒ " + str(f.get("error")))
    lines += ["", "## 二、原文摘录（只摆原文，不转述）", ""]
    for g in got:
        lines.append("### " + str(g.get("url")))
        lines.append("")
        lines.append("> " + (g.get("text") or "").strip()[:1800])
        lines.append("")
    if str(note or "").strip():
        lines += ["## 三、人工补注", "", str(note).strip(), ""]
    lines += ["---", "", "> 本胶囊判据：每个源可点开 · 取不到的已如实列为「未读到」 · 署名不可删。",
             "", "> " + STAMP_TITLE, ""]
    capsule = d / "absorbed_knowledge.md"
    capsule.write_text("\n".join(lines), encoding="utf-8")
    data = capsule.read_bytes()
    sha = hashlib.sha256(data).hexdigest()
    TRACE.mkdir(parents=True, exist_ok=True)
    passport = TRACE / (slug + ".passport.json")
    passport.write_text(json.dumps({
        "gbt_stamp": {"framework": "GBT小土豆", "version": "8.0.0", "mark": "GBT",
                      "developer": "自由的风", "ownership": "independent-personal",
                      "note": "本作品由 GBT小土豆V8 框架生成 · 独立私人框架"},
        "publish": {"rec_id": slug + "-" + sha[:8], "sha256": sha, "actor": "self_intake",
                    "published_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
                    "purpose": "未命中取源: " + t, "version": 1, "refined_rounds": 0},
        "absorbed": {"capsule": str(capsule).replace(chr(92), "/"), "bytes": len(data), "sha256": sha},
        "trace": {"sources": [{"url": g.get("url"), "status": g.get("status")} for g in got],
                  "not_read": [{"url": f.get("url"), "why": f.get("error")} for f in failed]}},
        ensure_ascii=False, indent=2), encoding="utf-8")
    ref = str(passport.relative_to(ROOT)).replace(chr(92), "/")
    toks = _tokens(t + " " + " ".join((g.get("text") or "")[:3000] for g in got))
    indexed = False
    # 🔴 2026-10-29 主人令：「每次吞的时候要先在镜像多维度空间里面把东西
    #   **拆解、分析、跑通**再吸收，就不会有（吞到二道垃圾）这个弊端。」
    #
    #   实测缺这道门的后果：devour/self_intake 原来「取源 → 直接落胶囊 → 直接入库」，
    #   全网一旦被 AI 生成内容填满，我们就是二道垃圾的搬运工，而且没有分辨能力。
    #
    #   intake_gate 做五道机检（零模型零幻觉）：
    #     ① 拆解成原子主张  ② 分类（url/number/file/port/opinion）
    #     ③ 可现读验的**真跑一次**（来源还在不在 / 端口 / 文件）
    #     ④ 与本机既有知识比对  ⑤ 判决 pass/warn/reject + 逐条原因
    #
    #   判决**不吃掉原文**：胶囊照留（可复查），只是**不给它进知识库的资格**。
    gate = None
    try:
        sys.path.insert(0, str(ROOT / "tools"))
        import intake_gate as _IG
        import importlib as _il
        _il.reload(_IG)
        gate = _IG.judge(slug)
    except Exception as exc:                                  # noqa: BLE001
        gate = {"verdict": "warn", "reasons": ["闸跑不起来：%s" % type(exc).__name__]}
    if (gate or {}).get("verdict") == "reject":
        sys.stderr.write("[intake] 🔴 吸收被拒（%s）：%s\n"
                         % (slug, "；".join(gate.get("reasons") or [])))
        indexed = False
    else:
        try:
            from .tools import context_vault as _CV
            add = _CV.VaultStore().add(ref, " ".join(toks), "warm")
            indexed = bool(add.get("ok")) and int(add.get("terms") or 0) > 0
        except Exception:
            indexed = False
    GROWTH.parent.mkdir(parents=True, exist_ok=True)
    with GROWTH.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps({"at": time.strftime("%Y-%m-%dT%H:%M:%S"), "topic": t, "slug": slug,
                             "capsule": str(capsule).replace(chr(92), "/"), "sha256": sha,
                             "sources": len(got), "failed": len(failed), "indexed": indexed,
                             "terms": len(toks)}, ensure_ascii=False) + "\n")
    return {"ok": True, "op": "intake", "topic": t, "capsule": str(capsule), "sha256": sha,
            "passport": str(passport), "sources": len(got), "not_read": len(failed),
            "indexed": indexed, "terms": len(toks),
            "next": "再跑 known（" + t + "）应当命中"}


def run(op: str = "known", **kw) -> dict:
    o = (op or "known").strip().lower()
    if o == "chain":
        return chain(kw.get("topic", ""))
    if o == "known":
        return known(kw.get("topic", ""))
    if o == "gate":
        return gate(kw.get("topic", ""), kw.get("source_ref", ""))
    if o == "rules":
        return rules()
    if o == "intake":
        return intake(kw.get("topic", ""), kw.get("urls"), kw.get("files"), kw.get("note", ""), kw.get("lang", ""))
    return {"ok": False, "reason": "unknown_op", "op": o,
            "known": list(READ_OPS) + list(WRITE_OPS),
            "executor": "万能插（five-dim.py cap self_intake）—— 不许另起传统执行器",
            "detail": "未知 op 只回错（fail-closed）"}

