---
name: gbt-figma
displayName: GBT · Figma 技能簇用法规程（7 条）
version: 1.0.0
description: GBT小土豆V8 使用 figma-* 技能簇的用法规程。以 state/skill_atlas.json 里 name 前缀 figma- 的 7 条为准，逐条点名"什么时候用它"，按意图分成底座/起手/生成/落地/固化五簇；规定两道闸（Figma 凭据闸只报已配未配或前 4 位掩码、改 Figma 远端动作必须先问主人），并如实记下本机现状：7 条全是 design-asset 通道的 41-42 行 stub、上游未 vendored、managed 目录 0 条、Figma 凭据全未配、mcporter 里没有 figma MCP、figma CLI 不在 PATH —— 所以本簇在本机当前不可执行，只能做意图路由与纪律。当用户要用 Figma 取稿/建组件/导出资源/建设计系统库/Code Connect/设计转代码，或 figma-use 与"到底能不能跑"的问题出现时使用。
triggers:
  - "figma"
  - "Figma"
  - "figma-use"
  - "figma 脚本"
  - "figma plugin api"
  - "设计稿"
  - "design to code"
  - "figma to code"
  - "code connect"
  - "figma library"
  - "design system library"
  - "figjam"
  - "figma tokens"
  - "figma 生成设计"
---

# GBT · Figma 技能簇用法规程

> 开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属
>
> 这是**我们自己的用法规程**（不是 Figma 官方文档的复述，更不是那 7 条 stub 的转抄）。
> 那 7 条 stub 讲"上游说这条技能大概干什么"，本文件讲
> "**在我们这台机器上，谁在什么条件下、按什么顺序用它，哪些东西本机根本跑不了，
> 以及什么动作绝对不许自动写到 Figma 上去**"。

---

## 0. 与 `gbt-aesthetic` 的分工（**先读这条，两层不许互相冒充**）

| | 管什么 | 一句话 |
|---|---|---|
| **`gbt-aesthetic`**（审美规程） | **好不好看** | 设计读数 → 三档转盘（`DESIGN_VARIANCE` / `MOTION_INTENSITY` / `VISUAL_DENSITY`）→ 三轴选型（形态×品牌语言×普适手艺）→ AI 味禁令 → 验收 |
| **`gbt-figma`**（本件） | **这些技能怎么用** | 工具契约、通道与落点、命令形态、凭据闸、远端写入闸、按意图选哪条、产出是什么 |

🔴 **三条不许越界**：

1. **本件不判好看。** 本件不会告诉你"这个 frame 该不该用紫渐变""间距该不该 96px" —— 那是 `gbt-aesthetic` §1/§3/§4 的活。
2. **`gbt-aesthetic` 不告诉你 Figma 怎么连。** 它讲审美判断与重设计协议，**不**讲 Figma token 怎么配、Code Connect 怎么推、哪条 figma 技能该先跑。
3. **接缝只有一处**：本件负责把稿子**取回来 / 还回去**（工具与闸），`gbt-aesthetic` 负责稿子**长什么样**（审美）。
   真正干活时顺序是：**先用本件过工具闸取到素材 → 再用 `gbt-aesthetic` 定档位与禁令 → 最后再回本件过写入闸还回 Figma**。
   **反过来（先定审美再想怎么连）会在没凭据时白做一轮。**

---

## 1. 🔴 本机现状现读（**这是本件最重要的一节，先看它再决定要不要往下读**）

读数时刻：**2026-09-22**，全部为**本次现读**，命令与返回见 §6。

