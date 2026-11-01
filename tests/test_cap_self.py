# -*- coding: utf-8 -*-
"""能力自知 `cap_self` 的防漂移判据（不需要模型、不需要网络）。

主人 2026-10-31：「所有原生能力她有时候连自己都不知道，这让我更纳闷」

为什么这份测试能防"不知道自己有什么"：
她的自知以前来自三份副本（注册表 / data 快照 / docs 手写数字），三份漂移时没人会红。
这里把**三源对账**钉成断言：快照落后、缺分派、缺 desc、policy 炸 —— 任何一条都 FAIL。
另外还测"漂移确实会被抓到"（喂一份假快照给 verify，必须红）。

跑法：python tests/test_cap_self.py
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
    from gbt_allinone.caps_registry import BENIGN_CAPS
    from gbt_allinone.tentacle import cap_self as CS

    print("[1] 五处齐")
    check("cap_self 在注册表", "cap_self" in BENIGN_CAPS)
    api = open(os.path.join(ROOT, "gbt_allinone", "api.py"), encoding="utf-8").read()
    check("api.py 有分派分支", 'if kind == "cap_self"' in api)

    print("[2] 三源对账（真跑）")
    v = CS.verify()
    check("verify 全绿", bool(v.get("ok")), v.get("failed"))
    c = v.get("counts") or {}
    check("注册表 = 快照 = 分派",
          c.get("registry") == c.get("snapshot") == c.get("dispatched"),
          c)

    print("[3] 漂移一定被抓到（负对照）")
    real = CS.snapshot
    try:
        CS.snapshot = lambda: {"fake_only": {"name": "fake_only"}}
        bad = CS.verify()
        check("假快照 ⇒ verify 必须红", bad.get("ok") is False, bad.get("failed"))
        check("漂移被点名（缺项/多项都报）",
              bool((bad.get("checks") or [{}])[0].get("extra"))
              or any(ch.get("missing") for ch in bad.get("checks") or []),
              bad.get("checks"))
    finally:
        CS.snapshot = real

    print("[4] has 的三种'没有'要分开说 / brief 能进上下文")
    h = CS.has("pulse_core")
    check("存在的位：has=True + 有分派 + 作用域说清",
          h.get("has") is True and h.get("dispatched") is True and "scopes" in h, h)
    n = CS.has("绝对不存在的能力名_zzz")
    check("不存在的位：has=False 且给 why", n.get("has") is False and bool(n.get("why")), n)
    b = CS.brief()
    check("brief 可塞进上下文（<1200 字）", b.get("ok") and b.get("chars", 9999) < 1200, b.get("chars"))
    check("brief 里含真实总数", str(len(BENIGN_CAPS)) in b.get("text", ""), b.get("text", "")[:80])

    print("[5] ask：按意图召回（离线、秒级）")
    a = CS.ask("帮我把文件转成 PPT")
    check("ask 有候选", bool(a.get("ok")) and a.get("count", 0) > 0, a.get("error"))

    print()
    if FAILED:
        print("FAILED %d: %s" % (len(FAILED), ", ".join(FAILED)))
        return 1
    print("ALL OK —— 她的自知现在只有一个真源，漂移会红")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
