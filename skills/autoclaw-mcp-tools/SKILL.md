---
name: autoclaw-mcp-tools
description: Use when users ask to access configured MCP services, external data providers, stocks, funds, macro data, news, files, databases, or mention mcporter/MCP tools.
---

# AutoClaw MCP Tools

当前工作区已配置 MCP 服务。优先通过 `mcporter --config C:\Users\ADMIN\Desktop\GBT小土豆V8\config\mcporter.json call` 调用这些服务；不要退回网页搜索，除非对应 MCP 服务不可用或用户明确要求网页搜索。

## 使用规则

- 先根据用户意图选择最匹配的 server.tool。
- 调用格式：`mcporter --config C:\Users\ADMIN\Desktop\GBT小土豆V8\config\mcporter.json call <server>.<tool> key=value`。
- 对只有 `query` 参数的工具，使用：`mcporter --config C:\Users\ADMIN\Desktop\GBT小土豆V8\config\mcporter.json call <server>.<tool> query="..."`。
- 汇总答案时说明数据来自对应 MCP 服务。

## 可用工具

当前没有可用 MCP 工具。
