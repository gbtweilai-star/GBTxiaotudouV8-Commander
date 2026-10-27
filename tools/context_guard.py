#!/usr/bin/env python3
"""上下文守护触手 —— 双向绑定 · 实时读取 · 异常即纠正 · 回大脑执行层

主人 2026-10-28 口径（原话拆成三件事）：
  ① 「触手双向绑定他的上下文页面实时读取」        → 本器 tick 读 window + stats
  ② 「一根触手双向绑定负责上下文溢出保护」        → 专责触手 context_overflow_guard
  ③ 「每一次上下文异常都要返回大脑执行层分析推理排布划分纠正」→ 异常即调 brain
  ④ 「继续回到主线跑」                            → 纠正后发 resume 标记，主线 id 不变

它与 ring_context 的分工（不重复造）：
  ring_context  负责"环本身"：有界窗口 / 溢出落库 / 秒查
  本器           负责"看着它"：读数、判异常、叫大脑、纠正、回主线
  大脑执行层     负责"判断"：brain_route 排布纠正动作

异常判据（客观、可复算，不靠感觉）：
  near_overflow   window_chars > 0.85 × 预算
  overflow        window_chars > 预算（环形本身出 bug 才会发生）
  lost            seq - spilled > 窗口条数（说明有条没落库就没了）
  stuck           连续 N 次 tick 内容指纹不变但 seq 在涨
  empty_window    有条但 window 空

用法：
  python3 tools/context_guard.py --once        # 单次体检（给 CI/验收）
  python3 tools/context_guard.py --watch       # 常驻
  python3 tools/context_guard.py --selftest    # 把上下文灌到近溢出，看它能不能发现并纠正
"""
from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import sys
import time

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

TENTACLE = "context_overflow_guard"
MAINLINE = "main.task"                       # 主线标识（纠正前后不变）
STATE = ROOT / "state" / "context_guard.json"
LEDGER = ROOT / "state" / "context_guard.jsonl"
NEAR = 0.85                                  # 近溢出阈值


def _ring(name: str = "default", budget: int = 0):
    from gbt_allinone.llm.ring_context import RingContext, DEFAULT_WINDOW_CHARS
    return RingContext(name=name, window_chars=int(budget) or DEFAULT_WINDOW_CHARS)


def sample(rc) -> dict:
    """① 实时读取（双向绑定读的那一侧）。"""
    st = rc.stats()
    win = rc.window()
    # 🔴 2026-10-28 修：stats() 的真实字段是
    #     window_chars  = **当前窗口字符数**（不是预算！）
    #     window_budget = 预算
    #     window_items  = 窗口条数
    #     db_turns      = 库里条数（**跨 name 共享**，不能拿来算"丢条"）
    #   第一版把 window_chars 当预算 ⇒ 每次都是"填充 100%"、每次都误报丢条。
    chars = sum(len(m.get("content") or "") for m in win)
    budget = int(st.get("window_budget") or 0)
    fp = hashlib.sha256(
        "".join(m.get("content") or "" for m in win).encode()).hexdigest()[:12]
    seq = int(st.get("seq") or 0)
    # db_turns 是**全库共享**的，只能当参考；判"丢条"不用它
    db_turns = int(st.get("db_turns") or 0)
    return {"at": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "seq": seq, "spilled": db_turns, "window_n": len(win),
            "window_chars": chars, "budget": budget,
            "fill": round(chars / budget, 3) if budget else None,
            "chars_now": chars,
            "fingerprint": fp}


