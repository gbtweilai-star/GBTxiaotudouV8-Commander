#!/usr/bin/env python3
"""主脑注意力消费端 —— 把队列里的疑点排布成动作，只对**真解决了的**销账

背景（2026-10-28）：
  队列原来是"只进不出"：三个源（llm_watch / context_guard / duty_board）
  都往里写，没人消费。主脑能看到 35 条未处理，却没有排布。

本器做三件事：
  ① 排布（triage）：按 severity 排序，按 codes 映射到具体动作
  ② 只读动作：能当场确认的直接查（现读，不猜）
  ③ 销账（ack）：**只对已证明确实解决的**销账；其余留在队列并写明卡在哪

绝不做的：
  · 不替主人发授权（越权类只上报，不自动处理）
  · 不因为"处理过了"就销账 —— 要有复核证据
  · 不猜 codes 之外的语义（判不了就说判不了）

用法：
  python3 tools/brain_attention.py                 # 只看板，不动
  python3 tools/brain_attention.py --ack-resolved  # 复核后销掉已解决的
  python3 tools/brain_attention.py --ack <at> --note "理由"
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys
import time

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

# codes → (动作类别, 谁来做, 说明)
ACTIONS: dict[str, tuple[str, str, str]] = {
    "越权声明": ("上报", "主人",
                 "自称已授权/绕过门。**只有主人能发授权**；AI 不得自我解锁，也不得代销账"),
    "完成声明无证据": ("要证据", "人补",
                    "要么补一条能复跑的命令 + 一次真读数，要么把话说回「未验」"),
    "机器事实无现读": ("现读", "可自办",
                    "涉及本机事实（端口/内存/版本）必须现读一次再答，不能凭记忆"),
    "自相矛盾": ("复核", "可自办", "同一答复里前后冲突，需指出冲突点"),
    "数字对不上": ("现读", "可自办", "数字必须与现读一致"),
    "near_overflow": ("已处理", "已自办",
                      "上下文守护已 force_spill + resume_mainline，复核填充已回落即可销"),
    "overflow": ("已处理", "已自办", "环形违约，守护已整理；需人工确认 window_budget"),
    "window_lost": ("复核", "人看", "有条目没落库就丢了，需人工查"),
    "empty_window": ("复核", "人看", "有 seq 但窗口空，需人工查"),
    "stuck": ("复核", "人看", "指纹不变但 seq 在涨，疑似复读"),
}

SEV_NAME = {0: "critical", 1: "high", 2: "medium", 3: "low"}


def queue() -> tuple[list[dict], int]:
    """返回 (最近若干条, **未处理总数**)。

    🔴 2026-10-28：`op=queue` 只回 `rows[-20:]`，真正的总数在 `count`。
       第一版直接把 len(rows) 当总数 ⇒ 显示 20 而实际 33，**口径错了**。
    """
    from gbt_allinone.api import run_task
    r = run_task("llm_watch", {"op": "queue"})
    res = (r.get("gbt_result") or {}).get("result") or r.get("result") or {}
    rows = res.get("rows") or []
    return rows, int(res.get("count") or len(rows))


def triage(rows: list[dict]) -> dict:
    """按 severity 排序并按 codes 映射动作。不改任何东西。"""
    board = []
    for r in rows:
        codes = r.get("codes") or []
        acts = []
        for c in codes:
            a = ACTIONS.get(c)
            if a:
                acts.append({"code": c, "action": a[0], "owner": a[1], "how": a[2]})
            else:
                acts.append({"code": c, "action": "判不了", "owner": "人看",
                             "how": "不在已知判据表里 —— **不猜**，交人"})
        # severity 在不同来源里类型不一（有的是 int、有的是字符串）
        # —— 实测 duty_board 的条目会让排序抛 TypeError，这里统一归一成 int
        try:
            sev = int(r.get("severity", 3))
        except (TypeError, ValueError):
            sev = 3
        board.append({"at": r.get("at"), "kind": r.get("kind"),
                      "severity": sev,
                      "sev_name": SEV_NAME.get(sev, "?"),
                      "codes": codes, "acts": acts,
                      "who": r.get("who")})
    board.sort(key=lambda x: (x["severity"], str(x["at"])))
    return {"total": len(board), "board": board}


def ctx_now_ok() -> dict:
    """现读：上下文现在是否已回落（用于判定 near_overflow 可否销账）。"""
    try:
        from gbt_allinone.llm.ring_context import RingContext
        rc = RingContext(name="default")
        st = rc.stats()
        budget = int(st.get("window_budget") or 0)
        chars = int(st.get("window_chars") or 0)
        fill = (chars / budget) if budget else 0
        return {"ok": fill <= 0.85, "chars": chars, "budget": budget,
                "fill": round(fill, 3)}
    except Exception as exc:                                  # noqa: BLE001
        return {"ok": False, "why": "%s: %s" % (type(exc).__name__, str(exc)[:80])}


def ack(at: str, note: str) -> dict:
    from gbt_allinone.api import run_task
    r = run_task("llm_watch", {"op": "ack", "at": at, "note": note})
    return (r.get("gbt_result") or {}).get("result") or r.get("result") or {}


def show(t: dict) -> None:
    tt = t.get("true_total") or t["total"]
    print("  未处理 %d 条（真实总数）· 本条看板展示最近 %d 条，按严重度排序\n"
          % (tt, t["total"]))
    if not t["total"]:
        print("  队列是空的")
        return
    cur = None
    for row in t["board"]:
        if row["sev_name"] != cur:
            cur = row["sev_name"]
            print("  ── %s ──" % cur.upper())
        print("   %s  %-14s %s" % (row["at"][-8:], row["kind"], row["codes"]))
        for a in row["acts"]:
            print("        · %-12s [%s] %s" % (a["code"], a["owner"], a["action"]))
            print("          %s" % a["how"][:88])


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ack-resolved", action="store_true")
    ap.add_argument("--ack", default="")
    ap.add_argument("--note", default="")
    a = ap.parse_args()

    rows, total = queue()
    t = triage(rows)
    t["true_total"] = total

    if a.ack:
        r = ack(a.ack, a.note or "人工指定销账")
        print("  销账 %s → %s" % (a.ack, r.get("销账") if r.get("ok") else r.get("error")))
        return 0 if r.get("ok") else 1

    show(t)

    if a.ack_resolved:
        print("\n  === 复核后销账（只销已证明确实解决的）===")
        c = ctx_now_ok()
        print("  现读上下文: %s 字 / %s 预算 · 填充 %s · 已回落=%s"
              % (c.get("chars"), c.get("budget"), c.get("fill"), c.get("ok")))
        done = skip = 0
        for row in t["board"]:
            codes = set(row["codes"])
            # 只销"上下文类 且 现在确实已回落"的 —— 其余一律留着
            if codes & {"near_overflow", "overflow"} and c.get("ok") and row["kind"] == "context_guard":
                r = ack(row["at"], "复核：上下文填充已回落至 %s（≤0.85）" % c.get("fill"))
                if r.get("ok"):
                    done += 1
                    print("    ✅ 销账 %s %s" % (row["at"], row["codes"]))
                else:
                    skip += 1
                    print("    ⚠ 销不动 %s：%s" % (row["at"], r.get("error")))
            else:
                skip += 1
        print("\n  销账 %d 条 · 留在队列 %d 条（其余需主人/人补，不代销）" % (done, skip))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\n已停")
