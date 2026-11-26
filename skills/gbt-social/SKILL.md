---
name: gbt-social
displayName: GBT · social 职业域用法规程（1 个能力位：auto_publish）
version: 1.0.0
description: GBT小土豆V8 的 `social` 职业域（社交推广 / 发布作品 / 收益平台）用法规程。这个域**只有 1 个能力位**：`auto_publish`。本文件把它写全：用途、五原语 PLAN·COMPOSE·PUBLISH·TRACK·SETTLE 逐个标「可不可逆 / 涉不涉钱 / 要不要过门」、六条红线、逐 op 静态查出来的作用域（**整位零作用域，连 PUBLISH 也是零** —— 门不在 policy，在模块自己的 gate_publish）、真命令、16 个 op 逐个点名、外部面（平台名单主人未给 ⇒ 一个平台名都不编；密钥 DPAPI；留痕 source_kind=publish）、失败典型样子、与 `gbt-lark` / `account_registry` / `coze_mail` 的边界；并记下实测读数（gate_publish 默认拒「发布」；gate_publish 对 plan 放行；gate_withdraw 拒提现；gate_metrics 拒刷量；gate_accounts 拒共用账号；gate_key 拒明文凭据）。当用户要发布作品 / 排期 / 成稿 / 追踪数据 / 汇总收益，或 auto_publish 报 irreversible_needs_gate / withdraw_needs_auth / fake_metrics / account_shared / not_implemented 时使用。
triggers:
  - "发布作品"
  - "社交推广"
  - "发布"
  - "排期"
  - "成稿"
  - "收益"
  - "提现"
  - "改价"
  - "追踪数据"
  - "auto_publish"
  - "social"
  - "全自动发布"
  - "irreversible_needs_gate"
  - "withdraw_needs_auth"
  - "fake_metrics"
---

# GBT · social 职业域用法规程（1 个能力位：`auto_publish`）

> 开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属
>
> **这份规程解决什么**：`social` 是一个**一位一域**的小域，但它身上压着**全仓最容易被说歪的一句话**：
> **"全自动"**。模块 docstring 把它钉死了 ——
> **"全自动 = 除「发布 / 提现 / 改价」之外全自动"**。
> 那三下**不可逆 + 出网 + 涉钱** ⇒ 必须过门。把"全自动"说成"连发布也不问"，
> 就是把**不可逆**当**可逆**。
> 另有两条必须同时记住：① **policy 层整位零作用域**（连 `publish` 都是零）——
> 门**不在 policy，在模块自己的 `gate_publish`**；② **现状是"只给边界、不给发"**（平台名单主人未给 ⇒
> 五个动作一律 `not_implemented`）。⇒ **"零作用域 ≠ 只读"** 与 **"能调 ≠ 能用"** 在本域同时成立。
> 本文件把「哪个 op、要不要过门、门在哪一层、失败长什么样、读数该看哪个字段」逐个钉死，
> 并把**本机实测过的坑**如实记下来 —— **没验过的一律写"未验"，不冒充验过**。

**唯一现读入口（别信任何二手描述，包括本文件）**：

```powershell
py -3.14 tools/codex-scripts/five-dim.py cap auto_publish ['<JSON载荷>'] [--full]
```

`cap` 一律走 `gbt_allinone.run_task`（**唯一门**）；被门拒绝就**如实报缺什么作用域**，不绕路。

---

## 0. 一位一域（先确认名字，别照抄别人的表）

现扫 `state/skill_atlas.json`（`domain == "social"`）**只有一条**：

| 域 | 能力位（kind） | handler | type | 注册表 desc 原文 |
|---|---|---|---|---|
| `social` | **`auto_publish`** | `auto_publish` | **`external`** | "社交推广 / 发布作品 / 收益平台·**全自动执行**（只读骨架·门）：五原语 PLAN/COMPOSE/PUBLISH/TRACK/SETTLE；核心口径 = **全自动 = 除「发布/提现/改价」之外全自动**（那几下不可逆+涉钱 ⇒ 必须过门：逐条确认或有 TTL 的令牌，默认 0 张）；六条红线（发布过门/密钥DPAPI/每次留痕 source_kind=publish/一人一号/收益只汇总不代提/不刷量）；平台名单**主人未给 ⇒ 一个平台名都不编**；type=external" |

模块头部另有 `CAP_TYPE = "external"`（`auto_publish.py:22`）· `TRACE_SOURCE_KIND = "publish"`（23）。
注册表 `requires_params=[]` · `params_hint=""` · `needs_confirmation=false` · `safe=true`
⇒ 空载荷调用**合法**（落到只读 `status`，见 §6.1）。

