# -*- coding: utf-8 -*-
"""hand_ik 判据：三连杆 box-constrained IK 的角度/残差/限位。"""
from __future__ import annotations

import math
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

FAILED = []


def check(name, cond, detail=""):
    print(("  ok   " if cond else "  FAIL ") + name + ("" if cond else "  " + str(detail)))
    if not cond:
        FAILED.append(name)


def straight():
    lm = [[0.0, 0.0, 0.0] for _ in range(21)]
    lm[1] = [0.006, 0.020, 0.0]; lm[2] = [0.010, 0.045, 0.0]
    lm[3] = [0.014, 0.065, 0.0]; lm[4] = [0.018, 0.085, 0.0]
    for name, x in (("index", -0.020), ("middle", 0.0), ("ring", 0.020), ("pinky", 0.040)):
        base = {"index": 5, "middle": 9, "ring": 13, "pinky": 17}[name]
        for k, y in enumerate((0.060, 0.100, 0.130, 0.150)):
            lm[base + k] = [x, y, 0.0]
    return lm


def curled():
    lm = straight()
    lm[6] = [-0.020, 0.080, 0.020]
    lm[7] = [-0.020, 0.070, 0.040]
    lm[8] = [-0.020, 0.050, 0.050]
    return lm


def main() -> int:
    from gbt_allinone.tentacle import hand_retarget as HR
    from gbt_allinone.tentacle import hand_ik as IK

    print("[1] 直手 → 非拇指屈曲≈0")
    r = IK.solve(straight(), HR.MODELS["generic_15dof"])
    check("ik ok", r.get("ok") is True, r)
    check("关节 15", len(r.get("joints") or {}) == 15, len(r.get("joints") or {}))
    nonthumb = [v for k, v in r["joints"].items()
                if k.endswith(("mcp", "pip", "dip")) and not k.startswith("thumb")]
    check("直手非拇指 ≤0.05 rad", max(nonthumb) <= 0.05, max(nonthumb))

    print("[2] 弯食指 → IK 追上目标")
    r2 = IK.solve(curled(), HR.MODELS["generic_15dof"])
    j = r2["joints"]
    check("index_mcp > 0.5", j["index_mcp"] > 0.5, j["index_mcp"])
    check("index_pip > 0.8", j["index_pip"] > 0.8, j["index_pip"])
    check("middle 不受影响", abs(j["middle_mcp"]) <= 0.05, j["middle_mcp"])
    check("每指残差 < 1e-3 m", max(x["rms_m"] for x in r2["ik"].values()) < 1e-3,
          r2["ik"])

    print("[3] 限位")
    model = HR.MODELS["generic_15dof"]
    for f in model["fingers"]:
        for jj in f["joints"]:
            v = j.get(jj["name"])
            if v is None:
                continue
            lo, hi = jj["limit"]
            check("%s 在限位内" % jj["name"], lo - 1e-6 <= v <= hi + 1e-6, (v, lo, hi))

    print("[4] 经万能插 op=ik")
    rr = HR.run("ik", landmarks=curled(), model="generic_15dof", unit="deg")
    check("op=ik ok", rr.get("ok") is True, rr)
    check("op=ik 有残差", bool(rr.get("ik")), rr)
    gg = HR.run("ik_global", landmarks=curled(), model="generic_15dof", unit="deg", smooth=0.3)
    check("op=ik_global ok", gg.get("ok") is True, gg)
    check("ik_global 记录平滑", gg.get("smooth") == 0.3, gg.get("smooth"))

    print()
    if FAILED:
        print("FAILED %d: %s" % (len(FAILED), FAILED))
        return 1
    print("ALL PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

