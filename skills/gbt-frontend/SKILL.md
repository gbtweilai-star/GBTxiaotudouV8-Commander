---
name: gbt-frontend
displayName: GBT · 前端技能簇用法规程（frontend-*）
version: 1.0.0
description: GBT小土豆V8 使用前端技能簇（frontend-* 四条：frontend-design / frontend-dev / frontend-skill / frontend-slides）的用法规程。它讲清这四条**怎么用**：谁是完整工作流、谁只是目录桩、在哪个根上读到的是哪一份、怎么按意图分簇点名、两道闸（凭据只报已配未配 + 会改外部/发版/上传的动作必须先问主人）、只读实跑过的命令与真实返回、以及本机已踩过的坑（同一技能名在两处内容不同、桩也是 SKILL.md、中文口语打不中英文触发词）。当用户要做前端落地页/产品页/组件、要把 PPT 转成 HTML 在线演示、要部署演示到公网 URL、要导出 PDF，或按名字点名 frontend-* 却不知道它到底能不能跑时使用。
triggers:
  - "前端"
  - "frontend"
  - "frontend-design"
  - "frontend-dev"
  - "frontend-skill"
  - "frontend-slides"
  - "落地页"
  - "landing page"
  - "产品页"
  - "HTML 演示"
  - "HTML 幻灯片"
  - "PPT 转 HTML"
  - "网页 PPT"
  - "导出 PDF"
  - "部署演示"
---

# GBT · 前端技能簇用法规程（`frontend-*`）

> 开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属
>
> 🔴 **一句边界（先划清）**：本件只管「**这四条前端技能怎么用**」——它们各自是什么、
> 在哪、哪条真能跑、怎么点名、要过哪道闸、产出落在哪。
> **「好不好看 / 有没有 AI 味 / 该选什么审美方向」回 `gbt-aesthetic`**，
> 本件**不做审美判断**，也不重复它的三档转盘与验收清单。
> 三层裁决顺序：**本件管我们的用法纪律** → 各技能自己的 `SKILL.md` 管流程细节 →
> `gbt-aesthetic` 管审美判断。三层都守。

---

## 0. 它是什么 / 在哪 / 哪一份才算数

### 0.1 名单（**以 `state/skill_atlas.json` 里 name 前缀为准**）

现读（2026-09-22 · 图鉴 `built_at = 2026-09-22T22:16:13`）：
**name 以 `frontend-` 开头的，图鉴里正好 4 条**：

| # | 技能名 | 通道 | 本机有没有真内容 |
|---|---|---|---|
| 1 | `frontend-design` | agent-skill | ✅ **有真正文**（审美方向 + 产码要求） |
| 2 | `frontend-dev` | design-asset | ⚠️ **只有目录桩**（指向上游，无流程） |
| 3 | `frontend-skill` | design-asset | ⚠️ **只有目录桩**（指向上游，无流程） |
| 4 | `frontend-slides` | agent-skill | ✅ **有完整工作流**（322 行 + 7 个支撑文件 + 3 个脚本） |

两条交叉核对都指向同一个 4：

```powershell
# ✅ 已验：图鉴口径（前缀 frontend-）
py -3.14 -c "import json;d=json.load(open('state/skill_atlas.json',encoding='utf-8'));print(sorted({s['name'] for s in d['skills'] if s['name'].startswith('frontend-')}))"
# → ['frontend-design', 'frontend-dev', 'frontend-skill', 'frontend-slides']

# ✅ 已验：omni 域口径
py -3.14 tools/codex-scripts/omni.py list --domain frontend
# → agent 技能 6 条：frontend-design / frontend-dev / frontend-skill / frontend-slides
#                    / taste-skill / ui-ux-pro-max
```

🔴 **两个口径不一样，别混**：`omni list --domain frontend` 报的是**整个 `frontend` 职业域**（6 条），
其中 `taste-skill`、`ui-ux-pro-max` **不以 `frontend-` 开头**，**不属本簇**；
本簇的条数**只认前缀**：**4 条**。（这两条同域邻居的用法不在本件范围内。）

