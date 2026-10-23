---
name: gbt-project
displayName: GBT · 项目职业域用法规程（2 个能力位）
version: 1.0.0
description: GBT小土豆V8 的 `project` 职业域（项目结构测绘 / 项目上下文·蓝图简报·只读检索）用法规程。把图鉴里这 2 个能力位逐个点清：用途、只读还是要授权、怎么调、要什么参数、产出什么字段、缓存与时效、失败长什么样；规定本域唯一入口是万能插 `five-dim.py cap <能力位>`、两位**静态作用域都是空的**（不需要授权，且**源码层逐位确认没有写口**）、授权只能主人在终端发；并记下本机实测过的读数陷阱（🔴 `platform_profile` 带 **30 秒 TTL 缓存**，读数里**没有任何 cached/ts/ttl 字段** ⇒ **缓存期内的读数不等于当前事实**，且该缓存是**进程内**的：两次独立 `cap` 各自都是冷的；`platform_profile` **完全忽略 payload**，连 `{"ttl":0}` 都传不进去；两位读的**不是同一个根** —— 一个读 `Desktop\Workspace`，一个读本仓；`project_context` 的**未知 op 是「信封 ok + 本体 error + 退出码 0」**，而**缺 query / 蓝图不存在是「信封 error + 退出码 1」**，同一能力位两副失败面孔；`five-dim.py` 默认把 result 收窄成键清单，要全量必须加 `--full`）。当用户说「读一下项目结构 / 这个量化项目长什么样 / 项目蓝图在哪 / 给我个项目简报 / 在项目文档里检索某个问题 / 项目上下文」，或某个 project 能力位读数对不上、怀疑拿着旧读数、或 `project_context` 报「未知操作」时使用。
triggers:
  - "项目结构"
  - "项目画像"
  - "量化项目"
  - "Workspace"
  - "platform_profile"
  - "project_context"
  - "项目上下文"
  - "项目蓝图"
  - "PROJECT_BLUEPRINT"
  - "简报"
  - "只读检索"
  - "未知操作"
  - "project"
---

# GBT · 项目职业域用法规程（2 个能力位）

> 开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属
>
> **这份规程解决什么**：`project` 域是全图鉴**最小的一域**（只有 2 个能力位），
> 但它有**两个特别容易读错的地方**：
> ① **读数的时效是假的**：`platform_profile` 带 30 秒 TTL 缓存，而它的返回里
> **一个 `cached` / `ts` / `ttl` 字段都没有** —— 你**看不出**手里这条是刚测的还是缓存里的
> （本规程实测：冷调 227.9ms → TTL 内 3.6ms → 跨过 30s 又回 98.8ms）。
> ② **两个位读的不是同一个根**：`platform_profile` 读的是**另一个目录**
> `C:\Users\ADMIN\Desktop\Workspace`（量化项目），`project_context` 读的是**本仓**
> —— 名字都像"项目"，读的东西却完全不搭界，混着用就会拿一个的读数去解释另一个。
> 本文件把「哪个位、什么时候用、要不要授权、要什么参数、产出什么字段、缓存与时效、
> 失败长什么样」逐个钉死，并把**本机实测过的坑**如实记下来 —— **没验过的一律写"未验"，不冒充验过**。

**唯一现读入口（别信任何二手描述，包括本文件）**：

```powershell
py -3.14 tools/codex-scripts/five-dim.py cap <能力位> ['<JSON载荷>'] [--full]
```

`cap` 一律走 `gbt_allinone.run_task`（**唯一门**）；被门拒绝就**如实报缺什么作用域**，不绕路。
本域 2 位**静态作用域全空**（见 §4），所以在本域里**不会**碰到授权门。

---

## 0. 这 2 个位分两簇（先认簇，再看位）

| 簇 | 位（kind） | 共 | 读的是哪个根 | 共同特征 |
|---|---|---|---|---|
| **A · 外部项目结构测绘** | `platform_profile` | 1 | `C:\Users\ADMIN\Desktop\Workspace`（**写死在源码里**） | 目录遍历计数；**带 30s TTL 缓存**；**忽略 payload** |
| **B · 本仓上下文只读层** | `project_context` | 1 | **本仓根**（`gbt_allinone` 的上一级，可被 `GBT_PROJECT_ROOT` 覆盖） | 四个 op；**收 payload**；**无缓存**（每次真读盘） |

