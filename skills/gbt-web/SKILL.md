---
name: gbt-web
displayName: GBT · Web 技能簇用法规程（web-*）
version: 1.0.0
description: GBT小土豆V8 使用 Web 技能簇（web-* 四条：web-artifacts-builder / web-design-guidelines / web-perf / web-search-plus）的用法规程。先把一句扫兴的话说清——这四条名字里都有 web，但**它们不是一类东西**：两条是本机目录桩（只有 SKILL.md、指向上游），web-perf 是完整性能体检流程但前置的 chrome-devtools MCP 本机没配（跑不了），web-search-plus 是能真跑的多provider检索但有 5 个 API key 全未配。规程含：逐条点名与按意图分簇、两道闸（凭据只报已配未配 + 装包/配 key/起容器/部署上线必须先问主人）、只读实跑过的命令与真实返回（含 --explain-routing 的"形状对内容空"陷阱）、报告层红线、以及本机已踩过的坑。当用户要审计网页性能与 Core Web Vitals、要按 Vercel/Anthropic 的规约做产品 UI、要建可嵌入的 React+Tailwind artifact、或要换检索 provider 时使用。
triggers:
  - "web"
  - "web-artifacts-builder"
  - "web-design-guidelines"
  - "web-perf"
  - "web-search-plus"
  - "网页性能"
  - "性能审计"
  - "Core Web Vitals"
  - "LCP"
  - "CLS"
  - "Lighthouse"
  - "核心网页指标"
  - "设计规约"
  - "Vercel 设计"
  - "artifact"
  - "多provider检索"
  - "换搜索源"
---

# GBT · Web 技能簇用法规程（`web-*`）

> 开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属
>
> 🔴 **一句边界（先划清）**：本件只管「**这四条 `web-*` 技能怎么用**」——它们是什么、在哪、
> **能不能跑**、怎么点名、要过哪道闸、产出长什么样。
> **「这个页面好不好看 / 该走什么审美方向」回 `gbt-aesthetic`**，本件**不做审美判断**。
> ⚠️ **特别注意**：`web-design-guidelines` 里带的是 **Vercel 的"规约"**，
> 那是**工程规约（布局/字体/色彩/动效/无障碍的可判定条款）**，**不是审美裁决**——
> 它与 `gbt-aesthetic` 相遇时：**规约看 `web-design-guidelines`，好看与否看 `gbt-aesthetic`**。
> 三层裁决顺序：**本件管我们的用法纪律** → 各技能自己的 `SKILL.md` 管流程细节 → `gbt-aesthetic` 管审美。

---

## 0. 先把丑话说前面：**这四条不是一类东西**

### 0.1 名单（**以 `state/skill_atlas.json` 里 name 前缀为准**）

现读（2026-09-22 · 图鉴 `built_at = 2026-09-22T22:16:13`）：
**name 以 `web-` 开头的，图鉴里正好 4 条**：

| # | 技能名 | 通道 | 本机内容（✅ 已验） | 能不能跑 |
|---|---|---|---|---|
| 1 | `web-artifacts-builder` | design-asset | ⚠️ **桩** 1327 B，只有 `SKILL.md` | ❌ **上游未装的桩** |
| 2 | `web-design-guidelines` | design-asset | ⚠️ **桩** 1253 B，只有 `SKILL.md` | ❌ **上游未装的桩** |
| 3 | `web-perf` | agent-skill | ✅ **真正文** 8198 B / 201 行（在 `~/.claude/skills`） | ⚠️ **前置闸不过 ⇒ 现在跑不了**（§0.3） |
| 4 | `web-search-plus` | agent-skill | ✅ **真实现** v2.7.2（在 `~/.openclaw-autoclaw/skills`）：`SKILL.md` 8802 B + **12 个文件**，含 `scripts/search.py` **84040 B**、`scripts/setup.py` 17036 B、`config.example.json` 4972 B | ⚠️ **程序能跑，但 5 个 provider key 全未配 ⇒ 真检索跑不了**（§0.4） |

两个口径交叉核对都指向同一个 4：

```powershell
# ✅ 已验：图鉴口径（前缀 web-）
py -3.14 -c "import json;d=json.load(open('state/skill_atlas.json',encoding='utf-8'));print(sorted({s['name'] for s in d['skills'] if s['name'].startswith('web-')}))"
# → ['web-artifacts-builder', 'web-design-guidelines', 'web-perf', 'web-search-plus']

# ✅ 已验：omni 域口径
py -3.14 tools/codex-scripts/omni.py list --domain web
# → 能力位 0 条；agent 技能 11 条
```

🔴 **两个口径差得很远，别混**：`omni list --domain web` 报 **11 条**（整个 `web` 职业域），
而本簇**只认前缀 = 4 条**。域里那另外 7 条 **不以 `web-` 开头 ⇒ 不属本簇**，
它们的用法不在本件范围内（下面 §0.5 只做"划清边界"的点名，不展开）：

