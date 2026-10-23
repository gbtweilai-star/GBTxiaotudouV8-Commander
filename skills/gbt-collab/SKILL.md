---
name: gbt-collab
displayName: GBT · collab 职业域用法规程（1 个能力位：stigmergy）
version: 1.0.0
description: GBT小土豆V8 的 `collab` 职业域（协作层的间接通道 / Stigmergy / 共识主动性 / 信息素场地）用法规程。这个域**只有 1 个能力位**：`stigmergy`。本文件把它写全：用途、四原语 DEPOSIT·READ·DECAY·FORAGE 逐个点名、五条红线做成机械闸、逐 op 静态查出来的作用域（**整位零作用域，连 DEPOSIT 也是零** —— 这就是"零作用域 ≠ 只读"的活样本）、真命令、12 个 op 逐个点名、落点（store/collab/stigmergy/pheromones.jsonl，只追加）、失败典型样子、与 `collab_gateway`（直连通道：会话/对等方/收件箱）和 `gbt-life`（同样只追加但落点不同）的边界；并记下实测读数（场地是空的 ⇒ READ/FORAGE 如实返回空不编方向；DECAY 的 deleted 恒为 0 因为挥发是读数不是删除；gate_append_only 走 AST 真引用判据而不是文本关键词）。当用户要留一条协作痕迹 / 读场地浓度 / 看挥发 / 问下一步该去哪 / 多方同时在场找不到具体对接人，或 stigmergy 报 deposit_without_source / deposit_kind_not_allowed / plaintext_key_in_pheromone / pheromone_deleted_or_overwritten 时使用。
triggers:
  - "协作层"
  - "信息素"
  - "场地"
  - "共识主动性"
  - "stigmergy"
  - "collab"
  - "留痕"
  - "多方协同"
  - "找不到找谁"
  - "deposit"
  - "forage"
  - "pheromone"
  - "deposit_without_source"
  - "pheromone_deleted_or_overwritten"
---

# GBT · collab 职业域用法规程（1 个能力位：`stigmergy`）

> 开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属
>
> **这份规程解决什么**：`collab` 是一个**一位一域**的小域，但它有一个**别处没有的性质**：
> **四原语里只有 `DEPOSIT` 会写，而且"写"就是"往账本末尾追加一行"**。
> 于是它成了全仓**最容易被读反的两句话**的样本：
> ① **"零作用域 ≠ 只读"** —— `DEPOSIT` 在 `policy.py` 里**一条分支都没有**，实测**零作用域**，
> 但它**真写盘**。这条口径甚至被写进了 `policy.py` 自己的注释里（`ledger_note` 那段：
> "对齐盘上 `stigmergy` 的先例"）。
> ② **"挥发 ≠ 删除"** —— `DECAY` 名字像"清理"，实测 `deleted: 0` **恒为 0**：
> **挥发是算术，账本只增不减、可回放**。
> 本文件把「哪个 op、要不要授权、门在哪一层、失败长什么样、读数该看哪个字段」逐个钉死，
> 并把**本机实测过的坑**如实记下来 —— **没验过的一律写"未验"，不冒充验过**。

**唯一现读入口（别信任何二手描述，包括本文件）**：

```powershell
py -3.14 tools/codex-scripts/five-dim.py cap stigmergy ['<JSON载荷>'] [--full]
```

`cap` 一律走 `gbt_allinone.run_task`（**唯一门**）；被门拒绝就**如实报缺什么作用域**，不绕路。

---

## 0. 一位一域（先确认名字，别照抄别人的表）

现扫 `state/skill_atlas.json`（`domain == "collab"`）**只有一条**：

| 域 | 能力位（kind） | handler | type | 注册表 desc 原文 |
|---|---|---|---|---|
| `collab` | **`stigmergy`** | `stigmergy` | **`internal`** | "**协作层的间接通道**：Stigmergy（共识主动性 / 信息素场地）。四原语 DEPOSIT/READ/DECAY/FORAGE；只有 DEPOSIT 会写、且**只追加**（挥发是读数，账本可回放）。五条红线做成机械闸：**无源不许留** deposit_without_source · **种类白名单** deposit_kind_not_allowed · **只追加** pheromone_deleted_or_overwritten（静态核本模块源码）· **不留明文密钥** plaintext_key_in_pheromone · **只给读数**（FORAGE 只排序不执行）。与 collab_gateway **并排、不替代**：直连=会话/对等方/收件箱，间接=信息素场地；场地放在 store/collab/stigmergy/。type=internal" |

模块头部另有 `CAP_TYPE = "internal"`（`stigmergy.py:33`）· `TRACE_SOURCE_KIND = "stigmergy"`（34）。
注册表 `requires_params=[]` · `params_hint=""` · `needs_confirmation=false` · `safe=true`
⇒ 空载荷调用**合法**（落到只读 `status`，见 §6.1）。