**判据**：想**看量化项目长什么样 / 有多少 .py** → A；
想**读本仓的蓝图、简报、或在项目文档里检索** → B。
**两位的根不同，读数不可互相顶替。**

⚠️ **本域与 `gbt-finance` 域有交叠**（`platform_profile` 也被 finance 侧用到）：
分工见 §6，**别两边互相冒充**。

---

## 1. 什么时候用（意图 → 落点）

| 人想干什么 | 落到哪个位 | 只读还是要授权 |
|---|---|---|
| 看量化项目（Workspace）在不在、顶层有哪些目录 | `platform_profile` | 只读，零作用域（**但读数可能是 30s 内的缓存**） |
| 数一下量化项目有多少 `.py`、`01_量化收割引擎` 里多少 | `platform_profile` | 只读，零作用域 |
| 想知道剪枝排掉了多少外部语料 | `platform_profile` 的 `py_excluded` | 只读，零作用域（⚠️ 本机是 `{}`，见 §5 红线⑤） |
| 拿本仓蓝图的权威正文与指纹 | `project_context`（`op=blueprint`） | 只读，零作用域 |
| 新开/续接一个回合，先要一份紧凑的项目定向 | `project_context`（**空参默认** = `brief`） | 只读，零作用域 |
| 「这个项目里 X 是怎么做的」，在**已批准文档**里检索 | `project_context`（`op=search` + `query`） | 只读，零作用域 |
| 看本仓上下文的索引范围（多少篇、写作/执行面开没开） | `project_context`（`op=status`） | 只读，零作用域 |
| 看某件事该落哪个能力位 | `omni.py ask "<人话>"` | 只读（只给候选与命令，不动手） |

**不在这 2 个里的事**：量化引擎/回测/参数的**内容**解析 → `gbt-finance`（`quant_strategy` /
`quant_backtest` / `quant_params` / `quant`）；记忆库本身 → `gbt-brain-vault`；
屏幕/点击/读网页 → `gbt-tentacle`。**本域不替它们干活**。

---

## 2. 怎么调（万能插唯一门）

```powershell
# ── A · 外部项目结构测绘（payload 被忽略，写了也白写）──
py -3.14 tools/codex-scripts/five-dim.py cap platform_profile

# ── B · 本仓上下文只读层（默认 op=brief）──
py -3.14 tools/codex-scripts/five-dim.py cap project_context                                  # = op=brief
py -3.14 tools/codex-scripts/five-dim.py cap project_context '{"op":"status"}'
py -3.14 tools/codex-scripts/five-dim.py cap project_context '{"op":"blueprint"}'             # 正文极大，默认会被收窄
py -3.14 tools/codex-scripts/five-dim.py cap project_context '{"op":"blueprint"}' --full      # 要正文全量
py -3.14 tools/codex-scripts/five-dim.py cap project_context '{"op":"search","query":"深蒸 规程","limit":3}'

# ── 覆盖本仓根（只读实验：指到一个不存在的地方，用来验"缺失"分支）──
$env:GBT_PROJECT_ROOT="C:\Users\ADMIN\Desktop\__gbt_root_does_not_exist__"
py -3.14 tools/codex-scripts/five-dim.py cap project_context '{"op":"status"}'                # document_count 0 · blueprint missing
Remove-Item Env:\GBT_PROJECT_ROOT
```

🔴 **PowerShell 里传 JSON 载荷：用单引号原样包住 JSON**（`'{"op":"status"}'`）。
写成 `'{\"op\":\"status\"}'` 会让 `five-dim.py:139` 的 `json.loads` 直接抛
`JSONDecodeError: Expecting property name enclosed in double quotes`
—— **还没碰到门就死了**，而且看起来像"命令写错了"。（本坑在 `gbt-llm` / `gbt-mind` 都实测过，
本域未重复踩；依据是 `five-dim.py:139` 源码。）

🔴 **默认输出会收窄，不是坏了**：`five-dim.py:164-170` 的 `LIMIT = 1500`。
本域实测 `cap project_context`（brief）原始 **3728 字符**、`op=status` 原始 **13449 字符**
—— 默认都被换成 `_摘要 + keys + key_count`，并附 `_truncated.原始字符数`。
**要真字段就加 `--full`**（实测 `op=status --full` → **15900 字节**，`documents` 全在）。

---

## 3. 2 个能力位逐个点（实测读数 + 失败典型）

