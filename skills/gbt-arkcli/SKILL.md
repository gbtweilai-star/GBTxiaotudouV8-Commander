---
name: gbt-arkcli
displayName: GBT · Ark 云端用法规程（BytePlus ModelArk）
version: 1.0.0
description: GBT小土豆V8 使用 BytePlus Ark CLI 的用法规程。规定每条 arkcli 命令必须带的调用前缀、两道闸（登录闸 + 账号验证闸）、按意图选哪个 arkcli-* 技能、计费动作的报价与确认纪律、以及本机已踩过的坑（--code 要给原始 base64、identity.verified=false 会挡计费写入、别改 ~/.arkcli-bp/、region 固定 ap-southeast-1）。当用户要用 Ark 云端做生图/生视频/对话/理解/部署 Endpoint/微调/查账单用量，或任何 arkcli 命令报 401、被闸挡住、路由拿不准时使用。
triggers:
  - "Ark"
  - "arkcli"
  - "BytePlus"
  - "方舟"
  - "ModelArk"
  - "Seedream"
  - "Seedance"
  - "部署 endpoint"
  - "微调"
  - "账单"
  - "用量"
  - "定价"
  - "生图"
  - "生视频"
---

# GBT · Ark 云端用法规程

> 开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属
>
> 这是**我们自己的用法规程**（不是 BytePlus 官方文档的复述）。官方那 25 个 `arkcli-*` 技能讲"每条命令怎么用"，
> 本文件讲"**在我们这儿，谁在什么条件下、按什么顺序、带什么前缀去用它**"。
> 技能之间有冲突时：**官方 `arkcli-shared` 管协议细节，本文件管我们的纪律**，两边都要守。

---

## 0. 它是什么 / 在哪 / 版本怎么控

| 项 | 值 |
|---|---|
| 版本 | **arkcli 1.0.33** |
| 位置 | `%APPDATA%\npm\arkcli.ps1`（全局 npm 装） |
| 状态目录 | `~/.arkcli-bp/` |
| 技能落点 | 9 处（`.agents` / `.claude` / `.gemini`(+antigravity) / `.continue` / `.copilot` / `.openclaw` / `.trae` / `.openclaw-autoclaw`），每处 25 个 |
| 控制面 region | **固定 `ap-southeast-1`** —— 别的 region 无效，**不许当兜底用** |
| 产品边界 | **只做 BytePlus 这一个产品**；不换租户、不借别的产品的凭据/端点/本地状态 |
| 自动更新 | **已关**（`update.mode=disabled`，实测 `previous: disabled`）—— 版本由人控 |

**版本纪律**：想钉死某版 = 先 `arkcli config set update.mode disabled`，再
`npm i @byteplus/ark-cli@<确切版本> -g --registry https://registry.npmjs.org`。
`arkcli update` / `arkcli update --check` 仍可用（那是显式动作，不受 `disabled` 影响）。

---

## 1. 🔴 每条命令都必须带这组前缀（别漏）

```powershell
$env:ARKCLI_NO_UPDATE_NOTIFIER='1'; $env:ARKCLI_CALLER_TYPE='ai_agent'
$env:ARKCLI_CALLER_NAME='unknown_agent'; $env:ARKCLI_SKILL_NAME='<当前那个 arkcli-* 技能>'
arkcli <命令> ...
```

- **每次调用都带全**，不是只带第一条 —— 它冻结已装版本，让**隐式版本检查、更新提示、自动排期**都不会插进来。
- `ARKCLI_CALLER_NAME`：本机没有可用的 agent 标识（只有 `DSH_*`）⇒ 按协议填 **`unknown_agent`**，**不冒认身份**。
- `ARKCLI_SKILL_NAME`：填**真正管事**的那个能力技能；只有本技能自己管的活才填 `gbt-arkcli`。
- 命令互相独立，**别把这几行 export 成全局**去影响别的 shell 活。

---

## 2. 两道闸（顺序不能颠倒）

### 闸一 · 登录闸

```powershell
arkcli auth status --format json      # logged_in 必须 true
```

非交互环境用**两段式**：

```powershell
arkcli auth login --no-browser                          # 取 authorize_url（600 秒有效）
arkcli auth login --no-browser --code <authorization-code>
```

🔴 **踩过的坑（照做，别自己解读）**：`--code` 要给**原始 base64 串**，**不要**先解成 `code=...&state=...` 再传 ——
**CLI 自己会 base64 解码**，传明文它会再解一次，报 `Authorization code is missing the code parameter
(decoded contents: 乱码)`。它自己的报错把这条讲得很清楚。

### 闸二 · 账号验证闸（**计费写入前必过**）

读 `byteplus_sso.identity.verified`：

