# 引擎（工作流/定时） · `engine`（10 位）

> 自动生成，数据源 `gbt_allinone/caps_registry.py`。只读 = 不改状态、不出网；其余调用前需人工授权（作用域门）。参数以 `requires_params` 标出；**必填载荷**与**常见错误**两列只写注册表登记过的（没登记就写「无必填」/通用三态），不猜。

| 能力位 | 类型 | 需参数 | 必填载荷 | 常见错误 | 它做什么 |
|---|---|---|---|---|---|
| `sched_define` | 只读 | 是 | `name`、`workflow`、`every_seconds` | `user_error` | 定时触发器：定义调度（工作流 + 间隔），无人值守自动执行 |
| `sched_status` | 只读 | — | —（注册表：无必填） | `user_error` | 定时触发器：查调度状态（上次执行/结果） |
| `sched_tick` | 只读 | — | —（注册表：无必填） | `user_error` | 定时触发器：扫描到期调度并执行（可由循环/计划任务驱动） |
| `transfer` | 只读 | — | —（注册表：无必填） | `user_error` | 数据传输算子（核心传输工具）：map/filter/merge/unique/sort/pluck/collect 等 14 个纯变换算子 |
| `wf_cache_clear` | 只读 | — | —（注册表：无必填） | `user_error` | 万能插：清空传输缓存（同输入复用的节点结果缓存） |
| `wf_define` | 只读 | 是 | `name`、`nodes` | `user_error` | 万能插执行引擎：定义工作流（DAG，校验环/依赖/能力合法性） |
| `wf_resume` | 只读 | 是 | `run_id` | `user_error` | 万能插执行引擎：从运行记录断点续跑（复用已完成节点，只重跑未完成的） |
| `wf_run` | 只读 | 是 | `name` | `user_error` | 万能插执行引擎：分层并行执行工作流，节点结果如实落盘 |
| `wf_status` | 只读 | — | —（注册表：无必填） | `user_error` | 万能插执行引擎：查运行记录（可按工作流名过滤） |
| `workflow_forge` | **需授权** | — | —（注册表：无必填） | `user_error` / `failed` | **工作流十式**（主人令 2026-10-16：skills.sh 累计安装 TOP10 蒸馏）：① **find_skill**（先现读名册再看外部，不重造）② **grill**（连续追问厘清目标/范围/判据/边界，上限 8 轮）③ **grill_docs**（追问+术语… |

> 表格里是**摘要**（超过 140 字截断）；下面每位还有**逐位详解**（完整原文 / 要哪张票 / 真调用命令 / 缺什么会怎么报）。

---

## 逐位详解

### `sched_define`

- **域**：`engine`（引擎（工作流/定时））
- **类型**：只读（不改状态、不出网） · **需参数**：是 —— 调度名 + 要跑的工作流名 + 间隔秒数（>0）
- **要哪张票（静态）**：零作用域（空 payload 下不需要票）
- **必填载荷**：`name`、`workflow`、`every_seconds` —— 调度名 + 要跑的工作流名 + 间隔秒数（>0）
- **常见错误**：缺参 / 参数非法 → `user_error`（必填：`name`、`workflow`、`every_seconds`）
- **它做什么**：定时触发器：定义调度（工作流 + 间隔），无人值守自动执行
- **怎么调**：`py -3.14 tools/codex-scripts/five-dim.py cap sched_define '<json>'`
- **失败三态**（本仓统一口径，不是这一位特有）：`denied` = 缺票，会点名`missing_scopes`；`needs_*` = 缺参/缺依赖，会带原因；`failed` = 真失败，回执带上游原话。**信封 `status=ok` ≠ 本体 `ok=true`。**

### `sched_status`

- **域**：`engine`（引擎（工作流/定时））
- **类型**：只读（不改状态、不出网） · **需参数**：否
- **要哪张票（静态）**：零作用域（空 payload 下不需要票）
- **必填载荷**：无必填（注册表 `requires_params=false`；空载荷落到该位默认 op）
- **常见错误**：参数非法 → `user_error`
- **它做什么**：定时触发器：查调度状态（上次执行/结果）
- **怎么调**：`py -3.14 tools/codex-scripts/five-dim.py cap sched_status '<json>'`
- **失败三态**（本仓统一口径，不是这一位特有）：`denied` = 缺票，会点名`missing_scopes`；`needs_*` = 缺参/缺依赖，会带原因；`failed` = 真失败，回执带上游原话。**信封 `status=ok` ≠ 本体 `ok=true`。**

