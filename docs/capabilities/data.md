# 数据 · `data`（12 位）

> 自动生成，数据源 `gbt_allinone/caps_registry.py`。只读 = 不改状态、不出网；其余调用前需人工授权（作用域门）。参数以 `requires_params` 标出；**必填载荷**与**常见错误**两列只写注册表登记过的（没登记就写「无必填」/通用三态），不猜。

| 能力位 | 类型 | 需参数 | 必填载荷 | 常见错误 | 它做什么 |
|---|---|---|---|---|---|
| `account_registry` | 只读 | — | —（注册表：无必填） | `user_error` | AI 账号登记表只读校验：一人一号（不共用账号/不共用凭证/只记路径/不许无主账号） |
| `audit_query` | 只读 | — | —（注册表：无必填） | `user_error` | 查审计账本（只读）：`event` 可选，按事件名过滤；回 `total` 与最近 10 条 `sample`。它是「无痕即不存在」这条公理的读口 —— 能力有没有真跑、门有没有真拦，都从这里取证。作用域 `audit_read`（读审计历史本身也要票）。 |
| `bi_distill` | 只读 | — | —（注册表：无必填） | `user_error` | **蒸馏件**（不是外挂）：把吞入件 dataease/dataease（**GPL-3.0**〔README 徽章明写 GPL v3；GitHub 未识别才标 NOASSERTION〕· 24603星 · Java「人人可用的开源 BI 工具」）蒸成三条取法+一条红线：①拖拽即… |
| `chart_html` | **需授权** | — | —（注册表：无必填） | `user_error` / `failed` | **数据 → 自包含交互 ECharts HTML**（蒸馏自 skills.sh smart-charts，只蒸思想不搬代码；2026-10-17）：CSV/TSV/JSON/XLSX → 单文件 HTML（ECharts 内联，零外链、离线可开）；自动推题型（bar/line… |
| `count_words` | 只读 | — | —（注册表：无必填） | `user_error` | 数词数：吃 `text`，回 `words`（按空白切分）与 `chars`（字符数，含中文）。只读、零作用域；用于产出字数核对（比如「这段旁白是不是 300 字」）。 |
| `datakit` | 只读 | — | —（注册表：无必填） | `user_error` | 本地数据工具（**只读**）：html→markdown · html→表格结构 · xlsx 字节→JSON · JSON 美化/排序 · 多段 CSV 合并（`op` 分派，见 `tools/datakit.py` 的 OPS）。🔴 **结果从返回里给、不落盘** ⇒ 作用域… |
| `db_plugin` | 只读 | — | —（注册表：无必填） | `user_error` | 数据库插件（只读骨架）：**存储后端注册表 + 触手双向连接**。**无限扩容 = 加一行**（BACKENDS 元组）—— 现登记 9 个后端（SQLite+FTS5 / 只读查询台 / 资产索引 / Obsidian / 记忆银行 / JSONL台账 / 飞书 / Notio… |
| `db_probe` | 只读 | — | —（注册表：无必填） | `user_error` | 本地只读查询台（dbx 蒸馏）：**SQLite 概览 + JSONL 行统计**——`sources` 列可查本地源 · `tables` 静态 SQL 列表/视图 · `schema` 参数化取 DDL + Python 解析列 · `counts` 每表行数（iterdum… |
| `echo` | 只读 | — | —（注册表：无必填） | `user_error` | 联调回显位：把 payload 原样打回来（回执里 `echo` 字段＝你发进去的那份）。用来验证「门 → 分派 → 回执」这条链通不通、信封形状对不对；不改状态、不出网、零作用域，永远是最安全的第一根探针。 |
| `humanizer` | **需授权** | — | —（注册表：无必填） | `user_error` / `failed` | **去 AI 味改写器**（蒸馏自 skills.sh humanizer-zh，只蒸思想；2026-10-17）：与 `human-tone-check` **同源**规则表，改写前后用同一判据量；中文优先（改成人话）。op=rewrite（text 或 file · out… |
| `record_grid` | 只读 | 是 | `text`、`path` | `user_error` | 行式记录网格：陌生文本结构画像/草案骨架/逐行解析/回写自证/词表校验（op=profile\|draft\|parse\|emit\|verify\|vocab\|presets） |
| `skill_finder` | **需授权** | — | —（注册表：无必填） | `user_error` / `failed` | **技能检索器**（蒸馏自 skills.sh find-skills，只蒸思想；2026-10-17）：一句需求 → 候选技能 + 来源/装与否/风险三列；另有 op=vet 出供应链体检报告。只读本机图鉴与技能目录，**不出网、不装不改**。op=find（q）/ vet（n… |

