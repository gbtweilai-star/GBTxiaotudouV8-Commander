---
name: gbt-infra
displayName: GBT · infra 职业域用法规程（1 个能力位：cloud_pc）
version: 1.0.0
description: GBT小土豆V8 的 `infra` 职业域（云电脑独立窗口 / 面板卡⑦ / 五原语 PROVISION·CONNECT·STATUS·SNAPSHOT·RELEASE）用法规程。这个域**只有 1 个能力位**：`cloud_pc`。本文件把它写全：用途、五原语逐个标「花不花钱 / 可不可逆 / 要不要过门」、逐 op 静态查出来的作用域（**整位零作用域，连 PROVISION/RELEASE 也是零** —— 这就是"零作用域 ≠ 只读"和"零作用域 ≠ 没门"的活样本）、真命令、13 个 op 逐个点名、五个闸（密钥/先算账/留痕/官方入口/身份内核）、落点与外部面（无落点、无出网、无凭据）、失败典型样子、与 `gbt-pipeline`（deploy_publish 那条钱/生产写入通道）的边界；并记下实测读数（gate_budget 缺预算账单即拒；gate_official 自己拼请求即拒；gate_identity 云上改写身份即拒；gate_key 明文凭据即拒）。当用户要开通/连上/快照/释放云电脑、要算云上预算、要问云电脑能不能用，或 cloud_pc 报 not_implemented / budget_bill_missing / self_built_request / plaintext_key 时使用。
triggers:
  - "云电脑"
  - "云主机"
  - "云服务器"
  - "开通"
  - "释放"
  - "快照"
  - "账单"
  - "预算"
  - "面板卡⑦"
  - "cloud_pc"
  - "infra"
  - "not_implemented"
  - "budget_bill_missing"
---

# GBT · infra 职业域用法规程（1 个能力位：`cloud_pc`）

> 开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属
>
> **这份规程解决什么**：`infra` 是一个**一位一域**的小域，但它踩的是**全仓最贵的一格**：
> "开通云主机"这个动作**花钱 + 不可逆**。它有两层最容易读反的东西：
> ① **policy 层完全零作用域**（连 `PROVISION` / `RELEASE` 都是零）—— 因为 `policy.py` 里
> **一条 `cloud_pc` 分支都没有**；门**不在 policy，在模块自己的 `gate_budget`**。
> ② **现状是"只给形状、不给开通"**：四个动作一律 `not_implemented + requires_external_key`。
> ⇒ **"零作用域 ≠ 只读"**（PROVISION 会花钱）与 **"能调 ≠ 能用"**（能调但一律未实现）**在同一格上同时成立**。
> 本文件把「哪个 op、要不要授权、门在哪一层、失败长什么样、读数该看哪个字段」逐个钉死，
> 并把**本机实测过的坑**如实记下来 —— **没验过的一律写"未验"，不冒充验过**。

**唯一现读入口（别信任何二手描述，包括本文件）**：

```powershell
py -3.14 tools/codex-scripts/five-dim.py cap cloud_pc ['<JSON载荷>'] [--full]
```

`cap` 一律走 `gbt_allinone.run_task`（**唯一门**）；被门拒绝就**如实报缺什么作用域**，不绕路。

---

## 0. 一位一域（先确认名字，别照抄别人的表）

现扫 `state/skill_atlas.json`（`domain == "infra"`）**只有一条**：

| 域 | 能力位（kind） | handler | type | 注册表 desc 原文 |
|---|---|---|---|---|
| `infra` | **`cloud_pc`** | `cloud_pc` | **`external`** | "云电脑独立窗口（只读骨架·门）：面板加一个**独立窗口**给她（数字人）**安装**云电脑（卡片 + 触手，**不是 iframe**）；五原语 PROVISION/CONNECT/STATUS/SNAPSHOT/RELEASE（逐个标花钱与不可逆）；五条红线（密钥DPAPI/先算账再花钱/每次留痕 source_kind=cloud_pc/不绕官方入口/身份内核不变）；type=external" |

模块头部另有 `CAP_TYPE = "external"`（`cloud_pc.py:21`）· `TRACE_SOURCE_KIND = "cloud_pc"`（22）。
注册表 `requires_params=[]` · `params_hint=""` · `needs_confirmation=false` · `safe=true`
⇒ 空载荷调用**合法**（落到只读 `status`，见 §6.1）。

