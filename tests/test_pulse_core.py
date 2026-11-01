# -*- coding: utf-8 -*-
"""四合一原生位 `pulse_core` 的**防丢失判据**（不需要引擎也能跑，缺件会明确报缺）。

主人令 2026-10-31：
  「把这套量化脉冲提速，直达压缩按需激活的理念化为她的原生能力，
    这样就不会出现遗漏和丢失了」

这份测试存在的唯一理由：**这套理念曾经活在文档里，每轮只实现一个切片、没人拦得住。**
现在它是一条能力位 + 一组可执行判据；判据红了就说明又被"实现丢了一半"，
CI/回归会当场咬住，不再靠人记得。

跑法：python tests/test_pulse_core.py
"""
from __future__ import annotations

import json
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
    from gbt_allinone.security import policy as P
    from gbt_allinone.tentacle import pulse_core as PC

    print("[1] 五处齐：注册 ↔ 分派 ↔ 门 ↔ 审计字段 ↔ 测试")
    check("pulse_core 在注册表", "pulse_core" in BENIGN_CAPS)
    api = open(os.path.join(ROOT, "gbt_allinone", "api.py"), encoding="utf-8").read()
    check("api.py 有分派分支", 'if kind == "pulse_core"' in api)
    fwd = P.evaluate("pulse_core", {"op": "route", "intent": "x"})
    check("route 默认零作用域（不擅自起进程）", not fwd.scopes, fwd.scopes)
    wake = P.evaluate("pulse_core", {"op": "route", "wake": True})
    check("route wake=true 收 process_execute", "process_execute" in wake.scopes, wake.scopes)
    wk = P.evaluate("pulse_core", {"op": "wake"})
    check("wake 收 process_execute", "process_execute" in wk.scopes, wk.scopes)

    print("[2] 四条判据各自的**硬证据**（不靠文档）")
    p = PC._pulse()
    check("脉冲：一次成包", bool(p.get("ok")), p.get("error"))
    check("脉冲：能力总数 > 300", (p.get("capabilities_total") or 0) > 300, p.get("capabilities_total"))

    q = PC._quant()
    check("量化：权重在位", bool(q.get("ok")), q.get("reason"))
    if q.get("ok"):
        check("量化：压缩比 ≥ 2×", (q.get("ratio") or 0) >= 2.0, q.get("ratio"))

    o = PC._ondemand()
    check("按需：闲置会睡（idle_sleep_s > 0）", (o.get("idle_sleep_s") or 0) > 0, o.get("idle_sleep_s"))
    check("按需：引擎可起（bin 在位）", bool(o.get("engine_bin")), "vendor 下没有 llama-server")

    d = PC._direct()
    rec = d.get("recall_at_k") or {}
    check("直达：候选池覆盖 351+127", (d.get("candidates") or 0) >= 470, d.get("candidates"))
    check("直达：召回读数 ≥ 99%", (rec.get("rate") or 0) >= 0.99,
          rec or "state/commander/recall-20.json 缺失（先跑 commander-coverage --recall-only）")

    print("[3] 总判据 verify()：任何一条不成立即红")
    v = PC.verify()
    check("verify 全绿", bool(v.get("ok")), v.get("failed"))

    print()
    if FAILED:
        print("FAILED %d: %s" % (len(FAILED), ", ".join(FAILED)))
        return 1
    print("ALL OK —— 四条都在，且都有读数")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
