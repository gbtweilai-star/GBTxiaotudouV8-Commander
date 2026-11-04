# 触手（手眼网耳） · `tentacle`（30 位）

> 自动生成，数据源 `gbt_allinone/caps_registry.py`。只读 = 不改状态、不出网；其余调用前需人工授权（作用域门）。参数以 `requires_params` 标出；**必填载荷**与**常见错误**两列只写注册表登记过的（没登记就写「无必填」/通用三态），不猜。

| 能力位 | 类型 | 需参数 | 必填载荷 | 常见错误 | 它做什么 |
|---|---|---|---|---|---|
| `agency_tentacles` | 只读 | — | —（注册表：无必填） | `user_error` | 职业触手中枢：吸收 Agency Agents 职业资料；每根触手独立统一大模型会话与隔离镜像房间；支持并发汇总 |
| `autonomy` | 只读 | — | —（注册表：无必填） | `user_error` | 自主契约：架构声明之后，除 **danger（终端危险能力）** 与 **transfer（转账/花钱）** 外，**禁止打扰主人、禁止要求主人帮助**。op=status 契约状态；op=declare 声明架构已给；op=check {"kind":...} 判定能不能问（只… |
| `blueprint` | 只读 | — | —（注册表：无必填） | `user_error` | 蓝图主链五段：op=make 架构→蓝图（阶段/任务/验收/风险，落 state/blueprints/）；op=approve 主人过目（**唯一允许的交互**，批准即进入自主模式、不再打扰）；op=mindmap 分析推理→任务图+依赖（mermaid 思维导图）；op=di… |
| `commander` | **需授权** | — | —（注册表：无必填） | `user_error` / `failed` | 触手主干·原生指挥官（**自有大模型权重 → 本机推理 → 主干判决**）：op=status 现读「权重/引擎/模型」三项（缺哪件说哪件，不编）；op=route 给一句意图，在**真名表**里选一个触手方法（不在候选里一律不采信＝幻觉防护）；op=ask 直接问权重一句；op… |
| `desktop_commander` | 只读 | — | —（注册表：无必填） | `user_error` | 桌面指挥官（Desktop Commander MCP）：终端+文件系统全能力触手；支持本地 stdio 与 remote 设备模式 |
| `desktop_distill` | 只读 | — | —（注册表：无必填） | `user_error` | **蒸馏件**（不是外挂）：把吞入件 CursorTouch/Windows-MCP（MIT · 8871★ · MCP Server for Computer Use in Windows）的**取法**提炼成我们自己的桌面操作判据（主人令 2026-10-12「我们吞噬都是加… |
| `express_direct` | 只读 | — | —（注册表：无必填） | `user_error` | 确定性直达（主人令 2026-10-13：「全部以触手来实现，砍掉『理由』这个不定因数」）：**指名派单、不猜**——给能力名即直达；执行一律经统一门 run_task（权限门/审计/钢印/禁用名单照旧生效，危险动作/付款由护栏+人工审核兜底）。**不给名字一律拒（fail_cl… |
| `legacy_guard` | 只读 | — | —（注册表：无必填） | `user_error` | 旧物守卫：查六类旧/重复——state/sync-backup 旧代码快照、过期工作树、旧面板归档、*.bak/.old/.orig、重复文档编号、state/tmp 临时件。op=status 结论；op=scan 逐条列；op=clean 删旧副本类（重复文档只报不删，删哪页… |
| `long_run_supervisor` | 只读 | — | —（注册表：无必填） | `user_error` | 长程无人值守任务监督：租约、心跳、检查点、有界重试、断点续作和主人升级 |
| `mcp_call` | 只读 | — | —（注册表：无必填） | `user_error` | 触手契约层：按契约调用已连接服务器的任意工具 |
| `mcp_connect` | 只读 | — | —（注册表：无必填） | `user_error` | 触手契约层：连接任意 MCP 工具服务器（学会契约协议=接入整个 MCP 生态） |
| `mcp_tools` | 只读 | — | —（注册表：无必填） | `user_error` | 触手契约层：列出已连接服务器的工具契约清单（名称+参数 schema） |
| `omarchy_bridge` | **需授权** | — | —（注册表：无必填） | `denied: missing_scopes` / `user_error` | **Omarchy 桥**（2026-10-15 主人拍 A 案：小土豆住进 Omarchy 当智能层）。接官方三根线：① `omarchy` CLI（含 `commands --json` 机读）；② `omarchy-shell` 的 UNIX-socket IPC（sock… |
| `omni_open` | 只读 | — | —（注册表：无必填） | `user_error` | 万能插·全自动打开：用她任何一项能力之前，**六类插座（process/file/api/web/app/ai）自动过一遍**，每类只给三种如实结论——可插 / 缺依赖（缺什么写在案）/ 需票；op=status 六类现状（含依据、缓存年龄），op=ensure 立刻重算。只做廉… |
| `omni_web` | **需授权** | 是 | **未登记**（注册表要参数，必填名待补） | `denied: missing_scopes` / `user_error` | 万能触手·Web六态：看结构/读源码/读讲解/改文件/交给AI/跑项目；git+github+stackblitz一键触达 |
| `pulse_core` | **需授权** | — | —（注册表：无必填） | `user_error` / `failed` | 触手四合一原生位：**脉冲提速**（一次拿全身状态）· **量化压缩**（主道 Q5_0，fp16 的 2.7×）· **按需激活**（引擎闲置卸权重、来请求再醒，起停过 process_execute 门）· **精准直达**（召回先兜住**全部能力位 + 全部触手方法**（条… |
| `remote_confinement` | **需授权** | — | —（注册表：无必填） | `denied: missing_scopes` / `user_error` | **执行者隔离**（主人 2026-10-09 点破：「沙盒隔离的是被测试的靶标，没隔离执行的人」）：exec 中继若在宿主以主人账号跑，云端敲的命令就跑在真机上。op=assess/verdict 现读执行身份（whoami+是否提权）与三条隔离路（Docker 守护/WSL… |
| `remote_controller` | **需授权** | — | —（注册表：无必填） | `user_error` / `failed` | 远程接管授权内核（2026-11-01 主人硬规矩：**必须远端用户点击同意**，请求方不能自批）：request 生成一次性 code + agent_secret（只给远端）→ approve 必须 remote_user.confirmed=true 且持 secret 的… |
| `tentacle` | 只读 | 是 | `action` | `user_error` | 触手/眼睛/双手/手：默认调本体原生能力，给意图自动命中，不给方法名也行；桌面动作见 see/read_text/click/type/list_windows（**条目数现算，见 tentacle_manifest**，不手写） |
| `tentacle_equip` | **需授权** | — | —（注册表：无必填） | `user_error` / `failed` | 触手**自配装备与账号**（主人令 2026-10-09）：**先有职业再谈装备** —— 职业从「vaults/agency_tentacles/library/zh」现读（272 个职业 / 19 个分域，三件套 count/examined/truncated 不截断），按… |
| `tentacle_manifest` | 只读 | — | —（注册表：无必填） | `user_error` | 触手能力总纲（注入大脑上下文）：**条目数运行时现算，不手写**（手写数会腐烂——2026-10-13 实测 66/85 两处打架、都没人数过）+ 三通道感官 + 六铁律 |
| `tentacle_pipeline` | 只读 | — | —（注册表：无必填） | `user_error` | 触手自动化流水线：四层七步、三公理、五红线；隔离执行、逐层汇报、dry-run 读数、终审只判不改、发布带回滚 |
| `tentacle_scale` | 只读 | — | —（注册表：无必填） | `user_error` | 亿万触手寻址（逻辑 · 只读）：10^8 地址空间按算不占盘（t00000001…）+ 1024 分片 + 每根钥匙由主密钥 HMAC 派生（同一根永远同一把、彼此不同、可复算）· 钥匙只回指纹。**实体化/落盘不做**（新增位无 policy 分支 = 零作用域，属登记在册的坑… |
| `tentacle_status` | 只读 | — | —（注册表：无必填） | `user_error` | 触手自诊断：硬件层就绪度 + 依赖分层 + 邻域覆盖 |
| `tool_bay` | **需授权** | — | —（注册表：无必填） | `user_error` / `failed` | 装备坞：触手「自配装备」走的那道门。白名单 15 件（本仓自定口径），每件状态靠**现跑探针**得出（没探针的如实报「无探针」，不得报已装）。install 三态：① 已在位（不耗票）② 需授权接上（screen/ui_tree/comfyui，**真过 auth_gate 的… |
| `trunk_cover` | 只读 | — | —（注册表：无必填） | `user_error` | 触手覆盖：**每个代码文件都要被某根触手认领**。op=status 覆盖率与按 owner 分布；op=scan 重扫落 state/trunk-cover.json；op=verify 判据（兜底率超阈值即红，并列出缺口文件）。认领规则从硬到软：同名文件 → 实现文件映射 →… |
| `trunk_reason` | 只读 | — | —（注册表：无必填） | `user_error` | 触手推理环：op=agent 跑一轮"看→想→动→再想"——先跑真实只读自检，再把现状喂给本机 7.6B 权重判断真风险/误报/下一步，然后按建议**只跑白名单内的只读检查**拿新证据，最后复核初判。op=reflect 单次反思；op=status 看大脑在不在。边界：act… |