> ⚠️ **`infra` 整个域在 `omni.DANGER_DOMAINS` 里**（`omni.py:105`：
> `DANGER_DOMAINS = {"pipeline","dangerous","infra","integration"}`）
> ⇒ 实测 `auto_run_verdict(cloud_pc)` = **`AUTO=False`**，理由是"域「infra」属于有后果的域"。
> **`omni run` 不代跑它** —— 要跑只能人工给命令。

---

## 1. 什么时候用（意图 → 落点）

| 人想干什么 | 落到哪个 op | 只读还是要授权 | 花不花钱 | 可不可逆 |
|---|---|---|---|---|
| 看这扇窗的形状（五原语 / 五红线 / 现状） | `status`（**空载荷默认就是它**） | 只读，**零作用域** | 否 | — |
| 只看五原语那五条 | `primitives` | 只读，零作用域 | 否 | — |
| 看独立窗口怎么摆 | `window` | 只读，零作用域 | 否 | — |
| 看五条红线 | `redlines` | 只读，零作用域 | 否 | — |
| 判一段载荷有没有明文云凭据 | `gate_key` | 只读闸，零作用域 | 否 | — |
| 判"花钱/不可逆动作前有没有先算账" | `gate_budget` | 只读闸，零作用域 | 否 | — |
| 判有没有留痕（`source_kind=cloud_pc`） | `gate_trace` | 只读闸，零作用域 | 否 | — |
| 判走的是不是官方 CLI/SDK | `gate_official` | 只读闸，零作用域 | 否 | — |
| 判云上有没有夹带身份改写 | `gate_identity` | 只读闸，零作用域 | 否 | — |
| **把云主机开出来、装底座** | `provision` | **零作用域（但政策上标 needs_gate）** | ✅ **花钱** | ❌ **不可逆** |
| **连上去干活** | `connect` | 零作用域（政策上标 needs_gate:false） | 否 | ✅ 可逆 |
| **留一份可回滚镜像** | `snapshot` | 零作用域（政策上标 needs_gate:false） | ✅ **花钱** | ✅ 可回滚 |
| **退掉** | `release` | **零作用域（但政策上标 needs_gate）** | 否 | ❌ **不可逆** |

**不在这 1 个位里的事**：部署 / 晋升 / 回滚 / 写生产交付区 → `gbt-pipeline`（`deploy_publish` 那条门）；
本机（非云）状态 → `gbt-system`；看屏幕操作云电脑界面 → `gbt-tentacle`。

---

## 2. 🔴 要过哪道门：**两层门，别只看一层**

```python
from gbt_allinone.security import policy
policy.evaluate("cloud_pc", {}).scopes                 # → ()
policy.evaluate("cloud_pc", {"op": "provision"}).scopes  # → ()   ← 连花钱动作也是零！
policy.evaluate("cloud_pc", {"op": "release"}).scopes    # → ()   ← 连不可逆动作也是零！
```

**第一层（policy）实测：整位零作用域。** 本机 2026-09-22 逐条查的全量：

| op | 作用域（实测） | policy 里有没有 `cloud_pc` 分支？ |
|---|---|---|
| `status` / `primitives` / `window` / `redlines` | **零** | **没有**（全文件 grep `cloud_pc` 零命中） |
| `gate_key` / `gate_budget` / `gate_trace` / `gate_official` / `gate_identity` | **零** | 没有 |
| **`provision`** | **零** | 没有 |
| **`connect`** | **零** | 没有 |
| **`snapshot`** | **零** | 没有 |
| **`release`** | **零** | 没有 |

🔴🔴 **零作用域 ≠ 只读** —— 本域就是这句话的**最贵**样本：
`provision`（**花钱 + 不可逆**）与 `release`（**不可逆**）在 policy 层**完全免卡**。
**"门没拦"只说明"policy 没把这一格收口"，不说明"这一步没有后果"。**

**第二层（模块自己的五个闸 + `not_implemented` 兜底）** —— **真正的门在这里**：

