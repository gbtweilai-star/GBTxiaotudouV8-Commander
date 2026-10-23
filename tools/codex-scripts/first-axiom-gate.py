# -*- coding: utf-8 -*-
"""first-axiom-gate -- V8 两条第一原理的机器闸（主人 2026-10-16 定）

公理一（起点性+真理性）：**所有行为必须留痕，否则不存在**（存在即证据）
  判据 A1：账本里每个 event=="call" 必须在随后 N 行内出现 event=="ok" 或 event=="error"；
          只有 call 没有收尾 => 该行为「无痕」=> 判不存在（RED）。
  判据 A2：state/delivery-claims.jsonl 每条 claims 指向的文件必须存在（不许宣告不存在的东西）。

公理二：**能力位必须现读可核，否则不算能力**（可核即真实）
  判据 B1：capability-audit 必须「断连 0 · 缺失 0」（现读，不采信清单自述）。
  判据 B2：delivery-claims 里带 expect_contains 的，文件必须真含该串（不可核 = 不算能力）。

负对照（保证闸真能响）：--selftest 会合成 ① 只有 call 没有收尾 ② 指向不存在文件 的假证据，
  两者都必须判 RED，否则本闸视为不可信。
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

import sys as _gbt_sys

for _gbt_s in (_gbt_sys.stdout, _gbt_sys.stderr):
    try:
        _gbt_s.reconfigure(encoding="utf-8")
    except Exception:
        pass


ROOT = Path(__file__).resolve().parents[2]
PY = sys.executable
LEDGER = ROOT / "gbt_allinone" / "store" / "audit.jsonl"
CLAIMS = ROOT / "state" / "delivery-claims.jsonl"


def tail_records(path: Path, nbytes: int = 400000):
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


def axiom_one(recs, gap: int = 400, min_age_sec: float = 180.0):
    """公理一：无痕即不存在。

    真配对键（2026-10-16 现读账本）：call 的收尾事件名就是**结果名**
    （ok / user_error / error / denied / gate_denied ...），且带同一个 meta.kind；
    sync_eye / sync_mouth / sync_ear 是五维合一的维，不是收尾。
    在读步骤（开始距今 < min_age_sec）不计红。
    """
    import time as _t
    red = []
    now = _t.time()
    endnames = ("ok", "error", "user_error", "denied", "gate_denied", "rejected", "timeout")
    for i, r in enumerate(recs):
        if r.get("event") != "call":
            continue
        age = now - float(r.get("ts") or 0)
        if age < min_age_sec:
            continue
        k = (r.get("meta") or {}).get("kind")
        win = recs[i + 1:i + 1 + gap]
        done = [x for x in win
                if (x.get("event") in endnames or str(x.get("event") or "").endswith("_error"))
                and ((x.get("meta") or {}).get("kind") in (None, k))]
        if not done:
            red.append({"where": "call@%s" % r.get("iso"), "why": "窗口内没有同 kind 的收尾事件（ok/error/*_error/denied）=> 无痕"})
    return red


def claims_rows(path: Path):
    if not path.is_file():
        return []
    out = []
    for ln in path.read_text(encoding="utf-8", errors="replace").splitlines():
        ln = ln.strip()
        if not ln:
            continue
        try:
            out.append(json.loads(ln))
        except Exception:
            continue
    return out


def axiom_two_claims(rows):
    red = []
    for r in rows:
        f = r.get("file") or r.get("path") or r.get("artifact")
        if not f:
            continue
        p = Path(f)
        if not p.is_absolute():
            p = ROOT / f
        if not p.is_file():
            red.append({"where": str(f), "why": "claims 指向的文件不存在 => 宣告了不存在的东西"})
            continue
        exp = r.get("expect_contains")
        if exp:
            body = p.read_text(encoding="utf-8", errors="replace")
            if str(exp) not in body:
                red.append({"where": str(f), "why": "expect_contains 未命中：%r" % exp})
    return red


def registry_red():
    """公理二：现读可核。四数用**尾部数字**解析（不依赖中文字面量，避免编码坑）。"""
    import re as _re
    p = subprocess.run([PY, "-X", "utf8", str(ROOT / "tools" / "codex-scripts" / "capability-audit.py")],
                       capture_output=True, text=True, encoding="utf-8", errors="replace", cwd=str(ROOT))
    out = (p.stdout or "") + (p.stderr or "")
    nums = _re.findall(r"([0-9]+)", out[-600:])
    if len(nums) < 4:
        return [{"where": "capability-audit", "why": "尾部读不出四数（拿到 %d 个数字）=> 现读失败，按红处理" % len(nums)}]
    tot, up, brk, miss = (int(x) for x in nums[-5:][:4])   # 报告尾巴是 总数/接上/断连/缺失/未探测
    bad = []
    if brk:
        bad.append({"where": "capability-audit", "why": "断连 %d" % brk})
    if miss:
        bad.append({"where": "capability-audit", "why": "缺失 %d" % miss})
    return bad, {"总数": tot, "接上": up, "断连": brk, "缺失": miss}


def main():
    ap = argparse.ArgumentParser(description="V8 两条第一原理机器闸")
    ap.add_argument("--selftest", action="store_true", help="负对照：假证据必须被判红")
    ap.add_argument("--gap", type=int, default=12)
    args = ap.parse_args()

    if args.selftest:
        fake_calls = [{"event": "call", "iso": "t1", "meta": {"kind": "x"}},
                      {"event": "call", "iso": "t2", "meta": {"kind": "y"}},
                      {"event": "ok", "iso": "t2", "meta": {"kind": "y"}}]
        r1 = axiom_one(fake_calls, gap=12)
        fake_claims = [{"file": "state/__no_such_file__.json", "expect_contains": "x"},
                       {"file": "README.md", "expect_contains": "__no_such_token__"}]
        r2 = axiom_two_claims(fake_claims)
        ok = len(r1) == 1 and len(r2) == 2
        print("负对照：无痕 call 判红 %d 条 · 假 claims 判红 %d 条 => %s" % (len(r1), len(r2), "OK" if ok else "闸不响，判据不可信"))
        return 0 if ok else 1

    if not LEDGER.is_file():
        print("未读到审计账本 => 如实报未读到，不假装通过")
        return 2
    recs = tail_records(LEDGER)
    a1 = axiom_one(recs, gap=args.gap)
    rows = claims_rows(CLAIMS)
    a2 = axiom_two_claims(rows)
    reg = registry_red()
    b1, counts = (reg if isinstance(reg, tuple) else (reg, {}))
    red = len(a1) + len(a2) + len(b1)
    print("公理一（存在即证据）：步数 %d · 无痕步 %d · claims %d 条 · owner 缺失/不含 %d"
          % (len([r for r in recs if r.get("event") == "call"]), len(a1), len(rows), len(a2)))
    print("公理二（可核即真实）：能力位 %s" % json.dumps(counts, ensure_ascii=False))
    for x in (a1 + a2 + b1)[:12]:
        print("  RED %s | %s" % (x["where"], x["why"]))
    print("== 第一原理闸：红 %d · 判定 %s ==" % (red, "PASS" if red == 0 else "FAIL"))
    return 0 if red == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())