> 表格里是**摘要**（超过 140 字截断）；下面每位还有**逐位详解**（完整原文 / 要哪张票 / 真调用命令 / 缺什么会怎么报）。

---

## 逐位详解

### `agency_tentacles`

- **域**：`tentacle`（触手（手眼网耳））
- **类型**：只读（不改状态、不出网） · **需参数**：否
- **要哪张票（静态）**：零作用域（空 payload 下不需要票）
- **必填载荷**：无必填（注册表 `requires_params=false`；空载荷落到该位默认 op）
- **常见错误**：参数非法 → `user_error`
- **它做什么**：职业触手中枢：吸收 Agency Agents 职业资料；每根触手独立统一大模型会话与隔离镜像房间；支持并发汇总
- **怎么调**：`py -3.14 tools/codex-scripts/five-dim.py cap agency_tentacles '<json>'`
- **失败三态**（本仓统一口径，不是这一位特有）：`denied` = 缺票，会点名`missing_scopes`；`needs_*` = 缺参/缺依赖，会带原因；`failed` = 真失败，回执带上游原话。**信封 `status=ok` ≠ 本体 `ok=true`。**

### `autonomy`

- **域**：`tentacle`（触手（手眼网耳））
- **类型**：只读（不改状态、不出网） · **需参数**：否
- **要哪张票（静态）**：零作用域（空 payload 下不需要票）
- **必填载荷**：无必填（注册表 `requires_params=false`；空载荷落到该位默认 op）
- **常见错误**：参数非法 → `user_error`
- **它做什么**：自主契约：架构声明之后，除 **danger（终端危险能力）** 与 **transfer（转账/花钱）** 外，**禁止打扰主人、禁止要求主人帮助**。op=status 契约状态；op=declare 声明架构已给；op=check {"kind":...} 判定能不能问（只有两个例外放行）；op=guard {"text":...} 把「需要你确认/要不要我/请提供…」这类回头问主人的句子**改写成自主推进**并记账；op=ledger 打扰账本。判据三条：架构已给才生效 / 例外只有 danger+transfer / 打扰必留痕。
- **怎么调**：`py -3.14 tools/codex-scripts/five-dim.py cap autonomy '<json>'`
- **失败三态**（本仓统一口径，不是这一位特有）：`denied` = 缺票，会点名`missing_scopes`；`needs_*` = 缺参/缺依赖，会带原因；`failed` = 真失败，回执带上游原话。**信封 `status=ok` ≠ 本体 `ok=true`。**

