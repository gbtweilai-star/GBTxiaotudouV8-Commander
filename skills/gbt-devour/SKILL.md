---
name: gbt-devour
displayName: GBT · devour（吞天）职业域用法规程（4 个能力位）
version: 1.0.0
description: GBT小土豆V8 的 `devour`（吞天 · 自我进化）职业域用法规程。把注册表里这 4 个能力位逐个钉死：用途、只读还是要授权、要哪个作用域、真命令、落点、失败长什么样。本域的核心不是"能吞什么"，而是**4 个位里有 3 个会真动手（写盘 / 出网 / 跑外部大模型），而其中 `devour_reflect` 的作用域是空的** —— 门不会拦它，`preflight` 也不会拦它，只有框架自己那张"会改状态"的表知道它会动手。所以本规程把「零作用域 ≠ 只读」写成第一条红线，并如实记下：只读的 `devour_scan` 真跑过（附不写盘的哈希证据），会写的三个一律**没跑**、逐条标「未验 + 卡在哪」。当用户说「吞天 / 吞噬 / 吞一个 GitHub 仓库 / 能力缺口 / 反思进化 / 认知循环 / devour」，或某个 devour 能力位报"需要人工授权"、读数对不上时使用。
triggers:
  - "吞天"
  - "吞噬"
  - "吞一个"
  - "吞噬仓库"
  - "devour"
  - "能力缺口"
  - "缺口扫描"
  - "反思进化"
  - "认知循环"
  - "自我进化"
  - "知识胶囊"
  - "需不需要授权"
  - "data_export"
---

# GBT · devour（吞天）职业域用法规程（4 个能力位）

> 开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属
>
> **这份规程解决什么**：`devour`（吞天）是"框架自己找食吃、自己进化"的那个域，图鉴里只有 4 个能力位，
> 但**4 个里有 3 个会真动手**（写盘 / 出网 / 调外部大模型），而且**其中有一个的作用域是空的**：
> `devour_reflect` 在 `policy.evaluate()` 里查出来 `scopes == []`、`restricted == false`，
> 在 `preflight._STATE_CHANGING_KINDS` 里却明明白白写着它会改状态（`preflight.py:57`）。
> ⇒ 门（`policy.authorize`）对它**直接放行**，`preflight` 也**从不拒绝**（它只做在途去重/复用），
> 于是"零作用域"这个读数会把人骗得以为它免卡只读 —— **这是本域最大的坑**。
> 本文件把「哪个位、什么时候用、要不要授权、落点在哪、失败长什么样」逐个钉死，
> 并**只把只读的那一个真跑过**，其余三个如实写"未验 + 为什么不做"。

**唯一现读入口（别信任何二手描述，包括本文件）**：

```powershell
py -3.14 tools/codex-scripts/five-dim.py cap <能力位> ['<JSON载荷>'] [--full]
```

`cap` 一律走 `gbt_allinone.run_task`（**唯一门**）；被门拒绝就**如实报缺什么作用域**，不绕路。
`--full` 不必加在这里的四个位上（它们返回体都很小，默认收窄不会触发）：`--full` 只在
返回体超过 1500 字符时才改变读数，作用见 `tools/codex-scripts/five-dim.py:165-170`。

---

## 0. 先认「手」：4 个位是 1 只读 + 3 会动手（**这是本域的全部风险**）

| 位 | 会不会动手 | 静态作用域 | 在 `preflight` 的"会改状态"表里 | `omni` 判据 |
|---|---|---|---|---|
| `devour_scan` | **只读**（实测：不写盘，见 §3.1 哈希证据） | 无（零作用域） | 否 | ✅ **AUTO（可直跑）** |
| `devour_github` | **会**：出网 + 写盘 | `data_export` + `filesystem_write` | 否（作用域已让它进侧效应） | 🔒 NO（要参数 + 要人确认 + 要过门） |
| `devour_reflect` | **会**：写 `store/devour_state.json`（弱 cap > 15 时还会出网） | **无（零作用域）** | **是**（`preflight.py:57`） | 🔒 NO（**靠"会改状态"表拦，不是靠作用域**） |
| `devour_pulse` | **会**：完整认知循环（吞 / 反思 / 消化 / 重组 / 创新 / 知识库） | `data_export` + `filesystem_write` + `external_llm` | **是**（`preflight.py:58`） | 🔒 NO |

