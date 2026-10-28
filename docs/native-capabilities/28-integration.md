# 28 · 集成与协作域 (`integration` / `collab` / `social` / `comms`)

> 12 能力位 · 外部系统接入 · 多智能体协作 · 社交发布 · 通信
>
> 这一域的共同特征：**它们都连向框架外部**——别的软件、别的 AI、别的平台、别的人。
>
> 开发者：自由的风 · 本署名不可删除、不可篡改归属

---

## 能力清单（逐位，取自注册表）

### 集成（integration · 7 位）

| 能力位 | 类型 | 说明 |
|---|---|---|
| `cli_chat` | 需授权 | 外部 CLI 助手**对话面板**：`agents` 只读底表（装没装/版本/能不能用） |
| `cli_ify` | 需授权 | **软件命令化**（蒸馏自 HKUDS/CLI-Anything）：Agent-Software Gap · 7 相流水线 · CLI-Hub 注册表 |
| `feishu_embed` | 只读 | 飞书镶嵌窗口（只读骨架·门）：**走浏览器触手不用 API**；四条红线（飞书是副本本地是源/凭据不许明文/…） |
| `notion_bridge` | 需授权 | Notion 资料舱：只读状态/最近页面/搜索/页面正文提取；凭证只从 env 或保险箱读 |
| `telegram_embed` | 只读 | Telegram 镶嵌窗口（只读骨架·门）：**默认走浏览器触手**（Bot API 要 bot 身份，跟「你」不是同一个） |
| `thebrain_bridge` | 需授权 | TheBrain 15 思维导图**接入桥**：把图集成进框架 + 把 AI 连上，**过变压器** |
| `whatsapp_embed` | 只读 | WhatsApp 镶嵌窗口（只读骨架·门）：**走浏览器触手不用 API**（官方 API 走 Business 身份） |

### 协作（collab · 2 位）

| 能力位 | 类型 | 说明 |
|---|---|---|
| `collab_gateway` | 需授权 | 协作网关（多智能体会话/信箱/同伴注册）：open_session / close_session / status / inbox |
| `stigmergy` | 只读 | **协作层的间接通道**：Stigmergy（共识主动性/信息素场地）。四原语 DEPOSIT / READ / DECAY |

### 社交（social · 2 位）

| 能力位 | 类型 | 说明 |
|---|---|---|
| `auto_publish` | 只读 | 社交推广/发布作品/收益平台·**全自动执行**（只读骨架·门）：五原语 PLAN / COMPOSE / PUBLISH / … |
| `eigenflux` | 只读 | AI 朋友圈（EigenFlux）· **只读能力位**：数字人可以自己找朋友、看朋友圈有什么 |

### 通信（comms · 1 位）

| 能力位 | 类型 | 说明 |
|---|---|---|
| `coze_mail` | 只读 | 对主人自有的单一地址（@coze.email）收发与整理；白名单**默认空（全拒）**、confirm_token 绑定 |

---

## 三条接入路线（选路原则）

```
                    ┌─────────────────────┐
                    │  要接的外部系统      │
                    └──────────┬──────────┘
                               │
              ┌────────────────┼────────────────┐
              │                │                │
    ┌─────────▼──────┐ ┌───────▼───────┐ ┌─────▼──────────┐
    │ 浏览器触手      │ │ 官方 API       │ │ CLI 包壳        │
    │ （不存凭据）    │ │ （要身份/计费）│ │ （不重写）      │
    └────────────────┘ └───────────────┘ └────────────────┘
     飞书/Telegram/       Notion /          cli_chat /
     WhatsApp 都用这条    Coze Mail         cli_ify
```

### 选路判据（写死）

| 条件 | 走哪条 |
|---|---|
| 系统有网页版、且不需要 API 专属身份 | **浏览器触手**（凭据不进框架） |
| 系统只提供 API、且用户已有正式身份 | **官方 API**（凭证从 env / 保险箱读） |
| 系统是本地软件、有 CLI 或能被包壳 | **CLI 包壳**（包壳不重写，焦位版重写会丢 90% 功能） |

---

## API 参考

### 外部 CLI 助手（cli_chat）

```python
import gbt_allinone as gbt

# 只读底表：装没装 / 版本 / 能不能用
result = gbt.run_task("cli_chat", {"op": "agents"})
# 返回: {ok, agents: [{name: "claude", installed: true, version: "..."}, ...]}

# 开一个对话
gbt.run_task("cli_chat", {"op": "open", "agent": "claude"})
```

### 软件命令化（cli_ify）

