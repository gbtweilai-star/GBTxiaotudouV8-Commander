---
name: gbt-cloudflare
displayName: GBT · Cloudflare 技能簇用法规程（cloudflare-* · 4 条）
version: 1.0.0
description: GBT小土豆V8 使用 Cloudflare 技能簇的用法规程。把这一簇的 4 条技能（平台总纲自带约 370 份 references · 邮件收发与投递率 · Cloudflare One 零信任与 SASE · 从 Zscaler 与 Palo Alto 与旧 VPN 迁移到 Cloudflare One）逐条点名并按意图分簇，规定两道闸（闸一凭据闸，wrangler 的 OAuth 凭据与 CLOUDFLARE_API_TOKEN 与 CLOUDFLARE_ACCOUNT_ID 只报已配/未配或前 4 位掩码；闸二发布与改远端闸，凡 deploy、删资源、改 DNS、下发 Zero Trust 策略、改 Access 与 Gateway 规则、开 TLS 检查、发邮件、开通域名邮件功能的动作一律先问主人），点破「零作用域不等于只读」「预训练不如现取」两个坑，以及本机现状（wrangler 4.111.0 已装且本地有 oauth 凭据文件、CLOUDFLARE_ 环境变量全未配、wrangler whoami 未验、postal-mime 未装、Cloudflare MCP 未接且无 MCP 工具健康）。当用户要写或部署 Worker/Pages、用 KV/D1/R2、发 Cloudflare 邮件、配 Zero Trust 与 WARP 与 Tunnel、做 SASE 迁移评估，或问 cloudflare 技能怎么选、wrangler 报未登录、这次改动会不会影响线上时使用。
triggers:
  - "cloudflare"
  - "Cloudflare"
  - "cloudflare-*"
  - "wrangler"
  - "Worker"
  - "Workers"
  - "Pages"
  - "KV"
  - "D1"
  - "R2"
  - "Durable Objects"
  - "Email Routing"
  - "Email Sending"
  - "邮件路由"
  - "发邮件"
  - "Zero Trust"
  - "SASE"
  - "Access"
  - "Gateway"
  - "WARP"
  - "Cloudflare Tunnel"
  - "cloudflared"
  - "DLP"
  - "CASB"
  - "设备态势"
  - "Zscaler"
  - "ZPA"
  - "ZIA"
  - "Palo Alto"
  - "Prisma"
  - "GlobalProtect"
  - "CLOUDFLARE_API_TOKEN"
---

# GBT · Cloudflare 技能簇用法规程

> 开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属
>
> 这是**我们自己的用法规程**（不是 Cloudflare 官方文档的复述，也不是这几条技能原文的复述）。
> 这几条技能讲的是"这一类 Cloudflare 工作该怎么做"，本文件讲
> "**在我们这儿，它们现在到底能不能跑、身份从哪来、谁在什么条件下按什么顺序去用它，
> 以及什么东西绝对不许自动发上云、下发给别人、发到别人的邮箱里**"。
> 冲突时的裁决顺序：**本文件管我们的纪律** → 各技能原文管它自己的产品细节 → **Cloudflare 官方文档是最终事实源**。三层都守。

---

## 0. 它是什么 / 在哪 / 🔴 最关键的两个事实

### 🔴 事实一：条数有两套口径，**本件按"更全"的那套点名（4 条，不是 3 条）**

| 口径 | 数 | 名单 |
|---|---|---|
| **按 `name` 前缀 `cloudflare-*`**（本次任务书给的口径） | **3** | `cloudflare-email-service` · `cloudflare-one` · `cloudflare-one-migrations` |
| **按验收器 `verify-distill.py --cluster cloudflare` 的口径**（`name == 簇名` **或** `name` 以 `簇名-` 开头） | **4** | 上面 3 条 **+ 裸名 `cloudflare`** |

现读证据：

```text
py -3.14 tools/codex-scripts/verify-distill.py --cluster cloudflare
  → facts.skills_in_atlas = 4        ← 验收器口径：4
py -3.14 tools/codex-scripts/omni.py list --domain cloudflare
  → 带出 7 条：cloudflare / cloudflare-email-service / cloudflare-one /
    cloudflare-one-migrations / sandbox-migrate-to-next / sandbox-next / sandbox-stable
  → 按 `cloudflare-*` 前缀筛 = 3；裸名 cloudflare 是第 4 条
```

🔴 **本件把 4 条全部点名** —— 因为验收器按"4 条都被点到"判通过，**漏掉裸名那条会被判 FAIL**。
这跟 `gbt-pptx` 当时遇到的 `pptx-*` 3 条 + 裸名 `pptx` 1 条是**同一类坑**。

⚠️ **别抢别的簇**：`--domain cloudflare` 带出来的
`sandbox-migrate-to-next` / `sandbox-next` / `sandbox-stable` **不是本簇**（`name` 不以 `cloudflare` 开头），
它们属于**另一个已登记的簇**（`sandbox` → `gbt-sandbox`）。
**本件只点名这条边界，绝不代管它们。**

### 事实二：这 4 条**不是桩**，而且都明写"**别信预训练，去现取**"

和 `venice-*` / `fal-*` 那种"只有一个 SKILL.md 的广告位"**完全不同**。现读清点：

| 技能 | 目录里有什么 | `SKILL.md` 体积 |
|---|---|---|
| **`cloudflare`**（裸名 · 平台总纲） | `SKILL.md` + **`references/` 里约 370 个文件**（60+ 个产品目录，每个目录含 `README.md` / `api.md` / `configuration.md` / `gotchas.md` / `patterns.md` 之类） | 8991 字节 |
| **`cloudflare-email-service`** | `SKILL.md` + `references/`（6 个文件：`sending.md` / `rest-api.md` / `routing.md` / `cli-and-mcp.md` / `deliverability.md` 等） | 7956 字节 |
| **`cloudflare-one`** | `SKILL.md`（**单文件**，但正文 176 行，密度很高） | 22293 字节 |
| **`cloudflare-one-migrations`** | `SKILL.md`（**单文件**，110 行） | 12363 字节 |

**三条原文都在反复说同一件事**（措辞各不相同，意思一致）：

- `cloudflare`：「Your knowledge of Cloudflare APIs, types, limits, and pricing may be outdated.
  **Prefer retrieval over pre-training** — the references in this skill are starting points,
  not source of truth.」并在表里给出四个取数源
  （Cloudflare docs 检索工具 / `@cloudflare/workers-types` / wrangler 的 `config-schema.json` / changelog）。