> ⚠️ **`collab` 域与 `collab_gateway` 不是一件事**：
> `collab_gateway`（会话 / 对等方 / 提案收件箱）是**直连通道**，它是另一个模块
> （`<仓>/gbt_allinone/collab_gateway.py`）。实测 `state/skill_atlas.json` 里
> **`collab_open` / `collab_close` / `collab_server_start` / `peer_register` 这些名字一个都不在**
> —— 它们只在 `security/policy.py` 里作为**规则条目**存在。
> ⇒ 🔴 **绝不许写"`cap collab_open`"这种命令**：图鉴里没有这个能力位，**写出来就是编造**。
> 本域只管 `stigmergy` 对应的事情。

---

## 1. 什么时候用（意图 → 落点）

| 人想干什么 | 落到哪个 op | 只读还是要授权 |
|---|---|---|
| 看场地形状（四原语 / 五红线 / 种类 / 账本路径 / 行数 / 两道闸） | `status`（**空载荷默认就是它**） | 只读，**零作用域** |
| 只看四原语那四条 | `primitives` | 只读，零作用域 |
| 看五条红线 | `redlines` | 只读，零作用域 |
| 看信息素种类白名单（含半衰期） | `kinds`（= `gate_kinds`） | 只读，零作用域 |
| **留一条信息素** | `deposit` | **零作用域，但真写盘（只追加一行）** |
| 读场地（按 subject 汇总有效强度） | `read` | 只读，零作用域 |
| 看挥发读数（还活着 / 已淡出各几条） | `decay` | 只读，零作用域（**不删行**） |
| 问"下一步更值得去哪" | `forage` | 只读，零作用域（**只排序，不执行**） |
| 看原始账本尾部 | `trail` | 只读，零作用域 |
| 看它与 `collab_gateway` 的关系 | `collab_bridge` | 只读，零作用域 |
| 静态核本模块"只追加" | `gate_append_only` | 只读闸，零作用域 |

**不在这 1 个位里的事**：点对点找人 / 会话 / 对等方 / 提案收件箱 → `collab_gateway`（**直连通道，不在本域图鉴里**）；
生命档案 → `gbt-life`（`life` 域）；看屏幕/点界面 → `gbt-tentacle`。

---

## 2. 🔴 要过哪道门：**整位零作用域 —— 但 DEPOSIT 真写盘**

```python
from gbt_allinone.security import policy
policy.evaluate("stigmergy", {}).scopes                  # → ()
policy.evaluate("stigmergy", {"op": "deposit"}).scopes   # → ()   ← 连"写"也是零！
```

**唯一权威**是 `gbt_allinone/security/policy.py` 的 `evaluate()`。
实测（本机 2026-09-22）：**`stigmergy` 在 `policy.py` 里没有任何 `elif kind == "stigmergy":` 分支**
（全文件 grep 只在一句注释里命中），所以：

| op | 作用域（实测） |
|---|---|
| `status` / `primitives` / `redlines` / `kinds` | **零** |
| `read` / `decay` / `forage` / `trail` / `collab_bridge` | **零** |
| `gate_kinds` / `gate_append_only` | **零** |
| 🔴 **`deposit`** | **零** |

🔴🔴 **零作用域 ≠ 只读 —— 本域就是这句话的样本。**
`deposit` 在门这一层**完全免卡**（policy 没给它挂任何作用域），
而它的实现最后一行是 `locked_append_text(path, …)` —— **真往盘上追加一行**。
**"门没拦"只说明"policy 没把这一格收口"，不说明"这一步没有后果"。**

> **这条口径是"被承认"的，不是"漏掉的"**：`policy.py` 里 `ledger_note` 那一段注释（第 349-354 行）原话写着
> **"现口径：**对齐盘上 `stigmergy` 的先例**（那一族也是「只追加」的能力，policy 里没有条目 ⇒ 零作用域）"**，
> 理由是那类写面**窄到只剩一条**：目标固定、只追加、单物理行、幂等、有闸。
> ⇒ **"零作用域"在这里是一个经过论证的设计选择，不是没人管。**
> **但它仍然是一次真写盘** —— 报"这次调用没有作用域"与报"这次调用没写东西"是两句话。

**那"门"在哪？** 本域的闸**不在 policy，在模块自己**（五条红线做成机械闸）：