> ⚠️ **`social` 域不在 `omni.DANGER_DOMAINS`**（那只有 `pipeline`/`dangerous`/`infra`/`integration`），
> 但实测 `auto_run_verdict(auto_publish)` = **`AUTO=False`**，理由是
> **"名字带写动作字样（deploy/release/publish/…）"**（`omni.DANGEROUS_NAME_RE` 命中 `publish`）。
> ⇒ **`omni run` 不代跑它** —— 要跑只能人工给命令。
> ⇒ 这条也顺带说明：**"不在危险域"不等于"会替你自动跑"**，两条判据是分开的。

---

## 1. 什么时候用（意图 → 落点）

| 人想干什么 | 落到哪个 op | 只读还是要过门 | 涉不涉钱 | 可不可逆 |
|---|---|---|---|---|
| 看这扇窗的形状（五原语 / 自动边界 / 现状） | `status`（**空载荷默认就是它**） | 只读，**零作用域** | 否 | — |
| 只看五原语那五条 | `primitives` | 只读，零作用域 | 否 | — |
| 只看"自动 vs 过门"那张表 | `policy` | 只读，零作用域 | 否 | — |
| 看六条红线 | `redlines` | 只读，零作用域 | 否 | — |
| 看平台名单 | `platforms` | 只读，零作用域 | 否 | — |
| 判一段载荷有没有明文平台凭据 | `gate_key` | 只读闸，零作用域 | 否 | — |
| 判"发布/提现/改价"有没有过门 | `gate_publish` | 只读闸，零作用域 | 否 | — |
| 判有没有留痕（`source_kind=publish`） | `gate_trace` | 只读闸，零作用域 | 否 | — |
| 判有没有共用账号（一人一号） | `gate_accounts` | 只读闸，零作用域 | 否 | — |
| 判提现有没有单独授权 | `gate_withdraw` | 只读闸，零作用域 | 否 | — |
| 判计划里有没有刷量/假数据 | `gate_metrics` | 只读闸，零作用域 | 否 | — |
| **把作品排到时间轴上** | `plan` | **零作用域（模块标 auto_ok）** | 否 | ✅ 可逆 |
| **出文案 / 封面 / 话题标签** | `compose` | 零作用域（auto_ok） | 否 | ✅ 可反复改 |
| 🔴 **发出去** | `publish` | **零作用域，但模块标 `NEEDS_GATE`** | 否 | ❌ **不可逆 + 出网** |
| **看已发布的数据** | `track` | 零作用域（auto_ok） | 否 | ✅ 只读 |
| **收益归集** | `settle` | 零作用域（**只汇总，不代提**） | 否 | ✅ |

**不在这 1 个位里的事**：发飞书消息 / 建飞书文档 → `gbt-lark` 簇；发邮件 → `gbt-comms`（`coze_mail`，`send`/`reply`/`register` 挂 `data_export`）；
账号合规底座 → `gbt-data`（`account_registry`）；看屏幕点发布按钮 → `gbt-tentacle`。

---

## 2. 🔴 要过哪道门：**两层门，别只看一层**

```python
from gbt_allinone.security import policy
policy.evaluate("auto_publish", {}).scopes               # → ()
policy.evaluate("auto_publish", {"op": "publish"}).scopes  # → ()   ← 连"发布"也是零！
```

**第一层（policy）实测：整位零作用域。** 本机 2026-09-22 逐条查的全量：

| op | 作用域（实测） | policy 里有没有 `auto_publish` 分支？ |
|---|---|---|
| `status` / `primitives` / `policy` / `redlines` / `platforms` | **零** | **没有**（全文件 grep `auto_publish` 零命中） |
| `gate_key` / `gate_publish` / `gate_trace` / `gate_accounts` / `gate_withdraw` / `gate_metrics` | **零** | 没有 |
| **`plan`** | **零** | 没有 |
| **`compose`** | **零** | 没有 |
| 🔴 **`publish`** | **零** | 没有 |
| **`track`** | **零** | 没有 |
| **`settle`** | **零** | 没有 |

🔴🔴 **零作用域 ≠ 只读** —— 本域就是这句话在**不可逆 + 出网**这一档上的样本：
`publish`（**发出去就收不回来**）在 policy 层**完全免卡**。
**"门没拦"只说明"policy 没把这一格收口"，不说明"这一步没有后果"。**

**第二层（模块自己的六个闸 + `not_implemented` 兜底）** —— **真正的门在这里**：