- `cloudflare-email-service`：「**Prefer retrieval over pre-training** for any Cloudflare Email Service task.」
  并明说「**If there is any discrepancy between this skill and the sources below, always trust the original source.**」
- `cloudflare-one`：「**Retrieval-first**: use current Cloudflare docs/API schemas instead of embedded product docs.」
  并在 Guardrails 里点名：「**Never guess category IDs, application IDs, wirefilter fields, or API request bodies.**」

🔴 **这条对我们是硬纪律**：**报价 / 限额 / 字段名 / 分类 ID / UI 路径，一律不许凭记忆写。**
**取不到就说"取不到"，不许编。**

### 落点与名册（现读）

| 项 | 值（2026-09-22 现读） |
|---|---|
| 条数 | **4 条**（见上表两套口径） |
| 通道 | **`agent-skill`**（按技能名加载执行） |
| 落点 | **1 处**：`C:\Users\ADMIN\.claude\skills\cloudflare*`（图鉴 `root` / `roots` 字段都登记这个目录，4 条 `root_count` 均为 1） |
| 上游归属 | Cloudflare 官方技能包（`cloudflare` 与 `cloudflare-email-service` 在正文里各自给了官方文档与 GitHub 取数源） |

🔴 **两个"别去找"的地方（现读确认）**：

1. **`~/.openclaw-autoclaw/skills` 顶层没有 `cloudflare*`；`~/.agents/skills` 也没有。**
   ⇒ **别在托管目录找不到就判"没装"**，也**绝不往 `~/.agents/skills` 写任何东西** ——
   那是别家工具的共享目录（本簇的正文**就在 `~/.claude/skills`**，本件**只读它、不改它**）。
2. **`~/.wrangler` 与 `%APPDATA%\xdg.config\.wrangler` 这两个目录都真实存在**
   （现读：各有 `cache` / `config` / `logs` / `tmp` 等），
   ⇒ **别以为"wrangler 没装所以没有目录"**；但**也不许去读里面的凭据字段值**（见 §2 闸一）。

---

## 1. 🔴 本机现状如实读数（2026-09-22 现读快照）

**结论先说：身体（wrangler）在，凭据文件也在，但"登录还有效吗"没验；环境变量那条路全断。**

| 检查项 | 现读结果 | 怎么读的 |
|---|---|---|
| `wrangler` 命令 | ✅ **已装 `4.111.0`** | `Get-Command wrangler` → `C:\Users\ADMIN\AppData\Roaming\npm\wrangler.ps1`；`wrangler --version` → `4.111.0` |
| 全局 npm 包 `wrangler` | ✅ 已装 `4.111.0` | `npm ls -g --depth=0` |
| Node.js | ✅ `v24.15.0` | `node --version` |
| **wrangler 本地 OAuth 凭据文件** | ✅ **存在**（两处都有 `config\default.toml`） | `Test-Path` 两个路径均为 `True` |
| 该文件里**有没有** `oauth_token` 字段 | ✅ **有**（各 1 处） | 只统计**键名命中次数**，**没有读值**：`Select-String -Pattern '^\s*oauth_token\s*=' \| Measure-Object` |
| 该文件里有没有 `expiration_time` | ✅ 有（各 1 处） | 同上读法（只数命中） |
| 该文件里有没有 `account_id` | ❌ **没有**（各 0 处） | 同上读法 |
| **`wrangler whoami`（登录态真验）** | ⚠️ **未验** | **这是出网请求**（要打 Cloudflare API）。按本次纪律**不做出网动作**，标记为未验 |
| `CLOUDFLARE_API_TOKEN` | **未配** | 环境变量现读为空 |
| `CLOUDFLARE_ACCOUNT_ID` | **未配** | 环境变量现读为空 |
| 任何 `CLOUDFLARE*` 环境变量 | **一个都没有** | 按名过滤 `CLOUDFLARE*` → 空集；`CF_*` 同样是空集 |
| `postal-mime`（收信/解析邮件要用） | ❌ **未安装** | `npm ls -g --depth=0` 里没有；原文要求用 `npm ls postal-mime` 查（**本机未在项目内查，只能报"全局没有"**） |
| Cloudflare MCP 是否接上 | ⚠️ **仓库配置里写了、健康度未知** | 仓内 `config/mcporter.json` 有 `connector:cloudflare` → `https://mcp.cloudflare.com/mcp`（`auth: "oauth"`，`enabled: true`） |
| 本机 MCP 总体健康度（仓库自述） | 🔴 **无 MCP 工具健康** | 工作区 `AGENTS.md` 的 MCP 段现读写着 "No MCP tools are currently healthy." |
| 本机 19681 端口是否在听 | ❌ **没有** | 监听端口现读列表里**没有 19681**；而 `mcporter.json` 里 `autoclaw-productivity` / `autoclaw-github` 都指向 `http://127.0.0.1:19681/...` ⇒ 那两个后端没起。⚠️ **`connector:cloudflare` 指向的是远端 HTTPS，与 19681 无关**，别把这两件事混起来 |

⚠️ **逐条读法（这三句是本件最该记住的）**：

1. **"有 `oauth_token` 字段" ≠ "登录还有效"。**
   本件只证明了**凭据文件在、里面有个 token 字段、还有个过期时间字段** ——
   **没有读值，也没有验它过没过期**。要验就得跑 `wrangler whoami`，**那是出网，要先问主人**。
   ⇒ **任何人问"wrangler 登录了吗"，本机现在的诚实答案是"凭据文件在，有效性未验"。**
2. **`CLOUDFLARE_API_TOKEN` 那条路是断的**（未配）。
   而 Cloudflare 的**REST API / 邮件发送的 REST 路径 / Zero Trust 的 API 下发**都要 token 或 OAuth。
   ⇒ **别以为"wrangler 能跑就等于 REST 那条路也能跑"** —— **是两个鉴权体系**（见 §2 闸一）。
3. **"MCP 配置里写了"≠"MCP 能用"。**
   仓库配置里确实有 `connector:cloudflare`，但**健康度未知**，
   而仓库 `AGENTS.md` 自述**当前没有任何 MCP 工具健康**。
   ⇒ **别拿"配置里有这一行"当"能调 Cloudflare MCP 检索工具"**（这几条技能反复推荐用它取数）。
   要真验它，得走 `web_fetch` / MCP 调用 —— **那都是出网，要先问主人**。

