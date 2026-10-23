# -*- coding: utf-8 -*-
"""accept_main54 -- **主 54 题判分器**（此前全仓缺失，2026-10-17 补齐）。

为什么要有它：`accept_q.json` 的 54 题只有 `{group, q}`，**没有判据/标准答案**，
而 6 个家族判分器各管自己那 44 题 ⇒ 主 54 一直无法机检（v48 的「54/54」是人工判的）。

判据来源（**不编**）：`gen_corpus_v50.py` 把每道主 54 题的**期望答案**从 v49 语料现读出来，
写进 `self_knowledge_v50.jsonl`（source=`v50-主54对齐`）。本判分器：
  1. 现读题库（`accept_q.json`）+ 语料期望答案，抽「关键实体词」= 期望答案里长度≥2 的中文词串
     / 长度≥4 的 ASCII 词，去重后取前 10 个（顺序即重要度）；
  2. 对模型答案算**关键覆盖率**；≥60%（且至少命中 2 个）记 PASS；
  3. 覆盖率不预设“全对”——分母是**题库里能给出期望答案的题**（未命中期望答案的题单列 skipped）。
用法：py -3.14 tools/train/accept_main54.py --answers .scratch/accept_a_v49.jsonl [--corpus ...]
"""
from __future__ import annotations
import argparse
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
QBANK = ROOT / ".scratch" / "accept_q.json"
CORPUS = ROOT / ".scratch" / "self_knowledge_v50.jsonl"
CJK = re.compile(r"[\u4e00-\u9fff]{2,}")
ASCII = re.compile(r"[A-Za-z_][A-Za-z0-9_\-]{3,}")
STOP = {"什么", "怎么", "哪些", "可以", "就是", "这个", "那个", "我们", "你们", "回答", "判据", "要点"}


def _keywords(text: str, limit: int = 10) -> list:
    toks = [t for t in CJK.findall(text) if t not in STOP and len(t) >= 2]
    toks += [t.lower() for t in ASCII.findall(text)]
    seen, out = set(), []
    for t in toks:
        if t in seen:
            continue
        seen.add(t)
        out.append(t)
        if len(out) >= limit:
            break
    return out


def load_expected(corpus: Path) -> dict:
    if not corpus.is_file():
        return {}
    exp = {}
    for ln in corpus.read_text(encoding="utf-8").splitlines():
        if not ln.strip():
            continue
        try:
            r = json.loads(ln)
        except Exception:                                        # noqa: BLE001
            continue
        if str(r.get("source") or "") == "v50-主54对齐":
            q = str(r.get("instruction") or "")
            q = re.sub(r"（[^）]*）$", "", q).strip()            # 去掉分组后缀
            exp[q] = str(r.get("output") or "")
    return exp


def main() -> int:
    ap = argparse.ArgumentParser(description="主 54 题判分（判据来源=语料期望答案，现读）")
    ap.add_argument("--answers", required=True)
    ap.add_argument("--corpus", default=str(CORPUS))
    ap.add_argument("--cover", type=float, default=0.6, help="关键覆盖率阈值（默认 0.6）")
    a = ap.parse_args()
    bank = [json.loads(l) for l in QBANK.read_text(encoding="utf-8").splitlines() if l.strip()] \
        if QBANK.is_file() else []
    exp = load_expected(Path(a.corpus))
    ans = {}
    for ln in Path(a.answers).read_text(encoding="utf-8").splitlines():
        if not ln.strip():
            continue
        try:
            r = json.loads(ln)
        except Exception:                                        # noqa: BLE001
            continue
        ans[str(r.get("q") or "").strip()] = str(r.get("a") or "")
    ok = tot = skipped = 0
    reds = []
    for item in bank:
        q = str(item.get("q") or "").strip()
        want = exp.get(q)
        if not want:
            skipped += 1
            continue
        got = ans.get(q, "")
        kws = _keywords(want)
        if not kws:
            skipped += 1
            continue
        tot += 1
        hit = [k for k in kws if k.lower() in got.lower()]
        cover = len(hit) / len(kws)
        good = cover >= a.cover and len(hit) >= 2
        if good:
            ok += 1
        else:
            reds.append((str(item.get("group") or "?"), q[:20], round(cover, 2), kws[:5]))
    print("== 主 54 判分：%d/%d PASS · 跳过 %d（无期望答案）· 阈值 覆盖率≥%.0f%% =="
          % (ok, tot, skipped, a.cover * 100))
    for g, q, c, k in reds[:8]:
        print("   RED [%s] %s 覆盖=%.2f 关键=…" % (g, q, c))
    return 0 if reds == [] else 1


if __name__ == "__main__":
    raise SystemExit(main())