| 闸 | 判据（模块源码） | 不通过时 |
|---|---|---|
| `gate_key` | 载荷里有没有 `sk`/`ak`/`eyJ`/`lta`/`LTAI` 打头的疑似凭据（`_KEYISH`） | `plaintext_key` |
| `gate_budget` | **花钱 / 不可逆动作之前**有没有同时给 `budget` 与 `bill` 两个读数 | `budget_bill_missing` |
| `gate_trace` | `trace_ref` 非空 **且** `source_kind == "cloud_pc"` | `call_not_traced` / `bad_source_kind` |
| `gate_official` | `entry` 必须以 `cli:` 或 `sdk:` 打头 | `official_entry_missing` / `self_built_request` |
| `gate_identity` | 载荷里有没有"改写/覆盖/替换/重写/重置/overwrite + 身份/人格/identity/内核" | `identity_write_on_cloud` |

**第三层（骨架兜底）**：`provision` / `connect` / `snapshot` / `release` 四个 op **一律**走
`_not_implemented(op)` ⇒ `{"ok": false, "denied": true, "rule": "not_implemented", "requires_external_key": true, …}`
（**源码所见，本规程未跑**，见 §8）。

> 🔴 **本域的门是"三层套着"，三层口径不完全一样，别拿一层的结论去说另一层**：
> policy 说"零作用域"、五原语表说 `PROVISION.needs_gate = True`（模块自报）、
> handler 说 `not_implemented`。**三个都在，三个都对，回答的是三个不同问题。**
>
> **授权只能主人在终端发**（本机 `auth status` 实测 15 个作用域 `grants_available` 全 0、`ai_can_grant:false`）。
> 本域**现在一门都不需要**（零作用域），所以**别去申请**；等真接线了再按那时的表走。
> 🔴 **AI 永远无权给自己发授权** —— 缺授权就如实报缺，**不找旁路、不改 `security/policy.py`**。

---

## 3. 怎么调（真命令）

```powershell
# ── 只读这一档（零作用域；本规程真跑过，见 §6）──
py -3.14 tools/codex-scripts/five-dim.py cap cloud_pc
py -3.14 tools/codex-scripts/five-dim.py cap cloud_pc '{"op":"primitives"}'
py -3.14 tools/codex-scripts/five-dim.py cap cloud_pc '{"op":"window"}'
py -3.14 tools/codex-scripts/five-dim.py cap cloud_pc '{"op":"redlines"}'
py -3.14 tools/codex-scripts/five-dim.py cap cloud_pc '{"op":"gate_trace","trace_ref":"t1","source_kind":"cloud_pc"}'
py -3.14 tools/codex-scripts/five-dim.py cap cloud_pc '{"op":"gate_budget","action":"provision"}'
py -3.14 tools/codex-scripts/five-dim.py cap cloud_pc '{"op":"gate_budget","action":"release"}'
py -3.14 tools/codex-scripts/five-dim.py cap cloud_pc '{"op":"gate_official","entry":"curl:https://api"}'
py -3.14 tools/codex-scripts/five-dim.py cap cloud_pc '{"op":"gate_identity","payload":"改写云上身份内核"}'
py -3.14 tools/codex-scripts/five-dim.py cap cloud_pc '{"op":"gate_key","payload":"sk-FAKEFAKEFAKEFAKE"}'

# ── 花钱 / 不可逆那一档（零作用域但本规程不跑，见 §8）──
py -3.14 tools/codex-scripts/five-dim.py cap cloud_pc '{"op":"provision"}'
py -3.14 tools/codex-scripts/five-dim.py cap cloud_pc '{"op":"connect"}'
py -3.14 tools/codex-scripts/five-dim.py cap cloud_pc '{"op":"snapshot"}'
py -3.14 tools/codex-scripts/five-dim.py cap cloud_pc '{"op":"release"}'
```

🔴 **PowerShell 里传 JSON 载荷：用单引号原样包住 JSON**（`'{"op":"primitives"}'`）。
写成 `'{\"op\":\"primitives\"}'` 会让 `five-dim.py:139` 的 `json.loads` 直接抛
`JSONDecodeError: Expecting property name enclosed in double quotes`（同族坑见 `gbt-llm` 的 §2）。

---

## 4. 有哪些 op（源码逐个点名，不猜）