---

## 2. 两道闸（顺序不能颠倒）

### 闸一 · 凭据闸（**本簇不是"一个 key"，而是两套平行鉴权**）

| 路 | 用什么 | 覆盖什么 | 本机现状 |
|---|---|---|---|
| **wrangler OAuth（浏览器登录）** | `wrangler login`（凭证落在 `default.toml`） | `wrangler` 全家：Workers / Pages / KV / D1 / R2 / 邮件开通 / routes / secrets 等 | ⚠️ **凭据文件在，有效性未验** |
| **API Token（REST）** | `CLOUDFLARE_API_TOKEN` 环境变量 / API Token | REST API：邮件发送 REST 路径、Zero Trust / Access / Gateway 的 API 下发、账号级资源管理 | 🔴 **未配** |
| **Account ID** | `CLOUDFLARE_ACCOUNT_ID` | 邮件 REST 端点要 `accounts/{account_id}`；很多账号级 API 也要 | 🔴 **未配** |
| **Cloudflare MCP（OAuth）** | 客户端 OAuth 接 `https://mcp.cloudflare.com/mcp` | 官方文档检索 / API schema 查询（这几条技能推荐的取数路） | ⚠️ **配置里有，健康度未验** |
| **Workers 绑定（Email 专用）** | `wrangler.jsonc` 里的 `send_email` binding | **在 Worker 里发邮件 —— 原文明确"不需要 API key"** | 取决于具体项目（本机无项目上下文，**不判断**） |

**只报状态，绝不报值。** 这是硬纪律，无例外。

```powershell
# ✅ 唯一允许的读法（只出"已配/未配"，不出值）
if ([Environment]::GetEnvironmentVariable('CLOUDFLARE_API_TOKEN')) {'已配'} else {'未配'}
if ([Environment]::GetEnvironmentVariable('CLOUDFLARE_ACCOUNT_ID')) {'已配'} else {'未配'}
# ✅ 要看个影子就只出前 4 位掩码（例：abcd****）
#    本机现在是「未配」，没有掩码可给
```

🔴 **绝对不许**：

- **读 `default.toml` 里 `oauth_token` 的取值**。允许的读法只有**数键名命中次数**（本件就是这么读的）。
- 把凭据值 echo 出来 · 写进任何 `.md` / 日报 / `MEMORY.md` / 聊天 · 贴进本规程 ·
  当参数明文传给命令行（**会进 shell 历史与进程列表**）。
- 把 Cloudflare 的 **Global API Key** 当成普通 token 对待 —— 那是**账号级全权**，
  本件建议：**主人在没有明确必要时不要用它**；本件**不主动索取、不使用**。
- 🔴 **原文的一处硬提醒要抄下来**：`cloudflare-one` 明写
  「**Generated IPsec PSKs and some OAuth/client secrets are returned once. Store them immediately.**」
  ⇒ **这类"只显示一次"的秘密：主人拿到后要立刻存到安全处，而本件与我一律不许把它打进对话或文件。**

**本机闸一现状（2026-09-22 现读）**：
环境变量那两条路（`CLOUDFLARE_API_TOKEN` / `CLOUDFLARE_ACCOUNT_ID`）**未配**；
wrangler 的 OAuth 凭据文件**在但未验**；Cloudflare MCP **配置里有、健康度未验**。
⇒ **闸一是"半开"状态**：**可能能跑 `wrangler` 的只读命令，但本件没有验过，所以不能宣称能跑。**
**要动手前，第一件事是先问主人"要不要花一次出网请求验 `wrangler whoami`"。**

---

### 闸二 · 发布 / 改远端 / 发出去确认闸（**本簇第二重的一簇**）

**本条高于技能原文，也高于 wrangler 自己的任何默认行为。**

**为什么必须由我们拦**：Cloudflare 的动作**直接改的是别人在用的东西**：
线上的 Worker / Pages、DNS 记录、Zero Trust 里**所有人的上网策略**、
**别人邮箱里收到的邮件**。**这里面没有一件是"跑错了重来一遍"就完事的**：
**DNS 改错了就是全站挂**，**Zero Trust 策略下错了就是全员断网或被放开**，
**邮件发出去撤不回来**。

#### 2.1 🔴 两个必须先破掉的错觉

**错觉一：「零作用域 ≠ 只读」。**

Cloudflare 的 API Token 是**按作用域（scope）授权**的，`wrangler` 也有账号级/zone 级之分。
**"这个 token 只挂了很少的作用域 / 这个 zone 上没有任何权限 / 这个命令看起来无害"
都不是"它只读"的证据。**
判据只有一个：**它实际改了什么**（线上流量？别人的策略？谁能访问什么？别人的邮箱？）。
⇒ **别因为没有作用域可查、或作用域看起来是空的，就把"不确认"当默认。**
**要判断一条命令是读还是写，去看它实际打出去的 HTTP method 与资源路径，而不是命令的长相。**

**错觉二：「技能里写了步骤，就等于我可以照着做」。**

`cloudflare-one` 的 Guardrails 里自己写着：
「**Do not enable broad production policies without explicit approval.**」
「**Start broad block/allow/DLP/TLS policies disabled limited to a pilot with specific target users or groups
unless the user approves a wider rollout.**」
`cloudflare-one-migrations` 写着：
「**Never create broad allow-all catchalls to preserve connectivity unless explicitly requested and time-limited.**」
「**Disable or delete stale/no-hit rules only with user approval.**」

🔴 **这些是"技能自己就要求先拿同意"的地方** —— 正好和我们的闸二对齐。
**但反过来说：技能里没这么写的地方，照样要过我们的闸二。**
**技能没拦 ≠ 我们可以做。**

#### 2.2 算"必须先进闸二"的动作（逐类点名）

