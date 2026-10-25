#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""只读能力位**运行时**普查（空参逐个真跑，不碰写口）。

为什么要有它（与 `caps-census.py` 的分工）：
  · `caps-census.py` 是**静态**的：查注册表 / policy / preflight，一个能力位都不执行。
  · 本脚本是**运行时**的：把"框架自己判定为可自动跑的只读位"逐个真空参调一次，
    把**静态预测**与**运行时实际**摆在一起 —— 差异就是故障线索。

谁能跑（**不是我挑的名单，是框架自己的判据**）：
  `omni.auto_run_verdict()` —— 仓里唯一的"能不能自动跑"判据。
  它同时要求：`enabled` ∧ 不是 `UNIMPLEMENTED_CAPS` ∧ `safe` ∧ 无必填参数
  ∧ 不在侧效应名单 ∧ 域不在 `DANGER_DOMAINS` ∧ 名字不带写动作字样
  ∧ 静态作用域为空 ∧ 不在 `preflight._STATE_CHANGING_KINDS`。

每个位一个**独立子进程**（超时只杀它自己），走 `five-dim.py cap`——
即仓里声明的**唯一门** `gbt_allinone.run_task`，不直接调模块函数、不绕门。

用法：
  python tools/codex-scripts/caps-runtime-census.py [--out <path>] [--timeout 60]
                                                    [--budget 1500] [--only a,b,c]
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import re
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from gbt_allinone import caps_registry as R          # noqa: E402
from gbt_allinone import preflight                    # noqa: E402
from gbt_allinone.security import policy              # noqa: E402

FIVE_DIM = ROOT / "tools" / "codex-scripts" / "five-dim.py"

# 逐个位的超时覆盖。为什么要有：`sec_scan` 实测 212.5s、`sec_chain` 233.9s 都是**真在工作**
# 的只读扫描器，拿 45s 一刀切会把"它很慢"记成"它挂了"。反过来 `cross_scan` 空参
# >560s 两次都不返回（已知挂死）⇒ 给它 60s 就够，别白等 300s。
SLOW_OVERRIDE = {
    "sec_scan": 300.0, "sec_chain": 300.0, "sec_surface": 120.0,
    "selfscan": 300.0, "truth_scan": 300.0, "coverage_auditor": 180.0,
    "inventory": 180.0, "signature_guard": 240.0, "file_hygiene": 180.0,
    "tentacle_cognition": 180.0, "orchestration_kernel": 180.0,
    "cross_scan": 60.0,
}


