---
name: gbt-lark
displayName: GBT · 飞书/Lark 用法规程（lark-cli）
version: 1.0.0
description: GBT小土豆V8 使用飞书/Lark 能力的用法规程。规定 lark-cli 的调用姿势（每轮显式 --as、shortcut > 已注册 API > api 裸调、机器读取前静音 notice）、两道闸（身份闸 bot vs user + 高风险确认闸 exit 10）、28 条 lark-* 技能按意图的分簇与选用、写出去的动作必须先问主人的先后顺序与要拿的回执、凭据只报「已配/未配」的纪律，以及本机已踩过的坑（auth status/whoami 不认 --format 只认 --json、Risk 行在 help 末尾不在顶部、bot 查用户资源会返回空成功而非报错）。当用户要发飞书消息、看日程开会、读写云文档/表格/多维表格、处理审批与任务、管云盘与知识库、发邮件、查 OKR 考勤，或任何 lark-cli 命令报 unknown flag、被 exit 10 挡住、身份/权限拿不准时使用。
triggers:
  - "飞书"
  - "lark"
  - "Lark"
  - "lark-cli"
  - "发消息"
  - "群聊"
  - "通讯录"
  - "日历"
  - "日程"
  - "会议室"
  - "云文档"
  - "多维表格"
  - "知识库"
  - "审批"
  - "待办"
  - "云空间"
  - "云盘"
  - "邮件"
  - "妙记"
  - "会议纪要"
  - "OKR"
  - "考勤"
  - "画板"
  - "幻灯片"
---

# GBT · 飞书/Lark 用法规程

> 开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属
>
> 这是**我们自己的用法规程**（不是 lark-cli 官方文档的复述）。官方那 28 条 `lark-*` 技能讲
> "每条命令怎么用"，本文件讲"**在我们这儿，谁在什么条件下、按什么顺序、带什么前缀去用它，
> 以及什么东西绝对不许自动写出去**"。
> 冲突时的裁决顺序：**本文件管我们的纪律** → `lark-shared` 管协议细节 → 各业务技能管命令细节。三层都守。

---

## 0. 它是什么 / 在哪 / 版本怎么控

| 项 | 值（2026-09-22 现读） |
|---|---|
| 工具 | **lark-cli 1.0.95** |
| 位置 | `C:\Users\ADMIN\AppData\Roaming\npm\lark-cli.ps1`（全局 npm 装，**在 PATH 里**） |
| 品牌 | `brand: "lark"`（**Lark 国际版**，不是 feishu 域名；端点 `open.larksuite.com`） |
| 应用 | appId 已配置（掩码 `cli_a933****`）· profile 名 = appId |
| 技能落点 | **3 处**：`~/.agents/skills` · `~/.claude/skills` · `~/.openclaw/skills`，每处 **28 条** |
| 通道 | **agent-skill**（按技能名加载执行）。⚠️ 万能插里 lark 域是 **0 个能力位** —— 别去 `five-dim.py cap` 找它 |
| 权威名单 | `lark-cli skills list`（现读，`count: 28`）与 `state/skill_atlas.json` 里 `name` 以 `lark-` 开头的条目一致 |
| 升级 | `lark-cli update`。**会同时更新 CLI 和 AI Skills**，是显式动作，**不由我们自动跑** |

**版本纪律**：本机 `doctor` 报 `1.0.95 → 1.0.96 available`（`cli_update: warn`）。
这是**告警不是故障**。要不要升由主人定；升之前先知道它**连技能一起换**，规程结论可能跟着变。

---

## 1. 调用姿势（每条命令的规矩）

### 1.1 选命令的优先级（照 `lark-skill-maker`）

```
lark-cli <service> +<verb>                       # ① Shortcut（高级封装）—— 优先
lark-cli <service> <resource> <method>           # ② 已注册 API（带类型）
lark-cli api <METHOD> <path> [--data/--params]   # ③ 裸调任何 OpenAPI —— 低层兜底
lark-cli schema <service>.<resource>.<method>    # 先查参数/类型/scope/risk，再动手
```

