---
name: gbt-gsap
displayName: GBT · GSAP 技能簇用法规程（gsap-*）
version: 1.0.0
description: GBT小土豆V8 使用 GSAP 技能簇（gsap-* 四条：gsap-core / gsap-timeline / gsap-scrolltrigger / gsap-react）的用法规程。它讲清这四条**怎么用**——以及一条必须说在前面的事实：本机这四条**全是目录桩**（只有 SKILL.md、无脚本、无 references、上游未 vendored），所以"点名它们"拿到的是上游入口而不是可执行规程；本机真正装着 GSAP 实现知识的是 live 目录里的 hyperframes-animation（4 份 GSAP adapter + gsap-effects）。规程含：逐条点名与按意图分簇、两道闸（凭据只报已配未配 + 装依赖/引外部 CDN/发版上线必须先问主人）、只读实跑过的命令与真实返回、以及本机已踩过的坑（桩也是 SKILL.md、有文件≠有流程、裸 python 是 3.12）。当用户说 gsap/补间/缓动/时间线/ScrollTrigger/滚动动画/useGSAP，或按名字点名 gsap-* 却不知道本机到底能不能跑时使用。
triggers:
  - "GSAP"
  - "gsap"
  - "gsap-core"
  - "gsap-timeline"
  - "gsap-scrolltrigger"
  - "gsap-react"
  - "补间"
  - "tween"
  - "缓动"
  - "easing"
  - "时间线动画"
  - "ScrollTrigger"
  - "滚动动画"
  - "滚动联动"
  - "useGSAP"
  - "网页动画"
---

# GBT · GSAP 技能簇用法规程（`gsap-*`）

> 开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属
>
> 🔴 **一句边界（先划清）**：本件只管「**这四条 GSAP 技能怎么用**」——它们是什么、在哪、
> **能不能跑**、怎么点名、要过哪道闸、真正的实现知识在哪一份文件里。
> **「这个动效好不好看 / 该用什么节奏与气质」回 `gbt-aesthetic`**，本件**不做审美判断**。
> 三层裁决顺序：**本件管我们的用法纪律** → 各技能自己的 `SKILL.md`（及 `hyperframes-animation`
> 的 GSAP adapter）管 API 细节 → `gbt-aesthetic` 管审美判断。三层都守。

---

## 0. 先把最重要的事实说了：**本簇四条全是目录桩**

### 0.1 名单（**以 `state/skill_atlas.json` 里 name 前缀为准**）

现读（2026-09-22 · 图鉴 `built_at = 2026-09-22T22:16:13`）：
**name 以 `gsap-` 开头的，图鉴里正好 4 条**：

| # | 技能名 | 通道 | 本机内容 | 文件全貌（✅ 已验） |
|---|---|---|---|---|
| 1 | `gsap-core` | design-asset | ⚠️ **桩** 1150 B | 只有 `SKILL.md` |
| 2 | `gsap-timeline` | design-asset | ⚠️ **桩** 1213 B | 只有 `SKILL.md` |
| 3 | `gsap-scrolltrigger` | design-asset | ⚠️ **桩** 1204 B | 只有 `SKILL.md` |
| 4 | `gsap-react` | design-asset | ⚠️ **桩** 1158 B | 只有 `SKILL.md` |

两个口径交叉核对都指向同一个 4：

```powershell
# ✅ 已验：图鉴口径（前缀 gsap-）
py -3.14 -c "import json;d=json.load(open('state/skill_atlas.json',encoding='utf-8'));print(sorted({s['name'] for s in d['skills'] if s['name'].startswith('gsap-')}))"
# → ['gsap-core', 'gsap-react', 'gsap-scrolltrigger', 'gsap-timeline']

# ✅ 已验：omni 域口径
py -3.14 tools/codex-scripts/omni.py list --domain gsap
# → 能力位 0 条；agent 技能 4 条（gsap-core / gsap-react / gsap-scrolltrigger / gsap-timeline）
#   ⇒ 这一簇域口径与前缀口径**一致**，都是 4 条
```

验收器也按前缀算（`tools/codex-scripts/verify-distill.py:128-129`）。

