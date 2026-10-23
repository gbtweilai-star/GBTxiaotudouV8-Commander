---
name: gbt-design-mastery
displayName: GBT 设计全维度总规程（七条线 · 融会贯通）
version: 1.0.0
description: GBT小土豆V8 的「设计全维度」总规程 —— 把七条设计线（定档与审美 / 界面实现 / 设计稿与设计系统 / 动效与合成 / 演示与文档 / 出图与素材 / 视频与成片，共 88 个技能成员 + 工作区设计规则与素材）融成**一条决策流**：人一句话 → 判是哪条线 → 判档 → 选型 → 落点 → 过闸 → 出件 → 验收；并写死冲突裁决（三处同名规则文件以谁为准、桩 vs 实现、云 vs 本机、审美 vs 技能、能力位 vs 技能簇）与一份总诚实账。当用户说「做个设计 / 落地页 / 改版 / 设计系统 / 出图 / 海报 / 动效 / PPT / 剪片」，或问「这件事该走哪条线、该用哪个技能」时使用。
triggers:
  - "设计"
  - "落地页"
  - "改版"
  - "设计系统"
  - "出图"
  - "海报"
  - "动效"
  - "PPT"
  - "剪片"
  - "该走哪条线"
  - "全维度"
  - "融会贯通"
---

# 设计全维度总规程（七条线 · 融会贯通）

> 开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属
>
> **定位**：本件是**总入口**（判线 + 裁决 + 验收口径）。每条线的**深读**在 `references/L1…L7`；
> 每条技能簇/能力域的**用法规程**仍归各自的 `gbt-*`（`gbt-aesthetic` · `gbt-figma` · `gbt-frontend` ·
> `gbt-web` · `gbt-gsap` · `gbt-pptx` · `gbt-fal` · `gbt-venice` · `gbt-autoglm` · `gbt-glmv` ·
> `gbt-remotion` · `gbt-hyperframes` · `gbt-video` · `gbt-video-tools` · `gbt-chengfeng`）。
> **本件不重复它们的内容，本件负责"串起来、判该走谁"。**

**真源（别信二手描述，包括本文件）**：

```powershell
py -3.14 tools/codex-scripts/design-inventory.py           # 现算七条线成员 → state/design_dimension.json
py -3.14 tools/codex-scripts/design-inventory.py --check    # 判"总规程有没有点名全部成员与规则"
py -3.14 tools/codex-scripts/gbt-checkup.py                 # 深蒸交付三关（域/簇/结构）
```

---

## 0. 一句话决策流（**先看这一段，再往下**）

```
人一句话 → ① 判线（表 0.1）→ ② 判档（L1：先做设计读数 → 定三档转盘）
        → ③ 选型（L1：三轴，形态 × 品牌语言 × 普适手艺）
        → ④ 落点（该线里的具体技能/规程）→ ⑤ 过闸（§4 两道闸）
        → ⑥ 出件 → ⑦ 验收（L1 审计器 + 本线自检）
```

**表 0.1 · 判线（用户的"要什么"→ 走哪条线 → 第一件事）**

| 用户想要… | 线 | 第一件事 | 出口 |
|---|---|---|---|
| "好不好看 / 有没有 AI 味 / 帮我定个调" | **L1** 定档与审美 | 先做**设计读数**，不许先上色 | 档位 + 选型 + 禁令清单 |
| "做页面 / 组件 / 原型 / 改版" | **L2** 界面实现 | 先认**基线**（读现有代码/稿），再动手 | 可跑界面 |
| "设计稿 / 设计系统 / 令牌 / Figma 对接" | **L3** 设计稿与设计系统 | 先问**单一真源**在哪（稿 or 码） | 令牌/系统/双向对齐 |
| "动效 / 转场 / 滚动 / 视频合成" | **L4** 动效与合成 | 先判**三层**（GSAP 网页 / HTML 合成 / React） | 动效或合成件 |
| "PPT / 幻灯片 / 报告 / PDF 转稿" | **L5** 演示与文档 | 先定**结构与页数**，再谈样式 | 演示件 |
| "出图 / 海报 / 素材 / 修图 / 3D" | **L6** 出图与素材 | 先查**凭据与本机能不能真出图**（§4 闸一） | 图像/素材 |
| "剪片 / 字幕 / 配音 / 成片" | **L7** 视频与成片 | 先查**工具链就位没**（Runtime/服务/ffmpeg） | 成片 |

