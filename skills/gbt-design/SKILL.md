---
name: gbt-design
displayName: GBT · Design 技能簇用法规程（4 条）
version: 1.0.0
description: GBT小土豆V8 使用 design-* 技能簇的用法规程。以 state/skill_atlas.json 里 name 前缀 design- 的 4 条为准（design-brief / design-consultation / design-md / design-review），逐条点名"什么时候用它"，按意图分成前置规格 / 从零建系统 / 单一真源载体 / 交付前审计四簇；规定两道闸（本簇不吃 API key 但 design-brief 声明了 file_write —— 写盘与覆盖必须先问主人；design-review 的"原子提交"= 改代码库，同样必须先问主人），并如实记下本机现状：4 条里只有 design-brief 有真内容（252 行、两份逐字节相同），另 3 条是 42 行 stub 且上游未 vendored，managed 目录里只有 design-brief 一条。当用户要用设计简报/设计咨询/写 DESIGN.md/交付前设计评审，或任何 design-* 名字的技能路由拿不准、被问"这个技能到底能不能跑"时使用。
triggers:
  - "design-brief"
  - "design-consultation"
  - "design-md"
  - "design-review"
  - "设计简报"
  - "design brief"
  - "ilang brief"
  - "设计咨询"
  - "从零建设计系统"
  - "品牌工作坊"
  - "DESIGN.md"
  - "设计令牌文档"
  - "设计评审"
  - "视觉审计"
  - "上线前设计检查"
---

# GBT · Design 技能簇用法规程

> 开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属
>
> 这是**我们自己的用法规程**（不是 Open Design 文档的复述，也不是那 4 条 stub 的转抄）。
> 那 4 条讲"上游说这条技能大概干什么"，本文件讲
> "**在我们这台机器上，哪条能真照着走、哪条只有一句承诺，以及什么东西绝对不许自动写进项目**"。

---

## 0. 与 `gbt-aesthetic` 的分工（**先读这条，两层不许互相冒充**）

| | 管什么 | 一句话 |
|---|---|---|
| **`gbt-aesthetic`**（审美规程） | **好不好看** | 设计读数 → 三档转盘（`DESIGN_VARIANCE` / `MOTION_INTENSITY` / `VISUAL_DENSITY`）→ 三轴选型（形态×品牌语言×普适手艺）→ AI 味禁令（P0/P1/P2）→ 验收（`audit_aesthetic.py` + `UI-check.md` 五步） |
| **`gbt-design`**（本件） | **这些技能怎么用** | 工具契约、通道与落点、闭词表与默认规则、产出是什么、凭据与写盘两道闸、按意图选哪条 |

🔴 **四条不许越界**：

1. **本件不判好看。** "该用哪个色""该偏 Linear 还是 Awwwards""这算不算 AI 味" —— 全部是 `gbt-aesthetic` §1/§3/§4 的活。
   **本件不做审美判断，也不替它下结论。**
2. **`gbt-aesthetic` 不替你选 design 技能。** 它讲审美判断与重设计协议，
   **不**讲 `design-brief` 的 8 维闭词表怎么填、`design-review` 的修复怎么落盘。
3. **接缝一（规格 → 审美）**：`design-brief` 产出的 **`DESIGN.md`** 正是 `gbt-aesthetic` §2"品牌语言"轴的输入形态。
   顺序是：**本件先把 brief 解析成 `DESIGN.md`（有据的令牌）→ 再让 `gbt-aesthetic` 按它定档位与禁令**。
   **不许跳过 `DESIGN.md` 直接凭感觉开审美。**
4. **接缝二（审计 → 修复）**：`design-review` 那一句只说 *"visual audit then fixes with atomic commits"* ——
   **它没有规定审计标准**。标准在 `gbt-aesthetic` §3/§7。
   ⇒ 分工：**`gbt-aesthetic` 管"用什么标准审、跑哪个检查器"；本件管"审完的修复怎么落盘、要不要先问主人"**。
   🔴 **"原子提交"= 往代码库里写**，这是本件闸二的核心，见 §2。

