#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""主人发票之后：把「要票」的那批**真跑一遍**（票用一张少一张，所以按窗口/一次性分开算）。

票种（现读）：
  · window（TTL 内可多次）：process_execute / external_llm / desktop_control / privacy_read /
    device_control / audio_output
  · one_shot（用掉即销）：deploy_publish / deploy_force / data_export / owner_control / remote_device

本脚本**刻意不跑**会碰交付区/排练区的 mirror_*（哪怕票够）——它们失败也可能留下半状态；
需要跑时另开一轮，并先在隔离房间里演练（本仓红线：生产面只收成品）。

产出：outputs/open-source-release/data/ticket-probe.json
用法：py -3.12 tools/codex-scripts/probe-with-tickets.py
"""
from __future__ import annotations

import concurrent.futures as cf
import json
import os
import pathlib
import sys
import tempfile
import time
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        pass

ROOT = pathlib.Path(__file__).resolve().parents[2]
_STORE = pathlib.Path(tempfile.mkdtemp(prefix="gbt_ticket_store_"))
os.environ["GBT_STORE_DIR"] = str(_STORE)
sys.path.insert(0, str(ROOT))

# 🔴 2026-10-21 实测坑：授权账本**就在 store 里**（store/auth_grants.jsonl）。
#    隔离 store 会把主人刚发的票一起隔离掉 ⇒ 上一轮 21 条全报"仍缺票"（票是真的、我看错账本）。
#    修法：隔离 store 建好后，把**真实账本只读复制**进来；写盘仍落在临时 store。
import shutil                                        # noqa: E402

_real_grants = ROOT / "gbt_allinone" / "store" / "auth_grants.jsonl"   # 现读：真账本在包内 store
if _real_grants.is_file():
    _STORE.mkdir(parents=True, exist_ok=True)
    shutil.copy2(_real_grants, _STORE / "auth_grants.jsonl")
    print("[票] 已把真实授权账本复制进隔离 store（%d 行）"
          % len((_STORE / "auth_grants.jsonl").read_text(encoding="utf-8").strip().splitlines()))
else:
    print("[票] 没找到 store/auth_grants.jsonl —— 本轮会全被拒（如实记）")

from gbt_allinone.api import run_task      # noqa: E402

OUT = ROOT / "outputs" / "open-source-release" / "data" / "ticket-probe.json"
TIMEOUT = 45

CASES = [
    # ── 需参数位（11 条要票的）──────────────────────────────────────────────
    ("autopilot", {"goal": "列一条当前告警并给出一句建议"}),
    ("think_loop", {"goal": "给一句今日提醒"}),
    ("sec_llm", {"prompt": "回一个字：好", "max_tokens": 64}),
    ("codex_chat", {"message": "只回一个字：好"}),
    ("codex_interrupt", {"thread_id": "probe-none"}),
    ("codex_turn_send", {"thread_id": "probe-none", "text": "回一个字：好"}),
    ("devour_github", {"repo": "https://github.com/octocat/Hello-World"}),
    ("omni_web", {"url": "https://example.com"}),
    ("tentacle", {"action": "available_actions"}),
    ("one_key_deploy", {"target": "probe-none-not-a-repo"}),
    ("pipeline_rollback", {"name": "probe-none"}),
    # ── 监控账里被门拒的只读位（票到手后重跑）────────────────────────────────
    ("codex_models", {}),
    ("llm_chat", {"messages": [{"role": "user", "content": "只回一个字：好"}]}),
    ("mcp_call", {}),
    ("mcp_connect", {}),
    ("codex_thread_new", {}),
    ("devour_pulse", {}),
    ("bluetooth", {}),
    ("bt_control", {}),
    ("vision", {}),
    ("voice", {}),
]


def unwrap(resp):
    b = resp.get("gbt_result", resp) if isinstance(resp, dict) else {}
    inner = b.get("result") if isinstance(b, dict) else None
    return (b if isinstance(b, dict) else {}), (inner if isinstance(inner, dict) else {})


def classify(b, i):
    if b.get("denied") or i.get("denied"):
        miss = b.get("missing") or i.get("missing") or []
        return "needs_ticket", "仍缺票：" + ",".join(miss)
    st = str(b.get("status") or "")
    msg = str(b.get("error") or b.get("message") or i.get("error") or i.get("reason") or "")
    if st == "ok" and i.get("ok") is not False:
        return "ok", "带票真跑通过"
    low = msg.lower()
    if "needs_dependency" in low or "http 0" in low or "未安装" in msg:
        return "needs_dependency", msg[:150]
    if any(k in msg for k in ("缺少", "需要", "不能为空", "要 ", "user_error")):
        return "needs_input", msg[:150]
    return "failed", (msg or st)[:150]


def one(cap, payload):
    t0 = time.time()
    try:
        with cf.ThreadPoolExecutor(max_workers=1) as ex:
            resp = ex.submit(run_task, cap, payload).result(timeout=TIMEOUT)
        b, i = unwrap(resp)
        v, note = classify(b, i)
        return {"cap": cap, "payload": payload, "status": b.get("status"),
                "verdict": v, "note": note, "elapsed_s": round(time.time() - t0, 2)}
    except cf.TimeoutError:
        return {"cap": cap, "payload": payload, "status": "timeout",
                "verdict": "failed", "note": "> %ds（已用票，但没在时限内回）" % TIMEOUT,
                "elapsed_s": round(time.time() - t0, 2)}
    except Exception as e:                                # noqa: BLE001
        return {"cap": cap, "payload": payload, "status": "exception",
                "verdict": "failed", "note": "%s: %s" % (type(e).__name__, str(e)[:140]),
                "elapsed_s": round(time.time() - t0, 2)}


def main() -> int:
    rows = []
    for cap, payload in CASES:
        r = one(cap, payload)
        rows.append(r)
        print("%-20s %-16s %-10s %s" % (r["cap"], r["verdict"], r["status"], r["note"][:70]))
    cnt: dict[str, int] = {}
    for r in rows:
        cnt[r["verdict"]] = cnt.get(r["verdict"], 0) + 1
    doc = {"at": time.strftime("%Y-%m-%dT%H:%M:%S"), "total": len(rows), "counts": cnt,
           "store": os.environ["GBT_STORE_DIR"],
           "口径": "主人已发票（window 可多次、one_shot 用掉即销）；刻意不跑 mirror_*（会碰交付区/排练区）",
           "rows": rows}
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(doc, ensure_ascii=False, indent=1), encoding="utf-8")
    print("\n计数：", cnt, "→", OUT)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

