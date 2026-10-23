# Sanity 项目接入 + 理智挑战赛（Sanity Challenge）· 设计登记（R-H482 · **图纸已落**）

> 主人给的方案**逐字登记**；🔴 **涉及个人信息与凭据的部分一律掩码/不落盘**（见 §0）。
> 一句话：**用现成知识库接 AI 代理，或者用 AI 快速 Vibe-code 一个奇怪应用 —— 两周内把流程跑通。**

---

## 0 · 🔴 隐私与凭据红线（本刀自查 · 先写在最前面）

| 项 | 处置 | 理由 |
|---|---|---|
| 主人给的两个**邮箱** | **一律掩码**：`lop***@gmail.com`（网页端项目管理员）· `pay***@gmail.com`（之前终端登录的号） | 个人信息**原值不落盘**（Anti-Manipulation / 凭据章节） |
| **Viewer Token**（为 MCP 生成的那个） | **只许走 DPAPI**，密钥名 `sanity_token`；**禁止明文**（不许写进本文档、聊天、日志） | 《Credentials》红线 |
| **Project ID** `ie9twlav` | 记为 **公开标识**（不是密钥）—— 比赛官方**要求**填进提交帖 | 与 Token 严格区分：**标识 ≠ 密钥** |
| 代理会话录屏上传前 | **先脱敏**（检查有没有泄露密钥），再点「公开」 | 主人原文已提醒；本图纸照抄为红线 |

## 一 · 现状与「账号不对」这件事（逐字登记）

**现象**：网页端项目**已建好**（活动日志：数据集已创建 · 项目已创建 · 增长计划已启动），但终端 CLI 报「没权限访问 `ie9twlav`」。

**原因（主人判断）**：活动日志的那句「`lop***@gmail.com` 受邀加入 gbt，并拥有管理员权限」⇒ **项目所有者/管理员是那个号**；
而终端之前登录的是 `pay***@gmail.com` ⇒ **账号不对**（不是没建项目）。

**两个方案（逐字）**

| 方案 | 做法 |
|---|---|
| **A（推荐）** | 让**终端换正确的账号登录**：先 `npx sanity logout`，再 `npx sanity login --provider google`；浏览器弹出时**确保选的是 `lop***@gmail.com`** |
| **B** | **把另一个账号也拉进来**：网页端 `https://www.sanity.io/manage` → 进 GBT 项目 → 「成员」→ 邀请 `pay***@gmail.com`，给 **Administrator** 权限 ⇒ 刷新后终端那个号就有权限 |

## 二 · 本地初始化（逐字 · **本刀未执行**）

```bash
npm create sanity@latest -- --project ie9twlav --dataset production --template clean
# 输入文件夹名（例：gbt-sanity）→ 进目录 → npm install → npm run dev → http://localhost:3333
```

## 三 · 下一步：准备比赛（逐字）

```
① 去 Sanity 后台 API 页面**生成 Viewer Token**（用于 MCP）
② 把 Token 存进 **DPAPI 密钥池**（密钥名 `sanity_token`）—— 不许明文落盘
③ 准备**导入知识库**（坑册 + 图纸）
```

## 四 · 两条参赛路径（逐字）

| 路径 | 核心 | 适合 | 评判重点 |
|---|---|---|---|
| **路径一：能查询真实内容的 AI 代理** | 用 Sanity 建结构化知识库 ⇒ AI 代理通过 **Sanity Context MCP** 查询 | 手上有现成文档/规则/资料 | 结构化内容运用 · 技术实现 · 知识库质量 · 可用性 |
| **路径二：AI 快速 Vibe-code 一个奇怪应用** | AI IDE 快速搭前端（Next.js / Astro），后端用 Sanity | 想做有创意、交互强的应用 | 开发过程记录**真实性** · 应用功能 · 架构思考 · 原创性 |

```
额外加分：使用 **App SDK** 或 **Workflow** 构建（不是只读前端）
建议（主人原话）：有现成知识库走**路径一更稳**；想玩创意走**路径二**；**也可两个都提交**（每路径单独发帖）
```

### 4.1 路径一五步（逐字）

