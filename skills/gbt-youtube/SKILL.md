---
name: gbt-youtube
displayName: GBT · YouTube 用法规程（技能簇 youtube-*）
version: 1.0.0
description: GBT小土豆V8 使用 YouTube 这一技能簇的用法规程。本簇按 `state/skill_atlas.json` 里 name 前缀核定共 3 条（`youtube-factory` · `youtube-watcher` · `youtube-clipper`），其中前 2 条是真业务件、`youtube-clipper` 是只指上游的目录桩。本规程把每条按意图分簇点名，钉死两道闸（① 凭据与依赖的**实测**账：`PEXELS_API_KEY` 未配、全机密钥池 `keys_total:0`、`yt-dlp` **不在 PATH**、`edge-tts` 在但不可用、`youtube-transcript-plus` **未装**；② **上传/发布到 YouTube 是公开发布，必须先问主人**），并记下真跑出来的读数（`get_transcript.py` 真跑吐 `Error: yt-dlp not found` 且 exit 1、`vtd.js` 真跑吐 `ERR_MODULE_NOT_FOUND`）与报告层红线（"工具在" ≠ "能出片"；"没报错" ≠ "下载到了"）。当用户要做 YouTube 视频/短视频/Shorts、要读某条视频的逐字稿或字幕、要下载视频/音频/字幕、要剪高光片段，或怀疑"怎么没出片/字幕拿不到"时使用。
triggers:
  - "YouTube"
  - "youtube"
  - "油管"
  - "视频字幕"
  - "逐字稿"
  - "transcript"
  - "字幕下载"
  - "Shorts"
  - "无脸视频"
  - "faceless"
  - "youtube-factory"
  - "youtube-watcher"
  - "youtube-clipper"
  - "剪高光"
  - "highlight reel"
---

# GBT · YouTube 用法规程（技能簇 `youtube-*`）

> 开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属
>
> 这是**我们自己的用法规程**（不是那 3 条技能官方文档的复述）。技能自身讲"每条怎么用"，
> 本文件讲"**在我们这台机器上，谁在什么条件下、按什么顺序去用它，什么已经真能跑、
> 什么还没接线、什么东西绝对不许自动发出去**"。
> 冲突时的裁决顺序：**本文件管我们的纪律** → 各技能自己的 `SKILL.md` 管命令细节。

---

## 0. 三处边界（**开工第一段就读这段**）

这一节是硬要求，三份规程各写一处，三处合起来才把"视频/幻灯片"这块地盘划清：

| 是谁 | 管什么 | 判决口径 | 它**不**管什么 |
|---|---|---|---|
| **`gbt-youtube`（本件）** | **YouTube 这一技能簇怎么用** —— 3 条技能的选用、两道闸、真跑读数、坑 | 以本件为纲，命令细节以各技能 `SKILL.md` 为准 | 不出本机能力位、不碰 Ark 云端、不碰幻灯片 |
| **`gbt-video-tools`** | **`video-*` 这一技能簇怎么用** —— 3 条技能的选用、两道闸、真跑读数、坑 | 同上 | **不是**"本机视频能力位"、**不是** Ark 云端那条 |
| **`gbt-video`**（已存在，**别重名别覆盖**） | **本机 `video` 职业域的 4 个能力位**（`media_pipeline` / `libtv_skill` / `libtv_workflow` / `h3_video_gen`）—— 走 `five-dim.py cap <能力位>` 的**能力域**规程 | 图鉴口径 | 不管技能簇、不管 YouTube/抖音这类外部平台 |
| **`gbt-arkcli`**（已存在） | **Ark 云端那一条**（`arkcli +gen` / Seedream / Seedance） | 它自己的调用前缀 + 登录闸 + 账号验证闸 + 计费纪律 | **不代表**本机任何技能或能力位已接线 |

**一句话记法**：**`gbt-youtube` 管"YouTube 技能怎么用"；`gbt-video-tools` 管"其它视频技能怎么用"；
`gbt-video` 管"本机视频能力位在哪、要不要授权"；`gbt-arkcli` 管"Ark 云端那条"。
四者谁都不许拿对方的读数替自己说话。**

🔴 **一条本簇特有的边界**：`youtube-*` 这 3 条与 `video-*` 那 3 条**有重叠风险**
（`video-transcript-downloader` 也能下 YouTube 字幕）。分工口径：
**"这条活的主语是 YouTube" ⇒ 走本件；"主语是视频文件本身（不分平台）" ⇒ 走 `gbt-video-tools`。**
两条都能干时**只选一条，别同时挂两条技能**（重复下载 = 白花时间和流量）。