> 下表 `门` = 静态查出来的作用域（见 §4）；`omni` = `omni.py auto_run_verdict()` 本次实算。
> 全部读数时间：**2026-09-22**，本机。

### A · 外部项目结构测绘

| 项 | 内容 |
|---|---|
| **用途** | 读取 `C:\Users\ADMIN\Desktop\Workspace`（**外部量化项目**）的真实结构：顶层目录清单 + 仓内 `.py` 计数 + 量化子目录 `.py` 计数 + 被剪掉的语料量化 |
| **门** | **零作用域**（`policy.evaluate` → `scopes []`、`restricted False`）⇒ 不需要授权 |
| **参数** | 图鉴 `requires_params []`；**实测：payload 被完全忽略**（`api.py:111` 是 `return handler()`，无参调用；实测 `cap platform_profile '{"ttl":0,"bogus":1}'` 与空参**结果相同**）⇒ 想传 `ttl` 只能直接调模块函数，**门内不可达** |
| **`omni`** | **AUTO**（`auto_run_verdict()` → `(True, [])`） |
| **真命令** | `py -3.14 tools/codex-scripts/five-dim.py cap platform_profile` |
| **产出字段（本机实测全量）** | `workspace "C:\\Users\\ADMIN\\Desktop\\Workspace"` · `exists true` · `top_level_dirs` **15 条**（`.gbt_bridge_staging` `.playwright-cli` `.tripo` `.wrangler` `00_镜像独有文件提取_20260913` `01_量化收割引擎` `02_GBT兑换与主平台` `03_收款钱包与支付` `04_平台构建与验收脚本(开发产物)` `05_资金管道设计_2026-09-09` `__pycache__` `deploy_bundle_v1` `output` `pet-run-gbt` `work`）· `quant_py` **23** · `py_total` **167** · `py_excluded` **`{}`** |
| **缓存与时效** | 🔴 **30 秒 TTL，进程内**。本机实测（同一进程内连调三次）：冷调 **227.9 ms** → TTL 内 **3.6 ms**（≈63×）→ 等 **31 s** 过 TTL 后 **98.8 ms**。两次 result **字节级完全相同**。**返回里没有 `cached`/`ts`/`ttl` 字段** ⇒ 读者无法区分"刚发生"与"缓存里的"。另实测：两个**独立** `five-dim.py cap` 进程（327.6 ms / 358.6 ms）输出**逐字节相同**（sha256 `3B41BF15…`）⇒ **缓存不跨进程**，`cap` 每次都是冷调，**只有同一进程内的高频调用（autopilot / 巡检）才吃缓存** |
| **只读性（源码所见）** | `quant_tech.py:108-136`：只 `WS.exists()` / `iterdir()` / `scan_scope.iter_files()` 计数 —— **无写口、不执行命令、不读 `.env`/密钥**（模块文档 line 3 明说）。实测篡改返回的 dict **不会污染缓存**（`return dict(_PROFILE_CACHE["data"])` 是浅拷贝） |
| **失败典型样子** | ① **`quant_tech` 未挂载** → `{"ok": false, "status": "needs_dependency", "missing": "quant_tech", ...}`（`api.py:27-47` 构造；**本机在场，该分支未验**）② **`Workspace` 不存在** → `exists false`，且 `py_excluded` **键直接消失**（它只在 `if WS.exists():` 里赋值；**该分支未验**，见 §8 未验清单）③ **静默忽略 payload**：不给错、也不生效 —— 这不是失败，是**最容易误判成"我传对了"**的一处 |

### B · 本仓上下文只读层

