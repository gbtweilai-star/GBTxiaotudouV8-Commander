# gbt-distilled-ops · 蒸馏来的四件原生能力

> 主人令（2026-09-28）：「**蒸馏提炼出契合 GBT小土豆V8 的原生能力**」——源是 GitHub 第 39 周爆款周榜的五个项目。
> 开发者：自由的风 · 本署名不可删除、不可篡改归属

## 蒸馏的第一条规矩：**先看家底，只补真缺的核**

从五个源里挑出"我们真没有"的核，**不重复造**已有的东西；抄的是**架构**，代码全部自写，
**一手仓库本轮未联网核验**（不出网），所以不引用它们的性能/规模数字。

| 源（周榜） | 我们缺的核 | 落地成为 | 已有的对位（**不重造**） |
|---|---|---|---|
| #01 **hindsight** | 记忆**来源追踪** + **记忆银行别名/零停机迁移** | `memory_bank` | 记忆读写 → `memory_manager`(FTS5) / `obsidian_vault` / `brain_vault` |
| #05 **paperclip** | **监督循环**（定时检查/重试/唤醒）+ **连接请求审批桥** | `agent_console` | 进程读数 → `task_manager`；门 → `auth_gate` / `cap_tags` |
| #03 **security-audit-skill** | **findings 契约** + **独立验证** + **可复现** + **改动面定向审查** | `code_audit` | 全量面扫描 → `penetrating_cross_scan` 三件套 + `sec_sweeper` |
| #02 **orca** | **一队 coding agent 并行**（worktree 隔离）+ 编队计划/收结果 | `agent_rig` | 四隔离 → `tentacle_fleet`；DAG → `dagrun` |
| #04 **ECC** | —— **不新增** | 见下方对位表 | Skills/记忆/安全/判据 四轴我们都有 |

### ECC（harness 加速包）的已有对位表（**这就是"不新增"的理由**）

| ECC 的四轴 | 我们的对位 | 现读 |
|---|---|---|
| Skills 打磨 | 技能源装唯一真相：`tools/skills_sync.py`（源 `skills/` ↔ 枢纽） | 85 条一致 · 0 分叉 |
| 直觉（快速启发式） | **Jev 快脑**（`gods_eye.op=decide`：确定性打分 + 置信度 + 不硬猜） | 无证据不拍板 |
| 记忆 | `memory_manager` + `obsidian_vault`（235 触手库 ↔ 本体库双向）+ `memory_bank`（新增来源/迁移） | 235/235 |
| 安全 | `penetrating_cross_scan` 三件套 + `sec_sweeper` + Mimosa 写入钩子 + `code_audit`（新增 findings 契约） | 需人核 0 |
| 研究优先 / 更快更稳 | 判据驱动（1000+ 条）+ 开机自检 + `sec_sweeper accelerate` | 覆盖矩阵无死角 |

## 四件的用法与硬规矩

### `memory_bank`（触手 `memory_bank`）
```python
run_task('memory_bank', {'op':'stamp','ref':'state/shortboard.json','origin':'我推的',
                         'session':'s1','why':'日报要用','evidence':'state/shortboard.json'})
run_task('memory_bank', {'op':'trace','ref':'state/shortboard.json'})     # 来源链 + 内容有没有被改过
run_task('memory_bank', {'op':'alias','name':'vault:本体','target':'vaults/lobehub'})
run_task('memory_bank', {'op':'migrate','old':'A','new':'B'})             # 只出计划
run_task('memory_bank', {'op':'migrate_apply','old':'A','new':'B','alias_name':'vault:X'})
```
- `origin` 只能是 `主人令 / 我推的 / 外部抓取 / 上游产物 / 测试夹具 / 未知` —— **来源不许猜**，`why` 必填。
- `trace` 报两件事：**印章在不在** + **现在的 sha 与印章是否一致**（不一致就是"被改过"）。
- 迁移 = **双写 → 逐文件校 sha → 原子切别名 → 失败回滚**；旧目标**只读保留**（本仓没有删除路径）。

