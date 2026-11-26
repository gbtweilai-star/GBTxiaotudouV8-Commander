---
name: gbt-ui_card
displayName: GBT · ui 职业域用法规程（1 个能力位：ui_card）
version: 1.0.0
description: GBT小土豆V8 的 `ui` 职业域（ACUI 卡片协议）用法规程。这个域**只有 1 个能力位**：`ui_card`。本文件把它写全：op=schema/validate/create/close/action/snapshot/events/clear/verify 逐个点名、**纯函数·零作用域**（不写盘/不出网）、卡片是**纯数据**的五条铁律（白名单 kind/action.type · 纯文本拒 HTML/脚本/事件属性 · TTL 到期自动清 · 动作只回发事件不执行工具 · 上限 20 张/4 动作/2000 字）、CardBoard 内存板的行为、失败典型样子（白名单外拒/注入拒/超限拒）、与 gbt-console（工作台）和 gbt-creation（创作出口）的边界；并记下实测读数。当用户要发卡片、要做自检卡/确认卡、要查卡片协议白名单、或 ui_card 报 user_error 时使用。
triggers:
  - "ui_card"
  - "ACUI"
  - "卡片协议"
  - "ui"
  - "确认卡"
  - "自检卡"
---

# GBT · ui 职业域用法规程（1 个能力位：`ui_card`）

> 开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属
>
> **这份规程解决什么**：`ui` 是一位一域的最小域，它是**ACUI 卡片协议**——
> 蒸自上游参考项目的 Scene Protocol / ACUI，做成**我们自己的版本**（主人 2026-11-02 令）。
> 它的核心是**卡片是纯数据**：不渲染 HTML、不执行脚本、动作只回发事件给主循环。
> 本文件把「哪个 op、要不要授权、失败长什么样、读数该看哪个字段」逐个钉死。

**唯一现读入口（别信任何二手描述，包括本文件）**：

```bash
python tools/codex-scripts/five-dim.py cap ui_card ['<JSON载荷>'] [--full]
```

一律走 `gbt_allinone.run_task`（**唯一门**）；被门拒绝就**如实报缺什么作用域**，不绕路。

---

## 0. 一位一域（先确认名字）

现读 `gbt_allinone/caps_registry.py`（`domain == "ui"`）**只有一条**：

| 域 | 能力位（kind） | handler | safe | 注册表 desc 原文 |
|---|---|---|---|---|
| `ui` | **`ui_card`** | `ui_card` | **true** | ACUI 卡片协议；卡片是**纯数据**：kind/action.type 白名单 · 纯文本（拒 HTML/脚本/事件属性）· TTL 到期自动清 · 最多 20 张/4 动作/2000 字；动作只回发 `ui_card_action` 事件（`executed=false`），不执行任何工具；**纯函数·零作用域** |

**它不干什么**：不渲染 UI、不执行脚本、不写盘、不出网、不调模型。它是**纯函数协议层**。

分派链（实测可调）：
`api.py:329`（`kind == "ui_card"` → `from .tools import ui_card as _uc`）
→ `gbt_allinone/tools/ui_card.py`（`run(op, **params)` 188-221 行是全部分派）

---

## 1. 什么时候用（意图 → 落点）

| 人想干什么 | 落到哪个 op | 只读还是要授权 |
|---|---|---|
| 看支持哪些 kind / action.type / 上限 | `schema` | 只读，**零作用域** |
| 校验一张卡合不合法（不落板） | `validate` | 只读，**零作用域** |
| **发一张卡到板** | `create` | 🔴 写内存板（不落盘） |
| 关掉一张卡 | `close` | 🔴 改内存板 |
| **点卡片上的按钮** | `action` | 🔴 只回发事件，`executed=false` |
| 看板上有哪些卡 | `snapshot` | 只读，**零作用域** |
| 看卡片事件账本 | `events` | 只读，**零作用域** |
| 清空卡片板 | `clear` | 🔴 改内存板 |
| 自检判据 | `verify` | 只读，**零作用域** |

**不在这 1 个位里的事**：渲染真实 UI 组件 → `gbt-console`（工作台）；创作内容 → `gbt-creation`。

---

## 2. 🔴 要过哪道门：**整域零作用域（纯函数）**

**实测（本机 · `policy.evaluate` 逐 op 真跑）**：

```python
policy.evaluate("ui_card", {"op": "schema"}).scopes        # → ()    零作用域
policy.evaluate("ui_card", {"op": "validate"}).scopes     # → ()    零作用域
policy.evaluate("ui_card", {"op": "create"}).scopes       # → ()    零作用域（写内存板，不落盘）
policy.evaluate("ui_card", {"op": "close"}).scopes        # → ()    零作用域
policy.evaluate("ui_card", {"op": "action"}).scopes       # → ()    零作用域（只回发事件）
policy.evaluate("ui_card", {"op": "snapshot"}).scopes     # → ()    零作用域
```

| op | 作用域（实测） | risk | restricted |
|---|---|---|---|
| 全部 9 个 op | **零** | low | false |

