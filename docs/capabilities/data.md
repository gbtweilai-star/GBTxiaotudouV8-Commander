# 数据 · `data`（12 位）

> 自动生成，数据源 `gbt_allinone/caps_registry.py`。只读 = 不改状态、不出网；其余调用前需人工授权（作用域门）。参数以 `requires_params` 标出。

| 能力位 | 类型 | 需参数 | 它做什么 |
|---|---|---|---|
| `account_registry` | 只读 | — | AI 账号登记表只读校验：一人一号（不共用账号/不共用凭证/只记路径/不许无主账号） |
| `audit_query` | 只读 | — | 只读查询统一数据后台日志 |
| `bi_distill` | 只读 | — | **蒸馏件**（不是外挂）：把吞入件 dataease/dataease（**GPL-3.0**〔README 徽章明写 GPL v3；GitHub 未识别才标 NOASSERTION〕· 24603星 · Java「人人可用的开源 BI 工具」）蒸成三条取法+一条红线：①拖拽即… |
| `chart_html` | **需授权** | — | **数据 → 自包含交互 ECharts HTML**（蒸馏自 skills.sh smart-charts，只蒸思想不搬代码；2026-10-17）：CSV/TSV/JSON/XLSX → 单文件 HTML（ECharts 内联，零外链、离线可开）；自动推题型（bar/line… |
| `count_words` | 只读 | — | 统计文本词数 |
| `datakit` | 只读 | — | 本地数据工具（**只读**）：html→markdown · html→表格结构 · xlsx 字节→JSON · JSON 美化/排序 · 多段 CSV 合并（`op` 分派，见 `tools/datakit.py` 的 OPS）。🔴 **结果从返回里给、不落盘** ⇒ 作用域… |
| `db_plugin` | 只读 | — | 数据库插件（只读骨架）：**存储后端注册表 + 触手双向连接**。**无限扩容 = 加一行**（BACKENDS 元组）—— 现登记 9 个后端（SQLite+FTS5 / 只读查询台 / 资产索引 / Obsidian / 记忆银行 / JSONL台账 / 飞书 / Notio… |
| `db_probe` | 只读 | — | 本地只读查询台（dbx 蒸馏）：**SQLite 概览 + JSONL 行统计**——`sources` 列可查本地源 · `tables` 静态 SQL 列表/视图 · `schema` 参数化取 DDL + Python 解析列 · `counts` 每表行数（iterdum… |
| `echo` | 只读 | — | 回显传入数据，用于联调 |
| `humanizer` | **需授权** | — | **去 AI 味改写器**（蒸馏自 skills.sh humanizer-zh，只蒸思想；2026-10-17）：与 `human-tone-check` **同源**规则表，改写前后用同一判据量；中文优先（改成人话）。op=rewrite（text 或 file · out… |
| `record_grid` | 只读 | 是 | 行式记录网格：陌生文本结构画像/草案骨架/逐行解析/回写自证/词表校验（op=profile\|draft\|parse\|emit\|verify\|vocab\|presets） |
| `skill_finder` | **需授权** | — | **技能检索器**（蒸馏自 skills.sh find-skills，只蒸思想；2026-10-17）：一句需求 → 候选技能 + 来源/装与否/风险三列；另有 op=vet 出供应链体检报告。只读本机图鉴与技能目录，**不出网、不装不改**。op=find（q）/ vet（n… |

> 表格里是**摘要**（超过 140 字截断）；完整原文见 [`data/capabilities.json`](../../data/capabilities.json) 的 `desc` 字段。

---

返回 [能力总表](../03-capabilities.md)