### 0.2 「桩」是什么意思（**这是本簇的核心事实，不许含糊**）

✅ 已验：这四条**每条只有一个 `SKILL.md`，没有任何脚本、没有任何 `references/`**。
而 `SKILL.md` 的正文**三段话**，全是目录索引式的：

1. **What it does** —— 一句英文概述（下面 §1 逐条抄了）；
2. **Source** —— `Upstream: https://github.com/greensock/skills` · `Category: animation-motion`；
3 .**How to use** —— 原文照抄：
   > "This catalogue entry advertises the skill in Open Design so the agent discovers it during
   > planning. **To run the full upstream workflow with its original assets, scripts, and references,
   > install the upstream bundle into your active agent's skills directory**"

🔴 **结论（必须照这个说）**：
**按名字点名 `gsap-core` / `gsap-timeline` / `gsap-scrolltrigger` / `gsap-react`，
本机给你的不是 GSAP 用法规程，而是"上游在哪个仓库"。**
本件**不假装**它们能跑，也**不许**为了"让它能跑"就私自 `git clone` 上游（见 §3 闸二）。

✅ 已验：**本机没有 vendored 上游** ——
工作区内没有 `greensock` 目录，只有 `审美相关skill/skills/gsap-scrolltrigger`
（以及 `.shadow-repo/` 下的同名影子副本），**那是桩本身，不是上游 bundle**。

### 0.3 那 GSAP 的实现知识在本机哪？（**本簇的替代路由**）

✅ 已验：本会话 `available_skills` 里有 **`hyperframes-animation`**（**live 目录，能按名字加载**），
它的 `description` 原文写着七个运行时适配器：
> "…the seven runtime adapters (**GSAP default**, plus Lottie, Three.js, Anime.js,
> CSS keyframes, Web Animations API, TypeGPU)… look up runtime-specific API (e.g. **GSAP eases**…)"

✅ 已验：它的 **GSAP 专章真的在**（在 `~/.agents/skills/hyperframes-animation/`，共 122 个文件）：

| 文件 | 大小 | 什么时候读它 |
|---|---|---|
| `adapters/gsap.md` | 7504 B | **GSAP API 总入口**：timeline / tweens / position parameters |
| `adapters/gsap-timeline-and-labels.md` | 3734 B | **时间线 + labels**（`gsap-timeline` 那条桩本该讲的东西） |
| `adapters/gsap-easing-and-stagger.md` | 13270 B | **缓动 + stagger**（`gsap-core` 那条桩本该讲的东西） |
| `adapters/gsap-transforms-and-perf.md` | 8552 B | **transform / 性能** |
| `rules/gsap-effects.md` | 6912 B | **可直接抄的效果配方** |
| `rules-index.md` | 21204 B | 先在这张索引里按触发词/标签挑原子动作 |

⇒ 🔴 **实践纪律**：**要点名 GSAP 就点名 `hyperframes-animation`**（它是 live 的、有 40 KB 真内容）。
**`gsap-*` 四条只当"上游坐标"用** —— 它们指的上游是 GreenSock 官方仓库，
**要不要装由主人定**（§3 闸二）。

---

## 1. 按意图分簇（**4 条一条不漏**）

**分簇说明**：下面这张"意图地图"讲的是**每条桩覆盖的意图边界**（照抄各桩自己的 `description`），
**不是"可执行清单"** —— 四条都不含步骤。**要真动手，走 §0.3 的 `hyperframes-animation`。**

### 簇 A · 基础补间 / 缓动 / 默认值

| 技能 | 什么时候用它（在"只有桩"的前提下） |
|---|---|
| **`gsap-core`** | **要知道"最基础那层的 GSAP 管什么"时用它**，或**当你要找上游 `gsap-core` 那条的坐标**时点名它。它自报的边界是：`gsap.to()` / `from()` / `fromTo()`、easing、duration、stagger、defaults —— 即**生产级网页动画原语**。⚠️ **本机这份不含任何 API 细节**。 |

### 簇 B · 序列与时间线编排

