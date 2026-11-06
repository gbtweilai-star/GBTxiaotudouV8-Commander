# -*- coding: utf-8 -*-
"""claim-audit —— 判据反推：每条结论都要能回到一条**可复跑的证据**。

## 为什么造这个（2026-11-06）

仓库里已经有一堆验证零件，但它们各管一段：
    criterion_bench  判据本身写得对不对
    omni-monitor     自述/实现/声明 三向对账
    cap_self verify  427 契约三源对账
    action_gate      动手前证据必须在盘上
    chain_kernel     七步链每步产出证据

缺的那一段是：**任意一句结论 → 一条能重跑的证据**。
于是出现「注释里写着判据在 X，而 X 根本不存在」这种事 —— 话说了，没人能反推。

本工具就是那一段：结论登记在 `state/claims.json`，每条绑一个**具名检查器**。
`run` 当场重跑，`PROVEN` 才留下 `last_ok_at`；跑不过就是 `BROKEN`，退出码 1。

## 三条纪律

1. **证据是检查器，不是任意命令** —— `cmd` 型必须显式 `allow_exec: true`，
   否则拒绝执行（默认不打开执行面）。
2. **不缓存结论** —— 每次 `run` 都真跑；`list` 里的 `age_h` 只是"上次证明到现在多久"。
3. **不静默** —— 检查器抛异常记 `BROKEN(check_error)`，不当成通过。

## 用法

    py tools/codex-scripts/claim-audit.py list
    py tools/codex-scripts/claim-audit.py run [--id X] [--slow] [--json]
    py tools/codex-scripts/claim-audit.py add --id X --claim "一句话" --check caps_contract
    py tools/codex-scripts/claim-audit.py add --id X --claim "..." --check file_sha --arg path=a --arg sha256=...
    py tools/codex-scripts/claim-audit.py rm --id X
    py tools/codex-scripts/claim-audit.py stale --days 7
"""
from __future__ import annotations

import argparse
import glob
import hashlib
import json
import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
STATE = ROOT / "state" / "claims.json"
TOOLS = ROOT / "tools" / "codex-scripts"

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        pass

CHECKS = {}


def check(name):
    def deco(fn):
        CHECKS[name] = fn
        return fn
    return deco


# ── 通用检查器（声明式，不开执行面）────────────────────────────
@check("file_sha")
def _file_sha(args):
    p = ROOT / str(args.get("path") or "")
    if not p.is_file():
        return False, "文件不存在: %s" % p
    got = hashlib.sha256(p.read_bytes()).hexdigest()
    want = str(args.get("sha256") or "").strip().lower()
    if not want:
        return True, "sha256=%s（未给期望值，仅报读数）" % got[:16]
    ok = got == want or (len(want) >= 12 and got.startswith(want))
    return ok, "sha256=%s 期望=%s" % (got[:16], want[:16])


@check("same_bytes")
def _same_bytes(args):
    a = ROOT / str(args.get("a") or "")
    b = ROOT / str(args.get("b") or "")
    if not (a.is_file() and b.is_file()):
        return False, "文件缺失: %s / %s" % (a, b)
    ha, hb = hashlib.sha256(a.read_bytes()).hexdigest(), hashlib.sha256(b.read_bytes()).hexdigest()
    return ha == hb, "a=%s b=%s" % (ha[:16], hb[:16])


@check("json_eq")
def _json_eq(args):
    p = ROOT / str(args.get("file") or "")
    if not p.is_file():
        return False, "文件不存在: %s" % p
    cur = json.loads(p.read_text(encoding="utf-8"))
    path = str(args.get("path") or "")
    for seg in [x for x in path.split(".") if x]:
        if isinstance(cur, list):
            cur = cur[int(seg)]
        else:
            cur = (cur or {})[seg]
    want = args.get("value")
    if isinstance(want, str) and want.lstrip("-").isdigit():
        want = int(want)
    return cur == want, "读到 %r，期望 %r" % (cur, want)


@check("count_eq")
def _count_eq(args):
    pattern = str(args.get("glob") or "")
    files = [Path(x) for x in glob.glob(str(ROOT / pattern), recursive=True)]
    files = [f for f in files if f.is_file()]
    needle = args.get("contains")
    if needle:
        hit = 0
        for f in files:
            try:
                if str(needle) in f.read_text(encoding="utf-8", errors="ignore"):
                    hit += 1
            except Exception:  # noqa: BLE001
                pass
        n = hit
    else:
        n = len(files)
    want = int(args.get("expect") or 0)
    return n == want, "命中 %d，期望 %d（glob=%s）" % (n, want, pattern)


