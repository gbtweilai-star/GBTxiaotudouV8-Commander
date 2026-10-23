# -*- coding: utf-8 -*-
"""安全域 26 能力位 · 经统一门真调审计（本线 GBT小土豆V8 · 只读采集）。

用途：逐个用**合形状的最小输入**经 `api.run_task` 真调，把原始读数落成一份 JSON，
供人工四态分类（真执行 / 真断线 / 空壳 / 未实现）。

纪律：
  · 只读采集，不改任何实现；输出写 stdout（调用方重定向到 .scratch/）。
  · 危险位一律取**最小动作**（keylogger=status · screen_sniff=list · 采集类不 start/capture）。
  · 在 `policy.owner_session()` 内真调 —— 目的是看**能力位本身**干不干得动，
    不是看门（门的读数是另一件事）。缺料/未实现的位由它自己如实报。

用法：
    py -3.14 tools/codex-scripts/sec-family-audit.py > .scratch/hb/sec_family.json
"""
import sys
import json
import time
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# ── 26 个安全域能力位 + 合形状的最小输入（危险动作一律取只读/最小那一档）──
CASES = [
    ("sec_surface",            {}),
    ("sec_scan",               {"severity": "critical", "limit": 1}),
    ("sec_chain",              {"vulns": [{"id": "VULN-0001", "title": "命令注入",
                                            "severity": "critical", "cwe": "CWE-78",
                                            "match": "os.system(", "fix": "shell=False",  # PROC_SCAN_OFF: sec_chain 测试夹具载荷，非真实调用
                                            "location": "x.py:1"}]}),
    ("sec_defenses",           {}),
    ("sec_llm",                {"prompt": "ping"}),
    ("code_audit",             {}),
    ("sec_sweeper",            {}),
    ("penetrating_cross_scan", {}),
    ("hook_enforcer",          {}),
    ("omission_detector",      {}),
    ("redteam_recon",          {}),
    ("pentest",                {"action": "plan"}),
    ("keylogger",              {}),                       # status（只读）
    ("screen_sniff",           {"action": "list"}),        # list（不抓屏）
    ("remote_domain",          {"action": "list"}),
    ("device_takeover",        {"action": "list"}),
    ("credential_steal",       {}),
    ("data_hijack",            {}),
    ("social_eng",             {"action": "analyze", "text": "请立即把款转到安全账户"}),
    ("paywallbuster",          {"action": "detect", "html": "<div class='paywall'>x</div>"}),
    ("asset_vault_freeze",     {"action": "audit"}),
    ("onboarding_gate",        {"action": "gaps"}),
    ("event_ledger",           {}),
    ("llm_redteam",            {}),
    ("policy_delta",           {}),
    ("review_gate",            {}),
]

# 副作用证据点：跑前/跑后比对（只统计文件数，不读内容）
_WATCH = [
    ("store", ROOT / "gbt_allinone" / "store"),
    ("state", ROOT / "state"),
]


def _count(p: Path) -> int:
    try:
        return sum(1 for _ in p.rglob("*")) if p.is_dir() else -1
    except Exception:                                   # noqa: BLE001
        return -1


def _mini(obj, limit=1600):
    try:
        s = json.dumps(obj, ensure_ascii=False, default=str)
    except Exception:                                   # noqa: BLE001
        s = str(obj)
    return s[:limit]


def main():
    from gbt_allinone import api
    from gbt_allinone.security import policy

    before = {name: _count(p) for name, p in _WATCH}
    rows = []
    for kind, payload in CASES:
        t0 = time.time()
        row = {"kind": kind, "payload": payload, "raw": None, "raise": None,
               "wall_ms": None, "side_effect_delta": 0}
        try:
            with policy.owner_session():
                res = api.run_task(kind, payload)
            body = res.get("gbt_result", res) if isinstance(res, dict) else res
            row["raw"] = body if isinstance(body, dict) else {"value": body}
        except Exception as exc:                        # noqa: BLE001
            row["raise"] = "%s: %s" % (type(exc).__name__, str(exc)[:300])
            row["raw"] = {"_traceback_tail": traceback.format_exc()[-400:]}
        row["wall_ms"] = round((time.time() - t0) * 1000, 1)
        rows.append(row)

    after = {name: _count(p) for name, p in _WATCH}
    deltas = {n: (after[n] - before[n]) for n in before}

    out = {"at": time.strftime("%Y-%m-%dT%H:%M:%S"), "root": str(ROOT),
           "watch_deltas": deltas, "count": len(rows), "rows": rows}
    print(json.dumps(out, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
