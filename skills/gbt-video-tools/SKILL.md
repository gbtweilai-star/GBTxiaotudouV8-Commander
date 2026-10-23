---
name: gbt-video-tools
displayName: GBT · 视频技能簇用法规程（技能簇 video-*）
version: 1.0.0
description: GBT小土豆V8 使用 `video-*` 这一技能簇的用法规程。本簇按 `state/skill_atlas.json` 里 name 前缀核定共 4 条（`video-pipeline` · `video-transcript-downloader` · `video-downloader` · `video-use`；**第 4 条 `video-use` 是技能目录被外部更新后新长出来的，由验收器抓出漏覆盖**），其中 2 条是真业务件、1 条有真脚本但未装依赖、1 条是只指上游的目录桩。⚠️ 本件**不是** `gbt-video`（那份是**本机 video 职业域 4 个能力位**的能力域规程），也**不是** `gbt-arkcli`（Ark 云端那条）—— 三处边界在 §0 写死。本规程把每条按意图分簇点名，钉死两道闸（① 凭据与依赖实测：密钥池 `keys_total:0`、`yt-dlp` 不在 PATH、`youtube-transcript-plus` 未装，而 `video-use` 的 ffmpeg/Pillow **在**；② **发布端一律不启用，出片/上传必须先问主人**），并记下真跑出来的读数与报告层红线。
triggers:
  - "视频技能"
  - "video-pipeline"
  - "分镜"
  - "storyboard"
  - "镜头契约"
  - "video-transcript-downloader"
  - "video-downloader"
  - "下载视频"
  - "rip audio"
  - "get subtitles"
  - "vtd.js"
  - "yt-dlp"
---

# GBT · 视频技能簇用法规程（技能簇 `video-*`）

> 开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属
>
> 这是**我们自己的用法规程**（不是那 3 条技能官方文档的复述）。技能自身讲"每条怎么用"，
> 本文件讲"**在我们这台机器上，谁在什么条件下、按什么顺序去用它，什么已经真能跑、
> 什么还没接线、什么东西绝对不许自动发出去**"。
> 冲突时的裁决顺序：**本文件管我们的纪律** → 各技能自己的 `SKILL.md` 管命令细节。

---

## 0. 🔴 三处边界（**开工第一段就读这段**）

这一节是硬要求。**三份规程各写一处，三处合起来才把"视频"这块地盘划清** ——
因为这三样东西**名字都带"video"**，谁读错谁就会拿错的读数说话。

| 是谁 | 管什么 | 判决口径 | 真身/入口 | 它**不**管什么 |
|---|---|---|---|---|
| **`gbt-video-tools`（本件）** | **`video-*` 这一技能簇"怎么用"** —— 3 条技能的选用、两道闸、真跑读数、坑 | 以本件为纲，命令细节以各技能 `SKILL.md` 为准 | `<仓>/skills/gbt-video-tools/SKILL.md` | **不是**本机能力位、**不是** Ark 云端那条、**不是** `youtube-*` 簇（那份是 `gbt-youtube`） |
| **`gbt-video`**（**已存在，别重名、别覆盖**） | **本机 `video` 职业域的 4 个能力位**（`media_pipeline` / `libtv_skill` / `libtv_workflow` / `h3_video_gen`）—— 图鉴里的**能力位**规程 | **图鉴口径**：`domain == "video"` 有且仅有 4 位；一律走 `py -3.14 tools/codex-scripts/five-dim.py cap <能力位>`（`run_task` 唯一门） | `<仓>/skills/gbt-video/SKILL.md` | 不管**技能簇**、不管 YouTube/抖音这类外部平台 |
| **`gbt-arkcli`**（已存在） | **Ark 云端那一条**（`arkcli +gen` / Seedream / Seedance） | 它自己的**调用前缀 + 登录闸 + 账号验证闸 + 计费报价确认**纪律 | `<仓>/skills/gbt-arkcli/SKILL.md` | **不代表**本机任何技能或能力位已接线 |

### 一句话记法

> **`gbt-video-tools` 管"视频技能怎么用"**（技能簇 · 按名字加载执行）；
> **`gbt-video` 管"本机视频能力位在哪、要不要授权"**（能力域 · 走 `five-dim.py cap`）；
> **`gbt-arkcli` 管"Ark 云端那条"**（外部 CLI · 两道闸 + 计费）。
> **三者谁都不许拿对方的读数替自己说话。**

### 三处最容易念反的地方（**逐条钉死**）

1. 🔴 **"技能簇里有 3 条" ≠ "本机有 3 个视频能力位"。**
   本簇实测 **`omni.py list --domain video` 报 `能力位 4 条`** —— 那 4 条是 **`gbt-video` 的**；
   本簇是 **技能**，走**按名字加载执行**的 `agent-skill` / `design-asset` 通道。
   **两套序号、两套清单，不许互相顶替。**
2. 🔴 **"某条技能名里有 `-downloader`" ≠ "本机能下载"。**
   本簇两条 `*download*` 技能**现在一条都跑不起来**（实测见 §3.3 / §4）。
   而**能力域**那 4 位也**全是只读骨架、生成端一条都没接**（`gbt-video` §0 原话）。
   ⇒ **本机现在"下载"和"出片"两边都不通**，只是**卡的原因不同**（这边卡依赖，那边卡未接线）。
