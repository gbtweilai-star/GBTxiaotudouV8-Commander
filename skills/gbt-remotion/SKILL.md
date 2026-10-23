---
name: gbt-remotion
displayName: GBT · Remotion 技能簇用法规程（remotion-* · 12 条）
version: 1.0.0
description: GBT小土豆V8 使用 Remotion 技能簇的用法规程。管住 12 条 remotion-* 技能（入口路由 · 起项目 · 写页面与动画 · 地图动画 · 音视频素材 · 字幕 · Studio 预览 · 渲染导出 · 应用化/SaaS · 文档检索 · 升级）的分簇与选用、两道闸（闸一凭据与依赖闸：要 Node 工程 + remotion 包，本机现读零安装、无 @remotion/cli、无工程、Mapbox 与 ElevenLabs 密钥未配；闸二出片/上传/发布/装包闸：render / still / studio / create-video / npm i / remotion add / browser ensure / install-whisper-cpp / Lambda·Vercel·Cloudflare 部署 / upgrade 一律先问主人），外加上一道本簇原文没写但出片前必须过的许可闸（Remotion 是 source-available，机构 >3 人需 Company License）。并如实记下本机现状（12 条原文都在盘、不是目录桩；但无 Node 工程、无 remotion 包 ⇒ 装得上、查得到、跑不起来），以及本机踩过的坑（图鉴里 remotion-* 是 12 条，但按 name 前缀匹配会数出 13 条 —— 第 13 条是同名的审美素材桩；4 条顶层 SKILL.md 的跨技能链接被剥掉了，只有 best-practices 里的内嵌副本才有活链；ffmpeg 本簇不需要装）。当用户要用 React 做视频、出分镜/标题卡/字幕/透明视频、接 Remotion Studio 预览、渲染导出、把 Remotion 接成 SaaS 应用，或问 remotion-* 技能怎么用、为什么跑不起来、要不要密钥、这次要装什么包时使用。
triggers:
  - "Remotion"
  - "remotion-*"
  - "用 React 做视频"
  - "程序化视频"
  - "代码出视频"
  - "动效视频"
  - "motion graphics"
  - "Remotion Studio"
  - "渲染视频"
  - "透明视频"
  - "ProRes"
  - "字幕"
  - "captions"
  - "Mediabunny"
  - "create-video"
  - "Lambda 渲染"
  - "标题卡"
  - "分镜"
---

# GBT · Remotion 技能簇用法规程

> 开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属
>
> 这是**我们自己的用法规程**（不是 Remotion 官方文档的复述，也不是那 12 条技能原文的复述）。
> 那 12 条 `remotion-*` 讲的是"这一条技能宣称能干什么"，本文件讲
> "**在我们这儿，它现在到底能不能跑、要先把什么装上、谁在什么条件下、按什么顺序去用它，
> 以及什么东西绝对不许自动发出去、什么东西出片前必须先把许可搞清楚**"。
> 冲突时的裁决顺序：**本文件管我们的纪律** → 各 `remotion-*` 技能原文管它自己宣称的能力边界。两层都守。

---

## 0. 它是什么 / 在哪 / 🔴 最关键的一个事实

**这 12 条是「真技能」，不是「目录桩」—— 但它们现在在本机「跑不起来」。**

这是本件最重要的一句，先记住，别读反：**"原文在盘" ≠ "能跑"**。

| 项 | 值（2026-09-22 现读） |
|---|---|
| 条数 | **12 条**（`name` 以 `remotion-` 开头，含连字符） |
| 通道 | **`agent-skill`**（按名字加载执行），**不是 `design-asset`** |
| 版本 | 12 条**全是 `4.0.526`**，同一版 |
| 落点 | `C:\Users\ADMIN\Desktop\GBT小土豆V8\skills\remotion-*`（**本仓自有技能，真身就在盘上**） |
| 每条里有什么 | **有真内容**：`SKILL.md` + 各自的 `*.md` 参考件 + `agents/openai.yaml` + `assets/remotion-icon.svg` |
| 12 条顶层目录合计 | **271 个文件 / 2,261,574 字节**（其中 `SKILL.md` 只占 **32,126 字节**） |
| 有没有脚本 | **没有 `scripts/`**（`has_scripts: false`）—— 但它本来就不靠自带脚本，靠的是 `npx` 命令 |
| 上游 | 12 条原文**都没写上游仓库地址**（与 `fal-*` 那种"只指上游"的桩完全不同） |

**和 `fal-*` 那一簇的关键区别（别把两簇混着理解）**：

| | `fal-*`（12 条） | `remotion-*`（12 条） |
|---|---|---|
| 本体 | **目录桩**，每条只有 `SKILL.md`，1108–1231 字节 | **真内容**，12 条合计 2.2 MB |
| 通道 | `design-asset` | `agent-skill` |
| 缺的是 | 凭据 + 运行体 + **上游包** | **只缺运行体**（Node 工程 + `remotion` 包） |
| 图鉴 `desc` | 读出是 `"|"`（YAML 块标量解析残渣，**不可用**） | **是真实一行描述，可用**（12 条逐条现读确认） |

⚠️ **但"真内容"救不了"跑不起来"**：Remotion 的所有动作都发生在**一个 Node 工程里**，
而本机**没有装 `remotion` 包、没有任何 Remotion 工程**（§1 逐项现读）。
所以这 12 条现在的作用是**"教会你怎么用"**，而不是**"现在就能出片"**。

---

### 0.1 落点复核（现读，两处必须分清）

