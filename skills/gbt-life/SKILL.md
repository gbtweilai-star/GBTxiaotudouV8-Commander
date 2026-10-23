---
name: gbt-life
displayName: GBT · life 职业域用法规程（1 个能力位：life）
version: 1.0.0
description: GBT小土豆V8 的 `life` 职业域（生命档案 / 事件记录 / 时光轴 / 每日回顾 / 章节 / 承诺 / 习惯 / 反思 / Vault 导出）用法规程。这个域**只有 1 个能力位**：`life`。本文件把它写全：用途、13 个 op 逐个标只读还是写盘、逐 op 静态查出来的作用域（读一律零作用域，写一律 filesystem_write，且写藏在 action/参数里）、真命令、落点（store/life/events.jsonl · state.json · life.lock · store/life_vault）、失败典型样子、与 `gbt-mind`（同样写框架 store 却零作用域）的边界；并记下本机实测到的读数陷阱（空参 `cap life` 就是 status 不会报错；`{"action":"create"}` 会被当成 op 而不是 chapter 的 action ⇒ user_error；`recall` / `today` 的 count:0 是真没命中不是坏了；`graph` 的 limit 是事件上限不是节点数）。当用户要记录经历 / 查时光轴 / 看今天的档 / 回忆某事 / 反思复盘 / 管理章节承诺习惯 / 导出 Vault，或 life 调用报"未知 life op"、报"需要人工授权（filesystem_write）"时使用。
triggers:
  - "生命档案"
  - "记录经历"
  - "时光轴"
  - "今天做了什么"
  - "每日回顾"
  - "回忆"
  - "反思"
  - "复盘"
  - "章节"
  - "承诺"
  - "习惯"
  - "Vault"
  - "obsidian"
  - "life"
  - "未知 life op"
  - "filesystem_write"
---

# GBT · life 职业域用法规程（1 个能力位：`life`）

> 开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属
>
> **这份规程解决什么**：`life` 是一个**一位一域**的小域，但它一个人身上挂了**十三个 op**，
> 而且**只读与写盘混在同一张 op 表里**：同一个位的 `timeline` 免卡、`record` 要 `filesystem_write`，
> 还有一条**半开**的（`reflect` 不带 `save` 免卡、带 `save:true` 要门），
> 更有三条**把动作藏在 `action` 里**的（`chapter` / `commitment` / `habit`：`list` 免卡、别的要门）。
> 本文件把「哪个 op、要不要授权、失败长什么样、读数该看哪个字段」逐个钉死，
> 并把**本机实测过的坑**如实记下来 —— **没验过的一律写"未验"，不冒充验过**。

**唯一现读入口（别信任何二手描述，包括本文件）**：

```powershell
py -3.14 tools/codex-scripts/five-dim.py cap life ['<JSON载荷>'] [--full]
```

`cap` 一律走 `gbt_allinone.run_task`（**唯一门**）；被门拒绝就**如实报缺什么作用域**，不绕路。

---

## 0. 一位一域（先确认名字，别照抄别人的表）

现扫 `state/skill_atlas.json`（`domain == "life"`）**只有一条**：

| 域 | 能力位（kind） | handler | 注册表 desc 原文 |
|---|---|---|---|
| `life` | **`life`** | `life` | "生命档案：事件记录、时光轴、每日回顾、章节、承诺、习惯、反思与 Vault 导出（写框架 store，不出网）" |

> **件名 = 域级 `gbt-life`，能力位 kind = `life`，两者同名段**。
> ⚠️ 写规程时的坑：`gbt-life` 里的 `life` **前面带连字符**，在"单词边界"判据下**不算命中**，
> 必须让 `life` 单独出现（本文件里到处都是）。
> 注册表 `requires_params=[]` · `params_hint=""` · `needs_confirmation=false` · `safe=true`
> ⇒ 空载荷调用**合法**（落到只读 `status`，见 §6.1）。

---

## 1. 什么时候用（意图 → 落点）

