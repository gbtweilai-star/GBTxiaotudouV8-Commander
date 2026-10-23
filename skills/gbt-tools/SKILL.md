---
name: gbt-tools
displayName: GBT · tools 职业域用法规程（6 个能力位）
version: 1.1.0
description: GBT小土豆V8 的 `tools` 职业域（空间投射卡片 / 能力穿透网 / Awesome Tools 蒸馏索引 / **改代码过门入口 / 版本库读面 / 版本库写面**）用法规程。前三位**静态零作用域**（`policy.evaluate()` 逐个实测，含未知 op）、源码层**无写盘原语**（逐文件扫过），实测 18 发调用在审计里只有 `call`+`ok`、**0 条 `auth_consumed`** ⇒ 全程没烧授权。后三位是 2026-09-23 新接的「改代码」那一条链，**门是 fail-closed**：`code_patch` 默认 dry_run 免卡，`apply`/`rollback` 与**未知 op** 一律挂 `filesystem_write`；`git_read` 全部 op 零作用域；`git_write` 全部 op 挂 `filesystem_write`（**不按 op 白名单判**）。逐个点清用途 / 只读还是要授权 / 真命令 / 有哪些 op / 失败典型样子；并记下本机实测到的漂移（`projection_card` 与 `capability_net` 走万能插时 **payload 被 api.py 丢掉**、图鉴里 `awesome_tools_index` 的 desc 被 `omni.py` 截到 300 字符、穿透网那格 `verified(readonly)` 是**写死的 9 口/6 位**而非算出来的 5）与三条读数红线（顶层 `status` 报 ok 且退出码 0 时本体仍可能 `ok false` + `denied true`；未知 op 报的是 `user_error` **不是** `denied`；默认输出被收窄成键清单是**包装器行为**、不是能力位行为）。当用户要读空间投射技能卡、要看能力穿透网七栏读数、要查 Awesome Tools 地图/映射/待归位/等你拍板、要**改代码（dry_run/apply/rollback）**、要读版本库状态与 diff/log、要 **stage/commit 指定路径**，或某个 tools 能力位读数对不上时使用。
triggers:
  - "空间投射"
  - "投射卡片"
  - "ARM"
  - "LIVE"
  - "投影仪"
  - "穿透网"
  - "能力穿透"
  - "七栏"
  - "Awesome Tools"
  - "工具地图"
  - "工具索引"
  - "蒸馏索引"
  - "待归位"
  - "等你拍板"
  - "tools"
  - "改代码"
  - "改前改后"
  - "回滚改动"
  - "版本库"
  - "git 状态"
  - "暂存"
  - "提交指定路径"
---

# GBT · tools 职业域用法规程（6 个能力位）

> 开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属
>
> **这份规程解决什么**：`tools` 域在注册表里 **6 个能力位**（2026-09-23 从 3 位长到 6 位）。
>
> **前 3 位**恰好是"只读"这件事最容易被人拿去吹的三个位：
> ① 一个把 `未核实` **写进值里**的技能卡片（`projection_card`）；
> ② 一个给**全机 177 个能力位**打体检分的穿透网（`capability_net`）；
> ③ 一个号称"地图"的外部工具蒸馏索引（`awesome_tools_index`）。
> 三位**看着都只读**。本规程的第一件事就是**复核这个"看着"**：
> 静态查门（`policy.evaluate`）+ 逐文件读源码 + 真跑 + 审计对账 —— 四条都做过，**结论跟"看着"一致**，
> 但**路径上抓到了四处漂移**，其中两处会让"我读了参数"变成"我其实没读到参数"。
>
> **后 3 位**（§3.5）是"**改代码**"那一条链：`code_patch`（唯一过门入口）·
> `git_read`（只读面）· `git_write`（写面）。它们**不是只读的**，而且门的设计是
> **fail-closed**（非 dry_run 一律要卡，不按 op 白名单判）——
> 这一节是 2026-09-23 补的：**域长了一半而规程没跟，等于这半域没人管**（`verify-distill` 实测判红）。
>
> 跟 `gbt-llm` 一样，**没验过的一律写"未验"，不冒充验过**。

**唯一现读入口（别信任何二手描述，包括本文件）**：

```powershell
py -3.14 tools/codex-scripts/five-dim.py cap projection_card
py -3.14 tools/codex-scripts/five-dim.py cap capability_net
py -3.14 tools/codex-scripts/five-dim.py cap awesome_tools_index '{"op":"..."}'
```

`cap` 一律走 `gbt_allinone.run_task`（**唯一门**）；被门拒绝就**如实报缺什么作用域**，不绕路。
默认输出会被 `five-dim.py` **收窄**（见 §6 红线③）；要全量加 `--full`。

---

## 0. 这 3 个位是三条互不相干的只读通道（先认通道，再看位）

| 通道 | 位（kind） | 共同特征 |
|---|---|---|
| **A · 技能卡片** | `projection_card` | 一张**把"未核实"当字段值**的诚实卡：5/5 原语全标 `未核实`、`verified false`；**只呈现，不执行** |
| **B · 体检读数** | `capability_net` | 全机穿透网**七栏**读数（local 158 + external 19 = 177），外加 4 条带触发条件的挂账 |
| **C · 外部地图** | `awesome_tools_index` | Awesome Tools 蒸馏索引：四原语 INDEX/LOOKUP/MAP/VERIFY + 三条带牙判据 + 五条红线 + 一页「等你拍板」 |

**判据**：
想读**一张技能卡现在什么状态** → A；
想知道**全机能力位到底有几个可真穿透** → B；
想知道**外面有哪些工具、配到哪个能力位、还有多少事等主人拍板** → C。

**这三位都**：
- `domain` = `tools` · `channel` = `omnipulg` · `enabled true` · `safe true` ·
  `requires_params []` · `params_hint ""` · `needs_confirmation false` · `disabled false` · `reason ""`；
- **静态零作用域**（§4 实测表）；
- 都被 `omni.py` 的 `auto_run_verdict()` 判为 **AUTO**（`omni run` 会替你跑），
  —— **但 `omni` 判 AUTO 从不等于"跑了就有你要的结果"**：`projection_card` 与 `capability_net`
  会把你的 payload **静默丢掉**（§5 漂移①②）。

**不在本域的同类事**：屏幕/点击/读网页 → `gbt-tentacle`（`tentacle` 域，本规程一次都没碰）；
Ark 云端生图/账单 → `gbt-arkcli`；审美/出图 → `gbt-aesthetic`。
**本域不替它们干活**，也别把 `tools` 当"所有跟工具有关的事"的垃圾桶 ——
它只有 3 个位，而且**没有一个是用来"跑工具"的**。

---

## 1. 什么时候用（意图 → 落点）