3. 🔴 **"Ark 能生视频" ≠ "本机 `video` 域接线了" ≠ "本簇技能能出片"。**
   三件事。Ark 那条走 `gbt-arkcli` 并要过它自己的两道闸 + 报价确认；
   **本件不替 Ark 报价、不替 Ark 出片**，**Ark 也不能拿它的读数说本机已接线。**

---

## 1. 它是什么 / 名单怎么核（**以图鉴现读为准**）

**核定口径**：`state/skill_atlas.json` 里 `name` 以 **`video-`** 开头的条目（**带横杠**）。

```powershell
py -3.14 tools/codex-scripts/omni.py list --domain video     # ✅ 已验（宽松匹配，会带进非本簇的行）
```

**真返回（原文摘录）**：

```
── 能力位 4 条（万能插 · 走 run_task 唯一门）──
  【video】4 条  (视频 剪辑 短片 分镜 渲染 成片)
     ✅ media_pipeline             AI短视频/电影/音乐流水线：镜像房间编排、产物自审、…
     🔒 libtv_skill                LibTV 技能（只读骨架·门）：…
     ✅ libtv_workflow             LibTV 节点式工作流（只读骨架·门）：…
     ✅ h3_video_gen               H3mini 视频生成（只读骨架·门）：…

── agent 技能 18 条（按名字加载执行）──
     …（含 video-downloader / video-pipeline / video-transcript-downloader /
        youtube-factory / youtube-watcher / vidu-skills / arkcli-gen …）
```

🔴 **这一屏最容易读错**：**"能力位 4 条"是 `video` 域（`gbt-video` 的地盘），
"agent 技能 18 条"里以 `video-` 开头的才是本簇。** 两段**不是**同一份名单。

**按 `name` 前缀精确数（权威口径）** ⇒ **4 条**（2026-09-22 晚：技能目录被外部更新，`video-use` 是**新长出来的第 4 条**；
本规程同步补点 —— **验收器按"前缀-* 或裸名"判，漏一条就 FAIL，这条是它抓出来的**）：

| # | 技能 | 通道 | 落点 | 形态 |
|---|---|---|---|---|
| 1 | **`video-pipeline`** | `agent-skill` | `~/.openclaw-autoclaw/skills/video-pipeline`（**多根**：也命中 `<仓>/审美相关skill/skills`） | **真业务件**（92 行，中文；**纯方法论蒸馏**，自述"**不含可执行插件**"） |
| 2 | **`video-transcript-downloader`** | `agent-skill` | `~/.openclaw-autoclaw/skills/video-transcript-downloader` | **有真脚本**（`scripts/vtd.js` + `package.json`）**但依赖未装** |
| 3 | **`video-downloader`** | `design-asset` | `<仓>/审美相关skill/skills/video-downloader` | ⚠️ **目录桩**（42 行，只指上游 `ComposioHQ/awesome-claude-skills`，**无脚本**） |
| 4 | **`video-use`** | `agent-skill` | `~/.openclaw-autoclaw/skills/video-use` | ✅ **真工具链**（`SKILL.md` 23306 B + `helpers/` 6 个 Python 脚本 + `tests/` + `install.md` + 一个 `manim-video` 子技能；**是 git clone，带 `.git/`**） |

**真身/技能落盘（现读）**：

```powershell
# ✅ 已验
Get-ChildItem "C:\Users\ADMIN\.openclaw-autoclaw\skills" -Directory |
  Where-Object { $_.Name -match '^(video)' } | Select-Object -ExpandProperty Name
# → video-pipeline / video-transcript-downloader
```

⚠️ **`vidu-skills` / `arkcli-gen` / `youtube-*` 不属于本簇**：它们在 `--domain video` 的
**宽松匹配**里出现，但 `name` **不以 `video-` 开头**。
`vidu-skills`（Vidu API 生视频）与 `arkcli-gen`（Ark 云端）**各有各的规程/门**，
**本件不代管、不代跑**。

---

## 2. 按意图分簇（4 条逐个点名）

### 簇 D · 剪 → **对话式剪片**（`video-use`，本簇唯一"脚本齐全 + 依赖也在"的一条）

| 技能 | 什么时候用它 | 它给什么 |
|---|---|---|
| **`video-use`** | "把这条口播剪一下 / 剪掉废话和重复 / 配字幕 / 上色 / 加个浮层动画 / 按我说的剪"，**或**要一条从转录到成片的可复现流程 | 一套**真实现**：`helpers/transcribe.py`（转录）· `transcribe_batch.py` · `pack_transcripts.py`（打包成决策用的逐字稿）· `render.py`（28.9 KB，切片/浮层/字幕/合成）· `grade.py`（调色）· `timeline_view.py`（时间线可视化）；外加一个 `manim-video` 子技能（数学动画，走 Manim） |

**它的硬规矩（原文写死，照抄不美化）** —— 这些是**会静默出错**的正确性条款，不是口味：
① 字幕**最后**上（在任何浮层之后，否则浮层盖住字幕）；
② **逐段抽取 + `-c copy` 无损拼接**，不要一条 filtergraph 走完（否则加浮层时每段二次编码）；
③ 每段边界加 **30ms 音频淡入淡出**（否则每个剪切点都有爆音）；
④ 浮层用 `setpts=PTS-STARTPTS+T/TB` 对齐窗口起点（否则看到的是动画中段）；
⑤ 主字幕用**输出时间线**偏移（否则拼接后字幕错位）。