| 人想干什么 | 落到哪个 op | 只读还是要授权 |
|---|---|---|
| 看档案活着没、有多少条、上次导出什么时候 | `status`（**空载荷默认就是它**） | 只读，零作用域 |
| 记一条经历 | `record`（兼 `event` / `remember`） | 🔒 `filesystem_write` |
| 翻时间线 | `timeline` | 只读，零作用域 |
| 看某一天（构造当日视图，**不落盘**） | `today`（兼 `day`） | 只读，零作用域 |
| 导出 Obsidian Vault（并把日期挂上） | `daily` | 🔒 `filesystem_write` |
| 全文回忆 | `recall` | 只读，零作用域 |
| 看关系图 | `graph` | 只读，零作用域 |
| 出一份周期复盘 | `reflect`（不带 `save`） | 只读，零作用域 |
| 出一份周期复盘**并落盘** | `reflect` + `save:true` | 🔒 `filesystem_write` |
| 列/管章节 | `chapter` + `action` | `action` 是 `""`/`list`/`status` ⇒ 只读；**其它一律** 🔒 |
| 列/管承诺 | `commitment` + `action` | 同上 |
| 列/管习惯 | `habit` + `action` | 同上 |
| 导出 Vault | `export`（兼 `export_obsidian` / `vault`） | 🔒 `filesystem_write` |
| 收敛外部来源进档案 | `ingest`（兼 `import_sources` / `sync_sources`） | 🔒 `filesystem_write` |

**不在这 1 个位里的事**：心智预演/评估/内部状态 → `gbt-mind`（`mind` 域，9 位，**全零作用域**）；
项目上下文 → `gbt-project`；屏幕/点击 → `gbt-tentacle`。

---

## 2. 🔴 要过哪道门：**逐 op 静态查，不靠跑它才知道**

```python
from gbt_allinone.security import policy
policy.evaluate("life", {"op": "record"}).scopes          # → ('filesystem_write',)
policy.evaluate("life", {"op": "timeline"}).scopes        # → ()
```

**唯一权威**是 `gbt_allinone/security/policy.py` 的 `evaluate()` 里 `elif kind == "life":` 那一段
（第 275-287 行）。本机 2026-09-22 逐条跑出来的全量（**一位一行，这就是本域的"门表"**）：

| op | 判门依据（policy 源码原文口径） | 作用域（实测） |
|---|---|---|
| `status` | `op = op or "status"`，不在任何写集里 | **零** |
| `timeline` | 不在写集里 | **零** |
| `today` / `day` | 不在写集里 | **零** |
| `recall` | 不在写集里 | **零** |
| `graph` | 不在写集里 | **零** |
| `reflect`（不带 `save`，或 `save:false`） | `elif op == "reflect" and bool(p.get("save"))` 不成立 | **零** |
| `reflect` + `save:true` | 上一条成立 | **`filesystem_write`** |
| `record` / `event` / `remember` | 在 `write_ops = {"record","event","remember","daily","export","export_obsidian","vault","ingest","import_sources","sync_sources"}` | **`filesystem_write`** |
| `daily` | 同上 | **`filesystem_write`** |
| `export` / `export_obsidian` / `vault` | 同上 | **`filesystem_write`** |
| `ingest` / `import_sources` / `sync_sources` | 同上 | **`filesystem_write`** |
| `chapter` / `commitment` / `habit`（无 `action`，或 `action` ∈ `""`/`list`/`status`） | `action = p.get("action") or "list"`，命中豁免集 | **零** |
| `chapter` / `commitment` / `habit`（`action` 是别的，例如 `create`/`close`/`update`） | 上一条不成立 | **`filesystem_write`** |
| 任何**未列出的** op | 既不进 `write_ops`、也不是 `reflect`/`chapter`/`commitment`/`habit` ⇒ **策略层零作用域**，**由 handler 自己抛 `未知 life op`** | 零（但会 user_error，见 §6.4） |

> ⚠️ **读表读全**：`write_ops` 集合**不含** `timeline`/`today`/`recall`/`graph`/`status`，
> 也不含 `chapter`/`commitment`/`habit`/`reflect` —— 那四条各自有**自己的**分支。
> ⇒ **"policy 里有 life 分支"不代表"所有 life op 都被判过"**：未列出的 op 是**零作用域放行**、
> 靠 handler 的 `raise ValueError` 兜底。**这是本域最容易读反的一处。**

