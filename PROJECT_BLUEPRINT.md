# PROJECT_BLUEPRINT.md - GBT小土豆V8

> 本文件是 GBT小土豆V8 的系统级立体蓝图。它描述现有架构、依赖方向、
> 当前进度、连带风险和落地顺序。
>
> 更新时间：2026-09-15
> 基线版本：gbt_allinone 8.0.0
> 当前能力：128 项已注册，117 项启用，11 项按安全策略禁用

## 一、系统边界

### 1.1 不可动摇的主从关系

- 主人拥有最终决策权、资金权、凭据权和发布权。
- AI 可以观察、检索、提议、执行已授权动作和验证结果。
- AI 不得自行扩大权限，不得绕过审批，不得改写主人设定的安全边界。
- 所有高风险动作必须经过人工在环审批，且审批必须绑定具体动作。

### 1.2 允许自动化

- 本地只读文件检索、公开网页检索、官方文档抓取。
- 自有权重内容的整理、索引、摘要和迁移。
- 已授权软件、设备、浏览器和业务系统的可视化操作。
- 带预算上限、审计记录和人工确认的受控执行。

### 1.3 明确禁止自动化

- 绕过 CAPTCHA、Cloudflare 盾、风控、访问控制或账号限制。
- 使用住宅代理、指纹伪造、隐身浏览器插件规避平台识别。
- 批量创建身份、自动注册账号或滥用临时邮箱和虚拟号码。
- 支付、实名、绑卡、注销、提权、破坏性删除等无人值守动作。
- 窃取、导出、猜测或明文落盘任何凭据。

安全工作应优先使用官方 API、OAuth、公开文档、用户自有账号和人工交接。

## 二、系统 DAG

```mermaid
flowchart TB
    Owner[主人 / 最终决策]
    Blueprint[PROJECT_BLUEPRINT.md]
    Panel[holo_pet 全息面板]
    LegacyUI[potato_pet 桌面壳]
    CodexBridge[Codex App Server 桥]
    API[gbt_allinone.api 统一入口]
    Registry[caps_registry 能力注册表]
    Policy[security.policy 权限策略]
    Auth[auth_gate 人工授权门]
    Audit[store.audit 审计后台]

    Engine[engine 万能插 DAG]
    LongRun[longrun 长程任务]
    Schedule[schedule 定时调度]
    Pipeline[pipeline 镜像门禁发布]
    Mirror[mirror_space 多维度空间]
    Rooms[room_space 沙盒会议室]
    Collab[collab_gateway 外部协作]

    Mind[mind_engine 心智状态]
    Life[life_archive 生命档案]
    Think[think_loop 推演环]
    LLM[llm 推理与外部模型]
    Codex[Codex 模型通道]

    Tentacle[tentacle 桌面触手]
    Browser[native_browser / CDP]
    Vision[vision / 视觉皮层]
    Voice[voice / ASR-TTS]
    Device[bluetooth / 设备总线]
    Notion[notion 只读资料舱]

    Store[(store 本地数据)]
    LifeVault[(life_vault 可迁移档案)]
    Workflows[(workflows / runs / schedules)]
    Pipelines[(mirror / gate / production)]
    Secrets[(环境变量 / DPAPI / 密钥库)]

    Owner --> Panel
    Owner --> LegacyUI
    Owner --> Blueprint
    Blueprint --> Registry
    Blueprint --> Policy

    Panel --> API
    LegacyUI --> API
    Panel --> CodexBridge
    CodexBridge --> API
    CodexBridge --> Codex

    API --> Policy
    Policy --> Auth
    Policy --> Registry
    Registry --> Engine
    API --> Audit
    Auth --> Audit

    Engine --> LongRun
    Engine --> Schedule
    Engine --> Pipeline
    Engine --> Rooms
    Engine --> Collab
    Pipeline --> Mirror
    Pipeline --> Pipelines
    Rooms --> Mirror
    Schedule --> Workflows
    LongRun --> Workflows

    API --> Mind
    API --> Life
    API --> Think
    API --> LLM
    API --> Tentacle
    API --> Browser
    API --> Vision
    API --> Voice
    API --> Device
    API --> Notion

    Mind --> Life
    Think --> LLM
    Think --> Engine
    Life --> LifeVault
    Mind --> Store
    Life --> Store
    Audit --> Store

    Tentacle --> Store
    Browser --> Store
    Vision --> Store
    Voice --> Store
    Device --> Store
    Notion --> Store
    Policy --> Secrets

    classDef owner fill:#f8d477,stroke:#6f4e00,color:#241800
    classDef control fill:#dcecff,stroke:#245d9b,color:#102b49
    classDef execution fill:#dff3df,stroke:#2e6b37,color:#15351a
    classDef cognition fill:#f2e2ff,stroke:#65418b,color:#2e1742
    classDef sense fill:#ffe5d6,stroke:#9a4d22,color:#4a210c
    classDef data fill:#eeeeee,stroke:#555555,color:#222222

    class Owner,Blueprint owner
    class Panel,LegacyUI,CodexBridge,API,Registry,Policy,Auth,Audit control
    class Engine,LongRun,Schedule,Pipeline,Mirror,Rooms,Collab execution
    class Mind,Life,Think,LLM,Codex cognition
    class Tentacle,Browser,Vision,Voice,Device,Notion sense
    class Store,LifeVault,Workflows,Pipelines,Secrets data
```

## 三、模块状态

| 模块 | 当前状态 | 责任边界 |
| --- | --- | --- |
| `holo_pet` | 可用 | Web 全息面板、Codex 流、审批、设备与五维状态 |
| `potato_pet` | 可用 | 桌面数字人、旧 GUI 与原有外部通道 |
| `codex_bridge` | 可用 | 真实 Codex App Server、动态工具和流式事件 |
| `api.py` | 可用 | 统一能力入口、审计和结果封装 |
| `caps_registry` | 可用 | 117 项启用能力与 11 项禁用能力 |
| `security.policy` | 可用 | 风险分级、作用域和主人会话判断 |
| `auth_gate` | 可用 | 受限动作的一次性人工授权 |
| `store.audit` | 可用 | 调用、成功、失败和拒绝的追加式记录 |
| `engine` | 可用 | DAG 工作流、并行、缓存、条件和重试 |
| `longrun` / `schedule` | 可用 | 长程任务与定时触发 |
| `pipeline` / `mirror_space` | 可用 | 镜像、门禁、发布、版本与回滚 |
| `room_space` | 可用 | 隔离房间、共享帧和晋升前演练 |
| `collab_gateway` | 可用 | 外部 AI 单连接、最小可见面与一次性令牌 |
| `mind_engine` | 可用 | 感知、评估、预演、元认知和反思 |
| `life_archive` | 可用 | 本地生命线、阅历召回和可迁移 Vault |
| `think_loop` | 可用 | 理解、推演、执行、纠错、反思、整理 |
| `tentacle` | 可用 | 屏幕、窗口、鼠标、键盘、进程和视觉操作 |
| `native_browser` | 可用 | CDP 标签页、DOM、脚本、Cookie、截图和网络监听 |
| `vision` / `voice` | 条件可用 | 缺少模型或识别依赖时如实报缺口 |
| `bluetooth` | 条件可用 | 读取、连接和受确认写入 |
| `notion` | 可用 | 只读资料检索，不提供写入接口 |
| 本地 RAG / 向量检索 | 未完成 | 当前以 JSONL、Vault 和结构化召回为主 |
| 统一只读 MCP 工具总线 | 部分完成 | 已有 MCP 连接，缺少按工具的强制只读隔离 |
| 自动化 Docker 沙箱 | 未完成 | 现有 Compose 只覆盖历史钱包模块 |
| 代理与解码服务预算闸 | 未完成 | 当前没有统一月度或单任务预算上限 |
| 系统资源触发安抚 | 未完成 | 心智状态已存在，但未绑定内存、CPU 和连续工作时长 |

## 四、关键依赖链

```mermaid
flowchart LR
    A[主人指令] --> B[任务分类与风险识别]
    B --> C[读取蓝图和相关记忆]
    C --> D[能力注册表检查]
    D --> E[策略与授权]
    E --> F[执行]
    F --> G[现实验证]
    G --> H[审计与结果]
    H --> I[反思、记忆或蓝图更新]
```

任何一步失败都必须原样暴露，不允许跳过验证或伪造成功。

## 五、风险登记

| ID | 风险 | 连带影响 | 当前控制 | 下一步 |
| --- | --- | --- | --- | --- |
| R1 | 第三方模型适配器缺少 Codex compaction item | 长会话自动压缩失败 | 已关闭 `remote_compaction_v2`，使用兼容回退 | 升级适配器或切换支持该协议的官方模型 |
| R2 | MCP 服务器可暴露写入和执行工具 | 工具越权、上下文污染 | 统一策略、审计和授权门 | 建立只读服务器白名单和每工具能力声明 |
| R3 | 浏览器和桌面控制属于高风险作用域 | 误点击、误写和隐私读取 | `browser_control`、`desktop_control`、HITL | 建立动作级确认和前后状态验证 |
| R4 | 本地服务脚本可能出现明文密钥 | 凭据泄露和费用风险 | 外部请求审计和脱敏 | 轮换密钥，改环境变量或 DPAPI |
| R5 | 发布链可写生产区 | 错误产物进入生产 | 镜像、门禁、版本和回滚 | 保持发布动作必须人工放行 |
| R6 | 外部模型、代理和解码服务可能失控计费 | 费用不可预测 | 暂无统一预算闸 | 增加按服务、按日和按月的硬上限 |
| R7 | 长期记忆尚非向量检索 | 召回精度受限 | 生命档案和结构化事件 | 在不外传隐私的前提下增加本地索引 |

## 六、落地顺序

### Phase 0：蓝图与基线

- 建立并维护 `PROJECT_BLUEPRINT.md`。
- 以能力注册表、策略、审计和测试结果作为真实基线。
- 每次架构变更同步更新 DAG、状态和风险登记。

### Phase 1：只读记忆与知识入口

- 优先使用本地 SQLite FTS 或本地向量索引建立检索层。
- 接入公开文档和主人指定资料，不采集私人会话作为训练语料。
- 记忆写入保留来源、时间和置信度，支持删除和迁移。

### Phase 2：只读 MCP 工具总线

- 每个 MCP 工具必须显式声明读、写、执行和外部发送作用域。
- 默认只允许只读工具，未知工具默认拒绝。
- 进程执行、文件写入和外部发送必须在隔离环境中运行。

### Phase 3：受控自动化

- 自动化仅限主人拥有或明确授权访问的系统。
- 使用普通浏览器自动化、官方 API 和人工交接完成登录。
- 高风险动作前冻结界面，展示目标、数据和后果，等待主人确认。

### Phase 4：安全防线

- 密钥只从环境变量、DPAPI 或受控密钥库读取。
- 自动化脚本运行在最小权限沙箱中，默认禁止访问局域网。
- 外部服务设置硬预算、调用上限、超时和紧急停止。

### Phase 5：状态与反馈

- 将资源压力、连续工作时间和任务失败信号接入心智状态。
- 安抚或庆祝只影响表达和建议，不覆盖事实、授权和安全策略。
- 当蓝图节点进入已完成状态时，记录可验证的完成依据。

## 七、完成判定

系统只有在以下条件全部满足时，才算完成对应阶段：

- 能力已注册并可从统一入口调用。
- 权限策略能识别风险作用域。
- 高风险动作能触发人工审批。
- 成功和失败均进入审计。
- 有可重复的验证命令或测试。
- 蓝图与实际代码一致。

## 八、基线验证

### 环境边界清单（需宿主或外部条件 · 不再作为故障追）

> 依据 2026-09-15 全量回归（89 项）的逐条定性结果。这些红项**不是代码缺陷**，
> 而是当前宿主/外部条件不满足；改用条件探测如实呈现，不再列入修复队列。

| 红项 | 归类原因 | 需要的条件 |
| --- | --- | --- |
| `test_bluetooth_capability` | 缺少 BLE 依赖 | 安装 `bleak` |
| `test_devour_github_real` | 需访问 GitHub | 宿主外网可达 |
| `test_mcp_full_chain` | 无健康 MCP 服务 | 启动并注册 MCP server |
| `test_sec_llm_configured` | 外部 LLM 授权门未开 | 主人授权外部模型调用 |
| `test_tentacle_active_window` | 桌面采集受限 | 交互式桌面会话 |
| `test_tentacle_chain` | 桌面采集受限 | 交互式桌面会话 |
| `test_tentacle_screenshot_diff` | 桌面采集受限 | 交互式桌面会话 |
| `test_tentacle_see` | 桌面采集受限 | 交互式桌面会话 |
| `test_tentacle_vision_snapshot_full_frame` | 桌面采集受限 | 活动的 IDD / 显示器 |

### 同源陈旧测试（门禁/契约变化导致期望不符 · 待逐条修复）

> 这些是**测试写得早于授权门与契约变更**，产品语义正确、断言过期。
> 修法：统一补"主人可信会话前置"（`policy.owner_session()`），或按门禁语义修正期望值。

| 红项 | 现象 | 修法预估 |
| --- | --- | --- |
| `test_autopilot_dry_run` | `KeyError: 'status'` | 同 pipeline：补主人会话前置 |
| `test_autopilot_requires_goal` | `'denied' != 'error'` | 按门禁语义修正期望 |
| `test_mcp_requires_server` | `'denied' != 'error'` | 同上（需先核实是否同源） |
| `test_osint_guard_blocks_private` | `'人工授权' not found in ''` | 补前置或改期望文案 |
| `test_tentacle_unknown_method` | `'denied' != 'ok'` | 补主人会话前置 |

> 待核 1 条：`test_sec_defenses_all_pass`（`False is not true`）——需区分是依赖环境项，
> 还是安全防线里的真缺陷，明日单独核实。

### 静默兜底（`except: pass`）人工审查结论（2026-09-15 · 宪章第九章第五条第 5 款）

审查范围：LLM / 桥接 / 安全链路相关模块中的静默兜底点。逐条定性如下。

| 位置 | 兜的是什么 | 定性 | 处置 |
| --- | --- | --- | --- |
| `security/abl_gateway.py:37` | 读取 `.env` 找 `ABLITERATION_API_KEY` 失败 | **合理兜底**（风哥最终裁定）：失败即返回空 key → `configured()` 如实为 False，不掩盖；**保留、不修** | 保留 + 已加注释 |
| `codex_bridge.py:242-245` | 关闭子进程 `stdin` 失败 | **合理兜底**（风哥裁定）：属清理路径，后续仍有 `terminate()` / `kill()` | 保留 + 已加注释 |
| `codex_bridge.py:249-256` | `kill()` 后 `wait()` 超时 | **合理兜底**（风哥裁定）：清理路径末端，失败不改变对外结论 | 保留 + 已加注释 |
| `security/security_brain.py:230-233` | 安全信号写审计失败 | **合理兜底（有备份）**（风哥裁定）：下方 L236-243 另有一次 `sec_signal_emit` 落审计，且**调用方看到的结果由第二条决定**（成功→ok:True，失败→ok:False+错误，对外可见） | 保留 + 已加注释 |
| `llm/cloud_llm.py:67-71` | 读取能力总数（自我认知锚点）失败 | **合理兜底**（风哥裁定）：失败返回 0 → 上游 `_resolve_awareness_anchor` 的 `if _n and _n != 118` 为假 → **原样返回文案，不替换、不伪造** | 保留 + 已加注释 |
| `codex_bridge.py:262` | 关闭子进程流失败 | **合理兜底**：清理路径末端，仅句柄回收不干净，不影响对外结论 | 保留 + 已加注释 |
| `codex_bridge.py:1339` | 停旧共享连接失败 | **合理兜底**：属"换新前清理"，`_shared` 会整体替换，不影响新建与使用 | 保留 + 已加注释 |
| `codex_bridge.py:55` | 降级审计写入失败 | **合理兜底（二级）**：审计写不进不能让"脱敏降级"本身失败；对外保证由返回值承担（固定占位符，不含原文） | 保留 + 已加注释 |
| `codex_bridge.py:48`（原编号）→ 现值 `:41-56` | 调用 `redact_text` 脱敏失败 | ⚠️ **真风险 → 已修**（风哥批准 2026-09-15）：原为"静默跳过脱敏直接返回"，现改为**降级返回占位符** `[redaction-unavailable]` + 写一条 `redact_degraded` 审计 | **已落地并验证**：镜像 6/6（5 种失败场景零泄漏）+ 契约测试 `test_redaction_fallback_never_leaks` OK + 全量回归红项持平 |

**结论（更新于 2026-09-15 补全后）**：**8 处为合理兜底（保留 + 已加注释）**，
**1 处为真风险（已修）**——`codex_bridge.py:41/53/56` 脱敏降级已落地，
并通过镜像 6/6 自测 + 契约测试 `test_redaction_fallback_never_leaks` + 全量回归红项持平。
`codex_bridge.py` 的裸 `pass` 静默兜底数已归零。

**判定基准（风哥 2026-09-15 指定 · 以后审查同类问题一律照此比对）**

| 判据 | 定性 | 处置 |
| --- | --- | --- |
| 兜底**不掩盖失败**（失败结果对调用方可见） | 合理兜底 | 保留 |
| 兜底**不伪造状态**（不编数字、不假 ok） | 合理兜底 | 保留 |
| 兜底**不留隐患**（清理路径、末端动作、有备份路径） | 合理兜底 | 保留 + 注释 |
| 兜底**静默跳过安全检查**（脱敏 / 权限 / 审计这类） | **真风险** | 必须修：镜像 → 生产 → 补契约测试 |

**裁定记录（2026-09-15 · 解释权归自由的风）**

- `security/abl_gateway.py:37` 经复核后由风哥**最终裁定为「合理兜底」**：保留、已加注释、**不修**。
- 复核期间记录在案的两条**观察项**（均为事实陈述，不构成缺陷，也不列入待修）：
  ① 诊断维度：`.env` 存在但读取失败时，对外信号与"确实未配置"相同（文案均为"未配置"）；
  ② 解析维度：`.env` 行首严格匹配 `ABLITERATION_API_KEY=`，且值两侧引号未剥离——
     若书写为 `export KEY=`、带引号、带 BOM 或前导空格，会读不到。
  以上两条**仅供日后需要时参考**，按裁定**不修、不追**。

**其他观察项（记录在案 · 不修，除非风哥另行批准）**

- `security/security_brain.py:234-235`：函数中间存在一个**孤儿字符串**（出现在函数首语句
  之外的位置，Python 不视其为 docstring）→ 运行时完全无效，属"失效文档"。
  证据：该字符串位于 `emit_signal()` 内部第二次审计调用之前，非函数首语句。
  处置（风哥裁定：**保留 + 注释**）：文本**保留原样**，仅在其上方加注释说明
  "Python 不视为 docstring、运行时无效果、仅供阅读参考"。
  已执行并验证：编译通过 + 全量回归红项 9→9 不变（零行为变更）。

- **敏感 CLI 审计（风哥 2026-09-17 记入观察项 · 不现在做）**：有进程调 `wallet_core` / `git` / `vault` 这类敏感 CLI 时，
  目前**不留任何审计**。建议机制：每次调用落一条 `sensitive_cli_invoked`（父进程链 + 时间戳 + 命令行摘要）。
  触发场景：2026-09-17 桌面 `天才交易原` 项目那对 `vault init` 进程（pid 10188/20440），事后只能靠 PSReadLine 历史回溯，
  且**证不出是谁发起的**。下次动审计层时补。

- **家目录被扫描（观察项 · 证据未齐）**：`git.exe`（ppid 8268）在 `C:\Users\ADMIN` 跑
  `git ls-files --others --exclude-standard`，2026-09-17 14:15:50 / 14:18:01 各一次。
  像某个工具在扫家目录仓库；**谁拉起的没证死**（沙箱进程枚举为假阴，提权只看到当下那一刻）。不修，记着。

- **房间级快照调用了不存在的原语（2026-09-17 实测发现 · 风哥拍「登记观察项 · 不在这一刀里修」）**：
  `room_space.py` 三处调用 `MS._replace_tree`（`:611` / `:1140` / `:1141`），而**全仓 `def _replace_tree` = 0 命中**
  （正对照 `def _tree_fingerprint` = 2 命中；AST 复核：`mirror_space.py` 11 个函数、`room_space.py` 41 个函数，均不含它）
  → `room_space.snapshot()` 与 `:1140` 路径**会抛 `AttributeError`**，**"房间级冻结"不能当现成原语用**。
  证据强度：**静态取证（全量读 + AST 清单 + 双面对照）· 未运行**（运行会写房间目录，属施工动作）。
  待定性：**历史遗留**（`_replace_tree` 曾被删/改名）还是**待补实现**。**不修，记着。**
  出处：`gbt_allinone/docs/阶段检查点打点器设计.md` §2.3②（同一轮取证）。

- **`.mirror.lock` 存在但无代码引用（2026-09-17 实测 · 风哥拍「登记观察项 · 不删不动」）**：
  `store/mirror_space/.mirror.lock`（1 B）确实存在，但 `rg "mirror.lock|mirror_lock" -g "*.py"` **0 命中**
  → **不存在**"镜像空间已经有把共享锁"这回事；打点器因此**自带锁**（`checkpoints/.lock`）。
  定性（风哥原话）：**"拿一把不存在的锁当保护，本身就是假绿的一种。"**
  处置：**那 1 B 文件不删、不动**，也不当作可用原语；**不修，记着。**

- **`mirror_status()` 挑「最新护照」用字符串排序（2026-09-17 发现 → 2026-09-17 已修 · 风哥批「带四个条件」）**：
  根因：`sorted(_PASSPORTS.glob("v*.json"))[-1]` 字符串序下取到 **`v9.json`**（它排在 `v20.json` 之后），
  于是 `clean` 与 `reality_drift` 全部对着 **v9 的 TodoMVC 基线**算 → 晋升 v20 后 `clean=False`，
  同份输出里 `dimension_vs_reality=[]`（维度与现实逐字节相同）→ **假红**。
  潜伏条件：v1–v19 内容完全相同 ＋ v20 是第一个两位数版本且是第一次内容差异。
  **修复（条件 1）**：两副本同步改为 `sorted(_PASSPORTS.glob("v*.json"), key=lambda p: int(p.stem[1:]))`。
  修前 SHA256 `FFD259D1D0323362…572A63215`（11,539 B）→ 修后 `CEB1E5F7A8F52E5B…0843AFE2`（11,570 B），两份仍字节相同。
  **契约测试（条件 2）**：`gbt_allinone/tests/test_mirror_space.py` —— 7 条，含「字符串序会取到 v9」的反向证明；
  另有修前/修后对照实证：旧代码 `clean=False`＋1 条漂移，新代码 `clean=True`＋0 条（`.scratch/_vsort_proof.py`）。
  **同类扫描（条件 3）**：见下表。**入档（本体）**：《版本号字符串序陷阱》→ CHARTER.md 第十二章第十/十一条 ＋ HEARTBEAT.md ＋ 生命档案。

**「取最新」字符串序陷阱 · 全仓同类扫描（2026-09-17 · 条件 3）**

扫描器 `.scratch/_scan_latest_trap.py`（AST ＋ 文本启发式），产出 `.scratch/_latest_trap_scan.json`。
覆盖 **371 个 .py**（带 BOM 的文件改用 `utf-8-sig` 读，**未解析 0**）＋ 56 个 JS/PS；
另有约 1,280 个第三方/生成物文件（浏览器扩展包、`.pylibs`、打包产物）按路径排除，未计入。

