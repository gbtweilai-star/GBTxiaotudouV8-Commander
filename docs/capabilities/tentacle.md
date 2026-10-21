# 触手（手眼网耳） · `tentacle`（18 位）

> 自动生成，数据源 `gbt_allinone/caps_registry.py`。只读 = 不改状态、不出网；其余调用前需人工授权（作用域门）。参数以 `requires_params` 标出。

| 能力位 | 类型 | 需参数 | 它做什么 |
|---|---|---|---|
| `agency_tentacles` | 只读 | — | 职业触手中枢：吸收 Agency Agents 职业资料；每根触手独立统一大模型会话与隔离镜像房间；支持并发汇总 |
| `desktop_commander` | 只读 | — | 桌面指挥官（Desktop Commander MCP）：终端+文件系统全能力触手；支持本地 stdio 与 remote 设备模式 |
| `desktop_distill` | 只读 | — | **蒸馏件**（不是外挂）：把吞入件 CursorTouch/Windows-MCP（MIT · 8871★ · MCP Server for Computer Use in Windows）的**取法**提炼成我们自己的桌面操作判据（主人令 2026-10-12「我们吞噬都是加… |
| `express_direct` | 只读 | — | 确定性直达（主人令 2026-10-13：「全部以触手来实现，砍掉『理由』这个不定因数」）：**指名派单、不猜**——给能力名即直达；执行一律经统一门 run_task（权限门/审计/钢印/禁用名单照旧生效，危险动作/付款由护栏+人工审核兜底）。**不给名字一律拒（fail_cl… |
| `long_run_supervisor` | 只读 | — | 长程无人值守任务监督：租约、心跳、检查点、有界重试、断点续作和主人升级 |
| `mcp_call` | 只读 | — | 触手契约层：按契约调用已连接服务器的任意工具 |
| `mcp_connect` | 只读 | — | 触手契约层：连接任意 MCP 工具服务器（学会契约协议=接入整个 MCP 生态） |
| `mcp_tools` | 只读 | — | 触手契约层：列出已连接服务器的工具契约清单（名称+参数 schema） |
| `omarchy_bridge` | **需授权** | — | **Omarchy 桥**（2026-10-15 主人拍 A 案：小土豆住进 Omarchy 当智能层）。接官方三根线：① `omarchy` CLI（含 `commands --json` 机读）；② `omarchy-shell` 的 UNIX-socket IPC（sock… |
| `omni_web` | **需授权** | 是 | 万能触手·Web六态：看结构/读源码/读讲解/改文件/交给AI/跑项目；git+github+stackblitz一键触达 |
| `remote_confinement` | **需授权** | — | **执行者隔离**（主人 2026-10-09 点破：「沙盒隔离的是被测试的靶标，没隔离执行的人」）：exec 中继若在宿主以主人账号跑，云端敲的命令就跑在真机上。op=assess/verdict 现读执行身份（whoami+是否提权）与三条隔离路（Docker 守护/WSL… |
| `tentacle` | 只读 | 是 | 触手/眼睛/双手/手：默认调本体原生能力，给意图自动命中，不给方法名也行；桌面动作见 see/read_text/click/type/list_windows（**条目数现算，见 tentacle_manifest**，不手写） |
| `tentacle_equip` | **需授权** | — | 触手**自配装备与账号**（主人令 2026-10-09）：**先有职业再谈装备** —— 职业从「vaults/agency_tentacles/library/zh」现读（272 个职业 / 19 个分域，三件套 count/examined/truncated 不截断），按… |
| `tentacle_manifest` | 只读 | — | 触手能力总纲（注入大脑上下文）：**条目数运行时现算，不手写**（手写数会腐烂——2026-10-13 实测 66/85 两处打架、都没人数过）+ 三通道感官 + 六铁律 |
| `tentacle_pipeline` | 只读 | — | 触手自动化流水线：四层七步、三公理、五红线；隔离执行、逐层汇报、dry-run 读数、终审只判不改、发布带回滚 |
| `tentacle_scale` | 只读 | — | 亿万触手寻址（逻辑 · 只读）：10^8 地址空间按算不占盘（t00000001…）+ 1024 分片 + 每根钥匙由主密钥 HMAC 派生（同一根永远同一把、彼此不同、可复算）· 钥匙只回指纹。**实体化/落盘不做**（新增位无 policy 分支 = 零作用域，属登记在册的坑… |
| `tentacle_status` | 只读 | — | 触手自诊断：硬件层就绪度 + 依赖分层 + 邻域覆盖 |
| `tool_bay` | **需授权** | — | 装备坞：触手「自配装备」走的那道门。白名单 15 件（本仓自定口径），每件状态靠**现跑探针**得出（没探针的如实报「无探针」，不得报已装）。install 三态：① 已在位（不耗票）② 需授权接上（screen/ui_tree/comfyui，**真过 auth_gate 的… |

> 表格里是**摘要**（超过 140 字截断）；完整原文见 [`data/capabilities.json`](../../data/capabilities.json) 的 `desc` 字段。

---

返回 [能力总表](../03-capabilities.md)