| 闸 | 判据（模块源码） | 不通过时 `rule` |
|---|---|---|
| `gate_key` | 载荷里有没有 `sk`/`ak`/`eyJ`/`ghp`/`cookie`/`token` 打头的疑似凭据（`_KEYISH`） | `plaintext_key` |
| `gate_publish` | **不可逆 / 涉钱动作必须过门**，三种方式**任选其一**：<br>① 逐条确认 `confirmed=true` ② 有 TTL 的批量令牌（`token` 非空 **且** `ttl_seconds` 是正数）<br>（`AUTO_OK` 的动作**不必**过门；不在两张表里的动作 ⇒ 拒） | `irreversible_needs_gate` / `unknown_action` |
| `gate_trace` | `trace_ref` 非空 **且** `source_kind == "publish"` | `call_not_traced` / `bad_source_kind` |
| `gate_accounts` | 同 `account_id` 被两个 `ai_id` 用 ⇒ 拒（**一人一号**） | `account_shared` |
| `gate_withdraw` | `action == "settle_withdraw"` 且 `authorized` 非真 ⇒ 拒 | `withdraw_needs_auth` |
| `gate_metrics` | 计划文本命中 `刷量/刷单/买粉/假数据/伪造/inflate/buy_followers` ⇒ 拒 | `fake_metrics` |

**第三层（骨架兜底）**：`plan` / `compose` / `publish` / `track` / `settle` 五个 op **一律**走
`_not_implemented(op)` ⇒ `{"ok": false, "denied": true, "rule": "not_implemented", "requires_external_key": true, …}`
（**源码所见，本规程未跑**，见 §8）。

> 🔴 **自动 vs 过门的**唯一权威表（模块自报，实测逐字）：
> - `AUTO_OK = ("plan", "compose", "track", "settle_read")` —— **全自动允许的动作，不必过门**
> - `NEEDS_GATE = ("publish", "settle_withdraw", "price_change")` —— **不可逆 / 涉钱，必须过门**
> - 一句话口径：**"全自动 = 除「发布 / 提现 / 改价」之外全自动"**
> - 现状：**`current.tokens_issued: 0`** —— "主人还没发过任何发布令牌 ⇒ 默认 **0 张** ⇒ 发布一律走逐条确认"
>
> ⚠️ 注意两张表**不是一个维度**：`AUTO_OK` 里写的是 `settle_read`，而 **`status` 里带的那条
> `gate_publish_default` 判的是 `publish`**；`NEEDS_GATE` 里写的是 `settle_withdraw` / `price_change`。
> ⇒ **"收益归集"整体是 auto_ok 侧的读数，只有"提现"那一下过门** —— 别把 `settle` 一律当涉钱。

**授权只能主人在终端发**（本机 `auth status` 实测 15 个作用域 `grants_available` 全 0、`ai_can_grant:false`）。
本域**现在一门都不需要**（零作用域），**发布那一道门是本域的令牌/TTL 门，不是 auth_gate 的作用域门**。
🔴 **AI 永远无权给自己发授权** —— 缺授权就如实报缺，**不找旁路、不改 `security/policy.py`**。

---

## 3. 怎么调（真命令）

```powershell
# ── 只读这一档（零作用域；本规程真跑过，见 §6）──
py -3.14 tools/codex-scripts/five-dim.py cap auto_publish
py -3.14 tools/codex-scripts/five-dim.py cap auto_publish '{"op":"primitives"}'
py -3.14 tools/codex-scripts/five-dim.py cap auto_publish '{"op":"policy"}'
py -3.14 tools/codex-scripts/five-dim.py cap auto_publish '{"op":"redlines"}'
py -3.14 tools/codex-scripts/five-dim.py cap auto_publish '{"op":"platforms"}'
py -3.14 tools/codex-scripts/five-dim.py cap auto_publish '{"op":"gate_key","payload":"sk-FAKEFAKEFAKEFAKE"}'
py -3.14 tools/codex-scripts/five-dim.py cap auto_publish '{"op":"gate_publish","action":"publish"}'
py -3.14 tools/codex-scripts/five-dim.py cap auto_publish '{"op":"gate_publish","action":"plan"}'
py -3.14 tools/codex-scripts/five-dim.py cap auto_publish '{"op":"gate_trace","trace_ref":"p1","source_kind":"publish"}'
py -3.14 tools/codex-scripts/five-dim.py cap auto_publish '{"op":"gate_withdraw","action":"settle_withdraw"}'
py -3.14 tools/codex-scripts/five-dim.py cap auto_publish '{"op":"gate_metrics","plan":"刷量买粉"}'
py -3.14 tools/codex-scripts/five-dim.py cap auto_publish '{"op":"gate_accounts","accounts":[{"account_id":"a1","ai_id":"x"},{"account_id":"a1","ai_id":"y"}]}'

# ── 发布 / 提现 / 改价那一档（零作用域但本规程不跑，见 §8）──
py -3.14 tools/codex-scripts/five-dim.py cap auto_publish '{"op":"publish"}'
py -3.14 tools/codex-scripts/five-dim.py cap auto_publish '{"op":"plan"}'
py -3.14 tools/codex-scripts/five-dim.py cap auto_publish '{"op":"compose"}'
py -3.14 tools/codex-scripts/five-dim.py cap auto_publish '{"op":"track"}'
py -3.14 tools/codex-scripts/five-dim.py cap auto_publish '{"op":"settle"}'
```

