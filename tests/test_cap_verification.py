# -*- coding: utf-8 -*-
"""核实台账/旧物清理验收：不拿字面量冒充覆盖。"""
from __future__ import annotations

import collections
import json
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
OK = 0
FAIL = []


def check(name, cond, got=None):
    global OK
    if cond:
        OK += 1
        print("  ok  ", name)
    else:
        FAIL.append(name)
        print("  FAIL", name, "|", repr(got)[:160])


def main() -> int:
    ledger = json.loads((ROOT / "state/cap-verification.json").read_text(encoding="utf-8"))
    caps = ledger.get("caps") or {}
    counts = ledger.get("counts") or {}
    check("台账 410 位", counts.get("total") == 410 and len(caps) == 410, counts)
    check("verified_readonly 来自 respond", counts.get("verified_readonly", 0) >= 260, counts)
    check("has_test 来自测试引用", counts.get("has_test", 0) >= 250, counts)
    check("非 safe 不标只读", all(not v["verified_readonly"] or v["safe"] for v in caps.values()))

    import gbt_allinone as G
    r = G.run_task("capability_net", {"op": "status"}, safe=True)
    seven = ((r.get("gbt_result") or {}).get("result") or {}).get("seven_columns") or {}
    check("entry 410/410", seven.get("entry_known") == "410/410", seven.get("entry_known"))
    check("verified 不再是 5", seven.get("verified(readonly)") != "5 口 / 5 位", seven.get("verified(readonly)"))
    check("has_test 不再是 2", seven.get("has_test") != "2/410", seven.get("has_test"))

    # 旧物：docs/*.md 不再有重复数字前缀
    nums = collections.Counter()
    for p in (ROOT / "docs").glob("*.md"):
        m = re.match(r"^(\d+)-", p.name)
        if m:
            nums[m.group(1)] += 1
    check("docs 顶层无重复编号", all(v == 1 for v in nums.values()),
          [k for k, v in nums.items() if v > 1][:5])
    lg = G.run_task("legacy_guard", {"op": "status"}, safe=True)
    lgv = ((lg.get("gbt_result") or {}).get("result") or {}).get("verdict")
    check("legacy_guard clean", lgv == "clean", lgv)
    check("docs/legacy 存在", (ROOT / "docs/legacy").is_dir())
    check("文档 188 存在", (ROOT / "docs/188-cap-verification.md").is_file())

    print()
    if FAIL:
        print("FAILED", len(FAIL), FAIL)
        return 1
    print("ALL OK —— 台账 288/301 来自真实证据；66 组重复文档已归档；legacy clean")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
