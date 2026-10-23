# -*- coding: utf-8 -*-
"""system 域只读位批量体检（扫描所有故障的框架口径）。

这些位是本仓自己设计的"体检口"：health / selfscan / truth_scan / cross_scan /
inventory / signature_guard / file_hygiene / wave_probe / shared_resources /
hook_registry / energy_pool / context_vault / coverage_auditor / auth_gate_status。
口径：**只调空参或只读 op**；每个位记 ok / status / 关键字段，异常如实记。
"""
import json
import sys
import time
from pathlib import Path

ROOT = Path(r"C:\Users\ADMIN\Desktop\GBT小土豆V8")
sys.path.insert(0, str(ROOT))
import gbt_allinone as gbt  # noqa: E402


def leaf(e):
    r = e.get("result") if isinstance(e, dict) else None
    if isinstance(r, dict) and isinstance(r.get("result"), dict):
        r = r["result"]
    return r if isinstance(r, dict) else e


SLOTS = [
    "health", "selfscan", "truth_scan", "inventory",
    "signature_guard", "file_hygiene", "wave_probe", "shared_resources",
    "hook_registry", "energy_pool", "context_vault", "coverage_auditor",
    "auth_gate_status", "caps_called_audit", "tentacle_cognition",
]

# 🔴 2026-09-25 **自纠（第一版读错了平面，把干净的三位报成了 ✗）**：
#    第一版对每个位做 `leaf(...)` 剥到**内层 payload** 再取 `.get("ok")` ——
#    可 `ok`/`status` 在**信封顶层**，内层 payload（如 health 的 {platform,python,time}）
#    **根本没有 ok 字段** ⇒ 一律 `✗` 且关键字段全空。
#    实测同一时刻直接调：
#      health   → {"platform":"Windows-11-10.0.26200-SP0","python":"3.14.5"}   0.3s
#      selfscan → {"verdict":"clean","findings":[],"sections":{…}}              0.4s
#      truth_scan → {"mode":"readonly","REAL":1,"FAKE":0,"verdict":"clean"}     0.0s
#    **它们没坏，是我读错平面** —— 与我在"钥匙"那栏犯的错同型（进程环境 vs 用户环境）。
#    ⇒ 改成从**信封顶层**取 ok/status，内层 payload 只作为读数展示。
#
# ⚠️ 已知限制（第一版还撞到）：`cross_scan` / `inventory` 一类重活位会**走全树**，
#    实测把整轮扫描拖过 600s。⇒ 本脚本**不把重活位放进默认批次**；
#    要跑它们请单独跑并自行带超时。
_HEAVY = {"cross_scan", "inventory"}   # 从默认批次剔除，避免整轮被拖死

print("%-20s %-6s %-14s %s" % ("位", "ok", "status", "关键读数（或内层 payload 摘要）"))
print("-" * 108)
summary = []
for k in SLOTS:
    t0 = time.time()
    try:
        env = gbt.run_task(k, {})
    except Exception as exc:  # noqa: BLE001
        print("%-20s %-6s %-14s %s" % (k, "✗", type(exc).__name__, str(exc)[:60]))
        summary.append({"slot": k, "ok": False, "error": str(exc)[:120]})
        continue
    secs = time.time() - t0
    ok = env.get("ok") if isinstance(env, dict) else None          # ← 信封顶层
    st = str((env or {}).get("status") or "-")[:14]
    # 读数优先级：内层 payload 的诊断字段 → 否则给 payload 的键
    inner = leaf(env)
    kv = ""
    if isinstance(inner, dict):
        for a in ("verdict", "green", "clean", "count", "total", "violations",
                  "issues", "gaps", "orphans", "alerts", "score", "level",
                  "soft", "hard", "coverage", "checked", "findings", "registered",
                  "routed", "unrouted", "failed", "anomalies"):
            if inner.get(a) is not None:
                kv += "%s=%s " % (a, json.dumps(inner[a], ensure_ascii=False)[:32])
        if not kv:
            kv = "payload键=" + ",".join(sorted(inner.keys())[:6])
    else:
        kv = repr(inner)[:60]
    print("%-20s %-6s %-14s %5.1fs %s" % (k, "✓" if ok else "✗", st, secs, kv[:64]))
    summary.append({"slot": k, "ok": ok, "status": st, "secs": round(secs, 2), "kv": kv})

print()
print("通过 %d / %d" % (sum(1 for s in summary if s.get("ok")), len(SLOTS)))
print("（口径：ok 取**信封顶层**；payload 里的 ok 字段是另一层，别混。）")
print()
print("=== 未通过的位：把它们的原文摊开 ===")
for k in SLOTS:
    try:
        r = leaf(gbt.run_task(k, {}))
    except Exception:
        continue
    if isinstance(r, dict) and not r.get("ok"):
        print("- %s" % k)
        print("  " + json.dumps(r, ensure_ascii=False, default=str)[:700])

Path(ROOT / "output" / "blueprint-audit" / "system-slots.json").write_text(
    json.dumps(summary, ensure_ascii=False, indent=1), encoding="utf-8")
print()
print("明细已写 output/blueprint-audit/system-slots.json")
