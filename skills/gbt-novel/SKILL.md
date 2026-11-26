---
name: gbt-novel
displayName: GBT · novel-* 技能簇用法规程（7 条：小说→短剧端到端流水线）
version: 1.0.0
description: GBT小土豆V8 的 `novel-*` 技能簇用法规程。这个簇**7 条**，是一条「小说/爽文 → 竖屏短剧」的端到端生产流水线：`novel-outline`（大纲）→ `novel-characters`（角色）→ `novel-art`（美术设定）→ `novel-script`（剧本）→ `novel-staging`（站位）→ `novel-storyboard`（分镜），外加 `novel-video-pipeline`（端到端一键成片）。本文件把每条**逐个点名**：用途、上下游衔接、产出物、质量门道数、零依赖/零 API key 的口径、什么时候用；并写死三条纪律（质量门由脚本确定性检查不靠模型自觉、交付提示词/JSON 不出图、流水线顺序不可乱跳）与边界（与 gbt-creation/gbt-video 的分工）。当用户要改编小说为短剧、出大纲/角色/美术/剧本/站位/分镜、或跑端到端成片时使用。
triggers:
  - "novel-outline"
  - "novel-characters"
  - "novel-art"
  - "novel-script"
  - "novel-staging"
  - "novel-storyboard"
  - "novel-video-pipeline"
  - "改编大纲"
  - "短剧大纲"
  - "分镜"
  - "角色卡"
  - "场景设定"
---

# GBT · novel-* 技能簇用法规程（7 条：小说→短剧端到端流水线）

> 开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属
>
> **这份规程解决什么**：`novel-*` 是**外来技能簇**（7 条），本机已装在 `~/.agents/skills/`。
> 它们拼起来是一条**小说转竖屏短剧**的端到端流水线。本文件把每条**逐个点名**：
> 用途、上下游衔接、产出物、质量门、口径，以及**流水线顺序不可乱跳**的纪律。

**唯一现读入口**：每条技能由 `skill <名>` 加载执行（agent-skill 通道）；
本规程不替代技能本身，只给**用法口径与衔接顺序**。

---

## 0. 七条是什么（先认全）

| # | 技能 | 一句话 | 产出物 | 质量门 |
|---|---|---|---|---|
| 1 | `novel-outline` | 小说→短剧大纲五件套（改编说明/人物表/爽点表/分集梗概/资产清单） | `outline.json` + Markdown + 评审报告 | 14 道 |
| 2 | `novel-characters` | 拆角色表/画像/形象提示词/音色提示词 | JSON + Markdown + `report.html` | — |
| 3 | `novel-art` | 美术设定集（场景 + 叙事道具），交付提示词不出图 | `art.json` + Markdown + 评审报告 | 10 道 |
| 4 | `novel-script` | 分集梗概→场次 + 节拍流（动作/台词交替） | `script.json` + Markdown + 评审报告 | 10 道 |
| 5 | `novel-staging` | 每场开场站位（谁在哪件东西哪侧/坐站/面朝） | `staging.json` + HTML 工具报告 | 8 道 |
| 6 | `novel-storyboard` | 分镜（段→分镜→分镜图），含 MiniMax H3 视频提示词 | `storyboard.json` + Markdown + 评审报告 | 18 道 |
| 7 | `novel-video-pipeline` | 端到端一键成片（分镜拆解+多角色配音+字幕对齐+运镜） | 竖屏短视频（本地闭环） | — |

**共同口径**：**零依赖、零 API key**（`novel-outline`/`novel-script` 用当前会话额度；其余纯本地）；
**质量门全部由脚本确定性检查**，不靠模型自觉；**交付提示词/JSON/报告，出图在下游**（`novel-art`/`novel-storyboard` 明确不出图）。

---

## 1. 🔴 流水线顺序（不可乱跳）

```
novel-outline ──→ novel-characters ──→ novel-art ──→ novel-script ──→ novel-staging ──→ novel-storyboard
                                                                                      │
                                                                                      ↓
                                                                                novel-video-pipeline（成片）
```

**衔接纪律**：
- `novel-art` **吃** `novel-outline` 的 `outline.json`（seed 预填场景清单与出现集）；
- `novel-staging` **吃** `novel-script` 的 `script.json` + `novel-art` 的 `art.json`（预填骨架）；
- `novel-script` 给 `--art` 可连光照状态一起对账；
- `novel-storyboard` 认领 `novel-script` 的剧本节拍，台词逐字进 `<d>` 块。

