---
name: gbt-hyperframes
displayName: GBT · HyperFrames 技能簇用法规程（10 条 · 8+1+1）
version: 1.0.0
description: GBT小土豆V8 使用 HyperFrames（用 HTML 合成渲染视频/动画的工具链）这一技能簇的用法规程。先钉死口径：图鉴里 name 以 `hyperframes-` 开头是 8 条，另有一条裸名 `hyperframes`（总入口，不在前缀内）和一条同族 `media-use`（媒体 OS，名字不带 hyperframes），本规程实际点名 10 条 —— 工作区自己的工具也是两种口径（`omni.py list --domain hyperframes` 报 10 条、`verify-distill.py --cluster hyperframes` 按前缀报 9 条）。逐条点名并分簇（总入口/合成契约/动画/关键帧/音频/创意方向/素材·字幕/registry/CLI/Studio），钉死两道闸：① 凭据与依赖现读（node v24.15.0 达标、ffmpeg 8.1.2 在、puppeteer chrome-headless-shell 152 在、但 doctor 报 ok:false —— 可用内存仅 1.1GB、Docker 未运行；HeyGen/AWS/GCP/Figma 凭据一个都没配，所以云端三条路与 publish 全关）；② 会出片 / 会上传 / 会发布 / 会装包 / 会调云端渲染的动作必须先问主人，逐条点名 `render` `benchmark` `publish` `cloud render` `cloudrun` `lambda` `feedback --file-issue` `skills update` `add` `browser ensure` `tts/transcribe/remove-background` `catalog --on-device` `auth login/logout` `telemetry` 以及 doctor 里写着「installs on first use」的两个包。含真跑过的命令与原始返回、四处「读错了地方」陷阱（`info` 在非项目目录也会成功、`doctor` 永远 exit 0、CLI 管的落点是 `~/.claude/skills` 不是 `~/.agents/skills`、`catalog` 号称纯本地却会联网拉 manifest）、以及与 `gbt-video` / `gbt-video-tools` / `gbt-remotion`（本机未交付）/ `gbt-arkcli` / `gbt-gsap` 的边界。当用户要做视频/动画/动效/片头/字卡/幻灯片/字幕片、要从网址或 Figma 出片、要用 registry 的 381 个块、或问 HyperFrames 在本机到底能不能跑、缺什么、这次会不会花钱/上传时使用。
triggers:
  - "HyperFrames"
  - "hyperframes"
  - "hyperframes-*"
  - "HTML 合成视频"
  - "用 HTML 做视频"
  - "做视频"
  - "出片"
  - "动画"
  - "动效"
  - "motion graphic"
  - "片头"
  - "字卡"
  - "title card"
  - "幻灯片"
  - "slideshow"
  - "explainer"
  - "promo"
  - "storyboard"
  - "分镜"
  - "关键帧"
  - "keyframes"
  - "GSAP"
  - "Lottie"
  - "Three.js"
  - "Anime.js"
  - "TypeGPU"
  - "字幕"
  - "captions"
  - "配音"
  - "TTS"
  - "转录"
  - "transcribe"
  - "registry 块"
  - "Studio"
  - "render"
  - "publish"
  - "cloud render"
  - "lambda"
  - "cloudrun"
  - "HeyGen"
---

# GBT · HyperFrames 技能簇用法规程

> 开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属
>
> 这是**我们自己的用法规程**（不是 HyperFrames 官方文档的复述，也不是那 10 条技能原文的复述）。
> 那 10 条讲"这一条技能宣称能干什么"，本文件讲
> "**在我们这儿，它现在到底能不能跑、谁在什么条件下、按什么顺序去用它，
> 以及什么东西绝对不许自动发出去**"。
> 冲突时的裁决顺序：**本文件管我们的纪律** → 各技能 `SKILL.md` 原文管它自己宣称的能力边界。
> 两层都守。**原文说了"要你批准才能 render"，本文件就把它钉成闸二，不给任何"反正是草稿"的口子。**

---

## 0. 它是什么 / 在哪 / 🔴 口径先说清（8 还是 9 还是 10）

**HyperFrames 是"用 HTML 合成来渲染视频"的一条工具链。**
一个 composition 就是一个 HTML 文件：DOM 用 `data-*` 声明时间、动画运行时是可 seek 的、
媒体播放由框架接管。它是**我们做视频/动画/动效的默认输出框架**（除非主人明确点别的框架，
或只要录一段浏览器操作）。**它不是"生成视频的模型"** —— 它不生成画面，
它把你写的 HTML/CSS/JS 一帧一帧渲成 mp4。

### 🔴 三个数都是真的，看你按哪个口径数

任务给的名单口径是"**`hyperframes-` 前缀 = 8 条**"。**现读图鉴，这个数对得上**，
但同一张图鉴里还有一条**不带连字符的裸名 `hyperframes`**（总入口），
以及一条**同族但不带 hyperframes 字样的 `media-use`**（媒体 OS）。所以：

| 口径 | 怎么数的 | 条数 | 谁给的定义 |
|---|---|---|---|
| **A（任务口径 · 前缀）** | 图鉴 `state/skill_atlas.json` 里 `name` 以 **`hyperframes-`** 开头 | **8** | 本任务指令；现读已核对 |
| **B（工作区验收器口径）** | `verify-distill.py --cluster hyperframes`：**只数** `name` 以 `"hyperframes-"` 开头的（`-*` 成员）；裸名 `hyperframes` 另列为 `bare_name_sibling` **信息项、不计入覆盖** | **8** | `tools/codex-scripts/verify-distill.py` 现读**源码**（见 §6 坑 6；该文件本次会话中被并发改过） |
| **C（工作区路由口径 · 本件采用）** | `omni.py list --domain hyperframes`：技能里凡命中这个域的 | **10** | `tools/codex-scripts/omni.py` 现读（见 §6 坑 7） |

**本规程按 C 点名 —— 也就是 10 条一条不漏**，因为任务要求"该簇每条都不许漏"，
而**裸名 `hyperframes` 恰恰是这一族的唯一入口**（原文写着 "Mandatory entry point:
read this first for any request…"），漏掉它整族就没有门；
`media-use` 则是**唯一管素材/配音/字幕/调色的那条**，漏掉它"字幕"这个意图在本族没有落点。

**A、B、C 三个数的关系（报数时必须连口径一起说）：**

- **8 = 图鉴前缀口径 = 验收器口径**（两者一致：只数 `hyperframes-*`）；
- **10 = 整族口径 = 本件采用的口径**（8 条 `-*` + 裸名入口 `hyperframes` + `media-use`）；
- **"9" 是本次会话中途的一个过期读数**（验收器一度把裸名并进前缀一起数，现读它自己的源码注释
  说明那是**上一轮的错误改动、已改回**）。**本件把它记下来只当历史，不当口径。**

⇒ **报"8 条"要说明是"只数前缀"；报"10 条"要说明是"整族"。
只报一个数而不说口径，就是本件定义的读数错误。**

| 项 | 值（2026-09-22 现读） |
|---|---|
| 整族条数 | **10 条**（前缀 8 + 裸名入口 1 + `media-use` 1） |
| 通道 | **`agent-skill`**（10 条全是；不是 `design-asset`） |
| 落点（3 处，同名同哈希） | `~/.agents/skills` · `~/.claude/skills` · `~/.openclaw/skills` |
| 权威安装点（CLI 自己报） | `C:\Users\ADMIN\.claude\skills`（`agent: claude-code`）—— **不是** `~/.agents/skills` |
| CLI | **`hyperframes@0.8.60`**（npx 缓存里两份副本；**不在 PATH**） |
| 上游仓库 | `github.com/heygen-com/hyperframes`（registry manifest 现读就在这个仓库的 `main/registry/`） |
| registry 规模 | `total: 381`（**不是整齐的 400**，见 §6 坑 5） |

🔴 **本件绝不往 `~/.agents/skills` 写任何东西** —— 那是别家工具的共享目录（AGENTS.md 明令）。
本规程只落两处（§7），且两处逐字节相同。

