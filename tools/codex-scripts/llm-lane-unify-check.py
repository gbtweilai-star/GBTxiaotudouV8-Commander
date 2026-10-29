#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# 开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属
"""大模型链路统一判据（llm-lane-unify-check）

主人令 2026-10-16：「我们自己的大模型链路要统一别分叉」。

旧病（仓里自己记着，长期无判据覆盖）：
  `cloud_llm._KEY_CHAIN` 自己写一份（9~10 条），`key_gateway.PROVIDERS` 14 条（2026-10-29 接入免密 kilo 后 13→14），
  两表差 nvidia-glm / nvidia-flash / freellmapi / gbt-local 且长期不同。

判据：`_KEY_CHAIN` 必须 **== PROVIDERS 去掉退场车道** 的派生结果（名字+顺序）。
负对照：少一条 / 两条对调 ⇒ 必须红（否则尺子是空的）。
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

WS = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(WS))
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


def derive() -> list:
    from gbt_allinone.llm import cloud_llm as C
    from gbt_allinone.llm.key_gateway import PROVIDERS
    retired = getattr(C, "_RETIRED_LANES", set())
    return [p["name"] for p in PROVIDERS
            if p.get("name") not in retired and p.get("select", True)]


def audit() -> dict:
    from gbt_allinone.llm import cloud_llm as C
    want = derive()
    have = [k[0] for k in C._KEY_CHAIN]
    bad = []
    if have != want:
        bad.append({"why": "两表不一致", "want": want, "have": have})
    if not have or have[0] != "agnes":
        bad.append({"why": "首位不是 agnes（Owner 2026-09-19 契约，test_framework 铉着）", "have": have[:2]})
    if "gbt-local" in have:
        bad.append({"why": "退场车道 gbt-local 又回到链里（主人：本机不再承担模型）"})
    return {"ok": not bad, "kind": "llm_lane_unify", "chain_len": len(have), "chain": have,
            "single_source": "gbt_allinone/llm/key_gateway.py::PROVIDERS",
            "derived_from": "cloud_llm._KEY_CHAIN 现为派生表", "violations": bad}


def selftest() -> dict:
    """负对照：模拟两种分叉，必须都被咬。"""
    from gbt_allinone.llm import cloud_llm as C
    real = C._KEY_CHAIN
    outs = {}
    try:
        C._KEY_CHAIN = real[:-1]
        outs["少一条被咬"] = not audit()["ok"]
        C._KEY_CHAIN = [real[1], real[0]] + list(real[2:])
        outs["对调被咬"] = not audit()["ok"]
    finally:
        C._KEY_CHAIN = real
    outs["正例绿"] = audit()["ok"]
    return {"ok": all(outs.values()), "kind": "llm_lane_unify_selftest", **outs}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="大模型链路统一判据")
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    r = selftest() if a.selftest else audit()
    if a.json:
        print(json.dumps(r, ensure_ascii=False, indent=1))
    else:
        print("链路统一：%s · 链长 %s · %s" % ("PASS" if r["ok"] else "FAIL",
              r.get("chain_len", "-"), "单一真源 " + r.get("single_source", "")))
        for v in (r.get("violations") or []):
            print("  ✖ " + json.dumps(v, ensure_ascii=False)[:150])
    return 0 if r["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
