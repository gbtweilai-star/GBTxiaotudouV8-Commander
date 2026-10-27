# -*- coding: utf-8 -*-
"""多域监控（补缺）：30 个域 × 只读能力位逐域跑一遍，出基线，支持回归对比。

为什么要有它：这轮改了 `caps_registry`、`cloud_llm`、`key_gateway`，
"修一处坏一处"这种事故**只有基线对比才抓得住**——单次跑绿证明不了"没弄坏别的"。

用法：
  py -3.14 -X utf8 tools/codex-scripts/multi-domain-monitor.py                # 跑一遍并存基线
  py -3.14 -X utf8 tools/codex-scripts/multi-domain-monitor.py --diff         # 与基线对比，报"回归/修好"
  py -3.14 -X utf8 tools/codex-scripts/multi-domain-monitor.py --diff --strict # 有回归就非零退出
口径：
  · 只跑 safe=true 且不需要参数的位（写口/需参数一律不跑，如实计入 untouched）
  · 每发 15s 看门狗；超时记 timeout，不记 0
  · 基线存 state/monitor/domain-baseline.json（换代码前跑一次 = 有了"改前对照"）
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
BASE = ROOT / "state" / "monitor" / "domain-baseline.json"


def run_one(cap: str, timeout: int) -> dict:
    """单能力探活 —— **用可杀子进程**，不用线程。

    🔴 2026-10-28 修（真 bug，不是调参）：
      原实现是 `ThreadPoolExecutor(1).submit(...).result(timeout=)`。
      Python **线程取消不了** —— result(timeout) 只是调用方不等了，
      挂死的工作线程仍在跑并永久占住那个 worker。实测跑到 security 域后
      **整个监控死锁**：日志 4 分钟不写、进程还在、只剩 0/1/2 三个 fd。

      改成子进程：超时直接 kill，资源全还回来，账上记 timeout 继续往下走。
      子进程 tools/cap_probe.py 走**同一个唯一门 run_task**，口径不变。
    """
    import json as _json
    import pathlib as _pl
    import subprocess as _sp
    import sys as _sys

    root = _pl.Path(__file__).resolve().parents[2]
    worker = root / "tools" / "cap_probe.py"
    t0 = time.time()
    try:
        p = _sp.run([_sys.executable, str(worker), cap],
                    capture_output=True, text=True, timeout=timeout, cwd=str(root))
    except _sp.TimeoutExpired:
        return {"result": "timeout", "ms": timeout * 1000,
                "why": "> %ds（子进程已 kill）" % timeout}
    except Exception as e:                                    # noqa: BLE001
        return {"result": "exception", "ms": int((time.time() - t0) * 1000),
                "why": "%s: %s" % (type(e).__name__, str(e)[:120])}
    ms = int((time.time() - t0) * 1000)
    line = (p.stdout or "").strip().splitlines()
    if not line:
        return {"result": "exception", "ms": ms,
                "why": "子进程无输出（rc=%s）%s" % (p.returncode, (p.stderr or "")[-100:])}
    try:
        d = _json.loads(line[-1])
    except Exception:                                         # noqa: BLE001
        return {"result": "exception", "ms": ms, "why": "非 JSON: " + line[-1][:100]}
    out = {"result": str(d.get("result") or "failed"), "ms": int(d.get("ms") or ms)}
    if d.get("why"):
        out["why"] = str(d["why"])[:160]
    if out["result"] == "denied":
        import re
        m = re.search(r"（([a-z_]+)）", out.get("why") or "")
        out["missing_scopes"] = [m.group(1)] if m else None
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--diff", action="store_true")
    ap.add_argument("--strict", action="store_true")
    ap.add_argument("--timeout", type=int, default=90)  # 安全扫描类要 30~65s，别用 15s 把它记成坏
    # 2026-10-21 加：把本轮读数（含 diff 结论）落一份给交付物用。
    # 理由（P9 账没有写手必烂）：开源仓里的 data/*.json 若是手抄的，下一次跑监控它不会自动更新。
    ap.add_argument("--out", default="", help="把本轮读数（含 diff 结论）另存到指定路径")
    a = ap.parse_args()

    from gbt_allinone import caps_registry as R

    caps = R.all_caps()
    by_dom: dict[str, list[str]] = {}
    skipped: dict[str, int] = {}
    for c in caps:
        dom = c.get("domain") or "other"
        if c.get("safe") and not c.get("requires_params"):
            by_dom.setdefault(dom, []).append(c["name"])
        else:
            skipped[dom] = skipped.get(dom, 0) + 1

    print("多域监控：%d 个域 · 测 %d 位只读位（另有 %d 位写口/需参数不跑）"
          % (len(by_dom), sum(len(v) for v in by_dom.values()), sum(skipped.values())))

    now = {"at": time.strftime("%Y-%m-%dT%H:%M:%S"), "domains": {}, "per_cap": {}}
    t0 = time.time()
    for dom in sorted(by_dom):
        rows = {}
        for cap in by_dom[dom]:
            r = run_one(cap, a.timeout)
            rows[cap] = r["result"]
            now["per_cap"][cap] = r
        ok = sum(1 for v in rows.values() if v == "ok")
        bad = {k: v for k, v in rows.items() if v != "ok"}
        now["domains"][dom] = {"tested": len(rows), "ok": ok,
                               "skip": skipped.get(dom, 0), "bad": bad}
        flag = "✅" if not bad else "⚠️"
        print("  %s %-13s 测 %2d · 通过 %2d · 未通过 %s"
              % (flag, dom, len(rows), ok, ", ".join("%s=%s" % (k, v) for k, v in bad.items()) if bad else "—"))
    now["elapsed_s"] = round(time.time() - t0, 1)
    tot_ok = sum(d["ok"] for d in now["domains"].values())
    tot = sum(d["tested"] for d in now["domains"].values())
    print("合计：%d/%d 通过 · 用时 %.1fs" % (tot_ok, tot, now["elapsed_s"]))

    BASE.parent.mkdir(parents=True, exist_ok=True)

    # 2026-10-21 加（F19 的教训：**失败的那个名字必须留住**）：上一轮出现过一次
    # 「1 条回归」，而我当时把输出用 Select-String 过滤掉了 ⇒ 失败位名字没留下来，
    # 事后只能靠整面复跑来"猜它是不是抖动"。现在**不论带不带 --out**，每轮都自动落一份
    # 全量读数 + diff 明细到 state/monitor/，名字再也不会因为打印被过滤而丢失。
    def _always_save(diff: dict | None) -> None:
        try:
            last = BASE.parent / "last-run.json"
            last.write_text(json.dumps(now, ensure_ascii=False, indent=1), encoding="utf-8")
            if diff is not None:
                (BASE.parent / "last-diff.json").write_text(
                    json.dumps({"at": now["at"], "totals": {"tested": tot, "ok": tot_ok,
                                                            "not_ok": tot - tot_ok},
                                "diff": diff}, ensure_ascii=False, indent=1), encoding="utf-8")
        except Exception as e:                                    # noqa: BLE001
            print("（自动留档失败：%s: %s）" % (type(e).__name__, str(e)[:80]))

    def _dump(diff: dict | None) -> None:
        _always_save(diff)
        if not a.out:
            return
        out = ROOT / a.out if not pathlib.Path(a.out).is_absolute() else pathlib.Path(a.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        payload = dict(now)
        payload["totals"] = {"tested": tot, "ok": tot_ok, "not_ok": tot - tot_ok}
        payload["diff"] = diff
        payload["baseline"] = str(BASE.relative_to(ROOT))
        out.write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
        print("读数已落：%s" % out)

    if not a.diff:
        if BASE.is_file():
            old = json.loads(BASE.read_text(encoding="utf-8"))
            bak = BASE.with_suffix(".prev.json")
            bak.write_text(json.dumps(old, ensure_ascii=False, indent=1), encoding="utf-8")
        BASE.write_text(json.dumps(now, ensure_ascii=False, indent=1), encoding="utf-8")
        print("基线已写：%s（上一次存到 .prev.json）" % BASE.relative_to(ROOT))
        _dump(None)
        return 0

    if not BASE.is_file():
        print("没有基线可比：先跑一次不带 --diff")
        return 2
    base = json.loads(BASE.read_text(encoding="utf-8"))
    regress, fixed = [], []
    for cap, cur in now["per_cap"].items():
        old = (base.get("per_cap") or {}).get(cap)
        if not old:
            continue
        if old.get("result") == "ok" and cur.get("result") != "ok":
            regress.append((cap, cur.get("result"), cur.get("why")))
        elif old.get("result") != "ok" and cur.get("result") == "ok":
            fixed.append((cap, old.get("result")))
    print("-" * 62)
    print("回归（改前 ok → 现在不 ok）：%d" % len(regress))
    for cap, res, why in regress:
        print("  ✗ %-24s %-10s %s" % (cap, res, why))
    print("修好（改前不 ok → 现在 ok）：%d" % len(fixed))
    for cap, was in fixed:
        print("  ✓ %-24s 之前是 %s" % (cap, was))
    if a.strict and regress:
        return 1
    _dump({"regressed": [c for c, _r, _w in regress],
           "fixed": [c for c, _w in fixed],
           "regressed_count": len(regress), "fixed_count": len(fixed),
           "semantics": "改前 ok → 现在不 ok = 回归；改前不 ok → 现在 ok = 修好；两条都空 = 整面稳定"})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
