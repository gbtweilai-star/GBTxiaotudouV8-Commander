---
name: gbt-voice
displayName: GBT 嘴 · 耳（voice 职业域用法规程）
version: 1.0.0
description: GBT小土豆V8 的 `voice` 职业域（语音合成 / 语音识别 / 语音复刻编排）用法规程。把图鉴里这 2 个能力位逐个点清 —— `voice`（Windows SAPI 真出声 + ASR 入口）与 `voice_orchestra`（17 项语音技能原子的只读检索 / 场景 Pipeline / 本机可跑性）—— 规定谁只读、谁要授权（`voice` 空参默认落到 tts ⇒ 要 `audio_output`）、真命令与真返回字段、失败长什么样、依赖哪些外部件与密钥；并附一份不许说反的诚实账（WASAPI 活动渲染端点 1 / 活动录音端点 0 —— 麦克风输入现在不可用，但既不是"没有麦克风硬件"，也不是"有麦克风能用"）。当用户要"念一段话 / 出声 / 朗读 / 合成语音 / 配音"、"识别语音 / 转写 / 语音转文字"、"语音复刻 / 变声"、"看看本机语音后端能不能跑"，或某个 voice 能力位报「需要人工授权」、报 `needs_dependency`、读数对不上时使用。
triggers:
  - "念一段话"
  - "出声"
  - "朗读"
  - "语音合成"
  - "TTS"
  - "配音"
  - "语音识别"
  - "转写"
  - "ASR"
  - "语音复刻"
  - "变声"
  - "voice"
  - "麦克风"
  - "语音中枢"
---

# GBT 嘴 · 耳（`voice` 职业域用法规程）

> 开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属
>
> 这是「人类视角操控一切」里**管嘴和耳朵的那一半**：`gbt-omni` 负责"人话落到哪个能力位"，
> 本规程负责"这一域到底怎么调、哪一声真能出、哪一声出不来、出不来时如实说什么"。

**唯一现读入口（别信任何二手描述，包括本文件）**：

```powershell
py -3.14 tools/codex-scripts/five-dim.py cap voice_orchestra              # 空参 = status：本机可跑性（只读）
py -3.14 tools/codex-scripts/five-dim.py cap voice '{"op":"status"}'      # 合成/识别入口自报状态（只读）
```

**本域只有 2 个能力位**（以 `state/skill_atlas.json` 里 `domain == "voice"` 的 `kind` 为准，
实测 `kind` 就是 `voice` 与 `voice_orchestra` 两个，不多不少）。**以它们的实时输出为准，本文件只是导读。**

---

## 1. 这一域到底是什么（一位一行）

| 能力位 | 是什么 | 只读 / 授权 | 一句话实话 |
|---|---|---|---|
| **`voice`** | 语音合成/识别**入口**：`tts` = Windows **SAPI**（零依赖、本机自带，真出声）；`asr` = 需外部后端的语音识别 | **分档**：`op=status`/`op=asr` **零作用域**（只读）；**空参或缺省 op 落到 `tts` ⇒ 要 `audio_output`**；带 `out` 还叠加 `filesystem_write` | **真能出声**的只有 SAPI 这一条；**ASR 后端本机没配**，如实报 `needs_dependency` |
| **`voice_orchestra`** | 语音技能**中枢**：17 项语音技能原子的检索（`list`）/ 场景 Pipeline（`pipeline`）/ 本机可跑性（`status`） | **只读三档零作用域**，随时可跑；三档之外**一律 fail-closed**（挂 `data_export` + `external_llm`） | 它读的是**仓内常量表**，不是真模型 —— **是"技能目录"，不是"技能执行器"** |

**两个字面事实（照抄图鉴，不许改写）**：

- `voice`.desc = 「语音合成/识别入口（良性子集）」· `voice_orchestra`.desc = 「语音技能中枢（多维度场景编排，只读）：技能原子检索 / 场景 Pipeline / 本机可跑性；今日挂 tools tab，升格条件见模块 docstring」
- 两位 `channel` 都是 `omnipulg`（走 `run_task` 唯一门）、`enabled` 都是 `true`。