---

## 1. 它是什么 / 名单怎么核（**以图鉴现读为准**）

**核定口径**：`state/skill_atlas.json` 里 `name` 以 **`youtube-`** 开头的条目。

```powershell
py -3.14 tools/codex-scripts/omni.py list --domain youtube    # ✅ 已验
```

**真返回（原文摘录）**：

```
── 能力位 0 条（万能插 · 走 run_task 唯一门）──

── agent 技能 3 条（按名字加载执行）──
     youtube-clipper                  design-asset |
     youtube-factory                  agent-skill  Generate complete YouTube videos from a single prompt - scri
     youtube-watcher                  agent-skill  Fetch and read transcripts from YouTube videos. Use when you
```

⇒ 🔴 **本簇在"万能插"里是 0 个能力位。** 图鉴 `/` 按 name 前缀数是 **3 条技能**，
`omni.py gaps` 也报 **`youtube-*  3 条  ⏳ 在队里（有技能，但无 GBT 口径规程）`** —— **三方读数一致**。

| # | 技能 | 通道 | 落点 | 形态 |
|---|---|---|---|---|
| 1 | **`youtube-factory`** | `agent-skill` | `~/.openclaw-autoclaw/skills/youtube-factory` | **真业务件**（164 行，v1.3.0，作者 Mayank8290；自述"100% free tools"） |
| 2 | **`youtube-watcher`** | `agent-skill` | `~/.openclaw-autoclaw/skills/youtube-watcher` | **真业务件**（48 行 + `scripts/get_transcript.py` 81 行） |
| 3 | **`youtube-clipper`** | `design-asset` | `<仓>/审美相关skill/skills/youtube-clipper` | ⚠️ **目录桩**（42 行，只指上游 `op7418/Youtube-clipper-skill`，**无脚本**） |

**真身/技能落盘（现读）**：

```powershell
# ✅ 已验：managed 目录里本簇只有 2 条真业务件
Get-ChildItem "C:\Users\ADMIN\.openclaw-autoclaw\skills" -Directory |
  Where-Object { $_.Name -match '^(youtube)' } | Select-Object -ExpandProperty Name
# → youtube-factory / youtube-watcher
```

⚠️ **边界（写清楚）**：本簇的每条技能都**只管 YouTube 这一侧**。
**"出一段视频"这件事本身**：本机 `video` 域的 4 个能力位**生成端一条都没接**
（见 `gbt-video`），**Ark 云端那条**走 `gbt-arkcli`。
本簇**既不替 `gbt-video` 说话，也不替 `gbt-arkcli` 报价**。

---

## 2. 按意图分簇（3 条逐个点名）

### 簇 A · 读 → 拿逐字稿/字幕（**本簇唯一有真脚本的一条**）

| 技能 | 什么时候用它 | 怎么用 |
|---|---|---|
| **`youtube-watcher`** | "把这条视频总结一下" / "这条视频讲了什么" / "给我逐字稿" —— **只要文字，不要视频文件** | 跑它自己的脚本把字幕转成纯文本，**再读输出做总结/问答**。它**不生成视频、不下载视频** |

**它的真命令（`SKILL.md` 原文）**：

```bash
python3 {baseDir}/scripts/get_transcript.py "https://www.youtube.com/watch?v=VIDEO_ID"
```

**它怎么干活（源码实测，`scripts/get_transcript.py`）**：**不是**调 YouTube API，
而是**外壳调 `yt-dlp`** 拿 `.vtt` 字幕，再在本地把 WebVTT 清洗成纯文本：

```python
cmd = ["yt-dlp", "--write-subs", "--write-auto-subs", "--skip-download",
       "--sub-lang", "en", "--output", "subs", url]
```

⇒ 🔴 **三个硬事实（源码级，不是猜的）**：
1. **它依赖 `yt-dlp` 在 PATH 里**。找不到就 `print("Error: yt-dlp not found. Please install it.")` + `sys.exit(1)`。
2. **字幕语言写死 `--sub-lang en`**（源码第 46 行）。**非英语视频它拿不到你要的那个语言**
   —— 技能正文说"Works with videos that have closed captions (CC) or auto-generated subtitles"，
   **但那句没告诉你语言写死了**。
3. **`--skip-download`**：只下字幕，**不下视频**。⇒ **它不可能"下载视频"**，别拿它当下载器。

### 簇 B · 造 → 一条完整的 YouTube 视频（**依赖最多的那条**）