**判据（一句话）**：
只想**看一眼缺口在哪** → `devour_scan`（本域唯一可直跑的）；
想**吞一个外部仓库** → `devour_github`（要过门 + 会出网，**先问主人**）；
想**让它反思/跑整轮认知循环** → `devour_reflect` / `devour_pulse`，**这两个一律不要由 AI 自己起**。

**"零作用域" ≠ "只读"**（本域的核心红线，源码实证）：
`policy.authorize()` 的第一句就是 `if not decision.restricted or is_trusted(): return {"ok": True, ...}`
（`security/policy.py:376`）。`devour_reflect` 的 `restricted` 是 `false` ⇒ **门在它面前是开着的**。
而 `api.py:1230-1245` 接着调的 `preflight.before_action()` **只会返回
`not_guarded|reuse|already_running|acquired` 四种状态的一路放行**（`preflight.py:958-995`），
**没有任何一种叫"拒绝"** ⇒ 它去写盘，没人拦。

---

## 1. 什么时候用（意图 → 落点）

| 人想干什么 | 落到哪个位 | 只读还是要授权 |
|---|---|---|
| 看能力缺口在哪、哪些域没人管 | `devour_scan` | 只读，零作用域，**可直跑** |
| 把某个 GitHub 仓库吞成知识胶囊 | `devour_github` | 🔒 `data_export` + `filesystem_write`（**出网**） |
| 回顾吞噬历史、找弱能力与重组机会 | `devour_reflect` | 🔒 **零作用域但会写盘**：不要自己起，要主人明确点头 |
| 跑一整轮"吞噬→反思→消化→重组→进化" | `devour_pulse` | 🔒 `data_export` + `filesystem_write` + `external_llm`（**出网 + 出模型**） |

**不在这 4 个里的事**：
屏幕/点击/读网页 → `gbt-tentacle`（`tentacle` 域）；接 MCP 工具服务器 → 同域外的 `mcp_connect`；
问别的 AI → `gbt-llm` 的 `llm_chat`；云端生图/生视频 → `gbt-arkcli`。
**别把 `devour` 当"所有自我进化相关的事"的垃圾桶** —— 它只这 4 个位。

---

## 2. 怎么调（唯一门 · 真命令）

```powershell
# ── 唯一可直跑的（只读，零作用域）──
py -3.14 tools/codex-scripts/five-dim.py cap devour_scan

# ── 会动手的三个：**只给命令，AI 不替你跑** ──
py -3.14 tools/codex-scripts/five-dim.py cap devour_github '{"repo":"https://github.com/owner/repo"}'
py -3.14 tools/codex-scripts/five-dim.py cap devour_github '{"url":"https://github.com/owner/repo","name":"my_cap"}'
py -3.14 tools/codex-scripts/five-dim.py cap devour_reflect
py -3.14 tools/codex-scripts/five-dim.py cap devour_pulse
```

🔴 **PowerShell 里传 JSON 载荷：用单引号原样包住 JSON**（`'{"repo":"..."}'`）。
写成 `'{\"repo\":\"...\"}'` 会让 `five-dim.py:139` 的 `json.loads` 直接抛
`JSONDecodeError: Expecting property name enclosed in double quotes`
—— **还没碰到授权门就死了**，而且看起来像"命令写错了"。

🔴 **`devour_scan` 的载荷会被整个忽略**：`api.py:710-712` 是
`return get_devourer().scan_gaps()`，**没有从 payload 取任何字段** ⇒ 传什么都不改变读数。
另外三个的载荷契约是 `repo` / `url` / `name`（`api.py:713-725`），**没有 `op` 参数**。

---

## 3. 4 个能力位逐个点（实测读数 + 失败典型）

> `门` 列 = `policy.evaluate(kind, {})` 静态查出来的作用域（§4 有复现命令）；
> `omni` 列 = `omni.py auto_run_verdict()` 会不会自动替你跑（§4 有复现命令）。
> 「实测」= 本规程交付时**真跑过并抄回的真实字段**；标「未验」的一律没跑。

### 3.1 `devour_scan` —— 唯一只读，唯一真跑过的（**实测**）