验收器也是这么算的（`tools/codex-scripts/verify-distill.py:128-129`：名字以 `簇名-` 开头）。
✅ 已验：`verify-distill.py --cluster frontend` 报 `skills_in_atlas: 4`。

### 0.2 落点：**同一个技能名，在不同根上内容不一样**

✅ 已验（三处逐文件比对，2026-09-22）：

| 技能 | `~/.openclaw-autoclaw/skills`（托管·装机） | `<仓>/审美相关skill/skills`（catalogue） | `~/.claude/skills` |
|---|---|---|---|
| `frontend-design` | **3622 B / 68 行**（无 `triggers`/`od`） | **3853 B / 78 行**（有 `triggers`/`od`） | —— |
| `frontend-dev` | —— | 1214 B（桩） | —— |
| `frontend-skill` | —— | 1170 B（桩） | —— |
| `frontend-slides` | **19654 B / 322 行**（完整工作流） | 1216 B（**桩**） | —— |

🔴 **`frontend-design` 两条副本的正文主体相同，但 frontmatter 不同**（托管那份**没有** `triggers`）。
⇒ **本规程以托管那份（`~/.openclaw-autoclaw/skills/frontend-design/SKILL.md`）为"原文"**，
因为那是按 AGENTS.md 约定装给 agent 读的那一份；同时把"另一处有分叉"记在这里，**不许假装只有一份**。

🔴 **`frontend-slides` 更要命**：托管目录那份是**完整工作流**，`审美相关skill/skills` 那份是**桩**。
⇒ **按名字点名 `frontend-slides` 时，你拿到哪一份完全取决于是谁在哪个根上解析它**。
本机能跑的那一份**只在** `~/.openclaw-autoclaw/skills/frontend-slides/`。

### 0.3 `frontend-slides` 的完整资产（✅ 已验，逐文件列过）

```
SKILL.md 19654B · STYLE_PRESETS.md 8202B · viewport-base.css 4037B
html-template.md 12535B · animation-patterns.md 4030B · README.md 6686B · LICENSE 1067B
scripts/extract-pptx.py 2917B · scripts/deploy.sh 8077B · scripts/export-pdf.sh 13615B
.claude-plugin/marketplace.json · plugins/frontend-slides/.claude-plugin/plugin.json
_store_meta.json
```

**没有 `viewport-base.css` 就没有合规的幻灯片** —— SKILL.md 原文写着
「**When generating, read `viewport-base.css` and include its full contents in every presentation.**」，
且「Every `.slide` must have `height: 100vh; height: 100dvh; overflow: hidden;`」是 **NON-NEGOTIABLE**。

---

## 1. 按意图分簇（**4 条一条不漏**）

### 1.1 总则

**先判断"这条有没有真内容"再决定要不要点名。** 上表已给答案：
`frontend-dev` 与 `frontend-skill` **本机只有桩** ⇒ **点名它们等于点名一个"上游在哪"的便条**。

### 1.2 簇 A · 定方向 + 产码（真能干活的）

| 技能 | 什么时候用它 |
|---|---|
| **`frontend-design`** | **要"有设计观点"的前端代码时用它**。它先逼你定一条**极端的美学方向**（brutally minimal / maximalist chaos / retro-futuristic / editorial / brutalist / art deco …），再按 Typography / Color / Motion / Spatial / Backgrounds 五节给要求，并明令禁止 Inter/Roboto/Arial、禁止紫渐变白底、**禁止跨次收敛到 Space Grotesk**。产物是**真能跑的代码**（HTML/CSS/JS、React、Vue 等）。⚠️ 它列的"Never use / 该选什么"是**它自己的美学主张**；**冲突时审美裁决回 `gbt-aesthetic`**。 |

### 1.3 簇 B · 出演示件（一条走完全流程的产线）