| 什么 | 在哪 | 现读 |
|---|---|---|
| 这 12 条（源 · 真身） | `<仓>/skills/remotion-*` | ✅ **在**（12 条，见上表） |
| managed 托管目录 | `C:\Users\ADMIN\.openclaw-autoclaw\skills\` | ❌ **顶层 0 条 `remotion`**（本件之前一条都没有；本件是这里的第一条 remotion 相关） |
| `~/.agents/skills` | 别家工具的共享目录 | ❌ **0 条 `remotion`**（该目录现读 **76 个子目录**；🔴 **本件绝不往这里写任何东西**） |
| 图鉴登记 | `<仓>/state/skill_atlas.json` | ✅ `name` 以 `remotion-` 开头 = **12 条** |

🔴 **"`~/.openclaw-autoclaw/skills` 顶层找不到 `remotion`" ≠ "没装"** ——
它们**根本不在托管目录里**，而在**工作区 `<仓>/skills/`** 下（§6 坑 1）。

---

### 0.2 🔴 与相邻件划边界（**谁管什么，先看这张表**）

本机有**四五个都在"做视频"的东西**，边界不清就会选错门。逐个写死：

| 相邻件 | 它管什么 | 与 `gbt-remotion` 的分界（一句话） |
|---|---|---|
| **`gbt-remotion`（本件）** | **`remotion-*` 这 12 条技能簇**：用 **React/TSX 写代码**造视频，要一个**本机 Node 工程**，产物是 MP4 / 透明视频 / still | **要"用代码写视频、要 Studio 交互编辑、要用 Remotion 那套 API" → 走这里。** |
| `gbt-video` | **本机 `video` 职业域的 4 个能力位**（`media_pipeline` / `libtv_skill` / `libtv_workflow` / `h3_video_gen`），且四位**当前全是只读契约面**，生成端**一条都没接线** | 那是**能力位**（走 `run_task` 唯一门），本件是**技能簇**（按名字加载）。**两个面不是一回事**：`gbt-video` 出不了片是"没接线"，本件跑不起来是"没装包"，**病因不同，别互相顶替**。 |
| `gbt-video-tools` | **`video-*` 技能簇 3 条**（`video-pipeline` / `video-transcript-downloader` / `video-downloader`）：**下载已有视频 + 转录 + 分镜流水线方法论** | 本件是**"造"视频**（从零写代码）；`video-*` 是**"拿/读"已有视频**（下载、转录）。**"下载这条 YouTube" 不该来本件。** |
| `gbt-arkcli` | **Ark 云端**（BytePlus ModelArk）：云端生图 / 生视频 / 对话 / 部署 Endpoint / 微调 / 查账单 | 本件是**本机 Node 出片**，Ark 是**云端按量计费**。🔴 **`remotion-saas` 里的 Lambda/Vercel/Cloudflare 是"自建云"，不是 Ark** —— 两套凭据、两套计费、互不通用，**别拿 Ark 的账单口径套 Remotion**。 |
| **`hyperframes` 技能簇**（9 条，**注意**） | **本机 HTML→视频 工具链**：入口技能**强制先读**，产物是 HyperFrames HTML composition | 🔴 **`gbt-hyperframes` 这个件在本仓不存在**（现读 `Test-Path` = `False`，`skills/` 下也没有 `gbt-hyperframes` 目录）—— 所以现在**不是"两个 gbt 件划界"，而是"一个上游技能簇 vs 本件"**，下表 §0.3 单列。 |

---

### 0.3 🔴 与 `hyperframes` 的交界（**两个都是"做视频"的工具链，最容易撞**）

**先报三个现读事实**：

1. `hyperframes` 这一簇（9 条：`hyperframes` / `-animation` / `-audio` / `-cli` / `-core` / `-creative` / `-keyframes` / `-registry` / `-studio`）在图鉴里的 **`root` 是 `C:\Users\ADMIN\.agents\skills`** ——
   也就是**别家工具的共享目录**。🔴 **本件不碰它、不往那里写。**
2. 它对应的工作区仓库是 **`_upstream\html-video`**（`html-video-monorepo`，自称 "HTML→Video meta-layer for coding agents"）。
   现读 **`node_modules` 不存在** ⇒ **未装**。
3. 那个仓库里**有一个 Remotion 适配器**：`_upstream\html-video\packages\adapter-remotion`（包名 `@html-video/adapter-remotion`，v0.1.0）。
   它自己 `package.json` 的 `description` 原文写着：**Phase 1 把已有 HTML/CSS/GSAP 帧桥到 Remotion 时间线上；Phase 2（另开 RFC）才加原生 React-tsx 模板**；
   它的 `peerDependencies` 是 `remotion ^4` / `@remotion/bundler ^4` / `@remotion/renderer ^4` / `react` / `react-dom`，且**全部标了 `optional: true`**。

**边界（写死，照这个选）**：

| 你要做什么 | 走哪条 | 为什么 |
|---|---|---|
| **"我这有个 HTML 页面，把它变成视频"** | **`hyperframes`** | 那是它的主场（HTML→Video 元层）；本件 12 条**没有一条**管"把现成 HTML 页面变视频"。 |
| **"用 React 从零写一个视频 / 要时间线交互编辑 / 要 Remotion 的 API"** | **本件 `gbt-remotion` 的 12 条** | 这才是 Remotion 那一套（`useCurrentFrame` / `interpolate` / Studio / render CLI）。 |
| **"走 hyperframes 的 Remotion 通道"** | ⚠️ **两边都不是现成能力** | 那是 `adapter-remotion`（**未装、未验**）。要用它得先 `pnpm install` + 装 Remotion peer 包 ⇒ **过闸二先问主人**，且**本件不为它背书**。 |

🔴 **一句话**：**HTML 变视频 → `hyperframes`；React 写视频 → 本件。**
两者唯一的交叉点是那个 **未安装**的 `adapter-remotion`，**别把它当"已经能串起来"**。

---

## 1. 🔴 本机现状如实读数（2026-09-22 现读快照）

**结论先说：这 12 条在本机「跑不起来」。缺的不是凭据，是运行体。**

**① 工具链（现读，全部 ✅）**

| 检查项 | 现读结果 | 怎么读的 |
|---|---|---|
| Node.js | ✅ **`v24.15.0`** | `node --version` |
| npm | ✅ **`11.12.1`** | `npm --version` |
| git | ✅ **`2.55.0.windows.3`** | `git --version` |
| ffmpeg（系统） | ✅ **`8.1.2-full_build-www.gyan.dev`** | `ffmpeg -version`（首行） |
| 浏览器 | ✅ Edge + Chrome **都在** | `Test-Path` 两个安装路径均 `True` |

⚠️ **但 ffmpeg 这个 ✅ 要读对**：**本簇根本不需要装系统 ffmpeg。**
`remotion-markup/ffmpeg.md` 原文写着：**"`ffmpeg` and `ffprobe` do not need to be installed. They are available via the `npx remotion ffmpeg` and `npx remotion ffprobe`"**。
⇒ 本机这个系统 ffmpeg 是**环境里本来就有**，**不是本簇的依赖项**，别拿它当"本簇依赖已满足"的证据。

**② 运行体（现读，全部 ❌ —— 这才是跑不起来的原因）**

| 检查项 | 现读结果 | 怎么读的 |
|---|---|---|
| `remotion` 包 | ❌ **未安装** | 全局 `npm root -g` 下 `Test-Path remotion` = **False**；`@remotion` = **False** |
| 全局 npm 包清单 | ❌ **25 个包里没有 remotion 相关** | `npm ls -g --depth=0`（有 `@byteplus/ark-cli` / `electron` / `n8n` / `pnpm`… 就是没有 remotion） |
| 任何工程里的 `node_modules/remotion` | ❌ **一个都没有** | `glob **/node_modules/remotion/package.json` → **No files found** |
| `@remotion/cli` 是否本地可用 | ❌ **否**（因为整个包都没有） | 同上；`remotion-upgrade` 原文第 2 步要先判这个，本机落在"不可用"分支 |
| 现成的 Remotion 工程 | ❌ **无** | 全仓（排除 `node_modules`）搜 `package.json` 里含 `remotion` 的只有 **5 处，全在 `_upstream\` 下的源码清单**（`_upstream\html-video` 4 处 + `_upstream\openhuman` 1 处），**都不是已安装的工程** |
| npx 缓存里有没有 remotion | ❌ **没有** | 枚举 `%LOCALAPPDATA%\npm-cache\_npx`（现读 **20 个缓存目录**），按名筛 `remotion` / `@remotion` / `create-video` → **空集** |
| `node_modules/.remotion/chrome-headless-shell` | ❌ **不存在**（因为没有任何工程渲染过） | 无 `node_modules` 可查 |

**③ 凭据（现读，只报"已配/未配"）**

| 检查项 | 现读结果 | 本簇哪一条需要它 |
|---|---|---|
| `MAPBOX_ACCESS_TOKEN` / `MAPBOX_TOKEN` | ❌ **均未配** | `remotion-maps` 的 **Mapbox** 技法（原文：`Requires a Mapbox key`） |
| `ELEVENLABS_API_KEY` / `ELEVEN_API_KEY` | ❌ **均未配** | `remotion-markup/voiceover.md`（原文：`ELEVENLABS_API_KEY` 环境变量） |
| 名字匹配 `MAPBOX` / `ELEVEN` / `REMOTION` 的环境变量 | ❌ **一个都没有**（空集） | —— |
| 其他（`OPENAI_API_KEY` / `GEMINI_API_KEY`） | ❌ 均未配（**本簇也不需要用**） | —— |

**🔴 本簇的凭据面很小，别有"整体缺凭据"的错觉**：

- **12 条里只有 2 条沾密钥**：`remotion-maps`（**且只有 Mapbox 技法要**，原文明确 **MapLibre "Requires no API key, fully free"**）与 `remotion-markup` 的语音旁白分支（ElevenLabs）。
- **其余 10 条一个密钥都不要** —— 它们要的是 **Node 工程 + 包**。
- **`remotion-docs` 是特例**：它自带一枚**上游公开的 Algolia 搜索 key**（**明文写在技能原文里**，不是主人的私钥），走 `POST https://plsduol1ca-dsn.algolia.net/...`。
  ⇒ 它**不需要主人配凭据**，但**需要出网**。这枚 key 是**上游发的公开检索 key**，**别当成我们的凭据去保管或转述**。