`academic-deep-research` · `autoglm-websearch` · `daily-ai-news` · `frontend-design` ·
`frontend-slides` · `glmv-pdf-to-web` · `website-builder`

（✅ 已验：这 7 条**全部只装在 `~/.openclaw-autoclaw/skills`**；
其中 `frontend-design` / `frontend-slides` 归 `gbt-frontend` 管。）

验收器也按前缀算（`tools/codex-scripts/verify-distill.py:128-129`）。

### 0.2 两条桩：`web-artifacts-builder` 与 `web-design-guidelines`

✅ 已验：两条**各只有一个 `SKILL.md`，无脚本、无 `references/`**，正文是目录索引式的三段：
它是什么 → 上游在哪 → "要跑完整上游工作流，得把上游 bundle 装到你的 skills 目录"。

- `web-artifacts-builder` → 上游 `https://github.com/anthropics/skills/tree/main/web-artifacts-builder`
  （`od.mode: prototype` · `od.category: web-artifacts`）
- `web-design-guidelines` → 上游 `https://github.com/vercel-labs/skills`
  （`od.mode: design-system` · `od.category: design-systems`）

🔴 **结论**：**点名这两条，本机给你的是"上游入口"，不是规约正文、不是工作流。**
本件**不假装**它们能跑，也**不许**为了"让它能跑"就私自 `git clone`（§2 闸二）。

### 0.3 `web-perf`：**流程是真的，前置闸现在过不去**

✅ 已验：`~/.claude/skills/web-perf/SKILL.md` = **8198 B / 201 行 真正文**。
它是一份**五阶段性能体检流程**：Phase 1 采性能 trace → Phase 2 分析 Core Web Vitals
→ Phase 3 网络分析 → Phase 4 无障碍快照 → Phase 5 代码库分析（第三方站点可跳）。

🔴 **但它的第一步就是"先确认工具在不在"**，原文照抄：
> "**FIRST: Verify MCP Tools Available** — **Run this before starting.**
> Try calling `navigate_page` or `performance_start_trace`.
> **If unavailable, STOP** — the chrome-devtools MCP server isn't configured."

✅ 已验（2026-09-22 现读）：**本机没有配 chrome-devtools**。
- `config/mcporter.json` 的 `mcpServers` 是：
  `autoclaw-productivity` · `autoclaw-github` · `notion` · `connector:cloudflare` · `connector:vercel`
  —— **没有 `chrome-devtools`**；
- 在 `config/` · `.openclaw/` · `.autoclaw/` 里搜 `chrome-devtools` 字样：**0 命中**；
- `AGENTS.md` 的 MCP 段也自报 **"No MCP tools are currently healthy."**

⇒ 🔴 **`web-perf` 现在跑不了**，按它原文就该 **STOP**，不该往下编读数。
它的 SKILL.md 给了修法（加一份 MCP 配置 + `npx -y chrome-devtools-mcp@latest`）——
**那要起进程/拉包 = 改本机，过 §2 闸二。**

⚠️ **且它的所有工具调用名（`navigate_page` / `performance_start_trace` /
`performance_analyze_insight` / `list_network_requests` / `get_network_request` / `take_snapshot`）
是 MCP 工具名，不是本机命令。** 本会话里**一个都没有** ——
**别把这些名字当命令跑**（§5 坑 2）。

### 0.4 `web-search-plus`：**能跑的是程序，不是检索**

✅ 已验（2026-09-22 现读）：

| 项 | 值 |
|---|---|
| 版本 | `version: 2.7.2`（frontmatter） |
| 落点 | `~/.openclaw-autoclaw/skills/web-search-plus/`（**12 个文件**） |
| 主程序 | `scripts/search.py` **84040 B** |
| 前置声明 | `metadata.openclaw.requires.bins = ["python3","bash"]`；`env` 列 5 个 key，**全标 `optional`**，附注 `"Only ONE provider key needed. All are optional."` |
| 支持的 provider | **5 个**：Serper（Google）· Tavily（研究）· Exa（神经/相似）· You.com（实时/RAG）· SearXNG（隐私/自托管） |
| **凭据状态** | 🔴 `config.json` **不存在**、`.env` **不存在**；`SERPER_API_KEY` / `TAVILY_API_KEY` / `EXA_API_KEY` / `YOU_API_KEY` / `SEARXNG_INSTANCE_URL` **全部：未配** |
| 离线能力 | ✅ **有**：`--explain-routing` 不需要 key（§3） |

🔴 **`web-search-plus` 是一条"检索"能力，不是"做网页"的能力** ——
它在 `web-` 前缀里是**因为名字**，不是因为职责。**别把它当前端技能用。**

⚠️ **边界（本会话已有更好的东西）**：本会话**自带 `web_search` 与 `web_fetch` 工具**，
**不需要 key、不需要装东西**。⇒ **默认走内置工具**；
只有当你要**指定 provider**（比如"用 Exa 找相似公司""用 SearXNG 隐私搜"）
或要它的 `--explain-routing` 时，才考虑 `web-search-plus`（**且要先配 key，过闸二**）。

