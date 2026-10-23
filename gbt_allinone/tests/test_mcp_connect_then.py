# -*- coding: utf-8 -*-
"""`mcp_connect` 的 `then` 口（2026-10-14 修「卡点二」）—— 正例 + 负对照。

缘由：`mcp_bridge._SESSIONS` 是**模块级**会话表 ⇒ 会话随**进程**生灭；
每次 `cap` 都是新进程 ⇒ 「连上」与「列契约 / 调工具」跨不了进程。
本测用一台**最小夹具 MCP 服务器**（`mcp_fixture_server.py`）证明：同一进程内 connect → tools / call 真通。

无 `process_execute` 票时**跳过**（不把"没票"伪装成"代码坏了"）。
"""
import sys
from pathlib import Path

import pytest

from gbt_allinone import api

FIXTURE = str(Path(__file__).resolve().parent / "mcp_fixture_server.py")


def _dig(obj):
    """读穿信封：取**最里层**带 `ok` 的那个 dict。

    🔴 为什么必须读穿：门对「能力位内部再调一次门」这种嵌套调用返回**两层信封**
    （`{status,kind,result:{status,kind,result:{ok:…}}}`）。本测第一版就只读了一层
    ⇒ `res.get("ok")` 恒 `None` ⇒ 断言假红。**同一个坑，别踩第二次。**
    """
    node, found = obj, None
    while isinstance(node, dict):
        if "ok" in node:
            found = node
        nxt = node.get("result")
        if not isinstance(nxt, dict):
            break
        node = nxt
    return found or {}


def _run(**payload):
    r = api.run_task("mcp_connect", payload)
    flat = _dig(r)
    if (isinstance(r, dict) and r.get("denied")) or flat.get("denied"):
        pytest.skip("需要 process_execute 票（本进程无票）")
    return flat


def test_connect_then_tools():
    res = _run(server="pytest-fix-tools", command=[sys.executable, FIXTURE], then="tools")
    assert res.get("ok") is True, res
    assert "ping" in [t.get("name") for t in (res.get("tools") or [])]


def test_connect_then_call():
    res = _run(server="pytest-fix-call", command=[sys.executable, FIXTURE],
               then="call", tool="ping", arguments={"say": "hi"})
    assert (res.get("call") or {}).get("text") == "pong:hi", res


def test_bogus_then_is_reported():
    res = _run(server="pytest-fix-bogus", command=[sys.executable, FIXTURE], then="bogus")
    assert res.get("ok") is False
    assert "不认的 then" in str(res.get("then_error"))


def test_tool_error_is_not_swallowed():
    """工具自己报错时，`ok` 必须是 False 且 `then_error` 带原文。

    🔴 由来（2026-10-14 实测）：MCP 层会把工具的业务错误报成 `ok:true` + `raw.isError:false`
    ——那发 `get_balance` 打到 HackerOne 回 401，而 `call.ok` 仍是 `true`、真值只在 `text` 里。
    这条用例就是钉死「**信封绿不许盖住本体红**」。
    """
    res = _run(server="pytest-fix-boom", command=[sys.executable, FIXTURE],
               then="call", tool="boom", arguments={})
    assert res.get("ok") is False, res
    assert "fixture boom" in str(res.get("then_error"))


def test_mcp_tools_still_refuses_without_session():
    """负对照：**零作用域**的 `mcp_tools` 不许因为这次改动就能起进程。"""
    res = _dig(api.run_task("mcp_tools", {"server": "never-connected-xyz"}))
    assert res.get("ok") is False, res
    assert "未连接" in str(res.get("error"))