| 人想干什么 | 落到哪个位 | 只读还是要授权 |
|---|---|---|
| 看「空间投射」这个技能现在什么状态、五原语齐不齐 | `projection_card` | **只读，零作用域**（实测不 denied） |
| 看 ARM 准备态 / LIVE 投射态怎么分、红线是哪几条 | `projection_card` | **只读，零作用域** |
| 看全机能力位**索引 / 入口 / 可达 / 已核实 / 有测试 / 可穿透**七栏 | `capability_net` | **只读，零作用域** |
| 看有哪些**挂账**（带复查触发条件的未决项） | `capability_net` | **只读，零作用域** |
| 查 Awesome Tools 的**四原语 / 五条红线 / 分类名 / 六个重点工具** | `awesome_tools_index` | **只读，零作用域** |
| 查「哪个工具配到哪个能力位」（映射） | `awesome_tools_index` 的 `map` / `lookup` | **只读，零作用域** |
| 跑**三条带牙判据**（索引只读 / 映射可追 / 未核实不标绿） | `awesome_tools_index` 的 `gate_readonly` / `gate_map` / `gate_verify` | **只读，零作用域** |
| 看**一页「等你拍板」**（还有多少事卡在主人那） | `awesome_tools_index` 的 `awaiting` | **只读，零作用域** |
| 真要**装工具 / 跑工具 / 拼请求** | ❌ **本域一个都做不到** | 本域明令"只呈现不执行"（§8 红线） |

> **一句判据**：本域三位**没有任何一个会写盘、会出网、会起进程**（§4 是源码级证据）。
> 所以本域**不存在"要授权"的位** —— 这不是"我们没查到"，是**查过四条路都指向同一结论**。

---

## 2. 怎么调（真命令 · 全部本次实跑过）

```powershell
# ── A · 空间投射只读卡片 ──（payload 会被丢掉，见 §5 漂移①）
py -3.14 tools/codex-scripts/five-dim.py cap projection_card
py -3.14 tools/codex-scripts/five-dim.py cap projection_card --full     # 拿全 18 个键

# ── B · 穿透网七栏读数 ──（payload 同样被丢掉，见 §5 漂移②）
py -3.14 tools/codex-scripts/five-dim.py cap capability_net

# ── C · Awesome Tools 蒸馏索引 ──（**这个位的 op 真生效**）
py -3.14 tools/codex-scripts/five-dim.py cap awesome_tools_index                          # status：46 键 · 116165 字符
py -3.14 tools/codex-scripts/five-dim.py cap awesome_tools_index '{"op":"primitives"}'    # 四原语
py -3.14 tools/codex-scripts/five-dim.py cap awesome_tools_index '{"op":"tools"}'         # 六个重点工具
py -3.14 tools/codex-scripts/five-dim.py cap awesome_tools_index '{"op":"map"}'           # 工具 → 能力位 映射
py -3.14 tools/codex-scripts/five-dim.py cap awesome_tools_index '{"op":"redlines"}'      # 五条红线
py -3.14 tools/codex-scripts/five-dim.py cap awesome_tools_index '{"op":"categories"}'    # 17 个分类名
py -3.14 tools/codex-scripts/five-dim.py cap awesome_tools_index '{"op":"evidence"}'      # 2026-09-20 取证读数
py -3.14 tools/codex-scripts/five-dim.py cap awesome_tools_index '{"op":"awaiting"}'      # 一页「等你拍板」
py -3.14 tools/codex-scripts/five-dim.py cap awesome_tools_index '{"op":"index","category":"环境配置"}'
py -3.14 tools/codex-scripts/five-dim.py cap awesome_tools_index '{"op":"lookup","name":"CC Switch"}'
py -3.14 tools/codex-scripts/five-dim.py cap awesome_tools_index '{"op":"gate_readonly","payload":{"category":"环境配置","do":"安装 nvm"}}'
py -3.14 tools/codex-scripts/five-dim.py cap awesome_tools_index '{"op":"gate_map"}'
py -3.14 tools/codex-scripts/five-dim.py cap awesome_tools_index '{"op":"gate_verify"}'
```

🔴 **PowerShell 里传 JSON 载荷：用单引号原样包住 JSON**（`'{"op":"awaiting"}'`）。
写成 `'{\"op\":\"awaiting\"}'` 会让 `five-dim.py:139` 的 `json.loads` 直接抛
`JSONDecodeError: Expecting property name enclosed in double quotes`
—— **还没碰到门就死了**，而且看起来像"命令敲错了"。**这是本机实测踩到的**（同 `gbt-llm` §2）。

---

## 3. 3 个能力位逐个点（实测读数 + 失败典型）

> `门` 列 = 静态查出来的作用域（见 §4）；`omni` 列 = `auto_run_verdict()` 会不会自动替你跑。

### A · `projection_card` — 空间投射只读卡片

| 项 | 值 |
|---|---|
| 用途 | 把「空间投射」这个技能**定义清楚、列出来**，不接任何执行路径 |
| 门 | **无**（零作用域） |
| omni | **AUTO** |
| handler 路径 | `api.py:322-324` → `projection_skill.skill_card()`（🔴 **直调，不看 payload**） |
| 源码 | `gbt_allinone/tools/projection_skill.py`（196 行，全文件读过） |

**实测读数（`cap projection_card`）**：`status ok` · `stamp true` · `denied false` · **exit 0** ·
result **18 键**（不带 `--full` 时被包装器收窄成键清单，原始 2980 字符）：

| 字段 | 实测值 |
|---|---|
| `ok` / `readonly` | `true` / `true` |
| `readonly_note` | 只呈现，不执行：不导入能力层、不调 run_task、无任何写盘原语 |
| `skill` / `name` | `spatial_projection` / `空间投射` |
| `status` / `verified` | **`未核实`** / **`false`** |
| `primitive_count` / `unverified_count` | **5** / **5**（5/5 全未核实） |
| `primitives` | `CAPTURE` 采集 · `MASK` 遮罩 · `MAP` 映射 · `FUSE` 融合 · `OUTPUT` 输出（每条带 `layer` / `upstream` / `downstream` / `status 未核实` / `why_unverified`） |
| `phases` | `ARM` 准备态 `lights_screen false` · `LIVE` 投射态 `lights_screen true` |
| `constraints` | 4 条，第一条就是 `ARM ≠ LIVE：准备态与投射态严格分离（准备态永不点亮）` |
| `closed_loop` | 采集 → 遮罩 → 映射 → 融合 → 输出 → 反馈（摄像头回拍验证 → 回到采集） |
| `gate_analogy` | ARM ≈ 镜像维度 · LIVE ≈ 生产写入 · 操作者按钮 ≈ 授权门 · 一句话：`投影仪不会因为『顺手』就亮了 —— 和 AI 不能自己给自己发授权是同一条纪律。` |
| `reference_projects` | MapMap（`mapmapteam/mapmap`）/ Splash（repo 空）/ ofxPiMapper（repo 空），**三条全 `verified false`**、`provenance owner-claim-20260919` |
| `execution` | `无：本卡片只被读取呈现，不接任何执行路径（与 launcher_inventory 同口径）` |