### `blueprint`

- **域**：`tentacle`（触手（手眼网耳））
- **类型**：只读（不改状态、不出网） · **需参数**：否
- **要哪张票（静态）**：零作用域（空 payload 下不需要票）
- **必填载荷**：无必填（注册表 `requires_params=false`；空载荷落到该位默认 op）
- **常见错误**：参数非法 → `user_error`
- **它做什么**：蓝图主链五段：op=make 架构→蓝图（阶段/任务/验收/风险，落 state/blueprints/）；op=approve 主人过目（**唯一允许的交互**，批准即进入自主模式、不再打扰）；op=mindmap 分析推理→任务图+依赖（mermaid 思维导图）；op=dispatch 按依赖拓扑派遣触手执行（**只跑安全能力位**，危险/转账留票）；op=status 进度与是否落地（landed 要求全部任务 ok）。纪律：蓝图不过目不派遣；不装成功，失败如实列。
- **怎么调**：`py -3.14 tools/codex-scripts/five-dim.py cap blueprint '<json>'`
- **失败三态**（本仓统一口径，不是这一位特有）：`denied` = 缺票，会点名`missing_scopes`；`needs_*` = 缺参/缺依赖，会带原因；`failed` = 真失败，回执带上游原话。**信封 `status=ok` ≠ 本体 `ok=true`。**

### `commander`

- **域**：`tentacle`（触手（手眼网耳））
- **类型**：**需授权**（会写盘 / 花钱 / 出网） · **需参数**：否
- **要哪张票（静态）**：零作用域（空 payload 下不需要票）
- **必填载荷**：无必填（注册表 `requires_params=false`；空载荷落到该位默认 op）
- **常见错误**：参数非法 → `user_error`；依赖不在位 → `needs_dependency`；上游不给 → `needs_input` / `failed`（带上游原话）
- **它做什么**：触手主干·原生指挥官（**自有大模型权重 → 本机推理 → 主干判决**）：op=status 现读「权重/引擎/模型」三项（缺哪件说哪件，不编）；op=route 给一句意图，在**真名表**里选一个触手方法（不在候选里一律不采信＝幻觉防护）；op=ask 直接问权重一句；op=start/stop 起停本机引擎（幂等，过 process_execute 门）。车道口径：**不出网、不按 token 计费、不要 external_llm 票**；引擎没起时主干照旧降级到云端车道/词表辅路，并把降级如实标出来。
- **怎么调**：`py -3.14 tools/codex-scripts/five-dim.py cap commander '<json>'`
- **失败三态**（本仓统一口径，不是这一位特有）：`denied` = 缺票，会点名`missing_scopes`；`needs_*` = 缺参/缺依赖，会带原因；`failed` = 真失败，回执带上游原话。**信封 `status=ok` ≠ 本体 `ok=true`。**

### `desktop_commander`

- **域**：`tentacle`（触手（手眼网耳））
- **类型**：只读（不改状态、不出网） · **需参数**：否
- **要哪张票（静态）**：零作用域（空 payload 下不需要票）
- **必填载荷**：无必填（注册表 `requires_params=false`；空载荷落到该位默认 op）
- **常见错误**：参数非法 → `user_error`
- **它做什么**：桌面指挥官（Desktop Commander MCP）：终端+文件系统全能力触手；支持本地 stdio 与 remote 设备模式
- **怎么调**：`py -3.14 tools/codex-scripts/five-dim.py cap desktop_commander '<json>'`
- **失败三态**（本仓统一口径，不是这一位特有）：`denied` = 缺票，会点名`missing_scopes`；`needs_*` = 缺参/缺依赖，会带原因；`failed` = 真失败，回执带上游原话。**信封 `status=ok` ≠ 本体 `ok=true`。**

### `desktop_distill`