| 技能 | 什么时候用它（在"只有桩"的前提下） |
|---|---|
| **`gsap-timeline`** | **要编排"多步动效序列"时点名它**。它自报的边界是：Timelines、sequencing、**position parameter**、labels、nesting、播放控制。⚠️ **本机这份不含任何 API 细节**；真读 `adapters/gsap-timeline-and-labels.md`（§0.3）。 |

### 簇 C · 滚动联动

| 技能 | 什么时候用它（在"只有桩"的前提下） |
|---|---|
| **`gsap-scrolltrigger`** | **要做"滚动驱动 / 钉住 / scrub"时点名它**。它自报的边界是：ScrollTrigger 的 scroll-linked animations、**pinning**、**scrub**、**refresh 处理**，适用编辑型站点与产品页。⚠️ **本机这份不含任何 API 细节**。🔴 `ScrollTrigger` 是 **GSAP 的插件**（不在 `gsap` 核心名义下随意使用），**引它之前先确认你引的是哪个包/哪条 CDN**（§3 闸二）。 |

### 簇 D · React / Next.js 集成

| 技能 | 什么时候用它（在"只有桩"的前提下） |
|---|---|
| **`gsap-react`** | **要在 React / Next.js 里安全地跑 GSAP 时点名它**。它自报的边界是：**`useGSAP` hook**、refs、**`gsap.context()`**、**cleanup**、**SSR**。关键词是"**safe motion**"——即**别忘了卸载时清理**。⚠️ 本机这份不含任何 API 细节，**也没有可抄的 cleanup 代码**。 |

### 簇 E · 真实现面（**不在本簇，但是本簇的落点**）

| 技能 | 什么时候用它 |
|---|---|
| **`hyperframes-animation`**（live · 非 `gsap-` 前缀） | **任何真要做 GSAP 动效的时刻**。先 `rules-index.md` 挑 2-4 条原子规则，需要查 API 再进对应 `adapters/gsap*.md`。⚠️ 它是 **HyperFrames 原生**口径（单条 paused timeline、seek-safe、deterministic）——**脱离 HyperFrames 的普通网页动画，它给的是可移植的手法与 API，不是 HyperFrames 的框架约束**，边界别混。 |

---

## 2. 两道闸（顺序不能颠倒）

### 闸一 · 凭据闸（**只报"已配 / 未配"，绝不贴值**）

✅ 已验（2026-09-22 现读）：

| 这条技能 | 需要什么凭据 | 本机状态 |
|---|---|---|
| `gsap-core` / `gsap-timeline` / `gsap-scrolltrigger` / `gsap-react` | **四条桩的 frontmatter 里没有 `requires` / `env` / `metadata` 段**（只有 `name` / `description` / `triggers` / `od`）⇒ **本机这四条不声明任何凭据需求** | ✅ **无凭据需求** |
| `hyperframes-animation`（替代路由） | **本次只读了它的 `description` 与 GSAP 章文件名，未逐条核它的凭据声明** | ⚠️ **未核**（不编） |

**凭据纪律（硬）**：

1. 🔴 **不许把任何 key / token / 账号信息写进文件、聊天、规程、日报**。
2. 要给人看**只报**「**已配 / 未配**」或**前 4 位掩码**（例 `sk-a1b2****`）。
3. 🔴 **不许为一个"目录桩"去配它上游的凭据** —— 那等于替上游做了它没做的事。
4. ⚠️ **（未验）GSAP 生态的许可与账号面**：本件**没有**核过"哪些插件属免费、哪些属付费/CDN 需登录"。
   **要用到非核心插件时，先自己去官方核清许可**，**不许照本件猜**。

### 闸二 · 会改外部 / 装依赖 / 引外部 CDN / 发版上线 —— **必须先问主人**

**本条高于技能自己的流程。** 理由：这四条桩**自己没有脚本**，所以"危险动作"不来自它们，
而来自**你为了"让它们跑起来"想做的那些事** —— 那正是最容易顺手做掉、又最难撤回的一类。

**算"改外部 / 装依赖 / 发版 / 上传"的动作**（一律先问主人）：