**授权只能主人在终端发**：

```powershell
python -m gbt_allinone auth grant --scope filesystem_write --ttl 600
```

或主人手写 `store/auth_grants.jsonl`。**授权一次性消耗**（`note` 原话：`授权一次性消耗；AI 调用路径无权自行发放`）。
🔴 **AI 永远无权给自己发授权** —— 缺授权就如实报缺，**不找旁路、不改 `security/policy.py`**。

---

## 3. 怎么调（真命令）

```powershell
# ── 只读这一档（零作用域；本规程真跑过，见 §6）──
py -3.14 tools/codex-scripts/five-dim.py cap life
py -3.14 tools/codex-scripts/five-dim.py cap life '{"op":"timeline","limit":3}'
py -3.14 tools/codex-scripts/five-dim.py cap life '{"op":"today"}'
py -3.14 tools/codex-scripts/five-dim.py cap life '{"op":"recall","query":"规程","limit":2}'
py -3.14 tools/codex-scripts/five-dim.py cap life '{"op":"graph","limit":5}'
py -3.14 tools/codex-scripts/five-dim.py cap life '{"op":"reflect","period":"week"}'
py -3.14 tools/codex-scripts/five-dim.py cap life '{"op":"chapter"}'
py -3.14 tools/codex-scripts/five-dim.py cap life '{"op":"commitment"}'
py -3.14 tools/codex-scripts/five-dim.py cap life '{"op":"habit"}'

# ── 写这一档（要 filesystem_write；本规程不跑，见 §8）──
py -3.14 tools/codex-scripts/five-dim.py cap life '{"op":"record","type":"milestone","title":"…","summary":"…"}'
py -3.14 tools/codex-scripts/five-dim.py cap life '{"op":"reflect","period":"week","save":true}'
py -3.14 tools/codex-scripts/five-dim.py cap life '{"op":"daily"}'
py -3.14 tools/codex-scripts/five-dim.py cap life '{"op":"export"}'
py -3.14 tools/codex-scripts/five-dim.py cap life '{"op":"ingest"}'
py -3.14 tools/codex-scripts/five-dim.py cap life '{"op":"chapter","action":"create","title":"…"}'
```

🔴 **PowerShell 里传 JSON 载荷：用单引号原样包住 JSON**（`'{"op":"today"}'`）。
写成 `'{\"op\":\"today\"}'` 会让 `five-dim.py:139` 的 `json.loads` 直接抛
`JSONDecodeError: Expecting property name enclosed in double quotes`（同族坑见 `gbt-llm` 的 §2）。

---

## 4. 有哪些 op（源码逐个点名，不猜）

`gbt_allinone/life_archive.py:1506` `run(op="status", **params)`，**13 个正式 op + 4 组别名**：

| op | 别名 | 去处（源码行） | 备注 |
|---|---|---|---|
| `status` | — | `status()`（1481） | 空载荷默认 |
| `record` | `event` · `remember` | `record_event(value)`（371） | `params["event"]` 是 dict 就用它，否则整个 `params` 当事件体 |
| `timeline` | — | `timeline(...)`（416） | 过滤：`start`/`date_start`、`end`/`date_end`、`type`/`event_type`、`tag`、`chapter`、`limit`(默认 100)、`ascending`(默认 True) |
| `today` | `day` | `build_daily(date)`（456） | **不落盘**的当日视图 |
| `daily` | — | `export_obsidian(vault, force)` + `{"date": …}`（1527-1529） | ⚠️ **名字像只读、其实是导出落盘** ⇒ 要 `filesystem_write` |
| `recall` | — | `recall(query, limit=10)`（501） | |
| `graph` | — | `graph(limit=1000)`（531） | `limit` 是**事件上限** |
| `reflect` | — | `reflect(period, save, note)`（567） | `period` 默认 `"week"` |
| `chapter` | — | `chapter(action="list", **payload)`（629） | 动作在 `action` 里 |
| `commitment` | — | `commitment(action="list", **payload)`（714） | 同上 |
| `habit` | — | `habit(action="list", **payload)`（807） | 同上 |
| `export` | `export_obsidian` · `vault` | `export_obsidian(vault 或 path, force)`（1552） | |
| `ingest` | `import_sources` · `sync_sources` | `ingest_sources()`（1557） | |

