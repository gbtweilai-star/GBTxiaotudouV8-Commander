# -*- coding: utf-8 -*-
"""orch-note.py — 往**编排账本**（`state/orchestrator-ledger.jsonl`）记一笔，并把形状钉死。

开发者：自由的风 · 守护者：公主土豆 · 禁止删除

## 主人令（2026-10-20 逐字）
「**每次那里问题 那里踩坑 方向是那里 都要记入到编排账本 别无脑操作**」

## 所以这一件只干三件事
1. `add`：按**既有 schema** `{at, job_id, slot, apply, 判决}` 追加一行（只追加，不重排）。
2. `check`：逐行校验现有账本 —— 坏行/缺键/空判决都点名，**不许静默通过**。
3. `selftest`：负控（空判决必须被拒、坏 JSON 必须被 check 逮到）。

## 为什么不用手抄 json
本仓老坑（P9「账没有写手必烂」/ P1「判据错尺假绿」）：手抄的账会缺键、会写成两种 schema、
会静默漏掉"为什么"。这一件把**拒收条件**写死：判决短于 12 字直接拒（"已完成"这种不算账）。

用法：
  py -3.14 tools/codex-scripts/orch-note.py add --job-id dh.quality.v1 \\
      --verdict "问题=… · 踩坑=… · 方向=…"
  py -3.14 tools/codex-scripts/orch-note.py check
  py -3.14 tools/codex-scripts/orch-note.py selftest
"""
from __future__ import annotations

import argparse
import json
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
LEDGER = ROOT / "state" / "orchestrator-ledger.jsonl"
KEYS = ("at", "job_id", "slot", "apply", "判决")
MIN_VERDICT = 12

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:                                              # noqa: BLE001
        pass


def _row(job_id: str, verdict: str, slot: str = "T00", apply: bool = True) -> dict:
    return {"at": time.strftime("%Y-%m-%dT%H:%M:%S"), "job_id": str(job_id).strip(),
            "slot": str(slot or "T00"), "apply": bool(apply),
            "判决": str(verdict).strip()}


def add(job_id: str, verdict: str, slot: str = "T00", apply: bool = True,
        dry: bool = False, target: Path | None = None) -> dict:
    jid = str(job_id or "").strip()
    ver = str(verdict or "").strip()
    if not jid:
        return {"ok": False, "why": "job_id 不许空"}
    if len(ver) < MIN_VERDICT:
        return {"ok": False, "why": "判决短于 %d 字，等于没记（P9）：%r" % (MIN_VERDICT, ver)}
    row = _row(jid, ver, slot, apply)
    tgt = Path(target) if target else LEDGER
    if not dry:
        tgt.parent.mkdir(parents=True, exist_ok=True)
        with tgt.open("a", encoding="utf-8", newline="\n") as fh:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")
    return {"ok": True, "wrote": (not dry), "target": str(tgt), "row": row}


def check(target: Path | None = None) -> dict:
    tgt = Path(target) if target else LEDGER
    if not tgt.is_file():
        return {"ok": False, "why": "账本不在：%s" % tgt, "rows": 0}
    bad, rows = [], 0
    for i, ln in enumerate(tgt.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
        if not ln.strip():
            continue
        try:
            j = json.loads(ln)
        except Exception as e:                                     # noqa: BLE001
            bad.append({"line": i, "why": "json: %s" % str(e)[:80]})
            continue
        miss = [k for k in KEYS if k not in j]
        if miss:
            bad.append({"line": i, "why": "缺键 %s" % miss})
            continue
        if len(str(j.get("判决") or "").strip()) < MIN_VERDICT:
            bad.append({"line": i, "why": "判决太短"})
            continue
        rows += 1
    return {"ok": not bad, "target": str(tgt), "rows": rows, "bad": bad}


def selftest() -> dict:
    tmp = Path(tempfile.gettempdir()) / ("orch-selftest-%d.jsonl" % time.time())
    if tmp.is_file():
        tmp.unlink()
    r1 = add("selftest.a", "负控：这条够长，应该写进去。", target=tmp)
    r2 = add("selftest.b", "短", target=tmp)                       # 必须被拒
    c1 = check(tmp)
    with tmp.open("a", encoding="utf-8") as fh:
        fh.write("{坏行\n")
    c2 = check(tmp)
    tmp.unlink(missing_ok=True)
    ok = (r1.get("ok") and not r2.get("ok") and c1.get("ok")
          and (not c2.get("ok")) and len(c2.get("bad") or []) == 1)
    return {"ok": ok, "append_ok": r1.get("ok"), "short_rejected": not r2.get("ok"),
            "clean_ok": c1.get("ok"), "bad_line_caught": not c2.get("ok")}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd")
    a = sub.add_parser("add")
    a.add_argument("--job-id", required=True)
    a.add_argument("--verdict", required=True)
    a.add_argument("--slot", default="T00")
    a.add_argument("--no-apply", action="store_true")
    a.add_argument("--dry", action="store_true")
    c = sub.add_parser("check")
    for p in (a, c):
        p.add_argument("--target", default="")
    sub.add_parser("selftest")
    ns = ap.parse_args(argv)

    if ns.cmd == "check":
        r = check(Path(ns.target) if ns.target else None)
        print(json.dumps(r, ensure_ascii=False, indent=1))
        return 0 if r.get("ok") else 1
    if ns.cmd == "selftest":
        r = selftest()
        print(json.dumps(r, ensure_ascii=False, indent=1))
        return 0 if r.get("ok") else 1
    if ns.cmd == "add":
        r = add(ns.job_id, ns.verdict, ns.slot, not ns.no_apply, ns.dry,
                Path(ns.target) if ns.target else None)
        print(json.dumps(r, ensure_ascii=False, indent=1))
        return 0 if r.get("ok") else 1
    ap.print_help()
    return 2


if __name__ == "__main__":
    sys.exit(main())