**依赖现读（本件实测）**：`ffmpeg 8.1.2-full_build` ✅ 在；`Pillow 12.3.0`（`py -3.14`）✅ 在；
**`manim` ❌ 未装**（`importlib.util.find_spec("manim")` → False）⇒ 那个 `manim-video` 子技能**现在跑不了**。
⇒ **本簇里只有它"看起来能跑"**（主体流程依赖在，Manim 那条不在）。

🔴 **仍然要过闸二**：它会**写出成片文件**（改盘、可能覆盖素材）⇒ **出片/覆盖/上传一律先问主人**；
本件**没有真跑过它**（没造过任何成片），凡"跑出来的效果"一律标**未验**。

### 簇 A · 规划 → 把片子"想清楚"（**本簇唯一内容完整的一条**）

| 技能 | 什么时候用它 | 怎么用 |
|---|---|---|
| **`video-pipeline`** | "这条片子怎么排 / 分镜怎么写 / 这镜头要有目的 / 预算怎么先拦 / 谁来审" —— **要判据与闸，不要成品** | 它给的是**生产契约**：分镜表四层结构、三条硬规则、预算闸、剪辑契约、内容与叙事闸、双人审闸 |

🔴 **它最重要的自述（原文）**：*「蒸馏自 `ttalkkaklab/social-flow`。**只搬判据与闸**：
生成端、发布端、增长循环一概不含」* + *「它是 Claude Code 插件形态；本工作区是 DSH
⇒ **本技能只蒸馏方法论，不含可执行插件**」*。
⇒ **它没有脚本、不能生成、不能发布。** 它的价值是**"开拍前的规矩"**。

**它的四条骨架（照原文，别自己改写）**：

- **铁律：分镜阶段只规划，不生成** —— `storyboard` 产出的是**计划**（提示词/引擎/价格），
  **一个像素都不生成**。意义：*「退回或废弃的分镜**成本为 0**」*。
- **三条硬规则**：① **不许在视频上画东西**（要箭头/原理 ⇒ 改做 HTML 动效页或真 3D 物件）
  ② **每一个镜头都要有目的**（读旁白 → 写 `shot.render` → 写理由；**复制别人的理由 = 失败**）
  ③ **开场不必是付费视频**（`hook_video` 默认**关**）。
- **预算闸**：`video_budget_usd` 默认 **$10/集** · `max_static_ground_seconds` 默认 **8 秒** ·
  `html_plate_max` 默认 **2** · **未知价格直接失败**（`cost-report.sh` 对未知价格 `exit 1`）。
- **双人审闸（HITL × 2）**：**分镜审批**（生产前）+ **发布审批**（公开前）。

### 簇 B · 取 → 下载/转写（**有真脚本，但依赖未装**）

| 技能 | 什么时候用它 | 怎么用 |
|---|---|---|
| **`video-transcript-downloader`** | "下载这条视频 / 存这个片段 / 抽音频 / 拿字幕 / 要干净的段落式逐字稿"，或 **yt-dlp/ffmpeg 的格式与播放列表排障** | 统一走它自己的 `scripts/vtd.js`：`transcript` / `download` / `audio` / `subs` / `formats` 五个子命令 |

**它的真命令（`SKILL.md` 原文摘录）**：

```bash
./scripts/vtd.js transcript --url 'https://…'            # 默认输出"干净段落"，时间戳可选
./scripts/vtd.js transcript --url 'https://…' --lang en
./scripts/vtd.js download  --url 'https://…' --output-dir ~/Downloads
./scripts/vtd.js audio     --url 'https://…' --output-dir ~/Downloads
./scripts/vtd.js subs      --url 'https://…' --output-dir ~/Downloads --lang en
./scripts/vtd.js formats   --url 'https://…'             # 列可选格式 id
```

**两条内部路径（`SKILL.md` 原文）**：
- **YouTube**：**尽量**走 `youtube-transcript-plus`；
- **其它情况**：先用 **`yt-dlp` 拉字幕**，再清洗成段落。
- 额外 `yt-dlp` 参数**放在 `--` 之后**（例：`-- --format 137+140`、`-- --remux-video mp4`）。
- `[Music]` 这类方括号提示**默认被剥掉**，要留加 `--keep-brackets`。

⚠️ **它自己给的"装"命令是 `brew install yt-dlp ffmpeg`**（**macOS 写法**）
+ 首次要 `cd … && npm ci`。**本机两条都没做过**（§3.2 / §4.2）。

### 簇 C · 下载（第二条路）：**目录桩**

| 技能 | 状态 | 怎么处置 |
|---|---|---|
| **`video-downloader`** | ⚠️ **目录桩**：42 行，`od.mode: video` / `od.category: video-generation`，上游 `https://github.com/ComposioHQ/awesome-claude-skills/tree/master/video-downloader`，**无脚本** | 只在规划期被"发现"。原文：*「To run the full upstream workflow with its original assets, scripts, and references, install the upstream bundle into your active agent's skills directory」* ⇒ **要用真流程，得先出网 + 主人点头装上游包。不许说"本机有下载能力"。** |

