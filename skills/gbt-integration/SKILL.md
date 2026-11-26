---
name: gbt-integration
displayName: GBT · integration 职业域用法规程（1 个能力位：feishu_embed）
version: 1.0.0
description: GBT小土豆V8 的 `integration` 职业域（飞书镶嵌窗口 / 面板卡⑥ / 走浏览器触手不走 API）用法规程。这个域**只有 1 个能力位**：`feishu_embed`。本文件把它写全：用途、四条红线、逐 op 静态查出来的作用域（**整位零作用域**，这就是"零作用域 ≠ 只读"的活样本）、真命令、9 个 op 逐个点名、外部面（三处 host「主人提供·盘上未见」+ 用户已登录会话）、失败典型样子、与 `gbt-automation`（它的接入点就是 browser_cap.open_url）的边界；并记下本机实测到的读数陷阱（`check_bypass`/`check_source`/`check_key` 外层 `status:"ok"` + `stamp:true` + `denied:false`，**内层却 `ok:false` + `denied:true`** —— 两层打脸；`op=open` 返回 not_implemented 不假装打开）。当用户要打开飞书知识库/文档/多维表格、要搜索飞书、要看最近文档，或 feishu 调用报 `bypass_login` / `feishu_as_source` / `call_not_traced` / `not_implemented` 时使用。
triggers:
  - "飞书"
  - "feishu"
  - "lark"
  - "多维表格"
  - "知识库"
  - "面板卡⑥"
  - "镶嵌窗口"
  - "浏览器触手"
  - "feishu_embed"
  - "integration"
  - "bypass_login"
  - "feishu_as_source"
---

# GBT · integration 职业域用法规程（1 个能力位：`feishu_embed`）

> 开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属
>
> **这份规程解决什么**：`integration` 是一个**一位一域**的小域，但它有两种"假"要拆：
> ① **假安全** —— `feishu_embed` 在 `security/policy.py` 里**一条分支都没有**，静态查出来**零作用域**；
> 但它描述的是"**打开飞书页面**"这种**对外**动作。**零作用域 ≠ 只读**，本域就是最干净的那个样本。
> ② **假失败 / 假成功** —— 实测同一发信封里，**外层说 `status ok` / `stamp true` / `denied false`，
> 内层说 `ok:false` / `denied:true`**。**两层打脸**，认哪层是本域最要紧的一问。
> 本文件把「哪个 op、要不要授权、失败长什么样、读数该看哪个字段」逐个钉死，
> 并把**本机实测过的坑**如实记下来 —— **没验过的一律写"未验"，不冒充验过**。

**唯一现读入口（别信任何二手描述，包括本文件）**：

```powershell
py -3.14 tools/codex-scripts/five-dim.py cap feishu_embed ['<JSON载荷>'] [--full]
```

`cap` 一律走 `gbt_allinone.run_task`（**唯一门**）；被门拒绝就**如实报缺什么作用域**，不绕路。

---

## 0. 一位一域（先确认名字，别照抄别人的表）

现扫 `state/skill_atlas.json`（`domain == "integration"`）**只有一条**：

| 域 | 能力位（kind） | handler | type | 注册表 desc 原文 |
|---|---|---|---|---|
| `integration` | **`feishu_embed`** | `feishu_embed` | — | "飞书镶嵌窗口（只读骨架·门）：面板卡⑥，**走浏览器触手不用 API**；四条红线（飞书是副本本地是源/凭据不许明文/不绕验证/每次操作留痕 source_kind=feishu）" |

模块头部自己写的 `CAP_TYPE = "external"`（`feishu_embed.py:25`：它是面板上的一道「门」）。
注册表 `requires_params=[]` · `params_hint=""` · `needs_confirmation=false` · `safe=true`
⇒ 空载荷调用**合法**（落到只读 `status`，见 §6.1）。

> ⚠️ **不要照抄"飞书 = lark 技能簇"那件事**：`omni.py` 的 `DISTILLED_CLUSTERS` 里
> `"lark": "gbt-lark"` 管的是 **28 条 lark-* 原生技能**（`lark-im` / `lark-doc` / `lark-base` …）；
> 本规程管的是**图鉴里那个能力位 `feishu_embed`** —— **两者不是一回事**。
> 要调飞书原生 API（消息/日历/文档/多维表格）走 `gbt-lark` 那个簇；本域只管"面板上那一扇窗"。