- **域**：`tentacle`（触手（手眼网耳））
- **类型**：只读（不改状态、不出网） · **需参数**：否
- **要哪张票（静态）**：零作用域（空 payload 下不需要票）
- **必填载荷**：无必填（注册表 `requires_params=false`；空载荷落到该位默认 op）
- **常见错误**：参数非法 → `user_error`
- **它做什么**：**蒸馏件**（不是外挂）：把吞入件 CursorTouch/Windows-MCP（MIT · 8871★ · MCP Server for Computer Use in Windows）的**取法**提炼成我们自己的桌面操作判据（主人令 2026-10-12「我们吞噬都是加入蒸馏提炼出契合我们的能力」）。四条：①状态先行（动手前先取一帧窗口/UI 状态）②UIA 优先、视觉可选（层级=UIA 直取→DOM 降噪→视觉兜底）③DOM 模式给浏览器降噪（Firefox 无 RootWebArea ⇒ 要 IAccessible2 兜底）④动作节律 op=rhythm（它的 0.2–0.5s 基线**现算**成「动后等稳定」等待，带上限防死等）。op=source 现读胶囊尺寸+逐文件 sha256 · op=provenance 逐条指回原话（含**未蒸馏**两行：起服务/装计划任务故意不取 · App-Tool 依赖英文 Windows 只当坑记）。**零作用域**：无 subprocess / 无 urllib / 无写盘。边界：win-mcp 干的事我们**已有**（tentacle / desktop_commander / browser）⇒ 本位只蒸取法，不建平行位。op=method/rhythm/source/provenance/where
- **怎么调**：`py -3.14 tools/codex-scripts/five-dim.py cap desktop_distill '<json>'`
- **失败三态**（本仓统一口径，不是这一位特有）：`denied` = 缺票，会点名`missing_scopes`；`needs_*` = 缺参/缺依赖，会带原因；`failed` = 真失败，回执带上游原话。**信封 `status=ok` ≠ 本体 `ok=true`。**

### `express_direct`

- **域**：`tentacle`（触手（手眼网耳））
- **类型**：只读（不改状态、不出网） · **需参数**：否
- **要哪张票（静态）**：零作用域（空 payload 下不需要票）
- **必填载荷**：无必填（注册表 `requires_params=false`；空载荷落到该位默认 op）
- **常见错误**：参数非法 → `user_error`
- **它做什么**：确定性直达（主人令 2026-10-13：「全部以触手来实现，砍掉『理由』这个不定因数」）：**指名派单、不猜**——给能力名即直达；执行一律经统一门 run_task（权限门/审计/钢印/禁用名单照旧生效，危险动作/付款由护栏+人工审核兜底）。**不给名字一律拒（fail_closed）**，不许替她猜一个去跑。入参：kind=能力名、payload=给它的入参。对位件 gbt_allinone/tentacle/express_bridge.py::direct
- **怎么调**：`py -3.14 tools/codex-scripts/five-dim.py cap express_direct '<json>'`
- **失败三态**（本仓统一口径，不是这一位特有）：`denied` = 缺票，会点名`missing_scopes`；`needs_*` = 缺参/缺依赖，会带原因；`failed` = 真失败，回执带上游原话。**信封 `status=ok` ≠ 本体 `ok=true`。**

### `legacy_guard`

- **域**：`tentacle`（触手（手眼网耳））
- **类型**：只读（不改状态、不出网） · **需参数**：否
- **要哪张票（静态）**：零作用域（空 payload 下不需要票）
- **必填载荷**：无必填（注册表 `requires_params=false`；空载荷落到该位默认 op）
- **常见错误**：参数非法 → `user_error`
- **它做什么**：旧物守卫：查六类旧/重复——state/sync-backup 旧代码快照、过期工作树、旧面板归档、*.bak/.old/.orig、重复文档编号、state/tmp 临时件。op=status 结论；op=scan 逐条列；op=clean 删旧副本类（重复文档只报不删，删哪页要人看内容）。每次清理记编排账本。
- **怎么调**：`py -3.14 tools/codex-scripts/five-dim.py cap legacy_guard '<json>'`
- **失败三态**（本仓统一口径，不是这一位特有）：`denied` = 缺票，会点名`missing_scopes`；`needs_*` = 缺参/缺依赖，会带原因；`failed` = 真失败，回执带上游原话。**信封 `status=ok` ≠ 本体 `ok=true`。**

### `long_run_supervisor`

- **域**：`tentacle`（触手（手眼网耳））
- **类型**：只读（不改状态、不出网） · **需参数**：否
- **要哪张票（静态）**：零作用域（空 payload 下不需要票）
- **必填载荷**：无必填（注册表 `requires_params=false`；空载荷落到该位默认 op）
- **常见错误**：参数非法 → `user_error`
- **它做什么**：长程无人值守任务监督：租约、心跳、检查点、有界重试、断点续作和主人升级
- **怎么调**：`py -3.14 tools/codex-scripts/five-dim.py cap long_run_supervisor '<json>'`
- **失败三态**（本仓统一口径，不是这一位特有）：`denied` = 缺票，会点名`missing_scopes`；`needs_*` = 缺参/缺依赖，会带原因；`failed` = 真失败，回执带上游原话。**信封 `status=ok` ≠ 本体 `ok=true`。**

### `mcp_call`

- **域**：`tentacle`（触手（手眼网耳））
- **类型**：只读（不改状态、不出网） · **需参数**：否
- **要哪张票（静态）**：`process_execute`
- **必填载荷**：无必填（注册表 `requires_params=false`；空载荷落到该位默认 op）
- **常见错误**：参数非法 → `user_error`
- **它做什么**：触手契约层：按契约调用已连接服务器的任意工具
- **怎么调**：`py -3.14 tools/codex-scripts/five-dim.py cap mcp_call '<json>'`
- **失败三态**（本仓统一口径，不是这一位特有）：`denied` = 缺票，会点名`missing_scopes`；`needs_*` = 缺参/缺依赖，会带原因；`failed` = 真失败，回执带上游原话。**信封 `status=ok` ≠ 本体 `ok=true`。**

### `mcp_connect`

