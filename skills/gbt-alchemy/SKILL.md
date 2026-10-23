---
name: gbt-alchemy
displayName: GBT · Alchemy 技能簇用法规程（alchemy-* · 3 条）
version: 1.0.0
description: GBT小土豆V8 使用 Alchemy 技能簇的用法规程。把 3 条 alchemy-* 技能（写进应用的 API 集成 · CLI 实时链上活 · 托管 MCP 服务）逐条点名并按「交付物是不是要发出去的代码」「CLI 装没装」分簇，规定两道闸（闸一身份与凭据闸，OAuth 会话或 ALCHEMY_API_KEY 只报已配/未配或前 4 位掩码；闸二上链与改远端与花钱闸，凡上链写、改远端云资源、x402 付 USDC、写 webhook、改 app 允许清单的动作一律先问主人），并点破「命令名看起来是读不等于只读」「零作用域不等于只读」这两个坑，以及本机现状（alchemy 0.24.0 已装但 auth status 报 authenticated false、doctor ok false、全部 ALCHEMY 环境变量未配、MCP 未接上）。当用户要查链上余额与交易、查 NFT 与代币价格、模拟交易、读合约、发交易、swap、跨链桥、发 Solana 交易、管 webhook 或 Alchemy app，或问 alchemy-* 技能怎么选、为什么报 AUTH_REQUIRED、这次花了多少钱时使用。
triggers:
  - "alchemy"
  - "Alchemy"
  - "alchemy-*"
  - "@alchemy/cli"
  - "ALCHEMY_API_KEY"
  - "链上"
  - "onchain"
  - "钱包余额"
  - "钱包地址"
  - "交易哈希"
  - "tx hash"
  - "NFT"
  - "ERC-20"
  - "token price"
  - "代币价格"
  - "simulate"
  - "模拟交易"
  - "swap"
  - "跨链"
  - "bridge"
  - "Solana"
  - "webhook"
  - "AUTH_REQUIRED"
  - "x402"
---

# GBT · Alchemy 技能簇用法规程

> 开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属
>
> 这是**我们自己的用法规程**（不是 Alchemy 官方文档的复述，也不是那 3 条技能原文的复述）。
> 那 3 条 `alchemy-*` 讲的是"这一条技能覆盖哪些命令/工具"，本文件讲
> "**在我们这儿，它现在到底能不能跑、身份从哪来、谁在什么条件下按什么顺序去用它，
> 以及什么东西绝对不许自动发上链、发上云、花出去**"。
> 冲突时的裁决顺序：**本文件管我们的纪律** → 各 `alchemy-*` 技能原文管它自己的命令细节。两层都守。

---

## 0. 它是什么 / 在哪 / 🔴 最关键的两个事实

### 事实一：这 3 条**不是桩**，是真内容 —— 但**能力本身在远端**

和 `venice-*` / `fal-*` 那种"只有一个 SKILL.md 的广告位"**完全不同**：
`alchemy-*` 三条**带着真材料**（现读清点）：

| 技能 | 目录里有什么 | `SKILL.md` 体积 |
|---|---|---|
| `alchemy-api` | `SKILL.md` + `agents/` + **`references/`（78 个文件）** + `LICENSE.txt` | 18078 字节 |
| `alchemy-cli` | `SKILL.md` + `agents/` + `LICENSE.txt` | 26278 字节 |
| `alchemy-mcp` | `SKILL.md` + `agents/` + `LICENSE.txt` | 11500 字节 |

**但它们指向的能力全在远端**：链上数据在 Alchemy 的 RPC/Data 端点，
管理面在 Alchemy 的 Admin API，x402 在第三方服务。
⇒ **"技能在本地" 与 "能力在本地" 是两件事。** 本件管的是"能不能真调通"，而现在是**否**（§1）。

### 事实二：这一簇的"副作用"比别的簇重得多 —— **它会动链、动云、动钱**

3 条里出现的动作包括（原文逐条可查）：
**发原生币 / 发 ERC-20 / 调合约写函数 / 授权与撤销 ERC-20 allowance / 同链 swap /
跨链 bridge / 发 Solana 交易 / 委托 SPL 代币 / 建删 webhook / 建删改 app 的
网络·地址·来源·IP 允许清单 / 用 USDC 逐次付费调第三方 API（x402）**。

🔴 **这里面没有一件是"跑错了重来一遍"就完事的**：交易上链即不可撤回，
允许清单改了就是**改了别人的安全边界**，x402 付出去的是**真 USDC**。
⇒ **本簇是"两道闸"里闸二最重的一簇**，读 §2 之前先读 §3。

### 落点与名册（现读）

| 项 | 值（2026-09-22 现读） |
|---|---|
| 条数 | **3 条** |
| 通道 | **`agent-skill`**（按技能名加载执行） |
| 落点 | **2 处**：`C:\Users\ADMIN\.agents\skills\alchemy-*` 与 `C:\Users\ADMIN\.claude\skills\alchemy-*`（图鉴 `roots` 字段两条都登记了） |
| 作者/版本 | `metadata.author = alchemyplatform` · `alchemy-api` v2.0 · `alchemy-cli` v2.1 · `alchemy-mcp` v1.0 |
| upstream 约定 | CLI 包 `@alchemy/cli`（npm）· MCP 端点 `https://mcp.alchemy.com/mcp`（OAuth 2.1 + PKCE）· 控制台 `https://dashboard.alchemy.com/` |

🔴 **两个"别去找"的地方（现读确认）**：

1. **`~/.openclaw-autoclaw/skills` 顶层没有 `alchemy-*`，`~/.openclaw/skills` 也没有。**
   ⇒ **别在托管目录找不到就判"没装"，也别往 `~/.agents/skills` 写任何东西** ——
   那是别家工具的共享目录（本簇的正文**就在那儿**，本件**只读它、不改它**）。
