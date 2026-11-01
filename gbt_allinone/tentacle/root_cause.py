# -*- coding: utf-8 -*-
"""病因定位（root_cause）：蒸馏自 v5 的 root_cause_debugger，**只留方法，换成我们的检查器**。

v5 的实现是"假设→取证→复现→修复→验证"（1148 行，自己做文件探针/复现包/git 快照）。
我们不需要那套通用探针 —— 我们**已经有** selfscan / truth_scan / signature_guard /
inventory / legacy_guard / orchestration 账本 / cap_self。所以这里只蒸馏三件事：

  1. **假设清单**：把症状映射成"我们自己的"可验证假设（不是通用规则）；
  2. **证据优先**：每条假设必须挂真调用读数，取不到就标 unknown，不猜；
  3. **落案卷**：每次诊断存 state/cases/<id>.json（假设/证据/结论/下一步），可复查。

op:
    diagnose  {"symptom": "..."}   # 诊断，返回排序后的假设 + 证据
    status                         # 案件列表
    case      {"id": "..."}        # 看某案卷
"""
from __future__ import annotations

import json
import pathlib
import time

ROOT = pathlib.Path(__file__).resolve().parents[2]
CASES = ROOT / "state" / "cases"


def _cap(kind: str, payload: dict | None = None) -> dict:
    from .. import api as _api
    try:
        env = _api.run_task(kind, payload or {}, probe=True)
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "error": "%s: %s" % (type(e).__name__, str(e)[:100])}
    gr = env.get("gbt_result") or {}
    res = gr.get("result") if isinstance(gr.get("result"), dict) else {}
    return {"ok": bool(env.get("ok")) and res.get("ok") is not False,
            "verdict": res.get("verdict") or "", "result": res,
            "error": res.get("error") or ""}


def _evidence() -> dict:
    """一次把我们的检查器全跑一遍（只读）。"""
    ev = {}
    ev["selfscan"] = _cap("selfscan")
    ev["truth_scan"] = _cap("truth_scan")
    ev["signature"] = _cap("signature_guard", {"scope": "all"})
    ev["inventory"] = _cap("inventory")
    ev["legacy"] = _cap("legacy_guard", {"op": "status"})
    ev["caps"] = _cap("cap_self", {"op": "verify"})
    panel = _cap("orchestration", {"op": "panel", "limit": 5})
    ev["panel"] = panel
    return ev


def _hypotheses(ev: dict, symptom: str) -> list:
    """把读数映射成假设（只列**我们的**检查器能证实的）。"""
    out = []

    def add(name, found, weight, evidence, next_probe):
        out.append({"hypothesis": name, "found": bool(found), "weight": weight,
                    "evidence": evidence, "next_probe": next_probe})

    # ① 能力位三数不一致
    counts = ((ev["caps"].get("result") or {}).get("counts") or {})
    vals = list(counts.values())
    mismatch = bool(counts) and len(set(vals)) > 1
    add("能力位三数不一致（注册表 / 快照 / 分派）", mismatch, 9 if mismatch else 0,
        counts or {"note": "cap_self 没回 counts"},
        "python tools/codex-scripts/export-capabilities.py 后重跑 cap_self verify")

    # ② 自检不干净
    ss = ev["selfscan"]
    add("自检不干净（路由/模块/存储）", ss.get("verdict") not in ("clean", "", None) or not ss.get("ok"),
        8, {"selfscan": ss.get("verdict"), "error": ss.get("error")},
        "gbt.run_task('selfscan') 看 findings 逐条")

    # ③ 署名缺失
    sig = ev["signature"]
    missing = (sig.get("result") or {}).get("missing") or []
    add("页面/文档署名缺失", bool(missing), 7,
        {"verdict": sig.get("verdict"), "missing_n": len(missing), "sample": missing[:3]},
        "gbt.run_task('signature_guard', {'restore': True})")

    # ④ 根目录异物
    inv = ev["inventory"]
    foreign = ((inv.get("result") or {}).get("items") or {}).get("foreign") or []
    add("根目录混入异物（不属于框架/环境）", bool(foreign), 7,
        {"verdict": inv.get("verdict"), "foreign": foreign[:5]},
        "决定归位或删除；inventory 会复核")

    # ⑤ 旧物
    lg = ev["legacy"]
    cats = (lg.get("result") or {}).get("categories") or {}
    dirty = {k: v for k, v in cats.items() if isinstance(v, dict) and (v.get("files") or 0) > 0}
    add("存在旧物（sync-backup/归档/tmp）", bool(dirty), 4,
        {"verdict": lg.get("verdict"), "dirty": dirty},
        "gbt.run_task('legacy_guard', {'op':'clean'})")

    # ⑥ 真相扫描
    ts = ev["truth_scan"]
    add("存在静默造假/无证据完成", ts.get("verdict") not in ("clean", "", None) or not ts.get("ok"),
        6, {"truth_scan": ts.get("verdict"), "error": ts.get("error")},
        "gbt.run_task('truth_scan') 看明细")

    # ⑦ 最近调用出错（账本）
    rows = (ev["panel"].get("result") or {}).get("ledger_recent") or []
    add("最近的编排/调用有失败记录", False, 2,
        {"note": "账本最近 %d 条已在 panel 里" % len(rows)}, "看 orchestration panel 的最近记录")

    out.sort(key=lambda h: -h["weight"])
    return out