| 项 | 内容 |
|---|---|
| 用途 | 能力缺口扫描：拿"期望有能力的域清单"对照注册表现有域，报哪些域**一个能力都没有** |
| 只读还是授权 | **只读**，零作用域，`safe: true`，`needs_confirmation: false` |
| 要哪个作用域 | **无**（`scopes []` · `restricted false` · `risk low`） |
| 怎么调 | `py -3.14 tools/codex-scripts/five-dim.py cap devour_scan` |
| 有哪些 op / 参数 | **无参数、无 op**；图鉴 `requires_params: []` · `params_hint: ""`；**payload 被完全忽略** |
| 落点 | **不落盘**。底层是 `devour.py:228` 的 `scan_gaps()`，只读模块常量 `caps_registry.BENIGN_CAPS` 后返回 |
| 实测关键字段 | `status "ok"` · `stamp true` · `denied false` · `result.ok true` · **`gaps` 2 条**（`ledger` · `wallet`，各带 `hint "域 X 无任何能力"`）· **`covered` 29 个域** · **`total_caps 147`**；退出码 **0** |
| 失败典型样子 | 底层只有一条兜底：`except Exception → {"ok": False, "error": str(e)[:200]}`（`devour.py:239-240`）—— **未验**（没造出这个条件；不去改代码凑故障） |

**只读的哈希证据**（不是"我觉得它没写"）：
连跑前后 `gbt_allinone/store/devour_state.json` 的 `sha256` 前 16 位都是 `B957C0E62BDEE3C3`、
`LastWriteTime` 都是 `2026-09-22T22:01:16.5088487+07:00`、
`store/devoured/` 下文件数都是 **98** ⇒ **三项读数全等，它确实没写**。

**🔴 读数陷阱**：`gaps` 报的 `ledger` / `wallet` **不是"框架能力缺失"**，是**故意的空**。
`devour.py:413-430` 的注释写明：`domains_expected` 里还留着 `wallet`/`finance`/`ledger`，
而那三域是**主人 2026-09-12 明确"资金能力注册清零"**掉的，
> 「不能因为一个过期的域清单就把它们自动造回来。见交付报告。」
⇒ 把 `devour_scan` 的 `gaps` 读成"该补 ledger/wallet 了"就是**念反了**：那是**过期清单的残影**。

### 3.2 `devour_github` —— 出网 + 写盘（**未验**）

| 项 | 内容 |
|---|---|
| 用途 | 拉一个 GitHub 仓库的 metadata + README，提炼要点，落成"吞噬知识胶囊" |
| 只读还是授权 | 🔒 **要授权**；图鉴 `needs_confirmation: true` |
| 要哪个作用域 | **`data_export` + `filesystem_write`**（`risk high`）⚠️ **不需要 `external_llm`** —— 它走的是 `urllib` 直连 GitHub API，不经过任何大模型 |
| 怎么调 | `py -3.14 tools/codex-scripts/five-dim.py cap devour_github '{"repo":"https://github.com/owner/repo"}'` |
| 有哪些 op / 参数 | **没有 op**。认 `repo`（也认 `url`）、可选 `name`（胶囊名）；缺 `repo` 抛 `ValueError`（`api.py:718`）。`max_readme_chars` 默认 6000，**不在能力位载荷契约里**（只有直接调模块方法才给得上） |
| 落点 | ① 出网：`https://api.github.com/repos/<owner>/<repo>` + `https://raw.githubusercontent.com/.../README.md`（`devour.py:264-284`）；② 写盘：`store/devoured/<cap_name>/` 下 `absorbed_knowledge.md` `knowledge.json` `run.py`（`devour.py:322-368`）；③ 状态：`store/devour_state.json`（`total_devours` / `total_absorbed` / `scan_learnings` / `known_issues`） |
| 未验 + 为什么不做 | 🔴 **本规程全程没跑它**：① 它**出网**（数据离开本机，`data_export` 就是为这个挂的）；② 它**写盘**（`store/devoured/` + 状态文件）。纪律是"会写的一律不跑" ⇒ **授权后的真实读数，本规程一个字段都没抄到** |
| 失败典型样子（**源码所见，未验**） | ① 缺 `repo`：`ValueError: 缺少 repo：请给出 GitHub 仓库 URL（如 https://github.com/owner/repo）`；② 解析不出：`{"ok": False, "error": "无法解析 GitHub 仓库: <url>"}`；③ 出网失败：`{"ok": False, "error": "GitHub API 404: Not Found", "repo": "..."}`（`urllib.error.HTTPError` 分支）；④ 落盘失败：`{"ok": False, "error": "吸收记录写入失败: ...", "gate": "publish"}` |

