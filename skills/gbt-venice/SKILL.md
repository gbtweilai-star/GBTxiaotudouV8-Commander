---
name: gbt-venice
displayName: GBT · Venice.ai 技能簇用法规程（venice-* · 5 条）
version: 1.0.0
description: GBT小土豆V8 使用 Venice.ai 技能簇的用法规程。把 5 条 venice-* 技能（出图端点与风格 · 改图/超分/去背景 · 视频生成与转写 · 文本转语音 · 音乐生成）逐条点名并按意图分簇，规定两道闸（闸一凭据闸 VENICE_API_KEY 只报已配/未配或前 4 位掩码；闸二计费确认闸，凡出网、花钱、产交付物、把本地素材传出去的调用一律先问主人，视频与音乐类要先把秒数或时长摊开）、以及本机现状（这 5 条是 design-asset 通道的「目录桩」，每条目录只有 SKILL.md，上游包未装、VENICE_API_KEY 未配、无 venice CLI 与 python 包、omni.py ask 不路由到它们，所以现在跑不起来）。当用户要用 Venice.ai 生图、改图、超分、去背景、生视频、做转写、配音、生成音乐，或问 venice-* 技能怎么用、为什么调用不起来、凭据在哪、这次花了多少钱时使用。
triggers:
  - "venice"
  - "Venice.ai"
  - "venice-*"
  - "venice image"
  - "venice generate"
  - "venice image edit"
  - "venice upscale"
  - "venice background removal"
  - "venice video"
  - "venice transcribe"
  - "tts"
  - "text to speech"
  - "voiceover"
  - "narration"
  - "music gen"
  - "jingle"
  - "background loop"
  - "VENICE_API_KEY"
---

# GBT · Venice.ai 技能簇用法规程

> 开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属
>
> 这是**我们自己的用法规程**（不是 Venice.ai 官方文档的复述，也不是那 5 条技能原文的复述）。
> 那 5 条 `venice-*` 讲的是"这一条技能宣称呼哪一类端点"，本文件讲
> "**在我们这儿，它现在到底能不能跑、凭据从哪来、谁在什么条件下按什么顺序去用它，
> 以及什么东西绝对不许自动发出去**"。
> 冲突时的裁决顺序：**本文件管我们的纪律** → 各 `venice-*` 技能原文管它自己宣称的能力边界。两层都守。
> 同型件参考：`gbt-fal`（同样是"目录桩簇"的规程，写法与本件一致）。

---

## 0. 它是什么 / 在哪 / 🔴 最关键的一个事实

**这 5 条是「目录桩（catalogue stub）」，不是「已具备的能力」。**

这是本件最重要的一句，先记住。5 条里的**每一条**正文都写着同样一段话（原文大意）：

> This catalogue entry advertises the skill in Open Design so the agent
> discovers it during planning. To run the full upstream workflow with
> its original assets, scripts, and references, **install the upstream
> bundle** into your active agent's skills directory.

翻译成人话：**它们只是"广告位"**——作用是让 agent 在做方案时**知道有 Venice.ai 这个选项**，
从而把它列进计划。**真正的脚本、资产、参考资料都不在本机**，要去上游仓库装。

| 项 | 值（2026-09-22 现读） |
|---|---|
| 条数 | **5 条** |
| 通道 | **`design-asset`**（审美素材），**不是 `agent-skill`** |
| 上游 | `https://github.com/veniceai/skills`（**5 条原文各自都写了这一行**，`od.upstream` 字段） |
| 每条目录里有什么 | **只有 `SKILL.md` 一个文件**（已递归清点，无 `scripts/`、无 `assets/`、无 `references/`） |
| 每条 `SKILL.md` 体积 | 1020 – 1186 字节 |
| frontmatter 里的 `od.mode` | `image`（2 条）· `video`（1 条）· `audio`（2 条） |
| frontmatter 里的 `od.category` | `image-generation`（2 条）· `video-generation`（1 条）· `audio-music`（2 条） |

**落点（现读，两处，5 条逐条哈希一致 ⇒ 内容对得上）**：