2. **`~/.alchemy` 配置目录不存在**（现读 `Test-Path` = `False`）。
   ⇒ 别假设"有个本地配置目录可以翻"，也别去造一个。

**同族但不在本簇的一条**：`agentic-gateway`（"without an API key"那条路，钱包 SIWE/SIWS + 按次付 USDC）。
它和 `alchemy-*` 互相在正文里点名交接，但它的 `name` **不以 `alchemy-` 开头**，
**按本次口径（以 atlas 里 name 前缀为准）不属本簇** ⇒ 本件**只点名这条边界，不代管它**。

---

## 1. 🔴 本机现状如实读数（2026-09-22 现读快照）

**结论先说：CLI 装上了，但闸一是关着的；MCP 那条路根本没接上。**

| 检查项 | 现读结果 | 怎么读的 |
|---|---|---|
| `alchemy` 命令（CLI） | ✅ **已装**，`0.24.0` | `Get-Command alchemy` → `C:\Users\ADMIN\AppData\Roaming\npm\alchemy.ps1`；`alchemy version` → `{"version":"0.24.0"}` |
| 全局 npm 包 `@alchemy/cli` | ✅ 已装 `0.24.0` | `npm ls -g --depth=0` |
| **登录状态** | 🔴 **未登录** | `alchemy --json --no-interactive auth status` → `{"authenticated": false}` |
| `ALCHEMY_API_KEY` | **未配** | 环境变量现读为空 |
| `ALCHEMY_WEBHOOK_API_KEY` | **未配** | 环境变量现读为空 |
| `ALCHEMY_WALLET_KEY` | **未配** | 环境变量现读为空 |
| `ALCHEMY_NETWORK` | **未配**（⇒ 走默认 `eth-mainnet`） | 环境变量现读为空 |
| 任何 `ALCHEMY*` 环境变量 | **一个都没有** | 按名过滤 `ALCHEMY*` → 空集 |
| `~/.alchemy` 配置目录 | **不存在** | `Test-Path` → `False` |
| `alchemy doctor` | 🔴 `ok: false` | 见下（原文抄录） |
| MCP 是否接上 `mcp.alchemy.com/mcp` | 🔴 **未接** | `.codex/config.toml` / `.claude.json` / Claude Desktop 配置里搜 `alchemy` → **命中 0**；仓内 `config/mcporter.json` 只有 `autoclaw-productivity` / `autoclaw-github` / `notion` / `connector:cloudflare` / `connector:vercel`，**没有 alchemy** |
| 本机 MCP 健康度（仓库自述） | **无 MCP 工具健康** | 工作区 `AGENTS.md` 的 MCP 段现读写着 "No MCP tools are currently healthy." |

**`alchemy doctor` 的真实返回（已验，抄关键段，未删改）**：

```json
{
  "ok": false,
  "checks": {
    "setup": {
      "complete": false,
      "missing": ["Provide one auth path: alchemy auth OR api-key"],
      "nextCommands": ["alchemy auth", "alchemy config set app"],
      "capabilities": {
        "rpc_data":     { "complete": false, "missing": ["api-key"],
                          "nextCommands": ["alchemy config set app", "alchemy config set api-key <key>"] },
        "admin_api":    { "complete": false, "missing": ["auth token"],
                          "nextCommands": ["alchemy auth"] },
        "notify_webhooks": { "complete": false, "missing": ["webhook API key"] }
      }
    }
  }
}
```

**逐条读法**（这三句是本件最该记住的）：

1. **CLI 在 ≠ 能跑。** 二进制装得好好的，`doctor.ok` 是 **false**，
   三个能力面（`rpc_data` / `admin_api` / `notify_webhooks`）**全部 `complete: false`**。
2. **`doctor` 说"没配"是可信的；它说"配好了"要再验一次。**
   技能原文自己警告过一处**已知假阳性**：`doctor` 可能报会话已就绪，
   但 RPC 命令仍失败于 `AUTH_REQUIRED`（因为**没有从 auth token 派生出 API key**）。
   原文的解法是拿 `alchemy evm gas` 做**轻量 RPC 冒烟测试** ——
   ⚠️ **但那是一次出网请求**，按本件闸二**也要先问主人**（只是代价极小、极易被同意）。见 §6 坑 2。
3. **`~/.eigenflux` 之类的"有本地目录"在这里不存在** —— `~/.alchemy` 就是没有。
   ⇒ 别把 `doctor` 的 `nextCommands` 当"我给你跑一遍就好了"，
   那两步（`alchemy auth` / `config set app`）**一个会开浏览器、一个要选 app**，
   **都得主人参与**。

⚠️ **诚实边界**：本件**没有**跑 `alchemy auth login`、**没有**跑 `alchemy evm gas`、
**没有**跑任何业务命令。上表里"未登录"来自 `auth status`（本地读），
**不是**"我试了一次调用然后被拒了"。**两者不许混着报。**

---

## 2. 两道闸（顺序不能颠倒）

### 闸一 · 身份与凭据闸（**先搞清"我代表谁"，再谈"我要做什么"**）

本簇的凭据**不是单一一个环境变量**，而是**多条平行的鉴权路**（技能原文 `alchemy-cli` 的
"Alternative auth methods" 表逐行可查）：

