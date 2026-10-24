# 系统 · `system`（51 位）

> 自动生成，数据源 `gbt_allinone/caps_registry.py`。只读 = 不改状态、不出网；其余调用前需人工授权（作用域门）。参数以 `requires_params` 标出；**必填载荷**与**常见错误**两列只写注册表登记过的（没登记就写「无必填」/通用三态），不猜。

| 能力位 | 类型 | 需参数 | 必填载荷 | 常见错误 | 它做什么 |
|---|---|---|---|---|---|
| `action_gate` | 只读 | — | —（空载荷走该位默认 op） | `user_error` | 先看→动脑→执行 前置闸（主人令「做事拥有先看在动脑执行，拒绝所有的无脑操作以及盲猜」）：**没证据不许动手**（evidence 必须真在盘上）· **证据要新**（默认 ≤600s，旧读数不许当现状）· **必须写预期**（hypothesis ≥8 字，否则算盲猜）· **… |
| `agent_console` | 只读 | — | —（空载荷走该位默认 op） | `user_error` | 代理驾驶舱：**任务监督循环 + 连接请求审批桥**（蒸馏自 GitHub 周榜 #05 paperclip，只取架构）：`add` 登记被监督任务（判活看**读数有没有如期更新**，不是 exit code）· `tick` 定时检查出 ok/stale/failed 并列出该… |
| `agent_control` | 只读 | — | —（空载荷走该位默认 op） | `user_error` | Agent 统一控制面（nasiko #04 蒸馏）：六面读数收进一屏——部署/路由/鉴权/限流/成本/链路，**每面带 src、不新起网关/Sidecar、只读不改配置**；读不到就写读不到（未验≠没有），成本面如实标 unknown。op=roster/facets/wher… |
| `agent_rig` | 只读 | — | —（空载荷走该位默认 op） | `user_error` | 编码智能体编队：**把本机已装的 CLI agent 编成并行流水线**（蒸馏自 GitHub 周榜 #02 orca，只取架构）：`agents` 只读盘点可编排的 agent（fail-closed）· `plan` 把一批任务分成 N 份（每份 worktree + 端口段… |
| `alerts` | 只读 | — | —（空载荷走该位默认 op） | `user_error` | 框架声带：近期异常摘要+根源线索（按能力聚合） |
| `answer_shaper` | 只读 | — | —（空载荷走该位默认 op） | `user_error` | 行动优先输出核（蒸馏自 2026-09-28 主人给的周榜截图 ayghri/i-have-adhd——截图只给仓库名，**未联网核验、未引用该仓任何代码/文本**；纪律取自本仓自己的沟通纪律与已有技能 gbt-adhd-mode，本件补**运行时可机检的核**）：`check`… |
| `asset_index` | 只读 | — | —（空载荷走该位默认 op） | `user_error` | 资产索引：**整棵树都连上 + 连上即可秒查**（主人令 2026-09-27）。build 把全树扫进 state/asset_index.db（键=跟随软链的物理真身，与绑定系统同口径，软链别名去重）；wire 给每个资产补触手标签（启发式优先，认不出用回退标签 projec… |
| `auth_gate_status` | 只读 | — | —（空载荷走该位默认 op） | `user_error` | 人工授权门状态：各作用域可用授权数（只读；授权只能人发放） |
| `cap_tags` | 只读 | — | —（空载荷走该位默认 op） | `user_error` | GBT 技能标签 + 主人调用许可（主人令「将所有的原生能力注册出专属的 GBT 技能标签，只有我允许了才能调用我的能力」）：每个能力位一个稳定标签 `GBT-<域>-<能力位>`，**从注册表现算**；权限类**由框架自己的判据推**（`policy.evaluate` 逐 o… |
| `caps_called_audit` | 只读 | — | —（空载荷走该位默认 op） | `user_error` | 能力位调用点审计（只读）：动态算 called_by，列出零调用点孤儿清单（同名模块自称不算接线） |
| `console_hub` | 只读 | — | —（空载荷走该位默认 op） | `user_error` | 工作台中枢：**所有独立页面的唯一数据源**（主人令 2026-09-28「把所有触手连接全面专业化 3D 可视化…每个工作流的独立页面需要精细设计排布…必须先全面扫描确保不能遗漏」）：`pages` 页面登记表（单一真相）· `graph` 3D 图（30 域→209 能力→绑… |
| `context_vault` | 只读 | — | —（空载荷走该位默认 op） | `user_error` | 上下文归档库（只读骨架·内调）：**索引+检索层，不是第四处存储**（只引用不复制正文）；内存多大上下文就多长（按**可用**内存算预算，不足则降级如实报）；快速搜索=倒排求交→打分→按预算裁剪 |
| `coverage_auditor` | 只读 | — | —（空载荷走该位默认 op） | `user_error` | 触手覆盖审计（只读骨架）：八短板↔八触手组 + 覆盖率读数 + 死角登记 + 五条红线 |
| `cross_scan` | 只读 | — | —（空载荷走该位默认 op） | `user_error` | 扫描一下/扫一下/深度扫描/交叉扫描/穿透式扫描/全框架扫：深度穿透式交叉验证（注册↔路由↔导入↔断链↔运行时↔多扫描器互证，十维），扫描器互相咬、不各报各的 |
| `delivery_gate` | **需授权** | — | —（空载荷走该位默认 op） | `user_error` / `failed` | **交付闸**（主人令 2026-10-09：「每一个能力必须单独跑通闭环才能交付，要不然我不管你做了多久我直接丢垃圾桶不带说的」）。移植来源 V9 core/delivery_gate.py，**设计借过来、件按 V8 自己造**：V8 的「独立验收器」= caps_sweep… |
| `detail_habit` | 只读 | — | —（空载荷走该位默认 op） | `user_error` | 细节化习惯 · **调用侧**门口（只读）：五问为准（输入/动作/明细/判据/接点 —— 与既有判据件 `tools/codex-scripts/detail-check.py`（主人令 2026-10-09）**同源**，op=same_source 逐字比对、分叉即红）+ 明… |
| `energy_pool` | 只读 | — | —（空载荷走该位默认 op） | `user_error` | 能源池（只读骨架·内调）：模型=燃料不是身份；能源抽象 EnergySource + 原生衍生器 + 按需分配；五条红线（模型非身份/能源可换栈不动/衍生码走原生路由/按需/没能源如实报缺） |
| `figure_gate` | **需授权** | — | —（空载荷走该位默认 op） | `user_error` / `failed` | **出图交付门**（蒸馏 `wheresryan22/anatomy` 与 `AirsupHQ/machine-skill` 两份开源 Skill 的铁律）：**"The object is the explanation" + "real numbers or nothing"… |
| `file_hygiene` | 只读 | — | —（空载荷走该位默认 op） | `user_error` | 文件卫生层：按 LAYOUT.md 家规自检乱放+自动归位（散落/空壳/越界数据/缓存） |
| `god_view` | 只读 | — | —（空载荷走该位默认 op） | `user_error` | **上帝视角**（主人令 2026-10-09：「上帝视角也是一个超级导航和给你意见和建议也是一种给项目增加的定心丸」）。来历如实：索引里 OpenClaw Monitor → god_view，2026-09-20 盘上 0 命中、只能标 unverified；原先 V8 只有… |
| `gods_eye` | 只读 | — | —（空载荷走该位默认 op） | `user_error` | 上帝之眼（主人令 2026-09-27）：**看得见创作页面**（7 个面板 + 服务端口真连）+ **两位顾问（权限机器可读）**——Claude 只出意见建议（架构/方向/评审，**无决策权**）· CodeBuddy 只做杂事（**对主项目没有执行权**，点主项目路径一律拒… |
| `growth_hooks` | 只读 | — | —（空载荷走该位默认 op） | `user_error` | 短板钩子 + 自主进化钩子（主人令「设计好短板钩子和自主进化钩子实现自我进化」）：短板**从已有读数算**（六面 + 未清故障 + 未实现 + 触手库覆盖 + 许可缺口），**每条带 src**；进化只**自动做不带门的**（读类/生成索引/补记忆），带门的列成待主人清单。两条纪… |
| `handoff` | 只读 | — | —（空载荷走该位默认 op） | `user_error` | 跨体接续包（ai-memory #08 蒸馏）：三桶=架构背景/失败尝试/未完成任务（缺桶必须显式空数组）；**没 src 不收**（传闻不入账）；只追加不删（作废走 retract）；read 给『每桶最新一条 + 未完成计数』供接手第一眼。op=write/read/retr… |
| `health` | 只读 | — | —（空载荷走该位默认 op） | `user_error` | 系统健康信息（平台/Python/时间） |
| `hook_registry` | 只读 | — | —（空载荷走该位默认 op） | `user_error` | 钩子矩阵只读注册表：50 钩子/六类/三层 + 三条红线（L3 不许挂触手内·失败隔离·链可中断） |
| `impact_check` | 只读 | 是 | —（空载荷走该位默认 op） | `user_error` | **影响面检查（多域监控的读数面）**（主人令 2026-10-19：「修改一个地方的时候要分出触手关注跟这个修复的地方相连的所有地方，确保你修改其他地方不会被连带故障」）：读 `state/model-pack/wiring.json` 邻接图（现读 **6301 节点 / 9… |
| `inventory` | 只读 | — | —（空载荷走该位默认 op） | `user_error` | 全息盘点：一次输出你的视图+框架的视图（归属四分类：框架/环境/数据/异物）——对齐两个世界 |
| `ledger_note` | 只读 | — | —（空载荷走该位默认 op） | `user_error` | **台账登记**（R-H600 立）：三原语 RULES（读七道硬闸）/ PREVIEW（只读预演，不落盘）/ APPEND（**唯一写原语**）。七道机械闸全做成闸、不是口号：**目标固定**（只能写 gbt_allinone/docs/待落刀登记.md，**调用方传不了路径*… |
| `orchestration_kernel` | 只读 | — | —（空载荷走该位默认 op） | `user_error` | 编排内核（三源蒸馏）：状态/动作空间 + 角色/流程 + 可存储图/挂起恢复；只读能力真执行 |
| `page_scan` | 只读 | — | —（空载荷走该位默认 op） | `user_error` | **按绑定逐页并发扫**（主人 2026-10-12 定的架构「触手随每一页绑定好，扫的时候按绑定一页一页传回来」）：源 = state/page-bindings.json 的逐页（页→落点→正向_能力位，全在盘）；**按契约判色**——绿=跑通 / 黄=需参数或需授权（契约与… |
| `project_drift` | 只读 | — | —（空载荷走该位默认 op） | `user_error` | **全项目变化监控（第三块监控：全控变化）**（主人 2026-10-19：「多余监控还缺了一个全控变化，也就是要有一个看着整个项目变化的」）：跟 heartbeat（每根触手还通不通）与 impact_check（这一刀会撞到谁）并列 —— 本位回答「**整个项目从基线到现在变… |
| `room_space` | **需授权** | — | —（空载荷走该位默认 op） | `user_error` / `failed` | 镜像房间空间（**隔离排练现实**，主人令生产面红线：所有假设/模拟/推演/打磨一律在房间里跑，房间不覆盖全局 mirror_space/reality）：create/enter/define_plan/get_plan/frame/gate/namespace/shape/s… |
| `root_fix` | 只读 | — | —（空载荷走该位默认 op） | `user_error` | 根治环：症状五问诊断/补丁债量化/根治铁律——她自己必须懂的根源追踪纪律 |
| `scan_cap` | **需授权** | — | —（空载荷走该位默认 op） | `user_error` / `failed` | **统一扫描位**（蒸馏 20 个星标最高、原理各异的开源扫描器：Trivy/Grype/OSV · Semgrep/CodeQL/Bandit ·gitleaks/TruffleHog · nuclei/ZAP · Syft · Checkov/tfsec/kube-linte… |
| `selfscan` | 只读 | — | —（空载荷走该位默认 op） | `user_error` | 体检一下/自检/查毛病/有没有问题/哪里有问题/框架健康：五维扫描（路由/模块/存储/审计/桩缺口），P0断连第一时间报警 |
| `shared_resources` | 只读 | — | —（空载荷走该位默认 op） | `user_error` | 共享资源池（只读骨架）：虚拟号/邮箱按需租借——资源可共享、身份不共享、每次调用留痕 |
| `signature_guard` | 只读 | — | —（空载荷走该位默认 op） | `user_error` | 署名守卫：扫描全框架页面开发者署名完整性，缺失即报可按需自动补回（禁止删除） |
| `skill_watch` | 只读 | — | —（空载荷走该位默认 op） | `user_error` | **技能观察器**（主人令 2026-10-11「使用技能在每次使用的时候都要注意技能的**变化和短板**来打磨进化」）：每次用技能留三笔 —— **用成没成（读数）· 它变了没（面漂移）· 它短板在哪（打磨点）**。① observe：cap/成败/耗时/错误类/被门拦 ⇒ 只… |
| `slim_profile` | 只读 | — | —（空载荷走该位默认 op） | `user_error` | 瘦身画像（simslim 架构蒸馏）：**命名类别 + profile + 三档闸 + 裁后复核**——`plan` 只读量出按类别的可回收体积（同 disk-plan）；`cut` **必须 confirm=true** 且**只搬不删**（.trash/slim-<ts>/<… |
| `spend_guard` | 只读 | — | —（空载荷走该位默认 op） | `user_error` | 花费守卫（paperclip 成本治理蒸馏）：**按维度追踪调用与 token + 阈值三态判定**——`ledger` 从 key_gateway 真账按日/按源聚合（token 记多少报多少，**免费通道 0 就报 0**，不按价目表脑补）· `policy` 阈值策略（数据… |
| `surface_bind` | 只读 | — | —（空载荷走该位默认 op） | `user_error` | 通用「可控制面」绑定器（主人令 2026-09-27：「其他工具全部都要可控按键一个不漏的绑定好」）：**让每个工具自己报出可控制键**（ffmpeg -filters/-encoders/-formats… · git help -a · genoffice --help ·… |
| `task_manager` | 只读 | — | —（空载荷走该位默认 op） | `user_error` | 任务管理器（主人令 2026-09-27）：一屏看全「任务 / 归属 / 内存占用 / CPU / 端口 / 进程ID」；psutil 读**真进程**（CPU 需两次采样：process_iter 的 info 是首次缓存，第二遍必须直接再调）；归属按**进程名优先**认（血账… |
| `tentacle_arm` | 只读 | — | —（空载荷走该位默认 op） | `user_error` | **触手操控臂**（主人令 2026-10-19「你要以这些能力的思路来操控触手，本身触手就是我们的手，所以必须学会这样的操控精度」）：把 Omni-Arm 的五层精度模型套到能力位上 —— 关节 = 一次 (kind, op, payload)；`dof` = 该位在注册表登记… |
| `tentacle_bind` | 只读 | — | —（空载荷走该位默认 op） | `user_error` | 资产↔触手穿透式绑定（主人令 2026-09-26）：每个资产绑定到产生/维护它的触手；bind/unbind/auto/sweep 增删绑定，scan 全量体检（红点只剩「触手断连」一种：资产缺失或触手不在注册表），coverage 报穿透率，一切动作追加写 state/ass… |
| `tentacle_cognition` | 只读 | — | —（空载荷走该位默认 op） | `user_error` | 触手认知包（只读骨架）：任务上下文/角色边界/自检三问/不确定上报/操作留痕 + 五条零容忍红线 |
| `theme_cap` | **需授权** | — | —（空载荷走该位默认 op） | `user_error` / `failed` | **主题能力位**（蒸馏自 Omarchy 的 "colors.toml 主色 + 模板重生成全系统配置"）：**一份取值空间（[colors] + [dims]） ⇒ 四个界面 CSS 的主题块一起变**。op=list/show 看色源；check 判据（漂移 + 悬空引用… |
| `trace_store` | 只读 | — | —（空载荷走该位默认 op） | `user_error` | 痕迹库只读读数：五张表（wave_samples/traces/trace_links/promotes/obsessions）条数 |
| `truth_scan` | 只读 | — | —（空载荷走该位默认 op） | `user_error` | 真实性审计层：逐能力验证真执行，零假执行铁律（probe 模式含副作用探针） |
| `ux_doctrine` | 只读 | — | —（空载荷走该位默认 op） | `user_error` | **交互铁律**（主人令 2026-10-09）：「在框架里面出来必须要用户求助帮忙的其他全部禁止掉……你开口要求用户的时候你就输了」「可以跟用户商量项目架构和排布，严禁要求用户帮助」「每次停下要么是项目部署完成，要么就是真正需要用户来操作的可以停下，其他时候你停下干嘛」。移植自… |
| `wave_probe` | 只读 | — | —（空载荷走该位默认 op） | `user_error` | 痕迹触手只读量一次波动（默认只量不写；trigger_mode 与盲区一并回报） |
| `welcome` | 只读 | — | —（空载荷走该位默认 op） | `user_error` | **启动欢迎语**（主人令 2026-10-10：「启动APP数字人的欢迎语，你来看看说什么，要有 GBT小土豆V8 和 开发者：自由的风，其他你来想要有未来感的语言」）。文字是**单一真源**（gbt_allinone/welcome.py 的 WELCOME；必含项由 che… |

