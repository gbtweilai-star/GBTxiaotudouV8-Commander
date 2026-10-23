---
name: gbt-chengfeng
displayName: GBT · 视频技能簇用法规程（技能簇 chengfeng-*）
version: 1.0.0
description: GBT小土豆V8 使用 `chengfeng-*` 这一技能簇（承风/乘风 chengfeng-videocut 中文口播剪辑工具链）的用法规程。本簇按 `state/skill_atlas.json` 里 name 前缀核定共 7 条（`chengfeng-check-updates` · `chengfeng-cut` · `chengfeng-subtitle` · `chengfeng-visual` · `chengfeng-export` · `chengfeng-videocut-workbench` · `chengfeng-report-bug`），是一条「环境检查 → 剪口播 → 字幕 → 画面 → 导出」的流水线外加一个工作台 CLI 操作件和一个 GitHub 上报件。本规程把每条按意图分簇点名，钉死两道闸（① 凭据/依赖/Runtime 与 Studio 是否就位——**现读本机 Runtime 与 Studio 全部不存在**；② 写盘/覆盖素材/导出成片/上报 GitHub 一律先问主人），并记下现读出来的结构错位与真跑读数。⚠️ 与本机另一份 `gbt-video-tools`（管本机 `video-*` 技能簇、含 `video-use` 那套对话式剪片）**都涉及剪视频但地盘不同**，边界在 §0 写死。当用户说剪口播、做字幕、配画面、导出成片、检查剪辑环境，或要操作 chengfeng-videocut 工作台/上报其 Bug 时使用。
triggers:
  - "chengfeng"
  - "承风"
  - "乘风"
  - "剪口播"
  - "chengfeng-cut"
  - "chengfeng-subtitle"
  - "chengfeng-visual"
  - "chengfeng-export"
  - "chengfeng-check-updates"
  - "chengfeng-videocut-workbench"
  - "chengfeng-report-bug"
  - "Studio 复核"
  - "删词账本"
  - "字幕分屏"
  - "画面层"
  - "成片导出"
---

# GBT · 视频技能簇用法规程（技能簇 `chengfeng-*`）

> 开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属
>
> 这是**我们自己的用法规程**（不是那 7 条技能官方文档的复述）。技能自身讲"每条怎么用"，
> 本文件讲"**在我们这台机器上，谁在什么条件下、按什么顺序去用它，什么已经真能跑、
> 什么还没就位、什么东西绝对不许自动发出去**"。
> 冲突时的裁决顺序：**本文件管我们的纪律** → 各技能自己的 `SKILL.md` 管命令细节。

---

## 0. 🔴 边界（**开工第一段就读这段**）

这一簇与本机**既有的 `gbt-video-tools` 都涉及"剪视频"**，而且工作区里还有一个
`tools/video/cut.py` 明确写着"方法口径来自 chengfeng-cut / chengfeng-videocut-workbench"。
**谁管哪条、重叠处怎么选，必须先写死，否则谁读错谁就拿错的读数说话。**

| 是谁 | 管什么 | 判决口径 | 真身/入口 | 它**不**管什么 |
|---|---|---|---|---|
| **`gbt-chengfeng`（本件）** | **`chengfeng-*` 这一技能簇"怎么用"** —— 7 条的选用、两道闸、现读可运行性、坑 | 以本件为纲，命令细节以各技能 `SKILL.md` 为准 | `<仓>/skills/gbt-chengfeng/SKILL.md` | **不是**本机能力位、**不是** Ark 云端、**不是** `video-*` 簇 |
| **`gbt-video-tools`**（**已存在，别重名、别覆盖**） | **`video-*` 这一技能簇"怎么用"** —— 4 条（`video-pipeline` / `video-transcript-downloader` / `video-downloader` / `video-use`） | 以那份为纲；它管的是**本机自带技能 + 外部脚本**，**不需要任何本地服务** | `<仓>/skills/gbt-video-tools/SKILL.md` | 不管 `chengfeng-*`；**没有** Runtime / Studio / 5190 这套 |
| **`gbt-video`**（已存在） | **本机 `video` 职业域的 4 个能力位**（图鉴里的**能力位**规程） | **图鉴口径**：`domain == "video"` 有且仅有 4 位；一律走 `py -3.14 tools/codex-scripts/five-dim.py cap <能力位>`（`run_task` 唯一门） | `<仓>/skills/gbt-video/SKILL.md` | 不管技能簇 |
| **`gbt-arkcli`**（已存在） | **Ark 云端那条**（`arkcli +gen` / Seedream / Seedance） | 它自己的**调用前缀 + 登录闸 + 账号验证闸 + 计费报价确认**纪律 | `<仓>/skills/gbt-arkcli/SKILL.md` | **不代表**本机任何技能已接线 |

### 🔴 与 `gbt-video-tools` 的重叠处怎么选（**逐条钉死**）

两条都叫"剪视频"，但**不是一回事、不是一套东西、不能互相顶替**：

| 维度 | **`chengfeng-*`（本件）** | **`video-*`（`gbt-video-tools`）** |
|---|---|---|
| **形态** | 一条**流水线的 5 段 + 1 个工作台 + 1 个上报**，段与段**交接产出物**（账本 → 字幕 → 画面 → 成片） | **互相独立的 4 条**，各干各的（规划 / 下载 / 转录 / 剪） |
| **依赖** | 🔴 **必须有一个独立 Runtime + 一个本地 Studio 服务（canonical 5190）**；Skill 只做编排，**Runtime 才是项目/账本/Studio 的唯一写入者** | ✅ **不需要任何本地服务**；直接用 `ffmpeg` / `yt-dlp` / Python 脚本干活 |
| **剪的姿势** | **"改账本，不切媒体"** —— 全程只产出一份删词账本，物理剪切只在最后一段发生 | **"直接切"** —— `video-use` 的 helpers 直接切片/合成/上色 |
| **中文口播** | ✅ **专精**：逐词转录、词典修字、五轮扫描口误/重复/口头禅 | ⚠️ **不专精**：`video-use` 是通用工具链 |
| **现读能不能跑** | 🔴 **一条也跑不了**：Runtime / Studio / 插件脚本**全部不在盘上**（§3） | ⚠️ 主体依赖在（ffmpeg/Pillow），**但 `video-transcript-downloader` 缺依赖、`video-downloader` 是桩** |

**选路判据（背下来）**：

> **要"中文口播精修 + 账本式可回退剪辑 + Studio 逐屏复核"** ⇒ **`chengfeng-*`**（**但先过闸一：Runtime 没装就先装**，装不上就如实报，不许拿别的工具顶替）。
> **要"通用下载 / 扒字幕 / 快速切一刀 / 不装任何服务"** ⇒ **`video-*`**（纪律见 `gbt-video-tools`）。
> **两条都不许拿对方的读数替自己说话**：`chengfeng-*` 没装 Runtime 时，**不能说"本机不能剪视频"**——那时是"这条链没就位"，不是"剪视频这件事做不到"。

### 🔴 工作区里还有一份"第三处"（**如实记，别扩大**）

`<仓>/tools/video/cut.py` 与 `pipeline.py` 是**我们工作区自己的本地可执行件**，
`cut.py` 头部自述：*「方法口径来自 `chengfeng-cut` / `chengfeng-videocut-workbench`
（已装技能，读它们的 SKILL.md 取craft）；执行只用本机 ffmpeg 8.1.2」*，
用法是 `python tools/video/cut.py silence <in.mp4> <out.mp4>` / `cut.py e`（只分析不落刀）/ `cut.py probe`。