---

## 1. 什么时候用（意图 → 落点）

| 人想干什么 | 落到哪个 op | 只读还是要授权 |
|---|---|---|
| 看这扇窗现在的形态（模式/真相源/要不要凭据/走哪条触手/三处 host） | `status`（**空载荷默认就是它**） | 只读，**零作用域** |
| 看它认哪 5 个动作 | `actions` | 只读，零作用域 |
| 看四条红线 | `redlines` | 只读，零作用域 |
| 看那三处 host 从哪来的 | `hosts` | 只读，零作用域 |
| 看它的浏览器触手接入点 | `tentacle` | 只读，零作用域 |
| 判一个计划有没有"绕验证"（模拟登录 / 抓 Cookie） | `check_bypass` | 只读闸，**零作用域** |
| 判一个计划有没有"把飞书当真相源" | `check_source` | 只读闸，零作用域 |
| 判一段载荷里有没有明文凭据 | `check_key` | 只读闸，零作用域 |
| 判有没有留痕（`source_kind=feishu`） | `check_trace` | 只读闸，零作用域 |
| **打开**知识库 / 文档 / 多维表格 / 搜索 / 最近文档 | `open` + `action` | **零作用域，但本质是对外动作**（现行版本返回 `not_implemented`，见 §4/§8） |

**不在这 1 个位里的事**：飞书原生 API（发消息 / 建文档 / 读多维表格 / 日历 / 审批） → `gbt-lark` 簇；
打开**任意**网页 → `gbt-automation`（`browser`）；看屏幕/点界面 → `gbt-tentacle`。

---

## 2. 🔴 要过哪道门：**整位零作用域 —— 这就是本域最该讲清的一条**

```python
from gbt_allinone.security import policy
policy.evaluate("feishu_embed", {}).scopes                                  # → ()
policy.evaluate("feishu_embed", {"op": "open", "action": "OPEN_WIKI"}).scopes  # → ()
```

**唯一权威**是 `gbt_allinone/security/policy.py` 的 `evaluate()`。
实测（本机 2026-09-22）：**`feishu_embed` 在 `policy.py` 里没有任何 `elif kind == "feishu_embed":` 分支**
（全文件 grep 零命中），所以：

| op | 作用域（实测） |
|---|---|
| `status` / `actions` / `redlines` / `hosts` / `tentacle` | **零** |
| `check_bypass` / `check_source` / `check_key` / `check_trace` | **零** |
| **`open`（含 `action`）** | **零** |

> 🔴🔴 **零作用域 ≠ 只读 —— 本域就是这句话的样本。**
> `open` 在门这一层**完全免卡**（policy 没给它挂任何作用域），
> 而它要做的事是"**去外部面把飞书打开**"。
> **"门没拦"只说明"策略层没把这一格收口"，不说明"这一步没有后果"。**
> 对照：`gbt-infra` 的 `cloud_pc` PROVISION（**花钱 + 不可逆**）同样零作用域；
> `gbt-social` 的 `auto_publish` PUBLISH（**不可逆 + 出网**）同样零作用域；
> `gbt-collab` 的 `stigmergy` DEPOSIT（**真写盘**）同样零作用域。
> ⇒ **一家四口都零作用域，四家都会动手。别拿作用域当"有没有后果"的尺子。**

**那"门"在哪？** 本域的闸**不在 policy，在模块自己**（四条红线做成机械闸）：
`check_no_bypass`（不绕验证）· `check_copy_not_source`（飞书是副本）· `check_no_plaintext_key`（凭据不许明文）·
`must_trace`（每次留痕 `source_kind=feishu`）。实测它们**真的会拒**（§6.4）。
⇒ **"policy 零作用域"+"模块自带闸"= 两道不同层的门**，别因为看见前一层是空的就说"没门"。

---

## 3. 怎么调（真命令）