### `sched_tick`

- **域**：`engine`（引擎（工作流/定时））
- **类型**：只读（不改状态、不出网） · **需参数**：否
- **要哪张票（静态）**：零作用域（空 payload 下不需要票）
- **必填载荷**：无必填（注册表 `requires_params=false`；空载荷落到该位默认 op）
- **常见错误**：参数非法 → `user_error`
- **它做什么**：定时触发器：扫描到期调度并执行（可由循环/计划任务驱动）
- **怎么调**：`py -3.14 tools/codex-scripts/five-dim.py cap sched_tick '<json>'`
- **失败三态**（本仓统一口径，不是这一位特有）：`denied` = 缺票，会点名`missing_scopes`；`needs_*` = 缺参/缺依赖，会带原因；`failed` = 真失败，回执带上游原话。**信封 `status=ok` ≠ 本体 `ok=true`。**

### `transfer`

- **域**：`engine`（引擎（工作流/定时））
- **类型**：只读（不改状态、不出网） · **需参数**：否
- **要哪张票（静态）**：零作用域（空 payload 下不需要票）
- **必填载荷**：无必填（注册表 `requires_params=false`；空载荷落到该位默认 op）
- **常见错误**：参数非法 → `user_error`
- **它做什么**：数据传输算子（核心传输工具）：map/filter/merge/unique/sort/pluck/collect 等 14 个纯变换算子
- **怎么调**：`py -3.14 tools/codex-scripts/five-dim.py cap transfer '<json>'`
- **失败三态**（本仓统一口径，不是这一位特有）：`denied` = 缺票，会点名`missing_scopes`；`needs_*` = 缺参/缺依赖，会带原因；`failed` = 真失败，回执带上游原话。**信封 `status=ok` ≠ 本体 `ok=true`。**

### `wf_cache_clear`

- **域**：`engine`（引擎（工作流/定时））
- **类型**：只读（不改状态、不出网） · **需参数**：否
- **要哪张票（静态）**：零作用域（空 payload 下不需要票）
- **必填载荷**：无必填（注册表 `requires_params=false`；空载荷落到该位默认 op）
- **常见错误**：参数非法 → `user_error`
- **它做什么**：万能插：清空传输缓存（同输入复用的节点结果缓存）
- **怎么调**：`py -3.14 tools/codex-scripts/five-dim.py cap wf_cache_clear '<json>'`
- **失败三态**（本仓统一口径，不是这一位特有）：`denied` = 缺票，会点名`missing_scopes`；`needs_*` = 缺参/缺依赖，会带原因；`failed` = 真失败，回执带上游原话。**信封 `status=ok` ≠ 本体 `ok=true`。**

### `wf_define`

- **域**：`engine`（引擎（工作流/定时））
- **类型**：只读（不改状态、不出网） · **需参数**：是 —— 工作流名 + 节点列表（带依赖关系的 DAG）
- **要哪张票（静态）**：零作用域（空 payload 下不需要票）
- **必填载荷**：`name`、`nodes` —— 工作流名 + 节点列表（带依赖关系的 DAG）
- **常见错误**：缺参 / 参数非法 → `user_error`（必填：`name`、`nodes`）
- **它做什么**：万能插执行引擎：定义工作流（DAG，校验环/依赖/能力合法性）
- **怎么调**：`py -3.14 tools/codex-scripts/five-dim.py cap wf_define '<json>'`
- **失败三态**（本仓统一口径，不是这一位特有）：`denied` = 缺票，会点名`missing_scopes`；`needs_*` = 缺参/缺依赖，会带原因；`failed` = 真失败，回执带上游原话。**信封 `status=ok` ≠ 本体 `ok=true`。**

### `wf_resume`