---

## 1. 🔴 本机现状现读（**这是本件最重要的一节**）

读数时刻：**2026-09-22**，全部为**本次现读**，命令与返回见 §6。

| 项 | 现读值 |
|---|---|
| 权威名单 | `state/skill_atlas.json` 里 `name` 以 **`design-`** 开头的条目 = **4 条**：`design-brief` · `design-consultation` · `design-md` · `design-review` |
| 与域列表的关系 | ⚠️ `py -3.14 tools/codex-scripts/omni.py list --domain design` 现读返回 **23 条**，**与簇不是一回事**（域里混着 `figma-*`、`autoclaw-design-capability`、`frontend-design`、`taste-skill` 等）⇒ **簇只按 name 前缀取** |
| 通道 | ⚠️ **两条通道混装**：`design-brief` = **`agent-skill`**；另 3 条 = **`design-asset`** |
| 落点 | `design-brief` → `C:\Users\ADMIN\.openclaw-autoclaw\skills\design-brief\SKILL.md`（**managed 目录**）<br>另 3 条 → `C:\Users\ADMIN\Desktop\GBT小土豆V8\审美相关skill\skills\<name>\SKILL.md` |
| 形态 | `design-brief` = **252 行真内容**（有工作流：8 维闭词表 → 符号到令牌解析 → 9 段式 `DESIGN.md` → `brief-preview.html` → 报告默认项）；另 3 条 = **42 行 stub**（一句上游描述 + 一个上游链接） |
| 目录内其它文件 | **4 个目录里都只有 `SKILL.md` 一个文件**（没有 `assets/`、`references/`、脚本） |
| 上游 | `design-brief` = Open Design 原生（frontmatter **无** `od.upstream`，`od.mode: design-system`、`platform: desktop`、`scenario: planning`）<br>`design-consultation` / `design-review` = `https://github.com/garrytan/gstack`<br>`design-md` = `https://github.com/google-labs-code/skills` |
| 副本情况 | 🔴 `design-brief` 有**两份逐字节相同**的副本：仓内 `审美相关skill/skills/design-brief/SKILL.md` 与 managed 版，sha256 现算均为 `DDCB70AE1BA4688EE948A3A0F8D3FB7888AD89A49D3E71C2E97661DE7D81AE5B` |
| 声明的能力 | `design-brief` frontmatter 明写 **`capabilities_required: [file_write]`**、**`outputs.primary: DESIGN.md`**、**`outputs.secondary: brief-preview.html`** ⇒ **它是本簇唯一一条声明要写盘的** |
| 凭据 | 本簇 **不吃任何 API key**（没有远端依赖）。为"证明我查过而不是假设"，本次把最可能被误当设计凭据的 7 个变量现读了一遍：`FIGMA_TOKEN` / `FIGMA_API_KEY` / `FIGMA_ACCESS_TOKEN` / `FIGMA_PERSONAL_ACCESS_TOKEN` / `FIGMA_OAUTH_TOKEN` / `MCP_FIGMA_TOKEN` / `OPEN_DESIGN_FIGMA_TOKEN` = **全部未配**（process 与 user 作用域都读过，**只报已配/未配，不打印值**）—— 但它们**对本簇不构成阻塞** |
| 图鉴 desc | ⚠️ **4 条的 `desc` 在图鉴里长度只有 1**（值就是一个 `|`），`triggers` 却抓到了（4–6 个）—— 见 §5 坑 4 |

### ⇒ 硬结论（不许软化）

**本簇里"能真照着走"的只有 `design-brief` 一条；另 3 条是"有名字、有承诺、没有实现"的目录条目。**

- `design-brief`：✅ **有可执行的工作流**（252 行，规定死了闭词表、默认规则、输出结构）。**唯一的前置是 `file_write`。**
- `design-consultation` / `design-md` / `design-review`：⚠️ **各只有一句上游描述 + 一个上游链接**，
  上游**未 vendored**（目录里除 `SKILL.md` 外一个文件都没有）⇒ **它们现在能提供的只有"这件事归它管"这条路由信息**，
  **不提供**任何可跑的命令、脚本、模板。