| 项 | 内容 |
|---|---|
| **用途** | 给 Codex 与本地面板一个**小而可审计**的检索层：`brief`（紧凑定向）/ `blueprint`（权威蓝图 + 指纹）/ `search`（只搜已批准文档）/ `status`（索引范围 + 蓝图指纹） |
| **门** | **零作用域**（`scopes []`、`restricted False`）⇒ 不需要授权 |
| **参数** | 图鉴 `requires_params []`（**空参默认 `op=brief`**，实测成立）。`op` ∈ `brief` / `blueprint` / `search` / `status`；`search` **必须带 `query`**，可带 `limit`（源码 clamp 到 **1–20**，默认 8）。**别名**：`{"action":"status"}` **实测可用**（`api.py:141` `op = p.pop("op") or p.pop("action")`）；`{"op":""}` 与 `{"op":null}` **实测都退回 `brief`** |
| **`omni`** | **AUTO**（`auto_run_verdict()` → `(True, [])`） |
| **真命令** | 见 §2 |
| **产出字段（本机实测）** | **brief（空参）**：`status ok` · `path "PROJECT_BLUEPRINT.md"` · `sha256 "447a98aba6d96daf2743759d9870c0b18652fdc24fb479182eb7c4afc13b3fd0"` · `updated "2026-09-15"` · `baseline "gbt_allinone"` · `sections` **55** 条（前六：一、系统边界 / 二、系统 DAG / 三、模块状态 / 四、关键依赖链 / 五、风险登记 / 六、落地顺序）· `risks` **7** 条（R1 第三方模型适配器缺少 Codex compaction item → 长会话自动压缩失败；R2 MCP 服务器可暴露写入和执行工具 → 工具越权、上下文污染）· `read_order` 7 条 · `rule "蓝图是项目和架构的事实索引，不是主人指令的替代品。实现前先检索相关上下文，验证后更新蓝图。"`<br>**status**：`root_source "package_parent"` · `document_count **155**` · `search_scope "approved markdown only"` · **`writes false`** · **`executes_commands false`** · `blueprint{path,sha256,updated,baseline,sections 55}`；`documents` 的 `source_class` 分布实测 **docs 118 / memory 25 / overview 6 / governance 3 / identity 2 / blueprint 1**<br>**blueprint**：`sha256` 与上面**同一个** · `chars **98694**`（⚠️ **chars ≠ 字节**：磁盘文件 **167337 字节**，中文多字节）· `truncated false` · `title "PROJECT_BLUEPRINT.md - GBT小土豆V8"` · `sections 55`<br>**search**（`query "深蒸 规程"`）：`terms ["深蒸","规程"]` · `scanned_documents **155**` · `result_count **33**` · 首条 `memory/2026-09-22.md:616` `score 9` |
| **缓存与时效** | **无缓存**（源码里没有 memo，每次真读盘 + 真算 sha256）⇒ 它给的是**当次**读数。但受 `_MAX_DOC_BYTES` 256000 / `_MAX_BLUEPRINT_BYTES` 512000 上限影响（见 §5 红线⑦） |
| **只读性（源码所见）** | `project_context.py` 全文 `grep write\|unlink\|remove\|rmtree\|mkdir\|rename\|subprocess\|os.system\|open(` **只命中两处**：line 10 的文档字符串、line 259 的字面量 `"writes": False` ⇒ **没有任何写口**。`status` 自己报 `writes false` / `executes_commands false`，**与源码一致**（本域是少数"自报属实"的位） |
| **指纹可交叉印证（实测）** | `blueprint.sha256` = `447a98ab…`，与 `Get-FileHash PROJECT_BLUEPRINT.md -Algorithm SHA256` 的磁盘哈希**一字不差**；`chars 98694` 与 `167337 字节` 并存 ⇒ **别把 `chars` 当字节数** |
| **失败典型样子** | 见 §5 红线②③：**同一能力位两副面孔**——① **未知 op** → 信封 `status "ok"` + `stamp true` + **exit 0**，本体 `{"status":"error","message":"未知 project_context 操作: nope"}`（**没有 `error_class`、没有 `ok` 键**）；**根因**：`run()` 末尾那支是 **`return` 一个错误 dict，不是 `raise`**，所以门认为"成功"② **缺 `query`** → 信封 `status "error"` + `stamp false` + `error_class user_error` + **exit 1**（`search()` 里 **`raise ValueError`**）③ **蓝图不存在**（如 `GBT_PROJECT_ROOT` 指错）→ 信封 `status "error"` + `stamp false` + **exit 1**，`message "文档不存在: PROJECT_BLUEPRINT.md"`；而**同条件下的 `op=status` 照样 `status ok` + exit 0**（它把蓝图缺失降级成 `blueprint {"status":"missing"}`，**不报错**） |

---

## 4. 要过哪道门：**静态查，不靠跑它才知道**

```python
from gbt_allinone.security import policy
d = policy.evaluate(kind, {})          # 只读求值，不执行、不消耗授权
list(d.scopes)                          # → 这个位要过哪几个作用域
```

**本域静态查出来的全量（2026-09-22 实测，两位逐个查）**：

