---
name: gbt-voice-studio
description: 本地语音一体化规程（蒸馏自 cerebral-work/VoiceStudio）—— 复刻/设计/配音/听写/有声书一条龙，含 agent 面（Local API & MCP）与 recipes/watch folders。当用户说「语音复刻 / 克隆声音 / 配音 / 听写 / 字幕转写 / 有声书 / VoiceStudio / 多语言配音」时使用。
---

# gbt-voice-studio · 本地语音一体化（能力不设限 · 红线=授权与不出网）

**出处**：https://github.com/cerebral-work/VoiceStudio （README 现读 HTTP 200 · 8,160 字符）
上游口径：**Open-source voice cloning, voice design, video dubbing, dictation, transcription &
audiobook creation in 646 languages**；三栏 Create / Produce / **Connect（Local API & MCP for agents、
reusable recipes、watch folders）**；默认引擎 k2-fsa/OmniVoice；安装为 **macOS/Linux 一键**（**本机 Windows 口径不符**）。

## 三档选面（先判再动）

1. **只要出声**（播报/朗读）⇒ 直接用 `voice`（Windows SAPI，已实测真出声）；
2. **要复刻 / 设计 / 多语言 / 配音 / 听写** ⇒ 需要语音引擎：**本机现读无此类引擎**，
   且上游安装是 macOS/Linux 口径 ⇒ **Windows 要另找路，装之前必须主人点头**（网络 + 磁盘 + 依赖）；
3. **要 agent 面**（让别的 agent 调）⇒ 走 `omni_plug` 插座（process/api）或 MCP（本机现读 **无健康 MCP**）。

## 四条红线（照本仓口径，不是自我设限）

1. **声纹 = 生物特征**：复刻/克隆**任何人的声音都必须主人授权**（走 `privacy_read`；缺授权就拒，不绕）；
2. **音源不出网**：本地音频/文本**不上传**任何第三方（要出网先问主人）；
3. **可指回**：每份产出记 **引擎 + 参数 + 输入指纹**（否则无法复核）；
4. **不谎报能力**：麦克风现状如实（本机实测 **活动录音端点 0** ⇒ 听写/采集类**当前不可用**，
   这是设备状态，不是「没有麦克风硬件」）。

## 与她已有位的分工

- `voice`（SAPI 出声 + ASR 入口）：**本件第 1 档就走它**，不重复造；
- `voice_orchestra`：17 项语音技能原子的**只读检索**（先查它有没有现成件，再决定要不要装新引擎）；
- `filmkit` / `chengfeng` / `hyperframes-audio`：**出片侧的音频加工**；本件管「语音生成与复刻」这条；
- 课程对照：Hands-on-AA **ch12 多模态智能体**。

## 判据（可机检）

- 出声类：`voice` 调用返回后**必须**有音频设备回执（无回执 = 未出声，不许当成功）；
- 复刻类：产出必须带 **授权号**（`auth_consumed`）+ 引擎名 + 参数；缺一 => 标「未验」；
- 采集类：先读录音端点；**0 个就如实报不可用**（不许硬跑出空结果当绿）。

## 边界与回滚

- 安装引擎属**新增能力**，按「新增即清旧」同一步清理被取代的旧件并记账；
- 回滚：删除本目录即恢复（本件不装任何东西、不改系统）。

> 开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属