| 动作 | 为什么必须先问 |
|---|---|
| **装上游 bundle**（`git clone https://github.com/greensock/skills` 之类，再拷进 skills 目录） | **改本机 + 从外部取代码**；且本仓技能目录有既定约定（§6），**不许随手建目录** |
| **`npm install gsap`**（或任何 `npm i`） | **改本机**（下载代码、写 `node_modules`、可能触发 postinstall）。✅ 已验：本仓工作区根**没有 `package.json`、没有 `node_modules`** ⇒ **本簇目前连包管理器面都没有**，一装就是"从零引入一套依赖" |
| **从外部 CDN 引 GSAP**（`<script src="https://cdn…">`） | **引入外部请求**：影响离线可用性、隐私面、供应链面；**且上线后是给所有人加载的** |
| **把带 GSAP 的页面部署上线**（Vercel / nginx / 云主机等） | **发版 / 上传**：对外可见、可被转发 |
| **跑 `py -3.14 tools/codex-scripts/omni.py build`** | **改本机状态文件**（重写 `state/skill_atlas.json`）。它不改外部、**但会改变全机读数**，属主人的登记动作（§6）——**我不自己跑** |

**顺序（先干什么 → 拿什么回执）**：

1. **摊开四件事**：**身份/账号**（用谁的账号、哪个 npm 账号/哪个托管商）· **目标**（哪个文件/哪个目录，
   **指名道姓**）· **内容**（要装的是哪个包、哪一版；要引的是哪条 CDN；要发的是哪一版页面）·
   **影响面**（谁会看到、能不能撤回、删了能不能恢复）。
2. **先做不碰外部与不装东西的部分**：读 `hyperframes-animation` 的 GSAP 章、在本地已存在的
   工程里写动画代码、本地浏览器打开验证 —— **这些都可以先做完**。
   **不要**因为"反正要问"就停在这不动。
3. **等一次明确同意**：**只覆盖这一条**（"这次装这个包"≠"以后这类都装"）。
   **主人没回话 = 没同意，停。**
4. **同意后才动手**，并按需取回执：
   - `npm install`：拿到**包名 + 版本 + exit code**；
   - 部署：拿到**live URL**，并**打开它确认动画真的在跑**（不是只看到 200）。
5. **失败就记失败**：原样保留错误与退出码，**不许把失败写成成功**（见 §4）。
6. **不许静默重试**：装依赖 / 发版类动作盲重试 = **可能重复发布**。重试前先确认第一次到底成没成。

---

## 3. 只读实跑过的命令与真实返回（**未验的已标**）

### 3.1 ✅ 已验（本机真跑过，返回照抄）

| 命令 | 关键返回 | 判定 |
|---|---|---|
| `py -3.14 tools/codex-scripts/omni.py list --domain gsap` | 能力位 **0** 条；agent 技能 **4** 条（gsap-core / gsap-react / gsap-scrolltrigger / gsap-timeline） | ✅ 域口径 = 4 |
| `py -3.14 -c "…startswith('gsap-')"` | `['gsap-core','gsap-react','gsap-scrolltrigger','gsap-timeline']` | ✅ 簇口径 = **4** |
| `Get-ChildItem 审美相关skill\skills\gsap-*\ -Recurse -File` | 每条**只有 `SKILL.md`**（1150/1158/1204/1213 B） | ✅ **全是桩**（无脚本、无 references） |
| `Get-Content gsap-*.md` 搜 `This catalogue entry advertises the skill` | **四条全部命中** | ✅ 桩的判据成立 |
| `Test-Path package.json / node_modules / node_modules\gsap`（工作区根） | **四个全部不存在** | ✅ **无 npm 包面 ⇒ gsap 库未装** |
| `Get-ChildItem -Recurse -Depth 4 -Directory \| ? Name -match 'greensock'` | **0 个**（只匹配到 `gsap-scrolltrigger` 桩目录与其 `.shadow-repo` 影子副本） | ✅ **上游未 vendored** |
| `node --version` / `npm --version` | `v24.15.0` / `11.12.1` | ✅ 运行时在（但**没有任何工程在用**） |
| `~/.agents/skills/hyperframes-animation/` 文件枚举 | **122 个文件**；`adapters/gsap.md` 7504 B · `gsap-timeline-and-labels.md` 3734 B · `gsap-easing-and-stagger.md` 13270 B · `gsap-transforms-and-perf.md` 8552 B · `rules/gsap-effects.md` 6912 B · `rules-index.md` 21204 B | ✅ **真 GSAP 知识面存在且可读** |
| `py -3.14 tools/codex-scripts/verify-distill.py --cluster lark` | `verdict: PASS` · `identical: true` · exit **0** | ✅ 验收器可用（对照件） |
| `py -3.14 tools/codex-scripts/verify-distill.py --cluster gsap` | 报 `"omni.py 的 DISTILLED_CLUSTERS 里没登记这个簇"` | ⚠️ **需主人登记**（§6） |