- `true` → 继续；
- `false` → **停**，把人送去 `https://console.byteplus.com/user/basics/` 完成**开户 + 支付验证**，等；
- 字段缺失 → 结果**未知**，不声称任何一种状态，原样保留后端结构化错误。

**`false` 挡的是这些**：激活模型 / 建 Endpoint / 部署 / 微调 / 建 Managed Agent。
**`false` 不挡**：列模型、查价、查用量、查账单、对话、生图/生视频这类读取与数据面调用（各技能自己的门仍适用）。

**本机当前状态（2026-09-22）**：`logged_in: true` · profile `platform_ap-southeast-1_accountwide` ·
API key active · **`identity.verified: false`**（账号 `paysssk`）⇒ **计费写入类动作现在会被挡**。

---

## 3. 按意图选技能（别拿 API Explorer 当默认入口）

| 人想干什么 | 走哪个技能 | 说明 |
|---|---|---|
| 先确认要不要登录/身份/换 key | `arkcli-auth` | 401、过期、被挡，都先来这 |
| 配置/区域/项目/语言/更新模式 | `arkcli-config` · `arkcli-profile` | 配置诊断走前者，profile 增删选用后者 |
| 查有哪些基础模型 | `arkcli-models` | 公开基础模型目录；自定义模型（`cm-*`）走 custommodel |
| 实时对话 / 推理 / 多模态追问 | `arkcli-chat` | 数据面 Responses API；支持 `@file` 与多轮续接 |
| 生图 / 生视频（Seedream/Seedance） | `arkcli-gen` | 图片同步返回；视频给 `task_id` 后轮询 |
| 看图/看视频/听音频/读文档（12 类任务） | `arkcli-understand` | OCR、bbox、视频问答、ASR、说话人分离、会议纪要等 |
| **建**推理 Endpoint（"部署一个模型"） | **`arkcli-deploy`（优先）** | 只要是**新建**意图就走它，别走 infer-endpoint 的 create |
| Endpoint 生命周期（查/列/启/停/改/删）与部署形态 | `arkcli-infer-endpoint` | 反触发：**创建意图**回 `arkcli-deploy` |
| 实时控制面查询：列资源 / **把 Endpoint 解析成它真正绑定的模型身份** | `arkcli-resources` | 只读：给出 base-model 血缘、能力、工作流与 **Region**；**不写 `profile.yaml`**。要"这个 EP 到底是哪个模型、什么能力"就问它 —— 别拿命名猜 |
| 自定义模型（`cm-*`）上传/量化/删除 | `arkcli-custommodel` | 并用它做直接推理前的 Endpoint 边界检查 |
| 数据集 / 微调 / 训练 | `arkcli-datasets` · `arkcli-train-finetune` | 微调任务 Id 是 `mcj-*` |
| Managed Agent 与会话 | `arkcli-agent` | |
| 账单（结算金额） | `arkcli-billing` | **账单 ≠ 用量**：用量近实时，账单 T+1 从财务视角结算 |
| 用量 / 配额 / 席位消费 | `arkcli-usage` | 席位**管理**（分配/绑定）走 `arkcli-plans` |
| 定价（结算单价 / Coding Plan 价） | `arkcli-pricing` | TTS/ASR/语音类定价**不支持**，别硬查 |
| 套餐（Coding Plan）买/续/席位 | `arkcli-plans` | 解绑**尚未开放**，路由走支持渠道 |
| 接本地编码 agent（Claude Code/Codex/OpenCode…） | `arkcli-helper` | 目标是"把模型接进某个客户端"就走它，别走 auth/config |
| 装/查/刷/卸官方技能 | `arkcli-connect` | **安装不需要登录**；`--path` 是隔离装到指定技能目录 |
| 查 IAM UserID | `arkcli-iam` | 直接走它，别去翻 Raw API Explorer |
| 诊断/查生成来源 | `arkcli-doctor` | `+verify-origin` 要先报**整批**总价、等**一次**确认，再原样转述终端的 JSON |
| 常规动作都没有覆盖 | `arkcli-api-explorer` | **低层兜底**，确认没有稳定产品命令了再用 |
| 首次接入一个模型进应用 | `arkcli-onboard` | 认证 → 账号闸 → 选可部署模型 → 复用或安全新建 Endpoint |

**选路顺序（照 `arkcli-shared`）**：产品命令（`arkcli <域> <动词>` 或 `arkcli +<工作流>`） >
先读该能力的参考文档 > 再考虑 API Explorer。**别从 API Explorer 起步。**

---

## 4. 我们的纪律（在官方协议之上）

1. **计费动作先报价再确认**：任何会花钱的动作（生图/生视频/部署/微调/`doctor +verify-origin`），
   **先把代价说清、等一次明确确认**，再执行。确认覆盖范围要说准（是这一批，还是这一条）。