| 类别 | 本簇里具体是哪些 | 为什么重 |
|---|---|---|
| **发布 / 部署** | `wrangler deploy` · `wrangler pages deploy` · `wrangler versions ...` · `wrangler rollback` · CI 里的自动发布 | **直接改线上** |
| **删 / 覆盖远端资源** | `wrangler delete` · 删 KV / D1 / R2 / Durable Objects / Queues · `wrangler r2 object delete` · 覆盖已有 DNS 记录 | **删了不一定能恢复** |
| **改 DNS / 路由 / 隧道** | 改 DNS 记录 · 改 Tunnel 路由（network route / hostname route）· 改 Worker routes · 改 Pages 自定义域 | **改错 = 全站挂** |
| **改 Zero Trust（最需要问）** | 改 Access 应用 / 策略 / 组 / IdP · 改 Gateway 的 DNS / Network / HTTP / Egress 策略 · 改设备配置文件（device profiles）· 改 enrollment 规则 · 改 DLP 配置文件 · 改 TLS 检查（开 decryption）· 改 resolver 策略 · 改 CASB 扫描设置 | **这是在改"谁能访问什么、能不能上网"** —— 影响面是**所有人** |
| **发出去（社会动作）** | 用 Email Service **发邮件**（Workers binding 或 REST）· 开通域名邮件功能（`wrangler email sending enable`）· 建邮件路由 / 转发目的地 · 建 Notify webhook | **邮件发出去撤不回来**；开通域名会**改这个域的邮件发信能力** |
| **改账号 / 计费面** | 改套餐 · 改 token / API key · 改 allowlist（IP / Origin / Address）· 改账号成员与角色 | **改的是谁能用这把钥匙** |
| **写本地秘密** | `wrangler secret put` · 往项目里写 `.dev.vars` / token | **凭据落盘** |

#### 2.3 顺序（先看什么 → 拿什么回执）

1. **先过闸一**：报 `CLOUDFLARE_API_TOKEN` / `CLOUDFLARE_ACCOUNT_ID` **已配 / 未配**、
   wrangler 凭据文件**在不在**、**有效性未验**。要验就**先问主人**能不能花一次 `wrangler whoami`。
2. **先摊开代价，再谈执行**。动手前必须把下面**五件事**摆给主人看：
   - **身份**：用哪一路（wrangler OAuth 还是 API Token）、**是哪个账号**（`account_id` 要指名；
     本机 `default.toml` 里**没有** `account_id` ⇒ **更要问清是哪个账号**）；
   - **目标**：**Worker / Pages 项目名 · zone（域名）· KV/D1/R2/DO 的命名空间或 bucket 名 ·
     Access 应用名 · Gateway 规则名 · 隧道名** —— **一个都不许含糊**；
   - **动作**：**是读还是写**（写在 §2.1 已说清判据）、**是新增还是覆盖还是删除**；
   - **影响面**：**谁会受影响**（线上用户？全体员工的上网？某个域名的全网？收件人？）·
     **能不能回滚**（Cloudflare 有版本与回滚，但**不是所有资源都能**）· **有没有开启"先禁用/只审计/只对试点组"**；
   - **预期花费**：Cloudflare 有大量**按用量计费**的产品（Workers / R2 / D1 / 邮件 / Logpush 等）。
     ⚠️ **本簇没有任何一条技能管定价** ⇒ **能查到就报算法，查不到就说"查不到估价"，不许编一个数**（见 §4）。
3. **能 `--dry-run` 就先 dry-run**（wrangler 的部分命令支持；**具体哪些支持本件未逐条验证**）。
   **能只看不动的就先只看**：`wrangler deployments list` / `wrangler versions list` 这类**读命令**先摸清现状。
4. **必须先"读现状"再"提改动"**：`cloudflare-one` 的 Workflow 第 4 步原文要求
   「**If account access is available, inspect existing resources before proposing or making changes**」——
   列明要看的对象：Access 应用/策略/组/IdP、Gateway 规则/列表/分类、设备配置/态势检查、
   隧道/路由、DNS/解析器设置、locations/sites。
   **这一步全是读，但也是出网 ⇒ 同样先问主人。**
5. **等一次明确同意**。**只覆盖这一条**，不是"以后这类都同意"。
   主人没回话 = **没同意**，停。主人说"先给试点组开" = **授权试点组**，不是"授权全员"。
6. **同意后才执行**，并且**只执行被授权的那一批**：授权试点组就别推全员，
   授权"先禁用建好"就**别顺手启用**（`cloudflare-one` 原文的默认姿势就是
   **"created disabled / audit-mode first, pilot small, compare logs, then expand"**）。
7. **拿回执（缺一不可）**：
   - **资源标识**：Worker/Pages 的 **version id** 或 **deployment id** · DNS 记录的 id ·
     Access 应用 / 策略 / Gateway 规则的 id · 隧道 id · 邮件 `queued` 计数等 —— **指名道姓**；
   - **状态**原文（成功 / 失败 / 进行中），**不许只说"成功了"**；
   - **生效范围**（推给了谁：全体 / 试点组 / 单个域名）；
   - **回滚路径**（怎么退回去：`wrangler rollback`？改回旧记录？禁用新规则？）——
     **`cloudflare-one-migrations` 原文把"rollback 明确"列为验收门，本件照抄执行**；
   - **实际计费口径**（上游回了就原样转述，没回就写"上游未回传计费"）。
8. **不盲重试**：Cloudflare 的写操作**不是都幂等**（新建类重试可能建两份；
   规则类重试可能叠成两条）。**重试前先读一次现状，确认第一次到底成了没有。**
9. **失败就照原样记**：**HTTP 状态码 + `errors[]` / `messages[]` 原文 + 命令退出码一字不改**，
   **绝对不许把失败写成成功**（见 §5）。

🔴 **绝对不允许**：凭据没配就"先试一下" · 主人没明确同意就 deploy / 删 / 改 DNS ·
**把宽泛的 block/allow 规则直接上生产**（`cloudflare-one` 与 `cloudflare-one-migrations` 都明令禁止）·
拿"反正是测试环境"当理由跳过确认（**得先证明那真是测试环境**）·
把一次授权当长期授权 · 看到超时就重发一遍 · 把失败包装成"已生效" ·
用 `--force` / `-y` 之类"跳过确认"的 flag 静默重试。

---

## 3. 按意图分簇（4 条，一条不漏）

**选路总则**：先问**这是"某个具体产品怎么落地"还是"整套网络/安全体系怎么改"**，
再问**是"造新东西"还是"从别家搬过来"**。**拿不准就先说"拿不准"，别硬凑一条。**

### 3.1 平台总纲（**任何 Cloudflare 开发任务的第一站**）—— 1 条

