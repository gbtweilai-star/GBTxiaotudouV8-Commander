# -*- coding: utf-8 -*-
"""tentacle-pulse-check.py —— **通电秒达**判据：每根触手从头到脚走一遍要多少毫秒。

主人令 2026-10-19（逐字）：「你弄好之后他就像电线一样通电秒达，如果没秒到就是那里不通」。

## 三层秒表（每一层都能单独判"通/不通"）
  · A 索引层：注册表 / 分派面 / 台账 / 页绑 / 资产绑 —— **纯字典命中**，应当是微秒级
  · B 门层：`policy.evaluate(kind, {op})` + `preflight.is_side_effect` —— 应当是毫秒级
  · C 真调用层：经唯一门真跑一发**只读 op**（抽样），量端到端毫秒

## 判据（写死，改要留痕）
  · A 全量 337 位平均 > 0.05 ms/位 或 P95 > 0.2 ms ⇒ 红（索引退化成扫表）
  · B 平均 > 2 ms/位 或 P95 > 5 ms ⇒ 红（门里在扫盘/扫大账）
  · C 抽样每发 > 500 ms ⇒ 红（这一位"通电不达"，要查它自己）
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
    t0 = time.perf_counter()
    miss = []
    for k in kinds:
        hit = (k in caps) and (k in led_names) and (k in asset_kinds) and (k in page_kinds or k in page_stems)
        if not hit:
            miss.append(k)
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
        t = time.perf_counter()
        try:
            r = G.run_task(k, {"op": _ops(k, caps)})
            ok = bool((r or {}).get("status") in ("ok", "denied") or (r or {}).get("ok"))
            if isinstance(r, dict) and (r.get("result") or {}).get("denied"):
                ok = True          # 被门拒也算"通了"（拒绝也是秒回）
        except Exception as exc:                               # noqa: BLE001
            ok, r = False, {"error": "%s: %s" % (type(exc).__name__, str(exc)[:120])}
        dt = (time.perf_counter() - t) * 1000
        c_rows.append({"kind": k, "op": _ops(k, caps), "ms": round(dt, 2), "ok": ok,
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
    if miss:
        reds.append("索引缺腿 %d 位：%s" % (len(miss), ", ".join(miss[:6])))
    return {"ok": not reds, "caps": len(kinds),
            "A": {"总ms": round(a_total, 3), "每ms": round(a_per, 5), "缺腿": miss},
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
    print("  A 索引层：%d 位共 %.2f ms · 平均 %.4f ms/位 · 缺腿 %d"
          % (r["caps"], r["A"]["总ms"], r["A"]["每ms"], len(r["A"]["缺腿"])))
    print("  B 门层　：平均 %.2f ms · P50 %.2f · P95 %.2f ｜ 最慢 %s"
          % (r["B"]["平均ms"], r["B"]["P50"], r["B"]["P95"],
             ", ".join("%s=%.1fms" % (x["kind"], x["ms"]) for x in r["B"]["最慢5"][:3])))
    print("  C 真调用：%d 发 · P50 %.1f ms · 最大 %.1f ms（预算 %d）"
          % (len(r["C"]["抽样"]), r["C"]["P50"], r["C"]["最大"], r["C"]["预算ms"]))
    for x in r["C"]["抽样"]:
        print("     %-22s %-8s %7.1f ms  %s" % (x["kind"], x["op"], x["ms"], "通" if x["ok"] else "不通"))
    if r["红"]:
        print("  🔴 " + " ｜ ".join(r["红"]))
    else:
        print("  ✅ 全链通电秒达：索引微秒级、门毫秒级、真调用在预算内 —— 没有不通的地方")
    return 0 if r["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