🔴 **"零作用域"≠"没副作用"**：`create`/`close`/`action`/`clear` 会改**内存里的 CardBoard**，
但**不落盘、不出网**——作用域为空是因为不碰外部载体。**别把"改内存板"读成"改状态要授权"**。

**本域不需要任何授权**：所有 op 都不挂作用域，未受信会话也能直接调。

---

## 3. 怎么调（真命令）

```bash
# ── 只读这一档（零作用域）──
python tools/codex-scripts/five-dim.py cap ui_card                          # 空载荷 = schema
python tools/codex-scripts/five-dim.py cap ui_card '{"op":"schema"}'
python tools/codex-scripts/five-dim.py cap ui_card '{"op":"snapshot"}'
python tools/codex-scripts/five-dim.py cap ui_card '{"op":"verify"}'

# ── 写内存板这一档（零作用域，但改板）──
python tools/codex-scripts/five-dim.py cap ui_card '{"op":"create","card":{"kind":"info","title":"自检","body":"一切正常","actions":[{"id":"ok","type":"confirm","label":"知道了"}]}}'
python tools/codex-scripts/five-dim.py cap ui_card '{"op":"action","id":"uc-...","action":"ok"}'
python tools/codex-scripts/five-dim.py cap ui_card '{"op":"close","id":"uc-..."}'
```

---

## 4. 有哪些 op（源码逐个点名 · `tools/ui_card.py:188-221`）

| op | 去处 | 性质 |
|---|---|---|
| `schema` | 返回 kinds/action_types/limits | 只读 |
| `validate` | `normalize_card(card)` → 校验归一化，不落板 | 只读 |
| `create` | `_BOARD.create(raw)` → 校验 + 入板 + 记事件 | 🔴 改内存板 |
| `close` | `_BOARD.close(id)` → 出板 + 记事件 | 🔴 改内存板 |
| `action` | `_BOARD.act(id, action_id)` → **只回发 `ui_card_action` 事件，`executed=false`** | 🔴 改内存板（但不执行工具） |
| `snapshot` | `_BOARD.snapshot()` → 当前板上卡片 | 只读 |
| `events` | `_BOARD.events[-100:]` → 最近 100 条事件 | 只读 |
| `clear` | `_BOARD.cards.clear()` → 清空板 | 🔴 改内存板 |
| `verify` | `verify()` → 24 条判据自检 | 只读 |
| 未知 op | `raise ValueError("未知 op: …")` | 拒（非门拒） |

---

## 5. 🔴 五条铁律（卡片是纯数据）

源码 `tools/ui_card.py:3-14` 写明，本规程逐条钉死：

1. **卡片是数据**：纯文本渲染，**不允许 HTML/脚本/事件属性**（`_SCRIPT_RX` 拒 `<script>`/`<style>`/`javascript:`/`on*=`）。
2. **白名单**：`kind` 不在 `(info, selfcheck, wake, image, video, confirm, weather)` 直接拒；`action.type` 不在 `(confirm, dismiss, open, send, link)` 直接拒。
3. **动作只回发事件**：`action` op 只产出 `ui_card_action` 事件给主循环，`executed` **恒为 `false`**——**不在这里执行任何工具**。
4. **TTL**：过期自动消失（`_purge`）；账本只记 `create`/`close`/`action`/`expired`/`evicted`，可审计。
5. **上限**：最多 **20 张**、同时最多 **4 个 action**、`body` ≤ **2000 字**、`title` ≤ 120 字、`ttl` ≤ 86400（默认 300）。

---

## 6. 落点 / 外部面

| 维度 | 实测 |
|---|---|
| **kind 白名单** | `info` / `selfcheck` / `wake` / `image` / `video` / `confirm` / `weather`（7 种） |
| **action.type 白名单** | `confirm` / `dismiss` / `open` / `send` / `link`（5 种） |
| **上限** | 20 张 / 4 动作 / body 2000 / title 120 / ttl 86400（默认 300） |
| **id 规则** | 卡片 id：`[A-Za-z0-9_-]{1,64}`；action id：`[a-z0-9_-]{1,32}` |
| **落点** | **纯内存**（`_BOARD = CardBoard()`）；不落盘、不出网 |
| **事件账** | 内存 `events`，`events` op 取最近 100 条；不持久化 |

---

## 7. 实测读数（本机真跑，原文抄录）

### 7.1 `cap ui_card '{"op":"schema"}'`

```json
{"gate":"run_task","kind":"ui_card","status":"ok","stamp":true,"denied":false,
 "result":{"ok":true,"kinds":["info","selfcheck","wake","image","video","confirm","weather"],
  "action_types":["confirm","dismiss","open","send","link"],
  "limits":{"cards":20,"actions":4,"title":120,"body":2000,"ttl":86400}}}
```

**读法**：`status:"ok"` 是外层；`result.kinds`/`action_types`/`limits` 是内层白名单与上限。

### 7.2 `cap ui_card '{"op":"create","card":{"kind":"evil","title":"x"}}'`