🔴 **所以：不许把 `design-review` 那一句"visual audit then fixes with atomic commits"说成"本机能跑设计评审并自动修复"。**
它现在**跑不了**；能跑的是 `gbt-aesthetic` §7 的验收（那是另一份规程的活）。

---

## 2. 两道闸（顺序不能颠倒）

### 闸一 · 凭据闸

**本簇不吃 API key** —— 这一点要写清，免得有人去翻凭据库。

**但**：`design-brief` 声明了 **`file_write`**，它要往工作目录写两个文件：
**`DESIGN.md`（主产物）+ `brief-preview.html`（次产物）**。
⇒ **"写盘"就是本簇的凭据等价物**：没有主人对"往哪儿写、写什么"的同意，就没有这一步。

**凭据纪律（硬）**：

1. 🔴 本件全篇**没有任何真实凭据值**；只报**已配 / 未配**或**前 4 位掩码**。
   `sk-a1b2****` 这种掩码写法是**纪律要求**，**不是**任何可用凭据。
2. 🔴 **不许自己去翻凭据**：本簇不需要，所以**任何"为了 design 去读 token 文件"的动作都是多余的，也是不许的**。
3. 本次现读那 7 个 `FIGMA_*` / `OPEN_DESIGN_*` 变量**全部未配**，**但这不影响本簇** ——
   **不许把它报成"设计能力被凭据挡住了"**（那是假的因果）。
4. **缺什么就报缺什么**：本簇会缺的是**`file_write` 的落点（写到哪个目录、覆盖不覆盖）**，不是密钥。

### 闸二 · 写盘 / 改仓库 = 🔴 必须先问主人

**本簇的"写出去"比 `gbt-figma` 那条更近身**，因为它写的是**你自己的项目目录**。

**算"写出去"的动作**：

- **生成 / 覆盖 `DESIGN.md`**（`design-brief` 主产物）—— 🔴 **`design-brief` 原文自己就要求**：
  *"If a DESIGN.md already exists in the working directory, the agent should ask the user whether to overwrite or skip."*
  **这条比我加的规矩更早生效：有旧 `DESIGN.md` 就必须问，不许静默覆盖。**
- **生成 `brief-preview.html`**；以及任何写进项目目录的产物；
- **`design-review` 的"修复 + 原子提交"** —— 🔴 **`atomic commits` 就是往代码库写**：
  会改**别的文件**、会进**版本历史**。**必须先问主人**（在哪分支、提交几条、能不能推）。
- **设计系统从零建出来之后的落盘**（`design-consultation` 的 mockup / 系统文件）；
- **改 / 覆盖任何已存在的设计系统文件**（`design-md` 管的 `DESIGN.md` 载体类文件）。

**顺序（先干什么 → 拿什么回执）**：

1. **摊开四件事**：
   **① 落点**（写到哪个目录、哪个文件名，**绝对路径写清**）·
   **② 内容**（要写的正文，或至少逐字摘要；`DESIGN.md` 要说清 8 维解析成了什么）·
   **③ 覆盖关系**（**已存在吗？覆盖还是跳过？**旧文件要不要先备份）·
   **④ 影响面**（谁会读这份文件 · 进不进版本库 · 会不会盖掉别人手写的令牌）。
2. **先只读**：**"读现有的 `DESIGN.md` / 读现有令牌"不过闸** —— 先读出来给主人看，再谈写。
3. **等一次明确同意**：**只覆盖这一次**，不是"以后这类都同意"。**主人没回话 = 没同意，停。**
4. **同意后动手**，参数用数组传，别让 shell 把主人给的字符串当语法解析。
5. **拿回执**：写盘要**指认到文件**（哪个路径、多少字节、sha256 或覆盖前后的差异）；
   提交要**指认到 commit sha**。**只报"成功了"不算回执。**
