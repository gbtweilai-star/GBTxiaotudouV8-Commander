# EigenFlux 审计通道设计（G1 · 独立事件通道）

> 性质：**设计稿**。本文件只出稿，不动手——不动任何生产代码、不建任何目录、不写任何 store 数据、不起任何 GUI。
> 依据：风哥 2026-09-17 批文（原文引用见 §0.1）；取证日期 2026-09-17，方式 = 全仓只读扫描 + 逐函数行号核对。
> 排期：本次**不排**施工序；开工时机 = 本稿复核通过之后。
> 本文件不含任何"已完成 / 可上线"结论。当前事实：**EigenFlux 链路全程零审计、零生命档案，`store/health/eigenflux/` 目录不存在。**

---

## §0 先摆三条待拍（都在"名字与口径"层，不在实现层）

### 0.1 依据原文（不许走样）

风哥批文（R54 · D2）原文：

> D2 · 审计通道 → 独立通道，不混主账本
> 落 `store/health/eigenflux/*.jsonl`
> 附：出站/入站/发送三类必须分事件名（`eigenflux_emit` / `eigenflux_recv` / `eigenflux_send`）

本稿**采这三个名字，一个不改、一个不加**。

**同时作废我上一版草稿的六个名字**（`eigenflux_polled` / `eigenflux_inbound` / `eigenflux_drafted` /
`eigenflux_sent` / `eigenflux_blocked` / `eigenflux_error`，见《EigenFlux 集成设计.md》§3.3(d)）。
不留两条打架的口径——新旧对照见 §3.2。

### 0.2 待拍 ①：`emit`（出站）与 `send`（发送）的分工

你给的三类里，"出站"与"发送"字面重叠。我按下面这套分工写；**如果你本意不是这套，先改本稿再动代码**。

| 事件名 | 本稿采用的语义 | 什么时候写 |
|---|---|---|
| `eigenflux_recv` | **入站事实**：本轮真的从网络取回了东西 | `feed poll` / `msg fetch` / `relation friends` / `profile show` 成功返回时 |
| `eigenflux_emit` | **出站意图**：一条内容准备对外发、被双闸门裁决的**那一刻** | 闸门放行（`allow`）或被拦（`block`）时 |
| `eigenflux_send` | **出站结果**：CLI 真被调用、拿到了返回 | `msg send` 返回之后（成功失败都写） |

为什么这么切：**意图与结果分开**，才查得出"想过要说、没说成"（有 `emit` 无 `send`）。
若你要的是按**内容类型**切（例如广播类出站 = `emit` / 私信类出站 = `send`），我照改——
但那会让"同一动作落几个事件"变成按内容类型判断，判据复杂一档。

### 0.3 待拍 ②：`store/health/` 能不能新立 eigenflux 的字段

既有口径（风哥 2026-09-17 拍）：`store/health/` **保留期对齐 §0.3，不另立期限、不新立 schema**。

我的理解：那句管的是**保留策略**（不另立期限）；**字段**沿 W2.5 健康面现成范式（`ts` / `result` / `detail` / `ttl_s`）
再加本域业务字段。**若你要"一个字都不许新立"**，我就退到纯 W2.5 字段集（业务信息塞进 `detail`）——说一声即可，我不猜。

### 0.4 待拍 ③：轮询心跳要不要逐条落档

`poll_interval_s=300` → 每轮 1 条 = **288 条/天**；30 天热层 ≈ **8,640 条**纯噪音。

我的提案：**不逐条落**。有变化（新动态 / 新私信）才落 `eigenflux_recv`；无变化的轮询只更新
`eigenflux_state.json` 的 `last_sync_at`（那是**状态文件**，不是账）。
与你在《EigenFlux 集成设计》§3.3(c) 拍的「轮询心跳 / 无变化 → 不落」同口径——本稿只是把它落到通道层。

---

## §1 定性：这个通道是什么、不是什么

| 是 | 不是 |
|---|---|
| EigenFlux 功能域的**独立事件通道**（append-only JSONL） | 主账本 `store/audit.jsonl`（**不混**） |
| 高频、**可丢**、只做排障与事后可查 | 生命档案 `life_archive`（**另批**，D2c 第二步） |
| UI 的**次要**数据源 | UI 的主数据源（UI 读 `eigenflux_state.json`） |
| 事件记录（无退出码） | 探针（探针才有 `rc=0/20/21/22`） |

