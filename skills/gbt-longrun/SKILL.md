---
name: gbt-longrun
displayName: GBT · longrun 职业域用法规程（4 个能力位）
version: 1.0.0
description: GBT小土豆V8 的 `longrun` 职业域（长程任务/无人值守/跨进程续跑/察言观色）用法规程。把图鉴里这 4 个能力位逐个点清：用途、只读还是要授权、要哪个作用域、怎么调、要什么参数、失败长什么样；规定本域唯一入口是万能插 `five-dim.py cap <能力位>`、授权判据静态可查（本域四位**静态全是零作用域**）、授权只能主人在终端发；并记下本机实测过的读数陷阱（图鉴把 `lr_tick` 标成"无需参数、无侧效应"，而 `preflight` 明写它会改状态、`omni` 据此拒绝自动跑——**同一份仓里两处说法不一致，以 preflight/omni 为准**；`lr_submit` 缺 `description` 会先报错再写盘）。当用户要用长程任务图（提交/推进/查进度）、要跨进程续跑无人值守任务、要给卡住的任务升级、要判断"这话该怎么说"，或某个 longrun 能力位报 user_error、读数对不上时使用。
triggers:
  - "长程任务"
  - "长程"
  - "任务图"
  - "无人值守"
  - "跨进程续跑"
  - "断点续作"
  - "lr_submit"
  - "lr_tick"
  - "lr_status"
  - "tactics_advise"
  - "察言观色"
  - "沟通分寸"
  - "升级包"
  - "stalled"
  - "longrun"
---

# GBT · longrun 职业域用法规程（4 个能力位）

> 开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属
>
> **这份规程解决什么**：`longrun` 域只有 4 个能力位，但它**不是"四个只读小工具"** ——
> 它是**唯一一条"跨进程可续"的写面**：`lr_submit` 往任务图里落盘，`lr_tick` 会**真的执行**图里的能力位并回写状态。
> 本域最大的坑不是"用错命令"，而是**读数把写动作读成只读**：
> ① 图鉴里 `lr_tick` 写着 `requires_params: []` + `needs_confirmation: false`（看着像免卡只读），
>    而 `gbt_allinone/preflight.py` 的 `_STATE_CHANGING_KINDS` **明写它"会改状态"**，`omni` 据此拒绝自动跑；
> ② `policy.evaluate()` 给这四位**全是零作用域**，于是"没有授权也能调"被误读成"所以它安全"。
> ⇒ **本文件把"哪个位、什么时候用、要不要授权、失败长什么样、读数该看哪一处"逐个钉死**，
> 并把**本机实测过的读数**如实记下来 —— **没验过的一律写"未验"，不冒充验过**。

**唯一现读入口（别信任何二手描述，包括本文件）**：

```powershell
py -3.14 tools/codex-scripts/five-dim.py cap <能力位> ['<JSON载荷>'] [--full]
```

`cap` 一律走 `gbt_allinone.run_task`（**唯一门**）；默认收窄 `result`，要全量加 `--full`。
被门拒绝就**如实报缺什么作用域**，不绕路。

---

## 0. 这 4 个位分两簇（先认簇，再看位）

| 簇 | 位（kind） | 共 | 共同特征 |
|---|---|---|---|
| **A · 长程任务图** | `lr_submit` · `lr_tick` · `lr_status` | 3 | 同一个落盘文件 `gbt_allinone/store/tasks.json`；跨进程可续；**两位会写盘（`lr_submit`/`lr_tick`），一位只读（`lr_status`）** |
| **B · 察言观色层** | `tactics_advise` | 1 | **纯只读**：纯文本启发式，零模型调用、零外部依赖、**不落盘**（只读可选的 `store/user_style.json`） |

**判据**：要**排队/推进/查**无人值守任务 → A（**先看 `lr_status`，再决定要不要动 `lr_tick`**）；
要**决定"这话该怎么说"**（语气/篇幅/结构，不改事实）→ B。

### 4 个位的确切名单（**以 `state/skill_atlas.json` 里 `domain == "longrun"` 的 `kind` 为准**）