⚠️ **诚实边界（别把上面读成"配个 key 就能跑"）**：
**装上 `remotion` 包这件事，本件一次都没做**（那是"装包"，见闸二）。
所以上表里所有 ❌ 都是**"东西不在"**，**不是"权限被挡"** —— **别对着不存在的运行体反复撞，然后报成"被权限拦了"**（§5 红线 6）。

**④ 所以现在是什么状态**

**"原文在盘、`omni` 查得到、会话目录里列得出来，但一条都跑不了。"**
四个状态**不许混着报**：**有原文** / **查得到** / **装上了** / **能用** —— 本机是前两个 **是**、后两个 **否**。
**"能调" ≠ "能用"**：`omni list` 把它列出来，只证明**它被登记了**，不证明**它能出片**。

---

## 2. 两道闸（顺序不能颠倒）+ 一道许可闸

### 闸一 · 凭据与依赖闸（**先搞清"我凭什么是它"，再谈"我要做什么"**）

**闸一是双面的：既查凭据，也查运行体。本簇主要卡在运行体。**

**① 依赖面（本簇的主闸）**

| 需要什么 | 本机现读 | 判断 |
|---|---|---|
| **Node.js ≥ 20** | ✅ v24.15.0 | **过**（`_upstream/html-video` 的 `engines` 也只要 `node >=20`） |
| **一个 Remotion 工程**（`package.json` + `remotion` 依赖） | ❌ 无 | **卡住** |
| **`remotion` 包 / `@remotion/cli`** | ❌ 未装 | **卡住** |
| **Chrome Headless Shell**（渲染时自动下到 `node_modules/.remotion/`） | ❌ 无（且要先有 `node_modules`） | **卡住**（首次渲染会自动下载，见闸二） |
| **系统 ffmpeg** | ✅ 有，但**本簇不需要** | **不构成闸**（原文：`npx remotion ffmpeg` 自带） |
| git（`remotion-create` 原文要求确保 Node 与 Git 都在） | ✅ 2.55.0 | **过** |

**② 凭据面（只有 2 处）**：`MAPBOX_*` ❌ 未配 · `ELEVENLABS_API_KEY` ❌ 未配。
**只报状态，绝不报值**，硬纪律无例外：

```powershell
# ✅ 唯一允许的读法（只出"已配/未配"，不出值）
if ($env:ELEVENLABS_API_KEY) {'已配'} else {'未配'}

# ✅ 要看影子就只出前 4 位掩码（例：sk-a1****）
#    前提是真的到了必须给人看的地步；本机现在是「未配」，没有掩码可给
if ($env:ELEVENLABS_API_KEY) { $env:ELEVENLABS_API_KEY.Substring(0,4) + '****' } else {'未配'}
```

🔴 **绝对不许**：`echo` 任何 key 的值 · 把值写进任何 `.md` / 日报 / `MEMORY.md` / 聊天 ·
把值当参数明文传给命令行（会进 shell 历史与进程列表）· 把值写进 `.env` 后**提交进仓** ·
拿 `remotion-docs` 里那枚**上游公开 Algolia key** 当"我们的凭据"保管或转述。

**闸一未过 ⇒ 连闸二都不必谈**（没有可执行的调用）。本机现在就卡在闸一的**依赖面**。

🔴 **本件一个包都没装、一次渲染都没跑。** 上表所有 ❌ 是**现读事实**，不是"我试过了但失败了"。

---

### 闸二 · 出片 / 上传 / 发布 / 装包确认闸（**凡会留下东西或花掉东西的动作，一律先问主人**）

**本条高于技能原文，也高于任何 CLI 的默认行为。**

**为什么必须由我们拦**：Remotion 这一套的每个"真动作"都**要么装包、要么起长驻服务、要么出片、要么上传出去**。
技能原文里那些 `npx …` 命令**写得很顺手**，**默认就会执行**（`remotion-create` 甚至直接给出一串脚手架命令），
**但上游不会替我们心疼**：装包会改依赖树、渲染会下 ~150MB 浏览器、部署会把东西发到别人机器上。

**算"必须先进闸二"的动作（本簇**全部**命中，一条都不许自动跑）：**

| # | 动作 | 为什么 | 原文出处（现读） |
|---|---|---|---|
| 1 | `npx create-video@latest …` | **装包 + 出网** | `remotion-create` |
| 2 | `npm i` | **装包** | `remotion-create` |
| 3 | `npx remotion add @remotion/media`（及任何 `@remotion/*` / `mediabunny` / `zod` / `@huggingface/transformers`） | **装包** | `remotion-markup` |
| 4 | `npx remotion browser ensure`（或首次渲染时自动触发） | **下载 Chrome Headless Shell** 到 `node_modules/.remotion/chrome-headless-shell/win64`（体量不小） | `remotion-render` 官方页（见 §6 坑 6） |
| 5 | `npx remotion render` | **出片**（产出交付物） | `remotion-render` / `remotion-create` / `remotion-markup` |
| 6 | `npx remotion still [id] --scale=0.25 --frame=30` | **出图**（虽只一帧，也是产物 + 要浏览器） | `remotion-markup` |
| 7 | `npx remotion studio --no-open` | **起长驻进程 + 占端口**（本机 3080 已在跑 GUI，别抢） | `remotion-studio` / `remotion-create` / `remotion-markup` |
| 8 | `npx remotion add @remotion/install-whisper-cpp` + `installWhisperCpp()` / `downloadWhisperModel()` | **装包 + 下载 whisper.cpp 与模型**（字幕转录那条） | `remotion-captions/transcribe-captions.md` |
| 9 | 调 **ElevenLabs** TTS 生成旁白 | **出网 + 计费 + 把文案送出去** | `remotion-markup/voiceover.md` |
| 10 | 请求 **Mapbox / MapTiler** 底图 | **出网**（且可能计费/有配额） | `remotion-maps`（MapLibre **不需要**） |
| 11 | `renderMediaOnLambda` / `renderMediaOnVercel` / `renderMediaOnCloudrun` / `renderMediaOnWeb` 及对应 CLI | 🔴 **上传 + 发布 + 计费**（东西离开本机、且**按渲染数计费**） | `remotion-saas/rendering.md` |
| 12 | `npx remotion upgrade` / `npm view remotion version` 后改依赖 / `npx skills update remotion-…` | **改依赖树 + 装技能** | `remotion-upgrade` |
| 13 | 把素材 / 工程 / 产物**上传到任何外部**（S3、Vercel、Lambda、CDN…） | **把本地数据送出去**，比花钱更该先问一次 | `remotion-saas` |
| 14 | `_upstream/html-video` 的 `pnpm install`（想走 `adapter-remotion`） | **装包**（且那是另一个簇的地盘） | §0.3 |

**顺序（先看什么 → 拿什么回执）：**

1. **先过闸一**：报**依赖面**（有没有工程 / 有没有包）+ **凭据面**（`MAPBOX_*`、`ELEVENLABS_API_KEY` **已配/未配**）。
   缺依赖 ⇒ **到此为止**，只把"缺什么"报给主人（**本机现在就是这一步**）。