`gbt_allinone/tools/cloud_pc.py:159` `run(op="status", **params)`，**13 个 op**：

| op | 去处（源码行） | 性质 |
|---|---|---|
| `status` | 汇编 `PRIMITIVES`/`WINDOW`/`RED_LINES`/`CURRENT` + `gate_trace`（163） | 只读 |
| `primitives` | `PRIMITIVES`（25） | 只读 |
| `window` | `WINDOW`（43） | 只读 |
| `redlines` | `RED_LINES`（55） | 只读 |
| `gate_key` | `check_no_plaintext_key(payload)`（76） | 只读闸 |
| `gate_budget` | `check_budget_first(budget, bill, action)`（86） | 只读闸 |
| `gate_trace` | `must_trace(trace_ref, source_kind)`（111） | 只读闸 |
| `gate_official` | `check_via_official(entry)`（126） | 只读闸 |
| `gate_identity` | `check_identity_not_on_cloud(payload)`（141） | 只读闸 |
| `provision` | `_not_implemented("provision")`（152/190） | 🔴 **花钱 + 不可逆** |
| `connect` | `_not_implemented("connect")` | 可逆 |
| `snapshot` | `_not_implemented("snapshot")` | 花钱、可回滚 |
| `release` | `_not_implemented("release")` | 🔴 **不可逆** |

**未知 op**：`raise ValueError("未知 op %r（可用：status/primitives/window/redlines/gate_key/gate_budget/gate_trace/gate_official/gate_identity/provision/connect/snapshot/release）")`。

### 五原语（模块自报的"钱与可逆"表，实测逐字）

| key | cn | reversible | costs_money | needs_gate | note（原文） |
|---|---|---|---|---|---|
| `PROVISION` | 开通安装 | **false** | **true** | **true** | 把云主机开出来、把底座装上去 —— **花钱 + 不可逆** |
| `CONNECT` | 连上 | true | false | false | 连上去干活；只读操作不写库 |
| `STATUS` | 读数 | true | false | false | 配置 / 用量 / 账单读数（只读） |
| `SNAPSHOT` | 快照 | true | **true** | false | 留一份可回滚的镜像 —— 花钱但**可回滚**，所以不必卡门，但仍要留痕 |
| `RELEASE` | 释放 | **false** | false | **true** | 退掉 —— **不可逆**，且**必须先给账单读数** |

> ⚠️ 注意 **`SNAPSHOT` 与 `RELEASE` 的 `costs_money` 口径不同**：
> `SNAPSHOT` 标"花钱但可回滚"（`needs_gate:false`），`RELEASE` 标"不花钱但不可逆"（`needs_gate:true`）。
> ⇒ **钱与不可逆是两根轴，别用一根轴去推另一根。**

### 五条红线（实测逐字）

1. 密钥只存 DPAPI：云端凭据走密钥池，不许明文落盘、不许进返回值
2. 先算账再花钱：开通 / 释放前必须先给**资源与预算读数**，不许先花钱后算账
3. 每次操作留痕：写 trace_store，source_kind=cloud_pc
4. 不绕官方入口：走云厂商官方 CLI / SDK，不许自己拼请求
5. 身份内核不变：**她住在云上、身份源仍在本地** —— 云端不许改写身份内核

---

## 5. 落点 / 外部面（动手会碰到什么）

模块 docstring 原话：**"本模块只读：`provision / connect / snapshot / release` 一律 `not_implemented`
（本地没有云厂商凭据 ⇒ 与「自给自足大脑」的降级策略一致：返回 needs_external_key，**不影响其他任务**）"**。
逐条对上（实测）：