| 什么 | 在哪 |
|---|---|
| 工作区那份 | `C:\Users\ADMIN\Desktop\GBT小土豆V8\审美相关skill\skills\venice-*` |
| managed 镜像那份 | `C:\Users\ADMIN\.openclaw-autoclaw\skills\autoclaw-design-capability\审美相关skill\skills\venice-*` |
| 图鉴登记 | `state/skill_atlas.json` 里 `name` 以 `venice-` 开头的条目 = **5 条**，两边一致 |

验证哈希用的读法（本件已跑，5 条 `identical=True`）：

```powershell
# ✅ 已验：两处副本逐条 Get-FileHash，5 条全 identical=True
Get-FileHash '<工作区>\审美相关skill\skills\<name>\SKILL.md' -Algorithm SHA256
Get-FileHash '<managed>\autoclaw-design-capability\审美相关skill\skills\<name>\SKILL.md' -Algorithm SHA256
```

🔴 **两个"别去找"的地方（现读确认）**：

1. **`~/.agents/skills` 下没有 `venice-*`**。本件**绝不往** `~/.agents/skills` 写任何东西 ——
   那是别家工具的共享目录（`~/.agents/skills` 现读挂着 alchemy-*/ef-* 等，**那是别的簇**）。
2. **`~/.openclaw-autoclaw/skills` 顶层没有 `venice-*`**。它们埋在
   `autoclaw-design-capability\审美相关skill\skills\` 下面，**不是托管目录的直接子项**，
   **别在顶层找不到就判"没装"**。

---

## 1. 🔴 本机现状如实读数（2026-09-22 现读快照）

**结论先说：这 5 条现在在本机「跑不起来」。** 三件事同时缺：凭据、运行体、上游包。

| 检查项 | 现读结果 | 怎么读的 |
|---|---|---|
| `VENICE_API_KEY` 环境变量 | **未配** | `[Environment]::GetEnvironmentVariable('VENICE_API_KEY')` → 空 |
| 任何 `VENICE*` 环境变量 | **一个都没有** | 枚举 `env:` 后按名过滤 `VENICE*` → 空集 |
| `venice` 命令（CLI） | **未找到** | `Get-Command venice` → 无结果 |
| Python 包 `venice` | **未安装** | `importlib.util.find_spec('venice')` → `False` |
| 上游 bundle 是否已装 | **未装**（每条目录只有 `SKILL.md`） | 递归清点目录内容 → 各 1 个文件 |
| 每条目录里有无可跑脚本 | **没有** | 同上 ⇒ "直接跑技能里的脚本"这条路**在本机不存在** |
| `omni.py ask` 是否路由到它 | **不路由**（已验） | `omni.py ask "用 venice 生成一张图"` → **只落到万能插能力位，5 条 `venice-*` 一条都没出现** |

⚠️ **诚实边界（重要，别把上面读成"已配好只差一步"）**：
**这 5 条技能原文里，一条都没有写"凭据怎么配"。** 它们只写了上游仓库地址。
所以上表里 `VENICE_API_KEY` 这个名字是**按 Venice.ai 的通行约定**记下的（Venice.ai 的 API 走
`Authorization: Bearer <key>`，官方 SDK 惯用这个环境变量名），
**不是从这 5 条原文里读出来的**，本件也**没有装上游包去核实过**。
⇒ 真要落地时，**以装上的上游包自己的 README 为准**，别拿本表当配置手册。
（本件**没有出网**去访问 `github.com/veniceai/skills` —— 按本次纪律不做出网动作。）

**而且：凭据未配 ≠ 调用会失败得漂漂亮亮。** 现在这个状态下，
任何 `venice-*` 的"真调用"**都不会发生**（没有运行体可以发起它），
所以**不会**出现"偷偷跑了一次、悄悄花了钱"这种情况 —— 但也**别因此就说"venice 能力可用"**。
**"装了、查得到"与"能跑"是两件事**，本件管的是后者，而后者现在是**否**。

---

## 2. 两道闸（顺序不能颠倒）

### 闸一 · 凭据闸（`VENICE_API_KEY`）

**只报状态，绝不报值。** 这是硬纪律，无例外。

```powershell
# ✅ 唯一允许的读法（只出"已配/未配"，不出值）
if ([Environment]::GetEnvironmentVariable('VENICE_API_KEY')) {'已配'} else {'未配'}