🔴 **簇 B 与簇 C 的重叠怎么选**：两条都叫"下载视频"。
**`video-transcript-downloader` 有真脚本（虽然依赖缺）**；
**`video-downloader` 是桩**。⇒ **要下载走簇 B，别走簇 C**（除非用户点名要装上游包）。

**选路示例**：用户说"这条片子的分镜该怎么排" → **`video-pipeline`**；
"把这条视频的字幕扒下来" → **`video-transcript-downloader`**；
"帮我下载视频" → **`video-transcript-downloader`**（**并说明 `video-downloader` 只是桩**）。

---

## 3. 闸一 · 凭据与依赖（**只报已配/未配，绝不贴值**）

### 3.1 凭据（实测：**本簇 3 条技能都不要求密钥；全机密钥池也是空的**）

| 名字 | 谁要它 | 实测 |
|---|---|---|
| **（无）** | **本簇 3 条技能一条都不要求 API key** | —— |
| `LIBTV_ACCESS_KEY` / `MINIMAX_API_KEY` | ⚠️ **不是本簇的** —— 它们属于**能力域** `libtv_skill` / `h3_video_gen`（见 `gbt-video`） | **UNSET（未配）** |
| 密钥池现状 | 本机全机 | **`keys_total: 0`** |

```powershell
# ✅ 已验：NAME ONLY，绝不打印值
foreach($n in @('LIBTV_ACCESS_KEY','LIBTV_API_KEY','LIBTV_TOKEN','MINIMAX_API_KEY')){
  $v=[Environment]::GetEnvironmentVariable($n)
  if([string]::IsNullOrEmpty($v)){ "UNSET  $n" } else { "SET    $n  first4=$($v.Substring(0,4))****" }
}
```

**真返回**：

```
UNSET  LIBTV_ACCESS_KEY
UNSET  LIBTV_API_KEY
UNSET  LIBTV_TOKEN
UNSET  MINIMAX_API_KEY
```

```powershell
# ✅ 已验：全机密钥池现状
py -3.14 tools/codex-scripts/five-dim.py cap model_key_pool
```

**真返回（原文摘录）**：

```json
{ "ok": true, "readonly": true, "keys_total": 0, "leases_active": 0,
  "known_profiles": ["agnes","deepseek"],
  "note": "按 AI 身份分池；一触手一号 = 批量注册 = 违规" }
```

🔴 **别把"未配"念成本簇的问题**：本簇**不需要**密钥；
上面那几个是**能力域**（`gbt-video`）的。**列出来是纪律性核对，不是本簇缺口。**
🔴 **报法纪律**：只说 **「已配 / 未配」** 或 **前 4 位掩码**。
**不许 echo、不许落盘、不许贴进规程/日报/对话**。本件里**不会出现任何一个真凭据**。

### 3.2 依赖（实测）

```powershell
# ✅ 已验（每一条都真跑过，下面是真实返回）
Get-Command ffmpeg         # → …\Gyan.FFmpeg_…\ffmpeg-8.1.2-full_build\bin\ffmpeg.exe
ffmpeg -version            # → ffmpeg version 8.1.2-full_build-www.gyan.dev
Get-Command yt-dlp         # → （找不到）
node --version             # → v24.15.0
```

| 依赖 | 谁要它 | 实测 |
|---|---|---|
| **`ffmpeg`** | `video-transcript-downloader`（转码/remux/抽音频） | ✅ **在**：`ffmpeg 8.1.2-full_build`（Gyan build，winget 装的） |
| **`yt-dlp`** | `video-transcript-downloader` 的**下载与字幕兜底路径** | 🔴 **不在 PATH** —— `Get-Command yt-dlp` 找不到；`yt-dlp --version` 报**不是可识别的命令** |
| **`youtube-transcript-plus`**（npm） | `video-transcript-downloader` 的**首选 YouTube 路径** | ❌ **未装**（`node_modules` 不存在，见 §4.2） |
| Node v24.15.0 | 跑 `vtd.js` | ✅ 在 |
| `video-pipeline` 的运行时 | —— | **无依赖**：它**是纯方法论**，不含可执行体 |

### 3.3 🔴 **闸一的正确说法：本簇现在一条都跑不通**

| 技能 | 卡在哪（**逐条实测**） |
|---|---|
| **`video-pipeline`** | **不卡** —— 但它**本来就没有可执行体**（"只蒸馏方法论，不含可执行插件"）⇒ **它永远给不出成品**，这是**设计如此**，不是故障 |
| **`video-transcript-downloader`** | **卡两件**：`yt-dlp` 不在 PATH **+** `youtube-transcript-plus` 未装（真跑报 `ERR_MODULE_NOT_FOUND`） |
| **`video-downloader`** | **卡"它只是个桩"**：无脚本、上游未装 |

⇒ **现在能说的最硬一句是**：**"本簇的三条技能，一条是方法论、一条缺依赖、一条是桩 ——
我一条视频都下载不了，一段字幕也拿不到。"**
**"技能写得很完整"和"这台机器上跑得起来"是两件事。**

---

## 4. 怎么调（**真命令 + 真返回**）

> 纪律：本节每一条都标了 **✅(真跑过)** 或 **(未验)**。**没跑过的不许说成跑过。**

### 4.1 `video-pipeline`（**无脚本，是"判据手册"**）