> 表格里是**摘要**（超过 140 字截断）；下面每位还有**逐位详解**（完整原文 / 要哪张票 / 真调用命令 / 缺什么会怎么报）。

---

## 逐位详解

### `action_gate`

- **域**：`system`（系统）
- **类型**：只读（不改状态、不出网） · **需参数**：否
- **要哪张票（静态）**：零作用域（空 payload 下不需要票）
- **必填载荷**：无必填（空载荷落到该位默认 op；位内更细的 op 参数见模块）
- **常见错误**：参数非法 → `user_error`
- **它做什么**：先看→动脑→执行 前置闸（主人令「做事拥有先看在动脑执行，拒绝所有的无脑操作以及盲猜」）：**没证据不许动手**（evidence 必须真在盘上）· **证据要新**（默认 ≤600s，旧读数不许当现状）· **必须写预期**（hypothesis ≥8 字，否则算盲猜）· **写/执行要票**（scope 或 owner 类许可）。过了发 gate_id，做完 `close` 回填结果+**亲眼看到的**（saw 不许空）。台账 state/action_gate.jsonl。op=observe/preflight/close/status/verify/where
- **怎么调**：`py -3.14 tools/codex-scripts/five-dim.py cap action_gate '<json>'`
- **失败三态**（本仓统一口径，不是这一位特有）：`denied` = 缺票，会点名`missing_scopes`；`needs_*` = 缺参/缺依赖，会带原因；`failed` = 真失败，回执带上游原话。**信封 `status=ok` ≠ 本体 `ok=true`。**

### `agent_console`

- **域**：`system`（系统）
- **类型**：只读（不改状态、不出网） · **需参数**：否
- **要哪张票（静态）**：零作用域（空 payload 下不需要票）
- **必填载荷**：无必填（空载荷落到该位默认 op；位内更细的 op 参数见模块）
- **常见错误**：参数非法 → `user_error`
- **它做什么**：代理驾驶舱：**任务监督循环 + 连接请求审批桥**（蒸馏自 GitHub 周榜 #05 paperclip，只取架构）：`add` 登记被监督任务（判活看**读数有没有如期更新**，不是 exit code）· `tick` 定时检查出 ok/stale/failed 并列出该做什么（**不擅自执行**）· `retry`/`wake` 要 process_execute 门 · `request`/`pending`/`approve` 连接请求审批桥：**approve 要求 TTY + 手打 YES ⇒ AI 批不了**。op=add/tick/board/retry/wake/request/pending/approve/verify/where
- **怎么调**：`py -3.14 tools/codex-scripts/five-dim.py cap agent_console '<json>'`
- **失败三态**（本仓统一口径，不是这一位特有）：`denied` = 缺票，会点名`missing_scopes`；`needs_*` = 缺参/缺依赖，会带原因；`failed` = 真失败，回执带上游原话。**信封 `status=ok` ≠ 本体 `ok=true`。**