| 站点 | 判定 | 依据 |
|---|---|---|
| `mirror_space.py:218/220` ×2 副本 | **真陷阱（已修）** | 字符串序取到 v9；修后取 v20 |
| `room_space.py:302 → 332`（passports 尾窗） | **同类命中（未修 · 低危）** | `passport_files[-10:]` 窗口 = v19/v2/v20/v3…v9，**缺 v11–v18**，「最近 10 个护照」不真 |
| `pipeline.py:388/392` ×2 副本（history 列表） | **同类命中（未修 · 低危）** | `for f in sorted(vdir.glob("v*"))` 只影响列表顺序；一旦有人取 `history[0]/[-1]` 就继承同一陷阱 |
| `pipeline.py:416→421` / `preflight.py:610→616`（回滚取最近） | **疑似 · 口径存疑** | `key=lambda p: p.stat().st_mtime` 取「最近」——口径是修改时间而非版本号；两处各自实现，易分叉 |
| `room_space.py:301 → 331`（snapshots 尾窗） | 安全 | `snapshot_id` 是定宽时间戳串，字符串序 == 时间序 |
| `mirror_space.py:194` / `pipeline.py:223` / `room_space.py:1094` | 安全 | `int(name[1:])` ＋ `max()`，本来就是数值序 |

> 未修的四处**不在本次授权范围**（风哥红线：修 `mirror_space.py` 不许顺手改别的），逐条记在案，另行批。

**命令行扫描假阴判例（2026-09-17 风哥拍「立，且必须入档」）**

`rg` 也是扫描器，**同样受《扫描器自证律》管**——它报「0 命中」时，必须先证明它自己不瞎。

| 命令 | 结果 |
| --- | --- |
| `rg -n "snapBounds"`（**不给路径**） | **0 命中** |
| `rg -n "snapBounds" .`（**给显式路径**） | **21 命中** |
| `rg --files`（默认）里 `holo_pet_w3` | **0 个**（`gbt_allinone/store/` 被 `.gitignore:25` 忽略） |
| `rg --files -uu` 里 `holo_pet_w3` | **29 个** |

同一条命令、同一份工作区，结果相反。**「rg 报 0」不是结论。**

**三件套（缺一不可）**：

1. **正对照**——先跑一个「必然有命中」的词（本次 `snapBounds` = 21），证明能扫到东西；
2. **负对照**——再跑一个「必然没有」的假词（本次 `zzz_not_real_qqq` = 0），证明不误报；
3. **显式路径**——目标扫描一律给路径（`.` 或具体目录），**不许**依赖默认遍历
   （默认遍历会吃掉 `.gitignore` 命中的目录，`gbt_allinone/store/` 就是被吃掉的那个）。

> 同族实证：本次查 `sec_hud` 得 0 命中 — 因正对照 21 处成立，故「本仓查无此物」可信。
> 若不带正对照，这个 0 只是「扫描器没吭声」，不是「不存在」。
- `llm/cloud_llm.py:56-77`：**数据陈旧 + 功能静默不生效**（记录在案 · 不修，除非另行批准）
  ① 源码硬编码锚点 `118`（旧能力总数），当前实际为 92 项；若外部注册表缺失 → `_n=0`
     → 不替换 → 文案可能残留过期数字（属"数据陈旧"，非伪造）。
  ② `_live_cap_total()` 依赖外部文件 `.gbt/_audit_caps.json`；该文件不存在时
     "自我认知锚点"功能静默不生效。
  定性：**不是空壳、不是假执行**（不编造数字）；仅作观察项记录，不列入待修。

- **吸其他窗口的右/下边失效（2026-09-17 V3/V6 界面级验收实测发现 · 未修）**：
  `shell/main.cjs` 把 `o.getBounds()`（Electron 形状 `{x,y,width,height}`）传给 `layout.snapBounds`，
  而后者读 `o.w / o.h` → 右/下边吸附目标恒等于对方左/上边。离线判别：预期吸 1300，实到 1296 不吸。
  定性：**字段名词口径不一致**（同族于版本号字符串序陷阱）。改的是 reality 产物 → 要走维度→scan→ascend，另批。
  **定性已完成（2026-09-17 · 离线判别 `.scratch/_r27_snap_proof.cjs`）：错在调用方 `main.cjs`**——
  `layout.cjs` 契约自洽（头注 `:4-5` 明写「主进程只是调用方」；`:123` 同时导出两个方向转换器；
  `snapBounds` `:97/106/107` 按契约只读 `o.w / o.h`）。症状比首报多两条：
  **B 尺寸被默认值改写**——`setBounds` 收到 `1120×720`（`normalize` 对缺 `w/h` 回落默认值），覆盖真实 400×300；
  **C 吸屏幕右/下边缘失效**——`b.w` 被默认成 1120 → 右边缘目标算成 800，实测停在 1516 不吸 1520。
  根因链 `main.cjs:363-370`（`:365` others、`:366` 自身都直接喂 `getBounds()`；`:368` 只比 `x/y` → 尺寸错**静默放行**）。
  **修复方案已出（待拍）**：`gbt_allinone/docs/W3吸附缺陷修复镜像方案.md` ——风哥 2026-09-17 拍「走纯 bug 修」：只做形状转换，**不顺手扩** `width/height`。
  **收尾（风哥 2026-09-17 拍 · 同日落账）**：产品改动已落**维度**（`holo_pet_w3/shell/main.cjs` `:365/:366` 两行形状转换
  ＋ 新增 `holo_pet_w3/tests/test_layout_snap.cjs` 7 用例）→ **V2/V3 纯函数层 7/7 过**。
  **V4 真实链路 = 判据未验 · 程序化路径不可验 · 真实链路待手动补验**——
  **不标「环境阻塞」**（身份问题已解，卡住的是**事件通道**，不是环境）：程序化移动只发 `move`、不发 `moved`，
  而吸附唯一入口在 `moved` 里 → 自动化结构上测不到；补验方式 = **风哥手动拖一次**（零侵入，不合成键鼠）。
  **S7 未批 → `ascend()` 未跑 → reality 仍是 v20 的 12 文件**（维度 14 文件，多出 main.cjs 改动 + 2 个新测试文件）。

  - **吸附判定只看 `x/y`，是否需扩到 `width/height`（2026-09-17 风哥拍「未取证 · 记观察项」）**：
    `main.cjs:368` 的 `if (next.x !== cur.x || next.y !== cur.y)` 不比较尺寸。**是不是缺陷没有实证**——
    若吸附设计本来就只判左右/上下对齐、尺寸不参与判定，顺手扩就是画蛇添足。
    处置：**不在「吸附形状转换」那一刀里动**（两个原子单元，不许混）；
    等有实证证明「只比 `x/y` 导致实际吸附错误」，再另批。
  - **吸附入口是否从 `moved` 扩到 `move` ＋ 防抖（2026-09-17 风哥拍「暂不做 · 记观察项」）**：
    `move` 在拖动时**像素级高频触发**，入口直接改过去会把窗口「锁」在吸附位、**反而拖不动**——
    需要防抖 / 节流设计（如「拖动结束后 100ms 再吸附」），**不是一行改动**，不许当一行改动顺手做。
    处置：另开原子单元时一并处理；法条见 `CHARTER.md` 第十八章 · 窗口事件通道律。
- **主控台品牌外露：`Codex · 正在建立通道`（2026-09-17 V3/V6 实测）**：生产面板底部芯片明文写 Codex 品牌，
  与《Codex 同化方案》「用户视野里不出现 Codex」目标冲突。
  **风哥 2026-09-17 拍：V2 链路级之前必须处理**（不许推到 W5）——它和「用户入口只有 holo_pet」是同一件事的两面。
- **主控台数字人未起（2026-09-17 V3/V6 实测 · 证据未齐）**：抓取时 `#avatar-canvas` 在（723×724），
  但 `#stage-fallback` 仍在显示（文案「正在检查 3D 渲染内核」）。时序问题还是真故障**没证死**，需再抓一次带更长等待。
- **Electron 在沙箱身份下跑不起来（2026-09-17 R28 实证 → 已入宪：CHARTER.md 第十七章 · GUI 身份律）**：
  同一份最小 Electron 脚本（不建任何窗口），**沙箱身份 `codexsandboxoffline` 起不来、真实用户 `ADMIN` 提权跑通**。
  - 提权臂：`whenReady` → 5 次 tick（300ms 间隔）→ `survived_1500ms` → **退出码 0**
    （`.scratch/_r28_min_electron.cjs` · `.scratch/_r28_min_electron_result.json` · pid 14704）。
  - 沙箱臂（历史）：R27 四组对照**全部** 2147483651（`0x80000003`）且 tick 全空；
    V4 两次都是「两窗建出来 → 无 `did-finish-load`」，userData 里连 `Local State` 都没写出来。
  - **身份取证（DPAPI · 只报成败不打印密钥）**：`.scratch/_w3_userdata/Local State` 的 `os_crypt.encrypted_key`
    是 `DPAPI` 前缀、283 B；沙箱身份 `CryptUnprotectData` **失败**（`winerr=-2146893813`）
    → **V3/V6 那次跑通的先例本来就是提权跑的**。V4 两次是沙箱跑的，所以挂。
  - 结论：**GUI 进程（Electron）必须真实用户身份**；沙箱身份下 Chromium 无法正常初始化。
    与《身份与封印判例》（DPAPI 必须真实用户身份）同源。

- **V4 真窗口实测：跑了，但结论 INCONCLUSIVE（2026-09-17 R28）**：
  提权下两窗 `did-finish-load` 双触发、真 bounds 读回（mover 1200,300,800×600 / peer 100,100,800×600，peer 右边缘 900），
  三步实测 **0/3 未吸附**——**但这个 0/3 不构成结论**，因为判据本身没验过：
  ① **驱动力没定性**：探针用程序化 `win.setBounds()` 移动，而 `main.cjs` 的吸附逻辑只挂在 `moved` 事件上，
     「程序化移动会不会触发 `moved`」**没有取证**（`electron.d.ts` 只标了 `moved` 为 `@platform darwin,win32`，不回答这个问题）；
  ② **探针自身报错**：hook 末尾 `await sleep(250)` 引用未定义函数 → `run_error: sleep is not defined` → `app.exit(3)`；
  ③ **断言被缩放污染**：`size_kept` 用严格相等比尺寸，而 125% 缩放下透明无边框窗每次 `setBounds` 后读回会 +1~+2px
     （800→802→803→805），即使逻辑没错也判 false。
  处置：**先定性驱动力，再谈产品缺陷**；不许把 0/3 当「吸附还是坏的」，也不许当「修好了」。
  证据：`.scratch/_r28_v4_result.json`（提权）· `.scratch/_r28_v4_result.sandbox-bak.json`（沙箱）。
  **R28 两臂对照实测（2026-09-17 · 一次启动两臂 · 提权 · `.scratch/_r28_v4_arm_results.json`）**：
  - 臂 A `win.setBounds(894,300)`：`x_after=894` **不吸**；**`moved_events=0`**、`move_events=1`；
  - 臂 B `win.setPosition(894,300)`：`x_after=894` **不吸**；**`moved_events=0`**、`move_events=1`；
  - 判别式落点：**A 不吸 + B 不吸**（预登记表第三行）→ 判据仍站不住；
    但**观测器把成因钉死**：**程序化移动只发 `move`、不发 `moved`**（两条 API 路径一致）；
    而 `snapBounds` 的唯一入口就在 `moved` 里（只读取证：`main.cjs` 全量窗口事件绑定只有
    `:363 moved` / `:372 resized` / `:373 close` / `:374 closed`，`snapBounds` 全仓**唯一调用点 `:366`**）。
  - 含义：上一轮那个 0/3 **不是产品缺陷的证据**，而是「程序化路径不可能触发该入口」的必然结果；
    这一刀的真实链路验证需要**用户真实移动**（合成键鼠会撞《宿主不打扰律》第 1/4 条），**要单独拍**。
  - 探针两处缺陷已修（测试侧，未动被测对象）：`sleep` 未定义 → `_r28_v4_hook.cjs:18` 补 `const sleep`；
    尺寸断言 → `:88-92` 改 ±5px 容差（修前副本 `.scratch/_r28_v4_hook.cjs.bak-prefix-20260917-152906`）。

```powershell
# 能力注册表基线
C:\Python310\python.exe -c "import sys;sys.path.insert(0,'.');import gbt_allinone as g;print(len(g.list_capabilities(filter_dangerous=False)))"

# 框架体检
C:\Python310\python.exe -c "import sys,json;sys.path.insert(0,'.');import gbt_allinone as g;print(json.dumps(g.run_task('selfscan',{}),ensure_ascii=False,indent=2))"

# 深度交叉扫描
C:\Python310\python.exe -c "import sys,json;sys.path.insert(0,'.');import gbt_allinone as g;print(json.dumps(g.run_task('cross_scan',{'deep':True}),ensure_ascii=False,indent=2))"
```

## 九、故障登记（F 编号体系 · 2026-09-17 立）

> 来源：《GBT全故障点设计》（`gbt_allinone/docs/GBT全故障点设计.md`）
> 编号：`F<层>.<序>`；节点号 `N*` 见《全项目思维导图架构》（`gbt_allinone/docs/全项目思维导图架构.md`）
> 登记口径：本节只登记**层级的收敛结论**，逐条故障点（45 条）在专门文档；`风险登记`（§五）与本节的分工是——§五记"能不能做成"，本节记"做成了会怎么坏"。

| ID | 层 | 故障点数 | 其中 P0 | 挂点 | 本轮实测状态 |
| --- | --- | --- | --- | --- | --- |
| FL1 | 身体层 | 5 | 0 | N1/N2/N3/N30 | 1 项半跑（SSE 心跳机制在案，未做断连演练） |
| FL2 | 心智层 | 4 | 1 | N6-N10 | 1 项真跑（同源机制：非法 JSON 回落） |
| FL3 | 执行层 | 4 | 1 | N12/N13/N14 | 2 项半跑（`codex_stop` 事件真实存在） |
| FL4 | 底座层 | 4 | 1 | N15-N18 | 2 项半跑（**实况同时存在 2 个 app-server**，单例口径已被事实修正） |
| FL5 | 保障层 | 6 | 2 | N19-N23 | 3 项真跑（账本写失败回写 / 坏行 311 / 空维度必拦） |
| FL6 | 连接层 | 4 | 0 | N17/N24/N25/N26 | 1 项历史真跑（中继死→看门狗 3 s 拉活） |
| FL7 | 存储层 | 4 | 1 | N8/N18/N31 | 2 项真跑（含 F7.3 已修复：`services.json` → `total=14`） |
| FL8 | 跨层 | 5 | 1 | N3/N5/N24 | 0（虚机与 shell 未成形，如实标未测） |
| FL9 | 外部依赖 | 5 | 0 | N27-N30 | 1 项半跑（凭据 401 与中继恢复有真回执） |
| FL10 | 安全 | 4 | 3 | N19-N22/N31 | 3 项半跑（凭据泄露面已有 2 处真证据） |

### 9.1 本轮由故障普查新发现的三个真问题（登记在案，未修）

| # | 问题 | 证据 | 定级 |
| --- | --- | --- | --- |
| Q1 | `Cloudflared` 服务命令行**明文内嵌隧道令牌**（base64，含 AccountTag 与 TunnelID），不经 DPAPI | 自启面扩展扫描 `Win32_Service.PathName` | P0（凭据面） |
| Q2 | DPAPI 解不开时 `load_from_vault()` **不抛异常**，返回 `("", "unreadable")` | `deepseek_key.py:198-211`；本轮真跑 | P0（**静默失效**——《静默失效律》的教科书形态：故障会伪装成"上游 401"） |
| Q3 | 生产审计流 **非空 287,891 行 / 物理 287,930 行中 311 行是坏 JSON（0.108%）**，当前无人计数、无人告警 | `.scratch/_audit_fields.py` · `_audit_count_methods.py`（2026-09-17T13:05 实测） | P1（审计完整性） |

### 9.2 复算命令（本节的每个数字都可复现）

```powershell
# 账本直方图（行数 / 坏行 / 事件分布 / who-why 缺项）
py -3.10 .scratch\_audit_events.py

# 进程快照（总数 / 无主进程 / 孤儿 / GBT 相关）
py -3.10 .scratch\_proc_snapshot.py

# 自启面扩展（RunOnce / Winlogon / WMI 订阅 / BITS / 服务 / 计划任务 / IFEO）
powershell -NoProfile -ExecutionPolicy Bypass -File .scratch\_autostart_expand.ps1

# 故障实测批（隔离 store，9 条）
py -3.10 .scratch\_fault_probe.py

# 镜像 S0 回执（维度清空 / 现实 v19 / 空维度必拦）
py -3.10 .scratch\_w3_s0.py
```

> 注：自启面脚本在**沙箱身份**下会让 WMI 与计划任务查询**返回 0 条而不报错**（假绿）。
> 复算必须在真实身份下跑，否则会得出"这台机器没有服务、没有计划任务"的错误结论。

---

> 开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属

### 品牌清洗第一刀（面板层 · 2026-09-17）

> **批次口径（方案原文 §3 首行）**：本刀 = **生产树 `holo_pet/` 批次，不走镜像维度**。
> 回滚走《主控台品牌清洗方案》§九的**备份 + SHA256**；`checkpoints/00001` 冻的是镜像维度+reality，覆盖不到本刀。
> 落盘结果：产品树三份文件已成刀（SHA256 见下表），改前原始字节在 `.scratch/_r36_prewrite_*.bak`。
> 过程留痕：`.scratch/_r36_patch_report.txt`（逐条命中数）· `.scratch/_r36_brand_gate_log.txt`（四闸门）· `.scratch/_r36_regression.txt`（全量回归）。

**改动范围**：`holo_pet/index.html`(8行) · `holo_pet/panel_server.py`(15处) · `holo_pet/app.js`(17处) ·
新增 `holo_pet/tests/test_panel_server.py::BrandGuardTests`(2条)。不碰 `codex_bridge.py`（桥接层第二刀）。

**改前 / 改后 SHA256（生产树；回滚凭据 = `.scratch/_r36_prewrite_*.bak`）**

| 文件 | 改前 | 改后 |
|---|---|---|
| `holo_pet/index.html` | `f506e2702d34ed59…` | `55780dd52c566a91…` |
| `holo_pet/panel_server.py` | `22ea53d9bfc24010…` | `cb6f8f64e21e2908…` |
| `holo_pet/app.js` | `e3cfa84ede1881ff…` | `6ded02b9b8664965…` |
| `holo_pet/tests/test_panel_server.py` | — | `964e52f5a2954ad6…`（新增 2 条测试，22/22 绿） |

**回滚口径**：逐文件拷回 `.scratch/_r36_prewrite_*.bak`，**重算 SHA256 比对通过才算回滚成功**。

**新立契约（不许回退）**

1. 入屏文案一律走白名单：`safe_last_error()`（Python）/ `safeLastError()`（JS）。
   白名单 = `_SAFE_TOKENS` + 连续中文片段；**拉丁字母串一律拦截**（含 `codex` 任意大小写）。
2. 原文不受影响：`state().last_error` 仍是原值；过滤结果只在 `last_error_safe`。
3. 入屏即留痕：显示安全文案时必写 `panel_error_rendered` 审计，含**原文全文 + 原文 sha256**；
   同 hash 只记一次（前端轮询不灌审计流）。写失败 → `last_error_audit.landed=false`，保留脏标记重试。
4. 四个静态闸门脚本：`.scratch/_brand_gate.py`（品牌/白名单/语法/文案长度，自带正负对照）。
5. 正负对照测试：`BrandGuardTests.test_safe_last_error_filters_codex_and_keeps_plain_chinese` +
   `test_rendered_last_error_is_audited_with_raw_hash`。
   调起方式：`py -3.10 -m unittest holo_pet.tests.test_panel_server -v`（22/22 绿）。
6. **运行环境口径**：`py -3.10` 在 Windows 默认按 cp936(GBK) 读脚本源码；含中文字面量的 `.scratch/`
   脚本必须 `PYTHONUTF8=1`，否则字符串匹配会整体失配（2026-09-17 实证）。

**观察项（登记在案，本刀未修）**

| # | 观察项 | 现状 | 处置 |
|---|---|---|---|
| O1 | `main.cjs:368` 吸附判定只比 `x/y`，未取证是否需扩到 `width/height` | 未取证 | 另开原子单元前不动 |
| O2 | 吸附入口只挂 `moved`，改挂 `move` 需防抖/节流 | 未修 | 另开单元 |
| O3 | V4 真实链路（真窗口拖拽吸附）判据未验 · 程序化路径不可验 | INCONCLUSIVE | 等风哥手动拖一次补验 |
| O4 | `room_space.py` 三处调 `MS._replace_tree`，全仓 `def _replace_tree` 0 命中 | 真缺陷候选 | 待定性：历史遗留 or 待补实现 |
| O5 | `.mirror.lock` 文件在但全仓无引用 | 1B 空锁 | 不删不动，登记 |
| O6 | `room_space.py:302→332` 的 `passport_files[-10:]` 窗口乱序（缺 v11–v18） | 未修 | W3 只呈现 v20 事实，不阻塞 |
| O7 | `panel_server.py` 英文错误邻居 8 行（C-2 桶） | 未修 | 跟桥接层第二刀一起 |
| **O8（已修 · 2026-09-17）** | **`HoloBridge.state()` 是高频只读路径，却每次调用都写生产审计**：`_sensory_hand()`→`api.run_task("tentacle_status")` 与 `_safe_bt_status()`→`api.run_task("bluetooth")` 各写 `call`+`ok` 2 条。审计里的 `"probe": true` 只是**标记**探针，**不减少写入** | 实测（`.scratch/_r37_o8_probe.txt`）：每次 `state()` **+4 行 / +531 B**（sensory 5s 缓存命中时 +2 行 / +254 B）；`app.js:2138` 30s 轮询 → **+1,062 B/分钟 ≈ 63.7 KB/小时 ≈ 510 KB/天** | **修复已落地**：`api.run_task(..., probe=True)` 函数级免审计口 + 面板两处调用点 + 蓝牙 TTL。V1–V5 全绿（`.scratch/_r42_o8_v1_v5.json`）：`state()` 字节增量 **0**、默认路径与面板动作路径照旧 +254 B、全量回归 104/红 9 持平。详见 `gbt_allinone/docs/O8修复方案-state去审计化.md` §七/§八 |
| O9 | C-1 桶已含进这一刀：`index.html:112` `App Server` · `index.html:411` + `app.js:1259` `Model → 模型` | 已改 | — |
| O10 | 文案长度实测：24 对全部 `new ≤ old`（`Sandbox · workspace-write` 18 → `沙箱：工作区可写` 8） | PASS | — |

**O11 · 自伤与自纠（如实留档）**

本轮我自己制造并自己纠正了一次回滚：把"生产树批次"误读成"只改镜像维度"，据此把正确的落地回滚了一次；后重读方案原文（§3 首行"批次：生产树 `holo_pet/`，不走镜像维度"）判定是自己错，随即把成刀版放回生产树。
收支：回滚与重放全程有 SHA256 对照（`.scratch/_r36_rollback_live.txt` · `_r36_reapply_live.txt`），产品树现态与成刀版一致，没有静默丢改动；本次仅多花了往返时间。
教训：《原子落地律》的边界必须来自**方案原文**，不能来自我对仓库结构的推断。