| 技能 | 什么时候用它 | 怎么用 |
|---|---|---|
| **`youtube-factory`** | "从一个主题做一条能发的 YouTube 视频" —— 脚本 / 配音 / 素材 / 字幕 / 封面一条龙 | 六步：**脚本**（用你的 LLM 写）→ **配音**（免费 Edge TTS）→ **B-roll 素材**（Pexels 免费）→ **合成**（FFmpeg）→ **字幕**（烧进画面）→ **封面**（自动生成） |

**它的命令形态（`SKILL.md` 原文，是斜杠命令不是 shell）**：

```
/youtube-factory [topic]
/youtube-factory script [topic] --length [minutes]
/youtube-factory [topic] --voice [en-US-ChristopherNeural]
/youtube-factory [topic] --style [documentary]
/youtube-factory [topic] --shorts
```

**产物落点（`SKILL.md` 原文）**：`~/Videos/OpenClaw/<your-video-title>/`
里面 6 件：`script.md` · `voiceover.mp3` · `video_raw.mp4` · `video_final.mp4` ·
`thumbnail.jpg` · `metadata.json`。

**它要三件（`SKILL.md` 的 `metadata.openclaw.requires` 原文）**：

```yaml
requires: { bins: ["ffmpeg", "edge-tts"], env: ["PEXELS_API_KEY"] }
primaryEnv: "PEXELS_API_KEY"
```

⇒ 🔴 **本簇"凭据闸"就落在这三件上**（实测见 §3）：
**`ffmpeg` 在 ✅ · `edge-tts` 在但不可用 ❌ · `PEXELS_API_KEY` 未配 ❌** ⇒ **三缺二。**
⚠️ 它给的 `--voice` 候选里有 `en-GB-SoniaNeural` / `en-AU-NatashaNeural` 等 6 个，
**都是英语声音**；素材源 **Pexels 是免费但要 key**。
⚠️ 它正文还写 `brew install ffmpeg` / `pip install edge-tts pillow python-dotenv requests`
—— **`brew` 是 macOS 写法，本机是 Windows，照抄必失败**（§7）。

### 簇 C · 剪 → 高光片段

| 技能 | 状态 | 怎么处置 |
|---|---|---|
| **`youtube-clipper`** | ⚠️ **目录桩**：42 行，`od.mode: video` / `od.category: video-generation`，上游 `https://github.com/op7418/Youtube-clipper-skill`，**无脚本、上游未装** | 只在规划期被"发现"。原文：*「To run the full upstream workflow with its original assets, scripts, and references, install the upstream bundle into your active agent's skills directory」* ⇒ **要用真流程，得先出网 + 主人点头装上游包。不许说"本机有剪高光能力"。** |

**选路示例**：用户说"帮我总结这条视频" → **`youtube-watcher`**（不是 `youtube-factory`）；
"用这个主题做条能发的视频" → **`youtube-factory`**（并先摊开 §5 那四件事）；
"把这条视频剪成高光" → **`youtube-clipper`** ⇒ **先说明它是桩、要装上游**。

---

## 3. 闸一 · 凭据与依赖（**只报已配/未配，绝不贴值**）

### 3.1 凭据（实测：**本簇要的密钥未配，全机密钥池也是空的**）

```powershell
# ✅ 已验：NAMES ONLY，绝不打印值
foreach($n in @('PEXELS_API_KEY','YOUTUBE_API_KEY','GOOGLE_API_KEY')){
  $v=[Environment]::GetEnvironmentVariable($n)
  if([string]::IsNullOrEmpty($v)){ "UNSET  $n" } else { "SET    $n  first4=$($v.Substring(0,4))****" }
}
```

**真返回**：

