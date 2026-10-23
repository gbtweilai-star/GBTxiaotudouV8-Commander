---
name: gbt-hands-on-aa
description: boyu-ai/Hands-on-AA 课程语料（一字不差逐字节落地件）+ 章节到能力位的路由表。当用户说「Hands-on-AA / 那个课程 / part_1~4 / 智能体课程内容 / 现读课程原文」时使用。
---

# gbt-hands-on-aa · 课程语料（逐字节落地 · 只索引不转述 · 有路由表）

**出处**：https://github.com/boyu-ai/Hands-on-AA （课程站 https://haa.boyuai.com）
**锚点**：commit f337dd7bbc66 · **82 个文件 · 26,391,538 字节**（与远端 blob 总量**精确相等**）

## 语料与索引

- 语料根：vendor/hands-on-aa/（part_1 ~ part_4，**15 本 notebook**）
- 索引：vendor/hands-on-aa.index.md · manifest：vendor/hands-on-aa.manifest.json（82 条 sha256）
- 路由表：state/hands-on-aa-bindings.json（**15/15 已绑 · 位名全部以 gbt_allinone list 现读校验**）

## 路由表（知识 → 位 → 怎么用）★ 要操控触手就看这里

| 章 | 主题 | 落到她的位 | 用法 |
|---|---|---|---|
| ch1 | 初探智能体 | stigmergy | 留痕/读场地，多步协作的第一步 |
| ch2 | 生成式大语言模型 | llm_status · brain_route | 先判模型可用性再派推理 |
| ch3 | 提示工程 | context_vault · brain_route | 先查 vault 取片段再拼提示 |
| ch4 | 评估与调试 | truth_scan · lr_submit · lr_tick | 任务带判据、可复跑 |
| ch5 | 智能体架构概览 | context_vault · orchestration_kernel | 记忆/工具/规划三件套 |
| ch6 | 记忆管理与检索增强 | context_vault · devour_scan | 检索增强，只引用不复制 |
| ch7 | 外部工具调用 | omni_plug · cli_chat | **工具调用就掉 omni_plug 插座** |
| ch8 | 推理·规划·树搜索 | brain_route · think_loop | 复杂任务先规划再执行 |
| ch9 | 指令微调 | devour_reflect · dream_replay | 把经验沉淀成规程 |
| ch10 | LoRA微调与量化 | devour_reflect · energy_pool | 算力账先看清楚 |
| ch11 | 强化微调 | devour_reflect · brain_route | 反馈回路 |
| ch12 | 多模态智能体 | vision · voice | 看图/出声两条路（麦克风现读不可用） |
| ch13 | 多智能体系统 | wf_define · wf_run · stigmergy | DAG 派活 + 分层并行 |
| ch14 | 智能体攻防 | sec_surface · sec_defenses · sec_llm | **攻防只做防御验证，且要终端 YES** |
| ch15 | 智能体协议(MCP/A2A) | omni_plug · collab_gateway · stigmergy | 协议面走插座与协作通道 |

## 三条铁律

1. **不许转述当原文**：回答课程内容时**现读** vendor/hands-on-aa/... 并给路径与行；转述会失真。
2. **不许把整篇塞进提示**：按 context-slim 只带片段（先查 context_vault，带出处）。
3. **语料只读**：改一个字节判据就红（C5）。

## 判据

    py -3.14 tools/codex-scripts/hands-on-aa-check.py --check      # 逐字节 82/82
    py -3.14 tools/codex-scripts/hands-on-aa-check.py --selftest   # 4/4

## 已知踩坑（留痕）

- **CRLF 陷阱**：core.autocrlf=true 会把文本检出成 CRLF（差 39,664 字节）；改 false + 强制重检后字节精确相等。
- **中文名路径假象**：PowerShell 给带中文的路径加引号传给 git 会「找不到文件」，那是工具假象。
- **编位名的教训**：曾把 cli_agent_hub 写进绑定表 —— 注册表里**只有 cli_chat**（caps_registry.py:1936），
  该名字是从技能描述文字抄来的。**位名一律以 gbt_allinone list 现读校验**，不许凭记忆写。

## 边界与回滚

- 课程语料版权归上游；她只**本地现读**，不外发、不商用再分发。
- 回滚：删 vendor/hands-on-aa/ + manifest + 索引 + 绑定表 + 本目录。

> 开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属