**⚠️ 图鉴的 `safe: true` 不等于"免授权"**：图鉴里 `voice` 也写着 `safe: true` · `requires_params: []`，
可它**空参调用会被门当场拒**（缺 `audio_output`）—— 因为空参在 `api.py` 里落到 `op="tts"`。
**只读档必须显式写 `op`**（见 §3）。这条正是 `omni list --domain voice` 里 `voice` 显示 🔒 而
`voice_orchestra` 显示 ✅ 的原因（该出口已改成查 `policy`，不是只查图鉴旗标）。

**`voice_orchestra` 今天为什么不升成独立 tab（照抄模块 docstring 的口径）**：
面板 tab 是"给用户看的能力边界"，而 2026-09-18 起真能跑的只有 2 项（`Kokoro-82M` / `sherpa-onnx`），
开 tab 展示 17 项、其中 15 项本机跑不了，就是"看起来更完备"。**升格条件两条**：
① B1 云后端到位、ASR / TTS / CLONE 三条真链路可跑；② 面板能展示这三条链路的真状态。
在此之前它是「**有明确升格条件的暂挂**」—— 不是"暂挂"，两者性质不同。

---

## 2. 怎么调（真命令 + 真返回字段 · 全部本机实跑过）

> 命令格式：`py -3.14 tools/codex-scripts/five-dim.py cap <能力位> '<payload_json>'`。
> `cap` 一律走 `gbt_allinone.run_task`（唯一门）；被门拒就**如实报缺什么作用域**，不绕路。

### 2.1 `voice_orchestra` —— 只读三档（零作用域，可直接跑）

**① `status`（空参默认就是它）—— 报本机可跑性**

```powershell
py -3.14 tools/codex-scripts/five-dim.py cap voice_orchestra
```

实测返回（`status ok` · `stamp true` · `denied false` · **exit 0**）：

```json
{"ok": true, "readonly": true, "op": "status", "registry_size": 17,
 "local_backends": {"onnxruntime": true, "torch": true, "dxcam": true, "sapi": true},
 "note": "本机可跑性以能 import 的后端为准；torch 缺失则 2B 级以上本地模型不可跑，见 gbt_allinone/docs/语音中枢v2.0-实测与部署.md"}
```

⚠️ **`local_backends` 四项全 `true` ≠ "那 17 项都跑得起来"**。它只探 `importlib.util.find_spec`
（"这个包在不在"），**不探模型权重在不在、显存够不够**。模块 docstring 记的是 2026-09-18 的口径
（真能跑 2 项）。**两个判据不是一回事，别把 `true` 说成"17 项都能跑"。**

**② `list` —— 检索技能原子**

```powershell
py -3.14 tools/codex-scripts/five-dim.py cap voice_orchestra '{"op":"list"}'
py -3.14 tools/codex-scripts/five-dim.py cap voice_orchestra '{"op":"list","domain":"TTS"}'
py -3.14 tools/codex-scripts/five-dim.py cap voice_orchestra '{"op":"list","domain":"CLONE","keyword":"GPT"}'
```

- `list` 实测 `count 17`；每条字段：`name` / `domain` / `provider` / `deployment` / `license` / `scene` / `highlights`。
- 逐域实测（`domain` 收窄后 `count` 就是该域条数）：
  `ASR` **3**（Whisper · Qwen3-ASR · VibeVoice-ASR）· `TTS` **3**（VoxCPM 2 · CosyVoice2 · Kokoro-82M）·
  `LLM` **2**（Qwen-Omni · Step-Audio 2）· `TOOL` **2**（sherpa-onnx · NVIDIA NeMo）·
  `CLONE` **7**（GPT-SoVITS · OpenVoice V2 · Fish Speech · Qwen3-TTS · VibeVoice · Seed-VC · VoiceStudio）。
  **`CLONE` 那条是源文件逐条读出来的**，不是从 `cap` 输出里读的 —— 原因见下面的截断坑。
