# -*- coding: utf-8 -*-
"""技能库判据：方法论 skill 能被列出、取到、匹配到，且不重名。

跑法：python tests/test_skills_hub.py
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
    from gbt_allinone.tentacle import skills_hub as SH

    print("[1] list：至少 20 个，且名字唯一")
    r = SH.run("list")
    check("count >= 20", (r.get("count") or 0) >= 20, r.get("count"))
    names = [s["name"] for s in r.get("skills") or []]
    check("名字唯一", len(names) == len(set(names)), names[:5])
    check("含 superpowers 吸收件", "test-driven-development" in names and "brainstorming" in names, names[:3])

    print("[2] get：能取全文")
    g = SH.run("get", name="test-driven-development")
    check("取到", g.get("ok") is True, g.get("error"))
    check("正文非空", len(g.get("text") or "") > 500, len(g.get("text") or ""))

    print("[3] match：写测试 → TDD 排第一")
    m = SH.run("match", query="我要改代码 先写测试 再实现", top=3)
    hit = [x["name"] for x in (m.get("matches") or [])]
    check("命中 TDD", hit and hit[0] == "test-driven-development", hit)

    print("[4] verify：无重名")
    v = SH.run("verify")
    check("verdict clean", v.get("verdict") == "clean", v)

    print()
    if FAILED:
        print("FAILED %d: %s" % (len(FAILED), ", ".join(FAILED)))
        return 1
    print("ALL OK —— 技能库可列/可取/可匹配/无重名")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