⇒ **上游没产出，下游别硬跑**：缺 `outline.json` 就先跑 outline，别空跑 art。

---

## 2. 逐条点名（用途 / 产出 / 门 / 什么时候用）

### 2.1 `novel-outline`（改编大纲）
- **用途**：把小说改编成短剧大纲五件套。
- **产出**：`outline.json` + Markdown + 单页评审报告（KPI 带/关键决策/爽点时间轴/调度矩阵/场景概览/质量门）。
- **门**：14 道（角色分档上限、主场景上限随集数动态、爽点间隔≤3 集、每集钩子悬念必填……）。
- **特色**：支持**体检模式**——贴一份现成大纲进来，只跑质量门给诊断。
- **用**：用户说「改编大纲 / 短剧大纲 / 拆大纲 / 小说转短剧」。

### 2.2 `novel-characters`（角色卡）
- **用途**：从小说/短故事拆角色表、人物画像、形象提示词、音色提示词。
- **产出**：JSON + Markdown + 可交互 `report.html`（形象提示词含角色设定图版面指令：左半身像+右全身三视图+细节条）。
- **口径**：报告语言可指定（`--lang`，默认中文）；零依赖、零 API key、不出图。
- **用**：用户说「拆小说角色 / 分析人物 / 生成角色卡」。

### 2.3 `novel-art`（美术设定）
- **用途**：给 AI 短剧出美术设定集（场景 + 叙事道具）。
- **产出**：`art.json` + Markdown + 评审报告（**交付提示词，不出图**——出图在下游）。
- **门**：10 道（锚点 3–5、无人无手、白底可抠、尺度短语、提示词英文……）。
- **口径**：为 AI 生成而设计，不是实拍；一致性锚点让环境/道具跨集长一样。
- **用**：用户说「场景设定 / 出场景 / 环境设定集 / 场景一致性」。

### 2.4 `novel-script`（剧本）
- **用途**：把分集梗概落成场次 + 节拍流（动作节拍与台词行交替，台词带说话人与语气，时长按语速折算）。
- **产出**：`script.json` + Markdown + 评审报告（时长仪表/分集剧本/场次总表/按角色聚合台词本）。
- **门**：10 道（每集时长 ±15%、单句 ≤35 字、说话人合法、钩子悬念落纸、钩子具象前 3 拍内兑现……）。
- **边界**：**剧本管戏，分镜管拍**——本条不分镜头、无镜号、不写生成提示词（那是 storyboard 的活）。
- **用**：用户说「写剧本 / 出剧本 / 台词 / 场次」。

### 2.5 `novel-staging`（站位）
- **用途**：给每场排开场站位（从场景图认能站能坐的东西，排谁在哪件东西哪侧/坐站/面朝/群演）。
- **产出**：`staging.json` + 可拖动调整的 HTML 工具报告（页面内可导出 JSON）。
- **门**：8 道（认图件数、东西在图上、出场人物不多不少、在场的人落在认出来的东西上、同侧不叠人……）。
- **口径**：吃 `script.json` + `art.json` 预填骨架；零依赖、零 API key。
- **用**：用户说「站位 / 开场站位 / 群戏站位 / 谁坐在哪 / 走位 / blocking」。

### 2.6 `novel-storyboard`（分镜）
- **用途**：出分镜，三层结构——段（一次视频生成 ≤15s）→ 分镜（段内 2–5s 剪切，认领剧本节拍）→ 分镜图（每切一张关键帧）。
- **产出**：`storyboard.json` + Markdown + 评审报告（分镜节奏带/分集分镜表/生成批次单/配音对齐单）。
- **门**：18 道（第 18 道 shot-recipe 可选：挂上卡库才查，不挂明说跳过）。
- **口径**：每段自带 MiniMax H3 视频提示词（官方口径默认英文、逐镜换行，`promptLang` 可切中文）；台词逐字进 `<d>` 块；**不出图**——交付每格画面提示词和该挂哪些参考图。
- **用**：用户说「分镜 / 出分镜 / 镜号」。

### 2.7 `novel-video-pipeline`（端到端成片）
- **用途**：小说/爽文/短剧文本转竖屏短视频的端到端全自动流水线。
- **产出**：竖屏短视频（本地闭环一键成片）。
- **含**：分镜拆解、多角色 AI 配音、毫秒级字幕对齐、Ken Burns 动态慢推运镜；按需联动 nologin.tools 免登录工具库（封面/音频混音/图片压缩）。
- **用**：用户要「小说生成短视频 / 一键成片 / 端到端出片」。