6. **失败就记失败**，**不许把失败写成成功**；🔴 **不许静默重试写操作**（可能重复生成、重复提交）。
7. 🔴 **不许自授权**：缺授权、缺主人同意，都**如实报缺哪一项**，
   **不许**改门、**不许**找旁路、**不许**自己去发授权。

---

## 3. 按意图分簇（**4 条一条不漏**）

**选路总则**：本簇靠 **name 前缀 `design-`** 取名单（**不靠 desc** —— 见 §5 坑 4）。
每条下面写的是"**什么时候用它**"，措辞来自该条自己的 `description` / `What it does`（**以上游原文为准，本件只做归位**）。

### 3.1 前置规格（**把模糊话变成明确规格**）

| 技能 | 什么时候用它 |
|---|---|
| **`design-brief`** | 要**把一份设计简报解析成具体设计规格**时；尤其是接到"做得专业一点"这种**模糊委托**、需要把歧义消掉时。它把 brief（I-Lang 结构化格式**或**自然语言）解析成 **8 个正交维度**（`palette` / `accent` / `typography` / `display` / `layout` / `mood` / `density` / `exclude`），再落成 9 段式 **`DESIGN.md`** + 可视预览 `brief-preview.html`，最后**如实报告哪些维度走了默认值、依据哪条规则**。触发词：`design brief` / `create a design brief` / `ilang brief` / `structured brief`。<br>🔴 **本簇唯一有真内容、能照着走的一条**（252 行）。 |

**`design-brief` 的两条硬条款（原文规定，别自己松）**：

1. **闭词表是硬的**：8 维只在它列出的值里取。遇到不认的值（例 `palette=ocean_blue`）
   **必须回问澄清**（原文给的问法："Did you mean `navy_and_white`, `monochrome_dark`, `light_clean`, or `earth_tones`?"），
   🔴 **不许猜、不许自己发明一个令牌表外的 hex**。
2. **默认值必须报账**：没被指定的维度，要按它的默认规则表取值，并在输出末尾**逐条列出"哪个维度走了默认 + 依据哪条规则"**
   ⇒ **不许把默认值当"用户要求的"静默带进设计**。

### 3.2 从零建系统 / 品牌工作坊

| 技能 | 什么时候用它 |
|---|---|
| **`design-consultation`** | 要**从零搭一套完整设计系统**、并且**愿意承担创作风险、要真实的产品 mockup** 时；用在**kickoff 工作坊**、**"品牌从零开始"**这类活。上游：`https://github.com/garrytan/gstack`，分类 `creative-direction`。⚠️ **stub，上游未 vendored** ⇒ 现在只能当路由信息。 |

### 3.3 单一真源载体

| 技能 | 什么时候用它 |
|---|---|
| **`design-md`** | 要**创建与管理 `DESIGN.md` 文件**、把**设计方向 / 令牌 / 视觉规则收进一份单一真源**时。上游：`https://github.com/google-labs-code/skills`（Google Labs / Stitch），分类 `design-systems`。⚠️ **stub，上游未 vendored** ⇒ 现在只能当路由信息。 |

**`design-brief` vs `design-md` 的边界（两条都碰 `DESIGN.md`，最容易混）**：

- **`design-brief`** 管的是**"从一份 brief 把第一版 `DESIGN.md` 生成出来"这条流程** —— **有真内容**（8 维闭词表 + 9 段式结构）。
- **`design-md`** 管的是**"`DESIGN.md` 这个载体的创建与管理"** —— **只有一句描述**，细节在上游。
- **选路**：**要"把 brief 变成规格" → `design-brief`**；**要"这套 `DESIGN.md` 该怎么维护/管" → `design-md`**。
  🔴 **当前真正能照着走的只有 `design-brief`；`design-md` 只用来指路**，**不许把它的那一句扩写成一套"管理规范"**。

### 3.4 交付前审计与修复

