# -*- coding: utf-8 -*-
"""brain-step-track -- 大脑执行层 · 实时步进跟踪（主人令 2026-10-16）

真 schema（现读 gbt_allinone/store/audit.jsonl）：{ts, iso, event, meta}；
  event=="call" 带 meta.kind / meta.synced / meta.payload_keys（**payload 只记键不记值**）。

判据分两层（避免假阳性把判据做瞎）：
  RED（硬违规，必须为 0）：
    R1 未进信封：meta.synced != true；
    R2 执行类未带确认：危险能力位里 payload_keys 含 code（= run 真跑代码）而无 confirm/owner_override。
  AMBER（读数提示，不作否决）：
    A1 疑似重试：同 kind + 同 payload_keys 在 4 步窗口内 >=3 次（值未入账 => 只能称疑似）；
    A2 纪律未开：meta.coding_discipline == false（本仓执行纪律钩子未生效，给覆盖率读数）。
账本 150MB+ ⇒ 只读尾部字节。
"""
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import sys as _gbt_sys

for _gbt_s in (_gbt_sys.stdout, _gbt_sys.stderr):
    try:
        _gbt_s.reconfigure(encoding="utf-8")
    except Exception:
        pass


ROOT = Path(__file__).resolve().parents[2]
CANDIDATES = [ROOT / "gbt_allinone" / "store" / "audit.jsonl", ROOT / "store" / "audit.jsonl",
              ROOT / "state" / "audit.jsonl"]
DANGER_KINDS = ("pod_link", "one_key_deploy", "mirror_release", "mirror_ascend", "qiankun",
                "room_space", "cloud_pc", "file_operation", "git_write", "code_patch",
                "deployment_rehearsal", "pipeline")
CONFIRM_KEYS = ("confirm", "owner_override", "owner_ok", "yes")


def audit_path() -> Path | None:
    for p in CANDIDATES:
        if p.is_file():
            return p
    hits = sorted(ROOT.glob("**/audit.jsonl"), key=lambda x: -x.stat().st_size)
    return hits[0] if hits else None


def tail_records(path: Path, nbytes: int = 400000) -> list:
    size = path.stat().st_size
    with path.open("rb") as f:
        f.seek(max(0, size - nbytes))
        chunk = f.read().decode("utf-8", "replace")
    lines = chunk.splitlines()[1:] if size > nbytes else chunk.splitlines()
    recs = []
    for ln in lines:
        ln = ln.strip()
        if not ln:
            continue
        try:
            recs.append(json.loads(ln))
        except Exception:
            continue
    return recs


def step_rows(recs: list) -> list:
    cs = [r for r in recs if r.get("event") == "call"]
    rows = []
    for i, r in enumerate(cs):
        m = r.get("meta") or {}
        kind = str(m.get("kind") or "?")
        keys = [str(x) for x in (m.get("payload_keys") or [])]
        red = []
        amber = []
        if m.get("synced") is not True:
            red.append("R1未进信封")
        if kind in DANGER_KINDS and "code" in keys and not any(c in keys for c in CONFIRM_KEYS):
            red.append("R2执行未带确认")
        win = cs[max(0, i - 3):i]
        same = [x for x in win if str((x.get("meta") or {}).get("kind")) == kind
                and [str(y) for y in ((x.get("meta") or {}).get("payload_keys") or [])] == keys]
        if len(same) >= 2:
            amber.append("A1疑似重试")
        if m.get("coding_discipline") is False:
            amber.append("A2纪律未开")
        rows.append({"iso": str(r.get("iso"))[11:], "kind": kind, "synced": m.get("synced"),
                     "keys": ",".join(keys)[:22], "red": red, "amber": amber})
    return rows


def render(rows: list) -> int:
    nred = namber = 0
    print("%-9s %-16s %-7s %-18s %s" % ("时间", "能力位", "信封", "payload键", "判定"))
    for r in rows:
        if r["red"]:
            nred += 1
        if r["amber"]:
            namber += 1
        tag = "OK"
        if r["red"]:
            tag = "RED: " + ", ".join(r["red"])
        if r["amber"]:
            tag += (" | " if r["red"] else "") + "提示: " + ", ".join(r["amber"])
        print("%-9s %-16s %-7s %-18s %s" % (r["iso"], r["kind"][:16], str(r["synced"]), r["keys"], tag))
    total = len(rows)
    env = sum(1 for r in rows if r["synced"] is True)
    print("== 步数 %d · 硬违规 %d · 提示步 %d · 信封覆盖 %.1f%% · 判定 %s =="
          % (total, nred, namber, (env / total * 100) if total else 0.0, "PASS" if nred == 0 else "FAIL"))
    return 0 if nred == 0 else 1


def main() -> int:
    ap = argparse.ArgumentParser(description="大脑执行层实时步进跟踪")
    ap.add_argument("--tail", type=int, default=20)
    ap.add_argument("--watch", type=int, default=0)
    args = ap.parse_args()
    p = audit_path()
    if not p:
        print("未读到审计账本 => 如实报未读到，不假装通过")
        return 2
    print("审计账本：%s（%.1f MB）" % (p, p.stat().st_size / 1024 / 1024))
    while True:
        rows = step_rows(tail_records(p))[-args.tail:]
        rc = render(rows)
        if not args.watch:
            return rc
        time.sleep(args.watch)
        print("-" * 64)


if __name__ == "__main__":
    raise SystemExit(main())