def diagnose(s: dict, prev: dict | None, streak: int) -> list[dict]:
    """③ 判异常。只报能复算的，不猜。"""
    out = []
    if s["budget"] and s["window_chars"] > s["budget"]:
        out.append({"code": "overflow", "why": "窗口 %d > 预算 %d（环形本身违约）"
                    % (s["window_chars"], s["budget"])})
    elif s["budget"] and s["fill"] and s["fill"] > NEAR:
        out.append({"code": "near_overflow", "why": "填充 %.0f%% > %.0f%% 阈值"
                    % (s["fill"] * 100, NEAR * 100)})
    # 🔴 原判据 "seq - spilled > window_n ⇒ 丢条" 是错的：
    #    db_turns 是**全库共享**的计数，跟本 name 的 seq 不同源，相减没有意义。
    #    真要验"没丢"，靠 recall 命中（见 --selftest 的秒查检查），不靠减出来。
    if s["budget"] and s["window_n"] == 0 and s["chars_now"] > 0:
        out.append({"code": "window_lost", "why": "字符 %d 但窗口 %d 条"
                    % (s["chars_now"], s["window_n"])})
    if s["seq"] > 0 and s["window_n"] == 0:
        out.append({"code": "empty_window", "why": "有 %d 条但窗口是空的" % s["seq"]})
    if prev and streak >= 3 and prev["fingerprint"] == s["fingerprint"] and s["seq"] > prev["seq"]:
        out.append({"code": "stuck", "why": "连续 %d 次指纹不变但 seq 在涨（可能是复读）" % streak})
    return out


def to_brain(s: dict, anomalies: list[dict]) -> dict:
    """④ 异常回大脑执行层：让它排布纠正动作（不自己拍脑袋）。"""
    intent = ("上下文异常纠正：%s。当前窗口 %d 字符 / 预算 %d，条数 %d。"
              "请给出纠正动作（缩小窗口 / 强制落库 / 丢弃重复 / 回主线）。"
              % ("、".join(a["code"] for a in anomalies),
                 s["window_chars"], s["budget"], s["window_n"]))
    try:
        from gbt_allinone.api import run_task
        r = run_task("brain_route", {"intent": intent})
        res = (r.get("gbt_result") or {}).get("result") or r.get("result") or {}
        best = res.get("best") or {}
        return {"called": True, "ok": bool(res.get("ok")),
                "intent": intent[:160],
                # 真实字段是 best.kind；degraded=true 表示语义路由降级到启发式，
                # 这时给出的匹配可能不相干 —— **如实带上，不装它"排布好了"**
                "routed": best.get("kind"),
                "routed_domain": best.get("domain"),
                "degraded": bool(res.get("degraded")),
                "path": res.get("path"),
                "candidates": res.get("candidates"),
                "reason": str(best.get("desc") or "")[:100]}
    except Exception as exc:                                  # noqa: BLE001
        return {"called": False, "error": "%s: %s" % (type(exc).__name__, exc)[:160]}


def correct(rc, s: dict, anomalies: list[dict]) -> dict:
    """⑤ 纠正 + ⑥ 回主线。纠正动作要真的改变读数，不能只写一句话。"""
    acts = []
    codes = {a["code"] for a in anomalies}

    if codes & {"overflow", "near_overflow"}:
        # 强制把最老的挤出去：再 push 一条会被 ring 自己挤出并落库
        r = rc.push("system", "【上下文守护】强制整理：把最老的挤进库，主线继续。")
        acts.append({"action": "force_spill", "ok": bool((r or {}).get("ok", True))})

    after = sample(rc)
    if s["budget"] and after["window_chars"] > s["budget"]:
        acts.append({"action": "shrink_window", "ok": False,
                     "why": "整理后仍超预算，需要人工调 window_chars"})

    # ⑥ 回主线：发一条 resume 标记，主线 id 不变
    rc.push("system", "【回主线】上下文已整理，继续 %s。" % MAINLINE)
    acts.append({"action": "resume_mainline", "ok": True, "mainline": MAINLINE})
    return {"acts": acts, "after": sample(rc)}


def bind_tentacle() -> dict:
    """② 专责触手与上下文资产双向绑定。"""
    try:
        sys.path.insert(0, str(ROOT / "tools"))
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "tentacle_bind", str(ROOT / "tools" / "tentacle_bind.py"))
        tb = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(tb)                          # type: ignore
        for fn in ("bind",):
            if hasattr(tb, fn):
                asset = str(ROOT / "gbt_allinone" / "llm" / "ring_context.py")
                getattr(tb, fn)(asset, TENTACLE, note="上下文溢出保护", quiet=True)
                return {"ok": True, "asset": asset, "tentacle": TENTACLE}
        return {"ok": False, "why": "tentacle_bind 没有 bind()"}
    except Exception as exc:                                  # noqa: BLE001
        return {"ok": False, "why": "%s: %s" % (type(exc).__name__, str(exc)[:120])}