🔴 **读法**：它是**"借了 chengfeng 的方法论、自己用 ffmpeg 实现"**的另一条路，
**不是 chengfeng 的 Runtime，也不能拿它当 chengfeng 已装好的证据**。
本件**不替它做规程**（它属工作区工具面）；但它与 `gbt-video-tools` 的簇名重叠怎么算，
**本件不擅自裁决**，见 §8 未验清单最后一行。

---

## 1. 它是什么 / 名单怎么核（**以图鉴现读为准**）

**核定口径**：`state/skill_atlas.json` 里 `name` 以 **`chengfeng-`** 开头的条目（**带横杠**）。

```powershell
# ✅ 已验：图鉴现读（本件核名单的真命令）
$j = Get-Content "state/skill_atlas.json" -Raw | ConvertFrom-Json
$j.skills | Where-Object { $_.name -like 'chengfeng-*' } |
  Select-Object name, channel, root_count
```

**真返回（现读原文摘录）**：

```text
chengfeng-check-updates        channel=agent-skill    root_count=1 roots=C:\Users\ADMIN\.openclaw-autoclaw\skills
chengfeng-cut                  channel=agent-skill    root_count=1 roots=C:\Users\ADMIN\.openclaw-autoclaw\skills
chengfeng-export               channel=agent-skill    root_count=1 roots=C:\Users\ADMIN\.openclaw-autoclaw\skills
chengfeng-report-bug           channel=agent-skill    root_count=1 roots=C:\Users\ADMIN\.openclaw-autoclaw\skills
chengfeng-subtitle             channel=agent-skill    root_count=1 roots=C:\Users\ADMIN\.openclaw-autoclaw\skills
chengfeng-videocut-workbench   channel=agent-skill    root_count=1 roots=C:\Users\ADMIN\.openclaw-autoclaw\skills
chengfeng-visual               channel=agent-skill    root_count=1 roots=C:\Users\ADMIN\.openclaw-autoclaw\skills
```

⇒ **7 条，全部 `agent-skill` 通道，单根**（都在 `~/.openclaw-autoclaw/skills`）。
**没有裸名兄弟**（图鉴里没有一条 name 正好等于 `chengfeng`），所以本簇口径就是这 7 条，不多不少。

**真身落盘（现读，逐条确认在盘上）**：

| # | 技能 | 盘上真身 | 自带的 references / scripts |
|---|---|---|---|
| 1 | `chengfeng-check-updates` | `~/.openclaw-autoclaw/skills/chengfeng-check-updates` | 无（只有 `SKILL.md` + `agents/openai.yaml`） |
| 2 | `chengfeng-cut` | `~/.openclaw-autoclaw/skills/chengfeng-cut` | `references/lessons.md` · `references/semantic-deletion.md` |
| 3 | `chengfeng-subtitle` | `~/.openclaw-autoclaw/skills/chengfeng-subtitle` | `references/subtitle-correction.md` |
| 4 | `chengfeng-visual` | `~/.openclaw-autoclaw/skills/chengfeng-visual` | `references/visual-judgment.md` · `references/visual-module-contract.md` · `animation-styles/`（含小黑 SVG 动效样式库 + 模板 + 图标） |
| 5 | `chengfeng-export` | `~/.openclaw-autoclaw/skills/chengfeng-export` | 无 |
| 6 | `chengfeng-videocut-workbench` | `~/.openclaw-autoclaw/skills/chengfeng-videocut-workbench` | `references/connection.md` · `references/operations.md` · `references/deletion.md` · `NOTICE.md` · `LICENSE` · `CITATION.cff` |
| 7 | `chengfeng-report-bug` | `~/.openclaw-autoclaw/skills/chengfeng-report-bug` | ✅ **`scripts/report-bug.cjs`（19521 B，真脚本，本簇唯一可执行件）** |

🔴 **如实记一句**：这 7 条**是"技能文件"在盘上，不是"工具链"在盘上**。
技能正文里点名的**插件根、`scripts/`、`references/`、Runtime、Studio 服务**——
**现读全部不存在**（§3 逐条实测）。**"技能装进来了" ≠ "这条流水线能跑"。**

---

## 2. 按意图分簇（7 条逐个点名）

**流水线本体是 5 段 + 2 个旁挂件**（工作台、上报）。
顺序不是"必须一次走完"，而是**每一段的入口前提**决定了它什么时候能被喊：

```text
①环境      chengfeng-check-updates  ← 所有业务件的第 0 步都引用它
                 ↓ 就绪
②剪辑      chengfeng-cut            ← 产出「账本」，不碰媒体
                 ↓ 账本
③字幕      chengfeng-subtitle       ← 账本 + 逐词稿 → 字幕（随时可重做）
                 ↓ 字幕屏
④画面      chengfeng-visual         ← 账本 + 字幕 → HTML 层
                 ↓
⑤导出      chengfeng-export         ← 把上面三样烧成一个 mp4（唯一画像素的地方）

旁挂件甲   chengfeng-videocut-workbench  ← 手动改已有工程（增删改查时间线），不是流水线的一段
旁挂件乙   chengfeng-report-bug          ← 出问题了才用；🔴 唯一出网的一条
```

### 簇 A · 环境 → **这条链的总闸**（1 条）

| 技能 | 什么时候用它 | 它给什么 |
|---|---|---|
| **`chengfeng-check-updates`** | "检查更新 / 安装剪辑环境 / 装播放器 / 检查剪辑环境 / 剪辑环境就绪了吗 / 配置转录凭证"，**或任何业务件（剪口播/字幕/画面/导出）要开工的第 0 步** | **三态结论**：`就绪` / `需新会话` / `停`。它管两件事：**skills 版本是否最新**（走 `check-plugin-update.cjs` 对 Marketplace `chengfeng-videocut` 做隔离比对，逐项要 version + 40-hex snapshotRevision + 40-hex contentRevision + SHA-256 四项齐全）与 **Runtime 是否配套**（走 `ensure-runtime.cjs --install-if-missing`） |

🔴 **它自带一条极硬的纪律，必须照做**：*「**停止就是停止：禁止用自制的审核页、播放器、
时间线或任何替代界面继续流程。** 产品不可用时做出的任何产出都不可信（真实案例：Runtime
缺失时 Agent 手搓了一个「审片台」网页，其审核决定与产品的账本格式完全不兼容，用户白做一遍）。」*
⇒ **本件把这条顶到前面**：**Runtime 没就位时，不许拿 `ffmpeg`、`tools/video/cut.py`、
HyperFrames、`video-use` 或任何别的工具"顶替着先剪一版"。** 那不是"绕过"，那是**产出不可信**。

### 簇 B · 剪辑 → **产账本，不碰媒体**（1 条）

| 技能 | 什么时候用它 | 它给什么 |
|---|---|---|
| **`chengfeng-cut`** | "剪口播 / 处理口误 / 生成口播基础素材 / 继续剪口播"，或确认卡回传 `action=return_cut_review` | **一份人工复核过的删词账本（Cuts + EDL）**。七步：就绪 → 建档（云端逐词转录 + `project create` + `ensure-running` + 双 readback）→ 修字（词典先于一切删词判断）→ 删词（**五轮扫描，每轮只找一类**：重复 / 残句改口 / 口误重说 / 英文卡壳 / 口头禅）→ 汇总（**删词汇总表 + 重复句子表**）→ 审核（全量 `cuts set`，CAS 带 `--expected-revision`，然后开 Studio）→ 复盘（对比提案与终版，归档三个抽屉） |

🔴 **它最值钱的一条设计**：*「**不切媒体**：账本改一次是几十毫秒，切一次是一个不可撤销的文件。
到本 Skill 结束，磁盘上没有任何新视频。」* ⇒ **这一段的产出判据是"表出来了"，不是"剪好了"。**
🔴 **它最贵的两个坑**（照原文）：`cuts set` 是**替换语义**，**交增量会把上一轮删词静默丢掉**；
判断**只能用 `transcript playback` 的播放顺序，不许自己从 `transcript.json` 拼**
（"说了两遍"靠播出来相邻，自己拼会把跳号读成缺内容而误否）。

