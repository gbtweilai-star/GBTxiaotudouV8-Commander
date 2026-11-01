"""GBT小土豆V8 · 把真实穿透扫描结果导出给认知界面（扫描可视化用数据）

跑三种目标（bindings / registry / tree:gbt_allinone），保留 per-unit 明细，
写 state/scan-data.json；tools/gen-console-data.py 会把它并入 console-data.js。

不做假数据：导出的是 penetrating_cross_scan 原样返回的 unit_details（agree/arbitrated/unhooked）。

用法：
    python tools/export-scan-data.py              # 三种都扫
    python tools/export-scan-data.py --targets bindings registry
"""
from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PY = str(ROOT / "pyembed" / "python.exe") if (ROOT / "pyembed" / "python.exe").is_file() else sys.executable
OUT = ROOT / "state" / "scan-data.json"
DEFAULT_TARGETS = ["bindings", "registry", "tree:gbt_allinone"]


def run_one(target: str) -> dict:
    t0 = time.time()
    p = subprocess.run([PY, "-X", "utf8", str(ROOT / "tools" / "penetrating_cross_scan.py"),
                        "scan", target], capture_output=True, text=True,
                       encoding="utf-8", errors="replace", cwd=str(ROOT), timeout=1800)
    took = int((time.time() - t0) * 1000)
    try:
        d = json.loads(p.stdout)
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "target": target, "error": "JSON 解析失败：%s" % str(e)[:120],
                "stdout_head": (p.stdout or "")[:200], "ms": took}
    return {
        "ok": bool(d.get("ok")), "target": target, "units": d.get("units"),
        "hooked": d.get("hooked"), "coverage": d.get("coverage"),
        "full_coverage": d.get("full_coverage"),
        "dead_spots": d.get("dead_spots") or [],
        "dead_spot_count": d.get("dead_spot_count", len(d.get("missing") or [])),
        "agree": d.get("agree"), "arbitrated": d.get("arbitrated"),
        "missing": d.get("missing") or [], "mode": d.get("mode"),
        "unit_details": d.get("unit_details") or [], "ms": took,
    }


def main(argv) -> int:
    targets = DEFAULT_TARGETS
    if "--targets" in argv:
        i = argv.index("--targets")
        targets = argv[i + 1:]
    out = {"generated_at": time.strftime("%Y-%m-%dT%H:%M:%S"), "scans": []}
    for t in targets:
        print("扫描:", t)
        r = run_one(t)
        print("  ok=%s units=%s hooked=%s coverage=%s 明细=%d ms=%d"
              % (r.get("ok"), r.get("units"), r.get("hooked"), r.get("coverage"),
                 len(r.get("unit_details") or []), r.get("ms", 0)))
        out["scans"].append(r)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print("写出:", OUT, "|", OUT.stat().st_size // 1024, "KB")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
