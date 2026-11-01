# -*- coding: utf-8 -*-
"""hand_retarget 判据（不需要模型/网络/硬件）。

跑法：python tests/test_hand_retarget.py
"""
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


def straight_hand():
    """21 点直手：所有手指沿 +y 伸直，掌平面在 z=0。"""
    lm = [[0.0, 0.0, 0.0] for _ in range(21)]
    # thumb: 1..4（沿掌前向，便于把"直手屈曲"判成 0）
    lm[1] = [0.006, 0.020, 0.0]
    lm[2] = [0.010, 0.045, 0.0]
    lm[3] = [0.014, 0.065, 0.0]
    lm[4] = [0.018, 0.085, 0.0]
    xs = {"index": -0.020, "middle": 0.0, "ring": 0.020, "pinky": 0.040}
    for name, x in xs.items():
        base = {"index": 5, "middle": 9, "ring": 13, "pinky": 17}[name]
        lm[base + 0] = [x, 0.060, 0.0]
        lm[base + 1] = [x, 0.100, 0.0]
        lm[base + 2] = [x, 0.130, 0.0]
        lm[base + 3] = [x, 0.150, 0.0]
    return lm


def curled_index_hand():
    lm = straight_hand()
    lm[5] = [-0.020, 0.060, 0.0]
    lm[6] = [-0.020, 0.080, 0.020]
    lm[7] = [-0.020, 0.070, 0.040]
    lm[8] = [-0.020, 0.050, 0.050]
    return lm


def splayed_hand():
    """直手 + 手指沿掌平面呈扇形张开（用于外展/左右手符号判据）。"""
    lm = straight_hand()
    for base, out in ((5, -0.012), (9, 0.0), (13, 0.012), (17, 0.024)):
        for step, k in enumerate(range(4)):
            lm[base + k][0] += out * (step + 1)
    for i, mul in ((1, 0.5), (2, 1.0), (3, 1.5), (4, 2.0)):
        lm[i][0] -= 0.010 * mul
    return lm


def main() -> int:
    from gbt_allinone.tentacle import hand_retarget as HR

    print("[1] 模型与状态")
    st = HR.run("status")
    check("status ok", st.get("ok") is True)
    check("两个内置模型", set(HR.MODELS) == {"generic_15dof", "generic_20dof"})
    check("models 列 15dof 的 15 个关节",
          len([j for f in HR.MODELS["generic_15dof"]["fingers"] for j in f["joints"]]) == 15)
    check("20dof 含 5 个外展", sum(1 for f in HR.MODELS["generic_20dof"]["fingers"]
                                  if f.get("spread")) == 5)

    print("[2] 直手 → 屈曲≈0")
    lm = straight_hand()
    r = HR.run("retarget", landmarks=lm, unit="deg")
    check("retarget ok", r.get("ok") is True, r.get("error"))
    check("关节数 15", r.get("joint_count") == 15, r.get("joint_count"))
    flex = [v for k, v in r["joints"].items() if k.endswith(("mcp", "pip", "dip"))]
    thumb_cmc = r["joints"].get("thumb_mcp", 0.0)
    others = [v for k, v in r["joints"].items()
              if k.endswith(("mcp", "pip", "dip")) and not k.startswith("thumb")]
    check("直手非拇指屈曲 ≤5°", max(others) <= 5.0, max(others))
    check("直手拇指 CMC 自然角 ≤15°", thumb_cmc <= 15.0, thumb_cmc)

    print("[3] 弯曲食指 → 屈曲变大")
    r2 = HR.run("retarget", landmarks=curled_index_hand(), unit="rad")
    vals = {k: v for k, v in r2["joints"].items() if k.startswith("index")}
    check("食指 mcp 屈曲 > 0.3 rad", vals["index_mcp"] > 0.3, vals)
    check("食指 pip 屈曲 > 0.3 rad", vals["index_pip"] > 0.3, vals)
    check("中指不受影响（middle_mcp ≈ 0）", abs(r2["joints"]["middle_mcp"]) <= 0.15,
          r2["joints"]["middle_mcp"])

    print("[4] 左右手外展符号")
    splay = splayed_hand()
    ran = HR.run("retarget", landmarks=splay, model="generic_20dof", hand="right", unit="rad")
    lan = HR.run("retarget", landmarks=splay, model="generic_20dof", hand="left", unit="rad")
    check("20dof 关节数 20", ran.get("joint_count") == 20, ran.get("joint_count"))
    check("张开手食指有外展角", abs(ran["joints"]["index_abd"]) > 0.01, ran["joints"]["index_abd"])
    check("左右外展符号相反",
          ran["joints"]["index_abd"] * lan["joints"]["index_abd"] < 0,
          (ran["joints"]["index_abd"], lan["joints"]["index_abd"]))

    print("[5] 直通模式 + 限位")
    r = HR.run("retarget", joints={"thumb_mcp": 99.0, "index_mcp": 0.2})
    check("越界被夹到限位", 0.0 <= r["joints"]["thumb_mcp"] <= 1.4, r["joints"])
    check("越界有记录", "thumb_mcp" in (r.get("clamped") or []), r.get("clamped"))
    check("直通单位换算", HR.run("retarget", joints={"index_mcp": 0.5}, unit="deg")
          ["joints"]["index_mcp"] > 20)

    print("[6] 错误输入")
    bad = HR.run("retarget", landmarks=[[0, 0, 0]] * 20)
    check("20 点被拒", bad.get("ok") is False and bad.get("status") == "user_error", bad)
    bad2 = HR.run("retarget", landmarks=lm, model="nope")
    check("未知模型被拒", bad2.get("ok") is False and bad2.get("status") == "needs_input", bad2)
    bad3 = HR.run("retarget")
    check("缺输入被拒", bad3.get("ok") is False and bad3.get("status") == "needs_input", bad3)
    check("未知 op fail-closed", HR.run("xxx").get("ok") is False)

    print()
    if FAILED:
        print("FAILED %d: %s" % (len(FAILED), FAILED))
        return 1
    print("ALL PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