### 簇 C · 字幕 → **一件可重做的事，不是流程的一段**（1 条）

| 技能 | 什么时候用它 | 它给什么 |
|---|---|---|
| **`chengfeng-subtitle`** | "做字幕 / 加字幕 / 改字幕 / 重新分屏 / 字幕不对" ——**刚剪完可以做，做完又删了两句可以再做一遍** | `subtitles.json`。核心口径：**字幕屏存的是"词 id 列表 + 显示文字"，不存秒数**，时间每次从账本现算 |

🔴 **它最容易被误读的一条**：**字幕不需要重新转录。**
原文：*「再送一遍 ASR 只是把同样的话重新听一次，花钱、花时间，而且听得更差」*；
`transcript retranscribe` 是**上一版设计的遗留**，正文明确写 **"做字幕不要用它"**。
⇒ **这条与它自己的 `agents/openai.yaml` 缓存描述（写的是"重新转写剪后视频"）不一致**，
**以 `SKILL.md` 正文为准**（§7.6 记了这个坑）。

### 簇 D · 画面 → **在录屏上盖 HTML 层**（1 条）

| 技能 | 什么时候用它 | 它给什么 |
|---|---|---|
| **`chengfeng-visual`** | "做分镜 / 配画面 / 加动画 / 圈重点 / B-roll / 做 storyboard" | `visuals.json` + `modules/<序号-名字>/index.html`。层**绑字幕屏（`--cues`）**，产品换算成词 id，**不存秒数**；由播放器逐帧驱动 |

🔴 **它的判据里最反直觉的一条**：**"不动"是最常见的正确答案。**
原文实测：*「画面自身足够清楚 → 不动。这是最常见的正确答案（实测 13 段里 4 段不动）」*、
*「不许把每段都做点什么——铺满不是目标」*。
另外两条硬规矩：**圈的坐标要像素统计量出来（不许目测，目测差过 50px）**；
**验收看像素、不查 DOM**（曾有 iframe"可见性翻转正确"但物理上不在画面里）；
**品牌图标用官方字形，不许手画替身**。

### 簇 E · 导出 → **唯一真正画像素的地方**（1 条）

| 技能 | 什么时候用它 | 它给什么 |
|---|---|---|
| **`chengfeng-export`** | "导出 / 出成片 / 烧字幕 / 渲染 / 导出视频 / 生成最终文件" | **成片.mp4**。把账本切片段、推近、字幕、HTML 画面层**一次全部烧进 mp4** |

🔴 **它的两条纪律最容易被念反**：
① *「**导出不进剪辑状态机**：它不改任何项目文件、不做 CAS 写入、不推进 stage，产出是一个新文件，
重跑一次就覆盖。**所以它不需要确认卡。**」*
② *「不许把"导出成功"说成"验收通过"——命令返回成功只是产品自己对得上，不是画面对。」*
验收要三件：命令成功返回（产品自己数尺寸/帧数/音轨）+ **从成片抽帧用眼睛看**（至少覆盖一个推近段、
一个整屏动画段、一个只有字幕的段、一个层与层的边界）+ **人耳听感**（没人听过一律记 `human listening UNVERIFIED`）。
⚠️ **不许用预览截图当成片的证据** —— *「预览和成片是两条渲染路径，验收要看的正是它们对不对得上」*。
**前置**：机器上要有 **Google Chrome**（本机 ✅ 在），纯 CLI 安装还要 `ffmpeg ≥ 6`。

### 簇 F · 工作台 → **手动改已有工程，不是流程的一段**（1 条）

| 技能 | 什么时候用它 | 它给什么 |
|---|---|---|
| **`chengfeng-videocut-workbench`** | "插入片段 / 删掉这句 / 移除动画 / 换个画面 / 调整顺序 / 管理时间线" | 把明确的编辑要求变成现有 Runtime CLI 操作（`workbench <operation> --api-base <origin> --project <projectId>`），**始终在同一工程回读结果** |

🔴 **它最重要的自述**：*「**不是另一套编辑引擎，也不是每次使用其他 Skill 前的必读入口。**」*
🔴 **它最硬的一条前置（现读最要紧）**：`references/connection.md` 明写
*「本方法要求 **Runtime >=0.5.9**，并实际提供所需 workbench commands 与服务 capabilities。
2026-09-20 核验的公开 Plugin 配套 Runtime **0.4.11 缺少这些命令**；**安装 Skill 文件不等于功能可用**。」*
⇒ **这条是"技能在盘上但功能不可用"的官方自述**，也是本件闸一的核心读数来源之一。

### 簇 G · 上报 → 🔴 **本簇唯一出网的一条**（1 条）

| 技能 | 什么时候用它 | 它给什么 |
|---|---|---|
| **`chengfeng-report-bug`** | "上报 Bug / 反馈剪口播问题 / 提交 GitHub Issue / 这个问题告诉开发者"，或要继续提交已预览的草稿 | 脱敏后的 GitHub Issue。流程：判定是否真是可复现 Bug → 最小只读诊断 → **脱敏 → 展示完整公开内容 → 用户明确确认 → 认证 + 标签检查 + 查重 → 创建 Issue** |

🔴 **它是两步，不是一步，中间隔着人的一次点头**：

```text
draft    只在本机生成脱敏草稿 + confirmationToken（30 分钟过期）   ← 现读可跑（§4.7）
submit   调 gh 出网：auth status → 查重 → issue create             ← 🔴 必须先问主人
```

固定仓库（**不许从当前目录猜 remote**）：`product` → `Agentchengfeng/chengfeng-videocut`；
`skills` → `Agentchengfeng/chengfeng-videocut-skills`。
**禁止放进正文**：API Key / Token / Cookie / `.env`；视频、音频、截图、完整日志或转录正文；
客户名、原视频名、真实 `projectId`、用户绝对路径。
🔴 **本机读数的关键一条**：`gh` **在**且**已登录**（§3 闸一）——所以**
"能不能报" 是通的，**"该不该报" 完全取决于主人的一次明确同意**。
*「仅仅检测到错误不等于同意上报。」*

---

## 3. 闸一 · 凭据 / 依赖 / **Runtime 与 Studio 是否就位**（**现读**）

> 纪律：本节每条都标 **✅(真跑过)** 或 **(未验)**。**没跑过的不许说成跑过。**
> 凭据只报 **"已配 / 未配"** 或前 4 位掩码，**绝不贴值**。

### 3.1 🔴 Runtime 与 Studio：**现读全部不存在**

| 探针（✅ 已验） | 真返回 | 判定 |
|---|---|---|
| `~/.chengfeng-videocut` 是否在 | **`False`** | 🔴 **Runtime 安装根不存在** |
| `~/.chengfeng-videocut/bin` | 不存在 | 🔴 **Skills 期望复用的稳定入口不存在** |
| `~/.chengfeng-videocut/app` | 不存在 | 🔴 **受管 Runtime 不存在** |
| 5190 端口是否在听 | **无进程在听 5190** | 🔴 **Studio / 常驻服务未在运行** |
| 进程名含 `chengfeng` | 无 | 🔴 无服务进程 |
| 计划任务名含 `chengfeng`/`videocut` | 无 | 🔴 `windows-task` 常驻服务未注册 |
| 注册表卸载项含 `chengfeng`/`videocut` | 空 | 🔴 **桌面版 App 没装**（所以"安装并至少启动一次"这条前置完全没满足） |
| `~/.codex` 下（深 4）名字含 `chengfeng`/`videocut` | 无 | 🔴 无插件 cache |
| `.codex\.tmp\bundled-marketplaces` | 只有 `openai-bundled` | 🔴 **无 `chengfeng-videocut` Marketplace** |
| `~/.openclaw-autoclaw/plugin-skills` | 空 | 🔴 无插件技能挂载 |
| 转录凭证 `~/.chengfeng-videocut/` 下 | 目录不存在 | 🔴 **云端转录凭证未配**（且**未去别处找**，见下） |