2. **先摊开代价，再谈执行**。动手前必须把下面**六件事**摆给主人看：
   - **要跑哪条技能 / 哪条命令**（**指名道姓**，别写"渲染一下"）；
   - **要装什么包、下什么二进制**（例：`remotion@4.0.526` + Chrome Headless Shell ~149.0.7790.0），**装到哪**（哪个工程的 `node_modules`）；
   - **输入**：用本地哪些素材（绝对路径），**会不会被上传出去**，多大、多少个；
   - **规模**：**几帧 / 几秒 / 几个 composition / 几条渲染**。
     🔴 **视频类必须把时长与分辨率单独拎出来写清**（"出 30 秒 1920×1080" 比"渲染一下"有用一百倍）；
   - **落点**：产物写到**哪个绝对路径**（**不许写进别的簇或生产面**）；
   - **预期花费**：本机**没有**任何 Remotion 定价技能（§4）；
     能查到就**报算法**，**查不到就写"查不到估价"**，**不许编一个数**。
3. **等一次明确同意**。**只覆盖这一批**，不是"以后这类都同意"。
   主人没回话 = **没同意**，停。主人说"先渲一帧看看" = **授权 1 帧**，不是"授权这个工程"。
4. **同意后才执行**，并且**只执行被授权的那一批**：授权 1 帧就别渲整片，授权 1 个 composition 就别批量渲。
5. **拿回执（缺一不可）**：
   - **命令原文** + **退出码**；
   - **实际装了什么**（包名 + 版本 + 落地的 `node_modules` 路径）；
   - **产物的绝对路径 + 字节数**（产交付物就得说清东西在哪、多大、**真的存在**）；
   - **渲染参数**：composition id / 帧数 / fps / 分辨率 / codec；
   - **实际计费口径**（若走了 ElevenLabs / Lambda / Mapbox，上游回了就原样转述，没回就写"上游未回传计费"）。
6. **长任务不盲重试**：`remotion studio` 是**长驻进程**，拿到 URL 就**记下来**；
   🔴 **不许对着它反复重启、反复抢端口**。**重试 = 可能重复装包 / 重复计费**。
7. **失败就照原样记**：退出码 + 原始报错（**一字不改**），**绝对不许把失败写成成功**（§5 红线 2）。

**🔴 本条硬条款（与 `gbt-lark` §3 同级的纪律）**：

> **凡会「出片 / 出图 / 上传 / 发布 / 装包 / 起长驻服务」的动作，动手前必须先问主人。**
> 这五类**没有例外**，**没有"反正是草稿"**，**没有"反正很小"**。

🔴 **绝对不允许**：没装包就"先 `npx` 试一下"（`npx` 会静默下载） · 主人没明确同意就 `render` ·
拿"只渲一帧/反正很快"当理由跳过确认 · 视频类不报时长分辨率就开跑 ·
把一次授权当长期授权 · 看到 studio 没起来就重发一遍 · 把 `_upstream` 里的东西当"已经装好"直接跑 ·
把失败包装成"已完成"。

**预判与降险（合法且鼓励）**：优先挑**最省的验证路径**——
先 `npx remotion still` **渲一帧** / 先用 `--scale=0.25` 缩图 / 先渲 **1 秒** 确认线路通不通，
再按确认过的档位放大。**"先渲一帧"也要先问主人**，只是**问的时候代价更小、更容易被同意**。

---

### 2.3 🔴 许可闸（**本簇 12 条原文一个字都没提，但出片前必须过**）

⚠️ **诚实标注**：这一节的依据**不是**那 12 条技能原文（**它们完全没写许可与定价**），
而是 **Remotion 官方 License FAQ 的现查原文**（2026-09-22 取，见 §6 坑 7 的出处）。
**本件把它单列出来，是因为它跟"能不能合法出片"直接相关，而不是因为它来自本簇。**

**要点（照官方 FAQ 现查，不是我们的推断）：**

| 项 | 官方口径原文要点 |
|---|---|
| 免费许可适用谁 | **个人**（个人或商用均可）· **≤3 人的组织/团队** · 非营利组织 · **正在评估**且尚未商用者 |
| 免费许可功能上有无限制 | **无**。"There is no difference in functionality between the Free License and Company License." |
| 超过 3 人怎么办 | 需 **Company License**。**Remotion for Creators$25/月/人**（自己写 Remotion 代码的人，**含用 agentic coding 工具写的人**）；**Remotion for Automators $0.01/render，最低消费 $100/月** |
| 什么算 automation | **拥有代码以编程方式调用**渲染 API 或命令 —— 官方列表**明确点名** `npx remotion render`、`npx remotion still`、`renderMedia()`、`renderStill()`、`renderMediaOnLambda()`、`renderMediaOnVercel()`、`renderMediaOnWeb()`、**`<Player>`** 等 |
| 1 render 怎么算 | **成功产出一个视频/音频/GIF/静帧/PDF = 1 render**。**Studio 与 Player 里的预览不算** |
| 是否开源 | 🔴 **不是**。原文："Remotion is source-available software, but it is **not** open source software according to the OSI definition" |
| 编解码器专利 | 许可**不覆盖** H.264/HEVC/AAC 等第三方专利 ⇒ 视用途与法域，**可能还需另外授权** |
| 远程遥测 | 客户端渲染**默认开启且不可关闭**；服务端渲染目前无自动遥测，**Remotion 5.0 起对 Automators 将强制** |

**⇒ 落在我们这儿的三条纪律：**

1. 🔴 **出片前先过一次许可闸**：本机是**什么主体、几个人**、这次是**"出成品给别人看"**还是**"搭自动化/SaaS"**。
   **拿不准就问主人**，**不许自己替主人认定"我们是个人所以免费"**。
2. 🔴 **`remotion-saas` 那条路要格外小心**：官方口径里 **`<Player>` 与渲染 API 都算 automation**，
   ⇒ **做 SaaS/自动化就直接落进按 render 计费的口径**。**这不是技术问题，是花钱问题**。
3. 🔴 **本件不是法务意见**：本件只转述官方 FAQ 的现查要点，
   **具体合规（尤其 >3 人、对外交付源码、编解码器专利）由主人判断**。

---

## 3. 按意图分簇（12 条，一条不漏）

**选路总则**：
**先读 `remotion-best-practices`（它是路由器，12 条的入口）** → 再看**你要的交付物是什么** →
最后落到具体技能。**拿不准就先说"拿不准"，别硬凑一条。**

### 3.0 入口路由 —— 1 条

| 技能 | 什么时候用它 |
|---|---|
| **`remotion-best-practices`** | 🔴 **永远先读这一条**。它是**官方路由器**：原文里把"创建视频 / 新工程 / 写 markup / 地图 / 多媒体 / 交互 / 渲染 / 开 Studio / 字幕 / SaaS / 查文档 / 升级"**全部指向对应的那条技能**。**别绕过它直接跳到某一条**——它开篇还写着一条**用户改动保护**纪律：**发现代码被别处改过，不要覆盖，当成有意为之或先问**。 |

### 3.1 起项目搭骨架 —— 1 条

| 技能 | 什么时候用它 |
|---|---|
| **`remotion-create`** | **要"从零开一个新视频工程/新 composition"** 时用它。原文给了完整脚手架决策树：**先探查当前目录（含隐藏文件）** →
  **空目录**（或只有 `.DS_Store` 这类可丢的系统元数据）→ 就地 `npx create-video@latest --yes --blank --no-tailwind .` + `npm i`；
  **非空目录** → **另起子目录**。
  🔴 **原文明确警告**：**别把所有隐藏文件都当垃圾** —— `.env`、`.git` 是**有意义的内容**。
  🔴 它还自己写了一条纪律：**"Only render if the user explicitly asks for it."**（**只在主人明确要求时才渲染**）—— **与本件闸二完全同向**。 |