# ── 仓库级检查器（走唯一门 / 现成脚本）────────────────────────
def _api():
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    from gbt_allinone import api
    return api


def _peel(env):
    res = (env or {}).get("result") or {}
    return res.get("result") if isinstance(res.get("result"), dict) else res


@check("caps_contract")
def _caps_contract(args):
    r = _api().run_task("cap_self", {"op": "verify"})
    inner = _peel(r) or {}
    counts = inner.get("counts") or {}
    vals = [counts.get(k) for k in ("registry", "snapshot", "dispatched")]
    ok = bool(inner.get("ok")) and len(set(vals)) == 1 and not (inner.get("failed") or [])
    return ok, "counts=%s failed=%s" % (counts, (inner.get("failed") or [])[:3])


@check("doc_signature")
def _doc_signature(args):
    r = _api().run_task("signature_guard", {"op": "status"})
    inner = _peel(r) or {}
    miss = inner.get("missing") or []
    ok = str(inner.get("verdict")) == "clean" and not miss
    return ok, "verdict=%s pages=%s missing=%d" % (
        inner.get("verdict"), inner.get("pages_checked"), len(miss))


def _run_tool(rel, argv, timeout=120):
    p = subprocess.run([sys.executable, str(TOOLS / rel)] + list(argv),
                       cwd=str(ROOT), capture_output=True, text=True,
                       encoding="utf-8", errors="replace", timeout=timeout)
    return p.returncode, (p.stdout or "") + (p.stderr or "")


@check("omni_gap")
def _omni_gap(args):
    rc, out = _run_tool("omni-monitor.py", ["--gap"], timeout=60)
    tail = [ln for ln in out.strip().splitlines() if ln.strip()][-1:]
    return rc == 0, "rc=%d %s" % (rc, tail[0] if tail else "")


@check("tiers_test")
def _tiers_test(args):
    # 只认退出码：unittest 全过才 rc=0（不再拿输出里有没有 "OK" 当判据）
    rc, out = _run_tool("run-tests.py", ["gbt_allinone.tests.test_atomic_sync_tiers"], timeout=120)
    return rc == 0, "rc=%d（8 条分级判据）" % rc


@check("criterion_ratchet")
def _criterion_ratchet(args):
    # 只认退出码：台架自己用 0/1 表达"有没有变坏"（不再做文本子串判断）
    rc, out = _run_tool("criterion_bench.py", ["check"], timeout=300)
    return rc == 0, "rc=%d" % rc


@check("cmd")
def _cmd(args):
    if not args.get("allow_exec"):
        return False, "拒绝执行：cmd 型证据必须显式 allow_exec=true"
    argv = args.get("argv")
    if isinstance(argv, str):
        argv = [x for x in argv.split() if x]
    if not argv:
        return False, "argv 为空"
    p = subprocess.run(argv, cwd=str(ROOT / str(args.get("cwd") or "")),
                       capture_output=True, text=True, encoding="utf-8",
                       errors="replace", timeout=int(args.get("timeout") or 120))
    want = int(args.get("expect_rc") or 0)
    return p.returncode == want, "rc=%d 期望=%d" % (p.returncode, want)


SLOW = {"criterion_ratchet"}


# ── 账本 ──────────────────────────────────────────────────────
def load():
    if not STATE.is_file():
        return {"v": 1, "claims": []}
    try:
        return json.loads(STATE.read_text(encoding="utf-8"))
    except Exception as e:  # noqa: BLE001
        raise SystemExit("state/claims.json 读不开：%s" % e)


def save(doc):
    STATE.parent.mkdir(parents=True, exist_ok=True)
    raw = (json.dumps(doc, ensure_ascii=False, indent=1) + "\n").encode("utf-8")
    tmp = STATE.with_name(STATE.name + ".tmp-%d" % os.getpid())
    with open(tmp, "wb") as fh:
        fh.write(raw)
        fh.flush()
        os.fsync(fh.fileno())
    os.replace(tmp, STATE)


def now_s():
    return time.strftime("%Y-%m-%dT%H:%M:%S")


def age_h(ts):
    if not ts:
        return None
    try:
        return round((time.time() - time.mktime(time.strptime(ts, "%Y-%m-%dT%H:%M:%S"))) / 3600.0, 1)
    except Exception:  # noqa: BLE001
        return None


