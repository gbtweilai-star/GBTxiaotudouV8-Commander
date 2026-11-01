# -*- coding: utf-8 -*-
"""`omni_open` 增量对比的判据：**墙上的洞变了必须立刻知道**。

主人 2026-11-01 之后的下一步：插口是扫出来的，那它变了（新插上/拔掉/通断翻转）
也必须像 `ghost_guard` 那样当场报警，而不是等下一个人发现。

这些用例全部离线（纯函数 `_diff`），不依赖真扫 25 秒。
跑法：python tests/test_omni_open_diff.py
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


def P(kind, target, ok=True):
    return {"kind": kind, "target": target, "ok": ok}


def main() -> int:
    from gbt_allinone.tentacle import omni_open as OO

    print("[1] 第一次扫描：不算漂移")
    d = OO._diff({}, [P("port", "127.0.0.1:80")])
    check("first_scan=True", d.get("first_scan") is True, d)
    check("不报警", not d.get("alert"), d)

    print("[2] 新增 / 拔掉 / 通断翻转")
    old = {"plugs": [P("port", "127.0.0.1:80"), P("ai", "http://127.0.0.1:8792", True),
                     P("file", "C:/a.db", True)]}
    new = [P("port", "127.0.0.1:80"), P("ai", "http://127.0.0.1:8792", False),
           P("process", "node")]
    d = OO._diff(old, new)
    check("拔掉 file 被认出", [x["target"] for x in d["removed"]] == ["C:/a.db"], d["removed"])
    check("新增 process 被认出", [x["target"] for x in d["added"]] == ["node"], d["added"])
    check("通断翻转被认出（ai true→false）", len(d["flipped"]) == 1 and d["flipped"][0]["now"] is False,
          d["flipped"])
    check("拔掉 ⇒ 报警", d.get("alert") is True, d.get("alert"))

    print("[3] 只新增不算警报（多了是好事，先记着）")
    d = OO._diff({"plugs": [P("port", "a")]}, [P("port", "a"), P("port", "b")])
    check("added=1 / removed=0", d["counts"] == {"added": 1, "removed": 0, "flipped": 0}, d["counts"])
    check("无拔掉/翻转 ⇒ 不 alert", d.get("alert") is False, d.get("alert"))

    print("[4] 键是 (kind,target)：同名不同类不算同一个洞")
    d = OO._diff({"plugs": [P("file", "x")]}, [P("port", "x")])
    check("file->port 视为拔掉+新增", d["counts"]["removed"] == 1 and d["counts"]["added"] == 1, d["counts"])

    print("[5] 走门：diff / history 两个 op 可用")
    import gbt_allinone as g
    r = g.run_task("omni_open", {"op": "diff"}, probe=True)["gbt_result"]["result"]
    check("diff op 返回结构", "diff" in r and "alert" in r, list(r))
    h = g.run_task("omni_open", {"op": "history"}, probe=True)["gbt_result"]["result"]
    check("history op 返回列表", isinstance(h.get("history"), list), type(h.get("history")))

    print()
    if FAILED:
        print("FAILED %d: %s" % (len(FAILED), ", ".join(FAILED)))
        return 1
    print("ALL OK —— 插口变了会进 diff，拔掉/翻转会 alert")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