| 闸 | 判据（模块源码） | 不通过时 `rule` |
|---|---|---|
| 无源不许留 | `source` 去空格后非空 | `deposit_without_source` |
| 种类白名单 | `kind` 必须在 `KINDS`（`task`/`path`/`danger`/`resource`） | `deposit_kind_not_allowed` |
| subject 必须有 | `subject` 非空 | `deposit_subject_missing` |
| subject 长度 | ≤ `MAX_SUBJECT_LEN = 120` | `deposit_subject_too_long` |
| 强度 | 必须是数，且 **`0 < 强度 ≤ 1`** | `deposit_strength_not_number` / `deposit_strength_out_of_range` |
| 正文长度 | ≤ `MAX_NOTE_LEN = 500` | `deposit_note_too_long` |
| 不留明文密钥 | 正文粗筛 `sk-` / `ghp_` / `AKIA`（`_SECRET_RE`） | `plaintext_key_in_pheromone` |
| 只追加（**静态核源码**） | 本模块源码里**不许**出现 unlink/truncate/覆写写法，**且必须真引用** `locked_append_text` | `pheromone_deleted_or_overwritten` / `append_path_missing` |
| 种类要有正半衰期 | `check_kinds()`：每种 `KINDS[k] > 0` | `kinds_empty` / `kind_without_half_life` |

⇒ **"policy 零作用域" + "模块自带九道闸" = 两层不同的门**，别因为看见前一层是空的就说"没门"。

**授权只能主人在终端发**（本机 `auth status` 实测 15 个作用域 `grants_available` 全 0、`ai_can_grant:false`）。
本域**现在一门都不需要**（零作用域），所以**别去申请**。
🔴 **AI 永远无权给自己发授权** —— 缺授权就如实报缺，**不找旁路、不改 `security/policy.py`**。

---

## 3. 怎么调（真命令）

```powershell
# ── 只读这一档（零作用域；本规程真跑过，见 §6）──
py -3.14 tools/codex-scripts/five-dim.py cap stigmergy
py -3.14 tools/codex-scripts/five-dim.py cap stigmergy '{"op":"primitives"}'
py -3.14 tools/codex-scripts/five-dim.py cap stigmergy '{"op":"redlines"}'
py -3.14 tools/codex-scripts/five-dim.py cap stigmergy '{"op":"kinds"}'
py -3.14 tools/codex-scripts/five-dim.py cap stigmergy '{"op":"read"}'
py -3.14 tools/codex-scripts/five-dim.py cap stigmergy '{"op":"read","subject":"<主题>"}'
py -3.14 tools/codex-scripts/five-dim.py cap stigmergy '{"op":"decay"}'
py -3.14 tools/codex-scripts/five-dim.py cap stigmergy '{"op":"forage","top":5}'
py -3.14 tools/codex-scripts/five-dim.py cap stigmergy '{"op":"trail","limit":20}'
py -3.14 tools/codex-scripts/five-dim.py cap stigmergy '{"op":"collab_bridge"}'
py -3.14 tools/codex-scripts/five-dim.py cap stigmergy '{"op":"gate_kinds"}'
py -3.14 tools/codex-scripts/five-dim.py cap stigmergy '{"op":"gate_append_only"}'

# ── 写那一档（零作用域但本规程不跑，见 §8）──
py -3.14 tools/codex-scripts/five-dim.py cap stigmergy '{"op":"deposit","kind":"task","subject":"<主题>","note":"<摘要>","strength":0.5,"source":"<谁留的>"}'
```

🔴 **PowerShell 里传 JSON 载荷：用单引号原样包住 JSON**（`'{"op":"read"}'`）。
写成 `'{\"op\":\"read\"}'` 会让 `five-dim.py:139` 的 `json.loads` 直接抛
`JSONDecodeError: Expecting property name enclosed in double quotes`（同族坑见 `gbt-llm` 的 §2）。

---

## 4. 有哪些 op（源码逐个点名，不猜）

`gbt_allinone/tools/stigmergy.py:326` `run(op="status", **params)`，**12 个 op**：

| op | 去处（源码行） | 说明 |
|---|---|---|
| `status` | 汇编四原语/五红线/`KINDS`/账本路径/行数/`collab_bridge`/两道闸（330） | 空载荷默认 |
| `primitives` | `PRIMITIVES`（36） | 四条 |
| `redlines` | `RED_LINES`（47） | 五条 |
| `kinds` | `check_kinds()`（274） | = `gate_kinds` |
| 🔴 `deposit` | `deposit(kind, subject, note, strength, source, now, root)`（121） | **唯一会写的 op**：过九道闸后 `locked_append_text` 追加一行 |
| `read` | `read(subject, kind, now, root)`（170） | 有效强度 = 强度 × `0.5^(龄期/半衰期)`；`min_effective` 默认 `0.05` |
| `decay` | `decay(now, root)`（211） | **只算不删**：返回 `rows`/`alive`/`faded`/`deleted:0` |
| `forage` | `forage(subject_prefix, top, now, root)`（231） | **只排序、不执行**；场地空 ⇒ 明说"场地是空的"、"不编方向" |
| `trail` | `trail(limit, root)`（253） | 原始账本尾部（只读） |
| `collab_bridge` | `collab_bridge()`（264） | 与 `collab_gateway` 的关系（只读，**不读写** collab 的会话/对等方/收件箱） |
| `gate_kinds` | `check_kinds()` | 闸 A |
| `gate_append_only` | `check_append_only()`（287） | 闸 B（**静态核本模块源码**） |