**为什么"未验"也要写失败样子**：这三条都是**源码里逐字存在的返回体**（`devour.py:256/259/325/399`），
写出来是为了让人**认得出**它，不是声称我见过它。**认得出 ≠ 验过**。

### 3.3 `devour_reflect` —— **零作用域但会写盘**（本域最危险的一个，**未验**）

| 项 | 内容 |
|---|---|
| 用途 | 反思：遍历 `store/devoured/` 逐胶囊打分（>1 个 action 得 80，否则 40），挑弱能力与重组候选 |
| 只读还是授权 | 🔴 **"零作用域"但会写盘**：`scopes []` · `restricted false` · `risk low` —— **门不会拦它**；图鉴 `needs_confirmation: true`，`omni` 拦它的唯一理由是 preflight 那张"会改状态"表 |
| 要哪个作用域 | **静态查出来是空**（`policy.py` 里根本没有 `devour_reflect` 分支）。⇒ 静态作用域这一栏**不能**当"只读"的证据 |
| 怎么调 | `py -3.14 tools/codex-scripts/five-dim.py cap devour_reflect` |
| 有哪些 op / 参数 | **无参数、无 op**；`requires_params: []`；payload 同样被忽略 |
| 落点 | ① **写盘**：`store/devour_state.json` 的 `reflections`（追加一条 `{at, total_caps, weak, strong}`，只留最近 50 条 —— `devour.py:817-823`）；② **读盘**：`store/devoured/*/knowledge.json` 与 `absorbed_knowledge.md`；③ **潜在出网**：`len(weak_caps) > 15` 时才 `_consult_brain()` → `llm/unified.ask()`（`devour.py:809-814`），**而它的静态作用域里没有 `external_llm`** |
| 未验 + 为什么不做 | 🔴 **没跑**：`preflight._STATE_CHANGING_KINDS`（`preflight.py:57`）把它明列为**会改状态**，`reflect()` 结尾无条件 `self._save_state()` ⇒ **跑了就改 `store/devour_state.json`**。会写的位一律不跑，故**授权后/放行后的真实读数一个字段都没有** |
| 失败典型样子 | ① `CAPS_DIR` 不存在 → **提前 `return {"ok": True, "total_devours": 0, "weak_caps": [], ...}`**（`devour.py:753-755`）—— 🔴 **空结果也报 `ok: true`**，和"真没有弱能力"长得一样；② 单个胶囊 `knowledge.json` 解析失败 → 该胶囊记 `{"score": 0, "error": "parse failed"}`，**整体仍 `ok: true`** |

**🔴 这条是本域的"零作用域 ≠ 只读"标本**：
`restricted == false` ⇒ `policy.authorize()` 在第一句就返回 `{"ok": True}`（`policy.py:376`）
⇒ `api.py:1209` 的拒绝分支**不会进** ⇒ `api.py:1240` 的 `preflight.before_action()`
对它会走 `observe → matched False → acquire 成功 → status "acquired"`（`preflight.py:979-995`）
⇒ **放行、执行、写盘**。**"门会拦住"在这里不成立。**

### 3.4 `devour_pulse` —— 完整认知循环（**未验**）