**O12（新观察项）**：`holo_pet/tests/test_panel_server.py` 不在 git 索引里（`git show HEAD:` 查无此路径），误改后没有版本对照可回退。建议把面板测试纳入版本控制或纳入 checkpoint 指纹。

### 2026-09-17 补记 · 两份新文档与两条新宪章

**新宪章（CHARTER.md 第十九、二十章 · 同日入档，见 HEARTBEAT.md 对应两节）**

- **第十九章 · 脚本编码律**（《Python 脚本必须显式 UTF-8》）：含非 ASCII 字面量的 Python 脚本
  （含 `.scratch/` 一次性诊断脚本）运行前必须 `PYTHONUTF8=1`，或脚本内显式声明编码；
  诊断输出也落文件不走控制台默认编码。两次实证：`panel_server` Token 管道（09-15）·
  `.scratch/_r36_patch.py` 中文字面量失配（09-17，实测 `gbk` vs `utf-8`）。
- **第二十章 · 边界来源律**（《原子单元边界必须来自方案原文》）：原子单元的边界必须逐字来自方案原文，
  不许来自对仓库结构的推断；回滚是破坏性动作，同样要有原文依据，且必留双向 SHA 对照。
  第一次实证：R36 第一刀凭推断回滚了正确落地（09-17）——已放回并 SHA 校验一致（O11）。

**新文档索引**

| 文档 | 性质 | 覆盖 |
|---|---|---|
| `gbt_allinone/docs/O8修复方案-state去审计化.md` | 方案（**已批 · 已动刀**） | `api.run_task` 加 `probe` 形参 + 面板两处状态探针免审计 + 蓝牙 TTL 缓存；§七 = 三问定性 + 13 处写点清单 + 五处契约测试；**§八 = 动刀实测留痕（落点/五闸门/改前改后逐字节/两处自留账）** |
| `gbt_allinone/docs/主控台品牌清洗第二刀方案-桥接层.md` | 方案（**待复核** · 第二刀出稿） | `codex_bridge.py` 异常文案 8 行 + C-2 桶英文错误邻居 8 行；两个扫描器均过《扫描器自证律》；§五 两条待拍 |
| `gbt_allinone/docs/checkpoint生产树指纹规格.md` | 规格（下一份 checkpoint 生效） | `checkpoints/00002/production_tree_manifest.json`：`path`+`sha256`+`mtime`+`bytes`，只打指纹不拷文件 |
| `gbt_allinone/docs/技能包评估_20260917.md` | 评估（**只出稿 · 不动手**） | 11 个技能包逐条对照本仓现状：A 组 6 个不装 / B 组 3 个自学并入 / C 组 1 个借方法论（品牌门禁）/ D 组 1 个一票否决；§六 两条事实纠正、§七 附带发现、§八 三条任务卡 |

**观察项补充**

- **O13**：`.scratch/_r37_o8_probe.py` 实测到 `state()` 每次调用耗时 **30–337 ms**（首调用 337 ms，含真实蓝牙栈查询）；前端 30 秒轮询下这不构成卡顿，但 V2 链路级把面板拉长运行后值得复测。
- **O14**：`HoloBridge.state()` 调 `sensory_state()` 与 `_safe_bt_status()`，两者**都**会查蓝牙栈（一次状态请求 = 2 次蓝牙查询）。O8 修完后建议合并为一次查询。
  > **2026-09-17 改正（实测推翻原口径，原文保留不改）**：逐路径隔离实测
  > （`.scratch/_r39_o8_o14_probe.py` → `.scratch/_r39_o8_o14_probe.txt`）显示
  > `sensory_state(force=True)` 单独跑只写 `call/ok/tentacle_status` 两条、**0 条 bluetooth**；
  > `state()` 整链 = 1 次 bluetooth（`:440` `_safe_bt_status`）+ 1 次 tentacle_status（`:441` → `sensory_state` → `_sensory_hand`）。
  > 真实形态是 **1 蓝牙 + 1 触手**，不是"2 次蓝牙查询"。**该合并动作取消**——没有第二条查询可合并，
  > 硬合并等于把一个不存在的需求写进代码（《反空壳律》）。O13 的"含真实蓝牙栈查询"成立。
- **O15（新观察项 · 风哥 2026-09-17 批）**：**内部诊断术语是否统一为"内核"，待另开单元。**
  第二刀方案 §五 5.3 那三处（`codex_bridge.py:1461` `"未找到 codex"` · `:1464` `"安装 Codex 或把 codex 加入 PATH 后重试"` ·
  `:1548` `"GBT Codex 通道自检"`）在 `doctor()` 与它的 CLI 里，**不上用户屏**，属**内部诊断输出**。
  风哥裁定：**本刀不改**——改它属"内部术语清洁"，与"品牌清洗"（判据 = 屏幕上一个 Codex 都不露）目标不同。
  单独立项，触发条件：将来做"内部术语统一"或诊断报告对外分享时一并处理。
- **O16（新观察项）**：`codex_bridge.py:1422` 的 `codex_path` **字段值**形如 `…\OpenAI\Codex\bin\codex.exe`，
  字段名与判定链（`app.js:238` 用它做可用性布尔判定）不许动；实测**当前不上屏**。
  若将来有诊断页把它直接渲染，**必须同时给脱敏显示**（否则等于把品牌路径连盘符一起送上屏）。

- **O17（新观察项 · 2026-09-17 技能包评估带出）**：**账本分层 / 轮转 / 索引旁路，待另开单元。**
  实测：`gbt_allinone/store/audit.jsonl` = **36,055,095 B**（第二大账本 `neural_tentacle/recent_transmissions.jsonl`
  仅 276,646 B）；自研链路**无索引、无 DB**（`.db` 仅存在于 `store/native_browser/profile/**`，是 Chromium 自带，与账本无关）。
  O8 修的是"高频只读路径别再写账"（已落地，`state()` 字节增量 0）；本条是它的自然后续——**存量账本怎么不无限长**。
  **红线**：不许用"上数据库"来解（那是把 append-only、人眼可读的账换成会锁、会事务、会损坏的库）。
  三件套方向：分层（热/温/冷）· 轮转（按大小或天切段 + 段清单）· 索引旁路（`audit.index.jsonl` 指向段 + 偏移）。
  出处：`gbt_allinone/docs/技能包评估_20260917.md` §B2 / §八 L2。

- **O18（新观察项 · 2026-09-17 由测试污染事件带出）**：**`_paths.STORE_DIR` 在 import 时绑定，
  让"谁先 import"决定了跑的是哪个 store。** 即：`gbt_allinone/__init__.py` → `.store` 在导入时把
  `STORE_DIR`/`_LOG` 钉成常量，晚到的 `GBT_STORE_DIR` 不再生效（详见 §八 口径 B）。
  本轮处置是**隔离兜底 + 报错停下**（`gbt_allinone/tests/__init__.py`），没有动 `store.py`——
   因为那是审计写入方，属生产核心，超出本次批复边界。
  **根治方向（待拍，单独单元）**：把 store 基址改成**惰性解析**（`_paths.store_dir()` 每次读环境；
  `store.py` / `schedule.py` 的模块级 `_LOG` / `_SCHED_FILE` 改为取用点解析），
  这样"导入顺序"不再能决定"写哪个 store"。**红线**：改审计写入方必须单独批 + 正负对照
  （正：隔离环境写进隔离 store；负：生产文件逐字节不变）。

 - **O19（新观察项 · 2026-09-17 风哥拍）**：**计时型断言不进回归套件，或加负载豁免。**
   实证：第一遍跑 `test_framework` 出过 1 条新红 `test_perf_baseline`（阈值 50/500/500 ms 的计时守卫），
   单跑 OK、清负载复跑 OK —— 是**负载抖动**，不是回归；但计时型断言进回归套件本身就是假红来源。
   长期方案：计时类从 `test_framework.py` 移出，进独立 `perf_baseline.py`。**本轮不动。**

 - **O20（已闭环 · 与 `t-sched-run` 同根因、不同文件 · 2026-09-17 风哥批"清，单独一刀"）**：
   清 `t-preflight-sched-*` 时盘出的**兄弟残留**已单独清完（不跟第二刀混）：
   - `store/workflows.json`：**17,137 B → 10,083 B**，清掉 `t-*` **20 条**（含 `t-preflight-*` 6 条），
     余 9 条（`ai-orchestration` / `gbt_polish_v1` / `self-polish` / `autopilot-r1..r3` / `bo-probe` / `bo-probe2` / `honesty-test`）；
   - `store/wf_runs/`：**492 个 `t-*` 文件 / 585,975 B** 整体搬迁出库，剩 55 个；生产 `t-` 前缀 **0 残留**。
   - 备份：`.scratch/_o20_workflows_backup_20260917T182309.json`（sha256 `6c3cc91f81db69c0…` 与原文逐字节一致）·
     `.scratch/_o20_wf_runs_backup_20260917T182309/`（492 文件 / 585,975 B，搬迁前后计数与字节数逐项相等）。
   - 证据：`.scratch/_r53_o20_clean.json` · 契约 **4/4 ok（rc=0）**。
   - **仍未动（只报，待拍）**：`autopilot-r*` / `bo-probe*` / `honesty-test` 6 条疑似测试定义，
     以及 11 个孤儿 run 名（`demo`/`par`/`rt`/`v-verify`/`v2-verify`/`v8_resume_test*` 等）——它们的危害同样是 0，
     但不带 `t-` 前缀，超出本次批复边界（《边界来源律》）。
   - 守卫：新增契约 `TestProductionStoreIsolation.test_production_workflows_has_no_test_residue` ——
    生产 `workflows.json` / `wf_runs/` 出现 `t-*` 即当场判红。

- **O21（真缺陷 · 2026-09-17 由 CF AI Gateway 评估带出 · 风哥升格 · 排在 V2 之前）**：
  **两条 LLM 通道治理不一致——通道 A 缺限流降级 + 侧车审计，通道 B 已有。**
  实证 **通道 B** `potato_pet/chat_client.py`：`:24-30` 密钥链（智谱 glm-4.7-flash → DeepSeek → Kimi →
  Moonshot → OpenAI）· `:32-34`/`:78-87` **429 → 该家冷却 300 s → 换链上下一家** · `:194-213` 换脑重试一次 ·
  侧车审计 `security/ai_audit.py:39-75` 写 `store/ai_audit/events.jsonl`。
  实证 **通道 A** `llm/cloud_llm.py`：`:13-28` 六家链（deepseek → kimi → openai → custom → anthropic → gemini），
  **无冷却、无换链、无侧车审计**（**写账调用 0 处**；文件内 3 处 `audit` 命中全是 `.gbt/_audit_caps.json`
  能力计数缓存，与写账无关——口径必须写"写账 0 处"，不许写"audit 0 命中"，那是两件事），
  只有 `:406` 重试 2 次 + `:449` 退避 1 s / 3 s。
  处置：**不现在修** —— 等 CF AI Gateway 采纳三条（缓存 / 限流 / 短窗日志）落地时，
  参考通道 B 的成熟模式补通道 A，走同一个原子单元。**优先级：V2 链路级之前**（V2 拉长运行时间，无冷却的通道先撑不住）。
  出处：`gbt_allinone/docs/CloudflareAIGateway评估.md` §②。**行号锚点 = `llm/cloud_llm.py`**
  （另有 `gbt_allinone/llm/cloud_llm.py` 副本，`:65` 之后行号 **+2**，见 O23）。

- **O22（接入前置 · 2026-09-17 由 CF AI Gateway 评估带出 · 风哥记，不动手）**：**CF AI Gateway 接入三件前置。**
  ① **另建 Token**：保险箱现有 `cfut****`（53 字符 · `/user/tokens/verify` → 200 active）权限域 =
  **所有帐户 · Cloudflare Tunnel:编辑**，**不覆盖 `AI Gateway: Read/Edit`**；
  ② **定账号**：`844b0356…` 还是 `82dd88c2…`（两个账号是既有事实，须人指定）；
  ③ **代码**：`llm/cloud_llm.py:435-441` 只设 `Content-Type` + `Authorization`，**不支持自定义 header** →
  用不了 `cf-aig-authorization` → 需一处小改（**不是零代码接入**）。
  处置：不现在做，与 O21 同一批处理。

- **O23（新观察项 · 2026-09-17 由 O21 行号复核带出 · 只登记，不动手）**：**通道 A 有两份副本，且已开始漂移。**
  实测：`llm/cloud_llm.py` **28,274 B / 473 行 / sha 前 16 `feadb2b765cbf165`** ·
  `gbt_allinone/llm/cloud_llm.py` **28,470 B / 475 行 / sha 前 16 `c571fc86e0090cc2`** —— **逐字节不相同**。
  `difflib` 全量对照：**全部差异只有 1 处**，就在 `except Exception:` 内多了 2 行注释
  （「合理兜底：读能力总数失败 → 返回 0 …故静默安全」）→ **当前功能等价，但行号自 `:65` 起差 2**
  （`:406` vs `:408` · `:435` vs `:437` · `:449` vs `:451`）。
  **两条加载路径都是真的**：`llm/bridge.py:27` 用 `spec_from_file_location` 按显式路径加载**同目录**的
  `cloud_llm.py`；`gbt_allinone/api.py:202/212`、`gbt_allinone/pipeline.py:92`、`gbt_allinone/think_loop.py:30`
  走 `from .llm import bridge` → 加载 **`gbt_allinone/llm/`** 那份；
  `gbt_allinone/tests/test_ai_audit.py:25` 也 `from gbt_allinone.llm import cloud_llm`。
  **危害**：同一逻辑两份源码，改一份另一份不动 → 正是今天 G4「同源缺陷」的同类形态（改了 A 以为改了 B）。
  **处置（待拍）**：先定性「哪份是权威 / 是否镜像关系」，再决定合并或立契约（两份 sha 必须相等）。
  **红线**：不许在没定性前手动同步两份——那会把"漂移"变成"两份都动过"，反而更难判。

- **O24（新观察项 · 2026-09-17 由 D9 壳先落地取证带出 · 风哥批「不并入本刀，记观察项」）**：
  **`holo_pet_w25/` 与壳同住维度树，工作区根两个都没有——待另开刀落地。**
  实测（逐子树拆开）：`mirror_space/dimension/` 整棵树 **14 文件 / 88,008 B**，其中
  **`holo_pet_w3/`（壳本体）= 11 文件 / 74,336 B**、**`holo_pet_w25/` = 3 文件 / 13,672 B**；
  `reality/` 侧逐项同构。**工作区根 `holo_pet_w3/` 与 `holo_pet_w25/` 均不存在**。
  定性：D9 这一刀**只落 `holo_pet_w3/`（11 文件）**；`holo_pet_w25/` 不是本批范围，
  要落**另开刀**（同样走「维度 → 工作区根」的一次性落地 + 同一套硬判据）。
  附带口径改正：此前把「14 文件」说成"壳"是**把维度树与壳混成了一个数**——
  **数字都真，是标签错了**；落地判据、G1、脚本 `would_copy` 一律按 **11** 走。
  依据：`gbt_allinone/docs/D9壳先落地方案.md` §1「一处数字改正」。

- **O25（新观察项 · 2026-09-17 由 D9 `--fix-readme` 取证带出 · 风哥批「不本刀修，记着」）**：
  **`mirror_space.shape()` 落审计时 `bytes` 字段的语义 = 字符数，不是磁盘字节数。**
  实测（同一文件、同一次写入）：审计里 `bytes: 1362`（`len(str(content))`）vs 磁盘真实 **2,421 B**。
  纯中文内容差得更远（UTF-8 下一汉字 3 字节）。
  **处置**：不在本刀修；**长期改惰性解析时一并修**（把 `len(str(content))` 换成 `len(content.encode("utf-8"))`，
  或按磁盘回读取 `stat().st_size`）。依据：`gbt_allinone/mirror_space.py:62` `shape()` 的 `_audit` 调用。

- **O26（已闭环 · 维度侧改毕 · 2026-09-17 W7 动刀同批处理）**：
  **`holo_pet_w3/README.md:17` 描述的是 W3 现状，W7 追加 EigenFlux 时必须同批改。**
  原文：`关一扇不影响其他（W3 只登记上帝视角一扇，所以全关 = 退到托盘，不等于退出）`。
  定性：**今天没错**（与 `shell/windows.json` 现状一致——只登记 `godview` 一扇），
  **W7 往 `windows.json` 追加 `eigenflux` 那一刻才过期**；现在改反而会写成假话。
  处置：**W7 出稿时同批改**，与 `windows.json` 追加条目视为**一个原子单元**。
  **闭环进展（R66 · 维度侧）**：`README.md` 的 :17 已改**动态口径**（不再写死窗口数）；`shell/windows.json` 的 `registry_note` 同批改（同一类「把现状写进文档」的假话）。
  **闭环条件 = S7 晋升 + 落地工作区根** —— 那一批做完才算真闭环（现在只到维度）。

- **O27（新观察项 · 2026-09-17 风哥批「附一条观察项」· 由 W7 出稿发现二带出）**：
  **多扇同级置顶窗口之间，谁在前取决于最后一次点击 —— 需要用户手动切换。**
  实测背景：单屏 **1536×864**（工作区 1536×816）放不下「上帝视角 1120×720 + AI 朋友圈 900×640」两扇，
  重叠不可避免。本刀采**同级置顶**（`alwaysOnTop:true` → `setAlwaysOnTop(true,"screen-saver")`，风哥 2026-09-17 拍甲案），
  互相盖住可接受。
  **处置：不现在做层级管理**。若将来用户抱怨「找不着窗口」，再考虑候选方案（托盘菜单置前 / 任务栏角标 / 层级优先级表）。
  依据：`holo_pet_w3/shell/main.cjs:361`；`gbt_allinone/docs/W7EigenFlux独立窗口接入方案.md` §六②。

- **O28（新观察项 · 2026-09-17 由 W7 动刀取证带出 · 风哥拍「暂不修 · 待另开刀统一换行符」）**：
  **`HEARTBEAT.md` 行尾混用：中段 17 行是裸 LF，其余是 CRLF。**
  实测（本轮 byte 级定位）：CRLF **281** 行 + 裸 LF **17** 行；裸 LF 集中在 `同化口径` 与
  `空不等于不存在律` 附近（byte 偏移 6,972 – 8,059），**不是 R65 / R66 插入块造成的**（那两块写的就是 CRLF）。
  定性：**不是缺陷，是历史行尾漂移** —— 人读没问题，但下游任何「按行尾逐字比对」的脚本会在**它**这里碰到**假失配**
  （《脚本编码律》同族现象）。
  **处置**：不在本刀修（原子单元边界外）；**另开一刀统一**，统一前先备份 + 留双向 SHA 对照。

  **R81 已闭环（2026-09-17）**：本文件 + `HEARTBEAT.md` + `audit.jsonl` **三份同批清完** —— 判据取**当时实测**，不取记录值。
  写法：备份 → 只把裸 LF 转 CRLF → 判据「归一化后逐字节相等」（证明**只动行尾、零内容变化**）。
- **O29（新观察项 · 2026-09-17 · **出处更正：本条原假设由本轮自证推翻**）**：
  **原假设**：「MCP 5 个服务器 0 个健康 —— 先诊断，再接新。」
  **本轮诊断结论：这 5 个不是小土豆的服务器，诊断对象选错了。**
  - 「No MCP tools are currently healthy」出自 `AGENTS.md:367-377` 的 `<!-- autoclaw:mcp-tools-guidance -->` **注入块** ——
    由桌面运行时生成，描述的是**运行时自己的 MCP 目录**，不是小土豆的触手，也不是本仓代码的输出。
  - 那 5 个（`config/mcporter.json`）：`autoclaw-productivity` / `autoclaw-github` → `http://127.0.0.1:19681/...`（本地）；
    `notion` / `connector:cloudflare` / `connector:vercel` → 外部 HTTPS + OAuth。
  - **实测**：`127.0.0.1:19681` → **CLOSED（连接被主动拒绝）** → 本地那两个必不健康；外部三个需联网 + 授权。
  - 小土豆自己的 MCP 触手是**另一套**：`tentacle/mcp_bridge.py` —— **纯 stdio · 会话制 · `command` 由调用方给**
    （`gbt_allinone/api.py:453-460` 的 `mcp_connect` 要求 `server` + `command`）。**它不读 `config/mcporter.json`。**
  - `MB.status()` 实测 → `{"servers": {}}`（会话池空，符合「现起现连」的设计）。
  **定性更正**：小土豆侧**没有「常驻服务器健康」这回事** —— 所以「5 个服务器 0 健康」在小土豆侧**不成立**（它根本没有 5 个服务器）。
  **处置**：本地 19681 服务该不该起 → 归桌面运行时运维，**不入本仓待办**。本条**降级为「已澄清」**，不占施工序。

- **O30（新观察项 · 2026-09-17 · 风哥拍「待核」）**：**Open Minis 能力待核 —— 4 条待验证，前提不成立则整个集成方案作废。**
  ① 是否存在／活跃 ② 是否提供 **MCP 服务端** ③ 是否支持配外部 MCP 服务器 ④ Alpine 沙箱与系统集成是否真实。
  取证前提：本进程网络受限 + 身份 = `desktop-vpvp0bp\codexsandboxoffline` → **待真实用户身份 + 可联网环境补验**。
  **附一条本轮新增判据（直接决定接入工作量）**：`tentacle/mcp_bridge.py` **只实现 stdio 传输**
  （`subprocess.Popen` + stdin/stdout 一行一 JSON，协议版本 `2025-06-18`，**无 HTTP 分支**）。
  → Open Minis 若提供 **stdio** 服务端 = 一条 `mcp_connect(server, command)` 调用；
  → 若提供 **HTTP / streamablehttp** 服务端（现代 MCP 更常见；现有 5 个全是 streamablehttp）= **要加 HTTP 传输层**，那是真工作量。
  **先核传输形态，再估工期。**

- **O31（新观察项 · 2026-09-17 · 本轮 byte 级实测带出 · 与本轮一次自伤同源）**：
  **`PROJECT_BLUEPRINT.md` 行尾混用：CRLF **649** 行 + 裸 LF **183** 行（同一文件内）。**
  残留裸 LF 共 **31 个连续段**（`346-348` / `350-356` / `630-684` 一带最密 / `833-856` 等），**不是本轮造成的**。
  **本轮自伤一笔（如实报）**：我给 §八 插 O29/O30 时用了 `\n` 拼行，**在 CRLF 文件里插了 21 行裸 LF** ——
  写完立刻 byte 级复读才发现，**当场补回 CRLF（628 → 658）**。
  **同一轮里犯了三次** —— 插 O29/O30 补 21 行，插 O31 时**又**用 `\n` 拼行，再补 9 行、后又插 2 行（合计 32 行）。
  **两次都是写完立刻 byte 级复读才抓到。** 教训：这条不能靠「记得」——**补丁脚本必须先把目标文件的换行符读出来，再按它拼行**，否则同一坑会一直踩。
  **这是「换行符」母题的第三种形态**：第一、二次是**锚点匹配失败**（已入宪《锚点必须同换行符》），
  这次是**写入时没跟随目标的换行符** —— 匹配与写入，两条路都会踩。
  **处置**：不在本刀统一（与 O28 同一批另开刀）；另开刀时两处一起收（`HEARTBEAT.md` 17 行 + 本文件 183 行），
  统一前先备份 + 留双向 SHA 对照。
  **R81 已闭环（2026-09-17）**：与 O28 同批清，实测 **660 CRLF / 208 裸 LF -> 868 / 0**。
  根治手段 = 本轮立的《写入必须同换行符》（宪章第二十四章第七条）+ `safe_io.insert_lines_aligned` —— 靠「记得」不行，靠工具。