⚠️ **它自己的一条纪律（原文照抄）**：`"Tavily, Serper, and Exa are NOT core OpenClaw providers.
❌ Don't modify ~/.openclaw/openclaw.json for these ✅ Use this skill's scripts"`。
✅ 已验：**`~/.openclaw/openclaw.json` 在本机根本不存在** ⇒ 这条"别乱改配置"的告警**在本机暂时无对象**，
但**纪律照样守**：走 skill 自己的脚本 / 环境变量，**别去动全局配置**。

### 0.5 划清边界（点名但不展开）

| 邻居 | 归属 | 一句话边界 |
|---|---|---|
| `website-builder` | 同域 · **非 `web-` 前缀** | 名字最像，**但不属本簇**。它指向上游的 "全站生成" 工作流，**也不在本会话技能目录里**。 |
| `fc-nginx-website` | **live 根**（`~/.openclaw-autoclaw/workspace/.agents/skills/fc-nginx-website`） | **上线托管规矩**（nginx 静态预览）。**要"部署上线"时，它的规矩优先于本件** —— 本件只管"点名哪条 web-* 技能"，不管"发到哪台机器上合不合规"。 |
| `frontend-design` / `frontend-slides` | 同域 · 归 `gbt-frontend` | 做落地页 / HTML 演示找它们。 |
| `glmv-pdf-to-web` | 同域 · 非前缀 | PDF → 网页。**本簇不管**。 |
| `autoglm-websearch` / `daily-ai-news` / `academic-deep-research` | 同域 · 非前缀 | 都是检索/资讯类。**与 `web-search-plus` 职责重叠** —— 选哪条见 §1.4。 |

---

## 1. 按意图分簇（**4 条一条不漏**）

**选路总则**：**先看"这条有没有真内容"**（§0.1 的表已给答案），再决定要不要点名。

### 1.1 簇 A · 产件：可嵌入的 React + Tailwind artifact

| 技能 | 什么时候用它（在"只有桩"的前提下） |
|---|---|
| **`web-artifacts-builder`** | **要按 Anthropic 的参考工作流做"复杂 claude.ai HTML artifact"时点名它**。它自报的边界是：**React + Tailwind** 建富交互、可嵌入的 artifact。⚠️ **本机这份不含工作流** ⇒ 它实际给你的是上游坐标。**要真动手：本机没有它的实现面**，得按 §2 闸二先问主人要不要装上游。 |

### 1.2 簇 B · 规约：产品 UI 的工程条款

| 技能 | 什么时候用它（在"只有桩"的前提下） |
|---|---|
| **`web-design-guidelines`** | **要在动手前对齐"可判定的工程条款"时点名它**（Vercel 工程团队口径，覆盖 **layout / typography / color / motion / accessibility**）。⚠️ **本机这份不含条款正文** ⇒ 它给你的是上游坐标（`vercel-labs/skills`）。🔴 **它管的是"规约"，不是"审美"**：条款能判"有没有做"（对比度够不够、焦点环在不在），**判不了"好不好看"** —— 后者回 `gbt-aesthetic`。 |

### 1.3 簇 C · 体检：性能与 Core Web Vitals

| 技能 | 什么时候用它 |
|---|---|
| **`web-perf`** | **要"审计 / profile / 优化页面加载性能、Lighthouse 分、站点速度"时用它**（它自己的触发语：`audit, profile, debug, or optimize page load performance, Lighthouse scores, or site speed`）。它给的是一份**五阶段清单 + 明确阈值**（见 §1.3.1）+ **报告格式**（CWV 汇总表 → Top Issues → 建议 → 代码库发现）。🔴 **但现在跑不了**（§0.3：前置 MCP 未配）。 |

#### 1.3.1 `web-perf` 的阈值表（**照它原文抄，本机未跑过、未复核**）

| 指标 | good / needs-improvement / poor |
|---|---|
| TTFB | < 800 ms / < 1.8 s / > 1.8 s |
| FCP | < 1.8 s / < 3 s / > 3 s |
| **LCP** | **< 2.5 s** / < 4 s / > 4 s |
| **INP** | **< 200 ms** / < 500 ms / > 500 ms |
| TBT | < 200 ms / < 600 ms / > 600 ms |
| **CLS** | **< 0.1** / < 0.25 / > 0.25 |
| Speed Index | < 3.4 s / < 5.8 s / > 5.8 s |

🔴 **这张表是"技能里写的"，不是"我在本机量出来的"** ——
它自己开篇就警告："Your knowledge of web performance metrics, thresholds, and tooling APIs
**may be outdated. Prefer retrieval over pre-training**"，
并列了三个取数源（`web.dev/articles/vitals` · `developer.chrome.com/docs/devtools/performance` ·
`developer.chrome.com/docs/lighthouse/performance/performance-scoring`）。
⇒ **引用具体阈值前先按它的要求去取最新文档**，别拿这张表当权威（§4）。

#### 1.3.2 `web-perf` 的行为纪律（照原文，很硬，值得单独列）