---

## 1. 🔴 本机现状如实读数（2026-09-22 现读快照）

**结论先说：本地这条链「基本齐、能搜、能起」，但 `doctor` 自己判 `ok: false`，
而且云端/发布/装包那几条路全是关的。**
**"装得上、搜得到、核心齐" ≠ "能出片"** —— 这三个状态本件分开报，不许混。

### 1.1 工具链（`npx hyperframes doctor --json` 现读，逐项照抄）

| 检查项 | 现读结果 | 判定 |
|---|---|---|
| Version | `0.8.60 (latest)` | ✅ |
| Node.js | `v24.15.0 (win32 x64)`（要求 ≥ 22） | ✅ |
| CPU | `12 cores · AMD Ryzen 5 5600H with Radeon Graphics @ 3294MHz` | ✅ |
| **Memory** | **`7.4 GB total · 1.1 GB available`** + hint「Low memory — renders may fail.」 | ❌ **关键** |
| Disk | `55.2 GB free` | ✅ |
| Frames cache | `%TEMP%\hyperframes-extract-cache-u · 55.2 GB free` | ✅ |
| Archive extractor | `Built into Windows` | ✅ |
| Environment | `non-TTY` | ✅ |
| **whisper-cpp** | **`Not found (optional — needed for transcription)`** | ❌ |
| **TTS (Kokoro)** | **`Not installed (optional — local voice fallback)`** + hint `pip install kokoro-onnx soundfile` | ❌ |
| BGM (MusicGen) | `MusicGen deps installed` | ✅ |
| onnxruntime-node | `Not installed (installs on first use)` | ⚠️ **首次使用会装包** |
| @google/genai | `Not installed (installs on first use)` | ⚠️ **首次使用会装包** |
| FFmpeg | `ffmpeg 8.1.2-full_build-www.gyan.dev`（WinGet Gyan 包） | ✅ |
| FFprobe | `ffprobe 8.1.2-full_build-www.gyan.dev` | ✅ |
| Chrome | `~\.cache\puppeteer\chrome-headless-shell\win64-152.0.7977.75\…\chrome-headless-shell.exe` | ✅ |
| Docker | `Docker version 29.6.1, build 8900f1d` | ✅ |
| **Docker running** | **`Not running`** | ❌ **`render --docker` 现在走不通** |
| **整包判定** | **`"ok": false`** | 🔴 **不是"能跑"的状态** |

⚠️ **`doctor --json` 永远 exit 0**（原文 + 实测都是 0）。**必须读 payload 的 `.ok`** ——
本机 `.ok = false`。**谁拿 `$LASTEXITCODE` 判"环境没问题"，谁就报错了。**

### 1.2 CLI 在哪 / 怎么跑（现读）

| 项 | 值 |
|---|---|
| `Get-Command hyperframes` | **NOT FOUND**（不在 PATH） |
| 实际可跑的位置 | npx 缓存 `C:\Users\ADMIN\AppData\Local\npm-cache\_npx\110f701c48e68d66\node_modules\hyperframes`（另有同版本副本 `b3420a731f2dd931`） |
| 版本 | `0.8.60`；`engines: { node: ">=22" }`；bin = `./bin/hyperframes.mjs` |
| 本件用的跑法 | `node <缓存>\bin\hyperframes.mjs <子命令>` —— **直跑缓存里的 bin，不走 `npx` 解析、不触网、可复现** |
| 本机跑过没 | **跑过**：`~/.hyperframes/config.json` 现读 `commandCount: 4`、`renderSuccessCount: 1`、`recentRenders` 有 1 条 `ok: true`（2026-09-22T15:33:26Z） |

⚠️ **"不在 PATH" ≠ "没装"。** 技能是 CLI 自己装进来的，CLI 本体躺在 npx 缓存里。
但**别因此就说"随时能跑"**：`doctor.ok=false`（§1.1）才是能不能出片的判据。

### 1.3 技能装了几份、齐不齐（`npx hyperframes skills check --json` 现读）

```json
{
  "location": "C:\\Users\\ADMIN\\.claude\\skills",
  "agent": "claude-code",
  "scope": "global",
  "updateAvailable": false,
  "summary": { "current": 10, "outdated": 0, "missing": 11, "coreMissing": 0, "removed": 0 }
}
```

- **`current: 10`** = 上面那整族 10 条，`outdated: 0`、`coreMissing: 0`、`removed: 0`。
  ⇒ **核心 10 条是齐的、是最新的**（installedHash 与 latestHash 逐条相同）。
- **`missing: 11`** = **workflow 层一条都没装**（HyperFrames 的 workflow 是**懒装**的）：
  `embedded-captions` · `faceless-explainer` · `figma` · `general-video` · `motion-graphics` ·
  `music-to-video` · `pr-to-video` · `product-launch-video` · `remotion-to-hyperframes` ·
  `slideshow` · `talking-head-recut`。
- 🔴 **这 11 条在图鉴里一条都没有**（现读逐个查过，全 `False`）—— 所以它们**不在本簇名单内**，
  但它们是**总入口路由表的实际目标**（§3.1）。**这意味着一半的路由目标不在本机。**
- ⚠️ **CLI 报的落点是 `~/.claude/skills`（agent: claude-code），不是 `~/.agents/skills`。**
  而三处（`.agents` / `.claude` / `.openclaw`）**各有一份、SKILL.md 哈希完全相同**（§1.4）。
  ⇒ **"CLI 在管哪一份"与"技能文件在哪"是两件事**，报数不许混。

### 1.4 三处落点逐字节比对（SHA256 前 16 位，现读）

| 技能 | `.agents\skills` | `.claude\skills` | `.openclaw\skills` | 字节 |
|---|---|---|---|---|
| `hyperframes` | `49E0854D6142EDB8` | `49E0854D6142EDB8` | `49E0854D6142EDB8` | 16760 |
| `hyperframes-animation` | `653F1C48643B115D` | `653F1C48643B115D` | `653F1C48643B115D` | 7924 |
| `hyperframes-audio` | `02BA8082A3654B7F` | `02BA8082A3654B7F` | `02BA8082A3654B7F` | 25578 |
| `hyperframes-cli` | `97C97B1607150CC5` | `97C97B1607150CC5` | `97C97B1607150CC5` | 19253 |
| `hyperframes-core` | `2B2893D5916A7B97` | `2B2893D5916A7B97` | `2B2893D5916A7B97` | 12153 |
| `hyperframes-creative` | `488782FC741A43E0` | `488782FC741A43E0` | `488782FC741A43E0` | 6354 |
| `hyperframes-keyframes` | `BF1C44010E4F1BD2` | `BF1C44010E4F1BD2` | `BF1C44010E4F1BD2` | 15901 |
| `hyperframes-registry` | `0694F970B3613B9F` | `0694F970B3613B9F` | `0694F970B3613B9F` | 9643 |
| `hyperframes-studio` | `A3925932D2F38CBF` | `A3925932D2F38CBF` | `A3925932D2F38CBF` | 3661 |
| `media-use` | `AF377BB914D0EE9B` | `AF377BB914D0EE9B` | `AF377BB914D0EE9B` | 7976 |

**三处同哈希 ⇒ 是 3 份副本，不是 3 个版本。** 报"几份"时说清，别让人以为装了 3 套不同东西。

### 1.5 registry 可达性（`catalog --query` 现读）

```json
{ "query": "glitch", "tier": "words", "tier_detail": "local word match",
  "dropped": 0, "unindexed": 0, "shown": 3, "total": 381,
  "report_gap": "npx hyperframes feedback --search-miss \"glitch\" --wanted \"<the move you needed>\" --tier words" }
```

另有 4 条 item 在加载时被打警告跳过：
`liquid-glass-notification` · `liquid-glass-widgets` · `lt-neon-border` · `vfx-iphone-device`
（`Error: Invalid registry manifest`）。

