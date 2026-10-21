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

> 表格里是**摘要**（超过 140 字截断）；下面每位还有**逐位详解**（完整原文 / 要哪张票 / 真调用命令 / 缺什么会怎么报）。

---

## 逐位详解

### `cli_chat`

- **域**：`integration`（集成（飞书/Notion/CLI））
- **类型**：**需授权**（会写盘 / 花钱 / 出网） · **需参数**：否
- **要哪张票（静态）**：零作用域（空 payload 下不需要票）
- **它做什么**：外部 CLI 助手**对话面板**（把「集成」面板真的接到对话上）：`agents` 只读底表（装没装/版本/**能不能一次性驱动**/一次形态）· `send` **真发一句话**给选定的 CLI 助手（claude `-p` / codebuddy `-p` / codex `exec` / copilot `-p`，形态**现跑 --help 亲验**）· `transcript` 会话账 · `verify`/`where`。**「免费」的确切含义**：走各 CLI **自己的登录态/额度**（订阅额度），不经框架 API key ⇒ **不吃 API 账单**（≠ 无额度上限）。⚠️ 与 freebuff 的**本质差别**：这 4 位**都有**非交互一次性入口（freebuff 是 TUI-only）⇒ 面板**能真聊**。⚠️ `send` = 起外部进程 + 把 prompt 送出本机 ⇒ 挂 `process_execute`+`external_llm`；policy.py 无本位分支（owner-only，AI 无权改）⇒ 门在模块内自闸（auth_gate 唯一校验入口），缺授权如实报缺。未装位/图形位 fail-closed 如实报缺 + 给装法，**不编**。safe=false：send 起进程且内容出本机（不是纯只读面）。type=internal
- **怎么调**：`py -3.14 tools/codex-scripts/five-dim.py cap cli_chat '<json>'`
- **失败三态**（本仓统一口径，不是这一位特有）：`denied` = 缺票，会点名`missing_scopes`；`needs_*` = 缺参/缺依赖，会带原因；`failed` = 真失败，回执带上游原话。**信封 `status=ok` ≠ 本体 `ok=true`。**

### `cli_ify`

- **域**：`integration`（集成（飞书/Notion/CLI））
- **类型**：**需授权**（会写盘 / 花钱 / 出网） · **需参数**：否
- **要哪张票（静态）**：零作用域（空 payload 下不需要票）
- **它做什么**：**软件命令化**（主人令 2026-10-16 深度蒸馏自 HKUDS/CLI-Anything）：上游原文现读（200·80,551 字）后补齐三块——**Agent-Software Gap**（智能体推理强、用真业务软件很差；焦位版重写会丢 90% 功能 ⇒ **包壳不重写**）· **7 相流水线**（Analyze→Design→Implement→Plan Tests→Write Tests→Docs→Publish）· **CLI-Hub 注册表**（对应本仓 state/cli-surfaces.json）。op=status/gate/plan/registry/check/gap（**全只读·零作用域**）。
- **怎么调**：`py -3.14 tools/codex-scripts/five-dim.py cap cli_ify '<json>'`
- **失败三态**（本仓统一口径，不是这一位特有）：`denied` = 缺票，会点名`missing_scopes`；`needs_*` = 缺参/缺依赖，会带原因；`failed` = 真失败，回执带上游原话。**信封 `status=ok` ≠ 本体 `ok=true`。**

### `feishu_embed`

- **域**：`integration`（集成（飞书/Notion/CLI））
- **类型**：只读（不改状态、不出网） · **需参数**：否
- **要哪张票（静态）**：零作用域（空 payload 下不需要票）
- **它做什么**：飞书镶嵌窗口（只读骨架·门）：面板卡⑥，**走浏览器触手不用 API**；四条红线（飞书是副本本地是源/凭据不许明文/不绕验证/每次操作留痕 source_kind=feishu）
- **怎么调**：`py -3.14 tools/codex-scripts/five-dim.py cap feishu_embed '<json>'`
- **失败三态**（本仓统一口径，不是这一位特有）：`denied` = 缺票，会点名`missing_scopes`；`needs_*` = 缺参/缺依赖，会带原因；`failed` = 真失败，回执带上游原话。**信封 `status=ok` ≠ 本体 `ok=true`。**

### `notion_bridge`

- **域**：`integration`（集成（飞书/Notion/CLI））
- **类型**：**需授权**（会写盘 / 花钱 / 出网） · **需参数**：否
- **要哪张票（静态）**：零作用域（空 payload 下不需要票）
- **它做什么**：Notion 资料舱（只读状态/最近页面/搜索/页面正文提取；凭证只从 env 或保险箱读）：status/recent/search/page。**F12 补齐** —— 这个模块有 run()、却没在册，门看不见它；现在按唯一门接线（safe=false：会出网读外部资料）。
- **怎么调**：`py -3.14 tools/codex-scripts/five-dim.py cap notion_bridge '<json>'`
- **失败三态**（本仓统一口径，不是这一位特有）：`denied` = 缺票，会点名`missing_scopes`；`needs_*` = 缺参/缺依赖，会带原因；`failed` = 真失败，回执带上游原话。**信封 `status=ok` ≠ 本体 `ok=true`。**