| kind | 图鉴 desc（原文） | `enabled` | `safe` | `handler` | `requires_params` | `params_hint` | `needs_confirmation` | `disabled` | `channel` |
|---|---|---|---|---|---|---|---|---|---|
| `lr_submit` | 长程任务层：提交任务（非LLM验收+重试+停滞升级，跨进程可续） | true | true | `lr_submit` | `[]` | `""` | **true** | false | `omnipulg` |
| `lr_tick` | 长程任务层：推进任务图（执行→验收→完成/重试/停滞） | true | true | `lr_tick` | `[]` | `""` | **false** | false | `omnipulg` |
| `lr_status` | 长程任务层：任务图进度与详情 | true | true | `lr_status` | `[]` | `""` | false | false | `omnipulg` |
| `tactics_advise` | 察言观色层：识别沟通信号→给出表达分寸（只调怎么说，不改事实） | true | true | `tactics_advise` | `[]` | `""` | false | false | `omnipulg` |

**确切条数：4 个**（`python tools/codex-scripts/omni.py gaps` 现算：`⏳ 在队里  longrun  4 个能力位  lr_submit、lr_tick、lr_status、tactics_advise`）。
🔴 **表里那四个 `requires_params: []` 是"图鉴的登记"，不是"空调用都成立"** —— 见 §5 第 1 条。

---

## 1. 什么时候用（意图 → 落点）

| 人想干什么 | 落到哪个位 | 只读还是要授权 | 会不会写盘 |
|---|---|---|---|
| 看长程任务还剩多少、哪个卡住了 | `lr_status` | **只读**（零作用域） | 不写 |
| 看某一个任务的详情（含升级包） | `lr_status` + `{"task_id":"T0001"}` | **只读**（零作用域） | 不写 |
| 往任务图里排一个新任务 | `lr_submit` | **零作用域，但会写盘 + 起长程任务** | ✅ 写 `store/tasks.json` |
| 推进任务图（跑下一个待办、验收、重试/停滞升级） | `lr_tick` | **零作用域，但 `preflight` 判定"会改状态"** | ✅ 挑到任务就写 `store/tasks.json` |
| 判断对方现在是急/累/受挫/满意/怀疑，该怎么说 | `tactics_advise` | **只读**（零作用域） | 不写 |
| 任务卡住要"带着方案回来" | `lr_tick` 触发 → 内调 `tactics.escalate()` 产出升级包（见 `lr_status` 的 `escalation`） | 走 `lr_tick` 那条门 | 随 `lr_tick` |

**不在这 4 个里的事**：屏幕/点击/读网页 → `gbt-tentacle`（`tentacle` 域）；
通用"长程无人值守任务监督（租约/心跳/检查点/有界重试）" → **`long_run_supervisor`**，注意它**属于 `tentacle` 域**（`omni ask "推进长程任务图"` 实测：`long_run_supervisor` 判 `✅ 只读无参，可直跑`，域是 `tentacle`）；
定时谁去推动 → `sched_tick`（`engine` 域）；`wf_*` 是进程内工作流 DAG（`engine` 域，秒~分钟级），**与 longrun 的跨进程任务图是两条路**：
`engine` = 单个工作流 DAG 并行（进程内，带检查点）；`longrun` = 跨进程长任务图（小时~天级，检查点天然落盘）；`schedule` = 谁来推动。

---

## 2. 怎么调（万能插唯一门）

```powershell
# ── A · 长程任务图 ──
py -3.14 tools/codex-scripts/five-dim.py cap lr_status                                  # 只读：全图进度 + 任务列表
py -3.14 tools/codex-scripts/five-dim.py cap lr_status '{"task_id":"T0001"}'            # 只读：单任务详情
py -3.14 tools/codex-scripts/five-dim.py cap lr_submit '{"description":"<任务描述>","kind":"<已注册能力位>","params":{},"priority":"medium","acceptance":["status_ok"],"max_attempts":3}'   # ⚠ 落盘 + 起长程任务
py -3.14 tools/codex-scripts/five-dim.py cap lr_tick '{"max_tasks":1}'                   # ⚠ preflight 判"会改状态"

# ── B · 察言观色层 ──
py -3.14 tools/codex-scripts/five-dim.py cap tactics_advise                              # 只读：空输入 → 默认分寸
py -3.14 tools/codex-scripts/five-dim.py cap tactics_advise '{"user_text":"<对方原话>","situation":"normal|stalled|failed|blocked"}'

# 要全量 result（默认会收窄成摘要）：尾部加 --full
py -3.14 tools/codex-scripts/five-dim.py cap lr_status --full
```

