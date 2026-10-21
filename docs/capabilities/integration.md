# 集成（飞书/Notion/CLI） · `integration`（7 位）

> 自动生成，数据源 `gbt_allinone/caps_registry.py`。只读 = 不改状态、不出网；其余调用前需人工授权（作用域门）。参数以 `requires_params` 标出。

| 能力位 | 类型 | 需参数 | 它做什么 |
|---|---|---|---|
| `cli_chat` | **需授权** | — | 外部 CLI 助手**对话面板**（把「集成」面板真的接到对话上）：`agents` 只读底表（装没装/版本/**能不能一次性驱动**/一次形态）· `send` **真发一句话**给选定的 CLI 助手（claude `-p` / codebuddy `-p` / codex… |
| `cli_ify` | **需授权** | — | **软件命令化**（主人令 2026-10-16 深度蒸馏自 HKUDS/CLI-Anything）：上游原文现读（200·80,551 字）后补齐三块——**Agent-Software Gap**（智能体推理强、用真业务软件很差；焦位版重写会丢 90% 功能 ⇒ **包壳不重… |
| `feishu_embed` | 只读 | — | 飞书镶嵌窗口（只读骨架·门）：面板卡⑥，**走浏览器触手不用 API**；四条红线（飞书是副本本地是源/凭据不许明文/不绕验证/每次操作留痕 source_kind=feishu） |
| `notion_bridge` | **需授权** | — | Notion 资料舱（只读状态/最近页面/搜索/页面正文提取；凭证只从 env 或保险箱读）：status/recent/search/page。**F12 补齐** —— 这个模块有 run()、却没在册，门看不见它；现在按唯一门接线（safe=false：会出网读外部资料）。 |
| `telegram_embed` | 只读 | — | Telegram 镶嵌窗口（只读骨架·门）：面板卡⑧，**默认走浏览器触手**（Bot API 要 bot 身份，跟「你这个号」不是一回事 ⇒ 只作可选支路，token 只从 env/DPAPI 读）；四条红线（Telegram是副本本地是源/凭据不许明文/不绕验证/每次操作留痕… |
| `thebrain_bridge` | **需授权** | — | TheBrain 15 思维导图**接入桥**（把图集成进框架 + 把 AI 连上，**过变压器**）：`status` 探针（TheBrain 装/跑 · 数据面 Brain.db/MetaDB/AiConversations · Orion · 我们的 AI 端点 · 变压器… |
| `whatsapp_embed` | 只读 | — | WhatsApp 镶嵌窗口（只读骨架·门）：面板卡⑦，**走浏览器触手不用 API**（官方 API 走 Business 账号+独立号码，不是「你这个号」）；四条红线（WhatsApp是副本本地是源/凭据不许明文/不绕验证/每次操作留痕 source_kind=whatsapp… |

> 表格里是**摘要**（超过 140 字截断）；完整原文见 [`data/capabilities.json`](../../data/capabilities.json) 的 `desc` 字段。

---

返回 [能力总表](../03-capabilities.md)
