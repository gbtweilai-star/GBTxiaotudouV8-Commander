# -*- coding: utf-8 -*-
"""`code_graph` 的判据：这个能力位曾经**注册了、分派了、模块却不存在**。

背景（2026-10-31 逐项核对抓到）：`run_task("code_graph", …)` 直接
`cannot import name 'code_graph' from 'gbt_allinone.tools'`。
2026-11-01 补上实现后，这份测试钉四件事：

  ① 建索引真的建得起来（ast 精确解析，exact=1）；
  ② 查得到符号、追得到调用方（file:line 要可指回）；
  ③ **BOM 容忍**：带 UTF-8 BOM 的 .py 也要能解析（实测踩过，BOM 会让 ast 直接 SyntaxError）；
  ④ 走唯一门可用（`run_task("code_graph", …)` 不报 ImportError）。

跑法：python tests/test_code_graph.py
"""
from __future__ import annotations

import os
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

FAILED = []


def check(name, cond, detail=""):
    print(("  ok   " if cond else "  FAIL ") + name + ("" if cond else "  " + str(detail)))
    if not cond:
        FAILED.append(name)


def main() -> int:
    from gbt_allinone.tools import code_graph as CG

    print("[1] 建索引（只跑一小片，秒级）")
    r = CG.index(["gbt_allinone/tentacle"], limit=15)
    check("index ok", bool(r.get("ok")), r)
    check("符号 > 0", (r.get("全库") or {}).get("symbols", 0) > 0, r.get("全库"))
    check("0 个解析失败", r.get("未解析数") == 0, r.get("未解析")[:3])

    print("[2] 查询与调用链")
    f = CG.find("route", limit=5)
    check("find 有命中", f.get("count", 0) > 0, f)
    check("命中带 file:line", all(h.get("file") and h.get("line") for h in f.get("hits") or []), f.get("hits"))
    c = CG.callers("invoke", limit=5)
    check("callers 返回结构", isinstance(c.get("callers"), list), c)
    d = CG.callees("run", limit=5)
    check("callees 返回结构", isinstance(d.get("callees"), list), d)
    s = CG.summary("gbt_allinone/tentacle")
    check("summary 有读数", s.get("files", 0) > 0 and s.get("symbols", 0) > 0, s)

    print("[3] BOM 容忍（实测踩过的坑）")
    tmp = os.path.join(ROOT, "state", "_cg_bom_probe.py")
    os.makedirs(os.path.dirname(tmp), exist_ok=True)
    with open(tmp, "wb") as fh:
        fh.write(b"\xef\xbb\xbf")                     # BOM
        fh.write("def bom_probe_fn():\n    return 1\n".encode("utf-8"))
    try:
        rr = CG.index([tmp], force=True)
        check("带 BOM 的文件解析成功", rr.get("未解析数") == 0, rr.get("未解析"))
        check("BOM 文件里的函数进库", CG.find("bom_probe_fn").get("count", 0) > 0, None)
    finally:
        try:
            os.remove(tmp)
        except OSError:
            pass

    print("[4] 走唯一门（不报 ImportError 就是修好了）")
    import gbt_allinone as g
    gate = g.run_task("code_graph", {"op": "stats"}, probe=True)
    res = gate.get("gbt_result", {}).get("result", {})
    check("run_task('code_graph') 可用", bool(res.get("ok")), gate.get("status"))

    print()
    if FAILED:
        print("FAILED %d: %s" % (len(FAILED), ", ".join(FAILED)))
        return 1
    print("ALL OK —— 代码图谱真的建得起来、追得到调用方、BOM 也不怕")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
