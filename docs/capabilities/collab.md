# 协作（信息素场地） · `collab`（2 位）

> 自动生成，数据源 `gbt_allinone/caps_registry.py`。只读 = 不改状态、不出网；其余调用前需人工授权（作用域门）。参数以 `requires_params` 标出。

| 能力位 | 类型 | 需参数 | 它做什么 |
|---|---|---|---|
| `collab_gateway` | **需授权** | — | 协作网关（多智能体会话/信箱/同伴注册）：open_session/close_session/status/inbox/register_peer/peer_status/request_peer/server_status/start_server。**F12 补齐**：同上… |
| `stigmergy` | 只读 | — | **协作层的间接通道**：Stigmergy（共识主动性 / 信息素场地）。四原语 DEPOSIT/READ/DECAY/FORAGE；只有 DEPOSIT 会写、且**只追加**（挥发是读数，账本可回放）。五条红线做成机械闸：**无源不许留** deposit_without_… |

> 表格里是**摘要**（超过 140 字截断）；下面每位还有**逐位详解**（完整原文 / 要哪张票 / 真调用命令 / 缺什么会怎么报）。

---

## 逐位详解

### `collab_gateway`

- **域**：`collab`（协作（信息素场地））
- **类型**：**需授权**（会写盘 / 花钱 / 出网） · **需参数**：否
- **要哪张票（静态）**：零作用域（空 payload 下不需要票）
- **它做什么**：协作网关（多智能体会话/信箱/同伴注册）：open_session/close_session/status/inbox/register_peer/peer_status/request_peer/server_status/start_server。**F12 补齐**：同上，原先没进注册表 ⇒ 门看不见它。
- **怎么调**：`py -3.14 tools/codex-scripts/five-dim.py cap collab_gateway '<json>'`
- **失败三态**（本仓统一口径，不是这一位特有）：`denied` = 缺票，会点名`missing_scopes`；`needs_*` = 缺参/缺依赖，会带原因；`failed` = 真失败，回执带上游原话。**信封 `status=ok` ≠ 本体 `ok=true`。**

### `stigmergy`

- **域**：`collab`（协作（信息素场地））
- **类型**：只读（不改状态、不出网） · **需参数**：否
- **要哪张票（静态）**：零作用域（空 payload 下不需要票）
- **它做什么**：**协作层的间接通道**：Stigmergy（共识主动性 / 信息素场地）。四原语 DEPOSIT/READ/DECAY/FORAGE；只有 DEPOSIT 会写、且**只追加**（挥发是读数，账本可回放）。五条红线做成机械闸：**无源不许留** deposit_without_source · **种类白名单** deposit_kind_not_allowed · **只追加** pheromone_deleted_or_overwritten（静态核本模块源码）· **不留明文密钥** plaintext_key_in_pheromone · **只给读数**（FORAGE 只排序不执行）。与 collab_gateway **并排、不替代**：直连=会话/对等方/收件箱，间接=信息素场地；场地放在 store/collab/stigmergy/。type=internal
- **怎么调**：`py -3.14 tools/codex-scripts/five-dim.py cap stigmergy '<json>'`
- **失败三态**（本仓统一口径，不是这一位特有）：`denied` = 缺票，会点名`missing_scopes`；`needs_*` = 缺参/缺依赖，会带原因；`failed` = 真失败，回执带上游原话。**信封 `status=ok` ≠ 本体 `ok=true`。**

---

返回 [能力总表](../03-capabilities.md)