**纪律**：**别从 `api` 裸调起步**。先 `--help` 看有没有 `+shortcut`，没有再用已注册 API，
都没有才落 `api`，而且**落 `api` 前必须先按 `lark-openapi-explorer` 从官方文档挖出方法/路径/参数/scope**，
**不许猜路径**。

### 1.2 每轮显式 `--as`（本机 `defaultAs = "auto"`）

本机 `whoami` 报 `identitySource: "auto_detect"`、`defaultAs: "auto"` ⇒ **省略 `--as` 时身份不确定**。
需要稳定身份时**全程显式**写 `--as user` / `--as bot`，别靠自动选择。

### 1.3 机器读取前静音 notice

```powershell
$env:LARKSUITE_CLI_NO_UPDATE_NOTIFIER='1'; $env:LARKSUITE_CLI_NO_SKILLS_NOTIFIER='1'
lark-cli auth status --json
```

它压掉 `_notice`（升级 / skills 落后 / 废弃命令）对 JSON 的干扰。
**注意**：压掉的是 `_notice`，**不是** `doctor` 自己的 `cli_update` 检查 —— 那个照样报。

### 1.4 一次调用，一条命令

命令互相独立，**别把环境变量 export 成全局**去影响别的 shell 活。

---

## 2. 两道闸（顺序不能颠倒）

### 闸一 · 身份闸（**动手前先搞清楚"我代表谁"**）

| | `--as user` 用户身份 | `--as bot` 应用身份 |
|---|---|---|
| **代表谁** | 用户**本人** | 应用**自己** |
| **能干什么** | 用户自己的资源：日历、云空间/云盘/云存储、邮箱、个人文档、待办、审批 | **只**访问 bot 自己的资源；应用级操作 |
| **不能干什么** | —— | 🔴 **看不到用户资源**；**不能代表用户操作**（发消息以应用名义发、建文档归属 bot） |
| **凭据从哪来** | 飞书开发者后台开 scope **+** 用户过 `auth login` 授权，**两层都要满足** | 只需后台开 scope **+** 本地已配 appId/appSecret，**不需要 `auth login`** |
| **本机状态** | ✅ 可用（`status: needs_refresh`，**调用时自动刷新**） | ✅ 可用（`status: ready`） |

🔴 **本机最危险的坑（官方原文，照做）**：**bot 查用户资源会返回"空成功"而不是报错**。
比如 `--as bot` 查日程，它会返回 **bot 自己的（空）日历**，`ok: true`，**看起来一切正常**。
⇒ **读用户数据必须显式 `--as user`；拿不准就先 `lark-cli whoami` 看当前生效身份。**

**bot 缺权限时**：把错误里的 `console_url` **原样**给主人，让他在开发者后台开 scope。
🔴 **绝不对 bot 执行 `auth login`**（那是用户身份的动作，对 bot 跑等于跑错闸）。

**user 缺权限时**：错误里有 `missing_scopes`（N 选 1）+ `console_url` + `hint`。
按**最小权限**走 `lark-cli auth login --scope "<missing_scope>" --no-wait --json`。
多次 login 的 scope **会累积**（增量授权）。

**凭据纪律（硬）**：

1. 🔴 **不许把凭据写进任何文件、任何聊天** —— 不 echo、不落盘、不贴进规程、不贴进日报、不贴进 MEMORY。
   包括 appSecret、accessToken、refreshToken、user_access_token。
2. 要给人看**只报**「**已配 / 未配**」，或**前 4 位掩码**（例 `cli_a933****`）。
3. 🔴 **不直接读也不直接写 lark-cli 的 config / profile 存储** —— 一律走命令，让密钥保持掩码。
4. 需要主人看授权链接时：URL **当 opaque string 原样转发**（不编解码、不加标点、不重拼 query），
   并用 `lark-cli auth qrcode <url> --output <相对路径>` 生成二维码，**URL 在前、二维码在后**。

### 闸二 · 高风险确认闸（`exit code 10`，**是门禁不是错误**）

