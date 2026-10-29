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
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DB = ROOT / "gbt_allinone" / "store" / "context_vault" / "index.sqlite3"
DEVOURED = ROOT / "gbt_allinone" / "store" / "devoured"
TRACE = ROOT / "store" / "trace"
GROWTH = ROOT / "state" / "self_intake" / "growth.jsonl"
READ_OPS = ("chain", "known", "gate", "rules", "plan", "batch", "rejudge", "ledger")
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
                     "plan（零写盘预演：下载+前闸判定，不落盘）",
                     "intake（取源 → 前闸 → 入库；真吞才落盘）",
                     "batch（批量幂等：同 topic 同源已吞过就跳过）",
                     "ledger（看账）+ rejudge（闸改后重判历史账）"],
            "iron_laws": ["只吞有出处的",
                          "必过前闸（_vet_source 规则级 + 可选 _verify_knowledge 模型级）",
                          "幂等（同 topic 同源已吞过不重复）",
                          "每步落盘（胶囊/护照/账本）",
                          "判不了就写拒（unavailable 不否决、unverified 不进索引）"],
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


# ── 入库验证门（2026-10-29 主人指出的「最大的隐患」）────────────────────────
# 🔴 隐患：intake 原来**取到就入库**，不区分「来源死了」和「内容坏了」。
#   fetch 200 但内容是反爬页/登录页/错误页 ⇒ 照样写胶囊、进索引 ⇒ 吞进垃圾知识。
#   现在：入库前过一道**规则级**验证门（零成本、不调模型、不转述），
#   把「取到的源」分成 accepted（验收）与 vetoed（取到但无效）两栏，
#   两者都**如实列出**（不编、不删），但只有 accepted 进索引。
#   同构于「先过镜像再进生产」：先验证，再入库。
_VET_MIN_CHARS = 60          # 清洗后正文字符数下限（低于 = 疑似空壳/反爬）
_VET_BLOCK_MAX_CHARS = 500   # 拦截词只在「短内容」里判：长文档提到 cloudflare 是正常引用，不是反爬页
_VET_BLOCK_PATTERNS = [       # 命中任一 = 疑似登录页/错误页/反爬（窄口径，避免误伤正文）
    "captcha", "verify you are human", "cloudflare", "just a moment",
    "access denied", "forbidden", "not found", "page not found",
    "please enable javascript", "enable javascript",
    "登录", "验证码", "请登录", "页面不存在", "访问被拒绝",
]


def _vet_source(text: str) -> tuple:
    """**纯函数**：验证一条取到的源够不够格当「有效知识」，返回 (verdict, why)。

    verdict ∈ ok / empty_shell / login_or_error。
    🔴 这是「取源 → 入库」之间的**验证门** —— 不转述、不改内容，只判这段原文
       能不能入库。它与「来源死」是**两回事**：fetch 抛异常 = 来源死（如实列「未读到」）；
       这里判的是「fetch 成功但内容是垃圾」= 内容坏（列「取到但无效」）。
    🔴 拦截词只在「短内容」里判（`_VET_BLOCK_MAX_CHARS` 以内）：反爬页/登录页是**短提示**；
       长文档正文里提到 cloudflare / 登录 是**正常引用**，若按子串命中会误伤（AGENTS.md 实测）。
    """
    t = re.sub(r"\s+", " ", str(text or "")).strip()
    if len(t) < _VET_MIN_CHARS:
        return "empty_shell", "清洗后仅 %d 字符，疑似空壳/反爬（下限 %d）" % (len(t), _VET_MIN_CHARS)
    if len(t) < _VET_BLOCK_MAX_CHARS:
        low = t.lower()
        for pat in _VET_BLOCK_PATTERNS:
            if pat in low:
                return "login_or_error", "命中拦截特征 %r（疑似登录页/错误页/反爬）" % pat
    return "ok", ""