### 3.2 ⚠️ 未验（**没跑，不许说成跑过**）

| 事项 | 为什么没验 |
|---|---|
| `git clone https://github.com/greensock/skills` | **从外部取代码 + 改本机**（§2 闸二）——需主人同意 |
| `npm install gsap` / `npm i gsap@<ver>` | **装依赖**（§2 闸二）——需主人同意 |
| 任何真在浏览器里跑的 GSAP 动画 | 本件只定纪律，不代跑产出 |
| GSAP 插件（ScrollTrigger / SplitText 等）的**许可与版本面** | 本次**没核**官方许可页 ⇒ **不编**（§2 闸一·条 4） |
| `hyperframes-animation` 里 GSAP 章的**具体 API 内容** | 本次只**核了文件存在与大小**，**没逐份通读** ⇒ 引用细节前必须自己读那 5 份文件 |

---

## 4. 🔴 报告层红线（读数纪律）

1. **读数先问一句：这是事实，还是我读错了地方？**
   本簇有**三个专门会给你"对的形状 + 错的内容"的地方**：
   - **桩也是 `SKILL.md`**：🔴 **文件存在 ≠ 有流程**。
     本机 4 条**每条只有一个 SKILL.md**，正文只指向上游。
     **判据是"有没有真步骤/脚本"，不是"文件在不在"。**
   - **`omni list --domain gsap` 报 4 条，和本簇 4 条一致** ——
     但**这次一致不等于这个口径永远对**（同域的 `frontend` 就是 6 vs 4，见 `gbt-frontend`）。
     **本簇的条数只认前缀。**
   - **`hyperframes-animation` 有 122 个文件、含 5 份 GSAP 文档** ——
     这只证明**材料在**，**不证明我已经读过、更不证明我会用**。
     **"索引里有一份" ≠ "我掌握它"。**
2. **有错也照原样记，不许把失败写成成功。** 保留退出码与原始错误文本。
3. **不许把"文件读到了"当"事情办成了"**：读 `adapters/gsap.md` 成功 **≠** 页面动画合格。
   合格要**在浏览器里真跑起来看**（且"我看了一眼"不等于"验过" —— 那是 `gbt-tentacle` 的活儿）。
4. **不许编命令、编路径、编技能名**：本件每条命令要么标 ✅（本机跑过），要么标 **（未验）**。
   **§0.3 那 5 个文件名是逐条 `Test-Path` 验过的**，不是我编的。
5. **不许报凭据细节**：只报**已配 / 未配**或**前 4 位掩码**。
6. **中文口语打不中英文触发词**（✅ 已验，§5 坑 3）：
   `omni ask "给页面加一个滚动触发的动画时间线"` 的候选里 **`gsap-*` 一条都不出现**。
   **这是打分机制，不是"这些技能不存在"** —— 别据此下结论，**直接按名字点名或读 §0.3**。

---

## 5. 本机踩过的坑（照做，别自己解读）

1. 🔴 **本簇是"全桩簇"，四条一个都不是可执行规程。**
   这是本机现读事实，**不是我读错了地方**（✅ `omni list --domain gsap` 报 `design-asset` 通道，
   而 `design-asset` 在 `gbt-omni` 的通道表里定义就是「**料，不是能力**」「**被引用**，不是被调用」）。
   ⇒ **别把"点了名"当成"装上了"。**

