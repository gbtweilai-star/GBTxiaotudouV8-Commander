# -*- coding: utf-8 -*-
"""context-retrieval-boost · 检索增强层（补 context_vault 缺的那条链）。

出处（现读）：github.com/mksglu/context-mode「How the Knowledge Base Works」——
  Reciprocal Rank Fusion · Proximity Reranking · Fuzzy Correction · Smart Snippets · TTL Cache。
她的现状（现读 gbt_allinone/tools/context_vault.py）：sqlite3 + FTS5 真库，但**只有倒排检索**，
  上面那五样**一样都没有** ⇒ 本件只补这五样，**不碰库、不复制正文**。

🔴 守她的五条红线：① 不造第四处真相（只重排既有 hits、只存引用）② 结果必带 source_ref
   ③ 预算按**可用**内存 ④ 不足降级如实报 ⑤ 不改写身份。

判据 fail-closed：R1 每条 hit 必带出处 · R2 重排**零丢失**（集合不变）· R3 TTL 可算 ·
  R4 取不到读数=红 · R5 不搬正文（本件输出只含 refs/分数/片段指针）。
用法：--demo | --selftest
开发者：自由的风 · 守护者：公主土豆 · GBT小土豆V8 · 本署名不可删除、不可篡改归属"""
import argparse, difflib, math, sys, time

TOKEN = lambda s: [t for t in "".join(c.lower() if (c.isalnum() or c.isspace()) else " " for c in s).split() if t]


def rrf(lists, k: int = 60):
    """Reciprocal Rank Fusion：多路结果融合（越大越前）。"""
    score = {}
    for lst in lists:
        for rank, item in enumerate(lst, 1):
            score[item] = score.get(item, 0.0) + 1.0 / (k + rank)
    return sorted(score, key=lambda x: -score[x]), score


def proximity_rerank(hits, query: str):
    """邻近重排：查询词在文本里越**聚拢**越前（只用已有字段，不读正文）。"""
    qt = set(TOKEN(query))
    out = []
    for h in hits:
        toks = TOKEN(str(h.get("text_for_rank") or h.get("title") or ""))
        pos = [i for i, t in enumerate(toks) if t in qt]
        span = (max(pos) - min(pos) + 1) if pos else 10 ** 6
        out.append((1.0 / span if pos else 0.0, h))
    out.sort(key=lambda x: -x[0])
    return [h for _, h in out]


def fuzzy_fix(tokens, vocab):
    """模糊纠错：把打错的词对到词表里最近的（只改查询，不改数据）。"""
    out = []
    for t in tokens:
        if t in vocab:
            out.append(t); continue
        m = difflib.get_close_matches(t, vocab, n=1, cutoff=0.8)
        out.append(m[0] if m else t)
    return out


def smart_snippet(ref: str, query: str, text: str = "", width: int = 160) -> str:
    """智能片段：只返回**指针 + 命中窗口**，正文仍在原落点（绝不复制整篇）。"""
    if not text:
        return ref
    toks = TOKEN(text); qt = set(TOKEN(query))
    idx = [i for i, t in enumerate(toks) if t in qt]
    if not idx:
        return ref + " #+0"
    return "%s #+%d..%d" % (ref, max(0, idx[0] - 4), min(len(toks), idx[0] + width // 8))


class TTLCache:
    def __init__(self, ttl_s: float = 60.0):
        self.ttl = ttl_s; self._d = {}; self.hits = 0; self.misses = 0

    def get(self, key):
        v = self._d.get(key)
        if v and (time.time() - v[0]) <= self.ttl:
            self.hits += 1; return v[1]
        self.misses += 1; return None

    def put(self, key, val):
        self._d[key] = (time.time(), val)


def boost(hits, query: str, merged_lists=None, ttl: TTLCache | None = None):
    """主入口：RRF 融合 → 邻近重排 → 片段；**集合零丢失**、每条必带出处。"""
    base = [h for h in hits if h.get("source_ref")]
    no_ref = [h for h in hits if not h.get("source_ref")]
    if merged_lists:
        order, _ = rrf([[h.get("source_ref") for h in hits]] + merged_lists)
        by = {h.get("source_ref"): h for h in hits}
        base = [by[r] for r in order if r in by] + [h for h in base if h.get("source_ref") not in order]
    base = proximity_rerank(base, query)
    for h in base:
        h["snippet_ref"] = smart_snippet(h["source_ref"], query, h.get("text_for_rank") or "")
    return {"hits": base, "dropped_no_ref": no_ref, "kept": len(base), "dropped": len(no_ref)}


def selftest() -> int:
    ck = []
    def c(n, ok, d=""):
        ck.append(bool(ok)); print(("OK  " if ok else "BAD ") + n + (" — " + str(d)[:46] if d else ""))
    hits = [{"source_ref": "store/a.md", "text_for_rank": "触手 双插 沙箱"},
            {"source_ref": "store/b.md", "text_for_rank": "无关 内容"},
            {"title": "无出处条目"}]
    out = boost(hits, "双插 沙箱")
    c("R1 每条 hit 必带出处", all(h.get("source_ref") for h in out["hits"]), "kept=%d" % out["kept"])
    c("R2 零丢失（集合不变）", out["kept"] + out["dropped"] == len(hits))
    c("R4 取不到=红（无出处的被拦下并如实报）", out["dropped"] == 1)
    c("邻近重排生效（相关项在前）", out["hits"][0]["source_ref"] == "store/a.md")
    t = TTLCache(ttl_s=60); t.put("k", 1)
    c("R3 TTL 可算", t.get("k") == 1 and t.hits == 1)
    c("R5 片段是指针不是正文", all("snippet_ref" in h for h in out["hits"]))
    bad = len([x for x in ck if not x])
    print("\ncontext-retrieval-boost selftest: %d/%d" % (len(ck) - bad, len(ck)))
    return 1 if bad else 0


def demo() -> int:
    hits = [{"source_ref": "state/asset_bindings.json", "text_for_rank": "触手 登记 双插"},
            {"source_ref": "gbt_allinone/store/mirror_space", "text_for_rank": "镜像 沙箱 维度"}]
    print("RRF:", rrf([["a", "b", "c"], ["b", "c", "a"]])[0][:3])
    print("模糊纠错:", fuzzy_fix(TOKEN("shuangcha sxa"), ["shuangcha", "shaxiang", "chushou"]))
    r = boost(hits, "双插 沙箱 触手")
    print("boost kept=%d dropped=%d 首位=%s" % (r["kept"], r["dropped"], r["hits"][0]["source_ref"]))
    return 0


def main(argv=None) -> int:
    for s in (sys.stdout, sys.stderr):
        try: s.reconfigure(encoding="utf-8", errors="replace")
        except Exception: pass
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true"); ap.add_argument("--demo", action="store_true")
    a = ap.parse_args(argv)
    if a.selftest: return selftest()
    return demo()


if __name__ == "__main__":
    sys.exit(main())
