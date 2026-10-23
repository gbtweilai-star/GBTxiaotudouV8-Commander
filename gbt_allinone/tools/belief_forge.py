# gbt-capability: belief_forge
# ⛔ 开发者：自由的风 · 永久钢印 · 禁止删除
"""信念锻造：**观察 → 信念（会学习，不改写历史）→ 心智模型**（蒸馏自 hindsight 的"学习半"）。

## 抓取口径（凡抓取必写源·时间·口径）
· **源**：2026-10-01 主人给的 GitHub 飙升榜 #4 截图 `vectorize-io/hindsight`（会学习的智能体记忆层）。
  README 原文要点：「an agent memory system built to create smarter agents that learn over time」；
  「focused on making agents that learn, not just remember」；三操作 retain/recall/reflect；
  四路检索（Semantic/Keyword/Graph/Temporal）+ **reciprocal rank fusion** + cross-encoder 重排；
  「**consolidates related facts into observations — deduplicated beliefs**」；
  「new information **strengthens, weakens or extends an existing belief instead of silently replacing it**」；
  「Reading one is a database read — no retrieval, no LLM call」（指心智模型）。
· **时间**：2026-10-01。MIT · Python · ★43,986（API 现读）。

## 蒸馏判断：hindsight 的核里我们真缺哪块
| 它的架构 | 我们已有的对位 | 结论 |
|---|---|---|
| 来源印章 / 别名 / 零停机迁移 | **`memory_bank`（2026-09 已蒸馏：就是同一源的上批）** | **已有，不重造** |
| 秒级全文检索 | `memory_manager`（SQLite FTS5，中文可检索） | **已有** |
| **观察→去重信念的巩固**（strengthen/weaken/extend，**不静默覆盖**） | 无（`devour_reflect` 只反思，不落信念账） | **补这块** |
| **心智模型**（常备答案，读取**不调 LLM**） | 无 | **补这块** |
| 四路检索 + RRF 融合 | 只有 FTS5 一路（关键词） | **本轮不接**：语义/图两路要嵌入模型与图谱，本机零算力 ⇒ 如实记为缺口，不放假读数 |

## 硬规矩
1. **不覆盖**：新证据只 `strengthen/weaken/extend` 置信度与历史（`history` 只追加），**旧值不许被静默改写**。
2. **无证据不收**：`observe` 必须带 `evidence`（非空）与 `source`；缺 ⇒ 结构化拒绝。
3. **只读口径**：`model` 是**纯读**（读本地账，不调任何模型）；读不到如实报缺。
4. **置信度有界**：夹在 0..1，且每次改动都留 `为什么`（哪条观察推的）。
"""
from __future__ import annotations

import hashlib
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
_CAP = "belief_forge"


def _store_dir() -> Path:
    """env 优先（现读）⇒ `_paths.STORE_DIR` ⇒ 包内默认（同 case_mine 的理由：导入期绑定改不动）。"""
    env = __import__("os").getenv("GBT_STORE_DIR")
    if env:
        return Path(env) / _CAP
    try:
        from gbt_allinone._paths import STORE_DIR
        return Path(STORE_DIR) / _CAP
    except Exception:  # noqa: BLE001
        return ROOT / "gbt_allinone" / "store" / _CAP


def _key(claim: str) -> str:
    return hashlib.sha256(" ".join(str(claim or "").split()).lower().encode("utf-8")).hexdigest()[:16]


def _read_jsonl(p: Path) -> list:
    if not p.is_file():
        return []
    out = []
    for line in p.read_text(encoding="utf-8", errors="replace").splitlines():
        try:
            out.append(json.loads(line))
        except Exception:  # noqa: BLE001
            continue
    return out


def _append_jsonl(p: Path, row: dict) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(row, ensure_ascii=False) + "\n")