| 项 | 内容 |
|---|---|
| 用途 | 一整轮自主进化：`quick_devour`（吞）→ `reflect`（反思）→ `digest`（消化）→ `recombine`（重组，最多 3 对）→ `innovate`（创新）→ `knowledge_base.pulse`（自省知识库） |
| 只读还是授权 | 🔒 **要授权**，且**在 preflight 的"会改状态"表里**；三项作用域全高 |
| 要哪个作用域 | **`data_export` + `filesystem_write` + `external_llm`**（`risk high`） |
| 怎么调 | `py -3.14 tools/codex-scripts/five-dim.py cap devour_pulse` |
| 有哪些 op / 参数 | **无参数、无 op**；注册表 `PARAM_REQUIRED` **故意不登记它**（`caps_registry.py:995` 注释：实测它带默认值也能跑完一轮、空调用返回 ok）—— ⚠️ 但"空调用能跑"**不等于"可以空调用去跑"**：它是**真实创建胶囊**的副作用能力（`cross_scan.py:99` 原话） |
| 落点 | ① 写盘：`store/devoured/` 新建胶囊（`innovate` 建 `knowledge.json` + `run.py`）；② 写盘：`store/devour_state.json`（`total_devours`/`total_caps_created`/`innovation_history`/`recombine_history`）；③ **出网+出模型**：`innovate()` **无条件** `_consult_brain()` → `llm/unified.ask()`（`devour.py:1050-1054`）；④ 知识库：`knowledge_base.pulse()` → `store/knowledge/`（`raw` / `techniques.jsonl` / `own_voice.md` / `energy.json` / `index.json` / `rejected.jsonl`，见 `knowledge_base.paths()`） |
| 未验 + 为什么不做 | 🔴 **没跑**：三项作用域（含 `external_llm` 数据出网）+ 会改状态表 + 会真建胶囊。**本规程不绕门、也不拿"反正门会拒"去试一发** —— 会写的一律不跑 |
| 失败典型样子（**源码所记，未验**） | 🔴🔴 **顶层 `ok` 恒为 `true`，失败藏在 `stage_errors` 里**（`devour.py:1225-1235`）。源码里逐字写着那场事故：`quick_devour` 曾因 `'list' object has no attribute 'values'` **整段死掉**，而 `stage_errors` 是 `{}`、`ok` 是 `true` —— **账面全绿，里头是死的**（`devour.py:1211-1216`）。2026-09-22 的修法是：段内自报失败（`ok is False`）也要收进 `stage_errors`，并把 `stages_degraded` 一起给出 |

**顺带一条"落点纪律"**（`knowledge_base.py:62-70`，源码原文）：
吞进来的**外部**知识**不许**进自省知识库 —— `store/devoured/`（别人的）与
`store/knowledge/`（我们自己的）**物理分开**，`FOREIGN_SOURCES` 里明列
`devour` / `devour_github` / `github`；白名单只收 `codex` / `gbt` / `gbt_allinone` / `owner`。
**本机现状**：`store/knowledge/` **尚不存在**（未建）⇒ 这一段在盘上还没有读数。

---

## 4. 要过哪道门：**静态查，不靠跑它才知道**

```python
from gbt_allinone.security import policy
d = policy.evaluate(kind, {})       # 只读求值，不执行
list(d.scopes); d.restricted; d.risk
```

**本域静态查出来的全量**（本规程交付时逐个复算过，四个位一次打印）：

| 位 | `scopes` | `restricted` | `risk` | `preflight.is_side_effect` |
|---|---|---|---|---|
| `devour_scan` | `[]` | `false` | `low` | `false` |
| `devour_github` | `["data_export","filesystem_write"]` | `true` | `high` | `true` |
| `devour_reflect` | `[]` | `false` | `low` | **`true`**（⚠️ 靠 `_STATE_CHANGING_KINDS`，不是靠作用域） |
| `devour_pulse` | `["data_export","filesystem_write","external_llm"]` | `true` | `high` | `true` |

作用域的中文含义（`policy.SCOPE_DESCRIPTIONS` 原文）：

| 作用域 | 覆盖 | 说明原文 |
|---|---|---|
| `data_export` | `devour_github` · `devour_pulse` | "把数据发送到外部服务或持久化到框架外" |
| `filesystem_write` | `devour_github` · `devour_pulse` | "写入、移动、删除或自动整理文件" |
| `external_llm` | `devour_pulse` | "把当前任务数据发送到外部大模型服务" |

**授权只能主人在终端发**：

```powershell
python -m gbt_allinone auth grant --scope data_export --ttl 600
python -m gbt_allinone auth grant --scope filesystem_write --ttl 600
python -m gbt_allinone auth grant --scope external_llm --ttl 600
```

