# -*- coding: utf-8 -*-
# gbt-capability: context_inject  ⛔ 开发者：自由的风 · GBT小土豆V8 · 永久钢印
"""上下文注入（context_inject）—— 我们自己的 P1 选择器。

对照上游参考项目的 ACI / 动态上下文注入 / 预取缓存 / UI 信号：
只蒸**选择判据**，不搬它的 SQLite/embedding。

输入：query + 候选（记忆 / 最近对话 / UI 信号 / 工具结果 / 预取缓存），各有 at/ttl/priority/source；
输出：有预算上限的选中项 + 丢弃原因 + 来源/字符账。纯确定性（无模型/无出网/无写盘）：
  · 过期（at+ttl < now）直接丢；
  · 去重（text/内容相同只留最高分）；
  · 相关度 = query 字符 trigram 覆盖 + 命中加分；再加来源优先级/新鲜度；
  · 来源配额（同一 source 最多 1/3），保证多样性；
  · 打包不超 budget，最多 40 条；无 query 时按优先级/新鲜度。
"""
from __future__ import annotations

import hashlib
import re
import time

DEFAULT_BUDGET = 3000
MIN_BUDGET = 200
MAX_BUDGET = 12000
MAX_ITEMS = 40
MAX_TEXT = 2000
SOURCE_PRIORITY = {"主人令": 1.0, "focus": 0.95, "memory": 0.85, "memory_bank": 0.8,
                   "recent_chat": 0.8, "ui_signal": 0.6, "tool_result": 0.7,
                   "prefetch": 0.5}
_CJK_RX = re.compile(r"[\u4e00-\u9fff]")


class InjectError(ValueError):
    pass


def _text(value, max_len=MAX_TEXT) -> str:
    return str(value or "")[:max_len]


def _grams(text: str):
    s = str(text or "").lower()
    grams = set(re.findall(r"[a-z0-9]{2,}", s))
    cjk = "".join(_CJK_RX.findall(s))
    grams |= {cjk[i:i + 2] for i in range(max(0, len(cjk) - 1))}
    return grams


def relevance(query: str, text: str) -> float:
    """0..1：query 与候选的 trigram/词覆盖；完全相同=1。"""
    q = _text(query).strip().lower()
    t = _text(text).strip().lower()
    if not q or not t:
        return 0.0
    if q in t:
        return 1.0
    qg, tg = _grams(q), _grams(t)
    if not qg:
        return 0.0
    hits = len(qg & tg)
    return round(min(1.0, hits / max(1, len(qg))), 4)


def _freshness(at, now: float) -> float:
    try:
        age = max(0.0, float(now) - float(at)) if at else 1e9
    except (TypeError, ValueError):
        return 0.0
    if age > 7 * 86400:
        return 0.0
    return round(max(0.0, 1.0 - age / (7 * 86400)), 4)


