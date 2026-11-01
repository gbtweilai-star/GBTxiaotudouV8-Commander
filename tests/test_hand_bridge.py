# -*- coding: utf-8 -*-
"""hand_bridge 判据（loopback + Modbus 帧，不需要真硬件/网络）。

跑法：python tests/test_hand_bridge.py
"""
from __future__ import annotations

import os
import struct
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

FAILED = []


def check(name, cond, detail=""):
    print(("  ok   " if cond else "  FAIL ") + name + ("" if cond else "  " + str(detail)))
    if not cond:
        FAILED.append(name)


def main() -> int:
    from gbt_allinone.tentacle import hand_bridge as HB

    print("[1] 状态/传输/档案")
    st = HB.run("status")
    check("status ok", st.get("ok") is True)
    check("loopback 可用", st["transports"]["loopback"]["available"] is True)
    check("Modbus TCP 可用（纯 stdlib）", st["transports"]["modbus_tcp"]["available"] is True)
    profs = HB.run("profiles")
    names = {p["name"] for p in profs["profiles"]}
    check("内置 6/20 DoF 档案", {"generic_6dof", "generic_20dof"} <= names, names)

    print("[2] loopback 生命周期")
    c = HB.run("connect", transport="loopback", profile="generic_6dof")
    check("connect ok", c.get("ok") is True, c.get("error"))
    sid = c.get("session")
    check("明标 simulated", c.get("simulated") is True)
    s0 = HB.run("read_state", session=sid)
    check("初态全 0", all(abs(v) < 1e-9 for v in s0["state"]["joints"].values()), s0)

    print("[3] dry_run 不写、真写才动")
    d = HB.run("move", session=sid, targets={"thumb_flex": 0.5})
    check("dry_run ok", d.get("ok") is True and d.get("dry_run") is True)
    check("dry_run 没有写", abs(HB.run("read_state", session=sid)["state"]["joints"]["thumb_flex"]) < 1e-9)
    m = HB.run("move", session=sid, targets={"thumb_flex": 0.5}, dry_run=False)
    check("真写 ok", m.get("ok") is True, m)
    check("回读 = 0.5", abs(HB.run("read_state", session=sid)["state"]["joints"]["thumb_flex"] - 0.5) < 1e-6)

    print("[4] 限位与拒收")
    m2 = HB.run("move", session=sid, targets={"thumb_flex": 99.0}, dry_run=False)
    check("越界夹到限位", abs(m2["applied"]["thumb_flex"] - 1.8) < 1e-6, m2)
    check("越界有记录", "thumb_flex" in (m2.get("clamped") or []), m2.get("clamped"))
    bad = HB.run("move", session=sid, targets={"不存在": 0.1})
    check("未知关节拒收", bad.get("ok") is False and bad.get("status") == "user_error", bad)
    check("未知会话拒收", HB.run("read_state", session="nope").get("ok") is False)
    check("未知传输拒收", HB.run("connect", transport="nope").get("ok") is False)

    print("[5] stop / disconnect")
    s = HB.run("stop", session=sid)
    check("stop ok", s.get("ok") is True, s)
    check("stop 后回 0", all(abs(v) < 1e-9 for v in HB.run("read_state", session=sid)["state"]["joints"].values()))
    dc = HB.run("disconnect", session=sid)
    check("disconnect ok", dc.get("ok") is True)
    check("会话已移除", HB.run("read_state", session=sid).get("ok") is False)

    print("[6] Modbus 帧（真编解码）")
    f = HB.modbus_build_read(1, 10, 3)
    check("FC03 帧长 = MBAP7 + PDU5", len(f) == 12, len(f))
    pdu = b"\x03\x06" + struct.pack(">HHH", 100, 200, 300)
    resp = struct.pack(">HHHB", 0, 0, len(pdu) + 1, 1) + pdu
    r = HB.modbus_parse(resp)
    check("FC03 解析值", r.get("values") == [100, 200, 300], r)
    w = HB.modbus_build_write(2, 5, [1, 2])
    check("FC16 帧含 unit=2", w[6] == 2, w[6])
    pdu16 = b"\x10" + struct.pack(">HH", 5, 2)
    resp16 = struct.pack(">HHHB", 0, 0, len(pdu16) + 1, 2) + pdu16
    r16 = HB.modbus_parse(resp16)
    check("FC16 解析地址/数量", r16.get("addr") == 5 and r16.get("count") == 2, r16)
    err = struct.pack(">HHHB", 0, 0, 3, 1) + b"\x83\x02"
    check("异常码被识别", HB.modbus_parse(err).get("ok") is False)

    print("[7] 真机口径（不缺数据时才继续）")
    check("serial 依赖状态有明确布尔",
          isinstance(HB.TRANSPORTS["serial"]["available"], bool))
    check("can 依赖状态有明确布尔", isinstance(HB.TRANSPORTS["can"]["available"], bool))
    check("未知 op fail-closed", HB.run("xxx").get("ok") is False)

    print()
    if FAILED:
        print("FAILED %d: %s" % (len(FAILED), FAILED))
        return 1
    print("ALL PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