**未知 op**：`raise ValueError("未知 op %r（可用：status/primitives/redlines/kinds/deposit/read/decay/forage/trail/collab_bridge/gate_kinds/gate_append_only）")`。

### 四原语（模块自报，实测逐字）

| name | 作用 | 判据 |
|---|---|---|
| `DEPOSIT` | 留一条信息素（**只追加**，必带 source） | 无源不许留 · 种类在白名单 · 强度 0<·<=1 · 不留明文密钥 |
| `READ` | 读场地：按 subject 汇总**有效强度**（= 强度 × 半衰期衰减） | 只读；没留过就如实返回空，**不编** |
| `DECAY` | 挥发**读数**：给出还活着 / 已淡出的条数 | **不删任何行**（挥发是算术，不是删除） |
| `FORAGE` | 按有效强度排序，给出「下一步更值得去哪」的**读数** | 只排序、**不自动执行**；无人留痕 ⇒ 明确说「场地是空的」 |

### 五种信息素（白名单 + 半衰期，实测逐字）

| kind | 半衰期（小时） |
|---|---|
| `task` | 6.0 |
| `path` | 2.0 |
| `danger` | 12.0 |
| `resource` | 8.0 |

> 白名单只有这 4 个（注释："借「真实蚂蚁的四类信息素」当上限，避免乱塞"）。
> ⇒ **要么在这里，要么就是 `deposit_kind_not_allowed`。不许自己加种类。**

### 五条红线（实测逐字）

1. 无源不许留：每次留痕必须写明 source（谁留的）
2. 种类白名单：kind 必须在 KINDS 里，且每条都有半衰期
3. 只追加：账本**不许删行 / 不许覆写**（挥发是读数）
4. 不留明文密钥：正文粗筛 sk- / ghp_ / AKIA 等
5. 只给读数：FORAGE / READ 不许触发任何外部动作

---

## 5. 落点 / 外部面（动手会碰到什么）

| 维度 | 现状（实测字段） |
|---|---|
| **账本落点** | `<仓>\gbt_allinone\store\collab\stigmergy\pheromones.jsonl`（`ledger_path()` = `_store_dir()/"pheromones.jsonl"`） |
| **场地目录** | `<仓>\gbt_allinone\store\collab\stigmergy`（**放在现有协作区下**） |
| **写法** | `locked_append_text(path, json.dumps(row, ensure_ascii=False) + "\n")` —— **只追加一行** |
| **现状行数** | `rows: 0`（**真实字段**；场地现在是**空的**） |
| **外部面** | **无**。不出网、不起进程、不碰 `collab_gateway` 的会话/对等方/收件箱（`no_side_effect` 原话） |
| **一行长什么样** | `{"kind": …, "subject": …, "strength": …, "note": …, "source": …, "at": <epoch 秒>}` |
| **坏行怎么处理** | `_load_rows()` 遇到 `JSONDecodeError` **不静默**：塞一条 `{"_broken": true}` 的**标记行**，**但仍不删** |
| **上限** | `MAX_NOTE_LEN = 500` · `MAX_SUBJECT_LEN = 120` · `MAX_STRENGTH = 1.0` · `MIN_EFFECTIVE = 0.05` |

**诚实边界（模块自己写的 `HONEST_BOUNDARY`，原文）**：
> "它保证「痕迹**可留、可读、可按半衰期挥发**，且账本**只增不减、可回放**」；
> 它保证不了「协同一定更聪明」—— 信息素会被**错误痕迹带偏**（这正是蚂蚁也会绕远路的原因）
> ⇒ 所以本模块**只给读数、不自动执行**，并且每条留痕**必须带源**（好追责、好回滚判断）。
> 它与 collab_gateway **并排**：直连解决点对点，间接解决「找不清谁」——**不是替代**。"

---

## 6. 实测读数（**只读真跑，抄真实字段**；机器 = 本机 2026-09-22）

### 6.1 空载荷 `cap stigmergy`