- **Be assertive**：先查网络请求 / DOM / 代码库**再下结论**，别软绵绵地"可能也许"。
- **Verify before recommending**：建议删之前**先确认它真没用**。
- **Quantify impact**：用 insights 给的预估节省；**0 ms 影响的不排进优先级**。
- **Skip non-issues**：渲染阻塞资源若预估影响 0 ms，**记下但不建议动手**。
- **Be specific**：说"把 hero.png（450 KB）压成 WebP"，**不说"优化图片"**。
- **Prioritize ruthlessly**：LCP 200 ms、CLS 0 的站点**已经很好，就直说很好**。

→ 🔴 **这六条与 `gbt-aesthetic` 的报告风格一致（都要求"具体、可核、不许泛泛"），
可以直接沿用；但"好看"的判断仍回 `gbt-aesthetic`。**

### 1.4 簇 D · 检索：多 provider 统一入口

| 技能 | 什么时候用它 |
|---|---|
| **`web-search-plus`** | **要"一条接口打通 5 个检索 provider、且让它自动选路"时用它**。它自报的定位是"Stop choosing search providers. Let the skill do it for you."（5 provider：Serper / Tavily / Exa / You.com / SearXNG）。**典型场景**：比价与本地（Serper）· 研究与解释（Tavily）· "像 X 的公司"/论文（Exa，支持 `--similar-url`）· 实时资讯（You.com）· 私密搜索（SearXNG）。🔴 **但本机 5 个 key 全未配 ⇒ 现在只能跑"离线路由解释"，不能真检索**（§0.4 / §3）。⚠️ **默认优先用本会话内置的 `web_search` / `web_fetch`**；只有要**指定 provider** 才走它。 |

**自动选路的实测读数（✅ 已验，§3 有完整返回）** —— 以及一个**必须知道的陷阱**：
`--explain-routing` 在**没有任何 key** 时会输出
`"provider": "serper"` 配 `"confidence": 0.0` 与 `"reason": "no_available_providers"`。
🔴 **别把 `provider: serper` 读成"它选了 Serper"** ——
**`reason` 与 `confidence` 才是真相：它一个可用 provider 都没有。**
（这正是 §4 第 1 条说的"对的形状 + 错的内容"。）

---

## 2. 两道闸（顺序不能颠倒）

### 闸一 · 凭据闸（**只报"已配 / 未配"，绝不贴值**）

✅ 已验（2026-09-22 现读）：

| 这条技能 | 需要什么凭据 | 本机状态 |
|---|---|---|
| `web-artifacts-builder` | 桩里未声明 | ⚠️ **未声明**（不编） |
| `web-design-guidelines` | 桩里未声明 | ⚠️ **未声明**（不编） |
| `web-perf` | **不是 key，是 MCP server**（`chrome-devtools`） | 🔴 **未配**（`config/mcporter.json` 5 个 server 里没有它；全 config 面搜 `chrome-devtools` 0 命中） |
| `web-search-plus` | 5 个 provider key（**只要 1 个即可起用**） | 🔴 **全部未配**：`SERPER_API_KEY` 未配 · `TAVILY_API_KEY` 未配 · `EXA_API_KEY` 未配 · `YOU_API_KEY` 未配 · `SEARXNG_INSTANCE_URL` 未配。`config.json` 与 `.env` **都不存在** |

**凭据纪律（硬）**：

1. 🔴 **不许把任何 key / token 写进文件、聊天、规程、日报** —— 包括 `SERPER_API_KEY` 等 5 个，
   以及 SearXNG 实例 URL（它可能内嵌 basic-auth）。
2. 要给人看**只报**「**已配 / 未配**」或**前 4 位掩码**（例 `sk-a1b2****`）。
3. 🔴 **不许读也不许写它落盘的 key 文件**（`config.json` / `.env`）—— **本次只核了"在不在"，没读内容**。
   要配 key 就走它的 `scripts/setup.py` 向导或环境变量，**让值保持掩码**。
4. 🔴 **不许为一个"目录桩"去配它上游的 key**（`web-artifacts-builder` 等）。
5. ⚠️ **`--explain-routing` 报的 `scores` 不是"凭据可用性"**：本机
   `serper: 6.0` 而其余 `0.0`，那是**它给 Serper 的意图打分**，
   **不代表 Serper 配好了**（`reason` 明说 `no_available_providers`）。

### 闸二 · 会改外部 / 装包 / 配 key / 起容器 / 发版上线 —— **必须先问主人**

**本条高于技能自己的流程。** 理由：这四条里**三条的正常用法都自带"装东西"或"发出去"**，
而它们的文档**把那些步骤写成了流程的正常环节** —— **文档写得顺，不等于我们可以自动做**。

**算"改外部 / 装东西 / 发版 / 上传"的动作**（一律先问主人）：