def observe(claim: str = "", evidence: str = "", source: str = "", polarity: int = 1, weight: float = 1.0) -> dict:
    """登记一条**观察**（必须带证据与来源；缺 ⇒ 拒）。"""
    claim, evidence, source = str(claim or "").strip(), str(evidence or "").strip(), str(source or "").strip()
    if not claim:
        return {"ok": False, "fail_closed": True, "error": "缺 claim：观察要有主张"}
    if not evidence:
        return {"ok": False, "fail_closed": True, "error": "缺 evidence：**无证据不收**"}
    if not source:
        return {"ok": False, "fail_closed": True, "error": "缺 source：来历不明不收"}
    pol = 1 if int(polarity or 1) >= 0 else -1
    w = max(0.0, min(3.0, float(weight if weight is not None else 1.0)))
    row = {"at": time.strftime("%Y-%m-%dT%H:%M:%S"), "claim": claim, "claim_key": _key(claim),
           "evidence": evidence[:400], "source": source[:160], "polarity": pol, "weight": w}
    _append_jsonl(_store_dir() / "observations.jsonl", row)
    return {"ok": True, "op": "observe", "claim_key": row["claim_key"], "at": row["at"],
            "_口径": "只登记，不改任何信念；信念由 consolidate 从观察账推"}


def consolidate(claim: str = "") -> dict:
    """把同类观察**巩固**成信念：置信度 = 证据加权（正负相抵），**只追加历史，不覆盖**。"""
    obs = _read_jsonl(_store_dir() / "observations.jsonl")
    if not obs:
        return {"ok": True, "op": "consolidate", "updated": [], "n": 0,
                "note": "观察账还空 —— **空不是绿**，是没有料"}
    want = _key(claim) if str(claim or "").strip() else ""
    groups: dict = {}
    for o in obs:
        k = o.get("claim_key")
        if not k or (want and k != want):
            continue
        groups.setdefault(k, []).append(o)
    bel_f = _store_dir() / "beliefs.jsonl"
    prev = {}
    for b in _read_jsonl(bel_f):
        prev[b.get("claim_key")] = b
    updated = []
    for k, rows in groups.items():
        pos = sum(r["weight"] for r in rows if r["polarity"] > 0)
        neg = sum(r["weight"] for r in rows if r["polarity"] < 0)
        total = pos + neg
        conf = 0.0 if total <= 0 else round(min(1.0, pos / total), 3)
        old = prev.get(k) or {}
        old_conf = old.get("confidence")
        if old_conf is None:
            move = "extend"
        elif abs(conf - float(old_conf)) < 1e-9:
            move = "extend"
        elif conf > float(old_conf):
            move = "strengthen"
        else:
            move = "weaken"
        rec = {"claim_key": k, "claim": rows[-1]["claim"], "confidence": conf,
               "evidence_n": len(rows), "pos_weight": round(pos, 2), "neg_weight": round(neg, 2),
               "updated_at": time.strftime("%Y-%m-%dT%H:%M:%S"), "move": move,
               "why": "由 %d 条观察推（正权 %.2f / 负权 %.2f）" % (len(rows), pos, neg),
               "sources": sorted({r["source"] for r in rows})[:6],
               "prev_confidence": old_conf,
               "history": (old.get("history") or []) + [{"at": time.strftime("%Y-%m-%dT%H:%M:%S"),
                                                         "confidence": conf, "move": move}]}
        _append_jsonl(bel_f, rec)
        updated.append({"claim_key": k, "confidence": conf, "move": move,
                        "was": old_conf, "evidence_n": len(rows)})
    return {"ok": True, "op": "consolidate", "updated": updated, "n": len(updated),
            "_口径": "历史只追加（不覆盖）；置信度=证据加权；move ∈ strengthen/weaken/extend"}


def beliefs(min_conf: float = 0.0) -> dict:
    """现读信念（每条取最新一版；`history` 在盘上保留）。"""
    rows = {}
    for b in _read_jsonl(_store_dir() / "beliefs.jsonl"):
        rows[b.get("claim_key")] = b
    items = [r for r in rows.values() if float(r.get("confidence") or 0) >= float(min_conf or 0)]
    items.sort(key=lambda r: -float(r.get("confidence") or 0))
    return {"ok": True, "op": "beliefs", "beliefs": items, "n": len(items),
            "all_n": len(rows)}


