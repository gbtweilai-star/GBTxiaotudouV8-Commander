# 语音 · `voice`（4 位）

> 自动生成，数据源 `gbt_allinone/caps_registry.py`。只读 = 不改状态、不出网；其余调用前需人工授权（作用域门）。参数以 `requires_params` 标出；**必填载荷**与**常见错误**两列只写注册表登记过的（没登记就写「无必填」/通用三态），不猜。

| 能力位 | 类型 | 需参数 | 必填载荷 | 常见错误 | 它做什么 |
|---|---|---|---|---|---|
| `hf_voice` | 只读 | — | —（空载荷走该位默认 op） | `user_error` | Hugging Face 歌声/语音（**3 臂轮询**，主人令 2026-09-28「把插件连接好部署语音…安装 3 个这个插件轮询使用避免卡壳」）：本机零算力跑不动歌声合成（语音中枢 v2.0 一手实测）⇒ 真唱走云。**3 臂（hf-1/2/3）按轮询 + 冷却换道**用（… |
| `voice` | 只读 | — | —（空载荷走该位默认 op） | `user_error` | 本机语音入口（良性子集）：空 payload 默认落到 TTS，真让本机发声 ⇒ 要 `audio_output`；另有 ASR 入口。本机实测口径：WASAPI 活动渲染端点 1 个、活动录音端点 0 个 ⇒「能出声」已验证，「能听」当前不可用（不是没有麦克风，是录音端点没起来… |
| `voice_orchestra` | 只读 | — | —（空载荷走该位默认 op） | `user_error` | 语音技能中枢（多维度场景编排，只读）：技能原子检索 / 场景 Pipeline / 本机可跑性；今日挂 tools tab，升格条件见模块 docstring |
| `voice_studio` | 只读 | — | —（空载荷走该位默认 op） | `user_error` | VoiceStudio（debpalash · AGPL-3.0 · 只蒸馏思想不搬代码）**两层面**。① **桥接面**（要上游后端在线）：status/capabilities/transcribe/plan/mcp_info/where —— 上游 Local API 现… |

> 表格里是**摘要**（超过 140 字截断）；下面每位还有**逐位详解**（完整原文 / 要哪张票 / 真调用命令 / 缺什么会怎么报）。

---

## 逐位详解

### `hf_voice`

- **域**：`voice`（语音）
- **类型**：只读（不改状态、不出网） · **需参数**：否
- **要哪张票（静态）**：零作用域（空 payload 下不需要票）
- **必填载荷**：无必填（空载荷落到该位默认 op；位内更细的 op 参数见模块）
- **常见错误**：参数非法 → `user_error`
- **它做什么**：Hugging Face 歌声/语音（**3 臂轮询**，主人令 2026-09-28「把插件连接好部署语音…安装 3 个这个插件轮询使用避免卡壳」）：本机零算力跑不动歌声合成（语音中枢 v2.0 一手实测）⇒ 真唱走云。**3 臂（hf-1/2/3）按轮询 + 冷却换道**用（与 key_gateway 同一纪律）：单臂连续失败 3 次冷却 300s、自动投下一臂 ⇒ 避免单点卡壳。**出网硬钉**：只 https + 主机白名单（HF 三个官方域）+ 显式拒私有/环回/保留地址 + 拒重定向；**只回掩码**，密钥只走 env:/vault: 引用。`sing` 过 external_llm 门；模型表全部**未验**（本机无 token）。op=status/arms/models/sing/rotate/verify/where
- **怎么调**：`py -3.14 tools/codex-scripts/five-dim.py cap hf_voice '<json>'`
- **失败三态**（本仓统一口径，不是这一位特有）：`denied` = 缺票，会点名`missing_scopes`；`needs_*` = 缺参/缺依赖，会带原因；`failed` = 真失败，回执带上游原话。**信封 `status=ok` ≠ 本体 `ok=true`。**

### `voice`