| 技能 | 什么时候用它 |
|---|---|
| **`cloudflare`** | **任何"要在 Cloudflare 上做点什么"的开发任务**，**先读它**。它是**自带约 370 份 references 的平台总纲**：Workers · Pages · 存储（KV / D1 / R2 / Durable Objects / Hyperdrive / Vectorize / Queues / Pipelines）· AI（Workers AI / Vectorize / Agents SDK / AI Gateway / AI Search）· 功能开关（Flagship）· 网络（Tunnel / Spectrum / Smart Placement / Network Interconnect）· 安全（WAF / DDoS / Bot Management / API Shield / Turnstile）· 观测（Analytics Engine / Web Analytics / Tail Workers / Observability）· 媒体（Images / Stream / Realtime / RealtimeKit / Calls）· IaC（Terraform / Pulumi）· 构建（Wrangler / Miniflare / workerd / C3）· 以及 Caching / Cron / Email Routing / Email Workers / Snippets / Workers for Platforms / Workers VPC / Workflows / Artifacts / Containers / Secrets Store / Zaraz 等。**用法是"先用它的决策树找对产品，再加载对应 references"**。🔴 **它的第一条纪律是"别信预训练"**：报限额、价格、类型签名、配置项、兼容性日期之前，**先去取当前文档**；**reference 与文档冲突时以文档为准**。 |

### 3.2 邮件（**发出去的那条**）—— 1 条

| 技能 | 什么时候用它 |
|---|---|
| **`cloudflare-email-service`** | **要在 Cloudflare 上发或收发事务性邮件**时用它：**Email Sending**（Workers binding `env.EMAIL.send()` 或 REST API）· **Email Routing**（收信 `email()` handler / 转发 / 回复 / 解析）· Agents SDK 的 `onEmail()` / `replyToEmail()` · SPF/DKIM/DMARC 与投递率 · `wrangler email` 系列命令 · MCP 邮件工具。触发场景原文列举：给 Worker **加邮件** · 从**外部应用/agent**发信（Node/Go/Python）· 从**编码 agent**发信 · 首次开通 Email Sending 或 Email Routing · 发信进垃圾箱要查投递率。🔴 **原文的第一句是"先查前提"**：① 域名**开通了吗**（`npx wrangler email sending list`，没在列里就 `npx wrangler email sending enable <domain>`）② binding 配了吗（`wrangler.jsonc` 里的 `send_email`）③ 要收信/解析的话 **`postal-mime` 装了吗**（`npm ls postal-mime`）。🔴 **两条硬边界**：**这条只管事务性邮件，原文明确不许拿它做营销/群发**；**REST 与 Workers binding 的字段不一样**（REST 用 `from.address` 与 `reply_to`，binding 用 `from.email` 与 `replyTo`；REST 返回 `{delivered, permanent_bounces, queued}` 而**不是** `messageId`）—— 原文专门用一整张"Common Mistakes"表列这些坑。 |

🔴 **`cloudflare-email-service` 是"发出去"的动作 ⇒ §2 闸二最高一档**：**发邮件前必须先问主人。**

### 3.3 零信任与 SASE（**改别人上网策略的那条**）—— 1 条

| 技能 | 什么时候用它 |
|---|---|
| **`cloudflare-one`** | **要设计 / 配置 / 排障 / 评审 Cloudflare One（零信任与 SASE）部署**时用它。覆盖：**Access**（应用接入控、策略、组、IdP、SaaS 联邦）· **Gateway**（DNS / Network / HTTP / Egress 策略、TLS 解密、DLP）· **Cloudflare One 设备客户端（WARP）**（enrollment 规则、device profiles、split tunnel）· **Tunnel / Mesh**（cloudflared、私有网络、路由、虚拟网络、私有 DNS）· **Cloudflare WAN** 与 Network Firewall · **DLP** · **CASB** · **设备态势**与用户风险 · **Infrastructure Access**（SSH / RDP / VNC / kubectl）· 日志与 Analytics 与 DEX。它的 Workflow 是**五步**：分类问题（架构/配置/排障/迁移/评审）→ 收集上下文（账号、用户站点应用、IdP、SCIM、设备管理、流量路径、合规约束、爆炸半径）→ **按涉及产品只取当前文档** → **有账号权限就先读现状再提改动** → **提出改动集（含前提、验证、回滚），风险动作默认"先禁用或只限试点"**。🔴 **它的 Guardrails 是一串"不许做"**：**不许编 group selector**（没有 SCIM 就没有组）· **不许把 Access Group 与 IdP/SCIM 组混为一谈** · **不许把 Browser Rendering 与 Browser Isolation 混为一谈** · **不许在没配 resolver policy 的情况下指望私有主机名能解析** · **开 TLS 检查与 DLP 之前必须先规划 Do Not Inspect 例外** · **生产策略没明确批准不许开**。🔴 **它明写"启动时先取当前文档"**：报限额、设置、API 字段、分类 ID、精确 UI 路径之前**必须现取**。 |

### 3.4 从别家迁过来（**出方案的那条**）—— 1 条

| 技能 | 什么时候用它 |
|---|---|
| **`cloudflare-one-migrations`** | **要从 Zscaler（ZIA / ZPA）· Palo Alto（NGFW / Prisma / GlobalProtect）· 传统 VPN / SWG / SD-WAN 迁到 Cloudflare One** 时用它：**迁移评估 · 策略映射 · 上线计划 · 对齐度与缺口分析**。它的 Workflow 是**七步**：认源栈 → **先要导出与日志（要结构化导出，不要截图或散文转述）** → 建清单（身份/组/应用/目标/连接器/DNS·URL·防火墙·DLP·TLS 策略/对象列表/站点/例外/命中数/合规日志）→ **出映射计划（源对象 → Cloudflare 目标资源 → 置信度 → 前提 → 不支持或部分支持 → 人工决策）** → **先建依赖**（身份与 SCIM → 连接器/on-ramp → 路由/DNS → 列表/对象 → TLS bypass → Access 应用与策略 → Gateway 策略 → DLP/CASB → 日志）→ **安全分阶段**（加迁移前缀、**规则默认禁用或只审计**、小范围试点、比对日志、再扩）→ **每条源规则都必须有归属**（映射到某个 Cloudflare 对象，**或者**进"未迁移"清单并写明原因与安全影响）。正文按源栈列了**大量具体陷阱**（ZIA 的自定义 URL 分类会裂成 IP/域名/URL 三份列表、CAUTION/warn 行为在 Gateway **没有精确对应**；ZPA 的 app segment / server group / connector group **不是 1:1**、要**每个 connector group 建一条 Tunnel**、ZPA bypass 对应的是 WARP split tunnel 排除项而**不是** Access `bypass`、默认 Access 应用目标上限 **5 个 hostname**、IP 锚定应用要先定 egress 决策；Palo Alto 的**一条规则可能裂成多个 Cloudflare 资源**、App-ID/zone/HIP/解密**很少能精确翻译**）。🔴 **它对"能跑"的要求比别条更狠**：**每一步之后要拿 Cloudflare 对象数与源侧解析数比对，不一致就停**；**`unsupported` / `partial` / `unmapped` / `needs_identity` / `needs_posture` / `manual_review` 每一项都要人工过一遍**；**收尾必须产出"源规则对账表"**。 |