| 技能 | 什么时候用它 |
|---|---|
| **`frontend-slides`** | **要"能在浏览器里放的演示"时用它**：从零做 HTML 演示，或**把 .pptx 转成 HTML**，或**改一份已有的 HTML 演示**。它是**六阶段产线**：Phase 0 判模式（A 新建 / B PPT 转换 / C 增强）→ Phase 1 内容发现（**一次性问齐**目的/篇幅/内容/是否要浏览器内编辑）→ Phase 1.2 图片评估（真读图并判 USABLE / NOT USABLE）→ Phase 2 风格发现（**先给 3 张单页预览让人挑**，不给抽象选项）→ Phase 3 生成（单文件、内联 CSS/JS、**必须内嵌 viewport-base.css 全文**）→ Phase 4 PPT 转换 → Phase 5 交付 → Phase 6 分享（部署公网 URL 或导出 PDF，**见 §3 闸二**）。**零依赖**是它的硬口径：单 HTML 文件、不用 npm、不用构建工具。 |

**Phase 0 的模式判据（照原文）**：用户要"从零做一个" → Mode A；给的是 `.pptx` → Mode B；
给的是"已有 HTML 要改好" → Mode C。**Mode C 有专门的改动规则**：
加内容前先按密度上限点数、加图必须 `max-height: min(50vh, 400px)`、超限就**主动拆页**别等人问。

### 1.4 簇 C · 只有索引、没有流程（**点名前先知道这一点**）

| 技能 | 什么时候用它（在"只有桩"的前提下） |
|---|---|
| **`frontend-dev`** | **当你要找"上游那份完整工作流"的入口时用它**。本机这份的正文只有三件事：它是什么（全栈前端 + 电影级动画 + 走 **MiniMax API** 生图/生视频 + 生成艺术，适合 hero 页与展示站）、上游在哪（`https://github.com/MiniMax-AI/skills`）、以及**一段"要把上游 bundle 装到你 agent 的 skills 目录才能跑完整流程"的说明**。🔴 **本来要告诉它"用 MiniMax 生成媒体"之前，先看 §3 闸一**（那会调用外部 API）。 |
| **`frontend-skill`** | **当你要找 OpenAI 那套"克制构图"的前端 playbook 入口时用它**。本机这份的正文同样只有：它是什么（用**克制的构图**做视觉强的落地页/网站/App UI，OpenAI 生产前端 playbook）、上游在哪（`https://github.com/openai/skills`）、以及同样那段"装上游 bundle"的说明。**它给的"restrained composition"是方向词，不是可执行步骤。** |

🔴 **诚实条款**：本机**没有** vendored 上游 bundle。
`frontend-dev` / `frontend-skill` 的**真正工作流不在本机** ——
本件**不假装**它们能跑，也**不许**为了"让它能跑"就私自 `git clone` 上游（见 §3 闸二）。

---

## 2. 两道闸（顺序不能颠倒）

### 闸一 · 凭据闸（**只报"已配 / 未配"，绝不贴值**）

✅ 已验（2026-09-22 现读）：

| 这条技能 | 需要什么凭据 | 本机状态 |
|---|---|---|
| `frontend-design` | **不需要**任何 API key（纯产码） | ✅ 无凭据需求 |
| `frontend-slides` | **本地产线不需要 key**；但 **Phase 6A 部署要 Vercel 账号**（是账号/登录，不是 key） | ⚠️ `vercel` **不在 PATH** ⇒ 未登录、未装 |
| `frontend-dev` | 上游工作流要 **MiniMax API**（生成媒体） | ⚠️ **本机未配 · 上游未装 ⇒ 无法核对** |
| `frontend-skill` | 上游未装 ⇒ 无从判断 | ⚠️ **未知**（不编） |

**凭据纪律（硬）**：

1. 🔴 **不许把任何 key / token 写进文件、聊天、规程、日报**。
2. 要给人看**只报**「**已配 / 未配**」或**前 4 位掩码**（例 `sk-a1b2****`）。
3. 🔴 **不许为一个"目录桩"去配它上游的 key** —— 那等于替上游做了它没做的事。
4. `frontend-slides` 的 Phase 6A 若涉及 Vercel token / 环境变量：**同样只报已配/未配**。

### 闸二 · 会改外部 / 发版 / 上传 / 装东西的动作 —— **必须先问主人**

**本条高于技能自己的流程。** 理由：`frontend-slides` 的 Phase 4/6 **自带"装东西"和"发到公网"两步**，
而它的 SKILL.md **把这两步写成了流程的正常环节**（"install python-pptx if needed"、
"installs if not"、"Deploy to a live URL"）—— **文档写得顺，不等于我们可以自动做**。

