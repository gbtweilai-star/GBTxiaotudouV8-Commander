# -*- coding: utf-8 -*-
"""`inventory` 认「部署形态」的判据：checkout（根即仓库）vs home（家根+子目录）。

主人令 2026-11-01（按源码推荐落地）：旧分类器只有一种形态假设 —— 家根是收过的目录、
仓库包在子目录里。于是把仓库根当工作目录时，`docs/ assets/ tests/ tools/` 这些
**本来属于仓库**的顶层项全被判成"异物"（实测 29 项假阳性），
`file_hygiene` / `cross_scan` 跟着一起红。

修法：**多认一种形态**（不是把分类表调松）——
checkout 形态下，仓库**声明过的**顶层项归 `framework`；清单来自 `state/repo-layout.json`
（由仓库快照生成），取不到才退回页图前缀与固定件，**绝不猜**。

跑法：python tests/test_inventory_checkout.py
"""
from __future__ import annotations

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

FAILED = []


def check(name, cond, detail=""):
    print(("  ok   " if cond else "  FAIL ") + name + ("" if cond else "  " + str(detail)))
    if not cond:
        FAILED.append(name)


def main() -> int:
    from gbt_allinone import inventory as INV

    print("[1] 形态识别")
    check("当前是 checkout 形态", INV._CHECKOUT is True, INV._CHECKOUT)
    check("输出里带 mode/assumption", True)  # 由 [2] 的 scan 结果验证

    print("[2] 盘点：仓库自己的顶层项不再是异物")
    r = INV.scan()
    check("mode=checkout", r.get("mode") == "checkout", r.get("mode"))
    check("assumption 写得出来", bool(r.get("assumption")), r.get("assumption"))
    check("foreign 已清零", r.get("verdict") == "clean" and not (r.get("items") or {}).get("foreign"),
          (r.get("verdict"), (r.get("items") or {}).get("foreign")))
    fw = (r.get("items") or {}).get("framework") or []
    for must in ("gbt_allinone", "docs", "tests", "tools"):
        check("  %s 归 framework" % must, must in fw, fw[:10])

    print("[3] 真异物仍然会被抓（不许一刀切放行）")
    import pathlib
    stray = pathlib.Path(str(INV._HOME / "totally-not-in-repo-xyz.bin"))
    check("清单外的东西仍判 foreign", INV._classify(stray) == "foreign", INV._classify(stray))

    print("[4] home 形态下旧口径不变（不许为了让我们绿而改旧机器读数）")
    old = INV._CHECKOUT
    try:
        INV._CHECKOUT = False
        r2 = INV.scan()
        check("home 形态仍会报 foreign>0", (r2.get("verdict") != "clean"), r2.get("verdict"))
    finally:
        INV._CHECKOUT = old

    print()
    if FAILED:
        print("FAILED %d: %s" % (len(FAILED), ", ".join(FAILED)))
        return 1
    print("ALL OK —— checkout/home 两种形态各有判据，真异物照样抓")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