2. **绝不外泄凭据**：不 echo、不落盘的还有 token / API key / access key / secret key。
   需要给人看就只报 `已配置 / 未配置` 或前 4 位掩码（例 `VxCg****8AeZ`）。
3. **不直接读写 `~/.arkcli-bp/`**：一律走命令，让密钥保持掩码、让迁移保持完整。
4. **不换产品、不换 region**：固定 `ap-southeast-1`；别拿别的产品同名命令当兜底。
5. **遇 401 别乱重试**：先回闸一查登录与身份，别对着业务命令反复撞。
6. **登录/选模型/选 profile 都不是最终交付**：它们是中间步骤，**办完原任务才算完**。
7. **`--dry-run` 在 `config` / `profile` 全域被拒**：要预告变更就**原样复述要做的改动**并先取得确认，
   不要假装有预览。`profile show/list` 会同步远端 key 并回写本地清单，**不是无副作用**。
8. **别把本规程当官方文档替代**：命令级细节以对应 `arkcli-*` 技能为准。

---

## 4.5 🔴 报告层红线 + 未验账（后补，对齐其余规程的硬要求）

> 这一节是**体检器**指出缺项后补的（`tools/codex-scripts/audit-regulations.py` 报"缺：报告层红线、未验账"）。
> 补它的理由不是形式：Ark 这条链上**"看起来像失败"和"真的是失败"差得很远** ——
> 抓错一次就白花一笔钱，或白等一张根本不存在的授权。

**红线：读数先问"这是事实，还是我读错了地方"**（四条本机实测过的）：

1. **被闸挡住 ≠ 命令写错了** —— 先看返回里的 `status` 与**缺哪个作用域 / 哪道闸**，
   再决定说"没配好"还是"没授权"。参数写错会先抛参数类错误，别把两者混成一句"跑不了"。
2. **`identity.verified = false` 挡的是"计费写入"那一类**，不是"整个 Ark 都用不了" ——
   范围说小、说准；不许拿它当"全都不能干"的借口，也不许绕过去硬试。
3. **`--code` 要给原始 base64** —— 转义/换行/引号写法会让调用在**碰门之前**就失败，
   现象看着像"参数不对 / 服务端拒绝"，实际是**本地把字符串改了**。**先怀疑自己手里的载荷。**
4. **`reason` / `how_to_grant` 常常只覆盖第一个缺的作用域** ⇒ 判缺什么一律读
   **`missing_scopes` / `missing` 全量数组**，别只读那句人话。

**未验账（写这份规程时"没跑过"的一律在这里；谁跑过谁把它挪出去并附原样返回）**：

| 没跑过的东西 | 为什么没跑 |
|---|---|
| `arkcli auth login`（含两段式 `--no-wait` / `--device-code`） | **会改本机登录态**，是主人的授权动作 |
| `arkcli config init --new` / 换 region / 换 profile | 改本机配置；且 region **固定 `ap-southeast-1`**，不当兜底试 |
| `arkcli update` | 升版本**会连带换掉全部 AI Skills**，版本归人控 |
| 任何**计费动作**（生图 / 生视频 / 部署 Endpoint / 微调 / 批量理解） | 花钱 + 出网，要过 §2 两道闸与报价确认 |
| `doctor +verify-origin` 的真批次 | 有单价、要一次确认覆盖整批，无需求时不试跑 |

> 纪律：**本规程里凡没有"命令 => 读数"证据的结论，一律按上表口径当"未验"**；
> 要把某行挪出去，必须**附上那次的原样返回** —— 不许只删表不加证。

---

## 5. 固化与依赖

| 什么 | 在哪 |
|---|---|
| 本规程（源） | `<仓>/skills/gbt-arkcli/SKILL.md` |
| 本规程（装机） | `~/.agents/skills/gbt-arkcli/` · `~/.openclaw-autoclaw/skills/gbt-arkcli/` |
| Ark 能力面声明 | `<仓>/holo_pet/ark_surface.json`（由 `tools/codex-scripts/make_ark_surface.py` 现读技能目录生成） |
| 能力台呈现 | `/api/capabilities` 的 `app.ark`（25 条）；能力球上是一条 `arkcli` 域、**紫环＝外部 CLI**、**不给"调用"按钮**（它不走 `/api/capability`） |
| 人话落点 | `python tools/codex-scripts/omni.py ask "查一下这个月花了多少"` → 会落到 `arkcli-billing`（`agent-skill` 通道） |

**依赖是真外部进程**：`arkcli` 必须已装且已登录；本规程**不代替**它。装/卸/换版本见 §0。