🔴 **PowerShell 里传 JSON 载荷：用单引号原样包住 JSON**（`'{"max_tasks":1}'`）。
写成 `'{\"max_tasks\":1}'` 会让 `five-dim.py` 的 `json.loads` 直接抛
`JSONDecodeError: Expecting property name enclosed in double quotes` —— **还没碰到门就死了**，而且看起来像"命令写错了"。

**另一条入口（GUI，不是命令）**：`gbt_allinone/app.py` 有「长程任务面板」（`run_task("lr_status", {})`）与「推进任务图」
（`run_task("lr_tick", {"max_tasks": 3})`）两个按钮 —— **同一个唯一门，只是有界面**。命令与它等价，别把 GUI 当第二条路。

---

## 3. 要过哪道门：**静态查，不靠跑它才知道**

```python
from gbt_allinone.security import policy
d = policy.evaluate(kind, payload)      # 只读求值，不执行、不消耗授权
list(d.scopes)                          # → 这个位要过哪几个作用域
d.restricted                            # → bool(scopes)
```

**本域静态查出来的全量（2026-09-22 实测，逐位 × 5 种 payload 形态核对过 `policy.py`）**：

| 位 | `scopes` | `restricted` | `risk` | 说明 |
|---|---|---|---|---|
| `lr_submit` | `[]` | false | `low` | `policy.py` 里**没有** `lr_submit` 这条分支 ⇒ 零作用域 |
| `lr_tick` | `[]` | false | `low` | 同上 |
| `lr_status` | `[]` | false | `low` | 同上 |
| `tactics_advise` | `[]` | false | `low` | 同上 |

实测的 5 种 payload 形态（`{}` · `{"op":"advise"}` · `{"op":"status"}` · `{"action":"submit"}` · `{"method":"x"}`）
**四位 × 五种结果完全一致**：`scopes=[]` · `restricted=False` · `risk=low`。
⇒ **这四位没有任何"换个 op 就变受限"的隐藏分支**（与 `prompt_bridge` / `notion` 那种 fail-closed 完全不同）。

**授权只能主人在终端发**（发之前先想清楚：本域四位**根本不需要作用域**，别去为一个不需要门的动作要授权）：

```powershell
python -m gbt_allinone auth grant --scope <作用域> --ttl 600
python -m gbt_allinone auth status
```

🔴 **AI 永远无权给自己发授权** —— 缺授权就如实报缺，**不找旁路、不改 `security/policy.py`、不改 `auth_gate`**。

### 3.1 🔴 "零作用域" ≠ "可以随便自动跑"（**本域最大的口径坑**）

门有两层，**别只看第一层**：

| 层 | 在哪 | 本域读数 |
|---|---|---|
| ① 授权门 | `gbt_allinone/security/policy.py` 的 `evaluate()` | 四位**全零作用域** ⇒ 不消耗授权 |
| ② 状态变更判据 | `gbt_allinone/preflight.py` 的 `_STATE_CHANGING_KINDS`（`preflight.py:47-59`） | **`lr_submit` 与 `lr_tick` 在名单里**（`lr_status` / `tactics_advise` 不在） |

`_STATE_CHANGING_KINDS` 的注释原文（`preflight.py:45-46`）：

> 安全策略没有覆盖、但会改变框架自身状态的动作；新增动作默认在这里显式声明，
> **不能靠"没写 scope"就当只读**。

**`omni` 的自动执行判据同时吃这两层**（实测输出，2026-09-22）：

```powershell
py -3.14 tools/codex-scripts/omni.py ask "推进长程任务图"
#   [8.5] lr_tick  ... → cap lr_tick   🔒 不自动跑：框架自己的 preflight 把它列为**会改状态**（不是只读）
#   [7.0] lr_status ... → cap lr_status ✅ 只读无参，可直跑
#   [5.5] lr_submit ... → cap lr_submit 🔒 不自动跑：在侧效应名单里，要人确认 / 名字带写动作字样（deploy/release/publish/…） / 框架自己的 preflight 把它列为**会改状态**（不是只读）
#   [1.0] tactics_advise ... → cap tactics_advise ✅ 只读无参，可直跑
```

