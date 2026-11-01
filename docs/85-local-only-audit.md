# 85 · 本地算力审计（2026-11-01）

> 主人最新铁令：**所有能力用本地算力实现，不再花钱/上云。**
> 本页把短剧管线里每一处外部依赖点名，并标出已改/未改。

## 一、逐项点名

| 位置 | 外部依赖 | 性质 | 现状 |
|---|---|---|---|
| `drama_forge._edge_tts` / `tools/codex-scripts/edge-tts.py` | Microsoft Edge TTS `speech.platform.bing.com` | **云** | 已改为**显式 `-CloudTts`/`allow_cloud_tts` 才用**；默认不走 |
| `tools/drama-build.ps1` 默认 `Voice=local` | 本机 SAPI | 本地 | ✅ 默认 |
| `tools/stock-fetch.ps1` | Openverse API / Picsum | **云** | 仍存在，但**非默认**；仅 `-StockQueriesFile` 显式调用 |
| `drama_forge -Gen` + `GBT_T2I_CMD` | 外部生成器 | 外部 | 默认关闭；不配就 `needs_model` |
| `stabilityai/sd-turbo`（`vendor/hf`） | 模型权重只下载一次；推理在本机 CPU | 本地推理 | ✅ 文生图本地跑 |
| `torch` / `diffusers` / `PIL` / `ffmpeg` | 本机 | 本地 | ✅ |
| `edge-tts` Python 包（`vendor/pylibs`） | 仅用于云 TTS 可选路径 | 云 | 非默认 |

## 二、当前成片的真实出身（不混）

| 成片 | 画面 | 配音 | 是否本地-only |
|---|---|---|---|
| `顶替新娘` E01–E03 | Openverse/Picsum CC 照片（云取图） | Edge zh-TW（云 TTS） | ❌ 不是 |
| `文生图-氛围` | SD-Turbo 本机生成 | Edge zh-TW（云） | ❌ TTS 是云 |
| `本地算力-测试` | SD-Turbo 本机生成 | 本机 SAPI（zh-CN） | ✅ 全本地（但非台湾腔） |
| `随意成片` | 用户照片（本地） | Edge zh-TW（云） | ❌ TTS 是云 |

## 三、本地台湾腔的唯一正路
本机 SAPI 实测只有：
```
Microsoft Huihui Desktop | zh-CN | Female
Microsoft Zira Desktop  | en-US | Female
Microsoft David Desktop | en-US | Male
```
**没有 zh-TW 女声**。要同时“本地 + 台湾腔”，必须装 Windows zh-TW 语言包（不花钱，但要管理员）：

```powershell
# 管理员 PowerShell；由 tools\install-zh-tw-voice.ps1 打印/执行
Add-WindowsCapability -Online -Name Language.TextToSpeech~~~zh-TW~0.0.1.0
```
装完后 `drama-build` 的本地 SAPI 会自动优先选 `zh-TW + Female`；没有就明确回退 zh-CN，并写清不是台湾腔，**不再偷偷联网 Edge**。

## 四、当前默认行为
- `drama-build.ps1`：`Voice=local`；只有 `-CloudTts` 且 `-Voice zh-TW-*` 才走 Edge；
- `drama_forge._tts`：`local/sapi/auto` → 本机 SAPI；`zh-TW-*` 且未显式允许云 → `needs_local_voice`，**fail-closed**；
- 取图：默认只用 `-AssetsDir` 本地图或 `-Gen` 本地生成；`-StockQueriesFile` 需显式，且文档标“云”。

## 五、还没解决的
- **本地 zh-TW 女声**：缺语言包（需管理员）；装前无法既本地又台湾腔；
- **高质量人物文生图**：SD-Turbo CPU 1–4 步人物畸形，已拒绝交付；要更好需更大本地模型/GPU（不花钱但更重）；
- **图生视频**：本机无模型，不假装；
- 既有三集成片/氛围片仍含云依赖，不能标“本地-only”。

> 开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属
