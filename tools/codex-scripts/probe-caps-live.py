# -*- coding: utf-8 -*-
"""能力自证：把**每一位只读能力**真调一次，逐位留读数（证明"能力属实"，不是"模型会背"）。

安全边界（写死，不许放宽）：
  · `safe=true`（只读）且不需要参数 ⇒ **真调**（空 payload）。
  · `safe=true` 但要参数 ⇒ 不瞎编参数，标 `needs_params`（如实记）。
  · `safe=false`（写盘/花钱/出网）⇒ **一律不跑**，标 `needs_auth`。开源测试不越授权门。
每发调用带 20 秒看门狗；超时记为 timeout（不记 0、不记 ok）。

产出：
  outputs/open-source-release/data/capability-live-test.json   （逐位读数）
  .scratch/caps_live_summary.json                              （按域汇总）
用法：
  py -3.14 -X utf8 tools/codex-scripts/probe-caps-live.py
"""
from __future__ import annotations

import argparse
import concurrent.futures as cf
import json
import pathlib
import sys
import time
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        pass

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="outputs/open-source-release/data/capability-live-test.json")
    ap.add_argument("--timeout", type=int, default=20)
    ap.add_argument("--limit", type=int, default=0, help="只跑前 N 位（0=全部）")
    a = ap.parse_args()

    from gbt_allinone import api as API

    from gbt_allinone import caps_registry as R
    caps = R.all_caps()
    if a.limit:
        caps = caps[: a.limit]

    rows = []
    t_all = time.time()
    for i, c in enumerate(caps, 1):
        name, safe = c["name"], bool(c.get("safe"))
        need_p = bool(c.get("requires_params"))
        row = {"capability": name, "domain": c.get("domain"), "readonly": safe,
               "requires_params": need_p}
        if not safe:
            row.update({"result": "needs_auth", "ms": None,
                        "note": "会写盘/花钱/出网 ⇒ 未跑（开源测试不越授权门）"})
            rows.append(row)
            continue
        if need_p:
            row.update({"result": "needs_params", "ms": None,
                        "note": "需要业务参数 ⇒ 不瞎编，未跑"})
            rows.append(row)
            continue

        t0 = time.time()
        try:
            with cf.ThreadPoolExecutor(max_workers=1) as ex:
                fut = ex.submit(API.run_task, name, {})
                r = fut.result(timeout=a.timeout)
            ms = int((time.time() - t0) * 1000)
            if not isinstance(r, dict):
                row.update({"result": "bad_shape", "ms": ms, "note": str(type(r).__name__)})
            else:
                denied = bool(r.get("denied"))
                status = str(r.get("status") or "")
                inner = r.get("result") if isinstance(r.get("result"), dict) else {}
                ok = (not denied) and (status == "ok") and (inner.get("ok") is not False)
                row.update({"result": "ok" if ok else ("denied" if denied else "failed"),
                            "ms": ms, "status": status,
                            "denied": denied,
                            "missing_scopes": r.get("missing_scopes") or None,
                            "error": (r.get("reason") or r.get("error")
                                      or (inner.get("error") if isinstance(inner, dict) else None))})
        except cf.TimeoutError:
            row.update({"result": "timeout", "ms": a.timeout * 1000,
                        "note": "超过 %ds 没回" % a.timeout})
        except Exception as e:                                    # noqa: BLE001
            row.update({"result": "exception", "ms": int((time.time() - t0) * 1000),
                        "error": "%s: %s" % (type(e).__name__, str(e)[:160])})
        rows.append(row)
        if i % 20 == 0:
            print("  ... %d/%d" % (i, len(caps)), flush=True)

    # 汇总
    agg: dict[str, dict[str, int]] = {}
    for r in rows:
        d = agg.setdefault(r["domain"] or "other", {})
        d[r["result"]] = d.get(r["result"], 0) + 1
    cnt: dict[str, int] = {}
    for r in rows:
        cnt[r["result"]] = cnt.get(r["result"], 0) + 1

    out = pathlib.Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({
        "at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "total": len(rows),
        "counts": cnt,
        "elapsed_s": round(time.time() - t_all, 1),
        "rule": ("只读且无需参数的能力位**真调一次**；需参数的不瞎编（needs_params）；"
                 "写口/花钱/出网的一律不跑（needs_auth）。超时记 timeout，不记 0。"),
        "by_domain": agg,
        "rows": rows,
    }, ensure_ascii=False, indent=1), encoding="utf-8")

    pathlib.Path(".scratch").mkdir(exist_ok=True)
    pathlib.Path(".scratch/caps_live_summary.json").write_text(
        json.dumps({"counts": cnt, "by_domain": agg, "total": len(rows)},
                   ensure_ascii=False, indent=1), encoding="utf-8")

    print("=" * 60)
    print("总计 %d 位 · 用时 %.1fs" % (len(rows), time.time() - t_all))
    for k in ("ok", "failed", "denied", "timeout", "exception", "needs_params", "needs_auth", "bad_shape"):
        if cnt.get(k):
            print("  %-14s %d" % (k, cnt[k]))
    print("落盘：", out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
