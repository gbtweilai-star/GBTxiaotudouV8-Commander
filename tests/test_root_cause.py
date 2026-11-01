# -*- coding: utf-8 -*-
"""病因定位判据：假设必须挂证据、无假设不硬编、案卷落盘。

跑法：python tests/test_root_cause.py
"""
from __future__ import annotations

import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

FAILED = []


def check(name, cond, detail=""):
    print(("  ok   " if cond else "  FAIL ") + name + ("" if cond else "  " + str(detail)[:200]))
    if not cond:
        FAILED.append(name)


def main() -> int:
    from gbt_allinone.tentacle import root_cause as RC

    print("[1] diagnose：跑得动且有读数")
    r = RC.run("diagnose", symptom="测试用例失败")
    check("ok", r.get("ok") is True, r.get("error"))
    dg = r.get("evidence_digest") or {}
    check("证据齐全（6 项）", len(dg) >= 6, dg)
    check("verdict 合法", r.get("verdict") in ("root_cause_found", "inconclusive"), r.get("verdict"))

    print("[2] 假设排序：有 found 的排前面")
    cid = r.get("case")
    c = RC.run("case", id=cid)
    hs = (c.get("case") or {}).get("hypotheses_ranked") or []
    check("假设数 >= 7", len(hs) >= 7, len(hs))
    weights = [h["weight"] for h in hs]
    check("按权重降序", weights == sorted(weights, reverse=True), weights[:5])
    check("每条都有 next_probe", all(h.get("next_probe") for h in hs))

    print("[3] 案卷落盘")
    check("case 文件存在", c.get("ok") is True and bool(c.get("case")), c.get("error"))
    check("案件能列", (RC.run("status").get("count") or 0) >= 1, RC.run("status").get("count"))

    print("[4] 不猜：假设全部不成立时如实 inconclusive")
    # 造一个"全是好消息"的假证据来验证判定逻辑
    fake = {
        "caps": {"result": {"counts": {"registry": 1, "snapshot": 1, "dispatched": 1}}},
        "selfscan": {"ok": True, "verdict": "clean"},
        "signature": {"ok": True, "verdict": "clean", "result": {"missing": []}},
        "inventory": {"ok": True, "verdict": "clean", "result": {"items": {"foreign": []}}},
        "legacy": {"ok": True, "verdict": "clean", "result": {"categories": {}}},
        "truth_scan": {"ok": True, "verdict": "clean"},
        "panel": {"result": {}},
    }
    hs2 = RC._hypotheses(fake, "x")
    found = [h for h in hs2 if h["found"]]
    check("全好时无假设成立", len(found) == 0, [h["hypothesis"] for h in found])

    print()
    if FAILED:
        print("FAILED %d: %s" % (len(FAILED), ", ".join(FAILED)))
        return 1
    print("ALL OK —— 假设挂证据、按权重排序、无假设不硬编、案卷可查")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