```powershell
# ── 只读这一档（零作用域；本规程真跑过，见 §6）──
py -3.14 tools/codex-scripts/five-dim.py cap feishu_embed
py -3.14 tools/codex-scripts/five-dim.py cap feishu_embed '{"op":"actions"}'
py -3.14 tools/codex-scripts/five-dim.py cap feishu_embed '{"op":"redlines"}'
py -3.14 tools/codex-scripts/five-dim.py cap feishu_embed '{"op":"hosts"}'
py -3.14 tools/codex-scripts/five-dim.py cap feishu_embed '{"op":"tentacle"}'
py -3.14 tools/codex-scripts/five-dim.py cap feishu_embed '{"op":"check_bypass","action":"模拟登录"}'
py -3.14 tools/codex-scripts/five-dim.py cap feishu_embed '{"op":"check_source","action":"以飞书为源"}'
py -3.14 tools/codex-scripts/five-dim.py cap feishu_embed '{"op":"check_key","payload":"sk-FAKEFAKEFAKEFAKE"}'
py -3.14 tools/codex-scripts/five-dim.py cap feishu_embed '{"op":"check_trace","trace_ref":"x","source_kind":"feishu"}'

# ── 对外那一档（零作用域但本规程不跑，见 §8）──
py -3.14 tools/codex-scripts/five-dim.py cap feishu_embed '{"op":"open","action":"OPEN_WIKI","target":"…"}'
```

🔴 **PowerShell 里传 JSON 载荷：用单引号原样包住 JSON**（`'{"op":"actions"}'`）。
写成 `'{\"op\":\"actions\"}'` 会让 `five-dim.py:139` 的 `json.loads` 直接抛
`JSONDecodeError: Expecting property name enclosed in double quotes`（同族坑见 `gbt-llm` 的 §2）。

---

## 4. 有哪些 op（源码逐个点名，不猜）

`gbt_allinone/tools/feishu_embed.py:175` `run(op="status", **params)`，**9 个 op**：

| op | 去处（源码行） | 说明 |
|---|---|---|
| `status` | `FeishuEmbed().status()`（144） | 空载荷默认；返回 `mode` / `source_of_truth` / `credential_needed` / `network_needed` / `tentacle` / `hosts` / `note` |
| `actions` | 枚举 `FeishuAction`（29） | 5 个：`OPEN_WIKI`（打开知识库）· `OPEN_DOC`（打开文档）· `OPEN_BASE`（打开多维表格）· `SEARCH`（搜索）· `LIST_RECENT`（最近文档） |
| `redlines` | `RED_LINES`（61） | 四条 |
| `hosts` | `FEISHU_HOSTS`（45） | 三处 + `HOSTS_NOTE` |
| `tentacle` | `BROWSER_TENTACLE`（54） | `module` / `entry` / `siblings` / `native` |
| `check_bypass` | `check_no_bypass(params)`（74） | 拒：`bypass_login` |
| `check_source` | `check_copy_not_source(params)`（88） | 拒：`feishu_as_source` |
| `check_key` | `check_no_plaintext_key(params.get("payload") or "")`（102） | 拒：`plaintext_key` |
| `check_trace` | `must_trace(params.get("trace_ref") or "", params.get("source_kind") or "")`（112） | 拒：`call_not_traced` / `bad_source_kind` |
| `open` | `FeishuEmbed().open(action, target)`（154） | **骨架期**：`action` 不认 ⇒ `unknown_action`；打开类缺 `target` ⇒ `missing_target`；认了且给了 target ⇒ **`{"ok": false, "reason": "not_implemented"}`** |

**未知 op**：`raise ValueError("未知 op %r（可用：status/actions/redlines/hosts/tentacle/check_bypass/check_source/check_key/check_trace/open）")`。

⚠️ **动作名两套都认**（`FeishuEmbed._to_action` 1134-142）：**`name` 与 `value` 都行**
—— 源码注释写着"实测踩过：只认 value ⇒ `OPEN_WIKI` 会被判未知"。
⇒ 传 `"OPEN_WIKI"` 和传 `"打开知识库"` **都可以**。

---

## 5. 落点 / 外部面（动手会碰到什么）

模块 docstring 原话：**"本骨架只读：不打开浏览器、不出网、不落盘、不发密钥。"** 逐条对上：