> 表格里是**摘要**（超过 140 字截断）；下面每位还有**逐位详解**（完整原文 / 要哪张票 / 真调用命令 / 缺什么会怎么报）。

---

## 逐位详解

### `account_registry`

- **域**：`data`（数据）
- **类型**：只读（不改状态、不出网） · **需参数**：否
- **要哪张票（静态）**：零作用域（空 payload 下不需要票）
- **必填载荷**：无必填（注册表 `requires_params=false`；空载荷落到该位默认 op）
- **常见错误**：参数非法 → `user_error`
- **它做什么**：AI 账号登记表只读校验：一人一号（不共用账号/不共用凭证/只记路径/不许无主账号）
- **怎么调**：`py -3.14 tools/codex-scripts/five-dim.py cap account_registry '<json>'`
- **失败三态**（本仓统一口径，不是这一位特有）：`denied` = 缺票，会点名`missing_scopes`；`needs_*` = 缺参/缺依赖，会带原因；`failed` = 真失败，回执带上游原话。**信封 `status=ok` ≠ 本体 `ok=true`。**

### `audit_query`

- **域**：`data`（数据）
- **类型**：只读（不改状态、不出网） · **需参数**：否
- **要哪张票（静态）**：零作用域（空 payload 下不需要票）
- **必填载荷**：无必填（注册表 `requires_params=false`；空载荷落到该位默认 op）
- **常见错误**：参数非法 → `user_error`
- **它做什么**：查审计账本（只读）：`event` 可选，按事件名过滤；回 `total` 与最近 10 条 `sample`。它是「无痕即不存在」这条公理的读口 —— 能力有没有真跑、门有没有真拦，都从这里取证。作用域 `audit_read`（读审计历史本身也要票）。
- **怎么调**：`py -3.14 tools/codex-scripts/five-dim.py cap audit_query '<json>'`
- **失败三态**（本仓统一口径，不是这一位特有）：`denied` = 缺票，会点名`missing_scopes`；`needs_*` = 缺参/缺依赖，会带原因；`failed` = 真失败，回执带上游原话。**信封 `status=ok` ≠ 本体 `ok=true`。**

### `bi_distill`

- **域**：`data`（数据）
- **类型**：只读（不改状态、不出网） · **需参数**：否
- **要哪张票（静态）**：零作用域（空 payload 下不需要票）
- **必填载荷**：无必填（注册表 `requires_params=false`；空载荷落到该位默认 op）
- **常见错误**：参数非法 → `user_error`
- **它做什么**：**蒸馏件**（不是外挂）：把吞入件 dataease/dataease（**GPL-3.0**〔README 徽章明写 GPL v3；GitHub 未识别才标 NOASSERTION〕· 24603星 · Java「人人可用的开源 BI 工具」）蒸成三条取法+一条红线：①拖拽即建模（先把数据做成可拖拽的字段模型，再谈图）②连接面如实列（「支持 X」= 真连得上；OLTP/OLAP/数仓/文件/API 五类照实登记，连不上如实说）③可分享是产品属性（分析产物必须能交出去，不留在自己盘里）④🔴**许可红线 GPL-3.0：只引用不复制**（复用其实现要先过 GPL）。op=source 现读胶囊尺寸+逐文件 sha256 · op=provenance 逐条指回原话（含**未蒸馏**一行：离线安装包/install.sh 不取）。**零作用域**。边界：接入端 ≡ 我们**已有**的 genoffice/datakit/record_grid；本位只蒸取法，**不建平行位**。op=method/source/provenance/where
- **怎么调**：`py -3.14 tools/codex-scripts/five-dim.py cap bi_distill '<json>'`
- **失败三态**（本仓统一口径，不是这一位特有）：`denied` = 缺票，会点名`missing_scopes`；`needs_*` = 缺参/缺依赖，会带原因；`failed` = 真失败，回执带上游原话。**信封 `status=ok` ≠ 本体 `ok=true`。**