- 可用 `domain` 只有 5 个：`ASR` / `TTS` / `CLONE` / `LLM` / `TOOL`（大小写不敏感）。

**③ `pipeline` —— 给定场景给端到端技能链**

```powershell
py -3.14 tools/codex-scripts/five-dim.py cap voice_orchestra '{"op":"pipeline","scene":"有声书"}'
```

实测（`"有声书"`）：

```json
{"ok": true, "op": "pipeline", "scene": "有声书",
 "steps": {"Voice Clone (变声)": "GPT-SoVITS — 5秒克隆目标音色",
           "TTS (嘴巴)": "VoxCPM 2 — 48kHz 高保真合成，30语言9方言",
           "调度骨架": "本地脚本 / ComfyUI 批处理",
           "推荐理由": "追求极致音质与特定音色，适合长音频内容生产。",
           "复刻接入点": "先离线克隆主播音色，再批量合成全本有声书。"}}
```

六个场景名（照抄 `build_pipeline`）：**实时对话 / 有声书 / 视频配音 / 跨语言配音 / 歌声转换 / 无障碍语音修复**；
给别的字符串会落到兜底 `默认` 那一步（**不报错**，只会给一句"请指定场景"—— 别把兜底当成功链）。

**`voice_orchestra` 的三种失败典型（都真跑过）**

| 你怎么调错 | 真返回（关键字段） | 退出码 |
|---|---|---|
| `op=pipeline` 但没给 `scene` | `result.ok false` · `unavailable true` · `denied false` · `rule "voice_scene_required"` · `missing ["scene"]` · 顶层仍是 `status ok` | **0** |
| `op=list` 但 `domain` 乱写 | `result.ok false` · `rule "voice_unknown_domain"` · `missing ["domain"]` · `why "未知 domain: BOGUS（可用 ASR/TTS/CLONE/LLM/TOOL）"` | **0** |
| `op` 不在 `list/pipeline/status`（例如 `{"op":"tts"}`） | 门先拦：`status "denied"` · `missing_scopes ["data_export","external_llm"]` · 顶层就是拒绝信封 | **1** |

⚠️ 前两种 **`denied: false` 但 `ok: false`** —— 它是"**做不了**"的结构化上报（`_cannot`），
**不是被门拒**。把 `ok:false` 一律读成"缺授权"是错的。

### 2.2 `voice` —— 合成（SAPI）/ 识别（需配后端）入口

**参数映射（`gbt_allinone/api.py:934-940`，直接映射，不嵌套）**：
`op`（默认 `"tts"`）· `text` · `voice`（按描述子串匹配发音人）· `rate`（整数，SAPI 语速）· `out`（落盘 WAV 路径）· `audio`（ASR 输入音频路径）。
可用 `op` 只有三个：**`tts` / `asr` / `status`**（源码里 `speak` 是 `tts` 的别名）。

**① 只读档：`status`（零作用域，可直接跑）**

```powershell
py -3.14 tools/codex-scripts/five-dim.py cap voice '{"op":"status"}'
```

实测（`status ok` · `stamp true` · exit 0）：

```json
{"ok": true, "tts": "win-sapi（可用）", "asr": "needs_dependency"}
```

**② 只读档：`asr`（零作用域，但本机没后端 ⇒ 如实返回缺依赖）**

```powershell
py -3.14 tools/codex-scripts/five-dim.py cap voice '{"op":"asr","audio":"probe.wav"}'
```

实测（**门放行了**，是本体的业务失败；**exit 0** —— 退出码陷阱见 §4）：

```json
{"ok": false, "status": "needs_dependency",
 "missing": "GBT_ASR_BASE_URL / GBT_ASR_API_KEY",
 "note": "ASR 后端未配置；tts（SAPI）已可用"}
```

**要真转写，得先配这两样**（`GBT_ASR_BASE_URL` + `GBT_ASR_API_KEY`，OpenAI 兼容
`/audio/transcriptions` 端点；可选 `GBT_ASR_MODEL`，默认 `whisper-1`）。
源码里还写明：**语音原文与密钥都不进账本**，只留长度与 `audio_sha256` 指纹。

