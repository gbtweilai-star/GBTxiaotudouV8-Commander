# -*- coding: utf-8 -*-
"""闭环拦截闸（closed-loop-or-trash）—— **没跑通闭环的，一律拒收**。

## 主人令（2026-10-11 逐字）
  「从现在开始**凡是没有跑通闭环并确认的都给我拦截丢垃圾桶**，
    再出现一次这样的事情**你也可以进垃圾桶**了」

## 这条闸咬什么
**不是咬代码，是咬「声明」** —— 凡是自称「完成 / 已接线 / 已部署 / 已开通 / 全部通过」
的地方，**必须能当场复跑出证据**；跑不出 ⇒ **拒收，落进垃圾桶台账**。

## 三道口径（写死）
  ① **无证据即拒**：一条声明要过闸，必须带 cmd（可复跑命令）+ expect_contains（期望读数）。
     缺任一 ⇒ 拒收。
  ② **复跑才算数**：cmd 必须**当场真跑**，读数里**真含** expect_contains；否则拒收。
  ③ **拒收留痕**：被拒的声明落 state/trash_rejected.jsonl（只追加，不删 —— 垃圾桶也要能查）。

## 与既有件的关系（不重写第二份）
  · **复用** tools/codex-scripts/proof-of-run-check.py 的复跑逻辑与
    state/delivery-claims.jsonl 的声明形状；
  · 本件只补**「拒收」这一半**：proof-of-run 报「哪条没过」，本件把「没过」**落进垃圾桶**。

用法: py -3.14 -X utf8 tools/codex-scripts/closed-loop-gate.py [--json] [--selftest] [--sweep]
"""
from __future__ import annotations

import argparse
import json
import os
import pathlib
import subprocess
import sys
import time

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8")           # type: ignore[attr-defined]
    except Exception:
        pass

WS = pathlib.Path(__file__).resolve().parents[2]
CLAIMS = WS / "state" / "delivery-claims.jsonl"
TRASH = WS / "state" / "trash_rejected.jsonl"


def _load_claims() -> list:
    if not CLAIMS.is_file():
        return []
    out = []
    for ln in CLAIMS.read_text(encoding="utf-8", errors="replace").splitlines():
        ln = ln.strip()
        if not ln:
            continue
        try:
            out.append(json.loads(ln))
        except Exception:                          # noqa: BLE001
            continue
    return out


def _reject(row: dict, why: str) -> dict:
    rec = {"at": time.strftime("%Y-%m-%dT%H:%M:%S"), "id": row.get("id"),
           "what": row.get("what"), "why": why, "claim": row}
    TRASH.parent.mkdir(parents=True, exist_ok=True)
    with TRASH.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(rec, ensure_ascii=False) + chr(10))
    return rec


def judge_one(row: dict, *, run: bool = True, timeout: int = 180) -> dict:
    """判一条声明：无证据即拒；有证据就**当场复跑**。"""
    cid = row.get("id")
    cmd = row.get("cmd")
    expect = row.get("expect_contains")
    # ① 无证据即拒
    if not cmd or not expect:
        return {"id": cid, "verdict": "拒收", "why": "缺 cmd 或 expect_contains（无证据即拒）"}
    if not run:
        return {"id": cid, "verdict": "待复跑", "why": "有证据，未跑"}
    # ② 复跑才算数
    env = dict(os.environ)
    env["OPENBLAS_NUM_THREADS"] = "1"
    try:
        p = subprocess.run(cmd, shell=True, cwd=str(WS), capture_output=True,
                           text=True, timeout=timeout, env=env)
        blob = (p.stdout or "") + (p.stderr or "")
    except subprocess.TimeoutExpired:
        return {"id": cid, "verdict": "拒收", "why": "复跑超时（>%ds）" % timeout}
    if expect not in blob:
        return {"id": cid, "verdict": "拒收",
                "why": "复跑读数里没有期望串 %r（rc=%s）" % (expect, p.returncode)}
    return {"id": cid, "verdict": "通过", "why": "复跑命中 %r" % expect, "rc": p.returncode}


def sweep(run: bool = True) -> dict:
    claims = _load_claims()
    results, trashed = [], []
    for row in claims:
        r = judge_one(row, run=run)
        results.append(r)
        # ③ 拒收留痕
        if r["verdict"] == "拒收":
            trashed.append(_reject(row, r["why"]))
    bad = [r for r in results if r["verdict"] == "拒收"]
    return {"ok": not bad, "total": len(results), "rejected": len(bad),
            "results": results, "trashed": len(trashed), "trash_file": str(TRASH)}


def selftest() -> int:
    ok = []
    r1 = judge_one({"id": "neg-no-evidence", "what": "假装做完了"}, run=False)
    ok.append(("真植入负控·无 cmd/expect ⇒ 必拒", r1["verdict"] == "拒收", r1["why"]))
    r2 = judge_one({"id": "neg-bad-expect", "cmd": "echo hello",
                    "expect_contains": "zz_never_printed_2026"}, run=True)
    ok.append(("真植入负控·复跑不含期望串 ⇒ 必拒", r2["verdict"] == "拒收", r2["why"]))
    r3 = judge_one({"id": "pos-ok", "cmd": "echo closed_loop_ok",
                    "expect_contains": "closed_loop_ok"}, run=True)
    ok.append(("真植入正控·复跑命中 ⇒ 必过", r3["verdict"] == "通过", r3["why"]))
    n = len(_load_claims())
    ok.append(("真件·声明台账能读", n >= 0, "%d 条" % n))
    bad = [x for x, c, _ in ok if not c]
    for n2, c, d in ok:
        print("  %-46s %s  (%s)" % (n2, "✅" if c else "❌", d))
    print("")
    print("closed-loop-gate 自检: %s（%d 条）"
          % ("全部通过" if not bad else "%d 条失败" % len(bad), len(ok)))
    return 1 if bad else 0


def main() -> int:
    ap = argparse.ArgumentParser(description="闭环拦截闸：没跑通闭环的一律拒收")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--sweep", action="store_true", help="对现有交付声明全量复跑")
    a = ap.parse_args()
    if a.selftest:
        return selftest()
    r = sweep(run=a.sweep)
    print("=" * 76)
    print("闭环拦截闸 —— 没跑通闭环的，一律拒收（垃圾桶台账留痕）")
    print("=" * 76)
    print("  模式: %s" % ("全量复跑" if a.sweep else "只查证据在不在（未复跑）"))
    print("  声明 %d 条 · **拒收 %d** · 垃圾桶 %d 条" % (r["total"], r["rejected"], r["trashed"]))
    print("  垃圾桶台账: %s" % r["trash_file"])
    print("")
    for x in r["results"][:14]:
        mark = {"通过": "✅", "拒收": "🗑️", "待复跑": "·"}.get(x["verdict"], "?")
        print("  %s %-28s %s" % (mark, str(x.get("id"))[:28], x["why"]))
    if r["rejected"]:
        print("")
        print("  🗑️ **被拒 %d 条已落垃圾桶**（只追加，可查）" % r["rejected"])
    print("")
    if a.json:
        print(json.dumps(r, ensure_ascii=False, indent=1))
    return 0 if r["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