或主人手写 `store/auth_grants.jsonl`。
**AI 永远无权给自己发授权** —— 缺授权就如实报缺，**不找旁路、不改 `security/policy.py`、不改 `auth_gate`**。

**哪些位 `omni` 会替你自动跑**（本域唯一一个）：`devour_scan`
（`omni list --domain devour` 实测：`✅ devour_scan`，其余三个 `🔒`）。
另外三个的理由（`auto_run_verdict()` 实测输出）：
`devour_github` = 需要参数 `repo` + 要人确认 + 要过门；`devour_reflect` = 要人确认 +
**框架自己的 preflight 把它列为会改状态（不是只读）**；`devour_pulse` = 要人确认 + 要过门 + 同上。

> ⚠️ **别在本机 CLI 里拿"未授权"当护栏**：本规程交付时 `policy.is_trusted()` 实测为 **`false`**
> （`five-dim.py` 走的是 `run_task`，**没有** `owner_session()` 包裹），所以三个受限位会被门拒。
> 但 `devour_reflect` **零作用域 ⇒ 门在它面前本来就是开的**，
> 而且一旦被包进 `owner_session()`（`codex_bridge.py:1068/1110/1150/1207/1215` 就是这么用的）
> 或设了 `GBT_OWNER_SESSION=1`，**连 `devour_pulse` 也会直通**。
> ⇒ **"这次没被拒"永远不能当成"它安全"**，判据只有静态表 + 自己的手。

---

## 5. 🔴 读数红线（先问"这是事实，还是我读错了地方"）

1. **"零作用域" ≠ "只读"**（本域最贵的一条）。
   `devour_reflect` 的 `scopes []` / `restricted false` 是真的，**但它会写 `store/devour_state.json`**。
   判据要**两张表一起看**：`policy.evaluate()` 的 `scopes` **加** `preflight._STATE_CHANGING_KINDS`。
   ⇒ 只查作用域就宣布"免卡只读" = **念反读数**。

2. **授权被拒时是"扁平错误信封"，不是常规信封**。
   `missing` / `reason` / `how_to_grant` / `note` 在**顶层**（`api.py:1217-1228`），**没有 `gbt_result`**。
   `five-dim.py:141-162` 的 R-H299 注释就是拿一次事故换的：原来只读 `r["gbt_result"]`
   ⇒ 被拒时 `gr` 为空 ⇒ 打出来是 **`status: unknown · denied: false`——门明明说"拒了"，报表却说"未知、没拒"**。
   ⇒ **读顶层字段**。⚠️ **本域未实测到这一发**：三个受限位一律没跑，
   所以那张拒绝信封**长什么样，本规程只有源码级别的把握，没有运行级别的读数**。

3. **`reason` / `how_to_grant` 只覆盖第一个缺的作用域，`missing` 才是全量**。
   `auth_gate.py:170` 先算出**全量** `missing`（如 `devour_pulse` = 三个），
   但 `error` / `how_to_grant`（`auth_gate.py:200-203`）**只写 `missing[0]`**。
   ⇒ 对 `devour_pulse`，只读 `reason` 只会看到 `data_export`，**漏掉 `filesystem_write` 与 `external_llm`**；
   主人照 `how_to_grant` 只发一条授权，下一次**照样被拒**。**以 `missing`（全量数组）为准。**

4. **`status: "ok"` ≠ 本体 `ok: true`**。
   `five-dim.py` 的 `status` 来自**门/信封**，`result` 里的 `ok` 才可能是业务结论 ——
   两者可以不一致：`devour_github` 落盘失败时返回 `{"ok": False, "error": ...}`，
   而这次调用的门是过的、`status` 是 `ok`；`devour_pulse` 更狠，**顶层 `ok` 恒为 `true`，
   失败全在 `stage_errors`**（`devour.py:1211-1235`）。
   ⚠️ 本域唯一真跑的那发（`devour_scan`）**两者恰好都是 true** ——
   **别把这一发的巧合当通则**：它的 `result.ok` 是同一次打印里独立读出的一条字段，不是从 `status` 推出来的。