### `telegram_embed`

- **域**：`integration`（集成（飞书/Notion/CLI））
- **类型**：只读（不改状态、不出网） · **需参数**：否
- **要哪张票（静态）**：零作用域（空 payload 下不需要票）
- **它做什么**：Telegram 镶嵌窗口（只读骨架·门）：面板卡⑧，**默认走浏览器触手**（Bot API 要 bot 身份，跟「你这个号」不是一回事 ⇒ 只作可选支路，token 只从 env/DPAPI 读）；四条红线（Telegram是副本本地是源/凭据不许明文/不绕验证/每次操作留痕 source_kind=telegram）；**发消息停授权门**
- **怎么调**：`py -3.14 tools/codex-scripts/five-dim.py cap telegram_embed '<json>'`
- **失败三态**（本仓统一口径，不是这一位特有）：`denied` = 缺票，会点名`missing_scopes`；`needs_*` = 缺参/缺依赖，会带原因；`failed` = 真失败，回执带上游原话。**信封 `status=ok` ≠ 本体 `ok=true`。**

### `thebrain_bridge`

- **域**：`integration`（集成（飞书/Notion/CLI））
- **类型**：**需授权**（会写盘 / 花钱 / 出网） · **需参数**：否
- **要哪张票（静态）**：零作用域（空 payload 下不需要票）
- **它做什么**：TheBrain 15 思维导图**接入桥**（把图集成进框架 + 把 AI 连上，**过变压器**）：`status` 探针（TheBrain 装/跑 · 数据面 Brain.db/MetaDB/AiConversations · Orion · 我们的 AI 端点 · 变压器，只读）· `graph`/`search`/`notes` 读思维导图（**离线直读 Brain.db（mode=ro）优先**，每个节点边都带 `source` 出处 —— 照 brain_graph 铁律：指不出的不画）· `ask`/`summarize` **把 AI 连接上且过变压器**：图上下文 → `transformer.compress`（省 token）→ `cache_get`（省调用）→ `llm/unified.ask`（真模型）→ `cache_put`，**给前后两个数** · `endpoint` 报告「TheBrain 的 AI 该填什么」+ 变压器前置端点形态 · `serve` 起**变压器前置的 OpenAI 兼容端点**（TheBrain 指向它 ⇒ 每次请求先过变压器，链路：TheBrain → 本端点 → 127.0.0.1:31716 桥 → 网关 → 模型）· `think`/`link` 写回（Orion）· `verify`/`where`。⚠️ 关键事实：TheBrain 后端带 OpenAI.dll/Anthropic.dll（OpenAI 兼容），框架**已有** OpenAI 兼容端点 127.0.0.1:31716（llm/genoffice_bridge）—— 但**不过变压器**；本模块补的就是这一环（这就是主人「用变压器连接上」的落点）。⚠️ 未订阅 ⇒ TheBrain 自带 AI 面不可用（preferences.message="No active subscription found."）。⚠️ 红线：**不改 Brain.db**（mode=ro）· **不写 TheBrain 配置** · **不回显凭据明文**（只给指纹）。写面/真调 = 出网/触外部 ⇒ `ask` 挂 `external_llm`、`think`/`link`/`serve` 挂 `process_execute`；policy.py 无本位分支（owner-only，AI 无权改）⇒ 门在模块内自闸（auth_gate 唯一校验入口），缺授权如实报缺。safe=false。type=internal
- **怎么调**：`py -3.14 tools/codex-scripts/five-dim.py cap thebrain_bridge '<json>'`
- **失败三态**（本仓统一口径，不是这一位特有）：`denied` = 缺票，会点名`missing_scopes`；`needs_*` = 缺参/缺依赖，会带原因；`failed` = 真失败，回执带上游原话。**信封 `status=ok` ≠ 本体 `ok=true`。**

### `whatsapp_embed`

- **域**：`integration`（集成（飞书/Notion/CLI））
- **类型**：只读（不改状态、不出网） · **需参数**：否
- **要哪张票（静态）**：零作用域（空 payload 下不需要票）
- **它做什么**：WhatsApp 镶嵌窗口（只读骨架·门）：面板卡⑦，**走浏览器触手不用 API**（官方 API 走 Business 账号+独立号码，不是「你这个号」）；四条红线（WhatsApp是副本本地是源/凭据不许明文/不绕验证/每次操作留痕 source_kind=whatsapp）；**发消息是不可逆动作 ⇒ 停在授权门前**
- **怎么调**：`py -3.14 tools/codex-scripts/five-dim.py cap whatsapp_embed '<json>'`
- **失败三态**（本仓统一口径，不是这一位特有）：`denied` = 缺票，会点名`missing_scopes`；`needs_*` = 缺参/缺依赖，会带原因；`failed` = 真失败，回执带上游原话。**信封 `status=ok` ≠ 本体 `ok=true`。**

---

返回 [能力总表](../03-capabilities.md)