**未知 op**：`raise ValueError("未知 life op，可用: status/record/timeline/today/daily/recall/graph/reflect/chapter/commitment/habit/export/ingest")`
（`life_archive.py:1559-1562`）—— 实测报错文案**逐字如此**（§6.4）。

**另有 3 个不由 `run()` 暴露的写入口**（源码所见，**未验**）：
`remember_work_log`（1267）· `remember_lesson`（1292）· `remember_mind_event`（1314）
—— 它们是**别的模块直接调**的（`root_fix.work_log` / `charter` / `mind_engine`），
实测 `timeline` 返回的 `source.kind` 就是这三家的签名（§6.2）。

---

## 5. 落点（会写到哪 —— 写动作的一切都在这里）

| 目标 | 路径 | 写法 |
|---|---|---|
| 事件账本 | `gbt_allinone/store/life/events.jsonl` | **只追加**（`_iter_events_reversed()` 倒着读尾部） |
| 状态档 | `gbt_allinone/store/life/state.json` | 章节 / 承诺 / 习惯 / `last_export` |
| 锁 | `gbt_allinone/store/life/life.lock` | 写前加锁 |
| 默认 Vault | `gbt_allinone/store/life_vault` | `export` / `daily` 的落点；可用 `vault`/`path` 覆盖 |

**不出网**（注册表 desc 原话），**不保存完整对话、原始媒体与密钥**
（实测 `op=commitment` 返回的承诺 `detail` 原文），写前一律过 `_safe_text() → redact_text()` **脱敏**。
条数上限：`_MAX_TEXT=500` · `_MAX_TITLE=160` · 去重扫描窗 `_DEDUPE_SCAN=2000` · `_SCHEMA_VERSION=1`。
事件体带 `privacy` 字段（实测本机全是 `"private"`）。

---

## 6. 实测读数（**只读真跑，抄真实字段**；机器 = 本机 2026-09-22）

### 6.1 空载荷 `cap life` —— **就是 status，不报错**

```json
{"gate":"run_task","kind":"life","status":"ok","stamp":true,"denied":false,
 "result":{"ok":true,"state":"alive","events":172,
   "first_at":"2026-09-11T19:39:11","last_at":"2026-09-21T16:09:46+07:00",
   "counts":{"milestone":62,"lesson":92,"chapter":1,"commitment":1,"task":8,"charter":7,"mistake":1},
   "chapters":1,"commitments":1,"habits":0,
   "vault":"C:\\Users\\ADMIN\\Desktop\\GBT小土豆V8\\gbt_allinone\\store\\life_vault",
   "last_export":{"at":"2026-09-17T14:22:21+07:00",
     "vault":"C:\\Users\\ADMIN\\Desktop\\GBT小土豆V8\\gbt_allinone\\store\\life_vault",
     "events":101,"conflicts":0},
   "operations":["status","record","timeline","today","daily","recall","graph","reflect",
                 "chapter","commitment","habit","export","ingest"]}}
```

exit **0**。⇒ **与 `gbt-automation` 的 `browser` 正好相反**：那边空载荷 = `open` ⇒ `user_error`；
这边空载荷 = `status` ⇒ 正常只读。**别把两个域的空参行为互相套。**

### 6.2 `timeline` / `today` / `recall` / `graph` / `reflect`

| 命令 | 本体关键字段（实测） | exit |
|---|---|---|
| `{"op":"timeline","limit":3}` | `ok:true` · `total:172` · `events` 3 条 · `order:"asc"`；每条含 `id` `at` `type` `title` `summary` `importance` `confidence` `valence` `tags[]` `people[]` `projects[]` `capabilities[]` `links[]` `source{kind,ref,digest}` `evidence_sha256` `privacy` | 0 |
| `{"op":"today"}` | `ok:true` · `date:"2026-09-22"` · `count:0` · `first_at:null` · `last_at:null` · `type_counts:{}` · `top_tags:[]` · **`tone:"平稳"`** · `average_valence:0.0` · `highlights:[]` | 0 |
| `{"op":"recall","query":"规程","limit":2}` | `ok:true` · `query:"规程"` · **`count:0`** · `events:[]` | 0 |
| `{"op":"graph","limit":5}` | `ok:true` · **`node_count:13`** · **`edge_count:14`** · `nodes[]`（`event:` / `tag:` 两类）· `edges[]` | 0 |
| `{"op":"reflect","period":"week"}` | `ok:true` · `period:"week"` · `start:"2026-09-15"` · `event_count:106` · `type_counts{task:8,lesson:35,milestone:55,charter:7,mistake:1}` · `milestones[]`（**5 条**）· `lessons[]`（**9 条**）· `open_commitments[]`（1 条）· `habits:[]` · `note:""` | 0 |