| 维度 | 现状（实测） |
|---|---|
| **形态** | 面板**卡⑥**；`mode: "browser_tentacle"` —— **走浏览器触手，不走 API** |
| **真相源** | `source_of_truth: "local"` —— **本地是源，飞书是副本** |
| **凭据** | `credential_needed: false` —— 走**你已登录的浏览器会话**，不需要 DPAPI、不需要新密钥 |
| **外部面** | `network_needed: "user_session（你已登录的浏览器会话）"` |
| **三处 host** | `resonate.feishu.cn` · `my.feishu.cn` · `kjpt2h5ekoxy.jp.larksuite.com`，**三处 `from` 全是"主人提供"**；`HOSTS_NOTE` 原话："盘上**未抓到** feishu/larksuite URL ⇒ 状态为「主人提供 · 盘上未见」，**不擅自验证、不擅自请求**" |
| **触手接入点** | `module: "gbt_allinone/browser_cap.py"` · `entry: "open_url"` · `siblings: ["open_url","search","fetch","automate","run"]` · `native: "gbt_allinone/native_browser.py（51 个函数）"` |
| **落盘** | **无**。连 trace 也只是**校验**（`check_trace` 判 `trace_ref` 非空 + `source_kind == "feishu"`），模块自己**不写** `trace_store` |
| **为什么不用 API** | 模块 docstring 原话："凭据读不出（沙箱身份读不了 DPAPI）+ 出网受限 ⇒ API 路径跑不通" |

---

## 6. 实测读数（**只读真跑，抄真实字段**；机器 = 本机 2026-09-22）

### 6.1 空载荷 `cap feishu_embed`

```json
{"gate":"run_task","kind":"feishu_embed","status":"ok","stamp":true,"denied":false,
 "result":{"ok":true,"readonly":true,"mode":"browser_tentacle",
   "source_of_truth":"local","credential_needed":false,
   "network_needed":"user_session（你已登录的浏览器会话）",
   "tentacle":{"module":"gbt_allinone/browser_cap.py","entry":"open_url",
     "siblings":["open_url","search","fetch","automate","run"],
     "native":"gbt_allinone/native_browser.py（51 个函数）"},
   "hosts":[{"host":"resonate.feishu.cn","from":"主人提供"},
            {"host":"my.feishu.cn","from":"主人提供"},
            {"host":"kjpt2h5ekoxy.jp.larksuite.com","from":"主人提供"}],
   "note":"面板卡⑥：只呈现 + 走浏览器触手打开；**本刀不改面板**"}}
```

exit **0**。

### 6.2 `actions` / `hosts` / `tentacle`

| 命令 | 本体关键字段（实测） | exit |
|---|---|---|
| `{"op":"actions"}` | `ok:true` · `actions` 5 条：`OPEN_WIKI→打开知识库` · `OPEN_DOC→打开文档` · `OPEN_BASE→打开多维表格` · `SEARCH→搜索` · `LIST_RECENT→最近文档` | 0 |
| `{"op":"hosts"}` | `ok:true` · 三处 host（同上）· `note:"三处 host **均由主人提供**；盘上**未抓到** feishu/larksuite URL ⇒ 状态为「主人提供 · 盘上未见」，**不擅自验证、不擅自请求**。"` | 0 |
| `{"op":"tentacle"}` | `ok:true` · `module:"gbt_allinone/browser_cap.py"` · `entry:"open_url"` · `siblings[…5]` · `native:"gbt_allinone/native_browser.py（51 个函数）"` | 0 |

### 6.3 `check_trace`（唯一"放行"的闸）

```json
{"gate":"run_task","kind":"feishu_embed","status":"ok","stamp":true,"denied":false,
 "result":{"ok":true,"readonly":true,"trace_ref":"x","source_kind":"feishu"}}
```

`{"op":"check_trace","trace_ref":"","source_kind":"feishu"}` ⇒ 内层
`{"ok":false,"denied":true,"rule":"call_not_traced","why":"每次打开/操作飞书都要留痕（调用级）；无痕即未发生"}`。

### 6.4 🔴🔴 **两层打脸**：外层 ok，内层 denied

`{"op":"check_bypass","action":"模拟登录"}`：

```json
{"gate":"run_task","kind":"feishu_embed","status":"ok","stamp":true,"denied":false,
 "result":{"ok":false,"denied":true,"rule":"bypass_login","seen":"模拟登录",
   "why":"不绕验证：用你已登录的浏览器会话；模拟登录 / 抓 Cookie 一律拒"}}
```

`{"op":"check_source","action":"以飞书为源"}` ⇒ 内层
`{"ok":false,"denied":true,"rule":"feishu_as_source","seen":"以飞书为源","why":"本地是真相源、飞书做镜像/外发；把飞书当源 = 给知识库口径再添一处（已有三处未收口）"}`

