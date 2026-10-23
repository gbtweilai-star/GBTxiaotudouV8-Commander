# -*- coding: utf-8 -*-
"""tentacle-stress -- capability (tentacle) execution STRESS TEST.

Design is based on SOURCE READING, not guessing:
  1. every "cap" call is a FRESH PROCESS (five-dim wrapper) -> process spawn is one ceiling;
  2. default run carries an AUTO ENVELOPE (same-process wu-wei envelope + auto open/close step
     + audit ledger append) -> envelope tax is measurable;
  3. ledger/audit appends go through safe_io.FileLock (timeout=30.0s, poll=0.05s)
     -> concurrent calls queue on the lock;
  4. payload travels on argv -> the OS command line length is a hard breakpoint,
     so --stdin is the reliable entry.

Every probe goes through the only gate. Load uses zero-scope read-only caps.
Two-layer reading: gate status/denied is authoritative; the capability body may have no ok field.
"""
from __future__ import annotations

import argparse
import concurrent.futures as cf
import json
import statistics
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
GATE = ROOT / "tools" / "codex-scripts" / "five-dim.py"
PY = sys.executable


def one(cap, payload, stdin=False, no_env=False, timeout=180.0):
    cmd = [PY, "-X", "utf8", str(GATE), "cap", cap]
    inp = None
    if stdin:
        cmd.append("--stdin")
        inp = payload
    else:
        cmd.append(payload)
    if no_env:
        cmd.append("--no-envelope")
    t0 = time.time()
    try:
        p = subprocess.run(cmd, input=inp, capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=timeout)
    except subprocess.TimeoutExpired:
        return {"sec": timeout, "exit": None, "status": "timeout", "ok": False,
                "denied": None, "reason": "timeout", "err": ""}
    sec = round(time.time() - t0, 2)
    out = p.stdout or ""
    err = p.stderr or ""
    status = "unparsed"
    ok = False
    denied = None
    reason = None
    try:
        j = json.loads(out[out.find("{"):])
        status = j.get("status")
        denied = bool(j.get("denied"))
        body = j.get("result") if isinstance(j.get("result"), dict) else {}
        ok = (status == "ok" and not denied)
        reason = body.get("reason") or j.get("reason")
    except Exception:
        status = "stderr" if err.strip() else "unparsed"
    return {"sec": sec, "exit": p.returncode, "status": status, "ok": ok,
            "denied": denied, "reason": reason, "err": err.strip()[-80:]}


def pctl(xs, q):
    xs = sorted(xs)
    return xs[min(len(xs) - 1, int(len(xs) * q))] if xs else 0


def burst(cap, payload, n, workers, no_env=False):
    t0 = time.time()
    with cf.ThreadPoolExecutor(max_workers=workers) as ex:
        rs = list(ex.map(lambda _: one(cap, payload, no_env=no_env), range(n)))
    wall = round(time.time() - t0, 2)
    secs = [r["sec"] for r in rs]
    bad = [r for r in rs if not r["ok"]]
    kinds = {}
    for r in bad:
        k = str(r["status"]) + ("/denied" if r["denied"] else "")
        kinds[k] = kinds.get(k, 0) + 1
    return {"n": n, "workers": workers, "wall": wall, "p50": round(statistics.median(secs), 2),
            "p95": round(pctl(secs, 0.95), 2), "max": round(max(secs), 2),
            "ok": n - len(bad), "bad": kinds, "thru": round(n / wall, 2) if wall else 0}


def main():
    ap = argparse.ArgumentParser(description="capability execution stress test")
    ap.add_argument("--cap", default="count_words")
    ap.add_argument("--n", type=int, default=6)
    ap.add_argument("--levels", default="1,2,4,8,16")
    ap.add_argument("--payload", default='{"text":"a b c"}')
    ap.add_argument("--argv-bytes", default="1024,16384,32000")
    ap.add_argument("--skip-stdin", action="store_true")
    args = ap.parse_args()
    print("== tentacle stress | cap", args.cap, "| n per level", args.n, "==")
    print("-- probe 1: concurrency ladder (default envelope, real path) --")
    for lv in [int(x) for x in args.levels.split(",") if x.strip()]:
        r = burst(args.cap, args.payload, args.n, lv)
        print("  conc %-3d | wall %-6s | p50 %-5s | p95 %-5s | max %-5s | ok %d/%d | thru %-6s/s | bad %s"
              % (lv, r["wall"], r["p50"], r["p95"], r["max"], r["ok"], r["n"], r["thru"], r["bad"] or "-"))
    print("-- probe 2: envelope tax (same load, --no-envelope control) --")
    a = burst(args.cap, args.payload, args.n, 1)
    b = burst(args.cap, json.dumps({"text": "a b c", "_control": True}), args.n, 1, no_env=True)
    print("  conc 1 | with envelope p50 %-5s | no envelope p50 %-5s | tax per call %s s"
          % (a["p50"], b["p50"], round(a["p50"] - b["p50"], 2)))
    print("-- probe 3: payload size (argv hard breakpoint vs --stdin) --")
    for nbytes in [int(x) for x in args.argv_bytes.split(",") if x.strip()]:
        pl = json.dumps({"text": "x" * max(0, nbytes - 16)})
        ra = one(args.cap, pl)
        line = "  argv %7d chars | exit %-5s | status %-9s | ok=%s" % (len(pl), ra["exit"], ra["status"], ra["ok"])
        if not args.skip_stdin:
            rs = one(args.cap, pl, stdin=True)
            line += " || stdin: exit %-5s | status %-9s | ok=%s" % (rs["exit"], rs["status"], rs["ok"])
        print(line)
    print("-- probe 4: error taxonomy (two-layer read) --")
    probes = (("unknown cap", "no_such_cap_zzz", '{"op":"status"}'),
              ("unknown op (validating cap)", "music_auto", '{"op":"zzz"}'),
              ("empty payload", "music_auto", "{}"),
              ("scope-gated cap", "pod_link", '{"op":"status"}'),
              ("non json", args.cap, "not-json"))
    for label, cap, pl in probes:
        r = one(cap, pl)
        print("  %-28s | exit %-5s | status %-8s | ok=%-5s | denied=%-5s | reason %s"
              % (label, r["exit"], r["status"], r["ok"], r["denied"], str(r["reason"])[:26]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

