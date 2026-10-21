# 语音 · `voice`（4 位）

> 自动生成，数据源 `gbt_allinone/caps_registry.py`。只读 = 不改状态、不出网；其余调用前需人工授权（作用域门）。参数以 `requires_params` 标出。

| 能力位 | 类型 | 需参数 | 它做什么 |
|---|---|---|---|
| `hf_voice` | 只读 | — | Hugging Face 歌声/语音（**3 臂轮询**，主人令 2026-09-28「把插件连接好部署语音…安装 3 个这个插件轮询使用避免卡壳」）：本机零算力跑不动歌声合成（语音中枢 v2.0 一手实测）⇒ 真唱走云。**3 臂（hf-1/2/3）按轮询 + 冷却换道**用（… |
| `voice` | 只读 | — | 语音合成/识别入口（良性子集） |
| `voice_orchestra` | 只读 | — | 语音技能中枢（多维度场景编排，只读）：技能原子检索 / 场景 Pipeline / 本机可跑性；今日挂 tools tab，升格条件见模块 docstring |
| `voice_studio` | 只读 | — | VoiceStudio（debpalash · AGPL-3.0 · 只蒸馏思想不搬代码）**两层面**。① **桥接面**（要上游后端在线）：status/capabilities/transcribe/plan/mcp_info/where —— 上游 Local API 现… |

> 表格里是**摘要**（超过 140 字截断）；完整原文见 [`data/capabilities.json`](../../data/capabilities.json) 的 `desc` 字段。

---

返回 [能力总表](../03-capabilities.md)
