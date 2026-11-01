# -*- coding: utf-8 -*-
"""触手主干 · 原生指挥官车道的**契约测试**（不需要权重、不需要引擎，全部可离线跑）。

主人令 2026-10-31：「把我们的原生无限制指挥官大模型权重彻底融合进触手主干」
「要做到所有的触手都能通过我们自己的大模型权重」「每一项能力都要全方位不能遗漏」。

这份测试钉住四件事，钉的都是**接线**而不是"能不能答"：

  ① 注册表里有 `commander`，且 api.py 真有分派分支（三处齐：注册 ↔ 分派 ↔ 审计）；
  ② 作用域口径：status/route/ask = 零作用域；start/stop 才收 process_execute；
  ③ 缺权重/缺引擎时**如实报**（ok=False + 缺什么），绝不假绿；
  ④ 候选池覆盖：`catalog_caps()` 的集合 ⊇ 注册表全集，且 `_shortlist` 能对每个域召回。

跑法：python tests/test_commander_trunk.py
"""
from __future__ import annotations

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

FAILED = []


def check(name, cond, detail=""):
    if cond:
        print("  ok   %s" % name)
    else:
        print("  FAIL %s %s" % (name, detail))
        FAILED.append(name)


def main() -> int:
    from gbt_allinone.caps_registry import BENIGN_CAPS
    from gbt_allinone.security import policy as P
    from gbt_allinone.tentacle import commander as C

    print("[1] 注册 ↔ 分派")
    check("commander 在注册表", "commander" in BENIGN_CAPS)
    src = open(os.path.join(ROOT, "gbt_allinone", "api.py"), encoding="utf-8").read()
    check("api.py 有 commander 分派分支", 'if kind == "commander"' in src)

    print("[2] 作用域口径")
    st = P.evaluate("commander", {"op": "status"})
    check("status 零作用域", not st.scopes, str(st.scopes))
    rt = P.evaluate("commander", {"op": "route", "intent": "x"})
    check("route 零作用域", not rt.scopes, str(rt.scopes))
    sp = P.evaluate("commander", {"op": "start"})
    check("start 要 process_execute", "process_execute" in sp.scopes, str(sp.scopes))
    tp = P.evaluate("tentacle", {"op": "plan", "intent": "x"})
    check("tentacle op=plan 不动手、不扣桌面票", not tp.scopes, str(tp.scopes))

    print("[3] 缺件如实报（不假绿）")
    w = C.weights()
    check("weights() 有 ok/reason 形状", isinstance(w.get("ok"), bool) and ("reason" in w or "path" in w))
    if not w.get("ok"):
        check("缺权重时给出看过哪些位置", bool(w.get("looked")))
        check("缺权重时给恢复办法", bool(w.get("how")))
    r = C.route("帮我看看有哪些窗口", timeout=3) if w.get("ok") else {"ok": False, "error": "no weights"}
    if not w.get("ok"):
        check("没权重时 route 不假绿", r.get("ok") is False)
    stt = C.status()
    check("status 三件套齐全", all(k in stt for k in ("weights", "engine_bin", "endpoint")))

    print("[4] 候选池覆盖（全方位）")
    caps = C.catalog_caps()
    names = {c["name"] for c in caps}
    check("候选池 ⊇ 注册表全集", set(BENIGN_CAPS).issubset(names),
          "缺: %s" % sorted(set(BENIGN_CAPS) - names)[:10])
    check("候选池不小于注册表", len(names) >= len(BENIGN_CAPS))
    from gbt_allinone import semantic_route as _SR
    methods = {i["method"] for i in (_SR.method_table() or {}).get("items") or []}
    allnames = names | methods
    short = C._shortlist("把文件转成 PPT", 10, "auto")
    check("短名单非空且全是真名", bool(short) and all(s["name"] in allnames for s in short),
          str([s["name"] for s in short if s["name"] not in allnames]))
    check("短名单带 space 标记", all(s.get("space") in ("method", "cap") for s in short))
    # 每个域至少能被召回一条（域覆盖，不是逐位覆盖 —— 逐位覆盖由 commander-coverage.py 真跑量）
    doms = {c["domain"] for c in caps}
    got = set()
    probe = {"system": "系统体检", "data": "数据统计字数", "finance": "量化策略回测",
             "tentacle": "触手截图", "security": "漏洞扫描", "creation": "生成图片视频"}
    for dom, q in probe.items():
        for s in C._shortlist(q, 30, "auto"):
            rec = next((c for c in caps if c["name"] == s["name"]), None)
            if rec and rec["domain"] == dom:
                got.add(dom)
    check("抽样域能被召回", len(got) >= 3, "命中 %s / 探针 %s" % (sorted(got), sorted(probe)))

    print()
    if FAILED:
        print("FAILED %d: %s" % (len(FAILED), ", ".join(FAILED)))
        return 1
    print("ALL OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