- **域**：`tentacle`（触手（手眼网耳））
- **类型**：只读（不改状态、不出网） · **需参数**：否
- **要哪张票（静态）**：`process_execute`
- **必填载荷**：无必填（注册表 `requires_params=false`；空载荷落到该位默认 op）
- **常见错误**：参数非法 → `user_error`
- **它做什么**：触手契约层：连接任意 MCP 工具服务器（学会契约协议=接入整个 MCP 生态）
- **怎么调**：`py -3.14 tools/codex-scripts/five-dim.py cap mcp_connect '<json>'`
- **失败三态**（本仓统一口径，不是这一位特有）：`denied` = 缺票，会点名`missing_scopes`；`needs_*` = 缺参/缺依赖，会带原因；`failed` = 真失败，回执带上游原话。**信封 `status=ok` ≠ 本体 `ok=true`。**

### `mcp_tools`

- **域**：`tentacle`（触手（手眼网耳））
- **类型**：只读（不改状态、不出网） · **需参数**：否
- **要哪张票（静态）**：零作用域（空 payload 下不需要票）
- **必填载荷**：无必填（注册表 `requires_params=false`；空载荷落到该位默认 op）
- **常见错误**：参数非法 → `user_error`
- **它做什么**：触手契约层：列出已连接服务器的工具契约清单（名称+参数 schema）
- **怎么调**：`py -3.14 tools/codex-scripts/five-dim.py cap mcp_tools '<json>'`
- **失败三态**（本仓统一口径，不是这一位特有）：`denied` = 缺票，会点名`missing_scopes`；`needs_*` = 缺参/缺依赖，会带原因；`failed` = 真失败，回执带上游原话。**信封 `status=ok` ≠ 本体 `ok=true`。**

### `omarchy_bridge`

- **域**：`tentacle`（触手（手眼网耳））
- **类型**：**需授权**（会写盘 / 花钱 / 出网） · **需参数**：否
- **要哪张票（静态）**：`process_execute`
- **必填载荷**：无必填（注册表 `requires_params=false`；空载荷落到该位默认 op）
- **常见错误**：缺票 → `denied`，回执点名 `missing_scopes`（本行静态票：`process_execute`）；参数非法 → `user_error`；依赖不在位 → `needs_dependency`；上游不给 → `needs_input` / `failed`（带上游原话）
- **它做什么**：**Omarchy 桥**（2026-10-15 主人拍 A 案：小土豆住进 Omarchy 当智能层）。接官方三根线：① `omarchy` CLI（含 `commands --json` 机读）；② `omarchy-shell` 的 UNIX-socket IPC（socket 名 = md5(OMARCHY_PATH/shell+WAYLAND_DISPLAY)，**现算不写死**）；③ `hyprctl` + `$XDG_RUNTIME_DIR/hypr/*.sock`（排窗/切工作区）。op=assess 现读两侧（宿主能不能接 · WSL 里装没装）· list 读命令表 · probe_wsl 探 WSL 痕迹 ·theme_list 读主题表 · **events 读窗口事件流**（$XDG_RUNTIME_DIR/hypr/<HIS>/.socket2.sock，逐行 EVENT>>DATA；**一次性读取、读完即断** —— 官方说过该 socket 同步求值，挂着会冻结）· window（activewindow）· clients（打开的窗口列表）（以上只读）；set_theme/theme_install/dispatch/eval/plugin_* 是写类。两条纪律：**没装就如实报**（ok=false + reason，绝不假装接上）；**写类 fail-closed**（不在 Omarchy 会话里就拒，并说清怎么开）。**WSL2 里跑不了 Hyprland**（无 DRM/KMS）⇒ WSL 那栏只做"装没装"的探针，不做"接上桌面"的承诺。本件不装 Omarchy、不写它的配置。
- **怎么调**：`py -3.14 tools/codex-scripts/five-dim.py cap omarchy_bridge '<json>'`
- **失败三态**（本仓统一口径，不是这一位特有）：`denied` = 缺票，会点名`missing_scopes`；`needs_*` = 缺参/缺依赖，会带原因；`failed` = 真失败，回执带上游原话。**信封 `status=ok` ≠ 本体 `ok=true`。**

### `omni_open`

- **域**：`tentacle`（触手（手眼网耳））
- **类型**：只读（不改状态、不出网） · **需参数**：否
- **要哪张票（静态）**：零作用域（空 payload 下不需要票）
- **必填载荷**：无必填（注册表 `requires_params=false`；空载荷落到该位默认 op）
- **常见错误**：参数非法 → `user_error`
- **它做什么**：万能插·全自动打开：用她任何一项能力之前，**六类插座（process/file/api/web/app/ai）自动过一遍**，每类只给三种如实结论——可插 / 缺依赖（缺什么写在案）/ 需票；op=status 六类现状（含依据、缓存年龄），op=ensure 立刻重算。只做廉价探针，不跑 26s 的全量 discover、不擅自起进程；「没探到」绝不说成「已打开」。
- **怎么调**：`py -3.14 tools/codex-scripts/five-dim.py cap omni_open '<json>'`
- **失败三态**（本仓统一口径，不是这一位特有）：`denied` = 缺票，会点名`missing_scopes`；`needs_*` = 缺参/缺依赖，会带原因；`failed` = 真失败，回执带上游原话。**信封 `status=ok` ≠ 本体 `ok=true`。**

### `omni_web`