### `agent_control`

- **域**：`system`（系统）
- **类型**：只读（不改状态、不出网） · **需参数**：否
- **要哪张票（静态）**：零作用域（空 payload 下不需要票）
- **必填载荷**：无必填（空载荷落到该位默认 op；位内更细的 op 参数见模块）
- **常见错误**：参数非法 → `user_error`
- **它做什么**：Agent 统一控制面（nasiko #04 蒸馏）：六面读数收进一屏——部署/路由/鉴权/限流/成本/链路，**每面带 src、不新起网关/Sidecar、只读不改配置**；读不到就写读不到（未验≠没有），成本面如实标 unknown。op=roster/facets/where
- **怎么调**：`py -3.14 tools/codex-scripts/five-dim.py cap agent_control '<json>'`
- **失败三态**（本仓统一口径，不是这一位特有）：`denied` = 缺票，会点名`missing_scopes`；`needs_*` = 缺参/缺依赖，会带原因；`failed` = 真失败，回执带上游原话。**信封 `status=ok` ≠ 本体 `ok=true`。**

### `agent_rig`

- **域**：`system`（系统）
- **类型**：只读（不改状态、不出网） · **需参数**：否
- **要哪张票（静态）**：零作用域（空 payload 下不需要票）
- **必填载荷**：无必填（空载荷落到该位默认 op；位内更细的 op 参数见模块）
- **常见错误**：参数非法 → `user_error`
- **它做什么**：编码智能体编队：**把本机已装的 CLI agent 编成并行流水线**（蒸馏自 GitHub 周榜 #02 orca，只取架构）：`agents` 只读盘点可编排的 agent（fail-closed）· `plan` 把一批任务分成 N 份（每份 worktree + 端口段 + 隔离 HOME + 独立日志，口径抄 tentacle_fleet）**只出计划** · `dispatch` 要 process_execute 门、任务只进文件不进命令行 · `collect` 从各份 worktree 收改动。op=agents/plan/dispatch/status/collect/verify/where
- **怎么调**：`py -3.14 tools/codex-scripts/five-dim.py cap agent_rig '<json>'`
- **失败三态**（本仓统一口径，不是这一位特有）：`denied` = 缺票，会点名`missing_scopes`；`needs_*` = 缺参/缺依赖，会带原因；`failed` = 真失败，回执带上游原话。**信封 `status=ok` ≠ 本体 `ok=true`。**

### `alerts`

- **域**：`system`（系统）
- **类型**：只读（不改状态、不出网） · **需参数**：否
- **要哪张票（静态）**：零作用域（空 payload 下不需要票）
- **必填载荷**：无必填（空载荷落到该位默认 op；位内更细的 op 参数见模块）
- **常见错误**：参数非法 → `user_error`
- **它做什么**：框架声带：近期异常摘要+根源线索（按能力聚合）
- **怎么调**：`py -3.14 tools/codex-scripts/five-dim.py cap alerts '<json>'`
- **失败三态**（本仓统一口径，不是这一位特有）：`denied` = 缺票，会点名`missing_scopes`；`needs_*` = 缺参/缺依赖，会带原因；`failed` = 真失败，回执带上游原话。**信封 `status=ok` ≠ 本体 `ok=true`。**

### `answer_shaper`

- **域**：`system`（系统）
- **类型**：只读（不改状态、不出网） · **需参数**：否
- **要哪张票（静态）**：零作用域（空 payload 下不需要票）
- **必填载荷**：无必填（空载荷落到该位默认 op；位内更细的 op 参数见模块）
- **常见错误**：参数非法 → `user_error`
- **它做什么**：行动优先输出核（蒸馏自 2026-09-28 主人给的周榜截图 ayghri/i-have-adhd——截图只给仓库名，**未联网核验、未引用该仓任何代码/文本**；纪律取自本仓自己的沟通纪律与已有技能 gbt-adhd-mode，本件补**运行时可机检的核**）：`check` 五条确定性规则逐条判定（R1 首行是行动不是铺垫 · R2 有编号步骤 · R3 步骤≤5 · R4 无客套收尾 · R5 有下一步），零模型零出网零幻觉、每条带命中细节；`shape` **纯机械重排**（剥铺垫/抽编号步骤/截到 5 步），抽不出的原样进「未判定」区标需人看——**不替作者补写一字**。op=check/shape/where
- **怎么调**：`py -3.14 tools/codex-scripts/five-dim.py cap answer_shaper '<json>'`
- **失败三态**（本仓统一口径，不是这一位特有）：`denied` = 缺票，会点名`missing_scopes`；`needs_*` = 缺参/缺依赖，会带原因；`failed` = 真失败，回执带上游原话。**信封 `status=ok` ≠ 本体 `ok=true`。**

### `asset_index`

- **域**：`system`（系统）
- **类型**：只读（不改状态、不出网） · **需参数**：否
- **要哪张票（静态）**：零作用域（空 payload 下不需要票）
- **必填载荷**：无必填（空载荷落到该位默认 op；位内更细的 op 参数见模块）
- **常见错误**：参数非法 → `user_error`
- **它做什么**：资产索引：**整棵树都连上 + 连上即可秒查**（主人令 2026-09-27）。build 把全树扫进 state/asset_index.db（键=跟随软链的物理真身，与绑定系统同口径，软链别名去重）；wire 给每个资产补触手标签（启发式优先，认不出用回退标签 project_context —— 诚实标注归属，不假装认出了专门触手）；find 查索引**不扫盘**（实测 17-22ms）。op=build/wire/find/stats
- **怎么调**：`py -3.14 tools/codex-scripts/five-dim.py cap asset_index '<json>'`
- **失败三态**（本仓统一口径，不是这一位特有）：`denied` = 缺票，会点名`missing_scopes`；`needs_*` = 缺参/缺依赖，会带原因；`failed` = 真失败，回执带上游原话。**信封 `status=ok` ≠ 本体 `ok=true`。**

### `auth_gate_status`

- **域**：`system`（系统）
- **类型**：只读（不改状态、不出网） · **需参数**：否
- **要哪张票（静态）**：零作用域（空 payload 下不需要票）
- **必填载荷**：无必填（空载荷落到该位默认 op；位内更细的 op 参数见模块）
- **常见错误**：参数非法 → `user_error`
- **它做什么**：人工授权门状态：各作用域可用授权数（只读；授权只能人发放）
- **怎么调**：`py -3.14 tools/codex-scripts/five-dim.py cap auth_gate_status '<json>'`
- **失败三态**（本仓统一口径，不是这一位特有）：`denied` = 缺票，会点名`missing_scopes`；`needs_*` = 缺参/缺依赖，会带原因；`failed` = 真失败，回执带上游原话。**信封 `status=ok` ≠ 本体 `ok=true`。**

### `cap_tags`

- **域**：`system`（系统）
- **类型**：只读（不改状态、不出网） · **需参数**：否
- **要哪张票（静态）**：零作用域（空 payload 下不需要票）
- **必填载荷**：无必填（空载荷落到该位默认 op；位内更细的 op 参数见模块）
- **常见错误**：参数非法 → `user_error`
- **它做什么**：GBT 技能标签 + 主人调用许可（主人令「将所有的原生能力注册出专属的 GBT 技能标签，只有我允许了才能调用我的能力」）：每个能力位一个稳定标签 `GBT-<域>-<能力位>`，**从注册表现算**；权限类**由框架自己的判据推**（`policy.evaluate` 逐 op 问作用域 + 图鉴 safe/needs_confirmation），**读不出来一律按 owner**（默认严）。`owner` 类=只有主人发许可才能调；许可在 `gbt_allinone/store/owner_permits.jsonl`，**本能力没有任何写它的路径**，终端 `permit` 命令要求 TTY + 手打 YES ⇒ **AI 发不出许可**。op=tags/check/permits/how/audit/verify/where/permit
- **怎么调**：`py -3.14 tools/codex-scripts/five-dim.py cap cap_tags '<json>'`
- **失败三态**（本仓统一口径，不是这一位特有）：`denied` = 缺票，会点名`missing_scopes`；`needs_*` = 缺参/缺依赖，会带原因；`failed` = 真失败，回执带上游原话。**信封 `status=ok` ≠ 本体 `ok=true`。**

### `caps_called_audit`

- **域**：`system`（系统）
- **类型**：只读（不改状态、不出网） · **需参数**：否
- **要哪张票（静态）**：零作用域（空 payload 下不需要票）
- **必填载荷**：无必填（空载荷落到该位默认 op；位内更细的 op 参数见模块）
- **常见错误**：参数非法 → `user_error`
- **它做什么**：能力位调用点审计（只读）：动态算 called_by，列出零调用点孤儿清单（同名模块自称不算接线）
- **怎么调**：`py -3.14 tools/codex-scripts/five-dim.py cap caps_called_audit '<json>'`
- **失败三态**（本仓统一口径，不是这一位特有）：`denied` = 缺票，会点名`missing_scopes`；`needs_*` = 缺参/缺依赖，会带原因；`failed` = 真失败，回执带上游原话。**信封 `status=ok` ≠ 本体 `ok=true`。**

### `console_hub`

- **域**：`system`（系统）
- **类型**：只读（不改状态、不出网） · **需参数**：否
- **要哪张票（静态）**：零作用域（空 payload 下不需要票）
- **必填载荷**：无必填（空载荷落到该位默认 op；位内更细的 op 参数见模块）
- **常见错误**：参数非法 → `user_error`
- **它做什么**：工作台中枢：**所有独立页面的唯一数据源**（主人令 2026-09-28「把所有触手连接全面专业化 3D 可视化…每个工作流的独立页面需要精细设计排布…必须先全面扫描确保不能遗漏」）：`pages` 页面登记表（单一真相）· `graph` 3D 图（30 域→209 能力→绑定弧→**运行脉冲=真台账尾**）· `widgets` Bento 九部件（**每个数带 src**）· `layout` 布局记忆 · `scan` **「不能遗漏」机检**（盘上现读 vs 登记表双向比对，未登记=盲区必须 0）。op=pages/graph/widgets/layout/scan/verify/where
- **怎么调**：`py -3.14 tools/codex-scripts/five-dim.py cap console_hub '<json>'`
- **失败三态**（本仓统一口径，不是这一位特有）：`denied` = 缺票，会点名`missing_scopes`；`needs_*` = 缺参/缺依赖，会带原因；`failed` = 真失败，回执带上游原话。**信封 `status=ok` ≠ 本体 `ok=true`。**

