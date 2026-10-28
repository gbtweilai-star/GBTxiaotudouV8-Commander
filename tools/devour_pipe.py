#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""devour_pipe —— 吞噬流水线（固化版）。

把这一场验证过的三件拼成**一条可复跑、可断点续、可批量**的流水线：

    取源 self_intake.intake  →  前闸 intake_gate.judge  →  入库 context_vault + 统一索引
                                    ↓ reject
                              胶囊照留、**不给进库资格**

## 为什么固化
  三件单独都验过（真知识过、人造垃圾拒），但散着用等于没有：
  · 谁都不记得该按什么顺序调
  · 中间任一步失败没人记
  · 批量吞到一半断了不能续
  固化 = **一个契约 + 一份账**。

## 契约
  · 只吞有出处的（intake 自带 source_ref 强制）
  · 必过前闸（reject 则 indexed=false，账上留痕，不静默）
  · 幂等（同 topic 同 sha 已吞过就 skip，不重复入库）
  · 每步落盘（state/devour_pipe.json + 追加账 state/devour_pipe.jsonl）
  · 判不了就写判不了（不编）

## 用法
  python3 tools/devour_pipe.py plan  --topic "主题" --urls a,b   # 只取源+判，不吞
  python3 tools/devour_pipe.py run   --topic "主题" --urls a,b   # 全流程
  python3 tools/devour_pipe.py batch --file topics.json          # 批量（[{topic,urls},…]）
  python3 tools/devour_pipe.py ledger                            # 看账
