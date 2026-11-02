# -*- coding: utf-8 -*-
"""hand_bridge 力/接触接口：loopback 仿真真跑；真机 must fail-closed。"""
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
    from gbt_allinone.tentacle import hand_bridge as HB

    print("[1] loopback 接触")
    c = HB.run("connect", transport="loopback", profile="generic_20dof")
    check("connect", c.get("ok") is True, c)
    sid = c["session"]
    m = HB.run("move", session=sid, targets={"index_mcp": 0.5}, dry_run=False)
    check("move", m.get("ok") is True, m)
    r = HB.run("contact", session=sid, joint="index_mcp", external=0.2, stiffness=100)
    check("contact ok", r.get("ok") is True, r)
    check("contact 明确 simulated", r.get("simulated") is True, r)
    check("force=k*(q-qe)", abs(r.get("force", 0) - 30.0) < 1e-6, r)
    f = HB.run("read_force", session=sid)
    check("read_force", f.get("ok") is True and abs(f["force"]["index_mcp"] - 30.0) < 1e-6, f)
    cp = HB.run("compliance", session=sid, stiffness=50, damping=0.1)
    check("compliance", cp.get("ok") is True and cp.get("stiffness") == 50, cp)
    HB.run("stop", session=sid)
    HB.run("disconnect", session=sid)

    print("[2] 非 loopback 必须 fail-closed")
    fake = HB.run("contact", session="nope", joint="index_mcp", external=0.0)
    check("无会话拒绝", fake.get("ok") is False, fake)

    print()
    if FAILED:
        print("FAILED %d: %s" % (len(FAILED), FAILED))
        return 1
    print("ALL PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