def _load_omni():
    spec = importlib.util.spec_from_file_location(
        "omni_mod", ROOT / "tools" / "codex-scripts" / "omni.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _readonly_set(omni) -> tuple[list[str], dict[str, list[str]]]:
    """返回 (可自动跑的 kind 列表, 每个被排除位的理由)。判据一律取 omni 自己的。"""
    ok, why = [], {}
    for kind, meta in sorted(R.BENIGN_CAPS.items()):
        meta = meta if isinstance(meta, dict) else {}
        decision = policy.evaluate(kind, {})
        cap = {
            "kind": kind,
            "domain": meta.get("domain"),
            "safe": bool(meta.get("safe")),
            "enabled": kind not in set(R.DISABLED_CAPS),
            "unimplemented": kind in set(R.UNIMPLEMENTED_CAPS),
            "requires_params": list((R.PARAM_REQUIRED.get(kind) or {}).get("params") or []),
            "needs_confirmation": preflight.is_side_effect(kind, {}, decision),
        }
        verdict, reasons = omni.auto_run_verdict(cap)
        if verdict:
            ok.append(kind)
        else:
            why[kind] = reasons
    return ok, why


_ENV_LINE = re.compile(r'"status"\s*:\s*"([^"]+)"')


def _probe(kind: str, timeout: float) -> dict:
    t0 = time.time()
    try:
        proc = subprocess.run(
            [sys.executable, str(FIVE_DIM), "cap", kind, "--no-envelope"],
            cwd=str(ROOT), capture_output=True, text=True,
            encoding="utf-8", errors="replace", timeout=timeout)
        out, err, rc = proc.stdout or "", proc.stderr or "", proc.returncode
    except subprocess.TimeoutExpired:
        return {"kind": kind, "verdict": "timeout", "timeout_s": timeout,
                "elapsed": round(time.time() - t0, 2),
                "note": "超过单个位的预算被强杀 —— 这本身是读数（挂死/无界等待）"}
    elapsed = round(time.time() - t0, 2)
    rec = {"kind": kind, "rc": rc, "elapsed": elapsed, "stdout_bytes": len(out)}
    try:
        env = json.loads(out)
    except Exception as exc:                                        # noqa: BLE001
        rec["verdict"] = "unparsable"
        rec["note"] = "%s: %s" % (type(exc).__name__, str(exc)[:120])
        rec["stdout_head"] = out[:400]
        rec["stderr_head"] = err[:400]
        return rec
    res = env.get("result") if isinstance(env.get("result"), dict) else {}
    rec["status"] = env.get("status")
    rec["denied"] = bool(env.get("denied"))
    rec["body_status"] = res.get("status")
    rec["body_ok"] = res.get("ok") if "ok" in res else None
    rec["error_class"] = res.get("error_class")
    rec["message"] = str(res.get("message") or res.get("error") or "")[:200]
    rec["keys"] = sorted(res.keys())[:24]
    if rec["denied"]:
        rec["verdict"] = "denied"
        rec["missing"] = env.get("missing") or res.get("missing")
    elif rec["status"] == "error" or rec["body_status"] == "error":
        rec["verdict"] = "error"
    elif rec["body_status"] in ("needs_dependency", "not_implemented", "unimplemented"):
        rec["verdict"] = "needs_dependency"
    elif rec["status"] == "ok":
        rec["verdict"] = "ok"
    else:
        rec["verdict"] = "other"
    return rec


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="output/blueprint-audit/caps-runtime-census.json")
    ap.add_argument("--timeout", type=float, default=60.0)
    ap.add_argument("--budget", type=float, default=1500.0)
    ap.add_argument("--only", default="")
    args = ap.parse_args()

    omni = _load_omni()
    runnable, excluded = _readonly_set(omni)
    if args.only:
        want = {x.strip() for x in args.only.split(",") if x.strip()}
        runnable = [k for k in runnable if k in want]

    out_path = ROOT / args.out
    out_path.parent.mkdir(parents=True, exist_ok=True)
    records, t_start = [], time.time()
    for kind in runnable:
        left = args.budget - (time.time() - t_start)
        if left <= 5:
            records.append({"kind": kind, "verdict": "skipped_budget",
                            "note": "总预算用尽，**没跑**（不许读成通过）"})
            continue
        rec = _probe(kind, min(SLOW_OVERRIDE.get(kind, args.timeout), left))
        records.append(rec)
        out_path.write_text(json.dumps(
            {"runnable_total": len(runnable), "done": len(records),
             "budget_s": args.budget, "timeout_s": args.timeout,
             "records": records}, ensure_ascii=False, indent=2), encoding="utf-8")
        sys.stderr.write("[%3d/%3d] %-22s %-16s %6.2fs\n"
                         % (len(records), len(runnable), kind, rec.get("verdict"), rec.get("elapsed") or 0))

    from collections import Counter
    tally = Counter(r.get("verdict") for r in records)
    summary = {
        "runnable_total": len(runnable),
        "probed": len(records),
        "tally": dict(tally),
        "not_ok": [{"kind": r["kind"], "verdict": r.get("verdict"),
                    "message": r.get("message") or r.get("note")} for r in records
                   if r.get("verdict") not in ("ok",)],
        "out": str(out_path),
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
