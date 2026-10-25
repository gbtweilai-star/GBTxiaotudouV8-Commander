# -*- coding: utf-8 -*-
"""骨架真相源判据（rig-source-check）—— 专业骨架（Rigify）不许比手搓表更差。

主人令（2026-10-09）：「数字人位置都错了」「安装专业化多功能骨架绑定工具，别自己手搓」。
本件咬四件事（**逐骨报，不报合计**）：
  ① **父链完整**：每根骨的 p 要么是 root、要么是表里真有的骨（缺一个就是断链）
  ② **镜像律**：rest_L == -rest_R、off_x_L == -off_x_R（容差 0.5），与页面既有约定同口径
  ③ **比例落在人形区间**：髋到足底占全高 0.45–0.62 · 膝 0.68–0.80 · 踝 0.90–0.99 · 肩 0.16–0.24
  ④ **负对照会红**：把一侧 rest 取反 / 把髋比例改出区间 ⇒ 必须报红（判据自己也要被测）
用法： py -3.14 -X utf8 tools/codex-scripts/rig-source-check.py [--js <rig-data.js>]
退出码：0 全过 · 1 有红 · 2 读不动
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_JS = ROOT / "holo_pet_w3" / "digital-human" / "rig-data.js"
RANGES = {"髋到足底占全高": (0.45, 0.62), "膝占全高": (0.68, 0.80),
          "踝占全高": (0.90, 0.99), "肩占全高": (0.16, 0.24)}


def load_js(p: Path) -> dict:
    t = p.read_text(encoding="utf-8")
    i, j = t.index("="), t.rindex(";")
    return json.loads(t[i + 1:j])


def check(d: dict, tol: float = 0.5) -> dict:
    bones = d.get("骨") or []
    if not bones:
        return {"ok": False, "errs": ["rig-data.js 里一根骨都没有"]}
    names = {b["n"] for b in bones}
    errs, rows = [], []
    by = {b["n"]: b for b in bones}
    for b in bones:
        p = b.get("p")
        if p != "root" and p not in names:
            errs.append("%s 的父骨 %s 不在表里（断链）" % (b["n"], p))
        rows.append("%-11s p=%-11s len=%-8s rest=%-8s" % (b["n"], p, b["len"], b["rest"]))
    pairs = []
    for n in sorted(names):
        if n.endswith("L") and (n[:-1] + "R") in names:
            L, R = by[n], by[n[:-1] + "R"]
            d_rest = abs(L["rest"] + R["rest"])
            d_off = abs(L["off"][0] + R["off"][0])
            pairs.append((n, d_rest, d_off))
            if d_rest > tol:
                errs.append("镜像律破：%s rest=%.2f vs %s rest=%.2f（差 %.2f）"
                            % (n, L["rest"], R["n"], R["rest"], d_rest))
            if d_off > tol:
                errs.append("镜像律破：%s off.x=%.2f vs %s off.x=%.2f（差 %.2f）"
                            % (n, L["off"][0], R["n"], R["off"][0], d_off))
    prop = d.get("比例") or {}
    for k, (lo, hi) in RANGES.items():
        v = prop.get(k)
        if v is None:
            errs.append("比例缺读数：%s" % k)
        elif not (lo <= float(v) <= hi):
            errs.append("比例出区间：%s = %s（应 %.2f–%.2f）" % (k, v, lo, hi))
    return {"ok": not errs, "errs": errs, "rows": rows,
            "镜像对": len(pairs), "最大镜像误差": max([max(a, b) for _, a, b in pairs] or [0]),
            "比例": prop, "骨数": len(bones)}


def selftest(d: dict) -> int:
    import copy
    bad1 = copy.deepcopy(d)
    for b in bad1["骨"]:
        if b["n"] == "upperArmL":
            b["rest"] = -b["rest"]
    r1 = check(bad1)
    red1 = not r1["ok"]
    print("负对照A·一侧 rest 取反 ⇒ 期望红 实得 %s（%s）" % ("红" if red1 else "绿", r1["errs"][:1]))
    bad2 = copy.deepcopy(d)
    bad2["比例"] = dict(bad2["比例"], **{"髋到足底占全高": 0.90})
    r2 = check(bad2)
    red2 = not r2["ok"]
    print("负对照B·髋比例改到 0.90 ⇒ 期望红 实得 %s（%s）" % ("红" if red2 else "绿", r2["errs"][:1]))
    bad3 = copy.deepcopy(d)
    bad3["骨"] = [b for b in bad3["骨"] if b["n"] != "shinL"]
    r3 = check(bad3)
    red3 = not r3["ok"]
    print("负对照C·抽掉 shinL ⇒ 期望红 实得 %s（%s）" % ("红" if red3 else "绿", r3["errs"][:1]))
    return 0 if (red1 and red2 and red3) else 1


def main() -> int:
    ap = argparse.ArgumentParser(description="骨架真相源判据")
    ap.add_argument("--js", default=str(DEFAULT_JS))
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    p = Path(a.js)
    if not p.is_file():
        print("rig-data.js 不在：%s（先跑 blender -P tools/codex-scripts/rigify-skeleton.py）" % p)
        return 2
    try:
        d = load_js(p)
    except Exception as exc:                                       # noqa: BLE001
        print("读不动：%s" % exc)
        return 2
    if a.selftest:
        rc = selftest(d)
        print("自检：%s" % ("全过" if rc == 0 else "不过"))
        return rc
    r = check(d)
    print("骨架真相源 %s" % p)
    print("来源：%s" % d.get("来源", "?"))
    print("骨 %d · 镜像对 %d · 最大镜像误差 %.3f" % (r["骨数"], r["镜像对"], r["最大镜像误差"]))
    print("比例：%s" % json.dumps(r["比例"], ensure_ascii=False))
    for row in r["rows"]:
        print("  " + row)
    if r["errs"]:
        print("\n红 %d 条：" % len(r["errs"]))
        for e in r["errs"]:
            print("  - " + e)
    print("\n判据：%s" % ("PASS" if r["ok"] else "FAIL"))
    return 0 if r["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