2. ✅ **同一批 `gsap-*` 目录在 `.shadow-repo/审美相关skill/skills/` 下还有一份影子副本。**
   `Get-ChildItem -Recurse -Depth 4` 会**同时命中两处**，看起来像"装了两次"。
   ⇒ **数目录数会虚报**；要判"真正有几条"，**看 `state/skill_atlas.json` 的去重后名单**（它记 `roots`）。

3. ✅ **中文提问与英文触发词 n-gram 不重叠 ⇒ 0 分。**
   这四条桩的 `triggers` **全是英文**（`gsap` / `tween` / `easing` / `scrolltrigger` /
   `useGSAP` / `react animation` …）。
   ✅ 实测：`omni ask "给页面加一个滚动触发的动画时间线"` 的候选里，
   **一个 `gsap-*` 都没出现**（该次落到了 `mirror_*` / `cloud_pc` / `health` / `selfscan` 等能力位）。
   而 `omni.py:488-496` 的 `rank()` **只把有命中的 append 进候选** ⇒ **"榜上无" = 0 分**。
   ⇒ **口语打不中时不要怀疑技能不存在，直接点名或读 §0.3。**

4. ✅ **`omni ask` 的候选有上限，看全文再下结论。**
   `omni.py:501` 调 `rank(intent, domain)`（默认 `top=8`）。我实测时曾把输出
   **截到前 25 行**就下结论说"一条都没落到"—— **那是我的截断，不是工具的上限**。

5. ✅ **裸 `python` 在本机是 3.12，不是仓声明的 3.14。**
   `python` → `C:\Python312\python.exe`；`py -3.14` 与 `python3` → **3.14.5**。
   ⇒ **凡是技能文档里写 `python ...` 的，一律改写成 `py -3.14`**，别照抄。
   ⚠️ 这条对本簇尤其相关：`gsap-react` 的"SSR / cleanup"场景要跑构建，
   **用错解释器会让"跑不起来"看起来像"代码坏了"**。

6. 🔴 **本会话的技能目录里看不到这 4 条中的任何一条 —— 两处独立核实过。**
   ① **目录侧**：本会话 `available_skills`（现读）里**没有 `gsap-*`**；
   ② **文件系统侧**：✅ 已验 —— 本会话真正解析的 `.agents` 根**不止一个**：
   `~/.agents/skills`（`gbt-aesthetic` / `hyperframes-animation` / `media-use` … 在这里）、
   `~/.openclaw-autoclaw/workspace/.agents/skills`（`fc-nginx-website` 在这里）、
   以及 `~/.openclaw-autoclaw/agents/<agent>/workspace/.agents/skills`。
   ⇒ **这 4 条在以上任何一个 `.agents` 根里都不存在**（✅ 12 条目标技能命中数为 **0**）。
   ⇒ 而它们所在的 `~/.openclaw-autoclaw/skills`（AGENTS.md 说的"托管目录"）
   **不在那几个 live 根之列** —— 证据：同目录下的 `website-builder` / `autoglm-websearch` /
   `daily-ai-news` / `glmv-pdf-to-web` / `web-search-plus` / `frontend-slides`
   **一个都不在本会话 `available_skills` 里**。
   ⇒ 本件仍按 **AGENTS.md 的托管目录约定**装到 `~/.openclaw-autoclaw/skills/`
   （与已交付的 `gbt-lark` **同款**）。**这是本仓既定做法。**
   🔴 **绝不往任何 `~/.agents/skills/` 写**（那是别家工具的共享目录）。

7. ✅ **`hyperframes-animation`（§0.3 的落点）在 `~/.agents/skills` —— 那条路是 live 的。**
   ⇒ **同一个问题"本机有没有 GSAP 知识"，问 `gsap-*` 的答案是"没有"，问
   `hyperframes-animation` 的答案是"有 5 份文档"。** 两个都真，
   **区别只在"读的哪个根"** —— 这正是 §4 第 1 条要防的那类误读。

---

## 6. 固化位置（**重启后要在**）