```
UNSET  PEXELS_API_KEY
UNSET  YOUTUBE_API_KEY
UNSET  GOOGLE_API_KEY
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

⇒ **`keys_total: 0`** —— **本机没有任何可借的密钥。**

| 名字 | 谁要它 | 实测 |
|---|---|---|
| **`PEXELS_API_KEY`** | `youtube-factory`（B-roll 素材，`primaryEnv`） | ❌ **UNSET（未配）** |
| `YOUTUBE_API_KEY` | **本簇 3 条技能都不要**（`youtube-watcher` 走 `yt-dlp` 不走 API） | ❌ UNSET（**点了名但没人要它** —— 这是纪律性核对，不是缺口） |
| `GOOGLE_API_KEY` | **本簇 3 条技能都不要** | ❌ UNSET（同上） |

🔴 **报法纪律**：只说 **「已配 / 未配」** 或 **前 4 位掩码**（如 `sk-a1b2****`）。
**不许 echo、不许落盘、不许贴进规程/日报/对话**。本件里**不会出现任何一个真凭据**。

⚠️ **`youtube-factory` 的 `SKILL.md` 写 `echo "PEXELS_API_KEY=your_key" >> ~/.openclaw-video-skills/config.env`**
—— 本件**不执行它**（那是落盘明文，见 §9 红线）。
**实测该配置文件本身也不存在**：

```powershell
# ✅ 已验
Test-Path "$env:USERPROFILE\.openclaw-video-skills\config.env"    # → False
```

### 3.2 依赖（实测：**三件里只有一件能用**）

```powershell
# ✅ 已验（每一条都真跑过，下面是真实返回）
Get-Command ffmpeg     # → …\Gyan.FFmpeg_…\ffmpeg-8.1.2-full_build\bin\ffmpeg.exe
ffmpeg -version        # → ffmpeg version 8.1.2-full_build-www.gyan.dev
Get-Command yt-dlp     # → （找不到）
python3 --version      # → Python 3.14.5
Get-Command edge-tts   # → …\Python312\Scripts\edge-tts.exe
node --version         # → v24.15.0
```

| 依赖 | 谁要它 | 实测 |
|---|---|---|
| **`ffmpeg`** | `youtube-factory`（合成）、`video-transcript-downloader`（转码） | ✅ **在**：`ffmpeg 8.1.2-full_build`（Gyan build，winget 装的） |
| **`yt-dlp`** | **`youtube-watcher` 的唯一依赖** | 🔴 **不在 PATH** —— `Get-Command yt-dlp` 找不到；`yt-dlp --version` 报**不是可识别的命令** |
| **`edge-tts`** | `youtube-factory`（配音） | ⚠️ **可执行文件在，但实测不可用**：`edge-tts --version` 与 `edge-tts --help` **都是 `exit=1` 且无输出**（装在 **Python312** 的 Scripts 里） |
| `youtube-transcript-plus`（npm） | `video-transcript-downloader` 的首选路径 | ❌ **未装**（见 §4.3） |
| Python 3.14.5 | —— | ✅ 在 |

### 3.3 🔴 **闸一的正确说法：这三条技能现在一条都跑不通**

| 技能 | 卡在哪（**逐条实测**） |
|---|---|
| **`youtube-watcher`** | **卡 `yt-dlp`**：真跑脚本 ⇒ `Error: yt-dlp not found. Please install it.` + `exit=1` |
| **`youtube-factory`** | **卡两件**：`PEXELS_API_KEY` 未配 **+** `edge-tts` 不可用（`exit=1`） |
| **`youtube-clipper`** | **卡"它只是个桩"**：无脚本、上游未装 |

⇒ **现在能说的最硬一句是**：**"这三条技能的流程、依赖、产物形状我都读全了，
但工具链一条都没齐 —— 我一条视频都出不了，一条字幕都拿不到。"**
**"技能写得很完整"和"这台机器上跑得起来"是两件事。**

---

## 4. 怎么调（**真命令 + 真返回**）

> 纪律：本节每一条都标了 **✅(真跑过)** 或 **(未验)**。**没跑过的不许说成跑过。**

### 4.1 `youtube-watcher` 的脚本（✅ **真跑了，失败也是真读数**）

```powershell
# ✅ 已验：真跑（拿一条公开视频试，脚本在"找 yt-dlp"这一层就断了，没有出网）
py -3.14 "C:\Users\ADMIN\.openclaw-autoclaw\skills\youtube-watcher\scripts\get_transcript.py" `
  "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
```

**真返回（原文）**：

```
Error: yt-dlp not found. Please install it.
exit=1
```

✅ **语法也单独验过**：`py -3.14 -m py_compile scripts/get_transcript.py` ⇒ **`exit=0`**
（脚本本身没语法错，**是依赖缺**，不是脚本坏）。

🔴 **这一发的意义**：它证明**脚本真的会跑、真的会报错**（不是"文件不存在"那种假失败），
而且**报错信息干净可读**。⇒ **补上 `yt-dlp` 后它就能进下一步。**
⚠️ **`{baseDir}` 要替换成真实技能目录**（`~/.openclaw-autoclaw/skills/youtube-watcher`），
技能里写的 `{baseDir}` 是占位符，**照抄会报路径不存在**。

### 4.2 `youtube-factory`（**未验：一条都跑不了**）

