# 短剧产线（drama_forge）

> 2026-11-01 · 让 GBT天真 **不再手搓短剧**：剧本（时间码）→ 分镜 → 台湾腔旁白/字幕 → 竖屏成片，一条命令。
> 原生位：`drama_forge`（creation，写 outputs；不自动发布）。

## 一、它替掉哪些手工活

| 手搓环节 | drama_forge 自动做 |
|---|---|
| 剧本拆镜/数时长 | 复用 `drama.parse_timed` 切分镜，六字段契约照旧 |
| 逐镜念旁白 | **默认 zh-TW-HsiaoChenNeural（台湾腔女声，Edge TTS 联网）**；可 `-Voice` 切 HsiaoYu 等；失败明确报错，**不降级成普通话** |
| 字幕对时 | 与旁白同源生成 SRT（烧进画面 + 软字幕轨），不手抄两遍 |
| 配画面 | 有 `assets_dir` 用你的自有图；没有就渲**分镜卡 animatic**（明标，不冒充成片） |
| 竖屏装配 | ffmpeg 1080×1920 / 30fps / H.264 + AAC，一条命令出 `episode.mp4` |
| 验收 | ffprobe 判 MP4/竖屏/时长/音轨/字幕轨，逐条红绿 |

## 二、契约

| op | 作用 |
|---|---|
| `storyboard` | 剧本 → 分镜 JSON（不写盘） |
| `make` | 全链产片：分镜 → 卡片/自有图 → TTS → SRT → episode.mp4 → report.md/json |
| `verify` | 对已有 MP4 做 ffprobe 判据 |
| `status` / `where` | 只读 |

`make` 关键参数：
- `script`：必填，`0s – 4s（标题）大特写 推近 …` 格式（与 `drama` 链头同格式）；
- `assets_dir`：可选，里面放 `01.png/02.jpg...` 按镜序用；
- `name`：输出目录名；`min_dur`/`max_dur`：验收窗口（短剧正片建议 60/180；预告/测试可 5/60）。

输出落 `outputs/drama-forge/<name>/`：`cards/`、`audio/`、`episode.srt`、`episode.mp4`、`report.md`、`report.json`。

## 三、一键脚本（推荐）

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File tools\drama-build.ps1 `
  -ScriptFile .\script.txt -Name 醒来E1 -MinDur 5 -MaxDur 60 [-AssetsDir .\assets]
```
它把 **台湾腔 Edge TTS 放在 Python helper 层**（`tools/codex-scripts/edge-tts.py`），再调 `drama_forge make` 装配。
实测：18.27s / 1080×1920 / 有音轨 / 有字幕 / 五项判据全绿。

**接 AI 画面（可选）**：设 GBT_T2I_CMD（{prompt}/{out}/{idx} 占位）后加 -Gen；没配就 
eeds_model 并回退分镜卡——**本件不内置模型，不假装出图**。

## 三·五、示例（真跑）

```python
api.run_task("drama_forge", {
  "op": "make", "name": "醒来E1", "min_dur": 5, "max_dur": 60,
  "script": "0s – 4s（标题）大特写 黑屏里浮起一行字\n4s – 9s（睁眼）特写 推近 它在冷却液池底睁眼\n9s – 14s（对视）近景 环绕 影子回头，两张脸对上\n"
})
```

## 三·六、多集策划（series）

```python
api.run_task("drama_forge", {"op":"series","premise":"被顶替的新娘在婚礼上认出了凶手","episodes":3,
  "episode_sec":90,"genre":"都市悬疑","characters":["她","他"]})
```
- 输出 `outputs/drama-forge/series-*/`：`series.json`（bible）+ `E01.txt/E02.txt…`（每集 5 拍：钩子/铺垫/冲突/反转/悬念，带时间码分镜稿）；
- 然后用一键脚本逐集装配：`drama-build.ps1 -ScriptFile …\E01.txt -Name 剧名-E01 [-AssetsDir ...] [-Gen]`；
- 只做策划/分镜稿，不生成画面。
## 三·八、真素材成片（CC 授权照片）

```powershell
powershell ... -File tools\drama-build.ps1 -ScriptFile E01.txt -Name 剧名-E01 `
  -StockQueriesFile queries.json   # 每镜一句英文 query 的 JSON 数组
```
- `tools\stock-fetch.ps1` 从 Openverse 取 **by/by-sa/cc0** 真实照片（取不到兜底 Picsum），写 `credits.json`；
- 实测三集：**61.3s / 1080×1920 / 有音轨 / 有字幕 / 五项全绿 / visual_mode=assets**；
- 商用前按 `credits.json` 逐张核对署名与许可；这不是 AI 生成画面。
## 三·九、台湾腔女声（2026-11-01 修）

- 本机 SAPI 实测只有 `Microsoft Huihui Desktop`（zh-CN 女声），**没有 zh-TW 女声** ⇒ 之前默认念出来是普通话，所以“变味”。
- 现默认：**`zh-TW-HsiaoChenNeural`**（Edge TTS，台湾腔女声）**本地优先**：默认 `Voice=local`（SAPI；本机现只有 zh-CN Huihui）；`-CloudTts` 才显式用 Edge zh-TW。三集当前成片是 **Edge 云配音历史版**，不是本地配音；要本地台湾腔先装 zh-TW 语言包（见 docs/85）。
- 实测重装 E01：5 镜全部 `zh-TW-HsiaoChenNeural`，成片 **61.07s / 1080×1920 / 有音轨 / 有字幕**。
- 候选试听：`交付成片/顶替新娘/试听-HsiaoChen-自然.mp3`、`试听-HsiaoChen-泼辣.mp3`、`试听-HsiaoYu-泼辣.mp3`、`试听-Google-zhTW.mp3`（同一句，挑最对味的再锁默认）。
- 边界：Edge TTS **需联网**；要完全本地台湾腔，需装 zh-TW 语言包（管理员）后切 SAPI/OneCore；没装就明确写联网，不假装本地。
## 四、诚实边界（必须看）

- **不生成 AI 画面/视频**：没 `assets_dir` 时产出的是**分镜卡 animatic**（报告里 `visual_mode=storyboard_cards`），不是"AI 短剧成片"。
- 不下载/不复制原视频、不自动发布；TTS 本地离线；只写 `outputs/`。
- 旁白自然时长会重排镜头（`reading.timeline_note` 会写）；与剧本声明时长不一致不藏。
- 素材是自有/授权图时，才是"真画面装配"；要 AI 生成图/视频，需另接生成模型（comfy_native/comfy_cloud 等）。

> 开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属