### `context_vault`

- **域**：`system`（系统）
- **类型**：只读（不改状态、不出网） · **需参数**：否
- **要哪张票（静态）**：零作用域（空 payload 下不需要票）
- **必填载荷**：无必填（空载荷落到该位默认 op；位内更细的 op 参数见模块）
- **常见错误**：参数非法 → `user_error`
- **它做什么**：上下文归档库（只读骨架·内调）：**索引+检索层，不是第四处存储**（只引用不复制正文）；内存多大上下文就多长（按**可用**内存算预算，不足则降级如实报）；快速搜索=倒排求交→打分→按预算裁剪
- **怎么调**：`py -3.14 tools/codex-scripts/five-dim.py cap context_vault '<json>'`
- **失败三态**（本仓统一口径，不是这一位特有）：`denied` = 缺票，会点名`missing_scopes`；`needs_*` = 缺参/缺依赖，会带原因；`failed` = 真失败，回执带上游原话。**信封 `status=ok` ≠ 本体 `ok=true`。**

### `coverage_auditor`

- **域**：`system`（系统）
- **类型**：只读（不改状态、不出网） · **需参数**：否
- **要哪张票（静态）**：零作用域（空 payload 下不需要票）
- **必填载荷**：无必填（空载荷落到该位默认 op；位内更细的 op 参数见模块）
- **常见错误**：参数非法 → `user_error`
- **它做什么**：触手覆盖审计（只读骨架）：八短板↔八触手组 + 覆盖率读数 + 死角登记 + 五条红线
- **怎么调**：`py -3.14 tools/codex-scripts/five-dim.py cap coverage_auditor '<json>'`
- **失败三态**（本仓统一口径，不是这一位特有）：`denied` = 缺票，会点名`missing_scopes`；`needs_*` = 缺参/缺依赖，会带原因；`failed` = 真失败，回执带上游原话。**信封 `status=ok` ≠ 本体 `ok=true`。**

### `cross_scan`

- **域**：`system`（系统）
- **类型**：只读（不改状态、不出网） · **需参数**：否
- **要哪张票（静态）**：零作用域（空 payload 下不需要票）
- **必填载荷**：无必填（空载荷落到该位默认 op；位内更细的 op 参数见模块）
- **常见错误**：参数非法 → `user_error`
- **它做什么**：扫描一下/扫一下/深度扫描/交叉扫描/穿透式扫描/全框架扫：深度穿透式交叉验证（注册↔路由↔导入↔断链↔运行时↔多扫描器互证，十维），扫描器互相咬、不各报各的
- **怎么调**：`py -3.14 tools/codex-scripts/five-dim.py cap cross_scan '<json>'`
- **失败三态**（本仓统一口径，不是这一位特有）：`denied` = 缺票，会点名`missing_scopes`；`needs_*` = 缺参/缺依赖，会带原因；`failed` = 真失败，回执带上游原话。**信封 `status=ok` ≠ 本体 `ok=true`。**

### `delivery_gate`

- **域**：`system`（系统）
- **类型**：**需授权**（会写盘 / 花钱 / 出网） · **需参数**：否
- **要哪张票（静态）**：零作用域（空 payload 下不需要票）
- **必填载荷**：无必填（空载荷落到该位默认 op；位内更细的 op 参数见模块）
- **常见错误**：参数非法 → `user_error`；依赖不在位 → `needs_dependency`；上游不给 → `needs_input` / `failed`（带上游原话）
- **它做什么**：**交付闸**（主人令 2026-10-09：「每一个能力必须单独跑通闭环才能交付，要不然我不管你做了多久我直接丢垃圾桶不带说的」）。移植来源 V9 core/delivery_gate.py，**设计借过来、件按 V8 自己造**：V8 的「独立验收器」= caps_sweep 真过唯一门调用那位能力 + 它自己的测试件。op=status 读全量扫账逐档计数 · check 单件**现跑** · audit 逐件判定 · gate 硬闸（不可交付⇒ok=false）。判据：通/如实否⇒可交付 · 如实拒⇒可交付但要写明缺哪张票 · 要参数/缺依赖/真坏/未扫⇒**禁交付**；参数型输入口要**登记**（DECLARED_NEEDPARAM）才放行，没登记一律照旧禁交付。
- **怎么调**：`py -3.14 tools/codex-scripts/five-dim.py cap delivery_gate '<json>'`
- **失败三态**（本仓统一口径，不是这一位特有）：`denied` = 缺票，会点名`missing_scopes`；`needs_*` = 缺参/缺依赖，会带原因；`failed` = 真失败，回执带上游原话。**信封 `status=ok` ≠ 本体 `ok=true`。**

### `detail_habit`

- **域**：`system`（系统）
- **类型**：只读（不改状态、不出网） · **需参数**：否
- **要哪张票（静态）**：零作用域（空 payload 下不需要票）
- **必填载荷**：无必填（空载荷落到该位默认 op；位内更细的 op 参数见模块）
- **常见错误**：参数非法 → `user_error`
- **它做什么**：细节化习惯 · **调用侧**门口（只读）：五问为准（输入/动作/明细/判据/接点 —— 与既有判据件 `tools/codex-scripts/detail-check.py`（主人令 2026-10-09）**同源**，op=same_source 逐字比对、分叉即红）+ 明细必须逐项（只报合计数 = 没有细节）+ 三条扩展（模糊词禁用 / 回读三件 / 一步产出<=3）。缺哪件点哪件，**部分合格不算合格**；op=habit/same_source/check_text/check_step/check
- **怎么调**：`py -3.14 tools/codex-scripts/five-dim.py cap detail_habit '<json>'`
- **失败三态**（本仓统一口径，不是这一位特有）：`denied` = 缺票，会点名`missing_scopes`；`needs_*` = 缺参/缺依赖，会带原因；`failed` = 真失败，回执带上游原话。**信封 `status=ok` ≠ 本体 `ok=true`。**

### `energy_pool`

- **域**：`system`（系统）
- **类型**：只读（不改状态、不出网） · **需参数**：否
- **要哪张票（静态）**：零作用域（空 payload 下不需要票）
- **必填载荷**：无必填（空载荷落到该位默认 op；位内更细的 op 参数见模块）
- **常见错误**：参数非法 → `user_error`
- **它做什么**：能源池（只读骨架·内调）：模型=燃料不是身份；能源抽象 EnergySource + 原生衍生器 + 按需分配；五条红线（模型非身份/能源可换栈不动/衍生码走原生路由/按需/没能源如实报缺）
- **怎么调**：`py -3.14 tools/codex-scripts/five-dim.py cap energy_pool '<json>'`
- **失败三态**（本仓统一口径，不是这一位特有）：`denied` = 缺票，会点名`missing_scopes`；`needs_*` = 缺参/缺依赖，会带原因；`failed` = 真失败，回执带上游原话。**信封 `status=ok` ≠ 本体 `ok=true`。**

### `figure_gate`

- **域**：`system`（系统）
- **类型**：**需授权**（会写盘 / 花钱 / 出网） · **需参数**：否
- **要哪张票（静态）**：零作用域（空 payload 下不需要票）
- **必填载荷**：无必填（空载荷落到该位默认 op；位内更细的 op 参数见模块）
- **常见错误**：参数非法 → `user_error`；依赖不在位 → `needs_dependency`；上游不给 → `needs_input` / `failed`（带上游原话）
- **它做什么**：**出图交付门**（蒸馏 `wheresryan22/anatomy` 与 `AirsupHQ/machine-skill` 两份开源 Skill 的铁律）：**"The object is the explanation" + "real numbers or nothing" + §8 像批评家一样看图（required）"**。op=checklist 列“不算完成”六条并**逐条标可检度**（M 机检 / A 需产物 / H 只能人看）；declare_numbers 必须说清屏幕上的数由谁算出来；record_round 记一轮看图与问题清单；verdict 是 **fail-closed** 交付判据：数未声明 / 轮次不足 4 轮 / 最新一轮还有未清问题 ⇒ 不可交付。标 H 的那几条**仍需人看**，本件不假装能自动判美丑。
- **怎么调**：`py -3.14 tools/codex-scripts/five-dim.py cap figure_gate '<json>'`
- **失败三态**（本仓统一口径，不是这一位特有）：`denied` = 缺票，会点名`missing_scopes`；`needs_*` = 缺参/缺依赖，会带原因；`failed` = 真失败，回执带上游原话。**信封 `status=ok` ≠ 本体 `ok=true`。**

### `file_hygiene`

- **域**：`system`（系统）
- **类型**：只读（不改状态、不出网） · **需参数**：否
- **要哪张票（静态）**：零作用域（空 payload 下不需要票）
- **必填载荷**：无必填（空载荷落到该位默认 op；位内更细的 op 参数见模块）
- **常见错误**：参数非法 → `user_error`
- **它做什么**：文件卫生层：按 LAYOUT.md 家规自检乱放+自动归位（散落/空壳/越界数据/缓存）
- **怎么调**：`py -3.14 tools/codex-scripts/five-dim.py cap file_hygiene '<json>'`
- **失败三态**（本仓统一口径，不是这一位特有）：`denied` = 缺票，会点名`missing_scopes`；`needs_*` = 缺参/缺依赖，会带原因；`failed` = 真失败，回执带上游原话。**信封 `status=ok` ≠ 本体 `ok=true`。**

### `god_view`