| 项 | 现读值 |
|---|---|
| 权威名单 | `state/skill_atlas.json` 里 `name` 以 **`figma-`** 开头的条目 = **7 条** |
| 与域列表的关系 | `py -3.14 tools/codex-scripts/omni.py list --domain figma` 也报 **7 条**（域与簇**这次恰好一致**，但别把域当簇的通例 —— 见 §5 坑 2） |
| 通道 | **7 条全部是 `design-asset`** —— ⚠️ **不是** `agent-skill` |
| 落点 | `C:\Users\ADMIN\Desktop\GBT小土豆V8\审美相关skill\skills\<name>\SKILL.md`（7 个目录，**每个目录里只有 SKILL.md 一个文件**：没有 `assets/`、没有 `references/`、没有脚本） |
| managed 目录 | `C:\Users\ADMIN\.openclaw-autoclaw\skills\figma-*` = **0 条**（现读：该目录下 `figma-*` 文件夹数为 0） |
| 形态 | 全部是 **41–42 行 stub**：frontmatter + `What it does` + `Source` + `How to use`，正文只有一句上游描述 + 一个上游链接 |
| 上游 | 7 条**全部**指向 `https://github.com/figma/skills`（**未 vendored**，仓里没有上游的脚本与 reference） |
| Figma 凭据 | `FIGMA_TOKEN` · `FIGMA_API_KEY` · `FIGMA_ACCESS_TOKEN` · `FIGMA_PERSONAL_ACCESS_TOKEN` · `FIGMA_OAUTH_TOKEN` = **全部未配**（process 与 user 两个作用域都读过，**只报已配/未配，不打印值**） |
| Figma MCP | `config/mcporter.json` 里**没有** figma server。现有 5 个是 `autoclaw-productivity` · `autoclaw-github` · `notion` · `connector:cloudflare` · `connector:vercel` |
| Figma CLI | `figma` · `figma-cli` · `figma-connect` · `code-connect` **都不在 PATH** |
| Figma 桌面版 | `%LOCALAPPDATA%\Figma` · `%APPDATA%\Figma` · `~/.figma` **三个都不存在** |
| 运行时 | `node` = `C:\Program Files\nodejs\node.exe`、`npx` = `...\npx.ps1` **存在**（只说明将来若装官方 MCP 有运行时，**不等于现在能连**） |
| 图鉴 desc | ⚠️ 7 条的 `desc` 在图鉴里长度只有 **1**（值就是一个 `|`）—— 见 §5 坑 4 |

### ⇒ 硬结论（不许软化）

**本簇在本机当前不可执行，只能做意图路由与纪律。**

理由四条，全部已验：**① 没有凭据**（5 个 token 变量全未配）· **② 没有执行通道**（mcporter 无 figma MCP、CLI 不在 PATH、桌面版未装）·
**③ 上游未 vendored**（7 条各只有一个上游链接，没有可跑的脚本/资产）· **④ 那 7 个目录里除 `SKILL.md` 外一个文件都没有**。

**所以**：本件的价值是"**告诉你这件事该归哪条管、以及它现在为什么跑不动**"，
**不是**一本"照着敲就能跑"的命令手册。**任何声称本机现在能跑 Figma 动作的话，都是编的。**

---

## 2. 两道闸（顺序不能颠倒）

### 闸一 · Figma 凭据闸

**Figma 的远端读写只有两条正路**：① Personal Access Token / OAuth（走 Figma REST 或 Plugin API）；
② 官方 MCP server（OAuth）。**本机两条都没有**（见 §1）。

**凭据纪律（硬，与 `gbt-lark` §2 同源）**：

1. 🔴 **只报「已配 / 未配」，或前 4 位掩码**（例 `figd****`）。**绝不打印、绝不落盘、绝不贴进聊天/日报/MEMORY/本规程。**
2. 🔴 **不许自己去翻凭据**：不许读 `~/.figma`、不许读任何 MCP/CLI 的 config 或 token 缓存去"找"一个 token。
   本机那三个路径本次已确认**不存在**（§1），**也不该存在由本件去读的东西**。要配凭据 = **主人的动作**。
3. **要给主人配的时候，只给变量名与位置，不给示例值**：`FIGMA_TOKEN` / `FIGMA_API_KEY` / `FIGMA_ACCESS_TOKEN` /
   `FIGMA_PERSONAL_ACCESS_TOKEN` / `FIGMA_OAUTH_TOKEN`（本件不规定他必须用哪个名字 —— 这五个是**本次现读的候选名**，
   不是本仓的既定契约；**名字由主人的接入方式决定**）。
4. **缺凭据就如实报"取不到"**，然后**停下**。🔴 **不许**用别的手段"绕"出一个稿子来（读缓存、读截图当稿子、
   凭印象编 frame 名字），**更不许**把"没连上"写成"连上了但文件是空的"。

**检查动作（本次真跑过，可复用）**：