⚠️ **这一条的特殊之处（诚实说）**：它的**正文产出主要是"评估与方案"**，
**它自己直接改远端的机会比另外三条少**（映射表、试点计划、rollback 计划、对账表都是文档）。
🔴 **但这不等于它"零风险"**：**它的方案一旦被执行，全部落到 §2 闸二**；
而且它正文里那些具体动作（建 Tunnel、建 Access 应用、建 Gateway 规则、加迁移前缀）
**本身就是改远端**。⇒ **读它 = 出方案（可以）；照着它动手 = 过闸二（必须先问主人）。**

**分簇小结（4 簇 / 4 条，逐条已点名）**：
平台总纲（开发第一站）1 · 邮件（发出去）1 · 零信任与 SASE（改别人上网）1 · 从别家迁过来（出方案）1 = **4**。

**选路示例**：
"帮我写个 Worker / 用 R2 存东西 / 这个 Pages 怎么配" → `cloudflare`（**先读总纲，再加载对应 references**）；
"给这个站点加一个发信功能 / 邮件进垃圾箱了" → `cloudflare-email-service`🔴 **发出去，先问主人**；
"设计一套零信任接入 / WARP 老是掉 / split tunnel 怎么选 / 要开 TLS 检查" → `cloudflare-one`🔴 **改远端，先问主人**；
"我们要从 Zscaler 搬过来 / 把 Palo Alto 规则翻一遍" → `cloudflare-one-migrations`（**出方案可以，动手过闸二**）；
"把我们 Cloudflare 上的 Worker 发布一下" → **不是某一"条技能"的活**，是 `wrangler` 的操作 ⇒ 🔴 **闸二，先问主人。**

---

## 4. 🔴 本簇**没有**覆盖的几件事（诚实边界，别硬凑）

| 主人可能会问 | 本簇管不管 | 该怎么说 / 该去哪 |
|---|---|---|
| **"这一下要花多少钱？"** | ❌ **不管**。**4 条里没有一条是定价技能**；三条原文都只反复说"**去取当前文档**，别信预训练"。 | **只许报算法（单价 × 用量），不许编单价。** 本机已有的"查定价"能力是 **Ark 那条路**（`gbt-arkcli` 的 `arkcli-pricing`）—— 那是 **BytePlus ModelArk**，**跟 Cloudflare 完全两个产品，绝不通用，别互相顶替**。Cloudflare 的价要现取官方文档（**本件未取，未验**）。 |
| **"还剩多少额度 / 这个月用了多少？"** | ⚠️ **只在细节里沾边**。`cloudflare-one` 提到 Gateway logs / Access audit logs / Logpush / DEX，`cloudflare` 提到 Observability / Analytics Engine / Web Analytics —— **但都是"日志与观测"，不是"账单与配额查询"。** | 如实说"本簇没有查账单/配额的能力"，让主人去 Cloudflare Dashboard 看。**别编一个"查用量"的命令。** |
| **"wrangler 登录了吗？"** | ✅ **能给，但本件没给** —— 需要 `wrangler whoami`，**那是出网**。 | 见 §1：本机只能报**凭据文件在、有效性未验**。**要验先问主人。** |
| **"帮我起一个本地预览服务器"** | ✅ 管（`cloudflare` 的 Wrangler / Miniflare / workerd 那几份 references；`wrangler dev` 之类）。 | ⚠️ **它会占端口、会起进程** ⇒ 按本件纪律：**起服务前先说清端口与用途，先问主人**（本机 3080 已被 DSH Web GUI 占用，别撞）。 |
| **"Cloudflare 上一共有哪些模型 / 我该用哪个"** | ⚠️ **沾边但不是目录**：`cloudflare` 覆盖 Workers AI 与 Vectorize 的**用法**，`cloudflare-email-service` 提到 `cloudflare-docs` 检索工具。 | **要模型目录得现取官方文档**（原文的 Retrieval Sources 表给了取数路）。**本件未取，未验；不许凭记忆列模型名。** |
| **"把我们的邮件域名开一下群发"** | 🔴 **明确不许**。原文写：「Email Service is for **transactional email only**」；营销/群发要用**专门的行销邮件平台**。 | **照原文回绝，并说清是产品边界。** 别拿它去撞群发。 |
| **"Zero Trust 迁移要我 100% 一次切完"** | 🔴 **原文的姿势正好相反**：**要宽泛策略默认禁用、要试点、要并行跑、要能回滚、要出对账表。** | **不许承诺"一次切完"**；把原文的七步工作流与 Validation Gates 摆出来。**"一次全量"要么有明确授权，要么不做。** |

---

## 5. 🔴 报告层红线（读数纪律）

1. **读数先问一句：这是事实，还是我读错了地方？**
   本簇最典型的"读错地方"有六种，**报数前先排除**：
   - **`~/.openclaw-autoclaw/skills` / `~/.agents/skills` 顶层找不到 `cloudflare*`**
     ⇒ 不等于没装，它们在 **`~/.claude/skills`**（§0 已验）；
   - **裸名 `cloudflare` 容易被前缀筛漏掉** ⇒ **用 `cloudflare-*` 筛会得 3 条，
     而验收器要 4 条**（§0 已验）。**报条数时两套口径都要说清。**
   - **`--domain cloudflare` 会多带 4 条无关条目**（3 条 `sandbox-*` 属别的簇，外加它自己）
     ⇒ **`--domain` 不是权威名册，图鉴的 `name` 前缀才是**；
   - **"配置里有 `connector:cloudflare`" ≠ "Cloudflare MCP 能用"**（健康度未验，
     且仓库自述**无 MCP 工具健康**）⇒ 这条最容易被读成"取数路已就绪"；
   - **"`default.toml` 里有 `oauth_token`" ≠ "登录有效"**（§1）；
   - **19681 端口没在听** 影响的是 `autoclaw-*` 那两个 MCP 后端，
     **跟 `connector:cloudflare` 的远端 HTTPS 毫无关系** ⇒ **别张冠李戴**。
