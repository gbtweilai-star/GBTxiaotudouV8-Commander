---
name: gbt-command
displayName: GBT · 指挥手册（派活 → 验收，7 类指挥动作 · 非 LLM 验收）
version: 1.0.0
description: GBT小土豆V8 的「指挥」用法规程：把人当指挥者、把 AI/触手当手，按七类指挥动作（切活/派活/交接/验收/升级/停手/复盘）下活，且**验收一律用非 LLM 判据**。给出两条真口的可复制命令：派活口 `wf_define` + `wf_run`（DAG、模板注入、分层并行、断点续跑），验收口 `lr_submit` + `lr_tick`（判据词表 status_ok / contains:<kw> / file_exists:<path> / no_error，未知判据 fail-closed，重试到 3 次后 failed 或 stalled）。当用户要派活给 AI/触手干活、要定"什么算干完"、要验收一份产物、要判断失败该重试还是升级、要停下来问主人、或要复盘记账时使用。蒸馏来源 msitarzewski/agency-agents（现查 158292 星），逐条出处见 docs/AI指挥手册-蒸馏.md。
triggers:
  - "指挥"
  - "派活"
  - "派单"
  - "验收"
  - "什么算干完"
  - "判据"
  - "非LLM验收"
  - "交接"
  - "升级"
  - "停手"
  - "复盘"
  - "wf_define"
  - "wf_run"
  - "lr_submit"
  - "lr_tick"
---

# gbt-command · 指挥手册（派活 → 验收）

> 开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属
>
> **口径（主人令 2026-10-08）**：GBT小土豆V8 是**站在人类角度的指挥者**，AI/触手是**干活的手**。
> 本 skill 只讲**指挥**：怎么派活、怎么交接、怎么验收、怎么升级、怎么停手、怎么复盘。

---

## 0. 铁律（先看这条，再看别的）

**凡"让干活的模型自己说干完了"的写法，一律不合格。**

每条判据定完先反问一句：

> **这个判据能不能用不长嘴的东西算出来？**
> 能（文件存在 / 非空 / 哈希一致 / 读数一致 / 帧差非零 / 谓词返回真）⇒ 达标；
> 不能（"我干完了" / "应该没问题" / "看起来对"）⇒ **回炉，别派活**。

**血账（本仓真实事故，必须记住）**：曾用「文件存在且 >1MB」当成功判据 ⇒ ffmpeg 失败时，
把**昨晚的旧片**认证成新片并盖上新指纹。**假绿比错更贵**：它把错误变成了"已验收"。
⇒ 判据必须能区分「**这次真做了**」与「**上次的还在**」。

---

## 1. 派活口：`wf_define` + `wf_run`

**入口**（仓根执行）：

```bash
# 定义（DAG 可以走文件：只认仓内 state/ 下的相对路径）
py -3.14 -m gbt_allinone run wf_define '{"file":"state/<你的dag>.json"}'

# 执行（分层并行；fail_fast 默认 True）
py -3.14 -m gbt_allinone run wf_run '{"name":"<工作流名>"}'

# 查记录 / 断点续跑
py -3.14 -m gbt_allinone run wf_status '{"name":"<工作流名>"}'
py -3.14 -m gbt_allinone run wf_resume '{"run_id":"<run_id>"}'
```

**DAG 形状**：

```json
{"name": "cmd-demo-dispatch-accept",
 "nodes": [
   {"id": "deliver",  "kind": "<能力位>", "params": {"...": "..."}},
   {"id": "readback", "kind": "<能力位>", "depends_on": ["deliver"],
    "params": {"...": "{{deliver.<字段路径>}}"}}
 ]}
```

**派活用得上的节点级武器**（都在 `gbt_allinone/engine.py`）：