**结论一句话**：**这台机器上 `chengfeng-*` 的工具链（Runtime / Studio / 插件脚本）
一样都没有；盘上只有 7 份技能文本。** 业务件第 0 步的"就绪检查"**现在必然拿不到"就绪"**。

### 3.2 🔴 结构错位：技能正文假设的"插件根"在本机不存在

技能正文的路径约定是 **`<插件根>/scripts/*.cjs`** 与 **`<插件根>/skills/<技能名>/…`**，
而"插件根"要**从技能实际源文件向上两级**定位。**现读实测**：

```powershell
# ✅ 已验
$skillDir = "C:\Users\ADMIN\.openclaw-autoclaw\skills\chengfeng-cut"
Split-Path (Split-Path $skillDir -Parent) -Parent
# → C:\Users\ADMIN\.openclaw-autoclaw          ← 这就是本机算出来的"插件根"
Test-Path "C:\Users\ADMIN\.openclaw-autoclaw\scripts\check-plugin-update.cjs"   # → False
Test-Path "C:\Users\ADMIN\.openclaw-autoclaw\scripts\ensure-runtime.cjs"        # → False
Test-Path "C:\Users\ADMIN\.openclaw-autoclaw\scripts\videocut-cli.cjs"          # → False
Test-Path "C:\Users\ADMIN\.openclaw-autoclaw\skills\chengfeng-report-bug"       # → False（应为 <插件根>/skills/…）
Test-Path "C:\Users\ADMIN\.openclaw-autoclaw\references\business-workflow-contract.md"  # → False
Test-Path "C:\Users\ADMIN\.openclaw-autoclaw\references\ai-term-dictionary.md"          # → False
Test-Path "C:\Users\ADMIN\.openclaw-autoclaw\.codex-plugin\plugin.json"                 # → False
```

⇒ **7 条技能是被"平铺"进托管技能目录的**（`~/.openclaw-autoclaw/skills/chengfeng-*/`），
**没有带上它们赖以运行的那层插件外壳**。上游的真身布局是
`plugins/chengfeng-videocut/{.codex-plugin, scripts, references, skills/*}`（§4.1 现读上游确认），
被漏掉的正是 `scripts/`、`references/`、`.codex-plugin/` 和那层 `skills/` 包装。

🔴 **这一条的正确说法**（**不是**"技能写错了"）：**技能文本按插件形态写的路径约定，
在"平铺安装"这种落盘方式下解析不到东西。**
⇒ 后果是**技能自己点名的每个 `<插件根>/scripts/*.cjs` 命令现在都跑不了**；
**`chengfeng-report-bug` 是唯一的例外**（它的脚本路径按平铺后的相对位置**正好落在**
`chengfeng-report-bug/scripts/report-bug.cjs`，现读**确实存在**，§4.7）。
**这属于"安装不完整 / 落盘方式与文档约定不一致"，属缺件，不是工具坏了。**

### 3.3 依赖：**机器前置大部分在，缺的是 Runtime 那一件**

| 依赖 | 谁要它 | ✅ 现读实测 | 判定 |
|---|---|---|---|
| **Node.js ≥ 20** | 跑所有 Plugin 脚本 | `node --version` → **v24.15.0** | ✅ **在**（远高于下限） |
| **Google Chrome** | 导出烧字幕/动画 | `C:\Program Files\Google\Chrome\Application\chrome.exe` | ✅ **在** |
| **Git** | skills 更新身份自证 | `git version` → **2.55.0.windows.3** | ✅ **在** |
| **FFmpeg / FFprobe** | 导出、换源判定、抽帧验收 | `ffmpeg/ffprobe version` → **8.1.2-full_build-www.gyan.dev**（winget 那个 Gyan build） | ✅ **在**（但注意：`chengfeng` 的受管版本应随桌面 App 进 Product 目录，**现在是用系统 PATH 里这个**） |
| **Bun** | Runtime 随包工具 | `bun --version` → **1.3.14** | ✅ **在**（`~/.bun/bin`） |
| **`gh`** | 上报 Bug 的提交端 | `gh` → `C:\Program Files\GitHub CLI\gh.exe` | ✅ **在**，**已登录**（见 3.4） |
| 🔴 **Runtime / Studio** | **6 条业务件的全部功能** | `~/.chengfeng-videocut` **不存在** | 🔴 **不在** |
| 🔴 **插件外壳（scripts/references/.codex-plugin）** | 所有 `<插件根>/scripts/*.cjs` | 逐一 `Test-Path` → **全 False** | 🔴 **不在** |
| 🔴 **云端转录凭证** | `chengfeng-cut` 的建档 | `~/.chengfeng-videocut` 不存在 ⇒ 未配 | 🔴 **未配**（**NAME/存在性级结论，不含任何值**） |

⚠️ **本机 `whisper.exe` 在**（`Python312\Scripts\whisper.exe`）——但 **`chengfeng-cut` 明令
"只用云端 ASR，禁止回退本地 ASR"**：没有可用云端 ASR 时报
`missing_cloud_transcription_adapter` 并停止。
⇒ **不许拿本机 whisper 去顶替 `chengfeng-cut` 的转录**（那是技能正文禁止的回退）。

### 3.4 凭据（**只报已配/未配，不贴值**）

| 名字 | 谁要它 | 现读 |
|---|---|---|
| **云端转录 API Key** | `chengfeng-cut` 建档（`videocut-cli.cjs config set transcription.apiKey`） | 🔴 **未配**（安装根不存在；**未去别处翻找**） |
| **GitHub 凭据** | `chengfeng-report-bug` 的 `submit` | ✅ **已配**：`gh auth status` → exit 0，登录 `github.com`（活动账号 `paysssk-creator`，token 掩码 `gho_****`，scopes 含 `repo`） |
| 目标仓库可见性 | 上报落点 | ✅ 两个仓库都**存在、public、`has_issues: true`**（`Agentchengfeng/chengfeng-videocut` open issues 11；`…-skills` 20） |

🔴 **报法纪律**：只说 **「已配 / 未配」** 或**前 4 位掩码**。**不许 echo、不许落盘、不许贴进规程/日报/对话。**
本件里**不会出现任何一个真凭据**（`gho_****` 是 `gh` 自己打的掩码，非真值）。

### 3.5 🔴 闸一的正确说法

> **"`chengfeng-*` 这一簇 7 条技能文本在盘上，但它们赖以运行的 Runtime、Studio、
> 插件脚本与插件级 references 一样都不在；机器前置（Node/Chrome/Git/FFmpeg/Bun/gh）倒是基本齐。
> 所以现在这 7 条**一条业务功能都跑不起来**，卡的是"工具链没装"，不是"技能坏了"。**
> **"技能文档写得很完整"和"这台机器上跑得起来"是两件事。**

---

## 4. 怎么调（**真命令 + 真返回**）

> 纪律：本节每一条都标了 **✅(真跑过)** 或 **(未验)**。**没跑过的不许说成跑过。**
> ⚠️ **本节所有 `<插件根>` 都是字面占位符**——本机**解析不出**这个根（§3.2），
> 所以这些命令**本机现在都执行不了**，照抄会把路径代进一个没有 `scripts/` 的目录。

### 4.1 ✅ 上游现读：确认"被漏掉的到底是什么"（本件做过的核对）