```powershell
# 只读：逐名看"已配/未配"，不打印值 —— ✅ 已验
foreach($v in @('FIGMA_TOKEN','FIGMA_API_KEY','FIGMA_ACCESS_TOKEN','FIGMA_PERSONAL_ACCESS_TOKEN','FIGMA_OAUTH_TOKEN')){
  if([Environment]::GetEnvironmentVariable($v,'Process')){"$v = 已配"}else{"$v = 未配"}
}
```

**本次现读结果**：**5 个全部「未配」**（process 与 user 作用域一致）。

### 闸二 · 改 Figma 远端 = 🔴 必须先问主人

**"改 Figma 远端"包括但不限于**（对照 §3 那 7 条）：

- 在 Figma 文件里**建 / 改 / 删节点、改属性、改 Figma Variables（令牌）**（`figma-use` 的 canvas writes）；
- **改 / 发布设计系统库**（`figma-generate-library`）；
- **推 Code Connect 映射**（`figma-code-connect-components`）—— 它会**改代码库**，是双向的写入；
- **把代码/描述写进 Figma 变成界面**（`figma-generate-design`）—— 在别人的设计文件里造东西；
- **新建 Figma / FigJam 文件**（`figma-create-new-file`）—— 看起来无害，但**在团队空间里建文件是可见动作**；
- 把生成的规则 / `DESIGN.md` / 令牌文件**写进项目目录**（`figma-create-design-system-rules`、`figma-implement-design` 的产出侧）。

**顺序（先干什么 → 拿什么回执）**：

1. **摊开四件事**：
   **① 目标**（file key / 完整 URL / 要建的文件名；**指名道姓**，不许说"那个稿子"）·
   **② 身份**（用谁的凭据、代表哪个团队/工作区）·
   **③ 内容**（要写什么节点/什么变量/什么映射，或至少逐字摘要）·
   **④ 影响面**（谁会看到 · 能不能撤回 · **会不会动到已发布的库** · 要不要同步改代码库）。
2. **能只读就先只读**：先把"要改的东西"**读出来给主人看**（现状截图/节点清单/令牌现值），**读不触发闸**。
3. **等一次明确同意**：**只覆盖这一条**，不是"以后这类都同意"。**主人没回话 = 没同意，停。**
4. **同意后重试**：在**原始参数**上动手，**不要重写一条新命令**；参数用参数数组传，别让 shell 把主人给的字符串当语法解析。
5. **拿回执**：成功要有**可指认的对象**（file key + 节点 id / variable id / 发布的 library 版本号 / commit sha）。
   **只报"成功了"不算回执。**
6. **失败就记失败**：原样保留错误码/消息，**不许把失败写成成功**；**不许静默重试写操作**（可能重复创建节点/重复推送映射）。
7. 🔴 **不许自授权**：缺凭据、缺授权、缺主人同意里**任何一项**，都**如实报缺哪一项**，
   **不许**改门、**不许**找旁路、**不许**调用任何"万能插"能力位去替自己开门。

---

## 3. 按意图分簇（**7 条一条不漏**）

**选路总则**：本簇靠 **name 前缀 `figma-`** 取名单（**不靠 desc** —— 见 §5 坑 4）。
每条下面写的是"**什么时候用它**"，措辞来自该条自己 stub 的 `What it does`（**以上游原文为准，本件只做归位**）。

### 3.1 底座（**先过这一条，别的才谈得上**）

| 技能 | 什么时候用它 |
|---|---|
| **`figma-use`** | 要**跑 Figma Plugin API 脚本**做画布写入、检视、Figma Variables、设计系统工作时。**它是本簇其他每一条的前置**（stub 原文：*"Prerequisite for every other Figma skill in this catalogue."*）⇒ **任何 figma 动作之前先确认这条通不通**；它不通，后面 6 条全部不成立。触发词：`figma use` / `figma plugin api` / `figma canvas` / `figma scripts`。 |

### 3.2 起手（先有一张空文件）

| 技能 | 什么时候用它 |
|---|---|
| **`figma-create-new-file`** | 要**新建一张空白 Figma Design 或 FigJam 文件**时；放在脚本化设计系统流程 / 工作坊流程的**第一步**。触发词：`figma new file` / `figjam new` / `create figma file`。 |

### 3.3 生成（**代码 → Figma**）