2. **有错也照原样记，不许把失败写成成功。**
   保留 **命令退出码** + **HTTP 状态码** + **`errors[]` / `messages[]` 原文**。
   **Cloudflare 的 API 错误信封形状（`success` / `errors` / `messages` / `result`）是它自己的口径，
   别拿别的产品的 `code`/`msg` 去套。**
3. **不许把"命令跑通了"当"事情办成了"**：`wrangler` 退出码 0 只说明**这一次调用**被受理；
   **deploy 要拿到 version/deployment id 才算落地**；**改策略要说清"推给了谁、生效没有"**。
4. **不许编命令、编路径、编技能名、编单价、编限额、编字段名、编分类 ID。**
   `cloudflare-one` 原文**专门禁止**「Never guess category IDs, application IDs,
   wirefilter fields, or API request bodies」。**这条我们照抄。**
   本件出现的每一条命令要么**本机真跑过**（标 ✅），要么明确标 **（未验）**。
5. **不许报"已配/未配"之外的凭据细节**：只许**已配 / 未配**或**前 4 位掩码**。
   **`default.toml` 里的 `oauth_token` 取值永远不许出现在任何报告里。**
6. **凭据未配 / MCP 未接 ≠ 权限被挡。** 那是"东西不在"，不是"门不让你过"。
   **别对着不存在的鉴权反复撞，然后报成"被权限拦了"。**
7. 🔴 **「零作用域 ≠ 只读」**（本簇的核心红线，§2.1）。
   **没有作用域声明、作用域很少、zone 上没有权限 —— 都不是"只读"的证据。**
   判据只有"它实际打出去的是什么"。
8. 🔴 **「能调 ≠ 能用」**：`wrangler --version` 能跑（**这条不需要鉴权**），
   `wrangler whoami` 没验 —— **别拿"wrangler 有反应"当"Cloudflare 上能干活了"。**
9. **`verify-distill.py --cluster cloudflare` 的 FAIL 要读对意思**（见 §6 坑 1）：
   它现在报 FAIL **只是因为登记还没做**，**不是因为规程写坏了**。

---

## 6. 本机踩过的坑 / 已验事实（照做，别自己解读）

1. ✅ **`--cluster cloudflare` 报 `skills_in_atlas = 4`（不是 3）。**
   现读 `py -3.14 tools/codex-scripts/verify-distill.py --cluster cloudflare` 返回：

   ```json
   {"clusters": [{"cluster": "cloudflare", "skill": null,
     "fail": ["omni.py 的 DISTILLED_CLUSTERS 里没登记这个簇"],
     "facts": {"skills_in_atlas": 4}}],
    "hard_failures": 1, "verdict": "FAIL"}
   ```

   （退出码 **1**。）
   🔴 **这是本件最重要的一个发现**：验收器把**裸名 `cloudflare`** 也算进这一簇
   （判据是 `name == 簇名` **或** `name` 以 `簇名 + "-"` 开头）。
   ⇒ **只按 `cloudflare-*` 前缀点名会漏掉一条，验收必然 FAIL。本件已把 4 条全部点名。**
   **FAIL 的另一半原因（"没登记"）由主人处理** —— 本件**不改 `omni.py`、不改 `policy.py`。**
2. ✅ **`omni.py list --domain cloudflare` 带出 7 条，其中 4 条无关。**
   `cloudflare` / `cloudflare-email-service` / `cloudflare-one` / `cloudflare-one-migrations` 是本簇；
   `sandbox-migrate-to-next` / `sandbox-next` / `sandbox-stable` **属 `sandbox` 簇（`gbt-sandbox`）**，
   只是名字/描述里带了 Cloudflare 字样才被这个 `--domain` 筛出来。
   **万能插能力位 0 条** ⇒ **别去 `five-dim.py cap` 里找 `cloudflare` 域的能力位 —— 那里是 0。**
3. ✅ **`omni.py ask` 不路由到 `cloudflare*`。**
   现读 `omni.py ask "给这台机器配 Cloudflare Zero Trust"` → **只落到万能插能力位**
   （`cloud_pc` / `browser` / `stigmergy` / `libtv_workflow` / `desktop_commander`），
   **一条 `cloudflare*` 都没出现**。
   ⇒ **别拿"omni 没推它"当"它不存在"**，也**别拿"图鉴里有它"当"一句话就能调到它"**。
4. ✅ **4 条全部落在 `~/.claude/skills`（单根）。**
   `~/.openclaw-autoclaw/skills` 与 `~/.agents/skills` 顶层**都没有 `cloudflare*`**（已验）。
   `~/.claude/skills` 下现有 4 个 `cloudflare*` 目录（已验）。
5. ✅ **`cloudflare` 那条带着约 370 份 references**（已递归清点：
   60+ 个产品子目录，每个含 `README.md` / `api.md` / `configuration.md` / `gotchas.md` / `patterns.md` 之类；
   `cloudflare-email-service` 带 6 份 references；`cloudflare-one` 与 `cloudflare-one-migrations` 是单文件）。
   ⇒ **"真内容"这一条是验过的**，与 `venice-*` / `fal-*` 的"桩"**不是一回事**。
6. ✅ **wrangler 环境：`4.111.0` 已装（全局 npm），Node `v24.15.0`。**
   **`postal-mime` 全局未装**（原文说收信/解析要用 `npm ls postal-mime` 查，
   本件**只在全局范围查了**，**没在具体项目里查** ⇒ 这一条**只是个线索，不是判决**）。
7. ✅ **两个 wrangler 配置目录都存在，且 `config\default.toml` 里都有 `oauth_token` 与
   `expiration_time` 字段、都没有 `account_id` 字段。**
   **读法是"只数键名命中次数"**，**没有读任何值**（§2 闸一）。
8. ✅ **19681 端口没有在听说明别的事。**
   现读监听端口列表里**没有 19681**；而 `mcporter.json` 里 `autoclaw-productivity` /
   `autoclaw-github` 都指向 `http://127.0.0.1:19681/...`。
   ⚠️ **`connector:cloudflare` 指向的是 `https://mcp.cloudflare.com/mcp`（远端 HTTPS + OAuth），
   跟 19681 无关** ⇒ **别把这两件事混起来报。**