| 路 | 怎么配 | 覆盖哪些命令 | 本机现状 |
|---|---|---|---|
| **浏览器登录（推荐）** | `alchemy auth login`（无头环境加 `--device-code`） | **RPC/Data + Admin 全覆盖**（原文写明：现在**没有单独的 access key 步骤**了） | 🔴 **未登录**（`authenticated: false`） |
| **API key** | `alchemy config set api-key <key>` 或环境变量 `ALCHEMY_API_KEY` | RPC/Data（`evm rpc` / `evm data` / `evm tx` / `solana rpc` …） | 🔴 **未配** |
| **Webhook key** | `alchemy config set webhook-api-key <key>` 或 `ALCHEMY_WEBHOOK_API_KEY` | `webhook` | 🔴 **未配** |
| **Agent 钱包会话** | `alchemy wallet connect --mode session --instance-name <label>`（**要在 dashboard 里批**） | `evm send` / `evm contract call` / `evm approve` / `evm swap` / `xchain bridge` / `solana send` / `* status` / `solana delegate` | 🔴 **未配** |
| **本地钱包** | `alchemy wallet connect --mode local`（EVM 用 `--import <path>`） | 同上，可加 `--signer local` 覆盖 | 🔴 **未配** |
| **x402 网关鉴权（Alchemy 自家 API）** | `alchemy wallet connect --mode local --chain evm` 然后 `alchemy config set x402 true` | 开了 `--x402` 时的 RPC 与 Data | 🔴 **未配** |
| **x402 付第三方** | `alchemy wallet connect --mode local`（配一个 x402 付款 signer） | `alchemy x402 request <url>` / `alchemy x402 balance` | 🔴 **未配** |

**不需要任何鉴权的三条**（原文明确）：`alchemy evm network list` · `alchemy solana network list` ·
`alchemy version` / `update-check`。

**只报状态，绝不报值。** 这是硬纪律，无例外。

```powershell
# ✅ 唯一允许的读法（只出"已配/未配"，不出值）
if ([Environment]::GetEnvironmentVariable('ALCHEMY_API_KEY')) {'已配'} else {'未配'}
# ✅ 要看个影子就只出前 4 位掩码（例：alch****）
#    本机现在是「未配」，没有掩码可给
```

🔴 **绝对不许**：

- **`--reveal` 这个全局 flag** —— 原文自己写着 "Show secrets in plain text (use with care)"。
  **我们不用它。** 本件把它当**危险 flag** 记：任何人（包括我）都不许拿它把
  api key / wallet key 打到 stdout 上。
- 把凭据值 echo 出来 · 写进任何 `.md` / 日报 / `MEMORY.md` / 聊天 · 贴进本规程 ·
  当参数明文传给命令行（**会进 shell 历史与进程列表**）。
- **直接读 `alchemy config list` / `config get` 里的密钥字段**。
  （`config list` 是允许的命令，但**输出里凡是密钥就只报已配/未配**，别把整块 JSON 贴出来。）

🔴 **一处必须我们自己加的纪律（技能原文与它冲突，以本件为准）**：
`alchemy-cli` 与 `alchemy-api` 的原文都推荐用 CLI **把 API key 抽出来并 `persist to 项目的 .env`**，
还给了完整的 `sed`/`grep` 脚本。**那会把凭据落盘到项目目录。**
**我们的规矩是：这一步必须先问主人**——说清"要写哪个 `.env`（绝对路径）、会不会进 git、
写完谁读得到"，**拿到明确同意才做**；同时**无论何时都不许把值贴进对话**（原文自己也是这么要求的）。
⇒ **别照抄那段脚本直接跑。**

**本机闸一现状（2026-09-22 现读）**：`auth status` = `authenticated: false`，
所有 `ALCHEMY*` 环境变量未配，`doctor.ok = false`
⇒ **闸一是关着的**。在主人完成鉴权之前，任何 `alchemy-*` 真调用都**不该被尝试**。

**闸一与闸二的先后**：闸一未过 ⇒ **连闸二都不必谈**（没有可执行的调用）。
需要凭据时：**告诉主人"闸一未过，需要 `alchemy auth login` 或配 `ALCHEMY_API_KEY`"，然后停** ——
**不要自己去要、去猜、去旁路，也不要替主人跑 `auth login`。**

---

### 闸二 · 上链 / 改远端 / 花钱确认闸（**本簇最重的一道**）

**本条高于技能原文，也高于 CLI 自己的任何默认行为。**

**为什么必须由我们拦**：CLI 自己的门**只覆盖一部分**：
它有 `--dry-run`、`--yes`、退出码约定，**但它不会替你判断"这件事该不该做"**。
而本簇的动作里有**不可撤回的链上写、会改别人安全边界的云资源写、真金白银的 USDC 支出**。

#### 2.1 🔴 两个必须先破掉的错觉

**错觉一：「命令名看起来是读，所以是只读」。错的。**

`alchemy evm rpc <method> [params...]` 是**通用 JSON-RPC 直通** ——
**它是不是只读，完全取决于你传的 `<method>`**：

| 传进去的 method | 实际性质 |
|---|---|
| `eth_blockNumber` / `eth_getBalance` / `eth_call` / `eth_getLogs` | **只读** |
| **`eth_sendRawTransaction`** / `eth_sendTransaction` / `eth_signTransaction` | 🔴 **上链写**（要过闸二） |

同理 `alchemy evm trace <method>` / `alchemy evm debug <method>` 也是直通。
⇒ **纪律：凡是对 `alchemy evm rpc` / `evm trace` / `evm debug` / `solana rpc` / `solana das`
这类"直通"命令动手，必须先把 method 名字**报给主人**并说清它是读还是写。**
**别拿"命令是 `rpc`"当"这是读"。**

**错觉二：「零作用域 ≠ 只读」。**

本簇**没有任何"作用域（scope）"声明**可以拿来当护栏 —— 不像别的工具有 scope 列表能查。
**"这个动作没有声明作用域 / 只碰一个对象 / 命令很短"都不是"它只读"的证据。**
判据只有一个：**它实际改了什么**（链上状态？远端资源？谁的安全边界？谁的钱？）。
⇒ **别因为没有 scope 可查，就把不确认当默认。**

#### 2.2 算"必须先进闸二"的动作（逐类点名）