| 技能 | 什么时候用它 |
|---|---|
| **`figma-generate-design`** | 要**按代码或文字描述在 Figma 里建/更新界面**，并且要**用设计系统组件 + design tokens** 把应用页面翻译进 Figma 时。触发词：`figma generate design` / `code to figma` / `screen generation` / `figma from code`。 |
| **`figma-generate-library`** | 要**从代码库建/更新一整座成品级（professional-grade）设计系统库**，让 **Figma 里的"真源"跟已发版组件保持同步**时。触发词：`figma library` / `design system library` / `figma from codebase` / `sync figma`。 |

**两条的区别（最常问的一处）**：`figma-generate-design` 造的是**页面/屏幕**；
`figma-generate-library` 造的是**组件库本身**。**要页面还是要库，先把这句问清，别混。**

### 3.4 落地（**Figma → 代码**）

| 技能 | 什么时候用它 |
|---|---|
| **`figma-implement-design`** | 要把 **Figma 设计按 1:1 视觉保真翻成生产可用代码**、把 Figma frame 直接交给前端 agent 时。触发词：`figma to code` / `implement figma` / `figma fidelity` / `1:1 figma`。 |
| **`figma-code-connect-components`** | 要把 **Figma 设计组件与代码组件用 Code Connect 挂起来**，让设计系统的更新**自动流进代码库**时。触发词：`figma code connect` / `design to code` / `figma components` / `code connect`。 |

### 3.5 固化（把规矩写成一份文件）

| 技能 | 什么时候用它 |
|---|---|
| **`figma-create-design-system-rules`** | 要为 Figma→代码流程**生成项目专属的设计系统规则**，把**令牌、命名、lint 规则收在一处**时。触发词：`figma rules` / `design system rules` / `figma to code rules` / `figma tokens`。 |

### 3.6 选路示例（按人话 → 落到哪条）

| 主人说 | 落到 |
|---|---|
| "把这张 Figma 稿子做成网页" | `figma-implement-design`（**先** `figma-use` 把稿子读出来） |
| "把我们的 React 组件库同步进 Figma" | `figma-generate-library` |
| "把这个页面的代码画成 Figma" | `figma-generate-design` |
| "给我一张空 Figma 文件开工" | `figma-create-new-file` |
| "组件和代码挂起来，改了设计代码跟着走" | `figma-code-connect-components` |
| "令牌和命名规则写成一份文档" | `figma-create-design-system-rules` |
| "先去 Figma 里看一眼现状" | `figma-use`（只读读取，**不过闸二**） |

🔴 **上面每一条落地动作，本机现在都跑不了**（§1 硬结论）。选路示例是**归位示例，不是可用示例**。

---

## 4. 🔴 报告层红线（读数纪律）

1. **不许把"目录里有这条技能"说成"这条技能能用"。** 本簇 7 条是 stub，**有名字不等于有实现**（§1 已验：每个目录里只有 `SKILL.md`）。
2. **不许编命令、编路径、编参数、编 figma 变量名。** 本件里出现的每条命令要么标 **✅ 已验**（本次真跑过，§6），要么明确标 **（未验）**。**没跑过的不许说成跑过。**
3. **不许报凭据细节。** 只报**已配 / 未配**，或**前 4 位掩码**。本件全篇**没有任何真实 token 值**。
4. **不许把"没连上"包装成"连上了但是空的"。** 这是最像成功的一种假读数。
5. **有错照原样记**：保留错误码 / 原话 / 退出码。**缺凭据 ≠ 操作失败 ≠ 文件为空**，三者不许混着报。
6. **不许把"上游 README 里这么写"当成"本机这么做验证过"。** 本件的 §3 措辞来自 stub 的 `What it does`（= 上游描述），**已如实标注来源**。
7. **子方法与能位**：本簇是技能簇（按名字加载执行），**不是**万能插能力位。别为了"走门"去硬套 `five-dim.py cap <名字>`。

---

## 5. 本机踩过的坑（照做，别自己解读）

1. ✅ **`open <url>` 在 Windows 上不存在。** 7 条 stub 的 `How to use` 都写了
   `open https://github.com/figma/skills`。现读：`Get-Command open` → **不存在**（无输出）。
   ⇒ **照抄这句会直接 command not found。** 要打开链接请由主人点，或由主人决定用什么方式；
   **本件不代跑"打开浏览器"这种带副作用动作**（未验，也不该硬试）。

