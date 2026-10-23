# -*- coding: utf-8 -*-
"""执行动作台账 + 重启守卫（action-ledger）—— 每天的动作全登记，重启后**不许无脑重做**。

主人令（2026-10-09，逐字）：「以及每天所有的执行动作都要登记避免重启之后，无脑操作」。

## 为什么要有它
本仓已有三本账，但没有一本管「**这件事做过了没有**」：
  · state/action_gate.jsonl      —— 动手**前**的纪律闸（拿旧读数当现状…），不是执行账；
  · state/action_evidence.jsonl  —— 证据包（文件 sha），不是执行账；
  · state/logbook.jsonl          —— 变更账（改了啥），粒度到「变更」不到「动作」。
于是重启之后最容易犯的错就是：**把昨天已经做过的事，当成没做过再做一遍**（无脑操作）。

## 本件三件事
1. record  —— 登记一次执行动作（含 **idem 幂等键**：动作+目标；同键再登记会被点名为重复）
2. check   —— 动手前查：这个 idem 做过没有？（做过 ⇒ **exit 1 + 打脸原文**，不许闷头重做）
3. boot    —— **重启报告**：今天做过的逐条 · **已完成清单（别重做）** · 未闭合的（要接着做）· 报警

## 纪律
  · 只追加（append-only），**不删不改**历史行；
  · idem 缺省按「动作|目标」归一化生成；
  · 报警一律取 state/capability-audit.json **现读**，本件不自己编一份；
  · --selftest 负对照：造一条重复 ⇒ 必须报红。
用法：
  py -3.14 -X utf8 tools/codex-scripts/action-ledger.py record --what "启动面板桥" --target "127.0.0.1:8765" --evidence "HTTP 200"
  py -3.14 -X utf8 tools/codex-scripts/action-ledger.py check  --idem "启动面板桥|127.0.0.1:8765"
  py -3.14 -X utf8 tools/codex-scripts/action-ledger.py boot
退出码：record 0 · check 已做过=1/没做过=0 · boot 有报警或有未闭合=1
"""
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
LEDGER = ROOT / "state" / "action-ledger.jsonl"
AUDIT = ROOT / "state" / "capability-audit.json"


def _norm_idem(what: str, target: str) -> str:
    t = (target or "").strip().lower()
    w = " ".join(str(what or "").split())
    if not t:
        return w + "|（无目标）"
    return "%s|%s" % (w, t)


def _rows() -> list:
    if not LEDGER.is_file():
        return []
    out = []
    for line in LEDGER.read_text(encoding="utf-8", errors="replace").strip().splitlines():
        try:
            out.append(json.loads(line))
        except ValueError:
            out.append({"坏行": line[:120]})
    return out


def _today() -> str:
    return time.strftime("%Y-%m-%d")