| 类别 | 本簇里具体是哪些 | 为什么重 |
|---|---|---|
| **上链写（不可撤回）** | `alchemy evm send` · `alchemy evm contract call` · `alchemy evm approve`（含 `--revoke`/`--unlimited`）· `alchemy evm swap execute` · `alchemy xchain bridge execute` · `alchemy solana send` · `alchemy solana delegate approve/revoke` · **任何 `evm rpc` 里的 `eth_send*`** | 交易一旦广播**撤不回来**；`--unlimited` 授权是**已知的高危动作** |
| **花钱（真 USDC）** | `alchemy x402 request <url>` · `alchemy x402 balance`（余额读，但配套的付款是花钱）· 任何 `--x402` 计费路径 | 按次付 USDC；原文写明非交互模式下**不给 `--max-payment` 就退出 `9`**，`--yes` 且无上限**退出 `2`** |
| **改远端云资源** | `alchemy webhook create/update/delete` · `alchemy app create/update/delete` · `alchemy app select`（改默认 app）· `alchemy config set`（改本机 CLI 默认，影响后续所有命令） | 会影响线上流量与账号资源 |
| **改安全边界（最需要问）** | `alchemy app networks`（网络允许清单）· `app address-allowlist` · `app origin-allowlist` · `app ip-allowlist` | **这是在改"谁能用这把钥匙"** —— 放宽等于开面，收紧等于可能打断别人的线上服务 |
| **写本地凭据** | 任何把 api key / wallet key 落盘到 `.env` 或配置的动作（§2 上文点名） | 凭据落盘 |
| **提交长任务后重试** | 任何拿到 `call ID` / `tx hash` 之后的"再跑一遍" | **可能在链上重复执行 / 重复扣费** |

#### 2.3 顺序（先看什么 → 拿什么回执）

1. **先过闸一**：报 `auth status` 与相关环境变量**已配 / 未配**。
   未过 ⇒ **到此为止**，只把"缺哪一路鉴权"报给主人。（本机当前就是这一步。）
2. **先摊开代价，再谈执行**。动手前必须把下面**五件事**摆给主人看：
   - **身份**：用哪一路（浏览器会话 / API key / session 签名器 / local 签名器）—— **指名道姓**；
     并说清**用的是哪个 app**（原文有 `APP_REQUIRED` 这个坑，默认 app 没选就别开跑）；
   - **链与网络**：`-n/--network` 到底是哪条（默认 `eth-mainnet`，**别默默用默认**）；
   - **目标**：**合约地址 / 收款地址 / token 合约 / 金额与精度 / call-id 或 tx hash**，**一个都不许含糊**；
   - **影响面**：这笔交易**改谁的什么状态**、能不能撤回、`--unlimited` 会不会开无限授权、
     允许清单改了会**放谁进来或挡住谁**；
   - **预期花费**：gas / fee / USDC 单价，能查到就**报算法**，查不到就**说"查不到估价"**，
     **不许编一个数**（本簇**没有定价类技能**，见 §4）。
3. **先 `--dry-run`**（命令支持时：`webhook *` / `app *` / `x402 request` 都有）。
   **它不广播、不落盘、不花钱**，会把请求原样打出来 —— **直接拿给主人 review**，这是最省的确认方式。
4. **上链动作额外加一道**：原文要求先跑
   `alchemy --json --no-interactive wallet status --verify`
   确认**会话还有效**（过期的签名器 + 已授权的动作 = 最糟的组合）。
   ⚠️ 这一步**也是出网**，按本件纪律**同样先问主人**（只是代价极小）。
   然后**再** `--dry-run`，**再**广播。
5. **等一次明确同意**。**只覆盖这一条**，不是"以后这类都同意"。
   主人没回话 = **没同意**，停。主人说"先发 0.001 试试" = **授权这一笔**，不是"授权这个动作"。
6. **同意后才执行**，并且**只执行被授权的那一笔**：授权 0.001 就别发 0.01，授权 1 张就别发 4 张。
7. **拿回执（缺一不可）**：
   - **call ID 或 tx hash**（原文：钱包签名的 EVM 动作返回 smart wallet **call ID**；
     `alchemy evm status <call-id-or-tx-hash>` 两种都收）；
   - **状态**原文（`queued` / `in_progress` / `COMPLETED` / 失败）；
   - **链上确认**（有区块号/tx hash 就报，别只说"提交成功"——**提交成功 ≠ 上链成功**）；
   - **实际计费口径**（上游回了就原样转述，没回就写"上游未回传计费"）。
8. **长任务不盲重试**：拿到 `call ID` / `tx hash` **先记下来再轮询**。
   **重试 = 可能重复执行、重复扣费**。要重试前**先确认第一次到底成了没有**。
9. **失败就照原样记**：**退出码 + `code` + `message` + `recovery` 一字不改**，
   **绝对不许把失败写成成功**（见 §4 错误码表与 §5）。

🔴 **绝对不允许**：凭据没配就"先试一下" · 主人没明确同意就广播交易 ·
拿"反正是测试网/反正是小额"当理由跳过确认 · 用 `--unlimited` 授权而不单独说明 ·
改允许清单不说明放开了谁 · 把一次授权当长期授权 · 看到超时就重发一遍 ·
把失败包装成"已完成" · **用 `--reveal` 把密钥打出来**。

🔴 **关于 `--yes`**：原文里 `webhook delete` / `app delete` / `x402 request` 这些命令支持 `--yes`。
**`--yes` 是"跳过交互确认"，不是"跳过我们的闸"。**
**看到命令需要 `--yes` 时，先回闸二，把要删/要付的东西摊给主人，拿到同意再追加 `--yes` 重跑。**
**绝不默认加 `--yes` 静默重试。**