"""
from __future__ import annotations

import json
import pathlib
import sys
import time

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))

STATE = ROOT / "state" / "devour_pipe.json"
LEDGER = ROOT / "state" / "devour_pipe.jsonl"


def _load() -> dict:
    try:
        return json.loads(STATE.read_text(encoding="utf-8"))
    except Exception:                                         # noqa: BLE001
        return {"items": {}}


def _save(d: dict) -> None:
    STATE.parent.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")


def _log(rec: dict) -> None:
    LEDGER.parent.mkdir(parents=True, exist_ok=True)
    with LEDGER.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(rec, ensure_ascii=False) + "\n")


def _slug(topic: str) -> str:
    import re
    s = re.sub(r"[^\w\u4e00-\u9fff-]+", "-", topic.strip().lower())
    return s.strip("-")[:60] or "untitled"


def one(topic: str, urls: list, do_absorb: bool = True) -> dict:
    """一条流水线。返回可审计的回执。"""
    from gbt_allinone.api import run_task
    import intake_gate as IG

    rec = {"at": time.strftime("%Y-%m-%dT%H:%M:%S"), "topic": topic,
           "urls": urls, "absorbed": False}

    # plan 是**零写盘预演**：自己下载、自己判，不落胶囊、不入库。
    # 🔴 2026-10-29 修：上一版 plan 也走 intake ⇒ intake 内部必然落胶囊+入库，
    #    "只看不吞"是假的（实测 plan 回执里"入库=是"）。
    if not do_absorb:
        texts, failed = [], []
        import urllib.request as _U
        for u in (urls or []):
            try:
                req = _U.Request(u, headers={"User-Agent": "gbt-devour"})
                with _U.urlopen(req, timeout=25) as r0:
                    texts.append("# %s\n\n%s" % (u, r0.read().decode("utf-8", "replace")))
            except Exception as exc:                          # noqa: BLE001
                failed.append({"url": u, "why": type(exc).__name__})
        if not texts:
            rec.update({"verdict": "no_source", "absorbed": False,
                        "gate": {"reasons": ["一个源都没取到（预演不落盘）"]},
                        "intake": {"ok": False, "sources": 0, "failed": failed}})
            _log(rec); return rec
        g = IG.judge_text("\n\n".join(texts), label=topic)
        rec.update({"verdict": g.get("verdict"), "indexed": False, "absorbed": False,
                    "gate": {"verdict": g.get("verdict"), "claims": g.get("claims"),
                             "proved_ok": g.get("proved_ok"), "proved_bad": g.get("proved_bad"),
                             "ai_smell": g.get("ai_smell"), "reasons": g.get("reasons")},
                    "intake": {"ok": True, "sources": len(texts), "failed": failed},
                    "dry_run": True})
        _log(rec); return rec

    # ① 取源 —— 只吞有出处的
    r = run_task("self_intake", {"op": "intake", "topic": topic, "urls": urls or []})
    res = (r.get("gbt_result") or {}).get("result") or r.get("result") or {}
    rec["intake"] = {"ok": res.get("ok"), "sources": res.get("sources"),
                     "not_read": res.get("not_read"),
                     "reason": res.get("reason")}
    if not res.get("ok"):
        rec["verdict"] = "no_source"
        _log(rec)
        return rec

    # ② 前闸 —— 拆解/分析/跑通
    slug = _slug(topic)
    g = IG.judge(slug)
    rec["gate"] = {"verdict": g.get("verdict"), "claims": g.get("claims"),
                   "proved_ok": g.get("proved_ok"), "proved_bad": g.get("proved_bad"),
                   "ai_smell": g.get("ai_smell"), "reasons": g.get("reasons")}
    rec["verdict"] = g.get("verdict")
    rec["indexed"] = bool(res.get("indexed")) and g.get("verdict") != "reject"

    # ③ 统一索引（进她自己的记忆册）
    if rec["indexed"] and do_absorb:
        try:
            import memory_unify as MU
            MU.index()
            rec["unified_indexed"] = True
        except Exception as exc:                              # noqa: BLE001
            rec["unified_indexed"] = False
            rec["unified_err"] = type(exc).__name__
    rec["absorbed"] = bool(rec["indexed"])
    _log(rec)
    return rec


def show(rec: dict) -> None:
    mark = {"pass": "✅", "warn": "⚠️", "reject": "🔴"}.get(rec.get("verdict") or "", "·")
    g = rec.get("gate") or {}
    print("  %s %-26s 取源 %s · 主张 %s · 跑通 %s · 失败 %s · 入库 %s"
          % (mark, rec["topic"][:26], rec.get("intake", {}).get("sources"),
             g.get("claims", "-"), g.get("proved_ok", "-"),
             g.get("proved_bad", "-"), "是" if rec.get("absorbed") else "否"))
    for w in (g.get("reasons") or []):
        print("       - %s" % w)


def main(argv: list) -> int:
    op = argv[1] if len(argv) > 1 else "ledger"
    args = argv[2:]
    d = _load()

    def opt(name, default=None):
        if name in args:
            i = args.index(name)
            return args[i + 1] if i + 1 < len(args) else default
        return default

    if op in ("plan", "run"):
        topic = opt("--topic")
        urls = [u.strip() for u in (opt("--urls") or "").split(",") if u.strip()]
        if not topic:
            print("  要给 --topic"); return 2
        rec = one(topic, urls, do_absorb=(op == "run"))
        d["items"][_slug(topic)] = rec
        _save(d)
        show(rec)
        return 0

    if op == "batch":
        f = opt("--file")
        if not f:
            print("  要给 --file（[{topic,urls},…]）"); return 2
        items = json.loads(pathlib.Path(f).read_text(encoding="utf-8"))
        for it in items:
            t = str(it.get("topic") or "")
            us = it.get("urls") or []
            if not t:
                continue
            slot = _slug(t)
            prev = d["items"].get(slot) or {}
            # 幂等：同 topic 同源且已入库 ⇒ skip（不重复吞、不重复入库）
            if prev.get("absorbed") and prev.get("urls") == us:
                print("  ⏭ %-26s 已吞过同源，skip" % t[:26])
                continue
            rec = one(t, us, do_absorb=True)
            d["items"][slot] = rec
            _save(d)
            show(rec)
        return 0

    if op == "rejudge":
        # 闸修好之后，把历史账**就地按新判据重判**（不重抓、不重吞）。
        # 为什么需要：账里存的是"当时那一版闸"的判决；闸本身修过 bug（假失败），
        # 不重判的话账会一直骗人。
        import intake_gate as IG
        items = d.get("items") or {}
        n = 0
        for slot, rec in items.items():
            g = IG.judge(slot)
            if not g.get("ok"):
                continue
            rec["gate"] = {"verdict": g.get("verdict"), "claims": g.get("claims"),
                           "proved_ok": g.get("proved_ok"), "proved_bad": g.get("proved_bad"),
                           "ai_smell": g.get("ai_smell"), "reasons": g.get("reasons")}
            rec["verdict"] = g.get("verdict")
            rec["rejudged_at"] = time.strftime("%Y-%m-%dT%H:%M:%S")
            n += 1
        _save(d)
        print("  已按当前判据重判 %d 条" % n)
        for slot, rec in items.items():
            show(rec)
        return 0

    # ledger
    items = d.get("items") or {}
    from collections import Counter
    c = Counter((v.get("verdict") or "?") for v in items.values())
    print("  ═══ 吞噬账 ═══")
    print("  共 %d 条 · %s" % (len(items), dict(c)))
    for k, v in list(items.items())[-12:]:
        show(v)
    if LEDGER.is_file():
        n = len(LEDGER.read_text(encoding="utf-8").splitlines())
        print("\n  追加账 %d 行 · %s" % (n, LEDGER))
    return 0


if __name__ == "__main__":
    import os
    os.environ.setdefault("GBT_AUTONOMOUS", "1")
    raise SystemExit(main(sys.argv))