🔴 **PowerShell 里传 JSON 载荷：用单引号原样包住 JSON**（`'{"op":"policy"}'`）。
写成 `'{\"op\":\"policy\"}'` 会让 `five-dim.py:139` 的 `json.loads` 直接抛
`JSONDecodeError: Expecting property name enclosed in double quotes`（同族坑见 `gbt-llm` 的 §2）。

---

## 4. 有哪些 op（源码逐个点名，不猜）

`gbt_allinone/tools/auto_publish.py:182` `run(op="status", **params)`，**16 个 op**：

| op | 去处（源码行） | 性质 |
|---|---|---|
| `status` | 汇编 `PRIMITIVES`/`AUTO_OK`/`NEEDS_GATE`/`RED_LINES`/`PLATFORMS`/`CURRENT` + 两道默认闸（187） | 只读 |
| `primitives` | `PRIMITIVES`（26） | 只读 |
| `policy` | `AUTO_OK` / `NEEDS_GATE` / `one_line`（200） | 只读 |
| `redlines` | `RED_LINES`（43） | 只读 |
| `platforms` | `PLATFORMS` + `PLATFORMS_NOTE`（206） | 只读 |
| `gate_key` | `check_no_plaintext_key(payload)`（69） | 只读闸 |
| `gate_publish` | `check_publish_gated(action, token, ttl_seconds, confirmed)`（79） | 只读闸 |
| `gate_trace` | `must_trace(trace_ref, source_kind)`（113） | 只读闸 |
| `gate_accounts` | `check_one_account_one_ai(accounts)`（127） | 只读闸 |
| `gate_withdraw` | `check_no_withdraw_without_auth(action, authorized)`（148） | 只读闸 |
| `gate_metrics` | `check_no_fake_metrics(plan)`（163） | 只读闸 |
| `plan` | `_not_implemented("plan")`（174/224） | 排期（auto_ok） |
| `compose` | `_not_implemented("compose")` | 成稿（auto_ok） |
| 🔴 `publish` | `_not_implemented("publish")` | **不可逆 + 出网（NEEDS_GATE）** |
| `track` | `_not_implemented("track")` | 追踪（auto_ok） |
| `settle` | `_not_implemented("settle")` | 收益归集（只汇总不代提） |

**未知 op**：`raise ValueError("未知 op %r（可用：status/primitives/policy/redlines/platforms/gate_key/gate_publish/gate_trace/gate_accounts/gate_withdraw/gate_metrics/plan/compose/publish/track/settle）")`。

### 五原语（模块自报的"钱与可逆"表，实测逐字）

| key | cn | reversible | costs_money | needs_gate | note（原文） |
|---|---|---|---|---|---|
| `PLAN` | 排期 | true | false | false | 把作品排到时间轴上（纯本地） |
| `COMPOSE` | 成稿 | true | false | false | 文案 / 封面 / 话题标签（纯本地，可反复改） |
| `PUBLISH` | 发布 | **false** | false | **true** | **不可逆 + 出网** —— 发出去就收不回来 |
| `TRACK` | 追踪 | true | false | false | 看已发布的数据（只读） |
| `SETTLE` | 收益归集 | true | false | false | **只汇总，不代提**；提现是钱的动作，单独授权 |

### 六条红线（实测逐字）

1. 发布必须过门：不可逆 + 出网 ⇒ 要么主人发一张**有 TTL 的批量令牌**，要么逐条确认（默认 **0 张令牌**）
2. 密钥只存 DPAPI：平台凭据走密钥池，不许明文落盘、不许进返回值
3. 每次发布留痕：写 trace_store，source_kind=publish
4. 一人一号：接合规底座 account_registry —— 不许共用账号、不许抢别人的号
5. 收益只汇总不代提：提现 / 改价是**钱**的动作，单独授权
6. 不刷量、不做假数据、不绕验证：**数据可以难看，但不能是假的**

---

