# -*- coding: utf-8 -*-
"""用她自己的原生扫描做深度体检（不另造扫描器）。

逐个调用原生能力，子进程 + 超时隔离；只读/自带判据；
结果落 state/native-scan/report.json，不粉饰。
"""
from __future__ import annotations

import json
import pathlib
import subprocess
import sys
import time

ROOT = pathlib.Path(__file__).resolve().parent.parent
PY = sys.executable
HELPER = ROOT / "tools" / "cap_probe_one.py"
OUT = ROOT / "state" / "native-scan"

SCANS = (
    ("selfscan", "status"),
    ("inventory", "status"),
    ("signature_guard", "status"),
    ("file_hygiene", "status"),
    ("legacy_guard", "status"),
    ("cap_self", "verify"),
    ("caps_called_audit", "audit"),
    ("coverage_auditor", "matrix"),
    ("capability_net", "status"),
    ("tentacle_status", "status"),
    ("truth_scan", "status"),
    ("page_scan", "status"),
    ("page_scan", "scan"),
    ("cross_scan", "scan"),
)


def one(cap, op, timeout):
    t0 = time.time()
    try:
        p = subprocess.run([PY, "-X", "utf8", str(HELPER), str(ROOT), cap, op],
                           capture_output=True, text=True, encoding="utf-8",
                           errors="replace", timeout=timeout)
        lines = (p.stdout or "").strip().splitlines()
        data = json.loads(lines[-1]) if lines else {}
        data["ms"] = int((time.time() - t0) * 1000)
        data["op"] = op
        return data
    except subprocess.TimeoutExpired:
        return {"cap": cap, "op": op, "timeout": True,
                "ms": int((time.time() - t0) * 1000)}
    except Exception as e:  # noqa: BLE001
        return {"cap": cap, "op": op, "error": "%s: %s" % (type(e).__name__, str(e)[:160]),
                "ms": int((time.time() - t0) * 1000)}


def main(argv=None) -> int:
    timeout = float((argv or [None, "120"])[1] if argv and len(argv) > 1 else 120)
    OUT.mkdir(parents=True, exist_ok=True)
    rows = []
    for cap, op in SCANS:
        print("SCAN", cap, op, flush=True)
        rows.append(one(cap, op, timeout))
    (OUT / "report.json").write_text(json.dumps(rows, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(rows, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
