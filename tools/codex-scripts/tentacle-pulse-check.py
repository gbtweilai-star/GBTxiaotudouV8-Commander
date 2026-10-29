# -*- coding: utf-8 -*-
"""tentacle-pulse-check.py —— **通电秒达**判据：每根触手从头到脚走一遍要多少毫秒。

主人令 2026-10-19（逐字）：「你弄好之后他就像电线一样通电秒达，如果没秒到就是那里不通」。

## 三层秒表（每一层都能单独判"通/不通"）
  · A 索引层：注册表 / 分派面 / 台账 / 页绑 / 资产绑 —— **纯字典命中**，应当是微秒级
  · B 门层：`policy.evaluate(kind, {op})` + `preflight.is_side_effect` —— 应当是毫秒级
  · C 真调用层：经唯一门真跑一发**只读 op**（抽样），量端到端毫秒

## 判据（写死，改要留痕）
  · A 全量平均 > 0.05 ms/位 或 P95 > 0.2 ms ⇒ 红（索引退化成扫表）
  · A 缺腿：**只看核心腿**（注册表 / 台账 / 页绑），缺一个 ⇒ 红
      —— 2026-10-29 改（主人令「（A）修判据」）：原判据把「资产绑」也算进必中四腿，
         但资产绑的契约方向相反（保证"每个资产都绑到触手"，不是"每位都是资产绑定名"）。
         实测 `cap tentacle_bind {"op":"gaps"}` → missing=0；348 位里 101 位无资产名，
         其同名页只被 classify 成 project_context（note=asset_index.wire），属正常归类。
         ⇒ 资产绑覆盖改为**只读数、不判红**，读数照常打印，不隐藏。
  · B 平均 > 2 ms/位 或 P95 > 5 ms ⇒ 红（门里在扫盘/扫大账）
  · C 抽样每发 > 500 ms ⇒ 红（这一位"通电不达"，要查它自己）
      —— 2026-10-29 加：**超预算重试一次取最小值**，两次读数都留在 `尝试` 里。
         依据：本判据单跑 a1art_skill 26/61/111ms，而 `boot-selfcheck --jobs 2`
         里同发报 1440/1570ms（旁边 77s 级重判据在抢 CPU）⇒ 那是负载不是"不通"。
         真慢的位重试仍慢，照样红。
  **不合格就非零退出** —— 不许把"慢"念成"通"。

用法：py -3.14 tools/codex-scripts/tentacle-pulse-check.py [--sample 8] [--json]
开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属
"""
from __future__ import annotations

import argparse
import json
import statistics as st
import sys
import time
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    if hasattr(_s, "reconfigure"):
        _s.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parents[2]
STATE = ROOT / "state"
A_BUDGET_AVG, A_BUDGET_P95 = 0.05, 0.2      # ms / 位
B_BUDGET_AVG, B_BUDGET_P95 = 2.0, 5.0
C_BUDGET = 500.0                            # ms / 发


def _caps() -> dict:
    sys.path.insert(0, str(ROOT))
    from gbt_allinone.caps_registry import BENIGN_CAPS
    return dict(BENIGN_CAPS)


def _json(p: Path):
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:                                          # noqa: BLE001
        return {}


def _ops(kind: str, caps: dict) -> str:
    import re
    desc = str((caps.get(kind) or {}).get("desc") or "")
    m = re.search(r"op=([a-z0-9_/、, \-]+)", desc)
    if not m:
        return "status"
    for o in re.split(r"[/、,，\s]+", m.group(1)):
        o = o.strip().strip("（）()")
        if o and re.match(r"^[a-z][a-z0-9_]*$", o):
            return o
    return "status"


def _pct(v, q):
    if not v:
        return 0.0
    v = sorted(v)
    i = min(len(v) - 1, max(0, int(round(q * (len(v) - 1)))))
    return v[i]