# ✅ 要看个影子就只出前 4 位掩码（例：v1a2****）
#    前提是真的到了必须给人看的地步；本机现在是「未配」，没有掩码可给
```

🔴 **绝对不许**：把值 echo 出来 · 把值写进任何 `.md` / 日报 / `MEMORY.md` / 聊天 ·
把值贴进本规程 · 把值当参数明文传给命令行（会进 shell 历史与进程列表）·
直接把值写进任何配置文件（本机没有 Venice 的配置目录，**别去造**）。

**本机闸一现状（2026-09-22 现读）**：`VENICE_API_KEY` **未配** ⇒ **闸一是关着的**。
在主人配置凭据之前，任何 `venice-*` 真调用都**不该被尝试**。
需要凭据时：**告诉主人"闸一未过，需要配 `VENICE_API_KEY`"，然后停**，不要自己去要、去猜、去旁路。

**闸一与闸二的先后**：闸一未过 ⇒ **连闸二都不必谈**（没有可执行的调用）。
这跟 `gbt-lark` 的"身份闸在前"、`gbt-fal` 的"凭据闸在前"是同一个道理：
**先搞清"我凭什么是它"，再谈"我要做什么"。**

---

### 闸二 · 计费确认闸（**凡出网 / 花钱 / 产交付物 / 送素材出去，一律先问主人**）

**本条高于技能原文，也高于任何上游包的默认行为。**

**为什么必须由我们拦**：Venice.ai 是**外部算力服务**，调用即出网。这 5 条覆盖的动作里，
**视频类与音乐类是"按时长"计的**（`venice-video` / `venice-audio-music`），
**语音类是"按字符数或时长"计的**（`venice-audio-speech`），**出图类是"按张/按步"计的**
（`venice-image-generate` / `venice-image-edit`）。
一次"手滑多跑一遍"就是**真金白银**，而**上游包不会替你心疼**。

**算"必须先进闸二"的动作**（本簇 5 条全部命中，无一例外）：

- **一次真实生成 / 编辑 / 转写 / 合成调用**（任何会打到 Venice.ai 端点的请求）—— 出网 + 计费；
- **批量跑**（N 张图 / N 秒视频 / N 秒音频 / N 个变体）—— 计费是乘法，**先报总数**；
- **把产物落盘成"交付物"**（出图 / 出片 / 出音频 / 出转写稿）—— 产出交付物；
- **上传素材到外部**（参考图 / 待编辑图 / 待转写的音视频）—— **这是把本地数据送出去**，
  比花钱更值得先问一次；
- **任何会写进主人项目/发布出去的动作**（把图直接发到某个渠道、覆盖既有素材）—— 改远端。

**顺序（先看什么 → 拿什么回执）：**

1. **先过闸一**：报 `VENICE_API_KEY` **已配 / 未配**。未配 ⇒ **到此为止**，只把"缺凭据"报给主人。
   （本机当前就是这一步。）
2. **先摊开代价，再谈执行**。动手前必须把下面**五件事**摆给主人看：
   - **模型/端点**：走哪一类端点（出图 / 改图 / 视频 / TTS / 音乐）—— **指名道姓**；
   - **输入**：本地哪个文件（绝对路径）会被**上传出去**，多大、多少个；
   - **规模**：**几张图 / 几秒视频 / 几秒音频 / 多少字符**。视频与音乐类
     **必须把秒数单独拎出来写清**（按时长计的东西，不说秒数 = 没说代价）；
   - **档位/分辨率/音色**：会不会因为档位不同而单价不同；
   - **预期花费**：能查到单价就**报算法**（`单价 × 数量`），**查不到就说"查不到估价"**，
     **不许编一个数**（见 §4：本簇**没有任何一条技能管定价**）。
3. **等一次明确同意**。**只覆盖这一批**，不是"以后这类都同意"。
   主人没回话 = **没同意**，停。主人说"先来一张试试" = **授权 1 张**，不是"授权这个模型"。
4. **同意后才执行**，并且**只执行被授权的那一批**：授权 4 秒就别跑 8 秒，授权 1 张就别跑 4 张。
5. **拿回执（缺一不可）**：
   - **请求/任务 id**（`request_id` / `task_id` / `queue_id` 之类）—— 事后对账的唯一凭据；
   - **状态**：`queued` / `processing` / `completed` / 失败，**原样报**；
   - **产物的绝对落盘路径 + 字节数**（产交付物就得说清东西在哪、多大、真的存在）；
   - **实际计费口径**（上游回了就原样转述，没回就写"上游未回传计费"）。
6. **长任务不盲重试**：提交后拿到 `task_id` 就**记下来再轮询**。
   **重试 = 可能重复计费**。要重试前**先确认第一次到底成了没有**。
7. **失败就照原样记**：HTTP 状态码 + 原始错误体（`status` / `detail` / `error`）**一字不改**，
   **绝对不许把失败写成成功**（见 §5）。

🔴 **绝对不允许**：凭据没配就"先试一下" · 主人没明确同意就跑生成 ·
拿"反正是草稿/反正很小"当理由跳过确认 · 视频/音乐类不报秒数就开跑 ·
把一次授权当长期授权 · 看到超时就重发一遍 · 把失败包装成"已完成"。

**预判与降险（合法且鼓励）**：
优先挑**最省的验证路径**——先 1 张 / 先 1 秒 / 先最低档位确认线路通不通，
再按确认过的档位放大。**"先花小钱验线路"也要先问主人**，只是**问的时候代价更小、更容易被同意**。

---

## 3. 按意图分簇（5 条，一条不漏）

**选路总则**：先看**交付物是什么**（图 / 视频 / 声音 / 文字），
再看**输入是什么**（文 / 图 / 视频 / 音频），最后才落到具体技能。
**拿不准就先说"拿不准"，别硬凑一条。**

### 3.1 图像生成（文生图 / 挑风格）—— 1 条

| 技能 | 什么时候用它 |
|---|---|
| **`venice-image-generate`** | **主力出图入口**。要用 Venice.ai 的**出图端点**从文字生成图片、并在**可选风格**里挑一种时用它。触发词原文给了 `venice image` / `venice generate` / `venice ai image`。**诉求是"造出一张新图"** 就走它。 |

### 3.2 图像编辑与画质处理（改图）—— 1 条

| 技能 | 什么时候用它 |
|---|---|
| **`venice-image-edit`** | **改已有的图**：图像编辑（edits）、**超分放大**（upscaling）、**去背景**（background removal）。触发词原文给了 `venice image edit` / `venice upscale` / `venice background removal`。注意它原文把**三件事写进同一条**（改内容 / 抬尺寸 / 去背景）⇒ **同一条技能里选哪个动作要说清**，别一句"处理一下"就开跑。 |

**这两条的分界（别选错）**：**从无到有造一张** → `venice-image-generate`；
**拿一张现成的图去改 / 放大 / 抠背景** → `venice-image-edit`。

### 3.3 视频生成与转写 —— 1 条

| 技能 | 什么时候用它 |
|---|---|
| **`venice-video`** | **要视频或要转写**时用它：原文写的是 **video generation 与 transcription workflows**。触发词给了 `venice video` / `venice video gen` / `venice transcribe`。⚠️ **同一条里混了"生成"与"转写"两种活**（一个出视频、一个出文字），**进去前先定死是哪一种**。 |

🔴 **本条是"按时长计费"的重灾区**：进闸二时**必须把秒数写出来**（见 §2 第 2 步）。

### 3.4 语音合成（文本转语音）—— 1 条

| 技能 | 什么时候用它 |
|---|---|
| **`venice-audio-speech`** | **要人声**时用它：**TTS 模型 / 音色（voices）/ 输出格式 / 流式**四件事；原文点名的用途是 **narration（旁白）、voiceover（配音）、对话型 agent 的声音**。触发词给了 `tts` / `venice speech` / `text to speech` / `voiceover` / `narration`。 |

### 3.5 音乐生成 —— 1 条

| 技能 | 什么时候用它 |
|---|---|
| **`venice-audio-music`** | **要一段音乐**时用它：**音乐生成的任务排队（queueing）、取回（retrieval）、完成态（completion）端点**；原文点名的用途是 **jingle（短广告曲）、background loop（循环背景乐）、prototype scoring（原型配乐）**。触发词给了 `venice music` / `music gen` / `jingle` / `background loop` / `score`。 |

**注意这条原文写了"排队 / 取回"** ⇒ 它是**异步任务模型**（提交后要取回），
所以 §2 第 6 步"拿到 id 再轮询、不许盲重试"对本条是**硬要求**。

**分簇小结（5 簇 / 5 条，逐条已点名）**：
图像生成 1 · 图像编辑与画质 1 · 视频生成与转写 1 · 语音合成 1 · 音乐生成 1 = **5**。

**选路示例**：
"用 venice 出几张概念图" → `venice-image-generate`（**先过两道闸**）；
"这张图背景太乱，去掉 / 这张太小，放大" → `venice-image-edit`；
"用 venice 出一段视频" / "把这段录音转成文字" → `venice-video`（**先报秒数，并说清是哪种活**）；
"把这段稿子念成旁白" → `venice-audio-speech`；
"给这个原型配一段背景乐" → `venice-audio-music`（**先报时长**）。

---

## 4. 🔴 本簇**没有**覆盖的几件事（诚实边界，别硬凑）

本簇 5 条原文（每条约 1 KB 的桩）里，**没有一条**管下面这些事。
**主人问到这些时，不要拿 `venice-*` 里的哪一条去硬凑答案** —— 如实说"本簇不管"。

| 主人可能会问 | 本簇管不管 | 该怎么说 / 该去哪 |
|---|---|---|
| **"Venice.ai 上有哪些模型？哪个好？"** | ❌ **不管**。5 条里**没有**模型目录类技能。 | 如实说"本簇没有可查的模型目录"。真要目录得看上游包/上游站点（**本机未装、未验**）。 |
| **"这一下要花多少钱？"** | ❌ **不管**。5 条里**没有**定价类技能。 | **只许报算法（单价 × 数量），不许编单价。** 本机已有的"查模型 / 查定价"能力是 **Ark 那条路**（`gbt-arkcli` 管着的 `arkcli-models` / `arkcli-pricing`）—— 但那是 **BytePlus ModelArk**，**跟 Venice.ai 是两个产品**，**定价与目录都不通用，别互相顶替**。 |
| **"这个任务排队到哪了？"** | ❌ **不管**。5 条里**没有**队列查询类技能。 | 只能靠**你自己提交时记下的 id/queue id** 去上游查（见 §2 第 6 步）。**别编一个"查队列"的命令。** |
| **"还剩多少额度 / 配额？"** | ❌ **不管**。5 条里**没有**配额类技能。 | 如实说"本簇没有查配额的能力"，让主人去 Venice.ai 控制台看。 |
| **"怎么配凭据？"** | ❌ **不管**。**5 条原文一个字都没提凭据。** | 见 §1 诚实边界：`VENICE_API_KEY` 是按通行约定记的名字，**以装上的上游包 README 为准**。 |

**这几格是本件的"防编造"锚点**：本簇的边界就到这里，**越界就是猜**。

---

## 5. 🔴 报告层红线（读数纪律）

1. **读数先问一句：这是事实，还是我读错了地方？**
   本簇最典型的"读错地方"有三种，**报数前先排除**：
   - **`~/.openclaw-autoclaw/skills` 顶层找不到 `venice-*`** ⇒ 不等于没装，它们埋在
     `autoclaw-design-capability\审美相关skill\skills\` **下面**（§0 已验）；
   - **`state/skill_atlas.json` 里条目的 `desc` 字段可能被 YAML 块标量解析坏**
     （同型件 `fal-*` 当时读出的是 `"|"`）。本簇现读 `desc` 是**正常句子**
     （例 `Image generation endpoints and available styles via the Venice.ai API.`），
     **但描述一律以各技能 `SKILL.md` 原文为准**，不拿图鉴 `desc` 当判决；
   - **`omni.py ask` 完全不路由到 `venice-*`** —— 现读跑了
     `omni.py ask "用 venice 生成一张图"`，**只落到万能插的能力位，一条 `venice-*` 都没出现**。
     原因是它们是 **`design-asset` 通道**，不是 `agent-skill`。
     ⇒ **别拿"omni 没推它"当"它不存在"**，也**别拿"图鉴里有它"当"人类一句话就能调到它"**。
2. **有错也照原样记，不许把失败写成成功。** HTTP 状态码、`status`、`detail`、`error` 原文保留。
3. **不许把"装了/查得到"当"能跑"。** 本簇现在**装了、查得到、但跑不起来**（§1）。
   这三个状态**不许混着报**。
4. **不许编命令、编路径、编技能名、编单价、编模型名。**
   本件出现的每一条命令要么**本机真跑过**（标 ✅），要么明确标 **（未验）**。
   **没跑过的不许说成跑过。**
5. **不许报"已配/未配"之外的凭据细节**：只许**已配 / 未配**或**前 4 位掩码**。
6. **凭据未配 / 上游未装 ≠ 权限被挡。** 那是"东西不在"，不是"门不让你过"。
   **别对着不存在的运行体反复撞，然后报成"被权限拦了"。**
7. 🔴 **「零作用域 ≠ 只读」**：本簇虽然现在是"根本跑不起来"，但**别把这个经验推成**
   "凡是没有作用域的调用都安全"。**没有任何作用域声明 ≠ 只读** ——
   Venice.ai 的调用会出网、会计费、会把本地素材送出去，**它只是没有"作用域"这个说法而已**。
8. **`verify-distill.py --cluster venice` 的 FAIL 要读对意思**（见 §6 坑 1）：
   它现在报 FAIL **只是因为登记还没做**，**不是因为规程写坏了**。

---

## 6. 本机踩过的坑 / 已验事实（照做，别自己解读）

1. ✅ **`--cluster venice` 曾必然报 FAIL，原因是"没登记"，不是"写错了"。**
   ✅ **2026-09-22 已修：登记已完成** —— 现读 `DISTILLED_CLUSTERS` 共 **22** 项且含
   `"venice": "gbt-venice"`，`py -3.14 tools/codex-scripts/verify-distill.py --cluster venice`
   现读 **`fail: []` / `hard_failures: 0` / `verdict: PASS`**（5/5 覆盖）。
   下面是**当时的原始读数**，留作"没登记时长什么样"的样本（**别再当成现状引用**）：

   ```json
   {"clusters": [{"cluster": "venice", "skill": null,
     "fail": ["omni.py 的 DISTILLED_CLUSTERS 里没登记这个簇"],
     "facts": {"skills_in_atlas": 5}}],
    "hard_failures": 1, "verdict": "FAIL"}
   ```

   （退出码 **1**。）
   **注意 `facts.skills_in_atlas` 已经是 5** —— 说明验收器**已经能看到这 5 条**，
   缺的只是 `omni.py` 的 `DISTILLED_CLUSTERS` 里那一行登记。
   🔴 **（历史读数，已被推翻）当时 `DISTILLED_CLUSTERS` 只有 `arkcli` / `lark` / `fal` / `autoglm` /
   `figma` / `design` / `autoclaw` / `sandbox` / `pptx` / `youtube` / `video` 这些项，没有 venice。**
   ✅ **2026-09-22 现读：那张表已有 22 项、`venice` 在册** ⇒ 这一条**只作历史样本**。
   **本件不改 `omni.py`、不改 `policy.py`、不动别的域或别的簇。**
2. ✅ **`venice-*` 是 `design-asset`，不是 `agent-skill`。**
   `py -3.14 tools/codex-scripts/omni.py list --domain venice` 现读：
   万能插能力位 **0 条**；agent 技能 **5 条，全部是 `venice-*` 且通道标 `design-asset`**
   （**这个 `--domain` 这次没有带出无关条目**）。
   ⇒ **别去 `five-dim.py cap` 里找 `venice` 域的能力位 —— 那里是 0。**
3. ✅ **每条技能目录里只有 `SKILL.md` 一个文件。**
   递归清点 5 个目录：只有 `SKILL.md`，**1050 / 1050 / 1020 / 1186 / 1182 字节**
   （`venice-image-edit` / `venice-image-generate` 各 1050 · `venice-video` 1020 ·
   `venice-audio-music` 1186 · `venice-audio-speech` 1182）。
   ⇒ **没有可跑的脚本**。
4. ✅ **两处副本逐条哈希一致**（工作区 ↔ managed），5 条全 `identical=True`。
   读法见 §0。⇒ **本簇不存在"两份不一样"的问题**。
5. ✅ **本件本次全程零真调用。** 跑过的**只有只读/结构类命令**：
   `omni.py list --domain venice` · `omni.py ask`（一次）· `verify-distill.py --cluster venice` ·
   图鉴与技能原文阅读 · 目录清点 · `Get-FileHash` · 环境变量存在性检查 · `Get-Command` · `find_spec`。
   **没有发出任何一个 Venice.ai 请求，没有花一分钱，没有上传任何素材。**
6. ⚠️ **（未验）上游仓库 `https://github.com/veniceai/skills` 的实际内容。**
   这 5 条原文各自都写了这个地址，但**本机没有把它拉下来**，
   本次**也没有出网去访问它**（按本次纪律：不做出网动作，出网要先问主人）。
   ⇒ **上游到底提供什么脚本、什么凭据约定、什么定价，本件一概不负责** —— **待验**。