| 步 | 动作 |
|---|---|
| 1 | 注册 Sanity → 建项目 → 记下 **Project ID**（提交时必须填）· `npm install -g @sanity/cli` · `sanity init` 选模板 |
| 2 | 用 **TypeScript 定义 Schema**（如 article / rule / faq）· 导入知识库（`sanity dataset import` 或 Studio 里加）· `sanity deploy` |
| 3 | 配置 **Sanity Context MCP**（把内容变成**可导航知识库**、每条**链接到来源**）· 具体步骤见官方文档与 Discord `#mcp-server` |
| 4 | 构建 AI 代理（任何支持 MCP 的框架：Claude Code / Gemini CLI / Codex / Copilot CLI）→ 指向 Context MCP 端点 → 测问答 · **录下会话并上传 DEV 的 Agent Sessions（点「公开」前先脱敏）** |
| 5 | 在 DEV 发帖，标签 **`#sanitychallenge`**；按官方模板，**必须含 Project ID 或公共数据集 URL**、测试凭证（如需登录）、代理会话嵌入（可选加分） |

### 4.2 路径二（逐字）

```
用 AI IDE（Cursor / Windsurf / Codex）快速生成前端（Next.js 或 Astro）⇒ 后端接 Sanity（@sanity/client 或 GROQ）
⇒ 做一个**奇怪但有趣**的应用（把视频转 GIF 的组件 / 触发外部 API 的工作流 / 内容审核流程）
⇒ **记录开发过程**（AI 对话、提交、遇到的问题都截图或录屏，体现**真实过程**）
⇒ 同样在 DEV 发帖（标签 #sanitychallenge + Project ID + 测试说明）
```

## 五 · 两周时间表（逐字）

| 天数 | 任务 |
|---|---|
| 第 1-2 天 | 注册 Sanity，建项目，学 Schema 和 GROQ |
| 第 3-5 天 | 导入知识库，配置 Context MCP |
| 第 6-8 天 | 搭建 AI 代理，连接 MCP，测试问答 |
| 第 9-10 天 | 录制代理会话，脱敏，上传 DEV |
| 第 11-12 天 | 写提交帖子，检查格式 |
| 第 13-14 天 | 优化，提交（**截止 10 月 4 日 23:59 PDT**） |

## 六 · 注意事项（逐字）

### 6.0 四条红线（写死 · 逐字）

| 红线 | 说明 |
|---|---|
| **密钥 DPAPI** | Token（Viewer Token 等）只走 DPAPI 密钥池，**不许明文** |
| **每次操作留痕** | 写 `trace_store`（`source_kind` 按环节命名） |
| **不碰面板 8765** | 面板正在跑的实例不动 |
| **走今天规矩** | 开护照 → 改 → 用例 → 独立复核 → 关账 |

```
· **必须包含 Sanity Project ID**，否则可能视为不完整
· **不要泄露密钥**（上传会话前检查）
· 资格要求：查看官方规则与 FAQ，确认符合参赛资格
· **所有有效提交都有完成徽章**（没获奖也有收获）
· 可同时提交两个路径，但**每个路径单独发帖**
```

## 七 · 先取证（本刀现场 · 只读）与边界

| 项 | 读数 |
|---|---|
| node | ✅ **v24.15.0**（`C:\Program Files\nodejs\node.exe`） |
| npx | ✅ 在（`npx.ps1`） |
| npm | ⚠️ **取不到**（PATH 里没有 `npm` 命令） |
| 全局 `sanity` CLI | ❌ **不在 PATH** |
| 本仓 sanity 痕迹 | 17 行，但**全是无关的**（`design-systems/sanity` 那套设计系统目录、别的脚本里的变量名）⇒ **没有 Sanity 项目痕迹** |
| 本地初始化 | ❌ `gbt-sanity` / `sanity.json` / `sanity.config.ts` **都不存在** |
| DPAPI 密钥池 | 现有 5 份（cloudflare_api · deepseek_api · feishu_app · notion_api · xingyun_app）⇒ **没有 `sanity_token`** |

### 7.1 🔴 本刀边界（一个字不编 · 一条命令都没跑）

```
① 本刀**只落图纸** + 登记进待落刀登记：**不执行任何命令**
   （不跑 npx / npm / sanity login / 不装依赖 / **不出网** / 不写路径 / **不建 gbt-sanity 目录**）
② **不生成、不保存任何 Token**（DPAPI 里没有 sanity_token 这一项）
③ 🔴 **终端换号（方案 A）与邀成员（方案 B）只有主人能做**（要浏览器登录会话）
④ 🔴 **生成 Viewer Token 也只有主人能做**（后台 API 页面）⇒ 之后才轮到我接「导入知识库」
⑤ 本图纸**未注册任何能力位**、未改任何代码、未动待定格（仍 46 条）
```

---

> 开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属
> 登记 2026-09-21（R-H482）· 状态：**图纸已落**；未换号 / 未初始化 / 未生成 Token / 未接 MCP / 能力位未立