```powershell
# ✅ 已验（只读，出网 gh api）
gh api "repos/Agentchengfeng/chengfeng-videocut-skills/contents/plugins/chengfeng-videocut?ref=stable" --jq '.[].name'
```

**真返回（原文）**：`.codex-plugin / .gitignore / .mcp.json / README.md / dist / package-lock.json /
package.json / public / references / runtime-requirements.json / scripts / server.mjs / skills`

```powershell
# ✅ 已验
gh api "repos/Agentchengfeng/chengfeng-videocut-skills/contents/plugins/chengfeng-videocut/references?ref=stable" --jq '.[] | "\(.name) \(.size)"'
```

**真返回（原文）**：`ai-term-dictionary.md 3554` · `business-workflow-contract.md 4596` ·
`runtime-and-product-contract.md 15631`
⇒ 这三份**正是 7 条技能正文反复引用的"插件级 references"，本机一份都没有**（§3.2）。

```powershell
# ✅ 已验：上游插件里 7 条技能**全部存在**（逐条现读，避免 API 分页截断误判）
foreach ($s in @('chengfeng-check-updates','chengfeng-cut','chengfeng-export','chengfeng-report-bug','chengfeng-subtitle','chengfeng-videocut-workbench','chengfeng-visual')) {
  gh api "repos/Agentchengfeng/chengfeng-videocut-skills/contents/plugins/chengfeng-videocut/skills/$s?ref=stable" --jq '.name'
}
```

**真返回**：7 条**逐条都有**（含 `chengfeng-videocut-workbench`）。
⚠️ **注意别读错**：一次 `contents/skills` 列目录**只回 6 条**（API 分页/截断所致），
**逐条查才是真读数** —— 差点据此误判"上游也没有 workbench 那条"。

### 4.2 ✅ 现读版本合同与可获得性（**用来判"该装哪个"，不替主人做安装决定**）

```powershell
# ✅ 已验
gh api "repos/Agentchengfeng/chengfeng-videocut-skills/contents/plugins/chengfeng-videocut/runtime-requirements.json?ref=stable" -H "Accept: application/vnd.github.raw"
```

**真返回（原文摘录）**：`releaseTag: "v0.4.8"` · `minimumRuntimeVersion: "0.4.8"` ·
`portableAsset: "chengfeng-videocut-portable.tar.gz"` ·
`studioCapabilities.topLevelViews: ["storyboard","preview","koubo"]` ·
`capabilities.managedStudioService: true` · `capabilities.serviceOperations: [...]`

```powershell
# ✅ 已验
gh api "repos/Agentchengfeng/chengfeng-videocut/releases" --jq '.[0:5][] | .tag_name'
```

**真返回（原文）**：`v0.4.11` · `v0.4.10` · **`v0.5.9-windows-beta.1`** · `v0.4.9` · `v0.4.8`
其中 `v0.5.9-windows-beta.1` 现读 `prerelease: true`（`draft: false`，发布于 2026-08-21）。

🔴 **两处读数必须分开念，别混成一句**：
- **stable 分支的 `minimumRuntimeVersion` 是 `0.4.8`**（这是**版本合同**面的下限）；
- **`chengfeng-videocut-workbench` 的 `references/connection.md` 要求 Runtime ≥ `0.5.9`**
  （这是**功能能力**面的门槛，且它自述"2026-09-20 核验的公开 Plugin 配套 Runtime 0.4.11 缺少这些命令"）。
⇒ **正确说法**：**"合同下限是 0.4.8，但工作台那条要 ≥0.5.9；公开面目前能满足 ≥0.5.9 的只有一个
Windows Beta 预发布版（`prerelease: true`）。"** **不能**简单说"版本不够"或"版本够了"。
⚠️ **本件不替主人做安装决定**：装 Beta 预发布 vs 等正式版，是主人的判断题（§5）。

### 4.3（未验）`chengfeng-check-updates` 的就绪检查

```bash
node "<插件根>/scripts/check-plugin-update.cjs" --marketplace chengfeng-videocut --json
node "<插件根>/scripts/ensure-runtime.cjs" --install-if-missing --json
node "<插件根>/scripts/videocut-cli.cjs" doctor --json
```

**未验，卡在哪**：`<插件根>/scripts/` **本机不存在**（§3.2 三个 `Test-Path` 全 False），
**解析不出可执行文件**。且第 2 条会**出网 + 装 Runtime + 写 `~/.chengfeng-videocut`** ⇒ 属闸二。
**本件没跑，也不会自己去跑。**

### 4.4（未验，且依赖 Runtime）`chengfeng-cut` 的建档/修字/删词/审核

```bash
node "<插件根>/scripts/videocut-cli.cjs" project create "<项目目录>" --video "<视频>" --transcript "<逐词稿>" --json
node "<插件根>/scripts/ensure-running.cjs" --json                       # 声明式确保常驻服务（canonical 5190）
node "<插件根>/scripts/videocut-cli.cjs" workflow get "<项目目录>" --json
node "<插件根>/scripts/videocut-cli.cjs" transcript dictionary "<项目目录>" --dictionary "<插件根>/references/ai-term-dictionary.md" --json
node "<插件根>/scripts/videocut-cli.cjs" transcript playback "<项目目录>" --json
node "<插件根>/scripts/videocut-cli.cjs" cuts set "<项目目录>" --file "<提案文件>" --expected-revision "<当前revision>" --json
```

**未验，三重叠卡点**：① `<插件根>/scripts/` 不存在；② **Runtime 不存在**（`ensure-running`
`Test-Path "$env:USERPROFILE\.chengfeng-videocut"` → False，5190 无人听）；③ **云端转录凭证未配**。
**本件没跑。**

### 4.5（未验，且依赖 Runtime）`chengfeng-subtitle` / `chengfeng-visual` / `chengfeng-export`

```bash
# 字幕
node "<插件根>/scripts/videocut-cli.cjs" subtitle build "<项目目录>" --json
# 画面
node "<插件根>/scripts/videocut-cli.cjs" visual frame <project> --cues sub-0004,sub-0005 --count 12 --out <dir> --json
node "<插件根>/scripts/videocut-cli.cjs" visual add   <project> --module modules/01-xx/index.html --cues sub-0004,sub-0005 --json
# 导出（🔴 会写盘出成片）
node "<插件根>/scripts/videocut-cli.cjs" export <project> --dry-run --json     # 先看计划，不编码
node "<插件根>/scripts/videocut-cli.cjs" export <project> --json               # 🔴 真出成片
```

**未验，卡点同上（脚本不在 + Runtime 不在 + Studio 不在）**。**本件没跑，一条都没有。**

### 4.6（未验，且需要 ≥0.5.9 的 Runtime）`chengfeng-videocut-workbench`

它给的是**追加到已验证 Runtime 参数数组上的参数**，**不是可复制的 shell 命令**（原文明确）：

```json
["workbench","commands","--json"]
["workbench","connect","--api-base","<origin>","--project","<projectId>","--json"]
["workbench","<operation>","--api-base","<origin>","--project","<projectId>","--file","<absolute-request.json>","--json"]
```

**未验，卡点**：① Runtime 不在；② 它自述**要 Runtime ≥0.5.9**，而"公开面 0.4.11 缺这些命令"；
③ **`commands` 返回的 `mode/fields/required/capability` 才是真实合同**——本机连不上，
**本件不许凭字段名猜形状**。**本件没跑。**

### 4.7 ✅ **唯一真跑过的一发**：`chengfeng-report-bug` 的脚本在盘上

```powershell
# ✅ 已验（只读：确认脚本存在与大小）
Get-Item "C:\Users\ADMIN\.openclaw-autoclaw\skills\chengfeng-report-bug\scripts\report-bug.cjs" |
  Select-Object FullName, Length
```

