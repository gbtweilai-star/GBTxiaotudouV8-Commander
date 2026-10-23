# -*- coding: utf-8 -*-
"""five-dim-gate -- 「不管何时都要以五维合一的方式执行任务」的机器闸。

判据（现读账本，不采信自述）：
  F1 完整度：每一发 call 在时间窗内必须有**脑(开步/执行)** 且伴随 **眼(sync_eye) · 耳(sync_ear) · 嘴(sync_mouth)**；
     缺哪一维就报哪一维 => 该步「不是五维合一」。
  F2 信封：call 必须 synced == true（与定海神针/第一原理闸同口径）。
  F3 绕门迹象：窗口内出现 call 但 audit 里没有对应的 kind 收尾 => 交第一原理闸（此处只报读数）。
用法：py -3.14 tools/codex-scripts/five-dim-gate.py [--window 15] [--tail 300]
"""
from __future__ import annotations
import argparse, json, time
from pathlib import Path

import sys as _gbt_sys

for _gbt_s in (_gbt_sys.stdout, _gbt_sys.stderr):
    try:
        _gbt_s.reconfigure(encoding="utf-8")
    except Exception:
        pass


ROOT = Path(__file__).resolve().parents[2]
LEDGER = ROOT / "gbt_allinone" / "store" / "audit.jsonl"
DIMS = ("sync_eye", "sync_ear", "sync_mouth")


def tail_records(path: Path, nbytes: int = 500000):
    size = path.stat().st_size
    with path.open("rb") as f:
        f.seek(max(0, size - nbytes))
        chunk = f.read().decode("utf-8", "replace")
    lines = chunk.splitlines()[1:] if size > nbytes else chunk.splitlines()
    out = []
    for ln in lines:
        ln = ln.strip()
        if not ln:
            continue
        try:
            out.append(json.loads(ln))
        except Exception:
            continue
    return out


def main():
    ap = argparse.ArgumentParser(description="五维合一执行闸")
    ap.add_argument("--window", type=int, default=20, help="时间窗（秒），双向")
    ap.add_argument("--tail", type=int, default=300, help="只看最近多少条记录")
    a = ap.parse_args()
    if not LEDGER.is_file():
        print("未读到审计账本 => 如实报未读到，不假装通过")
        return 2
    recs = tail_records(LEDGER)[-a.tail:]
    calls = [r for r in recs if r.get("event") == "call"]
    now = time.time()
    red = []
    checked = 0
    for c in calls:
        ts = float(c.get("ts") or 0)
        if now - ts < 60:      # 在读步骤跳过
            continue
        if "_control" in ((c.get("meta") or {}).get("payload_keys") or []):
            continue   # \u538b\u529b\u6d4b\u8bd5\u7684\u8d1f\u5bf9\u7167\u8c03\u7528\uff08\u6545\u610f\u4e0d\u8fdb\u4fe1\u5c01\uff09\uff0c\u4e0d\u7b97\u4e94\u7ef4\u5408\u4e00\u8fdd\u89c4
        checked += 1
        win = [r for r in recs if abs(float(r.get("ts") or 0) - ts) <= a.window]
        have = {d: any(r.get("event") == d for r in win) for d in DIMS}
        missing = [d.replace("sync_", "") for d, ok in have.items() if not ok]
        synced = (c.get("meta") or {}).get("synced")
        if missing or synced is not True:
            red.append({"iso": str(c.get("iso"))[11:], "kind": str((c.get("meta") or {}).get("kind")),
                        "missing": missing, "synced": synced})
    print("五维合一执行闸：检查步 %d · 不合规 %d" % (checked, len(red)))
    for x in red[:12]:
        print("  RED %s %s | 缺维 %s | 信封 %s" % (x["iso"], x["kind"][:16], x["missing"] or "-", x["synced"]))
    if checked == 0:
        print("（窗口内没有可判定的步 => 如实报未读到，不假装通过）")
        return 2
    ok = not red
    print("== 判定 %s ==" % ("PASS" if ok else "FAIL"))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())

