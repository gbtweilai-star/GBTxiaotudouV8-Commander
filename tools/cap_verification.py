# -*- coding: utf-8 -*-
"""能力位核实台账：从真实只读探针 + 真实测试文件引用生成。

不是“人工标绿”：每条都来自：
  · state/cap-smoke/report.json 的 responded 行（真调用、只读 op、子进程超时隔离）；
  · tests/ 与 gbt_allinone/tests/ 里对该能力位名字的真实引用。
"""
from __future__ import annotations

import json
import pathlib
import re
import sys
import time

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from gbt_allinone.caps_registry import BENIGN_CAPS

OUT = ROOT / "state" / "cap-verification.json"
SMOKE = ROOT / "state" / "cap-smoke" / "report.json"


def main() -> int:
    smoke = json.loads(SMOKE.read_text(encoding="utf-8")) if SMOKE.is_file() else {}
    rows = {r.get("cap"): r for r in smoke.get("small") or []}
    test_text = ""
    for folder in (ROOT / "tests", ROOT / "gbt_allinone/tests",
                   ROOT / "holo_pet/tests", ROOT / "holo_pet_w3/tests",
                   ROOT / "tools/dsh-superagent/tests", ROOT / "vendor/taste-skill/tests"):
        for p in (folder.glob("*.py") if folder.is_dir() else []):
            try:
                test_text += "\n" + p.read_text(encoding="utf-8", errors="replace")
            except OSError:
                pass
    caps = {}
    vr = 0
    ht = 0
    for name, meta in BENIGN_CAPS.items():
        r = rows.get(name) or {}
        safe = bool(meta.get("safe"))
        verified = safe and r.get("verdict") == "responded"
        has_test = bool(re.search(r"(?<![A-Za-z0-9_])" + re.escape(name) + r"(?![A-Za-z0-9_])", test_text))
        if verified:
            vr += 1
        if has_test:
            ht += 1
        caps[name] = {"safe": safe, "probe_verdict": r.get("verdict") or "not_probed",
                      "probe_op": r.get("op"), "verified_readonly": bool(verified),
                      "has_test": has_test}
    report = {"at": time.strftime("%Y-%m-%dT%H:%M:%S"),
              "source": ["state/cap-smoke/report.json", "tests/", "gbt_allinone/tests/"],
              "counts": {"total": len(caps), "verified_readonly": vr, "has_test": ht},
              "note": "verified_readonly = safe 且真实只读探针 responded；has_test = 测试文件真实引用能力位名；不把探针当人工核实",
              "caps": caps}
    OUT.write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps({"out": str(OUT), **report["counts"]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