**③ 出声档：`tts` —— 要 `audio_output`（本机当前没有）**

```powershell
py -3.14 tools/codex-scripts/five-dim.py cap voice '{"op":"tts","text":"你好"}'
py -3.14 tools/codex-scripts/five-dim.py cap voice                       # 空参 = tts，一样要授权
```

实测**两发都被门拒**（`status "denied"` · `stamp false` · `denied true` · **exit 1**）：

```json
{"missing_scopes": ["audio_output"],
 "reason": "需要人工授权（audio_output）：让本机发声（TTS 合成/播放）或写入音频产物",
 "how_to_grant": ["终端运行: python -m gbt_allinone auth grant --scope audio_output --ttl 600",
                  "或主人手写 store/auth_grants.jsonl 追加一行（格式见 auth_gate.SCOPES 与 README）"],
 "note": "授权一次性消耗；AI 调用路径无权自行发放"}
```

**本会话实测的授权账**（`py -3.14 -m gbt_allinone auth status`，只读）：
`audio_output.grants_available = 0` · `desktop_control.grants_available = 0` ·
`ai_can_grant = false` · `grant_sources = ["CLI 交互确认（auth grant）","主人手写 store/auth_grants.jsonl"]` ·
`note = "授权一次性消耗，默认 10 分钟过期；AI 无权发放"`（全表 15 个作用域）。
⇒ **缺就如实报缺，不许绕门、不许改 `security/policy.py`、不许给自己发授权。**

**④ `op` 写错（且不带 `out`）⇒ 门放行，本体报错**

```powershell
py -3.14 tools/codex-scripts/five-dim.py cap voice '{"op":"nope"}'
```

实测：`status "error"` · `message "未知 op: nope（可用: tts/asr/status）"` · `error_class "user_error"` · **exit 1**。

**⑤ 源码读出、但本次没跑的分支（明确标注）**：

- `text` 缺失时 `tts()` 抛 `ValueError("缺少 text：要合成的文本")` —— **源码读出，未跑**
  （因为要走到那一步得先有 `audio_output` 授权，而本次被门拦在门外）。
- `out` 落盘分支（`SAPI.SpFileStream` + `SSFMCreateForWrite=3`）—— **未跑**，
  静态查门是 `filesystem_write` **+** `audio_output` 双作用域。
- `voice` 参数（按发音人描述子串换声）—— **未跑**。

---

## 3. 门（`gbt_allinone/security/policy.py` **静态**查出来的，逐位实测）

静态查法（不执行能力体）：`policy.evaluate(kind, payload).scopes`。本机实测结果：

| 调用 | 静态作用域 | risk |
|---|---|---|
| `voice` **空参** `{}` | `["audio_output"]` | medium |
| `voice` `{"op":"status"}` | `[]` | low |
| `voice` `{"op":"asr","audio":"a.wav"}` | `[]` | low |
| `voice` `{"op":"tts","text":"x"}` | `["audio_output"]` | medium |
| `voice` `{"op":"speak","text":"x"}` | `["audio_output"]` | medium |
| `voice` `{"op":"tts","text":"x","out":"o.wav"}` | `["filesystem_write","audio_output"]` | high |
| `voice` `{"op":"asr","audio":"a.wav","out":"o.wav"}` | `["filesystem_write"]` | high |
| `voice_orchestra` 空参 / `list` / `pipeline` / `status` | `[]` | low |
| `voice_orchestra` 其它任何 op（如 `clone`） | `["data_export","external_llm"]` | high |

**四条读法（照做）**：

1. **`voice` 空参要授权**（默认落 `tts`）⇒ 想只读，**必须显式写 `op:"status"` 或 `op:"asr"`**。
2. `voice_orchestra` 的三档零作用域是**显式声明**的（源码注释原文：读的是仓内常量表，不碰数据面、
   不外发、不落盘）；**三档之外是 fail-closed**，为的是将来加 `tts`/`clone` 动作时不被静默放行。