| 动作 | 出处 | 为什么必须先问 |
|---|---|---|
| **配 provider key**（写 `config.json` 或设 5 个环境变量之一） | `web-search-plus` 的 `scripts/setup.py` 向导 | **落盘凭据 + 联网到第三方服务**；且一配就开始**消耗配额/可能计费** |
| **跑 `python3 scripts/setup.py`** | 同上（原文："Interactive setup (recommended for first run)"） | **会写 `config.json`（落盘 key）** |
| **真发一次检索**（`scripts/search.py -q "..."`） | 同技能 | **出网 + 消耗 provider 配额**；无 key 时会直接报缺（§3） |
| **起 SearXNG 容器**（原文给的是 `docker run -d -p 8080:8080 searxng/searxng`） | 同技能 FAQ | **起长期进程 + 开端口**；**且本机 `docker` 未核过在不在** |
| **自托管/暴露一个 SearXNG 实例** | 同技能 | **开对外端点**；原文的 SSRF 防护（拦云元数据端点、拦内网 IP）**指的是它会拒绝危险 URL，不是"我们可以随便暴露一个"** |
| **加 chrome-devtools MCP 配置 + 起它** | `web-perf` 的修法（`npx -y chrome-devtools-mcp@latest`） | **改本机配置 + 起进程 + 拉包** |
| **装上游 bundle**（`git clone` anthropics/skills 或 vercel-labs/skills 再拷进 skills 目录） | 两条桩的 "How to use" | **从外部取代码 + 改本机**；且本仓技能目录有既定约定（§6） |
| **把页面/站点部署上线** | 本簇**没有**部署命令，但常有下一步 | **发版 / 上传** ⇒ **先过 `fc-nginx-website` 的托管规矩，再问主人** |

**顺序（先干什么 → 拿什么回执）**：

1. **摊开四件事**：**身份/账号**（用谁的 provider 账号、谁的托管商）· **目标**（哪个文件/哪个 URL，
   **指名道姓**）· **内容**（要配哪个 provider、要发哪一版页面、要检索什么）·
   **影响面**（谁会看到、能不能撤回、删了能不能恢复、会不会产生费用）。
2. **先做不碰外部、不装东西的部分**：读 `web-perf` 的清单与阈值、读两条桩指的上游、
   `--explain-routing` 离线看选路、用**内置 `web_search`/`web_fetch` 拿资料** ——
   **这些都可以先做完**。**不要**因为"反正要问"就停在这不动。
3. **等一次明确同意**：**只覆盖这一条**（"这次配 Serper"≠"以后 provider 都配"）。
   **主人没回话 = 没同意，停。**
4. **同意后才动手**，并按需取回执：
   - 配 key：只回报 **"XX provider 已配"**（**不回报值**）；
   - 检索：拿到**结果 JSON 的 `provider` / `routing.auto_routed` / `routing.confidence`**
     （它自己的输出契约，§3.1）；
   - 上线：拿到**live URL**，并**打开确认**。
5. **失败就记失败**：原样保留错误与退出码（例如 §3 那条 `Missing API key`），
   **不许把失败写成成功**（§4）。
6. **不许静默重试写/计费类动作**：检索可能计费、发布可能重复 —— **重试前先确认第一次到底成没成**。

---

## 3. 只读实跑过的命令与真实返回（**未验的已标**）

### 3.1 ✅ 已验（本机真跑过，返回照抄）

