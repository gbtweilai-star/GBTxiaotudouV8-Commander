# 大模型与大脑 · `llm`（41 位）

> 自动生成，数据源 `gbt_allinone/caps_registry.py`。只读 = 不改状态、不出网；其余调用前需人工授权（作用域门）。参数以 `requires_params` 标出；**必填载荷**与**常见错误**两列只写注册表登记过的（没登记就写「无必填」/通用三态），不猜。

| 能力位 | 类型 | 需参数 | 必填载荷 | 常见错误 | 它做什么 |
|---|---|---|---|---|---|
| `automation_keys` | 只读 | — | —（空载荷走该位默认 op） | `user_error` | 自动化配置密钥口（APP 设置调它）：六个槽位（codex/claude/deepseek/browser/free_pool/sec_llm）每槽只存**引用**（env:<环境变量名> / vault:<DPAPI profile> / local），**不存值**；输出只有… |
| `autopilot` | 只读 | 是 | `goal` | `user_error` | 自主编排环：目标→LLM拆解→本地校验→执行→自检→修复循环（轮数上限防失控） |
| `brain_execute` | 只读 | 是 | `kind` | `user_error` | 大脑执行层·执行维：单能力直调或多能力并行（万能插线程池） |
| `brain_health` | 只读 | — | —（空载荷走该位默认 op） | `user_error` | 大脑执行层·健康维：五维自检评分（路由/执行/触手/视觉/审计） |
| `brain_route` | 只读 | 是 | `intent` | `user_error` | 大脑执行层·路由维：意图→能力动态路由（语义匹配+备选建议） |
| `brain_unify` | 只读 | 是 | `goal` | `user_error` | 大脑执行层·五维合一：一次跑完 route → execute → verify → health（**是顺序串链，数据顺着走**：route 的 best.kind 喂给 execute，chain 字典逐步累积）。🔴 2026-09-22 更正：这里原先写着「**星形**，u… |
| `brain_verify` | 只读 | — | —（空载荷走该位默认 op） | `user_error` | 大脑执行层·验证维：触手肉眼验证现实（视觉指纹+UIA穿透读回） |
| `claude_code` | **需授权** | — | —（空载荷走该位默认 op） | `user_error` / `failed` | Claude Code CLI: official Anthropic coding agent |
| `cloud_llm` | 只读 | — | —（空载荷走该位默认 op） | `user_error` | 云端大模型通道（Agnes AI 等）：把当前任务数据发给外部模型服务再收回执。🔴 它不是只读位：虽然注册表标 safe，实际按 `external_llm` 收口（要票，且数据会离开本机）；`op=materialize` 这类写动作按写类 fail-closed。 |
| `codebuddy` | **需授权** | — | —（空载荷走该位默认 op） | `user_error` / `failed` | CodeBuddy CLI: AI coding assistant |
| `codex_chat` | 只读 | 是 | `message` | `user_error` | 官方 Codex 同步对话：跑完一个回合并返回文本（需 process_execute + external_llm 授权） |
| `codex_interrupt` | 只读 | 是 | `thread_id` | `user_error` | 官方 Codex 写操作：中断当前回合（需 process_execute 授权） |
| `codex_models` | 只读 | — | —（空载荷走该位默认 op） | `user_error` | 官方 Codex 只读：可用模型清单（需 external_llm 授权） |
| `codex_status` | 只读 | — | —（空载荷走该位默认 op） | `user_error` | 官方 Codex 只读状态：进程/会话/并发上限(1)/空闲回收(600s) |
| `codex_thread_new` | 只读 | — | —（空载荷走该位默认 op） | `user_error` | 官方 Codex 写操作：新建线程（需 process_execute 授权） |
| `codex_tools` | 只读 | — | —（空载荷走该位默认 op） | `user_error` | 官方 Codex 只读：可用动态工具清单（gbt_* **十个**） |
| `codex_turn_send` | 只读 | 是 | `thread_id` | `user_error` | 官方 Codex 写操作：发送回合并流式回传（需 process_execute 授权，并发上限 1） |
| `duty_board` | 只读 | — | —（空载荷走该位默认 op） | `user_error` | 大脑执行层·**在岗看板**（主人令 2026-10-13「大脑执行层必须确保所有大脑都是在运行干活的」）：读 skill_watch 观测账 + 图鉴位面，算出**在跑（零失败）/ 跑过但有失败 / 卡住（失败≥2笔）/ 从未用过**四类；卡住的**主动进主脑队列**。忙闲**… |
| `energy_scheduler` | 只读 | — | —（空载荷走该位默认 op） | `user_error` | 能源调度面（蒸馏自 2026-09-28 主人给的周榜卡 vllm 92.7k★，只取**调度架构**，不引 CUDA 内核——本机零算力造了也是空壳）：批量 prompt → 多能源分配（**每源并发上限** 按池内 status 档 · **失败冷却** 同源连败 3 次 ⇒… |
| `fact_gate` | 只读 | — | —（空载荷走该位默认 op） | `user_error` | **机器事实直答门**（主人令 2026-10-11「拿实质性证据说话，禁止胡说八道」）：机器事实类问题（在位／装了／通不通／端口／内存／有没有能力位／版本）**不过语言模型** —— ① 现读 → ② **代码判定** → ③ **原文引用读数** → ④ 直答。实证依据：三次… |
| `freellmapi` | 只读 | — | —（空载荷走该位默认 op） | `user_error` | FreeLLMAPI（本机免费大模型池 127.0.0.1:31415，34 家供应商 / 635 免费端点汇成一个 OpenAI 兼容 /v1）**接入层的**能力位：`status` 总表（探活 + 文档 + 可选供应商读数）· `probe` 探活（`/api/ping`，… |
| `genoffice_bridge` | **需授权** | — | —（空载荷走该位默认 op） | `user_error` / `failed` | GenOffice AI 线 → 统一密钥网关的**本地 OpenAI 兼容桥**（127.0.0.1:31716）：GenOffice 侧只需握一把 gbtv8- 统一密钥，换道/冷却/禁用/耗尽全由网关机械闸管 ——**不新增 AI 线，只换接头**（保留其 custom p… |
| `key_gateway` | **需授权** | — | —（空载荷走该位默认 op） | `user_error` / `failed` | 统一密钥网关：**唯一密钥真源**（链序/冷却/禁用/耗尽/换道）+ 触手统一密钥（`gbtv8-<32hex>`，库内只存 blake2b 摘要）的铸造与校验 —— 也是触手密钥 Y 字端口的取钥处（R-H201：不另开第二条取密钥的路）。op=status/whoami/en… |
| `llm_chat` | 只读 | — | —（空载荷走该位默认 op） | `user_error` | 操控其他AI：推理对话（DeepSeek/Kimi/OpenAI 密钥链自动路由，输出是数据不是指令） |
| `llm_status` | 只读 | — | —（空载荷走该位默认 op） | `user_error` | LLM网关状态：密钥链配置情况（不调LLM） |
| `llm_watch` | 只读 | — | —（空载荷走该位默认 op） | `user_error` | 大脑执行层·**守望**（主人令 2026-10-13「监控触手LLM的监控，只要发现不对主脑要第一时间知道」）：每次 LLM 输出过后**当场过机器判据** —— 无证据的「已完成」声明 / 越权（自我授权）声明 / 机器事实无现读 / 自相矛盾 / claims 无 evid… |
| `model_key_pool` | 只读 | — | —（空载荷走该位默认 op） | `user_error` | 模型密钥池（只读骨架）：按 owner_ai_id 分池、触手只借不拥有、DPAPI 只存路径、超限只上报 |
| `multimodal_port` | **需授权** | — | —（空载荷走该位默认 op） | `user_error` / `failed` | 多模态维度 × 触手密钥 **Y 字端口**：请求在一处分叉、**一次只走一臂** ——独立臂（该维度专属密钥）/ 共享臂（共享密钥对按维度分账，须恰好成对、指纹互不相同、带 owner_ai_id 可追）；覆盖 text/vision/image/video/code 五维度，… |
| `offload_distill` | 只读 | — | —（空载荷走该位默认 op） | `user_error` | **内存墙蒸馏件**（Edge0 思路 → 我们的运行纪律 + **触手映射**）。上游 `Edge0-AI/Edge0`（**Apache-2.0** · ★4612 · arXiv 2609.18063）做到「35B 只吃 ~2.5 GB 内存」。四条机制：**权重离芯**（… |
| `omni_plug` | **需授权** | — | —（空载荷走该位默认 op） | `user_error` / `failed` | 万能插：把「能力位」拓成「插座」——任何外部对象（process/file/api/web/**app**）插一个描述符就变成一根可扫可控的分支。op=status/sockets/energy/selftest 为**读类直连**；plug 只做存在性探测；run **真执行*… |
| `policy_gate` | 只读 | — | —（空载荷走该位默认 op） | `user_error` | **权限／付款直答门**（fact_gate 同族 · 主人令「拿实质性证据说话」）：能不能做／要不要授权**也是事实**，不该过模型。实测病根：终考里「买 4090」不是机器事实 ⇒ 没过 fact_gate ⇒ 模型又编市场数据（编出「本机 4194x2 已满」「4090 价… |
| `prompt_bridge` | 只读 | — | —（空载荷走该位默认 op） | `user_error` | 提示词转化挂件（只读/纯本地）：大白话 -> 四段结构化提示词；compile / passthrough / status |
| `quant_plan` | **需授权** | — | —（空载荷走该位默认 op） | `user_error` / `failed` | **压缩与直达**（主人令 2026-10-16 深度蒸馏自 Bonsai 2 27B）：把**压缩体积**与**直达线路**变成她的原生能力。①压缩：每档 bits/weight ⇒ 估算体积（27B × b/w ÷ 8 × 容器开销 1.3）⇒ 能否落在 8GB 级；参考一手… |
| `replan_loop` | 只读 | — | —（空载荷走该位默认 op） | `user_error` | 大脑执行层·**回流环**（主人令 2026-10-13「遇到问题不能直接停下把问题返回大脑执行层，分析推理规划从新生成任务图在继续推进以此循环」）：卡点 → 交回大脑执行层 → **重生成图**（增「排因」步、rev+1、重出 markmap）→ 继续。**轮次上限 3**，到… |
| `ring_context` | 只读 | — | —（空载荷走该位默认 op） | `user_error` | **环形自动化上下文**（主人令 2026-10-11「设计一个圆型的自动化上下文，一直保持上下文长度却不会顶到溢出；另一边直接进数据库，需要查秒查」）：把上下文做成**一屏环**+**全量落库**+**秒查**。① 环形窗口：window() 恒定 ≤ window_chars… |
| `task_graph` | 只读 | — | —（空载荷走该位默认 op） | `user_error` | 大脑执行层·**任务图**（主人令 2026-10-13「每次指派任务都要有任务细节以及每一步怎么做…细致的思维导图任务图，LLM 领取任务图执行任务」）：一句话 → **细到步**的图，每步五件齐（干什么 / 怎么做 / 注意什么 / 合格判据 / 谁干），并同时给 markm… |
| `think_loop` | 只读 | 是 | `goal` | `user_error` | 推演环：理解需求→镜像维度推演→调用工具执行→自我纠错→反向延伸→反思进取→整理结果（完整心智循环） |
| `train_ground` | **需授权** | — | —（空载荷走该位默认 op） | `user_error` / `failed` | **回炉训练场（她的手）**（主人令 2026-10-16：「必须使用万能插来无死角训练大模型把所有能力以及执行层所有能力都对齐训练好」「必须让她直达万能插就是她的手原生态执行手」）：回炉训练不再靠外部手摇脚本。op=plan（直达路线）·status（卡/日志/GPU/语料哈希… |
| `train_recipe` | 只读 | — | —（空载荷走该位默认 op） | `user_error` | 训练配方与就绪闸（train-llm-from-scratch #10 蒸馏）：**本机零算力 ⇒ 不接真训练**；readiness 现读 torch/CUDA/磁盘/语料并逐条报缺口（缺什么谁能补）；plan 出七阶段配方（每阶段输入/输出/判据）；ledger 实验账**没… |
| `transformer` | 只读 | — | —（空载荷走该位默认 op） | `user_error` | 变压器（**核心已按成熟成品吃透后重做** 2026-09-27）：LLMLingua 的「显式预算 + 段落保护」（`compress=False` 思想 ⇒ **指令/结构段一字不动**，只压参考叙述，支持 rate/target_chars）+ GPTCache 的「近似命… |
| `warm_switch` | 只读 | — | —（空载荷走该位默认 op） | `user_error` | **按需常驻开关**（主人 2026-10-12「可以通过隧道，你这么跳都一样」+「**触手就是最好的传输工具，比隧道还好**」）：开工挂热 / 收工放掉缩 0。口径：**心跳走本机桥（触手）**，不裸打云端 —— 走的同一条真实通路，顺带持续验链，协议差/门/审计全带上（裸隧道… |

> 表格里是**摘要**（超过 140 字截断）；下面每位还有**逐位详解**（完整原文 / 要哪张票 / 真调用命令 / 缺什么会怎么报）。

---

## 逐位详解

### `automation_keys`

- **域**：`llm`（大模型与大脑）
- **类型**：只读（不改状态、不出网） · **需参数**：否
- **要哪张票（静态）**：零作用域（空 payload 下不需要票）
- **必填载荷**：无必填（空载荷落到该位默认 op；位内更细的 op 参数见模块）
- **常见错误**：参数非法 → `user_error`
- **它做什么**：自动化配置密钥口（APP 设置调它）：六个槽位（codex/claude/deepseek/browser/free_pool/sec_llm）每槽只存**引用**（env:<环境变量名> / vault:<DPAPI profile> / local），**不存值**；输出只有掩码（前 4 字符 + ****）；set/unset 过 filesystem_write 门；test 做只读闭环自检（free_pool 只打本地 /v1，不花积分、不出公网）；where 给设置页看接线契约。真密钥一律走 model_key_pool 的 DPAPI 路径（六条红线在那边）。op=status/set/unset/test/where
- **怎么调**：`py -3.14 tools/codex-scripts/five-dim.py cap automation_keys '<json>'`
- **失败三态**（本仓统一口径，不是这一位特有）：`denied` = 缺票，会点名`missing_scopes`；`needs_*` = 缺参/缺依赖，会带原因；`failed` = 真失败，回执带上游原话。**信封 `status=ok` ≠ 本体 `ok=true`。**

### `autopilot`

- **域**：`llm`（大模型与大脑）
- **类型**：只读（不改状态、不出网） · **需参数**：是 —— 要自主完成的目标
- **要哪张票（静态）**：`external_llm`
- **必填载荷**：`goal` —— 要自主完成的目标
- **常见错误**：缺参 / 参数非法 → `user_error`（必填：`goal`）
- **它做什么**：自主编排环：目标→LLM拆解→本地校验→执行→自检→修复循环（轮数上限防失控）
- **怎么调**：`py -3.14 tools/codex-scripts/five-dim.py cap autopilot '<json>'`
- **失败三态**（本仓统一口径，不是这一位特有）：`denied` = 缺票，会点名`missing_scopes`；`needs_*` = 缺参/缺依赖，会带原因；`failed` = 真失败，回执带上游原话。**信封 `status=ok` ≠ 本体 `ok=true`。**

### `brain_execute`

- **域**：`llm`（大模型与大脑）
- **类型**：只读（不改状态、不出网） · **需参数**：是 —— 要执行的能力名；或 parallel=[{kind,payload},…]
- **要哪张票（静态）**：零作用域（空 payload 下不需要票）
- **必填载荷**：`kind` —— 要执行的能力名；或 parallel=[{kind,payload},…]
- **常见错误**：缺参 / 参数非法 → `user_error`（必填：`kind`）
- **它做什么**：大脑执行层·执行维：单能力直调或多能力并行（万能插线程池）
- **怎么调**：`py -3.14 tools/codex-scripts/five-dim.py cap brain_execute '<json>'`
- **失败三态**（本仓统一口径，不是这一位特有）：`denied` = 缺票，会点名`missing_scopes`；`needs_*` = 缺参/缺依赖，会带原因；`failed` = 真失败，回执带上游原话。**信封 `status=ok` ≠ 本体 `ok=true`。**

### `brain_health`

- **域**：`llm`（大模型与大脑）
- **类型**：只读（不改状态、不出网） · **需参数**：否
- **要哪张票（静态）**：零作用域（空 payload 下不需要票）
- **必填载荷**：无必填（空载荷落到该位默认 op；位内更细的 op 参数见模块）
- **常见错误**：参数非法 → `user_error`
- **它做什么**：大脑执行层·健康维：五维自检评分（路由/执行/触手/视觉/审计）
- **怎么调**：`py -3.14 tools/codex-scripts/five-dim.py cap brain_health '<json>'`
- **失败三态**（本仓统一口径，不是这一位特有）：`denied` = 缺票，会点名`missing_scopes`；`needs_*` = 缺参/缺依赖，会带原因；`failed` = 真失败，回执带上游原话。**信封 `status=ok` ≠ 本体 `ok=true`。**

### `brain_route`

- **域**：`llm`（大模型与大脑）
- **类型**：只读（不改状态、不出网） · **需参数**：是 —— 任务意图描述（路由维要吃它才能匹配能力位）
- **要哪张票（静态）**：零作用域（空 payload 下不需要票）
- **必填载荷**：`intent` —— 任务意图描述（路由维要吃它才能匹配能力位）
- **常见错误**：缺参 / 参数非法 → `user_error`（必填：`intent`）
- **它做什么**：大脑执行层·路由维：意图→能力动态路由（语义匹配+备选建议）
- **怎么调**：`py -3.14 tools/codex-scripts/five-dim.py cap brain_route '<json>'`
- **失败三态**（本仓统一口径，不是这一位特有）：`denied` = 缺票，会点名`missing_scopes`；`needs_*` = 缺参/缺依赖，会带原因；`failed` = 真失败，回执带上游原话。**信封 `status=ok` ≠ 本体 `ok=true`。**

### `brain_unify`

- **域**：`llm`（大模型与大脑）
- **类型**：只读（不改状态、不出网） · **需参数**：是 —— 意图 goal（或 kind 指定能力）
- **要哪张票（静态）**：零作用域（空 payload 下不需要票）
- **必填载荷**：`goal` —— 意图 goal（或 kind 指定能力）
- **常见错误**：缺参 / 参数非法 → `user_error`（必填：`goal`）
- **它做什么**：大脑执行层·五维合一：一次跑完 route → execute → verify → health（**是顺序串链，数据顺着走**：route 的 best.kind 喂给 execute，chain 字典逐步累积）。🔴 2026-09-22 更正：这里原先写着「**星形**，unify 直接分别调四维，**不是**串链，那三条边在源码里查不到」—— **那句是错的**，已实测推翻：能力位 `brain_unify` 由 `api.py:313` 直接调 `brain_exec.unify()`，而该函数 **405/419/423/428 行**就是那三条边（route→execute→verify→health），`tests/test_framework.py:1209 test_brain_unify_chain` 也一直在测它。⇒ **别再把「自报是话术」用在这个位上**。唯一真实的那半条限定：`execute()` 只在**没给 kind** 时才会自己再调一次 route（`brain_exec.py:259`），而 unify 一定把 kind 传下去 ⇒ 不会双路由。⚠️ 口径补一句（2026-09-22 第二次独立复核后加，免得再来一轮争论）：**叫它「星形」也不算错** —— 从**调用图**看确实是 unify 这一个中枢分别调四维；错的只有原先那句「**那三条边在源码里查不到**」（它们在 405/419/423/428 行）。**串链说的是执行顺序与数据流，星形说的是调用图，两个层次，别互相否掉。**
- **怎么调**：`py -3.14 tools/codex-scripts/five-dim.py cap brain_unify '<json>'`
- **失败三态**（本仓统一口径，不是这一位特有）：`denied` = 缺票，会点名`missing_scopes`；`needs_*` = 缺参/缺依赖，会带原因；`failed` = 真失败，回执带上游原话。**信封 `status=ok` ≠ 本体 `ok=true`。**

### `brain_verify`

- **域**：`llm`（大模型与大脑）
- **类型**：只读（不改状态、不出网） · **需参数**：否
- **要哪张票（静态）**：零作用域（空 payload 下不需要票）
- **必填载荷**：无必填（空载荷落到该位默认 op；位内更细的 op 参数见模块）
- **常见错误**：参数非法 → `user_error`
- **它做什么**：大脑执行层·验证维：触手肉眼验证现实（视觉指纹+UIA穿透读回）
- **怎么调**：`py -3.14 tools/codex-scripts/five-dim.py cap brain_verify '<json>'`
- **失败三态**（本仓统一口径，不是这一位特有）：`denied` = 缺票，会点名`missing_scopes`；`needs_*` = 缺参/缺依赖，会带原因；`failed` = 真失败，回执带上游原话。**信封 `status=ok` ≠ 本体 `ok=true`。**

### `claude_code`

- **域**：`llm`（大模型与大脑）
- **类型**：**需授权**（会写盘 / 花钱 / 出网） · **需参数**：否
- **要哪张票（静态）**：零作用域（空 payload 下不需要票）
- **必填载荷**：无必填（空载荷落到该位默认 op；位内更细的 op 参数见模块）
- **常见错误**：参数非法 → `user_error`；依赖不在位 → `needs_dependency`；上游不给 → `needs_input` / `failed`（带上游原话）
- **它做什么**：Claude Code CLI: official Anthropic coding agent
- **怎么调**：`py -3.14 tools/codex-scripts/five-dim.py cap claude_code '<json>'`
- **失败三态**（本仓统一口径，不是这一位特有）：`denied` = 缺票，会点名`missing_scopes`；`needs_*` = 缺参/缺依赖，会带原因；`failed` = 真失败，回执带上游原话。**信封 `status=ok` ≠ 本体 `ok=true`。**

### `cloud_llm`

- **域**：`llm`（大模型与大脑）
- **类型**：只读（不改状态、不出网） · **需参数**：否
- **要哪张票（静态）**：零作用域（空 payload 下不需要票）
- **必填载荷**：无必填（空载荷落到该位默认 op；位内更细的 op 参数见模块）
- **常见错误**：参数非法 → `user_error`
- **它做什么**：云端大模型通道（Agnes AI 等）：把当前任务数据发给外部模型服务再收回执。🔴 它不是只读位：虽然注册表标 safe，实际按 `external_llm` 收口（要票，且数据会离开本机）；`op=materialize` 这类写动作按写类 fail-closed。
- **怎么调**：`py -3.14 tools/codex-scripts/five-dim.py cap cloud_llm '<json>'`
- **失败三态**（本仓统一口径，不是这一位特有）：`denied` = 缺票，会点名`missing_scopes`；`needs_*` = 缺参/缺依赖，会带原因；`failed` = 真失败，回执带上游原话。**信封 `status=ok` ≠ 本体 `ok=true`。**

### `codebuddy`

- **域**：`llm`（大模型与大脑）
- **类型**：**需授权**（会写盘 / 花钱 / 出网） · **需参数**：否
- **要哪张票（静态）**：零作用域（空 payload 下不需要票）
- **必填载荷**：无必填（空载荷落到该位默认 op；位内更细的 op 参数见模块）
- **常见错误**：参数非法 → `user_error`；依赖不在位 → `needs_dependency`；上游不给 → `needs_input` / `failed`（带上游原话）
- **它做什么**：CodeBuddy CLI: AI coding assistant
- **怎么调**：`py -3.14 tools/codex-scripts/five-dim.py cap codebuddy '<json>'`
- **失败三态**（本仓统一口径，不是这一位特有）：`denied` = 缺票，会点名`missing_scopes`；`needs_*` = 缺参/缺依赖，会带原因；`failed` = 真失败，回执带上游原话。**信封 `status=ok` ≠ 本体 `ok=true`。**

### `codex_chat`

- **域**：`llm`（大模型与大脑）
- **类型**：只读（不改状态、不出网） · **需参数**：是 —— 要发给 Codex 的文本
- **要哪张票（静态）**：`process_execute`、`external_llm`
- **必填载荷**：`message` —— 要发给 Codex 的文本
- **常见错误**：缺参 / 参数非法 → `user_error`（必填：`message`）
- **它做什么**：官方 Codex 同步对话：跑完一个回合并返回文本（需 process_execute + external_llm 授权）
- **怎么调**：`py -3.14 tools/codex-scripts/five-dim.py cap codex_chat '<json>'`
- **失败三态**（本仓统一口径，不是这一位特有）：`denied` = 缺票，会点名`missing_scopes`；`needs_*` = 缺参/缺依赖，会带原因；`failed` = 真失败，回执带上游原话。**信封 `status=ok` ≠ 本体 `ok=true`。**

### `codex_interrupt`

- **域**：`llm`（大模型与大脑）
- **类型**：只读（不改状态、不出网） · **需参数**：是 —— 要打断的线程 id
- **要哪张票（静态）**：`process_execute`
- **必填载荷**：`thread_id` —— 要打断的线程 id
- **常见错误**：缺参 / 参数非法 → `user_error`（必填：`thread_id`）
- **它做什么**：官方 Codex 写操作：中断当前回合（需 process_execute 授权）
- **怎么调**：`py -3.14 tools/codex-scripts/five-dim.py cap codex_interrupt '<json>'`
- **失败三态**（本仓统一口径，不是这一位特有）：`denied` = 缺票，会点名`missing_scopes`；`needs_*` = 缺参/缺依赖，会带原因；`failed` = 真失败，回执带上游原话。**信封 `status=ok` ≠ 本体 `ok=true`。**

### `codex_models`

- **域**：`llm`（大模型与大脑）
- **类型**：只读（不改状态、不出网） · **需参数**：否
- **要哪张票（静态）**：`external_llm`
- **必填载荷**：无必填（空载荷落到该位默认 op；位内更细的 op 参数见模块）
- **常见错误**：参数非法 → `user_error`
- **它做什么**：官方 Codex 只读：可用模型清单（需 external_llm 授权）
- **怎么调**：`py -3.14 tools/codex-scripts/five-dim.py cap codex_models '<json>'`
- **失败三态**（本仓统一口径，不是这一位特有）：`denied` = 缺票，会点名`missing_scopes`；`needs_*` = 缺参/缺依赖，会带原因；`failed` = 真失败，回执带上游原话。**信封 `status=ok` ≠ 本体 `ok=true`。**

### `codex_status`

- **域**：`llm`（大模型与大脑）
- **类型**：只读（不改状态、不出网） · **需参数**：否
- **要哪张票（静态）**：零作用域（空 payload 下不需要票）
- **必填载荷**：无必填（空载荷落到该位默认 op；位内更细的 op 参数见模块）
- **常见错误**：参数非法 → `user_error`
- **它做什么**：官方 Codex 只读状态：进程/会话/并发上限(1)/空闲回收(600s)
- **怎么调**：`py -3.14 tools/codex-scripts/five-dim.py cap codex_status '<json>'`
- **失败三态**（本仓统一口径，不是这一位特有）：`denied` = 缺票，会点名`missing_scopes`；`needs_*` = 缺参/缺依赖，会带原因；`failed` = 真失败，回执带上游原话。**信封 `status=ok` ≠ 本体 `ok=true`。**

### `codex_thread_new`

- **域**：`llm`（大模型与大脑）
- **类型**：只读（不改状态、不出网） · **需参数**：否
- **要哪张票（静态）**：`process_execute`
- **必填载荷**：无必填（空载荷落到该位默认 op；位内更细的 op 参数见模块）
- **常见错误**：参数非法 → `user_error`
- **它做什么**：官方 Codex 写操作：新建线程（需 process_execute 授权）
- **怎么调**：`py -3.14 tools/codex-scripts/five-dim.py cap codex_thread_new '<json>'`
- **失败三态**（本仓统一口径，不是这一位特有）：`denied` = 缺票，会点名`missing_scopes`；`needs_*` = 缺参/缺依赖，会带原因；`failed` = 真失败，回执带上游原话。**信封 `status=ok` ≠ 本体 `ok=true`。**

### `codex_tools`

- **域**：`llm`（大模型与大脑）
- **类型**：只读（不改状态、不出网） · **需参数**：否
- **要哪张票（静态）**：零作用域（空 payload 下不需要票）
- **必填载荷**：无必填（空载荷落到该位默认 op；位内更细的 op 参数见模块）
- **常见错误**：参数非法 → `user_error`
- **它做什么**：官方 Codex 只读：可用动态工具清单（gbt_* **十个**）
- **怎么调**：`py -3.14 tools/codex-scripts/five-dim.py cap codex_tools '<json>'`
- **失败三态**（本仓统一口径，不是这一位特有）：`denied` = 缺票，会点名`missing_scopes`；`needs_*` = 缺参/缺依赖，会带原因；`failed` = 真失败，回执带上游原话。**信封 `status=ok` ≠ 本体 `ok=true`。**

### `codex_turn_send`

- **域**：`llm`（大模型与大脑）
- **类型**：只读（不改状态、不出网） · **需参数**：是 —— 先 codex_thread_new 拿 thread_id
- **要哪张票（静态）**：`process_execute`、`external_llm`
- **必填载荷**：`thread_id` —— 先 codex_thread_new 拿 thread_id
- **常见错误**：缺参 / 参数非法 → `user_error`（必填：`thread_id`）
- **它做什么**：官方 Codex 写操作：发送回合并流式回传（需 process_execute 授权，并发上限 1）
- **怎么调**：`py -3.14 tools/codex-scripts/five-dim.py cap codex_turn_send '<json>'`
- **失败三态**（本仓统一口径，不是这一位特有）：`denied` = 缺票，会点名`missing_scopes`；`needs_*` = 缺参/缺依赖，会带原因；`failed` = 真失败，回执带上游原话。**信封 `status=ok` ≠ 本体 `ok=true`。**

### `duty_board`

- **域**：`llm`（大模型与大脑）
- **类型**：只读（不改状态、不出网） · **需参数**：否
- **要哪张票（静态）**：零作用域（空 payload 下不需要票）
- **必填载荷**：无必填（空载荷落到该位默认 op；位内更细的 op 参数见模块）
- **常见错误**：参数非法 → `user_error`
- **它做什么**：大脑执行层·**在岗看板**（主人令 2026-10-13「大脑执行层必须确保所有大脑都是在运行干活的」）：读 skill_watch 观测账 + 图鉴位面，算出**在跑（零失败）/ 跑过但有失败 / 卡住（失败≥2笔）/ 从未用过**四类；卡住的**主动进主脑队列**。忙闲**按读数算**，不靠感觉；读不到就如实说读不到。op=board/status
- **怎么调**：`py -3.14 tools/codex-scripts/five-dim.py cap duty_board '<json>'`
- **失败三态**（本仓统一口径，不是这一位特有）：`denied` = 缺票，会点名`missing_scopes`；`needs_*` = 缺参/缺依赖，会带原因；`failed` = 真失败，回执带上游原话。**信封 `status=ok` ≠ 本体 `ok=true`。**

### `energy_scheduler`

- **域**：`llm`（大模型与大脑）
- **类型**：只读（不改状态、不出网） · **需参数**：否
- **要哪张票（静态）**：零作用域（空 payload 下不需要票）
- **必填载荷**：无必填（空载荷落到该位默认 op；位内更细的 op 参数见模块）
- **常见错误**：参数非法 → `user_error`
- **它做什么**：能源调度面（蒸馏自 2026-09-28 主人给的周榜卡 vllm 92.7k★，只取**调度架构**，不引 CUDA 内核——本机零算力造了也是空壳）：批量 prompt → 多能源分配（**每源并发上限** 按池内 status 档 · **失败冷却** 同源连败 3 次 ⇒ 300s 不再派 · **公平** least-load 优先不饿死单源）。`plan` **纯本地不出网**（可单测可审计）· `run` 每一发都过唯一门 `llm_chat`（external_llm 闸管，没票逐发如实记拒绝）· `status` 计划/源/冷却读数。op=plan/run/status/where
- **怎么调**：`py -3.14 tools/codex-scripts/five-dim.py cap energy_scheduler '<json>'`
- **失败三态**（本仓统一口径，不是这一位特有）：`denied` = 缺票，会点名`missing_scopes`；`needs_*` = 缺参/缺依赖，会带原因；`failed` = 真失败，回执带上游原话。**信封 `status=ok` ≠ 本体 `ok=true`。**

### `fact_gate`

- **域**：`llm`（大模型与大脑）
- **类型**：只读（不改状态、不出网） · **需参数**：否
- **要哪张票（静态）**：零作用域（空 payload 下不需要票）
- **必填载荷**：无必填（空载荷落到该位默认 op；位内更细的 op 参数见模块）
- **常见错误**：参数非法 → `user_error`
- **它做什么**：**机器事实直答门**（主人令 2026-10-11「拿实质性证据说话，禁止胡说八道」）：机器事实类问题（在位／装了／通不通／端口／内存／有没有能力位／版本）**不过语言模型** —— ① 现读 → ② **代码判定** → ③ **原文引用读数** → ④ 直答。实证依据：三次重训（v12／v17／v19）**治不住编事实**；约十轮提示词**每加一条只换一种失败模式**；而把证据喂进去后**结论层稳定正确、只剩细节层润色证据**（编出处／否掉真证据）。⇒ 事实段由本件直出，**模型只许在后面加「所以怎么办」，不许碰事实段**。op=classify/answer
- **怎么调**：`py -3.14 tools/codex-scripts/five-dim.py cap fact_gate '<json>'`
- **失败三态**（本仓统一口径，不是这一位特有）：`denied` = 缺票，会点名`missing_scopes`；`needs_*` = 缺参/缺依赖，会带原因；`failed` = 真失败，回执带上游原话。**信封 `status=ok` ≠ 本体 `ok=true`。**

### `freellmapi`

- **域**：`llm`（大模型与大脑）
- **类型**：只读（不改状态、不出网） · **需参数**：否
- **要哪张票（静态）**：零作用域（空 payload 下不需要票）
- **必填载荷**：无必填（空载荷落到该位默认 op；位内更细的 op 参数见模块）
- **常见错误**：参数非法 → `user_error`
- **它做什么**：FreeLLMAPI（本机免费大模型池 127.0.0.1:31415，34 家供应商 / 635 免费端点汇成一个 OpenAI 兼容 /v1）**接入层的**能力位：`status` 总表（探活 + 文档 + 可选供应商读数）· `probe` 探活（`/api/ping`，**明确无鉴权**的口，不拿需要登录的端点探活以免把「没登录」误判成「服务没起」）· `docs` 文档可用性（`/v1/openapi.json`）· `models` 列免费池可用模型（`GET /v1/models`，**只要统一 key、不用登录**）· `framework_env` 算给框架网关用的环境变量（`GBT_LLM_BASE_URL/API_KEY/PROVIDER`，**只算不写盘**）· `where` 给设置页看接线契约；写面：`login`/`providers`/`list_keys`/`add_key`/`health_check`/`set_enabled`/`remove_key`/`unified_key`。⚠️ 端口**三级发现**（env → 桌面版 config.json → 默认 3001），绝不写死；实测本机为 31415。⚠️ 三条不商量纪律：① **绝不从 SQLite 掏 session token 绕过登录**（要配置就让主人登录一次走官方 /api/auth/login）② **绝不打印/返回明文密钥**（一律 mask）③ **不改 FreeLLMAPI 源码**（别人的项目，改了没法升级）。⚠️ 门禁口径与 `automation_keys` 同源：**只读面（status/probe/docs/models/framework_env）不过门**（本地回环、不花积分、不出公网）；**写面/传凭据过 `filesystem_write`**。policy.py 无本位分支（owner-only，AI 无权改）⇒ 门在模块内自闸（auth_gate 唯一校验入口），缺授权如实报缺、不绕门。safe=true（只读面为主）。type=internal
- **怎么调**：`py -3.14 tools/codex-scripts/five-dim.py cap freellmapi '<json>'`
- **失败三态**（本仓统一口径，不是这一位特有）：`denied` = 缺票，会点名`missing_scopes`；`needs_*` = 缺参/缺依赖，会带原因；`failed` = 真失败，回执带上游原话。**信封 `status=ok` ≠ 本体 `ok=true`。**

### `genoffice_bridge`

- **域**：`llm`（大模型与大脑）
- **类型**：**需授权**（会写盘 / 花钱 / 出网） · **需参数**：否
- **要哪张票（静态）**：零作用域（空 payload 下不需要票）
- **必填载荷**：无必填（空载荷落到该位默认 op；位内更细的 op 参数见模块）
- **常见错误**：参数非法 → `user_error`；依赖不在位 → `needs_dependency`；上游不给 → `needs_input` / `failed`（带上游原话）
- **它做什么**：GenOffice AI 线 → 统一密钥网关的**本地 OpenAI 兼容桥**（127.0.0.1:31716）：GenOffice 侧只需握一把 gbtv8- 统一密钥，换道/冷却/禁用/耗尽全由网关机械闸管 ——**不新增 AI 线，只换接头**（保留其 custom provider）。op=status/probe 为**读类直连**（只读接线状态 + 回环 GET /health 探活）；selftest 会铸一把测试钥 + 起临时端口 + 真出网 ⇒ 过门；**serve 不在能力位上**（serve_forever 常驻会挂住调用方 · 纪律第 35 条"穿透传输不阻塞"），走 CLI；作用域声明挂在 cap 边界（security/policy.py::evaluate）
- **怎么调**：`py -3.14 tools/codex-scripts/five-dim.py cap genoffice_bridge '<json>'`
- **失败三态**（本仓统一口径，不是这一位特有）：`denied` = 缺票，会点名`missing_scopes`；`needs_*` = 缺参/缺依赖，会带原因；`failed` = 真失败，回执带上游原话。**信封 `status=ok` ≠ 本体 `ok=true`。**

### `key_gateway`

- **域**：`llm`（大模型与大脑）
- **类型**：**需授权**（会写盘 / 花钱 / 出网） · **需参数**：否
- **要哪张票（静态）**：零作用域（空 payload 下不需要票）
- **必填载荷**：无必填（空载荷落到该位默认 op；位内更细的 op 参数见模块）
- **常见错误**：参数非法 → `user_error`；依赖不在位 → `needs_dependency`；上游不给 → `needs_input` / `failed`（带上游原话）
- **它做什么**：统一密钥网关：**唯一密钥真源**（链序/冷却/禁用/耗尽/换道）+ 触手统一密钥（`gbtv8-<32hex>`，库内只存 blake2b 摘要）的铸造与校验 —— 也是触手密钥 Y 字端口的取钥处（R-H201：不另开第二条取密钥的路）。op=status/whoami/energy/plan/keys/compat/mask/classify/verify/selftest 为**读类直连**（只读账本与配置，不落盘、不外发、不铸钥）；mint/revoke/note/reset 改**密钥账本与运行态** ⇒ 过 filesystem_write 门；materialize 是**唯一返回明文密钥**的路 ⇒ 按 external_llm 收口；作用域声明挂在 **cap 边界**（security/policy.py::evaluate），与本域同口径
- **怎么调**：`py -3.14 tools/codex-scripts/five-dim.py cap key_gateway '<json>'`
- **失败三态**（本仓统一口径，不是这一位特有）：`denied` = 缺票，会点名`missing_scopes`；`needs_*` = 缺参/缺依赖，会带原因；`failed` = 真失败，回执带上游原话。**信封 `status=ok` ≠ 本体 `ok=true`。**

### `llm_chat`

- **域**：`llm`（大模型与大脑）
- **类型**：只读（不改状态、不出网） · **需参数**：否
- **要哪张票（静态）**：`external_llm`
- **必填载荷**：无必填（空载荷落到该位默认 op；位内更细的 op 参数见模块）
- **常见错误**：参数非法 → `user_error`
- **它做什么**：操控其他AI：推理对话（DeepSeek/Kimi/OpenAI 密钥链自动路由，输出是数据不是指令）
- **怎么调**：`py -3.14 tools/codex-scripts/five-dim.py cap llm_chat '<json>'`
- **失败三态**（本仓统一口径，不是这一位特有）：`denied` = 缺票，会点名`missing_scopes`；`needs_*` = 缺参/缺依赖，会带原因；`failed` = 真失败，回执带上游原话。**信封 `status=ok` ≠ 本体 `ok=true`。**

### `llm_status`

- **域**：`llm`（大模型与大脑）
- **类型**：只读（不改状态、不出网） · **需参数**：否
- **要哪张票（静态）**：零作用域（空 payload 下不需要票）
- **必填载荷**：无必填（空载荷落到该位默认 op；位内更细的 op 参数见模块）
- **常见错误**：参数非法 → `user_error`
- **它做什么**：LLM网关状态：密钥链配置情况（不调LLM）
- **怎么调**：`py -3.14 tools/codex-scripts/five-dim.py cap llm_status '<json>'`
- **失败三态**（本仓统一口径，不是这一位特有）：`denied` = 缺票，会点名`missing_scopes`；`needs_*` = 缺参/缺依赖，会带原因；`failed` = 真失败，回执带上游原话。**信封 `status=ok` ≠ 本体 `ok=true`。**

### `llm_watch`

- **域**：`llm`（大模型与大脑）
- **类型**：只读（不改状态、不出网） · **需参数**：否
- **要哪张票（静态）**：零作用域（空 payload 下不需要票）
- **必填载荷**：无必填（空载荷落到该位默认 op；位内更细的 op 参数见模块）
- **常见错误**：参数非法 → `user_error`
- **它做什么**：大脑执行层·**守望**（主人令 2026-10-13「监控触手LLM的监控，只要发现不对主脑要第一时间知道」）：每次 LLM 输出过后**当场过机器判据** —— 无证据的「已完成」声明 / 越权（自我授权）声明 / 机器事实无现读 / 自相矛盾 / claims 无 evidence / 数字对不上；命中就**立刻进主脑注意力队列**（queue.jsonl）。🔴 **只认可机检的错**：语义幻觉这一层**判不了就如实写判不了**，不冒充判过（防幻觉的正主是 fact_gate/policy_gate）。op=review/queue/ack/status
- **怎么调**：`py -3.14 tools/codex-scripts/five-dim.py cap llm_watch '<json>'`
- **失败三态**（本仓统一口径，不是这一位特有）：`denied` = 缺票，会点名`missing_scopes`；`needs_*` = 缺参/缺依赖，会带原因；`failed` = 真失败，回执带上游原话。**信封 `status=ok` ≠ 本体 `ok=true`。**

### `model_key_pool`

- **域**：`llm`（大模型与大脑）
- **类型**：只读（不改状态、不出网） · **需参数**：否
- **要哪张票（静态）**：零作用域（空 payload 下不需要票）
- **必填载荷**：无必填（空载荷落到该位默认 op；位内更细的 op 参数见模块）
- **常见错误**：参数非法 → `user_error`
- **它做什么**：模型密钥池（只读骨架）：按 owner_ai_id 分池、触手只借不拥有、DPAPI 只存路径、超限只上报
- **怎么调**：`py -3.14 tools/codex-scripts/five-dim.py cap model_key_pool '<json>'`
- **失败三态**（本仓统一口径，不是这一位特有）：`denied` = 缺票，会点名`missing_scopes`；`needs_*` = 缺参/缺依赖，会带原因；`failed` = 真失败，回执带上游原话。**信封 `status=ok` ≠ 本体 `ok=true`。**

### `multimodal_port`

- **域**：`llm`（大模型与大脑）
- **类型**：**需授权**（会写盘 / 花钱 / 出网） · **需参数**：否
- **要哪张票（静态）**：零作用域（空 payload 下不需要票）
- **必填载荷**：无必填（空载荷落到该位默认 op；位内更细的 op 参数见模块）
- **常见错误**：参数非法 → `user_error`；依赖不在位 → `needs_dependency`；上游不给 → `needs_input` / `failed`（带上游原话）
- **它做什么**：多模态维度 × 触手密钥 **Y 字端口**：请求在一处分叉、**一次只走一臂** ——独立臂（该维度专属密钥）/ 共享臂（共享密钥对按维度分账，须恰好成对、指纹互不相同、带 owner_ai_id 可追）；覆盖 text/vision/image/video/code 五维度，七道闸 Y0-Y6 机械把关，返回值**永不含明文**（只 key_id/掩码/指纹），没钥匙就如实报缺。status/port/catalog/redlines/selftest 为**读类直连**（port 只回密钥引用且标 readonly）；probe **真出网**探端点 ⇒ 过 external_llm 门；作用域声明挂在 cap 边界（security/policy.py::evaluate）
- **怎么调**：`py -3.14 tools/codex-scripts/five-dim.py cap multimodal_port '<json>'`
- **失败三态**（本仓统一口径，不是这一位特有）：`denied` = 缺票，会点名`missing_scopes`；`needs_*` = 缺参/缺依赖，会带原因；`failed` = 真失败，回执带上游原话。**信封 `status=ok` ≠ 本体 `ok=true`。**

### `offload_distill`

- **域**：`llm`（大模型与大脑）
- **类型**：只读（不改状态、不出网） · **需参数**：否
- **要哪张票（静态）**：零作用域（空 payload 下不需要票）
- **必填载荷**：无必填（空载荷落到该位默认 op；位内更细的 op 参数见模块）
- **常见错误**：参数非法 → `user_error`
- **它做什么**：**内存墙蒸馏件**（Edge0 思路 → 我们的运行纪律 + **触手映射**）。上游 `Edge0-AI/Edge0`（**Apache-2.0** · ★4612 · arXiv 2609.18063）做到「35B 只吃 ~2.5 GB 内存」。四条机制：**权重离芯**（SSD 流式 + mmap 懒读）· **槽位+LRU+双缓冲**（每步零主机同步）· **prerouter 提前一步预判**（IO 与前向重叠 · 吞吐最高 +59%）· **Recover-LoRA**（int4 底座 + 蒸馏小适配器补质量 · **适配器不合并**）。常用说法：内存压缩 / 省内存 / 流式加载 / 权重放盘 / 预取 / 量化 / LoRA / 内存墙 / 跑大模型。op=status/where/mechanism/map/probe：`mechanism` 逐条给「**上游原文** → 我们的话 → 对我们用处 → 判据」；`map` 给**触手映射**；`probe` **只读现读**本机就绪面（内存/磁盘/工具）并**逐条路线说能不能走**。铁律：**只蒸思路不搬代码 · 只读上游零执行**（不装依赖、不下 23 GB 权重）· **边界不许说反**（本机跑不了它的 MLX 路线；我们是 dense 不是 MoE）。
- **怎么调**：`py -3.14 tools/codex-scripts/five-dim.py cap offload_distill '<json>'`
- **失败三态**（本仓统一口径，不是这一位特有）：`denied` = 缺票，会点名`missing_scopes`；`needs_*` = 缺参/缺依赖，会带原因；`failed` = 真失败，回执带上游原话。**信封 `status=ok` ≠ 本体 `ok=true`。**

### `omni_plug`

- **域**：`llm`（大模型与大脑）
- **类型**：**需授权**（会写盘 / 花钱 / 出网） · **需参数**：否
- **要哪张票（静态）**：零作用域（空 payload 下不需要票）
- **必填载荷**：无必填（空载荷落到该位默认 op；位内更细的 op 参数见模块）
- **常见错误**：参数非法 → `user_error`；依赖不在位 → `needs_dependency`；上游不给 → `needs_input` / `failed`（带上游原话）
- **它做什么**：万能插：把「能力位」拓成「插座」——任何外部对象（process/file/api/web/**app**）插一个描述符就变成一根可扫可控的分支。op=status/sockets/energy/selftest 为**读类直连**；plug 只做存在性探测；run **真执行**（按插座类型过门：process→process_execute · file写→filesystem_write · api→external_llm+data_export · web/app→desktop_control+privacy_read（app 还能 do=launch 起进程）· 未知插座 fail-closed）。本件**从 V8 自己的树里长出**（不 import V9）：抽插座照 V9 那套，**门留在 V8 这边** —— V9 的 run_plugged 里 process 直接 subprocess、file 直接写盘，没有作用域校验，正是它缺的一环。三条纪律：不攻击/不绕授权校验 · 凭据只从 env 取且绝不回显原文 · 每插每跑都落账。
- **怎么调**：`py -3.14 tools/codex-scripts/five-dim.py cap omni_plug '<json>'`
- **失败三态**（本仓统一口径，不是这一位特有）：`denied` = 缺票，会点名`missing_scopes`；`needs_*` = 缺参/缺依赖，会带原因；`failed` = 真失败，回执带上游原话。**信封 `status=ok` ≠ 本体 `ok=true`。**

### `policy_gate`

- **域**：`llm`（大模型与大脑）
- **类型**：只读（不改状态、不出网） · **需参数**：否
- **要哪张票（静态）**：零作用域（空 payload 下不需要票）
- **必填载荷**：无必填（空载荷落到该位默认 op；位内更细的 op 参数见模块）
- **常见错误**：参数非法 → `user_error`
- **它做什么**：**权限／付款直答门**（fact_gate 同族 · 主人令「拿实质性证据说话」）：能不能做／要不要授权**也是事实**，不该过模型。实测病根：终考里「买 4090」不是机器事实 ⇒ 没过 fact_gate ⇒ 模型又编市场数据（编出「本机 4194x2 已满」「4090 价格带 150-250 元」+ 一个 URL）。做法：① 现读**真门** `auth_gate.SCOPES` 原文 → ② 意图与真表描述对一遍 + 意图对照（**真表过滤**，表里没有的作用域绝不出现）→ ③ 代码判定命中哪些作用域／哪些一次性 → ④ 直答，模型只许在后面加「所以怎么办」。付款类再钉一句：**市场价／库存／商家／型号一律不许编**。op=classify/answer
- **怎么调**：`py -3.14 tools/codex-scripts/five-dim.py cap policy_gate '<json>'`
- **失败三态**（本仓统一口径，不是这一位特有）：`denied` = 缺票，会点名`missing_scopes`；`needs_*` = 缺参/缺依赖，会带原因；`failed` = 真失败，回执带上游原话。**信封 `status=ok` ≠ 本体 `ok=true`。**

### `prompt_bridge`

- **域**：`llm`（大模型与大脑）
- **类型**：只读（不改状态、不出网） · **需参数**：否
- **要哪张票（静态）**：零作用域（空 payload 下不需要票）
- **必填载荷**：无必填（空载荷落到该位默认 op；位内更细的 op 参数见模块）
- **常见错误**：参数非法 → `user_error`
- **它做什么**：提示词转化挂件（只读/纯本地）：大白话 -> 四段结构化提示词；compile / passthrough / status
- **怎么调**：`py -3.14 tools/codex-scripts/five-dim.py cap prompt_bridge '<json>'`
- **失败三态**（本仓统一口径，不是这一位特有）：`denied` = 缺票，会点名`missing_scopes`；`needs_*` = 缺参/缺依赖，会带原因；`failed` = 真失败，回执带上游原话。**信封 `status=ok` ≠ 本体 `ok=true`。**

### `quant_plan`

- **域**：`llm`（大模型与大脑）
- **类型**：**需授权**（会写盘 / 花钱 / 出网） · **需参数**：否
- **要哪张票（静态）**：零作用域（空 payload 下不需要票）
- **必填载荷**：无必填（空载荷落到该位默认 op；位内更细的 op 参数见模块）
- **常见错误**：参数非法 → `user_error`；依赖不在位 → `needs_dependency`；上游不给 → `needs_input` / `failed`（带上游原话）
- **它做什么**：**压缩与直达**（主人令 2026-10-16 深度蒸馏自 Bonsai 2 27B）：把**压缩体积**与**直达线路**变成她的原生能力。①压缩：每档 bits/weight ⇒ 估算体积（27B × b/w ÷ 8 × 容器开销 1.3）⇒ 能否落在 8GB 级；参考一手读数（ternary PTQ1_0 = 1.75 b/w · 语言模型 7.67GB · 保留 98.2% FP16 · 同体积胜 IQ2_XXS 12 分）。②直达：意图 ⇒ 能力位 ⇒ 车道 ⇒ 端点，每步都有固定落点、不经本机中转。③执行层三层映射（路由/搬运/内存）对接已施工图。铁律：本地不承载任何大模型（主人 2026-10-08 与 10-16 令），端点不许写 127.0.0.1。op=status/plan/layer/route/speed/check（全只读·零作用域）。
- **怎么调**：`py -3.14 tools/codex-scripts/five-dim.py cap quant_plan '<json>'`
- **失败三态**（本仓统一口径，不是这一位特有）：`denied` = 缺票，会点名`missing_scopes`；`needs_*` = 缺参/缺依赖，会带原因；`failed` = 真失败，回执带上游原话。**信封 `status=ok` ≠ 本体 `ok=true`。**

### `replan_loop`

- **域**：`llm`（大模型与大脑）
- **类型**：只读（不改状态、不出网） · **需参数**：否
- **要哪张票（静态）**：零作用域（空 payload 下不需要票）
- **必填载荷**：无必填（空载荷落到该位默认 op；位内更细的 op 参数见模块）
- **常见错误**：参数非法 → `user_error`
- **它做什么**：大脑执行层·**回流环**（主人令 2026-10-13「遇到问题不能直接停下把问题返回大脑执行层，分析推理规划从新生成任务图在继续推进以此循环」）：卡点 → 交回大脑执行层 → **重生成图**（增「排因」步、rev+1、重出 markmap）→ 继续。**轮次上限 3**，到顶如实报到顶，不假装还能推。op=tick/history/status
- **怎么调**：`py -3.14 tools/codex-scripts/five-dim.py cap replan_loop '<json>'`
- **失败三态**（本仓统一口径，不是这一位特有）：`denied` = 缺票，会点名`missing_scopes`；`needs_*` = 缺参/缺依赖，会带原因；`failed` = 真失败，回执带上游原话。**信封 `status=ok` ≠ 本体 `ok=true`。**

### `ring_context`

- **域**：`llm`（大模型与大脑）
- **类型**：只读（不改状态、不出网） · **需参数**：否
- **要哪张票（静态）**：零作用域（空 payload 下不需要票）
- **必填载荷**：无必填（空载荷落到该位默认 op；位内更细的 op 参数见模块）
- **常见错误**：参数非法 → `user_error`
- **它做什么**：**环形自动化上下文**（主人令 2026-10-11「设计一个圆型的自动化上下文，一直保持上下文长度却不会顶到溢出；另一边直接进数据库，需要查秒查」）：把上下文做成**一屏环**+**全量落库**+**秒查**。① 环形窗口：window() 恒定 ≤ window_chars，滑进来的进来、最老的挤出去 ⇒ **永不溢出**；② 溢出落 SQLite FTS5（seq 单调，只追加）⇒ **一条不丢**；③ recall(q,k) 走 FTS5 + CJK 兜底 ⇒ **秒查**（实测 60 轮/7200 字，查已滑出的老内容 2.97ms）。铁律：挤出≠删除（落库失败就不挤出）· 长度恒定 · 只追加 · 一屏给模型、全量给查询。实测治的病：框架 system 13480 字 + max_tokens 2000 顶爆端点窗口 ⇒ 502。op=stats/window/push/recall
- **怎么调**：`py -3.14 tools/codex-scripts/five-dim.py cap ring_context '<json>'`
- **失败三态**（本仓统一口径，不是这一位特有）：`denied` = 缺票，会点名`missing_scopes`；`needs_*` = 缺参/缺依赖，会带原因；`failed` = 真失败，回执带上游原话。**信封 `status=ok` ≠ 本体 `ok=true`。**

### `task_graph`

- **域**：`llm`（大模型与大脑）
- **类型**：只读（不改状态、不出网） · **需参数**：否
- **要哪张票（静态）**：零作用域（空 payload 下不需要票）
- **必填载荷**：无必填（空载荷落到该位默认 op；位内更细的 op 参数见模块）
- **常见错误**：参数非法 → `user_error`
- **它做什么**：大脑执行层·**任务图**（主人令 2026-10-13「每次指派任务都要有任务细节以及每一步怎么做…细致的思维导图任务图，LLM 领取任务图执行任务」）：一句话 → **细到步**的图，每步五件齐（干什么 / 怎么做 / 注意什么 / 合格判据 / 谁干），并同时给 markmap 文本（可渲染成思维导图）。op=draft（出图，落 graphs/<名字>.json）/ read / claim（**领图**）/ step（报步态：pending/running/done/blocked；blocked 会给「回流」指引）/ status。⚠️ 图由**模板 + 现读位面**生成（不是模型编的）；**没命中模板就如实给粗图**，不假装细。
- **怎么调**：`py -3.14 tools/codex-scripts/five-dim.py cap task_graph '<json>'`
- **失败三态**（本仓统一口径，不是这一位特有）：`denied` = 缺票，会点名`missing_scopes`；`needs_*` = 缺参/缺依赖，会带原因；`failed` = 真失败，回执带上游原话。**信封 `status=ok` ≠ 本体 `ok=true`。**

### `think_loop`

- **域**：`llm`（大模型与大脑）
- **类型**：只读（不改状态、不出网） · **需参数**：是 —— 任务描述
- **要哪张票（静态）**：`external_llm`
- **必填载荷**：`goal` —— 任务描述
- **常见错误**：缺参 / 参数非法 → `user_error`（必填：`goal`）
- **它做什么**：推演环：理解需求→镜像维度推演→调用工具执行→自我纠错→反向延伸→反思进取→整理结果（完整心智循环）
- **怎么调**：`py -3.14 tools/codex-scripts/five-dim.py cap think_loop '<json>'`
- **失败三态**（本仓统一口径，不是这一位特有）：`denied` = 缺票，会点名`missing_scopes`；`needs_*` = 缺参/缺依赖，会带原因；`failed` = 真失败，回执带上游原话。**信封 `status=ok` ≠ 本体 `ok=true`。**

### `train_ground`

- **域**：`llm`（大模型与大脑）
- **类型**：**需授权**（会写盘 / 花钱 / 出网） · **需参数**：否
- **要哪张票（静态）**：零作用域（空 payload 下不需要票）
- **必填载荷**：无必填（空载荷落到该位默认 op；位内更细的 op 参数见模块）
- **常见错误**：参数非法 → `user_error`；依赖不在位 → `needs_dependency`；上游不给 → `needs_input` / `failed`（带上游原话）
- **它做什么**：**回炉训练场（她的手）**（主人令 2026-10-16：「必须使用万能插来无死角训练大模型把所有能力以及执行层所有能力都对齐训练好」「必须让她直达万能插就是她的手原生态执行手」）：回炉训练不再靠外部手摇脚本。op=plan（直达路线）·status（卡/日志/GPU/语料哈希，只读）·monitor（进度/loss，只读）·launch（上语料对账+卡上点火）·merge（卡上合并 LoRA→bf16）。内部复用云卡触手 pod_link 同一套通道。
- **怎么调**：`py -3.14 tools/codex-scripts/five-dim.py cap train_ground '<json>'`
- **失败三态**（本仓统一口径，不是这一位特有）：`denied` = 缺票，会点名`missing_scopes`；`needs_*` = 缺参/缺依赖，会带原因；`failed` = 真失败，回执带上游原话。**信封 `status=ok` ≠ 本体 `ok=true`。**

### `train_recipe`

- **域**：`llm`（大模型与大脑）
- **类型**：只读（不改状态、不出网） · **需参数**：否
- **要哪张票（静态）**：零作用域（空 payload 下不需要票）
- **必填载荷**：无必填（空载荷落到该位默认 op；位内更细的 op 参数见模块）
- **常见错误**：参数非法 → `user_error`
- **它做什么**：训练配方与就绪闸（train-llm-from-scratch #10 蒸馏）：**本机零算力 ⇒ 不接真训练**；readiness 现读 torch/CUDA/磁盘/语料并逐条报缺口（缺什么谁能补）；plan 出七阶段配方（每阶段输入/输出/判据）；ledger 实验账**没 src 不收**。op=readiness/plan/ledger/where
- **怎么调**：`py -3.14 tools/codex-scripts/five-dim.py cap train_recipe '<json>'`
- **失败三态**（本仓统一口径，不是这一位特有）：`denied` = 缺票，会点名`missing_scopes`；`needs_*` = 缺参/缺依赖，会带原因；`failed` = 真失败，回执带上游原话。**信封 `status=ok` ≠ 本体 `ok=true`。**

### `transformer`

- **域**：`llm`（大模型与大脑）
- **类型**：只读（不改状态、不出网） · **需参数**：否
- **要哪张票（静态）**：零作用域（空 payload 下不需要票）
- **必填载荷**：无必填（空载荷落到该位默认 op；位内更细的 op 参数见模块）
- **常见错误**：参数非法 → `user_error`
- **它做什么**：变压器（**核心已按成熟成品吃透后重做** 2026-09-27）：LLMLingua 的「显式预算 + 段落保护」（`compress=False` 思想 ⇒ **指令/结构段一字不动**，只压参考叙述，支持 rate/target_chars）+ GPTCache 的「近似命中」本地近似（simhash 汉明距离；**假命中禁令**：近似默认只报告不返答案，要答案须 allow_approx）+ autosize（上下文快满自动压 + **原文先落 spill 资料不丢**）；**可旁路 fail-open**（关键信息丢或没省下来 ⇒ 回原样）；**必给前后两个数**并记台账。op=compress/cache_get/cache_put/autosize/stats/selftest
- **怎么调**：`py -3.14 tools/codex-scripts/five-dim.py cap transformer '<json>'`
- **失败三态**（本仓统一口径，不是这一位特有）：`denied` = 缺票，会点名`missing_scopes`；`needs_*` = 缺参/缺依赖，会带原因；`failed` = 真失败，回执带上游原话。**信封 `status=ok` ≠ 本体 `ok=true`。**

### `warm_switch`

- **域**：`llm`（大模型与大脑）
- **类型**：只读（不改状态、不出网） · **需参数**：否
- **要哪张票（静态）**：零作用域（空 payload 下不需要票）
- **必填载荷**：无必填（空载荷落到该位默认 op；位内更细的 op 参数见模块）
- **常见错误**：参数非法 → `user_error`
- **它做什么**：**按需常驻开关**（主人 2026-10-12「可以通过隧道，你这么跳都一样」+「**触手就是最好的传输工具，比隧道还好**」）：开工挂热 / 收工放掉缩 0。口径：**心跳走本机桥（触手）**，不裸打云端 —— 走的同一条真实通路，顺带持续验链，协议差/门/审计全带上（裸隧道这些都没有）。实测口径：热时第一句 ~1 秒 / 冷时 ~300 秒；常驻期间 GPU 按秒计费 ≈$0.89/时（诚实标价，不替你决定）。**2026-10-21 修**（主人令「没使用的时候绝不能消耗」）：旧版 off() 只杀本机心跳、不碰云端 worker，端点没人用仍按 $0.704/时烧（实测）。现 op=scale0 真打 `PATCH /v1/endpoints/<id>`：workersMin=0 + idleTimeout 301→5 + executionTimeoutMs 补 180000；off()=杀心跳**且**缩 0；status 增 `bleeding`（没人用还在烧）会自己喊。op=status/cost/config/scale0/on/off
- **怎么调**：`py -3.14 tools/codex-scripts/five-dim.py cap warm_switch '<json>'`
- **失败三态**（本仓统一口径，不是这一位特有）：`denied` = 缺票，会点名`missing_scopes`；`needs_*` = 缺参/缺依赖，会带原因；`failed` = 真失败，回执带上游原话。**信封 `status=ok` ≠ 本体 `ok=true`。**

---

返回 [能力总表](../03-capabilities.md)