- **域**：`system`（系统）
- **类型**：只读（不改状态、不出网） · **需参数**：否
- **要哪张票（静态）**：零作用域（空 payload 下不需要票）
- **必填载荷**：无必填（空载荷落到该位默认 op；位内更细的 op 参数见模块）
- **常见错误**：参数非法 → `user_error`
- **它做什么**：**上帝视角**（主人令 2026-10-09：「上帝视角也是一个超级导航和给你意见和建议也是一种给项目增加的定心丸」）。来历如实：索引里 OpenClaw Monitor → god_view，2026-09-20 盘上 0 命中、只能标 unverified；原先 V8 只有一块**只读总览**（自述「只呈现，不执行」），既不会导航也不会给意见 —— 本轮补成真能力位。四个 op：overview 全局一屏（能力位/域分布/报警/交付闸/今天动作，全现读）· navigate goal=<人话> **超级导航**（意图→域→档 A/B/C 排序，附可直接照抄的命令）· advise 按现读状态给**排好序的意见与建议**（每条带依据，定心丸）· where 一页说清现状与下一步。口径：**只读零作用域**（不起进程/不写盘/不出网）· **不猜**（导航给分与命中词）· **不许反问**（按 ux_doctrine 不开口闸，只给具体候选与命令）。
- **怎么调**：`py -3.14 tools/codex-scripts/five-dim.py cap god_view '<json>'`
- **失败三态**（本仓统一口径，不是这一位特有）：`denied` = 缺票，会点名`missing_scopes`；`needs_*` = 缺参/缺依赖，会带原因；`failed` = 真失败，回执带上游原话。**信封 `status=ok` ≠ 本体 `ok=true`。**

### `gods_eye`

- **域**：`system`（系统）
- **类型**：只读（不改状态、不出网） · **需参数**：否
- **要哪张票（静态）**：零作用域（空 payload 下不需要票）
- **必填载荷**：无必填（空载荷落到该位默认 op；位内更细的 op 参数见模块）
- **常见错误**：参数非法 → `user_error`
- **它做什么**：上帝之眼（主人令 2026-09-27）：**看得见创作页面**（7 个面板 + 服务端口真连）+ **两位顾问（权限机器可读）**——Claude 只出意见建议（架构/方向/评审，**无决策权**）· CodeBuddy 只做杂事（**对主项目没有执行权**，点主项目路径一律拒，只服从与待命）· **决策权在主体**（我）；**每日汇报** = GBT 探针汇报 + 全量扫描 ⇒ **缺点/短板/卡点**（每条带来源 src，不许编）；`plan` 把"提升整体实力"落成提案与决策（留痕 state/gods_eye_plan.jsonl）；`panel` 出上帝之眼页面。op=see/advisors/ask/daily/plan/panel
- **怎么调**：`py -3.14 tools/codex-scripts/five-dim.py cap gods_eye '<json>'`
- **失败三态**（本仓统一口径，不是这一位特有）：`denied` = 缺票，会点名`missing_scopes`；`needs_*` = 缺参/缺依赖，会带原因；`failed` = 真失败，回执带上游原话。**信封 `status=ok` ≠ 本体 `ok=true`。**

### `growth_hooks`

- **域**：`system`（系统）
- **类型**：只读（不改状态、不出网） · **需参数**：否
- **要哪张票（静态）**：零作用域（空 payload 下不需要票）
- **必填载荷**：无必填（空载荷落到该位默认 op；位内更细的 op 参数见模块）
- **常见错误**：参数非法 → `user_error`
- **它做什么**：短板钩子 + 自主进化钩子（主人令「设计好短板钩子和自主进化钩子实现自我进化」）：短板**从已有读数算**（六面 + 未清故障 + 未实现 + 触手库覆盖 + 许可缺口），**每条带 src**；进化只**自动做不带门的**（读类/生成索引/补记忆），带门的列成待主人清单。两条纪律写死：**不自批授权**；**撞 state/holdout.json 封存验收集的步骤一律拦下**（判据不许既当训练又当验收）。op=shortboard/evolve/history/verify/where
- **怎么调**：`py -3.14 tools/codex-scripts/five-dim.py cap growth_hooks '<json>'`
- **失败三态**（本仓统一口径，不是这一位特有）：`denied` = 缺票，会点名`missing_scopes`；`needs_*` = 缺参/缺依赖，会带原因；`failed` = 真失败，回执带上游原话。**信封 `status=ok` ≠ 本体 `ok=true`。**

### `handoff`

- **域**：`system`（系统）
- **类型**：只读（不改状态、不出网） · **需参数**：否
- **要哪张票（静态）**：零作用域（空 payload 下不需要票）
- **必填载荷**：无必填（空载荷落到该位默认 op；位内更细的 op 参数见模块）
- **常见错误**：参数非法 → `user_error`
- **它做什么**：跨体接续包（ai-memory #08 蒸馏）：三桶=架构背景/失败尝试/未完成任务（缺桶必须显式空数组）；**没 src 不收**（传闻不入账）；只追加不删（作废走 retract）；read 给『每桶最新一条 + 未完成计数』供接手第一眼。op=write/read/retract/verify/where
- **怎么调**：`py -3.14 tools/codex-scripts/five-dim.py cap handoff '<json>'`
- **失败三态**（本仓统一口径，不是这一位特有）：`denied` = 缺票，会点名`missing_scopes`；`needs_*` = 缺参/缺依赖，会带原因；`failed` = 真失败，回执带上游原话。**信封 `status=ok` ≠ 本体 `ok=true`。**

### `health`

- **域**：`system`（系统）
- **类型**：只读（不改状态、不出网） · **需参数**：否
- **要哪张票（静态）**：零作用域（空 payload 下不需要票）
- **必填载荷**：无必填（空载荷落到该位默认 op；位内更细的 op 参数见模块）
- **常见错误**：参数非法 → `user_error`
- **它做什么**：系统健康信息（平台/Python/时间）
- **怎么调**：`py -3.14 tools/codex-scripts/five-dim.py cap health '<json>'`
- **失败三态**（本仓统一口径，不是这一位特有）：`denied` = 缺票，会点名`missing_scopes`；`needs_*` = 缺参/缺依赖，会带原因；`failed` = 真失败，回执带上游原话。**信封 `status=ok` ≠ 本体 `ok=true`。**

### `hook_registry`

- **域**：`system`（系统）
- **类型**：只读（不改状态、不出网） · **需参数**：否
- **要哪张票（静态）**：零作用域（空 payload 下不需要票）
- **必填载荷**：无必填（空载荷落到该位默认 op；位内更细的 op 参数见模块）
- **常见错误**：参数非法 → `user_error`
- **它做什么**：钩子矩阵只读注册表：50 钩子/六类/三层 + 三条红线（L3 不许挂触手内·失败隔离·链可中断）
- **怎么调**：`py -3.14 tools/codex-scripts/five-dim.py cap hook_registry '<json>'`
- **失败三态**（本仓统一口径，不是这一位特有）：`denied` = 缺票，会点名`missing_scopes`；`needs_*` = 缺参/缺依赖，会带原因；`failed` = 真失败，回执带上游原话。**信封 `status=ok` ≠ 本体 `ok=true`。**

### `impact_check`

- **域**：`system`（系统）
- **类型**：只读（不改状态、不出网） · **需参数**：是 —— target=要查的目标，如 code:gbt_allinone/api.py / cap:tentacle_arm / holo_pet_w3/omni-arm/index.html；**op=status / risky / where 不用传**；也可用 targets=[…] 一次查多处；depth 默认 2（上限 3）
- **要哪张票（静态）**：零作用域（空 payload 下不需要票）
- **必填载荷**：无必填（空载荷落到该位默认 op；位内更细的 op 参数见模块）
- **常见错误**：参数非法 → `user_error`
- **它做什么**：**影响面检查（多域监控的读数面）**（主人令 2026-10-19：「修改一个地方的时候要分出触手关注跟这个修复的地方相连的所有地方，确保你修改其他地方不会被连带故障」）：读 `state/model-pack/wiring.json` 邻接图（现读 **6301 节点 / 951536 有向边 / 单连通分量 100%**），给一个目标（能力位名 / 代码路径 / 页面路径）就算出它 1~2 跳的影响面。**不是 selfscan**（那是框架五维自检），本位只管刀口宽度。op=status（图的规模·连通性·构建时间，取不到如实报 missing 不编 0）· op=impact（必填 target 或 targets，depth≤3 ⇒ 影响面构成 + **1 跳必验清单**；目标不在图里**如实拒绝**，绝不把空集当"没影响"）· op=risky（n ⇒ 按 1 跳邻居数排最危险的件，并如实标注"本图不分强弱边"）· op=where。**全部纯读免门**：不写盘、不出网、不起进程。已知读数：`code:gbt_allinone/api.py` 1 跳 = 337 个能力位 · depth=2 = 4859 节点 · `cap:tentacle_arm` 2 跳 = 342 节点
- **怎么调**：`py -3.14 tools/codex-scripts/five-dim.py cap impact_check '<json>'`
- **失败三态**（本仓统一口径，不是这一位特有）：`denied` = 缺票，会点名`missing_scopes`；`needs_*` = 缺参/缺依赖，会带原因；`failed` = 真失败，回执带上游原话。**信封 `status=ok` ≠ 本体 `ok=true`。**

### `inventory`

- **域**：`system`（系统）
- **类型**：只读（不改状态、不出网） · **需参数**：否
- **要哪张票（静态）**：零作用域（空 payload 下不需要票）
- **必填载荷**：无必填（空载荷落到该位默认 op；位内更细的 op 参数见模块）
- **常见错误**：参数非法 → `user_error`
- **它做什么**：全息盘点：一次输出你的视图+框架的视图（归属四分类：框架/环境/数据/异物）——对齐两个世界
- **怎么调**：`py -3.14 tools/codex-scripts/five-dim.py cap inventory '<json>'`
- **失败三态**（本仓统一口径，不是这一位特有）：`denied` = 缺票，会点名`missing_scopes`；`needs_*` = 缺参/缺依赖，会带原因；`failed` = 真失败，回执带上游原话。**信封 `status=ok` ≠ 本体 `ok=true`。**

### `ledger_note`