⚠️ **`catalog` 号称"完全是本地的、什么都不发"，但现读它首次运行会联网拉 manifest 并落盘。**
本件跑之前 `~/.hyperframes` 里只有 `config.json` + `install-state.json`；
跑完 `~/.hyperframes/cache/` 下多了 **382 个文件**（159 blocks + 222 components + 1 manifest）。
**这是本件亲手造成的副作用，如实记账：只拉取、无安装、无发布、无计费。**

### 1.6 凭据闸现状（只报已配/未配）

| 凭据 | 现读 | 关掉了什么 |
|---|---|---|
| `HEYGEN_API_KEY` | **未配** | 云端渲染、publish、media-use 免费路径 |
| `HYPERFRAMES_API_KEY` | **未配** | 同上（备选顺序第二位） |
| `~/.heygen/credentials` | **不存在** | 同上（备选顺序第三位） |
| `FIGMA_TOKEN` | **未配** | `hyperframes figma asset/tokens/component` |
| `AWS_REGION` / `AWS_PROFILE` / `AWS_ACCESS_KEY_ID` | **全 absent** | `hyperframes lambda *` |
| `GOOGLE_APPLICATION_CREDENTIALS` | **未配** | `hyperframes cloudrun *` |
| `HEYGEN_API_URL` | absent | 只用默认 `https://api.heygen.com` |

`auth status` 实跑原样返回：

```
Not signed in to HeyGen (non-interactive).
Set HEYGEN_API_KEY to use HeyGen, or workflows fall back to local engines (Kokoro voice · MusicGen music).
```

（退出码 **1**。⚠️ **未登录时的 exit 1 是正常离线态，不是命令失败** —— `cloud.md` 原文写明，
脚本应写成 `auth status || echo offline`。别把它报成"报错了"。）

### 1.7 一句话现状

| 问 | 答（2026-09-22 现读） |
|---|---|
| 能不能调？ | **能调**（CLI 0.8.60 在缓存里，直跑成功过） |
| 能不能用？ | **本地链路基本齐但 `doctor.ok=false`**（可用内存 1.1GB、Docker 未运行）；**云端/发布全部关**（凭据一个都没有） |
| 能不能出片？ | **本件没验过出片**（§8）。按 `doctor` 的判据，**大分辨率渲染有失败风险**，`render --docker` 现在走不通 |
| 要不要 key？ | **本地渲染不要 key**；**凡走 HeyGen / AWS / GCP / Figma 都要**，现读**全未配** |
| 要不要 node/ffmpeg？ | **要**：node ≥ 22（本机 v24.15.0 ✅）、ffmpeg + ffprobe（本机 8.1.2 ✅）、puppeteer chrome-headless-shell（本机 152 ✅） |

---

## 2. 两道闸（顺序不能颠倒）

### 闸一 · 凭据与依赖闸

**只报状态，绝不报值。** 这是硬纪律，无例外。

```powershell
# ✅ 唯一允许的读法（只出"已配/未配"，不出值）
foreach ($v in 'HEYGEN_API_KEY','HYPERFRAMES_API_KEY','FIGMA_TOKEN') {
  if (Test-Path "env:$v") { "$v : PRESENT" } else { "$v : absent" }
}
# ✅ 要看影子只出前 4 位掩码（例：sk-a1b2****）；本机全未配，没有掩码可给
```

🔴 **绝对不许**：`echo $env:HEYGEN_API_KEY` · 把值写进任何 `.md` / 日报 / `MEMORY.md` / 聊天 ·
贴进本规程 · 当参数明文传给命令行（会进 shell 历史与进程列表） ·
写进 `~/.heygen/credentials` 之类文件（**那个文件由 `auth login` 自己管，权限 0600，别手造**）。

**依赖闸（现读）**：node ✅ · ffmpeg/ffprobe ✅ · chrome-headless-shell ✅ · docker ✅（**未运行**）·
`jq` ❌（不在 PATH —— `doctor --json | jq -e '.ok'` 这条官方写法在本机**跑不通**，
要用 PowerShell 解析 payload）· `aws`/`sam` ❌ · `gcloud` ❌ · `terraform` ❌ · `bun` ✅。

**闸一与闸二的先后**：本地动作闸一基本已过（能起）；**云端动作闸一未过 ⇒ 连闸二都不必谈**
（没有可执行的调用）。跟 `gbt-lark` 的"身份闸在前"是一个道理。

---

### 闸二 · 确认闸（**凡出片 / 上传 / 发布 / 装包 / 调云端，一律先问主人**）

**本条高于技能原文，也高于任何上游默认行为。**
HyperFrames 原文其实**自己就写了要批准**（`hyperframes-core` 的验收清单最后一行：
「`npx hyperframes render` only after the user approves」；`hyperframes-cli`：
「Never render merely because checks pass.」）—— **本文件把这条钉成我们的硬闸，并把它扩到下面全部动作。**

**算"必须先进闸二"的动作（逐条点名，都是本簇原文里真实存在的子命令）：**

**A. 会出片（产交付物 / 吃满机器）**

- `npx hyperframes render` —— 出 mp4/mov/png-sequence/webm。含
  `--quality draft|looks|delivery`、`--docker`、`--strict`、`--batch rows.json`。
  **原文：渲染永远需要 `review-loop.md` 定义的最终批准。**
- `npx hyperframes benchmark` —— **会真渲染 5 个预设 × 每个重复 N 次（默认 3）**，
  ⇒ **一次 benchmark ≈ 15 次渲染级开销**。不是"量一下而已"，**先问**。
- `npx hyperframes media-treatment`（apply/clear）—— 改本地素材并落盘。

**B. 会上传 / 会发布（东西出门，比花钱更该先问）**

- `npx hyperframes publish` —— **把项目源码（HTML + 素材）上传，返回托管 URL**。
  `--public` **让任何拿到 URL 的人都能看**；`--yes` **跳过确认提示**（原文：只跳提示、不改可见性）。
  🔴 **`--yes` 是给 CI 的，不是给我们的许可。本件一律：先问主人，再决定要不要 `--public`。**
- `npx hyperframes cloud render` —— **zip → 直传 S3 → 提交渲染 → 下载**（托管在 HeyGen，**按 credit 计费**）。
  **上传上限 200 MB**；`--dry-run --json` 可在**不登录、不上传、不花 credit** 的前提下先看归档体积
  —— **要探体积就用 `--dry-run`，别拿真跑当探测。**
- `npx hyperframes cloudrun sites create ./project` —— **上传内容寻址的项目归档**。
- `npx hyperframes cloudrun render` / `render-batch` —— 自管 GCP 渲染；`sites create` + `render-batch` 是**批量**，计费是乘法。
- `npx hyperframes lambda render` / `render-batch` —— 自管 AWS 渲染，同样**批量会翻倍花钱**。
- `npx hyperframes feedback` —— **发到一个公开频道**。原文要求提交前**脱敏**：
  去掉绝对路径、家目录前缀、用户名/机器标识、凭据；stack trace 只留 basename + 行号。
- `npx hyperframes feedback --file-issue` —— 🔴 **把最小复现包发布到一个公开 URL**。
  原文写明「This publishes the project publicly, so it is opt-in and **consent-gated**」
  ⇒ **没有主人明确同意，绝不加这个 flag。**
- `npx hyperframes capture <url>` —— 出网抓站点（并下载图片/SVG）；
  注意 `--skip-vision` 的存在说明**默认可能调 AI 视觉** ⇒ 出网 + 可能计费。

**C. 会装包 / 会下载**

- `npx hyperframes init <project>` —— **总会对着 GitHub 校验并刷新技能**
  （原文：`--skip-skills` **暂时失效**，想跳过要设 `HYPERFRAMES_SKIP_SKILLS=1`）
  ⇒ **scaffold 一个项目会顺带写技能目录。先问。**
- `npx hyperframes skills` / `skills update [名]` —— 写技能到 `~/.claude/skills`（装/刷新/清理）。
- `npx hyperframes add <name>`（含 `--human-friendly` 交互装）—— 装 registry 块。
  **原文：`add` 即使对昨天装过的条目也仍然需要网络**（只缓存 manifest，不缓存条目文件）⇒ **不许承诺离线装。**