```json
{"gate":"run_task","kind":"stigmergy","status":"ok","stamp":true,"denied":false,
 "result":{"ok":true,"readonly":true,"kind":"stigmergy","domain":"collab","type":"internal",
   "primitives":[ …4 条，见 §4 表… ],
   "red_lines":[ …5 条，见 §4 表… ],
   "kinds":["danger","path","resource","task"],
   "ledger":"C:\\Users\\ADMIN\\Desktop\\GBT小土豆V8\\gbt_allinone\\store\\collab\\stigmergy\\pheromones.jsonl",
   "rows":0,
   "bridge":{"ok":true,"readonly":true,
     "direct_channel":"collab_gateway（会话 / 对等方 / 提案收件箱）——**我知道找谁**",
     "indirect_channel":"stigmergy（信息素场地）——**我只知道场地**",
     "relationship":"**并排、不替代**：直连解决点对点；间接解决「找不清谁 / 多方同时在场」",
     "shared_store":"C:\\Users\\ADMIN\\Desktop\\GBT小土豆V8\\gbt_allinone\\store\\collab\\stigmergy",
     "no_side_effect":"本函数**不读写** collab 的会话/对等方/收件箱"},
   "gate_kinds":{"ok":true,"readonly":true,"kinds":["danger","path","resource","task"],
     "half_life_hours":{"danger":12.0,"path":2.0,"resource":8.0,"task":6.0}},
   "gate_append_only":{"ok":true,"readonly":true,"append_only":true,
     "writer":"locked_append_text","checked":"本模块源码静态核（不许删行 / 不许覆写）"}}}
```

exit **0**。

### 6.2 只读四原语 + trail + bridge（逐个真跑）

| 命令 | 本体关键字段（实测） | exit |
|---|---|---|
| `{"op":"read"}` | `ok:true` · `readonly:true` · `primitive:"READ"` · **`subjects:[]`** · `count:0` · `faded_below:0` · `min_effective:0.05` · `note_zh:"场地是空的也照实说（**不编**）"` | 0 |
| `{"op":"decay"}` | `ok:true` · `readonly:true` · `primitive:"DECAY"` · `rows:0` · `alive:0` · `faded:0` · 🔴 **`deleted:0`** · `note_zh:"**挥发是读数，不是删除**：账本可回放，行只增不减"` | 0 |
| `{"op":"forage"}` | `ok:true` · `readonly:true` · `primitive:"FORAGE"` · **`suggestions:[]`** · `reason:"场地是空的（**没人留过痕**）⇒ **不编方向**"` | 0 |
| `{"op":"trail"}` | `ok:true` · `readonly:true` · `rows:0` · `tail:[]` · `ledger:"…\\store\\collab\\stigmergy\\pheromones.jsonl"` | 0 |
| `{"op":"gate_kinds"}` | `ok:true` · `readonly:true` · `kinds` 4 条 · `half_life_hours` 见 §4 | 0 |
| `{"op":"gate_append_only"}` | `ok:true` · `readonly:true` · **`append_only:true`** · `writer:"locked_append_text"` · `checked:"本模块源码静态核（不许删行 / 不许覆写）"` | 0 |

🔴 **两处必须读对**：
- **`rows:0` / `count:0` / `subjects:[]` / `suggestions:[]` 是"场地真的空的"，不是"能力坏了"**
  （源码自己写着"照实说、不编"、"不编方向"）。
- **`deleted:0` 不是"这一发没删到东西"** —— 它是**常量 0**：
  这个模块**没有任何删行路径**（`gate_append_only` 就是静态核这一点）。⇒ **别把 `deleted:0` 读成"删了 0 条，下次可能删"**。
- **`readonly:true` 出现在 READ/DECAY/FORAGE/TRAIL/两道闸上，但 `deposit` 的返回里是 `readonly:false`**
  （源码 `deposit()` 返回 `{"ok": True, "readonly": False, …}`）
  ⇒ 🔴 **`readonly` 这个字段本模块是逐 op 真标的，可以当判据**（对比 `gbt-infra` 的 `gate_official`
  那格 `readonly:true` 是**常量** —— 同名不同义，别跨模块套）。

### 6.3 `gate_append_only` 的一个真坑（源码注释留档）

静态核**不是文本关键词搜索**，走的是 **AST 真引用判据**（`source_judge.uses_name`）。
源码第 310-320 行的注释原话：
> "🔴 2026-09-22 修：原来 `"locked_append_text" not in src` 是**文本关键词** —— 注释里提一句就过关，
> 于是"我没读到真源码"这层保护**失效**（假绿）。现走 AST 真引用判据；**文本先当廉价前置筛**…
> `None`（解析不了）**也**按未测处理 ⇒ 保持 fail-closed。"

⇒ **教训可复用**：**"源码里出现过某关键词"不是"源码真的用了它"**。
本规程引任何"源码里写着 X"时，都按**读到的行号**给位置，不给"我搜到了"这种话。

### 6.4 `deposit`（**源码所见，未跑**）