⇒ **本域正确口径**：**只有 `lr_status` 与 `tactics_advise` 是"只读、可直跑"**；
`lr_submit` / `lr_tick` **零作用域但会改状态**，**不许因为它们不要授权就当只读自动跑**。
`omni run` 也不会替你跑这两位（它按 `auto_run_verdict` 默认拒绝）。

---

## 4. 4 个能力位逐个点（实测读数 + 失败典型）

> 下表 `门` 列 = §3 静态查出来的作用域；`实测` 列 = **本机真跑过的关键字段**；
> 没真跑的一律写**未验**并说明卡在哪。

### A · 长程任务图

| 位 | 用途 | 门 | 参数（源码为准） | 实测关键字段 | 失败典型样子 |
|---|---|---|---|---|---|
| `lr_status` | 任务图进度与详情 | 无（零作用域） | 可选 `task_id`（`api.py:177-179`） | **无参**：`status ok` · `stamp true` · `denied false`；`result.progress {total 58, done 33, failed 25, stalled 0, pending 0}` · `result.tasks` 为**全量任务数组**（本机 58 条）；单条字段：`task_id` `description` `kind` `params` `priority` `depends_on` `acceptance` `max_attempts` `attempts` `status` `fingerprints` `last_error` `created_at`（有升级包时还有 `escalation`）。**给 `task_id`**：`result` 直接是**那一条任务对象**（本机 `T0001` 实测：`last_error "人工授权门拒绝（未授权操作）"` · `escalation.options` 三条方案） | **`task_id` 不存在**：`status error` · `stamp false` · `denied false` · exit **1**；`result {status "error", kind "lr_status", message "任务不存在: T9999", error_class "user_error"}`。🔴 **这是 `user_error`、不是 `denied`** —— 别读成"没授权" |
| `lr_submit` | 提交任务（非LLM验收+重试+停滞升级，跨进程可续） | 无（零作用域）**但仍会写盘** | **必填** `description`（`longrun.py:52-53`）· **必填** `kind` 且必须是 `BENIGN_CAPS` 里的已注册能力位（`longrun.py:54-55`）· 可选 `params` `priority`(high/medium/low) `depends_on` `acceptance` `max_attempts`(默认 3) | ⛔ **未验**（本规程**没跑**它：一跑就往 `store/tasks.json` 落一条新任务并 `audit("longrun_submit")`，等于真起长程任务）。**源码可读到的成功形状**：`{"ok": True, "task_id": "T00NN"}`（`longrun.py:80`）；落盘字段见 `longrun.py:61-75`；`acceptance` 缺省 `["status_ok"]` | **卡在哪**：卡在纪律"会写盘的不真跑"。**源码可读到的失败形状**（未跑，但每条都在**产生任何副作用之前**抛）：缺 `description` → `LongrunError("需要 description")`；`kind` 未注册 → `LongrunError("能力未注册: <kind>（只能编排已注册能力）")`；`priority` 非法 → `LongrunError("priority 必须是 high/medium/low")`。经唯一门时应被 `api.py` 包成 `status error` · `error_class user_error` · exit 1（同 `lr_status` 的 `user_error` 信封形状）——**这一步未验** |
| `lr_tick` | 推进任务图（执行→验收→完成/重试/停滞） | 无（零作用域）但 **`preflight` 判"会改状态"** | 可选 `max_tasks`（默认 **1**，`api.py:176`；`longrun.py:138` 取 `max(1,int(max_tasks))`） | **空队列实测**（`{"max_tasks":1}`）：`status ok` · `stamp true` · `denied false` · exit **0**；`result {ran [], progress {total 58, done 33, failed 25, stalled 0, pending 0}}`。**同一发的前后哈希证明没写盘**：`store/tasks.json` SHA256 `FBEA8301…2EB1D3` **前后一致**、`LastWriteTime` 不变（`_save()` 在 `longrun.py` 里写在挑到任务的循环体内，**空队列 ⇒ 循环直接 break ⇒ 一次都没写**）。审计侧另有 `preflight_checked … "side_effect": true`（`preflight.py` 自己认定它是侧效应动作） | **有 pending 时会真执行**：挑任务 → `run_task(...)` → Judge 验收 → `done` / 重试 / `stalled`（同指纹出现 **3** 次）/ `failed`（`attempts >= max_attempts`），**并写盘**。🔴 **本机现在 `pending 0`，所以"挑到任务那条路"本规程没跑（未验）** —— 不许拿空队列的读数说"lr_tick 是只读的" |