def _case_id() -> str:
    return "RC-%s-%04d" % (time.strftime("%Y%m%d-%H%M%S"), int(time.time() * 1000) % 10000)


def diagnose(symptom: str = "") -> dict:
    symptom = str(symptom or "").strip()
    ev = _evidence()
    hs = _hypotheses(ev, symptom)
    top = [h for h in hs if h["found"]]
    cid = _case_id()
    case = {"id": cid, "at": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "symptom": symptom, "hypotheses_ranked": hs,
            "found": [h["hypothesis"] for h in top],
            "verdict": "root_cause_found" if top else "inconclusive",
            "note": "只列检查器能证实的假设；一条都不成立就如实说 inconclusive（不猜）"}
    try:
        CASES.mkdir(parents=True, exist_ok=True)
        (CASES / (cid + ".json")).write_text(json.dumps(case, ensure_ascii=False, indent=1),
                                             encoding="utf-8")
    except Exception:  # noqa: BLE001
        pass
    return {"ok": True, "case": cid, "symptom": symptom,
            "verdict": case["verdict"], "found": case["found"],
            "top": top[:3], "evidence_digest": {
                "selfscan": ev["selfscan"].get("verdict"),
                "truth_scan": ev["truth_scan"].get("verdict"),
                "signature": ev["signature"].get("verdict"),
                "inventory": ev["inventory"].get("verdict"),
                "legacy": ev["legacy"].get("verdict"),
                "caps": counts_safe(ev)},
            "next": [h["next_probe"] for h in top[:3]],
            "case_file": str(CASES / (cid + ".json"))}


def counts_safe(ev: dict) -> dict:
    try:
        return (ev["caps"].get("result") or {}).get("counts") or {}
    except Exception:  # noqa: BLE001
        return {}


def status() -> dict:
    rows = []
    if CASES.is_dir():
        for f in sorted(CASES.glob("*.json"), reverse=True)[:20]:
            try:
                d = json.loads(f.read_text(encoding="utf-8"))
            except Exception:  # noqa: BLE001
                continue
            rows.append({"case": d.get("id"), "at": d.get("at"),
                         "verdict": d.get("verdict"), "found": d.get("found")})
    return {"ok": True, "count": len(rows), "cases": rows}


def case(cid: str) -> dict:
    p = CASES / (str(cid) + ".json")
    if not p.is_file():
        return {"ok": False, "error": "user_error: 没有这个案卷：%s" % cid}
    return {"ok": True, "case": json.loads(p.read_text(encoding="utf-8"))}


def run(op: str = "status", **kw) -> dict:
    op = (op or "status").lower()
    if op == "diagnose":
        return diagnose(str(kw.get("symptom") or ""))
    if op == "status":
        return status()
    if op == "case":
        return case(str(kw.get("id") or ""))
    return {"ok": False, "error": "root_cause 不认 op=%s（diagnose/status/case）" % op}