**预判与降险（合法且鼓励）**：
优先挑**最省的验证路径** —— 能 `--dry-run` 就先 dry-run；能查余额/模拟就先查；
能小额就先小额。原文给了现成的省法：
`alchemy evm simulate asset-changes` / `execution`（**单笔模拟，只读**）与
`asset-changes-bundle` / `execution-bundle`（**批量模拟，只读**）——
**"先模拟再广播"是本簇的标准降险姿势**，而模拟本身**也出网**，**也要先问主人**。

---

## 3. 按意图分簇（3 条，一条不漏）

**选路总则**（照原文的三问，**别跳**）：
① **这是"本会话里马上做的活"，还是"要写进应用代码、发出去的代码"？**
② **如果是在本会话里做的活：`@alchemy/cli` 在本机装了吗？**
③ **如果是要写进应用的代码：有 API key 吗？**
三问答完，落到下面某一条。**拿不准就先说"拿不准"，别硬凑一条。**

| 问题 | 答案 | 落到哪条 |
|---|---|---|
| 要写**会发出去的应用代码**，且有 API key | — | **`alchemy-api`** |
| 要写会发出去的应用代码，**且没有** API key（自付式 agent / 明确要 x402·MPP） | — | **不在本簇** → `agentic-gateway`（同族，见 §0 边界） |
| 要**在本会话里马上做链上活**，且 **CLI 已装** | 或 CLI 与 MCP 都可用 | **`alchemy-cli`**（**原文：CLI 是首选，拿不准就选 CLI**） |
| 要**在本会话里马上做链上活**，**CLI 没装**，但 MCP 已接上 | — | **`alchemy-mcp`** |
| 要**在本会话里马上做链上活**，**CLI 和 MCP 都没有** | — | **装 CLI，然后用 `alchemy-cli`**（原文明确：**别退回 curl/裸 HTTP** —— 那是 `alchemy-api` 的路） |

### 3.1 应用集成（**写进代码**的那条）—— 1 条

| 技能 | 什么时候用它 |
|---|---|
| **`alchemy-api`** | **要把 Alchemy 接进"会发出去的应用代码"**（服务端 / 后端 / dApp / worker / 脚本，**跑在当前 agent 会话之外**）、且**有或愿意建一个 API key** 时用它。它是**普通服务端集成的首选路**。覆盖：EVM JSON-RPC（HTTP/WSS）、Token API、NFT API、Transfers API、Prices API、Portfolio API、Simulation、Webhooks、Solana（RPC / DAS / Yellowstone gRPC）、**Sui gRPC**、Wallets/Account Kit、Rollup 与一堆 recipes。**`references/` 里有 78 个文件**，深用法以那里为准。🔴 **原文的硬门**：动手前必须确认 `$ALCHEMY_API_KEY`；**不许**退回"无 key 的公开端点"（原文点名不许用 `.../v2/demo`、不许拿 publicnode / llamarpc / cloudflare-eth 之类公共 RPC 兜底）。🔴 **它不是"在本会话里随手查一次"的路** —— 那是 `alchemy-cli`。 |

### 3.2 本会话里的链上实操（**CLI** 那条）—— 1 条

| 技能 | 什么时候用它 |
|---|---|
| **`alchemy-cli`** | **要在本会话里马上做链上活**（实时查询、分析、管理、本机自动化）时用它 —— **原文点名它是"首选的本机运行时路"**。命令按链分组（`evm` / `solana` / `xchain`）与按产品面分组（`wallet` / `app` / `webhook` / `auth` / `config`），**每条都给结构化 JSON 输出**。覆盖：EVM 链上读（余额 / 交易 / 收据 / 区块 / gas / 日志 / 直通 RPC·trace·debug / 合约只读调用）· Data API（ERC-20 余额与元数据、allowance、NFT 列表与元数据、转账历史、现货与历史价格、跨网组合视图）· 交易模拟（单笔/批量 × 资产变化/执行轨迹）· **钱包签名写动作**（send / contract call / approve / swap / status）· Solana（RPC / DAS / send / delegate / program）· 跨链桥 · webhook · app 管理（Admin API）· 用量与计量 · x402 付第三方 · CLI 自管。🔴 **原文的四条硬规矩**：① **每条命令都带 `--json --no-interactive`**；② 退出码 0 读 stdout 当 JSON，非 0 读 stderr 当 JSON；③ **绝不裸跑 `alchemy`**；④ **有 CLI 命令就绝不用 curl/裸 HTTP**（那是 `alchemy-api` 的路）。🔴 **动手前的 preflight 是两条**：`alchemy --json --no-interactive doctor` **加** `alchemy evm gas` —— **原文明确警告 `doctor` 有假阳性**，必须靠 `evm gas` 这个轻量 RPC 冒烟测试兜底（**但它是出网，按本件纪律先问主人**，见 §6 坑 2）。 |

### 3.3 本会话里的链上实操（**MCP** 那条）—— 1 条

| 技能 | 什么时候用它 |
|---|---|
| **`alchemy-mcp`** | **要在本会话里马上做链上活，且符合这三条同时成立**时用它：① 是实时查询/分析/管理/本机自动化；② MCP 客户端**已经**接上 `https://mcp.alchemy.com/mcp`（或主人愿意接）；③ **`@alchemy/cli` 没有装在本地**。原文：**CLI 装了、或两者都有 ⇒ 优先 `alchemy-cli`**。它暴露 **159 个工具 / 100+ 条链**，分三面：**Admin 8**（`ping` / `list_apps` / `get_app` / `select_app` / `create_app` / `update_app` / `list_chains` / `update_allowlist`）· **RPC 123**（标准 EVM RPC 31 · Token API 3 · 转账与收据 2 · 交易模拟 5 · Trace 6 · Debug 6 · ERC-4337 账户抽象 7 · Solana 标准 RPC 50 · Solana Enhanced & DAS 13）· **Data 28**（NFT API 21 · Prices 3 · Portfolio 4）。🔴 **两条操作硬规矩**：① **任何 RPC/Data 工具调用前必须先 `select_app`**（它会把该 app 的 API key 缓存给后面用；没选 app 工具会报明确的错）；② **别从 agent 里用 curl/裸 HTTP 绕开 MCP 服务**（那是 `alchemy-api` 的路）。🔴 **本机现状：第②条前提不成立** —— MCP **没接上**（§1 已验，四处客户端配置里 `alchemy` 命中 0，仓内 `mcporter.json` 里也没有它）⇒ **闸一未过，这条现在跑不起来**。 |