# ── 模型级验真（新能力 · 2026-10-29）───────────────────────────────────────
# 🔴 GBT 深度思考里说的「拆解→分析→跑通→吸收」，规则级验证门只挡「空壳/登录页」，
#   挡不住「空话/感慨/营销文案」这类**看着有字、其实不可对账**的内容。
#   这一道用**免费车道 Kilo** 判「能不能对账」：可复现的方法/可查证的事实/可执行的操作。
#   不转述、不改内容，只给 verdict；免费车道不在位/模型挂了 ⇒ unavailable（不假装验证过）。
_VERIFY_PROMPT = (
    "判断下面这段内容是不是「能对账的知识」。能对账 = 含可复现的方法、可查证的事实、"
    "可执行的操作或可引用的出处；不能对账 = 空话、感慨、营销文案、无法验证的断言。\n"
    "只回一个词：verified 或 unverified。不要解释、不要别的字。\n\n"
    "主题：%s\n\n内容：\n%s"
)


def _parse_verdict(reply: str) -> tuple:
    """**纯函数**：解析模型验真返回，提取 (verdict, why)。

    verdict ∈ verified / unverified / unavailable。fail-closed：读不出 ⇒ unavailable。
    🔴 先判 unverified 再判 verified —— unverified 含 verified 子串，顺序反了会把
       「不可对账」判成「可对账」（同族错误：先判 shadowed 会丢掉真依赖）。
    """
    r = str(reply or "").strip()
    if not r:
        return "unavailable", "模型空回"
    low = r.lower()
    if "unverified" in low or any(k in low for k in
                                  ("不可对账", "不可复现", "空话", "感慨", "营销", "不通过", "unverifiable")):
        return "unverified", r[:200]
    if "verified" in low or any(k in low for k in ("可对账", "可复现", "可查证", "通过")):
        return "verified", r[:200]
    return "unavailable", "判定读不出：" + r[:80]


def _verify_knowledge(topic: str, text: str) -> tuple:
    """模型级验真：用**免费车道 Kilo** 判这段知识能不能对账，返回 (verdict, why)。

    verdict ∈ verified / unverified / unavailable。
    🔴 fail-closed：免费车道不在位 / 模型挂了 ⇒ unavailable（不假装验证过，也不静默放行）。
    """
    try:
        from .llm import key_gateway as _kg
        mat = _kg.materialize("kilo")
        if not mat.get("ok"):
            return "unavailable", "免费车道不在位：" + str(mat.get("error"))
        from .llm import cloud_llm as _cl
        body = {"messages": [{"role": "user",
                              "content": _VERIFY_PROMPT % (str(topic or ""), (text or "")[:3000])}],
                # kilo-auto/free 是推理模型：reasoning 会吃 token，给足 512 才有 content 空间
                # （实测 80 会被 reasoning 吃光 → content 空 → 上游 200 但空答）。
                "max_tokens": 512, "temperature": 0.0}
        reply = _cl._call_once(mat["wire"], mat["url"], mat["model"], mat["key"],
                               body, "", "", 45, "kilo")
        return _parse_verdict(reply)
    except Exception as exc:
        return "unavailable", "验真失败：" + type(exc).__name__ + ":" + str(exc)[:80]