| 武器 | 干什么 | 派活时怎么用 |
|---|---|---|
| `{{node.field.path}}` | 上游输出注入下游参数（整串保类型） | **这就是"不冷启动"**：下一棒的输入直接吃上一棒的产物 |
| `{{*}}` / `{{*.path}}` | 扇入聚合全部上游 | 多路汇总时用 |
| `depends_on` | 拓扑分层 | 无依赖的同层**并行**；有依赖的等上游过 |
| `fail_fast`（默认 True） | 任一节点失败即停 | **不许改成 False 去"跑完整看看"** |
| `max_node_retries`（默认 0） | 节点重试 | 机械失败（网络/锁）才开；判据不成立别重试 |
| `retry_backoff` | 重试退避秒数 | 同上 |
| `when` | 条件执行（AST 白名单，禁函数调用） | 不满足则**跳过，不算失败**——**别拿它当验收** |
| `fallback` | 主能力最终失败时走备选 | 降级要留 `gbt_fallback` 标记 |
| `routes` | 条件分流（switch 语义） | 按上游读数选分支 |
| `timeout` | 节点超时秒数 | **无人值守必须给** |
| `cache` / `cache_ttl` | 同 (kind, 参数指纹) 命中即复用 | 重跑不重算 |

**派活纪律**：
- 节点 = **一步一产物**。一个节点塞两件事 ⇒ 切错了。
- 参数里**不写**"尽量/大约/看着办"；阈值写数字。
- `when` 只用来**跳过**，**不用来验收**（跳过不是失败 ⇒ 用它验收会造出假绿）。

---

## 2. 验收口：`lr_submit` + `lr_tick`（**非 LLM 判据**）

**判据词表只有这四个**（`gbt_allinone/longrun.py:_judge`）：

| 判据 | 语义 |
|---|---|
| `status_ok` | 执行状态 == ok |
| `contains:<关键词>` | 结果 JSON 里含该词（大小写不敏感） |
| `file_exists:<路径>` | 该路径存在（**abs 或 os.path.exists 认的相对路径**） |
| `no_error` | 结果不含错误 |

**别的词一律判失败**（`未知验收标准: <c>`）——**fail-closed，这是特性不是缺陷**。

```bash
# 提交：acceptance 就是判据列表；max_attempts 缺省 3
py -3.14 -m gbt_allinone run lr_submit \
  '{"description":"<做什么>","kind":"<能力位>","params":{...},
    "acceptance":["status_ok","file_exists:<真路径>","contains:<关键词>"]}'

# 推进（执行 → 验收 → 完成/重试/停滞）
py -3.14 -m gbt_allinone run lr_tick '{"max_tasks":3}'

# 查进度
py -3.14 -m gbt_allinone run lr_status '{}'
```

**读数怎么读**（`lr_tick` 每行给 `{task_id, status, attempts, why}`）：

| `status` | 含义 | 指挥动作 |
|---|---|---|
| `done` | 全部验收标准满足 | 进下一棒 |
| `pending` | 判不过、**还有重试额度** | 等或补信息（**别重复喂同样的输入**——那是同因复读） |
| `failed` | 重试耗尽（判据明确不成立） | **升级**（换手 / 分解 / 改路线 / 带限制接受 / 延期） |
| `stalled` | 重试耗尽（同因空转，无新信息） | **升级给人**（别续烧） |

**已实测原文读数**（2026-10-08）：

```
{'task_id': 'T0059', 'status': 'done',    'attempts': 1, 'why': '全部验收标准满足'}
{'task_id': 'T0060', 'status': 'failed',  'attempts': 3, 'why': '文件不存在: .../NO-SUCH-FILE.txt'}
{'task_id': 'T0061', 'status': 'stalled', 'attempts': 3, 'why': '未知验收标准: some_unknown_criterion'}
```

⇒ 一次证明三件事：**判据真判** · **判不过会重试到顶** · **未知判据 fail-closed 且单列 `stalled`**。

---

## 3. 有"产出即自证"的能力位，优先用它（判据不用自己造）

有些能力位**自己就带非 LLM 自证**，派活时直接吃它的回读字段：

| 能力位 | 自证字段 | 为什么是硬判据 |
|---|---|---|
| `create`（`op=write`） | `verify_new_sha` · `verify_backup_sha` · `idempotent` | **写后从磁盘读回逐字节比对**（`file_operation.py:515-525`）；`idempotent=True` = 再读一次盘、字节完全相同 ⇒ 证明"这次真做了" |
| `filmgrade.deliver_check` | `level` / 关键帧间隔（按秒）/ 音轨 codec | 回读产物确认，不看脚本自证 |
| `audio_extract` | ffprobe 回读读数 | 产出即验证 |

**示例（本轮实测跑通的派活 DAG）**：节点 `deliver` 用 `create` 写文件，节点 `readback` 再用同样内容写一次
⇒ `idempotent: True` 就是"盘上内容和预期逐字节一致"的机械证明。
原文读数：`deliver {'bytes':66,'sha256':'e7d790bf…','wrote':True,'verify_new_sha':True}` · `readback {'wrote':False,'idempotent':True}`。