九道闸的顺序与返回（`stigmergy.py:121-167`）：`source` 空 ⇒ `deposit_without_source`；
`kind` 不在白名单 ⇒ `deposit_kind_not_allowed`；`subject` 空 ⇒ `deposit_subject_missing`；
`subject` 超 120 ⇒ `deposit_subject_too_long`；`strength` 非数 ⇒ `deposit_strength_not_number`；
`strength` 不在 `(0, 1]` ⇒ `deposit_strength_out_of_range`；`note` 超 500 ⇒ `deposit_note_too_long`；
正文命中密钥正则 ⇒ `plaintext_key_in_pheromone`；
全过 ⇒ `{"ok": true, "readonly": false, "primitive": "DEPOSIT", "row": {...}, "ledger": "<路径>",
"note_zh": "**只追加一行**（挥发靠读数，不删行）"}`。

🔴 注意 `deposit` 被拒时返回的是 **`{"ok": false, "denied": true, "rule": …}`**（**内层**），
而外层信封仍然是 `status:"ok"` —— **又一处"外层 ok、内层 denied"**（同族见 `gbt-integration` §6.4）。
**本规程未跑这条**（理由见 §8）。

---

## 7. 失败典型样子（照着认，别认错）

| 症状 | 真因 | 正确读法 |
|---|---|---|
| 内层 `rule:"deposit_without_source"` | 没给 `source` | 源码原话："**无源不许留**：留痕必须写明 source（谁留的）—— 否则场地会变谣言" |
| 内层 `rule:"deposit_kind_not_allowed"` + `allowed` | `kind` 不在 4 类白名单里 | **不许自己加种类**（白名单每条都有半衰期） |
| 内层 `rule:"deposit_strength_out_of_range"` + `range:[0.0,1.0]` | 强度不在 `(0, 1]` | 注意是**开区间下界**：`0` 也不行（"0 等于没留"） |
| 内层 `rule:"plaintext_key_in_pheromone"` + `masked` | 正文里带了明文密钥 | 命中即拒、**不写盘** |
| 内层 `rule:"pheromone_deleted_or_overwritten"` + `found` | **本模块源码里**出现了删/截/覆写写法 | 这是**静态核自己的源码**，不是"你这次删了东西" |
| 内层 `rule:"append_path_missing"` | 源码里既没删除写法、也没真引用 `locked_append_text` | 源码原话："说明我没读到真源码（**未测不按绿**）" |
| `rule:"kinds_empty"` | 白名单为空 | 源码原话："**没测到**（空样本不按绿）" |
| `rule:"kind_without_half_life"` + `kinds` | 某种没正半衰期 | "那条信息素**永不淡出**（场地会被压死）" |
| `subjects:[]` / `suggestions:[]` | 场地真的空的 | **照实说、不编方向** |
| `deleted:0` | **常量**（本模块没有删行路径） | **别读成"这次删了 0 条"** |
| 期望"点对点找人" | **走错通道** | 那是 `collab_gateway`（直连），本域是**间接通道** |
| `JSONDecodeError: Expecting property name enclosed in double quotes` | PowerShell 转义了 JSON | 用单引号原样包（§3） |

---

## 8. 🔴 未验清单（**为什么不做**，逐条）

| 动作 | 状态 | 为什么不做 |
|---|---|---|
| 🔴 `{"op":"deposit",…}` | **未验** | **真写盘**（往 `store/collab/stigmergy/pheromones.jsonl` 追加一行）。任务明令"只跑只读 op"，**写口不碰** |
| `deposit` 的九条拒绝分支 | **未验** | 只读了源码（`stigmergy.py:121-167`），**一条都没跑**（它们本身不写盘，但都挂在写 op 上） |
| `deposit` 的**成功**分支 | **未验** | 会写盘；且**会真的改变场地读数**（`rows` 从 0 变 1），属"改状态" |
| 用 `root` 参数写到**别的目录** | **未验** | `deposit/read/decay/forage/trail` 都收 `root` 覆盖落点；本规程**一个都没试**（那等于另开一个场地） |
| `read` 的**非空**分支（`subject` 过滤 / 有效强度汇总 / `faded_below`） | **未验** | 场地 `rows:0` ⇒ 要验就得先写一条（`deposit`）⇒ 与本条上一条冲突，**只能停在"未验"** |
| `forage` 的**非空**分支（排序 + `why`） | **未验** | 同上 |
| `_load_rows` 的坏行分支（`_broken` 标记） | **未验** | 要有坏行才验得到；**不许为了验它去写坏行** |
| 与 `collab_gateway` 的联调 | **未验** | `collab_gateway` 的位**不在本域图鉴里**；且那属别域 |