| 命令 | 关键返回 | 判定 |
|---|---|---|
| `py -3.14 tools/codex-scripts/omni.py list --domain web` | 能力位 **0** 条；agent 技能 **11** 条 | ✅ 域口径 = 11（≠ 本簇 4） |
| `py -3.14 -c "…startswith('web-')"` | `['web-artifacts-builder','web-design-guidelines','web-perf','web-search-plus']` | ✅ 簇口径 = **4** |
| 两条桩目录递归枚举 | 各**只有 `SKILL.md`**（1327 B / 1253 B） | ✅ **是桩** |
| 搜桩正文 `This catalogue entry advertises the skill` | **两条都命中** | ✅ 桩的判据成立 |
| `web-search-plus` 目录递归枚举 | **12 个文件**；`scripts/search.py` **84040 B** · `scripts/setup.py` 17036 B · `config.example.json` 4972 B · `README.md` 23073 B | ✅ **真实现** |
| `Test-Path config.json / .env` | **两个都不存在** | ✅ 未落盘凭据 |
| `[Environment]::GetEnvironmentVariable(...)` × 5 | `SERPER_API_KEY` / `TAVILY_API_KEY` / `EXA_API_KEY` / `YOU_API_KEY` / `SEARXNG_INSTANCE_URL` → **全部"未配"** | ✅ **5 个全未配**（只报已配/未配） |
| `py -3.14 …/web-search-plus/scripts/search.py -h` | 完整 usage：`-p/--provider {serper,tavily,exa,you,searxng,auto}` · `--explain-routing` · `--similar-url` · `--searxng-url` · `--cache-stats` … | ✅ **程序可跑** |
| `py -3.14 …/search.py --explain-routing -q "iPhone 16 Pro Max price"` | `"provider": "serper"` · `"confidence": 0.0` · `"confidence_level": "low"` · **`"reason": "no_available_providers"`** · `scores: serper 6.0, 其余 0.0` · `intent_breakdown.shopping_signals: 2` | ✅ **离线可用**；⚠️ **"形状对内容空"陷阱**（§1.4 / §4） |
| `py -3.14 …/search.py -q "test" --max-results 1` | `{"error": "Missing API key for serper", "env_var": "SERPER_API_KEY", "how_to_fix": [3 条], "provider": "serper"}` · **exit 1** | ✅ **真检索被凭据挡住**（不是崩溃） |
| `python3 -c "import sys;print(sys.executable)"` | `C:\Users\ADMIN\AppData\Local\Python\pythoncore-3.14-64\python.exe` · **3.14.5** | ✅ 它声明的 `bins: ["python3","bash"]` **两条都在** |
| `bash --version`（25 s 限时） | `GNU bash, version 5.3.9(1)-release (x86_64-pc-linux-gnu)` | ✅ bash 在（⚠️ WSL 冷启动 **>8 s**） |
| `config/mcporter.json` 解析 | servers = `autoclaw-productivity` · `autoclaw-github` · `notion` · `connector:cloudflare` · `connector:vercel` | ✅ **无 `chrome-devtools`** |
| 在 `config/`·`.openclaw/`·`.autoclaw/` 搜 `chrome-devtools` | **0 命中** | ✅ `web-perf` 前置闸不满足 |
| `Test-Path ~/.openclaw/openclaw.json` | **不存在** | ✅ `web-search-plus` 那条"别改它"的告警在本机无对象 |
| `py -3.14 tools/codex-scripts/verify-distill.py --cluster lark` | `verdict: PASS` · `identical: true` · exit **0** | ✅ 验收器可用（对照件） |
| `py -3.14 tools/codex-scripts/verify-distill.py --cluster web` | 报 `"omni.py 的 DISTILLED_CLUSTERS 里没登记这个簇"` | ⚠️ **需主人登记**（§6） |

### 3.2 ⚠️ 未验（**没跑，不许说成跑过**）

| 事项 | 为什么没验 |
|---|---|
| `scripts/setup.py`（交互向导） | **会落盘 key**（§2 闸二）——需主人同意 |
| 任何**真检索**（配 key 后） | **出网 + 可能计费**（§2 闸二）——需主人同意 |
| `docker run … searxng/searxng` | **起容器 + 开端口**（§2 闸二）；且**本机 `docker` 在不在都没核过** |
| 任何 `web-perf` 的 MCP 工具调用（`navigate_page` 等） | **MCP 未配 ⇒ 调不到**；本件**没有**把它们当命令跑 |
| 任何性能审计 / Lighthouse 取数 | 同上（前置闸不过） |
| 上游 `anthropics/skills` / `vercel-labs/skills` 的任何命令 | **上游未 vendored**，本机没有可跑的东西 |
| `web-perf` 那张阈值表的**正确性** | 本次**只做了原文转录，没有复核**；它自己都要求"prefer retrieval over pre-training" |

---

## 4. 🔴 报告层红线（读数纪律）

1. **读数先问一句：这是事实，还是我读错了地方？**
   本簇**四个专门会给你"对的形状 + 错的内容"的地方**：
   - **`--explain-routing` 的 `provider` 字段**（🔴 最阴的一个）：
     `"provider": "serper"` 配 `"reason": "no_available_providers"` + `confidence 0.0`。
     **形状上"它选了 Serper"，真相是"它一个可用的都没有"。**
     ⇒ **读路由必须连 `reason` 与 `confidence` 一起读。**
   - **`omni list --domain web` = 11 ≠ 本簇 4**：域口径与前缀口径**不是一回事**。
   - **桩也是 `SKILL.md`**：文件存在 **≠** 有流程（`web-artifacts-builder` / `web-design-guidelines`）。
   - **MCP 工具名不是命令**：`navigate_page` / `performance_start_trace` / `take_snapshot`
     是 **`web-perf` 要调的 MCP 工具**，**本机一个都没有**。
     **别把它们当 CLI 跑**，跑出来的"not found"**不是性能读数**。
2. **有错也照原样记，不许把失败写成成功。** 保留退出码与原始错误文本
   （例：`Missing API key for serper` + **exit 1**）。
3. 🔴 **不许编造性能读数**：`web-perf` 现在**跑不了**（§0.3）。
   **"没量到"就写"没量到"** —— **绝不允许**写出"LCP 1.8 s / CLS 0.05"这类**没量过的数**。
   这是本簇**最容易犯、也最严重的一条**。
4. 🔴 **阈值不是权威**：§1.3.1 那张表是**技能里写的**，且它自己要求**先取最新文档**。
   引用前先取数，**别把转录当复核**。
5. **不许报凭据细节**：只报**已配 / 未配**或**前 4 位掩码**。
   连 **SearXNG 实例 URL** 也算凭据面（可能内嵌 basic-auth）—— **只报已配/未配**。