- **域**：`system`（系统）
- **类型**：只读（不改状态、不出网） · **需参数**：否
- **要哪张票（静态）**：零作用域（空 payload 下不需要票）
- **必填载荷**：无必填（空载荷落到该位默认 op；位内更细的 op 参数见模块）
- **常见错误**：参数非法 → `user_error`
- **它做什么**：**台账登记**（R-H600 立）：三原语 RULES（读七道硬闸）/ PREVIEW（只读预演，不落盘）/ APPEND（**唯一写原语**）。七道机械闸全做成闸、不是口号：**目标固定**（只能写 gbt_allinone/docs/待落刀登记.md，**调用方传不了路径**）· **只追加**（目标末尾必须是换行，否则拒写，不修不补）· **单物理行**（行内不许换行 ⇒ 一刀一个物理行）· **禁半角双引号**（中文串用「」）· **行首形状**（`> **<label> 补记`，复核脚本按行首锚定）· **幂等**（同 label 已存在 ⇒ 拒写）· **缺前驱拒写**（给了 after 就必须是当前最后一条，防插队防回填）。⚠️ 它**不判内容对错**（那是取证 + 独立复核的活）；写失败一律抛错，不返回半成功。type=internal
- **怎么调**：`py -3.14 tools/codex-scripts/five-dim.py cap ledger_note '<json>'`
- **失败三态**（本仓统一口径，不是这一位特有）：`denied` = 缺票，会点名`missing_scopes`；`needs_*` = 缺参/缺依赖，会带原因；`failed` = 真失败，回执带上游原话。**信封 `status=ok` ≠ 本体 `ok=true`。**

### `orchestration_kernel`

- **域**：`system`（系统）
- **类型**：只读（不改状态、不出网） · **需参数**：否
- **要哪张票（静态）**：零作用域（空 payload 下不需要票）
- **必填载荷**：无必填（空载荷落到该位默认 op；位内更细的 op 参数见模块）
- **常见错误**：参数非法 → `user_error`
- **它做什么**：编排内核（三源蒸馏）：状态/动作空间 + 角色/流程 + 可存储图/挂起恢复；只读能力真执行
- **怎么调**：`py -3.14 tools/codex-scripts/five-dim.py cap orchestration_kernel '<json>'`
- **失败三态**（本仓统一口径，不是这一位特有）：`denied` = 缺票，会点名`missing_scopes`；`needs_*` = 缺参/缺依赖，会带原因；`failed` = 真失败，回执带上游原话。**信封 `status=ok` ≠ 本体 `ok=true`。**

### `page_scan`

- **域**：`system`（系统）
- **类型**：只读（不改状态、不出网） · **需参数**：否
- **要哪张票（静态）**：零作用域（空 payload 下不需要票）
- **必填载荷**：无必填（空载荷落到该位默认 op；位内更细的 op 参数见模块）
- **常见错误**：参数非法 → `user_error`
- **它做什么**：**按绑定逐页并发扫**（主人 2026-10-12 定的架构「触手随每一页绑定好，扫的时候按绑定一页一页传回来」）：源 = state/page-bindings.json 的逐页（页→落点→正向_能力位，全在盘）；**按契约判色**——绿=跑通 / 黄=需参数或需授权（契约与门，不是故障）/ **红=契约也满足却仍失败**；页/落点/在册三项独立判；并发用满（实测引擎 ≥4096 根零失败）。op=scan/status
- **怎么调**：`py -3.14 tools/codex-scripts/five-dim.py cap page_scan '<json>'`
- **失败三态**（本仓统一口径，不是这一位特有）：`denied` = 缺票，会点名`missing_scopes`；`needs_*` = 缺参/缺依赖，会带原因；`failed` = 真失败，回执带上游原话。**信封 `status=ok` ≠ 本体 `ok=true`。**

### `project_drift`

- **域**：`system`（系统）
- **类型**：只读（不改状态、不出网） · **需参数**：否
- **要哪张票（静态）**：零作用域（空 payload 下不需要票）
- **必填载荷**：无必填（空载荷落到该位默认 op；位内更细的 op 参数见模块）
- **常见错误**：参数非法 → `user_error`
- **它做什么**：**全项目变化监控（第三块监控：全控变化）**（主人 2026-10-19：「多余监控还缺了一个全控变化，也就是要有一个看着整个项目变化的」）：跟 heartbeat（每根触手还通不通）与 impact_check（这一刀会撞到谁）并列 —— 本位回答「**整个项目从基线到现在变了什么、变得合不合理**」。基线不重扫全仓：把 `outputs/repo-pack/files.jsonl`（308,075 件 · 带 bytes/mtime/sha16）收成基线，每次只 stat 一遍，**只对变了的少数件真算 sha16**（单件 >8MB 与超出预算的如实标「内容未验」，不冒充没变）。op=status（基线在哪·多旧·覆盖多少件；没基线就明说"还不知道"）· op=drift（新增/改动/删除/仅碰时间 四类 + 异常项 + 用时；**mtime 早于基线时刻的差异归「基线漏收/旧差异」，不当新变化报**）· op=baseline（冻结新基线，写盘 ⇒ filesystem_write 挂在处理器层）· op=where。异常判据五条：在役/冻结/敏感面被动 · 成批变动(新增>500/删除>100) · 新增可执行件 · 0 字节新件 · 基线过期>24h。实测：全仓 stat 一遍 93 s / 308,291 件
- **怎么调**：`py -3.14 tools/codex-scripts/five-dim.py cap project_drift '<json>'`
- **失败三态**（本仓统一口径，不是这一位特有）：`denied` = 缺票，会点名`missing_scopes`；`needs_*` = 缺参/缺依赖，会带原因；`failed` = 真失败，回执带上游原话。**信封 `status=ok` ≠ 本体 `ok=true`。**

### `room_space`

- **域**：`system`（系统）
- **类型**：**需授权**（会写盘 / 花钱 / 出网） · **需参数**：否
- **要哪张票（静态）**：零作用域（空 payload 下不需要票）
- **必填载荷**：无必填（空载荷落到该位默认 op；位内更细的 op 参数见模块）
- **常见错误**：参数非法 → `user_error`；依赖不在位 → `needs_dependency`；上游不给 → `needs_input` / `failed`（带上游原话）
- **它做什么**：镜像房间空间（**隔离排练现实**，主人令生产面红线：所有假设/模拟/推演/打磨一律在房间里跑，房间不覆盖全局 mirror_space/reality）：create/enter/define_plan/get_plan/frame/gate/namespace/shape/scan/simulate/parity/rehearse/release/sync/status/snapshot。**F12 补齐（2026-10-18 真接完）**：第一版只说"按唯一门接线"，实际 api.py 只路由了前八个；simulate/parity/rehearse/release 等八个原语模块里有、门上没有 ⇒ `gate` 永远报「没有房间排练报告」，房间正路走不完。本轮补齐后「排练 → 盖章 → 原子替换」才真能在门上闭环。
- **怎么调**：`py -3.14 tools/codex-scripts/five-dim.py cap room_space '<json>'`
- **失败三态**（本仓统一口径，不是这一位特有）：`denied` = 缺票，会点名`missing_scopes`；`needs_*` = 缺参/缺依赖，会带原因；`failed` = 真失败，回执带上游原话。**信封 `status=ok` ≠ 本体 `ok=true`。**

### `root_fix`

- **域**：`system`（系统）
- **类型**：只读（不改状态、不出网） · **需参数**：否
- **要哪张票（静态）**：零作用域（空 payload 下不需要票）
- **必填载荷**：无必填（空载荷落到该位默认 op；位内更细的 op 参数见模块）
- **常见错误**：参数非法 → `user_error`
- **它做什么**：根治环：症状五问诊断/补丁债量化/根治铁律——她自己必须懂的根源追踪纪律
- **怎么调**：`py -3.14 tools/codex-scripts/five-dim.py cap root_fix '<json>'`
- **失败三态**（本仓统一口径，不是这一位特有）：`denied` = 缺票，会点名`missing_scopes`；`needs_*` = 缺参/缺依赖，会带原因；`failed` = 真失败，回执带上游原话。**信封 `status=ok` ≠ 本体 `ok=true`。**

### `scan_cap`

- **域**：`system`（系统）
- **类型**：**需授权**（会写盘 / 花钱 / 出网） · **需参数**：否
- **要哪张票（静态）**：零作用域（空 payload 下不需要票）
- **必填载荷**：无必填（空载荷落到该位默认 op；位内更细的 op 参数见模块）
- **常见错误**：参数非法 → `user_error`；依赖不在位 → `needs_dependency`；上游不给 → `needs_input` / `failed`（带上游原话）
- **它做什么**：**统一扫描位**（蒸馏 20 个星标最高、原理各异的开源扫描器：Trivy/Grype/OSV · Semgrep/CodeQL/Bandit ·gitleaks/TruffleHog · nuclei/ZAP · Syft · Checkov/tfsec/kube-linter/kube-bench · ClamAV/YARA · licensee · file）。**三条已落地**：①引擎与规则解耦 + 离线导入（规则/消音台账现读 state/scan_rules/，报 rules_source 与 rules_age_s）；②机器可读 + 退出码门控（schema + severity×confidence + exit_code）；③消音台账不静默（每条必须带 reason，被消音条数与理由全部回报）。九个品种：secrets/sast/deps/iac/inventory/blindspot/orphans/stamp/unimplemented。铁律：**扫描给的是候选不是判决**（disposition=candidate），不把“零假阳”当卖点。op=species/scan/report；前两个只读，report 写 store/scan_cap/。
- **怎么调**：`py -3.14 tools/codex-scripts/five-dim.py cap scan_cap '<json>'`
- **失败三态**（本仓统一口径，不是这一位特有）：`denied` = 缺票，会点名`missing_scopes`；`needs_*` = 缺参/缺依赖，会带原因；`failed` = 真失败，回执带上游原话。**信封 `status=ok` ≠ 本体 `ok=true`。**

### `selfscan`

