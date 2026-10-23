# -*- coding: utf-8 -*-
"""dh_pose 判据件（正负控齐）· 2026-10-13 建位时同批落。

正控：语义编译真的产出骨角度（转身走 Y 轴＝自转 · 屈指覆盖 30 根指骨）
负控：认不出的意图 / 命令不成三元组 ⇒ **fail-closed**，绝不瞎编

可 pytest 跑，也可直接 `python gbt_allinone/tests/test_dh_pose.py`。
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from gbt_allinone.tools import dh_pose  # noqa: E402


def test_status_reads_semantics():
    r = dh_pose.run("status")
    assert r["ok"] is True
    assert r["条数"] >= 30, "语义表条数应 ≥30（现读 %s）" % r.get("条数")
    assert r["不写盘"] is True


def test_yaw_goes_through_y_axis():
    """转身必须落在**局部 Y**（自转轴）——这是换探针才量出来的那条。"""
    r = dh_pose.run("compile", cmd=["转身", "-", 35])
    assert r["ok"] is True, r
    hips = r["pose"].get("mixamorig:Hips")
    assert hips and abs(hips[1]) > 1.0, "Hips 的自转应落在 Y 轴，实得 %s" % hips
    assert abs(hips[0]) < 1e-6 and abs(hips[2]) < 1e-6, "自转不该牵动 X/Z：%s" % hips


def test_finger_curl_covers_30_bones():
    r = dh_pose.run("compile", cmd=["屈指", "L", 78])
    assert r["ok"] is True
    fingers = [k for k in r["pose"] if "Hand" in k]
    assert len(fingers) == 15, "单手屈指应覆盖 15 根（5 指 × 3 节），实得 %d" % len(fingers)


def test_unknown_intent_fails_closed():
    r = dh_pose.run("compile", cmd=["打太极", "-", 30])
    assert r["ok"] is False and r.get("fail_closed") is True
    assert "语义表里没有" in r["error"]


def test_bad_cmd_shape_fails_closed():
    r = dh_pose.run("compile", cmd=["抬臂", "R"])
    assert r["ok"] is False and r.get("fail_closed") is True


def test_unknown_op_fails_closed():
    r = dh_pose.run("飞起来")
    assert r["ok"] is False and r.get("fail_closed") is True
    assert "ops" in r


if __name__ == "__main__":
    fails = []
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            try:
                fn()
                print("PASS %s" % name)
            except AssertionError as e:  # noqa: BLE001
                fails.append(name)
                print("FAIL %s : %s" % (name, e))
    print("判据 %s（%d 条）" % ("全过" if not fails else "有红：" + ",".join(fails),
                              len([k for k in globals() if k.startswith("test_")])))
    raise SystemExit(1 if fails else 0)