`video-pipeline` 盘上只有 `SKILL.md`（+ `_meta.json` / `_store_meta.json`），**没有任何脚本** ——
这与它自己的自述一致（*「本技能只蒸馏方法论，不含可执行插件」*）。
⇒ **本件不给它编命令。** 它的用法是**在动手前照它的闸去检查自己的计划**：

| 它的闸 | 怎么用（照原文） |
|---|---|
| 分镜表四层 | `sequence → scene → shot`，容器 `data/[频道]/episodes/[选题]/`；每 shot 必写**为什么这么选** |
| `shot.render` | 静帧（配运镜）/ 3D 角色 / 3D 物件 / 数据图 / 生成视频 —— **先读旁白，再决定** |
| `shot.eyeline` | 一条记录同时驱动**四处**（分镜板图标 · MCP 入参 · 源图提示词 · 拍摄脚本），**四处必须同源** |
| `shot.depth` | 数"观众一次要读几样东西"：一样 → 浅景深并点名锐面；两样以上 → 深景深并从前到后列出 |
| `shot.style` | **一个镜头要离开全片预设只能走这个字段**，且必须**经人工在 HITL 里批准过** |
| 可转发物 | 一句能原样被转出去的话；**「求转发」不算，那是请求**；缺了分镜板打回 |
| 信息句 | 去掉人名**仍为真**的一句 —— 现在时、不填数字、不填人名、不描述画面 |

### 4.2 `video-transcript-downloader`（✅ **真跑了，失败也是真读数**）

```powershell
# ✅ 已验：真跑
node "C:\Users\ADMIN\.openclaw-autoclaw\skills\video-transcript-downloader\scripts\vtd.js" --help
```

**真返回（原文摘录）**：

```
Error [ERR_MODULE_NOT_FOUND]: Cannot find package 'youtube-transcript-plus'
imported from C:\Users\ADMIN\.openclaw-autoclaw\skills\video-transcript-downloader\scripts\vtd.js
    at Object.getPackageJSONURL (node:internal/modules/package_json_reader:301:19)
    …
```

**旁证（同一次会话里读到的）**：

```powershell
# ✅ 已验
Get-Content "…\video-transcript-downloader\package.json" -Raw
# → { "name": "video-transcript-downloader", "version": "1.0.0", "private": true,
#     "type": "module", "dependencies": { "youtube-transcript-plus": "^1.1.1" } }

Test-Path "…\video-transcript-downloader\node_modules"     # → False
```

🔴 **这一发说明三件事**：
1. **`vtd.js` 是 ESM（`"type": "module"`）** ⇒ 依赖必须在**技能自己的目录**里能解析到；
2. **`node_modules` 根本不存在** ⇒ **`.js` 在、依赖不在**，Node 在 **import 那一层**就抛错，
   **连 `--help` 都到不了**；
3. **它是被 `npm ci` 落下的那一步**（`SKILL.md` 的 Setup 原文：
   `cd ~/Projects/agent-scripts/skills/video-transcript-downloader && npm ci`）。

⚠️ 🔴 **`SKILL.md` 的 Setup 路径是本机不存在的路径**：
它写 `~/Projects/agent-scripts/skills/…`，而**实测真身**在
`~/.openclaw-autoclaw/skills/video-transcript-downloader`。
⇒ **照抄 Setup 会 `cd` 到一个不存在的目录。**
⚠️ **未验**：`npm ci` 的真实执行 —— 它**出网 + 在该技能目录落 `node_modules`**，
属于"改盘/装依赖"，**要主人点头**（§5）。**本件没跑。**

### 4.3 `video-downloader`（**是桩，无命令可跑**）

`video-downloader` 目录里只有 `SKILL.md`。它正文给的唯一"命令"是：

```bash
# SKILL.md 原文（这是叫你去浏览器看，不是可执行流程）
open https://github.com/ComposioHQ/awesome-claude-skills/tree/master/video-downloader
```

⇒ **本件不给它编命令。** 要用它 ⇒ **先出网 + 主人点头装上游包**（§5）。

### 4.4 边界核对：能力域那边**别在本件里找**

```powershell
# ✅ 已验（只读）
py -3.14 tools/codex-scripts/omni.py list --domain video
# → ── 能力位 4 条 ──  media_pipeline / libtv_skill / libtv_workflow / h3_video_gen
```

这 4 位的**逐个用法、授权查法、读数陷阱**在 **`gbt-video`** 里（那是能力域规程）。
🔴 **本件不复制它的读数** —— 只记一句它自己的结论：
**这 4 位"全是只读契约面，真出片/出图的那条生成端一条都没接线"。**
要查它们的门：`py -3.14 tools/codex-scripts/five-dim.py cap <能力位>`（`run_task` 唯一门）。

---

## 5. 闸二 · 出片/发布/下载的动作**必须先问主人**

**本条高于技能自己的任何提示。** 🔴 **本簇的"发布端"有个特殊之处，得说清**：

`video-pipeline` 的原文写着 *「**主人 2026-09-21 定：自动发布先不开**，
链路做到「成片 + 文案」为止」*，并且对发布端有一句极硬的话：

> *「发布工具**自身没有复核闸**，一次调用就是一次公开发帖 —— 所以它**只能**躲在发布技能的
> HITL 门后面。（**本工作区主人已定：发布端不启用。**）」*

🔴 **读法**：**"发布端不启用"是主人的纪律，不是"本机没有发布工具"。**
⇒ **本规程把这条纪律顶到最前面**：本簇**任何**上传/发布动作，
**先过主人的一次明确同意**，而且**默认答案是不做**。