**失败典型样子**：
- 🔴 **payload 被丢掉**：`cap projection_card '{"op":"status"}'` 与 `cap projection_card '{"op":"card"}'`
  **返回的是同一个东西**（都是 18 键的完整卡），**不是**模块 `run(op="status")` 那个 4 键的形状。
  原因：`api.py:322-324` 直接调 `skill_card()`，**根本不把 payload 传下去**，
  模块里那个 `run(op="status"|"card")` 走万能插**调不到**（见 §5 漂移①）。
- `status` 字段值是**中文字符串 `未核实`**，不是 `ok` —— 那是**卡片自报的技能状态**，
  别跟信封顶层的 `status: "ok"`（= 门过了）混成一个东西。**同一个词在两处是两个意思。**
- **实测没有 denied**：本卡零作用域，门不拦。**但"没被拒"不等于"硬件在"** ——
  `verified false` + `5/5 未核实` 就是它自己的诚实账。

---

### B · `capability_net` — AI 能力穿透网（七栏读数）

| 项 | 值 |
|---|---|
| 用途 | 把索引拆成能力位，给出**七栏**读数（"不是导航，是穿透"） |
| 门 | **无**（零作用域） |
| omni | **AUTO** |
| handler 路径 | `api.py:505-512` → `ai_capability_net.build_net()`（🔴 **直调，不看 payload**） |
| 源码 | `gbt_allinone/tools/ai_capability_net.py`（216 行，全文件读过） |
| 数据源 | `caps_registry`（local **158**）+ `.cluster/dd_squad/toolchain_manifest.json`（external **19**） |

**实测读数（`cap capability_net`）**：`status ok` · `stamp true` · `denied false` · **exit 0** ·
result **5 键**（本身就小，没被收窄）：

| 字段 | 实测值 |
|---|---|
| `ok` / `readonly` | `true` / `true` |
| `seven_columns.indexed` | **`177/177`**（= local 158 + external 19） |
| `seven_columns.entry_known` | **`23/177`**（local 19 + external 4 条带 url） |
| `seven_columns.reachable` | **`19/158`** |
| `seven_columns["verified(reachable)"]` | **`19/158`** |
| `seven_columns["verified(readonly)"]` | **`9 口 / 6 位`** ⚠️ **写死的**（源码 183 行），见 §5 漂移③ |
| `seven_columns.has_test` | **`2/158`**（= `project_context` · `prompt_bridge`） |
| `seven_columns.penetrate_ready` | **`9 口 / 6 位`** ⚠️ 同样**写死**（源码 185 行） |
| `counts` | `total 177` · `local 158` · `external 19` |
| `honest_boundary` | 穿透网只保证『能力位可路由』，不保证『每个能力位都可穿透』；『在索引里』不等于『能穿透』，『能穿透』不等于『已核实能穿透』，『已核实』不等于『已授权』。 |

**`needs_review` 4 条（连触发条件一起给，防死账）**：

| 挂账 | 触发条件 |
|---|---|
| `ghost_guard.main(argv=None)` | 主人显式点名要跑 ghost_guard 时复查 |
| `prompt_bridge.run(op='compile')` | compile 的写盘行为被核实后复查 |
| `transfer.transfer(payload=None)` | 签名被明确改成只读档时复查 |
| `trend_watch(4候选)` | 主人指定用哪个候选时复查 |

**独立复核过数据源**：`.cluster/dd_squad/toolchain_manifest.json` 实测存在（9214 字节），
`groups` = `generation` / `drama` / `publishing`，逐组求和 **正好 19 条** —— 与 `counts.external 19` 对得上。

**失败典型样子**：
- 🔴 **payload 被丢掉**：`cap capability_net '{"op":"net"}'` 返回的**还是 5 键的 status 形状**，
  **拿不到 `nodes` / `local` / `external` 全量**。原因：`api.py:505-512` 直接调 `build_net()`
  再**手工挑 5 个键**返回，模块里那个能出全量的 `run(op="net")` 走万能插**调不到**（见 §5 漂移②）。
  ⇒ **"穿透网能给我每个能力位的明细"这句话，走万能插是做不到的**；要明细得直读模块或走别的路。
- `external_nodes()` 读不到那份 manifest 时**静默返回 `[]`**（源码 `if not p.is_file(): return []`）
  ⇒ `counts.external` 会变成 0、`entry_known` 跟着掉，**但 `status` 还是 ok**。
  看到 `external 0` 别读成"外部工具都没了"，**先去看那份 json 在不在**。
- **实测没有 denied**：零作用域，门不拦。

---

### C · `awesome_tools_index` — Awesome Tools 蒸馏索引（地图）

| 项 | 值 |
|---|---|
| 用途 | 核心命题：**这个仓库不是「代码」，是「地图」** —— 只引用不复制、只映射不照搬；**工具可以换，身份不变** |
| 门 | **无**（零作用域） |
| omni | **AUTO** |
| handler 路径 | `api.py:489-493` → `awesome_tools_index.run(op, **rest)`（✅ **`op` 真生效**，与本域另两位相反） |
| 源码 | `gbt_allinone/tools/awesome_tools_index.py`（**4124 行**；全文件扫过写盘原语，只精读了头部 / `run()` / 出口） |
| desc 原文 | 图鉴里这条是 **300 字符**（`omni.py:299` 的 `[:300]` 截的），末尾断在 `CowAgent→i`；**注册表原文更长**，写全了 `CowAgent→im_multiplex · OpenClaw Monitor→god_view`（§5 漂移④） |

**四原语（实测 `{"op":"primitives"}`，四条 `writes` 全 `false`）**：

| key | 中文 | 干什么 |
|---|---|---|
| `INDEX` | 检索 | 按分类检索工具（只读） |
| `LOOKUP` | 详情 | 看单个工具的形状：它是什么、干什么用（只读） |
| `MAP` | 映射 | **工具 → 能力位** —— 每条都必须带**出处**，无出处不许进映射 |
| `VERIFY` | 核实 | **验证工具是否已安装 / 可接入** —— 未核实不许标 green |

**三条带牙判据（都有真读数，不是口号）**：

| 判据 | 怎么咬人 | 实测样子 |
|---|---|---|
| **索引只读** `index_not_readonly` | 检索里混进写动作 ⇒ 拒 | 见下方「带牙判据实测」 |
| **映射可追** `map_without_source` | 无出处的映射 ⇒ 拒 | `cap ... '{"op":"gate_map"}'`（不给 entries）→ `ok true` · note `未提供映射 ⇒ 本闸不适用（不扩大化）` |
| **未核实不标绿** `unverified_green` | 没核实的标 green ⇒ 拒 | `cap ... '{"op":"gate_verify"}'`（不给 status）→ `ok true` · `status "unverified"` · note `没给状态 ⇒ 一律按 unverified（默认不绿）` |