def intake(topic: str = "", urls: list = None, files: list = None, note: str = "",
           lang: str = "", verify: bool = False, items: list = None) -> dict:
    if items:
        # 批量幂等（GBT 说的 batch）：同 topic 同源已吞过就跳过，其余逐个走单个 intake。
        results = []
        for _item in items:
            _item = _item or {}
            _t = str(_item.get("topic", "")).strip()
            if not _t:
                results.append({"ok": False, "reason": "need_topic", "item": _item})
                continue
            _already = _devoured_sources(_t)
            _urls = [str(u).strip() for u in (_item.get("urls") or []) if str(u).strip()]
            _new = [u for u in _urls if u not in _already]
            if _urls and not _new:
                results.append({"ok": True, "topic": _t, "status": "skipped",
                                "why": "同 topic 同源已吞过（幂等跳过）"})
                continue
            _r = intake(_t, _new, _item.get("files"), _item.get("note", ""),
                        _item.get("lang", ""), verify=verify)
            results.append({"topic": _t, **_r})
        return {"ok": True, "op": "batch", "count": len(results),
                "吞了": sum(1 for r in results if r.get("ok") and r.get("op") == "intake"),
                "跳过": sum(1 for r in results if r.get("status") == "skipped"),
                "拒": sum(1 for r in results if not r.get("ok")),
                "results": results}
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
    # ── 入库验证门：把「取到的源」拆成 accepted（验收）与 vetoed（取到但无效）──
    accepted, vetoed = [], []
    for g in got:
        g["vet"], g["vet_why"] = _vet_source(g.get("text") or "")
        (accepted if g["vet"] == "ok" else vetoed).append(g)
    if not accepted:
        return {"ok": False, "reason": "all_sources_vetoed", "topic": t,
                "vetoed": [{"url": g.get("url"), "why": g.get("vet_why")} for g in vetoed],
                "failed": [{"url": f.get("url"), "why": f.get("error")} for f in failed],
                "detail": "源全被验证门拦下（疑似空壳/登录页/错误页）⇒ 不写胶囊、不吞垃圾"}
    # ── 模型级验真（可选，默认关——不花钱；显式 verify=True 才调免费车道 Kilo）──
    #   verified 进索引；unverified 保留原文但不进索引；unavailable 如实记（免费车道挂，不硬否决）。
    verified, unverified = [], []
    if verify:
        for g in accepted:
            g["verify"], g["verify_why"] = _verify_knowledge(t, g.get("text") or "")
            (verified if g["verify"] == "verified" else unverified).append(g)
    else:
        verified = accepted
    slug = _slug(t)
    d = DEVOURED / slug
    d.mkdir(parents=True, exist_ok=True)
    lines = ["# 胶囊 · " + t, "",
             "> 吞噬日期：" + time.strftime("%Y-%m-%d") + " ｜ 来源：未命中后取源（self_intake） ｜ 语言：" + (lang or "auto"),
             ">", "> " + STAMP_TITLE, "", "---", "", "## 一、取到的源", ""]
    for g in accepted:
        lines.append("- `" + str(g.get("url")) + "`（" + str(len(g.get("text") or "")) + " 字符）")
    if vetoed:
        lines += ["", "**取到但无效**（被验证门拦下，如实列出，不编、不索引）："]
        for g in vetoed:
            lines.append("- `" + str(g.get("url")) + "` ⇒ " + str(g.get("vet_why")))
    if failed:
        lines += ["", "**未读到**（网络/来源死，如实列出，不编）："]
        for f in failed:
            lines.append("- `" + str(f.get("url")) + "` ⇒ " + str(f.get("error")))
    lines += ["", "## 二、原文摘录（只摆原文，不转述）", ""]
    for g in accepted:
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
        "trace": {"sources": [{"url": g.get("url"), "status": g.get("status"), "vet": g.get("vet"),
                              "verify": g.get("verify")} for g in accepted],
                  "vetoed": [{"url": g.get("url"), "why": g.get("vet_why")} for g in vetoed],
                  "unverified": [{"url": g.get("url"), "why": g.get("verify_why")}
                                 for g in unverified],
                  "not_read": [{"url": f.get("url"), "why": f.get("error")} for f in failed]}},
        ensure_ascii=False, indent=2), encoding="utf-8")
    ref = str(passport.relative_to(ROOT)).replace(chr(92), "/")
    toks = _tokens(t + " " + " ".join((g.get("text") or "")[:3000] for g in verified))
    indexed = False
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
                             "sources": len(accepted), "vetoed": len(vetoed),
                             "verified": len(verified), "unverified": len(unverified),
                             "failed": len(failed),
                             "indexed": indexed, "terms": len(toks)}, ensure_ascii=False) + "\n")
    return {"ok": True, "op": "intake", "topic": t, "capsule": str(capsule), "sha256": sha,
            "passport": str(passport), "sources": len(accepted), "vetoed": len(vetoed),
            "verified": len(verified), "unverified": len(unverified),
            "not_read": len(failed),
            "indexed": indexed, "terms": len(toks),
            "verify": [{"url": g.get("url"), "verdict": g.get("verify"), "why": g.get("verify_why")}
                       for g in accepted] if verify else None,
            "next": "再跑 known（" + t + "）应当命中"}