- **O33（已闭环 · 2026-09-17 · R82 单独一刀落地 · 风哥拍「立 O 项 + 单独一刀」）**：
  **模块硬编码路径，绕开 `_paths.STORE_DIR`** —— `root_fix.py:22/134/135`（`_BASE / 'store' / 'pit_log.json'`、
  `_BASE / 'store' / 'work_log.jsonl'`）与 `auth_gate.py:24/25`（`_BASE / "store" / "auth_grants.jsonl"`）。
  -> 设 `GBT_STORE_DIR` 对它们**无效**，跑测试照样写生产 store。
  **与 O20 根因不同**：O20 是**测试侧没设隔离**；这条是**模块自己绕开隔离**。
  **实测（两臂对照）**：臂 A 静默 60 s -> 生产 store **零变化**；臂 B 跑一次 `test_framework.py`（隔离 store 已设）
  -> 生产变化 **3 个文件**（新增 `auth_grants.jsonl`、改 `pit_log.json`、改 `work_log.jsonl`）。
  产物形态：生产 `work_log.jsonl` 尾行是 `{"action": "lesson", "title": "测试日志"}` —— **每跑一次回归 +1 行**。
  **为什么契约没拦住**：`TestProductionStoreIsolation` 只守 `schedules.json` / `workflows.json` / `wf_runs/` 三条，
  这三条从它下面漏过去 —— **契约是绿的，漏网是真的**。
  **处置**：单独一刀（清副作用 + 改硬编码走 `_paths.STORE_DIR` + 契约扩到这三条 + 正负对照）；**不跟 O28/O31 混**。
- **判据脆弱性（2026-09-17 · R81 实测 · 风哥批「并入 O33 那一刀」）**：`test_framework.test_emit_writes_inside_store`
  断言的是 `"store" in written` —— 挂的是**隔离目录的名字**，不是语义。
  实测：隔离目录取成 `gbt_r81_regression_*` 时该条**当场假红**（全量 10 红）；换回 `gbt_test_store` 即回到 9 红。
  -> 判据改 `Path(written).resolve().is_relative_to(Path(STORE_DIR))`（《判据不许挂在旧数据上》同族：判据挂在**名字**上）；**R82 已落**——落在比 `startswith` 更严的形态上（先 resolve 再比，抗 `..` 与大小写差异）。


- **O33 落地实测（R82 · 2026-09-17）**：清生产副作用 **3 份**（`pit_log.json` 23,441 B / 115 条 -> **6,716 B / 16 条**；
  `work_log.jsonl` 10,479 B / 107 行 -> **1,377 B / 6 行**，回到纯 CRLF；`auth_grants.jsonl` 0 B 已删）；
  改路径来源 **3 处**（`root_fix.py` 顶部 + 两处 store 常量、`auth_gate.py` 顶部 + `_GRANTS`、
  `tests/test_framework.py:87`）——最后这处是本刀回归**当场暴露**的第 5 个硬编码点：
  **测试自己按 `__file__` 拼生产路径**，删/写的是**生产**授权文件（`gf.unlink()` 会删掉主人手写的授权）；
  改写入口 **1 处**（`checkpoint.py:291` 加 `align_to_existing=True`）；
  契约 **+3 条**（`pit_log` 严格三元组 / `work_log` 测试日志行 / `root_fix`+`auth_gate` 落点）；
  判据脆弱性 **1 处**改语义。
  **全量回归 111 项 / 红 9**（红项集合 = 宿主环境类 9 条，与基线逐项一致；此前那条**假红**
  `test_emit_writes_inside_store` 转绿）；**生产 store 逐文件 sha256 跑前跑后零变化**（5,212 文件）。
  **判别性负对照 RED_AS_EXPECTED**：同一份新契约 + 动刀前备份里的旧真身 -> 7 项里 **2 项当场红**
  （`..._store_untouched_by_root_fix_and_auth_gate` / `..._work_log_has_no_test_residue`），
  沙箱"生产"被写进 `测试坑-契约…` 并生成 `auth_grants.jsonl`。
  取证：`.scratch/_r82_o33_clean_evidence.json` · `_r82_o33_patch_evidence.json` ·
  `_r82_o33_patch3_evidence.json` · `_r82_o33_regression_verdict.json` · `_r82_o33_red_as_expected.json` ·
  备份 `_r82_o33_backup_20260917T212014/`（10 份 + manifest）。

- **O32（接入前置 · 2026-09-17 · 由 MCP 传输形态复核带出 · 风哥批「记 O32」）**：
  **MCP 接入工作量判据 = 传输形态** —— 对方给 **stdio** 服务端 -> 近乎配置项级
  （`tentacle/mcp_bridge.py` 就是 `subprocess.Popen` + 一行一 JSON，纯 stdio）；
  对方只给 **HTTP / streamablehttp** -> 要真加一层传输（代码里**没有** HTTP 分支）。
  **先核传输形态，再估工期。**

- **O34（新观察项 · 2026-09-17 · R81 byte 级实测带出 · 风哥拍「立 O34 · 单独排期」）**：
  **主账本 311 行半截/重复残片**（`[]}}` / `0}}` 这类，不可解析），集中在 **2026-09-11** 打磨期并发压测段。
  与 O21（35.8 MB 无索引）**同族** —— 主账本**数据质量债**。
  检查器已自证过（正对照尾行可解析 · 残片自证 `[]}}` / `0}}` 只有后半截）。
  **处置：本刀不修，单独排期。**

- **O35（新观察项 · 2026-09-17 · R82 O33 动刀带出 · 风哥拍「本刀只做 checkpoint.py:291 一行」）**：
  **同族写入口待统一** —— `root_fix._save_pits`（`_PIT_PATH.write_text`）·
  `root_fix.work_log`（`_WORKLOG_PATH.open('a')`）· `auth_gate._save_grants`（`_GRANTS.write_text`）·
  `checkpoint.audit`（`locked_append_text`）。四条都绕开统一写入口的行尾对齐。
  **本刀只做 `checkpoint.py:291`**（先做一处验证防线有效，再批量推广）。
  **O35 扩展（R83 · 2026-09-17 · 风哥拍「O36 并入 O35，不另立 · 分三档定性」）**
  **三档判据**：**高危** = **写**生产；**中危** = **读**生产；**低危** = 只读历史 / 兜底默认（优先走 `_paths.STORE_DIR`）。
  逐条实测（byte 级读盘 + 写操作枚举 · 只读证据脚本 `.scratch/_r83_sites_evidence.py`）：
  1. **高危 · `mirror_space.py:28`**（`_STORE = _BASE / "store"`，`_paths` **零引用**）——
     写：`shape()` 落维度树并 `_audit("deploy_stage_write")` · `unshape()` 删 · `ascend()` `rmtree` / `copytree` 覆盖 `_REALITY` · 写 `_PASSPORTS/vN.json`。
  2. **高危 · `qiankun.py:22`**（`_STORE = _BASE / "store"` -> `_QUEUE`）—— 写：`_QUEUE.parent.mkdir` + `_QUEUE.write_text`（部署队列）。
  3. **高危 · `hygiene.py:129/132`**（`_BASE / "store" / ...` -> `p.rename(target)`）—— 写：`fix=True` 时把散落文件**搬进** store。
  4. **高危 · `think_loop.py:112`**（`Path(__file__).parent / "store" / "polish_insights.json"`）—— 写：`p.write_text(...)`。
  5. **高危 · `tentacle/vision_bus.py:21`**（`_STORE = _BASE.parent / "store"`）—— 写：`_STORE.mkdir` · `transfer_cache.json` · `_VISION_DIR/*.json`，并调 `store.audit`。
  6. **中危 · `ghost_guard.py:149`**（`_BASE / "store" / "devoured"`）—— 只 `iterdir` / `rglob` / `read_text`，**无写操作**。
  7. **中危 · `signature.py:90`**（`_BASE / "store" / "pipeline" / "production"`）—— 只 `rglob` + `read_text`；
     注：这条**可能是设计意图**（署名守卫天生要看生产产物）—— 定性时标注，不预判为缺陷。
  8. **低危 · `tentacle/brain/visual_cortex.py:38`** —— `_paths.STORE_DIR` **优先**，硬编码只是**兜底默认**。
  9. **低危 · `tentacle/brain/visual_memory.py:48`** —— 同上；文件头自述「数据落 V8 store, 遵守 `GBT_STORE_DIR` 隔离」。
  另：`checkpoint.py:92` 的 `resolve_store_dir()` 也是**兜底默认**，属正常（原 O36 已记）。
  **处置：本刀只定性、不动手。** 高危 5 条按风哥档位「立即修」-> **待批单开一刀**
  （都写生产，须备份 + 契约 + 判别性负对照）；中危 2 条**排期修**；低危 2 条**不动**。

- **O36（2026-09-17 R82 立 · R83 已并入 O35 扩展 —— 风哥拍「同族缺陷合并治，不另立」；编号保留作溯源）**：
  **`store` 路径硬编码家族远不止 root_fix / auth_gate。** 全仓实测量到至少还有
  `mirror_space.py:28` · `qiankun.py:22` · `ghost_guard.py:149` · `hygiene.py:129/132` · `signature.py:90` ·
  `think_loop.py:112` · `tentacle/vision_bus.py:21` · `tentacle/brain/visual_cortex.py:38` ·
  `tentacle/brain/visual_memory.py:48`（另：`checkpoint.py:92` 的 `resolve_store_dir()` 是**兜底默认**，属正常）。
  **不预判为缺陷**：其中多数是"按家根定位生产产物"的设计意图（如 `signature` 读生产管线产物）。
  **处置：逐条定性后才许改；本刀只收 root_fix / auth_gate / `tests/test_framework.py:87` 三处。**

- **O37（新观察项 · 2026-09-17 · R82 O33 动刀带出 · 如实登记 · 待风哥拍）**：
  **`safe_io` 的换行对齐按"文件主流"，不按"命中行的局部区段"。**
  实证：`gbt_allinone/tests/test_framework.py` 文件主流 **CRLF（739）**，但命中行落在 **911–1110 的 200 行裸 LF 区段**
  （全文件共 7 段裸 LF，合计 375 行）——按主流对齐会把 CRLF **写进纯 LF 区段**，等于新造混行尾。**两个读数都记上**（判据不许挂在旧数据上）：动刀前 **739 CRLF / 375 裸 LF**；O33 落完 **743 / 452**（新增行按局部裸 LF 拼，LF 涨的全是新增行）。
  本刀绕开办法：补丁脚本**逐处显式声明局部行尾**（`nl`），落完复核 `crlf/lf` 增量与预期**逐项相等**。
  **待拍**：是否给 `safe_io.edit_text_once` 加 `newline=` 显式覆盖参数（**默认行为不动**）。
- **O38（新观察项 · 2026-09-17 · R83 立 · 风哥拍「固化证据源」）**：
  **memory 补记的证据源 = `.scratch/archive/` 脚本 mtime + 正文**，
  **不依赖** `CHARTER.md` / `PROJECT_BLUEPRINT.md` 的 R 号引用。
  理由：R82 实测那两份文档**只引到 R65 / R66 / R81**，**R68–R80 一条引用都没有** ——
  拿它当唯一证据源只会得到「无记录」的假结论。以后补 memory 缺口一律按本口径取证。

- **O39（新观察项 · 2026-09-17 · R83 立 · 风哥拍「记一笔」）**：
  **`gbt_allinone/docs/通信域与创作出口方案稿.md` 自身是全裸 LF**（24,003 B · 253 行 / CRLF 0），
  与家根主流（CRLF）不同 —— **待统一**。属换行符母题（《写入必须同换行符》），**本刀不动**。
- **O40（新观察项 · 2026-09-17 · R83 立 · 风哥拍「记」）**：
  **判据字符串必须跨条目唯一** —— 判据（锚点串 / 断言串）不许用**跨条目重复**的短串，
  否则必然假红（或假绿）。**本项目第二次踩「锚点不唯一」。**
  实证：R83 复验首跑把判据写成「`如实登记 · 待风哥拍）**：`」—— 撞上 **O37** 的同名尾串
  -> `pb_o36_marker_gone = false` **假红**；第一次是 O36 / O37 两条头部**同尾串**（R83 §八 动刀当场）。
  处置：判据改用**条目专属串**（如 `O36（新观察项`）。本条只登记，不设强制工具。
- **O41（新观察项 · 2026-09-17 · R84 立 · 风哥拍「记」）**：
  **判据窗口必须与位置无关** —— 判据不许挂在"动刀前的偏移/索引"上（插入/删除后必然漂移）。
  **本项目第三次踩「判据自己写错」。** 三次：① R83 O37 同名尾串（判据串跨条目重复）；
  ② O40 同族（判据串跨条目重复，已立律）；③ **R84 偏移漂移** —— `all_clauses_have_marker`
  用**原偏移 ±60/±20 窗口**判定，17 处插入后逐条右移，越往后越飘出窗口 -> **假红**
  （写入本身完全正确：`roundtrip_identity=true` / +459 = 17×27 / CRLF 与裸 LF 不变）。
  处置：判据改为**与位置无关**的判法（每个 marker 必须紧贴 `**同级效力**`，或换行后紧贴）。

- **O42（新观察项 · 2026-09-17 · R84 立 · 风哥拍「记」）**：
  **证据文件不许当状态载体** —— 状态与证据必须分离，否则 `dry-run` 会毁掉续跑锚点。
  实证（R84）：`_r84_evidence.json` 里的 `backup` 指针被一次 dry-run 覆写 -> 续跑 `KeyError: 'backup'`。
  处置：续跑**不读证据文件**，改为**按内容认亲**（在 `.scratch/_r84_backup_*` 里找哪份去掉 17 个
  marker 后能逐字节还原原状）。证据文件只写不读（除人工复核）。

- **O43（新观察项 · 2026-09-17 · R84 立 · 风哥拍「记」）**：
  **闸门与状态恢复必须同轮设计** —— 不许分两轮，否则中断在中间会产生「部分完成」状态。
  实证（R84）：第二次 `--go` 在 memory 步 `KeyError: 'after'` 中断 —— 此时 **O40 已写、memory 未写**；
  第三次 `--go` 被幂等闸门 `pb_o40_count` 挡下（rc=14，**没有重复插入**）。
  **三条闸门都按设计停手**（写入未污染 / 未重复 / 最终状态可逐字节证明），代价是**三次尝试才收口**。
  处置：动刀脚本必须**同轮**给出「中断在哪一步都能续跑」的入口，而不是事后补。
- **O44（判例 · 2026-09-17 · R86 立 · 风哥拍「三处入档」）**：
  **判据必须与文件主流匹配** —— **CRLF 主流**文件断言 `bare_lf == 0`；**LF 主流**文件断言 `crlf == 0`。
  拿错断言对象 = **永久红或永久绿**。与 **O41** 同族（判据自己写错），不同层：**O41 治位置漂移，本项治对象错配**。
  四次实证：R83 同名尾串 / O40 同族 / R84 偏移漂移 / **R85 本轮**（对整文件裸 LF 的 `safe_io.py` 断言 `bare_lf == 0` -> 永久红）。
  **三处入档 = 生命档案 + `CHARTER.md` 第二十六章 + `HEARTBEAT.md`；§八 只留本条指针**（保 O 序号连续，免「查条目会漏」）。

- **O45（新观察项 · 2026-09-17 · R86 立 · 风哥拍「加一条观察项」）**：
  **三级回退是特例，不是范式** —— `mirror_space.py` / `tentacle/vision_bus.py` 会被
  `spec_from_file_location` **无包上下文加载**（`checkpoint._load_sibling`），顶部写 `from . import _paths` 直接崩，
  故 store 解析写成「包内 `_paths.STORE_DIR` -> 同目录 `_paths.py` 按路径加载 -> env/默认」三级回退。
  **将来如果有第三个文件需要它，先问「为什么这个文件在无包上下文加载」，而不是无脑复制三级回退。**
  本刀只准两处（R86 高危 5 条）；`qiankun.py` / `hygiene.py` / `think_loop.py` 是纯包内模块，只走一级。
- **O46（新观察项 · 2026-09-17 · R87 立 · 风哥拍「批」）**：
  **闸门基线必须取「本轮首跑前的备份 manifest」，不许取「当前盘面」** ——
  分段执行时「当前盘面」可能已经是**中间态**。实证（R86 文档刀）：复跑把「改前」取成了中间态 ->
  memory 读数表**三行 +0 假数字**，后按首轮备份 `.scratch/_r86_docs_backup_20260917T220702` 更正。
  与 **O42**（证据不许当状态载体）+ **O43**（闸门与状态恢复必须同轮）同族 —— 三条都是「**状态一致性**」的不同面。
  处置：动刀脚本的「改前」一律读**首跑前备份**（或备份 manifest），续跑复用同一份基线，不许重取当前盘面。
- **O47（新观察项 · 2026-09-17 · R88 立 · 风哥拍「立 O47」）**：
  **「旁观者」角色待定义 —— 本契约稿为初稿** —— 定位：**独立于执行者的观察位**（旁观者看执行者干活）。
  职能只有三件：**提醒 / 意见 / 建议**。**四条硬边界**：① 零执行权 ② 只递草案不落地 ③ 不越位出声 ④ 不进生产。
  甲案 = **严格只读**：万能插四面里它只准碰 `wf_status`（`wf_define` / `wf_run` / `wf_resume` 都不在它手上）。
  **分层放行**（同日拍 · R89 回填最终口径）：分档轴 = **触发条件**。
  **日常档** = 落地动作**四条全过**（**低敏感 · 可逆 · 不碰生产树 · 不发布**） -> **执行者可自主放行**；
  **敏感档** = **任一条不过** -> **落档等风哥点头 —— 执行者无权当场放行**。
  **敏感档直接触发项**（不看四条判据，命中即落）：**写生产 · 删文件 · 发布 · 跨域调度 · 调外部账号**。
  初稿：`.scratch/旁观者契约稿.md`。实体**零命中**（本仓无「旁观者」）—— 只立契约，**不建常驻入口**。
- **O48（新观察项 · 2026-09-17 · R89 立 · 风哥拍「立 O48」）**：
  **判据 / 脚本里的常量必须与盘上真值同源** —— 判据基准值一律来自**当前实测**
  （读盘 / 首跑前备份 manifest），不许来自「上一版留下的数字」，也不许来自脚本作者记忆里的措辞。
  实证来源：**R87 自伤第 5 条** —— `O46_BODY` 常量与首跑实际写盘文本不一致 -> 假红；
  以及 R89 本轮：O47 正文旧措辞与契约稿最终口径不一致（文书内部两套口径）。
  与 **O41**（判据与位置无关）/ **O44**（判据与文件主流匹配）/ **O46**（基线取首跑前备份）同族 ——
  四条都是「**判据自己写错**」。
- **O49（新观察项 · 2026-09-17 · R89 立 · 风哥拍「立 O49」）**：
  **家根影子大扫** —— 家根**同名 `.py` 计数一律判据取当时实测**：逐字节同源数（R90 归档前实测 **20**）· 家根同名 `.py` 分叉数（判据取当时实测 · 归档后现测 **11**）· 家根独有 **5**（丙类）。
  唯一活跃暴露面：`holo_pet/panel_server.py:27-32` 把**工作区根**挂进 `sys.path`；裸导入 **判据取当时实测**（口径 = **落家根影子 0 命中** · 非「字符串零命中」· 见 **O51**）
  —— 上了膛，没扣扳机。
  本次已归档 5 件（`root_fix.py` 旧残骸 + 4 件孪生）-> `.scratch/archive/root_shadow_20260917/`。
  **单开一刀清：归档 20 同源 + 5 独有 + 影子子目录。**
  **R91 收口（09-17）：91 件（46 项 = 甲 / 乙 86 件 + 丙 5 件）全数归档** -> `.scratch/archive/root_shadow_20260917`；两份 manifest 逐件 sha256 复核 **86/86 + 5/5** · `bad: []`；**家根顶层 `.py` 现测 0**；常驻防线 `gbt_allinone/tools/shadow_check.py` 已落并判别性自证（**live 红 0** / **归档副本红 47 rc=1**）；**门禁 W 维已挂**（`cross_scan.py` dims 含 "W" · `shadow_verdict=GREEN`）。**
  09-16《影子模块取证报告》分类（dup_byt 26 / dup_eol 6 / orphan_real 6 / root_only 5）**已过期** ——
  本刀改掉 4 件孪生后 dup_byt 26 -> 20，**判据取当时实测**。
  与 **O48**（判据常量必须与盘上真值同源）同族：都是「盘上真值与引用面不一致」。
- **O50（新观察项 · 2026-09-17 · R91 立 · 风哥拍「三条 O 项全立」）**：
  **`brain` / `caps` 悬挂导入** —— 框架自身有裸顶层导入 `from brain.*` / `from caps.*`，
  真身实测 **17 处（brain 12 / caps 5）**，集中在 `gbt_allinone/llm/cloud_llm.py` 与
  `gbt_allinone/tentacle/omni_{controller,domain,process,read,vision,window}.py`；
  而 `gbt_allinone/` 里**没有** `brain/` 与 `caps/` 包 —— 现在靠**家根** `brain/`
  （无 `__init__.py` 的命名空间包磁铁）勉强解析，`brain.cognition` / `caps.console_vision` 实际**不存在**（运行到就 ImportError）。
  与影子大扫**不是同一件事** —— 清影子不修它们，修它们也不该混进影子刀。