**算"写出去"的动作（一律先问主人）**：

| 动作 | 为什么算"写出去" |
|---|---|
| 🔴 **把成片发布到任何公开平台**（YouTube / 抖音 / TikTok / B站 / 视频号…） | **不可撤回的公开动作**；主人已定**发布端不启用** |
| **发邮件/消息把成品或链接给真人** | 离开本机的社会动作 |
| **下载视频/音频/字幕到本地** | 占盘、可能涉版权；`yt-dlp` 还有**风控/地域限制**风险 —— 建议先确认 |
| **装依赖**（`npm ci` 落 `node_modules`、装 `yt-dlp`） | **改本机全局/技能目录状态** |
| **`npx skills add …` / 克隆上游包**（`video-downloader` 那条路） | 出网 + 改技能目录 |
| **改 `~/.openclaw-autoclaw/skills/video-*` 下任何文件** | 改的是**别人技能的盘上状态**，本件**绝不擅自动手** |

**顺序（先干什么 → 拿什么回执）**：

1. **摊开四件事**：**身份**（以谁的名义）· **目标**（哪个平台/账号、哪个 URL、**指名道姓**）·
   **内容**（要发的原文或文件路径）· **影响面**（谁会看到、能不能撤回、`public` 还是 `unlisted`）。
2. **能预演就先预演**：`video-transcript-downloader` 的 `formats` 子命令
   **只列格式、不下载** ⇒ **可以先跑它把可选格式报给主人**（但**注意它现在连 import 都过不去**，§4.2）。
3. **等一次明确同意**：**只覆盖这一次**，不是"以后这类都同意"。主人没回话 = **没同意**，停。
4. **同意后照原命令重试** —— 不是重写一条新命令。
5. **拿回执**：要读到**落盘文件的绝对路径** + 大小；发布类要**视频 id / 链接**。
   **只说"成功了"不算回执。**
6. **失败就记失败**：原样保留错误与退出码，**不许把失败写成成功**。
7. **不许静默重试写操作**：上传盲重试 = **重复投稿**；下载盲重试 = **重复占盘**。
   **重试前先确认第一次到底成没成。**

---

## 6. 🔴 报告层红线（读数纪律）

> 出口前先问一句：**「这是事实，还是我读错了地方？」**

1. 🔴 **「有脚本」≠「跑得起来」**（本簇最贵的一条）：`video-transcript-downloader`
   **确实有 `scripts/vtd.js`（真文件）**，但**实测连 `--help` 都抛
   `ERR_MODULE_NOT_FOUND`** —— 因为 `node_modules` 不存在。
   ⇒ **"技能目录里有 .js"只说明作者写了脚本，不说明这台机器能执行它。**
2. 🔴 **`video-pipeline` 的韩语闸遇非韩文是"未检查"，不是"通过"**（原文明写，**照抄不美化**）：
   *「文案风格闸是韩语专用：`check-style.py` 遇到非韩文**退出 4（SKIP）并明说"未检查"**，
   **绝不说"通过"**。非韩文文案必须人工读。」*
   ⇒ **别把 `exit 4` 念成"风格没问题"。** 同族的已知局限还有：拍摄脚本与调研解析器**仅韩语**·
   分镜复核渲染的检查条句子**硬编码英文**· **端上出图会打散韩文字形**（带文字的帧必须走付费路径）。
3. 🔴 **「`omitAutoPublish` / 发布端不启用」是纪律，不是能力读数。**
   它的意思是**"我们决定不发"**，**不是**"本机没有发布工具"。
   ⇒ **别把它念成"系统里不存在发布这条路"** —— 真存在，是**我们主动不开**。
4. **「一条技能是桩」≠「这条能力不存在」**：`video-downloader` 只是**目录桩**，
   上游 `ComposioHQ/awesome-claude-skills` 里**真有**那个包。
   ⇒ 正确说法是**"本机没装，要用得先装"**，不是"这世上没有"。**两者不许混。**
5. **`omni.py list --domain video` 是宽松匹配**：那 18 条 agent 技能里
   **只有 3 条** name 以 `video-` 开头。⇒ **名单一律回图鉴按 `name` 前缀数**，
   别拿 `--domain` 的打印当"本簇名单"。
6. **有错也照原样记**：保留错误原文与**退出码**。
   `vtd.js` 的 `ERR_MODULE_NOT_FOUND` 是**依赖缺件**，**不是**"命令敲错了"。
7. **不许编命令、编路径、编技能名**：本文件每条命令要么标 **✅ 已验**，要么标 **(未验)** 并写明卡在哪。
   **没跑过的不许说成跑过。**
8. **凭据只报"已配/未配"或前 4 位掩码**：本件**零凭据**，这是纪律不是遗漏。

---

## 7. 本机踩过的坑（照做，别自己解读）

1. ✅ 🔴 **`vtd.js` 的 `node_modules` 不存在 ⇒ 连 `--help` 都跑不到。**
   真因：它是 ESM（`"type": "module"`），`youtube-transcript-plus` 要在**技能目录里**解析到，
   而 `Test-Path …\node_modules` ⇒ **False**。
   **别把这读成"脚本坏了"** —— 是**依赖没装**（`npm ci` 没跑过）。