## 5. 落点 / 外部面（动手会碰到什么）

模块 docstring 的现状口径 + 实测字段逐条对上：

| 维度 | 现状（实测字段） |
|---|---|
| **落点** | **无**。本模块**不写盘、不出网、不发** |
| **平台名单** | `platforms: []`（**空**）· `platforms_note: "主人说「各种社交 / 发布作品 / 收益平台」，但**没列名单** ⇒ 本骨架**一个平台名都不编**（未取证不引外部）；待主人给名单后逐个落『官方入口 / 授权方式 / 收益口径』三格"` |
| **凭据** | `current.credentials_present: false` · `requires_external_key: true` |
| **令牌** | `current.tokens_issued: 0` · `tokens_note: "主人还没发过任何发布令牌 ⇒ 默认 0 张 ⇒ 发布一律走逐条确认"` |
| **平台在册数** | `current.platforms_present: 0` |
| **留痕口径** | `TRACE_SOURCE_KIND = "publish"`；`status` 带的 `gate_trace` 实测 `{"ok":true,"readonly":true,"trace_ref":"publish","source_kind":"publish"}` |
| **将来真接时走哪** | `next: "主人给平台名单 + 凭据（走密钥池）+ 授权出网后，逐个接官方入口"` |
| **一句话口径** | `one_line: "**全自动 = 除「发布 / 提现 / 改价」之外全自动**"` |

---

## 6. 实测读数（**只读真跑，抄真实字段**；机器 = 本机 2026-09-22）

### 6.1 空载荷 `cap auto_publish`

```json
{"gate":"run_task","kind":"auto_publish","status":"ok","stamp":true,"denied":false,
 "result":{"ok":true,"readonly":true,"kind":"auto_publish","domain":"social","type":"external",
   "primitives":[ …5 条，见 §4 表… ],
   "auto_ok":["plan","compose","track","settle_read"],
   "needs_gate":["publish","settle_withdraw","price_change"],
   "red_lines":[ …6 条，见 §4 表… ],
   "platforms":[],
   "platforms_note":"主人说「各种社交 / 发布作品 / 收益平台」，但**没列名单** ⇒ 本骨架**一个平台名都不编**（未取证不引外部）；待主人给名单后逐个落『官方入口 / 授权方式 / 收益口径』三格",
   "current":{"tokens_issued":0,
     "tokens_note":"主人还没发过任何发布令牌 ⇒ 默认 0 张 ⇒ 发布一律走逐条确认",
     "platforms_present":0,"credentials_present":false},
   "requires_external_key":true,
   "gate_publish_default":{"ok":false,"denied":true,"rule":"irreversible_needs_gate",
     "action":"publish","token_given":false,"ttl_ok":false,"confirmed":false,
     "why":"**不可逆 / 涉钱动作必须过门**：要么逐条确认，要么一张有 TTL 的令牌 —— 把「全自动」理解成「连发布也不问」，就是把不可逆当可逆"},
   "gate_trace":{"ok":true,"readonly":true,"trace_ref":"publish","source_kind":"publish"}}}
```

exit **0**。🔴 **注意最后两条是"一放一拒"**：
`gate_trace` **放行**（`trace_ref` 传的是 `TRACE_SOURCE_KIND`），
`gate_publish_default` **拒绝**（默认 0 张令牌、没逐条确认）。
⇒ **同一个 `status` 里既有一个 ok 又有一个 denied** —— **别整发看一个 `ok` 就下结论**。

### 6.2 `policy` / `platforms`（只读）

| 命令 | 本体关键字段（实测） | exit |
|---|---|---|
| `{"op":"policy"}` | `ok:true` · `readonly:true` · `auto_ok:["plan","compose","track","settle_read"]` · `needs_gate:["publish","settle_withdraw","price_change"]` · `one_line:"**全自动 = 除「发布 / 提现 / 改价」之外全自动**"` | 0 |
| `{"op":"platforms"}` | `ok:true` · **`platforms:[]`** · `note` 同 §6.1 的 `platforms_note` | 0 |

### 6.3 六个闸（逐个真跑）