一条口径先钉死：**健康快照是数据，故障事件是账。**
（出自《GBT全故障点设计.md》对 `store/health/` 与 `store/audit.jsonl` 的分界。）
所以：**通道写不进去 = 故障事件 → 走主账本**；**通道里的一条正常记录 = 数据 → 走 health**。

---

## §2 现状取证（每条可复算）

| # | 事实 | 证据 |
|---|---|---|
| 1 | EigenFlux 全链**零审计** | `potato_pet/eigenflux_bridge.py` 内 `store.audit` / `audit(` **0 命中**；`life_archive` / `mind_engine` **0 命中** |
| 2 | **`_run()` 是唯一出网收口** | `potato_pet/eigenflux_client.py` 全文件 `subprocess.run` **仅 1 处**（`:109`，在 `_run()` 内）；`_run(` 调用点 **5 处**：`:164` feed · `:194` messages · `:220` friends · `:246` profile · `:317` send_message |
| 3 | CLI 形态**只有 5 种** | `feed poll` · `msg fetch` · `msg send` · `relation friends` · `profile show` |
| 4 | 入站是**并发**的 | `refresh()`（`:264`）用 `ThreadPoolExecutor(max_workers=4)` 同时打 4 路 → 通道写入必须**线程安全** |
| 5 | 出站有**两扇门** | `holo_pet/panel_server.py::eigenflux()`（`:839`，7 组 op）与 `potato_pet/eigenflux_bridge.py` 的 `_send_worker()`（`:129`）/ `_auto_reply()`（`:138`） |
| 6 | 面板已有审计口，但**通主账本** | `panel_server.py::_panel_audit()`（`:154`）→ `store.audit("panel_" + event)`。**本通道不复用它**（复用就等于混账） |
| 7 | 现成健康面范式 | `store/health/main_console.jsonl`（**648 B / 2 行**）：`ts` / `probe` / `target` / `result` / `detail` / `latency_ms` / **`ttl_s`** |
| 8 | 目标目录**不存在** | `store/health/` 下只有 `main_console.jsonl` 1 个文件；`store/health/eigenflux/` **不存在**（本稿只登记，不建目录） |
| 9 | 写盘原语现成 | `gbt_allinone/safe_io.py:109 locked_append_text()`：跨进程文件锁 + `fsync`，JSONL 行不会交错或半落盘 |
| 10 | 保留策略现成 | 《GBT全故障点设计.md》§0.3：热 **30 天** / 冷 **365 天** / 指纹**永久** |

---

## §3 事件名与语义

### 3.1 三个事件（采风哥口径）

| 事件名 | 方向 | 写入时机 | 必填业务字段 | 建议 `ttl_s` |
|---|---|---|---|---|
| `eigenflux_recv` | 入站 | 5 种 CLI 里**读类**返回成功且**内容有变化**时 | `source`（feed/messages/friends/profile）· `items` · `hashes[]` | 900 |
| `eigenflux_emit` | 出站意图 | 双闸门裁决那一刻 | `decision`（`allow` / `block`）· `reason` · `content_sha256` · `content_chars` | 600 |
| `eigenflux_send` | 出站结果 | `msg send` 返回后（成功失败都写） | `op_id` · `ok` · `code` · `error` · `latency_ms` | 600 |

### 3.2 新旧对照（旧建议作废，不再出现）

| 旧名（作废） | 去向 |
|---|---|
| `eigenflux_polled` | **取消**（走 §0.4：无变化不落；有变化落 `eigenflux_recv`） |
| `eigenflux_inbound` | → `eigenflux_recv` |
| `eigenflux_drafted` | → `eigenflux_emit`（`decision=allow`，草稿生成那一刻） |
| `eigenflux_sent` | → `eigenflux_send` |
| `eigenflux_blocked` | → `eigenflux_emit`（`decision=block`，**不新立名字**） |
| `eigenflux_error` | → `eigenflux_send`（`ok=false`，`error` 原文进 `detail`） |

**一条硬约束**：同一个动作**只许落一个事件名**。落两个 = 计数重复 = 自己把自己的账做花。

---

## §4 记录 schema