- `npx hyperframes catalog --on-device` —— 一次性 **~33 MB** 模型下载（ONNX bge-small-en-v1.5 + 向量）。
  **原文：先说出体积，让人自己决定。绝不静默开启。**
- `npx hyperframes browser ensure` —— **下载 pinned Chrome**。
- `npx hyperframes tts` / `transcribe` / `remove-background` —— 产出素材（旁白音频、词级转录、透明视频），
  **原文：每个首次运行可能各自下载自己的模型。**
- `doctor` 里写着 **"installs on first use"** 的两个包：**`onnxruntime-node`** 与 **`@google/genai`**
  ⇒ **某些命令会顺手装包**。这是 `doctor --json` 现读出来的，不是猜的。
- `npx hyperframes upgrade` / init 时的 pin bump —— **换 CLI 版本**（原文：成功后要在总结里**点名旧版本与新版本**；
  `check` 失败要**回滚 `package.json` 并留在旧 pin**）。
- `npx hyperframes render` 里的 `--docker`（拉镜像）—— 归 A 与 C 双重。

**D. 会动凭据 / 身份 / 全局开关**

- `npx hyperframes auth login`（OAuth 开浏览器，**写 `~/.heygen/credentials` 权限 0600**）·
  `auth login --api-key`（headless，可 `echo "$HEYGEN_API_KEY" | … --api-key`）·
  **`auth logout`（清掉已存凭据）** · `auth refresh`（强制刷 token）。
  🔴 **`auth logout` 是破坏性动作**（把主人已配好的会话清掉），**先问。**
- `npx hyperframes figma asset|tokens|component` —— 要 `FIGMA_TOKEN`，走 REST 出网。
- `npx hyperframes lambda deploy|destroy` —— **建 / 拆 CloudFormation 栈**（Lambda + Step Functions + S3 + IAM）。
- `npx hyperframes cloudrun deploy|destroy` —— **建 / 拆 GCP 栈**（Terraform；`destroy` 会连 scratch bucket 一起删）。
- `npx hyperframes telemetry disable|enable` —— **改全局遥测开关**（现读 `telemetryEnabled: true`）。

**顺序（先看什么 → 拿什么回执）：**

1. **先过闸一**：报凭据 **已配 / 未配**、报 `doctor --json` 的 **`.ok`**。
   云端动作若凭据未配 ⇒ **到此为止**，只把"缺凭据"报给主人。
2. **先摊开代价，再谈执行**。动手前必须摆给主人看：
   - **动作**：具体哪条子命令（**指名道姓**，别写"渲染一下"）；
   - **落点**：本地出片 / 上传到哪 / 发到哪个公开频道 —— **说清是不是"出门"**；
   - **规模**：几条 / 几秒 / 几帧 / 几档 quality / 几路并发（`--max-concurrent` 默认 **50**）；
   - **上传体积**：走 cloud 的先用 `--dry-run --json` 报 `size_bytes` 与 200 MB 上限的关系；
   - **预期花费**：查得到就报算法，**查不到就说"查不到估价"，不许编一个数**。
3. **等一次明确同意**。**只覆盖这一批**，不是"以后这类都同意"。
   主人没回话 = **没同意**，停。主人说"先 draft 一版看" = **授权一次 draft**，不是"授权 delivery"。
4. **同意后才执行**，并且**只执行被授权的那一批**。
5. **拿回执（缺一不可）**：命令原文 · 退出码 · 产物绝对路径 + 字节数 ·
   云端任务 id（`asset_id` / `render_id` / `execution-name`）· 实际计费口径（没回传就写"上游未回传"）。
6. **长任务不盲重试**：拿到 id 就记下来再轮询。**重试 = 可能重复计费**。
7. **失败照原样记**：状态码 + 原始错误体一字不改，**绝不许把失败写成成功**。

🔴 **绝对不允许**：主人没同意就 render · 拿"反正是 draft / 反正很短"跳闸 ·
把 `publish --yes` 当成"跳过问主人" · 用 `feedback` 把绝对路径/家目录/用户名发到公开频道 ·
未同意就加 `--file-issue` · 静默开 `--on-device` 的 33 MB 下载 · 静默 `browser ensure` 下 Chrome ·
在云栈还活着时 `destroy` 而不先确认产物已取回 · 把一次授权当长期授权 · 看到超时就重发。

**预判与降险（合法且鼓励）**：优先挑最省的验证路径 —— 先 `--quality draft`、
先 `lint` 再 `check`、云上传先用 `--dry-run --json` 探体积、先 1 帧 snapshot 再整片。
**"先花小钱验线路"也要先问主人**，只是问的时候代价更小、更容易被同意。

---

## 3. 按意图分簇（10 条，一条不漏）

**选路总则**：先看**这一步要产出什么**（要方案 / 要能跑的 HTML / 要动效 / 要音 / 要素材 / 要装块 / 要命令 / 要能给人编辑的时间线），
再落到具体技能。**拿不准就按 §3.1 先过总入口，别硬凑一条。**

### 3.1 总入口 / 路由 —— 1 条

| 技能 | 什么时候用它 |
|---|---|
| **`hyperframes`** | **这一族唯一的大门，先读它**。任何"做视频/动画/动效/片头/说明片/带字幕的片段/字卡/叠层/幻灯片或可交互 deck / Remotion 移植 / 任意 HyperFrames HTML 合成"的请求，以及"检查·诊断·校验·预览·发布·批量渲染一个已有 HyperFrames 项目"，都从这里起。它还负责：**恢复项目状态**（先看 `BRIEF.md` / `hyperframes.json` / `STORYBOARD.md`，别一上来就问）、**捕获意图**（fresh creation 才跑 intent interview）、**选并安装 owning workflow**、**路由域能力**。它原文自称是**默认输出框架**（除非主人明确点别的框架，或只要录一段浏览器操作）。 |

🔴 **本机现实**：它的 §2 路由表指向 **11 条 workflow**（`/slideshow`、`/general-video`、`/embedded-captions`、
`/music-to-video`、`/motion-graphics`、`/pr-to-video`、`/product-launch-video`、`/talking-head-recut`、
`/faceless-explainer`、`/remotion-to-hyperframes`）—— **这 11 条现读全部 `missing`（§1.3）**。
原文给的安装口是 `npx hyperframes skills update <workflow-name>`（**属闸二 C 类，先问**）。
**原文还明确：命令失败就如实抛出，不许凭记忆重建 workflow。本件照办。**

### 3.2 合成契约（技术底座）—— 1 条

| 技能 | 什么时候用它 |
|---|---|
| **`hyperframes-core`** | **写 composition HTML 之前必读**。它管"一个可渲染项目长什么样"：两种根形态（standalone 不能包 `<template>` / 子合成必须包）、根必须用 `width/height:100%` 而不是硬编码 `1920px`、**每个合成只注册一个 `gsap.timeline({paused:true})`** 且键名 = 根 `data-composition-id`、渲染长度由根 `data-duration` 决定（**不是时间线长度**）、`data-*` 全量查表、`class="clip"`、轨道与 z-index、子合成与变量、媒体播放归框架、以及**确定性禁令**。还有一份"首建必踩"的 lint 清单（CSS transform 与 GSAP tween 打架、`<video>`/`<audio>` 带 `crossorigin`、`data-start` 嵌套、`<audio>` 缺 `id` 会静音、tween `.clip` 的 `autoAlpha`、具名字体缺 `@font-face`）。**改已有合成本事也在这**（先读文件、保住不相干的 timing/ID/变量）。 |

### 3.3 动画与运行时 —— 1 条

| 技能 | 什么时候用它 |
|---|---|
| **`hyperframes-animation`** | **全部运动知识**：原子运动规则（挑 2–4 条拼）、多阶段场景 blueprint、场景间过渡、更广的动效技法，以及**七个运行时适配器**（GSAP 默认，另有 Lottie / Three.js / Anime.js / CSS keyframes / WAAPI / TypeGPU）。选运行时也在这（GSAP 管 95%）。还含**编排审计**（`scripts/animation-map.mjs`：死区、stagger 一致性、生命周期告警）与 **24 个具名文字动画效果**。**要"动态/动起来/怎么动"就落这里。** |