5. **退出码不可信**。`five-dim.py:172` 是
   `return 0 if out["status"] in ("ok", "success") else 1` —— **只看门的 `status`，不看 `result.ok`**。
   ⇒ 一次"门过了但本体失败了"的调用会给出 **exit 0**。
   本域实测：`devour_scan`（含 `--full`）`status ok` ⇒ **exit 0**；
   被拒/`user_error` ⇒ exit 1。**别把 exit 1 一律读成"命令敲错了"**，先看 `status` 是 `denied` 还是 `error`。

6. **`stamp: true/false` 是回归印章的有无，不是成功与否**。
   本域实测 `devour_scan`：`stamp true`；`denied` 与 `user_error` 一律 `stamp false`。

7. **图鉴是索引，实测才是读数**。本域这次抓到的漂移：
   图鉴 `invoke` 写的是 `python tools/codex-scripts/five-dim.py …`，
   而本机口径是 `py -3.14 tools/codex-scripts/five-dim.py …`（图鉴只是拼串，不是"真跑过"）。
   ⇒ **图鉴对不上时以实测为准，并把漂移记下来**；能修的当场修回真源，修不了的明写"未修"。
   （本域这条**未修**：修它要动 `omni.py` 的拼串，本次不许动 `omni.py`。）

8. **"能空调用" ≠ "可以空调用"**。`devour_pulse` / `devour_reflect` 的 `requires_params` 都是 `[]`，
   注册表甚至**故意**不把 `devour_pulse` 登记成"需要参数"（`caps_registry.py:994-995` 注释）。
   但它们**无参调用就是完整副作用**（真建胶囊 / 真写状态）—— 探测名单（`cross_scan.PROBE_SKIP_KINDS`，
   2026-09-24 起含 `preflight.state_changing_kinds()` 全量）就是为这个把它们拉进跳过名单的。
   ⇒ **"无参数"这条判据只说明"叫得动"，不说明"叫得安全"。**

---

## 6. 不许做什么（红线）

1. **不许给自己发授权**：不跑 `auth grant`、不手写 `store/auth_grants.jsonl`、
   不改 `security/policy.py` / `auth_gate`。
2. **不许绕门**：不许为了"绕过授权"直接调 `gbt_allinone.devour` 里的模块函数
   （`get_devourer().reflect()` / `devour_pulse()` / `devour_github_repo()`）替掉 `run_task` 唯一门
   —— AGENTS.md 明令：那是**未经授权的写入**，纪律上就是违规。
3. **不许跑会写的那三个**（`devour_github` / `devour_reflect` / `devour_pulse`）：
   尤其 `devour_reflect` —— **它零作用域，门不会替你拦**，跑一次就真改 `store/devour_state.json`。
4. **不许跑 `tools/codex-scripts/probe_gaps.py`**：它第 51 行把 `("devour_reflect", {})` 送进
   `API.run_task` ⇒ **会真的执行 reflect 并写盘**（这个脚本名字叫"探测"，对 devour 却不是零副作用）。
5. **不许把 `devour_scan` 的 `gaps` 读成"该补 ledger/wallet"**：那是主人 2026-09-12
   清零资金能力后**留下的过期清单残影**（`devour.py:424-430` 原话）。
6. **不许把 `devour_pulse` 的顶层 `ok: true` 当"这一轮跑成了"**：
   先看 `stage_errors` 与 `stages_degraded` 空不空。
7. **不许改 `tools/codex-scripts/omni.py`**（`DISTILLED_DOMAINS` 的登记行见 §8，本次未擅自动手）；
   **不许动别的域**、不许改 `policy.py` / `devour.py`。
8. **不许调 `tentacle` 的任何方法**（挂 `desktop_control`，一次性授权，今天已被烧掉两张）：
   本域与触手无关，别把 `devour`（"吞噬触手"这个名字很容易误导）当成触手入口。
9. **不许把本规程当"吞天官方文档"**：命令级细节以当次源码为准，
   本文件管的是**我们这儿的纪律与读数口径**。

---

## 7. 固化与出处（**重启后要在**）