def record(what: str, target: str = "", evidence: str = "", result: str = "ok",
           actor: str = "ai", closed: bool = True, idem: str = "") -> dict:
    key = idem or _norm_idem(what, target)
    rows = _rows()
    dup = [r for r in rows if r.get("idem") == key]
    rec = {"at": time.strftime("%Y-%m-%dT%H:%M:%S"), "actor": actor, "what": what,
           "target": target, "evidence": evidence, "result": result, "closed": bool(closed),
           "idem": key, "dup_of": len(dup)}
    LEDGER.parent.mkdir(parents=True, exist_ok=True)
    with LEDGER.open("a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    rec["重复次数"] = len(dup)
    rec["warn"] = ("⚠️ 这条 idem 之前登记过 %d 次 —— 如果是同一件已完成的事，就是**无脑重做**"
                   % len(dup)) if dup else ""
    return rec


def check(idem: str) -> dict:
    rows = [r for r in _rows() if r.get("idem") == idem]
    if not rows:
        return {"ok": True, "done": False, "idem": idem, "note": "没做过 —— 可以动手"}
    last = rows[-1]
    return {"ok": False, "done": True, "idem": idem, "times": len(rows), "last": last,
            "note": "🔴 **做过了**（%s · %s）—— 重启后别无脑重做；要重做请说清改了什么前提"
                    % (last.get("at"), last.get("result"))}


def alarms() -> dict:
    if not AUDIT.is_file():
        return {"known": False, "why": "审计台账不在（先跑 capability-audit.py）"}
    try:
        d = json.loads(AUDIT.read_text(encoding="utf-8"))
    except ValueError as exc:
        return {"known": False, "why": "台账读不动：%s" % exc}
    items = d.get("items") or []
    bad = [i for i in items if i.get("state") in ("断连", "缺失")]
    opt = [i for i in items if i.get("state") == "按需未启用"]
    return {"known": True, "断连": len(bad), "按需未启用": len(opt),
            "逐条": [{"id": i.get("id"), "state": i.get("state"), "why": str(i.get("why"))[:120]}
                     for i in bad]}


def boot() -> dict:
    rows = _rows()
    today = _today()
    tk = [r for r in rows if str(r.get("at", "")).startswith(today)]
    by_idem = {}
    for r in rows:
        by_idem.setdefault(r.get("idem"), []).append(r)
    done = [{"idem": k, "times": len(v), "last": v[-1].get("at"),
             "what": v[-1].get("what"), "evidence": str(v[-1].get("evidence"))[:80]}
            for k, v in by_idem.items() if v[-1].get("closed")]
    open_ = [{"idem": k, "what": v[-1].get("what"), "at": v[-1].get("at")}
             for k, v in by_idem.items() if not v[-1].get("closed")]
    # 🔴 2026-10-09 判据自身的错（自查出来的，实测撞了）：
    #    原来「同 idem 出现多次」一律判**疑似无脑重做** ⇒ 把**重新验证**也冤枉了。
    #    正解：**同 idem 且证据逐字相同** = 真无脑重做；**证据不同** = 重新验证（正常，另列）。
    blind, reverify = [], []
    for k, v in by_idem.items():
        if len(v) < 2:
            continue
        evs = {str(r.get("evidence") or "") for r in v}
        (blind if len(evs) == 1 else reverify).append(k)
    dup = blind
    al = alarms()
    return {"ok": (al.get("断连") == 0 if al.get("known") else False) and not open_ and not dup,
            "at": time.strftime("%Y-%m-%dT%H:%M:%S"), "今天": len(tk), "台账总条数": len(rows),
            "今天做过的": [{"at": r.get("at"), "what": r.get("what"),
                            "target": r.get("target"), "result": r.get("result")} for r in tk],
            "已完成·重启后别重做": done, "未闭合·要接着做": open_,
            "被重复登记（疑似无脑重做）": dup,
            "重复验证（读数不同·正常）": reverify, "报警": al}


def selftest() -> int:
    global LEDGER
    import tempfile
    old = LEDGER
    with tempfile.TemporaryDirectory() as td:
        LEDGER = Path(td) / "l.jsonl"
        # 负对照要造**真无脑重做**：同 idem **且证据逐字相同**（读数不同的那叫重新验证）
        record("自检动作", "t/1", "同一份证据")
        r2 = record("自检动作", "t/1", "同一份证据")
        c = check(_norm_idem("自检动作", "t/1"))
        b = boot()
        red_dup = r2["重复次数"] == 1 and bool(r2["warn"])
        red_chk = (c["done"] is True) and not c["ok"]
        red_boot = "自检动作|t/1" in b["被重复登记（疑似无脑重做）"]
        print("负对照A·同 idem 再登记 ⇒ 点名重复：%s（重复 %d 次）" % ("红" if red_dup else "绿", r2["重复次数"]))
        print("负对照B·check 已做过 ⇒ 报「做过了」：%s" % ("红" if red_chk else "绿"))
        print("负对照C·boot 列出疑似无脑重做：%s" % ("红" if red_boot else "绿"))
        LEDGER = old
        return 0 if (red_dup and red_chk and red_boot) else 1


def main() -> int:
    ap = argparse.ArgumentParser(description="执行动作台账 + 重启守卫")
    sub = ap.add_subparsers(dest="op")
    p1 = sub.add_parser("record")
    p1.add_argument("--what", required=True)
    p1.add_argument("--target", default="")
    p1.add_argument("--evidence", default="")
    p1.add_argument("--result", default="ok")
    p1.add_argument("--actor", default="ai")
    p1.add_argument("--open", dest="closed", action="store_false")
    p1.add_argument("--idem", default="")
    p2 = sub.add_parser("check")
    p2.add_argument("--idem", required=True)
    sub.add_parser("boot")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    if a.selftest:
        rc = selftest()
        print("自检：%s" % ("全过" if rc == 0 else "不过"))
        return rc
    if a.op == "record":
        print(json.dumps(record(a.what, a.target, a.evidence, a.result, a.actor,
                                getattr(a, "closed", True), a.idem), ensure_ascii=False, indent=1))
        return 0
    if a.op == "check":
        r = check(a.idem)
        print(json.dumps(r, ensure_ascii=False, indent=1))
        return 0 if r["ok"] else 1
    b = boot()
    print("=" * 78)
    print("重启守卫 · %s" % b["at"])
    print("=" * 78)
    print("  台账 %d 条 · 今天 %d 条" % (b["台账总条数"], b["今天"]))
    al = b["报警"]
    print("  报警：%s" % (("断连 %d · 按需未启用 %d" % (al["断连"], al["按需未启用"]))
                        if al.get("known") else ("未知（%s）" % al.get("why"))))
    for x in al.get("逐条") or []:
        print("    [%s] %s ｜ %s" % (x["state"], x["id"], x["why"]))
    print("-" * 78)
    print("  ✅ 已完成·**重启后别重做**（%d 条）" % len(b["已完成·重启后别重做"]))
    for x in b["已完成·重启后别重做"][-12:]:
        print("    %s ｜ %s ｜ %s" % (x["last"], str(x["what"])[:40], x["evidence"][:40]))
    if b["未闭合·要接着做"]:
        print("  ⏳ 未闭合·要接着做（%d 条）" % len(b["未闭合·要接着做"]))
        for x in b["未闭合·要接着做"]:
            print("    %s ｜ %s" % (x["at"], str(x["what"])[:50]))
    if b.get("重复验证（读数不同·正常）"):
        print("  ○ 重复验证·读数不同（正常，不是无脑重做）：%d 条" % len(b["重复验证（读数不同·正常）"]))
    if b["被重复登记（疑似无脑重做）"]:
        print("  🔴 疑似无脑重做（同 idem 多次登记，%d 条）" % len(b["被重复登记（疑似无脑重做）"]))
        for k in b["被重复登记（疑似无脑重做）"]:
            print("    " + k)
    print("\n判据：%s" % ("PASS" if b["ok"] else "FAIL"))
    return 0 if b["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