2. ✅ 🔴 **`video-transcript-downloader` 的 `SKILL.md` Setup 路径在本机不存在。**
   它写 `cd ~/Projects/agent-scripts/skills/video-transcript-downloader && npm ci`，
   实测真身在 `~/.openclaw-autoclaw/skills/video-transcript-downloader`。
   ⇒ **照抄 Setup 会 `cd` 到空目录。** 这也是"技能文档 vs 本机现实"的典型错位。
3. ✅ **`yt-dlp` 不在 PATH**，而它是 `video-transcript-downloader` 的**下载与兜底路径**。
   技能的装法是 `brew install yt-dlp ffmpeg`（**macOS**）—— 本机**没有 `brew`**。
   对照：**`ffmpeg` 在**（`Get-Command ffmpeg` → winget 那个 Gyan build），
   ⇒ **本簇缺的只有 `yt-dlp` 那一件外部二进制**（加上 npm 那一件）。
4. ✅ **`video-pipeline` 是"方法论蒸馏"，不是"插件"。**
   目录里只有 `SKILL.md`，**没有 `check-style.py`、`cost-report.sh` 这些它在正文里点名的上游文件**。
   ⇒ 它提到那些脚本时是在**描述上游的行为**（作为判据的出处），
   **不是**"本机有这些脚本可跑"。**别去盘上找。**
5. ✅ 🔴 **`video` 这个域名在同一屏里指两样东西。**
   `omni.py list --domain video` 先打 **"能力位 4 条"**（`gbt-video` 的地盘），
   再打 **"agent 技能 18 条"**（本簇只占 3 条）。
   ⇒ **看读数先确认自己在读哪一段**（这正是 §0 第 1 条要钉的）。
6. ✅ **目录桩不会自己告诉你它是桩。** `video-downloader` 的 frontmatter 里
   `od.mode: video` / `od.category: video-generation` 看着像业务件，
   **"这是桩"那句写在正文第 30 行之后**。
   ⇒ **触发一个 design-asset 技能前，先看它正文有没有 "install the upstream bundle"。**
7. ⚠️ **（未验）`npm ci` 的真实执行。** 它会**出网**并往该技能目录写 `node_modules`
   ⇒ 属于"装依赖/改盘"，**要主人点头**。**本件没跑。**
8. ⚠️ **（未验）`yt-dlp` 的真实下载。** 补上二进制后能跑，但**真下载是外部动作**，
   且 `yt-dlp` 有**风控/地域限制**脾性 ⇒ **要主人点头**（§5）。**本件没跑。**

---

## 8. 未验清单（**如实列，不许拿它当通过**）

| 项 | 卡在哪 / 为什么不做 |
|---|---|
| **`video-pipeline` 出一件成品** | **永远不验（设计如此）**。它**没有可执行体**，原文自述"只蒸馏方法论，不含可执行插件"。**这不是缺口，是它的形态** |
| **`vtd.js` 真下一条视频/一份字幕** | **未验**。卡两件：`node_modules` 不存在（`ERR_MODULE_NOT_FOUND`）+ `yt-dlp` 不在 PATH（§3.2） |
| **`npm ci` 装 `youtube-transcript-plus`** | **未验（未跑）**。要**出网 + 在该技能目录落盘** ⇒ 属"装依赖"，要主人点头（§5） |
| **`video-downloader` 的上游包** | **未验（且本件不装）**。要 `npx skills add`／装 `ComposioHQ/awesome-claude-skills` = **出网 + 主人点头 + 改技能目录** |
| **任何一次真发布/上传** | 🔴 **本规程一次都没做，也不该由我做。** 主人已定**发布端不启用**（§5）；**这条不是"未验"，是"不做"** |
| **`check-style.py` 的 `exit 4（SKIP）` 真跑** | **未验**。该脚本**不在本机盘上**（它属上游 `social-flow`）；本件只照抄它自述的行为。**别把 `exit 4` 念成"通过"**（§6.2） |
| **`video` 域 4 个能力位** | **不在本件范围**（边界见 §0）。它们的用法与授权查法在 **`gbt-video`**；要现读走 `five-dim.py cap <能力位>` |
| **Ark 云端那条** | **不在本件范围**。走 **`gbt-arkcli`**（它自己的前缀 + 两道闸 + 计费纪律） |
| **本簇是否该进 `omni.py` 的 `DISTILLED_CLUSTERS`** | **未验（且本件不擅自动手）**。登记是交付报告里给主人的一行，**本件不自己写进 `omni.py`**（见 §10） |
| **本簇除这 3 条外还有没有隐藏成员** | **未验（口径性未验）**。图鉴是**现扫产物**（`python tools/codex-scripts/omni.py build`），重建后需重查 |

---

## 9. 不许做什么（红线）

1. 🔴 **不许自动发布/上传到任何公开平台。** 主人已定**发布端不启用**（§5）；
   `video-pipeline` 原文那句"发布工具自身没有复核闸，一次调用就是一次公开发帖"
   **必须当纪律照做**。
2. 🔴 **不许把明文密钥写进任何文件**（本簇不需要密钥，更没理由落盘）。
   凭据只走密钥池/DPAPI（本机 `keys_total: 0` ⇒ **如实报"未配"**）。
