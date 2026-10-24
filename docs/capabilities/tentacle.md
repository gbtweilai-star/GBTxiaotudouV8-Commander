# 触手（手眼网耳） · `tentacle`（18 位）

> 自动生成，数据源 `gbt_allinone/caps_registry.py`。只读 = 不改状态、不出网；其余调用前需人工授权（作用域门）。参数以 `requires_params` 标出；**必填载荷**与**常见错误**两列只写注册表登记过的（没登记就写「无必填」/通用三态），不猜。

| 能力位 | 类型 | 需参数 | 必填载荷 | 常见错误 | 它做什么 |
|---|---|---|---|---|---|
| `agency_tentacles` | 只读 | — | —（注册表：无必填） | `user_error` | 职业触手中枢：吸收 Agency Agents 职业资料；每根触手独立统一大模型会话与隔离镜像房间；支持并发汇总 |
| `desktop_commander` | 只读 | — | —（注册表：无必填） | `user_error` | 桌面指挥官（Desktop Commander MCP）：终端+文件系统全能力触手；支持本地 stdio 与 remote 设备模式 |
| `desktop_distill` | 只读 | — | —（注册表：无必填） | `user_error` | **蒸馏件**（不是外挂）：把吞入件 CursorTouch/Windows-MCP（MIT · 8871★ · MCP Server for Computer Use in Windows）的**取法**提炼成我们自己的桌面操作判据（主人令 2026-10-12「我们吞噬都是加… |
| `express_direct` | 只读 | — | —（注册表：无必填） | `user_error` | 确定性直达（主人令 2026-10-13：「全部以触手来实现，砍掉『理由』这个不定因数」）：**指名派单、不猜**——给能力名即直达；执行一律经统一门 run_task（权限门/审计/钢印/禁用名单照旧生效，危险动作/付款由护栏+人工审核兜底）。**不给名字一律拒（fail_cl… |
| `long_run_supervisor` | 只读 | — | —（注册表：无必填） | `user_error` | 长程无人值守任务监督：租约、心跳、检查点、有界重试、断点续作和主人升级 |
| `mcp_call` | 只读 | — | —（注册表：无必填） | `user_error` | 触手契约层：按契约调用已连接服务器的任意工具 |
| `mcp_connect` | 只读 | — | —（注册表：无必填） | `user_error` | 触手契约层：连接任意 MCP 工具服务器（学会契约协议=接入整个 MCP 生态） |
| `mcp_tools` | 只读 | — | —（注册表：无必填） | `user_error` | 触手契约层：列出已连接服务器的工具契约清单（名称+参数 schema） |
| `omarchy_bridge` | **需授权** | — | —（注册表：无必填） | `denied: missing_scopes` / `user_error` | **Omarchy 桥**（2026-10-15 主人拍 A 案：小土豆住进 Omarchy 当智能层）。接官方三根线：① `omarchy` CLI（含 `commands --json` 机读）；② `omarchy-shell` 的 UNIX-socket IPC（sock… |
| `omni_web` | **需授权** | 是 | **未登记**（注册表要参数，必填名待补） | `denied: missing_scopes` / `user_error` | 万能触手·Web六态：看结构/读源码/读讲解/改文件/交给AI/跑项目；git+github+stackblitz一键触达 |
| `remote_confinement` | **需授权** | — | —（注册表：无必填） | `denied: missing_scopes` / `user_error` | **执行者隔离**（主人 2026-10-09 点破：「沙盒隔离的是被测试的靶标，没隔离执行的人」）：exec 中继若在宿主以主人账号跑，云端敲的命令就跑在真机上。op=assess/verdict 现读执行身份（whoami+是否提权）与三条隔离路（Docker 守护/WSL… |
| `tentacle` | 只读 | 是 | `action` | `user_error` | 触手/眼睛/双手/手：默认调本体原生能力，给意图自动命中，不给方法名也行；桌面动作见 see/read_text/click/type/list_windows（**条目数现算，见 tentacle_manifest**，不手写） |
| `tentacle_equip` | **需授权** | — | —（注册表：无必填） | `user_error` / `failed` | 触手**自配装备与账号**（主人令 2026-10-09）：**先有职业再谈装备** —— 职业从「vaults/agency_tentacles/library/zh」现读（272 个职业 / 19 个分域，三件套 count/examined/truncated 不截断），按… |
| `tentacle_manifest` | 只读 | — | —（注册表：无必填） | `user_error` | 触手能力总纲（注入大脑上下文）：**条目数运行时现算，不手写**（手写数会腐烂——2026-10-13 实测 66/85 两处打架、都没人数过）+ 三通道感官 + 六铁律 |
| `tentacle_pipeline` | 只读 | — | —（注册表：无必填） | `user_error` | 触手自动化流水线：四层七步、三公理、五红线；隔离执行、逐层汇报、dry-run 读数、终审只判不改、发布带回滚 |
| `tentacle_scale` | 只读 | — | —（注册表：无必填） | `user_error` | 亿万触手寻址（逻辑 · 只读）：10^8 地址空间按算不占盘（t00000001…）+ 1024 分片 + 每根钥匙由主密钥 HMAC 派生（同一根永远同一把、彼此不同、可复算）· 钥匙只回指纹。**实体化/落盘不做**（新增位无 policy 分支 = 零作用域，属登记在册的坑… |
| `tentacle_status` | 只读 | — | —（注册表：无必填） | `user_error` | 触手自诊断：硬件层就绪度 + 依赖分层 + 邻域覆盖 |
| `tool_bay` | **需授权** | — | —（注册表：无必填） | `user_error` / `failed` | 装备坞：触手「自配装备」走的那道门。白名单 15 件（本仓自定口径），每件状态靠**现跑探针**得出（没探针的如实报「无探针」，不得报已装）。install 三态：① 已在位（不耗票）② 需授权接上（screen/ui_tree/comfyui，**真过 auth_gate 的… |

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

### `omni_web`

- **域**：`tentacle`（触手（手眼网耳））
- **类型**：**需授权**（会写盘 / 花钱 / 出网） · **需参数**：是 —— op=看结构|读源码|读讲解|改文件|gitingest|跑项目；repo=GitHub URL或本地路径；files=[…]（read_source）；path/content/mode（edit_file，mode=write|append|replace）；max_files/max_chars（gitingest）
- **要哪张票（静态）**：`filesystem_write`、`data_export`
- **必填载荷**：**未登记**：注册表标了 `requires_params=true`，但 `PARAM_REQUIRED` 里还没有它的必填名 —— 先按模块代码现读，不要猜（空载荷会撞 user_error）
- **常见错误**：缺票 → `denied`，回执点名 `missing_scopes`（本行静态票：`filesystem_write`、`data_export`）；参数非法 → `user_error`；依赖不在位 → `needs_dependency`；上游不给 → `needs_input` / `failed`（带上游原话）
- **它做什么**：万能触手·Web六态：看结构/读源码/读讲解/改文件/交给AI/跑项目；git+github+stackblitz一键触达
- **怎么调**：`py -3.14 tools/codex-scripts/five-dim.py cap omni_web '<json>'`
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

---

返回 [能力总表](../03-capabilities.md)
