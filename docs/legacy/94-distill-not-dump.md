# 94 · 蒸馏而不搬运：从 v5 只提炼"契合我们"的东西

> 主人 2026-11-01：「你要吞噬蒸馏提炼出契合我们自己的能力，或者加强现有能力，不是胡乱吞噬哈」

原则（写死，以后照此执行）：

1. **只取方法，不搬实现**：对方 1148 行的通用探针，我们用自己已有的检查器替代；
2. **能加强就不新建**：能改进现有能力位的（如 `energy_core`），不另起一个壳；
3. **重复的不吸**：已有同等能力的（如 `skills_hub` vs 对方 `skill_library`）不重复造；
4. **用不上的不吸**：隐喻类、平台类、别人的测试套，一律拒收并写清理由；
5. **吸完必须有判据**：每条吸收都要有 `tests/test_*.py` 或现有判据覆盖。

---

## 一、吸收了（3 条，全部改造后落地）

### 1) 熔断器 → **加强 `energy_core`**（不新开能力位）

- 来源：v5 `caps/circuit_breaker`（185 行，CLOSED/OPEN/HALF_OPEN 状态机）
- 改造：只取"三态 + 阈值窗口"这一个点，嵌进我们唯一取电口 `energy_core.think()`：
  - 60s 内失败 3 次 ⇒ 跳闸（open），此后 `think()` **秒回 `circuit_open`**，不再白等 300s；
  - 冷却 30s ⇒ `half_open` 放一个探测；成功即闭合（closed）；
  - 状态落 `state/energy-breaker.json`，`energy_core.status()` 带 `breaker` 字段；
  - 新增 `energy_core.run(op='breaker', do='status|reset|trip')` 供排障/演练。
- 实测：`3 次失败 → open`；`think 立即 circuit_open`；`reset → closed`。
- 为什么值得：引擎挂了时 40 个触手不该各等 300s —— 这是**实打实的提速**。

### 2) 病因定位 → 新增 `root_cause`（第 378 位，方法重写）

- 来源：v5 `caps/root_cause_debugger`（1148 行：假设→取证→复现→修复→验证）
- 改造：**不搬那套通用文件探针**，只取"假设 + 证据 + 案卷"三件事，换成**我们自己的**检查器：
  - 7 条假设：能力位三数不一致 / 自检不干净 / 署名缺失 / 根目录异物 / 旧物 / 静默造假 / 最近失败；
  - 每条假设必须挂真调用读数（`cap_self` `selfscan` `signature_guard` `inventory` `legacy_guard` `truth_scan` `orchestration`）；
  - 一条不成立 ⇒ 如实 `inconclusive`（**不猜**）；
  - 每次诊断落 `state/cases/RC-*.json`，可复查。
- 实测：`diagnose` 返回 6 项证据摘要 + 排序假设 + `next_probe`；案卷可列可读。
- 判据：`tests/test_root_cause.py`（4 组 9 条，含"全好时无假设成立"）。

### 3) 唯一执行路径 → 第 377 位 `chain_kernel`（上一轮已落，这里补一句定位）

- 来源：v5 `UNIFIED_PATH.md` + `pipeline.md` + `gates.md`
- 改造：只取"不可跳步 + 每步证据 + 准入准出"，七步链每步调**我们的**能力位取证。
- 判据：`tests/test_chain_kernel.py`（4 组 10 条）。

---

## 二、拒收（以及为什么）

| v5 的东西 | 拒收理由 |
|---|---|
| `skill_library`（806 行，24 项工程技能 spec/plan/build/test…） | **重复**：我们上轮已落 `skills_hub`（22 个 skill + 注册表 + 匹配），再搬一套等于两套做法打架 |
| `quad_brain.md`（推理脑⇄编程脑循环） | **已有等价**：`blueprint → land` 已经是"计划→执行→验证→固化"的闭环，再加一层循环只会绕 |
| `stock_* / stock_browser_trader / fund_pool` | **已有等价**：`quant` / `quant_backtest` / `quant_params`；且交易属危险动作，要过门 |
| `state_space / superposition_planner / waveform_collapse / dimensional_shift / quantum_reasoner` | **隐喻类**：名字很响，实质是把"多候选/概率"换了个量子说法；我们已有 `mirror_*` + `blueprint` 选路，不吸收这类包装 |
| `_2captcha / phishing_engine / keylogger / dns_tunneler / darknet_scanner` | **危险面**：明确的攻击/绕过工具，不进框架；真需要时走技术评估与票 |
| `input_sanitizer`（419 行，SQLi/XSS/路径/命令注入模式库） | **暂不吸**：我们对外输入面目前只有 devour 白名单 + 研究摘录，攻击面小；等接入外部表单/API 再说（先记在 backlog） |
| 62 个对方测试 / npm 插件清单 / 赞助商 / 官网 / 部署 bat | 平台打包件，与 `run_task` 形态无关 |

