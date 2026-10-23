# gbt-capability: case_mine
# ⛔ 开发者：自由的风 · 永久钢印 · 禁止删除
"""案例挖掘：**公开盈利案例 → 结构化案例卡**（蒸馏自 starter story，只取"结构化案例库"架构）。

## 抓取口径（本仓规矩：凡抓取必写源·时间·口径）
· **源**：2026-10-01 主人给的站点截图（starter story 的 S 标）。站点页原文要点：
  「3,032+ real, revenue-generating projects — the tools they built on, how they grew」；
  「39 curated, filterable databases of real, profitable businesses — built for founders, not readers」；
  「The deepest interviews with real founders.」；公开数据入口 `starterstory.com/data`（"Live · Updating now"）。
· **时间**：2026-10-01。
· **口径**：**不复制原文全文**（版权）；只落**结构化字段 + 短引文（≤240 字）**，每条必带来源 URL 与抓取时间。

## 蒸馏判断：starter story 的核里我们真缺哪块
| 它的能力 | 我们已有的对位 | 结论 |
|---|---|---|
| 3000+ 项目库（营收 / 起步成本 / 工具 / 渠道 结构化） | 无（`topic_watch` 只追话题、`trend_watch` 只记爆款、`recon.last30days` 只取趋势） | **补这块**：案例卡 schema |
| 39 个可筛数据库（按类别挑） | 无 | **补**：按类别 / 关键词检索本地语料 |
| 长访谈（故事全文） | `media_run`（内容链）/ 电影产线 | 只取**结构字段**喂选题；**不搬全文** |
| 站点抓取（JS 重、有 robots） | 触手 `omni_web`（robots + 礼仪 + 自适应重定位，现成） | **复用，不造第二套抓取** |

## 硬规矩
1. **本件自己不发 HTTP**：取数一律经唯一门 `run_task('tentacle', {'action': 'web_read'/'web_fetch', …})`
   ⇒ 抓取礼仪与授权口径**只有一处**（触手那套），本件不新增第二套网络面。
2. **不编**：正文里读不到的字段落 `未读到`（`None` / `""`），**绝不用示例值顶**。
3. **不搬全文**：每条卡只留短引文（`EXCERPT_MAX`），全文不落盘。
4. **来源必带**：每条卡必须有 `source_url` + `fetched_at` + `text_sha256`（可溯源、可复验）。
5. **读不到就如实报**：语料为空 / 来源未登记 ⇒ 结构化拒绝（fail-closed），不返空即绿。
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

_EXCERPT_MAX = 240
_CAP = "case_mine"

# ── 登记源（只读公开页；取数走触手门，本件不发 HTTP）─────────────────────────
SOURCES = {
    "starterstory": {
        "url": "https://www.starterstory.com/data",
        "主页": "https://www.starterstory.com/",
        "是什么": "真实盈利项目库（营收/起步成本/工具/渠道）+ 39 个可筛数据库 + 长访谈",
        "口径": "原文自称 3,032+ projects · Free · 公开列表页 /data",
        "抓取方式": "run_task('tentacle', {'action':'web_read','url':…})（触手礼仪）",
    },
}


def _store_dir() -> Path:
    """store 基址：**env 优先（现读）** ⇒ `_paths.STORE_DIR` ⇒ 包内默认。

    🔴 env 优先是**故意**的：`_paths.STORE_DIR` 在导入期绑定一次，测试/多进程换 store
    时改不动它（实测：隔离 store 里的测试反而写进了默认 store）—— 所以这里**每次现读**。
    """
    env = __import__("os").getenv("GBT_STORE_DIR")
    if env:
        return Path(env) / _CAP
    try:
        from gbt_allinone._paths import STORE_DIR
        return Path(STORE_DIR) / _CAP
    except Exception:  # noqa: BLE001
        return ROOT / "gbt_allinone" / "store" / _CAP


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8", "replace")).hexdigest()


def _rel(p) -> str:
    """路径显示：**仓内则相对、仓外则绝对**（隔离 store 在仓外 —— relative_to 会抛）。"""
    try:
        return str(Path(p).relative_to(ROOT))
    except Exception:  # noqa: BLE001
        return str(p)


# ── 净值 / 字段抽取（确定性；读不到 ⇒ 未读到，不编）────────────────────────
_RE_MONEY = re.compile(r"\$ ?([0-9][0-9,.]*)\s*([KkMm])?\s*(?:/|per )?\s*(mo|month|monthly|yr|year|annual)?",
                       re.IGNORECASE)
_RE_URL = re.compile(r"https?://[^\s\"'<>)]+")


def _money(text: str):
    """→ (月营收字符串 or None, 原文片段)。只认带 `/mo`、`/month`、`MRR` 语境的数字。"""
    for m in _RE_MONEY.finditer(text or ""):
        tail = (text[m.end():m.end() + 12] or "").lower()
        unit = (m.group(3) or "").lower()
        if unit in ("mo", "month", "monthly") or "mrr" in tail or "per month" in tail:
            return m.group(0).strip(), text[max(0, m.start() - 40):m.end() + 20].strip()
    return None, ""


def _first(patterns, text):
    for p in patterns:
        m = re.search(p, text or "", re.IGNORECASE)
        if m:
            return m.group(0).strip()[:120]
    return None


def ingest(text: str, source_url: str, source_key: str = "starterstory",
           name: str = "", category: str = "", limit: int = 40) -> dict:
    """**离线可测**：正文（触手取回的）→ 案例卡列表。读不到的字段落 `未读到`。"""
    if not str(text or "").strip():
        return {"ok": False, "fail_closed": True, "error": "正文为空 ⇒ 不给卡（不编案例）"}
    if not str(source_url or "").strip():
        return {"ok": False, "fail_closed": True, "error": "缺 source_url ⇒ 卡无法溯源，拒"}
    fetched_at = time.strftime("%Y-%m-%dT%H:%M:%S")
    sha = _sha(text)
    cards = []
    # 卡片切分：优先按行块；找不到结构 ⇒ 落一张"整页卡"并如实标注 field_gaps
    blocks = [b.strip() for b in re.split(r"\n{2,}", text) if b.strip()]
    if not blocks:
        blocks = [text.strip()]
    for b in blocks[:max(1, int(limit))]:
        revenue, rev_ev = _money(b)
        urls = _RE_URL.findall(b)
        started = _first([r"(?:started|launched|began)[^.]{0,60}", r"起步[^。]{0,40}"], b)
        tools = _first([r"(?:tools?|stack|built (?:on|with))[^.]{0,80}"], b)
        channels = _first([r"(?:growth|channels?|traffic|marketing)[^.]{0,80}"], b)
        # 名字：块首行去掉 URL 后若是个短行（2–60 字）⇒ 就是名字；否则如实「未读到」
        _first_line = (b.splitlines() or [""])[0]
        _cand = _RE_URL.sub("", _first_line).strip(" -|·:：\t")
        _name = (name or "").strip() or (_cand if 2 <= len(_cand) <= 60 else "") or "未读到"
        card = {
            "name": _name,
            "category": (category or "").strip() or "未读到",
            "monthly_revenue": revenue or "未读到",
            "revenue_evidence": rev_ev[:160],
            "started": started or "未读到",
            "tools": tools or "未读到",
            "channels": channels or "未读到",
            "links": urls[:3],
            "excerpt": b[:_EXCERPT_MAX],
            "excerpt_truncated": len(b) > _EXCERPT_MAX,
            "source_key": source_key,
            "source_url": source_url,
            "fetched_at": fetched_at,
            "text_sha256": sha,
        }
        cards.append(card)
    return {"ok": True, "op": "ingest", "cards": cards, "n": len(cards),
            "_口径": "只留结构化字段 + 短引文（≤%d 字）；全文不落盘；读不到落『未读到』" % _EXCERPT_MAX}


def save(cards: list, source_key: str = "starterstory") -> dict:
    """追加落盘（去重按 text_sha256+excerpt 前缀；**只追加**）。"""
    d = _store_dir()
    d.mkdir(parents=True, exist_ok=True)
    f = d / "cases.jsonl"
    seen = set()
    if f.is_file():
        for line in f.read_text(encoding="utf-8", errors="replace").splitlines():
            try:
                r = json.loads(line)
                seen.add((r.get("text_sha256"), (r.get("excerpt") or "")[:60]))
            except Exception:  # noqa: BLE001
                continue
    added, skipped = 0, 0
    with f.open("a", encoding="utf-8") as fh:
        for c in (cards or []):
            key = (c.get("text_sha256"), (c.get("excerpt") or "")[:60])
            if key in seen:
                skipped += 1
                continue
            fh.write(json.dumps(c, ensure_ascii=False) + "\n")
            seen.add(key)
            added += 1
    return {"ok": True, "op": "save", "added": added, "skipped": skipped, "file": _rel(f)}


def search(q: str = "", category: str = "", limit: int = 20) -> dict:
    """本地语料检索（只读）：关键词命中 name/tools/channels/excerpt。"""
    f = _store_dir() / "cases.jsonl"
    if not f.is_file():
        return {"ok": True, "op": "search", "hits": [], "n": 0,
                "note": "语料还空（先 fetch+ingest+save）——**空不是绿**，是没有料"}
    ql = str(q or "").lower().strip()
    cat = str(category or "").strip()
    hits = []
    for line in f.read_text(encoding="utf-8", errors="replace").splitlines():
        try:
            r = json.loads(line)
        except Exception:  # noqa: BLE001
            continue
        if cat and str(r.get("category") or "") != cat:
            continue
        blob = " ".join(str(r.get(k) or "") for k in ("name", "tools", "channels", "excerpt", "monthly_revenue")).lower()
        if ql and ql not in blob:
            continue
        hits.append(r)
    return {"ok": True, "op": "search", "hits": hits[:max(1, int(limit))], "n": len(hits),
            "source": _rel(f)}


def fetch(url: str, source_key: str = "starterstory", keyword: str = "") -> dict:
    """**经唯一门**取公开页正文（本件不发 HTTP）：调用触手 web_read。"""
    try:
        from gbt_allinone import api
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": "api 不可用：%s" % str(exc)[:80]}
    payload = {"action": "web_read", "url": str(url)}
    if keyword:
        payload["text"] = str(keyword)
    r = api.run_task("tentacle", payload, safe=True)
    if not isinstance(r, dict):
        return {"ok": False, "error": "触手回形不对：%s" % type(r).__name__}
    if r.get("denied") is True or str(r.get("status")) == "denied":
        return {"ok": False, "fail_closed": True, "gated": True,
                "missing_scopes": r.get("missing_scopes") or r.get("scopes"),
                "how_to_grant": "经主人终端：py -3.14 -m gbt_allinone auth grant --scope desktop_control --ttl 600"}
    inner = ((r.get("gbt_result") or {}).get("result")
             if isinstance(r.get("gbt_result"), dict) else None) or r.get("result") or {}
    text = inner.get("text") or inner.get("full_text") or ""
    if not text:
        return {"ok": False, "error": "触手取回无正文（如实报缺，不编）", "raw_keys": sorted(inner)[:8]}
    return {"ok": True, "op": "fetch", "url": str(url), "text": text, "chars": len(text),
            "via": "run_task('tentacle', web_read)（唯一门）"}


def sources() -> dict:
    return {"ok": True, "op": "sources", "sources": SOURCES,
            "_口径": "只读公开页；取数一律经唯一门（触手 web_read）；本件自己不发 HTTP"}


def where(**_kw) -> dict:
    return {"ok": True, "op": "where", "kind": _CAP, "tentacle": _CAP,
            "entry": "run_task('case_mine', {...})",
            "ops": ["sources", "fetch", "ingest", "save", "search", "where"],
            "distilled_from": "2026-10-01 主人给的站点截图 starter story（真实盈利项目库 + 39 可筛库 + 长访谈）"
                              "——只取**结构化案例库**架构（字段 schema + 类别检索 + 来源可溯源）",
            "not_copied": "不搬它的站点/前端/全文访谈（版权）；抓取不另造一套 —— 走触手 omni_web（robots + 礼仪现成）",
            "hard_rules": ["本件自己不发 HTTP（取数经唯一门 run_task('tentacle', web_read)）",
                           "不编：读不到的字段落『未读到』",
                           "不搬全文：只留结构化字段 + 短引文（≤%d 字）" % _EXCERPT_MAX,
                           "来源必带：source_url + fetched_at + text_sha256",
                           "语料为空如实报『没料』（空 ≠ 绿）"],
            "files": {"语料": _rel(_store_dir()) + "/cases.jsonl"},
            "contract": [
                {"op": "sources", "params": "—", "returns": "登记源与抓取口径"},
                {"op": "fetch", "params": "url + [keyword]", "returns": "经门取回的正文（chars）"},
                {"op": "ingest", "params": "text + source_url + [name/category]", "returns": "结构化案例卡（离线可测）"},
                {"op": "save", "params": "cards", "returns": "追加落盘（去重，只追加）"},
                {"op": "search", "params": "[q] + [category]", "returns": "本地语料命中（只读）"},
            ]}


def run_op(op: str = "sources", **params) -> dict:
    op = (op or "sources").lower()
    for n, fn in (("sources", sources), ("fetch", fetch), ("ingest", ingest),
                  ("save", save), ("search", search), ("where", where)):
        if op == n:
            return fn(**params)
    return {"ok": False, "fail_closed": True,
            "error": "未知 op:%s（sources/fetch/ingest/save/search/where）" % op}


if __name__ == "__main__":                                     # 主人的终端入口
    import argparse
    ap = argparse.ArgumentParser(description="案例挖掘（starter story 架构蒸馏 · 结构化案例卡）")
    ap.add_argument("cmd", nargs="?", default="sources")
    ap.add_argument("--url", default="")
    ap.add_argument("--text", default="")
    ap.add_argument("--q", default="")
    ap.add_argument("--category", default="")
    a = ap.parse_args()
    if a.cmd == "fetch":
        out = run_op("fetch", url=a.url)
    elif a.cmd == "ingest":
        out = run_op("ingest", text=open(a.text, encoding="utf-8").read() if a.text else "", source_url=a.url)
    elif a.cmd == "search":
        out = run_op("search", q=a.q, category=a.category)
    else:
        out = run_op(a.cmd)
    print(json.dumps(out, ensure_ascii=False, indent=1))