**真返回**：`…\chengfeng-report-bug\scripts\report-bug.cjs`，**Length = 19521**

```powershell
# ✅ 已验（只读：从源码确认"哪一步出网"）
Select-String -Path "…\chengfeng-report-bug\scripts\report-bug.cjs" -Pattern 'gh |issue create|auth status'
```

**真返回（原文行摘录）**：`[ "issue", "list", "--repo", repo, "--state", "open", … ]`（查重）·
`[ "issue", "create", "--repo", repo, "--title", …, "--body-file", "-", "--label", "bug" ]`（创建）·
`process.env.CHENGFENG_VIDEOCUT_GH_BIN || "gh"`（`gh` 可被环境变量覆盖）。

🔴 **读法**：
- `report-bug.cjs draft …` ⇒ **只在本机读写 JSON 草稿 + 生成 token**，**现读可跑**（脚本在、Node 在）；
- `report-bug.cjs submit …` ⇒ **经 `gh` 出网创建公开 Issue** ⇒ 🔴 **闸二，必须先问主人**；
- 脚本会先 `gh auth status`、查目标仓库 Issues、查 `bug` 标签，**任何一步失败就保留草稿**。
⚠️ **未验**：**本件没有跑过 `draft` 也没有跑过 `submit`**（不想在没主人的报告目标时造垃圾文件/公开 Issue）。
上面只是**脚本存在性 + 出网位置**的只读核对。

### 4.8 ✅ 现读：`Get-Command chengfeng*` 的真实含义

```powershell
# ✅ 已验：PATH 与命令解析
Get-Command chengfeng -ErrorAction SilentlyContinue     # → 没有名为 chengfeng 的命令
where.exe chengfeng                                      # → INFO: Could not find files …（exit 1）
$env:PATH -split ';' | ForEach-Object { Get-ChildItem $_ -Filter "*chengfeng*" -EA SilentlyContinue }   # → 空
```

🔴 **读法纪律**：本机**没有任何名为 `chengfeng*` 的可执行命令**在 PATH 上 ——
**这符合设计**：这一簇的入口**不是**一个叫 `chengfeng` 的二进制，而是
**`node <插件根>/scripts/*.cjs` 那几支脚本 + 5190 上的 Runtime 服务**。
⇒ **"PATH 里没有 chengfeng 命令" 不能念成"没装"**，也**不能**念成"装了就能敲 `chengfeng`"。
**真正的就位判据是 §3.1 那两条：`~/.chengfeng-videocut` 在不在、5190 有没有人听。**

---

## 5. 闸二 · 写盘 / 覆盖素材 / 导出成片 / 上报 **必须先问主人**

**本条高于技能自己的任何提示。** 本簇的"写出去"分四类，**后果不一样，纪律一样：先问**。

| # | 动作 | 为什么算"写出去" | 具体落点（技能原文） |
|---|---|---|---|
| 1 | 🔴 **导出成片** | **落一个新文件；重跑一次就覆盖** | `videocut-cli.cjs export <project>`；`.chengfeng-videocut/export/` 下的 `assembled.mkv` / `overlay/*.png` / `spans/*.mp4` |
| 2 | 🔴 **上报 Bug 到 GitHub** | **不可撤回的公开文章**（对外出网 + 公开可见） | `report-bug.cjs submit` → `gh issue create --repo Agentchengfeng/… --label bug` |
| 3 | 🔴 **换源 / 覆盖素材** | **删两个源文件、拷新文件、改指纹** | 导出正文「换源四步」：`input/source.mp4` 与 `uploads/source.mp4` 是**硬链接对** ⇒ 删两个、拷新件、再建硬链接；改 `project.json` 的 `source.sha256`；**还要改 `workbench.json` 的 `sourceSha256`**（漏了它，剪辑预览拒绝生成） |
| 4 | 🔴 **装 Runtime / 装依赖 / 更新 skills** | **改本机状态 + 出网** | `ensure-runtime.cjs --install-if-missing`（装替换 `~/.chengfeng-videocut/app`，**项目数据不动**）· `report-bug` 的 `gh` 认证 · skills 激活（对用户 `CODEX_HOME` 执行 `marketplace remove/add/upgrade`） |

**顺序（先干什么 → 拿什么回执）**：

1. **摊开四件事**：**身份**（以谁的名义）· **目标**（哪个工程/哪个仓库/哪个 URL，**指名道姓**）·
   **内容**（要发的原文或文件路径）· **影响面**（会不会覆盖已有成片、Issue 是公开的、能不能撤回）。
2. **能预演就先预演**：导出**必须先跑 `--dry-run`** 把计划（片长、帧数、字幕屏数、画面层数、
   推近段数、输出尺寸）**念给主人听**；上报**必须先出 `draft` 并把
   `repo / label=bug / title / 完整脱敏正文` 展示给主人**，同时给出 `confirmationToken` 与过期时间。
3. **等一次明确同意**：**只覆盖这一次**，不是"以后这类都同意"。主人没回话 = **没同意**，停。
   （上报那条尤其硬：*「仅仅检测到错误不等于同意上报」*、*「令牌只绑定草稿内容，
   **并不自行证明用户同意**」*。）
4. **同意后照原命令重试** —— 不是重写一条新命令。
5. **拿回执**：导出要**成片绝对路径 + 尺寸/帧数**；上报要**GitHub Issue URL**
   （*「只有拿到 GitHub Issue URL，才能说"已经上报"」*）；换源要**新指纹写入后的回读**。
   **只说"成功了"不算回执。**
6. **失败就记失败**：原样保留错误与退出码（`github_auth_required` / `github_issue_create_failed` /
   `confirmation_mismatch` / `readback_mismatch` 各有各的处置），**不许把失败写成成功**。
7. **不许静默重试写操作**：上报盲重试 = **重复开 Issue**（原文：*「创建结果没有明确 Issue URL 时，
   不自动重试；它可能已经创建」*）；导出盲重试 = **重复覆盖成片**。

🔴 **两条"看起来像写、其实技能明确说不用确认卡"的，也记下来（免得念反）**：
- `chengfeng-cut` 的 `cuts set` **要 CAS 的 `--expected-revision`**（这是**产品层的并发保护**，
  不是"要不要问主人"）；且 `chengfeng-cut` 最终**不弹确认卡、不执行剪切**——
  *「物理剪切的确认卡属于导出 Skill」*。
- `chengfeng-export` 明确 *「**导出不进剪辑状态机**…**所以它不需要确认卡**」* ——
  **这是产品契约层面的"不需要 CAS 确认"**，**不等于**"导出不用问主人"：
  🔴 **落盘/覆盖成片这件事，按本件第 2 类仍要过主人的一次点头。**

---

## 6. 🔴 报告层红线（读数纪律）

> 出口前先问一句：**「这是事实，还是我读错了地方？」**

1. 🔴 **「技能在盘上」≠「工具链就位」**（本簇最贵的一条）：7 条 `SKILL.md` 都在、
   自带的 `references/` 也大多在，**但 Runtime / Studio / `<插件根>/scripts/` 一样都没有**（§3.1–3.2）。
   ⇒ **"图鉴索引到了 7 条" 只说明技能文本被扫到了，不说明这条流水线能用。**
2. 🔴 **「技能自述的路径」≠「本机的现实路径」**：正文写 `<插件根>/scripts/…` 与
   `<插件根>/skills/<名>/…`，而本机把 7 条**平铺**在 `~/.openclaw-autoclaw/skills/`。
   ⇒ **两者不许混**：正确说法是**"落盘方式与文档约定不一致"**，
   **不是**"技能写错了"，也**不是**"脚本坏了"。