| 什么 | 在哪 |
|---|---|
| 本规程（源 · 真身） | `<仓>/skills/gbt-gsap/SKILL.md` |
| 本规程（装机） | `~/.openclaw-autoclaw/skills/gbt-gsap/SKILL.md`（**与源稿逐字节相同**） |
| 被规程管的 4 条能力 | `<仓>/审美相关skill/skills/gsap-{core,timeline,scrolltrigger,react}/SKILL.md`（**四条桩**，**不由本件代管，别改**） |
| **真实现知识**（替代路由） | `~/.agents/skills/hyperframes-animation/`（`adapters/gsap*.md` · `rules/gsap-effects.md` · `rules-index.md`） |
| 能力名册（现读） | `<仓>/state/skill_atlas.json`（`name` 以 `gsap-` 开头） |
| 人话入口 | `py -3.14 tools/codex-scripts/omni.py ask "<一句话>"`；⚠️ 口语打不中时直接点名 |
| 验收 | `py -3.14 tools/codex-scripts/verify-distill.py --cluster gsap` |
| 审美裁决 | `gbt-aesthetic`（**本件不做审美判断**） |

**验收器现状（✅ 已验）**：`--cluster gsap` 现在报
`"omni.py 的 DISTILLED_CLUSTERS 里没登记这个簇"`（`skills_in_atlas: 4`，exit 1）。

🔴 **`omni.py` 的簇登记由主人做，本件不许自登记** ——
要加的一行是主人在 `omni.py` 的 `DISTILLED_CLUSTERS` 表里补的：`"gsap": "gbt-gsap"`。
⚠️ **行号会漂，别记行号**：本次现读该表在 `omni.py:150`，
而**同一次会话里它已经从我最初读到的 143 漂到了 150** ⇒ **只认表名。**
该表现读已有 11 个簇，**本簇不在其中**。**我和本件都无权改 `omni.py`。**

**纪律**：本规程**不代替**这 4 条技能自己的 `SKILL.md`（它们也没有内容可代替）。
上游未装 / 工具没配好，就**如实报"取不到"**，**不许编读数**。
`omni.py` 与 `security/policy.py` **不是本件该动的东西**。

---

## 7. 诚实边界（这段不许删）

1. **本件是"用法规程"，不是"能力已具备"。** 它把 4 条**分簇、点名、定了纪律**；
   **它同时也把"这 4 条不含流程"这件事说清楚了** —— 这是本件最有价值的一句。
2. 🔴 **本簇的真实可执行面 = 0。** 四条**全是目录桩**，**上游未 vendored**。
   "图鉴里有 4 条" **不等于** "4 条都能跑"。**别把"索引过"读成"精通了"。**
   本机真正装着 GSAP 实现知识的是 **`hyperframes-animation`**（**live、122 文件、含 5 份 GSAP 文档**）。
3. **本次实跑的都是只读类动作**：`omni list`、图鉴前缀查询、`verify-distill`、
   目录/文件枚举、`Test-Path`、`--version`。
   **任何 clone 上游、`npm install`、引 CDN、部署上线，本次都没跑** ——
   涉及它们的地方已按 §3.2 标注 **（未验）**。
4. **本机状态是 2026-09-22 的现读快照**（图鉴 `built_at = 2026-09-22T22:16:13`）。
   **换机器、换版本、重跑 `omni build` 后必须重新现读**，别把这份读数当永久事实。
5. **凭据只报"已配/未配"**：本件出现 `sk-a1b2****` 只是**掩码书写示例**，
   **不是**任何真实凭据，本机也没有任何 `gsap-*` 需要 key。
6. **审美判断不在这件里。** 本件只负责"怎么把它们用起来、以及它们其实没内容"；
   "这个动效好不好看 / 节奏对不对 / 有没有 AI 味" **一律回 `gbt-aesthetic`**。
7. ⚠️ **`hyperframes-animation` 的 GSAP 章我只核了"在不在、多大"，没通读。**
   引用它里面的具体 API 细节前，**必须自己把那 5 份文件读了** —— 本件不替它们背书。
