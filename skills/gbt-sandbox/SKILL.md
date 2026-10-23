---
name: gbt-sandbox
displayName: GBT · Cloudflare Sandbox 用法规程（3 条）
version: 1.0.0
description: GBT小土豆V8 使用 sandbox-* 技能簇的用法规程。以 state/skill_atlas.json 里 name 前缀 sandbox- 的 3 条为准（sandbox-stable / sandbox-next / sandbox-migrate-to-next），逐条点名「什么时候用它」，按意图分成日常稳定线 / 1.0 preview 线 / 稳定线搬到 1.0 三簇，并先立一道「判线闸」（看 npm 依赖行 + 容器镜像行，两条必须同线）；规定两道闸（凭据只报已配未配或前 4 位掩码，且「非密配置进 sandbox env、活凭据留在 Worker」是硬条款；装包、改 lockfile/Dockerfile、生产容器 rollout 一律先问主人）。同时**纠正一个容易读错的前提**：这 3 条讲的不是本机沙箱，而是 **Cloudflare Sandbox（Cloudflare Containers 上的隔离 Linux，由 Workers 驱动）**这个第三方云产品。当用户要建/改 Cloudflare Sandbox 应用、在 Worker 里跑隔离命令、用 @cloudflare/sandbox 的 exec/sessions/terminals/tunnels，或要把稳定线迁到 Sandbox SDK 1.0 preview 时使用。
triggers:
  - "sandbox"
  - "沙箱"
  - "Cloudflare Sandbox"
  - "@cloudflare/sandbox"
  - "sandbox-next"
  - "sandbox-stable"
  - "sandbox-migrate-to-next"
  - "Cloudflare Containers"
  - "容器沙箱"
  - "隔离 Linux"
  - "1.0 preview"
  - "wrangler deploy"
---

# GBT · Cloudflare Sandbox 用法规程

> 开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属
>
> **边界一句话**：`gbt-tentacle` 管**这台机器的桌面**（手 = UIA 穿透操作、眼 = DXGI 取真帧、
> 网 = 出网读源码、耳 = 出声与听声）；**本件管云端的 Cloudflare 隔离 Linux 容器**——
> 那是一个**由 Workers 驱动的第三方云产品**，你写的是 **TypeScript + npm + wrangler**，
> 跑不在本机。两条线**零重叠**：本件不取屏幕帧、不点鼠标、不碰音频；
> `gbt-tentacle` 也不碰 `@cloudflare/sandbox`。

## 🔴 先纠一个最容易读错的前提：「沙箱」在这台机器上是**三个不同的东西**

本条**必须写在最前面**，因为"沙箱"这个词在本机至少有三种含义，**混在一起会读错地方**：

| # | 说的是什么 | 在哪 | 归谁管 |
|---|---|---|---|
| 1 | **Cloudflare Sandbox** —— Cloudflare Containers 上的隔离 **Linux 容器**，Worker 里用 TS 驱动 | **云端**（`@cloudflare/sandbox` + wrangler） | **本件（`gbt-sandbox`）** |
| 2 | **DSH / 本会话的文件沙箱策略**（本次现读 `danger-full-access`） | 本机 DSH 运行时 | **不归本件**，也不归 `gbt-tentacle`；是 harness 自己的策略 |
| 3 | 本仓 `AGENTS.md` 提到的**沙箱身份** `desktop-vpvp0bp\codexsandboxoffline`（该身份下 `C:\Python312\python.exe` 起不来） | 本机进程身份口径 | **不归本件**；那是本机读数口径问题 |

⇒ **读到 `sandbox-*` 三条技能时，先确认讲的是 ①（云产品）**，**别**把它们当成本机沙箱的操作说明，
**也别**把本机沙箱的读数当成 Cloudflare Sandbox 的状态。**这是本件最值钱的一句话。**

---

## 0. 它是什么 / 在哪 / 条数怎么核（2026-09-22 现读）