- **域**：`engine`（引擎（工作流/定时））
- **类型**：只读（不改状态、不出网） · **需参数**：是 —— 要续跑的运行 id（wf_status 里可查）
- **要哪张票（静态）**：零作用域（空 payload 下不需要票）
- **必填载荷**：`run_id` —— 要续跑的运行 id（wf_status 里可查）
- **常见错误**：缺参 / 参数非法 → `user_error`（必填：`run_id`）
- **它做什么**：万能插执行引擎：从运行记录断点续跑（复用已完成节点，只重跑未完成的）
- **怎么调**：`py -3.14 tools/codex-scripts/five-dim.py cap wf_resume '<json>'`
- **失败三态**（本仓统一口径，不是这一位特有）：`denied` = 缺票，会点名`missing_scopes`；`needs_*` = 缺参/缺依赖，会带原因；`failed` = 真失败，回执带上游原话。**信封 `status=ok` ≠ 本体 `ok=true`。**

### `wf_run`

- **域**：`engine`（引擎（工作流/定时））
- **类型**：只读（不改状态、不出网） · **需参数**：是 —— 要跑的工作流名（先用 wf_define 定义）
- **要哪张票（静态）**：零作用域（空 payload 下不需要票）
- **必填载荷**：`name` —— 要跑的工作流名（先用 wf_define 定义）
- **常见错误**：缺参 / 参数非法 → `user_error`（必填：`name`）
- **它做什么**：万能插执行引擎：分层并行执行工作流，节点结果如实落盘
- **怎么调**：`py -3.14 tools/codex-scripts/five-dim.py cap wf_run '<json>'`
- **失败三态**（本仓统一口径，不是这一位特有）：`denied` = 缺票，会点名`missing_scopes`；`needs_*` = 缺参/缺依赖，会带原因；`failed` = 真失败，回执带上游原话。**信封 `status=ok` ≠ 本体 `ok=true`。**

### `wf_status`

- **域**：`engine`（引擎（工作流/定时））
- **类型**：只读（不改状态、不出网） · **需参数**：否
- **要哪张票（静态）**：零作用域（空 payload 下不需要票）
- **必填载荷**：无必填（注册表 `requires_params=false`；空载荷落到该位默认 op）
- **常见错误**：参数非法 → `user_error`
- **它做什么**：万能插执行引擎：查运行记录（可按工作流名过滤）
- **怎么调**：`py -3.14 tools/codex-scripts/five-dim.py cap wf_status '<json>'`
- **失败三态**（本仓统一口径，不是这一位特有）：`denied` = 缺票，会点名`missing_scopes`；`needs_*` = 缺参/缺依赖，会带原因；`failed` = 真失败，回执带上游原话。**信封 `status=ok` ≠ 本体 `ok=true`。**

### `workflow_forge`

- **域**：`engine`（引擎（工作流/定时））
- **类型**：**需授权**（会写盘 / 花钱 / 出网） · **需参数**：否
- **要哪张票（静态）**：零作用域（空 payload 下不需要票）
- **必填载荷**：无必填（注册表 `requires_params=false`；空载荷落到该位默认 op）
- **常见错误**：参数非法 → `user_error`；依赖不在位 → `needs_dependency`；上游不给 → `needs_input` / `failed`（带上游原话）
- **它做什么**：**工作流十式**（主人令 2026-10-16：skills.sh 累计安装 TOP10 蒸馏）：① **find_skill**（先现读名册再看外部，不重造）② **grill**（连续追问厘清目标/范围/判据/边界，上限 8 轮）③ **grill_docs**（追问+术语表与决策记录）④ **arch_review**（结构体检与重构机会，不动手）⑤ **browser_ops**（点/填/抽，先看后动）⑥ **tdd_loop**（红-绿-重构，没先红不算 TDD）⑦ **setup_rules**（状态/标签/文档规则一次定死）⑧ **style**（先定视觉契约）⑨ **handoff**（现状+资料位置+下一步）⑩ **triage**（四档分类与状态推进，不下模棱两可）。**不重造**：真执行走既有位（browser/code_audit/aesthetic）；**先看后动**（第 37 条）。op=grill/grill_docs/find_skill/arch_review/browser_ops/tdd_loop/setup_rules/style/handoff/triage/check/route（**全只读·零作用域）。
- **怎么调**：`py -3.14 tools/codex-scripts/five-dim.py cap workflow_forge '<json>'`
- **失败三态**（本仓统一口径，不是这一位特有）：`denied` = 缺票，会点名`missing_scopes`；`needs_*` = 缺参/缺依赖，会带原因；`failed` = 真失败，回执带上游原话。**信封 `status=ok` ≠ 本体 `ok=true`。**

---

返回 [能力总表](../03-capabilities.md)