### `chart_html`

- **域**：`data`（数据）
- **类型**：**需授权**（会写盘 / 花钱 / 出网） · **需参数**：否
- **要哪张票（静态）**：零作用域（空 payload 下不需要票）
- **必填载荷**：无必填（注册表 `requires_params=false`；空载荷落到该位默认 op）
- **常见错误**：参数非法 → `user_error`；依赖不在位 → `needs_dependency`；上游不给 → `needs_input` / `failed`（带上游原话）
- **它做什么**：**数据 → 自包含交互 ECharts HTML**（蒸馏自 skills.sh smart-charts，只蒸思想不搬代码；2026-10-17）：CSV/TSV/JSON/XLSX → 单文件 HTML（ECharts 内联，零外链、离线可开）；自动推题型（bar/line/pie）与轴；落 state/charts/。op=make（data=路径 · kind/title/out 可选）。
- **怎么调**：`py -3.14 tools/codex-scripts/five-dim.py cap chart_html '<json>'`
- **失败三态**（本仓统一口径，不是这一位特有）：`denied` = 缺票，会点名`missing_scopes`；`needs_*` = 缺参/缺依赖，会带原因；`failed` = 真失败，回执带上游原话。**信封 `status=ok` ≠ 本体 `ok=true`。**

### `count_words`

- **域**：`data`（数据）
- **类型**：只读（不改状态、不出网） · **需参数**：否
- **要哪张票（静态）**：零作用域（空 payload 下不需要票）
- **必填载荷**：无必填（注册表 `requires_params=false`；空载荷落到该位默认 op）
- **常见错误**：参数非法 → `user_error`
- **它做什么**：数词数：吃 `text`，回 `words`（按空白切分）与 `chars`（字符数，含中文）。只读、零作用域；用于产出字数核对（比如「这段旁白是不是 300 字」）。
- **怎么调**：`py -3.14 tools/codex-scripts/five-dim.py cap count_words '<json>'`
- **失败三态**（本仓统一口径，不是这一位特有）：`denied` = 缺票，会点名`missing_scopes`；`needs_*` = 缺参/缺依赖，会带原因；`failed` = 真失败，回执带上游原话。**信封 `status=ok` ≠ 本体 `ok=true`。**

### `datakit`

- **域**：`data`（数据）
- **类型**：只读（不改状态、不出网） · **需参数**：否
- **要哪张票（静态）**：零作用域（空 payload 下不需要票）
- **必填载荷**：无必填（注册表 `requires_params=false`；空载荷落到该位默认 op）
- **常见错误**：参数非法 → `user_error`
- **它做什么**：本地数据工具（**只读**）：html→markdown · html→表格结构 · xlsx 字节→JSON · JSON 美化/排序 · 多段 CSV 合并（`op` 分派，见 `tools/datakit.py` 的 OPS）。🔴 **结果从返回里给、不落盘** ⇒ 作用域天然为空，**不需要也不该改 `policy.py`**。**为什么不给落盘版**：一个会写盘的新能力位若 policy 里没有分支，就是**绕过门**；`policy.py` 是安全文件，只有主人能改 —— 要落盘请他加分支。
- **怎么调**：`py -3.14 tools/codex-scripts/five-dim.py cap datakit '<json>'`
- **失败三态**（本仓统一口径，不是这一位特有）：`denied` = 缺票，会点名`missing_scopes`；`needs_*` = 缺参/缺依赖，会带原因；`failed` = 真失败，回执带上游原话。**信封 `status=ok` ≠ 本体 `ok=true`。**