| 项 | 值（现读） |
|---|---|
| 权威条数 | **3 条**，`state/skill_atlas.json` 里 `name` 以 `sandbox-` 开头 |
| 核对命令 | `py -3.14 tools/codex-scripts/omni.py list --domain sandbox` → 实测 `agent 技能 3 条` |
| 通道 | **agent-skill**（按技能名加载执行）。⚠️ 万能插里 `sandbox` 域是 **0 个能力位** —— 别去 `five-dim.py cap` 找它 |
| 装机落点 | 🔴 **`C:\Users\ADMIN\.claude\skills\`**（atlas `why` 现读：**「Claude Code 侧」**） |
| 🔴 **不在哪** | `~/.openclaw-autoclaw/skills/` 里 **`sandbox-*` = 0 条**；`~/.agents/skills/` = **0**；`~/.openclaw/skills/` = **0**（本次逐目录扫过） |
| 来源 | **上游 cloudflare/skills** 那套（不是本仓自产，也不是 AutoClaw store 装） |
| 有无附件 | `sandbox-next` **有** `references\`（`api-quick-ref.md` 3344 B · `examples.md` 526 B）；`sandbox-stable` / `sandbox-migrate-to-next` **无**（`has_references: False`） |
| 体量 | `sandbox-stable` 9009 B / 84 行 · `sandbox-next` 7071 B / 69 行 · `sandbox-migrate-to-next` 8128 B / 137 行 |
| 本机有无项目 | 🔴 **没有**。仓内 `@cloudflare/sandbox` 检索**零命中**；仓里唯一的部署配置 `deploy\wrangler.toml` 是 **Cloudflare Pages**（`pages = { directory = "." }`），**不含** `sandbox` / `containers` / `durable` 任何一项 |

**逐条点名（一条不许漏）**：

1. `sandbox-stable`
2. `sandbox-next`
3. `sandbox-migrate-to-next`

**一句话总纲（三条技能自己的推荐口径）**：
**新项目**走 `@next`（`sandbox-next`）；**已在稳定线的应用**留在 `sandbox-stable` 继续发；
**要搬迁**时才用 `sandbox-migrate-to-next`，且**1.0 成为稳定版之前不硬切**。

---

## 1. 先过「判线闸」，再选技能（**顺序不能颠倒**）

🔴 **动手写代码前，必须先看这个 app 真实在哪个包线上**。三条技能**互为排他**，选错线的代价是**混用 API**：

| 看什么 | 必须匹配 |
|---|---|
| **npm 依赖行** | 默认 `@cloudflare/sandbox`（**不是** `@next` / preview tag）→ 走 **stable**；`@cloudflare/sandbox@next`（或别的 preview tag）→ 走 **next** |
| **容器镜像行** | 稳定线镜像（**不是** `cloudflare/sandbox:next`）→ stable；同线 preview（如 `cloudflare/sandbox:next` / `next-python`）→ next |

**分流表（三条技能原文合起来的裁决）**：

| 现读发现 | 动作 |
|---|---|
| 默认 `@cloudflare/sandbox`（无 `@next`） | **停** → 载 **`sandbox-stable`** |
| `@cloudflare/sandbox@next` 或 `next` 镜像 | **停** → 载 **`sandbox-next`** |
| 用户要**从稳定线搬到 1.0 / `@next`** | **停** → 载 **`sandbox-migrate-to-next`**（**不许**在稳定包上"半套"preview API） |
| 只在**稳定线**清理**已废弃 API** | **留在 `sandbox-stable`**，走 [2026 废弃指南](https://developers.cloudflare.com/sandbox/guides/2026-deprecation/)。**那不是搬去 `@next`** |
| 只有**自部署 bridge** | bridge **还没进 1.0 preview 线** → **留在稳定包 + 稳定镜像**（两处原文都这么说） |

🔴 **铁律：Worker 包与容器镜像必须同线，双向都不许混**
（stable Worker + `@next` 镜像 ❌；`@next` Worker + stable 镜像 ❌）。

```
用户要建/改 Cloudflare Sandbox 应用 ──→ 先过判线闸 ┬─ 稳定线     ──→ sandbox-stable
                                                  ├─ @next 线   ──→ sandbox-next
                                                  └─ 要搬迁     ──→ sandbox-migrate-to-next