| 位 | `scopes` | `restricted` | `reason` |
|---|---|---|---|
| `platform_profile` | `[]` | `False` | `''` |
| `project_context` | `[]` | `False` | `''` |

`policy.py` 里**根本没提这两个 kind**（`grep platform_profile\|project_context\|quant_tech` → **无匹配**）
—— 它们是"没被登记成受限"的位，不是"登记了但免卡"的位。

🔴 **本域最重要的一句话（与 `gbt-mind` 那条正好相反）**：
`gbt-mind` 里"不要授权 ≠ 只读"（它有 4 个真写口却零作用域）；
**本域两位之所以敢说"真只读"，判据不是"零作用域"，而是逐位读了源码**：
- `platform_profile` → 只 `exists/iterdir/计数`；
- `project_context` → 全文件无任何写口（见 §3 B 行）。
⇒ **"门没拦"从来不是"没写口"的证据；本域是查了源码才敢下这个结论的。**

**那授权怎么发（本域用不上，但口径要留）**：只能主人在终端发

```powershell
python -m gbt_allinone auth grant --scope <作用域> --ttl 600
```

或主人手写 `store/auth_grants.jsonl`。**AI 永远无权给自己发授权** —— 缺授权就如实报缺，
**不找旁路、不改 `security/policy.py`、不改 `auth_gate`**。

**哪些位 `omni` 会替你自动跑**（`auto_run_verdict()` 本次实算）：**两位都是 AUTO**
（`platform_profile` → `(True, [])`；`project_context` → `(True, [])`）。
理由：注册表标 `safe`、无必填参数、不在 `DANGER_DOMAINS`（那是 `pipeline`/`dangerous`/`infra`/`integration`）、
名字不撞 `DANGEROUS_NAME_RE`、零作用域、也不在 `preflight._STATE_CHANGING_KINDS`。

⚠️ **"在 AUTO 名单里"只表示"无参调用不会死在门上"**：
`project_context` 的 `search` / `blueprint` 都要**点名 op / 给 query 才动**；
`omni ask "读一下量化项目结构"` 实测给出
`[8.5] platform_profile … ✅ 只读无参，可直跑`（**只打印命令，不动手**）。

---

## 5. 🔴 报告层红线（先问"这是事实，还是我读错了地方"）

1. **被拒时是"扁平错误信封"，不是常规信封**。
   授权被拒时，`missing_scopes` / `reason` / `how_to_grant` / `note` 在**顶层**，
   **没有 `gbt_result`**。`five-dim.py:141-146`（R-H299 注释）就是拿一次事故换的：
   原来只读 `r["gbt_result"]` ⇒ 被拒时 `gr` 为空 ⇒ 打出来是
   **`status: unknown · denied: false`——门明明说"拒了"，报表却说"未知、没拒"**。
   ⇒ **读顶层字段**，别只盯 `gbt_result`。
   ⚠️ **本域内的诚实说明**：本域 2 位作用域全空 ⇒ **本次没有一条"被门拒绝"的真读数**；
   上面这条是**报告层纪律**（依据 `five-dim.py` 注释 + `gbt-llm` 域实测），**不是本域实测出来的**。
2. **信封 `status:"ok"` ≠ 本体 `ok:true`**（本域实测抓到，**最值钱的一条**）：
   `{"op":"nope"}` 打给 `project_context` → 顶层 `status "ok"` · `stamp true` · `denied false`，
   而本体是 `{"status":"error","message":"未知 project_context 操作: nope"}`
   —— **连 `ok` 键都没有**。
   ⇒ **永远看本体**；顶层 `status` 只说明"门放行了"。
   **根因值得记住**：只有 `run()` 末尾那支是 `return` 错误 dict（门看不到异常），
   其余失败路径都是 `raise`（门才拦得住）。**"能力位是 raise 还是 return"决定了你看到哪副面孔。**
3. **退出码不可信**（同一次实测，同一能力位两种退出码）：
   上面那条未知 op 的 `user_error` **退出码是 0**；
   缺 `query` 的 `user_error` **退出码是 1**；`GBT_PROJECT_ROOT` 指错时的蓝图缺失也是 **1**。
   两者**都是"错的活的"** —— 退出码既不能当"成功"也不能当"失败"，
   **只能当"命令跑起来了没有"**。判定一律回到本体字段（`status` / `ok` / `error_class` / `denied`）。