`{"op":"check_key","payload":"sk-FAKEFAKEFAKEFAKE"}` ⇒ 内层
`{"ok":false,"denied":true,"rule":"plaintext_key","seen":"sk-FAKE…","why":"凭据不许明文；本方案走浏览器触手，压根不需要新凭据"}`

🔴 **这三条外层全是 `status "ok"` · `stamp true` · `denied false` · exit 0**，
**而内层全是 `ok:false` · `denied:true`**。
**两句话互相打脸。** 认哪层？
⇒ **认内层**：外层的 `ok/status` 描述的是**"这一发调用有没有被门拦"**（拦了才是外层 denied），
内层的 `ok/denied` 描述的是**"这个闸判的结论"**。
**`check_*` 系列返回的 `denied:true` 是"该被拒"的正解，不是"我被拒了"。**
⇒ **判"这一发成功了吗"看外层；判"被检的那个计划合规吗"看内层。两个问题，两层回答，别串。**

（同族活样本：`gbt-tentacle` 里 `cap tentacle '{"method":"audio_devices"}'` 的
外层 `status ok` 与内层 `cognition.focus.denied:true` 打脸 —— 那边内层是**认知层自己的账**，
**不是调用结果**。⇒ **"内外打架"时先问"内层那一格是谁的账"，再决定认哪层。**）

### 6.5 `open`（**源码所见，未跑**）

`FeishuEmbed().open()` 三个分支（`feishu_embed.py:154-172`）：

| 给什么 | 返回 |
|---|---|
| `action` 不在枚举里 | `{"ok": false, "denied": true, "rule": "unknown_action", "action": …, "known": ["OPEN_WIKI","OPEN_DOC","OPEN_BASE","SEARCH","LIST_RECENT"]}` |
| 是 `OPEN_WIKI`/`OPEN_DOC`/`OPEN_BASE` 但 **`target` 空** | `{"ok": false, "denied": true, "rule": "missing_target", "action": …, "why": "打开类动作要给出目标（知识库/文档/表格）"}` |
| 认了且给了 `target` | `{"ok": false, "reason": "not_implemented", "next": "接浏览器触手（原生优先）：gbt_allinone/browser_cap.py.open_url", "action": …, "credential_needed": false, "note": "骨架期如实说未实现，不假装已打开"}` |

🔴 注意第三条：**`ok:false` 但 `denied` 那几个字段不在** —— 它**不是被门拒，是"还没接线"**。
`reason` 是 `not_implemented`，不是 `denied`。⇒ **别把"未实现"读成"没授权"。**
本条**未跑**（理由见 §8）。

---

## 7. 失败典型样子（照着认，别认错）

| 症状 | 真因 | 正确读法 |
|---|---|---|
| 外层 `status:"ok"` 而内层 `ok:false` + `denied:true` + `rule:"bypass_login"/"feishu_as_source"/"plaintext_key"/"call_not_traced"` | **闸判"这个计划该拒"** | **不是"我被拒了"**；外层 ok 表示调用本身没被门拦（§6.4） |
| 内层 `ok:false` + `reason:"not_implemented"`（**没有 `denied`**） | 骨架期没接线 | 不是"没授权"，是"还没实现"（§6.5） |
| 内层 `rule:"unknown_action"` + `known:[…]` | `action` 拼错 | 用 5 个枚举名之一（`name`/`value` 都认） |
| 内层 `rule:"missing_target"` | 打开类动作没给 `target` | 补 `target` |
| 报"三处 host 是哪三处" | 只有 `op=hosts` / `op=status` 有 | 别去别处找；且 `HOSTS_NOTE` 明确写了"盘上未验证" |
| 期望"发飞书消息 / 建文档" | **走错域** | 那是 `gbt-lark` 簇（28 条 lark-* 技能），不是本域 |
| `JSONDecodeError: Expecting property name enclosed in double quotes` | PowerShell 转义了 JSON | 用单引号原样包（§3） |

---

## 8. 🔴 未验清单（**为什么不做**，逐条）