def _devoured_sources(topic: str) -> set:
    """幂等依据：某 topic 已吞过的源 URL 集合（读 passport.trace.sources）。"""
    slug = _slug(topic)
    p = TRACE / (slug + ".passport.json")
    if not p.is_file():
        return set()
    try:
        d = json.loads(p.read_text(encoding="utf-8"))
        return {str(s.get("url")) for s in ((d.get("trace") or {}).get("sources") or [])
                if s.get("url")}
    except Exception:
        return set()


def plan(topic: str = "", urls: list = None, files: list = None, verify: bool = False) -> dict:
    """**零写盘预演**：自己下载 + 自己判，但**不落胶囊、不入库、不记账**。

    🔴 这是 GBT 说的「plan 假预演」的正解：上一版 plan 复用 intake ⇒ 必然落盘，
       回执里还写着「入库=是」。这里只 fetch + 前闸（+ 可选验真），回执写清
       「如果 run 会吞哪些 / 拒哪些」，**账不多一条**。
    """
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
        return {"ok": False, "reason": "no_source_fetched", "topic": t,
                "failed": [{"url": f.get("url"), "why": f.get("error")} for f in failed]}
    verdicts, would_accept, would_veto = [], 0, 0
    for g in got:
        v, why = _vet_source(g.get("text") or "")
        if v != "ok":
            verdicts.append({"url": g.get("url"), "verdict": v, "why": why, "action": "拒"})
            would_veto += 1
            continue
        if verify:
            vv, vwhy = _verify_knowledge(t, g.get("text") or "")
            act = ("吞" if vv == "verified" else
                   ("吞(验真不可用)" if vv == "unavailable" else "参考标记(不进索引)"))
            verdicts.append({"url": g.get("url"), "verdict": vv, "why": vwhy, "action": act})
            would_accept += 1
        else:
            verdicts.append({"url": g.get("url"), "verdict": v, "why": "", "action": "吞"})
            would_accept += 1
    return {"ok": True, "op": "plan", "topic": t,
            "预演": {"会吞": would_accept, "会拒": would_veto, "未读到": len(failed)},
            "verdicts": verdicts,
            "_口径": "零写盘：只下载+判定，不落胶囊、不入库、不记账；run 才真正落盘"}


def batch(items: list = None, verify: bool = False) -> dict:
    """批量**计划**（零写盘）：对每个 item 做幂等判断 + 预演，返回「该吞 / 跳过 / 会拒」。

    🔴 真吞 = 对「该吞」的逐个走 intake（`op=intake` + `items`，挂 filesystem_write 门）。
       batch 本身零写盘、零作用域，只出计划 —— 这样写盘门不会被「batch」这个名字绕过。
    """
    out = []
    for item in (items or []):
        item = item or {}
        topic = str(item.get("topic", "")).strip()
        if not topic:
            out.append({"topic": topic, "action": "拒", "why": "need_topic"})
            continue
        already = _devoured_sources(topic)
        urls = [str(u).strip() for u in (item.get("urls") or []) if str(u).strip()]
        # files 的源标识与 intake 一致：url 写的就是 str(f)（原始传入路径）
        file_ids = [str(f) for f in (item.get("files") or []) if str(f).strip()]
        all_sources = urls + file_ids
        new_urls = [u for u in urls if u not in already]
        new_files = [f for f in (item.get("files") or []) if str(f).strip() and str(f) not in already]
        skipped = [s for s in all_sources if s in already]
        if all_sources and not (new_urls or new_files):
            out.append({"topic": topic, "action": "跳过", "why": "同 topic 同源已吞过（幂等）",
                        "skipped": skipped})
            continue
        plan_r = plan(topic, new_urls, new_files, verify=verify)
        out.append({"topic": topic,
                    "action": ("吞" if plan_r.get("ok") else "拒"),
                    "skipped": skipped, "plan": plan_r})
    return {"ok": True, "op": "batch", "count": len(out),
            "该吞": sum(1 for x in out if x.get("action") == "吞"),
            "跳过": sum(1 for x in out if x.get("action") == "跳过"),
            "会拒": sum(1 for x in out if x.get("action") == "拒"),
            "results": out,
            "_口径": "零写盘：只出计划（幂等 + 预演）；真吞 = op=intake + items"}