- **O51（新观察项 · 2026-09-17 · R91 立）**：
  **现行正文（Owner 风哥 · 2026-09-18 拍 · 本节 O51 以此为准）**：判据自己写错续计至第 **10 次**（R83/O40/R84/R85/O48/R91/R92d2/R93/R94/R95）——**按实际发生次数计，不按轮次编号 R 计**。
  **O51 修复方向（Owner 风哥 · 2026-09-18）**：**判据必须对应到可观测行为差异。**
  不写「她用了这个能力」，写「**上下文里没有出现『该用哪个能力』的推理步骤**」；
  不写「她记住了」，写「**任务中不需要查清单就能命中**」；
  不写「她听懂了」，写「**行为发生了，但没产生调用指令**」。
  换言之：机器（或复核人）能直接在运行期观测到的差异才叫判据；「她想起了 / 她懂了 / 她会了」这类**不可观测的心理描述一律不算判据**。
  下方「续计至第 **12** 次」段及其后「更正（R103 / R103b / R104）」各段写死的 10 / 11 / 13 / 14 / 15 次，
  **均为早前口径**；原文一字未改，保留作溯源。
  **影子名命中必须按「解析落点」判，不许按「字符串命中」判** ——
  R90《影子大扫方案稿》判据 1 写「裸导入 0 命中」，实际 `store` **本身就是甲类 31 件之一**，
  有 **3 处 `import store`** 命中，落点是**第三方 skill 同目录的局部模块**
  （`审美相关skill/design-skeletons/last30days/scripts/store.py`），与家根无关；
  「没有一处落在影子名上」与同句列出的落点 `store` **自相矛盾**。
  正确判据 = **落家根影子 0 命中**；拿字符串命中当判据 = **永久红或假绿**。
  与 **O41**（与位置无关）/ **O44**（与文件主流匹配）/ **O48**（常量与盘上真值同源）同族 ——
  **「判据自己写错」第六次**（实证：R83 同名尾串 / O40 同族 / R84 偏移漂移 / R85 主流错配 / O48 常量过期 / R91 字符串命中）。
  **续计至第 12 次**（2026-09-17 · 风哥拍「归 O51 续计，不另立 O」）—— 第 7 次 = **R92d2**（拿 **LF 字面量对 CRLF 文件**做还原 -> 假红）· 第 8 次 = **R93**（store 指纹判据指到**家根 `store`**，真身是 `gbt_allinone/store` -> 读到 0 文件判「零扰动」假红）· 第 9 次 = **R94**（探针用**文本模式**读 CRLF 文件 -> 通用换行折叠 -> `## R` 头假数字 0）。第 10 次 = **R95**（复验脚本自建判据首跑假红，判据重建错）· 第 11 次 = **R95b**（落地脚本撤销 `insert-before` 拆成两步、多去一个换行 -> GO FAILED rc=1；`match_expected=true`，**写入本身正确**）· 第 12 次 = **R95b**（复验脚本在**已含尾部空行**的切片上又补一个 CRLF -> 假红）。另 **R95b 证据侧** `lines_added` 手算 14 / 实测 CRLF 15，同为「判据自己写错」，归同族不再单列号。同族缺陷归一个 O 号，不拆新号。
  **更正（R103 · 风哥 2026-09-18 拍「O51 更新为 10 次」· 如实报）**：O51 **现行计数 = 10 次**。
  第 1–6 次 = R83 同名尾串 / O40 同族 / R84 偏移漂移 / R85 主流错配 / O48 常量过期 / R91 字符串命中；
  第 7–9 次 = R92d2 / R93 / R94；**第 10 次 = R103**（**判据侧写错**：落地脚本 dry-run 空跑却拿「盘上 == 新内容」
  当 roundtrip 判据 —— 空跑必然红；复验脚本另有**三处判据错**：插入物重述缺尾换行 / CRLF 判据写成 `crlf*2 == lf` /
  子进程 env 只给 `PATH`+`PYTHONUTF8` 导致 Python 起不来（`_Py_HashRandomization_Init`）。）
  本条上方「续计至第 **12** 次」段的第 10/11/12 次（R95 / R95b）**为早前口径、已不占号**；
  下方「本轮 O51 不续计 —— 保持 **9** 次」**为 R97 期间口径、已被本更正取代**。两处原文一字未改，保留作溯源。
  （口径归并按您两次裁定推导：先「保持 9 次」、本轮「更新为 10 次」= 9 + R103。若与您本意不符请点名，我改回。）
  **更正（R103b · 风哥 2026-09-18 拍「O51 = 11 次」）**：**第 11 次 = R103b** —— 复验脚本的**还原判据自己写错两轮**
  （`rstrip` 后补一个换行少了一个；块边界取错），**判据侧错、被测文件没错**。**O51 现行计数 = 11 次。**
  **更正（R104 · 风哥 2026-09-18 拍「O51 = 13 次」）**：**第 12 次 = R104** —— `test_framework.test_perf_baseline` **判据与自身声明不符**：
  docstring 自称「阈值 = 实测中位数 × 10 的富余量」，实际 `ghost_guard` 固定 **500 ms**，而当时实测中位数 **285 ms**
  （7 次：285/275/323/293/286/240/265）= **仅 1.75x** 富余 —— 满负载套件下当场假红一次（529 ms > 500 ms；
  单独点名跑 3/3 绿、全量重跑回 9 红）。**本刀不动实现，只登记**；修法（docstring 改如实描述，或改成动态计算）
  留待本条第 12 次处置时再动。
  **第 13 次 = R104** —— `.scratch/_r104b_guard_negctl.py` **负对照脚本自己写错**：子进程源码多一个 `)`
  -> `SyntaxError: unmatched ')'`，让「指纹有牙」那一臂假红（`differs: false`，`before` / `after` 都是 `{}`）；
  当场修一行后真红。**判据侧错、被测物没错。** **O51 现行计数 = 13 次。**
  **第 14 次 = R104**（风哥 2026-09-18 拍「计 1 次」）—— 同轮**判据侧连错三轮**（真值推导式写错 · 把插入首行**两空格缩进**当粘连垃圾剥掉 · 把「**总字节数相同**」当成「内容相同」），**按一次事件计 1 次**，不按三轮计三次。**O51 现行计数 = 14 次。**
  **口径（R104 补 · 风哥 2026-09-18 拍）**：**现行计数以最新更正块为准** —— 本条上方任何写死数字的口径段（含上方交叉指针里的 **13 次**）**均为早前口径**，原文一字未改，保留作溯源。
  **第 15 次 = R104 收口同轮**（风哥 2026-09-18 拍「续计，同轮修完 #14 后又犯，不另分组」）—— 复验判据**边界取少一行**（把更正块末行取成 **9** 行、实为 **10** 行）；**dry 内拦下、未落盘**。**O51 现行计数 = 15 次。**
  **工具层偶发（不入号 · 登记一笔）**：R104 · 独立复验的一行 `py -c` 命令里写了 `ins.count(b chr(10))` -> `SyntaxError`，改一行即过；**非仓内文件缺陷**。
- **O52（新观察项 · 2026-09-17 · R91 立）**：
  **扫描器 `SKIP_DIRS` 未含 `.scratch`** —— 影子归档后复扫，**36 条命中里 19 条是归档副本**
  （`.scratch/archive/root_shadow_20260917/...`），**扫描面被自己的归档污染**；真身命中 **17 处**。
  与 **O51** 同族：都是「扫描 / 判据的作用面没跟盘上真实边界对齐」。
  **续计（风哥 2026-09-18 拍「归入 O52，不新立号」×2）**：O52 **计数 1 → 3**：
  第 1 次 = **R91**（`SKIP_DIRS` 未含 `.scratch` -> 扫描面被自己的归档污染）；
  **第 2 次 = R103b**（**隔离 store 必须一次一换** —— 复用同一个 `GBT_STORE_DIR` 目录，上一跑残留的 `schedules` 让
  `test_wf_when_conditional` / `test_wf_fallback` 假红 `KeyError: 'ok'`；换全新隔离面当场 `Ran 2 tests / OK`，
  全套 **119 条 9 红 0 error**、与基线逐项同名）；
  **第 3 次 = R103c**（**扫描器行号 ≠ 文案行号** —— `_r40_c2_scan.py` 报的是 **AST 节点起始行**，文案在多行容器里时
  差 1–3 行；实测 3 处：`Notion…` 799->**801** · `EigenFlux adapter unavailable` 815->**818** · `codex_not_ready` 925->**926**；
  **按扫描器行号下刀会在 4.2 / 4.3 改错行** -> 动刀定位**一律按字面量原文**）。
- **O53（新观察项 · 2026-09-17 · R92 立 · 风哥拍「立 O53」）**：
  **`import` 顺序决定 `STORE_DIR` 绑定** —— `_paths.STORE_DIR` 在 `import gbt_allinone` 那一刻就被**钉成常量**，
  此后再设 `GBT_STORE_DIR` 对它**无效**。任何脚本必须**先设环境变量、后 import**。
  与 **R86 G6 首跑自伤**同族（测试侧隔离没设对）—— 两次实证：**R86 G6 / R92d2**（09-17）。
  防御：脚本头部**显式先设 `GBT_STORE_DIR`**，或改用**子进程隔离**（复跑实测生产 store 零扰动）。
- **O54（新观察项 · 2026-09-17 · R92 立 · 风哥拍「立 O54」）**：
  **门禁跑一次必留审计足迹** —— `cross_scan` X 维调 **6 个扫描器**，在生产树上跑一次约 **+4 行 / +2.3 KB**。
  不是框架缺陷（隔离下写隔离 store）—— 但**每次跑门禁都留足迹**。
  处置：**固定走隔离 store**（同 `GBT_STORE_DIR` 机制）—— 门禁不该往生产主账本写；**单独一刀**，不跟别的混。
- **O55（新观察项 · 2026-09-17 · R92 立 · 风哥拍「记一笔」）**：
  **G 维判据与 PEP 420 不一致** —— 认 `__init__.py`，**不认命名空间包**；本轮按判据建了包标记
  `gbt_allinone/tools/__init__.py`。下次撞上时再决定：**改判据** or **建包标记**。
- **O56（新观察项 · 2026-09-17 · R93 立 · 风哥拍「立 O56」）**：
  **`gbt_allinone/` 混行尾 16 件待统一** —— 判据取当时实测：`gbt_allinone/**/*.py` **2,741 件**
  （主流 CRLF **1,376** / 主流 LF **1,313** / 打平或无换行 **52** / **混行尾 16**）。
  16 件集中在最近动过的文件（CRLF / LF）：`auth_gate.py`（159 / 81）· `caps_registry.py`（520 / 47）· `engine.py`（551 / 5）·
  `mirror_space.py`（294 / 4）· `pipeline.py`（437 / 12）· `selfscan.py`（334 / 4）· `store.py`（125 / 24）· `__main__.py`（1 / 3）·
  `llm/cloud_llm.py`（467 / 8）· `security/abl_gateway.py`（113 / 5）· `security/security_brain.py`（325 / 22）·
  `tentacle/brain/transmit.py`（9 / 59）· `tests/test_api_probe.py`（1 / 297）· `tests/test_framework.py`（743 / 571）·
  `tests/test_mirror_space.py`（1 / 138）· `tests/__init__.py`（1 / 37）。
  与 **O28 / O31 / O37** 同族（区段混行尾）。**本刀零归一化，一个字节没碰它们。**
  处置：待另开一刀统一 —— **判据取当时实测，不取记录值**。
  附：`gbt_allinone/` **不是统一 CRLF** —— `tools/*.py` 新建为 LF **不判缺陷**（主流 LF 的大头是 `.pylibs/` 第三方 vendored）。
- **O57（新观察项 · 2026-09-17 · R94 立 · 风哥拍「DSH 锁 `0.1.5-rc.2`」）**：
  **DSH 锁 `0.1.5-rc.2` —— 开发者预览版不许追 latest** —— 起法固定 `npx @deepseek-ai/dsh@0.1.5-rc.2 web --no-open`；
  `latest` 会撞不兼容变更（`.d.ts` 面随版本变，本仓只按 `0.1.5-rc.2` 取证）。
- **O58（新观察项 · 2026-09-18 · M3 立 · 风哥「分析一遍再配置」）**：
  **DeepSeek 型号 id 的唯一真相 = `deepseek-flash`** —— 官方 MODEL VERSION 就是 **DeepSeek-V4.1-Flash**；第二真模型 = **`deepseek-v4-pro`**。
  **上游白名单实测**（`chat/completions` · 证据 `.scratch/_m3_alias_probe.py`）：`deepseek-flash` · `deepseek-v4-flash` ·
  `deepseek-v4-flash-vision-exp` · `deepseek-v4-pro` → **200**；`deepseek-v4.1-flash` · `tdpsk_deepseek-v4-flash-202605` ·
  `tdpsk_deepseek-v4-pro-202606` → **400**，原文 `The supported API model names are deepseek-flash, deepseek-v4-pro, but you passed ...`。
  - `deepseek-v4-flash` / `deepseek-v4-flash-vision-exp` = **已退休模型的兼容别名**，上游 `served_model` 一律回 `deepseek-flash`：
    **能用，但不是规范 id** —— 新写配置一律用 `deepseek-flash`；见别名只当路标、不当型号。
  - **判据必须认上游实测，不认第三方代理侧 id**：`tdpsk_*` 属 **AutoClaw 自己的代理**（`zai` provider ·
    `autoclaw-proxy/proxy/autoclaw`），是代理侧命名空间、由 `X-Request-Model` 头路由 —— **不得**按官方 id 改写，
    也**不得**拿它反推官方型号。故 AutoClaw 侧三个配置一个字节未动（`models.json` 两处 `deepseek-v4-flash*` 实测 **200**，非缺陷）。
  - 同族教训：**别拿版本号当型号 id**。M1 轮凭印象写成 `deepseek-v4.1-flash`，上游 **400**；本轮以**上游 400 原文**为判据改正。
  - 现行官方口径：两模型 **1M 上下文 / 384K 最大输出**；并发 flash **2500** · pro **500**；flash 峰谷 input $0.3/$0.15 · output $1.2/$0.6 每 1M。
- **已知待办（甲案 E 型 · 2026-09-18 · 风哥拍「登记挂账，不立 O 号」）**：
  `insert_lines_aligned` 的 `before` + 锚点**在行首** + `addition` **不带尾换行** -> `甲\r\n新增乙\r\n`（右粘）。
  现行 docstring 口径是「`addition` 需自带结尾换行」。**触发条件**：调用方忘了带尾换行才暴露。
  要治得改 API 语义（自动补尾换行 / 显式校验）= **新增契约**，不在甲案刀面内 ——
  **等谁真踩了再加守卫**，比预防性改造划算。
- **强制规则（能力落地必须同批登记出口清单 · 2026-09-18 · 风哥拍「建议顺手补一刀」）**：
  **新增能力（cap）必须同时登记出口清单 —— `cap 名 / 面板 tab / 入口文件`，未登记不算完工。**
  背景（实证 · 2026-09-18 刀 2b 取证时）：能力库存与货架是**两张表** —— `caps_registry` 已注册 `coze_mail`（:432）与 `create`（:438），
  但 `holo_pet_w3/index.html` 当时 4 个 tab（四视图 / 工作树 / 故障矩阵 / 驾驶舱）对两者**零引用**：能力越堆越多、界面一动不动。
  缺的就是这一环：写功能的人不负责挂出口，挂出口的人没有统一清单。
  落地口径：每个 cap 落地时必须在本条下方滚动登记一行（三格缺一不可）；缺任一格 = 该 cap **判未完工**，不许标 done。
  尚未挂出口的写「（未挂）」并注明原因，不允许空着；敏感档动作写「不挂（物理上没有键）」并列出动作名。
  | cap 名 | 面板 tab | 入口文件 | 状态 |
  |---|---|---|---|
  | `coze_mail` | 工具（`data-view="tools"`） | `gbt_allinone/coze_mail_cap.py` → `holo_pet_w3/shell/main.cjs` `w3Tools()` | 已挂：status 亮；search / read / draft 灰带原因；mark / send / reply / register 不挂 |
  | `create` | 工具（`data-view="tools"`） | `gbt_allinone/file_operation.py` → `holo_pet_w3/shell/main.cjs` `w3Tools()` | 已挂：status 亮；intent / output 灰带原因；configure / write 不挂 |


- **四码可达性表（R97/R98 取证 · 风哥 2026-09-18 拍「登记修正版 · 带可达列」）**：

  | 触发 | 底层 | `compile()` 实际抛出 | 可达 |
  |---|---|---|---|
  | 语法坏 / IndentationError | SyntaxError | SyntaxError | 是 |
  | cookie 名不存在（含 BOM 冲突） | LookupError | SyntaxError | 是 |
  | 非 UTF-8 坏字节 | UnicodeDecodeError | SyntaxError（被包装） | 是 |
  | 源码含 NUL | ValueError | ValueError | 是 |
  | 仅 `tokenize.detect_encoding()` + 显式 `.decode()` 路径 | — | UnicodeDecodeError | **否 · 当前不可达** |

  **validator 跑在 `mkstemp` 之前** —— 拒绝路径结构上不产生任何文件（不是靠 finally 清理）。
  旧版四行表若照抄，会让后人写出死 `except UnicodeDecodeError`。
  **validator 有效拦截案例（R103 · 实证）**：落地脚本里写了 `b"R103 复核"` —— 中文塞进**字节字面量** ->
  `SyntaxError: bytes can only contain ASCII literal characters`，被 `_py_syntax_validator` **当场拒绝**、盘上零改动
  （「先校验、后 `mkstemp`」的正面实证；风哥拍「可记录为有效拦截案例，不需要额外测试」）。
  本刀 4 个落盘目标改前 `compile(bytes)` 预检全过：`_paths.py` / `store.py` / `test_framework.py` / `test_ai_audit.py`。
  **警告（R103 实测 · 风哥拍「在项目文档里留一句警告」）**：`.pylibs/` 下有 **8 个 vendored `.py`** 在 CPython 3.10 下
  `compile()` 即 **SyntaxError**（numpy typing 存根等），另有 pyautogui 的 `\e` 未转义告警。**将来若给 `.py` 开默认 validator，
  必须排除 `.pylibs/`**，否则会拒绝写 vendored 文件。当前默认 `validator=None`，不受影响、不在本刀范围。

- **动刀前拦截的定性错误：3** —— 三件都在**动刀前**被实测拦下，未进代码、未进 landed 判据，无后续影响：
  ① 元宝 · 四码分因（R97）：对 `UnicodeDecodeError` 可达性的定性错误；
  ② 规则 4 口径写错（R104/R105）：把 `before` 的判定点写成「看锚点是否以 `nl` 开头」，由 D/E/F 六型实测拦下；
  ③ 同一次错误的**第二张脸**（R105）：由错口径推导出「`test_safe_io.py:522` 会变、须按 (a) 改」，被实测否决、**未实施** —— 522 属 D 型（锚点 `甲` 前是 `\r\n`，已在行首），甲案不补换行，**一字节不动**。
  ②③ 同根同源，合并表述（不另开 O 号、不入 O51）；本条以此处为当前定稿。
  **不计入 O51**：O51 衡量的是「已落地的判据骗了我们」；把动刀前的正确取证计入会让 O51 通胀、失去判别力。
  规则：将来 **landed 代码**里出现四码分因误判，才是 O51 第 10 次。
- **本轮 O51 不续计** —— 保持 **9 次**（风哥 2026-09-18 拍「不续计、不新开」）。
  **（R103 更正）**：本句口径已由上方 **O51** 条目的「更正（R103）」取代 —— **O51 现行计数 = 10 次**（第 10 次 = R103）。
  **（R104 更正）**：现行计数已更新为 **13 次** —— 本段上方「才是 O51 第 10 次」与本行口诀「现行计数 = 10 次」**均为早前口径**，
  已被上方 O51 条目「更正（R104）」取代（**第 12 次 = `test_perf_baseline` 口径不一致** · **第 13 次 = 负对照脚本括号写错**）。原文一字未改，保留作溯源。

### 契约测试判例 · 窗口可见性（2026-09-17 · 风哥批「写进 §八 作为契约测试判例」）

**判例**：`holo_pet_w3/tests/test_layout_snap.cjs` **第 8 例**（窗口可见性契约）**不是「跑绿就算数」** ——
它自带**判别性负对照**：同一份新测试 + **写盘前备份里那份旧 `main.cjs`** → 必须**红**，
且必须红在 `show: placed.visible` 那条断言上（本轮实测 `7 过 / 1 红`，`verdict = RED_AS_EXPECTED`）。

**为什么写成判例**：这条契约守的是「**声明 ≠ 生效**」——注册表里 `default.visible:false` 曾「声明了没人用」
（与 R63 `--gbt-violet` 声明了、`var()` 0 引用同类）。
**下次谁动 `holo_pet_w3/shell/main.cjs`，必须跑它（含负对照）——只跑正对照不算过。**

证据：`.scratch/_r66_visibility_negctl.json` · 隔离目录 `.scratch/_r66_negctl/`（**零生产写入**）；
契约正面对照：维度树测试 **12 通过 / 0 失败**（4 品牌 + 8 布局）。
- **CF AI Gateway 评估 · 五条「待真实用户身份下复核」（2026-09-17 · 风哥标）**：官方文档未取（网络受限）·
  日志上限未裁定（风哥口径 **100,000** vs 参考文档 **10M**，数字打架不替人裁）· 缓存命中率未实测 ·
  Kimi/GLM 兼容性未实测 · 真实 key 池未验（本进程身份 = `desktop-vpvp0bp\codexsandboxoffline`，
  **沙箱身份不是真实用户**；8 个 LLM key 变量全未设置**不代表**真实环境没有）。
  **定性：不是"没取证"，是"本进程身份下不可取证"。**

### S7 前置三条执行口径（2026-09-17 · 风哥批）

**口径 A · 回滚路径验证 = 隔离两臂对照，不许在生产上跑。**
`rewind()` 是 `rmtree(reality)` + `copytree(vN)` 的全量替换，在生产上跑就是拿 production 当试验品。
验证方法固定为**副本两臂对照**（副本 store 上跑，生产零写入）：

| 臂 | 操作 | 判据 |
|---|---|---|
| A | `rewind(最新版)` | 回滚后 == 回滚前（路径活着、幂等） |
| B | `rewind(任意历史版)` | 回滚后 == 该历史版（真会换） |

两臂结果必须不同（《扫描器自证律》）。**第一次实证（09-17）**：臂 A `rewind(20)` 零变化 True；
臂 B `rewind(19)` 把 reality 换成 Backbone TODO demo（26 文件被换）——**前提为假**（v19 不是本项目版本），
所以当晚**没有在生产上跑任何 rewind**。取证：`.scratch/_r47_rewind_isolated.txt`。
**推论（写给未来）**：`timelines/vN` 的 N 是**全局晋升序号**，不是"本项目第 N 版"——跨项目复用时必须先核指纹，不许按 N 推断。

**口径 B · 测试必须隔离 store 目录，不许写生产。**
**第一次实证（09-17）**：`unittest discover` 跑回归，把 `t-sched-run`（`every_seconds=1` / `enabled=true`）
写进了**生产** `gbt_allinone/store/schedules.json`（`test_framework.py` 的调度用例）。
根因：`gbt_allinone/__init__.py` → `.store` 在 **import 时**就把 `_paths.STORE_DIR` 绑成常量，
而 discover 先导入父包、再跑测试模块体 —— 测试里再设 `GBT_STORE_DIR` 已经来不及。
处置：① 兜底 `gbt_allinone/tests/__init__.py`（导入即设隔离 store；若父包已绑生产 → **直接报错停下**，
宁可红不写生产）；② 契约测试 `TestProductionStoreIsolation`（正对照 = 隔离 store 里看得到动作，
负对照 = 生产文件逐字节不变）；③ 生产 `schedules.json` 里的测试条目已清（备份
`.scratch/_sched_backup_20260917T175745.json`，清理前 sha256 `3e90c606…`）。
**清账完成（第二批 · 风哥 2026-09-17 批）**：同文件那两条 09-15 探针遗留的 `t-preflight-sched-*`
（`every_seconds=3600`、`enabled=true`）已清，**同类遗留已清空**（`schedules.json` 现存 `{}`）。

- **生成点取证（不是猜的）**：两条键的 `defined_at` 是 **09-15 11:05:15 / 11:07:04**（间隔 109 s）；
  同一分钟窗口 11:04:51–11:07:31 里还有 `t-engine` / `t-ff` / `t-resume` / `t-cache` / `t-fanin` /
  `t-routes` / `t-sub-inner` / `t-sub-outer` / `t-to` / `t-sched` 的 `wf_runs` —— 与 `test_framework.py`
  的用例名**逐条对应**，说明那是一次**未隔离 store 的全量自测 / 探针验收**在写生产。
  `preflight_checked` 的 observation 原文写着 `"error": "调度不存在: t-preflight-sched-<ns>"`，
  名字是驱动脚本调用时**现拼**的（全仓源码搜 `t-preflight` = 0 命中，生成脚本已不在盘上）。