```

---

## 2. 按意图分簇（3 簇，一条不缺）

### A 簇 · 日常稳定线

| 技能 | 什么时候用它 |
|---|---|
| **`sandbox-stable`** | 在**当前稳定默认包** `@cloudflare/sandbox` 上**建或改** Cloudflare Sandbox 应用：命令、会话（sessions）、文件、端口、隧道、终端、bridge、生产部署，或**留在稳定线**清理废弃 API。**不负责** `@next`（走 `sandbox-next`）、**不负责**搬迁（走 `sandbox-migrate-to-next`）。 |

**它给的契约（非可协商项，原文口径）**：

- `await sandbox.exec(command)` 收**命令字符串**，**命令跑完**才 resolve，返回**缓冲的** `stdout` / `stderr` / `exitCode`。
- 长任务与流式用**稳定线**的命令 API（`startProcess` / `execStream` 及相关 helper）——
  **不是** `@next` 的单 handle 模型。**别在稳定包上编出 `@next` 的 `output()` handle。**
- **Sessions** 可跨命令保存工作目录与环境（默认 session / `enableDefaultSession` / `createSession`）。
- 交互式浏览器终端在稳定线通常用 **`sandbox.terminal(request)`** + session/xterm helper ——
  **不是** preview 的 `createTerminal`（除非包已是 `@next`）。
- 用隧道或大/二进制流时**优先 RPC 传输**；**HTTP/WebSocket 传输已废弃**。
- 非密配置放 sandbox env；**活凭据留在 Worker**；进程要调外部 API 时用 outbound handler。
- 生产 preview 域名走那些 URL 形态时**需要自定义域上的泛域名 DNS**。
- 🔴 **依赖还是 stable 时，不许套用 `@next` 的 argv / `process.output()` API。**

最小形状（原文）：

```ts
import { getSandbox, proxyToSandbox, Sandbox } from "@cloudflare/sandbox";
export { Sandbox };
const sandbox = getSandbox(env.Sandbox, "user-123");
const result = await sandbox.exec('python3 -c "print(2 + 2)"');
// result.stdout, result.exitCode, result.success
```

**留在 stable 的废弃清理**：先升包 + 升匹配镜像，再照指南办。典型检索（原文）：

```sh
rg 'SANDBOX_TRANSPORT|transport:|exposePort\(|enableDefaultSession|execStream\(|readFileStream|writeFileStream'
```

⚠️ **本机没装 `rg`**（现读：**不在 PATH**）⇒ 这条**照抄跑不了**，要换等价检索工具（见 §5 未验项）。**这条路径不会把你切到 `@next`。**

### B 簇 · 1.0 preview 线

| 技能 | 什么时候用它 |
|---|---|
| **`sandbox-next`** | 在 `@cloudflare/sandbox@next`（Sandbox SDK **1.0 preview**）上**建或改**应用：代码执行、AI runner、interpreter、类 CI 任务、终端、文件、挂载、隧道、preview URL、生命周期，或排错。**不负责**默认稳定包（走 `sandbox-stable`）、**不负责** stable→@next 的搬迁（走 `sandbox-migrate-to-next`）。 |

**它给的契约（原文口径，**与 stable 正好相反**，这是最容易记错的一处）**：

- `sandbox.exec(argv)` 收 **argv 列表**，**进程启动**就 resolve，返回 **handle**，**不是**跑完的结果。
- 用 handle 方法收结果：`output()` · `logs()` · `waitForExit()` · `waitForPort()` · `waitForLog()` · `kill(signal?)`。
- **没有隐式 shell**：要 shell 语法就显式给 shell，例如 `["/bin/bash", "-lc", script]`。
- **每次 launch 都是独立的**：一次 `exec` 里的 `cd` / `export` **看不见于**下一次。
  要跨命令就**按次传 `cwd` / `env`**，或者干脆一个 shell 脚本跑完。
- **process handle 没有 stdin** ⇒ 交互式用**终端**（`createTerminal` + `connect`）。
- 本地 `timeout` / `AbortSignal` **只取消"等待"**，**不杀进程**；要杀用 `kill` 或 `exec` 的**远端** `timeout`。
- `getProcess` / `listProcesses` / `getTerminal` / `listTerminals` **不会**启动容器；没容器时返回 `null` / `[]`。
- process / terminal 的 **id 属于"当前容器"**，不是永远属于那个 sandbox id。要跨 replace 存活，
  **存整份 job（argv、cwd、env、app 状态）**，**别只存一个 id**。
- 非密配置只放 `setEnvVars` / launch `env`；🔴 **活凭据留在 Worker**，沙箱调外部 API 用 outbound handler。
- 🔴 **不许编造已移除的稳定线 API**（core 上的 `gitCheckout`、字符串 `exec` 的完成语义、
  session 执行、`sandbox.terminal(request)`）。
- 🔴 **不许对所有错误用同一个 retry 循环**（见 Errors 文档）。

最小形状（原文）：

```ts
import { getSandbox, proxyToSandbox, Sandbox } from "@cloudflare/sandbox";
export { Sandbox };
const sandbox = getSandbox(env.Sandbox, "user-123");
const process = await sandbox.exec(["python3", "-c", "print(2 + 2)"]);
const result = await process.output({ encoding: "utf8" });
// result.stdout, result.exitCode
```

**它自带的非穷尽速查（可选读，本机实测存在）**：
`references/api-quick-ref.md`（**3344 B**，只覆盖 process / terminal / interpreter）·
`references/examples.md`（**526 B**，`next` 分支的 examples 索引）。

### C 簇 · 稳定线搬到 1.0

| 技能 | 什么时候用它 |
|---|---|
| **`sandbox-migrate-to-next`** | **真的动手搬**：把 Cloudflare Sandbox 应用从 stable `@cloudflare/sandbox` 迁到 `@cloudflare/sandbox@next`（Sandbox SDK 1.0 preview），或用户明确说"迁移/升级到 Sandbox 1.0 / `@next`"。**不负责**日常稳定线（走 `sandbox-stable`）、**不负责**新建 `@next` 应用（走 `sandbox-next`）。 |

**工作流（5 步，顺序执行；🔴 任何一步需要用户决定就停在那一步）**：

1. **Review** 硬规则与替换映射表
2. **Audit** 代码库：列命中点与目标形状
3. **Clarify** 问用户（cutover / bridge / Python 镜像 / 映射覆盖不到的调用点）
4. **Upgrade** 包、镜像、代码
5. **Validate**

**硬规则（原文）**：Worker 包与容器镜像必须同 `@next` 线 ·
🔴 **生产 cutover 用即时（immediate）容器 rollout**（stable 与 `@next` 控制协议**双向不兼容**，
渐进 rollout 会留一段**破碎的混合窗口**，在途容器工作会中断）· cutover 后
`await sandbox.exec(...)` 意为**进程已启动**、不是**命令已完成** · argv 原样（无隐式 shell）·
handle **无 stdin** ⇒ 交互用终端 · observation `timeout` / `AbortSignal` **只取消等待**、
不杀进程 · **不许一个 retry 包所有错** · **不许编 API** · **自部署 bridge 留 stable**。

**替换映射表（原文，照抄用）**：

| Stable | `@next` |
|---|---|
| `SANDBOX_TRANSPORT` / `transport` / `setTransport` | 删掉 —— **只用 RPC** |
| `await sandbox.exec("cmd")` → 缓冲结果 | `await sandbox.exec(argv)` → handle，再 `output` / 各种 wait |
| `execStream` / `startProcess` | 同一个 handle：`logs` · `waitFor*` · `kill` |
| 默认 / 命名 sessions | **没了** —— 按次 `cwd`/`env`，或一个 shell 脚本 |
| `sandbox.terminal(request)` / session terminal | `createTerminal` + `terminal.connect(request)` |
| xterm `sessionId` | `terminalId` |
| `Sandbox` 上的 interpreter 方法 | `withInterpreter` → `sandbox.interpreter.*` |
| `gitCheckout` | 用 `exec` 走 argv `git` |
| 字符串 kill 信号 | **只能数字** |
| Files / mounts / backups / ports / tunnels / `proxyToSandbox` | **基本不变**（stable 页面上 session/transport 那部分忽略） |

**审计检索（原文）**：

```sh
rg 'SANDBOX_TRANSPORT|transport:|setTransport|enableDefaultSession|createSession|getSession|deleteSession|execStream\(|startProcess\(|killProcess\(|sandbox\.terminal\(|sessionId|gitCheckout\(|SandboxTransport|ExecutionSession'
```

另外还要查：字符串 `exec(` · 先 `cd` 后另一个 `exec` · `Sandbox` 上裸用 `createCodeContext` / `runCode`。

**要问用户的（原文）**：能否用 `--containers-rollout=immediate` 切生产（在途进程/终端/流可能停）？·
有没有自部署 bridge（留 stable）？· Python interpreter 要不要换 **`-python`** 镜像变体？·
映射表覆盖不到的调用点怎么处理？

**升级（原文）**：`npm install @cloudflare/sandbox@next` · Dockerfile `FROM cloudflare/sandbox:next`
（Python 用 `cloudflare/sandbox:next-python`）；不在浮动 `next` 上时，Worker 与镜像用**同一个 prerelease tag**。

**部署 cutover（原文）**：

```sh
npx wrangler deploy --containers-rollout=immediate
```

`rollout_active_grace_period` 留默认 `0`（被抬高过就设回 `0`）。**cutover 后，deploy 前的 process/terminal id 全部失效。**

**验收 8 条（原文）**：lockfile + Dockerfile 同 `@next` 线 · 对 `@next` 做 typecheck ·
smoke 跑 argv `exec` + `output({ encoding: "utf8" })` · 用到长进程/终端/interpreter 就各 smoke 一遍 ·
错误能区分（unavailable / interrupted-RPC / stale / local wait）· 沙箱 env 里**没有活凭据** ·
**再 grep 一遍已移除的 API** · 生产确实用了 `--containers-rollout=immediate`。

**红旗（原文，见一条就停）**：`@next` Worker 配 stable 镜像（或反向）· 这次 cutover 用了渐进 rollout ·
把 `await exec` 当命令完成 · 以为 `cd`/export 跨 `exec` 保留 · 一个 retry 包所有错 ·
编 `gitCheckout`/进程 stdin/没文档的 API · deploy 后还留着 cutover 前的 process/terminal id ·
没经用户同意就强切生产 · 把活凭据放进 `setEnvVars` / launch `env`。

---

## 3. 两道闸

### 闸① · 凭据闸（**只报已配/未配或前 4 位掩码，绝不贴值**）

本簇**不吃 API key**，但**凭据纪律是它的硬条款**（三条技能都写了），照做：

| 规则 | 出处口径 |
|---|---|
| 🔴 **非密配置进 sandbox env**（`setEnvVars` / launch `env` / sandbox env） | stable + next 两处都写 |
| 🔴 **活凭据留在 Worker**；沙箱进程要调外部 API，走 **outbound handler** | stable + next 两处都写 |
| 🔴 **沙箱 env 里不许有活凭据** | migrate 的「验收 6」+「红旗 9」明写 |
| 🔴 **别问、别 echo、别落盘**任何 token / secret | 本件纪律（同 `gbt-arkcli` / `gbt-lark` 一脉） |
| 🔴 本机是否已配 Cloudflare 凭据 —— **本次没查**（见 §5 未验项），要查也只报**已配/未配**或**前 4 位掩码** | 本件纪律 |

**为什么这条对本簇格外要紧**：`wrangler` 一跑就可能**真的部署到云上**，
而在沙箱 env 里塞活凭据 = 把密钥交给**一个隔离容器里的任意进程**。这是**设计层漏洞**，不是磁盘状态。

### 闸② · 🔴 会改系统配置 / 装包 / 写盘 / 部署的动作，**必须先问主人**

**本簇命中这条的动作密度比 `autoclaw-*` 更高**（这一簇天生就是"改代码 + 发上云"），逐条点名：

| 动作 | 属于 | 为什么必须先问 |
|---|---|---|
| `npm install @cloudflare/sandbox@next` / 换 `@cloudflare/sandbox` 版本 | **装包 + 改 lockfile** | 会**改依赖树**、改 `package-lock.json`；还会连带把 Worker 包推到另一条线 |
| 改 `Dockerfile` 的 `FROM cloudflare/sandbox:...` | **改配置** | 镜像行与包行必须同线，改一半 = **混线**（红旗第 1 条） |
| 🔴 `npx wrangler deploy --containers-rollout=immediate` | **改生产 + 不可逆** | **生产 cutover**：在途进程/终端/流**会被中断**；deploy 前的 process/terminal id **全部失效** |
| 任何 `wrangler deploy` / `wrangler pages deploy` | **改生产** | 往云上写；本仓 `deploy\wrangler.toml` 是 Pages，**别把它当 Sandbox 项目顺手发** |
| 按替换映射表**改代码库** | **写盘（改代码）** | 一次迁移会**大面积改文件**；改前报**命中点清单与目标形状**，等一次同意 |
| 装/换 `rg`（审计检索要用） | **装包** | 本机 **`rg` 不在 PATH**；`winget`/`choco`/`scoop` 装什么都得主人点头 |
| 拆掉 `SANDBOX_TRANSPORT` / 删 session API | **改代码 + 改行为** | 会让**在跑的旧容器**与**新代码**对不上；必须配合即时 rollout 一起做 |
| 给 `rollout_active_grace_period` 改值 | **改部署配置** | 原文要求留 `0`；动它就改变了混合窗口的长度 |

**顺序（先干什么 → 拿什么回执）**：

1. **摊开四件事**：**身份**（哪个 Cloudflare 账号 / 哪个 Worker，**指名道姓**）· **目标**
   （具体仓库路径 + 哪个 `package.json` / `wrangler.toml` / `Dockerfile`）· **内容**（改什么、替换哪些 API）·
   **影响面**（在途进程会不会停、id 失不失效、能不能回滚、旧容器还认不认新协议）。
2. **只读的先跑**：判线闸（读 `package.json` / lockfile / `Dockerfile` 的**行**）、`wrangler --version`、
   `omni.py …`、`Test-Path` —— **这些不写任何东西，不需要许可**。
3. **等一次明确同意**：**只覆盖这一条**。**改生产**这一档尤其要**明确到 rollout 策略**
   （`--containers-rollout=immediate` 会不会断在途工作）。主人没回话 = **没同意**，停。
4. **先改本地、后上云**：升级包/镜像 + 改代码 + 本地 typecheck，**都先在本地做完**；
   **生产是"一次" deploy（Worker + 镜像同线）**。staging/branch 先行。
5. **拿回执**：部署要拿回**这次 deploy 的实际落点与结果**；迁移要拿回**§2 C 簇的 8 条验收**逐条过。
6. **失败就记失败**：原样保留错误类别（unavailable / interrupted-RPC / stale / local wait）与退出码，
   **不许把失败写成成功**。

🔴 **`wrangler` 是本机真实存在的全局命令**（现读 `4.111.0`）⇒ **它能真发上云**。
**"命令在 PATH 里" 不是 "可以自动跑"** —— 本件的闸②就是为了拦这一步。

---

## 4. 🔴 报告层红线（读数纪律）

1. **读数先问一句：这是事实，还是我读错了地方？** 本簇有**四个**会静默给你"对的形状 + 错的内容"的地方：
   - 🕳 **「沙箱」三义**（见开头那张表）：把本机 DSH 文件沙箱 / 沙箱身份，当成 Cloudflare Sandbox 的状态；
   - 🕳 **`exec` 的语义在两条线上正好相反**：stable = **跑完**才 resolve、给缓冲结果；
     `@next` = **启动**就 resolve、给 handle。**同一行代码，两条线上含义不同** ⇒ 报"能跑"之前先报**在哪条线**；
   - 🕳 **process / terminal id 不是永久的**（属"当前容器"，且 cutover 后旧 id 全失效）——
     拿旧 id 报"任务还在"就是读错了地方；
   - 🕳 **`getProcess` / `listProcesses` / `getTerminal` / `listTerminals` 不启动容器**，
     没容器时返回 `null` / `[]` —— **空数组不是"没有任务"，是"容器没起"**。
   ⇒ **报数前先确认：哪条线（stable / @next）· 哪个容器 · 哪个包行对哪个镜像行**，三件事对得上。
2. **"能调" ≠ "能用"（本簇的招牌）**：
   - 技能里给了**一整套文档 URL 与 API 形状**，本机也有 `wrangler 4.111.0` / `npm 11.12.1` /
     `npx` / `node v24.15.0` —— **工具链齐**；
   - 但本机**没有一个 Cloudflare Sandbox 项目**（`@cloudflare/sandbox` 全仓零命中），
     **一次也没跑过** `sandbox.exec` ⇒ **"工具在" ≠ "这条链在本机跑通过"**。
   - **不许因为"文档写着"就报"可用"**；本次的账是**未验**（§5）。
3. **不许把"命令跑通了"当"事情办成了"**：`wrangler deploy` 退出码 0 **不等于**
   在途任务没断、也不等于**包与镜像同线**。要判成败走**它自己的验收清单**（stable 的 ship 前检查 / migrate 的 8 条）。
4. **不许编命令、编路径、编 API**：三条技能**都明文禁止编 API**（`gitCheckout`、进程 stdin、
   没文档的 helper 都是**反复点名的反例**）。本文件出现的每条命令，要么**本次实测过**（§5），
   要么明确标 **（未验）**、要么是**技能原文**（会点明出处）。
5. **不许报凭据细节**：只报**已配 / 未配**或**前 4 位掩码**（§3 闸①）。
6. **🔴 域名/端点别外泄**：三条技能写了**生产 preview 域名需要泛域名 DNS**这类部署事实；
   报告时**只讲规则，不贴本机/本项目的具体域名、账号 id、Worker 名**（同 `AGENTS.md` 的暴露保护）。

---

## 5. 本机真跑过的命令（逐条：命令 → 关键返回 → 判定）

| # | 命令 | 关键返回（抄真实） | 判定 |
|---|---|---|---|
| 1 | `py -3.14 tools/codex-scripts/omni.py list --domain sandbox` | `── 能力位 0 条` + `── agent 技能 3 条`，逐条列出 3 个名字 | ✅ **条数=3，与 atlas 一致**；本簇**不吃授权门** |
| 2 | `py -3.14 tools/codex-scripts/omni.py ask "迁移到 Cloudflare Sandbox 1.0"` | 「走 agent 技能」段：`sandbox-migrate-to-next` **26.4** · `sandbox-next` **26.4** · `sandbox-stable` **26.4**（前三名，分最高） | ✅ **人话 → 技能**这一环**通且准** |
| 3 | `py -3.14 tools/codex-scripts/omni.py ask "sandbox-next"` | 「走 agent 技能」段**空**（点名式 query 没命中技能通道） | ⚠️ **点名不等于命中** —— 走技能要**按名字加载**，别指望 `ask` 替你选 |
| 4 | `py -3.14 tools/codex-scripts/omni.py gaps` | `sandbox-*  3 条  ⏳ 在队里（有技能，但无 GBT 口径规程）` | ⚠️ **交付前的读数**；本条**不会因本件交付而自动变**（§7.2） |
| 5 | `… verify-distill.py --cluster sandbox` | `"skill": null` · `fail: ["omni.py 的 DISTILLED_CLUSTERS 里没登记这个簇"]` · `facts.skills_in_atlas: 3` · `verdict: "FAIL"` · exit 1 | ⚠️ **机检入口对本簇不可用**（红线禁止改 `omni.py`）；**`skills_in_atlas: 3` 这个数是对的** |
| 6 | 逐目录扫 `sandbox-*` 落点 | `.claude\skills` → **3** · `.agents\skills` → **0** · `.openclaw\skills` → **0** · `.openclaw-autoclaw\skills` → **0** | ✅ **落点判清**：只在 Claude Code 侧；**别去托管目录找** |
| 7 | `Get-ChildItem .claude\skills\sandbox-next -Recurse` | `SKILL.md 7071` · `references\api-quick-ref.md 3344` · `references\examples.md 526` | ✅ **附件真在**（`sandbox-stable` / `migrate` 无 `references\`） |
| 8 | `Get-Item` + `Get-FileHash` 三条 | stable **9009 B / 84 行** · next **7071 B / 69 行** · migrate **8128 B / 137 行** | ✅ 体量读数（§0） |
| 9 | `wrangler --version` | **4.111.0**（`%APPDATA%\npm\wrangler.ps1`） | ⚠️ **工具在 PATH，能真发上云** ⇒ §3 闸② 必须拦 |
| 10 | `npm --version` / `npx` / `node --version` | `11.12.1` / `C:\Program Files\nodejs\npx.ps1` / **v24.15.0** | ✅ 工具链齐 |
| 11 | `Get-Command rg` | **不在 PATH** | ❌ 技能原文两条审计 `rg '…'` **照抄跑不了** ⇒ 标未验，见下 |
| 12 | 读 `deploy\wrangler.toml` | `name = "gbt-xiaotudou-v8"` · `compatibility_date = "2024-11-01"` · `pages = { directory = "." }` | ✅ 仓里唯一的 Cloudflare 部署是 **Pages**，**不是 Sandbox** |
| 13 | 在 `deploy\wrangler.toml` 检索 `sandbox\|container\|durable` | **零命中** | ✅ **本机没有 Cloudflare Sandbox 项目** |
| 14 | 全仓 `*.md` / `*.json` 检索 `@cloudflare/sandbox` | **零命中** | ✅ 坐实"无项目、无实测" |
| 15 | `Test-Path skills\gbt-sandbox` / `~\.openclaw-autoclaw\skills\gbt-sandbox` | 交付前**均为 `False`** | ✅ 本件是**新增**，没覆盖旧件 |

**没跑过 / 跑不了的（标未验，不许说成跑过）**：

- 🔴 **任何 Cloudflare Sandbox 真实调用**（`sandbox.exec` / `createTerminal` / `waitForPort` /
  `proxyToSandbox` …）—— 本机**没有项目、没有 `@cloudflare/sandbox` 依赖**。**全部未验**。
- 🔴 **`npm install @cloudflare/sandbox@next`** —— **未验**，且**属装包**（§3 闸②要主人点头）。
- 🔴 **`npx wrangler deploy --containers-rollout=immediate`** —— **未验**，且**属改生产 + 不可逆**。
  本次**故意不跑**。
- ⚠️ **两条 `rg '…'` 审计命令** —— 本机 **`rg` 不在 PATH**，**照抄跑不了**。
  等价做法**未验**（可用 `Select-String -Path <glob> -Pattern '…'` 之类替代，但**本次没跑过**，
  **所以本件不把它写成"已验证的替代命令"**，只记事实）。
- ⚠️ **三条技能引用的全部 Cloudflare 文档 URL** —— 本次**没有逐条出网抓取**（只读技能原文）。
  **文档当前内容未验**。
- ⚠️ **本机 Cloudflare 凭据是否已配** —— **本次没查**。要查也只报**已配/未配**或**前 4 位掩码**。

---

## 6. 固化位置（**重启后要在**）

| 什么 | 在哪 |
|---|---|
| 本规程（源 · 真身） | `<仓>\skills\gbt-sandbox\SKILL.md` |
| 本规程（装机） | `C:\Users\ADMIN\.openclaw-autoclaw\skills\gbt-sandbox\SKILL.md`（**与源稿逐字节相同**） |
| 被规程管的 3 条 | `C:\Users\ADMIN\.claude\skills\sandbox-*`（**上游件，不由本件代管，别改**） |
| 能力名册（现读） | `py -3.14 tools/codex-scripts/omni.py list --domain sandbox` · `<仓>\state\skill_atlas.json`（`name` 以 `sandbox-` 开头） |
| 人话入口 | `py -3.14 tools/codex-scripts/omni.py ask "迁移到 Cloudflare Sandbox 1.0"` → 落到 `sandbox-*` 三条（26.4 并列） |
| 队列读数 | `py -3.14 tools/codex-scripts/omni.py gaps` |

**纪律**：本规程**不代替**那 3 条技能，也不代替 Cloudflare 官方文档。
`omni.py` 与 `security/policy.py` **不是本件该动的东西** —— 本件只加一份规程，**不动门**。
🔴 **绝不写 `~/.agents/skills/`**（那是别家工具的共享目录）；
🔴 **也绝不往 `~/.claude/skills/` 写** —— 那是**上游**的落点，本件只在**本仓 + 托管目录**两处存在。

---

## 7. 诚实边界（这段不许删）

1. **本件是"用法规程"，不是"能力已具备"。** 它把 3 条**点名、分簇、把判线闸与两道闸定死**；
   每条技能的深度契约**以它自己的 `SKILL.md` 为准**（`sandbox-next` 还另有 `references\` 两份），本件**不替代**。
2. **⚠️ 机检入口对本簇现读是 FAIL，且本件不许去修它。**
   `verify-distill.py --cluster sandbox` 报
   **「omni.py 的 DISTILLED_CLUSTERS 里没登记这个簇」**（`facts.skills_in_atlas: 3`）。
   要 PASS 需在 `tools/codex-scripts/omni.py` 的 `DISTILLED_CLUSTERS` 加一行 `"sandbox": "gbt-sandbox"` ——
   **那是改 `omni.py`，本次红线明令禁止**。⇒ 本件只保证**两份产物逐字节相同**（哈希口径），
   **不保证 omni 登记表已更新**。同理 `omni.py gaps` 里 `sandbox-*` **仍显示「⏳ 在队里」**。
3. **本次实跑的全是只读/诊断类**：`omni.py list/ask/gaps` · `verify-distill` · `--version` 类 ·
   `Get-Command` · `Test-Path` · `Get-Item` · `Get-FileHash` · `Get-ChildItem` · `Select-String`。
   **Cloudflare Sandbox 的任何真实调用、任何 `npm install`、任何 `wrangler deploy`，本次都没跑**（§5 末段逐条标未验）。
4. **本机状态是 2026-09-22 的现读快照**（3 条 · 全在 `.claude\skills` · wrangler 4.111.0 · npm 11.12.1 ·
   node v24.15.0 · **本机无 Sandbox 项目**）。**换机器、装上游 skills 更新、换 wrangler 版本后必须重新现读。**
5. **上游会变**：这 3 条来自 **cloudflare/skills**，且 `sandbox-next` 押的是 **1.0 preview** ——
   **preview API 会改**。技能自己就写着「**以 preview 文档与已装的 `@next` 类型为准**」。
   ⇒ 本件记的是**技能原文在 2026-09-22 的样子**，**不是** Cloudflare 当前 API 的保证。
6. **凭据方面本件什么都没查**：本件**不声称**本机 Cloudflare 凭据已配或未配（**未验**）；
   报告时只允许**已配 / 未配**或**前 4 位掩码**。