def ledger(topic: str = "") -> dict:
    """看账：列每条吞噬记录（每条的 topic/时间/来源数/判定/入库）。"""
    rows = []
    if GROWTH.is_file():
        try:
            for line in GROWTH.read_text(encoding="utf-8", errors="replace").splitlines():
                if not line.strip():
                    continue
                j = json.loads(line)
                if topic and str(topic).strip() not in str(j.get("topic", "")):
                    continue
                rows.append(j)
        except (OSError, ValueError):
            pass
    return {"ok": True, "op": "ledger", "count": len(rows), "rows": rows}


def _capsule_excerpts(capsule: str) -> str:
    """抽出胶囊里的「原文摘录」段（## 二 之后），供 rejudge 重判。抽不到回空串。

    🔴 边界用 `^## (?!#)`（行首 ## 且后面不是 #）——裸 `## ` 会误匹配 `### https://…`
       三级标题里的 `## `（第二个#+第三个#+空格），导致抽取在第一个 `###` 处就断掉，
       rejudge 把整段长原文判成「仅 1 字符」（WCAG 胶囊实测踩过）。
    """
    try:
        txt = Path(capsule).read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""
    m = re.search(r"## 二、原文摘录[^\n]*\n(.*?)(?=^## (?!#)|\Z)", txt, re.S | re.M)
    if not m:
        return ""
    lines = [ln[2:].strip() if ln.startswith("> ") else ln.strip() for ln in m.group(1).splitlines()]
    return "\n".join(x for x in lines if x).strip()


def rejudge() -> dict:
    """用**新前闸**重判历史账：读已吞胶囊的原文摘录，重新过 `_vet_source`，报差异。

    🔴 只读 + 报，**不自动改历史账**（改历史是主人决策；本 op 只回答「按新判据哪些会拒」）。
    """
    rows = [r for r in _registered_topics() if r.get("capsule")]
    diff = []
    for row in rows:
        exc = _capsule_excerpts(row.get("capsule", ""))
        if not exc:
            continue
        v, why = _vet_source(exc)
        if v != "ok":
            diff.append({"slug": row.get("slug"), "title": row.get("title"),
                         "verdict": v, "why": why, "capsule": row.get("capsule")})
    return {"ok": True, "op": "rejudge", "重判": len(rows), "会拒": len(diff),
            "diff": diff, "_口径": "只读+报差异；不自动改历史账"}


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
    if o == "plan":
        return plan(kw.get("topic", ""), kw.get("urls"), kw.get("files"), verify=bool(kw.get("verify")))
    if o == "ledger":
        return ledger(kw.get("topic", ""))
    if o == "rejudge":
        return rejudge()
    if o == "batch":
        # 批量计划（零写盘）：幂等 + 预演；真吞走 intake+items（有 filesystem_write 门）
        return batch(kw.get("items"), verify=bool(kw.get("verify")))
    if o == "intake":
        return intake(kw.get("topic", ""), kw.get("urls"), kw.get("files"), kw.get("note", ""),
                      kw.get("lang", ""), verify=bool(kw.get("verify")))
    return {"ok": False, "reason": "unknown_op", "op": o,
            "known": list(READ_OPS) + list(WRITE_OPS),
            "executor": "万能插（five-dim.py cap self_intake）—— 不许另起传统执行器",
            "detail": "未知 op 只回错（fail-closed）"}