```bash
# SKILL.md 原文的装法（⚠️ brew 是 macOS 写法，本机照抄必失败）
brew install ffmpeg
pip install edge-tts pillow python-dotenv requests
echo "PEXELS_API_KEY=your_key" >> ~/.openclaw-video-skills/config.env
```

**未验**，卡在三处（逐条说明，不含糊）：
1. **它是 `editing-cordis` 之外的斜杠命令形态**（`/youtube-factory [topic]`），
   是**给 OpenClaw 客户端**的命令，**不是**一条我能直接 `pwsh` 跑的 shell 命令
   ⇒ **本机没有对应的可执行入口**（技能目录里**没有任何脚本**，只有 `SKILL.md`）。
2. **`PEXELS_API_KEY` 未配** ⇒ B-roll 那一步拿不到素材。
3. **`edge-tts` 实测 `exit=1` 不可用** ⇒ 配音那一步出不来。

⇒ 我**不把这包装成"跑过了"**。

### 4.3 `video-transcript-downloader` 的 `vtd.js`（**旁证：本簇同族技能也断在依赖**）

虽然这条属于 `video-*` 簇（规程在 `gbt-video-tools`），但它**首选路径就是 YouTube**，
所以读数放这儿做旁证：

```powershell
# ✅ 已验
node "C:\Users\ADMIN\.openclaw-autoclaw\skills\video-transcript-downloader\scripts\vtd.js" --help
```

**真返回（原文摘录）**：

```
Error [ERR_MODULE_NOT_FOUND]: Cannot find package 'youtube-transcript-plus'
imported from C:\Users\ADMIN\.openclaw-autoclaw\skills\video-transcript-downloader\scripts\vtd.js
```

**旁证**：`package.json` 里 `dependencies: { "youtube-transcript-plus": "^1.1.1" }`，
而 `node_modules` 目录**不存在**（`Test-Path … \node_modules` → **False**），
技能正文要求先 `npm ci`。⇒ **同一族的 YouTube 路都断在依赖上，不是孤例。**

### 4.4 本簇的"零能力位"读数（**别去找**）

```powershell
# ✅ 已验
py -3.14 tools/codex-scripts/omni.py list --domain youtube
# → ── 能力位 0 条（万能插 · 走 run_task 唯一门）──
```

⇒ 🔴 **`youtube` 不在万能插的能力位里** ⇒ **别去 `five-dim.py cap` 找它**
（那会报图鉴里不存在）。本簇**只能按技能名加载执行**。
对照：`video` 域**有** 4 个能力位（见 `gbt-video`）—— **两件事，别混。**

---

## 5. 闸二 · 上传/发布/公开的动作**必须先问主人**

**本条高于技能自己的任何提示。** 🔴 **本簇是这个"闸二"最要紧的地方** ——
因为 `youtube-factory` 这个技能名字里就写着 **"publish-ready"**，
它自述产物里有一个 **`video_final.mp4`** 并且正文注释是 **`# With captions (upload this!)`**。

🔴 **"upload this!" 是技能作者的话，不是主人的话。** 本规程**明确覆盖它**：
**技能建议你上传 ≠ 你可以上传。**

**算"写出去"的动作（一律先问主人）**：

| 动作 | 为什么算"写出去" |
|---|---|
| 🔴 **上传/发布视频到 YouTube**（含 Shorts / TikTok / Reels —— 技能正文自己点名的三个平台） | **不可撤回的公开动作**：发出去就有人看到了，而且可能被推荐、被转载、被存档 |
| **改标题/描述/标签/封面（已发布视频）** | 改的是**别人已经在看的**东西 |
| **设可见性（public / unlisted / private）** | `public` 与 `private` 是两个世界 |
| **发邮件/消息把成品或链接给真人** | 离开本机的社会动作 |
| **下载视频到本地** | ⚠️ **也建议先确认**：占盘、可能涉版权；**本件不替代主人对版权的判断** |
| **装环境**（`pip install edge-tts …` / 装 `yt-dlp` / `brew install`） | **改本机全局状态** |
| **写 `~/.openclaw-video-skills/config.env`** | **明文落盘凭据** —— 见 §9，**本件绝不执行** |
| **`npx skills add …` 装上游技能包**（`youtube-clipper` 那条路） | 出网 + 改技能目录 |

**顺序（先干什么 → 拿什么回执）**：

1. **摊开四件事**：**身份**（发到哪个频道/以谁的名义）· **目标**（具体平台+账号，**指名道姓**）·
   **内容**（成品文件路径 + 标题/描述原文）· **影响面**（谁会看到、能不能撤回、
   `public` 还是 `unlisted`）。