7. ⚠️ **（未验）`VENICE_API_KEY` 就是本簇唯一凭据、以及它的鉴权头形状。**
   这是按 **Venice.ai 的通行约定**记的（§1 已说明），
   **不是**从这 5 条原文读出来的（它们**没提任何凭据**）。
   ⇒ 装上游包后**以它的 README 为准**。
8. ⚠️ **（未验）这 5 条之间的产物能否互转。**
   例：`venice-image-generate` 出来的图能否直接喂给 `venice-image-edit`、
   `venice-audio-speech` 出来的音频能否当 `venice-video` 的音轨、
   `venice-video` 的转写输出是什么格式。
   ⇒ 原文只各说各的，**没写互通**。**没有实测过，不许宣称能串。**
9. ⚠️ **（未验）`venice-video` 里"生成"与"转写"到底是不是同一套端点。**
   原文把两件事写在一句里（`Video generation and transcription workflows`），
   桩里没给端点清单。⇒ **别假设它们是同一条链路**，落地时以装上的上游包为准。

---

## 7. 固化位置（**重启后要在**）

| 什么 | 在哪 |
|---|---|
| 本规程（源 · 真身） | `<仓>/skills/gbt-venice/SKILL.md` |
| 本规程（装机） | `C:\Users\ADMIN\.openclaw-autoclaw\skills\gbt-venice\SKILL.md`（**与源稿逐字节相同**，用哈希证明） |
| 被规程管的 5 条能力 | `<仓>/审美相关skill/skills/venice-*` 与 `~/.openclaw-autoclaw/skills/autoclaw-design-capability/审美相关skill/skills/venice-*`（**不由本件代管，别改**） |
| 能力名册（现读） | `py -3.14 tools/codex-scripts/omni.py list --domain venice` · `<仓>/state/skill_atlas.json`（`name` 以 `venice-` 开头） |
| 验收 | `py -3.14 tools/codex-scripts/verify-distill.py --cluster venice` |