### 3.4 关键帧（镜头与姿态契约）—— 1 条

| 技能 | 什么时候用它 |
|---|---|
| **`hyperframes-keyframes`** | **推近/推远（punch-in/out）、缩放、重新取景（reframe）、Ken Burns、镜头运动、match cut / whip pan 交接**，以及任何 seek-safe 的 2D/3D 关键帧；还有 GSAP / CSS keyframes / Anime.js / WAAPI / FLIP / 路径 / 遮罩 / SVG morph·draw / 文字拖尾 / 3D 景深，和 `hyperframes keyframes` 诊断。**它自带"创作者请求 → 真实机制"对照表**（含"任意 mid-source 冻结不支持、要预处理成独立片段"这种诚实边界）。⚠️ **边界**：关键帧**只管画面运动，不管剪辑装配** —— 切/裁/换序属 `hyperframes-core`，声音淡入淡出/交叉淡化属 `hyperframes-audio`。**它与 `hyperframes-animation` 的分工：animation 管"整场怎么演"，keyframes 管"某个主体怎么动"。** |

### 3.5 创意方向（非动画）—— 1 条

| 技能 | 什么时候用它 |
|---|---|
| **`hyperframes-creative`** | **设计规格（`frame.md` / `design.md` / `DESIGN.md`，优先级按此序）、配色、字体、旁白、节拍规划、音频反应式视觉、构图模式、品牌/风格决策**。它原文点出**最大失败源**：不做这两件事（先读 `house-style.md` 与 `video-composition.md`）就会产出"像网页的视频"。含 24 个 palette、frame-presets、visual-styles、design-picker、story-spine、narration、audio-reactive，以及 `scripts/contrast-report.mjs`、`scripts/extract-audio-data.py`。**它刻意不管动画**（动画回 3.3）。 |

### 3.6 音频（已放上时间线的混音）—— 1 条

| 技能 | 什么时候用它 |
|---|---|
| **`hyperframes-audio`** | **音频已经放进合成里了，现在要混**：淡入淡出、交叉淡化、轨道增益/音量、音量自动化、**闪避（ducking）**、音乐床压旁白（**voiceover carve**）、轨道上挂效果（EQ / 压缩 / 限幅 / 噪声门 / 饱和 / 延迟 / 混响 / 合唱 / 移相 / bitcrush）、在音量或任意效果参数上画自动化包络、以及**一条 submix 总线（`<hf-audio-group>`）带一串效果 + 一个推子 + 一个自动化时钟管多条轨**。⚠️ **边界写死在它原文里**：**找音源/生成音源（BGM、SFX、做旁白）不是它，是 `/media-use`；剪辑时序与轨道布局也不是它，是 `/hyperframes-core`。** |

### 3.7 素材 / 字幕 / 配音（媒体 OS）—— 1 条

| 技能 | 什么时候用它 |
|---|---|
| **`media-use`** | **这一族里唯一管素材的那条**，一个动词 `resolve`：BGM（HeyGen 目录 1 万+ 首）、SFX（内置 19 个 + 目录）、image（7.5 万+ 矢量）、icon、**logo**（svgl → simple-icons → GitHub avatar → favicon，**从不重画**）、**voice（TTS 旁白）**、grade（测量出来的校正候选）、lut（`.cube`）。目录里没有就走 `generate`（TTS / 音乐 / 图像模型）；**旁白、转录、字幕、去背景走同一个音频引擎**；还有对已有素材的操作（cut / reframe / transform）与跨项目复用。另外它管**宽泛的视觉反馈**（素材发暗/发闷/无聊/要复古·DV·印刷·ASCII/要隐私/要揭示）。 |

🔴 **"字幕"这个意图在本族的正确落点（本件必须点明，因为它最容易找错）**：
**本族 10 条里没有任何一条叫"字幕"。** 字幕能力是**分散在四处**的：

| 要做的事 | 落在哪 |
|---|---|
| 转录出词级时间、产出字幕数据 | **`media-use`**（音频引擎：transcription / captions） |
| 字幕**轨道怎么摆**、安全区在哪 | **`hyperframes-studio`**（一条字幕轨、`data-track-kind="captions"`、title-safe 80%） |
| 字幕的 lint 规则（`caption_*`） | **`hyperframes-core`** |
| "给已有口播素材加平字幕、不改素材" | **workflow `/embedded-captions`** —— ⚠️ **本机未装**（§1.3） |

⇒ **有人问"字幕怎么做"，不许指一条叫 captions 的技能（不存在），要按上表分流，并说明那条 workflow 未装。**

### 3.8 registry（381 个现成块/组件）—— 1 条

| 技能 | 什么时候用它 |
|---|---|
| **`hyperframes-registry`** | **在手工搭任何"具名视觉"之前**，先来这里搜：**CRT 扫描线、glitch、色差、胶片颗粒、shimmer 扫光、图表、代码/终端窗口、地图、彩纸爆开**……现读 registry `total: 381`，而**搜索在什么都不装、没有项目、没有账号时就能排全目录**。也管 `hyperframes add <name>`、`catalog` 的各种过滤、装完怎么接（block 走 `data-composition-src`；component 是片段，HTML/CSS/JS 分别粘）、安装落点（默认 `compositions/` 与 `compositions/components/`，可在 `hyperframes.json` 改）、以及**自己写新块并提上游 PR**（idea → scaffold → validate → PR）。 |

⚠️ **它原文反复强调的一条**：**查询一律用英文**，哪怕视频是中文/日文 —— 目录是英文索引的，
别的文字写进去**搜不到任何东西**（会报 `No searchable words in query`）。
**这条对我们是高频坑：中文项目最容易顺手用中文搜。**
装块属闸二 C 类（**要联网 + 写项目文件**，先问）。

### 3.9 CLI / 工程循环 —— 1 条

| 技能 | 什么时候用它 |
|---|---|
| **`hyperframes-cli`** | **命令层的唯一权威**：`init` `add` `catalog` `capture` `lint` `check` `snapshot` `compare` `grade-compare` `preview` `play` `present` `beats` `keyframes` `render`（单个/批量）`publish` `cloud` `cloudrun` `feedback` `lambda` `doctor` `browser` `info` `upgrade` `skills` `compositions` `timeline` `docs` `benchmark` `telemetry` `transcribe` `auth` `tts` `remove-background`。也管**构建/渲染失败的诊断**。它给出标准 dev loop（scaffold → 搜块 → 写 → `lint` → **`check`** → `preview --background` → 批准后 `render` → `ffprobe` 验片）。⚠️ `validate` / `inspect` / `layout` 是**废弃别名**，新指令里不许再出现。 |

**本件把它的两条硬规矩抄下来当纪律**：
① **`check` 是最终门**（它先跑 lint，再用一个浏览器会话做运行时/请求/布局/motion 断言/WCAG 对比度审计），
**不要在前面再单独跑一次 lint**；`--strict` 才让 warning 也卡退出码。
② 🔴 **lint 报 error 会顺手关掉布局与对比度审计** —— 那时 `check` 会报 `0 sample(s)` / `0/0 text checks`，
**读起来像干净文件，其实什么都没跑**。**先清 lint error，再信那两个数。**

### 3.10 Studio（给人编辑的时间线布局）—— 1 条

| 技能 | 什么时候用它 |
|---|---|
| **`hyperframes-studio`** | **这个项目要给人用 Studio 打开并编辑**时，管"时间线怎么摆才读得懂"：**每个场景都做成子合成**（根里只剩定时宿主 + 媒体 + 音频；嵌套标记不会自己变成一行，会闷成一行没法单独裁）、**字幕只占一条轨**、**一条轨只放一种元素**（`data-track-kind` = `video`（来自标签）/ `graphics` / `captions` / `audio`）、以及**安全区**（action-safe 90% / title-safe 80%，两框都是 Premiere 默认值，源码在 `previewSafeMargins.ts`）。⚠️ **它只管"摆"，不管"怎么改"** —— 单个剪辑动作（切/裁/改速/音量/复制/替换）在 `hyperframes-core` 的 `creator-editing-recipes.md`。 |