> **"未验"不是"不能用"**：上表每一条都**存在**、都**有源码落点**；缺的是**当次运行证据**。
> 本规程**不拿"我以为能"当"验过"**。
> 🔴 **本域的未验比别域更硬**：唯一的写 op 就是唯一能让 `read`/`forage`/`decay`"有东西可读"的手段
> ⇒ **"只跑只读"这条纪律，直接决定本域的非空读数永远验不到**。
> **这是纪律的代价，如实的说法就是"未验"，不是"我推测它应该能"。**

---

## 9. 与相邻域的边界（一句话切干净）

| 相邻 | 谁是谁 | 边界 |
|---|---|---|
| `collab_gateway`（**模块，不在本域图鉴里**） | 协作层的**直连**通道：会话 / 对等方 / 提案收件箱 | 两家**并排、不替代**（源码原话）：直连解决"**我知道要找谁**"，间接解决"**我只知道场地 / 找不清谁 / 多方同时在场**"。🔴 `collab_bridge` 实测返回 `no_side_effect:"本函数**不读写** collab 的会话/对等方/收件箱"` ⇒ **本域不替它干活、也不读它的账** |
| `gbt-life`（`life` 域） | 生命档案 | **两家都是"只追加"，但落点与语义完全分开**：`life` → `store/life/events.jsonl`（**挂 `filesystem_write` 门**）；`stigmergy` → `store/collab/stigmergy/pheromones.jsonl`（**零作用域**）。⇒ **"都只追加"不等于"门口径一样"** |
| `gbt-tools` / `gbt-engine` 等零作用域域 | — | 本域与它们同属"**零作用域但会动手**"那一族；**判据永远是逐 op 看源码，不是看作用域是否为空** |
| `gbt-tentacle`（`tentacle` 域） | 手眼网耳 | 本域**不出网、不起进程、不碰桌面**（`HONEST_BOUNDARY` 原话：只保证"可留、可读、可挥发、只增不减"） |

---

## 10. 🔴 报告层红线（先问"这是事实，还是我读错了地方"）

1. **零作用域 ≠ 只读**（**本域核心红线**）。`deposit`（**真写盘**）在 policy 层**零作用域**。
   ⇒ **作用域只回答"policy 这一层有没有收口"，不回答"这一步有没有后果"。**
   这条口径在 `policy.py` 里被**明确援引**（`ledger_note` 那段："对齐盘上 `stigmergy` 的先例"）
   —— **是设计选择，不是漏掉；但仍然是一次真写盘。**
2. **零作用域 ≠ 没门**。本域的门在**模块自己**：九道闸 + 两道静态核。
   ⇒ **别把"policy 没有分支"读成"这事没人管"。**
3. **`status:"ok"` ≠ 本体 `ok:true`**。本域这一版实测**外层与本体没打架**（只读那六条外层 ok + 本体 `ok:true`），
   但 **`deposit` 的九条拒绝是"外层 ok + 内层 `ok:false` + `denied:true`"**（源码所见）
   ⇒ **外层根本看不出拒绝**。判"这一发调用成功了吗"看外层；判"被检对象合规吗"看内层。
4. **退出码不可信**。本域实测：只读成功 exit **0**；**内层拒绝（`deposit` 被闸拒）也 exit 0**；
   只有 `run_task` 层的 `denied` 才 exit **1**（本域零作用域，所以**够不到那一层**）。
   `stamp: true/false` 是**回归印章的有无**，不是成功与否。
5. **"挥发"≠"删除"**。`DECAY` 的 `deleted` **恒为 0**；`rows` 只增不减、账本可回放。
   ⇒ **别把 `decay` 读成"清理"，也别把 `deleted:0` 读成"这次没删到"。**
6. **"能调" ≠ "能用"**。`stigmergy` 在 `omni.auto_run_verdict()` 里实测 **`AUTO=True`**（零作用域 + 无必填参数），
   但**那个 AUTO 只覆盖"空载荷跑一发 status"** —— 它**完全不保证** `deposit` 能留、`read` 有东西可读。
   ⇒ **AUTO 判的是"这个位空参能不能自动跑"，不是"这个位能不能干活"。**
7. **同名不同义**：`readonly` 在本模块是**逐 op 真标**（`deposit` 返回 `false`），
   而在 `gbt-infra` 的 `gate_official` 里它是**常量**。⇒ **引字段前先看它在哪个模块、哪个分支。**
8. **"源码里出现某关键词"不是"源码真的用了它"**：`gate_append_only` 自己就吃过这个亏
   （文本关键词判据 ⇒ 注释里提一句就过关 ⇒ 假绿），现改走 **AST 真引用**且解析不了**按未测处理（fail-closed）**。
   ⇒ **引"源码写着 X"必须给行号，不给"我搜到了"。**