风险三档：`read` | `write` | **`high-risk-write`**。查法（**已验**）：

- shortcut：`lark-cli <service> +<cmd> --help` —— **Risk 行在 help 的末尾**（见 §6 坑 2）
- service 命令：`lark-cli schema <service>.<resource>.<method>` —— 返回里有 `"risk": "..."` 和 `"scopes": [...]`

`high-risk-write` 缺确认 flag 时，CLI 以 **退出码 10** 退出，stderr 给结构化信封：

```json
{ "ok": false, "error": { "type": "confirmation", "subtype": "confirmation_required",
  "action": "drive +delete", "risk": "high-risk-write", "hint": "add --yes to confirm" } }
```

**处理顺序（照 `lark-shared-high-risk-approval`）**：

1. **识别**：`exit 10` + `error.type == "confirmation"` + `error.subtype == "confirmation_required"`；
2. **向主人确认**：把 `error.action`、`error.risk` 和**关键参数**摊开说明，明确讲"这是高风险操作"；
3. **主人明确同意** → 按 `error.hint` 取确认 flag（多数是 `--yes`），**追加到自己原始 argv 的末尾**后重试；
4. **主人拒绝** → 终止，**不改写参数、不跳过门禁**。

🔴 **绝对不允许**：看到 `exit 10` 就默认加 `--yes` 静默重试（= 等于把门禁关了）·
把 `confirmation_required` 当网络/权限错误处理 · 主人没明确同意就追加确认 flag ·
用 shell 拼字符串重试（**用参数数组传 argv**，别让 shell 把主人给的参数当语法解析）。

提前预判：命令支持 `--dry-run` 时先跑它 —— **它不触发确认门禁**，会打印完整请求
（URL / body / params），可以直接拿给主人 review。

---

## 3. 🔴 写出去的动作必须先问主人（本规程的硬条款）

**本条高于 CLI 自己的闸。** 理由（已验）：`lark-cli im +messages-send --help` 的 Risk 是
**`write` 而不是 `high-risk-write`** ⇒ **CLI 不会拦它、不会要 `--yes`**。
但"发一条消息给真人群"是不可撤回的社会动作 —— **CLI 不拦，我们必须自己拦**。

**算"写出去"的动作**（一律先问主人）：

- 发消息 / 回复消息 / 发交互卡片 / 加急（`lark-im`）
- 发邮件 / 回复 / 转发（`lark-mail`）
- 发帖、改群名/群公告、拉人进群/移出群（`lark-im`）
- 新建 / 编辑 / 覆盖文档、表格、幻灯片、画板、多维表格记录（`lark-doc` / `lark-sheets` / `lark-slides` / `lark-whiteboard` / `lark-base` / `lark-markdown`）
- 发起审批 / 建任务 / 改任务状态 / 指派别人（`lark-approval` / `lark-task`）
- 云空间上传 / 新建文件夹 / 复制 / 移动 / **删除** / 改权限、改知识库节点与成员（`lark-drive` / `lark-wiki`）
- 建日程 / 改日程 / 邀请参会人 / 订会议室（`lark-calendar`）
- 部署或发布妙搭应用（`lark-apps`）
- 写 OKR 进展 / 目标 / 关键结果（`lark-okr`）

**顺序（先干什么 → 拿什么回执）**：

1. **摊开四件事**：**身份**（`--as user` 还是 `--as bot`，即"以谁的名义"）· **目标**
   （`chat_id` / `open_id` / `file_token` / `doc token`，**指名道姓**）· **内容**
   （原文，或至少是逐字摘要）· **影响面**（谁会看到、能不能撤回、删了能不能恢复）。
2. **`--dry-run` 先跑**（命令支持时）：把 URL / body / params 原样贴给主人看。**这一步不写任何东西。**
3. **等一次明确同意**：**只覆盖这一条**，不是"以后这类都同意"。主人没回话 = **没同意**，停。
4. **同意后重试**：在**自己的原始 argv** 上追加确认 flag（如 `--yes`）—— 不是重写一条新命令。
5. **拿回执**：成功要读到 **`ok == true`**（或退出码 0）+ **业务 id**
   （`message_id` / `file_token` / `doc token` / `task_guid` / `approval instance code`）。
   把"发到哪个群 / 改的哪个文档"报全，别只说"成功了"。