---

## 3. 🔴 三条纪律（拿实测坑换的）

1. **质量门由脚本确定性检查，不靠模型自觉**：每条技能的 N 道质量门都是脚本硬判，不靠"模型觉得差不多"——这是这套簇的核心可靠性。
2. **交付提示词/JSON，出图在下游**：`novel-art`/`novel-storyboard` **明确不出图**，交付的是提示词与结构；要真图/真片走下游生成。
3. **流水线顺序不可乱跳**：上游没产出，下游别硬跑（§1）；缺 `outline.json` 先跑 outline。

---

## 4. 落点 / 外部面

| 维度 | 实测 |
|---|---|
| **技能根** | `~/.agents/skills/novel-*/SKILL.md`（本机已装） |
| **依赖** | **零依赖**（`novel-outline`/`novel-script` 用当前会话额度，其余纯本地） |
| **API key** | **零 API key**（不配任何密钥） |
| **产出落点** | 工作目录内的 `outline.json`/`art.json`/`script.json`/`staging.json`/`storyboard.json` + Markdown + `report.html` |
| **出图/出片** | `novel-art`/`novel-storyboard` 不出图；`novel-video-pipeline` 本地闭环出片 |

---

## 5. 失败典型样子（照着认）

| 症状 | 真因 | 正确读法 |
|---|---|---|
| 下游跑报"缺 outline.json/script.json" | 上游没产出就跳下游 | 先跑上游（§1），别空跑 |
| `novel-art` 只出提示词没出图 | **设计如此** | 出图在下游，本条交付提示词 |
| 质量门判红 | 脚本确定性检查不通过 | 按门的判据改，别靠"模型觉得行" |
| `novel-storyboard` 的 H3 提示词是英文 | 官方口径默认英文 | 要中文用 `promptLang` 切 |
| 把"零 API key"读成"不需要额度" | `novel-outline`/`novel-script` 用会话额度 | 零 key ≠ 零额度，会话额度照耗 |

---

## 6. 与相邻域的边界（一句话切干净）

| 相邻 | 谁是谁 | 边界 |
|---|---|---|
| `gbt-creation` | 创作出口（create/drama/…） | 那是**框架创作能力位**；本簇是**外来技能簇**，专做小说→短剧 |
| `gbt-video` / `gbt-video-tools` | 视频域/视频技能簇 | 本簇的 `novel-video-pipeline` 出片是**本地闭环**；视频域是框架能力位 |
| `gbt-hyperframes` | HTML 合成视频 | 那是另一种成片路径；本簇 `novel-video-pipeline` 是小说转短剧专用 |

---

## 7. 🔴 报告层红线

1. **质量门是脚本判的，不是模型判的**：说"过了质量门"要指回脚本判据，不是"我觉得行"。
2. **"不出图"是口径不是故障**：`novel-art`/`novel-storyboard` 交付提示词，别读成"坏了没出图"。
3. **流水线顺序是纪律**：跳序跑下游必缺料，先补上游。
4. **零 API key ≠ 零成本**：`novel-outline`/`novel-script` 耗会话额度，如实报。

---

## 8. 不许做什么（红线）

1. **不许跳过上游硬跑下游**：缺 `outline.json` 不跑 art（§1）。
2. **不许**把 `novel-art` 的提示词当"已出图"。
3. **不许**替脚本改质量门判据（门是确定性检查，改了就失去可靠性）。
4. **不许**给 `novel-*` 配 API key（本簇口径是零 key）。

---

## 9. 固化与出处（**重启后要在**）

| 什么 | 在哪 |
|---|---|
| 本规程（源） | `<仓>/skills/gbt-novel/SKILL.md` |
| 本规程（装机·托管目录） | `C:\Users\ADMIN\.openclaw-autoclaw\skills\gbt-novel\SKILL.md` |
| 技能簇源 | `~/.agents/skills/novel-*/SKILL.md`（7 条，外来技能） |
| 簇登记 | `tools/codex-scripts/omni.py` 的 `DISTILLED_CLUSTERS["novel"]` |

**验收**：

```bash
python tools/codex-scripts/omni.py gaps    # B 部分 novel-* 应标「✅ 已深蒸 → gbt-novel」
```