**分簇小结（3 组 / 3 条，逐条已点名）**：
应用集成（写进代码）1 · 本会话实操（CLI）1 · 本会话实操（MCP）1 = **3**。
**真正常用的分工**：**"随手查/随手做" → `alchemy-cli`**（本机已装，路最短）；
**"写进要发出去的代码" → `alchemy-api`**；**`alchemy-mcp` 只在前两条都不成立时才轮到**。

**选路示例**：
"帮我查一下这个地址的 ETH 余额" → `alchemy-cli`（`evm data balance`；**只读，但仍出网，先问主人**）；
"这笔交易到底干了什么" → `alchemy-cli`（`evm tx` / `evm receipt`，或模拟面）；
"这个合约函数调用会有什么后果，先看看" → `alchemy-cli`（`evm simulate asset-changes`，**只读**）；
"把这笔转账真的发出去" → `alchemy-cli`（`evm send`）🔴 **闸二：先 `wallet status --verify` + `--dry-run` + 等主人同意**；
"把这个代币授权撤了" → `alchemy-cli`（`evm approve --revoke`）🔴 **闸二**；
"给我一个能在 Next.js 里查 NFT 的封装" → `alchemy-api`（**要 API key，先过闸一**）；
"我没装 CLI，但 MCP 接上了，帮我查余额" → `alchemy-mcp`（**本机未接 ⇒ 现在不成立**）。

---

## 4. 🔴 本簇**没有**覆盖的几件事（诚实边界，别硬凑）

| 主人可能会问 | 本簇管不管 | 该怎么说 / 该去哪 |
|---|---|---|
| **"这一下要花多少钱？"** | ⚠️ **部分**（**只有 x402 那条有 `--estimate` / `--max-payment`**）。**gas 估价本簇没有专门技能。** | `evm gas` 给的是**当前 gas 价**，**不是你这笔交易的总价**（还要 × gas 用量）。⇒ **能算就给算法，算不出就说"算不出"，不许编一个数。** 本机已有的"查定价"能力是 **Ark 那条路**（`gbt-arkcli` 的 `arkcli-pricing`）—— 那是 **BytePlus ModelArk**，**跟链上 gas / Alchemy 计费完全两回事，别互相顶替**。 |
| **"我用了多少 compute unit / 还剩多少额度？"** | ✅ **管**（`alchemy usage summary` / `usage timeseries`）—— **但有两个读数陷阱**，见下。 | 见下面两条 ⚠️。 |
| **"这张表里的 `usd` 列呢？"** | ⚠️ **`usage timeseries` 只收 `amount`**；`usd` 指标**已被移除**（原文记为 **2026-08-13 服务端变更**）。`usage summary` **两者都收**（逗号分隔）。 | **别把 `--metrics usd` 传给 timeseries**（原文明确：timeseries 上 `usd` 不合法）。**本条本件未实跑验证**（需要凭据）。 |
| **"为什么我要 90 天它只给我 7 天？"** | ✅ **管**，而且是个**读数陷阱**。 | 原文：timeseries 的区间上限按套餐 —— **Free 套餐最多回看 7 天，Pay-as-you-go 最多 30 天**，更长要找销售。🔴 **超限时 CLI 不报错，而是"返回被允许的区间"，并在响应里同时给出"你要的区间"和"我给的区间"** ⇒ **形状对、内容是截断的**。**报数前必须比对这两个区间，别把截断当全量。** |
| **"怎么选默认 app？"** | ✅ 管。 | 报 `APP_REQUIRED` 时：`alchemy --json --no-interactive app select <id>`（等价于 `config set app <id>`）。⚠️ **`app select` 不带 `--no-interactive` 会弹交互选择器** —— 那需要主人参与。 |
| **"Solana 的 swap 呢？"** | ❌ **没有实现**。 | 原文写明 `alchemy solana swap` **reserved for future support and is not implemented**。**别编命令。** |
| **"跨链桥支持哪些链？"** | ⚠️ 原文只写 **Bridge supports EVM mainnets**，具体清单**没给**。 | **别猜链名**；要清单去官方文档（本件**未验**，不做出网）。 |
| **"钱包私钥在哪？"** | 🔴 **永远不答、永远不碰**。 | 原文的关键设计：**session 钱包会话里 agent 永远看不到私钥**；会话会自动过期、可从 CLI 或 dashboard 撤销。**本地钱包模式（`--import <path>`）才是把私钥带进来的** ⇒ **那是主人自己的选择，本件不替它做，也不去读那个文件。** |

---

## 5. 本机踩过的坑 / 已验事实（照做，别自己解读）

1. ✅ **`alchemy version` 是"完全不需要鉴权"的读**（原文明确 `version` / `update-check` 免鉴权），
   已验返回 `{"version":"0.24.0"}`（**注意它也是 JSON**）。
2. ✅ **`auth status` 不需要网络也能给出 `authenticated: false`**（已验）。
   ⇒ 拿它当闸一的现读手段**是安全的、本地的**。
   **但反过来不成立**：它报 `true` 时**仍需 `evm gas` 冒烟测试**（原文的假阳性警告）。
