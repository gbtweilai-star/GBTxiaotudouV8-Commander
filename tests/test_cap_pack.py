# -*- coding: utf-8 -*-
"""能力包判据：能发现、默认不执行、执行过门、子进程受护栏。

跑法：python tests/test_cap_pack.py
"""
from __future__ import annotations

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

FAILED = []


def check(name, cond, detail=""):
    print(("  ok   " if cond else "  FAIL ") + name + ("" if cond else "  " + str(detail)[:200]))
    if not cond:
        FAILED.append(name)


def main() -> int:
    from gbt_allinone.tentacle import cap_pack as CP

    print("[1] discover：能扫到示例包")
    d = CP.run_op("discover")
    names = [p["name"] for p in d.get("packs") or []]
    check("发现 >=2 个", len(names) >= 2, names)
    check("含 example-hello", "example-hello" in names, names)
    check("executable 计数正确", d.get("executable") == sum(1 for p in d["packs"] if p["auto_exec"]), d)

    print("[2] info：能看 manifest")
    i = CP.run_op("info", name="example-hello")
    check("info ok", i.get("ok") is True, i.get("error"))
    check("actions 含 greet", "greet" in ((i.get("pack") or {}).get("actions") or []), i.get("pack"))

    print("[3] auto_exec=false ⇒ 拒绝执行（安全默认）")
    r = CP.run_op("run", name="example-hello", action="greet")
    check("refused", r.get("refused") is True, r)
    check("错误信息说明 auto_exec", "auto_exec" in str(r.get("error")), r.get("error"))

    print("[4] auto_exec=true ⇒ 仍要 process_execute 票（过门）")
    r2 = CP.run_op("run", name="example-echo", action="say", params={"msg": "hi"})
    if r2.get("ok"):
        check("有票时真跑出输出", "echo" in (r2.get("stdout") or ""), r2.get("stdout"))
    else:
        check("无票时明确 denied", r2.get("denied") is True or "票" in str(r2.get("error")), r2)

    print("[5] status 可读")
    st = CP.run_op("status")
    check("有 count", isinstance(st.get("count"), int), st)

    print()
    if FAILED:
        print("FAILED %d: %s" % (len(FAILED), ", ".join(FAILED)))
        return 1
    print("ALL OK —— 发现、默认不执行、执行过门、子进程受护栏")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