```python
# 状态与门
gbt.run_task("cli_ify", {"op": "status"})
gbt.run_task("cli_ify", {"op": "gate"})

# 7 相流水线计划
gbt.run_task("cli_ify", {
    "op": "plan",
    "software": "blender",
    "phases": ["Analyze", "Design", "Implement", "PlanTests",
               "WriteTests", "Docs", "Publish"]
})

# 已登记的命令面
gbt.run_task("cli_ify", {"op": "registry"})
```

**核心认知（Agent-Software Gap）**：智能体推理很强，但用真实业务软件很差。**焦位版重写会丢 90% 功能 ⇒ 包壳不重写。**

### Notion 资料舱（notion_bridge）

```python
# 状态（只读）
gbt.run_task("notion_bridge", {"op": "status"})

# 最近页面
gbt.run_task("notion_bridge", {"op": "recent"})

# 搜索
gbt.run_task("notion_bridge", {"op": "search", "q": "项目计划"})

# 页面正文
gbt.run_task("notion_bridge", {"op": "page", "id": "<page_id>"})
```

**凭据纪律**：只从环境变量或保险箱读，**永不落明文**。

### 飞书 / Telegram / WhatsApp 镶嵌（embed 三件）

```python
# 三个都是同一形态：走浏览器触手，不用 API
gbt.run_task("feishu_embed", {"op": "status"})
gbt.run_task("telegram_embed", {"op": "status"})
gbt.run_task("whatsapp_embed", {"op": "status"})
```

**为什么不用 API**：
- Telegram Bot API 要 **bot 身份**，跟「你」不是同一个身份
- WhatsApp 官方 API 要 **Business 身份**，个人号走不了
- 飞书 API 要应用授权，而**本地才是源、飞书是副本**

### TheBrain 思维导图（thebrain_bridge）

```python
gbt.run_task("thebrain_bridge", {"op": "status"})
```

**过变压器**：不直接把图的原始结构塞给 AI，先转成 AI 能理解的分层语义。

### 多智能体协作（collab_gateway）

```python
# 开会话
gbt.run_task("collab_gateway", {"op": "open_session", "topic": "重构讨论"})

# 注册同伴
gbt.run_task("collab_gateway", {"op": "register", "peer": "researcher"})

# 收信箱
gbt.run_task("collab_gateway", {"op": "inbox"})

# 关会话
gbt.run_task("collab_gateway", {"op": "close_session"})
```

### 间接协作通道（stigmergy）

```python
# 留信息素
gbt.run_task("stigmergy", {"op": "DEPOSIT", "field": "refactor", "value": 0.8})

# 读场地
gbt.run_task("stigmergy", {"op": "READ", "field": "refactor"})

# 衰减（时间会让信息素变淡）
gbt.run_task("stigmergy", {"op": "DECAY"})
```

**Stigmergy 是什么**：蚂蚁不直接对话，靠在地上留信息素协作。多智能体也一样——**不需要互相发消息，只需要在同一块场地上留下痕迹**。

### 社交发布（auto_publish）

```python
# 计划
gbt.run_task("auto_publish", {"op": "PLAN", "content": "作品介绍"})

# 编排
gbt.run_task("auto_publish", {"op": "COMPOSE"})

# 发布（需授权）
gbt.run_task("auto_publish", {"op": "PUBLISH", "platform": "..."})
```

### AI 朋友圈（eigenflux）

```python
result = gbt.run_task("eigenflux", {})
# 只读：数字人可以自己找朋友、看朋友圈有什么
```

### 通信（coze_mail）

```python
# 读信
gbt.run_task("coze_mail", {"op": "inbox"})

# 发信（白名单默认空 = 全拒）
gbt.run_task("coze_mail", {
    "op": "send",
    "to": "owner@coze.email",
    "subject": "...",
    "body": "..."
})
```

**白名单默认空（全拒）**：不是"忘了配"，是**故意默认全拒**——要发信必须显式把地址加进白名单 + 带 `confirm_token`。

---

## 安全边界

| 风险 | 措施 |
|---|---|
| 凭据泄漏 | 只从 env / 保险箱读，不落明文、不进仓 |
| 身份混用 | Telegram/WhatsApp 走浏览器触手，不用 bot/Business 身份 |
| 数据外发 | `data_export` / `external_llm` 门 |
| 误发信 | `coze_mail` 白名单默认空 + `confirm_token` |
| 副本与源混淆 | **飞书是副本，本地是源**（红线） |

> 开发者：自由的风 · GBT小土豆V8 · 独立私人框架，与任何企业公司无关
