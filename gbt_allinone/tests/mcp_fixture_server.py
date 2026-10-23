# -*- coding: utf-8 -*-
"""最小 MCP stdio 服务器 —— `test_mcp_connect_then.py` 的**常驻测试夹具**。

只为证一件事：「同进程 connect -> tools -> call」这条链真通（2026-10-14 修「卡点二」的证据件）。
命令行跑它没有意义，它是一台只回 JSON-RPC 的标准输入服务器。stdout 只许出现 JSON-RPC 行（桥按行解析）。
"""
import json
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

TOOLS = [
    {"name": "ping", "description": "回一个 pong 加你给的话",
     "inputSchema": {"type": "object", "properties": {"say": {"type": "string"}}}},
    {"name": "boom", "description": "故意报错的工具（验「工具错误不许被吞成 ok:true」）",
     "inputSchema": {"type": "object", "properties": {}}},
]


def _send(obj):
    sys.stdout.write(json.dumps(obj, ensure_ascii=False) + "\n")
    sys.stdout.flush()


for _line in sys.stdin:
    _line = _line.strip()
    if not _line:
        continue
    try:
        _msg = json.loads(_line)
    except Exception:
        continue
    _method = _msg.get("method")
    _rid = _msg.get("id")
    if _rid is None:
        continue
    if _method == "initialize":
        _send({"jsonrpc": "2.0", "id": _rid,
               "result": {"protocolVersion": "2024-11-05",
                          "capabilities": {"tools": {}},
                          "serverInfo": {"name": "gbt-fixture", "version": "0.0.1"}}})
    elif _method == "tools/list":
        _send({"jsonrpc": "2.0", "id": _rid, "result": {"tools": TOOLS}})
    elif _method == "tools/call":
        _args = (_msg.get("params") or {}).get("arguments") or {}
        if (_msg.get("params") or {}).get("name") == "boom":
            _send({"jsonrpc": "2.0", "id": _rid,
                   "result": {"content": [{"type": "text", "text": "Error: fixture boom"}],
                              "isError": True}})
        else:
            _send({"jsonrpc": "2.0", "id": _rid,
                   "result": {"content": [{"type": "text", "text": "pong:" + str(_args.get("say", ""))}],
                              "isError": False}})
    else:
        _send({"jsonrpc": "2.0", "id": _rid,
               "error": {"code": -32601, "message": "method not found: %s" % _method}})
