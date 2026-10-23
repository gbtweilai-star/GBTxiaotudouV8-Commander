# Skill 预算诊断报告

> 触发：系统警告 `Skill descriptions were shortened to fit the skills context budget`
> 口径：诊断到**根源**，不停在现象描述 · 出报告时间：2026-09-17 · 第二十八轮（R28）
> 数据：`.scratch/_r28_skill_audit.py` / `_r28_skill_dup.py` → `.scratch/_r28_skill_audit.json`
> 开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属

---

## 一、现象

系统在注入 skills 清单时，把每条 `description` **截断**（"shortened to fit the skills context budget"）。
可见证据：注入文本里 `cloudflare` 那条停在 `...feature flags (Flagship` 就断了，
而它在磁盘上的原始描述还有一大截。

---

## 二、实测数据（不是估计）

枚举六个 skill 根目录（`r0`~`r6` / 见 skills 目录表）下全部 `SKILL.md`：

| 指标 | 值 |
| --- | --- |
| `SKILL.md` 文件总数 | **91** |
| **唯一 skill 名** | **72** |
| **重复挂载** | **19 组** |
| 描述字符总量 | **31,104** |
| 重复白吃的字符 | **6,945**（**占总量的 22.3%**） |

**按根目录分布**

| 根 | 个数 | desc 字符 | 均长 |
| --- | --- | --- | --- |
| `r1`（`.agents/skills`） | 50 | 17,419 | 348 |
| `r0`（`.codex/skills`） | 26 | 9,092 | 350 |
| `r2`（`.codex/skills/.system`） | 6 | 2,064 | 344 |
| `r4`（`openai-primary-runtime`） | 6 | 1,697 | 283 |
| `r3`（`openai-bundled`） | 2 | 344 | 172 |
| `r6`（工作区 `.agents/skills`） | 1 | 488 | 488 |

**描述最长的 10 条**

| 字符 | skill |
| --- | --- |
| 1,467 | `ef-communication` |
| 1,068 | `ef-broadcast` |
| 734 | `alchemy-cli` |
| 722 | `opensea` |
| 647 | `alchemy-api` |
| 637 | `ef-profile` |
| 635 | `alchemy-mcp` |
| 582 | `lark-apps` |
| 572 | `imagegen`（×2 份） |
| 566 | `agentic-gateway` |

**按领域分布（与当前任务的相关性）**

| 领域 | 个数 | desc 字符 |
| --- | --- | --- |
| 飞书 `lark-*` | 28 | 5,547 |
| Cloudflare 系（Workers/Pages/D1/R2/Sandbox/Turnstile…） | 24 | 8,856 |
| Web3 系（Alchemy/OpenSea/Allium/agentic-gateway/EigenFlux） | 9 | 6,991 |
| 文档/设计系（docx/pptx/xlsx/pdf/imagegen/hatch-pet…） | 9 | 3,390 |
| 其他（工程、元技能、系统） | 21 | 6,320 |

---

## 三、根源（为什么总量必然超预算）

### 根源 1 · 同一 skill 被挂了两份（22.3% 是纯浪费）

19 组重复，全部是「`r0` 一份 + `r1`/`r2` 一份」这种同源并存：

`cloudflare` · `cloudflare-one` · `cloudflare-email-service` · `workers-best-practices` ·
`agents-sdk` · `durable-objects` · `sandbox-stable` · `sandbox-next` · `sandbox-migrate-to-next` ·
`wrangler` · `turnstile-spin` · `web-perf` · `imagegen` · `plugin-creator` · `openai-docs` ·
`skill-creator` · `skill-installer` · `review-agent` · `cloudflare-one-migrations`

**性质**：这不是「skill 太多」，而是**挂载点没有去重**。1/5 以上的预算在重复描述同一件事。
去重是**零信息损失**的收益——比精简描述安全得多。

### 根源 2 · 单条描述过长，必然触发截断

> 500 字符的描述有 **18** 条，最长 **1,467** 字符。
预算按「条数 × 每条上限」分配，单条越长，能保住语义的比例越低。
`ef-communication`（1,467）被截到约 120 字符 = **保留 8%**。

### 根源 3 · 领域与当前任务严重不匹配，但没有「按需加载」机制

飞书 28 + Cloudflare 24 + Web3 9 = **61 个（67%）**，与本项目当前主线（`holo_pet` / 镜像维度 / 宪章维护）
**无关**。而注入是**一次性全量**的：不用也得占预算。

### 根源 4 · 压缩是「截断」而不是「分层」

系统做的是**逐条截断**（保头丢尾）。截断**不区分重要性**：
`lark-im` 的「不负责：查询过去的视频会议记录」这类**边界说明**恰好长在尾部，最先被切掉。

---

## 四、回答四个追问