| 命令 | 本体关键字段（实测） | exit |
|---|---|---|
| `{"op":"gate_publish","action":"publish"}` | `ok:false` · `denied:true` · `rule:"irreversible_needs_gate"` · `action:"publish"` · `token_given:false` · `ttl_ok:false` · `confirmed:false` · `why:"**不可逆 / 涉钱动作必须过门**…"` | 0 |
| `{"op":"gate_publish","action":"plan"}` | **`ok:true`** · `readonly:true` · `action:"plan"` · **`gated:false`** · `note:"全自动允许的动作 ⇒ 不必过门（不扩大化）"` | 0 |
| `{"op":"gate_trace","trace_ref":"p1","source_kind":"publish"}` | `ok:true` · `readonly:true` · `trace_ref:"p1"` · `source_kind:"publish"`（**放行**） | 0 |
| `{"op":"gate_withdraw","action":"settle_withdraw"}` | `ok:false` · `denied:true` · `rule:"withdraw_needs_auth"` · `why:"**提现是钱的动作** ⇒ 必须主人单独授权；本模块默认只汇总、不代提"` | 0 |
| `{"op":"gate_metrics","plan":"刷量买粉"}` | `ok:false` · `denied:true` · `rule:"fake_metrics"` · **`hit:"刷量"`** · `why:"**数据可以难看，但不能是假的** —— 假数据会把后面的判断全带偏"` | 0 |
| `{"op":"gate_accounts","accounts":[{"account_id":"a1","ai_id":"x"},{"account_id":"a1","ai_id":"y"}]}` | `ok:false` · `denied:true` · `rule:"account_shared"` · **`bad:["a1 被两个 AI 共用（x / y）"]`** · `why:"**一人一号**：账号不共享（共享 = 封号风险 + 责任分不清）"` | 0 |
| `{"op":"gate_key","payload":"sk-FAKEFAKEFAKEFAKE"}` | `ok:false` · `denied:true` · `rule:"plaintext_key"` · **`masked:"sk-F****"`** · `why:"平台凭据只走密钥池（DPAPI）；明文进返回值就等于落了两处"` | 0 |

🔴 **上表七条里六条是"拒"，退出码全是 0。**
⇒ **本域的"拒"（`denied:true`）根本不反映在退出码上**：那是**闸的结论**，
不是 `run_task` 层的 `denied`（那一层才会 exit 1）。
**只看退出码会把六条拒绝全部读成成功。**

### 6.4 五个动作 op（**源码所见，未跑**）

`plan` / `compose` / `publish` / `track` / `settle` 一律走 `_not_implemented(op)`：

```python
{"ok": False, "denied": True, "rule": "not_implemented", "op": op,
 "requires_external_key": True,
 "reason": "平台名单主人未给、凭据也不在盘上 ⇒ 本骨架只给形状与闸，**不假装能发**",
 "next": "主人给平台名单 + 凭据（走密钥池）+ 授权出网后，逐个接官方入口"}
```

🔴 **`denied:true` 在这里的含义是"未实现"，不是"你没授权"**（`rule` 是 `not_implemented`）。
⇒ **两句话长得很像，别混**（同族坑见 `gbt-integration` §6.5）。

---

## 7. 失败典型样子（照着认，别认错）

| 症状 | 真因 | 正确读法 |
|---|---|---|
| `rule:"irreversible_needs_gate"` + `token_given:false` `confirmed:false` | **发布/提现/改价没过门** | **这是设计**，不是 bug：要么逐条确认，要么一张有 TTL 的令牌 |
| `rule:"not_implemented"` + `requires_external_key:true` | 骨架期没接线（平台名单未给、无凭据） | **不是"没授权"**；是"不假装能发"（§6.4） |
| `rule:"unknown_action"` | 动作不在 `AUTO_OK`/`NEEDS_GATE` 任一张表里 | 源码原话："**不许猜**"（先补表） |
| `rule:"fake_metrics"` + `hit` | 计划里出现刷量类字样 | **数据可以难看，但不能是假的** |
| `rule:"account_shared"` + `bad` | 同账号被两个 AI 共用 | 一人一号（接 `account_registry`） |
| `rule:"withdraw_needs_auth"` | 提现没有单独授权 | 默认**只汇总、不代提** |
| `rule:"plaintext_key"` + `masked` | 载荷带了明文平台凭据 | 凭据只走密钥池（DPAPI） |
| 期望"平台名单在这" | `platforms: []` | **主人未给 ⇒ 一个平台名都不编**；别自己补 |
| 期望"全自动就是不用问" | `one_line` 与 `NEEDS_GATE` | **"全自动 = 除「发布/提现/改价」之外全自动"** |
| `JSONDecodeError: Expecting property name enclosed in double quotes` | PowerShell 转义了 JSON | 用单引号原样包（§3） |

---

## 8. 🔴 未验清单（**为什么不做**，逐条）