9. ✅ **本件本次全程零出网、零改动。** 跑过的**只有只读/本地命令**：
   `wrangler --version` · `node --version` · `npm ls -g --depth=0` ·
   `Test-Path`（多处）· `Select-String | Measure-Object`（**只数键名，不读值**）·
   `Get-NetTCPConnection -State Listen` · `omni.py list` · `omni.py ask`（一次）·
   `verify-distill.py --cluster cloudflare` · 图鉴与技能原文阅读 · 目录清点 ·
   环境变量存在性检查 · `Get-Command`。
   **没有 deploy 任何东西、没有改任何 DNS 或策略、没有发任何邮件、没有花一分钱。**
10. ⚠️ **（未验）`wrangler whoami` 的真实返回。** 出网 ⇒ 本次没跑。
    ⇒ **"凭据文件在"就到此为止，不许推成"已登录"。**
11. ⚠️ **（未验）哪些 `wrangler` 子命令真的支持 `--dry-run`。**
    本件只笼统写了"部分支持"，**没有逐条验过**。
    ⇒ **别把"原文/惯例说支持"当"我验过它不动手"。**
12. ⚠️ **（未验）Cloudflare MCP（`https://mcp.cloudflare.com/mcp`）到底通不通、
    以及 `cloudflare-docs` 检索工具是否可用。** 需要出网 + OAuth ⇒ 本次没跑。
    ⇒ **而这几条技能反复推荐"用它取数"** —— 所以**这条未验会直接限制本簇的"取当前文档"能力**。
    诚实报法：「MCP 检索路未验，现在只能靠静态 references，取不到最新文档」。
13. ⚠️ **（未验）Cloudflare 的定价、限额、当前产品清单。**
    **本件没有取任何官方文档**（不出网）。⇒ 凡是涉及价格的，本件**只给算法，不给数**。
14. 🔴 **`~/.claude/skills` 是本簇的正文落点，不是我们的托管目录。**
    本件**只读它，绝不改**；本件自己的两份产物落在
    `<仓>/skills/gbt-cloudflare/` 与 `~/.openclaw-autoclaw/skills/gbt-cloudflare/`（§7）。
15. 🔴 **`wrangler` 的闸 ≠ 我们的闸。** `--force` / `-y` / 各命令的交互确认**只是 CLI 的交互控制**；
    **"这件事该不该动生产"没有任何一条命令会替你判断。别拿"CLI 没拦"当"可以发"。**

---

## 7. 固化位置（**重启后要在**）

| 什么 | 在哪 |
|---|---|
| 本规程（源 · 真身） | `<仓>/skills/gbt-cloudflare/SKILL.md` |
| 本规程（装机） | `C:\Users\ADMIN\.openclaw-autoclaw\skills\gbt-cloudflare\SKILL.md`（**与源稿逐字节相同**，用哈希证明） |
| 被规程管的 4 条能力 | `~/.claude/skills/cloudflare` · `~/.claude/skills/cloudflare-email-service` · `~/.claude/skills/cloudflare-one` · `~/.claude/skills/cloudflare-one-migrations`（**不由本件代管，别改**） |
| 不属于本簇但同域被带出的 3 条 | `~/.claude/skills/sandbox-*`（属 `sandbox` 簇 → `gbt-sandbox`，**本件不代管**） |
| 能力名册（现读） | `py -3.14 tools/codex-scripts/omni.py list --domain cloudflare` · `<仓>/state/skill_atlas.json`（`name == cloudflare` 或 `name` 以 `cloudflare-` 开头） |
| 闸一现读 | 环境变量存在性 · `Test-Path` 两个 `default.toml` · **（未验）`wrangler whoami`** |
| 验收 | `py -3.14 tools/codex-scripts/verify-distill.py --cluster cloudflare` |

🔴 **本件只加一份规程，不动门。**
`omni.py`（含 `DISTILLED_CLUSTERS` 登记）与 `security/policy.py` **不是本件该动的东西** ——
**登记由主人做**；本件**不给自己发授权、不调 `tentacle` 任何方法、不碰别的域/别的簇**。

**纪律**：本规程**不代替 Cloudflare 官方文档** ——
**它自己就说了"官方文档是最终事实源"**。取不到文档就**如实报"取不到"**，**不许编读数**。

---

## 8. 诚实边界（这段不许删）

1. **本件是"用法规程"，不是"能力已具备"。**
   它把 4 条技能**分簇、点名、定了两道闸与纪律**；
   但**每条技能的深度用法以它自己的 `SKILL.md` 与那约 370 份 references 为准**，
   而且**以 Cloudflare 官方文档为最终事实源**，本件**不替代**。
2. **本机现状是「wrangler 4.111.0 已装 / 凭据文件在但有效性未验 /
   `CLOUDFLARE_*` 全未配 / `postal-mime` 全局未装 / Cloudflare MCP 配置里有但健康度未验 /
   仓库自述无 MCP 工具健康」**（§1 逐项现读）。
   本件**没有**、也**没能**验证任何一个真实的 Cloudflare 调用 ——
   因为**闸一只到"凭据文件在"这一步，而且验它要出网**。
3. **本次实跑的都是只读/本地命令**（清单见 §6 第 9 条）。
   **任何 deploy、任何远端改动、任何邮件、任何出网请求、任何计费动作，本次都没跑。**
4. **本机状态是 2026-09-22 的现读快照。**
   **换机器、配了 token、验了登录、接了 MCP 之后必须重新现读** ——
   尤其 §1 那张表，**验一次 `wrangler whoami` 就会整片变**，别把这份读数当永久事实。
5. **凭据只报"已配/未配"**：本件**通篇没有出现任何凭据值**；
   `oauth_token` 只被**数了键名命中次数**，**取值一字未读、未打印、未记录**。
6. **本件的每一条技能描述都来自各技能 `SKILL.md` 原文**，不是来自图鉴的 `desc` 字段；
   凡是**照原文抄录而未经本机实测**的（MCP 端点行为、`--dry-run` 支持面、定价、限额、
   各产品当前细节），都已逐处标 **（未验）**。
7. **条数口径两套都已写明**（前缀 `cloudflare-*` = 3；验收器口径 = 4）。
   **本件按 4 条点名**，理由是**验收器按 4 条判通过**，且**多覆盖不构成越界**。