### 3.11 分簇小结（逐条已点名）

总入口 1 · 合成契约 1 · 动画 1 · 关键帧 1 · 创意方向 1 · 音频 1 · 素材/字幕 1 · registry 1 · CLI 1 · Studio 1 =
**10 条**。
（若按任务的前缀口径只数 `hyperframes-`：**8 条** = 上表去掉 `hyperframes` 与 `media-use`。）

**选路示例**：
"用 HTML 做个 30 秒产品说明片" → **`hyperframes`**（走 intent → 路由到 `/product-launch-video`，⚠️ 该 workflow 未装）
→ 写 HTML 时 **`hyperframes-core`** → 动效 **`hyperframes-animation`** → 颜色字体 **`hyperframes-creative`**；
"这个标题一个字一个字蹦出来" → **`hyperframes-registry`**（**先用英文搜**："reveal a headline one line at a time"）
→ 搜不到再 `hyperframes-animation` 手搭；
"给这张图推近一点" → **`hyperframes-keyframes`**；
"音乐太吵盖住旁白了" → **`hyperframes-audio`**（voiceover carve）；
"配个旁白 + 上字幕" → **`media-use`**（voice / transcription）+ **`hyperframes-studio`**（字幕轨）+ **`hyperframes-core`**（caption lint）；
"这段口播加平字幕" → workflow `/embedded-captions`（⚠️ **未装**）；
"给这个项目加 CRT 扫描线" → **`hyperframes-registry`**；
"这项目在 Studio 里打开一团乱" → **`hyperframes-studio`**；
"`check` 报了一堆" → **`hyperframes-cli`**；
"先看一眼能不能跑、缺什么" → **`hyperframes-cli`** 的 `doctor --json`（**读 `.ok`**）。

---

## 4. 🔴 边界：谁管什么（别互相冒充）

| 邻居 | 它管什么 | 与本件的分界（一句话） |
|---|---|---|
| **`gbt-video`** | **本机 `video` 职业域的 4 个能力位**（`media_pipeline` / `libtv_skill` / `libtv_workflow` / `h3_video_gen`），四位现读**全是只读契约面**，真出片端一条都没接线。 | **它管"本机原生 video 能力位"；本件管"HyperFrames 这条 HTML 合成工具链"。** 两边的"出片"完全不是一回事：**它那边没有接线，本件这边有真 CLI（且 `doctor.ok=false`）。** 不许拿一边的读数当另一边。 |
| **`gbt-video-tools`** | **`video-*` 技能簇 4 条**（`video-pipeline` / `video-transcript-downloader` / `video-downloader` / **`video-use`** —— 第 4 条是后来新增的，那份规程已补点），是"下载/转录/流水线/对话式剪片"那一簇。 | **本件不管 `video-*` 任何一条**；它也不管 `hyperframes-*`。**两边的转录不是同一条**（那边是 `youtube-transcript-plus` 类；本件这边是 `media-use` 音频引擎 + `hyperframes transcribe`）。 |
| **`gbt-remotion`** | ✅ **已交付**（2026-09-22 晚落稿：`skills/gbt-remotion/SKILL.md` 53984 B，源稿与装机件同哈希，已在 `DISTILLED_CLUSTERS` 登记 `remotion`）。它管 `remotion-*` **12 条**（React 造视频那条链）。 | **两边都是"用代码造视频"，但工具链不同**：本件走 **HTML 合成 + hyperframes CLI**；它走 **React + Remotion + npx**。**唯一交叉点**是总入口里那条 `/remotion-to-hyperframes` 路由（**那条 workflow 未装**）。⇒ 谁问 Remotion，落 `gbt-remotion`；谁问 HTML 合成，落本件。⚠️ **本行曾写"gbt-remotion 本机未交付、不许说它存在"——那是当时的现读，现在已过期**（那份规程是在本件成稿之后落地的）；**照本节读，别照旧稿**。 |
| **`gbt-arkcli`** | **Ark 云端**（BytePlus ModelArk）：生图/生视频/对话/理解/部署 Endpoint/微调/查账单用量。 | **完全不同的云。** HyperFrames 的云是 **HeyGen（托管）/ AWS Lambda / GCP Cloud Run**，凭据（`HEYGEN_API_KEY` vs Ark 的 profile）、计价（credit / 按调用 vs ModelArk 结算单价）、目录**都不通用**。**别互相顶替**（同 `gbt-fal` 那份的道理）。 |
| **`gbt-gsap`** | `gsap-*` 四条（`gsap-core` / `gsap-timeline` / `gsap-scrolltrigger` / `gsap-react`）的用法规程。 | **它自己就写明**："本机真正装着 GSAP 实现知识的是 live 目录里的 `hyperframes-animation`（4 份 GSAP adapter + `gsap-effects`）"。⇒ **两边是"上游点名桩"与"实现知识"的关系，不冲突、不重复**。要写 HyperFrames 里的 GSAP，落 `hyperframes-animation` 的 `adapters/gsap*.md`。 |
| **`gbt-omni`** | 人类视角操控入口（能力位/技能的一站式路由）。 | 本件是它的**下游规程**：omni 负责"人一句话落到哪个技能"，本件负责"落到 hyperframes 之后怎么用、过哪道闸"。**本件不给自己发授权、不调 `tentacle` 任何方法。** |
| **`gbt-aesthetic` / `gbt-design`** | 审美能力与设计流程（读数、转盘、三轴选型、AI 味禁令）。 | HyperFrames 的 `creative` / `animation` 是**"视频媒介内的"设计方向**；它们**不替代**通用设计流程。做视频时两边都要守：通用审美管"好不好看"，HyperFrames 原文管"视不视频"。 |

⚠️ **一句话总纲**：**本件管"HyperFrames 这 10 条技能在我们这儿怎么用、过哪道闸"；
不管"本机 video 能力位"（`gbt-video`）、不管 `video-*` 簇（`gbt-video-tools`）、
不管 Ark 云（`gbt-arkcli`）、不管 `gsap-*` 四条（`gbt-gsap`）。**

---

## 5. 🔴 报告层红线（读数纪律）

1. **读数先问一句：这是事实，还是我读错了地方？** 本簇有**四个**典型"读错地方"，报数前先排除：

   - **`hyperframes info` 在非 HyperFrames 目录也会成功**。本件在**仓库根**（工作区目录）跑
     `info --json`，得到 `name: "GBT小土豆V8"`、`resolution: "portrait"`、`1080x1920`、
     `duration: 0`、`elements: 0`、`tracks: 0`、`size: 6864353373`（≈ 6.86 GB），**退出码 0**。
     🔴 **这不是"这个仓库是 HyperFrames 项目"** —— 它只是把当前目录当项目根，
     没找到合成就报一个空壳，并把这整仓的体积当 `size`。**别拿这个当"本机有 hyperframes 项目"。**
   - **`doctor --json` 永远 exit 0**（原文 + 实测）。**必须读 payload `.ok`**（本机 `false`）。
   - **CLI 报的技能落点是 `~/.claude/skills`（agent: claude-code），不是 `~/.agents/skills`**，
     但技能文件在**三处都有同哈希副本**。⇒ **"CLI 在管哪一份"与"文件在哪"是两件事**，别混。
   - **`catalog --query` 号称"纯本地、什么都不发"，但首次运行会联网拉 manifest 并落盘**
     （本机实测：跑之前 `~/.hyperframes` 只有 2 个文件，跑完多出 382 个缓存文件）。
     ⇒ **"它号称本地" ≠ "它没触网"。** 报事实，别复述宣传语。
2. **有错也照原样记，不许把失败写成成功。** 状态码、`status`、`detail`、`error` 原文保留
   （本件连 registry 那 4 条 `Invalid registry manifest` 的警告都照抄了）。