6. **失败就记失败**：原样保留后端错误（`error.type` / `subtype` / `code` / `message` / `hint`），
   **不许把失败写成成功**（见 §5）。
7. **不许静默重试写操作**：写动作可能带幂等键，盲重试 = **重复发送**。重试前先确认第一次到底成没成。

**判断成功必须用 `ok == true`（或退出码 0），不要用 `code == 0`**（`lark-shared` 原文警告）：

- 成功信封在 **stdout**、退出码 0，**没有**顶层 `code` / `msg`；
- `code` 只出现在**错误**信封的 `error` 里，含义是上游 OpenAPI 的 numeric code。

按 OpenAPI 老格式 `{"code": 0, "msg": "ok"}` 判成功，会把**所有成功调用误判为失败** ——
封装写入类命令（如 `task +create`）时尤其危险，**误判会绕过幂等逻辑导致重复创建**。

---

## 4. 按意图选技能（28 条，一条不漏）

**选路总则**：先 `lark-cli <service> --help` 看有没有 `+shortcut`；每条命令动手前读**对应技能**；
技能间边界冲突时以**技能自己的 desc** 为准（下面每条都给了"什么时候用它"）。

### 4.1 共用协议层（**先读这三条，再碰业务**）

| 技能 | 什么时候用它 |
|---|---|
| **`lark-shared`** | **一切 lark-cli 活的底座，最先读**。身份（user vs bot）、`auth login/status/logout`、`--domain` 业务域授权、`missing_scopes`、输出契约、`exit 10` 高风险门、相对路径限制、`_notice`。 |
| **`lark-skill-maker`** | 要把飞书操作**封成可复用的 Skill** 时（包装原子 API 或编排多步流程）。它给 `SKILL.md` 模板与"description 决定触发"的原则。 |
| **`lark-openapi-explorer`** | 需求**现有技能和已注册 API 都覆盖不了**时。从官方文档库（`open.feishu.cn/llms.txt` → 模块 → 单 API）**逐层挖**原生 OpenAPI，再用 `lark-cli api` 裸调。**低层兜底，不是默认入口。** |

### 4.2 消息与群

| 技能 | 什么时候用它 |
|---|---|
| **`lark-im`** | 发/回消息、搜聊天记录、下载聊天里的图片文件、看群成员、搜群、建群/话题群、管理表情回复、发**加急**（应用内/短信/电话）、发与处理**交互卡片**（含 `card.action.trigger` 回调）、Feed 置顶与标签。**所有发出去的动作先过 §3。** |

### 4.3 通讯录

| 技能 | 什么时候用它 |
|---|---|
| **`lark-contact`** | 把**姓名/邮箱解析成 `open_id`**，或按 `open_id` 反查姓名/部门/邮箱/联系方式/个人状态/签名；也可按关键词搜可见的机器人/智能体。**别人提到一个名字、下一步要给他发消息或排日程时，先走它拿 id。** 部门树遍历/按部门列员工**不归它**（走原生 OpenAPI）。 |

### 4.4 日历与会议

| 技能 | 什么时候用它 |
|---|---|
| **`lark-calendar`** | 看/搜日程、创建/更新日程、管参会人、查忙闲与推荐时段、**预定会议室**。**排会（未来）走它**；查**过去**的视频会议记录走 `lark-meeting`。 |
| **`lark-meeting`** | 视频会议的**记录与产物**：纪要/逐字稿/妙记的查询、妙记搜索/上传/下载/编辑、机器人参会；**进行中**会议与**实时**会中内容问答、发会中聊天与表情。入口是 `meeting_id` / `meeting_no` / `event_id` / `note_id` / `minute_token` / 妙记 URL。 |
| **`lark-minutes`** | ⚠️ **转发桩**：**仅当用户或上游显式点名 `lark-minutes`** 时用它；实际一律**交由 `lark-meeting` 处理**。 |
| **`lark-note`** | ⚠️ **转发桩**：同上，显式点名时才用，实际交 `lark-meeting`。 |
| **`lark-vc`** | ⚠️ **转发桩**：同上，显式点名时才用，实际交 `lark-meeting`。 |
| **`lark-vc-agent`** | ⚠️ **转发桩**：同上，显式点名时才用，实际交 `lark-meeting`。 |