| 技能 | 什么时候用它 |
|---|---|
| **`design-review`** | 要在**上线前**做一次**视觉审计**、然后**带着修复**一起交付时；上游定位是 *"Designer Who Codes"* —— **视觉审计 → 修复 → 原子提交 → 前后对比截图**，用于**上线前把已发布的 UI 收紧**。上游：`https://github.com/garrytan/gstack`，分类 `creative-direction`。⚠️ **stub，上游未 vendored**。<br>🔴 **"修复 + 原子提交"要过 §2 闸二**（它会改代码库、进版本历史）。<br>🔴 **审计标准不在这一条里** —— 标准走 `gbt-aesthetic`（§3 AI 味禁令 + §7 验收：`audit_aesthetic.py` + `UI-check.md` 五步）。 |

### 3.5 选路示例（按人话 → 落到哪条）

| 主人说 | 落到 |
|---|---|
| "我就要个专业的落地页，别问了" | `design-brief`（把"专业"解析成 8 维，**并报账默认值**） |
| "这是 I-Lang 简报，照它做" | `design-brief` |
| "帮我从零想一套品牌视觉系统" | `design-consultation`（⚠️ 只有承诺，无实现） |
| "把设计方向/令牌写成一份单一真源" | `design-md`（⚠️ 只有承诺，无实现） |
| "上线前帮我把 UI 审一遍并修掉" | `design-review`（⚠️ stub；**审计标准走 `gbt-aesthetic`**；**修复落盘要先问主人**） |
| "这套东西到底好不好看" | 🔴 **不是本簇** → `gbt-aesthetic` |

---

## 4. 🔴 报告层红线（读数纪律）

1. **不许把"目录里有这条技能"说成"这条技能能用"。** 本簇 **1 条有实现、3 条只有承诺**（§1 已验：4 个目录里都只有 `SKILL.md`）。
2. **不许编命令、编路径、编参数。** 本件里出现的每条命令要么标 **✅ 已验**（本次真跑过，§6），要么明确标 **（未验）**。
   **没跑过的不许说成跑过。**
3. **不许编 `design-brief` 闭词表外的值。** 表外的值（`palette=ocean_blue` 这类）**一律回问**，**不许猜**（原文条款）。
4. **不许报凭据细节。** 只报**已配 / 未配**或**前 4 位掩码**。本件全篇**没有任何真实凭据值**。
5. **不许把"缺 `file_write` 同意"包装成"文件已生成"**；也不许把"没跑"写成"跑过了但没输出"。
6. **有错照原样记**：保留错误码 / 原话 / 退出码。**未配 ≠ 未授权 ≠ 执行失败**，三者不许混着报。
7. **不许把"上游 README 里这么写"当成"本机这么做验证过"。** §3 里 3 条 stub 的措辞**已如实标注来源**。
8. **子方法与能位**：本簇是技能簇（按名字加载执行），**不是**万能插能力位。别为了"走门"去硬套 `five-dim.py cap <名字>`。

---

## 5. 本机踩过的坑（照做，别自己解读）