9. **"图鉴是索引，实测才是读数"**：注册表 desc 说四原语、五红线、只追加，实测逐条对上；
   但 desc **没有**告诉你"DEPOSIT 在 policy 层零作用域" —— 那要**现查**。

---

## 11. 不许做什么（红线）

1. **不许给自己发授权**：不跑 `auth grant`、不手写 `store/auth_grants.jsonl`、不改 `security/policy.py` / `auth_gate`。
2. **不许绕门**：不许为了"绕过授权/绕过闸门"直接调 `gbt_allinone.tools.stigmergy` 里的函数替掉
   `run_task` 唯一门（AGENTS.md 明令：那是**未经授权的写入**，纪律上就是违规）。
3. **不许删行 / 不许覆写账本**（本模块的第三条红线，且由 `gate_append_only` **静态核源码**守着）。
   挥发只算不删。
4. **不许无源留痕**（`source` 必填，"否则场地会变谣言"）。
5. **不许自己加种类**（白名单只有 `task`/`path`/`danger`/`resource`，每条都有半衰期）。
6. **不许把明文密钥写进 `note`**（命中即拒；本规程示例不带任何真密钥）。
7. **不许让 `READ`/`FORAGE` 触发任何外部动作**（第五条红线：**只给读数**）。
8. **不许把 `collab_gateway` 的规则名当能力位去 `cap`**：那些名字**不在图鉴里**，
   写成 `cap` 命令就是**编造命令**（本规程 §0 那条 ⚠️ 的原因）。
9. **不许把"场地是空的"说成"能力不可用"**（源码原话："照实说、不编"）。
10. **不许改 `tools/codex-scripts/omni.py`**（本域登记行由交付报告给出，不擅自动手）；
    **不许动别的域**、不许改 `policy.py`。

---

## 12. 固化与出处（**重启后要在**）

| 什么 | 在哪 |
|---|---|
| 本规程（源） | `<仓>/skills/gbt-collab/SKILL.md` |
| 本规程（装机·托管目录） | `C:\Users\ADMIN\.openclaw-autoclaw\skills\gbt-collab\SKILL.md` |
| ⛔ **不许装到** | `~/.agents/skills/`（本仓 AGENTS.md 明令禁止） |
| 能力位名单（1 个：`stigmergy`） | `<仓>/state/skill_atlas.json`（`domain == "collab"`）· 现扫可重建：`python tools/codex-scripts/omni.py build` |
| 授权判据（**单一真相**） | `<仓>/gbt_allinone/security/policy.py` 的 `evaluate()` —— ⚠️ **本域在里面没有任何分支**（这就是"零作用域"的来源）；**同族先例的援引在 `ledger_note` 那段注释（第 349-354 行）** |
| op 分发 | `<仓>/gbt_allinone/api.py:494-498`（`kind == "stigmergy"` 那一支） |
| 实现（四原语/五红线/九闸） | `<仓>/gbt_allinone/tools/stigmergy.py`（`run()` 326；`deposit()` 121；`read()` 170；`decay()` 211；`forage()` 231；`check_kinds()` 274；`check_append_only()` 287；`HONEST_BOUNDARY` 371） |
| 直连通道（**别域**） | `<仓>/gbt_allinone/collab_gateway.py`（会话 / 对等方 / 提案收件箱） |
| 静态核工具 | `<仓>/gbt_allinone/tools/source_judge.py` 的 `uses_name`（AST 真引用判据）· `<仓>/gbt_allinone/safe_io.py` 的 `locked_append_text` |
| 门与拒绝信封 | `<仓>/gbt_allinone/run_task`（唯一门）· `tools/codex-scripts/five-dim.py:131-172`（扁平信封的读法） |

**深蒸登记（应加、本次未擅自动手 —— 登记由主人统一做）**：`omni.py` 的 `DISTILLED_DOMAINS` 加一行

```python
    "collab": "gbt-collab",
```

加完后 `python tools/codex-scripts/omni.py gaps` 里 `collab 1 个能力位` 会从
`⏳ 在队里` 变成 `✅ 已深蒸 → gbt-collab`。

**验收（做完怎么证明真的做了）**：

```powershell
py -3.14 tools/codex-scripts/verify-distill.py --domain collab --skill gbt-collab
```

1. 上面这条必须 **PASS**（覆盖 1/1）；
2. 两份产物**逐字节相同**（sha256 一致）；
3. 再静态查一次 `policy.evaluate("stigmergy", {"op":"deposit"}).scopes` —— 必须**仍是空**，
   且当场再看一眼 `storage/collab/stigmergy/pheromones.jsonl` 的行数有没有变
   （**"零作用域"与"没写盘"是两件事，要分别取证**）；
4. 声明"某 op 能用"之前，先问自己：**这条是实测读数，还是我读错了地方？** 拿不准就写"未验"。