**Judge（非 LLM 验收）的验收标准（`longrun.py:97-127`，源码为准）**：
`status_ok`（唯一"完成"判定，缺省）· `contains:<关键词>`（在整份结果 JSON 的小写串里找）· `file_exists:<路径>` · `no_error`。
**未知标准一律判失败**（`未知验收标准: <c>`）—— 不认识的写法**不会**被放过。
🔴 另有一条硬判据：**授权门拒绝如实传导为失败**（`longrun.py:100-103`）——
`denied` 意味着操作根本没执行，**不算任务成功**。本机历史任务里就有一批 `last_error "人工授权门拒绝（未授权操作）"` 的 `failed`。

### B · 察言观色层

| 位 | 用途 | 门 | 参数（源码为准） | 实测关键字段 | 失败典型样子 |
|---|---|---|---|---|---|
| `tactics_advise` | 识别沟通信号 → 给出表达分寸（只调怎么说，不改事实） | 无（零作用域） | 可选 `user_text`、`situation`（`api.py:813-816`）——**两位都可缺** | **空调用**：`status ok` · `stamp true` · exit 0；`result {posture "default", detected {}, situation "normal", tone "正常专业表达：结论先行，依据跟上，下一步明确", require [结论先行/依据可核/下一步明确], honesty [三条]}`。**`{"user_text":"这个急，马上要","situation":"stalled"}`**：`posture "steady_problemsolve"` · `detected {"urgency":["急","马上"]}` · `tone "先接住再解决，不辩解、不甩锅"` · `require ["先确认问题现象","给出根因或明确说还在查","带 2~3 个方案回来"]` · `situation "stalled"`。**`{"user_text":"还是不行，怎么又错了，我累了先这样","situation":"failed"}`**：`detected {"fatigue":["累了","先这样"],"frustration":["还是不行","又错","怎么又"]}` · `posture "steady_problemsolve"`（**`situation` 覆盖了情绪优先序**） | **它几乎不会"失败"** —— 空输入、乱输入都回 `ok`。🔴 **实测踩到的静默陷阱**：传 `{"op":"bogus"}` 它**不报错**，照样 `ok` 并回默认分寸（`posture "default"` · `detected {}` · `situation "normal"`）—— 因为它内部根本没有 `op` 概念，**未知键被无视**。⇒ 想让它按你的意思走，**必须用 `user_text`/`situation` 这两个真参数名**，写错键名会静默变成"默认分寸"，看起来像"识别不出来" |

**三样东西是什么（源码 `tactics.py:24-59`、`111-144`）**：
- `detected`：五维信号命中表 —— `urgency` / `fatigue` / `frustration` / `celebration` / `doubt`；
- `posture`：表达分寸，五选一 + 默认 —— `results_first`(急) / `compress`(累) / `steady_problemsolve`(受挫) / `credit_concrete`(成了) / `reanchor`(怀疑) / `default`；
- `honesty`：**不可逾越的三条铁律** —— 只调表达分寸不改事实 / 坏消息如实到达不隐藏不稀释 / 识别到困难必须带方案。
  优先级：**`situation ∈ {stalled, failed, blocked}` 一律覆盖成 `steady_problemsolve`**（`tactics.py:122-123`）；
  否则按 `urgency > frustration > doubt > fatigue > celebration` 取第一个命中（`tactics.py:88`）。

---

## 5. 🔴 读数红线（先问"这是事实，还是我读错了地方"）

1. **图鉴的 `requires_params: []` 不等于"空调用都成立"**。本域四位图鉴都是 `[]`，但源码里：
   `lr_submit` **缺 `description` 直接抛 `LongrunError("需要 description")`**（`longrun.py:52-53`）。
   ⇒ **以源码为准**；图鉴的 `[]` 只说明"没被登记进 `caps_registry.PARAM_REQUIRED`"。
   （同族的真事故先例：`brain_route` 曾因没登记而被判 AUTO，`omni run` 替你跑一发拿到 `user_error`，
   2026-09-22 已补登 —— 见 `caps_registry.py:1014-1021` 的注释。）