| 动作 | 状态 | 为什么不做 |
|---|---|---|
| 🔴 `{"op":"publish"}` | **未验** | **对外发布 + 不可逆**。任务明令 `auto_publish`（对外发布）不跑；虽然源码显示它会先走 `_not_implemented`，但**纪律上不碰** |
| `{"op":"plan"}` / `{"op":"compose"}` | **未验** | 同一族的动作 op（明令不跑）；虽然 `AUTO_OK` 说它们"全自动允许"，但**现行实现是 `not_implemented`** |
| `{"op":"track"}` / `{"op":"settle"}` | **未验** | 同上；`settle` 涉收益（**只汇总不代提**） |
| `gate_publish` 的**放行**分支（`confirmed:true` / `token` + 正 `ttl_seconds`） | **未验** | 只跑了默认拒绝那一发与 `plan` 豁免那一发；**"过门后放行"没跑** |
| `gate_publish` 的 `unknown_action` 分支 | **未验** | 只读了源码（93-95），**没跑** |
| `gate_accounts` 的 `accounts=None`（不适用）分支 | **未验** | 只读了源码（129-130），**没跑** |
| `gate_key` / `gate_metrics` / `gate_withdraw` 的**无命中**分支 | **未验** | 只跑了命中那一发 |
| 真去连任何平台 / 出网 | **未验** | 平台名单未给、凭据不在盘上；且属"出网 + 发布" |

> **"未验"不是"不能用"**：上表每一条都**存在**、都**有源码落点**；缺的是**当次运行证据**。
> 本规程**不拿"我以为能"当"验过"**。

---

## 9. 与相邻域的边界（一句话切干净）

| 相邻 | 谁是谁 | 边界 |
|---|---|---|
| `gbt-lark`（簇） | 28 条 `lark-*` 飞书技能 | **飞书是"发到飞书"，本域是"发到社交/作品/收益平台"**。两家都"对外"，但**平台名单、凭据口径、红线全不同** ⇒ 谁也别替谁 |
| `gbt-comms`（`coze_mail`） | 发信 / 收信 | `coze_mail` 的 `send` / `reply` / `register` 在 `policy.py` 里**明挂 `data_export`**（收紧）；本域 **policy 层零作用域**，门在模块的 `gate_publish`。⇒ **拿本域的"零作用域"去推 `coze_mail` 也免卡是错的，反之亦然** |
| `gbt-data`（`account_registry`） | 账号合规底座 | 本域第六条红线就是"接 `account_registry`"；`gate_accounts` 是**本域自己**的那道机械闸，**不替 `account_registry` 干活** |
| `gbt-infra`（`cloud_pc`） | 云电脑 | **都是 `type=external` + policy 零作用域 + 模块自带闸**，但 `cloud_pc` 的轴是**钱 / 不可逆**，本域的轴是**不可逆 + 出网 + 一人一号 + 不刷量**。⇒ **同族不同轴，别互推** |
| `gbt-tentacle`（`tentacle` 域） | 手眼网耳 | 真要"点发布按钮"是触手的活；本域只管"发布这个动作的边界与闸" |

---

## 10. 🔴 报告层红线（先问"这是事实，还是我读错了地方"）

1. **零作用域 ≠ 只读**（**本域核心红线之一**）。`publish`（不可逆 + 出网）在 policy 层**零作用域**。
   ⇒ **作用域只回答"policy 这一层有没有收口"，不回答"这一步有没有后果"。**
2. **零作用域 ≠ 没门**（**另一条**）。本域的门在**模块自己**：`NEEDS_GATE` 表 + 六个 `gate_*` + `_not_implemented` 兜底。
   ⇒ **别把"policy 没有分支"读成"这事没人管"。**
3. **"能调" ≠ "能用"**。零作用域意味着**调得到**；但五个动作 op **一律 `not_implemented`**
   ⇒ **一个都发不出去**。本域把这两件事同时摆在台面上。
4. **`status:"ok"` ≠ 本体 `ok:true`**。本域这一版实测**外层与本体没打架**（只读那条外层 ok + 本体 `ok:true`），
   但**七条闸全部是"外层 ok + 内层 `ok:false`"**（§6.3）⇒ **外层根本看不出拒绝**。
   更麻烦的是 §6.1：**同一个 `status` 里 `gate_trace` 放行、`gate_publish_default` 拒绝**
   ⇒ **整发看一个 `ok` 就下结论必然出错。**
5. **退出码不可信**。本域实测：只读成功 exit **0**；**七条闸拒绝也 exit 0**；
   只有 `run_task` 层的 `denied` 才 exit **1**（本域零作用域，所以**够不到那一层**）。
   ⇒ **本域全部拒绝都藏在"exit 0"后面。**
   `stamp: true/false` 是**回归印章的有无**，不是成功与否。