---

## 三、上一轮批量吞的 20 个 skill：按"用途"分类（不是全都能用）

| 类别 | skill | 在我们这怎么用 |
|---|---|---|
| **流程硬门**（可直接挂 `chain_kernel` 各步） | `brainstorming` `writing-plans` `executing-plans` `verification-before-completion` | Step 0/1/2/3 的"过门标准"引用 |
| **工程方法** | `test-driven-development` `systematic-debugging` `requesting-code-review` `receiving-code-review` | 改代码/排障/评审时的套路 |
| **协作/派工** | `dispatching-parallel-agents` `subagent-driven-development` | 对应 `wf_run` 并行与 `land` 派工 |
| **仓库工作法** | `using-git-worktrees` `finishing-a-development-branch` | 本机没 git 时装 git 之后才用得上（记录为条件可用） |
| **中文口径** | `chinese-code-review` `chinese-commit-conventions` `chinese-documentation` `chinese-git-workflow` | 提交/文档/评审的中文规范 |
| **写 skill / MCP / 引擎** | `writing-skills` `mcp-builder` `workflow-runner` `using-superpowers` | 只作**参考**（我们入口是 `run_task`，不套它们那层插件壳） |

结论：**20 个里真正"能改行为"的是前 13 个；后 7 个是参考件**，已在文档里标明，不假装全都用上。

---

## 四、本次终检

```
energy_core.think() 熔断：3 失败 → open → 秒回 circuit_open → reset 恢复
root_cause：diagnose 出 7 条假设 + 6 项证据摘要；案卷落盘；全好时 inconclusive
chain_kernel：七步不可跳步（上一轮）
cap_self 378 = 378 = 378
```

> 开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属

---

## 五、第二轮（2026-11-01 晚）：从 GBT-JXDWD（Rust 终端版）蒸馏

看的是 `paysssk-creator/GBT-JXDWD`（1919 文件；sandbox 626 / projects 1120 / payment 26）。
它值钱的是两个「防线」文件，不是它那套支付。

### 1) `execution_guard.py`（302 行：六大检测器防"模型劣根性"）
它防的是"模型手写代码"形态下的病：折叠读、edit drift、auto-repaired、compile≠done、
口头证据、批量 edit 无验证。**我们的形态不同（run_task + 账本）**，所以换成账本能证实的四类，
落成第 379 位 `execution_guard`：

| 我们抓的 | 判据 |
|---|---|
| ① 完成无证据 | 写动作（add/edit/fix/deploy/run）的 evidence 是空的/占位的 |
| ② 连续写无验证 | 连续 ≥3 个写动作之间没有任何 scan/verify/test |
| ③ 折叠当完整 | 结果带 `…`/`truncated` 却声称"完成/全绿/OK" |
| ④ 原地打转 | 同一 target 连续两次写、中间无验证 |

- `op=audit {"limit":200}` 出违规清单（high/mid + 修法）；`op=tail` 看最近；`op=status` 默认只看最近 50 条；
- **只审账本可证实的，不脑补动机**；已接进 `chain_kernel` 第 3 步（只记数，不追溯历史）；
- 判据 `tests/test_execution_guard.py`（6 组 10 条）。

### 2) `capability_protocol.py` 的资源护栏（`_apply_resource_limits` / `_kill_process_tree`）
它给能力子进程加超时与资源限制。我们落成 `tentacle/proc_guard.py` 并**接进身体桥**：

| 护栏 | 实现 |
|---|---|
| 超时杀**整棵进程树** | Windows `taskkill /PID <pid> /T /F`（`subprocess.kill()` 会留孤儿） |
| 输出封顶 | `max_chars` 截断并标 `truncated` |
| 环境净化 | 默认剔除 `*_TOKEN` / `*_API_KEY` / `*_SECRET`，只留 PATH 等 |

`body_bridge` 的 `body_*` 与 `body_map` 已改用 `run_capped`；判据 `tests/test_proc_guard.py`（4 组 9 条）。

### 拒收（JXDWD）
- `payment/`（26 文件：网关/分成/自动换币）：危险交易面，与 transfer 票冲突，不吸；
- `projects/` 1120 个业务项目：与框架无关；
- `sandbox/.framework_backups/` 历史备份：旧代码不进仓（我们自己的纪律）。
