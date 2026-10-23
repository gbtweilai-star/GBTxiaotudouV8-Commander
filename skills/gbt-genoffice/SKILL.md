---
name: gbt-genoffice
description: GenOffice 蒸馏版能力面（主人令 2026-09-27）：本地文档引擎全接（info/convert/create/slides/sheet/docs/merge/pdf/render/guide）· 免费AI 保留（search/image/media，耗 provider 积分）· **五个控制端显式移除**（open/selection/mcp/install-cli/skill）· 主控是万能插 run_task。
---

# gbt-genoffice · GenOffice 蒸馏（我们的用法）

> **口径**：GenOffice = Electron 应用（568M）+ 一套**很强的本地 CLI**（v0.10.1467，装在
> `%LOCALAPPDATA%\Programs\GenOffice\resources\cli\genoffice.cmd`）。
> 我们**不用它的应用进程**，只用它的 **CLI 引擎**；主控是我们自己的万能插。

## 1. 三步蒸馏（主人令原文：蒸馏成我们的 / 移除控制端 / 保留免费AI / 万能插主控 / 挨个接好）

### ① 接进来的（本地引擎 · 零云依赖 · 免费）
| op | 干什么 | 读/写 |
|---|---|---|
| `info` | 文档元数据与结构摘要（pptx/xlsx/docx/pdf） | 读 |
| `pdf` | 逐页读 PDF 文本层（**不需要 app 进程**） | 读 |
| `guide` | 写 ops/spec 前必读的 op 参考与设计指南（**要带域**：`guide slides`） | 读 |
| `capabilities` | 哪些云功能已配置（体检用） | 读 |
| `convert` | 格式转换（引擎级） | **写** |
| `create` | 从结构化内容建文档 | **写** |
| `merge` | `{{key}}` 占位符填充模板（docx/pptx/xlsx + JSON） | **写** |
| `slides` | 读/改/审/渲染 pptx（含版面审计、单页重建） | 读写并存（读子命令直连） |
| `sheet` | 读/改 xlsx（与应用同一条写路径） | 同上 |
| `docs` | 读/改 docx（与应用 in-app AI 同一套 op） | 同上 |
| `render` | **每页一张 PNG**（给 agent"用眼睛验收"用） | **写（出图）** |

### ② 保留的免费 AI（**走主人自配 provider，不是我们自建**）
`search` · `image` · `media` —— 经 Genspark / Serper / Tavily / Parallel 等。
⚠️ **口径**：这三个**会耗主人账号的积分**，**不许念成"全免费"**；本地那 11 个才是真免费。

### ③ 控制端类命令（**默认不接 · 主人点名放行 · 有留痕**）
| 命令 | 它是什么（默认不接的原因） |
|---|---|
| `open` | 拉起它的 **GUI 进程**并操控界面 —— 那是**它的控制面**；我们的主控是 `run_task` |
| `selection` | 读用户在**它编辑器里的选中** —— 依赖它的 GUI 控制面 |
| `mcp`（尤其 `--http`） | 它的**远程控制入口**（Streamable HTTP 服务器）—— 移除，避免出现第二条控制通路 |
| `install-cli` | 改本机 **PATH**（越界写入） |
| `skill` | 改**别的 coding agent** 的 MCP/技能配置（越界写入） |

**这不是拒绝**（主人 2026-09-27 纠正：「谁让你拒绝的啊，按我说的做」）：
带 `allow_control_endpoint: true` 点名即执行，并往 `state/genoffice_control.jsonl` 写一条留痕；
不带开关时返回 `{"ok": false, "needs_optin": true, "how": {...}}` —— **它只是告诉你开关在哪**。

## 2. 怎么用（主控 = 万能插）

```python
import gbt_allinone as g
g.run_task("genoffice", {"op": "status"})                      # 体检（版本 + 蒸馏口径 + capabilities）
g.run_task("genoffice", {"op": "ops"})                         # 自述能力面（接了哪些/移除哪些）
g.run_task("genoffice", {"op": "info", "args": ["<文件>"]})     # 读类：直连
g.run_task("genoffice", {"op": "render", "args": ["<文件>"]})   # 写类：过 filesystem_write 门
g.run_task("genoffice", {"op": "run", "args": ["help", "slides"]})   # 逃生舱：透传 CLI
```

**门**：读类直连；**写类过 `filesystem_write`**（拒绝时返回 `how_to_grant` 原文，交主人终端发放）。
**逃生舱**（`run`）保留，但**移除的控制端无法从逃生舱绕过**（同一个 `_REMOVED` 表先拦）。

## 3. 为什么"只用 CLI、不用它的应用"
- 应用进程 = 登录态 + 自动更新（`app-update.yml`）+ 遥测 + GUI 控制面 ⇒ **都不进我们的链路**；
- CLI 的本地引擎**零云依赖**（`pdf` 那类明确写着"without any app process"）；
- 于是"体积/依赖"留在它那边，**控制权在我们这边** —— 与主人令「以万能插为主控」同义。

## 4. 实测读数（2026-09-27 · 本机）
| 项 | 读数 |
|---|---|
| `status` | `genoffice 0.10.1467` · capabilities 已读 |
| `info`（真读 PDF） | `ok=true · exit=0 · pdf · 16 pages` |
| `pdf`（缺子命令） | 如实报 `expected "pdf read <file.pdf>"` —— **不装成功** |
| `render`（写面） | `denied=true · gate=filesystem_write` + 授权命令原文 |
| 控制端类（不带开关） | `ok=false · needs_optin=true` + 开关位置（**不是拒绝**） |
| 控制端类（点名放行） | 过开关 → 撞 `filesystem_write` 写门（`install-cli` 要写 PATH）⇒ 门是主人定的，一条命令可开 |
| 放行留痕 | `state/genoffice_control.jsonl` 追加一行（谁 · 何时 · 哪条） |
