# 164 · 语音设置（我们自己的 P1）

> 主人 P1：「语音设置页」。
> 对照上游参考项目「设置 → 语音识别 / TTS Provider / 音色 / 参数」：只取**设置契约**，不搬它的 Provider/SDK。
> 落成我们自己的本地设置：TTS 音色/语速/音高/音量 + ASR 后端（auto/whisper/windows）+ 语言 + 自动朗读。

## 一、四件

| 件 | 落点 |
|---|---|
| 模块/契约 | [`gbt_allinone/tools/voice_settings.py`](../../gbt_allinone/tools/voice_settings.py) · `verify()` **16 项** · `schema/validate/resolve/verify` |
| 统一门 | 注册能力位 **`voice_settings`**（`run_task("voice_settings", …)`；纯校验/解析 zero-scope，`policy.py` 未改） |
| API | `GET/POST /api/voice/settings`：读取设置 + schema；保存前走统一门 `validate`，以 trusted-owner 写 `state/voice-settings.json`，追加 `outputs/voice-settings/audit.jsonl` |
| APP 接线 | 数字人页 ⚙「语音设置」弹窗：音色下拉（系统 zh 声库）/ 语速 / 音高 / ASR 后端 / 自动朗读；保存立即生效 |
| 验收 | [`tests/test_voice_settings.py`](../../tests/test_voice_settings.py) |

## 二、实际行为

- **音色解析**：显式音色匹配 → 否则偏好 `Hanhan → Yating → Huihui → Yaoyao → Xiaoxiao`；空声库不报错也不回退英文；
- **朗读**：数字人 `speak()` 用设置里的 `tts_rate/tts_pitch/tts_volume`，`auto_speak=false` 只出字幕不出声；
- **ASR 后端**：`auto`=Whisper 优先/失败回 Windows；`whisper`=只走 Whisper，失败如实报、不偷偷降级；`windows`=只系统识别器；
- **持久化**：写入 `state/voice-settings.json`（原子替换），读不到/坏文件回默认，不崩。

## 三、真机读数（2026-11-02 APP）

| 项 | 读数 |
|---|---|
| `GET /api/voice/settings` | 默认 `auto` / 0.98 / 1.0 / 1.0 / auto_speak=true |
| `POST save` | 保存 `Huihui + rate 1.1` → `ok=true`，文件落盘 `state/voice-settings.json` |
| 坏值 | `tts_rate=9` → `user_error: tts_rate 范围 0.50..1.50`（不落盘） |
| 设置弹窗 | 打开后 7 个音色选项；选中 `Huihui`、语速 1.10；`__DH.speak` 拦截到 `voice=Huihui · rate=1.1` |
| 统一门 | `run_task("voice_settings", {"op":"verify"})` 可达；能力数 392 |

![数字人语音设置（APP 真机：音色/语速/音高/ASR 后端/自动朗读）](../assets/app-voice-settings.png)

## 四、边界（说死）

1. 设置是**本地行为参数**，不引入云 Provider/凭证；要接第三方 TTS/ASR 时另开设置项与门，不在这里偷加；
2. 音色列表来自**系统声库**（Electron `speechSynthesis`），不同机器不同；
3. 写盘走 console-server 的 trusted-owner 本地设置面（与现有设置同一条），能力位本身 zero-scope；
4. ASR 后端选择只影响 `/api/asr` 的上传 WAV 路径；麦克风设备选择未做（后续）；
5. 设置立即影响数字人；已开始的朗读不追溯。

## 五、复跑

```bash
py -3.14 -X utf8 tests/test_voice_settings.py
# APP 数字人页 → ⚙ → 改音色/语速 → 保存
# GET/POST http://127.0.0.1:8766/api/voice/settings
```

> 开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属