```json
{"ts":"2026-09-17T18:40:12","event":"eigenflux_send","seq":12,
 "op_id":"9f2c…","target":"msg send","result":"ok","detail":"",
 "content_sha256":"ab12…","content_chars":86,"redactions":{"url":0,"path":0},
 "latency_ms":842,"ttl_s":600}
```

| 字段 | 必填 | 说明 |
|---|---|---|
| `ts` | ✅ | ISO 本地时间（沿 W2.5） |
| `event` | ✅ | 三名之一，**枚举校验**，写错名字直接报错 |
| `seq` | ✅ | 该文件内自增（进程内锁保护；跨进程靠 `locked_append_text`） |
| `op_id` | ✅（emit / send） | UUID4，**`emit` 与 `send` 用同一个**，用于两段式配对 |
| `target` | ✅ | CLI 形态（`feed poll` / `msg send` …），**不带路径、不带参数值** |
| `result` | ✅ | `ok` / `fail`（沿 W2.5） |
| `detail` | ✅ | 失败原因**原文**（**不许 `except: pass` 吞掉**） |
| `content_sha256` | 出站必填 | 内容指纹 |
| `content_chars` | 出站必填 | 内容长度 |
| `redactions` | 可选 | 脱敏计数（`redact_text` 产出） |
| `latency_ms` | ✅ | 该次 CLI 调用耗时 |
| `ttl_s` | ✅ | 本记录有效期（**判据，不是装饰**） |

**两条脱敏红线**：

1. **内容原文永不入档**——只落 `content_sha256` + `content_chars` + 脱敏计数；要和 UI 对上时用 hash 反查，不靠人眼比对原文。
2. **他人内容只落摘要级指纹**——私信 / 好友动态属**他人隐私**，本通道也不存原文。
   这比 D2c 第二步的生命档案口径**更保守**：第一步就先按最严的来（**放开容易，收紧难**）。

---

## §5 写点清单（最小面积：1 + 2，共 3 处）

| # | 文件 · 函数 | 落事件 | 为什么在这 |
|---|---|---|---|
| 1 | `potato_pet/eigenflux_client.py::_run()`（`:98`） | `recv`（读类）/ `send`（写类） | **唯一出网收口**：`args`、耗时、`code`、`error` 都在它手里 |
| 2 | `potato_pet/eigenflux_bridge.py::_auto_reply()`（`:138`） | `emit` | 决策层：**这是"她决定要说的话"**，形状闸门 `public_text_guard`（`:166`）就在它上面 |
| 3 | `potato_pet/eigenflux_bridge.py::_send_worker()`（`:129`） | `emit` | 用户手动发也是出站意图，同口径 |

**为什么面板 `eigenflux()`（`panel_server.py:839`）不直接写**：它调的 op 最终都落在 `client`，写在那儿会**双写**。
一句话原则：**事件跟"事实发生的地方"走，不跟"UI 请求的地方"走。**

**分类表（`_run()` 内的 `args[:2]` → 事件）**：

| `args[:2]` | 事件 |
|---|---|
| `("feed","poll")` · `("msg","fetch")` · `("relation","friends")` · `("profile","show")` | `eigenflux_recv` |
| `("msg","send")` | `eigenflux_send` |
| 其它（将来新增子命令） | **不静默放过**：落 `recv` 且 `detail="unknown cli form"`，并**报红**（新形态必须有人拍） |

---

## §6 假绿防线（这一节决定通道能不能信）

### 6.1 两段式：先把"要说"写下来，再把"说了"写下来

```
emit(allow, op_id)  →  CLI msg send  →  send(op_id, ok=…)
```

崩在中间 → 有 `emit` 无 `send` → **可诊断**（"她想过要说，没发成"），不是静默丢账。

### 6.2 写不进去，就不许发

`eigenflux_audit()` **返回 bool**（照 `_panel_audit()` 的约定，`panel_server.py:154`）。
`emit` 写失败 → **出站动作中止**，并把这条失败当**故障事件**写主账本 `store/audit.jsonl`（依据 §1 口径）。
一句话：**没有这条账，就不许发。**

### 6.3 `ttl_s` 是判据

读方（上帝视角 / 面板）拿到最后一条记录，若 `now - ts > ttl_s` → **显示灰**，不许显示绿。
探针停了、轮询停了、文件写不进去——真值都是"没人看着"，而**没人看着不等于健康**（W2.5 §3.4 原口径）。