🔴 **本件只加一份规程，不动门。**
`omni.py`（含 `DISTILLED_CLUSTERS` 登记）与 `security/policy.py` **不是本件该动的东西** ——
**登记由主人做**；本件**不给自己发授权、不调 `tentacle` 任何方法、不碰别的域/别的簇**。

**纪律**：本规程**不代替上游包**。凭据没配 / 上游没装，就**如实报"跑不起来"**，**不许编读数**。

---

## 8. 诚实边界（这段不许删）

1. **本件是"用法规程"，不是"能力已具备"。**
   它把 5 条技能**分簇、点名、定了两道闸与纪律**；
   但**每条技能的深度用法以它自己的 `SKILL.md`（装上游包后）为准**，本件**不替代**。
2. **本机这 5 条现在是「目录桩 + 未配凭据 + 未装上游」的"跑不起来"状态。**
   本件**没有**、也**没能**验证任何一个真实的 Venice.ai 调用 ——
   因为**凭据未配、运行体不存在、上游包未装**（§1 逐项现读）。
3. **本次实跑的都是只读/结构类命令**（清单见 §6 第 5 条）。
   **任何业务读写、任何出网请求、任何计费动作，本次都没跑。**
4. **本机状态是 2026-09-22 的现读快照。**
   **换机器、配了 `VENICE_API_KEY`、装了上游包之后必须重新现读** ——
   尤其 §1 那张表，**配了凭据就会变**，别把这份读数当永久事实。
5. **凭据只报"已配/未配"**：本件**通篇没有出现任何凭据值**，
   因为本机 `VENICE_API_KEY` **未配**，**没有值可给**，也**永远不该给**。
6. **本件的每一条技能描述都来自各技能 `SKILL.md` 原文**，不是来自图鉴的 `desc` 字段。