3. **不许动 `tools/codex-scripts/omni.py` / `security/policy.py`** —— 本件只加一份规程，**不改门、不改登记表**。
4. **不许改 `~/.openclaw-autoclaw/skills/video-*` 下任何技能文件** —— 本件是被管对象的规程，不是它的补丁。
5. 🔴 **不许重名或覆盖 `gbt-video`** —— 那份是**能力域**规程（4 个能力位）；
   本件是**技能簇**规程（3 条技能）。**两份都必须在，边界见 §0。**
6. **不许往 `~/.agents/skills/` 写任何东西**（工作区 AGENTS.md 明令：那是别的工具的共享目录）。
7. **不许擅自装依赖**：`npm ci`、装 `yt-dlp`、`npx skills add` 都要**出网 + 改本机 + 主人点头**。
8. **不许把目录桩念成能力**：`video-downloader` 无脚本、上游未装，**它不能被"执行"**。
9. **不许把 `video-pipeline` 的方法论念成本机能力**：它自述"不含可执行插件"，
   **盘上也没有它点名的那些上游脚本**（§7.4）。
10. **不许拿 `gbt-video` / `gbt-arkcli` 的读数替本件说话**，也不许反过来（§0 三处边界）。
11. **不许把本规程当官方文档**：本簇 3 条技能的**命令级细节以它们自己的 `SKILL.md` 为准**；
    本文件管的是**我们这儿的纪律、读法、诚实账**。

---

## 10. 固化与出处（**重启后要在**）

| 什么 | 在哪 |
|---|---|
| 本规程（源 · 真身） | `<仓>/skills/gbt-video-tools/SKILL.md` |
| 本规程（装机 · 托管目录） | `~/.openclaw-autoclaw/skills/gbt-video-tools/SKILL.md`（**与源稿逐字节相同**） |
| ⛔ **不许装到** | `~/.agents/skills/`（本仓 AGENTS.md 明令禁止） |
| ⚠️ **不许重名/覆盖** | `<仓>/skills/gbt-video/SKILL.md`（**能力域**那份，**已存在**） |
| 技能名单（3 条） | `<仓>/state/skill_atlas.json`（`name` 以 `video-` 开头）· 现扫可重建：`python tools/codex-scripts/omni.py build` |
| 真业务件（2 条） | `~/.openclaw-autoclaw/skills/video-pipeline` · `…/video-transcript-downloader`（**不由本件代管，别改**） |
| 目录桩（1 条） | `<仓>/审美相关skill/skills/video-downloader`（`design-asset` 通道） |
| **能力域**（不是本件） | `gbt-video`（4 位）· 现读 `py -3.14 tools/codex-scripts/five-dim.py cap <能力位>` |
| **Ark 云端**（不是本件） | `gbt-arkcli`（`arkcli +gen` / Seedream / Seedance） |
| 人话入口 | `python tools/codex-scripts/omni.py ask "帮我下载这个视频的字幕"` |
| 验收 | `py -3.14 tools/codex-scripts/verify-distill.py --cluster video` |

**深蒸登记（应加、本次未擅自动手）**：`omni.py` 的 `DISTILLED_CLUSTERS` 加一行

```python
    "video": "gbt-video-tools",       # 3 条（2 真业务件 + 1 目录桩）：按意图分簇 + 发布端不启用
```

加完后 `verify-distill.py --cluster video` 才会从 **`FAIL: 没登记这个簇`** 变 PASS。
⚠️ **注意别撞车**：`DISTILLED_DOMAINS` 里的 `"video": "gbt-video"` 是**能力域**那条（**已存在，别动**）；
新增的是 **`DISTILLED_CLUSTERS`** 里按 `video-` 前缀管**技能簇**的这一行。
（本次**没改** `omni.py` —— 交付报告里给主人这一行，**没交付就会 FAIL，不会静默变绿**。）

---

## 11. 诚实边界（这段不许删）

1. **本件是"用法规程"，不是"能力已具备"。** 它把 3 条技能**分簇、点名、定了纪律**；
   **每条技能的深度用法以它自己的 `SKILL.md` 为准**，本件**不替代**。
2. **本次实跑的都是只读/失败探针**：`omni.py list` · 图鉴前缀清点 · `Get-Command` · `--version` ·
   环境变量**存在性**（不打印值）· `cap model_key_pool`（只读）·
   `node scripts/vtd.js --help`（真跑，报 `ERR_MODULE_NOT_FOUND`）·
   `Get-Content package.json` · `Test-Path node_modules`。
   **没有下载过任何视频/音频/字幕，没有上传过任何东西，没有装过任何依赖，
   没有改过任何技能文件，也没有跑过任何生成动作。**
3. **本机状态是现读快照**（`ffmpeg` 8.1.2 在 · `yt-dlp` 不在 · `youtube-transcript-plus` 未装 ·
   `node_modules` 不存在 · 密钥池 `keys_total:0` · Node v24.15.0）。
   **换机器、补完依赖、或图鉴重建后，本件的读数都要重查。**
4. **凭据只报"已配/未配"**：本件**不出现任何凭据值**；
   `LIBTV_*` / `MINIMAX_API_KEY` 实测**全部 UNSET**（且**它们本来就属能力域，不属本簇**）。
5. **本件与 `gbt-video` / `gbt-arkcli` / `gbt-youtube` / `gbt-pptx` 的边界**见 §0；
   **谁都不许拿对方的读数替自己说话。**