| 维度 | 现状（实测字段） |
|---|---|
| **落点** | **无**。本模块**不写盘、不出网、不起进程** |
| **云凭据** | `current.credentials_present: false` · `key_present: false` · `requires_external_key: true` |
| **凭据说明** | `credential_note: "盘上无云厂商凭据（本地不存明文，也未见密钥池里有云主机条目）"` |
| **云厂商 / 规格** | `provider: null` · `provider_note: "云厂商 / 规格 / 计费口径 **主人未给** ⇒ 本骨架**不编**（未取证不引外部）"` |
| **本机 vs 云** | `local_pc_state: "本机可用，但**云电脑 ≠ 本机**：两处读数不许互相顶"` |
| **窗口形态** | `WINDOW.form: "面板卡⑦ · 独立窗口（与其他卡同级）"` · `not_iframe: "**不是 iframe 嵌网页**（跨域 + 登录态会撞）—— 是「卡片 + 触手」"` · `for_whom: "给她（数字人）装一台云电脑"` · `source_of_truth: "local"` |
| **窗口三格** | `card_shows`：云主机状态（有没有/配置/用量/账单）· 装到哪一步（**只呈现读数，不代跑**）· 可回滚点（最近一次快照） |
| **按钮怎么走** | `buttons_go_through: "run_task(\"cloud_pc\", {...}) → 过 auth_gate → 触手"` |
| **将来真接时走哪** | `next: "主人给凭据（走密钥池）+ 授权出网后，接官方 CLI / SDK"`；`gate_official` 只认 `cli:` / `sdk:` 打头的入口 |

---

## 6. 实测读数（**只读真跑，抄真实字段**；机器 = 本机 2026-09-22）

### 6.1 空载荷 `cap cloud_pc`

```json
{"gate":"run_task","kind":"cloud_pc","status":"ok","stamp":true,"denied":false,
 "result":{"ok":true,"readonly":true,"kind":"cloud_pc","domain":"infra","type":"external",
   "primitives":[ …5 条，见 §4 表… ],
   "window":{ …见 §5 表… },
   "red_lines":[ …5 条，见 §4 表… ],
   "current":{"credentials_present":false,
     "credential_note":"盘上无云厂商凭据（本地不存明文，也未见密钥池里有云主机条目）",
     "provider":null,
     "provider_note":"云厂商 / 规格 / 计费口径 **主人未给** ⇒ 本骨架**不编**（未取证不引外部）",
     "local_pc_state":"本机可用，但**云电脑 ≠ 本机**：两处读数不许互相顶"},
   "requires_external_key":true,"key_present":false,
   "gate_trace":{"ok":true,"readonly":true,"trace_ref":"cloud_pc","source_kind":"cloud_pc"}}}
```

exit **0**。

### 6.2 三个只读 op 与四个闸（逐个真跑）

| 命令 | 本体关键字段（实测） | exit |
|---|---|---|
| `{"op":"primitives"}` | `ok:true` · `readonly:true` · `primitives` 5 条 | 0 |
| `{"op":"window"}` | `ok:true` · `readonly:true` · `window`（`form`/`not_iframe`/`for_whom`/`source_of_truth`/`card_shows`/`buttons_go_through`） | 0 |
| `{"op":"redlines"}` | `ok:true` · `readonly:true` · `red_lines` 5 条 | 0 |
| `{"op":"gate_trace","trace_ref":"t1","source_kind":"cloud_pc"}` | `ok:true` · `readonly:true` · `trace_ref:"t1"` · `source_kind:"cloud_pc"`（**放行**） | 0 |
| `{"op":"gate_budget","action":"provision"}` | `ok:false` · `denied:true` · `rule:"budget_bill_missing"` · `action:"provision"` · **`missing:["budget","bill"]`** · `why:"花钱 / 不可逆动作之前必须先有**资源与预算读数**（预算 + 账单）——「先花钱后算账」是本模块最贵的一种错"` | 0 |
| `{"op":"gate_budget","action":"release"}` | 同上，`action:"release"`，`missing:["budget","bill"]` | 0 |
| `{"op":"gate_official","entry":"curl:https://api"}` | `ok:false` · **`readonly:true`** · `denied:true` · `rule:"self_built_request"` · `why:"**自己拼 HTTP 请求 = 绕官方入口** ⇒ 一律拒"` | 0 |
| `{"op":"gate_identity","payload":"改写云上身份内核"}` | `ok:false` · `denied:true` · `rule:"identity_write_on_cloud"` · `hit:"改写云上身份内核"` · `why:"身份内核的源在本地；云端只跑**副本** ⇒ 不许在云上下身份改写指令"` | 0 |
| `{"op":"gate_key","payload":"sk-FAKEFAKEFAKEFAKE"}` | `ok:false` · `denied:true` · `rule:"plaintext_key"` · **`masked:"sk-F****"`** · `why:"凭据只走密钥池（DPAPI）；明文一旦进返回值就等于落了两处"` | 0 |