- **域**：`voice`（语音）
- **类型**：只读（不改状态、不出网） · **需参数**：否
- **要哪张票（静态）**：`audio_output`
- **必填载荷**：无必填（空载荷落到该位默认 op；位内更细的 op 参数见模块）
- **常见错误**：参数非法 → `user_error`
- **它做什么**：本机语音入口（良性子集）：空 payload 默认落到 TTS，真让本机发声 ⇒ 要 `audio_output`；另有 ASR 入口。本机实测口径：WASAPI 活动渲染端点 1 个、活动录音端点 0 个 ⇒「能出声」已验证，「能听」当前不可用（不是没有麦克风，是录音端点没起来）。
- **怎么调**：`py -3.14 tools/codex-scripts/five-dim.py cap voice '<json>'`
- **失败三态**（本仓统一口径，不是这一位特有）：`denied` = 缺票，会点名`missing_scopes`；`needs_*` = 缺参/缺依赖，会带原因；`failed` = 真失败，回执带上游原话。**信封 `status=ok` ≠ 本体 `ok=true`。**

### `voice_orchestra`

- **域**：`voice`（语音）
- **类型**：只读（不改状态、不出网） · **需参数**：否
- **要哪张票（静态）**：零作用域（空 payload 下不需要票）
- **必填载荷**：无必填（空载荷落到该位默认 op；位内更细的 op 参数见模块）
- **常见错误**：参数非法 → `user_error`
- **它做什么**：语音技能中枢（多维度场景编排，只读）：技能原子检索 / 场景 Pipeline / 本机可跑性；今日挂 tools tab，升格条件见模块 docstring
- **怎么调**：`py -3.14 tools/codex-scripts/five-dim.py cap voice_orchestra '<json>'`
- **失败三态**（本仓统一口径，不是这一位特有）：`denied` = 缺票，会点名`missing_scopes`；`needs_*` = 缺参/缺依赖，会带原因；`failed` = 真失败，回执带上游原话。**信封 `status=ok` ≠ 本体 `ok=true`。**

### `voice_studio`

- **域**：`voice`（语音）
- **类型**：只读（不改状态、不出网） · **需参数**：否
- **要哪张票（静态）**：零作用域（空 payload 下不需要票）
- **必填载荷**：无必填（空载荷落到该位默认 op；位内更细的 op 参数见模块）
- **常见错误**：参数非法 → `user_error`
- **它做什么**：VoiceStudio（debpalash · AGPL-3.0 · 只蒸馏思想不搬代码）**两层面**。① **桥接面**（要上游后端在线）：status/capabilities/transcribe/plan/mcp_info/where —— 上游 Local API 现读**只给「听」不给「说」**（/v1/audio/transcriptions + WS 流式 + MCP，**没有 TTS 端点**，合成在 Electron 应用本体里）⇒ 要出声走 `voice`(SAPI) 或 `hf_voice`(云)，要克隆得上游装应用且声纹需主人授权。② **三工作流面**（AI 短剧/电影/音乐 · **纯本地、零引擎、零出网**）：`cast` 角色↔音色台账（state/voice-cast.json，三工作流共用的音色一致性根）· `align` 音频节奏测绘（ffmpeg→20ms 帧能量→门限切段→每句 start/end/dur，**切不出就报 0 段不编时间轴**）· `fit` 台词→时长预算（CJK 按字/西文按词，给每行秒数与建议语速）· `subtitle` 段+行→SRT（**行数≠段数就拒**，绝不硬配）· `say` 台词→音频（engine=edge 云端 / sapi 本机 / upstream 转发；缺网或缺引擎如实报，音色名不对先拒不去撞网）· `timeline` 每句一音频件→按**实测时长累加**出精确边界与 SRT（`wrap` 按标点折行）· `brief` 三工作流各自的语音配方。写面自收窄在 state/ 与 projects·outputs·.scratch（只有 cast 的 set/rm 与 subtitle 落盘会写，落盘限 projects·outputs·.scratch）。
- **怎么调**：`py -3.14 tools/codex-scripts/five-dim.py cap voice_studio '<json>'`
- **失败三态**（本仓统一口径，不是这一位特有）：`denied` = 缺票，会点名`missing_scopes`；`needs_*` = 缺参/缺依赖，会带原因；`failed` = 真失败，回执带上游原话。**信封 `status=ok` ≠ 本体 `ok=true`。**

---

返回 [能力总表](../03-capabilities.md)