**读法**：这一簇**真正干活的是 `lark-calendar` + `lark-meeting` 两条**；那 4 条是"只认点名"的兼容别名。
**别主动往那 4 条上路由** —— 除非主人自己说了那个名字。

### 4.5 文档与表格（内容操作）

| 技能 | 什么时候用它 |
|---|---|
| **`lark-doc`** | **云文档（Docx）内容**：读、建、编辑正文，插入或下载图片附件，思维笔记。主人给文档 URL/token（含 `doubao.com` 的 `/docx/`、`/wiki/`）时用它 —— **按 URL 路径/token 路由，不看域名**。独立评论操作走 `lark-drive`。 |
| **`lark-sheets`** | **电子表格**：建表、工作表与行列结构（增删/合并/调尺寸/隐藏/冻结）、读写单元格（值/公式/样式/批注/单元格图片）、查找替换、批量更新，以及图表/透视表/条件格式/筛选器/迷你图/浮动图片。含财务建模（DCF、三张表、预算、Sensitivity）。**想按名字找表格文件，先用 `lark-drive` 的 `drive +search` 定位。** |
| **`lark-slides`** | **幻灯片**：建演示文稿、读内容、管页面（建/删/读/局部替换）。**不负责**云文档正文（走 `lark-doc`）、文档内独立画板（走 `lark-whiteboard`）、普通文件上传下载（走 `lark-drive`）。 |
| **`lark-whiteboard`** | **画板**：导出为预览图片、导出原始节点结构、用多种格式更新画板内容。文档**内嵌**的表格/Base 不归它（走 `lark-sheets` / `lark-base`）。 |
| **`lark-markdown`** | **飞书原生 Markdown 文件**：查看、创建、上传、编辑、**比较远端版本与本地草稿**。**纯本地 Markdown 不动它**；把 Markdown **导入成在线文档也不归它**。 |

### 4.6 知识库

| 技能 | 什么时候用它 |
|---|---|
| **`lark-wiki`** | **知识空间与节点**：建/查知识空间、看管空间成员、管节点层级（移动/复制/快捷方式）。在知识库里找或建文档、浏览空间结构时用它。**上传文件到节点下走 `lark-drive`；编辑正文走 `lark-doc`。** |

🔴 **Wiki token 路由（`lark-wiki-token-routing`，最容易搞错的一处）**：
URL 里的 `/wiki/<token>` 是**节点 token**，**不一定是**底层对象的 token。要对底层对象动手，
**先解包再按底层类型路由**：

```powershell
lark-cli drive +inspect --url 'https://xxx.feishu.cn/wiki/<wiki_token>'          # 优先方式
lark-cli wiki +node-get --node-token 'https://xxx.feishu.cn/wiki/<wiki_token>' --format json
```

按 `data.obj_type` 分流：`docx`/`doc` → `lark-doc` · `sheet` → `lark-sheets` · `bitable` → `lark-base` ·
`slides` → `lark-slides` · `file` → `lark-drive` · `mindnote` → 云空间能力走 `lark-drive`、节点层级走 `lark-wiki`。
评论/权限/导出/下载这类**云空间能力一律走 `lark-drive`**。
**别把底层对象 token 当节点 token 用**（反之亦然）。

### 4.7 云空间（云盘）