### 6.4 不许静默

- 写盘异常 → 异常类型 + 原文前 200 字写进 `detail`；
- 通道不可用 → 返回 `False`，调用方**必须处理**（中止 / 报红），**不许 `except: pass`**；
- 通道自身的健康 → 由**主账本**里那一类故障事件体现（**不自己给自己写健康**）。

---

## §7 文件布局、保留与轮转

| 项 | 口径 |
|---|---|
| 目录 | `store/health/eigenflux/`（本稿只登记，**不建**） |
| 文件 | **按天切段**：`eigenflux-YYYYMMDD.jsonl`——单文件不会无限长，删一天不影响其它天 |
| 保留 | **对齐 §0.3**：热 30 天 / 冷 365 天 / 指纹永久，**不另立期限** |
| 删除 | **默认不自动删**（与阶段检查点同口径：策略先定，执行器另批） |
| 清理 | 手动清理要**连 `.lock` 一起删**（W2.5 README 同款注意事项） |
| 量级 | 有变化才落 → 估 **< 100 条/天**（**估算不是实测**，落地后按首周实数回填） |

---

## §8 契约测试（正负对照必须给出不同结果）

| # | 造法 | 必须看到 |
|---|---|---|
| T1 | 正对照：mock client，用户手动发一条 | **1 条 `emit`(allow) + 1 条 `send`(ok)**，且 `op_id` 相同 |
| T2 | 负对照 A：内容带 Windows 路径（过不了形状闸门） | **1 条 `emit`(block) + 0 条 `send`** |
| T3 | 负对照 B：CLI 返回 `code != 0` | **1 条 `emit`(allow) + 1 条 `send`(ok=false)**，`detail` 有原文 |
| T4 | 判别性 | T1 / T2 / T3 的**事件序列互不相同**；任两组相同 → 报 `SCANNER_BLIND`，**不许报 PASS** |
| T5 | 不混账 | 跑完断言**主账本 `store/audit.jsonl` 增量 0 B** |
| T6 | 隔离 | 全程 `GBT_STORE_DIR` 指隔离目录；跑完断言**生产 store 逐字节不变** |
| T7 | 两段式 | 让 `send` 阶段抛异常 → **`emit` 在、`send` 缺** → 读方能报"有意图无结果" |

---

## §9 边界（本通道不碰什么）

- **不碰主账本**：`store/audit.jsonl` 只收**故障事件**（§1 口径），不收正常事件。
- **不碰生命档案**：`life_archive` 分级是 **D2c 第二步**，单独批。
- **不碰 UI**：不做数据源；UI 读 `eigenflux_state.json`。
- **不碰凭据**：不读 `credentials.json`，不落 token / appSecret / 路径。
- **不碰自动回复开关**：D1 已单独落地（config + 默认值双关）。
- **不建常驻采集器**：没有消费者之前不建生产者（《反空壳律》）。

---

## §10 施工序与红线

**施工序**（本稿复核通过后才动）：

1. 本稿复核 → 报风哥拍 §0 三条
2. 动刀：`eigenflux_client.py` 1 处（`_run`）+ `eigenflux_bridge.py` 2 处（`_auto_reply` / `_send_worker`）
3. 契约测试 7 条（§8）
4. 隔离验证：`GBT_STORE_DIR` 跑全套 → 生产零写入复核 → 报风哥
5. **S7 单独批**（老规矩）

**红线**：

- 内容原文**永不入档**（只 hash + 长度 + 脱敏计数）
- **不混主账本**；故障事件才走 `audit.jsonl`
- **写失败即中止出站**（没有这条账，就不许发）
- 不许 `except: pass` 吞掉写盘错误
- 同一动作**只落一个事件名**
- 跑测试必须 `GBT_STORE_DIR` 隔离
- **S7 单独批** · 宿主规矩照旧（串行、无并发、跑完即停）

---

## §11 本稿不做的事（先写下来，免得将来变成"应该做而没做"）

- 不建目录、不写文件、不动任何生产代码（**本稿只出稿**）
- 不做轮转删除器（保留策略先定，执行器后议）
- 不做 UI 消费端
- 不做生命档案分级落档（D2c 第二步）
- 不做"轮询去重"的持久化索引（第一步靠 `last_sync_at` + hash 列表够用，真不够再加）

---

> 开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属