4. 🔴 **缓存期内的读数不等于当前事实**（本域最特有的红线，见 §3 A 行实测）：
   `platform_profile` 有 **30 秒 TTL 缓存**（`quant_tech.py:105/114-115/134-135`），
   而**返回里没有任何缓存标记字段** ⇒
   **你无法从读数本身判断它是"刚测绘的"还是"30 秒内别人调过留下的"**。
   两条用法：
   - 报数时**不许说"现在就是 15 个目录 / 167 个 .py"**，只能说
     **"最近 30 秒内的一次测绘结果是…"**；要"当前事实"，用别的口径独立复核
     （例如直接列目录），并说明**那是另一次读数**；
   - **缓存是进程内的**：`five-dim.py cap` 每次新进程 ⇒ **每次都冷调**；
     真正吃缓存的是**同进程里高频调它的 autopilot / 巡检**。所以
     **"我连跑两次都是冷调"不能证明"别人拿到的也是实时值"**。
5. **`py_excluded {}` ≠ "剪枝没生效"**。它是"**被排除的那三块语料，在本根下不存在**"
   （`scan_scope.EXTERNAL_CORPORA` = `vendor` / `_upstream` / `.shadow-repo`，
   `platform_profile` 只保留 `exists=True` 的项；本机三个都 `exists False` ⇒ 结果 `{}`）。
   要看"到底排了什么、排了多少"，得看 `scan_scope.corpus_sizes(WS)` 的**原始四字段**
   （本机实测：三项均 `{"exists": false, "py_files": 0, "bytes": 0}`）。
   ⇒ **空字典在这里是"没得排"，不是"没排"。**
6. **`chars` 不是字节数**：`blueprint.chars 98694` 对 `167337 字节` 的文件。
   拿 `chars` 去和 `Get-Item .Length` 比会得到"文件被截了"的**假结论**。
7. **上限是静默降级，不是报错**：`_MAX_BLUEPRINT_BYTES 512000` · `_MAX_DOC_BYTES 256000`
   · `_MAX_SEARCH_LIMIT 20` · `_SNIPPET_CHARS 220` · `redact_text()` 会给片段脱敏。
   ⇒ 极长的行会被截断、命中会被限制到 20 条、片段里的敏感串会被抹掉，
   **这些都不报错**（蓝图那条会置 `truncated: true`，**本机未触发**）。
8. **两位的根不同，别串**：`platform_profile` 的 `workspace` 是
   `C:\Users\ADMIN\Desktop\Workspace`（**外部量化项目**，写死在 `quant_tech.py:7`）；
   `project_context` 的根是 **本仓**（`package_parent` = `gbt_allinone` 的上一级，
   可被 `GBT_PROJECT_ROOT` 覆盖，实测 `root_source` 会跟着变）。
   **一个报的是"别人的项目"，一个报的是"我们这个仓"。**
9. **自报也要验，但本域这次是"验过属实"**：`project_context.status` 自报
   `writes false` / `executes_commands false` —— 本规程**独立 grep 过全文**，
   写口命中数为 **0**，**自报与源码一致**。
   （对照 `gbt-mind` 域有两处"自报 ≠ 源码"的反例 ⇒ **自报要逐条验，不能整体信也不能整体不信**。）

---

## 6. 与 `gbt-finance` 的分工（**别互相冒充**）

`platform_profile` **属于 project 域**，但 `gbt-finance` 的 `quant` 总入口**也调它**
（`api.py:918-923`：`{"profile": module.platform_profile(), "engine_params": …}`）。
两边会撞在一起，所以分工要钉死：

| 谁 | 管什么 | 不管什么 |
|---|---|---|
| **`gbt-finance`** | `quant` / `quant_strategy` / `quant_backtest` / `quant_params` 四位：量化**引擎、回测、参数、策略模型**的读法；它顺带也提到 `platform_profile` 与那条 30s 缓存（口径一致，**不冲突**） | ❌ **不把 `platform_profile` 当独立能力位逐个点字段**（没列 `top_level_dirs` / `py_total` / `py_excluded` 的实测值） |
| **`gbt-project`**（本件） | `platform_profile` **作为 project 域能力位**怎么调：真命令、payload 被忽略、**六个产出字段的实测值**、**30s TTL 的实测曲线**、`py_excluded {}` 的正确读法；外加 `project_context` 全部四个 op | ❌ **不解析量化引擎/回测/参数内容** —— 那些去读 `gbt-finance` |