1. ✅ **任务书假设的 "每条技能都在 `~/.openclaw-autoclaw/skills/<name>/`" 对本簇只对 1/4 成立。**
   现读：managed 目录下 `design-*` 只有 **`design-brief`** 一条；
   `design-consultation` / `design-md` / `design-review` 在
   `C:\Users\ADMIN\Desktop\GBT小土豆V8\审美相关skill\skills\` 下。
   ⇒ **读原文要按 `state/skill_atlas.json` 的 `path` 字段走，别按目录名假设。**

2. ✅ **`design-brief` 有两份逐字节相同的副本，改一份不改另一份就哈希不一致。**
   现读 sha256：仓内与 managed 版**都是** `DDCB70AE1BA4688EE948A3A0F8D3FB7888AD89A49D3E71C2E97661DE7D81AE5B`。
   ⇒ **要改就两份一起改**（本次**两份都没动** —— 本件只管规程，不代管技能本体）。

3. ✅ **`--domain` 列表 ≠ 簇名单。** `omni.py list --domain design` 现读 **23 条**，
   `name` 前缀 `design-` 的只有 **4 条**。⇒ **簇按 name 前缀取**，否则会把 `figma-*`、`taste-skill` 等混进来。

4. ✅ **这 4 条的 `description:` 用了 YAML `|` 块标量，图鉴把它抓成了空。**
   现读：`state/skill_atlas.json` 里 4 条的 `desc` 长度 = **1**（值就是一个 `|`），`triggers` 抓到了（4–6 个）。
   表现是 `omni.py ask` 里这些条目的描述栏**是空的**（例：`design-brief` 在"按 design brief 生成 DESIGN.md"的
   ask 里排第 1，但描述栏空）。
   ⇒ **两条后果**：① **语义路由拿不到本簇的内容线索，主要靠名字与 triggers**；
   ② **本件自己的 frontmatter 必须用单行 `description:`，不许用 `|`** —— 否则新规程也会在图鉴里变成空描述。

5. ✅ **簇的机器验收 `verify-distill.py --cluster <簇>` 现在还判 FAIL，原因不是产物缺，是登记缺。**
   现读：`py -3.14 tools/codex-scripts/verify-distill.py --cluster design` 返回
   `{"cluster":"design","skill":null,"fail":["omni.py 的 DISTILLED_CLUSTERS 里没登记这个簇"],"facts":{"skills_in_atlas":4}}`，
   `verdict: FAIL`，`exit 1`。
   ⇒ **簇登记（`omni.py` 的 `DISTILLED_CLUSTERS`）由主人侧做，本件不许动 `omni.py`。**
   登记之后这个验收才会真正去查"两份同哈希 + frontmatter + **4 条技能名是否都被点到**"。

6. ✅ **`open <url>` 在 Windows 上不存在。** 3 条 stub 的 `How to use` 都写
   `open https://github.com/garrytan/gstack`（或 `google-labs-code/skills`）。
   现读：`Get-Command open` → **不存在**。⇒ **照抄这句会直接 command not found。**
   要打开链接请由主人点；**本件不代跑"打开浏览器"这种带副作用的动作**（未验，也不该硬试）。

7. ✅ **`design-brief` 的 `preview.entry: brief-preview.html` 指的是"它生成出来的"预览文件，不是目录里已有的资产。**
   现读：`design-brief` 目录里**只有 `SKILL.md`**。
   ⇒ **别去目录里找 `brief-preview.html`**；它是 `outputs.secondary`，**属于闸二要问过才写的东西**。

8. ⚠️ **（未验）3 条 stub 装上游 bundle 之后能不能真跑，本件不负责。**
   它们各自只说"把上游 bundle 装进你 agent 的技能目录就能跑完整流程"，**本次没装、没跑、没验**。
   ⇒ **不许把"装了就能用"当结论转述给主人。**

---

## 6. 本次真跑过的命令（证据清单）