- **域**：`tentacle`（触手（手眼网耳））
- **类型**：**需授权**（会写盘 / 花钱 / 出网） · **需参数**：是 —— op=看结构|读源码|读讲解|改文件|gitingest|跑项目；repo=GitHub URL或本地路径；files=[…]（read_source）；path/content/mode（edit_file，mode=write|append|replace）；max_files/max_chars（gitingest）
- **要哪张票（静态）**：`filesystem_write`、`data_export`
- **必填载荷**：**未登记**：注册表标了 `requires_params=true`，但 `PARAM_REQUIRED` 里还没有它的必填名 —— 先按模块代码现读，不要猜（空载荷会撞 user_error）
- **常见错误**：缺票 → `denied`，回执点名 `missing_scopes`（本行静态票：`filesystem_write`、`data_export`）；参数非法 → `user_error`；依赖不在位 → `needs_dependency`；上游不给 → `needs_input` / `failed`（带上游原话）
- **它做什么**：万能触手·Web六态：看结构/读源码/读讲解/改文件/交给AI/跑项目；git+github+stackblitz一键触达
- **怎么调**：`py -3.14 tools/codex-scripts/five-dim.py cap omni_web '<json>'`
- **失败三态**（本仓统一口径，不是这一位特有）：`denied` = 缺票，会点名`missing_scopes`；`needs_*` = 缺参/缺依赖，会带原因；`failed` = 真失败，回执带上游原话。**信封 `status=ok` ≠ 本体 `ok=true`。**

### `pulse_core`

- **域**：`tentacle`（触手（手眼网耳））
- **类型**：**需授权**（会写盘 / 花钱 / 出网） · **需参数**：否
- **要哪张票（静态）**：零作用域（空 payload 下不需要票）
- **必填载荷**：无必填（注册表 `requires_params=false`；空载荷落到该位默认 op）
- **常见错误**：参数非法 → `user_error`；依赖不在位 → `needs_dependency`；上游不给 → `needs_input` / `failed`（带上游原话）
- **它做什么**：触手四合一原生位：**脉冲提速**（一次拿全身状态）· **量化压缩**（主道 Q5_0，fp16 的 2.7×）· **按需激活**（引擎闲置卸权重、来请求再醒，起停过 process_execute 门）· **精准直达**（召回先兜住**全部能力位 + 全部触手方法**（条数现读，不写死），权重只在这份候选里挑）。op=status 四件套现读；op=verify **真跑四条判据**（防"文档说有、代码没有"）；op=route 一句话走完整条链；op=plan 只出计划；op=wake/stop 起停本机引擎。
- **怎么调**：`py -3.14 tools/codex-scripts/five-dim.py cap pulse_core '<json>'`
- **失败三态**（本仓统一口径，不是这一位特有）：`denied` = 缺票，会点名`missing_scopes`；`needs_*` = 缺参/缺依赖，会带原因；`failed` = 真失败，回执带上游原话。**信封 `status=ok` ≠ 本体 `ok=true`。**

### `remote_confinement`

- **域**：`tentacle`（触手（手眼网耳））
- **类型**：**需授权**（会写盘 / 花钱 / 出网） · **需参数**：否
- **要哪张票（静态）**：`process_execute`
- **必填载荷**：无必填（注册表 `requires_params=false`；空载荷落到该位默认 op）
- **常见错误**：缺票 → `denied`，回执点名 `missing_scopes`（本行静态票：`process_execute`）；参数非法 → `user_error`；依赖不在位 → `needs_dependency`；上游不给 → `needs_input` / `failed`（带上游原话）
- **它做什么**：**执行者隔离**（主人 2026-10-09 点破：「沙盒隔离的是被测试的靶标，没隔离执行的人」）：exec 中继若在宿主以主人账号跑，云端敲的命令就跑在真机上。op=assess/verdict 现读执行身份（whoami+是否提权）与三条隔离路（Docker 守护/WSL 发行版/低权账号）**并真验每条能不能跑**；ttl 读看门狗（中继最长 TTL）；grant **只查**主人发的 remote_device 票（AI 不发）；guard 是启中继前的最后一道闸：**未隔离 + 无票 ⇒ 一律拒启**（fail-closed），拒了说清怎么开。本件已焊进 desktop_commander.remote_start。
- **怎么调**：`py -3.14 tools/codex-scripts/five-dim.py cap remote_confinement '<json>'`
- **失败三态**（本仓统一口径，不是这一位特有）：`denied` = 缺票，会点名`missing_scopes`；`needs_*` = 缺参/缺依赖，会带原因；`failed` = 真失败，回执带上游原话。**信封 `status=ok` ≠ 本体 `ok=true`。**

### `remote_controller`

- **域**：`tentacle`（触手（手眼网耳））
- **类型**：**需授权**（会写盘 / 花钱 / 出网） · **需参数**：否
- **要哪张票（静态）**：零作用域（空 payload 下不需要票）
- **必填载荷**：无必填（注册表 `requires_params=false`；空载荷落到该位默认 op）
- **常见错误**：参数非法 → `user_error`；依赖不在位 → `needs_dependency`；上游不给 → `needs_input` / `failed`（带上游原话）
- **它做什么**：远程接管授权内核（2026-11-01 主人硬规矩：**必须远端用户点击同意**，请求方不能自批）：request 生成一次性 code + agent_secret（只给远端）→ approve 必须 remote_user.confirmed=true 且持 secret 的 HMAC 签名 → session 仅在 approved/未撤销时发；revoke 即时失效；audit 全留痕。边界：屏幕/输入/语音媒体通道与公网隧道未接（不假装已远控）；是“先同意再接管”的授权层。op=status/request/approve/deny/session/revoke/audit/where。
- **怎么调**：`py -3.14 tools/codex-scripts/five-dim.py cap remote_controller '<json>'`
- **失败三态**（本仓统一口径，不是这一位特有）：`denied` = 缺票，会点名`missing_scopes`；`needs_*` = 缺参/缺依赖，会带原因；`failed` = 真失败，回执带上游原话。**信封 `status=ok` ≠ 本体 `ok=true`。**