2. **能预演就先预演**：`youtube-watcher` 的**读字幕**是纯读（不写盘、不上传），
   **可以先跑它拿素材**；`youtube-factory` 的 `--length` / `--style` / `--voice` 参数
   **先只用来出脚本**（`/youtube-factory script [topic]`），**脚本阶段不生成也不发布**。
3. **等一次明确同意**：**只覆盖这一次**，不是"以后这类都同意"。主人没回话 = **没同意**，停。
4. **同意后照原命令重试** —— 不是重写一条新命令。
5. **拿回执**：要读到**成品文件的绝对路径** + **视频 id / 链接**（若已发布）。
   只说"成功了"**不算回执**。
6. **失败就记失败**：原样保留错误与退出码，**不许把失败写成成功**。
7. **不许静默重试写操作**：**上传盲重试 = 重复投稿**（可能变成两条公开视频）。
   **重试前先确认第一次到底成没成。**

---

## 6. 🔴 报告层红线（读数纪律）

> 出口前先问一句：**「这是事实，还是我读错了地方？」**

1. 🔴 **「工具在」≠「能用」**（本簇最贵的一条）：`edge-tts` 的 `.exe` **确实在盘上**
   （`…\Python312\Scripts\edge-tts.exe`），但**实测 `--version` 与 `--help` 都是 `exit=1` 且无输出**
   ⇒ **"`Get-Command` 找得到"只说明有个文件叫这个名字，不说明它能跑。**
   同理 `ffmpeg` 在**并且真的能跑**（`-version` 有输出）—— **两件的差别就是靠"真跑一次"分出来的。**
2. 🔴 **「没报错」≠「拿到了」**：`youtube-watcher` 的脚本有 3 条静默出口 ——
   ① `yt-dlp` 跑成功但**没有 `.vtt`** ⇒ `print("No subtitles found.")` + `exit 1`；
   ② 视频**没有 CC 也没自动字幕** ⇒ 同上；
   ③ 字幕语言**不是 `en`**（源码写死 `--sub-lang en`）⇒ 同样落进 ①。
   ⇒ **拿到空/报错时，先分清是"依赖缺"还是"这条视频真没字幕"，别一律念成"技能坏了"。**
3. **「技能名里有 publish」≠「CLI 会拦你」**：`youtube-factory` 的斜杠命令**不会**问你要 `--yes`。
   **CLI 不拦，我们必须自己拦**（§5 就是那道自设的闸）——**别拿"它没拦我"当"可以发"。**
4. **`youtube-factory` 的 `metadata.json` 是"生成物"，不是"已发布凭据"**：
   它里面装的是 Title/Description/Tags 的**草稿**。**产出它不等于上传了。**
5. **有错也照原样记**：保留错误原文与**退出码**。
   `get_transcript.py` 的 `exit=1` 是**依赖缺件**，**不是**"命令敲错了"。
6. **不许编命令、编路径、编技能名**：本文件每条命令要么标 **✅ 已验**，要么标 **(未验)** 并写明卡在哪。
   **没跑过的不许说成跑过。**
7. **凭据只报"已配/未配"或前 4 位掩码**：本件**零凭据**，这是纪律不是遗漏。

---

## 7. 本机踩过的坑（照做，别自己解读）

1. ✅ 🔴 **`yt-dlp` 不在 PATH —— 这是 `youtube-watcher` 的唯一死因。**
   真跑返回 `Error: yt-dlp not found. Please install it.` + `exit=1`。
   ⚠️ 而且它的 `SKILL.md` 给的装法是 `brew install yt-dlp`（**macOS**）或
   `pip install yt-dlp`——**在 Windows 上 `brew` 不存在**；`pip install yt-dlp` 才可能有用，
   但**装它要出网 + 主人点头**（§5）。
2. ✅ 🔴 **`youtube-watcher` 的字幕语言写死 `en`。**
   源码第 46 行 `"--sub-lang", "en"`。**技能正文完全没提这件事。**
   ⇒ 拿中文视频试它、结果"没字幕"，**很可能不是视频没字幕，是语言参数不匹配。**
3. ✅ **`youtube-watcher` 用的是"外壳调 `yt-dlp`"而不是 YouTube API。**
   这解释了两件事：① 它**不需要** `YOUTUBE_API_KEY`；
   ② 它**继承 `yt-dlp` 的全部脾气**（地域限制、风控、需要 cookies 等）。
   ⇒ **别拿"要不要 API key"去判它能不能跑。**