6. **中文口语打不中英文触发词**（✅ 已验，§5 坑 4）：
   `omni ask "查一下这个网页的性能和 Core Web Vitals"` **命中 `web-perf`**，
   而 `omni ask "帮我做一个前端的落地页，要有冲击力"` 里 **12 条一条都没有**。
   ⇒ **打不中时不要怀疑技能不存在，直接按名字点名。**

---

## 5. 本机踩过的坑（照做，别自己解读）

1. ✅ **`omni ask` 只列"有命中"的候选，且有上限。**
   `omni.py:501` 调 `rank(intent, domain)`（默认 `top=8`）；`omni.py:488-496` 里
   **只有 `hit` 非空才 append**。我实测时曾把输出**截到前 25 行**就下结论说
   "`frontend-*` 一条都没落到" —— **那是我的截断，不是工具的上限**。
   ✅ 反过来：`"查一下这个网页的性能和 Core Web Vitals"`（**全文**看）**真命中 `web-perf` 与 `frontend-slides`**。
   ⇒ **看全文再下结论。**

2. ✅ **`web-perf` 通篇是 MCP 工具名，不是本机命令。**
   它全文出现 `navigate_page` · `performance_start_trace` · `performance_analyze_insight` ·
   `list_network_requests` · `get_network_request` · `take_snapshot` ——
   **这些在本会话里一个都不可调用**（chrome-devtools MCP 未配）。
   ⇒ **别 `Get-Command navigate_page` 然后报"命令不存在"** ——
   那不叫"发现工具缺失"，那叫**读错了层级**（§4 第 1 条）。

3. ✅ **它自己要求的"FIRST 步骤"必须真跑，不许跳。**
   原文："**Run this before starting.** … If unavailable, **STOP**"。
   本机现状就是 **unavailable** ⇒ **正确动作是 STOP + 如实报"前置没配"**，
   **不是**"跳过它硬编一份审计报告"。

4. ✅ **中文提问与英文触发词 n-gram 不重叠 ⇒ 0 分（本簇同样适用）。**
   本簇四条的 `triggers` 里，`web-perf` 那条**在托管目录里没有 `triggers` frontmatter**
   （它只有 `name` + `description`），而两条桩的 `triggers` 是英文
   （`web artifacts` / `tailwind artifact` / `web design guidelines` / `vercel design` …）。
   ✅ 实测：`"查一下这个网页的性能和 Core Web Vitals"` **能命中**（因为 `web-perf` 的
   `description` 里就有 `Core Web Vitals` 这些词），
   而**纯中文口语**（`"帮我做一个前端的落地页"`）**一条都打不中**。
   ⇒ **打不中时直接点名。**

5. ✅ **`web-search-plus` 无 key 时的失败是"优雅报缺"，不是崩溃。**
   返回是结构化 JSON：`{"error":"Missing API key for serper","env_var":"SERPER_API_KEY",
   "how_to_fix":["1. Get your API key from https://serper.dev", …],"provider":"serper"}`，
   **exit 1**。
   ⇒ **别把它读成"技能坏了"** —— 它**如实报了缺什么、去哪配**。这正是我们要的报法。

6. ✅ **`web-perf` 和 `web-search-plus` 都不在 `~/.openclaw-autoclaw/skills` 一起。**
   `web-perf` 在 **`~/.claude/skills`**；`web-search-plus` 在 **`~/.openclaw-autoclaw/skills`**；
   两条桩在 **`<仓>/审美相关skill/skills`**。
   ⇒ **同簇四条分居三个根** —— **按名字找文件时必须先定位根**（§0.1 表已给）。
   只看一个目录会得出"这条不存在"的错结论。

7. 🔴 **本会话的技能目录里看不到这 4 条中的任何一条 —— 两处独立核实过。**
   ① **目录侧**：本会话 `available_skills`（现读）里**没有 `web-*`**；
   ② **文件系统侧**：✅ 已验 —— 本会话真正解析的 `.agents` 根**不止一个**：
   `~/.agents/skills`（`gbt-aesthetic` / `gbt-omni` / `hyperframes-animation` … 在这里）、
   `~/.openclaw-autoclaw/workspace/.agents/skills`（**`fc-nginx-website` 在这里**）、
   以及 `~/.openclaw-autoclaw/agents/<agent>/workspace/.agents/skills`。
   ⇒ **这 4 条在以上任何一个 `.agents` 根里都不存在**（✅ 12 条目标技能命中数为 **0**）。
   ⇒ 而它们所在的 `~/.openclaw-autoclaw/skills` **不在那几个 live 根之列** ——
   证据：同目录下的 `website-builder` / `autoglm-websearch` / `daily-ai-news` /
   `glmv-pdf-to-web` / `frontend-slides` / `web-search-plus` **一个都不在本会话 `available_skills` 里**。
   ⇒ 本件仍按 **AGENTS.md 的托管目录约定**装到 `~/.openclaw-autoclaw/skills/`
   （与已交付的 `gbt-lark` **同款**）。**这是本仓既定做法。**
   🔴 **绝不往任何 `~/.agents/skills/` 写**（那是别家工具的共享目录）。