3. ✅ **`doctor` 的 `ok` 不能单独信**（原文自己说的假阳性，§1 已抄）。
   **本机 `doctor.ok` 是 `false`，这一侧是可信的。**
4. ✅ **`--cluster alchemy` 现在必然报 FAIL，且原因是"没登记"，不是"写错了"。**
   现读 `py -3.14 tools/codex-scripts/verify-distill.py --cluster alchemy` 返回：

   ```json
   {"clusters": [{"cluster": "alchemy", "skill": null,
     "fail": ["omni.py 的 DISTILLED_CLUSTERS 里没登记这个簇"],
     "facts": {"skills_in_atlas": 3}}],
    "hard_failures": 1, "verdict": "FAIL"}
   ```

   （退出码 **1**。）`facts.skills_in_atlas` 已经是 3 —— 验收器**已经能看到这 3 条**，
   缺的只是 `omni.py` 的 `DISTILLED_CLUSTERS` 里那一行登记。
   🔴 **登记由主人做。本件不改 `omni.py`、不改 `policy.py`、不动别的域或别的簇。**
5. ✅ **`omni.py list --domain alchemy` 这次只带出本簇 3 条**（没有串入无关条目），
   万能插能力位 **0 条** ⇒ **别去 `five-dim.py cap` 里找 `alchemy` 域的能力位 —— 那里是 0。**
6. ✅ **`omni.py ask` 不路由到 `alchemy-*`。**
   现读 `omni.py ask "帮我查一下这个钱包的链上余额"` → **只落到万能插能力位**
   （`selfscan` / `cross_scan` / `quant_*` 等），**一条 `alchemy-*` 都没出现**。
   ⇒ **别拿"omni 没推它"当"它不存在"**，也**别拿"图鉴里有它"当"一句话就能调到它"**。
7. ✅ **本件本次全程零真调用、零上链、零出网。** 跑过的**只有只读/本地命令**：
   `alchemy version` · `alchemy --json --no-interactive auth status` ·
   `alchemy --json --no-interactive doctor` · `npm ls -g --depth=0` ·
   `omni.py list` · `omni.py ask`（一次）· `verify-distill.py --cluster alchemy` ·
   图鉴与技能原文阅读 · 目录清点 · 环境变量存在性检查 · `Get-Command` · `Test-Path`。
   **没有发出任何一个 RPC 请求、没有广播任何交易、没有花一分钱、没有上传任何素材。**
   ⚠️ **`alchemy evm gas` 这个原文要求的冒烟测试，本次没跑** —— 因为它是**出网请求**，
   按本件闸二**要先问主人**。**未验。**
8. ⚠️ **（未验）`--dry-run` 在每条命令上的真实行为。**
   原文只笼统说 `webhook *` / `app *` / `x402 request` 支持 `--dry-run`。
   **本件没跑过任何一条 `--dry-run`**（都要先过闸一）。
   ⇒ **别把"原文说支持"当"我验过它不广播"**。
9. ⚠️ **（未验）`usage summary` / `usage timeseries` 的真实返回与区间截断行为。**
   需要 Admin API 鉴权，本机未登录 ⇒ 上述"截断"描述**照原文记录，未实跑**。
10. ⚠️ **（未验）MCP 服务端 159 个工具清单与 `list_chains` 的真实返回。**
    MCP 未接上 ⇒ **无法核实**。上述数量**照 `alchemy-mcp` 原文记录**。
11. 🔴 **`~/.agents/skills` 与 `~/.claude/skills` 是本簇的正文落点，不是我们的托管目录。**
    本件**只读它们，绝不改**；本件自己的两份产物落在
    `<仓>/skills/gbt-alchemy/` 与 `~/.openclaw-autoclaw/skills/gbt-alchemy/`（§7）。
12. 🔴 **CLI 的闸 ≠ 我们的闸。**
    `--yes` / `--dry-run` 是 CLI 的交互控制；**"这件事该不该做"没有任何一条命令会替你判断**。
    **别拿"CLI 没拦"当"可以发"。**

---

## 6. 🔴 报告层红线（读数纪律）

1. **读数先问一句：这是事实，还是我读错了地方？**
   本簇最典型的"读错地方"有五种，**报数前先排除**：
   - **`doctor.ok`** —— 有**已知假阳性**（报就绪但 RPC 仍 `AUTH_REQUIRED`）。**别单独信它。**
   - **`usage timeseries` 的区间截断** —— 超套餐上限时**不报错**，返回被允许的区间。
     **别把截断当全量**（§4）。
   - **`--as` 式的身份错位**：本簇的等价物是 **CLI 未登录 vs 已登录、默认 app 选没选**。
     原文点名 `APP_REQUIRED` —— **没选默认 app 时，有些 `app` 子命令根本不知道该对谁动手**。
   - **`evm rpc <method>`** —— **命令名是读，method 可能是写**（§2.1）。**这是最危险的一处。**
   - **`~/.openclaw-autoclaw/skills` 顶层找不到 `alchemy-*`** ⇒ 不等于没装，它们在
     `~/.agents/skills` 与 `~/.claude/skills`（§0 已验）。