3. 🔴 **「PATH 里没有 `chengfeng` 命令」≠「没装」**（§4.8）：它的入口是
   `node <插件根>/scripts/*.cjs` + 5190 上的服务，**从来不是**一个叫 `chengfeng` 的二进制。
   ⇒ 判就位要回到 `~/.chengfeng-videocut` 与 5190 这两个**真判据**。
4. 🔴 **「合同下限 0.4.8」≠「工作台能用」**（§4.2）：stable 的
   `minimumRuntimeVersion=0.4.8`，但 `chengfeng-videocut-workbench` 要 **≥0.5.9**，
   而公开面满足 ≥0.5.9 的现读只有 `v0.5.9-windows-beta.1`（**prerelease: true**）。
   ⇒ **两句分开说，不许合并成"版本够/不够"。**
5. 🔴 **「缺件 / 未装」≠「这东西坏了」**：本簇现在跑不动的原因是
   **Runtime 与插件外壳没装**，**不是**技能有 bug。同理最后那句
   *「安装 Skill 文件不等于功能可用」* 是**技能自己写的**，不是我们的判断。
6. 🔴 **「`Get-Command chengfeng*` 报 0 条」要带方法说明**：PowerShell 的 `Get-Command`
   **不吃通配符**（它按字面名找）。**正确做法是 `where.exe` + 遍历 `$env:PATH`**（§4.8 已跑）。
   ⇒ **别把"通配符没展开"念成"命令不存在"** —— 这只说明"没有叫这个名字的字面命令"。
7. 🔴 **「`draft` 能跑」≠「Bug 已经报了」**（§4.7）：`draft` 只落本机草稿 + token；
   **只有 `submit` 拿到 Issue URL 才算上报**。
8. **凭据只报"已配/未配"**：本件零凭据值（`gho_****` 是 `gh` 自己的掩码）。
9. **有错也照原样记**：保留错误原文与**退出码**。
10. **不许编命令、编路径、编技能名**：本文件每条命令要么标 **✅ 已验**，要么标 **(未验)** 并写明卡在哪。
    **没跑过的不许说成跑过。**

---

## 7. 本机踩过的坑（照做，别自己解读）

1. ✅ 🔴 **7 条技能是"平铺"进来的，没带插件外壳。** `~/.openclaw-autoclaw/skills/chengfeng-*/`
   是**各自独立**的目录；"向上两级"算出来的插件根是 `~/.openclaw-autoclaw`，
   下面**没有** `scripts/`、`references/`、`.codex-plugin/`。
   ⇒ **技能正文里每一发 `<插件根>/scripts/*.cjs` 在本机都解析不到**（§3.2）。
2. ✅ 🔴 **Runtime 与 Studio 全不在**：`~/.chengfeng-videocut` False · 5190 无人听 ·
   无 `chengfeng` 进程 · 无 `windows-task` 计划任务 · 注册表无卸载项 · 无插件 cache ·
   无 `chengfeng-videocut` Marketplace。**七路探针一致指向"没装"**（§3.1）。
3. ✅ 🔴 **上游一次列目录只回 6 条技能，差点误判"上游也没有 workbench 那条"。**
   逐条 `gh api …/skills/<名>` 才是真读数（**7 条全在**）。⇒ **列表被截断 ≠ 条目不存在。**
4. ✅ **`Get-Command chengfeng*` 在 PowerShell 里不吃通配符**（§6.6）：
   它返回 0 条**不代表**PATH 扫过了。**改用 `where.exe` + 遍历 `$env:PATH`** 做的交叉验证。
5. ✅ **`gh` 已登录**（活动账号 `paysssk-creator`，scopes 含 `repo`），
   两个目标仓库都是 **public + has_issues** ⇒ **上报的"能不能"是通的**。
   🔴 **但"该不该"完全取决于主人的一次明确同意**（§5）——**技术可行不是授权。**
6. ✅ 🔴 **`chengfeng-subtitle` 的 `agents/openai.yaml` 缓存描述与它自己的 `SKILL.md` 正文矛盾**：
   yaml 的 `short_description` 写的是 *「重新转写剪后视频，只修文字和断句…」*（**旧版口径**），
   而 `SKILL.md` 正文明确 **"做字幕不要用 `transcript retranscribe`"**、字幕**不需要重新转录**。
   ⇒ **以 `SKILL.md` 正文为准**；那个 yaml 是陈旧的调用面元数据（其余 6 条的 yaml 与正文一致）。
7. ✅ 🔴 **`v0.5.9-windows-beta.1` 是 `prerelease: true`。**
   它是目前公开面唯一满足 workbench `≥0.5.9` 的东西，**但它是 Beta 预发布**。
   ⇒ **装不装、装正式还是 Beta，是主人的判断题**（§5），**本件不替他决定**。
8. ✅ **本机有 `whisper.exe`，但 `chengfeng-cut` 禁止回退本地 ASR。**
   ⇒ **不许拿 whisper 顶替**；没有云端 ASR 就报 `missing_cloud_transcription_adapter` 并停。
9. ✅ **工作区里还有一份"借了 chengfeng 方法口径、自己用 ffmpeg 实现"的件**
   （`tools/video/cut.py`，自述"方法口径来自 `chengfeng-cut` / `chengfeng-videocut-workbench`"）。
   ⇒ **它不是 chengfeng 的 Runtime，不能当"chengfeng 已装好"的证据**（§0 末段）。
10. ✅ **图鉴现读是快照**：`built_at = 09/22/2026 22:45:37`，`counts.skills = 335`。
    **重建图鉴（`python tools/codex-scripts/omni.py build`）后，本件的名单读数都要重查。**

---

## 8. 未验清单（**如实列，不许拿它当通过**）

| 项 | 卡在哪 / 为什么不做 |
|---|---|
| **`chengfeng-check-updates` 的就绪检查三态** | **未验**。`<插件根>/scripts/` 本机不存在；且第 2 条要**出网 + 装 Runtime** ⇒ 闸二 |
| **`chengfeng-cut` 从建档到出账本的全流程** | **未验**。脚本不在 + Runtime 不在 + 5190 无人听 + **云端转录凭证未配**。**本件没造过任何项目、没转录过任何媒体** |
| **`chengfeng-subtitle` / `chengfeng-visual` / `chengfeng-export`** | **未验**，同上。**本件没写过字幕、没做过画面层、没导出过任何成片** |
| **`chengfeng-videocut-workbench` 的 `workbench commands` 真形状** | **未验**。要 Runtime ≥0.5.9 且连得上；**本件不凭字段名猜合同**（原文明确"版本不匹配时读当前发行随包说明"） |
| **`report-bug.cjs draft` 真跑** | **未验（未跑）**。脚本在、Node 在，**本件不跑**：不想在没有真实待报问题、也没指定输出路径时凭空造草稿文件（避免留垃圾/误当证据） |
| 🔴 **`report-bug.cjs submit` / 任何一次 GitHub 上报** | 🔴 **本规程一次都没做，也不该由我做。** 虽然 `gh` 已登录、仓库可写，**出网创建公开 Issue 属闸二**（§5）。**这条不是"未验"，是"要先问主人"** |
| **安装 Runtime（含 `v0.5.9-windows-beta.1`）** | **未验（未跑，且本件不擅自装）**。装 Runtime = 出网 + 写 `~/.chengfeng-videocut` ⇒ 闸二；且 Beta vs 正式是主人的判断题 |
| **Gemini/云端转录凭证的真配置** | **未验（未跑）**。它会写本机配置并需要真密钥；**本件只报"未配"，未去任何别处翻找密钥** |
| **换源四步（含改 `workbench.json` 指纹）** | **未验**。要真实项目 + 同一次录制的高清版素材，且**会删/覆盖源文件**（闸二） |
| **`tools/video/cut.py` 与 `gbt-video-tools` 的簇名归属** | **未验（口径性未验）**。它是工作区工具面，**不属于 `chengfeng-*` 前缀口径，也不属于 `video-*` 前缀**；`omni.py` 的 `DISTILLED_CLUSTERS` 里**没有 `video` 之外的对应键**。⇒ **本件不擅自替它立规程或塞进 `chengfeng` 簇**，留作主人的裁决项 |
| **本簇除这 7 条外还有没有隐藏成员** | **未验（口径性未验）**。图鉴是**现扫产物**，重建后需重查（§7.10） |
| **本簇是否该进 `omni.py` 的 `DISTILLED_CLUSTERS`** | **未验（且本件不擅自动手）**。登记是交付报告里给主人的一行（§10），**本件不自己写进 `omni.py`**（红线明令） |