**五条红线（`{"op":"redlines"}`）**：
索引只读（INDEX/LOOKUP 不许带写动作）· 映射可追（每条必须带出处）· 未核实不标绿 ·
只引用不复制（**不把仓库内容抄进本仓**）· 不绕官方入口（工具要走它**自己的**官方入口，不许替它拼请求）。

**`op` 全表（43 个，源码 `if op ==` 分支现数）**——按用途分四组：

| 组 | op |
|---|---|
| **只读正向读数**（19） | `status` · `primitives` · `categories` · `tools` · `map` · `fragments` · `evidence` · `redlines` · `sections` · `section_rows` · `core_sources` · `pending` · `columns2` · `category_rows` · `source_columns` · `truncated` · `reappearing` · `source_order` · `awaiting` |
| **四原语本体**（2） | `index` · `lookup` |
| **带牙判据**（3） | `gate_readonly` · `gate_map` · `gate_verify` |
| **挂账/合流核对面**（19） | `incoming_distills` · `gate_incoming_distills` · `fusion_cases` · `gate_fusion_cases` · `fusion_sections` · `gate_fusion_sections` · `fusion_primitives` · `gate_fusion_primitives` · `fusion_rows` · `gate_fusion_rows` · `gate_sections` · `gate_section_rows` · `gate_crosscheck` · `gate_pending` · `gate_categories` · `gate_source_columns` · `gate_truncated` · `gate_reappearing` · `gate_source_order` |

🔴 **`op` 清单有第二处真相，而且它对不上**：模块末尾 `raise ValueError` 里那句
`（可用：status/primitives/.../gate_source_order）` **只列了 21 个**（实测数过），
而源码真实分支 **43 个** ⇒ **报错信息里没列的那 22 个照样能用**
（`awaiting` / `sections` / `section_rows` / `core_sources` / `pending` / `columns2` /
`category_rows` / `incoming_distills` / `fusion_*` 一族全在其中）。
**别拿报错里那串当完整清单**，也别因为报错没列就说"这个 op 不存在"。

**实测正向读数**：

| 命令 | 关键返回字段 | 判定 |
|---|---|---|
| `{"op":"lookup","name":"CC Switch"}` | `ok true` · `readonly true` · `primitive LOOKUP` · `tool.maps_to "auto_switch"` · `tool.status "unverified"` · `tool.evidence null` · `evidence_note "盘上 **0 命中**（2026-09-20 取证）"` | ✅ 命中主人明确配对的那条 |
| `{"op":"index","category":"环境配置"}` | `ok true` · `primitive INDEX` · `category "环境配置"` · **`items []`** · `note "仓库内容**未取证** ⇒ 索引池为空且**不编**（空样本不按绿…）"` | ✅ 索引池**就是空的**，且它**如实说空的理由**，不拿假数据凑绿 |
| `{"op":"evidence"}` | `hits` 六个重点工具**全 0**；`skills_dirs["~/.openclaw-autoclaw/skills"].count_seen 73`、`["~/.openclaw/skills"].count_seen 28`；`repo_evidenced false` | ✅ 六个工具**一个都不在盘上** |
| `{"op":"awaiting"}` | `counts`: `pending 10` · `order_mismatched 6` · `repeated 2` · `truncated 12` · `details_unowned 15` · **`total_items_needing_owner 45`** | ✅ 一页「等你拍板」：**45 项卡在主人那**，全只读、不落表 |

**带牙判据实测（🔴 本域最重要的读数坑，原文照抄）**：

```powershell
py -3.14 tools/codex-scripts/five-dim.py cap awesome_tools_index '{"op":"gate_readonly","payload":{"category":"环境配置","do":"安装 nvm"}}'
```
```json
{ "gate": "run_task", "kind": "awesome_tools_index", "status": "ok", "stamp": true, "denied": false,
  "result": { "ok": false, "denied": true, "rule": "index_not_readonly", "hit": "安装",
              "why": "INDEX / LOOKUP 只呈现不执行 —— 带写动作的检索等于把地图当扳手用" } }
```
**顶层 `status` 是 `ok`、`denied` 是 `false`、退出码是 `0`** —— 而**本体是 `ok false` + `denied true`**。
⇒ 判据**真的咬了**，但**只有读 `result` 内部那一层才看得见**（§6 红线②的现场证据）。

```powershell
py -3.14 tools/codex-scripts/five-dim.py cap awesome_tools_index '{"op":"lookup","name":"不存在的工具"}'
```
```json
{ "gate": "run_task", "kind": "awesome_tools_index", "status": "ok", "stamp": true, "denied": false,
  "result": { "ok": false, "denied": true, "rule": "not_in_index", "name": "不存在的工具",
              "why": "不在主人给的重点清单里 ⇒ **不编一个出来**（未取证不引外部）" } }
```
同一个形状：**顶层 ok / exit 0，本体 ok false + denied true**。

**失败典型样子**：
- 🔴 **未知 op 报的是 `user_error`，不是 `denied`**（这条要记牢，因为它**看起来像门拦的**）：
  ```powershell
  py -3.14 tools/codex-scripts/five-dim.py cap awesome_tools_index '{"op":"bogus_op"}'
  ```
  ```json
  { "gate": "run_task", "kind": "awesome_tools_index", "status": "error", "stamp": false, "denied": false,
    "result": { "status": "error", "kind": "awesome_tools_index",
                "message": "未知 op 'bogus_op'（可用：status/primitives/...）",
                "error_class": "user_error" } }
  ```
  **`denied false`**、`error_class user_error`、**exit 1**。
  ⇒ 门**根本没拦**（这个位零作用域、**未知 op 也零作用域**，实测过），
  是**模块自己 fail-closed 抛的 ValueError**。
  **"未知 op 被拒" ≠ "授权门拒了"** —— 别去找 `missing_scopes`，那里没有。
- `lookup` 未命中**不抛错、不返回空**，返回 `ok false` + `denied true` + `rule not_in_index`，
  **但信封顶层还是 ok、退出码还是 0**（见上）。
- `status` 全量 **116165 字符 / 46 键** ⇒ **不带 `--full` 一定被收窄成键清单**
  （`_truncated` 字段会明说原始字符数）。那是**包装器**干的，不是能力位输出小。

---

## 3.5 🔴 2026-09-23 新增的 3 位：改代码与版本库（**这一节是补的，因为规程曾经漏了半域**）