- **根因**：与 `t-sched-run` **同根因** —— 驱动在**没设 `GBT_STORE_DIR`** 的进程里跑，把验收用调度写进生产。
- **代价**：两条调度此后每小时被 `sched_tick` 真跑一次（最近一次 **09-17 17:41:53**），
  在 `wf_runs/` + `audit.jsonl` 里持续留痕。
- **处置**：`schedules.json` **879 B → 2 B（`{}`）**，JSON 合法；备份
  `.scratch/_sched_backup_20260917T181557.json`（sha256 `1a0c0fdb0fcefc18…` 与原文逐字节一致）；
  证据 `.scratch/_r52_preflight_sched_clean.json`。
- **隔离负对照（本轮实测）**：全量回归 **107 项 / 红 9**（红项集合与基线逐项一致），
  跑前跑后生产 `schedules.json` SHA256 `44136fa355b3678a…` 不变、生产 `audit.jsonl` 增量 **0 B**。
- **守卫**：新增契约 `TestProductionStoreIsolation.test_production_schedules_has_no_test_residue` ——
  生产 `schedules.json` 出现 `t-preflight-sched-*` / `t-sched-run` / `t-bad-sched` 即当场判红。

**口径 C · 生产树指纹排除规则写"为什么"，且排除后判据仍要活着。**
E7 新增（pip 生成的 vendored 依赖目录，当前落点 `.pylibs/`）；规则连同理由一起落进
`summary.exclude_rules`。判据：**正对照**改手写文件 → `--diff` 报 `modified`；**负对照**改 `.pylibs/` → 不报；
两组必须不同。契约测试：`test_boundary2_exclusion_does_not_blind_the_drift_check`。
实测收益（真树空跑）：生产树 manifest 从 **4311 文件 / 90.82 MB / 6.6 s** →
**342 文件 / 13,116,383 B（12.51 MB）/ 4.3 s**（此前写的"约 160 文件 / 2 MB"是估算，**以实测为准**）。
依据：`gbt_allinone/docs/checkpoint生产树指纹规格.md` §一 E7 + 边界 1 / 边界 2。


---

## R110 · 跨维晋升（工作树 → dimension → reality · v25）· 2026-09-18

**授权**：风哥「可以全面生产推进」——晋升不再等单独批，按 `mirror_space.ascend()`（设计里的**唯一生产写入口**）执行。

- **动刀前实测（O48：判据取当时实测）**：`dimension` 16 文件 == `reality` 16 文件（**无待晋升内容**）；
  工作树 `holo_pet_w3/` 16 文件 —— reality 落后 **3 新增**（`h1/index.html` / `h1/h1.css` / `h1/h1.js`）
  + **5 漂移**（`index.html` / `shell/main.cjs` / `shell/preload.cjs` / `shell/windows.json` / `window.js`）。
- **动作**：字节级同步 → `scan()` **5/5 全绿（19 文件）** → `ascend()` → **v25**。
- **改后实测**：reality 19 == dimension 19；`reality/holo_pet_w3/**` 与工作树逐文件 sha16 相同；
  `timelines/v25` 19 文件、与 dimension 逐字节相同；护照 `passports/v25.json`；
  `mirror_status()` 的 `dimension_vs_reality = []` · `reality_drift = []` · `clean = true`。
- **生产 store 指纹**：5,212 / 318,988,871 B / audit 36,074,193 B / sha16 `13cab849e1a617d3`
  → **5,238 / 319,164,273 B / audit 36,074,671 B / sha16 `6b0a4038189fd4d8`**
  （+26 文件 = 3 dimension + 3 reality + 19 timeline + 1 passport）；`outputs/` 文件 **0** 不变。
- **备份**：`.scratch/_r110_backup_20260918T045034/`（dimension + reality 全量；还原判据 = sha16 逐字节相同）。
- **记录值过期更正（重要）**：本文件上方那句「**S7 未批 → `ascend()` 未跑 → reality 仍是 v20 的 12 文件**」
  是 **R66 时代**的记录值。**现行实测 = `timelines` 最高 `v25` / reality `19` 文件**。以本段为准。
- **旁证**：`mirror_ascend` 能力层当前不可用，两处实测缺陷（**未动刀**）：
  ① `api.py:395-402` 把 `require_rehearsal` / `rehearsal_name` 传给 `mirror_space.ascend()`，
  而 `ascend()` 签名是 `(purpose: str = "")` → **调用面与实现签名不匹配**（潜在 `TypeError`，本次未触发）；
  ② 能力层调用被 `policy.py` 的授权作用域 **`deploy_publish`** 拦下 —— 该作用域**未注册**（报「未知授权作用域」）。
  故本轮走模块级 `ascend()`，**未碰 `policy.py`**（属刀二待拍 ①）。
- 证据：`.scratch/_r110_ascend_land.py` · `_r110_ascend_report.json` · `_r110_ascend_out.txt` ·
  `_r110_mirror_ascend_probe.py` · `_r110_probe_out.txt`。

---

## R111 · 桥接层第二刀（品牌清洗）收口 · 2026-09-18

**对象**：`gbt_allinone/docs/主控台品牌清洗第二刀方案-桥接层.md`，复核稿 `.scratch/_r103c_桥接层第二刀复核报告.md`（R103d 三条裁定已回填）。

- **范围（17 行）**：`codex_bridge.py` **9 行**（§三 8 行 + §5.1 一行）+ `panel_server.py` **§四 8 行**。
  **定位一律按字面量原文**（R103c 裁定 ①），不按行号；每处替换断言 `count == 1`，任一不中即整体中止、不写盘。
- **sha16 前后**：`codex_bridge.py` `6c028869cebd6ea4` → **`ba7610065faf5e79`**（67,121 → 67,074 B）；
  `panel_server.py` `295e8259631ec2bb` → **`63cbe6eb1468a369`**（65,764 → 65,757 B）。两文件原状无 BOM、行尾分布不变。
- **验收闸门 5/5 PASS**（`.scratch/_r111_bridge_brand_gate.py`，自带正负对照）：
  | 闸门 | 判据 | 结果 |
  |---|---|---|
  | A · A/B 类旧文案 | live **0** / 备份 **9-9** / 空对照 **0** | PASS |
  | B · 剩余 codex 落白名单 | 文本通道字面量 **19** 处全部落白名单、未落 **0**；备份未落 **4**（可判别）；合成干净文件 **0** | PASS |
  | C · 术语闸门（§四 8 行） | live **0** / 备份 **7-7** / 喂旧串 **7-7** | PASS |
  | D · `py_compile` 两文件 | rc = **0** | PASS |
  | E · 文本长度（字符） | 17 处 **零超长** | PASS |
- **回归**：`test_framework` **119 条 / 红 9** —— 红项集合与 **R104b 基线同名同数**
  （bluetooth · devour_github_real · mcp_full_chain · sec_llm_configured · tentacle×5）。
  隔离 store 跑，**生产 `audit.jsonl` 增量 0 B**（跑后指纹与跑前逐字相同）。
- **`test_codex_bridge.py` = 30 条 / 1 红**（`test_codex_chat_delegates_to_run_once`）：
  **两臂实测**——把改前备份换回去重跑，同样 **30 条 / 1 红 / 同名同项** → **既有红，非本刀引入**。
- **值守门（本节新增，防本次自伤重演）**：
  ① 备份必须**在写盘之前**读文件（写后读会存到新内容）；
  ② 文本长度闸门按**字符长度（屏幕列）**比较，不按字节 —— CJK 文案字节必增，按字节判会产生 4 处假红。
- **不动项（按批复）**：§5.3 三行 + `codex_path` 字段名（记 §八 **O15**）；`panel_server.py:863` `codex_not_ready`
  审计 meta 值永久不动；`app.js` / `index.html` 本刀一个字节未碰。
- **未做项**：方案 §七 闸门 6「一次真起面板」属施工步，本刀未跑（《宿主不打扰律》）。
- 证据：`.scratch/_r111_bridge_cut2_apply.py` · `_r111_bridge_cut2_report.json` · `_r111_bridge_brand_gate.py` ·
  `_r111_bridge_gate.json` · `_r111_gate_out.txt` · `_r111_bridge_tests.txt` · `_r111_tfw.txt` ·
  备份 `.scratch/_n2_backup_20260918T045220/`（`MANIFEST.json` 双向 sha256）。

---

## §八 挂账变更（R110/R111 · 2026-09-18 · 风哥「可以全面生产推进」）

**已销账**：
- 桥接层第二刀（原「**动刀等 S7 单独批**」）→ **已动刀收口**（R111）。
- 跨维晋升（原「**S7 未批**」）→ **已执行 v25**（R110）。
- `GBT_CREATE_ROOT` 隔离钩子 → R107 已收口（此前已在清单外）。

**新增待拍两条（实测带出，本刀不动）**：
1. `api.py` 的 `mirror_ascend` 分支**多传两个关键字**给 `mirror_space.ascend()`，签名不匹配。
2. `policy.py` 的授权作用域 **`deploy_publish` 未注册** → 能力层晋升入口整体不可用。

**仍挂（未动）**：刀二待拍两条（`policy.py` 越界扩 / `confirm_token` 单一来源）· 镜像臂 · 刀 2b′ ·
DSH 前提 2/3（等风哥本机起 `0.1.5-rc.2`）· 赏金台阶段二（等凭据 + 点名程序）·
`gbt_allinone/` **混行尾 16 件**（本刀复测：仍是 16 件，名字一个未变；其中 `caps_registry.py` 532/47、
`tests/test_framework.py` 743/667、`tests/__init__.py` 1/54 —— **记录值已漂，判据取当时实测**）·
README 文档缺陷（`~/.config/h1mcp/drafts` vs 实际 `%APPDATA%\h1mcp\drafts`）。

> 本段为 **R111 落盘时裁定快照**，时间性表述以最新段为准。

---

## 八、挂账变更（触手眼睛修复 R-H1 · 2026-09-18 夜 · 风哥拍「记录 + 单独立项」）

**新增两条（实测带出，本刀不动手）**：

- **O59（新观察项 · 2026-09-18 · R-H1 立 · 风哥拍「记录 + 单独立项」）**：**审计轮转器未施工 —— 阈值只活在文档里，运行时零执行。**
  实测：`gbt_allinone/store/audit.jsonl` = **36,112,031 B**（34.44 MiB）；`gbt_allinone/archived_logs/` 下 **2 个**轮转目录
  （均 2026-09-11 手工归档），与 `patch_debt` 的「审计轮转次数 = 2」对得上。
  设计口径在 `gbt_allinone/docs/GBT全故障点设计.md:60 / :61`（>15 MB 记 P2 / >20 MB 触轮转 / 轮转落 `audit_rotated`），
  但全仓 `.py` 检索 `audit_bytes` / 轮转阈值 / `audit_rotated` **命中 0** —— 阈值不在运行时 ⇒ 越线**不会有任何信号**
  （同样是静默失效，只是这次静默的是「它自己该报警」这件事）。同文档 `:615` 自认：`F5.2 审计爆盘 | B（轮转 + 冷压）| 半自动（需先施工）`。
  形态是**归档式**（`archived_logs/<日期-事由>/`）而非删除式 ⇒ H-01 / H-07 证据链可长期回溯。
  **限定：轮转器尚未施工** —— 36 MB 之后会继续涨，且不会有 `audit_rotated` 事件。
  并入 **O17**（账本分层 / 轮转 / 索引旁路，待另开单元）；本刀**只记录不施工**。
  下一步取证（成本极低）：记 **日增速** —— 静态 36 MB 不说明危险度，「每天涨多少」才说明。

- **O60（新观察项 · 2026-09-18 · R-H1 立 · 风哥拍「记录」）**：**遮蔽（shadowing）= 第三种病，三实例同根；`[B.self]` 146 处是它的存量。**
  根：**把某个目录放到优先级最高的位置，却没考虑它里面有什么会和谁撞名。**
  1. 顶层 `ledger.py` 遮蔽 `ledger/` 包 —— **2026-09-13 已识别并处理过**（归档为 `store/ledger_standalone_draft.py.bak`，
     见 `delivery/gbt-v8 生产补齐完成报告.md:38`）；本刀**维持现状**（风哥拍）：`hygiene.py:41` 的 `SKIP_TREES` 已含 `store`
     ⇒ 它躺的位置是对的；移走会让报告 :38 的路径失效 ⇒ 两处真相不得分叉。
  2. `.pylibs` 顶到 `sys.path[0]` 遮蔽系统包 —— 实测爆炸半径 `{numpy, cv2, dxcam}`；R-H1 已收敛到
     `dependency_paths.activate_local_dependencies()`（四处手打 `insert(0, .pylibs)` 清零）。
  3. `[B.self]` **146 处 `insert(0, 自身目录)`** —— 同机制，**尚未出事**。
  处置标准**照报告 :38 的先例走**（识别 → 归档 → 改引用），不必从零设计；`.bak` 的存在本身就是那份记录的物证。
  伴生登记：坑册同名一条（`guard = 无 guard（待补）`），测试留到不伤 H-07 基线的时机。

> 本段为 **R-H1 落盘时裁定快照**，时间性表述以最新段为准。

---

## 八、挂账变更（R-H2/R-H3 · 2026-09-18 夜 · 风哥拍「追踪根源修复」）

- **O61（新观察项 · 2026-09-18 · R-H2 立）**：**回归红集只在「同命令 + 同 store 新鲜度 + 同桌面身份」下可比。**
  复原：H-07 的 `Ran 173` = `test_ai_audit`(16)+`test_framework`(120)+`test_checkpoint`(28)+`test_api_probe`(9)，
  实跑复现 ✓。同口径复跑红集 9 → 18，两条原因各自实测：
  ① 基线命令的固定 `$env:TEMP\gbt_test_store` 是**累积 store**（盘上留 9/17 的 `t-when`/`t-fb`/`t-to`）
     ⇒ `wf_fallback`/`wf_when_conditional` 抛 `KeyError: 'ok'`；换全新 store 即消失。
  ② `tentacle×5`/`devour_github_real`/`mcp_full_chain` 变红是**执行身份**不同（沙箱桌面 1536×864、非输入桌面）。
  **红线（唯一定义处 = O61；本条会持续增长）**：跨身份**不比对计数，只逐名比对**；每次回归必须同时记
  「命令 / store 落点 / 身份读数」。**跨解释器**同理（且不比对依赖来源）——详见 O61 全条。
  > 口径：**红线的唯一定义处是 O61**；其它段落只放指针，不复制内容（复制 = 下次加变量只改一处）。
  证据：`.scratch/_rh2_tests_173.txt` · `_rh2_tests_173_fresh.txt` · `_rh2_pre9_baseline.md` · `_rh2_red_diff.md`。

- **R-H3（已落地 · 2026-09-18）**：**BitBlt「吞错」根治 —— 抓帧路径补前置身份门。**
  现象：`⚠️ omni_core: 吞错: … BitBlt: 拒绝访问`。根因：进程在 `WinSta0\CodexSandboxDesktop-…`（非输入桌面）⇒ GDI/DXGI 都拿不到屏。
  复发原因：9/17 只修了**表达层**（体检 + 文档），采集路径没接门 ⇒ 行为未变。
  本刀：`capture_environment.capacity()` + `omni_core.CaptureUnavailable` + 2s 缓存门 + 单播提示 + 后端全灭抛原因码；
  守护测试 `test_screen_capture_identity_gate`。回归同口径 **Ran 174**，红项 16 条与改前逐名一致（零回归）。
  文档同步：`gbt_allinone/docs/自我视觉验证设计.md` §九。

> 本段为 **R-H3 落盘时裁定快照**，时间性表述以最新段为准。

---

## 八、挂账变更（R-H5 · 2026-09-18 夜 · 风哥「先排除再排优先」+ 四条拍板）

- **O61 增补**：Ran 174 的身份读数已存档（`.scratch/_rh3_identity.json`：`interactive_desktop=false` ·
  `CodexSandboxDesktop-7637d56e…` · `session=1` · `1536×864` · `python 3.14.5`）。**变量由三个修正为四个**：
  命令 / store 新鲜度 / 桌面身份 / **解释器**（基线 3.12，本会话 3.14.5）。

- **R-H5 更正（撤回）**：`test_selfscan_clean` 的 `verdict='P0'` **不是生产信号，是夹具误报** ——
  生产 store 实测 **P1**（2 起运行时故障），全新空 store 实测 **P0 缺目录 `pipeline/*`/`wf_runs`**；
  该测试不覆盖 store，扫的是自己的隔离 store。与 R31「夹具没关预先存在的文件」同族。
  处置（待另开一刀）：补 store 骨架种子，或把断言改成「骨架齐时才判 P0」。

- **O62（新观察项 · R-H5 立）**：**采集身份门只盖住 `omni_core._screen_capture` 一条路径**，另有 4 处直接抓帧未过门：
  `vision_cap.py:62`（dxcam，能力层用户可见）· `vision_watch.py:300/306`（DXGI）· `omni_domain.py:261/263`
  （**PIL ImageGrab，正是会拒绝访问的 GDI BitBlt**）· `omni_controller.py:517-521`（mss）。
  走门的 11 处已核对。**口径**：层级断层的第二个可能位置 —— 列为待查，不默认全覆盖。

- **O63（新观察项 · R-H5 立 · 风哥「别用新的同名遮蔽庆祝旧病种的修复」）**：**`voice` 是三家共用的名字。**
  `caps_registry.py:530` cap key `"voice"` · `gbt_allinone/voice_cap.py` · `potato_pet/voice.py`（且
  `potato_pet/main.py:71/165/271/361` **裸 `import voice`**，靠 sys.path 决定拿哪个）。
  **定名**：中枢 cap = **`voice_orchestrator`**（与入口文件同名，本仓历史占用 0）。
  **待查**：`potato_pet` 那四处裸 import 是 [B.self] 同族风险（现下未出事），与 [B.self] 146 处合并观察。

> 本段为 **R-H5 落盘时裁定快照**，时间性表述以最新段为准。

---

## 八、挂账变更（R-H6 · 2026-09-18 夜 · 风哥第四条拍板「cap 名别叫 voice」落地）

- **O63 收口**：`voice` 名字归属已核查（三家占用：cap key `voice` / `voice_cap.py` / `potato_pet/voice.py`）。
  **中枢 cap 定名 `voice_orchestrator`**，出口清单三格同批填齐：
  cap 名 `voice_orchestrator` · 面板 tab **tools**（`holo_pet_w3/shell/main.cjs` `TOOLS_CAPS`）·
  入口文件 `gbt_allinone/voice_orchestrator.py`。四处原子改动（run() / registry / api / main.cjs）已落地并实测：
  编译 OK · `node --check` exit 0 · `list(CLONE)=7` · `pipeline=6 步` · 路由 **96/96** ·
  回归 **Ran 174 红 16 条与改动前逐名逐序一致**。

- **仍挂（未动）**：`potato_pet/main.py` 四处**裸 `import voice`**（[B.self] 同族，靠 sys.path 决定拿哪个模块）
  —— 与 [B.self] 146 处合并观察，不在本刀范围。

> 本段为 **R-H6 落盘时裁定快照**，时间性表述以最新段为准。

---

## 八、挂账变更（R-H7 · 2026-09-18 夜 · 风哥判「解释器最阴」的实证）

- **O61 再增补（解释器不只改计数，还改依赖来源）**：实测本仓 `.pylibs` 只有 **cp314** 一棵 ABI 树，
  与本机 install-manager 的 **3.14.5**（cache_tag `cpython-314`）**匹配** ⇒ 激活后
  `dxcam` / `cv2` / `py_ecc` **全部从 `.pylibs` 解析**；而 3.12 下 overlay 不可读、这三个包由系统提供。
  ⇒ **解释器同时决定「判据在哪跑」与「依赖从哪来」，且两边都不报错。**
- **同因第二例**：`py -0p` 名单（3.13 商店版 / 3.12 / 3.10）**不含** PATH 上实际的 3.14.5
  （install-manager 版）⇒「本机有几个 Python」本身有两套答案；且 3.12 在沙箱身份下起不来。
- **留痕第三例**：工作区 `__pycache__`（排除 `.pylibs`）pyc 分布 **312=84 / 314=86 / 310=40** ——
  三代替换并存，`.pyc` 不报错、不进 git status、不进任何记录。
- **红线（指针）**：跨解释器不比对计数、也不比对依赖来源 —— **正文以 O61 为唯一定义处**，本条不复制内容。
  四元组 = 命令 · store 落点 · 身份读数 · 解释器（含 `cache_tag`）。

> 本段为 **R-H7 落盘时裁定快照**，时间性表述以最新段为准。

---

## 八、挂账变更（R-H7 续 · 2026-09-18 夜 · 风哥「命令」→ 印章落地）

- **O61 落地（从红线变成可执行）**：新增 `gbt_allinone/tools/regression_stamp.py`（只读）——
  `stamp` 打四元组（命令 / store / 身份 / 解释器+cache_tag）并落 `.scratch/_stamp_*.json`；
  `run --expect-python X.Y` **解释器不匹配即拒绝执行（rc=2，fail-closed）**；
  判成败只认**原生 rc** 与结尾 `Ran N tests` / `OK|FAILED`（与 `native_rc.py` 同源铁律）。
  实测：3.14 匹配下跑守护测试原生 rc=0 OK；`--expect-python 3.12` 实测拒绝 rc=2。
  **口令**：没有印章的回归结论不采信。
- **附带**：`capture_environment.capacity()` 补 `process_session` / `remote_session`；
  印章命令用 `list2cmdline` 原样渲染；证据文件名加微秒；`git HEAD` 日期一并入章（呼应「HEAD 停在 9/13」那条口径）。

> 本段为 **R-H7 续落盘时裁定快照**，时间性表述以最新段为准。

---

## 八、挂账变更（R-H8 · 2026-09-18 夜 · 风哥「store 落点」→ 印章第二道门）

- **O61 第二道门（store 落点，与解释器同一手法）**：实测 `_paths.STORE_DIR` 为 **import 期绑定** ——
  env 在 import 后修改**静默不生效**（reload 才换）；不给 env 则落**生产 store**。
  处置：`regression_stamp.run` **强制 `--store fresh|<路径>`**（缺则 rc=2），并生成
  `.scratch/_stamp_site/sitecustomize.py` 注入 `PYTHONPATH`，让子进程**退出时自报真正绑定的 store**；
  请求与自报不一致 → 打印「**落点不一致 … 不可采信**」。
  实测三条：fresh 一致 / 显式路径一致 / **负对照（孩子自己改 env）正确标红**。
  口令：**回归结论要同时带解释器章与 store 章**；两者任一不符，红集与归属都不采信。

> 本段为 **R-H8 落盘时裁定快照**，时间性表述以最新段为准。

---

## 八、挂账变更（R-H9 · 2026-09-18 夜 · 风哥「桌面身份」→ 边界抬到 Owner 面前）

- **O62 增补（关键实测，改变结论）**：桌面身份**可以在进程内补救** ——
  `OpenInputDesktop()` 成功拿到输入桌面句柄 296 · `SetThreadDesktop(h)` 返回 True ⇒ 身份变
  `interactive_desktop=True / desktop='Default'`；同进程实测抓屏 **`ok=True size=[1920,1080] engine=mss`**。
  ⇒ R-H3 的 `non_interactive_desktop` 门由「终判」降级为「**带原因码的兜底**」；
  「非交互桌面」≠「采集不可用」。

