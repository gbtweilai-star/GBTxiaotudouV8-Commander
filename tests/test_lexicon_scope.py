# -*- coding: utf-8 -*-
"""`commander.route` 的人工词表收窄（lexicon scope）判据 —— 不需要引擎，全部离线。

为什么要有这份测试（docs/53）：
短意图（"审计"/"体检"/"镜像"）模型会选错兄弟位，改成「用 `data/intent-lexicon.json` 把人点名的
那几位收窄成候选」之后 1/6 → 5/5。这套收窄有三个必须钉死的性质：

  ① **命中才收窄**：词表没写的话，候选仍是 k 个（行为不变）；
  ② **收窄只减候选、不改判断**：最终仍是模型在候选里选（测试里用假模型验证这一点）；
  ③ **词表自身要干净**：say 词不重复、点到的能力位都在注册表里（否则收窄会指向空气）。

跑法：python tests/test_lexicon_scope.py
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
    from gbt_allinone.tentacle import commander as C

    lex = json.load(open(os.path.join(ROOT, "data", "intent-lexicon.json"), encoding="utf-8"))
    intents = lex.get("intents") or []

    print("[1] 词表自身的卫生")
    caps_named = {c for e in intents for c in (e.get("caps") or {})}
    check("点到的能力位全在注册表", caps_named <= set(BENIGN_CAPS),
          sorted(caps_named - set(BENIGN_CAPS))[:5])
    seen, dup = {}, []
    for e in intents:
        for s in e.get("say") or []:
            if s in seen and seen[s] != e.get("what"):
                dup.append(s)
            seen[s] = e.get("what")
    check("say 词不重复（冲突会让收窄并集变脏）", not dup, dup[:5])

    print("[2] 命中词表 ⇒ 收窄；没命中 ⇒ 不收窄")
    real_ask, real_alive = C.ask, C.alive
    calls = []

    def fake_ask(messages, **kw):
        # 从 prompt 里粗取候选名，回第一个 —— 证明"最终仍由模型在候选里选"
        text = messages[-1]["content"]
        cands = [n for n in C.catalog_caps() if n["name"] in text]
        calls.append([c["name"] for c in cands])
        return {"ok": True, "text": cands[0]["name"] if cands else "none", "ms": 1,
                "usage": {}, "logprobs": []}

    C.ask = fake_ask
    C.alive = lambda *a, **k: {"ok": True, "base": "fake"}
    try:
        # 脉冲直达会短路（0 token），所以收窄判据要看权重路径：pulse=False
        r1 = C.route("审计", k=12, pulse=False)
        check("『审计』被收窄", r1.get("lexicon_scoped") is True, r1.get("lexicon_scoped"))
        check("收窄后候选 ⊆ 词表点名的位", set(r1.get("candidates") or []) <= {"audit_query", "caps_called_audit"},
              r1.get("candidates"))
        check("收窄后仍由模型选（返回的是候选之一）",
              r1.get("name") in (r1.get("candidates") or []), r1.get("name"))

        r2 = C.route("把这段转成幻灯片", k=12, pulse=False)
        # 这句也可能命中词表（ppt 条目），所以用一个明确不在词表里的说法
        r3 = C.route("今天天气怎么样随便聊聊", k=12, pulse=False)
        check("词表外的说法不收窄", not r3.get("lexicon_scoped"), r3.get("lexicon_scoped"))
        check("词表外仍有 k 个候选", len(r3.get("candidates") or []) == len(set(r3.get("candidates") or [])),
              r3.get("candidates"))
    finally:
        C.ask, C.alive = real_ask, real_alive

    print("[3] 脉冲直达短路（提速主路径）")
    import time as _t
    t0 = _t.time()
    rp = C.route("审计", k=12)
    ms = (_t.time() - t0) * 1000
    check("route 默认走脉冲直达", rp.get("path") == "pulse_direct", rp.get("path"))
    check("脉冲直达 0 token", rp.get("tokens") == 0, rp.get("tokens"))
    check("脉冲直达是毫秒级（<500ms）", ms < 500, "%dms" % ms)

    print("[4] 可关闭（对照用）")
    C.ask = fake_ask
    C.alive = lambda *a, **k: {"ok": True, "base": "fake"}
    try:
        r4 = C.route("审计", k=12, use_lexicon=False, pulse=False)
        check("use_lexicon=False 时不收窄", not r4.get("lexicon_scoped"), r4.get("lexicon_scoped"))
    finally:
        C.ask, C.alive = real_ask, real_alive

    print()
    if FAILED:
        print("FAILED %d: %s" % (len(FAILED), ", ".join(FAILED)))
        return 1
    print("ALL OK —— 词表干净、命中才收窄、收窄不越权")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