> 判线判不干净时，**按"出口"倒推**：要的是"好不好看"→ L1；要的是"能跑的界面"→ L2；
> 要的是"一份可交付的成品"→ L5/L6/L7。**一次只走一条主线**，跨线需求拆成多步（例：先 L1 定档 → 再 L2 实现）。

---

## 1. 全维度地图（**本段由工具现算，别手改**）

<!-- DESIGN-INDEX:BEGIN -->

> 本段由 `tools/codex-scripts/design-inventory.py --write-index` **现算生成** —— **别手改**；
> 改线/加成员请改脚本里的 `LINES` 或图鉴，然后重跑本命令。

### L1 定档与审美（1 个成员）

出口：三档转盘 + 三轴选型 + AI 味禁令与验收清单

| 成员 | 通道 | 什么时候用它 |
|---|---|---|
| `gbt-aesthetic` | agent-skill | GBT小土豆V8 的审美能力。做设计、美化界面、给别的项目打磨视觉时用。它把「好看」拆成可执行、可复核的四件事：先做设计读数、再定三档转盘、然后按三轴选型（形态×品牌语言×普适手艺）、最后过 AI 味 |

规则/素材：

- `DESIGN.md` ✅ 在
- `OUTPUT_RULES.md` ✅ 在
- `tools/codex-scripts/audit_aesthetic.py` ✅ 在
- `tools/codex-scripts/fixtures/aesthetic-sins.html` ✅ 在

### L2 界面实现（8 个成员）

出口：可跑界面：HTML/App 页面、组件、原型

| 成员 | 通道 | 什么时候用它 |
|---|---|---|
| `frontend-design` | agent-skill | Create distinctive, production-grade frontend interfaces with high design quality. Use this skill wh |
| `frontend-dev` | design-asset | Full-stack frontend with cinematic animations, AI-generated media via MiniMax API, and generative ar |
| `frontend-skill` | design-asset | Create visually strong landing pages, websites, and app UIs with restrained composition. OpenAI's pr |
| `frontend-slides` | agent-skill | Create stunning, animation-rich HTML presentations from scratch or by converting PowerPoint files. U |
| `web-artifacts-builder` | design-asset | Build complex claude.ai HTML artifacts with React and Tailwind. Anthropic's reference workflow for s |
| `web-design-guidelines` | design-asset | Web design guidelines and standards by the Vercel engineering team. Covers layout, typography, color |
| `web-perf` | agent-skill | Analyzes web performance using Chrome DevTools MCP. Measures Core Web Vitals (LCP, INP, CLS) and sup |
| `web-search-plus` | agent-skill | Unified search skill with Intelligent Auto-Routing. Uses multi-signal analysis to automatically sele |

规则/素材：

- `REDESIGN.md` ✅ 在
- `UI-check.md` ✅ 在
- `CODE_INGESTION.md` ✅ 在
- `design-assets-index/` ✅ 在

### L3 设计稿与设计系统（11 个成员）

出口：设计令牌/设计系统/设计稿 ↔ 代码双向

| 成员 | 通道 | 什么时候用它 |
|---|---|---|
| `design-brief` | agent-skill | Parse a structured design brief written in I-Lang protocol format into a concrete design spec. Elimi |
| `design-consultation` | design-asset | Build a complete design system from scratch with creative risks and realistic product mockups. Usefu |
| `design-md` | design-asset | Create and manage DESIGN.md files. Useful for capturing design direction, tokens, and visual rules i |
| `design-review` | design-asset | Designer Who Codes: visual audit then fixes with atomic commits and before/after screenshots. Useful |
| `figma-code-connect-components` | design-asset | Connect Figma design components to code components using Code Connect so design-system updates flow  |
| `figma-create-design-system-rules` | design-asset | Generate project-specific design system rules for Figma-to-code workflows. Useful for capturing toke |
| `figma-create-new-file` | design-asset | Create a new blank Figma Design or FigJam file. Useful as the first step in scripted design-system o |
| `figma-generate-design` | design-asset | Build or update screens in Figma from code or description using design system components. Translate  |
| `figma-generate-library` | design-asset | Build or update a professional-grade design system library in Figma from a codebase. Useful for keep |
| `figma-implement-design` | design-asset | Translate Figma designs into production-ready code with 1:1 visual fidelity. Useful for handing off  |
| `figma-use` | design-asset | Run Figma Plugin API scripts for canvas writes, inspections, variables, and design-system work. Prer |