6. **"全自动"这句话必须按 `one_line` 念**：**除「发布 / 提现 / 改价」之外全自动**。
   把它读成"连发布也不问"，就是源码原话点名的那个**最贵的错**。
7. **不许替主人编平台名**。`platforms: []` 是**读数**，`platforms_note` 明说"一个平台名都不编"。
   ⇒ **任何形式的"常见平台有抖音/小红书/…"都属于编造**（未取证不引外部）。
8. **"图鉴是索引，实测才是读数"**：注册表 desc 说"只读骨架·门"，实测确实如此；
   但 desc **没有**告诉你"PUBLISH 在 policy 层零作用域" —— 那要**现查**。

---

## 11. 不许做什么（红线）

1. **不许给自己发授权**：不跑 `auth grant`、不手写 `store/auth_grants.jsonl`、不改 `security/policy.py` / `auth_gate`。
2. **不许自发令牌**：`tokens_issued: 0` 是**读数**；**令牌只能主人发**，AI 不许给生成/放宽 TTL。
3. **不许绕门**：不许为了"绕过发布门"直接调 `gbt_allinone.tools.auto_publish` 里的函数替掉
   `run_task` 唯一门（AGENTS.md 明令：那是**未经授权的写入**，纪律上就是违规）。
4. **不许发布**：这是本域的第一条红线，**不因为"只是试一下"而例外**。
5. **不许提现 / 改价**（钱的动作，单独授权；本模块默认**只汇总不代提**）。
6. **不许刷量、不许做假数据、不许绕验证**（"数据可以难看，但不能是假的"）。
7. **不许共用账号**（一人一号）。
8. **不许把明文平台凭据写进 payload / 文档 / 示例**（本规程示例全用 `sk-FAKEFAKEFAKEFAKE` 这种假串）。
9. **不许替主人编平台名单**（§10.7）。
10. **不许改 `tools/codex-scripts/omni.py`**（本域登记行由交付报告给出，不擅自动手）；
    **不许动别的域**、不许改 `policy.py`。

---

## 12. 固化与出处（**重启后要在**）

| 什么 | 在哪 |
|---|---|
| 本规程（源） | `<仓>/skills/gbt-social/SKILL.md` |
| 本规程（装机·托管目录） | `C:\Users\ADMIN\.openclaw-autoclaw\skills\gbt-social\SKILL.md` |
| ⛔ **不许装到** | `~/.agents/skills/`（本仓 AGENTS.md 明令禁止） |
| 能力位名单（1 个：`auto_publish`） | `<仓>/state/skill_atlas.json`（`domain == "social"`）· 现扫可重建：`python tools/codex-scripts/omni.py build` |
| 授权判据（**单一真相**） | `<仓>/gbt_allinone/security/policy.py` 的 `evaluate()` —— ⚠️ **本域在里面没有任何分支**（这就是"零作用域"的来源） |
| 自动执行判据 | `<仓>/tools/codex-scripts/omni.py` 的 `auto_run_verdict()` 与 `DANGEROUS_NAME_RE`（名字带 `publish` ⇒ `AUTO=False`） |
| op 分发 | `<仓>/gbt_allinone/api.py:484-488`（`kind == "auto_publish"` 那一支） |
| 实现（五原语/六红线/六闸） | `<仓>/gbt_allinone/tools/auto_publish.py`（`run()` 182；五原语 26；`AUTO_OK`/`NEEDS_GATE` 40-41；六红线 43；六个闸 69/79/113/127/148/163） |
| 门与拒绝信封 | `<仓>/gbt_allinone/run_task`（唯一门）· `tools/codex-scripts/five-dim.py:131-172`（扁平信封的读法） |

**深蒸登记（应加、本次未擅自动手 —— 登记由主人统一做）**：`omni.py` 的 `DISTILLED_DOMAINS` 加一行

```python
    "social": "gbt-social",
```

加完后 `python tools/codex-scripts/omni.py gaps` 里 `social 1 个能力位` 会从
`⏳ 在队里` 变成 `✅ 已深蒸 → gbt-social`。

**验收（做完怎么证明真的做了）**：

```powershell
py -3.14 tools/codex-scripts/verify-distill.py --domain social --skill gbt-social
```

1. 上面这条必须 **PASS**（覆盖 1/1）；
2. 两份产物**逐字节相同**（sha256 一致）；
3. 再静态查一次 `policy.evaluate("auto_publish", {"op":"publish"}).scopes` —— 必须**仍是空**
   （哪天空了变非空，回来改本文件 §2）；
4. 声明"某 op 能用"之前，先问自己：**这条是实测读数，还是我读错了地方？** 拿不准就写"未验"。