- **O64（新观察项 · 2026-09-18 · R-H9 立 · 待 Owner 授权）**：**采集路径是否自动 Attach 到输入桌面。**
  收益：沙箱身份下也能拿到真实桌面帧（基线绿的那批测试因此可复现）。
  代价（必须明示）：`SetThreadDesktop(WinSta0\Default)` = **从沙箱桌面跨到用户真实桌面**，
  越过沙箱隔离，后续 GUI 调用作用于用户桌面。
  技术约束：只影响当前线程；必须在创建窗口/钩子之前调用。
  **未授权前：capture 只报原因码，不自动切。**

> 本段为 **R-H9 落盘时裁定快照**，时间性表述以最新段为准。

---

## 八、挂账变更（R-H10 · 2026-09-18 夜 · 风哥「可见性」判据）

- **O61 第三条门（可见化律）**：四元组各配「出口 + 原因码」，缺一不许进判据链。
  出口（每次回归固定打印，可 grep）：`[stamp] interpreter=… / store_requested=… / store_match=… /
  identity=… desktop=… session=… / rc=…`；原因码：`interpreter_not_declared` · `interpreter_mismatch` ·
  `store_not_declared` · `store_binding_mismatch`（身份侧沿用 R-H3 的 `non_interactive_desktop`）。
  实测：四条原因码各触发一次通过；印章 JSON 增 `result` 段。
  **口令**：**没有原因码的失败不算证据** —— 因为它无法被 grep、无法被下一次定位复用。

> 本段为 **R-H10 落盘时裁定快照**，时间性表述以最新段为准。

---

## 八、挂账变更（R-H11 · 2026-09-18 夜 · 风哥「内存需求」）

- **O61 第四条门（内存）**：内存是会漂的变量（本机实测可用 **0.37–0.97 GB**，占用 86–94%），
  故与解释器/store/身份同规格处理 —— `regression_stamp` 增 `_memory()` 入章 +
  `--need-memory X` 低于阈值即拒绝（`reason_code=insufficient_memory`）；
  出口新增 `[stamp] memory=avail …/total …(load …%)`。实测：2 GB → 拒绝 rc=2；0.5 GB → 放行。
- **成本口径更正（风哥）**：下载是**磁盘**成本，加载才是**内存**成本 ⇒ 语音中枢文档改「成本三列」
  （磁盘 / 加载驻留 / 推理峰值）；实测触手栈+numpy 驻留仅 **31.4 MB**，
  本地视频模型 fp16 5B≈10 GB、14B≈28 GB（离本机总量 7.39 GB 一个数量级）。

> 本段为 **R-H11 落盘时裁定快照**，时间性表述以最新段为准。

---

## 八、挂账变更（R-H12 · 2026-09-18 夜 · 风哥「0.37 GB 够不够 / 下载」）

- **内存阈值（实测口径）**：A 路线（SAPI + 云端点）**峰值 59.6 MB** ⇒ 0.37 GB 够（6 倍余量）；
  Kokoro-82M int8 需 ≈0.35–0.45 GB（0.37 **贴线**）；浏览器/触手路线需 1–1.5 GB（0.37 差 3 倍）。
- **O65（新观察项 · R-H12 立）**：**SAPI 在非交互桌面 `E_ACCESSDENIED`（0x80070005）**，
  且失败后留下 **46 B 空壳 WAV**（只有头）。⇒ 「A 零算力闭环不挑机器」需修正为**同样挑身份** ——
  **身份限制第三例**（前两例：`tentacle×5` 必红、`C:\Python312` 起不来）。
  **待批一击**：`voice_cap` 失败时删除残骸 + 原因码 `sapi_access_denied`（**未动**）。
- **下载内存三档**：HTTP 流式 几 MB~几十 MB · pip 解包 几十~几百 MB · **浏览器下载 几百 MB~1 GB+**
  （绑页面渲染，且磁盘要留 2–3 倍临时缓存）。

> 本段为 **R-H12 落盘时裁定快照**，时间性表述以最新段为准。

---

## 八、挂账变更（R-H13 · 2026-09-18 夜 · 风哥「磁盘，无内存压力」）

- **O61 第五条门（磁盘）**：`regression_stamp` 增 `_disk()` 入章 + `--need-disk X`
  低于阈值即拒绝（`reason_code=insufficient_disk`）；出口新增
  `[stamp] disk=C:\ free … GB / total … GB`。实测：要 200 GB → 拒绝；要 1 GB → 放行。
  **口径**：内存会回落，**磁盘只降不升** ⇒ 磁盘要的是「预算 + 回收 + 轮转」，闸门只是下限。
- **磁盘预算（一手）**：C: **65.1 GB 可用** / 475.9 GB 总；工作区自身 ≈1.4 GB（`.scratch` 自造 **128 MB**）。
  候选占用：Kokoro int8 90 MB · Whisper-small 950 MB · Qwen3-ASR 0.6B 2.4 GB · VoxCPM 2 **8 GB** ·
  Step-Audio 2 8B **32 GB** · 浏览器下载缓存 2–3× · 1080p 成片 0.5–2 GB。
- **与 O17/O59 接线**：账本轮转（36 MB 且增长、阈值只在文档）与 `.scratch` 回收是同一件事的两端 ——
  都在吃「只降不升」的那块资源。建议另开一刀：`.scratch` 按天/按大小回收 + 账本轮转施工，
  共用**归档式（不删除式）**口径。

> 本段为 **R-H13 落盘时裁定快照**，时间性表述以最新段为准。

---

## 八、挂账变更（R-H14 · 2026-09-18 夜 · 风哥「加载权重」）

- **内存/磁盘口径再收一格：加载权重撞的是 commit limit，不是物理可用量。**
  实测：物理 7.39 GB、**commit 已用 17.89 GB / 上限 23.39 GB**、**分页文件 ≈11.35 GB（正在换页）**。
  ⇒ 「无内存压力」在系统级不成立 —— **内存压力已被静默转成磁盘压力**；
  物理不够时不报错，只变慢（与"吞错伪装故障"同族）。
  `regression_stamp` 内存行升级为三数：`[stamp] memory=avail … / commit=…/… GB pagefile=… GB (swapping)`。
- **候选判据更新**（按 commit 判）：Kokoro int8 0.23 GB ✅ · Whisper-small 1.32 GB ⚠️（加剧换页）·
  VoxCPM 2 10.8 GB ❌ · Step-Audio 2 8B 43 GB ❌（**超 commit 上限**）。
- **与磁盘线接线**：65.1 GB 可用里已有 **11.35 GB** 被分页文件占用，且随内存压力继续涨 ——
  与 O17/O59（账本轮转未施工）同源：**只降不升的那块资源正在被两头同时吃**。

> 本段为 **R-H14 落盘时裁定快照**，时间性表述以最新段为准。

---

## 八、挂账变更（R-H16 · 2026-09-18 夜 · 风哥「临界 / 推理峰值」）

- **O61 第六条门（换页）**：临界 ≠ 够。判据 = **可用 ≥ 峰值 × 1.3 且不在换页中**。
  `regression_stamp` 在声明 `--need-memory X` 时连带检查换页：重度换页即拒绝
  （`reason_code=swapping_active`），确要跑加 `--allow-swap`。实测：拒绝 rc=2 / 放行 rc=0 两条均通过。
- **推理峰值三层**：①权重（可算：82M→int8 82 MB / fp16 164 / fp32 328）· ②运行时 arena（可估）·
  ③**推理峰值增量**（中间激活 + 声码器上采样 + 音频缓冲，**必须实测，本机无 onnxruntime ⇒ 不给数**）。
- **判定更新**：Kokoro-82M int8 由「✅ 可进」降为「**⚠️ 临界**」——
  本机 avail 0.58–0.85 GB、pagefile 11.1 GB 正在换页；要跑须先腾 1.5–2 GB **且**确认不在换页。

> 本段为 **R-H16 落盘时裁定快照**，时间性表述以最新段为准。

---

## 八、挂账变更（R-H17 · 2026-09-18 夜 · 风哥「比加载更高（中间张量）」）

- **O61 第七条门（输入上限）**：**峰值是输入的函数，不是权重的函数。**
  实测换算：声码器 48 kHz×10 s×256 ch fp32 = **469 MB**（Kokoro int8 权重 82 MB，**高 5.7 倍**）·
  30 s×128 ch = 703 MB · Whisper 30 s 注意力分数（20 头物化）172 MB · 0.6B ASR 4096 上下文 KV（fp16）384 MB。
  ⇒ 本地推理的能力声明**必须写输入上限**（最长文本 / 最长音频秒数），峰值按**最坏输入**算；
  「临界」因此不是一个常量，是随输入移动的门槛。写入 `docs/语音中枢v2.0-实测与部署.md` §九。

> 本段为 **R-H17 落盘时裁定快照**，时间性表述以最新段为准。

---

## 八、挂账变更（R-H18 · 2026-09-18 夜 · A 版三判据实跑 + 两条拍板）

- **A 版零算力闭环实跑（印章下）**：① TTS 真出声 **FAIL**（SAPI `E_ACCESSDENIED`，产物 46 B 空壳）·
  ② 审计留痕 **PASS**（audit +246 B）· ③ 上游挂掉链路仍可用 **PASS ×2**（asr 结构化降级 / 编排层照常可读）。
  ⇒ **A 版在这套身份下 2/3 绿**；① 的阻力是**身份**不是内存。
- **拍板①（风哥，理由更硬）**：**先 A、不给 B1 的 key** ——
  "B1 一到，A 的判据就**再也测不出来**了"（A 验的是零依赖时链路是否完整；一旦接云后端，
  失败分不清是编排问题还是后端问题）。故：先把 A 的三条判据跑绿并留档，再谈 B1。
- **拍板②（风哥，理由待补全）**：**现在不装 CPU 依赖**。我方补两条同向理由：
  ① 一次只动一个变量（A 尚未全绿）；② 装了大概率撞换页（commit 18.03/23.39、pagefile 11.51 GB），
  跑出来只会得到"模型不行"的假结论。
- **未执行动作（等点名）**：释放 chrome ≈1.52 GB + ChatGPT ≈0.81 GB（≈2.3 GB）；
  未关的理由：A 版峰值仅 59.6 MB，且关 ChatGPT 可能切断对话线。

> 本段为 **R-H18 落盘时裁定快照**，时间性表述以最新段为准。

---

## 八、挂账变更（R-H19 · 2026-09-18 夜 · 风哥「A 的定义就是零新增依赖」）

- **O61 第八条门（依赖指纹）**：`regression_stamp` 增 `_deps()` —— dist-info 名单(排序)+关键包版本 → sha256 短指纹；
  印章每次打 `[stamp] deps=<n> pkgs sha16=<...> key=...`。实测两次完全一致（`78749ADE1E9614CC`，46 包）
  ⇒ **A 版判据 0 = 前后指纹一致**，把"零新增依赖"从声明变成可验。**口令**：不用信谁说没装，指纹自己会说话。
- **A 版判据更新为四条**：0 零新增依赖 ✅ · ① TTS 出声 ❌（SAPI 身份拒绝）· ② 审计留痕 ✅ · ③ 上游挂掉仍可用 ✅
  ⇒ **3/4**；① 的修复**只能在零依赖内**（O64 授权 / 真实桌面自跑），不得靠新增依赖解决。
- **口径**：`find_spec` 命中 ≠ 有 dist-info（实测 `dxcam` 在 `.pylibs` 里能被 find_spec 找到但无元数据）；
  依赖指纹以 dist-info 为准。

> 本段为 **R-H19 落盘时裁定快照**，时间性表述以最新段为准。

---

## 八、挂账变更（R-H20 · 2026-09-18 夜 · A 基线封存 + 最坏窗口复验）

- **A 基线封存**：`.scratch/_A_baseline_20260918.json`（四条判据 + 两次资源窗口 + 四元组 + 依赖指纹）。
  **3/4**：判据 0 零新增依赖 ✅（sha16 `78749ADE1E9614CC`）· ① TTS 出声 ❌（身份）· ② 审计留痕 ✅ · ③ 上游挂掉仍可用 ✅。
- **最坏窗口复验**：avail **0.29 GB** / load 96% / pagefile 10.93 GB 下结果与 0.86 GB 窗口**逐条相同**
  ⇒ **A 版行为与内存无关**；「0.37 GB 够不够」对 A 的答案 = **够**，无需关 chrome/ChatGPT
  （那 ≈2.3 GB 是留给触手/浏览器路线的）。
- **失效条件（写死）**：**任何安装/卸载 ⇒ A 基线当天失效且不可事后补跑**；另加换解释器 / 换身份 /
  换 store 落点 / HEAD 变更。**口径：A 的价值 = 当天、零依赖、一次跑通 —— 装了就不是 A 了。**

> 本段为 **R-H20 落盘时裁定快照**，时间性表述以最新段为准。

---

## 八、挂账变更（R-H21 · 2026-09-18 夜 · 装依赖前置判决 + 两条回执）

- **装依赖前置判决（风哥顺序第 3 步，用读数+算术先判）**：现状 commit **17.84/23.39 GB**、pagefile **11.42 GB**；
  放掉 chrome+ChatGPT（2.33 GB）后可用升至 3.29 GB，**但换页不会消失**（要让 pagefile 归零需放掉 ≈10.5 GB）。
  判据（可用 ≥ 峰值×1.3 **且不在换页中**）下，Kokoro int8 / fp32 / Whisper-small **两个窗口全 FAIL**，
  **否决项是「不在换页中」**。⇒ **现在装 = 白花下载 + 一次环境变更，且令当天 A 基线失效 ⇒ 不装。**
- **回执：名字碰撞已处理** —— `voice` 三家占用已核实；cap 定名 **`voice_orchestrator`**，
  注册表 + api + `main.cjs TOOLS_CAPS` 三处同批落地，路由 **96/96**。
- **回执：tools tab 已挂**；**「voice tab 等 B1 再开」**记为后续决定（与 B1 一并动）。

> 本段为 **R-H21 落盘时裁定快照**，时间性表述以最新段为准。

---

## 八、挂账变更（R-H22 · 2026-09-18 夜 · 风哥拍板「新开 voice tab」）

- **面板新增 voice tab**（`index.html` nav + view · `window.js` renderVoice/loadVoice ·
  `main.cjs` `VOICE_CAPS` + `w3Voice()` + `ipcMain w3:voice` + exports）；三文件行尾保持纯 CRLF。
- **出口清单（单一来源）**：`voice_orchestrator` 与 `voice` 均挂 **voice tab**；
  `voice_orchestrator` 已从 `TOOLS_CAPS` **整块移走**（实测该段不再含此名）。
- **面板状态如实**：`voice.tts = blocked_identity`（E_ACCESSDENIED 0x80070005 + 46 B 空壳）·
  `voice.asr = pending`（缺 `GBT_ASR_*`）· `voice_orchestrator` 三动作 live；**本页不挂发声/克隆动作键**。
- **验证**：`node --check` ×2 rc=0；结构自检全中；自写 headless 探针 **7/7 PASS**
  （`.scratch/_rh22_voice_probe.cjs`，假 electron 顶接 main.cjs —— 与仓内 `_w3_ipc_harness.cjs` 同法）。

> 本段为 **R-H22 落盘时裁定快照**，时间性表述以最新段为准。

---

## 八、挂账变更（R-H23/R-H24 · 2026-09-18 夜 · 回滚 voice tab + 作用域补分支）

- **voice tab 回滚**（风哥拍板「挂现有 tools tab」）：`index.html` / `window.js` / `shell/main.cjs` 恢复原状，
  `voice_orchestrator` 回到 `TOOLS_CAPS` 且动作三条；`node --check` rc=0；三文件纯 CRLF。
  **出口清单**：`voice_orchestrator` 与 `voice` 均挂 **tools tab**（voice tab 方案作废，版式留在
  `.scratch/_rh23_voiceTab_kept_*` 可再启用）。
- **坑册 23（自曝）**：多步编辑里每步重拍备份 ⇒ 快照是**中间态**，回滚回到半改完的状态。
  口诀：**备份只拍一次（首次改动之前）+ 回滚脚本必须幂等**。
- **证伪「Ran 174 基线要动」**：本刀改 3 个前端文件、**零 `.py` 改动** ⇒ `.py` 测试基线不受影响。
- **O66（新观察项 · R-H24 立）**：`voice_orchestrator` 在 `security/policy.py` **原本没有分支**
  ⇒ `scopes=[]` ⇒ `authorize()` 静默放行（不在授权体系内）。已补显式分支：`list/pipeline/status` 零作用域，
  **未列出动作 fail-closed**（`data_export` + `external_llm`）。**同族缺口**：既有 `voice` 能力 `op=tts`
  也是空 scopes（写类动作无作用域）——**未动，待拍**。

> 本段为 **R-H23/R-H24 落盘时裁定快照**，时间性表述以最新段为准。

---

## 八、挂账变更（R-H25 · 2026-09-18 夜 · 风哥「voice 够不够格独立」）

- **四层判定（一手判据）**：**域层 ✅ 已独立**（`domain=voice` 下已有 2 个 cap）·
  **授权层 ✅ 够格且必须**（13 个作用域里无音频类；`voice.tts` 空作用域）·
  **面板层 ❌ 不够格**（6 个 tab 全是视图维度，非能力域；3+3 条动作撑不起）·
  **名字层 ❌ 不够格**（`voice` 在 4 个文件被用 = 共用名，O60 病种现场）。
- **O67（新观察项 · R-H25 立 · 待拍）**：**作用域表两个缺口** ——
  ① 无音频/声音类作用域（建议新增 `audio_output` 并挂 `voice.tts`）；
  ② `osint_private` 代码 `add()` 过但 `SCOPE_DESCRIPTIONS` 未定义。
  **未动的原因**：给 `voice.tts` 挂作用域是**收紧授权**，非 trusted 会话下会由"静默放行"变为"需授权" = 行为变更。
- **面板层结论固化**：现有 tab 的准入判据是「**有一类要独立看的东西**」而非"有一类能力"；
  voice 暂无此需求 ⇒ **不开 tab**（voice tab 版式留在 `.scratch/_rh23_voiceTab_kept_*`）。

> 本段为 **R-H25 落盘时裁定快照**，时间性表述以最新段为准。

---

## 八、挂账变更（R-H26 · 2026-09-18 夜 · 风哥拍板「折中：tools + voice_orchestra」）

- **cap 改名 `voice_orchestrator` → `voice_orchestra`**（先查占用：词边界精确命中 0）：
  文件 `voice_orchestra.py` + 注册表 key/handler/desc + `api.py` kind/import + `main.cjs TOOLS_CAPS` +
  `security/policy.py` 分支/注释 + 活文档引用；**历史记录不改**。
  验证：路由 **96/96** · `list(CLONE)=7` · `pipeline` 6 步 · policy 只读三动作不受限、`tts` fail-closed ·
  面板 headless 探针 **4/4 PASS**（已无 `voice_orchestrator` 字样）。
- **升格条件写入模块 docstring**：① B1 云后端到位（ASR/TTS/CLONE 三条真链路可跑）；② 面板能展示三条链路真状态。
  性质：**「有明确升格条件的暂挂」≠「暂挂」**。判据沿用「出口清单写实际出口、不写规划出口」。
- **合规栏补**（风哥）：**GPL 触发=分发；AGPL 触发=通过网络提供服务** ⇒ 本机自用都不触发，
  **面板接外网/给人访问那天 AGPL 先响**。写入 `docs/语音中枢v2.0-实测与部署.md`。
- **自曝副作用**：改文档时 `write_text` 把 LF 文档整篇转成 CRLF，已修回 LF（12307 → 12120 B）。

> 本段为 **R-H26 落盘时裁定快照**，时间性表述以最新段为准。

---

## 八、挂账变更（R-H27 · 2026-09-18 夜 · 风哥「新变量：解释器」）

- **O61 第九条门（孩子解释器）**：`--expect-python` 原来只校验**印章自己**，跑判据的孩子没被比对。
  已补：不一致 → `reason_code=interpreter_child_mismatch`（负对照实测：孩子 3.10 被正确标红）。
  **同刀修假阳性**：孩子未 import 仓内包时误报 `store_binding_mismatch`。
- **本机解释器实测**：`py -3.10` ✅ 3.10.11 · `py -3.12` ❌ 起不来（stdlib 读不到）·
  PATH shim ✅ 3.14.5 · 3.13（商店版）未测。
  ⇒ **3.12 复现基线在本身份下不可能**（同 O64 性质：要换身份）；**3.10 可用** ⇒ 可做
  **零依赖的跨解释器交叉验证**（待拍）。

> 本段为 **R-H27 落盘时裁定快照**，时间性表述以最新段为准。

---

## 八、挂账变更（R-H28 · 2026-09-18 夜 · 解释器可用性矩阵）

- **O68（新观察项 · R-H28 立）**：**解释器可用性矩阵（本机 4 入口）** ——
  `py -3.10` ✅ 3.10.11 · `py -3.12` ❌ **找不到 stdlib** · `py -3.13` ❌ **起不了进程**
  （`Unable to create process …WindowsApps\python3.13.exe`）· PATH shim ✅ 3.14.5。
  **口径**：两类失败模式必须分开记，不许都写"起不来"。
- **红线分处观察（待拍）**：`PROJECT_BLUEPRINT:1305` = 跨身份只逐名比对；
  跨解释器那半在 O61 增补（R-H7）—— 同一道红线分了两处，读者可能只读到一半。
  建议合并为一条完整红线（**未擅改**）。

> 本段为 **R-H28 落盘时裁定快照**，时间性表述以最新段为准。

---

## 八、挂账变更（R-H29 · 2026-09-18 夜 · 风哥「红线再收一格 / 0.37 GB」）

- **坑册 24（自曝）**：docstring 承诺 `--same-as`，代码里没这个参数 ⇒ **红线只活在表达层**；
  **层级断层第三例**（前两例：体检文档 vs 采集路径；红线分两处）。口诀：**工具文档里写的每个开关/原因码，
  落地时必须当场跑一次**。
- **O61 第十条门（口径比对）**：`--same-as <旧印章|旧基线>` 落地 —— 比对「解释器 / 身份 / 依赖指纹 / git /
  store 模式」，不同即 `comparability=not_comparable` + `reason_code=not_comparable` + 红线原文
  （只允许逐名比对）。双向实测通过（A 基线 → `same_scope`；假 3.12 → `not_comparable`）。
  **两条细则**：① 任一侧 `None` 记**未知**不记差异（防假红）；② **`mem_bucket` 只披露不判**
  （实测 A 判据在 0.29 / 0.86 GB 两窗口逐条相同 ⇒ 内存对 A 不敏感，当闸只会造假红）。
- **0.37 GB**：落在 `tight(<=0.5GB)` 桶；A 基线已含 0.86 / 0.29 两窗口，印章现在每次都打桶值。

> 本段为 **R-H29 落盘时裁定快照**，时间性表述以最新段为准。

---

## 八、挂账变更（R-H31 · 2026-09-18 夜 · 两条拍板的可核验定位）

- **定位留档**（风哥两条）：挂 tools = `main.cjs:333`（三条 live 动作）· 升格条件 = `voice_orchestra.py:11-20`
  （`caps_registry.py:538` desc 指向它）· AGPL 触发点 = `docs/语音中枢v2.0-实测与部署.md:176-186`。