---

## 9. 不许做什么（红线）

1. 🔴 **不许把"技能在盘上"说成"这条链能用"。** Runtime / Studio / 插件脚本都不在（§3）；
   说了就是假账。
2. 🔴 **不许在 Runtime 缺失时自制替代界面或拿别的工具顶替。**
   `chengfeng-check-updates` 原文那条**"停止就是停止"**必须照做
   （真实事故：手搓"审片台"，审核决定与产品账本格式完全不兼容，用户白做一遍）。
3. 🔴 **不许自动导出成片、覆盖素材、换源、上报 GitHub。** 这四类一律**先问主人**（§5）；
   **默认答案是不做**；主人没回话 = 没同意。
4. 🔴 **不许把 `--dry-run`/`draft` 的产物说成最终产物**（计划 ≠ 成片；草稿 ≠ 已上报）。
5. 🔴 **不许拿本机 `whisper.exe` 顶替 `chengfeng-cut` 的云端 ASR**（技能正文禁止回退本地 ASR）。
6. **不许动 `tools/codex-scripts/omni.py` / `security/policy.py`** ——
   本件只加一份规程，**不改门、不改登记表**（登记那一行写在 §10 交给主人）。
7. **不许改 `~/.openclaw-autoclaw/skills/chengfeng-*` 下任何技能文件** ——
   本件是被管对象的规程，不是它的补丁。
8. 🔴 **不许重名或覆盖 `gbt-video-tools` / `gbt-video` / `gbt-arkcli`** ——
   四份各管一处，边界见 §0。**谁都不许拿对方的读数替自己说话。**
9. **不许往 `~/.agents/skills/` 写任何东西**（工作区 AGENTS.md 明令：那是别的工具的共享目录）。
10. **不许自授权**：装 Runtime、装依赖、激活 skills、发 Issue 都要主人点头；
    **不许调用 `tentacle` 任何方法**去"帮我点一下/看一眼"绕过这些门。
11. **不许编命令、编路径、编技能名**：本文件每条命令要么 **✅ 已验**、要么 **(未验)** 并写明卡在哪。
12. **不许把本规程当官方文档**：这 7 条的**命令级细节以它们自己的 `SKILL.md` 为准**；
    本文件管的是**我们这儿的纪律、读法、诚实账**。

---

## 10. 固化与出处（**重启后要在**）

| 什么 | 在哪 |
|---|---|
| 本规程（源 · 真身） | `<仓>/skills/gbt-chengfeng/SKILL.md` |
| 本规程（装机 · 托管目录） | `~/.openclaw-autoclaw/skills/gbt-chengfeng/SKILL.md`（**与源稿逐字节相同**） |
| ⛔ **不许装到** | `~/.agents/skills/`（本仓 AGENTS.md 明令禁止） |
| ⚠️ **不许重名/覆盖** | `gbt-video-tools`（`video-*` 簇）· `gbt-video`（能力域）· `gbt-arkcli`（Ark 云端） |
| 技能名单（7 条） | `<仓>/state/skill_atlas.json`（`name` 以 `chengfeng-` 开头）· 现扫可重建：`python tools/codex-scripts/omni.py build` |
| 技能真身（7 条） | `~/.openclaw-autoclaw/skills/chengfeng-*`（**不由本件代管，别改**） |
| 唯一的真脚本 | `~/.openclaw-autoclaw/skills/chengfeng-report-bug/scripts/report-bug.cjs`（19521 B） |
| 上游插件真身（本机缺的那层） | `Agentchengfeng/chengfeng-videocut-skills` → `plugins/chengfeng-videocut/{.codex-plugin,scripts,references,skills}`（`--ref stable`） |
| 上游 Runtime 发行 | `Agentchengfeng/chengfeng-videocut` releases（现读最新正式 `v0.4.11`；满足工作台 ≥0.5.9 的只有 `v0.5.9-windows-beta.1`，**prerelease**） |
| 人话入口 | `python tools/codex-scripts/omni.py ask "帮我剪这条中文口播"` |
| 验收 | `py -3.14 tools/codex-scripts/verify-distill.py --cluster chengfeng` |

**深蒸登记（应加、本次未擅自动手）**：`omni.py` 的 `DISTILLED_CLUSTERS` 加一行

```python
    "chengfeng": "gbt-chengfeng",     # 7 条：中文口播工具链（环境/剪/字幕/画面/导出 + 工作台 + 上报）；Runtime 与 Studio 现读未装
```

加完后 `verify-distill.py --cluster chengfeng` 才会从 **`FAIL: 没登记这个簇`** 变 PASS。
⚠️ **注意别撞车**：这份是 **`DISTILLED_CLUSTERS`** 里按 `chengfeng-` 前缀管**技能簇**的一行；
**不要动** `"video": "gbt-video-tools"`（那是 `video-*` 簇）与 `DISTILLED_DOMAINS` 里的
`"video": "gbt-video"`（那是**能力域**）。**三处各自独立，名字像但不是一回事。**
（本次**没改** `omni.py` —— 交付报告里给主人这一行，**没交付就会 FAIL，不会静默变绿**。）

---

## 11. 诚实边界（这段不许删）

1. **本件是"用法规程"，不是"能力已具备"。** 它把 7 条技能**分簇、点名、定了纪律**，
   并**如实记下它们现在跑不起来**；**每条技能的深度用法以它自己的 `SKILL.md` 为准**，本件**不替代**。
2. **本次实跑的都是只读探针**：图鉴前缀清点 · `Get-Command`/`where.exe`/遍历 `PATH` ·
   `Test-Path`（Runtime 根 / bin / app / 插件脚本 / 插件级 references / 7 条真身）·
   `Get-NetTCPConnection` 查 5190 · `Get-Process` / `Get-ScheduledTask` / 注册表卸载项 ·
   `node/ffmpeg/ffprobe/bun/git/py -3.14 --version` · `gh auth status` ·
   `gh api` 读上游目录/版本合同/发行列表 · 对 `report-bug.cjs` 做**存在性与出网位置**的源码检索。
   **没有装过任何 Runtime 或依赖，没有起过任何服务，没有转录/剪辑/导出过任何媒体，
   没有写过任何项目文件，没有上报过任何 Issue，也没有改过任何技能文件。**
3. **本机状态是现读快照**（`~/.chengfeng-videocut` 不存在 · 5190 无人听 · 无插件 cache ·
   Node v24.15.0 · Chrome 在 · FFmpeg 8.1.2 在 · Bun 1.3.14 在 · Git 2.55.0 在 · `gh` 已登录 ·
   图鉴 `built_at 09/22/2026 22:45:37`）。
   **换机器、补装 Runtime、或图鉴重建后，本件的读数都要重查。**
4. **凭据只报"已配/未配"**：本件**不出现任何凭据值**；
   云端转录凭证现读**未配**（安装根不存在），GitHub 凭据现读**已配**（仅掩码）。
5. **本件与 `gbt-video-tools` / `gbt-video` / `gbt-arkcli` 的边界**见 §0；
   **谁都不许拿对方的读数替自己说话。**