def cmd_list(a):
    doc = load()
    rows = []
    for c in doc.get("claims") or []:
        rows.append({"id": c.get("id"), "claim": c.get("claim"),
                     "check": c.get("check"), "max_age_h": c.get("max_age_h", 168),
                     "last_ok_at": c.get("last_ok_at"), "age_h": age_h(c.get("last_ok_at")),
                     "last_verdict": c.get("last_verdict")})
    print(json.dumps({"ok": True, "count": len(rows), "claims": rows},
                     ensure_ascii=False, indent=1))
    return 0


def cmd_run(a):
    doc = load()
    claims = doc.get("claims") or []
    if a.id:
        claims = [c for c in claims if c.get("id") == a.id]
        if not claims:
            raise SystemExit("没有这条结论：%s" % a.id)
    rows, broken = [], 0
    for c in claims:
        name = str(c.get("check") or "")
        fn = CHECKS.get(name)
        if fn is None:
            rows.append({"id": c.get("id"), "verdict": "BROKEN",
                         "why": "检查器不存在: %s（判据在 X，X 不在）" % name})
            broken += 1
            continue
        if name in SLOW and not a.slow:
            rows.append({"id": c.get("id"), "verdict": "SKIPPED",
                         "why": "慢检查（>20s），加 --slow 才跑"})
            continue
        t0 = time.time()
        try:
            ok, why = fn(c.get("args") or {})
        except Exception as e:  # noqa: BLE001
            ok, why = False, "check_error: %s: %s" % (type(e).__name__, e)
        ms = int((time.time() - t0) * 1000)
        c["last_run_at"] = now_s()
        c["last_verdict"] = "PROVEN" if ok else "BROKEN"
        c["last_why"] = why
        if ok:
            c["last_ok_at"] = c["last_run_at"]
        else:
            broken += 1
        rows.append({"id": c.get("id"), "verdict": c["last_verdict"], "ms": ms, "why": why})
    save(doc)
    out = {"ok": broken == 0, "at": now_s(), "broken": broken, "rows": rows}
    print(json.dumps(out, ensure_ascii=False, indent=1))
    return 0 if broken == 0 else 1


def cmd_add(a):
    doc = load()
    if a.check not in CHECKS:
        raise SystemExit("没有这个检查器：%s（可用：%s）" % (a.check, ", ".join(sorted(CHECKS))))
    args = {}
    for kv in a.arg or []:
        if "=" not in kv:
            raise SystemExit("--arg 要 k=v：%s" % kv)
        k, v = kv.split("=", 1)
        args[k] = v
    rows = [c for c in (doc.get("claims") or []) if c.get("id") != a.id]
    rows.append({"id": a.id, "claim": a.claim, "check": a.check, "args": args,
                 "max_age_h": a.max_age_h, "created_at": now_s()})
    doc["claims"] = rows
    save(doc)
    print(json.dumps({"ok": True, "id": a.id, "check": a.check, "args": args},
                     ensure_ascii=False, indent=1))
    return 0


def cmd_rm(a):
    doc = load()
    before = len(doc.get("claims") or [])
    doc["claims"] = [c for c in (doc.get("claims") or []) if c.get("id") != a.id]
    save(doc)
    print(json.dumps({"ok": True, "removed": before - len(doc["claims"])},
                     ensure_ascii=False, indent=1))
    return 0


def cmd_stale(a):
    doc = load()
    out = []
    for c in doc.get("claims") or []:
        h = age_h(c.get("last_ok_at"))
        limit = float(c.get("max_age_h") or 168)
        if h is None or h > limit:
            out.append({"id": c.get("id"), "age_h": h, "max_age_h": limit,
                        "claim": c.get("claim")})
    print(json.dumps({"ok": True, "stale": len(out), "rows": out},
                     ensure_ascii=False, indent=1))
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="判据反推：结论 -> 可复跑证据")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("list"); p.set_defaults(fn=cmd_list)
    p = sub.add_parser("run")
    p.add_argument("--id"); p.add_argument("--slow", action="store_true")
    p.add_argument("--json", action="store_true")
    p.set_defaults(fn=cmd_run)
    p = sub.add_parser("add")
    p.add_argument("--id", required=True); p.add_argument("--claim", required=True)
    p.add_argument("--check", required=True); p.add_argument("--arg", action="append")
    p.add_argument("--max-age-h", dest="max_age_h", type=float, default=168)
    p.set_defaults(fn=cmd_add)
    p = sub.add_parser("rm"); p.add_argument("--id", required=True); p.set_defaults(fn=cmd_rm)
    p = sub.add_parser("stale"); p.add_argument("--days", type=float, default=7)
    p.set_defaults(fn=cmd_stale)

    a = ap.parse_args(argv)
    return a.fn(a)


if __name__ == "__main__":
    sys.exit(main())