3. `out` 一旦出现，**即使在只读 op 上也叠加 `filesystem_write`** —— 门不拦 ≠ 只读。
4. **授权只能在主人终端发**（`python -m gbt_allinone auth grant --scope audio_output --ttl 600`）
   或主人手写 `store/auth_grants.jsonl`。**AI 永远无权给自己发授权。**

---

## 4. 🔴 报告层红线：读数先问「这是事实，还是我读错了地方」

三条**本域实测、可复现**的读错地方：

**① 授权被拒时，`cap` 打的是扁平错误信封 —— 读顶层，不要读 `gbt_result`。**
实测 `cap voice`（空参）的顶层键含 `denied` / `missing_scopes` / `reason` / `how_to_grant` / `note` / `result`，
**`gbt_result` 根本不存在**。`five-dim.py` 已按此修过（源码注释 **R-H299**：改前只读 `r["gbt_result"]`
⇒ 门明明说"拒了"，报表却打 `status: unknown · denied: false`，把"缺授权"读成"只是没跑通"）。
⇒ **判断"是不是被门拒"，看顶层 `denied` 与 `missing_scopes`。**

**② 信封 `status:"ok"` ≠ 本体 `ok:true`。**
本域三个实测例子，外层全是 `status "ok"` · `stamp true` · **exit 0**，而本体在说"做不了"：
`voice` 的 `op=asr` ⇒ `result.ok false` · `status needs_dependency`；
`voice_orchestra` 的 `op=pipeline` 缺 `scene` ⇒ `result.ok false` · `unavailable true`；
`voice_orchestra` 的 `op=list` 乱写 `domain` ⇒ `result.ok false`。
⇒ **只看外层状态/退出码 = 把"发现了问题"读成"一切都好"。本体 `ok`、`status`、`rule`、`missing` 才是结论。**

**③ 退出码不可信 —— 它只反映"门放没放行 / 有没有抛异常"，不反映"活干成没干成"。**
实测分布：`exit 0` 同时出现在**真成功**（`status`）、**业务拒绝**（`asr` 缺依赖 / `pipeline` 缺 scene）、
**域写错**（`unknown_domain`）三种情形；`exit 1` 出现在**被门拒**（`voice` 空参、`voice_orchestra` 未知 op）
与**本体抛错**（`voice` 未知 op，`error_class user_error`）。
判据只有一条：**顶层 `status` + `missing_scopes` + 本体 `ok`**。

**④ 附带的一个真坑：`cap` 的打印被硬截断到 1500 字符。**
`five-dim.py:130` 是 `print(json.dumps(out, …)[:1500])`。实测
`cap voice_orchestra '{"op":"list","domain":"CLONE"}'` 输出**正好 1500 字符**、JSON 在 `Seed-VC` 那条中间
被切断（`json.loads` 报 `line 84`），`count` 字段都看不到 —— **这不是能力坏了，是包装器截断**。
姿势：用 `domain` / `keyword` 收窄；要总数就读源码常量表（`VOICE_SKILL_REGISTRY`）。

---

## 5. 🔴 诚实账（本机音频链路的实测状态 —— **一句都不许反着说**）

### 5.1 录音侧（**这是最容易被说反的一条**）

**准确口径：WASAPI 层「活动录音端点 = 0」。麦克风输入现在不可用。**

| 口径（各是各的基准，别混用） | 本机读数 |
|---|---|
| **WASAPI** `EnumAudioEndpoints(eCapture, STATEMASK_ALL)` | **在册 5 条：ACTIVE 0 / NOTPRESENT 3 / UNPLUGGED 1 / DISABLED 1** |
| **WASAPI** `EnumAudioEndpoints(eCapture, DEVICE_STATE_ACTIVE).GetCount()` | **0** |
| **WASAPI** `GetDefaultAudioEndpoint(eCapture, eConsole)` | **失败** (-2147023728, "找不到元素。") = `ERROR_NOT_FOUND` |
| `winmm` `waveInGetNumDevs`（传统 MME 枚举，**在册口径**，本次未亲测） | 0（**这只是一条旁证，不是全部事实**） |
| PnP 音频端点 | 3 个 `Status=OK`：`扬声器 (iPhone Hands-Free HF Audio)` · `麦克风 (iPhone Hands-Free HF Audio)` · `扬声器 (Realtek(R) Audio)` |

