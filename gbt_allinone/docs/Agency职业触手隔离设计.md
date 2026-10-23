# GBT小土豆V8 · Agency 职业触手隔离设计

## 目标

把外部职业 Agent 吸收为 GBT 自己的职业目录，让每根触手拥有独立职业身份、独立统一大模型会话和独立镜像房间。职业资料是参考输入，不是可执行代码。

## 吸收边界

- 只读取 Markdown 职业定义的 frontmatter、标题、职责摘要和原文校验值。
- 外部 `scripts/`、安装器、转换器和命令示例不执行。
- 吸收后的原文只进入 `room_space/<room>/dimension/agency_agents/`。
- 不写全局生产区，不写用户 Agent 目录，不自动安装第三方 Agent。
- 每次吸收生成 `agency_agents/catalog.json`，记录来源仓库、文件数、分域、SHA-256 和拒收项。

## 触手模型

一根职业触手由以下五个不可混用的身份组成：

1. `profession`：职业身份，例如 Backend Architect。
2. `tentacle_id`：本次租约的唯一触手编号。
3. `llm_profile`：该职业自己的模型用途标签。
4. `context_namespace`：只属于这根触手的上下文空间。
5. `room_id`：只属于这根触手的镜像多维度房间。

触手不共享可变黑板、不读取其他触手的上下文、不覆盖其他触手的结果。

## 并发纪律

- 同一任务的职业触手可并行，默认最多 8 根，硬上限 32 根。
- 每根触手先创建自己的房间，再进入自己的房间，最后只在自己的房间写 `runs/result.json`。
- 主线程只收集结果摘要，不把一个触手的回复注入另一个触手的会话。
- 统一大模型入口仍是 `gbt_allinone/llm/unified.py`，不允许职业包自行直连模型。
- 模型不可用时返回 `needs_dependency` 或原始错误，不伪造完成。

## 汇总门

职业触手的并发结果只能作为镜像排练材料。进入生产前仍必须经过：

`room_plan → room_simulate → room_parity → room_rehearse → room_release`

涉及生产全局写入时，还必须由主人在终端发放 `deploy_publish` 授权。职业触手无权自授、无权越过 `run_task`、无权直接调用晋升函数。

## 调用面

- `agency_tentacles / status`：查看隔离策略。
- `agency_tentacles / catalog`：读取外部职业目录元数据。
- `agency_tentacles / absorb`：把职业资料复制到指定镜像房间。
- `agency_tentacles / parallel`：在多个独立镜像房间并发调用统一大模型。

## 当前诚实边界

“每根触手自带 LLM”在架构上已实现为独立会话租约和用途标签；是否真的发出模型请求，仍取决于统一模型网关和人工授权状态。当前实现不把多个职业伪装成一个共享会话，也不把外部 Agent 文本冒充已接通的底层工具。

> 开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属