### 3.2 写页面与动画（主干）—— 2 条

| 技能 | 什么时候用它 |
|---|---|
| **`remotion-markup`** | **主干技能**：写 Remotion React markup 的**内容 / 动画 / 特效**总规范（12 条里最厚的一条，63 个文件）。
  它管：**用 `useCurrentFrame()` + `interpolate()` 驱动动画**（🔴 原文明确：**CSS `transition`/`animation` 与 Tailwind 动画类不会正确渲染，必须改写**）· `Easing.bezier()/spring()` ·
  `<Video>`/`<Audio>`（`@remotion/media`）/`CanvasImage`/`AnimatedImage` · `staticFile()` · `from`/`durationInFrames`/`trimBefore` ·
  多场景 · 转场 · 特效 · 3D（Three.js / R3F）· 音效 · 音频可视化 · 字体（Google/本地）· Lottie · 参数化（Zod）· 测量 DOM/文字 · **FFmpeg 用法** · **静音检测** · 动态时长/尺寸。
  **只要是"往画面里写东西"，先看它。** |
| **`remotion-interactivity`** | **要让 Studio 能把你的代码"点着改"** 时用它。它讲的是**markup 怎么写才让 Studio 认得出来**：
  用 `<Interactive.Div>` 包元素 · **给元素起描述性 `name`（写死，别算）** · 🔴 **样式必须内联**（**不许引用常量、不许对象展开、不许算数**）·
  动画**必须是内联 `interpolate()` 调用**（**只认 `frame`，`fps`/`durationInFrames` 等可从 `useVideoConfig()` 解构**）·
  🔴 **用 `scale`/`translate`/`rotate`，别用 `transform`**（**只有前三个能被交互编辑**）·
  `defaultProps` 必须**内联字面量**（否则 Props 编辑器写不回代码）· `effects` 数组不许计算。
  **一句话：想让主人能在 Studio 里拖、不用改代码，就得照这条写。** |

### 3.3 专项画面：地图动画 —— 1 条

| 技能 | 什么时候用它 |
|---|---|
| **`remotion-maps`** | **画面里要有地图**（静态地图 · 航线/标记动画 · 地理讲解 · GeoJSON · 3D 地理飞行）时用它。
  🔴 **它的第一句就是纪律**："**Choose exactly one technique from the intended shot, then load only that technique's `TECHNIQUE.md`**" —— **按镜头选一种技法，只读那一个**（各技法目录**自包含**，删掉一个不影响其他）。
  5 种技法（现读目录名）：**`static-map`**（抓卫星图挂 `<Img>` 再在上面做动画）· **`mapbox`**（🔴 **要 Mapbox key**，样式更好、缩小时能显示圆地球、有埃菲尔铁塔这类 3D 建筑）·
  **`maplibre`**（🔴 **原文：不需要 API key，完全免费**，但没有 3D 建筑）· **`maptiler`**（用 MapTiler，**可在地理要素上画注记**：边界/河流/标签）· **`cesium`**（地形山脉飞越，"飞行模拟器"视角）。
  ⇒ **要免费就先看 `maplibre`；要好看又要 key 就看 `mapbox` —— 但 key 未配（§1）。** |

### 3.4 专项画面：素材与音视频元数据 —— 1 条

| 技能 | 什么时候用它 |
|---|---|
| **`remotion-multimedia`** | **要在浏览器里"读写"音视频（Mediabunny）** 时用它：**读音频时长** · **读视频宽高** · **读视频时长**。
  它是 12 条里**最薄的一条**（原文只有 20 行，指向 `mediabunny.dev/llms.txt` 概览 + 三个子文件）。
  🔴 **它的边界要读准**：`remotion-best-practices` 描述它是 **"achieving multimedia tasks in the browser, such as trimming, cropping videos, or getting metadata"** —— **浏览器侧**。
  **"把视频裁一刀"这种本地命令行活儿，本簇另有 `remotion-markup/ffmpeg.md` 管**，**别混。** |

### 3.5 字幕 —— 1 条

| 技能 | 什么时候用它 |
|---|---|
| **`remotion-captions`** | **要字幕/逐字稿**时用它。🔴 **原文第一条硬约束**：**所有字幕必须走 JSON**，且必须用 `@remotion/captions` 的 **`Caption` 类型**（`text` / `startMs` / `endMs` / `timestampMs` / `confidence` / `pageBreakAfter?`）。
  三个分支：**转写**（`transcribe-captions.md` → 🔴 要 `@remotion/install-whisper-cpp`，**会下载 whisper.cpp 与模型**，**闸二**）·
  **显示**（`display-captions.md`）· **从 `.srt` 导入**（`import-srt-captions.md`）。 |

### 3.6 Studio 预览 —— 1 条

| 技能 | 什么时候用它 |
|---|---|
| **`remotion-studio`** | **要看片/调片（预览）** 时用它：跑 **`npx remotion studio --no-open`** 拿 URL 再开浏览器。
  原文写明行为：**Studio 已经开着 ⇒ 只打印 URL 然后退出**；**没开 ⇒ 起长驻进程并打印 URL**。
  常用 flag（原文表）：**`--log=<error|warn|info|verbose>`** · **`--port=<number>`** · **`--force-new`**（同工程同端口再起一个实例）。
  🔴 **本机端口要小心**：DSH Web GUI 在 **3080** 上，**别默认抢这个端口**。🔴 **这是长驻服务 ⇒ 闸二。** |

### 3.7 渲染导出 —— 1 条

| 技能 | 什么时候用它 |
|---|---|
| **`remotion-render`** | **要出成品文件**时用它。原文给两条主命令：**`npx remotion render`**（出视频）与 **`npx remotion still`**（出静帧），完整选项指向官方 `render.md` / `still.md`。
  另有一条专章：**透明视频**（`transparent-videos.md`）—— 两条路：**ProRes**（原文示例命令：`npx remotion render --image-format=png --pixel-format=yuva444p10le --codec=prores --prores-profile=4444 MyComp out.mov`，适合**导入剪辑软件**）与 **WebM**（vp9）。
  🔴 **`remotion-create` 也重复了一遍同一条纪律：只在主人明确要求时才渲。** |

### 3.8 应用化 / SaaS（把 Remotion 接成产品）—— 1 条

| 技能 | 什么时候用它 |
|---|---|
| **`remotion-saas`** | **要把 Remotion 做成"应用"而不是"一条片子"** 时用它：给个表单接到渲染 · 或做一个**复杂视频编辑器**。
  原文分支：**挑模板/框架**（`framework.md`）· **`<Player>`**（把 Remotion 预览**嵌进 React 应用**，`player.md`）·
  **渲染形态二选一**（`rendering.md`：**客户端渲染 vs 服务端渲染**，并覆盖 **Lambda / Vercel / Node.js / Cloudflare** 四个选项）·
  以及与 **Vue / Angular / Svelte** 的配合（原文给的是 remotion.dev 的 `.md` 文档链接）。
  🔴 **这一条是闸二与许可闸的双重重灾区**：官方口径里 **`<Player>` 与渲染 API 都算 automation**（§2.3），**上传/发布/按 render 计费**全在这条路上。**别自己决定就部署。** |

### 3.9 文档检索 —— 1 条