| 命令 | 关键返回 | 判定 |
|---|---|---|
| `py -3.14 tools/codex-scripts/omni.py list --domain design` | 能力位 0 条 · agent 技能 **23 条**（含 4 条 `design-*`） | ✅ 抓到坑 3：域 23 ≠ 簇 4 |
| 读 `state/skill_atlas.json`（`name` 前缀 `design-`） | **4 条**：`design-brief`(`agent-skill`) · `design-consultation` · `design-md` · `design-review`（后三条 `design-asset`） | ✅ 名单成立，4 条 |
| 读 `state/skill_atlas.json` 的 `desc` / `triggers` | 4 条 `desc` 长度 = 1 · `triggers` 4–6 个 | ✅ 抓到坑 4 |
| `Get-ChildItem 'C:\Users\ADMIN\.openclaw-autoclaw\skills'`（筛 `design-*`） | 只有 **`design-brief`** | ✅ 抓到坑 1 |
| 逐目录列 `审美相关skill\skills\design-*\` 与 managed `design-brief\` 的文件 | 4 个目录**各只有 `SKILL.md`** | ✅ stub 形态与坑 7 成立 |
| 逐条读 4 份 `SKILL.md` | `design-brief` **252 行**；另 3 条 **42 行**；上游链接已抄 | ✅ §3 措辞有据 |
| `Get-FileHash` 两份 `design-brief/SKILL.md`（SHA256） | 两份**同哈希** `DDCB70AE1BA4688E…` | ✅ 抓到坑 2 |
| `[Environment]::GetEnvironmentVariable` × 7 个名（process + user） | **全部未配** | ✅ 闸一读数 |
| `py -3.14 tools/codex-scripts/omni.py ask "按 design brief 生成 DESIGN.md"` | `design-brief` **排第 1**（评分 15.6），描述栏**空** | ✅ 抓到坑 4 的实际表现 |
| `py -3.14 tools/codex-scripts/verify-distill.py --cluster design` | `skill: null` · `fail: 没登记` · `verdict: FAIL` · `exit 1` | ✅ 抓到坑 5 |

**本次一次都没跑过**：任何 `DESIGN.md` 生成 · 任何 `brief-preview.html` 生成 · 任何设计咨询 · 任何设计评审 ·
任何 `git commit` · 任何上游安装 · `open`。

---

## 7. 固化位置（**重启后要在**）

| 什么 | 在哪 |
|---|---|
| 本规程（源 · 真身） | `<仓>/skills/gbt-design/SKILL.md` |
| 本规程（装机） | `C:\Users\ADMIN\.openclaw-autoclaw\skills\gbt-design\SKILL.md`（**与源稿逐字节相同**，用 sha256 现算对比） |
| 被本件管的 4 条能力 | `design-brief` → `C:\Users\ADMIN\.openclaw-autoclaw\skills\design-brief\SKILL.md`；另 3 条 → `<仓>\审美相关skill\skills\design-*\SKILL.md`（**不由本件代管，别改**） |
| 能力名册（现读） | `state/skill_atlas.json`（`name` 前缀 `design-`）· `py -3.14 tools/codex-scripts/omni.py list --domain design` |
| 人话入口 | `py -3.14 tools/codex-scripts/omni.py ask "<一句话>"` |
| 验收 | `py -3.14 tools/codex-scripts/verify-distill.py --cluster design`（**簇登记由主人侧做**，登记前必 FAIL） |
| 审美那一层 | `skills/gbt-aesthetic/SKILL.md`（**本件不许改它**） |

**纪律**：本规程**不代替**那 4 条技能，也**不代替**上游。本件只加一份规程，
**不动** `tools/codex-scripts/omni.py`、**不动** `security/policy.py`、**不动** `gbt-aesthetic`、
**不动别的簇**、**不调用 `tentacle` 的任何方法**、**不给人给自己发授权**。

---

## 8. 诚实边界（这段不许删）

1. **本件是"用法规程"，不是"能力已具备"。** 它把 4 条技能**分簇、点名、定了两道闸**；
   **1 条有实现**（`design-brief`），**3 条只有承诺**（stub，上游未 vendored）。**本件不替代任何一条。**
2. **本件最重要的判定是一条分层判定**：*"`design-brief` 能照着走；另 3 条现在只能当路由信息。"*
   这条判定的**依据全在 §6 有命令与返回**；**装完上游之后必须重新现读**。
3. **本次实跑的全是只读/枚举/哈希/帮助类动作**（列表、读图鉴、读文件、算哈希、查环境变量、跑一次验收器）。
   **任何 `DESIGN.md` 生成、修复落盘、`git commit`、上游安装，本次都没跑** —— 涉及它们的地方已按 §4.2 标注。
4. **本机状态是 2026-09-22 的现读快照。** 通道、落点、副本哈希都可能变；**别把这份读数当永久事实**。
5. **本件与 `gbt-aesthetic` 的边界是硬的**：本件管"选哪条 design 技能、产出什么、写盘要不要问"，
   `gbt-aesthetic` 管"好不好看、按什么标准审"。**两层都不许替对方下结论。**
