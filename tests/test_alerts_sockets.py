# -*- coding: utf-8 -*-
"""`alerts` 认插口变化 的判据（离线，不重扫 25 秒）。

主人令 2026-11-01 之后的下一步（两个一起做之一）：
插口拔掉/断线不能只躺在 `state/omni_open.json` 里，**她一张嘴就要说出来**。

测法：直接替换 `omni_open._load` 的返回值（假快照），看 `selfscan.alerts()` 是否把它报出来。
跑法：python tests/test_alerts_sockets.py
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
    from gbt_allinone import selfscan
    from gbt_allinone.tentacle import omni_open as OO

    real = OO._load

    print("[1] 插口掉了 ⇒ alerts 必须说出来")
    OO._load = lambda: {"at": "2026-11-01T00:00:00", "diff": {
        "alert": True, "counts": {"added": 0, "removed": 1, "flipped": 1},
        "removed": [{"kind": "ai", "target": "http://127.0.0.1:8792"}],
        "flipped": [{"kind": "port", "target": "127.0.0.1:445", "was": True, "now": False}]}}
    a = selfscan.alerts(200) if "last" in selfscan.alerts.__code__.co_varnames else selfscan.alerts()
    check("sockets 字段在", "sockets" in a, list(a))
    check("alert 被转述", bool((a.get("sockets") or {}).get("alert")), a.get("sockets"))
    check("needs_a_look=True", bool(a.get("needs_a_look")), a.get("needs_a_look"))
    check("不是 quiet", a.get("quiet") is not True or a.get("anomalies"), a)

    print("[2] 没变化 ⇒ 不许虚报")
    OO._load = lambda: {"at": "2026-11-01T00:00:00",
                        "diff": {"alert": False, "counts": {"added": 2, "removed": 0, "flipped": 0}}}
    b = selfscan.alerts()
    check("sockets.alert=False", not (b.get("sockets") or {}).get("alert"), b.get("sockets"))

    print("[3] 首扫 ⇒ 不算漂移")
    OO._load = lambda: {"at": "2026-11-01T00:00:00",
                        "diff": {"alert": False, "first_scan": True}}
    c = selfscan.alerts()
    check("首扫不报警", not (c.get("sockets") or {}).get("alert"), c.get("sockets"))

    print("[4] 快照读不到 ⇒ 不能把声带弄崩")
    def _boom():
        raise RuntimeError("no snapshot")
    OO._load = _boom
    try:
        d = selfscan.alerts()
        ok = isinstance(d, dict)
    except Exception as e:  # noqa: BLE001
        ok = False
        print("    raised:", e)
    check("读不到也返回 dict（不崩）", ok)

    OO._load = real

    print()
    if FAILED:
        print("FAILED %d: %s" % (len(FAILED), ", ".join(FAILED)))
        return 1
    print("ALL OK —— 插口掉了，声带会喊；没掉，不虚报")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