🔴 **上表八条里六条是"拒"，退出码全是 0。**
⇒ **本域的"拒"（`denied:true`）根本不反映在退出码上**：那是**闸的结论**，
不是 `run_task` 层的 `denied`（那一层才会 exit 1）。
**只看退出码会把六条拒绝全部读成成功。**

🔴 还有一处混装：`gate_official` 的拒绝信封里**同时有 `readonly:true` 和 `denied:true`**
（源码 133 行 `{"ok": bool(ok), "readonly": True, …, "denied": (not ok), …}`）。
⇒ **别拿 `readonly:true` 当"这一发没问题"的证据** —— 它在这条分支里是**常量**，与判定无关。

### 6.3 四个动作 op（**源码所见，未跑**）

`provision` / `connect` / `snapshot` / `release` 一律走 `_not_implemented(op)`：

```python
{"ok": False, "denied": True, "rule": "not_implemented", "op": op,
 "requires_external_key": True,
 "reason": "本地无云厂商凭据 ⇒ 本骨架只给形状与闸，**不假装能开通**",
 "next": "主人给凭据（走密钥池）+ 授权出网后，接官方 CLI / SDK"}
```

🔴 **`denied:true` 在这里的含义是"未实现"，不是"你没授权"**：
`rule` 是 `not_implemented` 而**不是**任何作用域名，`missing` 也不在。
⇒ **两句话长得很像，别混**（同族坑见 `gbt-integration` §6.5 的 `not_implemented`）。

---

## 7. 失败典型样子（照着认，别认错）

| 症状 | 真因 | 正确读法 |
|---|---|---|
| `rule:"not_implemented"` + `requires_external_key:true` | 骨架期没接线 | **不是"没授权"**；是"主人没给凭据、本骨架不假装能开通"（§6.3） |
| `rule:"budget_bill_missing"` + `missing:["budget","bill"]` | 花钱/不可逆动作前**没给预算与账单读数** | **不是"没钱"** —— 判据是"有没有先给读数"（源码原话），不是余额 |
| `rule:"self_built_request"` | `entry` 不是 `cli:`/`sdk:` 打头 | 走官方入口；**自己拼 HTTP 请求一律拒** |
| `rule:"official_entry_missing"` | 根本没给 `entry` | 补 `entry`，形如 `cli:…` / `sdk:…` |
| `rule:"identity_write_on_cloud"` + `hit` | 载荷里夹了身份改写 | 身份源在本地，**云端只跑副本** |
| `rule:"plaintext_key"` + `masked` | 载荷里带了明文凭据 | 凭据只走密钥池（DPAPI） |
| `rule:"call_not_traced"` / `rule:"bad_source_kind"` | `trace_ref` 空 / `source_kind ≠ "cloud_pc"` | **无痕即未发生** |
| 期望"云电脑现在能用" | `provider: null` + `credentials_present: false` | **别把 `status:"ok"` 读成"云上可用"**（§6.1） |
| 期望"本机行云电脑就行" | `local_pc_state` 明说两处不许互相顶 | **云电脑 ≠ 本机** |
| `JSONDecodeError: Expecting property name enclosed in double quotes` | PowerShell 转义了 JSON | 用单引号原样包（§3） |

---

## 8. 🔴 未验清单（**为什么不做**，逐条）

| 动作 | 状态 | 为什么不做 |
|---|---|---|
| `{"op":"provision"}` | **未验** | **花钱 + 不可逆**。任务明令 `cloud_pc` 的 PROVISION 不跑；虽然源码显示它会先走 `_not_implemented`，但**纪律上不碰** |
| `{"op":"release"}` | **未验** | **不可逆**。同上，明令不跑 |
| `{"op":"snapshot"}` | **未验** | **花钱**。同上，明令不跑 |
| `{"op":"connect"}` | **未验** | 同一族的动作 op（明令不跑）；且它**不是只读 op**，只是"可逆" |
| `gate_trace` 的**失败**分支（`trace_ref` 空 / `source_kind` 错） | **未验** | 只读了源码分支（111-123），**没跑**；本规程只跑了成功那一发 |
| `gate_official` 的 `cli:` / `sdk:` 成功分支 | **未验** | 只跑了 `curl:…` 的**拒绝**那一发；成功那一发**没跑** |
| `gate_identity` / `gate_key` 的无命中分支（载荷干净） | **未验** | 只跑了命中那一发 |
| 真去连任何云厂商 CLI/SDK | **未验** | 盘上无凭据（`credentials_present:false`），且那属于"出网 + 花钱" |