2. ✅ **`--domain` 列表 ≠ 簇名单。** `omni.py list --domain design` 现读返回 **23 条**，
   但 `name` 前缀为 `design-` 的只有 **4 条**（见 `gbt-design`）。
   ⇒ **簇一律按 name 前缀取，别按 `--domain` 取**，否则会把 `figma-*` 和无关技能混进来。

3. ✅ **managed 目录里没有 figma 技能。** `C:\Users\ADMIN\.openclaw-autoclaw\skills` 下
   `figma-*` 文件夹数 = **0**。而本仓 `AGENTS.md` 又写着"新技能一律装到 managed 目录"。
   ⇒ **本簇的 7 条不在 managed 目录，别去那儿找，也别为了"统一"把它们复制过去**（那是改别人的簇/别人的落点）。
   本规程自己的安装件才落 managed 目录（§7）。

4. ✅ **这 11 条（含 figma 7 条）的 `description:` 用了 YAML `|` 块标量，图鉴把它抓成了空。**
   现读：`state/skill_atlas.json` 里 7 条的 `desc` 长度 = **1**（值就是一个 `|`），`triggers` 却抓到了（3–4 个）。
   表现是 `omni.py list --domain figma` 与 `omni.py ask "..."` 里这些条目的描述栏**是空的**。
   ⇒ **两条后果**：① **语义路由基本拿不到本簇的内容线索，只能靠名字和 triggers**；
   ② **本件自己的 frontmatter 必须用单行 `description:`，不许用 `|`** —— 否则新规程也会在图鉴里变成空描述。

5. ✅ **簇的机器验收 `verify-distill.py --cluster <簇>` 现在还判 FAIL，原因不是产物缺，是登记缺。**
   现读：`py -3.14 tools/codex-scripts/verify-distill.py --cluster figma` 返回
   `{"cluster":"figma","skill":null,"fail":["omni.py 的 DISTILLED_CLUSTERS 里没登记这个簇"],"facts":{"skills_in_atlas":7}}`，`verdict: FAIL`，`exit 1`。
   ⇒ **簇登记（`omni.py` 的 `DISTILLED_CLUSTERS`）由主人侧做，本件不许动 `omni.py`。**
   登记之后这个验收才会真正去查"两份同哈希 + frontmatter + **7 条技能名是否都被点到**"。

6. ⚠️ **（未验）装上游 bundle 之后能不能真跑，本件不负责。** 7 条 stub 都说"把上游 bundle 装进你
   agent 的技能目录就能跑完整流程"，但**本次没装、没跑、没验**。
   ⇒ **不许把"装了就能用"当结论转述给主人**；要么先装再验，要么说"未验"。

7. ⚠️ **（未验）Figma 官方 MCP 的接入方式。** 本机 `npx` 在，理论上可以起一个 MCP，
   **但本次没起、没配 OAuth、没验任何一次调用**。本件**不提供**未验的启动命令。

---

## 6. 本次真跑过的命令（证据清单）

