# -*- coding: utf-8 -*-
"""子进程护栏判据：超时杀树 / 输出封顶 / 环境净化。

跑法：python tests/test_proc_guard.py
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
    from gbt_allinone.tentacle.proc_guard import run_capped, _scrub_env

    py = sys.executable

    print("[1] 正常子进程")
    r = run_capped([py, "-c", "print('hello')"], timeout=20)
    check("returncode 0", r.get("returncode") == 0, r)
    check("stdout 有内容", "hello" in (r.get("stdout") or ""), r.get("stdout"))

    print("[2] 超时 → 杀整棵树")
    r2 = run_capped([py, "-c", "import time; time.sleep(10)"], timeout=1.0)
    check("timed_out", r2.get("timed_out") is True, r2.get("error"))
    check("记录击杀方式", bool((r2.get("killed") or {}).get("how")), r2.get("killed"))

    print("[3] 输出封顶")
    r3 = run_capped([py, "-c", "print('x'*5000)"], timeout=20, max_chars=1000)
    check("truncated", r3.get("truncated") is True, r3)
    check("输出长度受控", len(r3.get("stdout") or "") <= 1000, len(r3.get("stdout") or ""))

    print("[4] 环境净化")
    env = {"PATH": os.environ.get("PATH", ""), "GITHUB_TOKEN": "ghp_xxx", "MY_API_KEY": "k"}
    s = _scrub_env(env)
    check("去掉 token", "GITHUB_TOKEN" not in s, list(s))
    check("去掉 *_API_KEY", "MY_API_KEY" not in s, list(s))
    check("保留 PATH", "PATH" in s, list(s))

    print()
    if FAILED:
        print("FAILED %d: %s" % (len(FAILED), ", ".join(FAILED)))
        return 1
    print("ALL OK —— 超时杀树、输出封顶、环境净化")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