4. ✅ **`edge-tts` 装在 Python312，而不是当前默认的 3.14。**
   `py -0p` 显示本机有 **3.14（默认）/ 3.13 / 3.12 / 3.10** 四个版本。
   `edge-tts.exe` 在 `…\Programs\Python\Python312\Scripts\` 下，**且实测 `exit=1`**。
   ⇒ **"它在 PATH 里"和"它能跑"是两件事**；要修它也得先搞清楚装到哪个解释器。
5. ✅ **`youtube-factory` 的装法是 macOS/Linux 写法。**
   `brew install ffmpeg` 本机**没有 `brew`**；它正文的 `pip install` 列表里还有
   `pillow` / `python-dotenv` / `requests`（**用不用得上取决于它自己那套脚本，
   而它目录里一个脚本都没有**）。
6. ✅ **`youtube-factory` 没有脚本文件。** 实测它的目录里只有
   `SKILL.md` + `_meta.json` + `_store_meta.json`。
   ⇒ **它是"提示词级技能"（靠斜杠命令驱动宿主），不是"可执行工具"。**
   **别去它的目录里找 `.py`/`.sh`。**
7. ✅ **目录桩不会自己告诉你它是桩。** `youtube-clipper` 的 frontmatter 里
   `od.mode: video` 看着像业务件，**"这是桩"那句写在正文第 30 行之后**。
   ⇒ **触发一个 design-asset 技能前，先看它正文有没有 "install the upstream bundle"。**
8. ⚠️ **（未验）`--shorts` 的实际行为。** `SKILL.md` 说它出 **9:16 竖版、60 秒**，
   面向 YouTube Shorts / TikTok / Reels。**本规程没跑过**（依赖缺，跑不了）。
   而且 🔴 **它一次点名三个公开平台** ⇒ **发布闸（§5）在 `--shorts` 上尤其不能松。**

---

## 8. 未验清单（**如实列，不许拿它当通过**）

| 项 | 卡在哪 / 为什么不做 |
|---|---|
| **`youtube-watcher` 真拿到一条逐字稿** | **未验**。卡 `yt-dlp` 不在 PATH（§3.2）。补它要**出网 + 主人点头**；且**真下载是外部动作**（§5） |
| **`youtube-factory` 真出一条视频** | **未验**。三重卡：① 它是斜杠命令、**本机无对应可执行入口**；② `PEXELS_API_KEY` 未配；③ `edge-tts` `exit=1` 不可用 |
| **`youtube-factory` 的 `--shorts` / 各 `--voice` / 各 `--style`** | **未验（未跑）**。同上；**且默认 6 个 voice 全是英语**，中文场景未验 |
| **`youtube-clipper` 的上游包** | **未验（且本件不装）**。要 `npx skills add`／克隆 `op7418/Youtube-clipper-skill` = **出网 + 主人点头 + 改技能目录** |
| **任何一次真上传/发布** | **本规程一次都没做，也不该由我做。** 上传是**公开不可撤回**动作（§5），**必须主人点名 + 明确同意** |
| **`~/.openclaw-video-skills/config.env`** | **未验（且本件拒绝执行）**。它要**明文落盘** `PEXELS_API_KEY` ⇒ 违反 §9 红线。实测该文件**目前不存在** |
| **本簇是否该进 `omni.py` 的 `DISTILLED_CLUSTERS`** | **未验（且本件不擅自动手）**。登记是交付报告里给主人的一行，**本件不自己写进 `omni.py`**（见 §10） |
| **本簇除这 3 条外还有没有隐藏成员** | **未验（口径性未验）**。图鉴是**现扫产物**（`python tools/codex-scripts/omni.py build`），重建后需重查 |

---

## 9. 不许做什么（红线）

1. 🔴 **不许自动上传/发布到 YouTube、TikTok、Reels 或任何公开平台。**
   **哪怕技能自己写着 `# upload this!`** —— 那是作者的建议，**不是主人的授权**（§5）。
2. 🔴 **不许把明文密钥写进任何文件**：`youtube-factory` 正文那句
   `echo "PEXELS_API_KEY=your_key" >> ~/.openclaw-video-skills/config.env`
   **本件明确拒绝执行**。凭据只走密钥池/DPAPI（本机 `keys_total: 0` ⇒ **如实报"未配"**）。
