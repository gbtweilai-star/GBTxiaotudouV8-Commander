# -*- coding: utf-8 -*-
"""MCP 注册表闭环判据：登记 → 体检 → 列表 → 连上列工具 → 调工具 → 注销。

跑法：python tests/test_mcp_registry_loop.py
"""
from __future__ import annotations

import json
import os
import pathlib
import sys

ROOT = pathlib.Path(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, str(ROOT))

FAILED = []


def check(name, cond, detail=""):
    print(("  ok   " if cond else "  FAIL ") + name + ("" if cond else "  " + str(detail)[:200]))
    if not cond:
        FAILED.append(name)


def main() -> int:
    import gbt_allinone as gbt
    from gbt_allinone.security import policy
    from gbt_allinone.tentacle import mcp_bridge as MB

    demo = ROOT / "tools" / "mcp-demo-server.py"
    cfg = ROOT / "state" / "tmp" / "mcp-loop-test.json"
    cfg.parent.mkdir(parents=True, exist_ok=True)
    cfg.write_text(json.dumps({"mcpServers": {"gbt-demo": {
        "command": sys.executable,
        "args": [str(demo)],
        "cwd": str(ROOT),
        "description": "闭环用最小 MCP 服务器",
    }}}, ensure_ascii=False), encoding="utf-8")

    # 只登记/体检会写盘/起进程 ⇒ 走主人可信会话（CLI/GUI 的真实形态）
    with policy.owner_session():
        print("[1] 登记（mcp_register）")
        r = gbt.run_task("mcp_register", {"path": str(cfg)}, probe=True)["gbt_result"]["result"]
        check("登记成功", r.get("ok") is True and "gbt-demo" in (r.get("registered") or []), r)

        print("[2] 列表（mcp_servers）")
        ls = gbt.run_task("mcp_servers", {}, probe=True)["gbt_result"]["result"]
        names = [x["name"] for x in ls.get("servers") or []]
        check("能看到 gbt-demo", "gbt-demo" in names, names)

        print("[3] 体检（mcp_health）：真连真起子进程")
        h = gbt.run_task("mcp_health", {"timeout": 20}, probe=True)["gbt_result"]["result"]
        row = next((x for x in h.get("servers") or [] if x["server"] == "gbt-demo"), None)
        check("体检有这一台", row is not None, h)
        check("up=True", bool(row and row.get("up")), row)
        check("工具数=2", (row or {}).get("tools") == 2, row)

        print("[4] 按登记连上 + 列工具（connect_registered）")
        c = MB.connect_registered("gbt-demo")
        check("连上", c.get("ok") is True, c.get("error"))
        tools = [t["name"] for t in c.get("tools") or []]
        check("有 echo/add", tools == ["echo", "add"] or set(tools) >= {"echo", "add"}, tools)

        print("[5] 调工具（mcp_call）")
        call = gbt.run_task("mcp_call", {"server": "gbt-demo", "tool": "echo",
                                         "arguments": {"text": "闭环OK"}}, probe=True)["gbt_result"]["result"]
        check("调用 ok", call.get("ok") is True, call)
        check("回显正确", call.get("text") == "闭环OK", call.get("text"))

        print("[6] 注销（mcp_unregister）")
        u = gbt.run_task("mcp_unregister", {"server": "gbt-demo"}, probe=True)["gbt_result"]["result"]
        check("注销成功", u.get("ok") is True, u)
        ls2 = gbt.run_task("mcp_servers", {}, probe=True)["gbt_result"]["result"]
        check("列表里没了", "gbt-demo" not in [x["name"] for x in ls2.get("servers") or []], ls2)

    MB._stop("gbt-demo")
    try:
        cfg.unlink()
    except OSError:
        pass

    print()
    if FAILED:
        print("FAILED %d: %s" % (len(FAILED), ", ".join(FAILED)))
        return 1
    print("ALL OK —— MCP 注册表闭环：登记→列表→体检→连上→调工具→注销")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