**Q1 当前挂了哪些 skill、各多长？** → 91 条 / 31,104 字符，明细见 `.scratch/_r28_skill_audit.json`（含每条的 `desc_len` 与路径）。

**Q2 为什么总描述超预算？是太多还是太长？** → **两者都有，但主因是重复挂载**：
去重可立即回收 **22.3%**；再压 18 条超长描述可再回收一大块。真实「skill 数量」是 **72 个**，不是 91 个。

**Q3 哪些当前任务用不上？** → 见下节建议清单。

**Q4 压缩后会不会「名字可见但功能不明」？** → **会，而且已经发生**。
`cloudflare` 命中的注入文本停在 `feature flags (Flagship`；`ef-communication` 只保住了开头一句。
后果：模型**知道有这个技能**，但**不知道它的边界**（能做什么、不做什么、什么时候该用），
于是要么不敢用、要么误用——**这正是「截断」比「不注入」更坏的地方**。

---

## 五、建议清单（按当前任务 · 需风哥拍 · 本报告不动任何配置）

> 一句话：**下面这张表只是建议，改配置是 Owner 权限，我不自行动手。**

| 级别 | 动作 | 对象 | 依据 |
| --- | --- | --- | --- |
| **A · 立即回收（零损失）** | **去重**：每个重复 skill 只保留一份 | 19 组（见根源 1） | 同源同版本，去重不丢任何信息 |
| **B · 按当前任务停用** | 飞书 28 个 | `lark-*` | 本项目当前主线不碰飞书 |
| **B · 按当前任务停用** | Web3 9 个 | `alchemy-*` / `opensea` / `allium` / `agentic-gateway` / `ef-*` | 当前无链上工作 |
| **B · 按当前任务停用** | Cloudflare 24 个 | （含重复） | 云电脑走 Cloudflare Tunnel，但那是 **`cloudflared` 二进制 + DPAPI 凭据**，与 Workers/Pages 技能无关 |
| **B · 按当前任务停用** | 文档/设计 9 个 | `documents` / `presentations` / `spreadsheets` / `pdf` / `imagegen` / `hatch-pet` / `visualize` / `excel-live-control` / `template-creator` | 当前无出稿任务 |
| **C · 建议保留** | 工程/元技能 | `playwright` · `screenshot` · `openai-docs` · `security-best-practices` · `plugin-creator` · `skill-creator` · `skill-installer` · `cli-creator` · `define-goal` · `gh-address-comments` · `web-perf`(去重后) | 与本项目日常贴合；`openai-docs` 是自查入口 |
| **D · 待定** | Cloudflare 系在**做 W4 云电脑面板**时可能用到 Tunnel API | 需用时临时开 | 与「按需加载」配套 |

**保守估计收益**：A（去重）回收 22.3%；B 项停用再回收约 **55%–60%**。
两者叠加后，实际注入量可降到当前的 **1/4 左右**——那时描述**不再需要截断**，Q4 的问题自动消失。

---

## 六、长期优化方案（根治，不靠每次手动关）

1. **挂载点去重（治本第一刀）**
   同一 skill 只允许挂在一个根下；`r0` 与 `r1`/`r2` 的同名项合并，保留官方/系统那份。
   **验收判据**：`唯一名数 == 文件数`。

2. **描述上限 + 首句承载语义（治本第二刀）**
   每条描述 **≤ 120 字符**，且**第一句必须写全「什么时候用它」**；
   边界说明（"不负责…"）下沉到 `SKILL.md` 正文，不占注入预算。
   **验收判据**：`max(desc_len) ≤ 120`，且全部条目在注入里**无截断**。

3. **分层加载（治本第三刀）**
   - **L0 常驻**：元技能 + 当前项目的工程技能（约 15 条）
   - **L1 按域**：一个域一个包（飞书包 / Cloudflare 包 / Web3 包 / 出稿包），**用到才挂**
   - **L2 目录索引**：只注入"包名 + 一句用途 + 怎么开"，需要时再展开
   **验收判据**：默认注入 ≤ 30 条。

4. **自检钩子（防复发）**
   把「skill 预算体检」做成可复跑脚本（`_r28_skill_audit.py` 已具备雏形），
   常态化输出：文件数 / 唯一名数 / 重复列表 / `max(desc_len)` / 估算 tokens。
   **触发**：每次新增 skill 后跑一次；或每周一次。

5. **不许用「压缩描述」当常规手段**
   截断会制造 Q4 那类**假可用**（名字在、边界没了）。
   如果确实超预算，正确做法是**停用无关域**或**分层**，不是把描述剪短后假装它还在。

---

## 七、一句话结论

**这不是「skill 太多」的问题，是「挂载不去重 + 全量注入 + 截断代替分层」三个机制缺陷叠加。**
去重是零损耗的即时收益（22.3%）；分层是根治；截断应当只作为最后兜底，不该成为常态。

---

> 开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属