> **为什么要补**：本域从 **3 位长到 6 位** —— 2026-09-23 接进来的 `code_patch` / `git_read` / `git_write`
> 三位，都是"**改代码**"这件事的过门入口。而本规程当时只点到老的 3 位 ⇒
> `verify-distill.py --all` 实测判红：**「规程没点到这 3 个能力位」**。
> 这不是措辞问题：**域长了一半而规程没跟，等于这半域没人管**。

### 通道 D · 改代码的唯一过门入口

| 位 | 是什么 | 只读？ |
|---|---|---|
| `code_patch` | **改代码的唯一过门入口**。三原语 `dry_run`（**默认，只算不写**）/ `apply`（落盘）/ `rollback`（按回执退回） | ❌ `apply`/`rollback` 要 `filesystem_write` |

**九道机械闸**（照注册表原文，不是我的转述）：**仓内**（路径解析后必须在仓内）· **find 恰好一次**
（0 次 `not_found`；>1 次 `ambiguous` —— **绝不替你挑一个**）· **空改动拒写** · `expect_sha256` 对不上拒 ·
**二进制拒改**（前 8KB 有 NUL）· >4MB 拒改 · **逐字节替换**（换行/BOM 一个字节不动）· **原子写**（tmp+os.replace）·
**回执可回滚**（记 find/replace/改前改后哈希；回滚前先核 `after_sha256`，对不上就拒）。

### 通道 E · 版本库读 / 写（**分开登记，别混**）

| 位 | op | 作用域（**静态现查，逐 op**） |
|---|---|---|
| `git_read` | `status` · `diff` · `log` · `show` · `branch_list` · `stash_list` | **全部零作用域**（含未知 op） |
| `git_write` | `stage` · `commit` | **全部 `filesystem_write`**（含未知 op） |

`git_read` **七道闸**：**绝不过 shell**（一律 `shell=False`）· **反选项注入**（rev/path 不许以 `-` 开头）·
路径必须在仓内 · 每条命令带 `--` · 超时 60s + 输出上限 200KB · status 只报数量与前 40 条 · 零作用域。
⚠️ **不做** rebase / reset --hard / push —— 那些是「改历史 / 出网」，要单独设计。

`git_write` **只两个 op，且永远要点名路径**：`stage`＝`git add -- <paths>`；
`commit`＝**pathspec-limited**（`git commit -m … -- <paths>`，**不动索引里别的暂存内容**）。
为什么必须点名：本仓脏行可能上万，`commit -a` 一次就把不相干的全卷进去。

### 🔴 这三位上最该记住的一条：**门是 fail-closed，不按 op 白名单判**

```python
policy.evaluate("code_patch", {})                 # → []                    （默认 dry_run，免卡）
policy.evaluate("code_patch", {"op": "dry_run"})  # → []
policy.evaluate("code_patch", {"op": "apply"})    # → ['filesystem_write']
policy.evaluate("code_patch", {"op": "nope"})     # → ['filesystem_write']  ← **未知 op 也要卡**
policy.evaluate("git_write",  {"op": "nope"})     # → ['filesystem_write']  ← 同上
policy.evaluate("git_read",   {"op": "nope"})     # → []                    ← 只读面，未知 op 也不要卡
```

**别把它读成"零作用域所以只读"**：`code_patch` 空参求值确实是 `[]`，
但那是**默认走 dry_run**；换个 op 就要卡。**门的判据是"非 dry_run"，不是"op 在白名单里"** ——
后者一旦漏写一个新 op 就是白送一次写盘，前者漏不掉。

### 本节实测读数（2026-09-23 真跑，不是转述）

```
five-dim.py cap git_read '{"op":"status"}'                  → ok · 零作用域 · readonly true
                                                              字段 branch_line / dirty_n / dirty_sample / note
five-dim.py cap code_patch                                  → error · empty_find
                                                              "find 不能为空（空白替换只会误伤）"（user_error，不崩）
five-dim.py cap code_patch '{"op":"apply","path":…}'        → **denied** · missing ['filesystem_write']  ✅ 门拦住了
five-dim.py cap git_write  '{"op":"stage","paths":[…]}'     → **denied** · missing ['filesystem_write']  ✅ 门拦住了
```

**本节的"未验"账**：

| 项 | 状态 | 卡在哪 |
|---|---|---|
| `code_patch` **真 apply 一次** | ❌ **未验** | 要 `filesystem_write`，**AI 无权自授**；门拒绝已实测，但"落盘真的逐字节正确"没验过 |
| `code_patch rollback` 真回滚一次 | ❌ **未验** | 同上；且要先有一次成功的 apply 才有回执 |
| `git_read` 的 `diff` / `log` / `show` / `branch_list` / `stash_list` | ⚠️ **只验了 op 门（零作用域），没逐个真跑** | 本次只真跑了 `status` |
| `git_write` commit 的 "不动索引里别的暂存内容" | ❌ **未验** | 要 `filesystem_write`；那是它的**核心承诺**，没验过就不许替它宣传 |

---

## 4. 要过哪道门：**静态查，不靠跑它才知道**

```python
from gbt_allinone.security import policy
d = policy.evaluate(kind, payload)      # 只读求值，不执行、不消耗授权
list(d.scopes)                          # → 这个位要过哪几个作用域
```

**本域静态查出来的全量（2026-09-22 实测，逐个跑过 `policy.evaluate`）**：

| kind | payload 试过 | `scopes` | `risk` | `restricted` |
|---|---|---|---|---|
| `projection_card` | `{}` / `{"op":"card"}` | `[]` | `low` | `False` |
| `capability_net` | `{}` / `{"op":"net"}` | `[]` | `low` | `False` |
| `awesome_tools_index` | `{}` / `status` / `awaiting` / `gate_readonly` / `gate_map` / `index` / `lookup` / **`bogus_op`** | `[]` | `low` | `False` |

⇒ **3 个位全部零作用域**；`tools` **不在** `omni.py` 的 `DANGER_DOMAINS`
（那是 `pipeline`/`dangerous`/`infra`/`integration`）。
⚠️ **注意最后一行**：`awesome_tools_index` 的**未知 op 也是零作用域** ——
⇒ 这个域的"拒"**全部发生在 handler 里**（`raise ValueError` / `ok false`），
**门这一层对未知 op 是 fail-open 的**。这是一条真事实，不是设计缺陷的指控。

**源码级证据（比门更硬）—— 逐文件扫写盘/执行/网络原语**：

| 文件 | `write_text` / `write_bytes` / `mkdir` / `unlink` / `shutil` / `os.remove` / `subprocess` / `urllib` / `requests.` / `Popen` / `os.system` |
|---|---|
| `projection_skill.py` | **0 命中**（无写盘原语） |
| `ai_capability_net.py` | 只有 `subprocess` / `Popen` / `os.system` / `requests.` **各 1 处** —— 🔴 全在 `PROC_PRIMITIVES` 那个**字符串常量元组**里（第 28-29 行，是"自扫描器"的模式表，**不是调用**）⇒ **0 个真调用** |
| `awesome_tools_index.py` | 只 1 处 `open(` —— `open(__file__, encoding=...)`，**读自己**；其余写盘/执行/网络原语 **0 命中** |