---

## 6. 固化位置（**重启后要在**）

| 什么 | 在哪 |
|---|---|
| 本规程（源 · 真身） | `<仓>/skills/gbt-web/SKILL.md` |
| 本规程（装机） | `~/.openclaw-autoclaw/skills/gbt-web/SKILL.md`（**与源稿逐字节相同**） |
| `web-artifacts-builder` | `<仓>/审美相关skill/skills/web-artifacts-builder/`（**桩**） |
| `web-design-guidelines` | `<仓>/审美相关skill/skills/web-design-guidelines/`（**桩**） |
| `web-perf` | `~/.claude/skills/web-perf/SKILL.md`（**真正文**，**不由本件代管，别改**） |
| `web-search-plus` | `~/.openclaw-autoclaw/skills/web-search-plus/`（**12 文件**，**不由本件代管，别改**） |
| 上线托管规矩（**部署前必读**） | `~/.openclaw-autoclaw/workspace/.agents/skills/fc-nginx-website/` |
| 能力名册（现读） | `<仓>/state/skill_atlas.json`（`name` 以 `web-` 开头） |
| 人话入口 | `py -3.14 tools/codex-scripts/omni.py ask "<一句话>"`；⚠️ 口语打不中时直接点名 |
| 验收 | `py -3.14 tools/codex-scripts/verify-distill.py --cluster web` |
| 审美裁决 | `gbt-aesthetic`（**本件不做审美判断**） |

**验收器现状（✅ 已验）**：`--cluster web` 现在报
`"omni.py 的 DISTILLED_CLUSTERS 里没登记这个簇"`（`skills_in_atlas: 4`，exit 1）。

🔴 **`omni.py` 的簇登记由主人做，本件不许自登记** ——
要加的一行是主人在 `omni.py` 的 `DISTILLED_CLUSTERS` 表里补的：`"web": "gbt-web"`。
⚠️ **行号会漂，别记行号**：本次现读该表在 `omni.py:150`，
而**同一次会话里它已经从我最初读到的 143 漂到了 150** ⇒ **只认表名。**
该表现读已有 11 个簇，**本簇不在其中**。**我和本件都无权改 `omni.py`。**

**纪律**：本规程**不代替**这 4 条技能自己的 `SKILL.md`。
上游未装 / MCP 没配 / key 未配，就**如实报"取不到"**，**不许编读数** ——
**尤其是性能数字**（§4 第 3 条）。
`omni.py` 与 `security/policy.py` **不是本件该动的东西**。

---

## 7. 诚实边界（这段不许删）

1. **本件是"用法规程"，不是"能力已具备"。** 它把 4 条**分簇、点名、定了纪律**；
   **每条技能的深度流程以它自己的 `SKILL.md` 为准**，本件**不替代**。
2. 🔴 **本簇的可执行面现在 = 1.5 条**：
   - `web-search-plus`：**程序能跑**（`-h`、`--explain-routing` 已验），
     **但真检索要 key，5 个 key 全未配** ⇒ **实际检索面 = 0**；
   - `web-perf`：**流程是真的**（201 行），**但前置 MCP 未配 ⇒ 现在跑不了**；
   - `web-artifacts-builder` / `web-design-guidelines`：**本机只有桩**。
   **"图鉴里有 4 条" ≠ "4 条都能跑"。别把"索引过"读成"精通了"。**
3. **本次实跑的都是只读/帮助类动作**：`omni list`、图鉴前缀查询、目录枚举、`Test-Path`、
   环境变量**只判空**、`search.py -h`、`search.py --explain-routing`、
   一次**故意不发请求的成功路径以外**的 `search.py -q`（它被凭据挡住）、`--version`、`config` 读键名。
   **任何配 key、真检索、起容器、装上游、加 MCP、部署上线，本次都没跑** ——
   涉及它们的地方已按 §3.2 标注 **（未验）**。
4. **本机状态是 2026-09-22 的现读快照**（图鉴 `built_at = 2026-09-22T22:16:13`）。
   **换机器、换版本、重跑 `omni build` 后必须重新现读**，别把这份读数当永久事实。
   ⚠️ **凭据读数会漂**：`未配` 是**那一刻**的读数，主人配完就变。
5. **凭据只报"已配/未配"**：本件出现 `sk-a1b2****` 只是**掩码书写示例**，
   **不是**任何真实凭据；本机 5 个 provider key**全部未配**，且**本次没有读任何值**。
6. **审美判断不在这件里。** "好不好看 / 有没有 AI 味 / 该走哪个方向" **一律回 `gbt-aesthetic`**；
   `web-design-guidelines` 若装上，它给的是**可判定的工程规约**，**也不等于审美裁决**。
7. ⚠️ **`web-perf` 的阈值表与六条行为纪律是"原文转录"，不是"我复核过的结论"**（§3.2）。
   引用前先按它自己的要求去取最新文档。
