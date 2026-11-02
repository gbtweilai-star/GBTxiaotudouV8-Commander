# -*- coding: utf-8 -*-
"""纯 CPU 新节点走真正 engine（EmptyImage→AddNoise→Pad→Canny→SaveImage）。"""
from __future__ import annotations

import os
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

FAILED = []


def check(name, cond, detail=""):
    print(("  ok   " if cond else "  FAIL ") + name + ("" if cond else "  " + str(detail)))
    if not cond:
        FAILED.append(name)


def main() -> int:
    from gbt_allinone.tools import comfy_native as CN
    tmp = tempfile.mkdtemp(prefix="gbt-wf-purecpu-")
    out = os.path.join(tmp, "workflow.png")
    wf = {
        "nodes": [
            {"id": "n1", "node": "EmptyImage", "inputs": {"width": 64, "height": 64}},
            {"id": "n2", "node": "ImageAddNoise", "inputs": {"seed": 7, "strength": 0.1}},
            {"id": "n3", "node": "PadImageNode", "inputs": {"left": 2, "top": 2, "right": 2, "bottom": 2}},
            {"id": "n4", "node": "Canny", "inputs": {"low_threshold": 50, "high_threshold": 150}},
            {"id": "n5", "node": "SaveImage", "inputs": {"out": out}},
        ],
        "edges": [
            {"from": "n1", "to": "n2", "field": "image"},
            {"from": "n2", "to": "n3", "field": "image"},
            {"from": "n3", "to": "n4", "field": "image"},
            {"from": "n4", "to": "n5", "field": "image"},
        ],
    }
    r = CN.run({"op": "run", "workflow": wf})
    check("workflow ok", r.get("ok") is True, r.get("failed_at"))
    check("5 nodes traced", len(r.get("trace") or []) == 5, len(r.get("trace") or []))
    check("output exists", os.path.isfile(out), out)
    check("output 68x68", os.path.getsize(out) > 0 and True)
    print(r.get("trace", [{}])[-1].get("gate", {}).get("info", {}))
    print()
    if FAILED:
        print("FAILED %d: %s" % (len(FAILED), FAILED))
        return 1
    print("ALL PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
