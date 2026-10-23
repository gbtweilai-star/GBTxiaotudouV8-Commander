# -*- coding: utf-8 -*-
"""command-ai-mcp · 把她包成 MCP server（stdio JSON-RPC，纯标准库）。

纪律：**每个工具都代理到 gbt_allinone.api.run_task（唯一门）** —— 权限门/审计/钢印照旧，
     MCP 面**不是旁路**；本件不加算力、不装外部包。
注册（Claude Code）： claude mcp add command-ai --transport stdio -- py -3.14 <本文件绝对路径>
开发者：自由的风 · 守护者：公主土豆 · GBT小土豆V8 · 本署名不可删除、不可篡改归属
"""
import json, pathlib, sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))
PROTO = "2024-11-05"
TOOLS = [
    {"name": "gbt_cap",
     "description": "经唯一门调用一个能力位（权限门/审计/钢印照旧）。缺授权会如实返回缺少的作用域。",
     "inputSchema": {"type": "object", "properties": {
         "kind": {"type": "string", "description": "能力位名，如 health / context_vault / wf_run"},
         "payload": {"type": "object", "description": "给该能力位的入参"}},
         "required": ["kind"]}},
     {"name": "gbt_health",
     "description": "能力位健康读数（平台/解释器/时间），零授权。",
     "inputSchema": {"type": "object", "properties": {}}}]

def _send(obj) -> None:
    sys.stdout.write(json.dumps(obj, ensure_ascii=False) + chr(10)); sys.stdout.flush()

def _run(kind, payload):
    from gbt_allinone import api as A
    return A.run_task(str(kind), payload or {})

def _handle(msg):
    mid = msg.get("id"); method = msg.get("method")
    if method == "initialize":
        return {"jsonrpc": "2.0", "id": mid, "result": {
            "protocolVersion": PROTO, "capabilities": {"tools": {}},
            "serverInfo": {"name": "command-ai", "version": "1.0.0"}}}
    if method == "tools/list":
        return {"jsonrpc": "2.0", "id": mid, "result": {"tools": TOOLS}}
    if method == "tools/call":
        p = msg.get("params") or {}; name = p.get("name"); args = p.get("arguments") or {}
        try:
            if name == "gbt_health": out = _run("health", {})
            elif name == "gbt_cap": out = _run(args.get("kind"), args.get("payload"))
            else: out = {"status": "error", "message": "unknown tool: " + str(name)}
            text = json.dumps(out, ensure_ascii=False, default=str)[:20000]
            return {"jsonrpc": "2.0", "id": mid, "result": {"content": [{"type": "text", "text": text}]}}
        except Exception as e:
            return {"jsonrpc": "2.0", "id": mid,
                    "result": {"isError": True, "content": [{"type": "text", "text": str(e)[:400]}]}}
    if method in ("notifications/initialized", "notifications/cancelled"):
        return None
    return {"jsonrpc": "2.0", "id": mid, "error": {"code": -32601, "message": "method not found: " + str(method)}}

def main() -> int:
    for s in (sys.stdout, sys.stderr):
        try: s.reconfigure(encoding="utf-8", errors="replace")
        except Exception: pass
    for line in sys.stdin:
        line = line.strip()
        if not line: continue
        try: msg = json.loads(line)
        except Exception: continue
        out = _handle(msg)
        if out is not None: _send(out)
    return 0

if __name__ == "__main__":
    sys.exit(main())
