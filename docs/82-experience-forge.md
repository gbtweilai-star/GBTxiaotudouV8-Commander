# 82 · 成长闭环（experience_forge）

> 2026-11-01 · 主人判据：**"跑通"由外部验证器判，"固化"进记忆/工具/规则，不写权重。**
> 本件把闭环做成一个入口；不是"模型说自己学会了"。

## 一、闭环四段

| 段 | 谁负责 | 本件怎么接 |
|---|---|---|
| 生成 | 模型 | 代码/页面/脚本从这里出（不在本件内） |
| **外部验证** | 测试/编译/lint/真浏览器/运行时 | `verify` 必须给 `cmd + exit_code=0 + evidence`；证据可以是 `tests/`、`final_check`、`deep_audit`、`two-way-sync verify` 的产物 |
| **固化** | 记忆 / 工具 / 规则 | `record` 写入 `state/experience_forge/entries.jsonl`；`promote` 升成 `rules.json` / `tools.json` |
| 检索 | 记忆层 | `query` 按问题/尝试/方案/标签算重合；下次先查再生成 |

## 二、硬门（fail-closed）

- 没有 `verify` ⇒ `needs_verify`，**不收**；
- `verify.exit_code != 0` ⇒ `needs_verify`，**不收**；
- 没有 `evidence`（产物路径/测试名/读数摘要）⇒ 不收；
- `problem` < 6 字 / `solution` < 4 字 ⇒ 不收；
- 同问题+同验证重复 ⇒ `duplicate`，不重复写。

这是对"模型自己说跑通了"的正面拒绝：**没有外部证据，经验进不了库**。

## 三、op

| op | 作用 |
|---|---|
| `status` | 库路径、条数、规则/工具数、可用验证器清单 |
| `record` | 收一条带证据的经验（problem/attempts/solution/verify/files/tags） |
| `query` | 检索（问题→尝试→验证→最终方案） |
| `show` | 全量（自用/审计） |
| `promote` | `kind=rule` 写验证规则清单；`kind=tool` 写可调用模板 |
| `index` | **规范库直接进 FTS**（`state/experience_forge/*.jsonl` 已加进 memory_manager 扫描；不再写镜像） |
| `export_tests` | 读 `rules.json` 的结构化 checks，自动生成 `tests/test_experience_generated.py` |
| `mirror` | **镜像能力**：把规范库导出成派生扁平副本（默认 `state/mirror/experience_forge.jsonl`，不进 FTS，`out=` 可写旧路径） |
| `mirror_status` | 校验镜像是否与规范库同步（sha256 + 条数） |
| `verify` | 校验库：id 唯一、每条有合法 verify 证据、JSON 可读；**不重放历史命令** |
| `where` | 入口 |

## 四、本会话已固化的 4 条（真证据）

| 问题 | 外部验证 | 固化 |
|---|---|---|
| taste_guard 接入上游 inspector 时 Python 子进程 %TEMP% EPERM、Edge 退 | `deep_audit` 真跑 PASS（report.json） | 工具/规则 |
| `two-way-sync pull` 用旧副本覆盖新文件 | `two-way-sync verify` ALIGNED | 规则（newer-wins） |
| 上帝视角首页 10 FAIL / 9 WARN | `deep_audit` PASS · 0 FAIL | 规则（首屏可见 h1/真图/视图静态） |
| 短剧三集只有分镜卡、无真画面 | `drama-build` 三项 checks 全 true + 报告 | 工具（stock-fetch + 一键脚本） |

## 五、诚实边界

- **不写权重、不训练**；只写 `state/experience_forge/`。
- `verify` 只校验库与证据字段，**不重放任意历史命令**（安全）。
- 已接 `memory_manager` FTS5：**唯一真相 = `state/experience_forge/entries.jsonl`**，`memory_manager` 直接索引它；无镜像文件。实测 **564 docs**，`find "上帝视角首页"` 命中该 entries.jsonl。
- 记忆层不是第四处存储：条目是结构化索引，原始证据仍在 tests/outputs/交付树。\n- 回归闸：`tests/test_experience_rules.py` 手写守 3 条；`export_tests` 从 rules.json 自动生成 `tests/test_experience_generated.py`（5 条 check，实测 ALL PASS）。
- 镜像能力：`mirror` 生成派生副本 + `mirror_status` 校验 sha256/条数；实测 4 条、in_sync=true、`indexed_by_fts=false`（不制造重复命中）。

> 开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属