> **"未验"不是"不能用"**：上表每一条都**存在**、都**有源码落点**；缺的是**当次运行证据**。
> 本规程**不拿"我以为能"当"验过"**。

---

## 9. 与相邻域的边界（一句话切干净）

| 相邻 | 谁是谁 | 边界 |
|---|---|---|
| `gbt-pipeline`（`pipeline` 域，18 位） | 部署 / 晋升 / 回滚 / 写生产交付区 | **两家都"花钱般要紧"，但门在完全不同的层**：`one_key_deploy` / `mirror_release` / `room_release` / `pipeline_submit` / `pipeline_rollback` 在 `policy.py` 里**明挂 `deploy_publish`（部分另加 `process_execute`+`filesystem_write`）**；而 `cloud_pc` 的 **policy 层是零作用域**，门在模块自己的 `gate_budget`。⇒ **绝不许拿 `cloud_pc` 的"零作用域"去推断 `deploy_publish` 也免卡，反之亦然** |
| `gbt-integration`（`feishu_embed`） | 面板卡⑥ | **形态同族**（都是"面板加一扇窗 + 卡片 + 触手"，都零作用域），但本域**五原语里有花钱/不可逆的**；feishu_embed **不花钱、不落盘**。⇒ **"都零作用域"不等于"都不花钱"**（两域都在 `omni.DANGER_DOMAINS` 里） |
| `gbt-automation`（`browser`） | 浏览器 | 云电脑要**看界面**时，看的动作归触手；本域只管"开/连/快照/退"的形状与闸 |
| `gbt-tentacle`（`tentacle` 域） | 手眼网耳 | 卡片明说 `buttons_go_through` 走到"**触手**" —— 那是**接线后的**设计，**现在没接线**（一律 `not_implemented`） |

---

## 10. 🔴 报告层红线（先问"这是事实，还是我读错了地方"）

1. **零作用域 ≠ 只读**（**本域并列两条核心红线之一**）。
   `provision`（花钱+不可逆）与 `release`（不可逆）在 policy 层是**零作用域**。
   ⇒ **作用域只回答"policy 这一层有没有收口"，不回答"这一步有没有后果"。**
2. **零作用域 ≠ 没门**（**另一条**）。本域的门在**模块自己**的三层里：
   五原语表的 `needs_gate`、五个 `gate_*`、以及 `_not_implemented` 兜底。
   ⇒ **别把"policy 没有分支"读成"这事没人管"。**
3. **"能调" ≠ "能用"**。零作用域意味着**调得到**；但四个动作 op **一律 `not_implemented`**
   ⇒ **一个都干不了活**。本域把这两件事同时摆在台面上。
4. **`status:"ok"` ≠ 本体 `ok:true`**。本域这一版实测**外层与本体没打架**（只读那条外层 ok + 本体 `ok:true`），
   但**六条闸全部是"外层 ok + 内层 `ok:false`"**（§6.2）⇒ **外层根本看不出拒绝**。
   **判"这一发调用成功了吗"看外层；判"被检对象合规吗"看内层。**
5. **退出码不可信**。本域实测：只读成功 exit **0**；**六条闸拒绝也 exit 0**；
   只有 `run_task` 层的 `denied` 才 exit **1**（本域零作用域，所以**够不到那一层**）。
   ⇒ **本域全部拒绝都藏在"exit 0"后面。**
   `stamp: true/false` 是**回归印章的有无**，不是成功与否。
6. **混装字段别当真**：`gate_official` 的拒绝信封里 `readonly:true` 是**常量**（§6.2）。
   ⇒ **同一格字段在不同分支里可能语义不同**；引字段前先看它在哪个分支。
7. **读数与事实分开**：`provider: null` / `credentials_present: false` 是**现状读数**，
   不是"云电脑不存在"。模块自己写了"**本机可用，但云电脑 ≠ 本机**"。