| 命令 | 关键返回 | 判定 |
|---|---|---|
| `py -3.14 tools/codex-scripts/omni.py list --domain figma` | 能力位 0 条 · agent 技能 **7 条**（`figma-code-connect-components` / `figma-create-design-system-rules` / `figma-create-new-file` / `figma-generate-design` / `figma-generate-library` / `figma-implement-design` / `figma-use`，全部 `design-asset`） | ✅ 名单成立，7 条 |
| 读 `state/skill_atlas.json`（`name` 前缀 `figma-`） | **7 条**，与上条逐名一致 | ✅ 两处口径一致 |
| 读 `state/skill_atlas.json` 的 `desc` / `triggers` | 7 条 `desc` 长度 = 1 · `triggers` 3–4 个 | ✅ 抓到坑 4 |
| `Get-ChildItem 'C:\Users\ADMIN\.openclaw-autoclaw\skills'`（筛 `figma-*`） | **0 条** | ✅ 抓到坑 3 |
| 逐目录列 `审美相关skill\skills\figma-*\` 下的文件 | 7 个目录**各只有 `SKILL.md`** | ✅ stub 形态成立 |
| 逐条读 7 份 `SKILL.md` | 41–42 行；`od.upstream` 全为 `https://github.com/figma/skills` | ✅ §3 措辞有据 |
| `[Environment]::GetEnvironmentVariable` × 5 个 token 名（process + user） | **全部未配** | ✅ 闸一读数 |
| 读 `config/mcporter.json` | 5 个 server，**无 figma** | ✅ 无 MCP 通道 |
| `Get-Command figma / figma-cli / figma-connect / code-connect` | **都不在 PATH** | ✅ 无 CLI 通道 |
| `Test-Path %LOCALAPPDATA%\Figma` / `%APPDATA%\Figma` / `~/.figma` | **三个都不存在** | ✅ 无桌面版 |
| `Get-Command node / npx` | `C:\Program Files\nodejs\node.exe` · `...\npx.ps1` | ✅ 运行时在 |
| `Get-Command open` | **不存在** | ✅ 抓到坑 1 |
| `py -3.14 tools/codex-scripts/omni.py ask "帮我从 Figma 设计稿生成一个设计系统"` | 技能栏列出 7 条 figma-*（desc 为空，评分均 7.2） | ✅ 抓到坑 4 的实际表现 |
| `py -3.14 tools/codex-scripts/verify-distill.py --cluster figma` | `skill: null` · `fail: 没登记` · `verdict: FAIL` · `exit 1` | ✅ 抓到坑 5 |

**本次一次都没跑过**：任何 Figma 远端调用 · 任何 Plugin API 脚本 · 任何 MCP 连接 · 任何 token 配置 · `open` · 装上游 bundle。

---

## 7. 固化位置（**重启后要在**）

| 什么 | 在哪 |
|---|---|
| 本规程（源 · 真身） | `<仓>/skills/gbt-figma/SKILL.md` |
| 本规程（装机） | `C:\Users\ADMIN\.openclaw-autoclaw\skills\gbt-figma\SKILL.md`（**与源稿逐字节相同**，用 sha256 现算对比） |
| 被本件管的 7 条能力 | `C:\Users\ADMIN\Desktop\GBT小土豆V8\审美相关skill\skills\figma-*\SKILL.md`（**不由本件代管，别改**） |
| 能力名册（现读） | `state/skill_atlas.json`（`name` 前缀 `figma-`）· `py -3.14 tools/codex-scripts/omni.py list --domain figma` |
| 人话入口 | `py -3.14 tools/codex-scripts/omni.py ask "<一句话>"` |
| 验收 | `py -3.14 tools/codex-scripts/verify-distill.py --cluster figma`（**簇登记由主人侧做**，登记前必 FAIL） |

**纪律**：本规程**不代替**那 7 条技能，也**不代替**上游。本件只加一份规程，
**不动** `tools/codex-scripts/omni.py`、**不动** `security/policy.py`、**不动** `gbt-aesthetic`、
**不动别的簇**、**不调用 `tentacle` 的任何方法**、**不给人给自己发授权**。

---

## 8. 诚实边界（这段不许删）

1. **本件是"用法规程"，不是"能力已具备"。** 它把 7 条技能**分簇、点名、定了两道闸**；
   但**每条技能的深度用法以上游为准**，本件**不替代**，也**没有**把上游内容搬进来。
2. **本件最重要的结论是一条否定结论**：本簇在本机**当前不可执行**（无凭据 / 无通道 / 上游未 vendored）。
   这条结论的**每一条依据都在 §6 有命令与返回**；**换机器、换账号、装完上游之后必须重新现读**。
3. **本次实跑的全是只读/枚举/帮助类动作**（列表、读图鉴、读文件、查 PATH、读环境变量、跑一次验收器）。
   **任何 Figma 读写、MCP 连接、token 配置、上游安装，本次都没跑** —— 涉及它们的地方已按 §4.2 标注。
4. **本机状态是 2026-09-22 的现读快照。** 凭据、PATH、mcporter 配置都可能变；**别把这份读数当永久事实**。
5. **本件与 `gbt-aesthetic` 的边界是硬的**：本件管"怎么连、能不能连、连上后写不写"，
   `gbt-aesthetic` 管"好不好看"。**两层都不许替对方下结论。**