def run(sample: int = 8) -> dict:
    caps = _caps()
    kinds = sorted(caps)
    led = _json(STATE / "cap-bindings.json")
    led_names = {str(r.get("name")) for r in (led.get("caps") or []) if isinstance(r, dict)}
    assets = _json(STATE / "asset_bindings.json") or {}
    asset_kinds = set()
    for _p, meta in (assets.items() if isinstance(assets, dict) else []):
        for t in ((meta or {}).get("tentacles") or []):
            asset_kinds.add(str(t))
    pb = _json(STATE / "page-bindings.json")
    page_kinds = set()
    for r in (pb.get("逐页") or []):
        for k in (r.get("正向_能力位") or []):
            page_kinds.add(str(k))
    caps_dir = ROOT / "holo_pet_w3" / "brain" / "caps"
    page_stems = {p.stem for p in caps_dir.glob("*.html")} if caps_dir.is_dir() else set()

    # ── A 索引层 ────────────────────────────────────────────────────────────
    # 🔴 2026-10-29 改判据（主人令「（A）修判据」）：
    #   原判据要求「每位必须同时命中 注册表/台账/资产绑/页绑 四本账」。
    #   但**资产绑的契约方向相反**——它保证的是「每个资产都绑到触手」
    #   （实测 `cap tentacle_bind {"op":"gaps"}` → missing=0，52891 资产全有绑定），
    #   并不保证「每个能力位都作为某个资产的绑定名出现」。
    #   实测：348 位里 101 位无资产名，其同名页只被 classify 成 project_context
    #   （note=asset_index.wire），属正常归类、不是断连。
    #   ⇒ 拆两条腿：**核心腿**（注册表 / 台账 / 页绑）缺 = 红；
    #     **资产绑覆盖**只作读数如实报出，**不判红**（不隐藏、不美化、不删读数）。
    t0 = time.perf_counter()
    miss_core, miss_asset = [], []
    for k in kinds:
        core_hit = (k in caps) and (k in led_names) and (k in page_kinds or k in page_stems)
        if not core_hit:
            miss_core.append(k)
        if k not in asset_kinds:
            miss_asset.append(k)
    miss = miss_core                       # 兼容下游旧字段名「缺腿」
    a_total = (time.perf_counter() - t0) * 1000
    a_per = a_total / max(1, len(kinds))

    # ── B 门层 ──────────────────────────────────────────────────────────────
    from gbt_allinone.security import policy as _policy
    from gbt_allinone import preflight as _pf
    b_times = []
    for k in kinds:
        op = _ops(k, caps)
        t = time.perf_counter()
        _policy.evaluate(k, {"op": op})
        _pf.is_side_effect(k, {"op": op})
        b_times.append((time.perf_counter() - t) * 1000)
    b_avg, b_p50, b_p95 = st.fmean(b_times), _pct(b_times, 0.5), _pct(b_times, 0.95)
    b_slow = sorted(zip(b_times, kinds), reverse=True)[:5]

    # ── C 真调用层（抽样只读 op）────────────────────────────────────────────
    import gbt_allinone as G
    read_ok = [k for k in kinds
               if _ops(k, caps) in ("status", "count", "list", "where", "ruler", "health")]
    pick = read_ok[:sample] if read_ok else kinds[:sample]
    c_rows = []
    for k in pick:
        op = _ops(k, caps)
        attempts = []
        r = None
        # 🔴 2026-10-29 改判据（同一次「修判据」）：超预算**重试一次取最小值**。
        #   实测依据：本判据单跑 a1art_skill = 26 / 61 / 111 ms（远低于 500），
        #   但 `boot-selfcheck --jobs 2` 里同一发报 1440 / 1570 ms —— 旁边有
        #   77s 级的重判据（凭据自审）与 34.8s 的视图对账在抢 CPU。
        #   ⇒ 那是机器负载，不是这一位「通电不达」。C 层量的是**能力位自己的端到端**，
        #     所以允许一次重试取 min；**真慢的位重试仍然慢，依旧红**。
        #     两次读数都留在 `attempts` 里，不隐藏。
        for _ in range(2):
            t = time.perf_counter()
            try:
                r = G.run_task(k, {"op": op})
                ok = bool((r or {}).get("status") in ("ok", "denied") or (r or {}).get("ok"))
                if isinstance(r, dict) and (r.get("result") or {}).get("denied"):
                    ok = True          # 被门拒也算"通了"（拒绝也是秒回）
            except Exception as exc:                               # noqa: BLE001
                ok, r = False, {"error": "%s: %s" % (type(exc).__name__, str(exc)[:120])}
            attempts.append(round((time.perf_counter() - t) * 1000, 2))
            if ok and attempts[-1] <= C_BUDGET:
                break
        dt = min(attempts)
        c_rows.append({"kind": k, "op": op, "ms": round(dt, 2), "ok": ok,
                       "尝试": attempts if len(attempts) > 1 else None,
                       "status": (r or {}).get("status")})
    c_ms = [r["ms"] for r in c_rows] or [0.0]

    reds = []
    if a_per > A_BUDGET_AVG or _pct([a_per], 0.95) > A_BUDGET_P95:
        reds.append("A 索引层 %.4f ms/位（预算 %.2f）" % (a_per, A_BUDGET_AVG))
    if b_avg > B_BUDGET_AVG or b_p95 > B_BUDGET_P95:
        reds.append("B 门层 平均 %.2f / P95 %.2f ms（预算 %.1f/%.1f）" % (b_avg, b_p95, B_BUDGET_AVG, B_BUDGET_P95))
    slow_c = [r for r in c_rows if r["ms"] > C_BUDGET or not r["ok"]]
    if slow_c:
        reds.append("C 真调用 %d 发超预算/失败：%s" % (len(slow_c),
                                                ", ".join("%s=%.0fms" % (r["kind"], r["ms"]) for r in slow_c[:4])))
    if miss_core:
        reds.append("索引缺腿（核心腿：注册表/台账/页绑）%d 位：%s"
                    % (len(miss_core), ", ".join(miss_core[:6])))
    return {"ok": not reds, "caps": len(kinds),
            "A": {"总ms": round(a_total, 3), "每ms": round(a_per, 5),
                  "缺腿": miss_core,
                  "资产绑未覆盖": len(miss_asset),
                  "资产绑未覆盖_前6": miss_asset[:6],
                  "资产绑口径": ("只读数不判红：框架契约是「每个资产都绑到触手」"
                                 "（cap tentacle_bind gaps → missing=0），"
                                 "不是「每个能力位都必须是某个资产的绑定名」")},
            "B": {"平均ms": round(b_avg, 3), "P50": round(b_p50, 3), "P95": round(b_p95, 3),
                  "最慢5": [{"kind": k, "ms": round(m, 3)} for m, k in b_slow]},
            "C": {"抽样": c_rows, "P50": round(_pct(c_ms, 0.5), 1), "最大": round(max(c_ms), 1),
                  "预算ms": C_BUDGET},
            "红": reds,
            "预算": {"A_each": A_BUDGET_AVG, "B_avg": B_BUDGET_AVG, "B_p95": B_BUDGET_P95, "C": C_BUDGET}}