| 技能 | 什么时候用它 |
|---|---|
| **`remotion-docs`** | **要查 Remotion 当前 API/文档**（**而不是靠记忆里的旧 API 写代码**）时用它。
  原文给的工作流四步：**① 用 Algolia 搜索 API 查**（`POST https://plsduol1ca-dsn.algolia.net/1/indexes/*/queries`，带**上游公开的** `x-algolia-api-key` 与 `x-algolia-application-id`，index 名 `remotion`）→ **② 从命中里挑 URL** →
  **③ 给任意 docs URL 加 `.md` 后缀抓 Markdown**（原文例：`https://www.remotion.dev/docs/use-video-config.md`）→ **④ 用当前文档实现，而不是用记住的 API**。
  🔴 **它要出网，但不需要主人配凭据**（key 是上游公开检索 key，§1 ③）。 |
  **注意**：`remotion-docs` 与 `remotion-best-practices` **都自称是"入口"** —— 分工是：**best-practices 管"我该走哪条技能"，docs 管"这个 API 现在长什么样"。** |

### 3.10 升级维护 —— 1 条

| 技能 | 什么时候用它 |
|---|---|
| **`remotion-upgrade`** | **要升 Remotion 或相关包**时用它。原文五步：**① 先看 manifest 与 lockfile 判包管理器/工作区**（并**保留无关改动**）→
  **② 判 `@remotion/cli` 本地是否可用**：**可用**就跑 `npx remotion upgrade`（**它同时会更新工程本地的 Remotion skills，跳过后续手动步骤**）；
  **③ 不可用**则手动：`npm view remotion version` 取最新稳定版 → **把所有 `remotion` 与 `@remotion/*` 升到同一个确切版本**（保留各自 dependency 段落与工作区约定）→
  用 `npm view @remotion/studio@<version> dependencies --json` **对齐辅助包**（`zod` / `mediabunny` / `@huggingface/transformers`，`@mediabunny/*` 用 `mediabunny` 的版本）→ 跑包管理器更新 lockfile；
  **④ 更新已装技能**：`npx skills update remotion-best-practices remotion-captions remotion-create remotion-docs remotion-interactivity remotion-maps remotion-markup remotion-multimedia remotion-render remotion-saas remotion-studio remotion-upgrade --yes`（**原文逐条列了这 12 个名字**）；
  **⑤ 审 diff**，确认所有 Remotion 包同一版本、辅助包是对齐版本，CLI 可用时再跑 `npx remotion versions` 复核。
  🔴 **本机落在"CLI 不可用"分支**（没有包）⇒ **每一步都要装包/查网 ⇒ 闸二**。
  ⚠️ 🔴 **这一步会重写那 12 条技能原文** —— **本件（`gbt-remotion`）不在那 12 个名字里，所以升级不会覆盖本规程**；但也**别让升级顺手把本件动掉**。 |

**分簇小结（11 簇 / 12 条，逐条已点名）**：
入口路由 1 · 起项目 1 · 写页面与动画 2 · 地图 1 · 素材与元数据 1 · 字幕 1 · Studio 预览 1 · 渲染导出 1 · 应用化 1 · 文档检索 1 · 升级 1 = **12**。

**选路示例**：
"用代码做一条 30 秒产品片" → **`remotion-best-practices` → `remotion-create` → `remotion-markup`**（要 Studio 里可拖 → 叠 `remotion-interactivity`）；
"片子里要有航线地图" → **`remotion-maps`**（先挑技法；想免费就 `maplibre`，要 key 就 `mapbox` —— **key 未配**）；
"给这条口播加字幕" → **`remotion-captions`**（转写要 `install-whisper-cpp` ⇒ **闸二**）；
"我要先在浏览器里看一眼" → **`remotion-studio`**（长驻 + 端口 ⇒ **闸二**）；
"导成 MP4 / 导个带透明通道的给我剪" → **`remotion-render`**（透明走 ProRes 或 WebM ⇒ **闸二**）；
"把这个模板做成我们自己的在线生成器" → **`remotion-saas`**（🔴 **`<Player>`/渲染 API 算 automation** ⇒ **许可闸 + 闸二**）；
"`interpolate` 现在什么签名？" → **`remotion-docs`**（出网，无需主人配 key）；
"把 Remotion 升到最新" → **`remotion-upgrade`**（改依赖树 + 装技能 ⇒ **闸二**）；
"把视频裁一刀 / 读一下这段音频多长" → **`remotion-markup`** 的 ffmpeg / 静音检测分支，或 **`remotion-multimedia`**（**浏览器侧**读元数据）。

---

## 4. 🔴 本簇**没有**覆盖的几件事（诚实边界，别硬凑）

本簇 12 条原文里，**没有一条**管下面这些。**主人问到这些时，不要拿 `remotion-*` 里的哪一条去硬凑答案** —— 如实说"本簇不管"。

| 主人可能会问 | 本簇管不管 | 该怎么说 / 该去哪 |
|---|---|---|
| **"这一下要花多少钱 / Remotion 怎么收费？"** | ❌ **12 条原文完全没写**（**没有定价类技能**） | 定价与许可在 **Remotion 官方 License FAQ**（§2.3 已现查转述）。本机**已有的**"查模型/查定价"能力是 **Ark 那条路**（`gbt-arkcli` 的 `arkcli-pricing`）—— **那是 BytePlus ModelArk，跟 Remotion 毫无关系，别互相顶替。** |
| **"Remotion 有哪些版本/该装哪个？"** | ❌ **不管**（原文只给命令，不给版本矩阵） | `npm view remotion version`（**出网，闸二**）。⚠️ 本机图鉴记的是 **4.0.526**，**那是图鉴读数，不是"本机装了什么"**（本机**什么都没装**）。 |
| **"我的工程怎么起不来了 / 报错怎么修？"** | ❌ **不管** | 12 条里**没有排错类技能**。`remotion-docs` 能帮**查文档**，**不等于能排错**。 |
| **"把这段现成视频下载下来 / 转录一下"** | ❌ **不是本簇的地盘** | 那是 **`gbt-video-tools`**（`video-downloader` / `video-transcript-downloader`）或 **`hyperframes`**（`hyperframes-cli` 的 transcribe）。**本件只管"用 React 造视频"。** |
| **"把 HTML 页面变成视频"** | ❌ **不是本簇的地盘** | 走 **`hyperframes`**（§0.3）。**本件 12 条没有一条管这个。** |
| **"用 Ark 云端生个视频"** | ❌ **不是本簇的地盘** | 走 **`gbt-arkcli`**。**别把 `remotion-saas` 的 Lambda/Vercel/Cloudflare 当成 Ark。** |
| **"本机 video 职业域那几个能力位怎么调？"** | ❌ **不是本件** | 走 **`gbt-video`**（且那 4 位**当前都没接线**）。 |

**这些格是本件的"防编造"锚点**：本簇的边界就到这里，**越界就是猜**。

---

## 5. 🔴 报告层红线（读数纪律）