规则/素材：

- `DESIGN.md` ✅ 在
- `PRD_INGESTION.md` ✅ 在
- `审美相关skill/design-systems/` ✅ 在

### L4 动效与合成（24 个成员）

出口：动效与视频合成（HTML 合成 / React / GSAP 三层）

| 成员 | 通道 | 什么时候用它 |
|---|---|---|
| `gsap-core` | design-asset | Core GSAP API with gsap.to(), from(), fromTo(), easing, duration, stagger, and defaults. Production- |
| `gsap-react` | design-asset | GSAP React integration with useGSAP hook, refs, gsap.context(), cleanup, and SSR. Ships safe motion  |
| `gsap-scrolltrigger` | design-asset | GSAP ScrollTrigger for scroll-linked animations, pinning, scrub, and refresh handling. Useful for ed |
| `gsap-timeline` | design-asset | GSAP Timelines with sequencing, position parameter, labels, nesting, and playback control. Useful fo |
| `hyperframes-animation` | agent-skill | All animation knowledge for HyperFrames — atomic motion rules, multi-phase scene blueprints, scene t |
| `hyperframes-audio` | agent-skill | Use when audio already placed in a HyperFrames composition needs to be mixed: fade-in/fade-out, cros |
| `hyperframes-cli` | agent-skill | Use the HyperFrames CLI development loop: init, add, catalog, capture, lint, check, snapshot, compar |
| `hyperframes-core` | agent-skill | The HyperFrames composition contract — build one renderable project. Use for composition structure,  |
| `hyperframes-creative` | agent-skill | Non-animation creative direction for HyperFrames videos. Use for design spec (frame.md / design.md)  |
| `hyperframes-keyframes` | agent-skill | Use when a HyperFrames composition needs a punch-in, punch-out, zoom, reframe, Ken Burns treatment,  |
| `hyperframes-registry` | agent-skill | Search, install, and wire registry blocks and components into HyperFrames compositions. Use BEFORE h |
| `hyperframes-studio` | agent-skill | Use when building or editing a HyperFrames project that people open in Studio: how the timeline shou |
| `remotion-best-practices` | agent-skill | Router for all Remotion skills |
| `remotion-captions` | agent-skill | Transcribing, displaying and animating captions |
| `remotion-create` | agent-skill | Create a new Remotion video |
| `remotion-docs` | agent-skill | Search Remotion documentation |
| `remotion-interactivity` | agent-skill | Structure Remotion markup for interactivity |
| `remotion-maps` | agent-skill | Remotion Map animation knowledge |
| `remotion-markup` | agent-skill | Content, animation and effects best practices |
| `remotion-multimedia` | agent-skill | Interacting with Mediabunny |
| `remotion-render` | agent-skill | Export a Remotion video |
| `remotion-saas` | agent-skill | Build an app with Remotion |
| `remotion-studio` | agent-skill | Preview a Remotion video |
| `remotion-upgrade` | agent-skill | Upgrade Remotion, and related packages |

规则/素材：

- （本线**没有**工作区规则/素材 —— 原因见下）

> 说明：工作区内**没有**本线可指的规则/素材（原挂的 `visual-asset-director.md` 现读是「素材视觉审查」面，只在评审里提到 motion 一词，**产权属 L6/L2**，已摘）。GSAP 真知识落在**装机目录**：`hyperframes-animation/adapters/gsap*.md`（`~/.agents/skills` 与 `~/.claude/skills` 各一份，约 33 KB，**工作区里没有这份**）⇒ 读 GSAP 要出工作区。

### L5 演示与文档（7 个成员）

出口：幻灯片 / 报告 / PDF→网页或幻灯片