⇒ **既不是「没有麦克风硬件」，也不是「有麦克风能用」—— 这两种说法都不准。**
PnP 里**确实登记着一个状态 OK 的录音端点**（蓝牙免提那个麦克风），但 WASAPI 层活动录音端点为 0、
也没有默认录音设备，所以**现在录不到**。要真录，得主人去
**「声音设置 → 录制 → 显示禁用的设备」**里启用它 —— **那是改系统设置，我们不代劳、也不假装能。**

### 5.2 放音侧（有落点）

| 口径 | 本机读数 |
|---|---|
| **WASAPI** `EnumAudioEndpoints(eRender, STATEMASK_ALL)` | 在册 22 条：**ACTIVE 1** / DISABLED 2 / NOTPRESENT 18 / UNPLUGGED 1 |
| **WASAPI** `EnumAudioEndpoints(eRender, DEVICE_STATE_ACTIVE).GetCount()` | **1** |
| **WASAPI** `GetDefaultAudioEndpoint(eRender, eConsole)` | **OK** → `{29bc7e07-…}`（与注册表名 `扬声器` 对上） |
| `Win32_SoundDevice` | 6 条 `Status=OK`（AMD HD Audio ×2 · AMD Audio Device · Realtek HD Audio · Nahimic ×2） |

⇒ **放音链路是活的（活动渲染端点 1 个、默认端点设好了）**，所以 SAPI 出声有落点。
但与 `gbt-tentacle` 规程在册的 `cap tentacle '{"method":"audio_devices"}'` 口径（`count_out 1`，`扬声器 (Realtek(R) Audio)`）
是**两种粒度的计数**（`winmm` 设备 vs WASAPI 端点），数值相同不等于基准相同。

### 5.3 上面这些数字是怎么来的（**必须交代来源，不许含糊**）

- **来源 A（在册口径）**：`gbt_allinone/tentacle/omni_audio.py`（`audio_devices` / `audio_loopback` 的实现与
  「活动录音端点 = 0、在册 5 个」的实测记录）· `gbt_allinone/tentacle/wasapi_loop.py`（`DEVICE_STATE_*` 掩码枚举，
  以及"回环已通"那组读数）· `gbt-tentacle` 规程 §4。
- **来源 B（本次现场读数）**：我自己写的**独立 OS 层只读枚举脚本**，
  `comtypes` 直调 `IMMDeviceEnumerator.EnumAudioEndpoints` + `IMMDevice.GetState` + `GetDefaultAudioEndpoint`，
  **只枚举与读状态：不 `Initialize`、不 `Start`、不采集、不出声、不落盘**。
  **【来源 B 的三条硬标注，缺一不可】**
  ① **它是"非能力位路径"**：不经过任何 GBT 能力位，也不写任何账本；
  ② **它不消耗任何授权**（本会话 `py -3.14 -m gbt_allinone auth status` 实测
  `audio_output` / `desktop_control` 的 `grants_available` 全程为 **0**）—— 授权只在"**放行后真执行**"时消耗，
  审计口径**只认 `auth_consumed` 那一条**；被门拒是 `auth_denied`，**没有执行也没有消耗**；
  ③ **它不是触手的替代品**：它只做"取证"（读端点状态），**不 Initialize、不采集**，
  所以**它不证明"触手能听 / 能录"** —— 那两条仍然照 §5.5 #5 / #6 / #8 记「未验 · 卡在 `desktop_control` 一次性授权」，
  本规程**不授权**任何人在没有 `desktop_control` 时拿它去代替触手动作。

### 5.4 ⚠️ 一个不许再踩的读数陷阱：注册表 `DeviceState` **不能**当 WASAPI 状态用

实测（同一台机、同一时刻）：