| 动作 | 状态 | 为什么不做 |
|---|---|---|
| `{"op":"open",…}`（含给了 `target` 的发） | **未验** | **对外动作**（会去打开外部面）。虽然现行版本返回 `not_implemented`（源码所见）**根本到不了浏览器**，但纪律上属"对外" —— 本规程不跑 |
| 真去 `browser_cap.open_url` 打开那三处 host | **未验** | 会**真拉起浏览器 + 出网**；且 `HOSTS_NOTE` 明确"不擅自验证、不擅自请求" |
| 真去 `browser_cap.fetch` 抓飞书页面 | **未验** | 出网；且飞书页面需登录态，抓到的也只是登录墙 |
| `check_bypass` / `check_source` / `check_key` / `check_trace` 的**其它命中样本** | 部分**未验** | 本规程只跑了 3 个命中样本（模拟登录 / 以飞书为源 / 假 sk- 前缀）+ 1 个缺失样本（`trace_ref` 空）。**全部正则分支未穷举**（`_BYPASS_LOGIN` 7 条 / `_AS_SOURCE` 5 条） |
| `{"op":"check_trace",…,"source_kind":"别的"}` | **未验** | 已知会走 `bad_source_kind` 分支（源码 119-123），**没跑** |

> **"未验"不是"不能用"**：上表每一条都**存在**、都**有源码落点**；缺的是**当次运行证据**。
> 本规程**不拿"我以为能"当"验过"**。

---

## 9. 与相邻域的边界（一句话切干净）

| 相邻 | 谁是谁 | 边界 |
|---|---|---|
| `gbt-automation`（`browser`） | 浏览器自动化 | **本域的接入点就是它**：实测 `op=tentacle` 返回 `module:"gbt_allinone/browser_cap.py"`、`entry:"open_url"` ⇒ 飞书页面真要"打开"时**是 `browser` 在动手**。反过来：**`browser` 不知道"飞书"是什么** —— 三处 host、四条红线、五个动作**只在本域**。⇒ **要用飞书语义走本域；要"打开一个网址"走 `browser`** |
| `gbt-lark`（簇，不是域） | 28 条 `lark-*` 原生技能 | **两条完全不同的路**：`gbt-lark` 走 **API**（要身份闸、写出去先问主人）；`feishu_embed` **明确"不用 API"**（走浏览器触手、用你已登录的会话、不需凭据）。**谁也别替谁** |
| `gbt-tentacle`（`tentacle` 域） | 手眼网耳 | 本域**不碰屏幕、不点桌面**；`op=tentacle` 那三个字是"**浏览器触手**"（`browser_cap`），**不是** `tentacle` 域的能力位 |
| `gbt-infra`（`cloud_pc`） | 云电脑（同样是"面板加一扇窗"） | 两家**形态同族**（独立窗口 + 卡片 + 触手），但 **cloud_pc 零作用域且五原语里有花钱/不可逆的**；本域**不花钱、不落盘**。⇒ **别把两边的"零作用域"当成同一件事** |

---

## 10. 🔴 报告层红线（先问"这是事实，还是我读错了地方"）

1. **零作用域 ≠ 只读**（**本域的核心红线**）。`feishu_embed` 整位零作用域，而 `open` 本质对外。
   ⇒ **作用域只回答"门有没有拦"，不回答"这一步有没有后果"。**
2. **`status:"ok"` ≠ 本体 `ok:true`**。§6.4 三条闸就是活样本：
   外层 `status ok` + `stamp true` + `denied false`，内层 `ok:false` + `denied:true`。
   **判"这一发调用成功了吗"看外层；判"被检对象合规吗"看内层。**
3. **扁平拒绝信封**：若真被门拦（本域当前零作用域，实测**拦不到**），
   形状与 `gbt-automation` §6.5 一致 —— `missing_scopes` / `reason` / `how_to_grant` 在**顶层**，
   **没有 `gbt_result`**。⇒ **读顶层字段**。
4. **退出码不可信**。本域实测四类：
   只读成功 → exit **0**；闸判 `denied:true`（内层）→ **仍然 exit 0**；
   `check_trace` 缺 `trace_ref` → **exit 0**；只有**门拦**（外层 `denied`）才是 exit **1**。
   ⇒ **本域"内层拒绝"根本不反映在退出码上** —— 只看退出码会**全部读成成功**。
   `stamp: true/false` 是**回归印章的有无**，不是成功与否。