1. **读数先问一句：这是事实，还是我读错了地方？**
   本簇最典型的"读错地方"有**五种**，**报数前先排除**：
   - 🔴 **`~/.openclaw-autoclaw/skills` 顶层找不到 `remotion`** ⇒ **不等于没装**。
     它们在**工作区 `<仓>/skills/`** 下（§0.1 已验）。
   - 🔴 **按 `name` 前缀数会数出 13 条，不是 12 条。** 图鉴里有一条**裸名 `remotion`**
     （`design-asset` 通道、**审美素材桩**、只有 1205 字节的 `SKILL.md`、`od.mode: video`、`why: "审美素材：形态技能（大部头，按类聚合）"`、`root: 审美相关skill\skills`）。
     **它是第 13 条，且不是本簇的技能。** ⇒ **本簇口径一律按 `remotion-`（带连字符）数 = 12。**
     （`verify-distill.py` 报 `skills_in_atlas: 13` 就是因为它同时匹配 `name == 簇名`，见 §6 坑 2。）
   - 🔴 **`remotion-best-practices` 目录里"内嵌"了一整套 11 条兄弟技能的副本**（§6 坑 3）。
     ⇒ 看到 `remotion-best-practices` 有 **137 个文件 / 1.13 MB** 别以为"这一条技能特别大"，
     也**别把内嵌副本当成"另外装了 11 条"**（**磁盘上有 12 条顶层技能，不是 23 条**）。
   - 🔴 **4 条顶层 `SKILL.md` 的跨技能链接被剥掉了**（§6 坑 4）。
     ⇒ 读顶层 `remotion-create` 时看到 `see Remotion Best Practices` **是死文本**，
     **别以为那里有链接**；**活链只在内嵌副本里**。
   - 🔴 **图鉴的 `desc` 本簇是可用的**（12 条都是真描述）—— **别拿 `fal-*` 那个 `"|"` 的经验套过来**，
     也**不要**因为本簇 `desc` 好用就拿它当"技能全文"（**全文以 `SKILL.md` 原文为准**）。
2. **有错也照原样记，不许把失败写成成功。** 退出码、`status`、`detail`、`error` 原文保留。
3. **不许把"装了/查得到"当"能跑"。** 本簇是**"原文在盘、查得到、但零安装、跑不起来"**。
   **四个状态不许混着报**（§1 ④）。
4. **不许编命令、编路径、编技能名、编单价、编版本。**
   本件出现的每一条命令要么**本机真跑过**（标 ✅），要么明确标 **（原文命令 · 本机未跑）**。
   **没跑过的不许说成跑过**；**`npx …` 这类命令本件一条都没执行**（§6 坑 8）。
5. **不许报"已配/未配"之外的凭据细节**：只许**已配 / 未配**或**前 4 位掩码**。
   🔴 **`remotion-docs` 里那枚 Algolia key 是上游公开检索 key**，**不是主人的凭据** ——
   **本件正文里没有抄它的值**，**也不许**把它当"我们的凭据"保管、转述或写进任何配置。
6. **零安装 / 无工程 ≠ 权限被挡。** 那是"东西不在"，不是"门不让你过"。
   **别对着不存在的运行体反复撞，然后报成"被权限拦了"。**
7. **`verify-distill.py --cluster remotion` 的 FAIL 要读对意思**（见 §6 坑 1）：
   它现在报 FAIL **只是因为登记还没做**，**不是因为规程写坏了**。
8. 🔴 **本件不改 `omni.py`、不改 `security/policy.py`、不动别的簇、不给自己发授权、不调用 `tentacle` 任何方法。**
   登记由主人做（§7）。

---

## 6. 本机踩过的坑 / 已验事实（照做，别自己解读）

1. ✅ **`--cluster remotion` 现在必然报 FAIL，且原因是"没登记"，不是"写错了"。**
   现读 `py -3.14 tools/codex-scripts/verify-distill.py --cluster remotion` 返回（退出码 **1**）：

   ```json
   {"clusters": [{"cluster": "remotion", "skill": null,
     "fail": ["omni.py 的 DISTILLED_CLUSTERS 里没登记这个簇"],
     "facts": {"skills_in_atlas": 13}}],
    "hard_failures": 1, "verdict": "FAIL"}
   ```

   **注意 `skill: null`** ⇒ 它连 `gbt-remotion` 该叫什么都不知道，**因为登记表里没有这一行**。
   `omni.py` 的 `DISTILLED_CLUSTERS` 现读**只有 8 项**：
   `arkcli` / `lark` / `fal` / `autoglm` / `figma` / `design` / `autoclaw` / `sandbox` —— **没有 `remotion`**。
   🔴 **登记由主人做。本件不改 `omni.py`。**
2. ✅ **`facts.skills_in_atlas: 13` 是匹配规则导致的，不是"真有 13 条 `remotion-*`"。**
   现读 `verify-distill.py` 第 133 行的判据是：
   `name == c or name.startswith(c + "-")` —— 簇名 `remotion` 会**同时匹配裸名 `remotion`**。
   ⇒ 图鉴里 `remotion-*` = **12 条**（12 条全 `agent-skill`、v4.0.526），
   **裸名 `remotion` = 1 条**（`design-asset` 桩，`<仓>/审美相关skill/skills/remotion/SKILL.md`，**1205 字节**）。
   **12 + 1 = 13。** 现读 `omni.py list --domain remotion` 也印证：
   **「能力位 0 条」+「agent 技能 13 条」**（12 条 `agent-skill` + 1 条 `design-asset`），退出码 **0**。
3. ✅ **`remotion-best-practices` 是一条"自带兄弟副本"的打包件，不是普通技能。**
   现读它的目录：除 `SKILL.md` + `agents/` + `assets/` 外，**还有 11 个与顶层技能同名的子目录**：
   `remotion-captions` / `-create` / `-docs` / `-interactivity` / `-maps` / `-markup` / `-multimedia` / `-render` / `-saas` / `-studio` / `-upgrade`，
   **每个子目录里有一份 `REFERENCE.md`**（顶层同名技能里**没有** `REFERENCE.md`）。
   它的 `SKILL.md` 里那些 `./remotion-create/REFERENCE.md` 之类的链接，**就是指向这些内嵌副本的**。
   ⇒ **磁盘上是 12 条技能，不是 23 条**；`best-practices` 之所以 **137 files / 1,133,214 字节**，
   是因为它**把另外 11 条也装了一份**。另外 `remotion-markup` 的内嵌副本里还嵌了一层 `remotion-maps/REFERENCE.md`。
4. ✅ 🔴 **顶层 4 条技能的跨技能链接被"剥"掉了 —— 这是本簇最隐蔽的一个坑。**
   逐字节比哈希：**7 条内嵌 `REFERENCE.md` 与顶层 `SKILL.md` 完全相同**
   （captions / maps / multimedia / render / saas / studio / upgrade），
   **4 条不同**（`remotion-create` / `-docs` / `-interactivity` / `-markup`）—— **且行数一模一样，只差链接**。
   逐行 diff 出来都是同一种改动：**顶层的 Markdown 链接被拍平成裸文字**。
   例（`remotion-create` 顶层 vs 内嵌）：

   | 行 | 顶层 `SKILL.md`（**死文本**） | 内嵌 `REFERENCE.md`（**活链**） |
   |---|---|---|
   | 8 | `see Remotion Best Practices` | `see [Remotion Best Practices](../SKILL.md)` |
   | 45 | `Follow Remotion React Markup Best Practices and …` | `Follow [Remotion React Markup Best Practices](../remotion-markup/REFERENCE.md) and …` |
   | 49 | `follow guidance at Multi-scene videos.` | `follow guidance at [Multi-scene videos](../remotion-markup/multi-scene-video.md).` |
   | 80 | `For more options, see Rendering.` | `For more options, see [Rendering](../remotion-render/REFERENCE.md).` |

   ⇒ 🔴 **只加载顶层技能时，跨技能跳转是断的**（`remotion-create`→best-practices/markup/interactivity/render、`remotion-markup`→interactivity/captions、`remotion-docs`→best-practices、`remotion-interactivity`→video-editing **全都指不过去**）；
   **要拿活链，只能走 `remotion-best-practices` 里的内嵌副本。**
   ⚠️ **本件没有改这些文件**（那 12 条不归本件管）——**只把这个事实记下来**，别当成"已经修好了"。