2. **`needs_confirmation` 与 `preflight` 会打架，以 `preflight` 为准**。图鉴里 `lr_tick` 是 `needs_confirmation: false`，
   而 `preflight.py:47-59` 的 `_STATE_CHANGING_KINDS` **把它列为"会改状态"**，`omni ask` 实测打的是
   `🔒 不自动跑：框架自己的 preflight 把它列为**会改状态**（不是只读）`。
   ⇒ **同一份仓里两处说法不一致；`omni`（实际执行判据）站在 `preflight` 那边**。
   本次**没有改图鉴**（那要动 `caps_registry` / 图鉴生成物，超出本件范围）—— **如实记录这个漂移**。
3. **扁平拒绝信封：读顶层，别只盯 `gbt_result`**（`five-dim.py:132-153` 的 R-H299 注释，拿一次事故换的）。
   被门拒绝时**没有 `gbt_result`**，`denied` / `missing_scopes` / `reason` / `how_to_grant` / `note` 全在**顶层**，
   `result` 里另有一份。原来只读 `r["gbt_result"]` ⇒ 打出来是 `status: unknown · denied: false`——**门说拒了、报表说没拒**。
   `five-dim.py` 现在的读法：`gr = r.get("gbt_result") or r`，`denied` 由
   `status == "denied"` / `denied is True` / `missing` 非空 / `missing_scopes` 非空 **四者之一**判定。
4. **`stamp: true/false` 是回归印章的有无，不是成功与否**。本域实测：成功的 `lr_status` / `lr_tick` / `tactics_advise`
   都是 `stamp true`；失败（`lr_status` 的 `user_error`）是 `stamp false`。**别把 `stamp` 当 `ok`**。
5. **退出码**：`ok`/`success` → 0；**`denied` 与 `error` 一律 → 1**（`five-dim.py:163`）。
   **别把 exit 1 一律读成"命令敲错了"** —— 先看 `status` 是 `denied`、`error` 还是别的。
   本域实测：`lr_status '{"task_id":"T9999"}'` → `status error` · `error_class user_error` · exit 1。
6. **`status:"ok"` ≠ 内层业务 `ok:true`**。`five-dim.py` 打出来的 `status` 是**门/信封**的读数
   （它取 `gr.get("status") or ("ok" if r.get("ok") else "unknown")`）；业务结果里可能有自己的 `ok`。
   本域现成例子：`lr_tick` 外层 `status ok`，而 `result.ran` 是 **`[]`** ——
   **"命令成功"和"真的推进了任务"是两件事**：空队列时它成功但什么也没推进。
   同理 `lr_status` 外层 ok，而 `progress.failed 25` 说明图里有一堆失败任务。
7. **`lr_tick` 会执行"图里那个能力位"，不是你指定的能力位**。它 `run_task(t["kind"], t.get("params"))`
   （`longrun.py:142`）—— 图里排的是什么就跑什么，**包括需要授权的作用域动作**；
   被门拒绝会如实判失败（`longrun.py:100-103`）。⇒ **推进任务图之前先用 `lr_status` 看清图里排了什么**。
8. **本域四位"零作用域"不等于"本域安全"**：`lr_submit` / `lr_tick` 是**真写口**
   （落盘 `store/tasks.json` + 审计）。门没拦是因为**策略层根本没给它们挂作用域**，不是因为它们只读。

---

## 6. 不许做什么（红线）

1. **不许给自己发授权**：不跑 `auth grant`、不手写 `store/auth_grants.jsonl`、不改 `security/policy.py` / `auth_gate`。
   （本域四位本来就不要作用域，**更没有任何理由去发**。）
2. **不许绕门**：不许为了"绕过门"直接调 `gbt_allinone.longrun.submit()` / `.tick()` 替掉 `run_task` 唯一门
   （AGENTS.md 明令：那是**未经授权的写入**，纪律上就是违规）。`lr_tick` 自己内调时走的是 `from .api import run_task`
   —— **它都走门，你更不该跳过**。
3. **不许把"零作用域"读成"只读可自动跑"**：`lr_submit` / `lr_tick` 会改状态（见 §3.1）。
4. **不许拿空队列的 `lr_tick` 读数冒充"它是只读的"**：本机 `pending 0`，那一发只是"没活干"，
   挑到任务那条路**未验**。