### `db_plugin`

- **域**：`data`（数据）
- **类型**：只读（不改状态、不出网） · **需参数**：否
- **要哪张票（静态）**：零作用域（空 payload 下不需要票）
- **必填载荷**：无必填（注册表 `requires_params=false`；空载荷落到该位默认 op）
- **常见错误**：参数非法 → `user_error`
- **它做什么**：数据库插件（只读骨架）：**存储后端注册表 + 触手双向连接**。**无限扩容 = 加一行**（BACKENDS 元组）—— 现登记 9 个后端（SQLite+FTS5 / 只读查询台 / 资产索引 / Obsidian / 记忆银行 / JSONL台账 / 飞书 / Notion / TheBrain）。**绑定一次两个方向都查得到**（正向 触手→后端 · 反向 后端→触手），台账照 tentacle_bind（state/asset_bindings.jsonl · **只增不删**）。op=status/backends/ledger/bind/resolve/expand/check_source/check_key/check_bypass/check_trace
- **怎么调**：`py -3.14 tools/codex-scripts/five-dim.py cap db_plugin '<json>'`
- **失败三态**（本仓统一口径，不是这一位特有）：`denied` = 缺票，会点名`missing_scopes`；`needs_*` = 缺参/缺依赖，会带原因；`failed` = 真失败，回执带上游原话。**信封 `status=ok` ≠ 本体 `ok=true`。**

### `db_probe`

- **域**：`data`（数据）
- **类型**：只读（不改状态、不出网） · **需参数**：否
- **要哪张票（静态）**：零作用域（空 payload 下不需要票）
- **必填载荷**：无必填（注册表 `requires_params=false`；空载荷落到该位默认 op）
- **常见错误**：参数非法 → `user_error`
- **它做什么**：本地只读查询台（dbx 蒸馏）：**SQLite 概览 + JSONL 行统计**——`sources` 列可查本地源 · `tables` 静态 SQL 列表/视图 · `schema` 参数化取 DDL + Python 解析列 · `counts` 每表行数（iterdump 文本计数）· `jsonl` 行统计/筛选（纯 Python 可自由筛）。🔴 **零动态 SQL**（两版被安全钩子按"SQL 注入"拦下 ⇒ 静态字面量 + 参数取值 + Python 层解析；连接 mode=ro）；结果不落盘；不提供按条件查行（要就说，请主人给门加分支）。op=sources/tables/schema/counts/jsonl/where
- **怎么调**：`py -3.14 tools/codex-scripts/five-dim.py cap db_probe '<json>'`
- **失败三态**（本仓统一口径，不是这一位特有）：`denied` = 缺票，会点名`missing_scopes`；`needs_*` = 缺参/缺依赖，会带原因；`failed` = 真失败，回执带上游原话。**信封 `status=ok` ≠ 本体 `ok=true`。**

### `echo`

- **域**：`data`（数据）
- **类型**：只读（不改状态、不出网） · **需参数**：否
- **要哪张票（静态）**：零作用域（空 payload 下不需要票）
- **必填载荷**：无必填（注册表 `requires_params=false`；空载荷落到该位默认 op）
- **常见错误**：参数非法 → `user_error`
- **它做什么**：联调回显位：把 payload 原样打回来（回执里 `echo` 字段＝你发进去的那份）。用来验证「门 → 分派 → 回执」这条链通不通、信封形状对不对；不改状态、不出网、零作用域，永远是最安全的第一根探针。
- **怎么调**：`py -3.14 tools/codex-scripts/five-dim.py cap echo '<json>'`
- **失败三态**（本仓统一口径，不是这一位特有）：`denied` = 缺票，会点名`missing_scopes`；`needs_*` = 缺参/缺依赖，会带原因；`failed` = 真失败，回执带上游原话。**信封 `status=ok` ≠ 本体 `ok=true`。**