⚠️ **这正是"按名字 grep 会误判"的第一个现场**：`ai_capability_net.py` 里躺着
`"subprocess"` `"Popen"` `"os.system"` 这些**字符串**，**任何人 `grep subprocess` 都会以为它起进程** ——
它没有。**"代码里出现了这个词" ≠ "代码调了这件事"**，判据只能是自己打开看它在哪。

**授权只能主人在终端发**（本域**不需要**，写在这里是为了别处不误用）：

```powershell
python -m gbt_allinone auth grant --scope <scope> --ttl 600
```

或主人手写 `store/auth_grants.jsonl`。**授权一次性消耗**。
🔴 **AI 永远无权给自己发授权** —— 缺授权就如实报缺，**不找旁路、不改 `security/policy.py`、不改 `auth_gate`**。

**哪些位 `omni` 会替你自动跑**（`auto_run_verdict()` 实算，**3 个全在 AUTO**）：
`projection_card` · `capability_net` · `awesome_tools_index`
（三条 `required_scopes()` 全空、不在 `preflight._STATE_CHANGING_KINDS`、不在 `DANGER_DOMAINS`、名字不撞写动作正则）。
⇒ **但 AUTO 只说"能替你跑"，不说"跑出来是你要的"**：前两位会把 payload 丢掉（§5 漂移①②）。

**没烧授权的证据（审计对账）**：本次 18 发调用在 `gbt_allinone/store/audit.jsonl` 里
**只有 `call` + `ok`（外加 1 条 `user_error`）**，`auth_consumed` 与 `auth_denied` **各 0 条**。
⇒ **本域全程没消耗任何授权**（零作用域 ⇒ 压根不走 `auth_gate`）。

---

## 5. 本机实测到的漂移（**四处，都在这 3 个位里**）

> 图鉴是**索引**，注册表/源码是**真相**。对不上时**以源码与当次运行为准**，并把漂移记下来。

| # | 漂移 | 证据 | 影响 |
|---|---|---|---|
| ① | **`projection_card` 走万能插时 payload 被丢** | `api.py:322-324` 直调 `projection_skill.skill_card()`，不传 payload | 模块里 `run(op="status"|"card")` 那套**走万能插永久调不到**；传 `{"op":"status"}` 也只会拿到全量卡 |
| ② | **`capability_net` 走万能插时 payload 被丢** | `api.py:505-512` 直调 `build_net()` 并手工挑 5 键返回 | 模块里 `run(op="net")` 能出 `nodes`/`local`/`external` 全量，**走万能插拿不到** |
| ③ | **穿透网 `verified(readonly)` / `penetrate_ready` 两格是写死的** | 源码 183 / 185 行 `"%d 口 / %d 位" % (9, 6)` —— 是**字面量**，不是算的；而同一个文件里 `GREEN6` 只有 **5 个名字**（`brain_vault` / `project_context` / `root_fix` / `selfscan` / `topic_watch`），按它算应是 **5/158** | 读到的 `9 口 / 6 位` **不是本模块算出来的**；另外 `verified(reachable)` 与 `reachable` 实测**同为 `19/158`**（两者用的是同一个 `on_disk` 判据），也别当成两条独立证据 |
| ④ | **图鉴里 `awesome_tools_index` 的 desc 被截到 300 字符** | `omni.py:299` 的 `str(row.get("desc") or "")[:300]`；图鉴实测 **300 字符**、末尾断在 `CowAgent→i`；注册表原文更长 | 图鉴那条 desc **读不全**六个重点工具的映射；要完整的看 `caps_registry.py:930` |

**顺带一条口径更正（不是漂移，是"别搞混"）**：`awesome_tools_index` 的 `raise ValueError` 里
那串"可用 op"**只列 21 个**，源码真实分支 **43 个**（§3 C 已详述）——
**报错清单不是能力清单**。

---

## 6. 🔴 读数红线（先问"这是事实，还是我读错了地方"）

1. **授权被拒时是"扁平错误信封"，不是常规信封**。
   `missing_scopes` / `reason` / `how_to_grant` / `note` 在**顶层**（同时 `result` 里也有一份完整信封），
   **没有 `gbt_result`**。`five-dim.py:141-151` 的 R-H299 注释就是拿一次事故换的：
   原来只读 `r["gbt_result"]` ⇒ 被拒时 `gr` 为空 ⇒ 打出来是
   **`status: unknown · denied: false`——门明明说"拒了"，报表却说"未知、没拒"**。
   ⇒ **读顶层字段**，别只盯 `gbt_result`。
   ⚠️ **本域实测一次 denied 都没出现**（三位零作用域）—— 所以本规程**没资格拿本域当"拒绝信封"的例子**，
   这条只作为**读法**备用。
2. **🔴 顶层 `status: "ok"` ≠ 本体 `ok true`；退出码 0 也不等于成功。本域真踩到了。**
   `lookup` 未命中（`not_in_index`）与 `gate_readonly` 命中写词（`index_not_readonly`）**两发实测**，
   信封顶层都是 `status "ok"` · `denied false` · **exit 0**，
   而 `result` 里是 **`ok false` + `denied true` + `rule` + `why`**。
   ⇒ **判据只能落在 `result` 那一层**；只看顶层会把"判据咬了"读成"一切正常"。
3. **`_truncated` / `_摘要` 是包装器的行为，不是能力位的行为**。
   `five-dim.py:164-170` 在输出 > 1500 字符且没给 `--full` 时，
   把 `result` 换成键清单并加 `_truncated`（带**原始字符数**）。
   ⇒ 看到"只剩键名"**先加 `--full`**，别读成"这个位输出就这么点"。
   （对比：`capability_net` 输出本身就小，**不加 `--full` 也是全的**。）
4. **`stamp: true/false` 是回归印章的有无，不是成功与否**。
   实测：`ok` → `stamp true`；`user_error` → **`stamp false`**。
5. **退出码**：`ok`/`success` → 0；`denied` 与 `user_error` → **1**。
   **别把 exit 1 一律读成"命令敲错了"** —— 先看 `status` 是 `denied` 还是 `error`：
   本域实测的 exit 1 **是 `error` + `user_error`（未知 op），不是 denied**。
6. **"被门拒" ≠ "把授权烧掉了"**。要看花没花，**只认 `auth_consumed` 那一条审计**
   （`gbt_allinone/store/audit.jsonl`）。本域 18 发调用**只有 `call`+`ok`**，
   `auth_consumed` / `auth_denied` **各 0** ⇒ 既没被拒、也没烧。