5. **不许把 `tactics_advise` 当"话术表演"用**：它的三条 `honesty` 铁律是硬的 ——
   **只调怎么说，绝不改说什么**；坏消息如实到达，不隐藏不稀释。
6. **不许把没验过的写验过**：`lr_submit` 全路径、`lr_tick` 有任务路径一律标**未验 + 卡在哪**。
7. **不许改 `tools/codex-scripts/omni.py`**（本域登记行由交付报告给出，不擅自动手）；
   **不许动别的域**、不许改 `policy.py`。

---

## 7. 验收（做完怎么证明真的做了）

1. **只读两位必须真跑**：
   `py -3.14 tools/codex-scripts/five-dim.py cap lr_status --full` → 拿 `progress` 五个计数（本机 `total 58 / done 33 / failed 25 / stalled 0 / pending 0`）；
   `py -3.14 tools/codex-scripts/five-dim.py cap tactics_advise '{"user_text":"<原话>"}'` → 拿 `posture` + `detected` + `require`。
2. **静态门核对**：四位 `policy.evaluate(kind, payload)` 都应 `scopes=[]` · `restricted=False` · `risk=low`
   （不一致就是某处漂移了，回来改本文件）。
3. **写盘前先看**：动 `lr_tick` 之前先 `cap lr_status`，确认图里 pending 的 `kind` 是你愿意让它跑的；
   跑完用 `lr_status` 复核 `progress` 有无变化。
4. **哈希留证**：任何"这一发没写盘"的声明，要拿 `store/tasks.json` 的**前后 SHA256** 说话，不是"我觉得没有"。
5. 声明"某位能用"之前，先问自己：**这条是实测读数，还是我读错了地方？** 拿不准就写"未验"。

---

## 8. 固化与出处（**重启后要在**）

| 什么 | 在哪 |
|---|---|
| 本规程（源） | `<仓>/skills/gbt-longrun/SKILL.md` |
| 本规程（装机·托管目录） | `~/.openclaw-autoclaw/skills/gbt-longrun/SKILL.md` |
| ⛔ **不许装到** | `~/.agents/skills/`（本仓 AGENTS.md 明令禁止） |
| 能力位名单（4 个） | `<仓>/state/skill_atlas.json`（`domain == "longrun"`）· 现扫可重建：`python tools/codex-scripts/omni.py build` |
| 注册表登记（desc/safe/handler） | `<仓>/gbt_allinone/caps_registry.py`（`lr_submit` 152 · `lr_tick` 158 · `lr_status` 164 · `tactics_advise` 518） |
| 处理器与路由 | `<仓>/gbt_allinone/api.py`（`lr_*` 167-179 · `tactics_advise` 813-816） |
| 长程任务图实现（**唯一写面**） | `<仓>/gbt_allinone/longrun.py`（落盘 `store/tasks.json`） |
| 察言观色实现（**纯只读**） | `<仓>/gbt_allinone/tactics.py` |
| 授权判据（**单一真相**） | `<仓>/gbt_allinone/security/policy.py` 的 `evaluate()` |
| 状态变更判据（**第二层**） | `<仓>/gbt_allinone/preflight.py` 的 `_STATE_CHANGING_KINDS`（47-59） |
| 门与拒绝信封 | `<仓>/gbt_allinone/run_task`（唯一门）· `tools/codex-scripts/five-dim.py:132-163`（扁平信封的读法） |
| 自动执行判据 | `<仓>/tools/codex-scripts/omni.py` 的 `required_scopes()` / `auto_run_verdict()` |
| 人话落点 | `python tools/codex-scripts/omni.py ask "推进长程任务图"` → 落到 `lr_tick`（`omnipulg` 通道，实测判 🔒 不自动跑） |

**深蒸登记（应加、本次未擅自动手）**：`omni.py` 的 `DISTILLED_DOMAINS` 加一行

```python
    "longrun": "gbt-longrun",
```

加完后 `python tools/codex-scripts/omni.py gaps` 里 `longrun 4 个能力位` 会从
`⏳ 在队里` 变成 `✅ 已深蒸 → gbt-longrun`（本次实测它现在的状态就是
`⏳ 在队里  longrun  4 个能力位  lr_submit、lr_tick、lr_status、tactics_advise`）。
本件交付时**未改 `omni.py`** —— 按纪律由交付报告给出这一行，由人来落。