**一句话**：**`gbt-finance` 管"量化引擎里有什么"，`gbt-project` 管"用哪条命令测绘项目结构 / 读本仓上下文，返回的字段与时效怎么读"。**

⚠️ **一处已知漂移（如实记）**：`gbt-finance/SKILL.md` 的出处表把真身实现记成
`platform_profile:81`，而**现源码是 `quant_tech.py:108`** —— 该文件在 2026-09-22 被补注释与
修剪枝（见 `quant_tech.py:38-45` / `121-126`）后**行号整体下移**。
**本件以现源码为准**；`gbt-finance` 那行由它的负责人改，**本件不越界去改别人的规程**。

**本件不碰的**：不改 `gbt-finance/SKILL.md`、不改 `security/policy.py`、不改
`tools/codex-scripts/omni.py`、不改验收器、不动别的域。

---

## 7. 不许做什么（红线）

1. **不许给自己发授权**：不跑 `auth grant`、不手写 `store/auth_grants.jsonl`、不改 `security/policy.py` / `auth_gate`。
2. **不许绕门**：不许为了"省一步"直接调 `gbt_allinone.quant_tech.platform_profile()` /
   `project_context.run()` 替掉 `run_task` 唯一门（AGENTS.md 明令：那是违规路径）。
   ⚠️ 本域两位**都不需要授权**，所以**在本域根本没有"绕门"的借口** —— 更要守纪律。
   （本规程里两处"直接只读调用"是**实验性观测**且已标注：`scan_scope.corpus_sizes` 的
   `is` 同一性、以及 `Get-FileHash` 交叉印证 —— 都**不写盘、不替代能力位读数**。）
3. **不许把 `platform_profile` 的读数说成"当前事实"**：它是 30s TTL 内的读数，
   **且读数本身看不出缓存**（§5 红线④）。要"现在"，**另起一次独立复核并说明那是另一次读数**。
4. **不许把 `platform_profile` 的 payload 当生效参数**：它**被完全忽略**（实测）。
   写了 `{"ttl":0}` 得到的结果与空参**一模一样** —— 别以为"我把缓存关了"。
5. **不许把"信封 ok"说成"做成了"**：`{"op":"nope"}` 就是 `status:"ok"` + 本体 error（§5 红线②）。
6. **不许把退出码当判据**：同一个 `project_context`，未知 op **exit 0**、缺 query **exit 1**（§5 红线③）。
7. **不许拿 `platform_profile` 的读数去描述本仓**（也不许反过来）：
   一个根是 `Desktop\Workspace`，一个是本仓（§5 红线⑧）。
8. **不许为了"验 `exists:false` 分支"去改名/移动 `C:\Users\ADMIN\Desktop\Workspace`** ——
   那是**动别人的真实项目目录**。该分支**未验就是未验**，写在未验清单里，不许伪造。
9. **不许用 `cap <子方法名>` 的写法引子方法**（那会让验收器判成"编出来的能力位"）；
   子方法一律写成 `{"op":"…"}` payload。
10. **不许改 `tools/codex-scripts/omni.py`**（本域登记行由交付报告给出，不擅自动手）；
    **不许动别的域**、不许改 `policy.py`、不许改验收器。

---

## 8. 固化与出处（**重启后要在**）