| 来源 | 录音（Capture） | 渲染（Render） |
|---|---|---|
| `HKLM\SOFTWARE\Microsoft\Windows\CurrentVersion\MMDevices\Audio\*\DeviceState` | 在册 **7** 条，低 4 位看着有 **2** 条像 `ACTIVE`（含 `0x10000001`、`0x00000001`） | 在册 **23** 条，低 4 位看着有 4 条像 `ACTIVE` |
| WASAPI `EnumAudioEndpoints` + `GetState` | 在册 **5** 条，`ACTIVE` **0** | 在册 **22** 条，`ACTIVE` **1** |

注册表里还出现 `0x20000004` / `0x10000004` 这类**带高位**的值，且有的 GUID（如 `{da302d3d-…}`）
**WASAPI 根本不列**；`{60627402-…}` 注册表低 4 位像 `ACTIVE` 而 WASAPI 明确说 `DISABLED`。
⇒ **一律以 WASAPI 的 `EnumAudioEndpoints` / `GetState` / `GetDefaultAudioEndpoint` 为准**；
注册表只配当线索。**只看注册表就会把"0 个活动录音端点"读成"有麦克风"。**

### 5.5 未验清单（**不许在别处改写成"能"**）

| # | 没验的东西 | 卡在哪 |
|---|---|---|
| 1 | **真出声**（`voice` 的 `op=tts`，SAPI 朗诵） | **未验（会出声打扰，未在无人时执行）**，且缺 `audio_output`（一次性授权，本机 `grants_available 0`）⇒ 不绕门 |
| 2 | `out` **落盘 WAV** 分支 | 要 `filesystem_write` + `audio_output` 双授权 ⇒ **未执行**（会写盘的状态变更，不擅自动） |
| 3 | `voice` 参数（换发音人） | 同 #1，进不去门 |
| 4 | **ASR 真转写** | 缺 `GBT_ASR_BASE_URL` / `GBT_ASR_API_KEY`（另有外部服务与联网依赖）⇒ 只验到 `needs_dependency` 那一支 |
| 5 | **WASAPI 回环采集**（"听电脑在放什么"） | 走触手能力位要 **`desktop_control`**（**一次性授权**）；本会话实测**被门拒**（`auth_denied`，未执行、未消耗），且**不为验读数去消耗主人的一次性授权** ⇒ **未验 · 卡在 `desktop_control` 一次性授权**。在册实测口径（`48000Hz`/`2ch`/`32bit`，放 440Hz 时峰值 `32767`、均方根 `17750.8`）**引自 `wasapi_loop.py` 与 `gbt-tentacle` §4，不是本次亲测** |
| 6 | **麦克风采集**（`audio_record source=mic`） | 同 #5（`desktop_control`）+ 活动录音端点 0 ⇒ 双重卡住 |
| 7 | `voice_orchestra` 那 **17 项技能真跑起来** | 只验到 `status` 的 `find_spec` 探测；**模型权重 / 显存 / 各项目运行环境一概未验** |
| 8 | 触手音频四件套（`audio_devices` / `audio_voices` / `audio_loopback` / `audio_record`）经能力位的现场读数 | 本会话两发（`audio_devices`、`audio_voices`）实测 `status denied` · `stamp false` · `missing_scopes ["desktop_control"]` · exit 1。**被门拒 = `auth_denied` = 没有执行 = 没有消耗授权**（审计口径**只认 `auth_consumed` 那一条**；本会话 `grants_available` 全程 0）。**未验 · 卡在 `desktop_control` 一次性授权** |

**这份账与 §2 的"真跑过"是两回事**：§2 的每一条都有真实返回字段撑着；本表 8 条**都没有**。

---

## 6. 用法纪律（照做）

1. **调之前先静态查门**（`policy.evaluate(kind, payload).scopes`），别用"撞一次门"当发现手段。
2. **只读档必须显式写 `op`**：`voice` 用 `{"op":"status"}` / `{"op":"asr",…}`；
   `voice_orchestra` 用 `list` / `pipeline` / `status`。**空参 `voice` = tts = 要授权**。
3. **出声先问主人**：`tts` 会真的从扬声器念出来，**会打扰人**；且要 `audio_output`（**一次性、默认 10 分钟**）。
   **没授权就说"缺 `audio_output` + 给出主人要跑的那一行"，不许绕门。**