### `tentacle`

- **域**：`tentacle`（触手（手眼网耳））
- **类型**：只读（不改状态、不出网） · **需参数**：是 —— 触手能力名；或给 intent 走自动路由、op=caps 看全部
- **要哪张票（静态）**：零作用域（空 payload 下不需要票）
- **必填载荷**：`action` —— 触手能力名；或给 intent 走自动路由、op=caps 看全部
- **常见错误**：缺参 / 参数非法 → `user_error`（必填：`action`）
- **它做什么**：触手/眼睛/双手/手：默认调本体原生能力，给意图自动命中，不给方法名也行；桌面动作见 see/read_text/click/type/list_windows（**条目数现算，见 tentacle_manifest**，不手写）
- **怎么调**：`py -3.14 tools/codex-scripts/five-dim.py cap tentacle '<json>'`
- **失败三态**（本仓统一口径，不是这一位特有）：`denied` = 缺票，会点名`missing_scopes`；`needs_*` = 缺参/缺依赖，会带原因；`failed` = 真失败，回执带上游原话。**信封 `status=ok` ≠ 本体 `ok=true`。**

### `tentacle_equip`

- **域**：`tentacle`（触手（手眼网耳））
- **类型**：**需授权**（会写盘 / 花钱 / 出网） · **需参数**：否
- **要哪张票（静态）**：零作用域（空 payload 下不需要票）
- **必填载荷**：无必填（注册表 `requires_params=false`；空载荷落到该位默认 op）
- **常见错误**：参数非法 → `user_error`；依赖不在位 → `needs_dependency`；上游不给 → `needs_input` / `failed`（带上游原话）
- **它做什么**：触手**自配装备与账号**（主人令 2026-10-09）：**先有职业再谈装备** —— 职业从「vaults/agency_tentacles/library/zh」现读（272 个职业 / 19 个分域，三件套 count/examined/truncated 不截断），按分域 + 职业名关键词算出「这根触手要什么服务位 + 什么装备」，再走**两道现成的门**配上：装备走能力位 tool_bay（白名单+授权令牌），账号只从环境变量认（未配就如实报缺口，**不编账号、不存明文**）。op=status/professions/plan/report 为读类；equip 为写类（dry_run 默认真·只算不动；真配会消耗 process_execute）。**没立职业 → 空需求，不瞎配**。
- **怎么调**：`py -3.14 tools/codex-scripts/five-dim.py cap tentacle_equip '<json>'`
- **失败三态**（本仓统一口径，不是这一位特有）：`denied` = 缺票，会点名`missing_scopes`；`needs_*` = 缺参/缺依赖，会带原因；`failed` = 真失败，回执带上游原话。**信封 `status=ok` ≠ 本体 `ok=true`。**

### `tentacle_manifest`

- **域**：`tentacle`（触手（手眼网耳））
- **类型**：只读（不改状态、不出网） · **需参数**：否
- **要哪张票（静态）**：零作用域（空 payload 下不需要票）
- **必填载荷**：无必填（注册表 `requires_params=false`；空载荷落到该位默认 op）
- **常见错误**：参数非法 → `user_error`
- **它做什么**：触手能力总纲（注入大脑上下文）：**条目数运行时现算，不手写**（手写数会腐烂——2026-10-13 实测 66/85 两处打架、都没人数过）+ 三通道感官 + 六铁律
- **怎么调**：`py -3.14 tools/codex-scripts/five-dim.py cap tentacle_manifest '<json>'`
- **失败三态**（本仓统一口径，不是这一位特有）：`denied` = 缺票，会点名`missing_scopes`；`needs_*` = 缺参/缺依赖，会带原因；`failed` = 真失败，回执带上游原话。**信封 `status=ok` ≠ 本体 `ok=true`。**

### `tentacle_pipeline`

- **域**：`tentacle`（触手（手眼网耳））
- **类型**：只读（不改状态、不出网） · **需参数**：否
- **要哪张票（静态）**：零作用域（空 payload 下不需要票）
- **必填载荷**：无必填（注册表 `requires_params=false`；空载荷落到该位默认 op）
- **常见错误**：参数非法 → `user_error`
- **它做什么**：触手自动化流水线：四层七步、三公理、五红线；隔离执行、逐层汇报、dry-run 读数、终审只判不改、发布带回滚
- **怎么调**：`py -3.14 tools/codex-scripts/five-dim.py cap tentacle_pipeline '<json>'`
- **失败三态**（本仓统一口径，不是这一位特有）：`denied` = 缺票，会点名`missing_scopes`；`needs_*` = 缺参/缺依赖，会带原因；`failed` = 真失败，回执带上游原话。**信封 `status=ok` ≠ 本体 `ok=true`。**

### `tentacle_scale`