def model(question: str = "", set_answer: str = "", ttl_s: int = 0) -> dict:
    """**心智模型**：常备答案。读：纯本地账 + 相关信念（**不调任何模型**）；写：`set_answer` 预计算落账。"""
    f = _store_dir() / "models.json"
    doc = {}
    if f.is_file():
        try:
            doc = json.loads(f.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            doc = {}
    q = " ".join(str(question or "").split())
    if set_answer:
        if not q:
            return {"ok": False, "fail_closed": True, "error": "缺 question：模型要挂在一个问题上"}
        doc[_key(q)] = {"question": q, "answer": str(set_answer)[:2000],
                        "at": time.strftime("%Y-%m-%dT%H:%M:%S"),
                        "ttl_s": int(ttl_s or 0),
                        "evidence": "由调用方预计算并落账（读取时不调模型）"}
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(json.dumps(doc, ensure_ascii=False, indent=1), encoding="utf-8")
        return {"ok": True, "op": "model", "wrote": _key(q)}
    if not q:
        return {"ok": True, "op": "model", "models": list(doc.values()), "n": len(doc)}
    hit = doc.get(_key(q))
    if hit:
        return {"ok": True, "op": "model", "hit": True, "model": hit,
                "_口径": "纯数据库读（不检索不调模型）"}
    rel = [b for b in beliefs()["beliefs"] if str(b.get("claim") or "") in q or q in str(b.get("claim") or "")]
    return {"ok": True, "op": "model", "hit": False, "related_beliefs": rel[:5],
            "note": "没有预计算答案；已给相关信念（要常备答案就 set_answer 落一条）"}


def where(**_kw) -> dict:
    return {"ok": True, "op": "where", "kind": _CAP, "tentacle": _CAP,
            "entry": "run_task('belief_forge', {...})",
            "ops": ["observe", "consolidate", "beliefs", "model", "where"],
            "distilled_from": "2026-10-01 主人给的飙升榜 #4 vectorize-io/hindsight（会学习的记忆层）"
                              "——只取**学习半**：观察→去重信念的巩固（不覆盖）+ 心智模型（纯读）",
            "not_copied": "来源印章/别名/零停机迁移 **已有对位 `memory_bank`（同一源的上批）**，不重造；"
                          "四路检索本批不接（语义/图要嵌入与图谱，本机零算力 ⇒ 如实记缺口）",
            "hard_rules": ["不覆盖：新证据只 strengthen/weaken/extend，history 只追加",
                           "无证据不收（observe 必须带 evidence+source）",
                           "model 是纯读（不调模型）；置信度夹 0..1 且每次留『为什么』"],
            "files": {"观察账": "beliefs/observations.jsonl", "信念账": "beliefs/beliefs.jsonl",
                      "心智模型": "beliefs/models.json"},
            "contract": [
                {"op": "observe", "params": "claim + evidence + source + [polarity] + [weight]", "returns": "登记回执"},
                {"op": "consolidate", "params": "[claim]", "returns": "信念更新（move=strengthen/weaken/extend）"},
                {"op": "beliefs", "params": "[min_conf]", "returns": "现读信念（最新一版）"},
                {"op": "model", "params": "question + [set_answer]", "returns": "常备答案（读=纯本地账）"},
            ]}


def run_op(op: str = "beliefs", **params) -> dict:
    op = (op or "beliefs").lower()
    for n, fn in (("observe", observe), ("consolidate", consolidate),
                  ("beliefs", beliefs), ("model", model), ("where", where)):
        if op == n:
            return fn(**params)
    return {"ok": False, "fail_closed": True,
            "error": "未知 op:%s（observe/consolidate/beliefs/model/where）" % op}


if __name__ == "__main__":                                     # 主人的终端入口
    import argparse
    ap = argparse.ArgumentParser(description="信念锻造（hindsight 学习半蒸馏 · 观察→信念→心智模型）")
    ap.add_argument("cmd", nargs="?", default="beliefs")
    ap.add_argument("--claim", default="")
    ap.add_argument("--evidence", default="")
    ap.add_argument("--source", default="")
    ap.add_argument("--polarity", type=int, default=1)
    ap.add_argument("--question", default="")
    ap.add_argument("--set-answer", default="")
    a = ap.parse_args()
    kw = {"claim": a.claim, "evidence": a.evidence, "source": a.source, "polarity": a.polarity,
          "question": a.question, "set_answer": a.set_answer}
    print(json.dumps(run_op(a.cmd, **kw), ensure_ascii=False, indent=1))