### `agent_console`（触手 `agent_console`）
```python
run_task('agent_console', {'op':'add','name':'每晚全量扫描','evidence':'state/coverage_matrix.json','every_s':86400})
run_task('agent_console', {'op':'tick'})       # 判活：读数有没有如期更新（**不是 exit code**）
run_task('agent_console', {'op':'board'})      # 一屏看板
run_task('agent_console', {'op':'request','name':'链A','what':'要连外部模型','scope':'external_llm'})
run_task('agent_console', {'op':'pending'})    # 待主人批
```
- **只监督不擅自执行**：`retry` / `wake` 要 `process_execute` 门；缺票如实拒。
- **审批桥只认主人终端**：`approve` 要求 TTY + 手打 YES ⇒ **AI 批不了**（非交互会话直接拒）。

### `code_audit`（触手 `code_audit`）
```python
run_task('code_audit', {'op':'scan'})                       # 全量面（默认目标 gbt_allinone,tools）
run_task('code_audit', {'op':'scan','rules':'CRED-001'})    # 定向面（只查凭证）
run_task('code_audit', {'op':'diff_audit','base':'HEAD~3'}) # **改动面**（日常该用的就是这条）
run_task('code_audit', {'op':'verify_finding','id':'F-...'})# 独立验证（第二路读法）
run_task('code_audit', {'op':'repro','id':'F-...'})         # 可复制复现命令
```
- **没证据不许开 finding**；高 severity 必须有复现命令。
- **两路读法都命中才算确认**：改动过文件 ⇒ 旧 finding 自动降为 `unverified`（不许当已确认）。
- 命中先分诊：登记豁免 / 占位符 / 测试夹具 / **纯注释提及** / **检测器写法**（把危险词当字面量比较）
  一律不报；**变量目标的删除** 进 `needs_human`（静态判不出指向，不硬报）。
- 口径边界：**全量面天然含框架自家的清理路径**（`rmtree` 暂存目录等）；日常用 `diff_audit`。

### `agent_rig`（触手 `agent_rig`）
```python
run_task('agent_rig', {'op':'agents'})                                      # 盘点可编排的 CLI agent
run_task('agent_rig', {'op':'plan','tasks':'活一;活二;活三','agents_wanted':'codex,claude'})
run_task('agent_rig', {'op':'dispatch','plan_id':'rig-...','start':True})   # 要 process_execute 门
run_task('agent_rig', {'op':'collect','plan_id':'rig-...'})                 # 从各份 worktree 收改动
```
- 每份一个 **worktree + 端口段 + 隔离 HOME + 独立日志**（口径抄 `tentacle_fleet`，不另立一套）。
- **任务只进文件（`TASK.txt`）、不进命令行**；不把命令交给 shell。
- 不代持账号、不批量注册：跑的是**主人已装好并已授权**的 CLI。

## 判据与自检

- `gbt_allinone/tests/test_distilled_ops.py`：13 条（含**反向自检**：内容被改必报 · 别名成环必报 ·
  迁移 sha 不符必回滚 · AI 批不了连接请求 · 缺票不起编队 · 改文件后 finding 必变 unverified · 探针无读数必报不可用）。
- 新增即绑：四件都走过 `tools/binding_hook.py after-add`（六条腿全绿），并在 `vaults/<触手>/` 各有一页永久记忆。

## 这轮抓到的自己的错（写下来免得重犯）

1. **扫描器互相自报**：`code_audit` / `agent_rig` 的规则表与自检里必然出现危险字面量 ⇒ 被安全钩子与自己的判据判红。
   解法：模式串用**括号类**（`ev[ae]l`）或**运行时构造的正则**，源码里不复现危险字面量。
2. **假样本要只错一侧**：迁移回滚判据第一版让**两侧**都返回同一个错值 ⇒ 相等 ⇒ 判不出不一致。
   "喂坏样本"时必须确保**坏在哪一侧**是明确的。
3. **精度是审计器的命**：`regex.exec(` 不是动态执行；`DROP TABLE IF EXISTS` 不是破坏；`rmtree` 目标是不是临时目录——静态判不出。
   ⇒ 宁可进 `needs_human`，也不硬报；**报告不能落地就没人看**。