---

## 4. 交接：递什么、留什么

| 递什么 | 怎么递 |
|---|---|
| **上游产物** | `{{node.field.path}}` 注入下游参数 ⇒ 下游**不冷启动** |
| **这次做了什么** | 落 `store/wf_runs/<run_id>.json`（逐节点 status/results/耗时） |
| **判过/判不过** | `lr_tick` 的 `why` + `attempts`（逐次可读） |
| **账** | `state/logbook.jsonl`（只追加 + 自链哈希）· `store/audit.jsonl` |

```bash
py -3.14 tools/codex-scripts/logbook.py append --kind <类> --what "<做了什么>" --actor <谁>
```

**交接不许**：让下游自己去猜上游干了什么；把"待补"占位留在派单里（那是冷启动）。

---

## 5. 升级：失败怎么走

```
判不过
 ├── 还有额度（attempts < 3）⇒ 带**新信息**重试（同因复读 = 假修复）
 └── 额度用尽
      ├── failed（判据明确不成立）⇒ 升级：换手 / 分解 / 改路线 / 带限制接受 / 延期
      └── stalled（同因空转）      ⇒ 停手，报人
```

**升级件必须带**（我们的现状：这一条**还缺**，见 `docs/AI指挥手册-蒸馏.md` §3.1）：
失败史（逐次：发现什么 / 改了什么 / 为何还挂）· 根因 · **五选项** · 影响面 · **决策人与期限**。

---

## 6. 停手：这些情况必须停下来问主人

| 情况 | 为什么 | 现状落点 |
|---|---|---|
| **不可逆动作**（发布/上线/删除） | 自动化的终点站是**人的门** | `media_publish.submit` **恒 blocked**（零出网、绝不返回"已发布"） |
| **要凭据** | 凭据不代持；只从环境变量/密钥服务读 | `key_gateway`（返回值永不含明文） |
| **碰生产面** | 生产零修改、一次性晋升 | `mirror_rehearse` → `mirror_ascend`（**失败即阻断**） |
| **超预算/超时** | 无人值守必须有硬限时 | 节点 `timeout`（**总时限阀目前缺**） |
| **无授权的写** | 绕过关卡的成功 = 事故 | `filesystem_write` 门（授权只能主人发） |

---

## 7. 复盘：把这次经验写回记忆

每轮收工至少做两条：
1. **记一行账**：`py -3.14 tools/codex-scripts/logbook.py append --kind … --what … --actor …`
2. **固化新判据**：每踩一坑，坑变判据（**一坑不踩两次**）——新判据必须**在该坑重演时报红**。

**要看的数**（来自台账、可复算，不是回忆）：首次判过率 / 平均重试次数 / 完成比 / `lr_status` 的 `progress`。

---

## 8. 七类指挥动作速查（四元组）

| 类 | 一句话 | 我们的位 |
|---|---|---|
| **切活** | 一步一产物、一个判据能判完；跨阶段或判据要靠人解释 = 切错了 | `wf_define` 节点粒度 · `lr_submit` 一任务 |
| **派活** | 派单带：目标 + 边界 + 产物 + **可机检判据**；不写模糊词、不写复合动作 | `wf_define(params)` · `lr_submit(acceptance)` |
| **交接** | 递产物 + 递上下文（`{{node.field}}`）+ 递判过/判不过；**不冷启动** | 模板注入 · `wf_runs` · `logbook` |
| **验收** | **非 LLM 判据**；验收方 ≠ 产出方；判据要有牙 | `lr_submit(acceptance)` · `lr_tick(_judge)` |
| **升级** | 3 次到顶；`failed` 走五选项、`stalled` 停手报人；不续烧 | `lr_tick` 的 `failed` / `stalled` |
| **停手** | 不可逆 / 要凭据 / 碰生产 / 超预算 ⇒ 停下问主人 | 授权门 · `media_publish` · `mirror_*` |
| **复盘** | 记一行账 + 固化一条判据（一坑不踩两次） | `logbook.py` · `audit.jsonl` |

---

> 完整四元组逐条（32 条，带出处与行号）见 `docs/AI指挥手册-蒸馏.md`；
> 机器可读台账见 `state/command-playbook.json`。