```json
{"ok":false,"error":"user_error: 未知 kind: evil（允许 info,selfcheck,wake,image,video,confirm,weather）"}
```

**白名单外直接拒**，`user_error` 不是门拒（门根本没挂作用域）。

---

## 8. 失败典型样子（照着认）

| 症状 | 真因 | 正确读法 |
|---|---|---|
| `ok:false` + `error:"user_error: 未知 kind: …"` | kind 不在白名单 | 换合法 kind（§5） |
| `ok:false` + `error:"user_error: …含 HTML/脚本/事件属性"` | body/title 带注入 | 纯文本，别塞 HTML/`on*=`/`javascript:` |
| `ok:false` + `error:"user_error: actions 最多 4 个"` | 动作超上限 | 减到 ≤4 |
| `ok:false` + `error:"user_error: ttl 范围 0..86400"` | ttl 越界 | 调 ttl |
| `action` 回 `executed:false` | **设计如此** | 动作只回发事件，工具执行走主循环/统一门 |
| `close` 回 `ok:false` + `error:"no_such_card"` | 卡片不在板上 | 先 `snapshot` 看板上有什么 |
| 把 `create` 的"改内存板"读成"要授权" | 零作用域 ≠ 没副作用 | 改的是内存，不落盘不出网（§2） |

---

## 9. 🔴 未验清单

| 动作 | 状态 | 为什么不做 |
|---|---|---|
| 卡片渲染成真实 UI | **不做** | 本件是协议层，不渲染；渲染归 gbt-console |
| 动作触发真工具执行 | **不做** | `executed` 恒 false；工具执行走主循环/统一门 |
| 卡片落盘持久化 | **不做** | 纯内存板；持久化由调用方决定 |

> **"不做"不是"坏了"**：本件的纪律就是**卡片是纯数据、动作只回发事件**。

---

## 10. 与相邻域的边界（一句话切干净）

| 相邻 | 谁是谁 | 边界 |
|---|---|---|
| `gbt-console` | 工作台（3D 全景 + Bento） | 那是**渲染/展示层**；本域是**卡片协议层**，只产数据不渲染 |
| `gbt-creation` | 创作出口 | 创作产出内容；本域只承载"确认/自检/唤醒"等结构化卡片 |
| `gbt-system` | 体检/自检 | 自检的**结论**可做成 `selfcheck` 卡；本域只管卡片协议本身 |

---

## 11. 🔴 报告层红线

1. **外层 `status:"ok"` ≠ 内层合法**：判调用看外层，判卡片合不合法看 `result`/`error`（§7）。
2. **`user_error` ≠ 门拒**：白名单外/注入/超限是**本体拒**，门没挂作用域。
3. **`executed:false` 是设计**：动作只回发事件，别读成"动作没执行=坏了"。
4. **"零作用域"必须带"改内存板"说**：`create`/`close`/`action`/`clear` 改内存，但**不落盘不出网**。
5. **卡片是纯数据**：别把 HTML/脚本当卡片内容，白名单与注入拒是硬判据。

---

## 12. 不许做什么（红线）

1. **不许塞 HTML/脚本/事件属性**：卡片内容只许纯文本（`_SCRIPT_RX` 是硬判据）。
2. **不许给自己发授权**：本域本就零作用域，无需授权；更不许改 `security/policy.py`。
3. **不许绕门**：不直接调 `tools/ui_card.py` 的函数替掉 `run_task` 唯一门。
4. **不许**把 `action` 的 `executed:false` 读成"动作没执行=故障"——它是设计。
5. **不许**替主人编卡片内容/白名单——白名单是源码常量，不传的 kind 一律拒。

---

## 13. 固化与出处（**重启后要在**）

| 什么 | 在哪 |
|---|---|
| 本规程（源） | `<仓>/skills/gbt-ui_card/SKILL.md` |
| 本规程（装机·托管目录） | `C:\Users\ADMIN\.openclaw-autoclaw\skills\gbt-ui_card\SKILL.md` |
| 注册表条目 | `gbt_allinone/caps_registry.py`（`domain == "ui"` 唯一条，1592 行） |
| 分派 | `gbt_allinone/api.py:329` → `gbt_allinone/tools/ui_card.py`（`run()` 188-221） |
| 授权判据（**单一真相**） | `gbt_allinone/security/policy.py`（本域零作用域，无专属分支） |
| 现读入口 | `tools/codex-scripts/five-dim.py cap ui_card` |

**验收（做完怎么证明真的做了）**：

```bash
python tools/codex-scripts/verify-distill.py --domain ui --skill gbt-ui_card
```

1. 必须 **PASS**（覆盖 1/1）；
2. 两份产物**逐字节相同**（sha256 一致）；
3. 再静态查 `policy.evaluate("ui_card", {"op":"create"}).scopes` —— 必须**仍是** `()`；
4. 声明"卡片能渲染/动作能执行"之前先问：**这是实测读数，还是我读错了地方？** 本域是协议层，不渲染不执行。
