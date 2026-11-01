"""Run ONE capability through the single gate and print a compact JSON result.

Usage: python probe_one.py <repo_root> <capability>
Exits 0 even when the capability fails; the JSON carries status/exception.
"""
import json
import sys
import time

repo, kind = sys.argv[1], sys.argv[2]
sys.path.insert(0, repo)

t0 = time.time()
out = {"kind": kind}
try:
    import gbt_allinone as g
    r = g.run_task(kind, {}, probe=True)
    out["ms"] = int((time.time() - t0) * 1000)
    inner = r.get("gbt_result") if isinstance(r, dict) else None
    if not isinstance(inner, dict):
        inner = r if isinstance(r, dict) else {}
    out["status"] = inner.get("status") or ("ok" if inner.get("ok") else "no_status")
    out["denied"] = bool(inner.get("denied") or r.get("denied")) if isinstance(r, dict) else False
    out["missing"] = inner.get("missing") or (r.get("missing") if isinstance(r, dict) else None)
    out["resp"] = json.dumps(r, ensure_ascii=False)[:700]
except BaseException as e:  # noqa: BLE001 - probe must always report
    out["ms"] = int((time.time() - t0) * 1000)
    out["status"] = "exception"
    out["error"] = "%s: %s" % (type(e).__name__, str(e)[:300])

sys.stdout.write(json.dumps(out, ensure_ascii=False))