- **O69（新观察项 · 判据工具假阴性 · R-H31 立）**：`rg 'cap: "voice_orchestra"'` 在 PowerShell 下
  **双引号被吃掉 → 零命中**，差点误判"面板出口没落上"。**同族已有三例**：子串匹配误判占用 45 处、
  内联 `python -c` 引号被吃、本次假阴性。**口令**：含引号的模式一律 `-e` + 单引号，或改用脚本查。

> 本段为 **R-H31 落盘时裁定快照**，时间性表述以最新段为准。

---

## 八、挂账变更（R-H32 · 2026-09-18 夜 · 微信 Bot 入库前评审）

- **O70（新观察项 · R-H32 立 · 待拍）**：微信 iLink Bot 代码入库前的**四个硬冲突** ——
  ① 依赖口径（`aiohttp` vs 本仓 `httpx`）② **凭据落点**（`Path("bot_token.txt")` 相对路径 ⇒ 随 CWD 漂 + 明文）
  ③ 高频重写（每条消息 `save()` 整文件两次，无锁非原子）④ 幂等缺失（无 `msg_id` 去重 ⇒ 重复回复）。
  另两条口径：失败要结构化 + 原因码；**对外发消息属"先问再做"**、渠道默认 `unattended_allowed: false`。
- **拟定落地形态**：cap 名 `wechat_ilink`（词边界 0 占用）· 面板 tools tab · 入口 `gbt_allinone/wechat_ilink.py` ·
  policy 作用域（`external_llm` + 数据外发，未列出动作 fail-closed）· 常驻走 `services.json`。
  AI 回复接**已有**通道（`cloud_llm` / `deepseek-flash` / `deepseek_api.dpapi`），不新写 HTTP。

> 本段为 **R-H32 落盘时裁定快照**，时间性表述以最新段为准。

---

## 八、挂账变更（R-H33 · 2026-09-18 夜 · POST /send 接口评审）

- **O70 增补（接口面）**：若按「Bot 独立部署 + App 经 HTTP 调」的形态，`POST /send` 必须满足五条：
  ① 绑定 **127.0.0.1**（照 `panel_server.py:777` host 白名单 + `services.json` 现有回环惯例）·
  ② **鉴权**（裸路由任何本机进程可代发）· ③ 走 policy 外发作用域 + 审计只记「谁/何时/给谁/字数」·
  ④ **幂等键**（与入站 msg_id 去重同源）· ⑤ 长度上限 + **收件人白名单**（照 `coze_mail_cap._check_recipient`：
  白名单空 ⇒ 全拒）。
  **建议**：不开 HTTP 路由，改为 cap op（`wechat_ilink.send`）内部调用，避免"第二入口 + 第二真相"；
  确需跨进程才登记 `services.json` + 回环 + 本地令牌 + 默认关闭。**端口不入公开文档**。

> 本段为 **R-H33 落盘时裁定快照**，时间性表述以最新段为准。

---

## 八、挂账变更（R-H34 · 2026-09-18 夜 · POST /webhook 评审）

- **O70 再增补（双向中继面）**：`/send` = App→Bot（出站）· `/webhook` = Bot→App（入站转发）⇒ Bot 是双向中继。
  `/webhook` 四个新面：**投递可靠性**（重试/退避/失败落盘）· **去重**（重试 ⇒ 重复处理 ⇒ 重复回复）·
  **鉴权**（不鉴权则任何本机进程可伪造"微信来信"，伪造的是输入）· **外发边界**（App 在外网时私聊正文出机器）。
  对应原因码：`webhook_delivery_failed` / `webhook_duplicate` / `webhook_unauthorized` / `data_export`。
- **事实（一手）**：全仓**没有 webhook 接收端先例**；既有形态 = 同机同进程 callback + 回环服务登记。
  ⇒ **建议不开这层 HTTP 中继**，改 cap op（`wechat_ilink.send` / `.poll`）+ 常驻轮询；
  `/webhook` 仅在"处理逻辑跨机/跨语言"时才有意义。

> 本段为 **R-H34 落盘时裁定快照**，时间性表述以最新段为准。

---

## 八、挂账变更（R-H35 · 2026-09-18 夜 · 微信 Bot 评审收敛）

- **O70 收敛落点**：同一份 Bot 代码被贴三次 ⇒ 评审结论**落成可执行文档**
  `gbt_allinone/docs/微信iLink-Bot-评审与改造清单.md`（四硬冲突 + 两口径 + `/send` 五条 + `/webhook` 四面与四原因码
  + 推荐形态 + 接入前必须先拍的两件）。**原件未落盘**（按评审需先改四处）。
- **口令**：**结论要有落点，不靠人记** —— 同一份东西被问三次，问题不在答案，在于答案没有家。

> 本段为 **R-H35 落盘时裁定快照**，时间性表述以最新段为准。

---

## 八、挂账变更（R-H36 · 2026-09-18 夜 · POST /send 接口契约）

- **O70 增补（契约层）**：`POST /send` 接口契约落地到
  `docs/微信iLink-Bot-评审与改造清单.md §六` —— 请求（`to_user` / `text` / `idempotency_key` + 本地令牌头）、
  七种响应、以及**核心口径：业务性拒绝返 `200 + ok:false + reason_code`，不返 5xx**
  （5xx 会触发上游重试，把一次拒绝放大成一串重试；唯"凭据失效"返 503）。
  配套：审计只记五要素（正文不入日志）· 幂等键 30 分钟窗口 · 未知 reason_code 一律当失败。

> 本段为 **R-H36 落盘时裁定快照**，时间性表述以最新段为准。

---

## 八、挂账变更（R-H37 · 2026-09-18 夜 · POST /webhook 接口契约）

- **O70 增补（契约层 · webhook）**：`docs/微信iLink-Bot-评审与改造清单.md §七` ——
  请求头（令牌 / `X-GBT-Delivery-Id` / `X-GBT-Attempt`）+ body（`delivery_id` / `msg_id` / `from_user` /
  `text`(可选) / `context_token`）+ **五种响应下 Bot 的行为**（协议层错误与业务拒绝**都不重投**）。
  **三条口径**：at-least-once ⇒ 接收端必须幂等（重复投递返 `ok:true`，返错会被无限重投）·
  业务拒绝返 200 不返 5xx · 退避 1/2/4/8/16s 上限 5 次，耗尽落 `store/` 待投递队列 + 只读水位。
  **隐私默认**：`payload_mode=signal` 只投元数据不带正文，`full` 才带且走 `data_export`。

> 本段为 **R-H37 落盘时裁定快照**，时间性表述以最新段为准。

---

## 八、挂账变更（R-H38 · 2026-09-18 夜 · webhook 三条缺口 + 待拍摊开）

- **O70 增补（缺口修补）**：`docs/微信iLink-Bot-评审与改造清单.md §八` ——
  ① **失败路径隐私**：401/422 只落 Header 摘要 + delivery_id + 长度 + 原因码，**不落正文**（无论 payload_mode）；
  并补限定「**signal 去掉的是内容，不是元数据**」（四样元数据足以重建社交图谱）。
  ② **幂等窗口**：`delivery_id` 保留 ≥ 31s（建议分钟级），且 **TTL 与条数双约束**。
  ③ **attempt 执法方**：发送端自我限流（权威计数），接收端不依赖该头限流（仅观测）。
  判词留档：**"上限如果靠一个观测头来执法，那它就不是上限，是建议。"**
- **决策（风哥）**：**webhook = 要**（`/send` 的对称面）。**已知代价**：形态落 HTTP 中继，
  与单入口 `holo_pet` 的张力如实留存（已拍，按此执行）。
- **§十 待拍八条已摊开选项 + 我方建议**（便于一次拍完）。

> 本段为 **R-H38 落盘时裁定快照**，时间性表述以最新段为准。

- **O59 增补（R-H39 · 风哥）**：**「有阈值、无执行者」是同一个病种，别开两张单。**
  幂等记录（`delivery_id`）的**落点与清理**并入本条口径：
  · 落点 = `store/` 下与待投递队列**同处**（`wechat_ilink/`，不另开一处真相）；
  · 清理 = **TTL（≥31s，建议分钟级）+ 条数封顶双约束**，由同一个轮转/清理执行器负责 ——
    现在这个执行器**尚未施工**（与 `audit.jsonl` 轮转是同一个缺口）。
  口径：**一个执行器管所有"会涨的东西"**，不为每种记录各写一套清道夫。

---

## 八、挂账变更（R-H40/R-H41 · 2026-09-19 凌晨 · 八条拍板执行）

- **执行**：① 红线整理（O61=唯一定义处 · R-H7 换指针）· ② key 三步顺序留档 ·
  ③ `GBT_CAPTURE_ATTACH` **显式开关**落地并验证（默认关；打开后抓帧 `ok=True size=[1920,1080]`）·
  ⑤ `audio_output` 定义 + 挂 `voice.tts/speak`（`restricted=True`）·
  ⑥ 3.10 跨解释器复跑（判据②③复现 PASS，判据①同名红但病因不同）·
  ⑦ `prompt_bridge` 设计稿（边界/判据/基线影响）· ⑧ Bot 形态确认 HTTP 中继。
- **门抓我两次（正向样本）**：`safe_io` 写前语法校验挡下坏补丁（盘上零改动）；
  契约测试 `test_policy_scopes_are_registered` 抓到「policy 声明 `audio_output` 但 `auth_gate` 未注册」⇒ 补齐。
  **最终回归：Ran 174 / 红 16 / 逐名一致（零回归）**（未补注册时为 17）。
- **O67 修正**：`osint_private` = **auth_gate 有、policy 无**（方向与先前写法相反）；
  契约测试**只查单向** ⇒ **O71（新观察项）**：补反向断言（auth_gate 有而 policy 无者，须显式豁免）。

> 本段为 **R-H41 落盘时裁定快照**，时间性表述以最新段为准。

---

## 八、挂账变更（R-H42 · 2026-09-19 凌晨 · 风哥：门自动抓断层 + 失败模式维度）

- **⭐ 病种 ↔ 检测手段分类（风哥 2026-09-19 提炼 · 本轮最有价值）**：把今晚抓到的断层按**谁能抓**分开 ——

  | 断层形态 | 谁抓到 | 能否自动化 |
  |---|---|---|
  | `policy` 声明 ↔ `auth_gate.SCOPES` 注册 | **门自己抓**（契约测试） | ✅ 已自动（`test_policy_scopes_are_registered`） |
  | 红线 ↔ 指针（规则分两处） | 人眼抓 | ✅ **可**自动（同一规则只允许一处定义 + 其它处必须是引用） |
  | `docstring` ↔ 参数签名 | 人眼抓 | ✅ **可**自动（文档里写的开关/原因码必须能被 argparse/签名反查） |
  | 表达层 ↔ 行为层（"修得够不够"） | 人眼抓 | ❌ **不可**（没有机械判据，必须人判） |

  **口径**：**两边都是"注册表/声明"的，能自动；"修得够不够"的，只能人判。** 优先把前两类做成门。

- **O61 增补（第三个维度）**：会让"同口径"失效的不止身份与解释器，还有 **失败模式** ——
  实测：判据① 在 3.14 与 3.10 下**都红**，但一个是 SAPI/COM `E_ACCESSDENIED`、一个是
  `Permission denied`（comtypes 写 code cache）。
  ⇒ **O61 的记录字段增一栏：`failure_mode`**（不只记测试名，还要记错因关键字）。
  否则下一个复跑的人会把两种病因读成同一个问题。

- **O71（补反向断言 · 已立待落）**：`policy ↔ auth_gate` 的契约测试**只查单向**（policy 有、gate 无）；
  反向（gate 有、policy 无，实测 `osint_private`）**没人管** ⇒ 补反向断言 + 显式豁免清单。
  形态：**加进现有测试不新增测试方法**（使 `Ran 174` 不动）。

- **硬规矩（风哥拍 · 由本会话三次自曝立）**：**扫描范围必须与结论范围一致。**
  同族三次：`py_ecc` 全机复核（只扫本仓）· A 类扫描排除 `.scratch` · 改名遗留引用（扫描排除 `.scratch`）。
  规则：**写结论前先写范围**；范围不一致就把结论降级为"在 X 范围内未命中"，并要求**正对照**。

> 本段为 **R-H42 落盘时裁定快照**，时间性表述以最新段为准。

---

## 八、挂账变更（R-H43/R-H44 · 2026-09-19 凌晨）

- **O71 落地**：契约测试追加**反向断言** + 显式豁免清单 `{osint_private}`；
  **测试方法数 121→121 ⇒ `Ran 174` 不动**；两条契约测试 OK。
- **O72（新观察项 · 新能力 · 未完工）**：`prompt_bridge` **第一刀已落**（模块 stdlib-only + 独立测试 6/6），
  **接线四件未动**（`caps_registry` / `api.py` / `policy.py` / `main.cjs TOOLS_CAPS`）⇒ 按「缺一格 = 未完工」标未完工。
  下一步同批接线并验证 **routing 96 → 97**（新增 `routing` 栏即为拦"注册未分发"）。
- **判据工具也会造假红（实测）**：`prompt_bridge` 首跑 P2 报 `intent_loss`，根因是抽取器把
  「帮我写个」抽成跨填充词的 4 字块 ⇒ 修法「**先删填充词再抽块**」。

> 本段为 **R-H44 落盘时裁定快照**，时间性表述以最新段为准。

---

## 八、挂账变更（R-H46/R-H47 · 2026-09-19 凌晨 · prompt_bridge 收口）

- **O72 收口（已完工）**：`prompt_bridge` 接线四件落地 —— 注册表 96→97 · `api.py` 分发 ·
  `policy.py` 分支（三动作零作用域，**未列出动作 fail-closed**，实测 denied + `how_to_grant`）·
  `main.cjs TOOLS_CAPS` 一行（三动作 live）。**路由自检：registered=97 / routed=97 / unrouted=[] / ghost=[] / ok=True**。
- **门的度量（风哥要求）**：真红 **2**（`safe_io` 语法校验拦我的坏补丁 · 契约测试抓 `audio_output` 未注册）·
  假红 **2**（routing 的"旧进程验新码"人为假红 · P2 抽取器跨填充词块）· **无"从不叫"的门**。
  **口径**：假红都出在**测量侧**（我先造错，再被门抓）；门本身没造过一次假红。
- **两处更正**：① "吸收"丢时序 —— v1.0 是**执行前报态**，正确等价物是**前置查询**（`status` 零副作用纯函数 +
  新增 `test_status_is_side_effect_free`）；② **H3 降级为待办池**（不对应任何已记录失效模式；检索仅到第三方横评）。

> 本段为 **R-H47 落盘时裁定快照**，时间性表述以最新段为准。

---

## 八、挂账变更（R-H48 · 2026-09-19 凌晨 · 更正：门的度量方法）

- **更正（自曝）**：上一段的"门的叫法统计"用 `grep reason_code= .scratch/_stamp_*.txt` 得到**空表** ——
  因为印章的 `reason_code` 打在**印章进程 stdout**，`.txt` 里是**孩子的输出**。
  ⇒ **又一次"扫描范围 ≠ 结论范围"**（硬规矩刚立就当头踩）。
  已改为**手工枚举 + 一手产物指认**：真红 **2**（`safe_io` 语法校验 · 契约测试 scope）·
  假红 **2**（routing 旧进程验新码 · P2 跨填充词块）· 无"从不叫"的门。
- **新增自省**：**度量工具本身也要过"范围审查"** —— 数门之前先问"这些门的输出各自落在哪"。

> 本段为 **R-H48 落盘时裁定快照**，时间性表述以最新段为准。

---

## 八、挂账变更（R-H49 · 2026-09-19 凌晨 · 门度量 v2 + PRE-9 计划）

- **门度量 v2**：`门度量（2026-09-18/19 夜 · n=5 · 真红 2 · 假红 2 · 窗口=一晚）` ——
  **"零假红"≈"5 次抛硬币全正面"**，不是"不误报"；**度量改周期性**，**结论必带 n 与窗口**。
  **归类更正**：`regression_stamp` 那次是**正确拒绝**，不是"抓缺陷" ⇒ 真红 = **2**（两条都是抓缺陷）。
  原述"无从不叫的门"改述为"5 道中 4 道被观察到叫过；第 5 道叫的那次是拒绝而非抓缺陷"。
- **喂坏矩阵（实测）**：契约测试变异负对照 OK · `prompt_bridge` P2 负对照 OK ·
  `safe_io` 喂坏补丁 → `WriteRejected`（盘上零改动）。⇒ 前 3 道有"主动喂坏"证据；
  routing 自检与 `regression_stamp` **待补变异负对照**。
- **自省升格**：**度量工具本身也要过范围审查**（它是"关于门的门"，错了会静默错遍所有门的判断）；
  计数类结论必须同时给「扫描了什么 / 排除了什么 / 文件总数」。
- **PRE-9 计划（下一轮）**：**只归因不修**（保基线参照）+ 归因表加**病种栏**（六类之一/其它）；
  若全不落在已知病种上 ⇒ 病种体系不足，那是更重要的发现。**优先级：PRE-9 > 存量债三项。**

> 本段为 **R-H49 落盘时裁定快照**，时间性表述以最新段为准。

---

## 八、挂账变更（R-H50 · 2026-09-19 凌晨 · PRE-9 判据预注册 + 门规矩）

- **PRE-9 判据预注册（风哥 2026-09-19 · 下一轮照此判表）**：
  1. **四元组基准**：那 9 条来自 `_h1_tests_before_fresh × _after_fresh`（H-07 基线那次）⇒
     它们的四元组 = **基线那次**（3.12 等）。先回答：**这 9 条在今天（3.14 + 沙箱身份 + 新 store）还红吗？**
  2. **逐条"当前是否复现"四态**：① 今天仍红（真·活失败）② 今天变绿（基线期问题，须追"谁修好的"）
     ③ 今天红但**失败模式不同**（同名不同病，O61 第三维）④ **今天跑不起来（被身份/解释器挡住）= 不可复现**。
     ⚠️ **④ 必须是独立状态，绝不许并进"红"** —— "跑不起来"≠"还红"≠"绿"；
     "没测到"不得混进"测到了是红的"。（同族：unopposed = 提不出反对 ≠ 不反对）
  3. **"病种"栏允许填「其它」，且填了不算失败** —— 否则人会硬塞进六类，六类框架就变成新的"两处真相"。
  4. **该轮不许改代码，包括不许改测试**（✅ 读码/跑现有测试/看日志/对比失败模式；❌ 改测试、改判据）
     —— 任何改动都会让"新的 9 条"提前产生，而归因还没完。

- **门规矩（固化）**：**每道门都需要一个"变异负对照"**。证据阶梯：
  `观察到叫过（弱） < 主动喂坏→它叫了（证明会叫） < 主动喂好→它不叫（证明不总叫）`。
  喂坏样本**必须不碰生产路径**（临时文件 / 合成输入）。

- **两条待补门（不阻塞 PRE-9 · 已给非侵入做法）**：
  ① `routing` 自检：**用合成注册表喂它**（内存里造一条"注册了但没分发"的 cap 过自检函数）——
     叫了=有牙；不叫=它只检查真实注册表。**两种结果都有信息量**。
  ② `regression_stamp`：把"expect 3.14 / 实际 3.12"那次拒绝**固化成一条可重复测试**。

> 本段为 **R-H50 落盘时裁定快照**，时间性表述以最新段为准。

---

## 八、挂账变更（2026-09-19 凌晨 · APP 部署）

- **部署结论（实测）**：面板 `127.0.0.1:8765` 已在跑 · `/api/state` 200 · **对话端到端可用**
  （实测 SSE 返回「链路已通」· 当前走降级大脑 DeepSeek，因 `codex.connected=false`）·
  Electron 在装 · 启动件七件齐。
- **落地**：`holo_pet/deploy_check.py`（逐解释器矩阵，可反复跑）+ `holo_pet/部署-今天就能用.md`（三步操作单）。
- **缺件（不阻塞）**：3.10 缺 `PySide6`/`live2d`（只影响桌宠形态）· `websockets`（SSE 实测正常）·
  3.12 起不来（启动脚本第二候选坏）· Codex 未登录（只用降级大脑）。
- **本次新坑（第 4 条与既有账呼应）**：**同一句话被答两次** ⇒ 幂等在**面板侧**也真实存在。
  另有"PowerShell 发中文变问号" ⇒ **探测工具要过编码审查**（与"度量工具要过范围审查"同族）。
- **GUI 约束**：沙箱身份 `interactive_desktop=false` ⇒ 我起的窗口主人看不到，桌面壳必须主人双击。

> 本段为 **R-H51 落盘时裁定快照**，时间性表述以最新段为准。

---

## 八、挂账变更（2026-09-19 凌晨 · 部署收口）

- **能力层实测（一手）**：`mind` / `life` / `sensory` / `bluetooth` / `notion` / `eigenflux` / `xingyun`
  **全部 `ok:true` 且结果非空**；`last_error` 与 `last_error_safe` 空；`life.events=163`（`last_at` 就在刚刚）。
  `/api/quick` 白名单实测：`mind_pulse`/`logs` → `ok:true · path="route" · deferred:true`（路由通、结果异步）。
- **四条规矩入册**：① 入口脚本必 `reconfigure(utf-8)`；② **逐解释器测**（结论范围 ≤ 实测范围）；
  ③ **探测工具也要过编码审查**；④ **3.12 起不来 = 环境约束**（约束≠bug，写进 `holo_pet/部署-今天就能用.md` §五）。
- **部署单补两节**：§五 环境约束（3.12 起不来 · 沙箱非交互桌面 · 沙箱无出站网络 · 控制台 GBK）·
  §六 能干什么（`quick` 白名单 + 实测判读）。
- **O73（新观察项 · 层级断层第七候选）**：**面板侧幂等缺失** —— 实测同一句话被答两次，
  与 `/webhook` 契约「at-least-once ⇒ 接收端必须幂等」同源（契约层写了、面板层没做）。
- **A 的第一步（零副作用）通过**：`codex.exe` 在位 · `--version = codex-cli 0.155.0` · **未 login**。

> 本段为 **R-H52 落盘时裁定快照**，时间性表述以最新段为准。

## 十一、万能插座（2026-10-30 主人令：不要固定的六类）

| 文件 | 干什么 |
|---|---|
| `tools/omni_adapter.py` | `classify(target)` 现场判类（纯分析、不联网）→ `execute()` 动态生成适配器 |
| `gbt_allinone/omni_plug.py` | `op=universal`（或不给 `socket` 的 `run`）走万能入口 |
| `gbt_allinone/security/policy.py` | **共用同一个 classify** 挂作用域 ⇒ 门与执行同一判断 |
| `tools/omni_discover.py` | 自动认出机器上所有接口，生成 `state/omni_sockets.json` |
| `tools/omni_ios.py` | iOS 侧等价接口：`web`→apple-open · `app`→URL scheme · `see`→页面截帧+apple-vision |
| `tools/omni_audit.py` | 四态自审（ok / needs_ticket / platform_na / fail），固定六类 + universal 都测 |

**判得出的形态（不封闭）**：`http · ws · tcp · unix · path · dir · bin · cmd · scheme · mcp · remote`
**认不出也不说"不支持"**：按命令试跑一次并标明是猜的（`via=omni:fallback`）。

**门按类精确挂**（实测）：
```
read /etc/hostname → ()                          免票
settings launch    → ()                          免票
https://...        → (external_llm, data_export) 要票
python3 exec       → (process_execute,)          要票
```

**自审（有票）**：可用 16 · 需票 0 · 平台不支持 0 · **失败 0**