3. **不许把"装了 / 查得到 / 能调"当"能跑 / 能用"。** 本机是
   **装了 · 查得到 · 能调 · 但 `doctor.ok=false` · 云端全关**（§1）—— **这些状态不许混着报。**
4. **不许编命令、编路径、编版本号、编条数、编价格。**
   本件出现的每一条命令要么**本机真跑过**（§6 列了清单），要么明确标 **（未验）**。
   **没跑过的不许说成跑过。**
5. **不许报"已配/未配"之外的凭据细节**：只许 **已配 / 未配** 或**前 4 位掩码**。
6. **凭据未配 / 云栈未部署 ≠ 权限被挡。** 那是"东西不在"，不是"门不让你过"。
7. **`auth status` 未登录时的 exit 1 不是故障**（`cloud.md` 原文），别报成"命令失败了"。
8. **`missing: 11` 是"懒装的设计"，不等于"坏了"。** 但也**不等于"能用"** ——
   总入口一半的路由目标不在本机，要说清楚。
9. **`verify-distill.py --cluster hyperframes` 现在必然 FAIL，且原因是"没登记"，不是"规程写坏了"**（见 §6 坑 6）。

---

## 6. 本机踩过的坑 / 已验事实（照做，别自己解读）

1. ✅ **CLI 不在 PATH，但确实在 npx 缓存里，能直跑。**
   `Get-Command hyperframes` → **NOT FOUND**；
   `node C:\Users\ADMIN\AppData\Local\npm-cache\_npx\110f701c48e68d66\node_modules\hyperframes\bin\hyperframes.mjs --version`
   → **`0.8.60`**，退出码 **0**。
   ⇒ 本件所有命令都是**直跑缓存里的 bin**（不经过 `npx` 解析、不触网、可复现）。
   **另有一份同版本副本在 `_npx\b3420a731f2dd931`。**
2. ✅ **`auth status` 未登录时 exit 1 = 正常离线态。** 实跑原文：
   `Not signed in to HeyGen (non-interactive).` + `Set HEYGEN_API_KEY to use HeyGen, or workflows fall back to local engines (Kokoro voice · MusicGen music).`
   ⇒ **别报成"命令失败"**；脚本写法应是 `auth status || echo offline`。
3. ✅ **`doctor --json` 实跑 `ok: false`**，两个红的在：**Memory `7.4 GB total · 1.1 GB available`**、
   **Docker running `Not running`**；另有 **whisper-cpp `Not found`**、**TTS (Kokoro) `Not installed`**。
   **`onnxruntime-node` 与 `@google/genai` 都写着 `Not installed (installs on first use)`**
   ⇒ **这是"某些命令会顺手装包"的证据**，不是猜的。
4. ✅ **`skills check --json` 实跑**：`location: C:\Users\ADMIN\.claude\skills`、`agent: claude-code`、
   `current: 10` / `outdated: 0` / **`missing: 11`** / `coreMissing: 0` / `removed: 0`，退出码 0。
   **`current` 那 10 条的名字与 §3 的分簇名单逐字相同**（这就是名单的机器验证）。
   `missing` 那 11 条：`embedded-captions, faceless-explainer, figma, general-video, motion-graphics,
   music-to-video, pr-to-video, product-launch-video, remotion-to-hyperframes, slideshow, talking-head-recut`。
5. ✅ **registry 实测 `total: 381`，不是"约 400"的整齐数**；`tier: "words"`、`dropped: 0`、
   `unindexed: 0`、`shown: 3`（查 `"glitch"`），退出码 **0**。
   另有 **4 条 item 加载时被跳过**（`liquid-glass-notification`、`liquid-glass-widgets`、
   `lt-neon-border`、`vfx-iphone-device`，`Error: Invalid registry manifest`）。
   ⇒ **"约 400 个块"是宣传口径；能排的是 381 个名字，其中 4 条 manifest 是坏的。**
6. ✅ **`verify-distill.py --cluster hyperframes` 现在必然 FAIL，且原因是"没登记"，不是"规程写坏了"。**
   **同一个命令本件跑了两次，两次返回不一样 —— 因为那个文件在本次会话中间被并发改过**
   （`verify-distill.py` 现读 `LastWriteTime = 2026/9/22 22:47:45`，且是**未入 git 的新文件**）。

   **第一次跑（22:45 左右，旧版判据）**：
   ```json
   {"clusters": [{"cluster": "hyperframes", "skill": null,
     "fail": ["omni.py 的 DISTILLED_CLUSTERS 里没登记这个簇"],
     "facts": {"skills_in_atlas": 9}}],
    "hard_failures": 1, "verdict": "FAIL"}
   ```
   **第二次跑（22:47 之后，新版判据）**：
   ```json
   {"clusters": [{"cluster": "hyperframes", "skill": null,
     "fail": ["omni.py 的 DISTILLED_CLUSTERS 里没登记这个簇"],
     "facts": {"bare_name_sibling": ["hyperframes"], "skills_in_atlas": 8}}],
    "hard_failures": 1, "verdict": "FAIL"}
   ```
   （两次退出码都是 **1**。）

   **🔴 这个差异本身就是本件要记的坑**：
   - 旧版把 `name == c` 的**裸名并进前缀一起数** ⇒ 9；
   - 新版改回**只数 `-*` 成员** ⇒ 8，并把裸名单列成 `bare_name_sibling`（**信息项，不计入覆盖**）。
   - 新版源码注释原文写着这是**"上一轮我曾把裸名并进来，那条改动是错的"**、**"裸名兄弟改为只报告不计入"**。
   ⇒ **同一个命令两次读数不同，不是本件读错了地方，是判据被改了。**
   **教训：本仓的验收器/omni 是活文件，读数必须带时点；不许把一次读数当永久事实。**
   **本规程按整族 10 条写（§0 口径 C），并把前缀 8 条逐条点到** ——
   这样**旧版（9）与新版（8）两种判据下，覆盖检查都不会漏**
   （裸名 `hyperframes` 与 `media-use` 也都被点名，见 §3）。

   **本件还自跑了一次新版判据的等价检查**（用与验收器相同的正则
   `(?<![\w\-])<name>(?![\w\-])` 扫本规程正文）：
   `prefix names: 8` · `bare_name_sibling: ['hyperframes']` ·
   **`skills_covered: 8/8` · `missing: (none)` · `media-use mentioned: True`**。
   ⇒ **只差 `DISTILLED_CLUSTERS` 那一行登记，规程内容侧的判据已经全过。**

   🔴 **登记由主人做。** 本件**不改 `omni.py`**（它现读有 **12** 个已登记簇：
   `arkcli` `lark` `fal` `autoglm` `figma` `design` `autoclaw` `sandbox` `pptx` `youtube` `video` `frontend`，
   **其中没有 `hyperframes`**）、**不改 `security/policy.py`**（真身在 `gbt_allinone/security/policy.py`，
   根下没有那个路径）、**不改 `verify-distill.py`**。
   ⚠️ 注意 `omni.py` 与 `verify-distill.py` **都是 `??`（未入 git）** ⇒ **`git diff` 判不了它们有没有被改**，
   别拿"git 没显示改动"当"没被动过"。
7. ✅ **`omni.py list --domain hyperframes` 实跑**：**能力位 0 条**；**agent 技能 10 条**，
   正好是 §3 的整族名单（含 `media-use`；另有 `gbt-gsap` 因描述里带 GSAP 字样被这个 `--domain` 筛出来，
   **跟本簇无关**，别数进去）。
   ⇒ **别去 `five-dim.py cap` 里找 `hyperframes` 域的能力位 —— 那里是 0。**
8. ✅ **`info --json` 在仓库根也会"成功"**（§5.1 第一条）：`name: "GBT小土豆V8"`、
   `resolution: "portrait"`、`1080x1920`、`duration: 0`、`elements: 0`、`tracks: 0`、
   `size: 6864353373`、`_meta.latestVersion: "0.8.60"`、`updateAvailable: false`，退出码 **0**。
   **仓库根既没有 `hyperframes.json`、也没有 `package.json`**（现读都 False）
   ⇒ 那个 `name` 是从目录名取的，**`size` 是整仓体积**。**这是伪读数，不许当成项目事实。**