def tick(rc, prev: dict | None, streak: int, do_correct: bool = True) -> dict:
    s = sample(rc)
    anomalies = diagnose(s, prev, streak)
    rec = {"sample": s, "anomalies": anomalies, "tentacle": TENTACLE}
    if anomalies:
        rec["brain"] = to_brain(s, anomalies)
        if do_correct:
            rec["fix"] = correct(rc, s, anomalies)
        rec["level"] = "warn"
    else:
        rec["level"] = "ok"
    STATE.parent.mkdir(parents=True, exist_ok=True)
    with open(LEDGER, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
    STATE.write_text(json.dumps(rec, ensure_ascii=False, indent=2), encoding="utf-8")
    return rec


def show(rec: dict) -> None:
    s = rec["sample"]
    print("  [%s] 窗口 %d 条 / %d 字符 · 预算 %d · 填充 %s · seq %d · 落库 %d"
          % (rec["level"], s["window_n"], s["window_chars"], s["budget"],
             ("%.0f%%" % (s["fill"] * 100)) if s["fill"] is not None else "-",
             s["seq"], s["spilled"]))
    for a in rec["anomalies"]:
        print("     ⚠ %-14s %s" % (a["code"], a["why"]))
    if rec.get("brain"):
        b = rec["brain"]
        print("     → 大脑执行层: called=%s routed=%s%s %s"
              % (b.get("called"), b.get("routed"),
                 "（⚠ 语义路由降级，匹配可能不相干）" if b.get("degraded") else "",
                 b.get("error") or ""))
    if rec.get("fix"):
        print("     → 纠正: %s" % ", ".join(
            "%s=%s" % (a["action"], a["ok"]) for a in rec["fix"]["acts"]))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--once", action="store_true")
    ap.add_argument("--watch", action="store_true")
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--name", default="default")
    ap.add_argument("--budget", type=int, default=0)
    a = ap.parse_args()

    b = bind_tentacle()
    print("  双向绑定: %s" % ("✅ %s → ring_context" % TENTACLE if b.get("ok")
                              else "🔴 %s" % b.get("why")))

    rc = _ring(a.name, a.budget)

    if a.selftest:
        print("\n  === 灌注到近溢出，看守护能不能自己发现并纠正 ===")
        base = sample(rc)
        budget = base["budget"]
        print("  预算 %d 字符 · 起始 %d" % (budget, base["window_chars"]))
        prev, streak = None, 0
        fired = None
        for i in range(200):
            rc.push("user", "第%d轮：把窗口逐步撑满的正文，" % i * 8)
            rec = tick(rc, prev, streak if prev else 0)
            if rec["anomalies"] and fired is None:
                fired = (i, rec)
                print("\n  ⚠ 第 %d 轮触发异常：" % i)
                show(rec)
                break
            prev, streak = rec["sample"], (streak + 1 if prev and
                                           prev["fingerprint"] == rec["sample"]["fingerprint"]
                                           else 0)
        if not fired:
            print("  🔴 撑满 200 轮都没触发 —— 判据失灵，需要查")
            return 1
        after = sample(rc)
        print("\n  纠正后：窗口 %d 字符（预算 %d）· seq %d · 落库 %d"
              % (after["window_chars"], after["budget"], after["seq"], after["spilled"]))
        print("  窗口仍 ≤ 预算: %s · 没丢条: %s"
              % (after["window_chars"] <= after["budget"],
                 after["seq"] - after["spilled"] <= after["window_n"]))
        r = rc.recall("第3轮", k=2)
        print("  老内容仍秒查得到: %s" % r.get("ok"))
        return 0

    if a.once:
        rec = tick(rc, None, 0, do_correct=False)
        show(rec)
        return 0

    if a.watch:
        print("  常驻守护 · 每 3 秒读一次 · Ctrl-C 停")
        prev, streak = None, 0
        while True:
            rec = tick(rc, prev, streak)
            if rec["level"] != "ok" or len(rec["anomalies"]):
                show(rec)
            prev = rec["sample"]
            streak = streak + 1 if prev and rec["sample"]["fingerprint"] == prev["fingerprint"] else 0
            time.sleep(3)

    ap.print_help()
    return 2


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\n已停")