7. **grep 出来的词不等于调用的行为**：`ai_capability_net.py` 里 `"subprocess"` / `"Popen"` /
   `"os.system"` / `"requests."` **全是 `PROC_PRIMITIVES` 里的字符串模式**（自扫描用），
   **一个都没被调用**。⇒ 判"会写盘 / 会起进程"**只能打开源码看上下文**，不能靠 grep 命中数。
8. **图鉴对不上时，以源码与当次运行为准**。本域实测四处漂移（§5）：
   ①② `api.py` 丢 payload；③ 七栏里两格写死；④ 图鉴 desc 被 `omni.py` 截到 300 字符。
   ⇒ **能修的当场修回真源，修不了的明写"未修"**（本规程只登记，不擅自改 `api.py` / `omni.py`）。

---

## 7. 没验过什么（**诚实账 · 不许把它读成"验过了"**）

| 项 | 状态 | 卡在哪 |
|---|---|---|
| 五原语（CAPTURE/MASK/MAP/FUSE/OUTPUT）**真能不能跑** | ❌ **未验** | 卡片自己 `verified false` —— 需要真采集设备 / 真物理面 / 真投影仪 / 多机融合 / 全绿硬件门禁；**本机一条都没有，也不做出站取证** |
| `reference_projects`（MapMap / Splash / ofxPiMapper）**真是什么样** | ❌ **未验** | 三条 `verified false`、`provenance owner-claim-20260919`；**未联网核实、未上机实测**；Splash 与 ofxPiMapper 连 repo 都是空串 |
| ❌ **LIVE 投射态被点亮会怎样** | ❌ **未验（且本规程永不验）** | 投射是**物理世界的写操作**，光打到墙上撤不回来 ⇒ **本卡片明令"只呈现不执行"，本规程不绕** |
| `capability_net` 的 `verified(readonly)` / `penetrate_ready` **真值** | ❌ **未验** | 那两格是**写死的字面量**（§5 漂移③）；按源码 `GREEN6` 算应是 5 —— 但**"9 口/6 位"从哪来的，源码里查不到**，本规程**不替它编一个来源** |
| 穿透网 `nodes` 全量（每个能力位明细）**走万能插拿不到** | ⚠️ **未验** | `api.py:505-512` 只挑 5 键返回（§5 漂移②）；本规程**不直调模块函数绕门**（§8 红线②），故**没取全量** |
| `awesome_tools_index` 的**外部仓库内容** | ❌ **未验** | `repo_evidenced false`、`repo_note "（出网受限）⇒ 不引内容、不补清单"`；索引池**就是空的**，且它**明说不编** |
| 六个重点工具（CC Switch / MoneyPrinterTurbo / Huobao Drama / LocalMiniDrama / CowAgent / OpenClaw Monitor）**在不在盘上** | ✅ **验过 —— 全 0 命中** | `{"op":"evidence"}` 实测 `hits` 六条全 `0`；⇒ 六条一律 `unverified`（**这是"验过不在"，不是"未验"**） |
| `awaiting` 那 **45 项**到底该怎么处置 | ⚠️ **只验了"有多少、分别是什么"** | `{"op":"awaiting"}` 拿得到明细（pending 10 / order_mismatched 6 / repeated 2 / truncated 12 / details_unowned 15）；**怎么处置只能主人拍板**，模块明说"我不自解、不硬配、不为好看而落表" |
| `awesome_tools_index` 的 19 个 `fusion_*` / `gate_fusion_*` 面 | ⚠️ **未逐个跑** | 本次只跑了 §2 列出的那些 op；`fusion_*` 一族**没跑**（源码分支确认存在，行为**未验**） |

**一句话**：本域**验过的是"只读"这件事本身**（门 + 源码 + 审计三重），
**没验的是"它描述的那些东西真能不能用"** —— 而那恰恰是它自己**标了未核实**的部分。
**两者不许互相冒充。**

---

## 8. 不许做什么（红线）

1. **不许给自己发授权**：不跑 `auth grant`、不手写 `store/auth_grants.jsonl`、
   不改 `security/policy.py` / `auth_gate`。
2. **不许绕门**：不许为了"拿全量"或"绕开 payload 被丢"直接调
   `ai_capability_net.build_net()` / `projection_skill.skill_card()` /
   `awesome_tools_index.run()` 替掉 `run_task` 唯一门
   （AGENTS.md 明令：那是**未经授权的写入**，纪律上就是违规）。
   ⇒ 漂移①②如实写进本文件，**不擅自改 `api.py`**。
3. **不许把 `tools` 域当"跑工具的地方"**：三位**都不装工具、不跑工具、不拼请求**
   （`HONEST_BOUNDARY` 原文 + 源码 0 写盘原语）。
   ⚠️ 特别地：`awesome_tools_index` 的名字里带 `tools`，**但它是一张地图，不是一把扳手** ——
   它自己那三条带牙判据第一条就是为这个立的（`index_not_readonly`）。
4. **不许把 `projection_card` 的 `status` 说成"能跑了"**：它的值是**中文 `未核实`**，
   `verified false`、`5/5 未核实`。**"在"不等于"能用"，"在索引里"不等于"能穿透"。**
5. **不许把 `capability_net` 的 `9 口 / 6 位` 当算出来的读数**（§5 漂移③），
   也不许把 `reachable` 与 `verified(reachable)` 当成两条独立证据（实测同为 `19/158`）。
6. **不许把顶层 `status: "ok"` / 退出码 0 读成"本体成功"**（§6 红线②，本域有真现场）。
7. **不许改 `tools/codex-scripts/omni.py`、`gbt_allinone/api.py`、`security/policy.py`**；
   **不许动别的域**（本域只有 3 个位，改 `api.py` 会波及所有域）。
8. **不许替 `awesome_tools_index` 补内容**：索引池空就是空（"不编"是它的设计），
   45 项等主人拍板就是等 —— **不许为了好看硬配、不许自解**。
9. **不许把本规程当"空间投射 / Awesome Tools 官方文档"**：命令级细节以官方（MapMap 等）为准，
   本文件管的是**我们这儿的纪律与读数口径**。

---

## 9. 固化与出处（**重启后要在**）