| 什么 | 在哪 |
|---|---|
| 本规程（源） | `<仓>/skills/gbt-devour/SKILL.md` |
| 本规程（装机·托管目录） | `~/.openclaw-autoclaw/skills/gbt-devour/SKILL.md` |
| ⛔ **不许装到** | `~/.agents/skills/`（本仓 AGENTS.md 明令禁止） |
| 能力位名单（4 个） | `<仓>/state/skill_atlas.json`（`domain == "devour"`）· 现扫可重建：`python tools/codex-scripts/omni.py build` |
| 授权判据（**单一真相**） | `<仓>/gbt_allinone/security/policy.py` 的 `evaluate()`（`devour_github` :269 · `devour_pulse` :271；**`devour_scan` / `devour_reflect` 无分支 = 零作用域**） |
| **会不会动手**的判据（第二张表） | `<仓>/gbt_allinone/preflight.py` 的 `_STATE_CHANGING_KINDS`（:47-59，含 `devour_reflect` :57 · `devour_pulse` :58）· `is_side_effect()` :126-176 |
| 门与拒绝信封 | `<仓>/gbt_allinone/api.py` 的 `run_task` :1026 · `_run_task_core` :1149-1228 · `tools/codex-scripts/five-dim.py` :131-172（扁平信封的读法） |
| 授权发放与消耗 | `<仓>/gbt_allinone/auth_gate.py` 的 `check_and_consume_many` :140-206（`reason`/`how_to_grant` 只报 `missing[0]` 在 :200-203） |
| 能力实现 | `<仓>/gbt_allinone/devour.py`（`scan_gaps` :228 · `devour_github_repo` :242 · `reflect` :744 · `digest` :834 · `recombine` :913 · `innovate` :1027 · `devour_pulse` :1157）· 载荷分派在 `<仓>/gbt_allinone/api.py` :709-725 |
| 落点 | `store/devoured/`（吞进来的外部知识）· `store/devour_state.json`（累计账 + reflections）· `store/knowledge/`（自省知识库，由 `knowledge_base.py:42/75-85` 定） |
| 副作用名单（探测要跳过谁） | `<仓>/gbt_allinone/cross_scan.py` 的 `PROBE_SKIP_KINDS` :95-101（含 `devour_github` · `devour_pulse`） |
| 自动执行判据 | `<仓>/tools/codex-scripts/omni.py` 的 `required_scopes()` :149 · `auto_run_verdict()` :188 · `_state_changing_kinds()` :163 |
| 人话落点 | `python tools/codex-scripts/omni.py ask "看看能力缺口"` → 落到 `devour_scan`（`omnipulg` 通道） |

**深蒸登记（应加、本次未擅自动手）**：`omni.py` 的 `DISTILLED_DOMAINS` 加一行

```python
    "devour": "gbt-devour",
```

加完后 `python tools/codex-scripts/omni.py gaps` 里 `devour 4 个能力位` 会从
`⏳ 在队里` 变成 `✅ 已深蒸 → gbt-devour`（本次实测它现在的状态就是 `⏳ 在队里`）。
登记之前，验收走 `--skill` 探针模式（见下）。

**验收（做完怎么证明真的做了）**：

```powershell
# 1. 两份产物逐字节相同 + frontmatter 齐 + 4 个位一个不漏 + 命令没编造
py -3.14 tools/codex-scripts/verify-distill.py --domain devour --skill gbt-devour

# 2. 只读那一位复跑（唯一可直跑的）
py -3.14 tools/codex-scripts/five-dim.py cap devour_scan
#    → status ok · denied false · result.ok true · gaps 2(ledger,wallet) · covered 29 · total_caps 147

# 3. 静态查四个位的作用域（不执行、不消耗授权）
py -3.14 -c "import sys;sys.path.insert(0,'.');from gbt_allinone.security import policy;[print(k, list(policy.evaluate(k,{}).scopes)) for k in ('devour_scan','devour_github','devour_reflect','devour_pulse')]"
#    → devour_scan [] / devour_github ['data_export','filesystem_write'] /
#      devour_reflect [] / devour_pulse ['data_export','filesystem_write','external_llm']

# 4. 声明"某位能用"之前，先问自己：**这条是实测读数，还是我读错了地方？** 拿不准就写"未验"。
```

**本规程的诚实账（一句话）**：
4 个位里**只有 `devour_scan` 真跑过**（含不写盘的哈希证据）；
`devour_github` / `devour_reflect` / `devour_pulse` **一个都没跑**，
它们的所有描述都是**当次源码 + 静态只读求值**读出来的，**逐条标了"未验"**。