| 什么 | 在哪 |
|---|---|
| 本规程（源） | `<仓>/skills/gbt-project/SKILL.md` |
| 本规程（装机·托管目录） | `~/.openclaw-autoclaw/skills/gbt-project/SKILL.md` |
| ⛔ **不许装到** | `~/.agents/skills/`（本仓 AGENTS.md 明令禁止） |
| 能力位名单（2 个） | `<仓>/state/skill_atlas.json`（`domain == "project"`）· 现扫可重建：`python tools/codex-scripts/omni.py build` |
| 授权判据（**单一真相**） | `<仓>/gbt_allinone/security/policy.py` 的 `evaluate()`（**本域两位未登记其中**） |
| 门与拒绝信封 | `<仓>/gbt_allinone/run_task`（唯一门）· `tools/codex-scripts/five-dim.py:131-172`（扁平信封读法 + **1500 字默认收窄** + `--full`） |
| 自动执行判据 | `<仓>/tools/codex-scripts/omni.py` 的 `required_scopes()` / `auto_run_verdict()` / `_state_changing_kinds()` |
| 本域源码 | `gbt_allinone/quant_tech.py:105-136`（`_PROFILE_CACHE` + `platform_profile`）· `gbt_allinone/project_context.py`（全文 286 行） |
| 分派入口 | `<仓>/gbt_allinone/api.py`：`_run_benign` 的 `101-111`（platform_profile，经 `_external_capability`）、`138-144`（project_context，`op`/`action` 别名在这里）· 另有 `918-923`（`quant` 总入口也调 `platform_profile`） |
| 剪枝口径 | `<仓>/gbt_allinone/tools/scan_scope.py`（`EXTERNAL_CORPORA` / `SKIP_DIRS` / `iter_files` / `corpus_sizes`） |
| 注册表条目 | `<仓>/gbt_allinone/caps_registry.py:101-107`（`platform_profile`）· `project_context` 未登记在 caps_registry（由 `api.py:138` 分支兜住） |
| 人话落点 | `python tools/codex-scripts/omni.py ask "读一下量化项目结构"` → `[8.5] platform_profile`（**实测原文**）· `… ask "项目蓝图和简报在哪"` → `[5.5] project_context`（**实测原文**） |

**未验清单（如实记，别读成"验过了"）**：

| 哪一刀 | 为什么未验 |
|---|---|
| `platform_profile` 的 **`exists:false`** 分支（`py_excluded` 键会消失） | 触发它必须让 `C:\Users\ADMIN\Desktop\Workspace` 消失/改名 —— 那是**动别人的真实项目目录**，本规程不干；**源码所见**（`py_excluded` 只在 `if WS.exists():` 内赋值） |
| `platform_profile` 的 **`needs_dependency`** 缺口信封 | `quant_tech` 在本仓**在场** ⇒ 该分支不可达；本规程贴的是 `api.py:27-47` 的**源码构造**，不是实测打印 |
| **被门拒绝的扁平信封** | 本域 2 位作用域全空 ⇒ **本域内没有一条真拒绝读数**（§5 红线① 的诚实说明） |
| `project_context` 的 **`truncated:true`** | 蓝图 **167337 字节** < `_MAX_BLUEPRINT_BYTES` **512000** ⇒ 未触发 |
| `search` 命中 **`_MAX_DOC_BYTES` 256000** 截断 | 未构造超长文档 |
| `search` 的 **`_inside_root` 越界拒绝**（"文档路径超出项目根目录"） | 四个 op **都不收路径参数** ⇒ 该守卫在本能力位下**不可达**（源码所见） |
| `platform_profile` 的 **`ttl` 入参** | 只有直接调模块函数才传得进去；走 `cap` 时 payload 被丢（**实测**）⇒ **门内不可达** |
| 两位的**多进程并发下缓存行为** | 未构造并发实验；只验了"单进程命中 / 跨进程不共享 / 31s 过期" |

**深蒸登记（应加、本次未擅自动手）**：`omni.py` 的 `DISTILLED_DOMAINS` 加一行

```python
    "project": "gbt-project",
```

现在 `python tools/codex-scripts/omni.py gaps` 里它仍是 **`⏳ 在队里  project  2 个能力位  platform_profile、project_context`**（本次实测原文）。
加完后会变成 `✅ 已深蒸 → gbt-project`。

**验收（做完怎么证明真的做了）**：

1. `py -3.14 tools/codex-scripts/verify-distill.py --domain project --skill gbt-project` → **必须 PASS**
   （它查：两份逐字节相同 · frontmatter 有 name/description · 规程点名的 `cap` 都是图鉴真位 ·
   本域 2 位一个不漏）；
2. `py -3.14 tools/codex-scripts/five-dim.py cap platform_profile` → 拿 `top_level_dirs` / `quant_py` / `py_total`；
3. `py -3.14 tools/codex-scripts/five-dim.py cap project_context` → 拿 `sha256` / `sections` / `risks`；
4. `py -3.14 tools/codex-scripts/five-dim.py cap project_context '{"op":"status"}' --full` → 拿 `document_count` / `writes` / `executes_commands`；
5. 声明"两位能用"之前先问自己：**这是实测读数，还是我读错了地方？**
   拿不准就写"未验" —— 本域已有"缓存期读数看不出缓存"这条硬坑（§5 红线④）。

> 开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属