3. **不许动 `tools/codex-scripts/omni.py` / `security/policy.py`** —— 本件只加一份规程，**不改门、不改登记表**。
4. **不许改 `~/.openclaw-autoclaw/skills/youtube-*` 下任何技能文件** —— 本件是被管对象的规程，不是它的补丁。
5. **不许往 `~/.agents/skills/` 写任何东西**（工作区 AGENTS.md 明令：那是别的工具的共享目录）。
6. **不许擅自装环境**：装 `yt-dlp`、修 `edge-tts`、`pip install` 一堆、
   `npx skills add` 都要**出网 + 改本机 + 主人点头**。
7. **不许把目录桩念成能力**：`youtube-clipper` 无脚本、上游未装，**它不能被"执行"**。
8. **不许把 `Get-Command` 找得到念成"能用"**（§6.1 的 `edge-tts` 就是活证据）。
9. **不许把"技能写得很完整"念成"能出片"**：本簇**三条现在一条都跑不通**（§3.3）。
10. **不许把本规程当官方文档**：本簇 3 条技能的**命令级细节以它们自己的 `SKILL.md` 为准**；
    本文件管的是**我们这儿的纪律、读法、诚实账**。

---

## 10. 固化与出处（**重启后要在**）

| 什么 | 在哪 |
|---|---|
| 本规程（源 · 真身） | `<仓>/skills/gbt-youtube/SKILL.md` |
| 本规程（装机 · 托管目录） | `~/.openclaw-autoclaw/skills/gbt-youtube/SKILL.md`（**与源稿逐字节相同**） |
| ⛔ **不许装到** | `~/.agents/skills/`（本仓 AGENTS.md 明令禁止） |
| 技能名单（3 条） | `<仓>/state/skill_atlas.json`（`name` 以 `youtube-` 开头）· 现扫可重建：`python tools/codex-scripts/omni.py build` |
| 真业务件（2 条） | `~/.openclaw-autoclaw/skills/youtube-factory` · `…/youtube-watcher`（**不由本件代管，别改**） |
| 目录桩（1 条） | `<仓>/审美相关skill/skills/youtube-clipper`（`design-asset` 通道） |
| 能力位 | **无** —— `omni.py list --domain youtube` 报 **0 条**（别去 `five-dim.py cap` 找它） |
| 人话入口 | `python tools/codex-scripts/omni.py ask "帮我总结这个 YouTube 视频"` |
| 验收 | `py -3.14 tools/codex-scripts/verify-distill.py --cluster youtube` |

**深蒸登记（应加、本次未擅自动手）**：`omni.py` 的 `DISTILLED_CLUSTERS` 加一行

```python
    "youtube": "gbt-youtube",         # 3 条（2 真业务件 + 1 目录桩）：按意图分簇 + 发布闸
```

加完后 `verify-distill.py --cluster youtube` 才会从 **`FAIL: 没登记这个簇`** 变 PASS。
（本次**没改** `omni.py` —— 交付报告里给主人这一行，**没交付就会 FAIL，不会静默变绿**。）

---

## 11. 诚实边界（这段不许删）

1. **本件是"用法规程"，不是"能力已具备"。** 它把 3 条技能**分簇、点名、定了纪律**；
   **每条技能的深度用法以它自己的 `SKILL.md` 为准**，本件**不替代**。
2. **本次实跑的都是只读/失败探针**：`omni.py list` · 图鉴前缀清点 · `Get-Command` · `--version` ·
   `npm ls -g` · 环境变量**存在性**（不打印值）· `cap model_key_pool`（只读）·
   `get_transcript.py`（真跑，**在找 `yt-dlp` 那层就断，未出网、未下载**）·
   `vtd.js --help`（真跑，报 `ERR_MODULE_NOT_FOUND`）· `py_compile`。
   **没有产出过任何视频/音频/字幕文件，没有上传过任何东西，没有装过任何依赖，
   没有改过任何技能文件。**
3. **本机状态是现读快照**（`ffmpeg` 8.1.2 在 · `yt-dlp` 不在 · `edge-tts` 在但 `exit=1` ·
   `PEXELS_API_KEY` 未配 · 密钥池 `keys_total:0` · Node v24.15.0）。
   **换机器、补完依赖、或图鉴重建后，本件的读数都要重查。**
4. **凭据只报"已配/未配"**：本件**不出现任何凭据值**；
   `PEXELS_API_KEY` / `YOUTUBE_API_KEY` / `GOOGLE_API_KEY` 实测**全部 UNSET**。
5. **`gbt-youtube` 与 `gbt-video` / `gbt-video-tools` / `gbt-arkcli` 的边界**见 §0；
   **谁都不许拿对方的读数替自己说话。**