🔴 **两处必须读对**：
- **`count:0` 不是坏了**：`today` 今天确实一条没记（档案 `last_at` 是 09-21）；`recall "规程"` 确实没命中。
  空就是空，**不许编**。
- **`graph` 的 `limit` 是事件上限，不是节点上限**：本机 `limit=5` 实测 `node_count 13` / `edge_count 14`
  ⇒ 拿 `limit` 去对 `node_count` 会得出"limit 没生效"的**假**结论。

### 6.3 `chapter` / `commitment` / `habit`（只读档）

| 命令 | 本体关键字段（实测） | exit |
|---|---|---|
| `{"op":"chapter"}` | `ok:true` · `chapters[1]`：`id:"chapter_cb2dc3a3eba04167a695"` · `title:"生命线与连续性"` · `status:"open"` · `opened_at:"2026-09-14T11:08:11+07:00"` · `closed_at:null` · `tags:[]` | 0 |
| `{"op":"commitment"}` | `ok:true` · `commitments[1]`：`id:"commit_996cde2175494cf8a33b"` · `title:"生命档案持续生长"` · `detail:"重要经历自动归档，且不保存完整对话、原始媒体与密钥。"` · `status:"open"` · `importance:0.95` | 0 |
| `{"op":"habit"}` | `ok:true` · **`habits:[]`** | 0 |

### 6.4 🔴 参数陷阱：`{"action":"create"}` 会被当成 **op**

```json
{"gate":"run_task","kind":"life","status":"error","stamp":false,"denied":false,
 "result":{"status":"error","kind":"life",
   "message":"未知 life op，可用: status/record/timeline/today/daily/recall/graph/reflect/chapter/commitment/habit/export/ingest",
   "error_class":"user_error"}}
```

exit **1**。**真因**：`api.py:141` 是
`op = p.pop("op", None) or p.pop("action", None)` ——
**`action` 会被当成 op 的备选**。所以 `{"action":"create"}` 等价于 `op="create"`（一个不存在的 op），
而不是"chapter 的 action=create"。
⇒ **要用 `action` 必须同时写 `op`**：`{"op":"chapter","action":"create"}`。
🔴 **这条报错不是"能力没实现"，是载荷写错了**；两句话长得很像，别混。

### 6.5 写动作的门（静态判定，未跑）

`policy.evaluate("life", {"op":"record"}).scopes == ("filesystem_write",)`；
`{"op":"reflect","save":true}` 同；`{"op":"chapter","action":"create"}` 同。
本机 `auth status` 实测 **15 个作用域 `grants_available` 全 0**、`ai_can_grant:false`
⇒ 真跑这四条**必被门拒**（`status:"denied"` · `missing_scopes:["filesystem_write"]` · exit 1）。
**本规程不跑它们**（见 §8），所以"被拒的实测输出"也**未验** —— 上表是**静态查出来的**，不是跑的。

---

## 7. 失败典型样子（照着认，别认错）

| 症状 | 真因 | 正确读法 |
|---|---|---|
| `status:"error"` · `message:"未知 life op，可用: …"` · exit 1 | op 拼错，**或把 `action` 当成了 op** | 载荷写错（§6.4），不是能力缺失 |
| `status:"denied"` · `missing_scopes:["filesystem_write"]` | 写 op（record/daily/export/ingest/reflect+save/带写 action 的三条） | 是**门**；把 `how_to_grant` 原样交给主人 |
| `count:0` · `events:[]` / `habits:[]` | 真的没有 | **空就是空，不许编**（源码 `note_zh` 同口径：场地空照实说） |
| `graph` 的 `node_count` 比 `limit` 大 | `limit` 管的是**事件** | 别读成"limit 没生效" |
| `today` 的 `tone:"平稳"` 而 `count:0` | 没数据时的默认语气 | 别把 `"平稳"` 读成"今天很平静"的证据 |
| `JSONDecodeError: Expecting property name enclosed in double quotes` | PowerShell 转义了 JSON | 用单引号原样包（§3） |