2. **有错也照原样记，不许把失败写成成功。**
   保留 **退出码** + `code` + `message` + `recovery`。**本节把原文的错误码表抄在这里**，
   方便对账（原文来自 `agent-prompt`，**本件未逐条实跑**）：

   | code | 退出码 | 可重试 | recovery 要点 |
   |---|---|---|---|
   | `AUTH_REQUIRED` | 3 | 否 | `alchemy auth login`，或设 `ALCHEMY_API_KEY` / `config set api-key` |
   | `INVALID_API_KEY` | 3 | 否 | 换有效 key |
   | `APP_REQUIRED` | 3 | 否 | `app select <id>`（或 `config set app <id>`） |
   | `NETWORK_NOT_ENABLED` | 3 | 否 | 去 dashboard 给该 app 开这条网络 |
   | `SETUP_REQUIRED` | 3 | 否 | 跑 `doctor` 跟 `nextCommands` |
   | `PAYMENT_REQUIRED` | 9 | 否 | 给 x402 钱包充值，或改用 API key |
   | `RATE_LIMITED` | 5 | **是** | 退避重试；考虑升级套餐 |
   | `NETWORK_ERROR` | 6 | **是** | 查网络重试 |
   | `RPC_ERROR` | 7 | 否 | 查 method/params/网络；确认 key 有权限 |
   | `ADMIN_API_ERROR` | 8 | 否 | 看错误信息；admin 命令要已鉴权的浏览器会话 |
   | `NOT_FOUND` | 4 | 否 | 核对 address / hash / id |
   | `INVALID_ARGS` | 2 | 否 | `alchemy --json help <command>` |
   | `INTERNAL_ERROR` | 1 | 否 | 重试或报 bug |

   ⚠️ **`RATE_LIMITED`/`NETWORK_ERROR` 是"可重试"，但对"写动作"要另加一层**：
   **重试写动作可能重复执行**（§2.3 第 8 步）。**别拿"可重试"当"可以无脑重发"。**
3. **不许把"命令跑通了"当"事情办成了"**：退出码 0 只说明**这一次调用**被受理；
   **上链动作要拿到 tx hash / call ID 并且真的上链**才算落地；
   **`--dry-run` 成功一个字都不代表广播会成功。**
4. **不许编命令、编路径、编技能名、编单价、编链名、编工具数。**
   本件出现的每一条命令要么**本机真跑过**（标 ✅），要么**照原文抄录并标（未验）**。
   **没跑过的不许说成跑过。**
5. **不许报"已配/未配"之外的凭据细节**：只许**已配 / 未配**或**前 4 位掩码**。
   **`--reveal` 的输出永远不许出现在任何报告里。**
6. **凭据未配 / MCP 未接 ≠ 权限被挡。** 那是"东西不在"，不是"门不让你过"。
   **别对着不存在的鉴权反复撞，然后报成"被权限拦了"。**
7. 🔴 **「零作用域 ≠ 只读」**（本簇的核心红线，§2.1）。
   **没有任何 scope 声明可查，不等于这个动作是只读的。** 判据只有"它实际改了什么"。
8. 🔴 **「能调 ≠ 能用」**：`alchemy version` 能跑、`doctor` 能跑、`auth status` 能跑 ——
   **这三条都不需要鉴权**。**别拿"CLI 有反应"当"链上活能干了"。**

---

## 7. 固化位置（**重启后要在**）

| 什么 | 在哪 |
|---|---|
| 本规程（源 · 真身） | `<仓>/skills/gbt-alchemy/SKILL.md` |
| 本规程（装机） | `C:\Users\ADMIN\.openclaw-autoclaw\skills\gbt-alchemy\SKILL.md`（**与源稿逐字节相同**，用哈希证明） |
| 被规程管的 3 条能力 | `~/.agents/skills/alchemy-*` 与 `~/.claude/skills/alchemy-*`（**不由本件代管，别改**） |
| 能力名册（现读） | `py -3.14 tools/codex-scripts/omni.py list --domain alchemy` · `<仓>/state/skill_atlas.json`（`name` 以 `alchemy-` 开头） |
| 闸一现读 | `alchemy --json --no-interactive auth status` · `alchemy --json --no-interactive doctor` |
| 验收 | `py -3.14 tools/codex-scripts/verify-distill.py --cluster alchemy` |

🔴 **本件只加一份规程，不动门。**
`omni.py`（含 `DISTILLED_CLUSTERS` 登记）与 `security/policy.py` **不是本件该动的东西** ——
**登记由主人做**；本件**不给自己发授权、不调 `tentacle` 任何方法、不碰别的域/别的簇**。

**纪律**：本规程**不代替 Alchemy 官方文档，也不代替 CLI 自己的 `agent-prompt` 契约**。
凭据没配 / MCP 没接，就**如实报"跑不起来"**，**不许编读数**。

---

## 8. 诚实边界（这段不许删）

1. **本件是"用法规程"，不是"能力已具备"。**
   它把 3 条技能**分簇、点名、定了两道闸与纪律**；
   但**每条技能的深用法以它自己的 `SKILL.md`（以及 `alchemy-api` 那 78 个 references）为准**，
   本件**不替代**。
2. **本机现状是「CLI 已装 0.24.0 / 未登录 / 凭据全未配 / MCP 未接」**（§1 逐项现读）。
   本件**没有**、也**没能**验证任何一个真实的 Alchemy 调用 ——
   因为**闸一没过**。
3. **本次实跑的都是只读/本地命令**（清单见 §5 第 7 条）。
   **任何业务读写、任何出网请求、任何上链动作、任何计费动作，本次都没跑。**
4. **本机状态是 2026-09-22 的现读快照。**
   **换机器、配了 `ALCHEMY_API_KEY`、跑了 `alchemy auth login`、接了 MCP 之后必须重新现读** ——
   尤其 §1 那张表，**闸一一过就会整片变**，别把这份读数当永久事实。
5. **凭据只报"已配/未配"**：本件**通篇没有出现任何凭据值**，
   因为本机 `ALCHEMY_*` 全部**未配**，**没有值可给**，也**永远不该给**。
6. **本件的每一条技能描述都来自各技能 `SKILL.md` 原文**，不是来自图鉴的 `desc` 字段；
   凡是照原文抄录而**未经本机实测**的（错误码表、159 个工具、区间上限、`--dry-run` 行为等），
   都已逐处标 **（未验）**。
7. **`agentic-gateway` 不在本簇**（`name` 前缀不是 `alchemy-`），
   本件只在 §0 / §3 标出它的边界，**不代管它的纪律**。