5. **"能调" ≠ "能用"**。`feishu_embed` 在 `omni.auto_run_verdict()` 里实测
   **`AUTO=False`**，理由是"域「integration」属于有后果的域"（`omni.DANGER_DOMAINS`）。
   ⇒ **`omni run` 不代跑它**。而它自己 9 个 op 里**能真干活的只有闸与读数**，
   `open` 是 `not_implemented`。**"能调"（门零作用域）与"能用"（有没有接线）是两件事。**
6. **"图鉴是索引，实测才是读数"**：`hosts` 的三处 host **只在模块常量里**、`HOSTS_NOTE` 自己就说"盘上未见"。
   ⇒ **不许把这三处 host 说成"已验证可访问"**。

---

## 11. 不许做什么（红线）

1. **不许给自己发授权**：不跑 `auth grant`、不手写 `store/auth_grants.jsonl`、不改 `security/policy.py` / `auth_gate`。
2. **不许绕门**：不许为了"绕过授权/绕过闸门"直接调 `gbt_allinone.tools.feishu_embed` 里的函数替掉
   `run_task` 唯一门（AGENTS.md 明令：那是**未经授权的写入**，纪律上就是违规）。
3. **不许擅自验证那三处 host**：`HOSTS_NOTE` 原话"**不擅自验证、不擅自请求**"。
4. **不许模拟登录 / 抓 Cookie**：这是本域第一条红线（`bypass_login`），
   **不因为"就试一下"而例外**。
5. **不许把飞书当真相源**：本地是源、飞书是副本（`feishu_as_source`）。
6. **不许把凭据写进 payload**：`plaintext_key` 命中即拒（本规程连示例都用 `sk-FAKEFAKEFAKEFAKE` 这种假串）。
7. **不许把"外层 ok"说成"检查通过"**（§6.4）。
8. **不许改 `tools/codex-scripts/omni.py`**（本域登记行由交付报告给出，不擅自动手）；
   **不许动别的域**、不许改 `policy.py`。

---

## 12. 固化与出处（**重启后要在**）

| 什么 | 在哪 |
|---|---|
| 本规程（源） | `<仓>/skills/gbt-integration/SKILL.md` |
| 本规程（装机·托管目录） | `C:\Users\ADMIN\.openclaw-autoclaw\skills\gbt-integration\SKILL.md` |
| ⛔ **不许装到** | `~/.agents/skills/`（本仓 AGENTS.md 明令禁止） |
| 能力位名单（1 个：`feishu_embed`） | `<仓>/state/skill_atlas.json`（`domain == "integration"`）· 现扫可重建：`python tools/codex-scripts/omni.py build` |
| 授权判据（**单一真相**） | `<仓>/gbt_allinone/security/policy.py` 的 `evaluate()` —— ⚠️ **本域在里面没有任何分支**（这就是"零作用域"的来源） |
| 危险域名单 | `<仓>/tools/codex-scripts/omni.py:105` `DANGER_DOMAINS = {"pipeline","dangerous","infra","integration"}` |
| op 分发 | `<仓>/gbt_allinone/api.py:454-458`（`kind == "feishu_embed"` 那一支） |
| 实现 | `<仓>/gbt_allinone/tools/feishu_embed.py`（`run()` 175；四条闸 74/88/102/112；`open()` 154） |
| 门与拒绝信封 | `<仓>/gbt_allinone/run_task`（唯一门）· `tools/codex-scripts/five-dim.py:131-172`（扁平信封的读法） |

**深蒸登记（应加、本次未擅自动手 —— 登记由主人统一做）**：`omni.py` 的 `DISTILLED_DOMAINS` 加一行

```python
    "integration": "gbt-integration",
```

加完后 `python tools/codex-scripts/omni.py gaps` 里 `integration 1 个能力位` 会从
`⏳ 在队里` 变成 `✅ 已深蒸 → gbt-integration`。

**验收（做完怎么证明真的做了）**：

```powershell
py -3.14 tools/codex-scripts/verify-distill.py --domain integration --skill gbt-integration
```

1. 上面这条必须 **PASS**（覆盖 1/1）；
2. 两份产物**逐字节相同**（sha256 一致）；
3. 再静态查一次 `policy.evaluate("feishu_embed", {"op":"open"}).scopes` —— 必须**仍是空**
   （哪天空了变非空，回来改本文件 §2）；
4. 声明"某 op 能用"之前，先问自己：**这条是实测读数，还是我读错了地方？** 拿不准就写"未验"。