**算"改外部 / 发版 / 上传 / 装东西"的动作**（一律先问主人）：

| 动作 | 出处 | 为什么必须先问 |
|---|---|---|
| **部署演示到公网 URL**（Vercel） | `frontend-slides` Phase 6A：`bash scripts/deploy.sh <path>` | **发版 / 上传**：链接公开可访问、可被转发；**默认永久在线**直到主人去 Vercel 控制台删项目 |
| **导出 PDF**（要装 Playwright + 下 Chromium ~150MB） | Phase 6B：`bash scripts/export-pdf.sh` | **改本机**：装包 + 下载浏览器，落在临时目录 |
| **装 `python-pptx`** | Phase 4：`python scripts/extract-pptx.py ...`（原文写 "install python-pptx if needed"） | **改本机**：`pip install` 改环境 |
| **装 Vercel CLI** | Phase 6A：原文写 "Checks if Vercel CLI is installed (**installs if not**)" | **改本机 + 联网**：`deploy.sh` 自己会装 |
| **`npx vercel --version` / `npx vercel whoami`** | Phase 6A 第 1、2 步 | **联网下载包**（npx 首次会拉）；且 whoami 暴露账号身份 |
| **跑 `scripts/setup.py` 类向导** | （本簇无；见 `gbt-web`） | 会**落盘凭据** |

**顺序（先干什么 → 拿什么回执）**：

1. **摊开四件事**：**身份/账号**（用谁的 Vercel 账号）· **目标**（哪个文件/哪个目录，
   **指名道姓**）· **内容**（要发出去的是哪一版演示）· **影响面**（链接谁能看、能不能撤回、删了能不能恢复）。
2. **先跑不写外部的部分**：Phase 0–5 全是**本地**动作（问齐 → 读图 → 生成 HTML → 本地打开），
   **可以做完**。**不要**因为"反正要问"就跳过产线直接问部署。
3. **等一次明确同意**：**只覆盖这一条**（"这次发这个"≠"以后这类都发"）。
   **主人没回话 = 没同意，停。**
4. **同意后才动手**，并按需取回执：
   - 部署：拿到 **live URL**；
   - PDF：拿到**文件路径 + 文件大小**。
5. **失败就记失败**：原样保留错误（如 Playwright 装不上、Chromium 下载失败），
   **不许把失败写成成功**（见 §4）。
6. **部署后必须自检**（原文明确要求）：**打开部署出来的 URL，确认所有图片都加载**。
   本地图片靠 `src="..."` 自动打包，**CSS `background-image` 或怪路径会漏** ——
   资产多时**优先部署整个文件夹**而不是单个 HTML。

---

## 3. 只读实跑过的命令与真实返回（**未验的已标**）

### 3.1 ✅ 已验（本机真跑过，返回照抄）

| 命令 | 关键返回 | 判定 |
|---|---|---|
| `py -3.14 tools/codex-scripts/omni.py list --domain frontend` | 能力位 0 条；agent 技能 **6 条**（含 2 条同域邻居） | ✅ 域口径 |
| `py -3.14 -c "…startswith('frontend-')"` | `['frontend-design','frontend-dev','frontend-skill','frontend-slides']` | ✅ 簇口径 = **4** |
| `py -3.14 tools/codex-scripts/verify-distill.py --cluster lark` | `verdict: PASS` · `skills_covered 28/28` · `identical: true` · exit **0** | ✅ 验收器本身可用（对照件） |
| `py -3.14 tools/codex-scripts/verify-distill.py --cluster frontend` | `fail: ["omni.py 的 DISTILLED_CLUSTERS 里没登记这个簇"]` · `skills_in_atlas: 4` · exit **1** | ⚠️ **需主人登记**（§6） |
| `py -3.14 -c "import pptx"` | `ModuleNotFoundError` | ✅ **`python-pptx` 未装** |
| `python3 -c "import sys;print(sys.executable,sys.version)"` | `C:\Users\ADMIN\AppData\Local\Python\pythoncore-3.14-64\python.exe` · `3.14.5` | ✅ `python3` **是真解释器**，不是 Store 占位 |
| `node --version` / `npm --version` / `git --version` | `v24.15.0` / `11.12.1` / `2.55.0.windows.3` | ✅ 都在 |
| `Get-Command vercel` | **不在 PATH** | ✅ **未装/未登录** |
| `bash --version` | `GNU bash, version 5.3.9(1)-release (x86_64-pc-linux-gnu)` | ✅ 是 **WSL 的 Linux bash**（⚠️ 冷启动 **>8s**，25s 内返回） |
| `bash -lc "pwd"` | `/mnt/c/Users/ADMIN/Desktop/GBT灏忓湡璞哣8`（**乱码**） | 🔴 **中文路径在 WSL 侧读成乱码**（§5 坑 3） |