4. **要授权的不许绕**：报 `missing_scopes` / `reason` / `how_to_grant` 原文，本体读数写"未验"并说明缺哪个作用域。
5. **别把"图鉴 `safe: true`"当"免授权"**，也别把 `local_backends` 的 `true` 当"技能都能跑"。
6. **"做不了"与"被门拒"要分清**：`ok:false + unavailable:true + denied:false`（缺 scene / 域写错）≠ `status:"denied"`。
7. **失败就如实报缺什么**，不找旁路、不改 `security/policy.py`、不给自己发授权。

---

## 7. 验收（做完怎么证明真的做了）

1. **机器复核**：

   ```powershell
   py -3.14 tools/codex-scripts/verify-distill.py --domain voice --skill gbt-voice
   ```

   本器判五件事：A 两份产物在不在且**逐字节相同**；B frontmatter 有 `name` / `description`；
   C 这个域在 `omni.py` 的 `DISTILLED_DOMAINS` 里**已登记**；D 规程里每一发
   `five-dim.py cap <能力位>` 的能力位**在图鉴里真存在**（抓编造命令）；
   E 这个域的**每一个**能力位都被点到（抓遗漏）。**未判**的部分（叙述质量、坑写得准不准）它**不假装能判**。
2. **两份产物逐字节相同**（`Get-FileHash` / `sha256` 比对，见 §8）。
3. **§2 的每一条都是真跑过的**，返回字段照抄；§5.5 的 8 条都是真没验的，不许在别处写成"能"。
4. **本域两个能力位都要真跑**（都零作用域，没有借口）：`cap voice_orchestra` 与
   `cap voice '{"op":"status"}'` —— **"没授权"不能成为"没跑只读档"的借口**。

---

## 8. 固化与出处

| 什么 | 在哪 |
|---|---|
| 本规程（源） | `<仓>/skills/gbt-voice/SKILL.md` |
| 本规程（装机） | `~/.openclaw-autoclaw/skills/gbt-voice/SKILL.md`（**不写 `~/.agents/skills/`** —— 工作区 `AGENTS.md` 明令禁止） |
| 能力源码 | `gbt_allinone/voice_cap.py`（`voice`）· `gbt_allinone/voice_orchestra.py`（`voice_orchestra`，含 17 项 `VOICE_SKILL_REGISTRY` 与六个场景 Pipeline） |
| 门（静态作用域） | `gbt_allinone/security/policy.py`（`kind == "voice"` 与 `kind == "voice_orchestra"` 两段） |
| 调用入口 | `gbt_allinone/api.py`（`kind == "voice"` / `kind == "voice_orchestra"` 两段，参数映射与空参默认 op） |
| 万能插包装器 | `tools/codex-scripts/five-dim.py`（`cap` 分支；**扁平信封的读法**与 **1500 字符截断**都在这里） |
| 音频链路（旁系，不属本域） | `gbt_allinone/tentacle/omni_audio.py` · `gbt_allinone/tentacle/wasapi_loop.py` · 规程 `skills/gbt-tentacle/SKILL.md` |
| 图鉴（唯一真相） | `state/skill_atlas.json`（`domain == "voice"` 的 2 个 `kind`） |

**依赖清单（照实写）**：

- `voice` 出声：**Windows SAPI**（`comtypes.client.CreateObject("SAPI.SpVoice")`；落盘走 `SAPI.SpFileStream`）
  → 依赖**本机有活动渲染端点**（实测 1 个）与 **`audio_output` 授权**。
- `voice` 识别：**外部 ASR 服务**（OpenAI 兼容 `/audio/transcriptions`）+ 环境变量
  `GBT_ASR_BASE_URL` / `GBT_ASR_API_KEY`（可选 `GBT_ASR_MODEL`）—— **本机未配**。
- `voice_orchestra`：**零外部依赖**（读仓内常量表），只用 stdlib 的 `importlib.util.find_spec` 探包。

> 开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属
