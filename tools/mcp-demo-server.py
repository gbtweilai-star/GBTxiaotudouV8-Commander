"""最小 MCP stdio 服务器（闭环验证用）：initialize / tools/list / tools/call。

协议：一行一个 JSON-RPC 消息（与 mcp_bridge 一致）。
工具：echo(text) 原样回显；add(a,b) 求和。
"""
import json
import sys


def send(obj):
    sys.stdout.write(json.dumps(obj, ensure_ascii=False) + "\n")
    sys.stdout.flush()


TOOLS = [
    {"name": "echo", "description": "原样回显 text",
     "inputSchema": {"type": "object", "properties": {"text": {"type": "string"}},
                     "required": ["text"]}},
    {"name": "add", "description": "两数相加",
     "inputSchema": {"type": "object", "properties": {"a": {"type": "number"}, "b": {"type": "number"}},
                     "required": ["a", "b"]}},
]


def main() -> int:
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except Exception:
            continue
        method = msg.get("method")
        rid = msg.get("id")
        params = msg.get("params") or {}
        if method == "initialize":
            send({"jsonrpc": "2.0", "id": rid,
                  "result": {"protocolVersion": params.get("protocolVersion") or "2025-06-18",
                             "capabilities": {"tools": {}},
                             "serverInfo": {"name": "gbt-demo-mcp", "version": "1.0.0"}}})
        elif method == "notifications/initialized":
            continue
        elif method == "tools/list":
            send({"jsonrpc": "2.0", "id": rid, "result": {"tools": TOOLS}})
        elif method == "tools/call":
            name = params.get("name")
            args = params.get("arguments") or {}
            if name == "echo":
                text = str(args.get("text", ""))
            elif name == "add":
                try:
                    text = str(float(args.get("a", 0)) + float(args.get("b", 0)))
                except Exception:
                    send({"jsonrpc": "2.0", "id": rid,
                          "result": {"isError": True,
                                     "content": [{"type": "text", "text": "bad numbers"}]}})
                    continue
            else:
                send({"jsonrpc": "2.0", "id": rid,
                      "result": {"isError": True,
                                 "content": [{"type": "text", "text": "unknown tool: %s" % name}]}})
                continue
            send({"jsonrpc": "2.0", "id": rid,
                  "result": {"isError": False, "content": [{"type": "text", "text": text}]}})
        else:
            if rid is not None:
                send({"jsonrpc": "2.0", "id": rid,
                      "error": {"code": -32601, "message": "method not found: %s" % method}})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