### `humanizer`

- **域**：`data`（数据）
- **类型**：**需授权**（会写盘 / 花钱 / 出网） · **需参数**：否
- **要哪张票（静态）**：零作用域（空 payload 下不需要票）
- **必填载荷**：无必填（注册表 `requires_params=false`；空载荷落到该位默认 op）
- **常见错误**：参数非法 → `user_error`；依赖不在位 → `needs_dependency`；上游不给 → `needs_input` / `failed`（带上游原话）
- **它做什么**：**去 AI 味改写器**（蒸馏自 skills.sh humanizer-zh，只蒸思想；2026-10-17）：与 `human-tone-check` **同源**规则表，改写前后用同一判据量；中文优先（改成人话）。op=rewrite（text 或 file · out 可选）；返回 before_hits/after_hits/fixes；句长与逗号类只能人改，如实列出。
- **怎么调**：`py -3.14 tools/codex-scripts/five-dim.py cap humanizer '<json>'`
- **失败三态**（本仓统一口径，不是这一位特有）：`denied` = 缺票，会点名`missing_scopes`；`needs_*` = 缺参/缺依赖，会带原因；`failed` = 真失败，回执带上游原话。**信封 `status=ok` ≠ 本体 `ok=true`。**

### `record_grid`

- **域**：`data`（数据）
- **类型**：只读（不改状态、不出网） · **需参数**：是 —— 要画像/解析的内容：内联 text 或框架内相对路径 path（二选一）；parse 另需 plan 或 plan_name；emit 还要 records（记录列表）
- **要哪张票（静态）**：零作用域（空 payload 下不需要票）
- **必填载荷**：`text`、`path` —— 要画像/解析的内容：内联 text 或框架内相对路径 path（二选一）；parse 另需 plan 或 plan_name；emit 还要 records（记录列表）
- **常见错误**：缺参 / 参数非法 → `user_error`（必填：`text`、`path`）
- **它做什么**：行式记录网格：陌生文本结构画像/草案骨架/逐行解析/回写自证/词表校验（op=profile|draft|parse|emit|verify|vocab|presets）
- **怎么调**：`py -3.14 tools/codex-scripts/five-dim.py cap record_grid '<json>'`
- **失败三态**（本仓统一口径，不是这一位特有）：`denied` = 缺票，会点名`missing_scopes`；`needs_*` = 缺参/缺依赖，会带原因；`failed` = 真失败，回执带上游原话。**信封 `status=ok` ≠ 本体 `ok=true`。**

### `skill_finder`

- **域**：`data`（数据）
- **类型**：**需授权**（会写盘 / 花钱 / 出网） · **需参数**：否
- **要哪张票（静态）**：零作用域（空 payload 下不需要票）
- **必填载荷**：无必填（注册表 `requires_params=false`；空载荷落到该位默认 op）
- **常见错误**：参数非法 → `user_error`；依赖不在位 → `needs_dependency`；上游不给 → `needs_input` / `failed`（带上游原话）
- **它做什么**：**技能检索器**（蒸馏自 skills.sh find-skills，只蒸思想；2026-10-17）：一句需求 → 候选技能 + 来源/装与否/风险三列；另有 op=vet 出供应链体检报告。只读本机图鉴与技能目录，**不出网、不装不改**。op=find（q）/ vet（name）。
- **怎么调**：`py -3.14 tools/codex-scripts/five-dim.py cap skill_finder '<json>'`
- **失败三态**（本仓统一口径，不是这一位特有）：`denied` = 缺票，会点名`missing_scopes`；`needs_*` = 缺参/缺依赖，会带原因；`failed` = 真失败，回执带上游原话。**信封 `status=ok` ≠ 本体 `ok=true`。**

---

返回 [能力总表](../03-capabilities.md)