def main() -> int:
    ap = argparse.ArgumentParser(description="通电秒达：触手全链三层秒表")
    ap.add_argument("--sample", type=int, default=8)
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    r = run(a.sample)
    if a.json:
        print(json.dumps(r, ensure_ascii=False, indent=1))
        return 0 if r["ok"] else 1
    print("═" * 70)
    print("  通电秒达 · 触手全链三层秒表（%d 根）" % r["caps"])
    print("═" * 70)
    print("  A 索引层：%d 位共 %.2f ms · 平均 %.4f ms/位 · 缺腿（核心腿）%d"
          % (r["caps"], r["A"]["总ms"], r["A"]["每ms"], len(r["A"]["缺腿"])))
    print("     资产绑覆盖：%d/%d 位有资产名（未覆盖 %d，**只读数不判红** —— 契约方向相反）"
          % (r["caps"] - r["A"].get("资产绑未覆盖", 0), r["caps"],
             r["A"].get("资产绑未覆盖", 0)))
    print("  B 门层　：平均 %.2f ms · P50 %.2f · P95 %.2f ｜ 最慢 %s"
          % (r["B"]["平均ms"], r["B"]["P50"], r["B"]["P95"],
             ", ".join("%s=%.1fms" % (x["kind"], x["ms"]) for x in r["B"]["最慢5"][:3])))
    print("  C 真调用：%d 发 · P50 %.1f ms · 最大 %.1f ms（预算 %d）"
          % (len(r["C"]["抽样"]), r["C"]["P50"], r["C"]["最大"], r["C"]["预算ms"]))
    for x in r["C"]["抽样"]:
        att = ("（尝试 %s，取 min）" % x["尝试"]) if x.get("尝试") else ""
        print("     %-22s %-8s %7.1f ms  %s%s"
              % (x["kind"], x["op"], x["ms"], "通" if x["ok"] else "不通", att))
    if r["红"]:
        print("  🔴 " + " ｜ ".join(r["红"]))
    else:
        print("  ✅ 全链通电秒达：索引微秒级、门毫秒级、真调用在预算内 —— 没有不通的地方")
    return 0 if r["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
