# -*- coding: utf-8 -*-
"""人写意图基准（commander-bench-lexicon）：用**人写的词**量路由，不用 desc 回环。

为什么要有这把尺子（docs/51 的结论）：
    478 项合成基准的意图是从能力位自己的 desc 生成的 —— 对"孪生位"（quant* / *_distill）
    这条基准**构不出唯一正确答案**（quant 的 desc 里就写着"回测"）。用它调模型会越调越偏。
    仓里 `data/intent-lexicon.json` 的 `say` 是**人写的**、且不来自 desc ⇒ 拿它量"真实可用性"。

口径（三条，写死）：
    ① 查询 = 词条里的一条 `say` 人话（`--phrase first|longest|all`）；
    ② 期望 = 该词条 `caps` 里权重最高的那一项（人自己标的）；
    ③ 同时记两个数：**候选里有没有**（recall@k）与**选没选中**（hit@1）——
       分得开才知道是"召回没兜住"还是"模型选错"。

用法：
    python tools/codex-scripts/commander-bench-lexicon.py                 # 全部词条，各取首条 say
    python tools/codex-scripts/commander-bench-lexicon.py --limit 8       # 先跑 8 条
    python tools/codex-scripts/commander-bench-lexicon.py --k 12 --json state/commander/bench-lexicon.json
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)


def pick_phrase(entry: dict, mode: str) -> str:
    says = [str(s) for s in (entry.get("say") or []) if str(s).strip()]
    if not says:
        return ""
    if mode == "longest":
        return max(says, key=len)
    return says[0]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--k", type=int, default=12)
    ap.add_argument("--phrase", choices=["first", "longest"], default="first")
    ap.add_argument("--json", default="state/commander/bench-lexicon.json")
    args = ap.parse_args()

    from gbt_allinone.tentacle import commander as C

    lex = json.load(open(os.path.join(ROOT, "data", "intent-lexicon.json"), encoding="utf-8"))
    entries = lex.get("intents") or []
    if args.limit:
        entries = entries[: args.limit]

    rows = []
    t_all = time.time()
    for i, e in enumerate(entries, 1):
        q = pick_phrase(e, args.phrase)
        caps = e.get("caps") or {}
        if not q or not caps:
            continue
        want = max(caps.items(), key=lambda kv: float(kv[1] or 0))[0]
        t0 = time.time()
        r = C.route(q, k=args.k)
        ms = int((time.time() - t0) * 1000)
        cands = r.get("candidates") or []
        rows.append({
            "intent": q, "what": e.get("what"), "want": want,
            "picked": r.get("name"), "hit": r.get("name") == want,
            "in_candidates": want in cands, "confidence": r.get("confidence"),
            "ms": ms, "error": None if r.get("ok") else r.get("error"),
        })
        print("%2d/%d %-28s -> %-22s %s%s" % (
            i, len(entries), q[:26] + ("…" if len(q) > 26 else ""),
            r.get("name") or "-",
            "HIT " if rows[-1]["hit"] else ("MISS(召回有)" if rows[-1]["in_candidates"] else "MISS(召回无)"),
            " conf=%s" % r.get("confidence") if r.get("confidence") is not None else ""), flush=True)

    hit = sum(1 for x in rows if x["hit"])
    recall = sum(1 for x in rows if x["in_candidates"])
    out = {
        "at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "source": "data/intent-lexicon.json（人写 say，不回环 desc）",
        "k": args.k, "n": len(rows), "hit": hit, "recall": recall,
        "hit_rate": round(hit / len(rows), 4) if rows else 0.0,
        "recall_rate": round(recall / len(rows), 4) if rows else 0.0,
        "avg_ms": int((time.time() - t_all) * 1000 / len(rows)) if rows else 0,
        "note": "recall=期望项在候选里；hit=模型选中；两者分开 ⇒ 分清召回问题与判决问题",
        "rows": rows,
    }
    dst = args.json if os.path.isabs(args.json) else os.path.join(ROOT, args.json)
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    json.dump(out, open(dst, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("\n== 人写意图：命中 %d/%d = %.1f%% · 召回 %d/%d = %.1f%% · 平均 %dms"
          % (hit, len(rows), 100.0 * out["hit_rate"], recall, len(rows),
             100.0 * out["recall_rate"], out["avg_ms"]))
    print("落盘:", dst)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
