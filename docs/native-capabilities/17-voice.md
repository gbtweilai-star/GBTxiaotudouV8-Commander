# 17 · 语音能力 (`voice`)

> 5+ 能力位 · TTS/ASR · 语音工作室 · 管弦乐 · WASAPI回环
>
> 开发者：自由的风 · 本署名不可删除、不可篡改归属

---

## 能力清单

| 能力位 | 说明 |
|---|---|
| `voice` | 语音合成/识别（需TTS/ASR后端） |
| `voice_studio` | 语音工作室（多引擎、多音色、多语言） |
| `voice_orchestra` | 语音管弦乐（多角色对话编排） |
| `hf_voice` | 火山引擎语音 |
| `audio_extract` | 音频提取（视频→音频） |
| `audio_mix` | 音频混音 |
| `silero_vad` | 语音活动检测（Silero VAD） |
| `wasapi_loop` | WASAPI系统音频回环采集 |

## 三工作流

### 工作流1 · 语音对讲

```
麦克风 → WASAPI采集 → Silero VAD → ASR → LLM → TTS → 扬声器
```

### 工作流2 · 语音合成（配音）

```
文本 → 分句 → TTS多音色 → 混音 → 输出音频
```

### 工作流3 · 多角色对话（管弦乐）

```
剧本 → 角色分配 → 多音色TTS → 时间轴对齐 → 混音 → 成品
```

## API参考

### TTS合成

```python
import gbt_allinone as gbt

result = gbt.run_task("voice", {
    "op": "tts",
    "text": "你好，我是GBT小土豆V8",
    "voice": "zh-CN-XiaoxiaoNeural"
})
# 返回: {ok, path: "store/audio/tts_xxx.mp3", ms: 1200, duration: 2.5}
```

### ASR识别

```python
result = gbt.run_task("voice", {
    "op": "asr",
    "audio": "store/audio/record.wav"
})
# 返回: {ok, text: "识别出的文本", conf: 0.95}
```

### 语音工作室

```python
# 多引擎
gbt.run_task("voice_studio", {"op": "engines"})
# 返回: {ok, engines: [{name: "edge-tts", langs: [...], voices: [...]}]}

# 多音色
gbt.run_task("voice_studio", {"op": "voices", "lang": "zh-CN"})

# 合成（带情感）
gbt.run_task("voice_studio", {
    "op": "synthesize",
    "text": "今天天气真好",
    "voice": "zh-CN-XiaoxiaoNeural",
    "style": "cheerful",
    "rate": "+10%"
})
```

### 多角色对话

```python
result = gbt.run_task("voice_orchestra", {
    "script": [
        {"role": "旁白", "text": "很久以前...", "voice": "zh-CN-YunxiNeural"},
        {"role": "主角", "text": "我要去冒险！", "voice": "zh-CN-XiaoxiaoNeural"},
        {"role": "旁白", "text": "于是他出发了。", "voice": "zh-CN-YunxiNeural"}
    ],
    "out": "story.mp3"
})
```

### WASAPI回环采集

```python
# 采集系统音频（不需虚拟声卡）
result = gbt.run_task("tentacle", {
    "action": "audio_capture",
    "duration": 10,
    "out": "store/audio/system.wav"
})
```

### VAD语音活动检测

```python
result = gbt.run_task("voice", {
    "op": "vad",
    "audio": "store/audio/record.wav"
})
# 返回: {ok, segments: [{start: 0.5, end: 2.3}, {start: 3.1, end: 5.0}]}
```

## 后端依赖

| 后端 | 用途 | 环境变量 |
|---|---|---|
| Edge TTS | 免费TTS（微软） | 无需密钥 |
| Azure TTS | 高质量TTS | `AZURE_SPEECH_KEY` |
| 火山引擎 | 中文TTS | `HF_APP_ID` + `HF_ACCESS_KEY` |
| OpenAI TTS | 多语言TTS | `OPENAI_API_KEY` |
| Whisper | ASR | 本地安装 |
| Azure ASR | 云ASR | `AZURE_SPEECH_KEY` |

## 授权门

| 作用域 | 覆盖 |
|---|---|
| `audio_output` | 让本机发声（TTS合成/播放）或写入音频产物 |
| `privacy_read` | 读取麦克风 |

**实测教训**：改前一次性消耗授权放在`audio_output`上，等于"每说一句话回终端敲一次YES"，语音对讲在物理上不可用。现已改为**时段授权**（TTL内可多次用）。

## 性能

| 操作 | 耗时 |
|---|---|
| Edge TTS（短句） | ~800ms |
| Azure TTS（短句） | ~1.2s |
| Whisper ASR（10s音频） | ~2s（CPU）/ ~0.5s（GPU） |
| VAD（10s音频） | ~50ms |

> 开发者：自由的风 · GBT小土豆V8 · 独立私人框架，与任何企业公司无关