### 3.2 ⚠️ 未验（**没跑，不许说成跑过**）

| 命令 | 为什么没验 |
|---|---|
| `bash scripts/deploy.sh <path>` | **发版**（§2 闸二）——需主人同意 |
| `bash scripts/export-pdf.sh <path>` | 会装 Playwright + 下 Chromium（**改本机**）——需主人同意 |
| `python scripts/extract-pptx.py <in.pptx> <out>` | `python-pptx` 未装；装上属改本机 |
| `npx vercel --version` / `npx vercel whoami` | 联网拉包 + 暴露账号 |
| 上游 `frontend-dev`（MiniMax）/ `frontend-skill`（OpenAI）任何命令 | **上游未 vendored**，本机没有可跑的东西 |
| Phase 3 真生成一份演示 | 属产出动作，本件只定纪律不代跑 |

---

## 4. 🔴 报告层红线（读数纪律）

1. **读数先问一句：这是事实，还是我读错了地方？**
   本簇有**三个专门会给你"对的形状 + 错的内容"的地方**：
   - **同一个技能名在两处内容不同**（`frontend-design` 3622 vs 3853；`frontend-slides` 19654 vs 1216）
     ⇒ 报"我读了 `frontend-slides`"之前**先说清读的是哪个根**；
   - **桩也是 `SKILL.md`**：文件存在 **≠** 有流程。判据是正文里有没有真步骤
     （本机 4 条里 `frontend-dev` / `frontend-skill` **只有桩**）；
   - **`omni list --domain frontend` = 6 条 ≠ 本簇 4 条**：域口径与前缀口径**不是一回事**。
2. **有错也照原样记，不许把失败写成成功。** 保留退出码与原始错误文本。
3. **不许把"命令跑通了"当"事情办成了"**：Phase 5 的 `open [filename].html` **成功只说明本机打开了**，
   **不等于**演示合格；合格要看 §7 的验收口径。
4. **不许编命令、编路径、编技能名**：本件每条命令要么标 ✅（本机跑过），要么标 **（未验）**。
5. **不许报凭据细节**：只报**已配 / 未配**或**前 4 位掩码**。
6. **中文提问打不中英文触发词**（✅ 已验，§5 坑 4）：`omni ask "帮我做一个前端的落地页，要有冲击力"`
   的候选里 **`frontend-*` 一条都不出现**。**这是打分机制，不是"这些技能不存在"** —— 别据此下结论。

---

## 5. 本机踩过的坑（照做，别自己解读）

1. ✅ **`omni ask` 的候选是有上限的，且只列"有命中"的。**
   `omni.py:501` 调 `rank(intent, domain)`（默认 `top=8`），`omni.py:488-496` 里
   **只有 `hit` 非空才 append**。所以"榜上没有"= **0 分**，不是"被截断"。
   我实测时曾把输出**截到前 25 行**就下结论说"一条都没落到" —— **那是我的截断，不是工具的上限**。
   ⇒ **看全文再下结论。**

2. ✅ **中文口语 vs 英文触发词，n-gram 不重叠 ⇒ 0 分。**
   `frontend-*` 的 `triggers` 全是英文（`frontend design` / `landing page` / `html slides` …
   —— `frontend-design` 托管那份**连 `triggers` 都没有**）。
   ✅ 实测：`"帮我做一个前端的落地页，要有冲击力"` → **12 条一条不出现**；
   但 `"把 PPT 转成 HTML 幻灯片在线分享"` → **命中 `frontend-slides`**。
   ⇒ **口语打不中时不要怀疑技能不存在，直接按名字点名。**