- **域**：`tentacle`（触手（手眼网耳））
- **类型**：只读（不改状态、不出网） · **需参数**：否
- **要哪张票（静态）**：零作用域（空 payload 下不需要票）
- **必填载荷**：无必填（注册表 `requires_params=false`；空载荷落到该位默认 op）
- **常见错误**：参数非法 → `user_error`
- **它做什么**：亿万触手寻址（逻辑 · 只读）：10^8 地址空间按算不占盘（t00000001…）+ 1024 分片 + 每根钥匙由主密钥 HMAC 派生（同一根永远同一把、彼此不同、可复算）· 钥匙只回指纹。**实体化/落盘不做**（新增位无 policy 分支 = 零作用域，属登记在册的坑，要开请主人在 security/policy.py 挂作用域）；主密钥不在就如实报「未配」，不代建。op=space/addr/parse/shard/key/master
- **怎么调**：`py -3.14 tools/codex-scripts/five-dim.py cap tentacle_scale '<json>'`
- **失败三态**（本仓统一口径，不是这一位特有）：`denied` = 缺票，会点名`missing_scopes`；`needs_*` = 缺参/缺依赖，会带原因；`failed` = 真失败，回执带上游原话。**信封 `status=ok` ≠ 本体 `ok=true`。**

### `tentacle_status`

- **域**：`tentacle`（触手（手眼网耳））
- **类型**：只读（不改状态、不出网） · **需参数**：否
- **要哪张票（静态）**：零作用域（空 payload 下不需要票）
- **必填载荷**：无必填（注册表 `requires_params=false`；空载荷落到该位默认 op）
- **常见错误**：参数非法 → `user_error`
- **它做什么**：触手自诊断：硬件层就绪度 + 依赖分层 + 邻域覆盖
- **怎么调**：`py -3.14 tools/codex-scripts/five-dim.py cap tentacle_status '<json>'`
- **失败三态**（本仓统一口径，不是这一位特有）：`denied` = 缺票，会点名`missing_scopes`；`needs_*` = 缺参/缺依赖，会带原因；`failed` = 真失败，回执带上游原话。**信封 `status=ok` ≠ 本体 `ok=true`。**

### `tool_bay`

- **域**：`tentacle`（触手（手眼网耳））
- **类型**：**需授权**（会写盘 / 花钱 / 出网） · **需参数**：否
- **要哪张票（静态）**：零作用域（空 payload 下不需要票）
- **必填载荷**：无必填（注册表 `requires_params=false`；空载荷落到该位默认 op）
- **常见错误**：参数非法 → `user_error`；依赖不在位 → `needs_dependency`；上游不给 → `needs_input` / `failed`（带上游原话）
- **它做什么**：装备坞：触手「自配装备」走的那道门。白名单 15 件（本仓自定口径），每件状态靠**现跑探针**得出（没探针的如实报「无探针」，不得报已装）。install 三态：① 已在位（不耗票）② 需授权接上（screen/ui_tree/comfyui，**真过 auth_gate 的 check_and_consume**，没票如实报 needs_grant）③ 第三方件需主人装（**不代下、也不为此耗票**）。每装一次落账 state/tool_bay.jsonl。op=state 读类，install 写类。
- **怎么调**：`py -3.14 tools/codex-scripts/five-dim.py cap tool_bay '<json>'`
- **失败三态**（本仓统一口径，不是这一位特有）：`denied` = 缺票，会点名`missing_scopes`；`needs_*` = 缺参/缺依赖，会带原因；`failed` = 真失败，回执带上游原话。**信封 `status=ok` ≠ 本体 `ok=true`。**

### `trunk_cover`

- **域**：`tentacle`（触手（手眼网耳））
- **类型**：只读（不改状态、不出网） · **需参数**：否
- **要哪张票（静态）**：零作用域（空 payload 下不需要票）
- **必填载荷**：无必填（注册表 `requires_params=false`；空载荷落到该位默认 op）
- **常见错误**：参数非法 → `user_error`
- **它做什么**：触手覆盖：**每个代码文件都要被某根触手认领**。op=status 覆盖率与按 owner 分布；op=scan 重扫落 state/trunk-cover.json；op=verify 判据（兜底率超阈值即红，并列出缺口文件）。认领规则从硬到软：同名文件 → 实现文件映射 → tools 同名 → import 关系 → 兜底 tentacle（单独计数）。同时报"每个能力位有没有自己的文件"——没有的如实列名，不把兜底说成已覆盖。
- **怎么调**：`py -3.14 tools/codex-scripts/five-dim.py cap trunk_cover '<json>'`
- **失败三态**（本仓统一口径，不是这一位特有）：`denied` = 缺票，会点名`missing_scopes`；`needs_*` = 缺参/缺依赖，会带原因；`failed` = 真失败，回执带上游原话。**信封 `status=ok` ≠ 本体 `ok=true`。**

### `trunk_reason`

- **域**：`tentacle`（触手（手眼网耳））
- **类型**：只读（不改状态、不出网） · **需参数**：否
- **要哪张票（静态）**：零作用域（空 payload 下不需要票）
- **必填载荷**：无必填（注册表 `requires_params=false`；空载荷落到该位默认 op）
- **常见错误**：参数非法 → `user_error`
- **它做什么**：触手推理环：op=agent 跑一轮"看→想→动→再想"——先跑真实只读自检，再把现状喂给本机 7.6B 权重判断真风险/误报/下一步，然后按建议**只跑白名单内的只读检查**拿新证据，最后复核初判。op=reflect 单次反思；op=status 看大脑在不在。边界：act 只跑只读能力位，绝不写盘/执行/越权；大脑不在就如实报"没在想"。
- **怎么调**：`py -3.14 tools/codex-scripts/five-dim.py cap trunk_reason '<json>'`
- **失败三态**（本仓统一口径，不是这一位特有）：`denied` = 缺票，会点名`missing_scopes`；`needs_*` = 缺参/缺依赖，会带原因；`failed` = 真失败，回执带上游原话。**信封 `status=ok` ≠ 本体 `ok=true`。**

---

返回 [能力总表](../03-capabilities.md)

---

> 开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属