| 技能 | 什么时候用它 |
|---|---|
| **`lark-drive`** | **云盘/云存储**：上传下载、建文件夹、复制/移动/**删除**、看元数据、查权限设置、评论/权限/订阅、标题、版本、密级标签（secure labels）、**本地文件导入**（Word/Markdown/Excel/CSV/PPTX/.base → docx/sheet/bitable/slides）。整理云盘目录、判断链接类型/真实 token/标题都走它。**它也是所有"云空间能力"（评论、权限、导出、下载）的落点。** |

### 4.8 多维表格

| 技能 | 什么时候用它 |
|---|---|
| **`lark-base`** | **Base / 多维表格**：建表、字段、记录、视图、统计、公式/lookup、表单、仪表盘、**应用模式（BaseApp/AppMode 页面与组件）**、Workspace 目录、workflow、角色权限、模板中心。见 `/base/` 或 `/app/` 链接就走它。**BaseApp 不走 `lark-apps`**；文件导入导出转 `lark-drive`。 |

### 4.9 审批与任务

| 技能 | 什么时候用它 |
|---|---|
| **`lark-approval`** | **审批**：查处理待办/已办/实例，搜可发起的审批定义、看定义详情、**发起原生审批实例**。⚠️ **审批待办不是飞书任务** —— 非审批类待办走 `lark-task`。它**不负责**创建审批定义；三方审批定义不走原生提单。 |
| **`lark-task`** | **任务与清单**：建待办、看/改状态、拆子任务、组织清单、分配协作成员、上传任务附件、注册/注销**任务智能体**、更新智能体主页数据、写智能体任务记录。 |

### 4.10 邮件

| 技能 | 什么时候用它 |
|---|---|
| **`lark-mail`** | **邮箱**：起草/写邮件、草稿、发送/回复/转发、查阅、搜索、文件夹、标签、联系人、**监听新邮件**、收信规则。**只走邮件意图**；文档/表格/日历/纯通讯录查询/IM 聊天**不走它**。 |

### 4.11 目标与考勤

| 技能 | 什么时候用它 |
|---|---|
| **`lark-okr`** | **OKR**：看/编辑周期、目标、关键结果、对齐关系、量化指标、进展记录。**不负责**待办（`lark-task`）、日程会议（`lark-calendar`）、绩效评估。 |
| **`lark-attendance`** | **考勤**：只查**自己的**考勤打卡记录。 |

### 4.12 事件流

| 技能 | 什么时候用它 |
|---|---|
| **`lark-event`** | **实时事件监听/订阅/消费**：`lark-cli event consume <EventKey>` 以 **NDJSON** 流式吐事件（IM 消息/表情/群变更、审批状态变更、任务更新、VC 会议开始/加入/结束、妙记生成、画板更新…）。用于**写飞书机器人、实时消息处理、长驻订阅者、流式 webhook/推送处理器**。支持 `--max-events` / `--timeout` 有界运行，**stderr 有 ready-marker 契约**，就是为"AI agent 当子进程跑"设计的。 |

### 4.13 应用开发与托管

| 技能 | 什么时候用它 |
|---|---|
| **`lark-apps`** | **妙搭（Spark/Miaoda）**：建应用、本地全栈开发、云端生成迭代、创意设计（UI mockup/可交互原型/线框图/落地页/仪表盘/幻灯片 deck/视觉探索）、AI 与飞书平台能力集成、日志/Trace/监控/PV/UV、环境变量、协作者与角色、自动化触发器（定时/记录变更/Webhook/审批）。主人要"**开发/新建一个系统·工具·平台·应用**"或"用 HTML 做页面并部署"时走它。**不负责**普通云盘上传（`lark-drive`）、飞书文档编辑（`lark-doc`）、原生幻灯片（`lark-slides`）。 |

### 4.14 工作流编排（**多技能串起来的两条**）

| 技能 | 什么时候用它 |
|---|---|
| **`lark-workflow-standup-report`** | **日程待办摘要**：编排 `calendar +agenda` + `task +get-my-tasks`，生成指定日期的日程与未完成任务摘要。用来回答"今天/明天/本周有什么安排"。 |
| **`lark-workflow-meeting-summary`** | **会议纪要整理**：汇总指定时间范围内的会议纪要并生成结构化报告。用来出**会议周报**、回顾一段时间会议内容。 |

**选路示例**：主人说"帮我看看今天要干什么" → `lark-workflow-standup-report`（不是 `lark-calendar`）；
"把上周的会议整理成周报" → `lark-workflow-meeting-summary`；
"给我一个能用的报名系统" → `lark-apps`。

---

## 5. 🔴 报告层红线（读数纪律）

1. **读数先问一句：这是事实，还是我读错了地方？**
   lark-cli 有好几个地方会**静默地给你一个"对的形状 + 错的内容"**：
   - `--as bot` 查用户资源 → **空成功**（`ok: true`，数据是 bot 自己的空集）；
   - `/wiki/<token>` 当底层对象 token 用 → 形状对、对象错；
   - `--as` 省略 → 身份由 `auto_detect` 决定，可能不是你意图的那个。
   ⇒ **报数前先确认身份、token 类型、命令层级三件事对得上。**
2. **有错也照原样记，不许把失败写成成功。** 保留 `error.type` / `subtype` / `code` / `message` / `hint`，
   以及**退出码**。`exit 10` 是**门禁**，**不是**失败 —— 两者不许混着报。
3. **不许把"命令跑通了"当"事情办成了"**：`ok: true` 只说明**这一次调用**被受理；
   写动作要拿**业务 id 回执**才算落地（见 §3.5）。
4. **不许编命令、编路径、编技能名**：本文件里出现的每一条命令要么**已在本机跑过**（标 ✅），
   要么明确标 **（未验）**。**没跑过的不许说成跑过。**
5. **不许报"已登录/未登录"之外的凭据细节**：只报**已配 / 未配**或**前 4 位掩码**。
6. **身份不同 ≠ 权限被挡**：身份不对时先回闸一，**别对着业务命令反复撞**。

---

## 6. 本机踩过的坑（照做，别自己解读）

1. ✅ **`auth status` / `whoami` 不认 `--format`，只认 `--json`。**
   `lark-cli auth status --format json` 实测报
   `unknown flag "--format" for "lark-cli auth status"`（`exit 2`）。正确写法：

   ```powershell
   lark-cli auth status --json          # ✅ 已验
   lark-cli whoami                      # ✅ 已验（whoami 只认 --as）
   ```

   ⚠️ 但 **shortcut 上 `--format` 是合法 flag**（`--format json|pretty|table|ndjson|csv`，默认 json），
   `--json` 是 `--format json` 的简写（`calendar +agenda --help` 已验）。
   ⇒ **`--format` 可用与否随命令层级不同，"照着别处抄"就会撞 unknown flag。**
   注意 `lark-shared` 的 reference 里写的是"`--format json`（默认）"—— 那句讲的是**输出契约**，
   **不等于每个命令都收 `--format`**。

2. ✅ **Risk 行在 `--help` 的末尾，不在顶部。**
   `lark-shared-high-risk-approval` 说"shortcut `--help` **顶部**会显示 `Risk: high-risk-write`"。
   实测 `lark-cli drive +delete --help` 的 `Risk: high-risk-write` 打在**最后一行**，
   前面是 Usage/Flags。**只知道看顶部会漏判风险等级。**

3. ✅ **`drive` 没有 `file.delete` 这个 schema 资源。**
   `lark-cli schema drive.file.delete` 报 `Unknown resource`（`exit 1`），
   可用资源是 `files`（copy/create_folder/list/patch）等。**删除走 `drive +delete` shortcut，
   或 `api DELETE` 裸调 —— 别编 schema 路径。**

4. ✅ **CLI 的闸不等于我们的闸。**
   `im +messages-send` 的 Risk 是 **`write`**（**不是** `high-risk-write`）⇒ CLI **不会**要 `--yes`。
   但发消息是**不可撤回的社会动作** ⇒ 必须由 §3 我们自己的条款拦。**别拿"CLI 没拦"当"可以发"。**

5. ✅ **`schema` 是动手前唯一可靠的"风险 + scope"读法。**
   `lark-cli schema drive.files.patch` 返回里有 `"risk": "write"` 和 `"scopes": [...]`。
   **跑任何写命令前先 `schema` 一眼**，比撞一次门便宜。

6. ⚠️ **（未验）文件路径只接受 cwd 下的相对路径。**
   `lark-shared` 说 `--file` / `--output` / `--output-dir` / `@file` 传绝对路径会报
   `unsafe file path`。**本次没实跑这条**，写规程时按官方原文记下，**待验**。
   数据输入（`@file`、大 JSON）优先用 **stdin**，避免路径与转义问题。

7. ⚠️ **（未验）升级会连技能一起换。**
   `doctor` 报 `1.0.95 → 1.0.96 available`。`lark-cli update` 会**同时更新 CLI 和 AI Skills**。
   本次**没跑 update**（改版本是主人的决定），所以**升级后的行为差异本文件不负责**。

8. ⚠️ **（未验）`config init` 是首次配置的唯一入口。**
   `lark-cli config init --new` 会**阻塞**到主人打开链接完成或过期。本机 `config_file: pass`
   ⇒ **本机不需要 init**，本次没跑。

9. 🔴 **`lark-cli skills list` 与 `state/skill_atlas.json` 都是现读，两边都报 28 条 —— 名字逐条对得上。**
   但**技能落点是 3 处**（`.agents` / `.claude` / `.openclaw`），
   **managed 目录 `~/.openclaw-autoclaw/skills` 下没有 `lark-*`** ——
   ⇒ **别去 managed 目录找 lark 技能，也别往 `~/.agents/skills` 写**（那是别家工具的共享目录）。

---

## 7. 固化位置（**重启后要在**）

| 什么 | 在哪 |
|---|---|
| 本规程（源 · 真身） | `<仓>/skills/gbt-lark/SKILL.md` |
| 本规程（装机） | `~/.openclaw-autoclaw/skills/gbt-lark/SKILL.md`（**与源稿逐字节相同**，由 `verify-distill.py --cluster lark` 机检） |
| 被规程管的 28 条能力 | `~/.agents/skills/lark-*` · `~/.claude/skills/lark-*` · `~/.openclaw/skills/lark-*`（**不由本件代管，别改**） |
| 能力名册（现读） | `lark-cli skills list` · `<仓>/state/skill_atlas.json`（`name` 以 `lark-` 开头） |
| 人话入口 | `python tools/codex-scripts/omni.py ask "帮我在飞书发个消息"` → 落到 `lark-im`（`agent-skill` 通道） |
| 验收 | `py -3.14 tools/codex-scripts/verify-distill.py --cluster lark` |

**纪律**：本规程**不代替 lark-cli**。工具不在 PATH / 没配好，就**如实报"取不到"**，**不许编读数**。
`omni.py` 与 `security/policy.py` **不是本件该动的东西** —— 本件只加一份规程，**不动门**。

---

## 8. 诚实边界（这段不许删）

1. **本件是"用法规程"，不是"能力已具备"。** 它把 28 条技能**分簇、点名、定了纪律**；
   但**每条技能的深度用法以它自己的 `SKILL.md` 为准**，本件**不替代**。
2. **本次实跑的都是只读/帮助类命令**：`--version` · `auth status --json` · `whoami` · `--help` ·
   `skills list` · `doctor` · `schema`。**任何业务读写、`auth login`、`config init`、`update`、
   `event consume`、`exit 10` 的真实触发，本次都没跑** —— 涉及它们的地方已按上面 §5.4 标注。
3. **本机状态是 2026-09-22 的现读快照**（lark-cli 1.0.95 · 品牌 lark · 28 条技能）。
   **换机器、换版本、换应用后必须重新现读**，别把这份读数当永久事实。
4. **身份读数会漂**：`user` 身份当时是 `needs_refresh`（调用时自动刷新）。
   **读的是那一刻，不是永久结论。**
5. **凭据只报"已配/未配"**：本文件出现 `cli_a933****` 是**前 4 位掩码**，**不是**任何可用凭据。
