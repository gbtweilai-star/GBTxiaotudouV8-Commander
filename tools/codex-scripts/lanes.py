# -*- coding: utf-8 -*-
"""车道仪表：一句话进来，回答「哪个入口会接、要不要惊动模型」。

为什么要有：仓里有**两条**入口，覆盖完全不同 ——
  · /api/chat → _chat：capability_router（4 类）→ tactile pulse（2 个只读位）→ 算子提示 → 模型
  · api.run_task("brain_route")：视觉作战区 → 触手方法快车道 → 算子闸门 → 语义主路
此前只有「种子表」看方法侧、只有 stats 看闸门，**没有任何一个地方能同时看到两边**，
于是「这条到底会不会直达」全靠人猜。

本脚本**只判不执行**：不调模型、不写盘、不改台账。
  python tools/codex-scripts/lanes.py "看一眼屏幕" "列一下都开了什么窗口"
  Get-Content cmds.txt | python tools/codex-scripts/lanes.py --stdin

输出 ASCII 安全 JSON（控制台是 GBK，中文会炸）。
"""
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _ms(t0):
    return round((time.perf_counter() - t0) * 1000, 1)


def probe(text: str) -> dict:
    row = {"q": text}
    t = time.perf_counter()
    # ① chat：capability_router（判类；真执行在 _chat 里）
    try:
        from gbt_allinone import capability_router as CR
        c = CR.classify(text)
        row["cr_intent"] = c.get("intent") or ""
        row["cr_question"] = bool(c.get("question"))
        row["cr_error"] = c.get("error") or ""
    except Exception as exc:  # noqa: BLE001
        row["cr_error"] = "%s: %s" % (type(exc).__name__, str(exc)[:80])
    row["cr_ms"] = _ms(t)

    # ② chat：tactile pulse（只判能不能直达，不执行）
    t = time.perf_counter()
    try:
        from gbt_allinone import tactile_tree as TT
        p = TT.run("pulse", query=text)
        row["pulse"] = p.get("status") or ""
        row["pulse_cap"] = p.get("cap") or p.get("candidate") or ""
        row["pulse_why"] = str(p.get("why") or "")[:80]
    except Exception as exc:  # noqa: BLE001
        row["pulse"] = "error"
        row["pulse_why"] = "%s: %s" % (type(exc).__name__, str(exc)[:80])
    row["pulse_ms"] = _ms(t)

    # ③ brain_route：方法快车道
    t = time.perf_counter()
    try:
        from gbt_allinone import brain_exec as BE
        m = BE._method_lane(text)
        row["method"] = (m or {}).get("best", {}).get("method") or ""
    except Exception as exc:  # noqa: BLE001
        row["method"] = ""
        row["method_err"] = "%s: %s" % (type(exc).__name__, str(exc)[:80])
    row["method_ms"] = _ms(t)

    # ④ 算子闸门（两条入口共用；只有 brain_route 会直达，_chat 只拿它做提示）
    t = time.perf_counter()
    try:
        from gbt_allinone import operator_index as OI
        g = OI.gate(text)
        top = ((g.get("top") or [{}])[0]) or {}
        row["gate"] = {"hit": bool(g.get("hit")), "cap": top.get("cap") or "",
                       "score": top.get("score"), "margin": g.get("margin"),
                       "why": g.get("why")}
        n = OI.hint_note(text, gate_result=g)
        row["hint"] = n.get("note") or ""
    except Exception as exc:  # noqa: BLE001
        row["gate"] = {"hit": False, "cap": "", "why": "%s: %s" % (type(exc).__name__, str(exc)[:80])}
        row["hint"] = ""
    row["gate_ms"] = _ms(t)

    # 结论：两个入口各自怎么走
    if row["cr_intent"] and not row["cr_question"] and not row["cr_error"]:
        row["chat"] = "direct:" + row["cr_intent"]
    elif row["pulse"] == "ready":
        row["chat"] = "direct:pulse"
    elif row["pulse"] == "denied":
        row["chat"] = "denied"
    elif row["hint"]:
        row["chat"] = "model+hint"
    else:
        row["chat"] = "model"

    if row["method"]:
        row["brain"] = "method:" + row["method"]
    elif row["gate"]["hit"]:
        row["brain"] = "operator:" + row["gate"]["cap"]
    else:
        row["brain"] = "semantic"
    return row


def main(argv=None) -> int:
    args = list(argv if argv is not None else sys.argv[1:])
    if args and args[0] == "--stdin":
        items = [ln.strip() for ln in sys.stdin.read().splitlines()]
    else:
        items = args
    items = [x for x in items if x]
    if not items:
        print("用法：lanes.py \"句子\" [...]   或   lanes.py --stdin", file=sys.stderr)
        return 2
    rows = [probe(x) for x in items]
    direct = sum(1 for r in rows if str(r["chat"]).startswith("direct:"))
    denied = sum(1 for r in rows if r["chat"] == "denied")
    hinted = sum(1 for r in rows if r["chat"] == "model+hint")
    brain_fast = sum(1 for r in rows if str(r["brain"]).split(":")[0] in ("method", "operator"))
    print(json.dumps({
        "n": len(rows),
        "chat_direct": direct, "chat_denied": denied, "chat_hinted": hinted,
        "chat_model": len(rows) - direct - denied - hinted,
        "brain_local": brain_fast,
        "ms_max": max(r["cr_ms"] + r["pulse_ms"] + r["method_ms"] + r["gate_ms"] for r in rows),
        "rows": rows,
    }, ensure_ascii=True, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