| 什么 | 在哪 |
|---|---|
| 本规程（源） | `<仓>/skills/gbt-tools/SKILL.md` |
| 本规程（装机·托管目录） | `~/.openclaw-autoclaw/skills/gbt-tools/SKILL.md` |
| ⛔ **不许装到** | `~/.agents/skills/`（本仓 AGENTS.md 明令禁止） |
| 能力位名单（3 个） | `<仓>/state/skill_atlas.json`（`domain == "tools"`）· 现扫可重建：`python tools/codex-scripts/omni.py build` |
| 注册表原文（**desc 不被截的真相**） | `<仓>/gbt_allinone/caps_registry.py:679`（`projection_card`）· `:703`（`capability_net`）· `:928`（`awesome_tools_index`） |
| 万能插分发（**payload 在哪儿被丢**） | `<仓>/gbt_allinone/api.py:322`（`projection_card`）· `:489`（`awesome_tools_index`）· `:505`（`capability_net`） |
| 能力位实现 | `gbt_allinone/tools/projection_skill.py` · `gbt_allinone/tools/ai_capability_net.py` · `gbt_allinone/tools/awesome_tools_index.py` |
| 授权判据（**单一真相**） | `<仓>/gbt_allinone/security/policy.py` 的 `evaluate()` |
| 门与拒绝信封 | `<仓>/gbt_allinone/run_task`（唯一门）· `tools/codex-scripts/five-dim.py:131-172`（扁平信封的读法 + 收窄逻辑） |
| 自动执行判据 | `<仓>/tools/codex-scripts/omni.py` 的 `required_scopes()` / `auto_run_verdict()`（图鉴 desc 的 `[:300]` 在 `:299`） |
| 穿透网外部数据源 | `<仓>/.cluster/dd_squad/toolchain_manifest.json`（19 条 · groups `generation`/`drama`/`publishing`） |
| 审计（**花没花授权只认这里**） | `<仓>/gbt_allinone/store/audit.jsonl`（`auth_consumed` 才是真花掉） |
| 人话落点 | `python tools/codex-scripts/omni.py ask "看一下穿透网七栏读数"` → 落到 `capability_net`（`omnipulg` 通道） |

**深蒸登记（应加、本次未擅自动手 · 纪律不许改 `omni.py`）**：`omni.py` 的 `DISTILLED_DOMAINS` 加一行

```python
    "tools": "gbt-tools",
```

加完后 `python tools/codex-scripts/omni.py gaps` 里 `tools 3 个能力位` 会从
`⏳ 在队里` 变成 `✅ 已深蒸 → gbt-tools`。
**本次实测 `"tools" in DISTILLED_DOMAINS` == `False` ⇒ 它现在的状态就是 `⏳ 在队里`。**
（验收用 `--skill gbt-tools` 只为本次注入这条映射，**不动源文件**。）

**验收（做完怎么证明真的做了）**：

1. `py -3.14 tools/codex-scripts/verify-distill.py --domain tools --skill gbt-tools`
   → 必须 **PASS**（两份同哈希 + frontmatter 有 `name`/`description` + 3 个位一个不漏 + 无编造命令）；
2. `py -3.14 tools/codex-scripts/five-dim.py cap projection_card --full`
   → 必须拿到 `status "未核实"` · `verified false` · `primitive_count 5` · `unverified_count 5`；
3. `py -3.14 tools/codex-scripts/five-dim.py cap capability_net`
   → 必须拿到七栏 `177/177` · `23/177` · `19/158` · `19/158` · `9 口 / 6 位` · `2/158` · `9 口 / 6 位`
   与 `counts {total 177, local 158, external 19}`（不一致就是某处漂移了，回来改本文件）；
4. `py -3.14 tools/codex-scripts/five-dim.py cap awesome_tools_index '{"op":"lookup","name":"不存在的工具"}'`
   → **顶层必须仍是 `status "ok"` 且退出码 0，而 `result.ok` 必须 `false`、`result.denied` 必须 `true`**
   —— 这发就是 §6 红线②的**活体验收**，跑通说明你读到了该读的那一层；
5. 声明"某位能用"之前，先问自己：**这条是实测读数，还是我读错了地方？** 拿不准就写"未验"。

---

## 工具区 · LobeHub 桌面端（能力位 `lobehub` · 触手 `lobehub` · 主人令 2026-09-27）

主人原话：「把 `C:\Users\ADMIN\Desktop\LobeHub.lnk` 做成**可执行的插件**安装到**工具区**，
这个玩意功能是真的多，**都要跟触手双向绑定**，只要是**可控制的都要绑上**。」

**真身（实测）**：快捷方式 → `%LOCALAPPDATA%\Programs\LobeHub\LobeHub.exe`（Electron **2.2.18**）·
数据 `%APPDATA%\lobehub\`（设置 23 键 · `local-database.sqlite3` 13MB · leveldb · main.log 1.2 万行）·
运行时 `lobehub-storage\heteroAgent\{runs,bindings,inflight}` + `~/.lobehub/traces` ·
本地文件桥 `127.0.0.1:33250` · 云面 gateway。

**七面 76 把可控制键**（每把都在 `state/surfaces/lobehub.json`，**消失即断连**）：

| 面 | 键数 | 怎么控 |
|---|---|---|
| 设置面 | 23 | `settings`（读只回形状；写=白名单 + `filesystem_write` 门 + 先备份） |
| **可控制按键** | 4 | `shortcuts`（快速撰写 `Alt+Shift+Space` · 开设置 `Ctrl+,` …） |
| 接口操作面 | 27 | `ops`（桌面端**真调**的接口：`message:list` `task:*` `agent:*` `userMemory:*` …） |
| 助理面 | 9 | `agents`（界面上的 agent id） |
| 进程/启动面 | — | `status` / `launch` / `close`（**过 `process_execute` 门**） |
| 运行时面 | — | `runtime`（runs/traces/inflight/日志尾） |
| 网络面 | — | `bridge`（只连 127.0.0.1，端口取自应用自己的日志） |

**三条硬口径**（照 ComfyUI 那套，不另立门）：
1. **凭据只回形状，按键名掩码** —— 血账：掩码按**值**判过一次，`encryptedTokens` 的 DPAPI 密文
   被原样打出来；判据 `test_lobehub_surface` **D** 现在拿真实密文比对，出现就红。
2. **在跑的库只读副本**（拷到临时目录再读），绝不 `mode=rw` 打开在跑的 13MB 库。
3. **出网钉死**：模块里只有一个出口且主机写死 127.0.0.1；非法端口/相对路径一律拒（判据 G）。

**如实报的限制（不是坏，是别指望它）**：
- **非 ASCII 路径走不了这条桥**：我们的仓库路径带中文，原始请求在应用侧 `URIError: URI malformed`，
  百分号编码后也拿不到（`log_evidence` 里记着应用自己日志的行数）；
- **服务商 38 家 / 图像模型（GPT Image 2.5 · Nano Banana · Seedream 5 Pro · Qwen Image 3 …）
  在云账号里**，本地改不了 ⇒ 标"不可本地控"，不假装能控；
- 桥**无鉴权**（本机环回）：越界文件被拒（`/C:/Windows/win.ini` → 404），但它是开着的面。

**血账（顺手修掉的老账）**：`surface_bind` 的**委托分支**（comfyui/blender/lobehub）**提前 return**，
清单写了却**从没绑上触手** —— "接上了没绑上"。现在三个分支都显式 `_bind_manifest(...)` 并按工具署名。
