# 心智 · `mind`（27 位）

> 自动生成，数据源 `gbt_allinone/caps_registry.py`。只读 = 不改状态、不出网；其余调用前需人工授权（作用域门）。参数以 `requires_params` 标出；**必填载荷**与**常见错误**两列只写注册表登记过的（没登记就写「无必填」/通用三态），不猜。

| 能力位 | 类型 | 需参数 | 必填载荷 | 常见错误 | 它做什么 |
|---|---|---|---|---|---|
| `agent_council` | 只读 | — | —（注册表：无必填） | `user_error` | 多智能体议事会（蒸馏自 2026-09-28 主人给的周榜卡 AutoGen 61.2k★ 微软开源，只取**开会这一面**；并行干活已有 agent_rig/orca，拍板已有 Jev 四角色引擎，不重造）：`convene` 定题定角色（默认对位 Jev 四角色）· **发言… |
| `api_slot` | 只读 | — | —（注册表：无必填） | `user_error` | **动态 API 槽定义口**（主人 P1，2026-11-02）：op=schema/validate/register/remove/list/call/verify。只登记槽定义：https-only、拒 localhost/私网/URL 凭据、密钥只存环境变量引用名、参数… |
| `auto_switch` | 只读 | — | —（注册表：无必填） | `user_error` | 自动化切换引擎（只读骨架·内调）：意图分析(L1解析+L2交叉验证+L3置信度)→任务分级→模型切换→原生执行→验证审计；接线点只有 Intent JSON；五条红线（低置信先问主人/不许直接执行/每次切换记 model_used/不可逆二次确认/身份不许改写） |
| `belief_forge` | 只读 | — | —（注册表：无必填） | `user_error` | 信念锻造（hindsight 学习半蒸馏）：**观察 → 信念（会学习，不改写历史）→ 心智模型**——`observe` 登记观察（**必须带证据与来源**）· `consolidate` 把同类观察巩固成信念（置信度=证据加权；move ∈ strengthen/weaken… |
| `brain_council` | 只读 | — | —（注册表：无必填） | `user_error` | 脑会·编队群决策引擎：各脑出本域提案，委员长聚合裁决（纯推演·不出网·不落盘）；执行仍走主脑既有授权门 |
| `brain_vault` | 只读 | — | —（注册表：无必填） | `user_error` | 脑库接入：Obsidian 记忆库的读（recall=记忆总纲+收集箱）/ 写（remember=追加一条）/ 体检（status）—— 追加式、**没有任何删除路径**，写进去的想忘都忘不了 |
| `code_graph` | 只读 | — | —（注册表：无必填） | `user_error` | 代码知识图谱（主人令 2026-10-29，蒸馏自 symchenry/codegraph 的机制、不抄代码）：**本地 AST 预索引 → SQLite 图谱（symbols/edges/files + FTS5）→ 结构化查询**。给 AI 的是「文件:行 + 类型 + 签名… |
| `command_chain` | 只读 | — | —（注册表：无必填） | `user_error` | 指挥链·总指挥参谋部（主人令 2026-10-01「全部统一品牌统一智能体以 GBT小土豆V8 为主延申…不能重复和错误指挥」）：五段全踩已有件不重造 —— ①接令·理解意图（brain_route）②双顾问意见（大脑执行层读数 + gods_eye 顾问席，主人 9-28 分工… |
| `context_inject` | 只读 | — | —（注册表：无必填） | `user_error` | **上下文注入选择器**（主人 P1，2026-11-02）：op=schema/select/verify。给 query + 候选（记忆/最近对话/UI 信号/工具结果/预取缓存），纯确定性选出有预算上限的注入项：过期丢弃/去重/相关度/来源优先级/新鲜度/来源配额/字符预算… |
| `director_mood` | 只读 | — | —（注册表：无必填） | `user_error` | 导演 AI 情绪内核（只读）：七情六欲 + 半衰期；情绪只改『怎么看』，不改『看到什么』 |
| `doc_intake` | 只读 | — | —（注册表：无必填） | `user_error` | 知识库·**解析 → 入库 → 同步**那条链（吞 WeKnora 后蒸的另一面：本仓原来只有单件 `datakit`/`genoffice`）。三条口径：① **只吃本地文件**（出网那条路另挂门，本位不偷偷下载）② **不新造解析器**：md/txt 直读、html 只做去标… |
| `experience_forge` | 只读 | — | —（注册表：无必填） | `user_error` | 成长闭环（2026-11-01 主人判据：跑通由外部验证器判，固化进记忆/工具/规则而非权重）：record 只收**带外部验证证据**的经验（cmd+exit_code=0+evidence），缺验证或非零一律 needs_verify 拒收；query 检索「问题→尝试→验证… |
| `focus_stack` | 只读 | — | —（注册表：无必填） | `user_error` | **焦点栈 + 记忆审计**（主人 P1，2026-11-02）：op=schema/push/pop/clear/snapshot/audit/focus_events/verify。焦点栈=主循环「此刻最重要的事」，上限 12、同 id 提分不重复、按 score/时间排序；… |
| `local_brain` | 只读 | — | —（注册表：无必填） | `user_error` | 本地原生脑（只读骨架·内调）：本地模型=脑皮层（可换）·主机=纪律层（不可换）；五层链路（模型只做意图解析与结果解释）；五条红线（不许直接执行命令/不可逆必卡/缺参不许猜/每次留痕/身份不许改写） |
| `memory_bank` | 只读 | — | —（注册表：无必填） | `user_error` | 记忆银行：**来源追踪 + 别名 + 零停机迁移**（蒸馏自 GitHub 周榜 #01 hindsight，只取架构）：`stamp` 给每条记忆打来源印章（ref/sha256/origin/session/why/evidence）；`trace` 同时报**印章在不在**… |
| `memory_manager` | 只读 | — | —（注册表：无必填） | `user_error` | 记忆管理 + 万能精准秒搜（主人令 2026-09-27）：SQLite **FTS5 全文索引**（实测中文可检索）·七类源（记忆/文档/技能/状态/**能力位**/代理/助手记忆）⇒ find 秒级返回「路径+类型+高亮片段」，并**同时端出匹配的能力位**（"想到匹配面出现… |
| `meta_cognition` | 只读 | — | —（注册表：无必填） | `user_error` | 元认知循环（只读骨架）：自省→查内部→查外部→问主人→沉淀 + 五条红线（自省不是自责/不许硬猜/先查后问/问完沉淀/大脑也自省） |
| `mind` | 只读 | — | —（注册表：无必填） | `user_error` | 心智引擎：开工前预演 pre_work、评估、内部状态、经验召回与反思（写框架 store，不出网） |
| `observer_anchor` | 只读 | — | —（注册表：无必填） | `user_error` | 观察者锚点律只读骨架：三公理 + 六短板补齐 + 五条红线（同一方不许既扫又报/审计器必须被审/递归封顶/终止点只能由人设/关键节点人在场） |
| `obsidian_vault` | 只读 | — | —（注册表：无必填） | `user_error` | Obsidian 永久记忆层（主人令 2026-09-27「让触手的吞天拥有永久记忆 Obsidian，所有触手每一根都绑定独立的 Obsidian，再把所有的 Obsidian 和本体的自研 Obsidian 双向绑定到一起互通共享」）：**227 根触手各一本独立库**（`v… |
| `persona_kernel` | 只读 | 是 | `op` | `user_error` | 性格内核 v4.0：外温表达十律 + 内刚四基石（止损/主动/洞察/静待）+ 十条机械红线；四大基石原文一字不差；evolve 是唯一写口（驱动心智演化） |
| `proactive_report` | 只读 | — | —（注册表：无必填） | `user_error` | 主动汇报引擎只读判据层：四类汇报（新奇发现/主人需要/记忆命中/赚钱机会）+ 四维打分 + 不打扰门（静默时段/预算/去重/及格线）+ 短律成句；只判不说 |
| `reminder` | 只读 | — | —（注册表：无必填） | `user_error` | **提醒能力位**（主人 P1，2026-11-02）：op=schema/create/list/cancel/complete/due/verify。创建/列出/取消提醒；写 `state/reminders.json` 前先过 **filesystem_write 门**（… |
| `self_intake` | 只读 | — | —（注册表：无必填） | `user_error` | **未命中即取源 · 自递归改进**（主人令 2026-10-15：「在她的知识库未命中的时候转抓取全网国内外的论文来实现自我递归改进，这样就不会出现自己都不懂的东西就无脑操作了」。回路：**known（先查本地知识库）→ 未命中 ⇒ intake（抓取全网取源）→ 蒸馏胶囊（带… |
| `thought_stream` | 只读 | — | —（注册表：无必填） | `user_error` | **思考流/行动流归一化**（主人 P1，2026-11-02）：op=schema/normalize/verify。把已有 JSONL 事件行统一成 thought/action/result/guard/system 五类，带时间/actor/title/detail/来源… |
| `turn_trace` | 只读 | — | —（注册表：无必填） | `user_error` | **轮次追踪 Turn Trace**（主人 P2，2026-11-03）：op=schema/normalize/verify。把已有 JSONL 执行账按 session + 间隔（默认 45s）归并成“轮”：步骤/结果/证据/耗时；没有 input 字段就 null，不伪造… |
| `wiki_graph` | 只读 | — | —（注册表：无必填） | `user_error` | 知识库·**自维护百科 + 知识图谱 + 回滚**（吞 `Tencent/WeKnora` 后蒸的那一面：本仓原来只有碎片 `brain_vault`/`thebrain_bridge`/`asset_index`）。四件铁律：① **每页必须有出处**（无源页 verify 点… |

> 表格里是**摘要**（超过 140 字截断）；下面每位还有**逐位详解**（完整原文 / 要哪张票 / 真调用命令 / 缺什么会怎么报）。

---

## 逐位详解

### `agent_council`

- **域**：`mind`（心智）
- **类型**：只读（不改状态、不出网） · **需参数**：否
- **要哪张票（静态）**：零作用域（空 payload 下不需要票）
- **必填载荷**：无必填（注册表 `requires_params=false`；空载荷落到该位默认 op）
- **常见错误**：参数非法 → `user_error`
- **它做什么**：多智能体议事会（蒸馏自 2026-09-28 主人给的周榜卡 AutoGen 61.2k★ 微软开源，只取**开会这一面**；并行干活已有 agent_rig/orca，拍板已有 Jev 四角色引擎，不重造）：`convene` 定题定角色（默认对位 Jev 四角色）· **发言权** round_robin 下抢话 ⇒ 结构化拒绝 · `speak_auto` 大脑走门（llm_chat，external_llm 闸，没票如实报）· `vote` **终止要全员**投「结束」或轮次用尽，主持人不许独断 · `minutes` 纪要带全文 sha，篡改 ⇒ verify 当场报被改过。op=convene/speak/speak_auto/vote/minutes/verify/status/where
- **怎么调**：`py -3.14 tools/codex-scripts/five-dim.py cap agent_council '<json>'`
- **失败三态**（本仓统一口径，不是这一位特有）：`denied` = 缺票，会点名`missing_scopes`；`needs_*` = 缺参/缺依赖，会带原因；`failed` = 真失败，回执带上游原话。**信封 `status=ok` ≠ 本体 `ok=true`。**

### `api_slot`

- **域**：`mind`（心智）
- **类型**：只读（不改状态、不出网） · **需参数**：否
- **要哪张票（静态）**：零作用域（空 payload 下不需要票）
- **必填载荷**：无必填（注册表 `requires_params=false`；空载荷落到该位默认 op）
- **常见错误**：参数非法 → `user_error`
- **它做什么**：**动态 API 槽定义口**（主人 P1，2026-11-02）：op=schema/validate/register/remove/list/call/verify。只登记槽定义：https-only、拒 localhost/私网/URL 凭据、密钥只存环境变量引用名、参数白名单、超时 1..30s、上限 20；**零作用域**，不读 secret 值、不发请求。`call()` 永远 not_supported（执行器未接，需 network egress 门+注入），不假装调通。
- **怎么调**：`py -3.14 tools/codex-scripts/five-dim.py cap api_slot '<json>'`
- **失败三态**（本仓统一口径，不是这一位特有）：`denied` = 缺票，会点名`missing_scopes`；`needs_*` = 缺参/缺依赖，会带原因；`failed` = 真失败，回执带上游原话。**信封 `status=ok` ≠ 本体 `ok=true`。**

### `auto_switch`

- **域**：`mind`（心智）
- **类型**：只读（不改状态、不出网） · **需参数**：否
- **要哪张票（静态）**：零作用域（空 payload 下不需要票）
- **必填载荷**：无必填（注册表 `requires_params=false`；空载荷落到该位默认 op）
- **常见错误**：参数非法 → `user_error`
- **它做什么**：自动化切换引擎（只读骨架·内调）：意图分析(L1解析+L2交叉验证+L3置信度)→任务分级→模型切换→原生执行→验证审计；接线点只有 Intent JSON；五条红线（低置信先问主人/不许直接执行/每次切换记 model_used/不可逆二次确认/身份不许改写）
- **怎么调**：`py -3.14 tools/codex-scripts/five-dim.py cap auto_switch '<json>'`
- **失败三态**（本仓统一口径，不是这一位特有）：`denied` = 缺票，会点名`missing_scopes`；`needs_*` = 缺参/缺依赖，会带原因；`failed` = 真失败，回执带上游原话。**信封 `status=ok` ≠ 本体 `ok=true`。**

### `belief_forge`

- **域**：`mind`（心智）
- **类型**：只读（不改状态、不出网） · **需参数**：否
- **要哪张票（静态）**：零作用域（空 payload 下不需要票）
- **必填载荷**：无必填（注册表 `requires_params=false`；空载荷落到该位默认 op）
- **常见错误**：参数非法 → `user_error`
- **它做什么**：信念锻造（hindsight 学习半蒸馏）：**观察 → 信念（会学习，不改写历史）→ 心智模型**——`observe` 登记观察（**必须带证据与来源**）· `consolidate` 把同类观察巩固成信念（置信度=证据加权；move ∈ strengthen/weaken/extend，**history 只追加不覆盖**）· `beliefs` 现读 · `model` 心智模型（常备答案，**纯本地读、不调模型**）。op=observe/consolidate/beliefs/model/where
- **怎么调**：`py -3.14 tools/codex-scripts/five-dim.py cap belief_forge '<json>'`
- **失败三态**（本仓统一口径，不是这一位特有）：`denied` = 缺票，会点名`missing_scopes`；`needs_*` = 缺参/缺依赖，会带原因；`failed` = 真失败，回执带上游原话。**信封 `status=ok` ≠ 本体 `ok=true`。**

### `brain_council`

- **域**：`mind`（心智）
- **类型**：只读（不改状态、不出网） · **需参数**：否
- **要哪张票（静态）**：零作用域（空 payload 下不需要票）
- **必填载荷**：无必填（注册表 `requires_params=false`；空载荷落到该位默认 op）
- **常见错误**：参数非法 → `user_error`
- **它做什么**：脑会·编队群决策引擎：各脑出本域提案，委员长聚合裁决（纯推演·不出网·不落盘）；执行仍走主脑既有授权门
- **怎么调**：`py -3.14 tools/codex-scripts/five-dim.py cap brain_council '<json>'`
- **失败三态**（本仓统一口径，不是这一位特有）：`denied` = 缺票，会点名`missing_scopes`；`needs_*` = 缺参/缺依赖，会带原因；`failed` = 真失败，回执带上游原话。**信封 `status=ok` ≠ 本体 `ok=true`。**

### `brain_vault`

- **域**：`mind`（心智）
- **类型**：只读（不改状态、不出网） · **需参数**：否
- **要哪张票（静态）**：零作用域（空 payload 下不需要票）
- **必填载荷**：无必填（注册表 `requires_params=false`；空载荷落到该位默认 op）
- **常见错误**：参数非法 → `user_error`
- **它做什么**：脑库接入：Obsidian 记忆库的读（recall=记忆总纲+收集箱）/ 写（remember=追加一条）/ 体检（status）—— 追加式、**没有任何删除路径**，写进去的想忘都忘不了
- **怎么调**：`py -3.14 tools/codex-scripts/five-dim.py cap brain_vault '<json>'`
- **失败三态**（本仓统一口径，不是这一位特有）：`denied` = 缺票，会点名`missing_scopes`；`needs_*` = 缺参/缺依赖，会带原因；`failed` = 真失败，回执带上游原话。**信封 `status=ok` ≠ 本体 `ok=true`。**

### `code_graph`

- **域**：`mind`（心智）
- **类型**：只读（不改状态、不出网） · **需参数**：否
- **要哪张票（静态）**：零作用域（空 payload 下不需要票）
- **必填载荷**：无必填（注册表 `requires_params=false`；空载荷落到该位默认 op）
- **常见错误**：参数非法 → `user_error`
- **它做什么**：代码知识图谱（主人令 2026-10-29，蒸馏自 symchenry/codegraph 的机制、不抄代码）：**本地 AST 预索引 → SQLite 图谱（symbols/edges/files + FTS5）→ 结构化查询**。给 AI 的是「文件:行 + 类型 + 签名 + 调用链」，**不是文件正文** —— 省 token 就在这一点。.py 用标准库 `ast` 精确解析（exact=1，实测占 96%）；.js/.cjs 用正则粗解析并标 `exact=false`（本仓零新依赖原则，不引 tree-sitter）。**改名导入已还原**（`import x as _tf` 后调 `_tf()` 仍能追到真名 —— 不还原的话 `callers` 会漏掉真正调用方，实测漏过 omni_plug/gpu_lane）；`edges` 带 `src_file`，所以**同名函数不会串**（按名字 JOIN 曾把 5 个不同的 `discover` 混成一处）。扫描面排除 `node_modules`/`.pylibs`/`native_browser`/`mirror_space`（第三方与生成代码）。op=index/find/callers/callees/summary/stats
- **怎么调**：`py -3.14 tools/codex-scripts/five-dim.py cap code_graph '<json>'`
- **失败三态**（本仓统一口径，不是这一位特有）：`denied` = 缺票，会点名`missing_scopes`；`needs_*` = 缺参/缺依赖，会带原因；`failed` = 真失败，回执带上游原话。**信封 `status=ok` ≠ 本体 `ok=true`。**

### `command_chain`

- **域**：`mind`（心智）
- **类型**：只读（不改状态、不出网） · **需参数**：否
- **要哪张票（静态）**：零作用域（空 payload 下不需要票）
- **必填载荷**：无必填（注册表 `requires_params=false`；空载荷落到该位默认 op）
- **常见错误**：参数非法 → `user_error`
- **它做什么**：指挥链·总指挥参谋部（主人令 2026-10-01「全部统一品牌统一智能体以 GBT小土豆V8 为主延申…不能重复和错误指挥」）：五段全踩已有件不重造 —— ①接令·理解意图（brain_route）②双顾问意见（大脑执行层读数 + gods_eye 顾问席，主人 9-28 分工口径）③总指挥决策（确定性合并成工作单元，**必须引用双顾问出处**）④专业提示词（prompt_bridge 四段，带原意保真自检）⑤触手智能体分派台账（commit 只落账，**执行仍走各能力的门**）。两条铁律做成判据：**防重复**（work_key 唯一 · plan_hash 幂等 · 开放分派互斥）与**防错指挥**（幽灵能力/幽灵执行席/缺双顾问出处 全红）。op=plan/commit/close/assignments/roster/status/where
- **怎么调**：`py -3.14 tools/codex-scripts/five-dim.py cap command_chain '<json>'`
- **失败三态**（本仓统一口径，不是这一位特有）：`denied` = 缺票，会点名`missing_scopes`；`needs_*` = 缺参/缺依赖，会带原因；`failed` = 真失败，回执带上游原话。**信封 `status=ok` ≠ 本体 `ok=true`。**

### `context_inject`

- **域**：`mind`（心智）
- **类型**：只读（不改状态、不出网） · **需参数**：否
- **要哪张票（静态）**：零作用域（空 payload 下不需要票）
- **必填载荷**：无必填（注册表 `requires_params=false`；空载荷落到该位默认 op）
- **常见错误**：参数非法 → `user_error`
- **它做什么**：**上下文注入选择器**（主人 P1，2026-11-02）：op=schema/select/verify。给 query + 候选（记忆/最近对话/UI 信号/工具结果/预取缓存），纯确定性选出有预算上限的注入项：过期丢弃/去重/相关度/来源优先级/新鲜度/来源配额/字符预算。**零作用域**（不调模型/不出网/不写盘）；模型上下文仍由调用方使用。
- **怎么调**：`py -3.14 tools/codex-scripts/five-dim.py cap context_inject '<json>'`
- **失败三态**（本仓统一口径，不是这一位特有）：`denied` = 缺票，会点名`missing_scopes`；`needs_*` = 缺参/缺依赖，会带原因；`failed` = 真失败，回执带上游原话。**信封 `status=ok` ≠ 本体 `ok=true`。**

### `director_mood`

- **域**：`mind`（心智）
- **类型**：只读（不改状态、不出网） · **需参数**：否
- **要哪张票（静态）**：零作用域（空 payload 下不需要票）
- **必填载荷**：无必填（注册表 `requires_params=false`；空载荷落到该位默认 op）
- **常见错误**：参数非法 → `user_error`
- **它做什么**：导演 AI 情绪内核（只读）：七情六欲 + 半衰期；情绪只改『怎么看』，不改『看到什么』
- **怎么调**：`py -3.14 tools/codex-scripts/five-dim.py cap director_mood '<json>'`
- **失败三态**（本仓统一口径，不是这一位特有）：`denied` = 缺票，会点名`missing_scopes`；`needs_*` = 缺参/缺依赖，会带原因；`failed` = 真失败，回执带上游原话。**信封 `status=ok` ≠ 本体 `ok=true`。**

### `doc_intake`

- **域**：`mind`（心智）
- **类型**：只读（不改状态、不出网） · **需参数**：否
- **要哪张票（静态）**：零作用域（空 payload 下不需要票）
- **必填载荷**：无必填（注册表 `requires_params=false`；空载荷落到该位默认 op）
- **常见错误**：参数非法 → `user_error`
- **它做什么**：知识库·**解析 → 入库 → 同步**那条链（吞 WeKnora 后蒸的另一面：本仓原来只有单件 `datakit`/`genoffice`）。三条口径：① **只吃本地文件**（出网那条路另挂门，本位不偷偷下载）② **不新造解析器**：md/txt 直读、html 只做去标签（**并如实标注不是真解析**）、其余类型如实报「解析手未接」③ `sources` 只**如实报**外部源（飞书/GitLab）接线状态，**没接就说没接**。op=intake/plan/sources/verify/status/where
- **怎么调**：`py -3.14 tools/codex-scripts/five-dim.py cap doc_intake '<json>'`
- **失败三态**（本仓统一口径，不是这一位特有）：`denied` = 缺票，会点名`missing_scopes`；`needs_*` = 缺参/缺依赖，会带原因；`failed` = 真失败，回执带上游原话。**信封 `status=ok` ≠ 本体 `ok=true`。**

### `experience_forge`

- **域**：`mind`（心智）
- **类型**：只读（不改状态、不出网） · **需参数**：否
- **要哪张票（静态）**：零作用域（空 payload 下不需要票）
- **必填载荷**：无必填（注册表 `requires_params=false`；空载荷落到该位默认 op）
- **常见错误**：参数非法 → `user_error`
- **它做什么**：成长闭环（2026-11-01 主人判据：跑通由外部验证器判，固化进记忆/工具/规则而非权重）：record 只收**带外部验证证据**的经验（cmd+exit_code=0+evidence），缺验证或非零一律 needs_verify 拒收；query 检索「问题→尝试→验证→方案」；promote 升成 rule（验证规则）或 tool（可调用模板）；verify 只校验库与证据字段，不重放历史命令。op=status/record/query/show/promote/verify/where。边界：不写权重、不训练；存 state/experience_forge/（可后续接 memory_manager 索引）。
- **怎么调**：`py -3.14 tools/codex-scripts/five-dim.py cap experience_forge '<json>'`
- **失败三态**（本仓统一口径，不是这一位特有）：`denied` = 缺票，会点名`missing_scopes`；`needs_*` = 缺参/缺依赖，会带原因；`failed` = 真失败，回执带上游原话。**信封 `status=ok` ≠ 本体 `ok=true`。**

### `focus_stack`

- **域**：`mind`（心智）
- **类型**：只读（不改状态、不出网） · **需参数**：否
- **要哪张票（静态）**：零作用域（空 payload 下不需要票）
- **必填载荷**：无必填（注册表 `requires_params=false`；空载荷落到该位默认 op）
- **常见错误**：参数非法 → `user_error`
- **它做什么**：**焦点栈 + 记忆审计**（主人 P1，2026-11-02）：op=schema/push/pop/clear/snapshot/audit/focus_events/verify。焦点栈=主循环「此刻最重要的事」，上限 12、同 id 提分不重复、按 score/时间排序；记忆审计只对**调用方给的记录**做只读体检（缺 id/文本/时间、重复、过短/超长、明显凭据 secret_like），不回显凭据原文、不改记录；**零作用域**（不读盘/不写盘/不出网）。
- **怎么调**：`py -3.14 tools/codex-scripts/five-dim.py cap focus_stack '<json>'`
- **失败三态**（本仓统一口径，不是这一位特有）：`denied` = 缺票，会点名`missing_scopes`；`needs_*` = 缺参/缺依赖，会带原因；`failed` = 真失败，回执带上游原话。**信封 `status=ok` ≠ 本体 `ok=true`。**

### `local_brain`

- **域**：`mind`（心智）
- **类型**：只读（不改状态、不出网） · **需参数**：否
- **要哪张票（静态）**：零作用域（空 payload 下不需要票）
- **必填载荷**：无必填（注册表 `requires_params=false`；空载荷落到该位默认 op）
- **常见错误**：参数非法 → `user_error`
- **它做什么**：本地原生脑（只读骨架·内调）：本地模型=脑皮层（可换）·主机=纪律层（不可换）；五层链路（模型只做意图解析与结果解释）；五条红线（不许直接执行命令/不可逆必卡/缺参不许猜/每次留痕/身份不许改写）
- **怎么调**：`py -3.14 tools/codex-scripts/five-dim.py cap local_brain '<json>'`
- **失败三态**（本仓统一口径，不是这一位特有）：`denied` = 缺票，会点名`missing_scopes`；`needs_*` = 缺参/缺依赖，会带原因；`failed` = 真失败，回执带上游原话。**信封 `status=ok` ≠ 本体 `ok=true`。**

### `memory_bank`

- **域**：`mind`（心智）
- **类型**：只读（不改状态、不出网） · **需参数**：否
- **要哪张票（静态）**：零作用域（空 payload 下不需要票）
- **必填载荷**：无必填（注册表 `requires_params=false`；空载荷落到该位默认 op）
- **常见错误**：参数非法 → `user_error`
- **它做什么**：记忆银行：**来源追踪 + 别名 + 零停机迁移**（蒸馏自 GitHub 周榜 #01 hindsight，只取架构）：`stamp` 给每条记忆打来源印章（ref/sha256/origin/session/why/evidence）；`trace` 同时报**印章在不在**与**内容有没有被改过**（当前 sha vs 印章 sha）；`alias`/`resolve` 记忆库别名（多级链 + **环检测**）；`migrate`/`migrate_apply` 搬家**先双写→逐文件校 sha→原子切别名→失败回滚**，旧目标只读保留（无删除路径）。op=stamp/trace/alias/resolve/aliases/migrate/migrate_apply/verify/where
- **怎么调**：`py -3.14 tools/codex-scripts/five-dim.py cap memory_bank '<json>'`
- **失败三态**（本仓统一口径，不是这一位特有）：`denied` = 缺票，会点名`missing_scopes`；`needs_*` = 缺参/缺依赖，会带原因；`failed` = 真失败，回执带上游原话。**信封 `status=ok` ≠ 本体 `ok=true`。**

### `memory_manager`

- **域**：`mind`（心智）
- **类型**：只读（不改状态、不出网） · **需参数**：否
- **要哪张票（静态）**：零作用域（空 payload 下不需要票）
- **必填载荷**：无必填（注册表 `requires_params=false`；空载荷落到该位默认 op）
- **常见错误**：参数非法 → `user_error`
- **它做什么**：记忆管理 + 万能精准秒搜（主人令 2026-09-27）：SQLite **FTS5 全文索引**（实测中文可检索）·七类源（记忆/文档/技能/状态/**能力位**/代理/助手记忆）⇒ find 秒级返回「路径+类型+高亮片段」，并**同时端出匹配的能力位**（"想到匹配面出现的能力"）；index 增量（mtime+sha 未变即跳过；**不许整表清空** —— 实测因此丢过索引）；store 存记忆过 filesystem_write 门。SQL 纪律：全部内联字面量 + `?` 占位符，不用变量拼 SQL（安全钩子实测拦过两次）。op=index/find/store/stats
- **怎么调**：`py -3.14 tools/codex-scripts/five-dim.py cap memory_manager '<json>'`
- **失败三态**（本仓统一口径，不是这一位特有）：`denied` = 缺票，会点名`missing_scopes`；`needs_*` = 缺参/缺依赖，会带原因；`failed` = 真失败，回执带上游原话。**信封 `status=ok` ≠ 本体 `ok=true`。**

### `meta_cognition`

- **域**：`mind`（心智）
- **类型**：只读（不改状态、不出网） · **需参数**：否
- **要哪张票（静态）**：零作用域（空 payload 下不需要票）
- **必填载荷**：无必填（注册表 `requires_params=false`；空载荷落到该位默认 op）
- **常见错误**：参数非法 → `user_error`
- **它做什么**：元认知循环（只读骨架）：自省→查内部→查外部→问主人→沉淀 + 五条红线（自省不是自责/不许硬猜/先查后问/问完沉淀/大脑也自省）
- **怎么调**：`py -3.14 tools/codex-scripts/five-dim.py cap meta_cognition '<json>'`
- **失败三态**（本仓统一口径，不是这一位特有）：`denied` = 缺票，会点名`missing_scopes`；`needs_*` = 缺参/缺依赖，会带原因；`failed` = 真失败，回执带上游原话。**信封 `status=ok` ≠ 本体 `ok=true`。**

### `mind`

- **域**：`mind`（心智）
- **类型**：只读（不改状态、不出网） · **需参数**：否
- **要哪张票（静态）**：零作用域（空 payload 下不需要票）
- **必填载荷**：无必填（注册表 `requires_params=false`；空载荷落到该位默认 op）
- **常见错误**：参数非法 → `user_error`
- **它做什么**：心智引擎：开工前预演 pre_work、评估、内部状态、经验召回与反思（写框架 store，不出网）
- **怎么调**：`py -3.14 tools/codex-scripts/five-dim.py cap mind '<json>'`
- **失败三态**（本仓统一口径，不是这一位特有）：`denied` = 缺票，会点名`missing_scopes`；`needs_*` = 缺参/缺依赖，会带原因；`failed` = 真失败，回执带上游原话。**信封 `status=ok` ≠ 本体 `ok=true`。**

### `observer_anchor`

- **域**：`mind`（心智）
- **类型**：只读（不改状态、不出网） · **需参数**：否
- **要哪张票（静态）**：零作用域（空 payload 下不需要票）
- **必填载荷**：无必填（注册表 `requires_params=false`；空载荷落到该位默认 op）
- **常见错误**：参数非法 → `user_error`
- **它做什么**：观察者锚点律只读骨架：三公理 + 六短板补齐 + 五条红线（同一方不许既扫又报/审计器必须被审/递归封顶/终止点只能由人设/关键节点人在场）
- **怎么调**：`py -3.14 tools/codex-scripts/five-dim.py cap observer_anchor '<json>'`
- **失败三态**（本仓统一口径，不是这一位特有）：`denied` = 缺票，会点名`missing_scopes`；`needs_*` = 缺参/缺依赖，会带原因；`failed` = 真失败，回执带上游原话。**信封 `status=ok` ≠ 本体 `ok=true`。**

### `obsidian_vault`

- **域**：`mind`（心智）
- **类型**：只读（不改状态、不出网） · **需参数**：否
- **要哪张票（静态）**：零作用域（空 payload 下不需要票）
- **必填载荷**：无必填（注册表 `requires_params=false`；空载荷落到该位默认 op）
- **常见错误**：参数非法 → `user_error`
- **它做什么**：Obsidian 永久记忆层（主人令 2026-09-27「让触手的吞天拥有永久记忆 Obsidian，所有触手每一根都绑定独立的 Obsidian，再把所有的 Obsidian 和本体的自研 Obsidian 双向绑定到一起互通共享」）：**227 根触手各一本独立库**（`vaults/<触手>/`：README MOC + 记忆.md + `.obsidian/app.json`，Obsidian 直接能开）· **本体的自研库**=brain_vault 认的那本（Documents\Codex\ObsidianVault）· 双向 = 触手页链回 [[GBT本体记忆]] + 本体 [[触手总索引]] 链到每一本（两条都查）。**只追加、无删除路径**；不写主人自己的库（只指向）。写主人 Documents 目录时走 filesystem_write 门（`root=documents`）。op=status/provision/remember/sync_page/bind/recall/verify/where
- **怎么调**：`py -3.14 tools/codex-scripts/five-dim.py cap obsidian_vault '<json>'`
- **失败三态**（本仓统一口径，不是这一位特有）：`denied` = 缺票，会点名`missing_scopes`；`needs_*` = 缺参/缺依赖，会带原因；`failed` = 真失败，回执带上游原话。**信封 `status=ok` ≠ 本体 `ok=true`。**

### `persona_kernel`

- **域**：`mind`（心智）
- **类型**：只读（不改状态、不出网） · **需参数**：是 —— op=constitution/laws/bedrocks/red_lines/check/action/scan/color/evolve
- **要哪张票（静态）**：零作用域（空 payload 下不需要票）
- **必填载荷**：`op` —— op=constitution/laws/bedrocks/red_lines/check/action/scan/color/evolve
- **常见错误**：缺参 / 参数非法 → `user_error`（必填：`op`）
- **它做什么**：性格内核 v4.0：外温表达十律 + 内刚四基石（止损/主动/洞察/静待）+ 十条机械红线；四大基石原文一字不差；evolve 是唯一写口（驱动心智演化）
- **怎么调**：`py -3.14 tools/codex-scripts/five-dim.py cap persona_kernel '<json>'`
- **失败三态**（本仓统一口径，不是这一位特有）：`denied` = 缺票，会点名`missing_scopes`；`needs_*` = 缺参/缺依赖，会带原因；`failed` = 真失败，回执带上游原话。**信封 `status=ok` ≠ 本体 `ok=true`。**

### `proactive_report`

- **域**：`mind`（心智）
- **类型**：只读（不改状态、不出网） · **需参数**：否
- **要哪张票（静态）**：零作用域（空 payload 下不需要票）
- **必填载荷**：无必填（注册表 `requires_params=false`；空载荷落到该位默认 op）
- **常见错误**：参数非法 → `user_error`
- **它做什么**：主动汇报引擎只读判据层：四类汇报（新奇发现/主人需要/记忆命中/赚钱机会）+ 四维打分 + 不打扰门（静默时段/预算/去重/及格线）+ 短律成句；只判不说
- **怎么调**：`py -3.14 tools/codex-scripts/five-dim.py cap proactive_report '<json>'`
- **失败三态**（本仓统一口径，不是这一位特有）：`denied` = 缺票，会点名`missing_scopes`；`needs_*` = 缺参/缺依赖，会带原因；`failed` = 真失败，回执带上游原话。**信封 `status=ok` ≠ 本体 `ok=true`。**

### `reminder`

- **域**：`mind`（心智）
- **类型**：只读（不改状态、不出网） · **需参数**：否
- **要哪张票（静态）**：零作用域（空 payload 下不需要票）
- **必填载荷**：无必填（注册表 `requires_params=false`；空载荷落到该位默认 op）
- **常见错误**：参数非法 → `user_error`
- **它做什么**：**提醒能力位**（主人 P1，2026-11-02）：op=schema/create/list/cancel/complete/due/verify。创建/列出/取消提醒；写 `state/reminders.json` 前先过 **filesystem_write 门**（可信会话免票，其余要一次性授权；gate 不可用 fail-closed）。上限 200，due_at ISO/epoch，repeat none/daily/weekly；不做网络通知/后台线程，不假装已通知。
- **怎么调**：`py -3.14 tools/codex-scripts/five-dim.py cap reminder '<json>'`
- **失败三态**（本仓统一口径，不是这一位特有）：`denied` = 缺票，会点名`missing_scopes`；`needs_*` = 缺参/缺依赖，会带原因；`failed` = 真失败，回执带上游原话。**信封 `status=ok` ≠ 本体 `ok=true`。**

### `self_intake`

- **域**：`mind`（心智）
- **类型**：只读（不改状态、不出网） · **需参数**：否
- **要哪张票（静态）**：零作用域（空 payload 下不需要票）
- **必填载荷**：无必填（注册表 `requires_params=false`；空载荷落到该位默认 op）
- **常见错误**：参数非法 → `user_error`
- **它做什么**：**未命中即取源 · 自递归改进**（主人令 2026-10-15：「在她的知识库未命中的时候转抓取全网国内外的论文来实现自我递归改进，这样就不会出现自己都不懂的东西就无脑操作了」。回路：**known（先查本地知识库）→ 未命中 ⇒ intake（抓取全网取源）→ 蒸馏胶囊（带出处）→ 钢印护照 + 入 context_vault 索引 → 再查就命中**。op：known/gate/rules（只读）· intake（写）。**主执行器是万能插**（`five-dim.py cap self_intake`），不是传统执行器。铁律：未命中且无出处 ⇒ 拒绝干活；取不到就写「未读到」。
- **怎么调**：`py -3.14 tools/codex-scripts/five-dim.py cap self_intake '<json>'`
- **失败三态**（本仓统一口径，不是这一位特有）：`denied` = 缺票，会点名`missing_scopes`；`needs_*` = 缺参/缺依赖，会带原因；`failed` = 真失败，回执带上游原话。**信封 `status=ok` ≠ 本体 `ok=true`。**

### `thought_stream`

- **域**：`mind`（心智）
- **类型**：只读（不改状态、不出网） · **需参数**：否
- **要哪张票（静态）**：零作用域（空 payload 下不需要票）
- **必填载荷**：无必填（注册表 `requires_params=false`；空载荷落到该位默认 op）
- **常见错误**：参数非法 → `user_error`
- **它做什么**：**思考流/行动流归一化**（主人 P1，2026-11-02）：op=schema/normalize/verify。把已有 JSONL 事件行统一成 thought/action/result/guard/system 五类，带时间/actor/title/detail/来源；坏行跳过、凭据脱敏、去重、上限 200；**零作用域**（只读归一化/不出网/不写盘），不伪造事件。
- **怎么调**：`py -3.14 tools/codex-scripts/five-dim.py cap thought_stream '<json>'`
- **失败三态**（本仓统一口径，不是这一位特有）：`denied` = 缺票，会点名`missing_scopes`；`needs_*` = 缺参/缺依赖，会带原因；`failed` = 真失败，回执带上游原话。**信封 `status=ok` ≠ 本体 `ok=true`。**

### `turn_trace`

- **域**：`mind`（心智）
- **类型**：只读（不改状态、不出网） · **需参数**：否
- **要哪张票（静态）**：零作用域（空 payload 下不需要票）
- **必填载荷**：无必填（注册表 `requires_params=false`；空载荷落到该位默认 op）
- **常见错误**：参数非法 → `user_error`
- **它做什么**：**轮次追踪 Turn Trace**（主人 P2，2026-11-03）：op=schema/normalize/verify。把已有 JSONL 执行账按 session + 间隔（默认 45s）归并成“轮”：步骤/结果/证据/耗时；没有 input 字段就 null，不伪造用户输入/证据；**零作用域**只读归并（不调模型/不写盘）。
- **怎么调**：`py -3.14 tools/codex-scripts/five-dim.py cap turn_trace '<json>'`
- **失败三态**（本仓统一口径，不是这一位特有）：`denied` = 缺票，会点名`missing_scopes`；`needs_*` = 缺参/缺依赖，会带原因；`failed` = 真失败，回执带上游原话。**信封 `status=ok` ≠ 本体 `ok=true`。**

### `wiki_graph`

- **域**：`mind`（心智）
- **类型**：只读（不改状态、不出网） · **需参数**：否
- **要哪张票（静态）**：零作用域（空 payload 下不需要票）
- **必填载荷**：无必填（注册表 `requires_params=false`；空载荷落到该位默认 op）
- **常见错误**：参数非法 → `user_error`
- **它做什么**：知识库·**自维护百科 + 知识图谱 + 回滚**（吞 `Tencent/WeKnora` 后蒸的那一面：本仓原来只有碎片 `brain_vault`/`thebrain_bridge`/`asset_index`）。四件铁律：① **每页必须有出处**（无源页 verify 点名）② **悬空边**必须点名，不许静默 ③ **回滚=产生新版本、永不删历史** ④ 图**现算**，不存第二份真相。op=put/get/graph/neighbors/history/rollback/verify/status/where
- **怎么调**：`py -3.14 tools/codex-scripts/five-dim.py cap wiki_graph '<json>'`
- **失败三态**（本仓统一口径，不是这一位特有）：`denied` = 缺票，会点名`missing_scopes`；`needs_*` = 缺参/缺依赖，会带原因；`failed` = 真失败，回执带上游原话。**信封 `status=ok` ≠ 本体 `ok=true`。**

---

返回 [能力总表](../03-capabilities.md)