def select(query, candidates, budget=DEFAULT_BUDGET, now=None) -> dict:
    if not isinstance(candidates, list):
        raise InjectError("candidates 必须是数组")
    try:
        budget = int(budget)
    except (TypeError, ValueError):
        raise InjectError("budget 必须是整数")
    if budget < MIN_BUDGET or budget > MAX_BUDGET:
        raise InjectError("budget 范围 %d..%d" % (MIN_BUDGET, MAX_BUDGET))
    now = float(now if now is not None else time.time())
    dropped = {"expired": 0, "empty": 0, "duplicate": 0, "budget": 0, "over_items": 0,
               "invalid": 0}
    rows = []
    seen = {}
    for i, c in enumerate(candidates):
        if not isinstance(c, dict):
            dropped["invalid"] += 1
            continue
        text = _text(c.get("text") or c.get("content") or c.get("summary"))
        if not text.strip():
            dropped["empty"] += 1
            continue
        ttl = c.get("ttl")
        at = c.get("at") or c.get("ts")
        if ttl is not None:
            try:
                if at and float(at) + float(ttl) < now:
                    dropped["expired"] += 1
                    continue
            except (TypeError, ValueError):
                pass
        key = hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]
        source = str(c.get("source") or c.get("kind") or "unknown")
        rel = relevance(query, text)
        pri = float(c.get("priority") if c.get("priority") is not None
                    else SOURCE_PRIORITY.get(source, 0.4))
        fresh = _freshness(at, now)
        score = round(0.6 * rel + 0.25 * max(0.0, min(1.0, pri)) + 0.15 * fresh, 4)
        row = {"id": str(c.get("id") or key), "source": source, "text": text,
               "score": score, "relevance": rel, "priority": round(pri, 3),
               "freshness": fresh, "chars": len(text),
               "reason": "rel=%.2f/pri=%.2f/fresh=%.2f" % (rel, pri, fresh)}
        if key in seen:
            dropped["duplicate"] += 1
            if score > seen[key]["score"]:
                rows[seen[key]["_i"]] = None
                seen[key] = row
                row["_i"] = len(rows)
                rows.append(row)
            continue
        row["_i"] = len(rows)
        seen[key] = row
        rows.append(row)
    rows = [r for r in rows if r]
    rows.sort(key=lambda r: (-r["score"], -r["freshness"], r["id"]))
    # 来源配额：同 source 最多 ceil(MAX_ITEMS/3)
    cap = max(1, MAX_ITEMS // 3)
    picked, used, per_source = [], 0, {}
    for r in rows:
        if len(picked) >= MAX_ITEMS:
            dropped["over_items"] += 1
            continue
        if per_source.get(r["source"], 0) >= cap:
            continue
        if used + r["chars"] > budget:
            dropped["budget"] += 1
            continue
        picked.append(r)
        used += r["chars"]
        per_source[r["source"]] = per_source.get(r["source"], 0) + 1
    out = []
    for r in picked:
        r = dict(r)
        r.pop("_i", None)
        out.append(r)
    return {"ok": True, "query": _text(query, 300), "budget": budget, "used": used,
            "remaining": budget - used, "count": len(out), "items": out,
            "dropped": dropped, "source_counts": per_source,
            "provenance": "纯确定性选择；未调用模型/未出网"}


def verify() -> dict:
    checks = []

    def ck(name, cond, got=None):
        checks.append({"name": name, "ok": bool(cond), "got": got})

    base = [
        {"id": "m1", "source": "memory", "text": "主人喜欢数字人语音对讲", "at": 1000},
        {"id": "m2", "source": "ui_signal", "text": "当前打开浏览器页面", "at": 1000},
        {"id": "m3", "source": "精", "text": "内存里的旧内容", "at": 1000, "ttl": 5},
    ]
    r = select("语音对讲", base, budget=3000, now=1006)
    ck("过期项丢弃", r["dropped"]["expired"] == 1, r["dropped"])
    ck("相关项在前", r["items"] and r["items"][0]["id"] == "m1", [x["id"] for x in r["items"]])
    ck("预算记录", r["used"] <= r["budget"] and r["remaining"] == r["budget"] - r["used"])
    ck("来源统计", r["source_counts"].get("memory") == 1)
    r2 = select("", base, budget=3000, now=1006)
    ck("无 query 也能选", r2["ok"] and r2["count"] >= 1)
    dup = [{"id": "a", "source": "memory", "text": "同样内容", "at": 1000},
           {"id": "b", "source": "memory", "text": "同样内容", "at": 1000}]
    r3 = select("", dup, now=1006)
    ck("去重", r3["count"] == 1 and r3["dropped"]["duplicate"] == 1, r3["dropped"])
    r4 = select("x", [{"id": "a", "text": "a" * 900, "at": 1000},
                      {"id": "b", "text": "b" * 900, "at": 1000}], budget=1000, now=1006)
    ck("预算打包不超", r4["used"] <= 1000 and r4["count"] == 1, (r4["used"], r4["count"]))
    ck("budget 下限", _raises(lambda: select("x", base, budget=1)))
    ck("budget 上限", _raises(lambda: select("x", base, budget=99999)))
    ck("candidates 非数组", _raises(lambda: select("x", "bad")))
    ck("空文本丢", select("x", [{"id": "e", "text": ""}])["dropped"]["empty"] == 1)
    ck("相关度 1", relevance("语音", "语音对讲") == 1.0)
    ck("相关度 0", relevance("完全无关", "abc") == 0.0)
    ck("新鲜度", select("x", [{"id": "n", "text": "新", "at": 1000}], now=1006)["items"][0]["freshness"] > 0)
    srcs = [{"id": str(i), "source": "memory", "text": "记忆 %d" % i, "at": 1000} for i in range(20)]
    r5 = select("", srcs, budget=6000, now=1006)
    ck("来源配额", r5["source_counts"]["memory"] <= 13, r5["source_counts"])
    ck("schema 可达", "budget_default" in run("schema") and "sources" in run("schema"))
    ck("schema note", "note" in run("schema"))
    return {"ok": all(c["ok"] for c in checks), "checks": len(checks),
            "failed": [c for c in checks if not c["ok"]],
            "sha": hashlib.sha256(str(checks).encode()).hexdigest()[:12]}


def _raises(fn) -> bool:
    try:
        fn()
        return False
    except InjectError:
        return True


def run(op="schema", **params):
    op = str(op or "schema").lower()
    if op == "schema":
        return {"ok": True, "budget_default": DEFAULT_BUDGET,
                "budget_range": [MIN_BUDGET, MAX_BUDGET], "max_items": MAX_ITEMS,
                "sources": dict(SOURCE_PRIORITY),
                "note": "纯确定性；过期/去重/相关度/来源配额/预算"}
    if op == "select":
        try:
            return select(params.get("query"), params.get("candidates") or [],
                          params.get("budget") or DEFAULT_BUDGET,
                          params.get("now"))
        except InjectError as e:
            return {"ok": False, "error": "user_error: %s" % e}
    if op == "verify":
        return verify()
    raise ValueError("未知 op: %s（schema/select/verify）" % op)