5. ✅ **12 条顶层技能里一个脚本都没有，也不需要脚本。**
   现读 `state/skill_atlas.json`：12 条**全部 `has_scripts: false`**、`has_references: false`、`has_assets: true`。
   它们的"执行力"来自 **`npx` 命令**，不是自带脚本 ⇒ **"技能里有脚本能直接跑"这条路在本机不存在。**
6. ⚠️ **（官方文档现查，非本机实跑）Chrome Headless Shell 是"自动装进 `node_modules`"的。**
   官方 Chrome Headless Shell 页现查原文：**"Remotion is automatically installing 'Chrome Headless Shell' into your `node_modules` in order to render videos."**
   落地路径：**`node_modules/.remotion/chrome-headless-shell/[platform]/…`**（Windows 为 `win64`）；
   并写 `VERSION` 文件跟踪版本；**版本不匹配就删掉旧的重新下载**；
   可用 **`npx remotion browser ensure`**（或 API `ensureBrowser()`）提前装；也可 `--chrome-mode="chrome-for-testing"` 换另一种。
   官方版本对照表：**Remotion ≥ 4.0.452 ⇒ Chrome 149.0.7790.0** ⇒ 本簇的 **4.0.526 落在这一档**。
   🔴 **本机从未触发过这个下载**（没有工程、没渲染）——**这是"官方说会这样"，不是"我们跑过"。**
7. ⚠️ **（官方文档现查，非本簇原文）许可闸的口径来源。**
   §2.3 的内容取自 **Remotion 官方 License FAQ** 与 **Chrome Headless Shell** 两个 `.md` 页面（2026-09-22 现查 HTTP 200）。
   🔴 **标记清楚**：**本簇 12 条原文对许可、定价、遥测、浏览器下载"一个字都没写"**
   （现读在这 12 条目录里搜 `license` / `paid` / `company` / `Headless Shell` / `browser download` **全部零命中**）。
   ⇒ **§2.3 与坑 6 不是"本簇技能说的"，是"官方文档说的"**；**引用时别挂错出处。**
8. ✅ **本件本次全程零安装、零渲染、零出网业务调用。**
   跑过的**只有只读/结构类命令**：`node --version` · `npm --version` · `git --version` · `ffmpeg -version` ·
   `npm ls -g --depth=0` · `npm root -g` + `Test-Path` · 环境变量**存在性**检查 · `Test-Path` 浏览器路径 ·
   全仓 `glob` 找 `node_modules/remotion` · 全仓搜含 `remotion` 的 `package.json` · `_npx` 缓存枚举 ·
   12 条目录清点与 **SHA256 哈希比对** · 图鉴 JSON 解析 · 技能原文阅读 ·
   `verify-distill.py --cluster remotion` · `omni.py list --domain remotion` · `omni.py` 源码 grep · `verify-distill.py` 源码 grep。
   🔴 **没有跑过任何 `npx` / `npm i` / `pnpm install` / `remotion render` / `remotion studio`**，
   **没有下载 Chrome Headless Shell**，**没有调 ElevenLabs / Mapbox / Algolia**，**没有装任何包**。
9. ✅ **`omni.py` 不认 `--help`**（与 `gbt-fal` 记录一致）：
   用法是 `omni.py [--domain DOMAIN] [--channel CHANNEL] [--yes] [cmd] [intent]`。
10. ✅ **`_upstream/html-video` 是"源码在盘、依赖未装"的状态。**
    现读：`node_modules` **不存在**；根 `package.json` 的 `dependencies` 里**已经有** `@remotion/bundler ^4` / `@remotion/renderer ^4` / `remotion ^4` / `react ^18` / `react-dom ^18`，
    但那只是**声明**，**没有一个被装下来**。⇒ **别把它读成"Remotion 已经装好了"。**

---

## 7. 固化位置（**重启后要在**）

| 什么 | 在哪 |
|---|---|
| 本规程（源 · 真身） | `<仓>/skills/gbt-remotion/SKILL.md` |
| 本规程（装机） | `C:\Users\ADMIN\.openclaw-autoclaw\skills\gbt-remotion\SKILL.md`（**与源稿逐字节相同**，用哈希证明） |
| 被规程管的 12 条能力 | `<仓>/skills/remotion-*`（**本仓自有技能 · 真身**，**不由本件代管，别改**） |
| 第 13 条（**不是本簇**） | `<仓>/审美相关skill/skills/remotion/SKILL.md`（`design-asset` 桩，**别拿它凑数**） |
| 相邻工具链（**别碰**） | `hyperframes` 簇在 `C:\Users\ADMIN\.agents\skills`；其仓库在 `<仓>/_upstream/html-video`（**未装**） |
| 能力名册（现读） | `py -3.14 tools/codex-scripts/omni.py list --domain remotion` · `<仓>/state/skill_atlas.json`（`name` 以 `remotion-` 开头 = 12） |
| 验收 | `py -3.14 tools/codex-scripts/verify-distill.py --cluster remotion` |
| 官方事实来源（本次现查） | Remotion **License FAQ** 与 **Chrome Headless Shell** 两个官方页（§6 坑 6 / 坑 7） |

🔴 **本件只加一份规程，不动门。**
`omni.py`（含 `DISTILLED_CLUSTERS` 登记）与 `security/policy.py` **不是本件该动的东西** ——
**登记由主人做**；本件**不给自己发授权、不调 `tentacle` 任何方法、不碰别的域/别的簇**。

**纪律**：本规程**不代替技能原文**，也**不代替官方文档**。
包没装 / 工程没有 / key 没配，就**如实报"跑不起来"**，**不许编读数**。

---

## 8. 诚实边界（这段不许删）

1. **本件是"用法规程"，不是"能力已具备"，也不是"Remotion 教程"。**
   它把 12 条技能**分簇、点名、定了两道闸 + 一道许可闸与纪律**；
   但**每条技能的深度用法以它自己的 `SKILL.md` 原文为准**，本件**不替代**。
2. **本机这 12 条现在是「原文在盘 + 工具链齐 + 零 Remotion 安装 + 无工程」的"跑不起来"状态。**
   本件**没有**、也**没能**验证任何一次真实的 Remotion 渲染 ——
   因为 **`remotion` 包未装、工程不存在、`@remotion/cli` 不可用**（§1 逐项现读）。
3. **本次实跑的都是只读/结构类命令**（清单见 §6 第 8 条）。
   **任何装包、任何渲染、任何出网业务请求，本次都没跑。**
4. **本机状态是 2026-09-22 的现读快照。**
   **装了 `remotion` 包 / 建了工程 / 配了 key 之后必须重新现读** ——
   尤其 §1 那三张表，**装包就会变**，别把这份读数当永久事实。
5. **凭据只报"已配/未配"**：本件**通篇没有出现任何凭据值**，
   本机 `MAPBOX_*` 与 `ELEVENLABS_API_KEY` **都未配**，**没有值可给，也永远不该给**。
   `remotion-docs` 里那枚 **Algolia key 是上游公开检索 key**，**本件正文也没有抄它的值**。
6. **§2.3 许可闸与 §6 坑 6 的浏览器下载，出处是 Remotion 官方文档，不是本簇 12 条原文。**
   **本簇原文对许可/定价/遥测/浏览器下载零覆盖**（§6 坑 7 已逐项现读确认）。
   **本件不构成法务意见。**
7. **本件没有修任何东西。** 顶层 4 条技能被剥掉的跨技能链接（§6 坑 4）、
   图鉴里那条同名 `design-asset` 桩（§6 坑 2）、`DISTILLED_CLUSTERS` 缺登记（§6 坑 1）
   —— **本件只如实记下，一律没动。**