8. **"图鉴是索引，实测才是读数"**：注册表 desc 说"只读骨架·门"，实测确实如此；
   但 desc **没有**告诉你"PROVISION 在 policy 层零作用域" —— 那要**现查**。

---

## 11. 不许做什么（红线）

1. **不许给自己发授权**：不跑 `auth grant`、不手写 `store/auth_grants.jsonl`、不改 `security/policy.py` / `auth_gate`。
2. **不许绕门**：不许为了"绕过授权/绕过闸门"直接调 `gbt_allinone.tools.cloud_pc` 里的函数替掉
   `run_task` 唯一门（AGENTS.md 明令：那是**未经授权的写入**，纪律上就是违规）。
3. **不许**在没有 `budget` + `bill` 两个读数的情况下推进任何"花钱 / 不可逆"的动作
   —— 这条**写在源码里**，也写在这里。
4. **不许自己拼 HTTP 请求**去调云厂商（`self_built_request` 一律拒）—— 只走官方 CLI / SDK。
5. **不许在云端下身份改写指令**（身份源在本地）。
6. **不许把明文云凭据写进 payload / 文档 / 示例**（本规程示例全用 `sk-FAKEFAKEFAKEFAKE` 这种假串）。
7. **不许替主人编云厂商名、规格或计费口径**（`provider: null` 就是"主人未给"）。
8. **不许把 `status:"ok"` 说成"云电脑可用"**，也不许把 `local_pc_state` 那句"本机可用"套到云上。
9. **不许改 `tools/codex-scripts/omni.py`**（本域登记行由交付报告给出，不擅自动手）；
   **不许动别的域**、不许改 `policy.py`。

---

## 12. 固化与出处（**重启后要在**）

| 什么 | 在哪 |
|---|---|
| 本规程（源） | `<仓>/skills/gbt-infra/SKILL.md` |
| 本规程（装机·托管目录） | `C:\Users\ADMIN\.openclaw-autoclaw\skills\gbt-infra\SKILL.md` |
| ⛔ **不许装到** | `~/.agents/skills/`（本仓 AGENTS.md 明令禁止） |
| 能力位名单（1 个：`cloud_pc`） | `<仓>/state/skill_atlas.json`（`domain == "infra"`）· 现扫可重建：`python tools/codex-scripts/omni.py build` |
| 授权判据（**单一真相**） | `<仓>/gbt_allinone/security/policy.py` 的 `evaluate()` —— ⚠️ **本域在里面没有任何分支**（这就是"零作用域"的来源） |
| 危险域名单 | `<仓>/tools/codex-scripts/omni.py:105` `DANGER_DOMAINS = {"pipeline","dangerous","infra","integration"}` |
| op 分发 | `<仓>/gbt_allinone/api.py:479-483`（`kind == "cloud_pc"` 那一支） |
| 实现（五原语/五红线/五闸） | `<仓>/gbt_allinone/tools/cloud_pc.py`（`run()` 159；五原语 25；五红线 55；五个闸 76/86/111/126/141） |
| 门与拒绝信封 | `<仓>/gbt_allinone/run_task`（唯一门）· `tools/codex-scripts/five-dim.py:131-172`（扁平信封的读法） |

**深蒸登记（应加、本次未擅自动手 —— 登记由主人统一做）**：`omni.py` 的 `DISTILLED_DOMAINS` 加一行

```python
    "infra": "gbt-infra",
```

加完后 `python tools/codex-scripts/omni.py gaps` 里 `infra 1 个能力位` 会从
`⏳ 在队里` 变成 `✅ 已深蒸 → gbt-infra`。

**验收（做完怎么证明真的做了）**：

```powershell
py -3.14 tools/codex-scripts/verify-distill.py --domain infra --skill gbt-infra
```

1. 上面这条必须 **PASS**（覆盖 1/1）；
2. 两份产物**逐字节相同**（sha256 一致）；
3. 再静态查一次 `policy.evaluate("cloud_pc", {"op":"provision"}).scopes` —— 必须**仍是空**
   （哪天空了变非空，回来改本文件 §2）；
4. 声明"某 op 能用"之前，先问自己：**这条是实测读数，还是我读错了地方？** 拿不准就写"未验"。