9. ✅ **`~/.hyperframes/config.json` 现读**：`latestVersion: "0.8.60"`、`skillsOutdatedCount: 0`、
   `skillsMissingCount: 0`、**`telemetryEnabled: true`**、`commandCount: 4`、
   `renderSuccessCount: 1`、`recentRenders` 1 条 `ok: true`（2026-09-22T15:33:26Z）。
   ⇒ **本机至少成功出过一次片**（上一次会话的事），**但本件没有复现它**（§8）。
   ⚠️ 注意 `config.json` 的 `skillsMissingCount: 0` 与 `skills check` 的 `missing: 11` **不矛盾** ——
   前者指核心集，后者含未装的 workflow。**同一个词两个范围，读数时看清是哪个。**
10. ✅ **`jq` 不在 PATH**（`Get-Command jq` → NOT FOUND）。
    ⇒ `hyperframes-cli` 原文那句 `npx hyperframes doctor --json | jq -e '.ok'` **在本机直接跑不通**，
    要用 PowerShell 解析 payload。`timeline` 的 jq 一行流同理（原文自己也写了 node fallback）。
11. ✅ **`aws` / `sam` / `gcloud` / `terraform` 全不在 PATH**；`bun` ✅、`docker` ✅、`git` ✅。
    ⇒ **`lambda` 那条（要 AWS 凭据 + SAM + bun）和 `cloudrun` 那条（要 gcloud + terraform + Docker）
    在本机都缺前置**，与"凭据未配"是两层独立的缺失。
12. ⚠️ **（未验）真实出片 / lint / check / preview。** 本件**没有**创建项目、**没有**跑 `render`、
    `lint`、`check`、`preview`、`snapshot`。
    原因：`render` 产交付物且原文要求批准（闸二）；`init` 会写技能目录并联网校验（闸二 C 类）；
    `check`/`preview` 要起浏览器。**按本次纪律：凡过闸二的动作，一次都没跑。**
    **所以"本机具体能渲出什么画质/会不会因内存失败"本件一概不负责 —— 待验。**
13. ⚠️ **（未验）`cloud` / `lambda` / `cloudrun` / `publish` 任何一条。** 凭据全未配（§1.6），
    且这些动作过闸二。**本件一次都没跑、没上传、没发布、没花一分钱。**
14. ⚠️ **（未验）`--on-device` 离线语义检索档。** 原文说需一次性 ~33 MB 下载 +
    同意闸，**本件没下载**，所以本件跑出来的 `tier` 全是 `words`。
    ⇒ **"语义检索在本机好不好用"待验**；别拿 `words` 档的弱结果当"目录里没有"。
15. ⚠️ **（未验）上游仓库 `github.com/heygen-com/hyperframes` 的源码内容。**
    本件**没有 clone**；只通过 CLI 拉了 registry manifest（§1.5 的 382 个缓存文件）。
    ⇒ 上游实现细节、`packages/core/src/compiler/compositionAssembly.ts` 那些源码路径
    **只是技能原文里写的引用，本件没去核对过**。
16. ✅ **本件全程零真调用。** 跑过的只有**只读 / 结构类命令**：
    `--version` · `auth status` · `info --json` · `catalog --query "glitch" --json` ·
    `doctor --json` · `skills check --json` · `verify-distill.py --cluster hyperframes` ·
    `omni.py list --domain hyperframes` · 工具链 `Get-Command` 探测 · 环境变量存在性检查 ·
    路径存在性检查 · 三处落点哈希比对 · 缓存文件清点 · 技能原文与 references 阅读。
    **唯一写盘副作用**：`catalog --query` 拉下的 registry manifest 缓存（382 个文件，§1.5）——
    **无安装、无发布、无上传、无计费。**

---

## 7. 固化位置（**重启后要在**）

| 什么 | 在哪 |
|---|---|
| 本规程（源 · 真身） | `<仓>/skills/gbt-hyperframes/SKILL.md` |
| 本规程（装机） | `C:\Users\ADMIN\.openclaw-autoclaw\skills\gbt-hyperframes\SKILL.md`（**与源稿逐字节相同**，用哈希证明） |
| 被规程管的 10 条能力 | `~/.agents/skills` · `~/.claude/skills` · `~/.openclaw/skills` 三处的 `hyperframes*` 与 `media-use`（**不由本件代管，别改**；CLI 自报的落点是 `~/.claude/skills`） |
| CLI 本体 | npx 缓存 `_npx\110f701c48e68d66\node_modules\hyperframes`（`0.8.60`；**不在 PATH**） |
| registry 缓存 | `~/.hyperframes/cache/`（382 个文件：159 blocks + 222 components + 1 manifest） |
| 能力名册（现读） | `py -3.14 tools/codex-scripts/omni.py list --domain hyperframes` · `<仓>/state/skill_atlas.json` |
| 验收 | `py -3.14 tools/codex-scripts/verify-distill.py --cluster hyperframes`（现读 FAIL，原因：未登记） |

🔴 **本件只加一份规程，不动门。**
`omni.py`（含 `DISTILLED_CLUSTERS` 登记）与 `security/policy.py` **不是本件该动的东西** ——
**登记由主人做**；本件**不给自己发授权、不调 `tentacle` 任何方法、不碰别的簇、不改别的域**。
**本件也绝不往 `~/.agents/skills` 写任何东西。**

**纪律**：本规程**不代替技能原文**。原文说"要批准才 render"，本件就把批准钉成闸二；
原文说有 381 个块，本件就报 381（不报"约 400"）；原文说 `add` 离线装不了，本件就不承诺离线装。

---

## 8. 诚实边界（这段不许删）

1. **本件是"用法规程"，不是"能力已具备"。** 它把 10 条技能**分簇、点名、定了两道闸与纪律**；
   但**每条技能的深度用法以它自己的 `SKILL.md`（含各 `references/`）为准**，本件**不替代**。
2. **本机现在是"核心 10 条齐 · CLI 能调 · 但 `doctor.ok=false` · 云端与发布全关"的状态。**
   本件**没有**验证过任何一次真实出片、任何一次云渲染、任何一次上传或发布（§6 第 12–14 条逐项说明原因）。
3. **本次实跑的都是只读 / 结构类命令**（清单见 §6 第 16 条）。
   **任何业务写入、任何出片、任何出网发布、任何计费动作，本次都没跑。**
   唯一写盘是 registry manifest 缓存（**只读拉取，无安装**）。
4. **本机状态是 2026-09-22 的现读快照。** 换机器、配了 `HEYGEN_API_KEY`、起了 Docker、
   装了 11 条 workflow、或 CLI 升到新版本之后，**必须重新现读** ——
   尤其 §1 那几张表与 §1.7 的判定，**配了凭据就会变**，别把这份读数当永久事实。
5. **凭据只报"已配 / 未配"**：本件**通篇没有出现任何凭据值**，
   因为本机**一个都没配**，**没有值可给，也永远不该给**。
6. **`state/skill_atlas.json` 对本簇的 `desc` 被截断在 400 字符**（不是坏值，是截断），
   本件的每一条技能描述**都来自各技能 `SKILL.md` 原文**，不是来自图鉴的 `desc`。
7. **条数口径必须随报数一起说**：**图鉴前缀口径 8（= 验收器口径）· 整族口径 10**（§0）。
   本次会话中途验收器一度算出 **9**，那是它被并发改过的中间状态，**已不是现行口径**。
   只报一个数而不说口径，就是本件定义的读数错误。
8. **本仓的 `omni.py` / `verify-distill.py` 是活文件，且都未入 git。**
   本件在几十分钟内就亲眼看到 `verify-distill.py` 的判据变化导致同一条命令两次读数不同（§6 坑 6）。
   ⇒ **任何引用它们的读数都要带时点，不许当永久事实；也不许用 `git diff` 的空输出证明"没被动过"。**