3. ✅ **WSL 的 bash 读中文路径是乱码。**
   `bash -lc "pwd"` 在 `<仓>` 里返回 `/mnt/c/Users/ADMIN/Desktop/GBT灏忓湡璞哣8`。
   加 `LANG=C.UTF-8` **也一样乱**（试过）。
   ⇒ **给 `deploy.sh` / `export-pdf.sh` 传参时，尽量用"切到目录后传相对路径"**，
   别把中文绝对路径塞进 bash 命令行；实在要传，**先自己确认脚本收到的是不是那个文件**。

4. ✅ **`bash --version` 冷启动 8s 内不返回。** 第一次 8s 限时判"不可用"是**误判**；
   放到 25s 就正常返回 `GNU bash 5.3.9`。⇒ **WSL 首个命令要给它冷启动时间**，
   别用 3-8 秒的短超时判"没装"。

5. ✅ **`python3` 在本机是真 3.14.5，不是 Store 占位。**
   `python3 -c "import sys;print(sys.executable)"` → `…\pythoncore-3.14-64\python.exe`。
   ⚠️ 但**裸 `python`** 指向 `C:\Python312\python.exe`（**3.12**，与仓声明口径 3.14 **不同**）。
   ⇒ 技能文档里写的 `python scripts/...` **一律改写成 `py -3.14`**，别照抄。

6. ✅ **`vercel` 不在 PATH ⇒ Phase 6A 的第一步就走不通。**
   原文说"没装就先装 Node.js"—— 本机 Node **已有**（v24.15.0），
   缺的是 **Vercel CLI 本身 + 登录**。**这一步要联网 + 要账号 ⇒ 过 §2 闸二。**

7. ✅ **`python-pptx` 未装 ⇒ Mode B（PPT 转换）现在跑不了。**
   装上属"改本机"⇒ 过闸二。**没装就别承诺"能转 PPT"。**

8. ⚠️ **（未验）`deploy.sh` / `export-pdf.sh` 在 WSL bash 下的真实行为。**
   两个脚本是 `#!/usr/bin/env bash`，本机 `.sh` 只能走 WSL。
   **本次没跑**（发了会发版、导了会装浏览器）。**规程不替它们的行为背书。**

9. 🔴 **本会话的技能目录里看不到这 4 条中的任何一条 —— 而且这是两处独立核实过的。**
   ① **目录侧**：本会话 `available_skills`（现读）里**没有 `frontend-*`**；
   ② **文件系统侧**：✅ 已验 —— 本会话真正解析的 `.agents` 根**不止一个**：

   | live 根（✅ 逐条验过它里面有哪些本会话可见的技能） | 例 |
   |---|---|
   | `~/.agents/skills` | `gbt-aesthetic` · `gbt-arkcli` · `gbt-omni` · `gbt-tentacle` · `hyperframes-animation` · `media-use` |
   | `~/.openclaw-autoclaw/workspace/.agents/skills` | `fc-nginx-website` |
   | `~/.openclaw-autoclaw/agents/<agent>/workspace/.agents/skills` | `fc-nginx-website`（同一条在多个 agent 工作区各一份） |

   ⇒ **这 4 条在以上任何一个 `.agents` 根里都不存在**（✅ 已验：12 条目标技能在全部
   `.agents` 根里命中数为 **0**）。
   ⇒ 而它们所在的 `~/.openclaw-autoclaw/skills`（AGENTS.md 说的"托管目录"）
   **不在上面那几个 live 根之列** —— 证据：同一目录下的 `website-builder` /
   `autoglm-websearch` / `daily-ai-news` / `glmv-pdf-to-web` / `frontend-slides` / `web-search-plus`
   **一个都不在本会话 `available_skills` 里**。
   ⇒ 本件仍按 **AGENTS.md 的托管目录约定**装到 `~/.openclaw-autoclaw/skills/`
   （与已交付的 `gbt-lark` **同款**：`gbt-lark` 也只在 `~/.openclaw-autoclaw` + 仓 `skills/`，
   同样不在 `available_skills` 里）。**这是本仓既定做法，不是本件标新立异。**
   🔴 **绝不往任何 `~/.agents/skills/` 写**（那是别家工具的共享目录）。

