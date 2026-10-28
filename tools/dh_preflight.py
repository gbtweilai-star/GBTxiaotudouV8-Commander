#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""dh_preflight —— 数字人上场前必过的一道门（把孤儿能力接成活路径）。

为什么要有它：
  dh_asset_gate（八条资产闸）和 dh_realism（逼真度八步）一直是**孤儿** ——
  run_task 叫得到，但没有一条活路径在用。
  结果就是：页面加载哪份 glb、那份 glb 过不过闸，从来没人查。
  实测第一次接上就发现问题：闸写死 joints==65，而在役件 dh-v7-detail.glb 是 66 根骨
  ⇒ **这条闸对在役件恒红，而没人知道**。

它做什么：
  ① 从页面源码里读出**真正加载的 glb**（不是脚本里写死的那份）
  ② 拿它去跑 dh_asset_gate 八条
  ③ 顺带读 dh_realism 的缺口数（只读，不渲染）
  ④ 八条不全绿 ⇒ 返回 ok=False，并列出哪几条红

口径：只读。不起 Blender、不写盘、不出网。
"""
from __future__ import annotations

import json
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
PAGE = ROOT / "holo_pet_w3" / "digital-human" / "index.html"


def in_service_glb() -> tuple[str, str]:
    """从页面源码读真正加载的 glb（页面才是真源，不是脚本常量）。"""
    try:
        s = PAGE.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return "", "页面读不到"
    m = re.search(r"assets/(dh-[A-Za-z0-9_.-]+\.glb)", s)
    if not m:
        return "", "页面里找不到 assets/*.glb"
    return "holo_pet_w3/voice-theater/assets/" + m.group(1), ""


def main() -> int:
    glb, why = in_service_glb()
    if not glb:
        print(json.dumps({"ok": False, "why": why}, ensure_ascii=False))
        return 1
    from gbt_allinone.api import run_task

    r = run_task("dh_asset_gate", {"op": "run", "glb": glb})
    res = (r.get("gbt_result") or {}).get("result") or r.get("result") or {}
    rows = res.get("八条") or []
    ng = sum(1 for x in rows if x.get("过"))
    red = [x.get("名") for x in rows if not x.get("过")]

    gaps = None
    try:
        rr = run_task("dh_realism", {})
        rres = (rr.get("gbt_result") or {}).get("result") or rr.get("result") or {}
        gaps = rres.get("缺口")
    except Exception:                                        # noqa: BLE001
        pass

    out = {"ok": bool(rows) and ng == len(rows) and not red,
           "glb": glb, "字节": res.get("字节"),
           "八条": "%d/%d" % (ng, len(rows)),
           "红": red,
           "骨数提示": (rows[0].get("读数") if rows else ""),
           "逼真度缺口": gaps}
    print(json.dumps(out, ensure_ascii=False))
    return 0 if out["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