- **域**：`system`（系统）
- **类型**：只读（不改状态、不出网） · **需参数**：否
- **要哪张票（静态）**：零作用域（空 payload 下不需要票）
- **必填载荷**：无必填（空载荷落到该位默认 op；位内更细的 op 参数见模块）
- **常见错误**：参数非法 → `user_error`
- **它做什么**：体检一下/自检/查毛病/有没有问题/哪里有问题/框架健康：五维扫描（路由/模块/存储/审计/桩缺口），P0断连第一时间报警
- **怎么调**：`py -3.14 tools/codex-scripts/five-dim.py cap selfscan '<json>'`
- **失败三态**（本仓统一口径，不是这一位特有）：`denied` = 缺票，会点名`missing_scopes`；`needs_*` = 缺参/缺依赖，会带原因；`failed` = 真失败，回执带上游原话。**信封 `status=ok` ≠ 本体 `ok=true`。**

### `shared_resources`

- **域**：`system`（系统）
- **类型**：只读（不改状态、不出网） · **需参数**：否
- **要哪张票（静态）**：零作用域（空 payload 下不需要票）
- **必填载荷**：无必填（空载荷落到该位默认 op；位内更细的 op 参数见模块）
- **常见错误**：参数非法 → `user_error`
- **它做什么**：共享资源池（只读骨架）：虚拟号/邮箱按需租借——资源可共享、身份不共享、每次调用留痕
- **怎么调**：`py -3.14 tools/codex-scripts/five-dim.py cap shared_resources '<json>'`
- **失败三态**（本仓统一口径，不是这一位特有）：`denied` = 缺票，会点名`missing_scopes`；`needs_*` = 缺参/缺依赖，会带原因；`failed` = 真失败，回执带上游原话。**信封 `status=ok` ≠ 本体 `ok=true`。**

### `signature_guard`

- **域**：`system`（系统）
- **类型**：只读（不改状态、不出网） · **需参数**：否
- **要哪张票（静态）**：零作用域（空 payload 下不需要票）
- **必填载荷**：无必填（空载荷落到该位默认 op；位内更细的 op 参数见模块）
- **常见错误**：参数非法 → `user_error`
- **它做什么**：署名守卫：扫描全框架页面开发者署名完整性，缺失即报可按需自动补回（禁止删除）
- **怎么调**：`py -3.14 tools/codex-scripts/five-dim.py cap signature_guard '<json>'`
- **失败三态**（本仓统一口径，不是这一位特有）：`denied` = 缺票，会点名`missing_scopes`；`needs_*` = 缺参/缺依赖，会带原因；`failed` = 真失败，回执带上游原话。**信封 `status=ok` ≠ 本体 `ok=true`。**

### `skill_watch`

- **域**：`system`（系统）
- **类型**：只读（不改状态、不出网） · **需参数**：否
- **要哪张票（静态）**：零作用域（空 payload 下不需要票）
- **必填载荷**：无必填（空载荷落到该位默认 op；位内更细的 op 参数见模块）
- **常见错误**：参数非法 → `user_error`
- **它做什么**：**技能观察器**（主人令 2026-10-11「使用技能在每次使用的时候都要注意技能的**变化和短板**来打磨进化」）：每次用技能留三笔 —— **用成没成（读数）· 它变了没（面漂移）· 它短板在哪（打磨点）**。① observe：cap/成败/耗时/错误类/被门拦 ⇒ 只追加落账；② snapshot+drift：把技能当下可控制面（op 表/参数/节点/版本）与上次快照比，变了报 surface_changed（对齐「节点消失=断连」，升级改名也算）；③ shortboards+advise：按读数排行短板（失败率/耗时 P90/缺依赖/被门拒），每条给**可执行的打磨点**。铁律：只追加 · 不许编（无观测就报无观测）· **每条建议必须挂它对应的读数**。op=observe/snapshot/shortboards/advise/drift
- **怎么调**：`py -3.14 tools/codex-scripts/five-dim.py cap skill_watch '<json>'`
- **失败三态**（本仓统一口径，不是这一位特有）：`denied` = 缺票，会点名`missing_scopes`；`needs_*` = 缺参/缺依赖，会带原因；`failed` = 真失败，回执带上游原话。**信封 `status=ok` ≠ 本体 `ok=true`。**

### `slim_profile`

- **域**：`system`（系统）
- **类型**：只读（不改状态、不出网） · **需参数**：否
- **要哪张票（静态）**：零作用域（空 payload 下不需要票）
- **必填载荷**：无必填（空载荷落到该位默认 op；位内更细的 op 参数见模块）
- **常见错误**：参数非法 → `user_error`
- **它做什么**：瘦身画像（simslim 架构蒸馏）：**命名类别 + profile + 三档闸 + 裁后复核**——`plan` 只读量出按类别的可回收体积（同 disk-plan）；`cut` **必须 confirm=true** 且**只搬不删**（.trash/slim-<ts>/<类别>/，可原路取回）；`verify` 裁后复核（保留名单不许进垃圾桶 · 目标不许搬空 · 只裁 profile 内的类）；前后两个数现量。profile: dev 最保守 / safe 常用 / deep 最激进。op=plan/cut/verify/profiles/where
- **怎么调**：`py -3.14 tools/codex-scripts/five-dim.py cap slim_profile '<json>'`
- **失败三态**（本仓统一口径，不是这一位特有）：`denied` = 缺票，会点名`missing_scopes`；`needs_*` = 缺参/缺依赖，会带原因；`failed` = 真失败，回执带上游原话。**信封 `status=ok` ≠ 本体 `ok=true`。**

### `spend_guard`

- **域**：`system`（系统）
- **类型**：只读（不改状态、不出网） · **需参数**：否
- **要哪张票（静态）**：零作用域（空 payload 下不需要票）
- **必填载荷**：无必填（空载荷落到该位默认 op；位内更细的 op 参数见模块）
- **常见错误**：参数非法 → `user_error`
- **它做什么**：花费守卫（paperclip 成本治理蒸馏）：**按维度追踪调用与 token + 阈值三态判定**——`ledger` 从 key_gateway 真账按日/按源聚合（token 记多少报多少，**免费通道 0 就报 0**，不按价目表脑补）· `policy` 阈值策略（数据文件，主人可改；缺则如实标"默认"）· `verdict` 三态 ok/warn/stop（**只判定不拦**——拦仍走现有门；账读不到 ⇒ unknown ≠ ok）。op=ledger/policy/verdict/where
- **怎么调**：`py -3.14 tools/codex-scripts/five-dim.py cap spend_guard '<json>'`
- **失败三态**（本仓统一口径，不是这一位特有）：`denied` = 缺票，会点名`missing_scopes`；`needs_*` = 缺参/缺依赖，会带原因；`failed` = 真失败，回执带上游原话。**信封 `status=ok` ≠ 本体 `ok=true`。**

### `surface_bind`

- **域**：`system`（系统）
- **类型**：只读（不改状态、不出网） · **需参数**：否
- **要哪张票（静态）**：零作用域（空 payload 下不需要票）
- **必填载荷**：无必填（空载荷落到该位默认 op；位内更细的 op 参数见模块）
- **常见错误**：参数非法 → `user_error`
- **它做什么**：通用「可控制面」绑定器（主人令 2026-09-27：「其他工具全部都要可控按键一个不漏的绑定好」）：**让每个工具自己报出可控制键**（ffmpeg -filters/-encoders/-formats… · git help -a · genoffice --help · freebuff --help · python 每个标准库模块一把键 · blender 走 bpy 枚举）→ 落清单 state/surfaces/<工具>.json → 绑到该工具的触手；**重扫对比：新键并入、消失的键=断连**。安全写法：探针**生成脚本 + 字面量 cmd 执行**（不把 exe 变量当程序名 —— 钩子拦过）。op=probe/sweep/keys/verify
- **怎么调**：`py -3.14 tools/codex-scripts/five-dim.py cap surface_bind '<json>'`
- **失败三态**（本仓统一口径，不是这一位特有）：`denied` = 缺票，会点名`missing_scopes`；`needs_*` = 缺参/缺依赖，会带原因；`failed` = 真失败，回执带上游原话。**信封 `status=ok` ≠ 本体 `ok=true`。**

### `task_manager`

- **域**：`system`（系统）
- **类型**：只读（不改状态、不出网） · **需参数**：否
- **要哪张票（静态）**：零作用域（空 payload 下不需要票）
- **必填载荷**：无必填（空载荷落到该位默认 op；位内更细的 op 参数见模块）
- **常见错误**：参数非法 → `user_error`
- **它做什么**：任务管理器（主人令 2026-09-27）：一屏看全「任务 / 归属 / 内存占用 / CPU / 端口 / 进程ID」；psutil 读**真进程**（CPU 需两次采样：process_iter 的 info 是首次缓存，第二遍必须直接再调）；归属按**进程名优先**认（血账：只看命令行会把 chrome 误认成框架服务）；**网络列是"占着的端口"不是流量**（本机取不到 per-process 流量，不编）；stop 过 process_execute 门；page 生成我们视觉语言的静态页（SVG 图标·无 emoji·深色+青橙）。op=list/stop/page
- **怎么调**：`py -3.14 tools/codex-scripts/five-dim.py cap task_manager '<json>'`
- **失败三态**（本仓统一口径，不是这一位特有）：`denied` = 缺票，会点名`missing_scopes`；`needs_*` = 缺参/缺依赖，会带原因；`failed` = 真失败，回执带上游原话。**信封 `status=ok` ≠ 本体 `ok=true`。**

### `tentacle_arm`

- **域**：`system`（系统）
- **类型**：只读（不改状态、不出网） · **需参数**：否
- **要哪张票（静态）**：零作用域（空 payload 下不需要票）
- **必填载荷**：无必填（空载荷落到该位默认 op；位内更细的 op 参数见模块）
- **常见错误**：参数非法 → `user_error`
- **它做什么**：**触手操控臂**（主人令 2026-10-19「你要以这些能力的思路来操控触手，本身触手就是我们的手，所以必须学会这样的操控精度」）：把 Omni-Arm 的五层精度模型套到能力位上 —— 关节 = 一次 (kind, op, payload)；`dof` = 该位在注册表登记的几个 op；`limits` **现算**（policy.evaluate 的作用域 ＋ preflight.is_side_effect 判出的处理器层闸），不手写；`reversible` 只读 op 才算可逆。op=status/limits/plan/where（纯读免门）· op=move 逐关节走 `run_task`，**票由那一位自己的门收**（本位不另加门、也不绕门），动完按 `expect` **量误差**（不把"调了"当"到了"）。冲击保护：缺票/缺必填参/读不出 op 一律**动手前**拒（fail-closed）
- **怎么调**：`py -3.14 tools/codex-scripts/five-dim.py cap tentacle_arm '<json>'`
- **失败三态**（本仓统一口径，不是这一位特有）：`denied` = 缺票，会点名`missing_scopes`；`needs_*` = 缺参/缺依赖，会带原因；`failed` = 真失败，回执带上游原话。**信封 `status=ok` ≠ 本体 `ok=true`。**