---

## 6. 固化位置（**重启后要在**）

| 什么 | 在哪 |
|---|---|
| 本规程（源 · 真身） | `<仓>/skills/gbt-frontend/SKILL.md` |
| 本规程（装机） | `~/.openclaw-autoclaw/skills/gbt-frontend/SKILL.md`（**与源稿逐字节相同**） |
| 被规程管的 4 条能力 | `frontend-design` · `frontend-slides` 在 `~/.openclaw-autoclaw/skills/`；`frontend-dev` · `frontend-skill` 只在 `<仓>/审美相关skill/skills/`（**桩**）。**不由本件代管，别改** |
| 能力名册（现读） | `<仓>/state/skill_atlas.json`（`name` 以 `frontend-` 开头） |
| 人话入口 | `py -3.14 tools/codex-scripts/omni.py ask "<一句话>"`；⚠️ 口语打不中时直接点名 |
| 验收 | `py -3.14 tools/codex-scripts/verify-distill.py --cluster frontend` |
| 审美裁决 | `gbt-aesthetic`（**本件不做审美判断**） |

**验收器现状（✅ 已验）**：`--cluster frontend` 现在报
`"omni.py 的 DISTILLED_CLUSTERS 里没登记这个簇"`（`skills_in_atlas: 4`，exit 1）。

🔴 **`omni.py` 的簇登记由主人做，本件不许自登记** ——
要加的一行是主人在 `omni.py` 的 `DISTILLED_CLUSTERS` 表里补的：
`"frontend": "gbt-frontend"`。
⚠️ **行号会漂，别记行号**：本次现读该表在 `omni.py:150`，
而**同一次会话里它已经从我最初读到的 143 漂到了 150** ⇒ **只认表名 `DISTILLED_CLUSTERS`。**
该表现读**已有 11 个簇**（`arkcli` / `lark` / `fal` / `autoglm` / `figma` / `design` /
`autoclaw` / `sandbox` / `pptx` / `youtube` / `video`），**本簇不在其中**。
**我和本件都无权改 `omni.py`。**

**纪律**：本规程**不代替**这 4 条技能自己的 `SKILL.md`。
上游未装 / 工具没配好，就**如实报"取不到"**，**不许编读数**。
`omni.py` 与 `security/policy.py` **不是本件该动的东西**。

---

## 7. 诚实边界（这段不许删）

1. **本件是"用法规程"，不是"能力已具备"。** 它把 4 条**分簇、点名、定了纪律**；
   **每条技能的深度流程以它自己的 `SKILL.md` 为准**，本件**不替代**。
2. **本簇的真实可执行面只有 2 条**：`frontend-design`（真正文）与
   `frontend-slides`（完整工作流）。**`frontend-dev` / `frontend-skill` 本机只有桩** ——
   "图鉴里有 4 条" **不等于** "4 条都能跑"。**别把"索引过"读成"精通了"。**
3. **本次实跑的都是只读/读文件类动作**：`omni list`、图鉴前缀查询、`verify-distill`、
   `import pptx`、`--version`、`Get-Command`、目录枚举。
   **任何部署、导出 PDF、装包、PPT 转换、真生成演示，本次都没跑** ——
   涉及它们的地方已按 §3.2 标注 **（未验）**。
4. **本机状态是 2026-09-22 的现读快照**（图鉴 `built_at = 2026-09-22T22:16:13`）。
   **换机器、换版本、重跑 `omni build` 后必须重新现读**，别把这份读数当永久事实。
5. **凭据只报"已配/未配"**：本件出现 `sk-a1b2****` 只是**掩码书写示例**，
   **不是**任何真实凭据，本机也没有任何 `frontend-*` 需要 key。
6. **审美判断不在这件里。** 本件只负责"怎么把它们用起来"；
   "好不好看 / 有没有 AI 味 / 该往哪个方向走" **一律回 `gbt-aesthetic`**。
