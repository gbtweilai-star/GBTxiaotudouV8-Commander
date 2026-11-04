# -*- coding: utf-8 -*-
"""native_t2i_worker — 常驻 SD-Turbo worker（JSONL stdin/stdout），模型只加载一次。"""
from __future__ import annotations

import argparse
import json
import os
import sys


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", required=True, help="live repo root")
    ap.add_argument("--serve", action="store_true")
    args = ap.parse_args()
    root = os.path.abspath(args.root)
    sys.path.insert(0, root)
    from gbt_allinone.tools import comfy_native as CN

    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            req = json.loads(line)
            op = str(req.get("op") or "")
            if op == "i2v_svd":
                node = "i2v_svd"
            elif op == "t2i_fused" or str(req.get("model") or "") == "fused":
                node = "t2i_fused"
            else:
                node = "t2i_sdturbo"
            r = CN.NODES[node]["fn"](req, {})
        except Exception as e:  # noqa: BLE001
            r = {"ok": False, "error": "%s: %s" % (type(e).__name__, str(e)[:300])}
        sys.stdout.write(json.dumps(r, ensure_ascii=False) + "\n")
        sys.stdout.flush()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