---

## 8. 🔴 未验清单（**为什么不做**，逐条）

| 动作 | 状态 | 为什么不做 |
|---|---|---|
| `{"op":"record"}` / `event` / `remember` | **未验** | **真写档**（追加 `store/life/events.jsonl`：任务明令 life 的写档不跑） |
| `{"op":"reflect","save":true}` | **未验** | 真写盘 |
| `{"op":"daily"}` | **未验** | 真写 Vault（虽然名字像只读） |
| `{"op":"export"}` / `export_obsidian` / `vault` | **未验** | 真写 Vault 文件 |
| `{"op":"ingest"}` / `import_sources` / `sync_sources` | **未验** | 真写盘 |
| `{"op":"chapter","action":"create"/"close"/…}` 等同族写动作 | **未验** | 真写 `state.json` |
| `remember_work_log` / `remember_lesson` / `remember_mind_event` | **未验** | 不是 `run()` 暴露的 op（别的模块直调），且都是写口 |
| `{"op":"chapter","action":"create"}` 这种**不带 op 的写法** | 已验证 **会 user_error**（§6.4） | 这条**跑过**，属已验（只读副作用：抛错） |

> **"未验"不是"不能用"**：上表每一条都**存在**、都**有源码落点**、都**有静态门表**；
> 缺的是**当次运行证据**。本规程**不拿"我以为能"当"验过"**。

---

## 9. 与相邻域的边界（一句话切干净）

| 相邻 | 谁是谁 | 边界 |
|---|---|---|
| `gbt-mind`（`mind` 域，9 位） | 心智引擎：预演/评估/内部状态/经验召回/反思 | **两者都写框架 store，但门口径完全不同**：本机静态查 `mind` 域**9 位全零作用域**（实测），而 `life` 的写 op **一律挂 `filesystem_write`**。⇒ **绝不许拿 mind 的"免卡"推断 life 也免卡**。`life` 里 `source.kind == "mind_engine"` 的事件（实测 §6.2 可见 `mind.event:…`）是 **mind 写进来的**，不是 life 自己写的 |
| `gbt-project`（`project` 域） | 项目上下文 | 项目侧的档不在本域的 Vault 里 |
| `gbt-collab`（`stigmergy`） | 信息素场地 | 两者都"只追加"，但**落点分开**：`life` → `store/life/`；`stigmergy` → `store/collab/stigmergy/` |
| `gbt-tentacle` | 看屏幕/读网 | 本域**不出网**（注册表 desc 原话） |

---

## 10. 🔴 报告层红线（先问"这是事实，还是我读错了地方"）

1. **退出码不可信**。本域实测：**只读成功 exit 0**、**载荷写错（user_error）exit 1**、
   **门拒（denied）exit 1**。⇒ `exit 1` 先看 `status` 是 `denied` 还是 `error`；
   `exit 0` 也要看本体 `ok`。`stamp: true/false` 是**回归印章的有无**，不是成功与否。
2. **`status:"ok"` ≠ 本体 `ok:true`**。本域这一版实测**外层与本体没打架**（六条只读全是外层 ok + 本体 ok），
   但**同族位里打架的活样本就在隔壁**（`gbt-automation` 的 `native/status`、`gbt-integration` 的 `check_bypass`）
   ⇒ **口径仍要按"两层都看"执行**，不能因为本域碰巧一致就省掉一层。
3. **零作用域 ≠ 只读**。本域有反例的两个方向：
   ① `daily` / `export` 名字像只读，其实**写盘**（policy 如实挂了 `filesystem_write`）；
   ② **未列出的 op** 在 policy 里**零作用域放行**，靠 handler 抛错兜底（§2 那条 ⚠️）。