### `tentacle_bind`

- **域**：`system`（系统）
- **类型**：只读（不改状态、不出网） · **需参数**：否
- **要哪张票（静态）**：零作用域（空 payload 下不需要票）
- **必填载荷**：无必填（空载荷落到该位默认 op；位内更细的 op 参数见模块）
- **常见错误**：参数非法 → `user_error`
- **它做什么**：资产↔触手穿透式绑定（主人令 2026-09-26）：每个资产绑定到产生/维护它的触手；bind/unbind/auto/sweep 增删绑定，scan 全量体检（红点只剩「触手断连」一种：资产缺失或触手不在注册表），coverage 报穿透率，一切动作追加写 state/asset_bindings.jsonl 台账（只增不删）
- **怎么调**：`py -3.14 tools/codex-scripts/five-dim.py cap tentacle_bind '<json>'`
- **失败三态**（本仓统一口径，不是这一位特有）：`denied` = 缺票，会点名`missing_scopes`；`needs_*` = 缺参/缺依赖，会带原因；`failed` = 真失败，回执带上游原话。**信封 `status=ok` ≠ 本体 `ok=true`。**

### `tentacle_cognition`

- **域**：`system`（系统）
- **类型**：只读（不改状态、不出网） · **需参数**：否
- **要哪张票（静态）**：零作用域（空 payload 下不需要票）
- **必填载荷**：无必填（空载荷落到该位默认 op；位内更细的 op 参数见模块）
- **常见错误**：参数非法 → `user_error`
- **它做什么**：触手认知包（只读骨架）：任务上下文/角色边界/自检三问/不确定上报/操作留痕 + 五条零容忍红线
- **怎么调**：`py -3.14 tools/codex-scripts/five-dim.py cap tentacle_cognition '<json>'`
- **失败三态**（本仓统一口径，不是这一位特有）：`denied` = 缺票，会点名`missing_scopes`；`needs_*` = 缺参/缺依赖，会带原因；`failed` = 真失败，回执带上游原话。**信封 `status=ok` ≠ 本体 `ok=true`。**

### `theme_cap`

- **域**：`system`（系统）
- **类型**：**需授权**（会写盘 / 花钱 / 出网） · **需参数**：否
- **要哪张票（静态）**：零作用域（空 payload 下不需要票）
- **必填载荷**：无必填（空载荷落到该位默认 op；位内更细的 op 参数见模块）
- **常见错误**：参数非法 → `user_error`；依赖不在位 → `needs_dependency`；上游不给 → `needs_input` / `failed`（带上游原话）
- **它做什么**：**主题能力位**（蒸馏自 Omarchy 的 "colors.toml 主色 + 模板重生成全系统配置"）：**一份取值空间（[colors] + [dims]） ⇒ 四个界面 CSS 的主题块一起变**。op=list/show 看色源；check 判据（漂移 + 悬空引用 + 颜色尺寸各有人用）；render 预览（可 --outdir 落别处，**原件一字不动**）；discover 现读收录；apply 真写（先留 .bak）。**模板独立成件**（state/theme/templates/*.tpl），**块外一字不动**，没有标记块的文件跳过并点名。
- **怎么调**：`py -3.14 tools/codex-scripts/five-dim.py cap theme_cap '<json>'`
- **失败三态**（本仓统一口径，不是这一位特有）：`denied` = 缺票，会点名`missing_scopes`；`needs_*` = 缺参/缺依赖，会带原因；`failed` = 真失败，回执带上游原话。**信封 `status=ok` ≠ 本体 `ok=true`。**

### `trace_store`

- **域**：`system`（系统）
- **类型**：只读（不改状态、不出网） · **需参数**：否
- **要哪张票（静态）**：零作用域（空 payload 下不需要票）
- **必填载荷**：无必填（空载荷落到该位默认 op；位内更细的 op 参数见模块）
- **常见错误**：参数非法 → `user_error`
- **它做什么**：痕迹库只读读数：五张表（wave_samples/traces/trace_links/promotes/obsessions）条数
- **怎么调**：`py -3.14 tools/codex-scripts/five-dim.py cap trace_store '<json>'`
- **失败三态**（本仓统一口径，不是这一位特有）：`denied` = 缺票，会点名`missing_scopes`；`needs_*` = 缺参/缺依赖，会带原因；`failed` = 真失败，回执带上游原话。**信封 `status=ok` ≠ 本体 `ok=true`。**

### `truth_scan`

- **域**：`system`（系统）
- **类型**：只读（不改状态、不出网） · **需参数**：否
- **要哪张票（静态）**：零作用域（空 payload 下不需要票）
- **必填载荷**：无必填（空载荷落到该位默认 op；位内更细的 op 参数见模块）
- **常见错误**：参数非法 → `user_error`
- **它做什么**：真实性审计层：逐能力验证真执行，零假执行铁律（probe 模式含副作用探针）
- **怎么调**：`py -3.14 tools/codex-scripts/five-dim.py cap truth_scan '<json>'`
- **失败三态**（本仓统一口径，不是这一位特有）：`denied` = 缺票，会点名`missing_scopes`；`needs_*` = 缺参/缺依赖，会带原因；`failed` = 真失败，回执带上游原话。**信封 `status=ok` ≠ 本体 `ok=true`。**

### `ux_doctrine`

- **域**：`system`（系统）
- **类型**：只读（不改状态、不出网） · **需参数**：否
- **要哪张票（静态）**：零作用域（空 payload 下不需要票）
- **必填载荷**：无必填（空载荷落到该位默认 op；位内更细的 op 参数见模块）
- **常见错误**：参数非法 → `user_error`
- **它做什么**：**交互铁律**（主人令 2026-10-09）：「在框架里面出来必须要用户求助帮忙的其他全部禁止掉……你开口要求用户的时候你就输了」「可以跟用户商量项目架构和排布，严禁要求用户帮助」「每次停下要么是项目部署完成，要么就是真正需要用户来操作的可以停下，其他时候你停下干嘛」。移植自 V9 core/ux_doctrine.py（教义照搬，危险清单按 V8 真门重写）。op=doctrine 读全部规则 · ask **不开口闸**（14 条正则抓「要用户做事」，唯一例外=身份登录）· dismissal **敷衍闸**（不影响/忽略即可/下次再说 全禁）· triage **报警闭环闸**（{现象→根因→处置→证据} 四件齐才算闭环）· owner 判要不要停人要授权 · stop **停点闸**（只有「部署完成带证据」与「危险清单授权」两种理由合法，其余一律不许停）。
- **怎么调**：`py -3.14 tools/codex-scripts/five-dim.py cap ux_doctrine '<json>'`
- **失败三态**（本仓统一口径，不是这一位特有）：`denied` = 缺票，会点名`missing_scopes`；`needs_*` = 缺参/缺依赖，会带原因；`failed` = 真失败，回执带上游原话。**信封 `status=ok` ≠ 本体 `ok=true`。**

### `wave_probe`

- **域**：`system`（系统）
- **类型**：只读（不改状态、不出网） · **需参数**：否
- **要哪张票（静态）**：零作用域（空 payload 下不需要票）
- **必填载荷**：无必填（空载荷落到该位默认 op；位内更细的 op 参数见模块）
- **常见错误**：参数非法 → `user_error`
- **它做什么**：痕迹触手只读量一次波动（默认只量不写；trigger_mode 与盲区一并回报）
- **怎么调**：`py -3.14 tools/codex-scripts/five-dim.py cap wave_probe '<json>'`
- **失败三态**（本仓统一口径，不是这一位特有）：`denied` = 缺票，会点名`missing_scopes`；`needs_*` = 缺参/缺依赖，会带原因；`failed` = 真失败，回执带上游原话。**信封 `status=ok` ≠ 本体 `ok=true`。**

### `welcome`

- **域**：`system`（系统）
- **类型**：只读（不改状态、不出网） · **需参数**：否
- **要哪张票（静态）**：零作用域（空 payload 下不需要票）
- **必填载荷**：无必填（空载荷落到该位默认 op；位内更细的 op 参数见模块）
- **常见错误**：参数非法 → `user_error`
- **它做什么**：**启动欢迎语**（主人令 2026-10-10：「启动APP数字人的欢迎语，你来看看说什么，要有 GBT小土豆V8 和 开发者：自由的风，其他你来想要有未来感的语言」）。文字是**单一真源**（gbt_allinone/welcome.py 的 WELCOME；必含项由 check() 机械咬住）。三个 op：text 取全文+必含项判据 · audio 预生成音频的落点与状态 · boot 启动用**一次给全**（显示什么 + 播哪个文件）。🔴 音频**必须预生成**：本机 TTS 走 CPU，约 **150 倍慢于实时**（实测 2.36 秒用 327 秒）⇒ 启动时现造要等几十分钟；造一次缓存到盘，启动直接播；**没造就如实报**，界面退化成只显示文字 —— 不许静默、不许假装播了。只读零作用域。
- **怎么调**：`py -3.14 tools/codex-scripts/five-dim.py cap welcome '<json>'`
- **失败三态**（本仓统一口径，不是这一位特有）：`denied` = 缺票，会点名`missing_scopes`；`needs_*` = 缺参/缺依赖，会带原因；`failed` = 真失败，回执带上游原话。**信封 `status=ok` ≠ 本体 `ok=true`。**

---

返回 [能力总表](../03-capabilities.md)