| 成员 | 通道 | 什么时候用它 |
|---|---|---|
| `glmv-pdf-to-ppt` | agent-skill | Convert a PDF (research paper, report, or any document) into a polished multi-slide HTML presentatio |
| `glmv-pdf-to-web` | agent-skill | Convert a PDF (research paper, technical report, or project document) into a beautiful single-page a |
| `glmv-prd-to-app` | agent-skill | Build a complete, production-ready full-stack web application from PRD documents, prototype images,  |
| `pptx` | agent-skill | Read, generate, and adjust PowerPoint slides, layouts, and templates. Useful for executive decks, tr |
| `pptx-generator` | design-asset | Create and edit PowerPoint presentations from scratch with PptxGenJS — MiniMax's production-tested d |
| `pptx-html-fidelity-audit` | agent-skill | Audit a python-pptx export against its source HTML deck, identify layout/content drift (footer overf |
| `pptx-swarm` | agent-skill | Create new editable PowerPoint/PPT/PPTX slide decks using the PPTD swarm workflow. Use when the user |

规则/素材：

- `OUTPUT_RULES.md` ✅ 在

### L6 出图与素材（26 个成员）

出口：图像/素材产出（含 3D、抠图、超分、修图）

| 成员 | 通道 | 什么时候用它 |
|---|---|---|
| `autoglm-browser-agent` | agent-skill | Intelligent browser automation agent that can perform any task requiring a browser. Including but no |
| `autoglm-file-upload` | agent-skill | Use the AutoGLM Upload Mix API to upload local files such as images and documents, then obtain a fil |
| `autoglm-generate-image` | agent-skill | Use the AutoGLM text-to-image API to generate an image from a text prompt. Use this skill when the u |
| `autoglm-generate-image-seedream` | agent-skill | Use the AutoGLM Seedream text-to-image / image-to-image (image editing) API to generate images from  |
| `autoglm-image-recognition` | agent-skill | Use the AutoGLM Image Recognition API to analyze and describe image content. Use this skill when the |
| `autoglm-open-link` | agent-skill | Use the AutoGLM Open Link API to open a specific webpage and extract its main body text. Use this sk |
| `autoglm-remove-bg` | agent-skill | 去除图片的纯色/近纯色背景，输出透明底 PNG。当需要把 AI 生成的 logo / 图标 / 主视觉 从白底、卡片底或纯色底抠成透明，以便放到任意背景上时使用。用本地 Python（Pillow）  |
| `autoglm-search-image` | agent-skill | Use the AutoGLM image search API to search for related images based on a user query. Use this skill  |
| `autoglm-websearch` | agent-skill | Use the AutoGLM Web Search API to search the web. Use this skill when the user needs online search,  |
| `fal-3d` | design-asset | Generate 3D models from text or images via fal.ai. Useful for game assets, AR previews, product mock |
| `fal-generate` | design-asset | Generate images and videos using fal.ai AI models. Production-grade catalogue covering Flux, SDXL, i |
| `fal-image-edit` | design-asset | AI-powered image editing with style transfer, background removal, object removal, and inpainting via |
| `fal-kling-o3` | design-asset | Generate images and videos with Kling O3 — Kling's most powerful model family — via fal.ai. |
| `fal-lip-sync` | design-asset | Create talking head videos and lip sync audio to video via fal.ai. Useful for explainer avatars, mul |
| `fal-realtime` | design-asset | Real-time and streaming AI image generation via fal.ai. Suited for moodboard exploration, draft vari |
| `fal-restore` | design-asset | Restore and fix image quality — deblur, denoise, fix faces, and restore old documents using fal.ai's |
| `fal-train` | design-asset | Train custom AI models (LoRA) on fal.ai for personalized image generation tailored to a brand, chara |
| `fal-tryon` | design-asset | Virtual try-on — see how clothes look on a person via fal.ai's hosted try-on models. Useful for ecom |
| `fal-upscale` | design-asset | Upscale and enhance image and video resolution using AI super-resolution models hosted on fal.ai. |
| `fal-video-edit` | design-asset | Edit existing videos using AI — remix style, upscale, remove background, and add audio via fal.ai's  |
| `fal-vision` | design-asset | Analyze images — segment objects, detect, run OCR, describe, and answer visual questions via fal.ai  |
| `venice-audio-music` | design-asset | Music generation queueing, retrieval, and completion endpoints via Venice.ai. Suited for jingles, ba |
| `venice-audio-speech` | design-asset | Text-to-speech models, voices, formats, and streaming via Venice.ai. Useful for narration, voiceover |
| `venice-image-edit` | design-asset | Image edits, upscaling, and background removal via the Venice.ai API. |
| `venice-image-generate` | design-asset | Image generation endpoints and available styles via the Venice.ai API. |
| `venice-video` | design-asset | Video generation and transcription workflows via the Venice.ai API. |

规则/素材：

- `visual-asset-director.md` ✅ 在
- `design-assets-index/` ✅ 在

### L7 视频与成片（11 个成员）

出口：成片：剪辑/字幕/配音/导出（含能力域 video 4 位）

| 成员 | 通道 | 什么时候用它 |
|---|---|---|
| `chengfeng-check-updates` | agent-skill | 剪辑环境的唯一管理者：就绪检查（skills 是否最新 → Runtime 是否配套）、Skills 更新激活、Runtime 安装与体检。用户说检查更新、安装剪辑环境、装播放器、检查剪辑环境、剪辑环 |
| `chengfeng-cut` | agent-skill | 剪辑中文口播原素材：逐词转录、词典修字出修字表、五轮扫描找口误与重复、汇总表与重复句子表、打开 Studio 让用户复核、复盘沉淀用户偏好与词典。只产出一份已复核的删词账本，不切媒体、不做字幕、不做分 |
| `chengfeng-export` | agent-skill | 把剪好的口播烧成一个成片文件：账本切片段、推近、字幕、HTML 画面层，一次全部烧进 mp4。用户说导出、出成片、烧字幕、渲染、导出视频、生成最终文件时使用。不要用于生成删词候选、写字幕、做画面动画。 |
| `chengfeng-report-bug` | agent-skill | 整理、脱敏并上报 chengfeng-videocut 的 GitHub Bug。用户说上报 Bug、反馈剪口播问题、提交 GitHub Issue、这个问题告诉开发者，或要求继续提交已预览的 Bug |
| `chengfeng-subtitle` | agent-skill | 给剪好的口播做字幕：直接用已有的逐词稿加账本算出剪后时间（不必导出、不必重新转录）、用词典和作者文稿改写听错的专名、按句子分屏、在 Studio 里逐屏复核。用户说做字幕、加字幕、改字幕、重新分屏、字 |
| `chengfeng-videocut-workbench` | agent-skill | 操作 chengfeng-videocut 剪辑工作台的已有工程，通过 Runtime CLI 查工程与词句位置、添加或替换画面覆盖层、移除画面、删除明确指定的词句或片段、拆分裁剪移动已有片段、调整画 |
| `chengfeng-visual` | agent-skill | 给剪好的口播配画面：在录屏上盖 HTML 层（圈重点标注 / 小黑整屏动画 / 推近），层绑字幕屏、由播放器逐帧驱动、直接在预览里看。用户说做分镜、配画面、加动画、圈重点、B-roll、做 story |
| `video-downloader` | design-asset | Download videos from YouTube and other platforms for offline viewing, editing, or archival with supp |
| `video-pipeline` | agent-skill | 短视频/长视频从分镜到成片的生产契约：分镜表结构、镜头三契约（视线/景深/渲染路由）、转场与剪辑边界校验、成本前置闸、双人审闸。蒸馏自 ttalkkaklab/social-flow（Apache-2 |
| `video-transcript-downloader` | agent-skill | Download videos, audio, subtitles, and clean paragraph-style transcripts from YouTube and any other  |
| `video-use` | agent-skill | Edit any video by conversation. Transcribe, cut, color grade, generate overlay animations, burn subt |

规则/素材：

- （本线**没有**工作区规则/素材 —— 原因见下）

> 说明：工作区内**没有**本线专属规则文件（原挂的两件现读都不是规则：`IMAGE_GENERATION.md`是**生图面 L6** 的规程、全文只在第 38 行提到 video 一次；`render/` 是数字人项目的**PNG 产物**目录 260 文件 / 57 MB，成片落点是 `video-out/`）—— **产物与落点都不是规则**。L7 的口径在成员规程里（`gbt-video` / `gbt-video-tools` / `gbt-chengfeng` / `hyperframes-*`）与总规程 §4 两道闸。

<!-- DESIGN-INDEX:END -->

---

## 2. 七条线各管什么（摘要 → 深读）

| 线 | 一句话 | 深读 |
|---|---|---|
| L1 定档与审美 | 管**好不好看**：设计读数 → 三档转盘 → 三轴选型 → AI 味禁令 → 验收 | `references/L1-定档与审美.md` |
| L2 界面实现 | 管**做出来能跑**：页面/组件/原型/改版（先认基线再动手） | `references/L2-界面实现.md` |
| L3 设计稿与设计系统 | 管**稿与码对齐**：设计令牌、设计系统、Figma 双向 | `references/L3-设计稿与设计系统.md` |
| L4 动效与合成 | 管**动起来**：GSAP（网页）/ HyperFrames（HTML 合成）/ Remotion（React）三层 | `references/L4-动效与合成.md` |
| L5 演示与文档 | 管**讲清楚**：幻灯片/报告/PDF→网页或幻灯片 | `references/L5-演示与文档.md` |
| L6 出图与素材 | 管**图从哪来**：生成/修图/抠图/超分/3D + 素材库 | `references/L6-出图与素材.md` |
| L7 视频与成片 | 管**出成片**：下载/转录/剪辑/字幕/配音/导出 | `references/L7-视频与成片.md` |

---

## 3. 🔴 冲突裁决（**都是踩过的，别再自己发明**）

1. **三处同名规则文件**：`DESIGN.md` / `TASK_ROUTER.md` / `INDEX.md` / `REDESIGN.md` / `OUTPUT_RULES.md` /
   `INTERACTIONS.md` / `PRD_INGESTION.md` / `CODE_INGESTION.md` / `IMAGE_GENERATION.md` / `UI-check.md` /
   `visual-asset-director.md` 这 11 个名字**同时存在于三处**（仓根 · `autoclaw-design-capability` 技能目录 ·
   它的 `_noqa` 变体），**逐文件哈希互不相同**。
   ⇒ **以仓根那份为准**（那是 AGENTS.md 指的那套）；读/改前先 `Get-FileHash` 对一下手里是哪一份。
2. **桩 vs 实现**：`figma-*`(7) · `gsap-*`(4) · `fal-*`(12) · `venice-*`(5) 等**是目录桩**（只有 `SKILL.md`、指向上游）。
   **桩 ≠ 能力不存在**，但**桩也不能被执行** —— 要说"上游有、本机没装"。
   真实现常在别处：GSAP 的真知识在 `hyperframes-animation/adapters/gsap*.md`；PDF→稿在 `glmv-*`。
3. **云 vs 本机**：Ark（`gbt-arkcli`）· HeyGen/AWS/GCP（HyperFrames 那条）· fal / venice（各家 key）·
   **本机能力位**（`video` / `creation` 等域，走 `five-dim.py cap`）—— **凭据、计价、目录都不通用，别互相顶替**。
4. **审美 vs 技能**：L1 管"好不好看"，其余线管"怎么调得动"。**同一件东西两把尺子都要过**：
   "做得对不对"用该线规程判，"做得好不好看"回 L1 判。
5. **能力位 vs 技能簇**：`video` **能力域**是 4 个能力位（`media_pipeline`/`libtv_skill`/`libtv_workflow`/`h3_video_gen`，走 `cap`），
   `video-*` **技能簇**是 4 条技能（按名字加载执行）—— **同屏两段，不是一个东西**。
6. **同名键 `video`**：`DISTILLED_DOMAINS["video"]`（能力域）与 `DISTILLED_CLUSTERS["video"]`（技能簇）**各自独立**；
   报错若说"video 没登记"，先分清是域还是簇。
7. **清单里的 `rules` 是"被引用"，不是"产权"**（2026-09-22 现读纠错）：L4 原挂 `visual-asset-director.md`、
   L7 原挂 `IMAGE_GENERATION.md` + `render/`，**三件都不是那两条线的规则** ——
   `IMAGE_GENERATION.md` 是**生图面（L6）**的规程（全文只在第 38 行提到 video 一次）；
   `render/` 是数字人项目的 **PNG 产物**目录（260 文件 / 约 57 MB），成片落点其实是 `video-out/`；
   `visual-asset-director.md` 只在评审清单里提到 motion 一词，产权在 L6/L2。
   ⇒ 已从 `LINES` 摘掉，并在 §1 的 L4 / L7 段写明"本线没有工作区规则/素材"及原因。
   **产物、落点、被提一嘴，都不等于规则。**
8. **同名多份 ⇒ "读错地方"是本维度第一高频事故**（下面三例都是现读实测，不是推测）：
   - `frontend-slides`：装机目录那份是 **13 文件 / 82,234 B 的真工作流**，工作区 `审美相关skill/skills/` 那份
     只是 **1 文件 / 1,216 B 的桩** —— 读错地方会把**真件当桩**，然后报告"本机没这个能力"。
   - `DESIGN.md` 等 11 个规则名三处同名（见第 1 条），逐文件哈希不同，**认文件先认哈希**。
   - **目录名 ≠ 形态，两个方向都撞上过**：`审美相关skill/design-systems/` 名字像规则，实为
     **150 个品牌目录 / 158 文件的素材库**；`design-assets-index/` 名字像素材库，实为
     **3 文件 / 51 行的外链索引**。
   ⇒ 判形态**先量体积与文件数**（桩有稳定指纹：1 文件 + 约 1.1–1.3 KB + 41–42 行 + 含 `od.upstream`），
   再决定读不读全文；且**必须扫全部 root** —— 图鉴的 `path` 是单值，不会告诉你同名件还散在别处。

---

## 4. 两道闸（**全维度统一，任何线都不例外**）

**闸一 · 凭据与依赖（只报"已配/未配"，绝不贴值）**：动手前先现读该线要什么 ——
`FAL_KEY` / `VENICE_API_KEY` / `AUTOGLM*`（其实是本机 token 服务 `127.0.0.1:18432`）/ `FIGMA_TOKEN` /
`HEYGEN_API_KEY` / `MAPBOX_ACCESS_TOKEN` / `ELEVENLABS_API_KEY` / Ark profile / `python-pptx` / `pymupdf` /
`yt-dlp` / `remotion` 包 / `manim` / chengfeng Runtime……
**缺就说缺，不许"先跑跑看"**。

**闸二 · 有后果的动作必须先问主人**：出图/出片/导出/上传/**发布**/改远端（Figma、云盘、多维表格）/
装包（`npm i`、`pip install`、装 Runtime）/写盘覆盖素材 ——
**一律先摊开（做什么·输入什么·花多少·影响面）→ 等一次明确同意 → 执行 → 拿回执（产物路径 + 字节数/ID）。**

---

## 5. 验收（**怎么证明真做了**）

| 验什么 | 怎么验 |
|---|---|
| 单件设计产出"好不好看" | L1：先做设计读数，再跑 `tools/codex-scripts/audit_aesthetic.py`（**P0 非零退出 = 不合格**） |
| 界面/原型能不能跑 | L2：真开一次（内嵌或本地），**亲眼看到渲染结果**，不看"应该能跑" |
| 出图/出稿/成片真出了没 | 该线规程：要**产物路径 + 字节数/ID** 当回执；没有回执就是没出 |
| 总规程覆盖全不全 | `py -3.14 tools/codex-scripts/design-inventory.py --check`（**点名全覆盖才 PASS**） |
| 这份总规程**自己**落地没 | `py -3.14 tools/codex-scripts/verify-design-mastery.py`（八节齐 · 七份深读各点名本线成员 · 装机副本逐文件同哈希） |
| 装机留没留证据 | `py -3.14 tools/codex-scripts/install-design-mastery.py --check` + 回执 `state/design-mastery-install-receipt.json` |
| 深蒸交付没退化 | `py -3.14 tools/codex-scripts/gbt-checkup.py`（四关合一，第 ④ 关就是本件） |

---

## 6. 诚实账（**总账；逐线细账在 references 里**）

先把最容易说错的四句写死：

1. **"图鉴里有" ≠ "人一句话能调到"**：技能簇走 `agent-skill` 通道，`omni.py ask` **不路由**它们。
2. **"装了" ≠ "能跑"**：`figma-*`/`gsap-*`/`fal-*`/`venice-*` 是桩；`remotion` 包未装（`require.resolve` MODULE_NOT_FOUND）；
   `chengfeng` 的 Runtime/Studio 未装（`~/.chengfeng-videocut` 不在、5190 无监听）；`yt-dlp` 不在 PATH；
   `manim` / `python-pptx` 未装（`pymupdf` 同样未装）。
3. **🔴 "不在 PATH" ≠ "跑不起来"**（2026-09-22 现跑实测，两条都要说）：
   `hyperframes` **不在 PATH**，但 npx 缓存里那份**能离线跑** ——
   `node "$env:LOCALAPPDATA\npm-cache\_npx\<hash>\node_modules\hyperframes\bin\hyperframes.mjs" --version`
   → `0.8.60`，exit 0（`--help` 的命令面与 `hyperframes-cli` 原文一致）；
   而 `npx hyperframes` 这个写法**本身会去装包** —— `npx --no-install hyperframes --version` 原文报
   `npx canceled due to missing packages … ["hyperframes@0.8.61"]`。
   ⇒ 要跑本机这份就走**绝对路径**，别用裸 `npx hyperframes`。
4. **"凭据文件在" ≠ "凭据有效"**：例如 wrangler 的 `oauth_token` 键在，但**有效性没验过**；
   本维度更常见的是**名字全在、值全空**（L7 现读 9 个凭据名**全 UNSET**）。
5. **"审计器说干净" ≠ "人看着好看"**，而且**审计器自己有已知的假阴性**：
   `tools/codex-scripts/fixtures/aesthetic-sins.html` 第 21 行留着 `.bg-blob{background:url("blob.svg")}`
   （注释写明 "❌ P2-1"），现跑 `audit_aesthetic.py` 仍是 **P2 0** —— 脚本只抓
   `class="…blob|wave…"` 与 `<svg … blob|wave|ellipse>`，**抓不到 CSS 选择器写法**。
   另有：craft 七宗罪里 **#4（display 硬写 Inter/Roboto/system-ui）与 #5（圆角卡 + 左侧彩条）**
   在审计器里**没有 P0 实现**（#5 连人工清单 M1–M4 都没列）；craft 把"外链占位图床"记作 P1，
   审计器落 **P0-6**（更严，以审计器为准）。⇒ 机检通过只能说"这一类没命中"，**不能说"这类问题不存在"**。

**本件自己没验过的**：本文件是**索引与裁决**，不含任何可执行体 ——
它的"能跑"只到"命令能跑通"这一层（`design-inventory.py --check` 过）；
**七条线里各自的"没验过什么"，以那七份 references 与各 `gbt-*` 规程的「未验」表为准**，
本件**不替它们打包票**。

---

## 7. 固化与出处

| 什么 | 在哪 |
|---|---|
| 本规程（源 / 装机） | `<仓>/skills/gbt-design-mastery/SKILL.md` · 装机**两处**：`~/.openclaw-autoclaw/skills/gbt-design-mastery/`（AutoClaw 产品口径）**和** `<仓>/.dsh/skills/gbt-design-mastery/`（**本机 DSH 真会扫的项目根**） |
| 🔴 为什么必须两处 | 现读 `dsh-skill-filesystem` 只扫 `<项目>/.dsh/skills` · `<项目>/.agents/skills` · `preset/skills` · `$DSH_HOME/skills` · `~/.agents/skills` —— **不含 `~/.openclaw-autoclaw/skills`**。实测（动态插件读本会话技能层）：不传 `cwd` 只有 78 条、`gbt-*` 仅 4 条（全来自 `~/.agents/skills`）；传上本工作区 `cwd` 后 92 条，本件以 `source: project-dsh` 出现并可加载（22,059 字符）。⇒ **只装 `.openclaw-autoclaw` 对 DSH 会话等于没装。** |
| 七条线深读 | `<仓>/skills/gbt-design-mastery/references/L1…L7` |
| 清单真源（现算） | `state/design_dimension.json`（由 `tools/codex-scripts/design-inventory.py` 生成） |
| 各簇用法规程 | `skills/gbt-aesthetic` · `gbt-figma` · `gbt-design` · `gbt-frontend` · `gbt-web` · `gbt-gsap` · `gbt-pptx` · `gbt-fal` · `gbt-venice` · `gbt-autoglm` · `gbt-glmv` · `gbt-remotion` · `gbt-hyperframes` · `gbt-video` · `gbt-video-tools` · `gbt-chengfeng` |
| 工作区设计规则 | 仓根 `AGENTS.md` 指的那一套（`DESIGN.md` / `TASK_ROUTER.md` / `REDESIGN.md` / `UI-check.md` / `visual-asset-director.md` / `IMAGE_GENERATION.md` / `OUTPUT_RULES.md` …） |
| 机器门 | `design-inventory.py --check`（索引覆盖）· `verify-design-mastery.py`（本件落地：八节 + 七份深读 + **两个装机根**逐文件同哈希）· `install-design-mastery.py`（装机 + 回执）· `mirror-design-regulations.py --check`（16 条簇规程镜像核对）· `audit_aesthetic.py`（好看与否的机检）· `gbt-checkup.py`（四关合一） |
| 装机回执 | `state/design-mastery-install-receipt.json`（逐文件 sha256 + 字节数 + 落盘时间，现算） |
| 各簇规程的本会话可加载副本 | `<仓>/.dsh/skills/gbt-<簇>/`（**16 条**，由 `tools/codex-scripts/mirror-design-regulations.py` 现读本表名单镜像，回执 `state/design-regulations-mirror-receipt.json`）—— 现读会话技能目录已列出这 17 条（总规程 + 16 簇），说明"点得到"不只是文件在盘上 |