4. **"能调" ≠ "能用"**。`life` 在 `omni.auto_run_verdict()` 里实测 **`AUTO=True`**（零作用域 + 无必填参数），
   但**那个 AUTO 只覆盖"空载荷跑一发 status"** —— 它**完全不保证** `record`/`export`/`ingest` 能用。
   ⇒ **AUTO 判的是"这个位空参能不能自动跑"，不是"这个位能不能干活"。**
5. **扁平拒绝信封**：写 op 被拒时 `missing_scopes` / `reason` / `how_to_grant` / `note`
   在**顶层**，**没有 `gbt_result`**（同 `gbt-automation` §6.5 的形状）。⇒ **读顶层字段**。
6. **`source.kind` 是"谁写的"，不是"谁该读"**。实测 `timeline` 的 `source.kind` 出现
   `root_fix.work_log` / `charter` / `mind_engine` / `manual` 四种 ⇒ **档案是多方汇聚的**，
   看到某条不对**先去问写它的那个模块**，不要在 `life` 上乱改。

---

## 11. 不许做什么（红线）

1. **不许给自己发授权**：不跑 `auth grant`、不手写 `store/auth_grants.jsonl`、不改 `security/policy.py` / `auth_gate`。
2. **不许绕门**：不许为了"绕过授权"直接调 `gbt_allinone.life_archive` 里的函数替掉 `run_task` 唯一门
   （AGENTS.md 明令：那是**未经授权的写入**，纪律上就是违规）。
3. **被拒了就是拒了**：`denied` 之后**不许换路径再试**、不许改 payload 碰运气。
4. **不许把空结果编成有结果**：`count:0` / `habits:[]` 就照实报空（源码自己写着"照实说不编"）。
5. **不许把 `daily` / `export` 当只读**（它们要 `filesystem_write`）。
6. **不许改 `tools/codex-scripts/omni.py`**（本域登记行由交付报告给出，不擅自动手）；
   **不许动别的域**、不许改 `policy.py`。

---

## 12. 固化与出处（**重启后要在**）

| 什么 | 在哪 |
|---|---|
| 本规程（源） | `<仓>/skills/gbt-life/SKILL.md` |
| 本规程（装机·托管目录） | `C:\Users\ADMIN\.openclaw-autoclaw\skills\gbt-life\SKILL.md` |
| ⛔ **不许装到** | `~/.agents/skills/`（本仓 AGENTS.md 明令禁止） |
| 能力位名单（1 个：`life`） | `<仓>/state/skill_atlas.json`（`domain == "life"`）· 现扫可重建：`python tools/codex-scripts/omni.py build` |
| 授权判据（**单一真相**） | `<仓>/gbt_allinone/security/policy.py` 的 `evaluate()` → `elif kind == "life":`（第 275-287 行） |
| op 分发 | `<仓>/gbt_allinone/api.py:138-144`（`kind in ("life","mind","project_context")` 那一支） |
| 实现 | `<仓>/gbt_allinone/life_archive.py`（`run()` 1506；`status()` 1481；写口 `record_event` 371） |
| 门与拒绝信封 | `<仓>/gbt_allinone/run_task`（唯一门）· `tools/codex-scripts/five-dim.py:131-172`（扁平信封的读法） |

**深蒸登记（应加、本次未擅自动手 —— 登记由主人统一做）**：`omni.py` 的 `DISTILLED_DOMAINS` 加一行

```python
    "life": "gbt-life",
```

加完后 `python tools/codex-scripts/omni.py gaps` 里 `life 1 个能力位` 会从
`⏳ 在队里` 变成 `✅ 已深蒸 → gbt-life`。

**验收（做完怎么证明真的做了）**：

```powershell
py -3.14 tools/codex-scripts/verify-distill.py --domain life --skill gbt-life
```

1. 上面这条必须 **PASS**（覆盖 1/1）；
2. 两份产物**逐字节相同**（sha256 一致）；
3. 写 op 的静态门表必须与 §2 **逐个一致**（不一致就是某处漂移了，回来改本文件）；
4. 声明"某 op 能用"之前，先问自己：**这条是实测读数，还是我读错了地方？** 拿不准就写"未验"。
