# -*- coding: utf-8 -*-
"""自主契约判据：架构给完后，除 danger/transfer，不许打扰主人。

三条必须有读数：
  ① 架构未给 ⇒ 允许提问（否则没法干活）
  ② 架构已给 ⇒ 只有 danger / transfer 放行，其余一律拒绝并记账
  ③ 模型输出里"回头问主人"的句子会被**改写**掉（不是删掉信息，是改成自主推进）

跑法：python tests/test_autonomy.py
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
    from gbt_allinone.tentacle import autonomy as AU

    st_file = os.path.join(ROOT, "state", "autonomy.json")
    backup = open(st_file, encoding="utf-8").read() if os.path.exists(st_file) else None

    print("[1] 架构未给：允许提问")
    if os.path.exists(st_file):
        os.remove(st_file)
    r = AU.check("other")
    check("未声明时 allow=True", r.get("allow") is True, r)

    print("[2] 架构已给：只有两个例外")
    AU.declare("判据测试")
    check("danger 放行", AU.check("danger").get("allow") is True)
    check("transfer 放行", AU.check("transfer").get("allow") is True)
    denied = AU.check("other")
    check("其他一律拒绝", denied.get("allow") is False, denied)
    check("拒绝有原因", "禁止打扰" in str(denied.get("reason")), denied.get("reason"))

    print("[3] guard 改写「回头问主人」的句子")
    g = AU.guard("需要你确认一下用哪个参数；要不要我继续？")
    check("被改写", g.get("rewritten") is True, g)
    check("改写后不再含问句", ("需要你确认" not in g.get("text", "")) and ("要不要我" not in g.get("text", "")),
          g.get("text"))
    check("改写保留了自主标记", "自主" in str(g.get("text")), g.get("text"))

    print("[4] 打扰必留痕")
    led = AU.ledger(limit=5)
    check("账本有条目", led.get("count", 0) >= 1, led.get("count"))

    if backup is not None:
        open(st_file, "w", encoding="utf-8").write(backup)

    print()
    if FAILED:
        print("FAILED %d: %s" % (len(FAILED), ", ".join(FAILED)))
        return 1
    print("ALL OK —— 架构给完后只放行 danger/transfer；问句被改写；打扰留痕")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
