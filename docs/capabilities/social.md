# 社交发布 · `social`（2 位）

> 自动生成，数据源 `gbt_allinone/caps_registry.py`。只读 = 不改状态、不出网；其余调用前需人工授权（作用域门）。参数以 `requires_params` 标出。

| 能力位 | 类型 | 需参数 | 它做什么 |
|---|---|---|---|
| `auto_publish` | 只读 | — | 社交推广 / 发布作品 / 收益平台·**全自动执行**（只读骨架·门）：五原语 PLAN/COMPOSE/PUBLISH/TRACK/SETTLE；核心口径 = **全自动 = 除「发布/提现/改价」之外全自动**（那几下不可逆+涉钱 ⇒ 必须过门：逐条确认或有 TTL 的令牌… |
| `eigenflux` | 只读 | — | AI 朋友圈（EigenFlux）· **只读能力位**（主人令 2026-10-08「数字人可以自己找朋友、看朋友圈有没有好玩和有用的消息」）：op=status/feed/friends/candidates/digest/metadata/where。一律**现读** `~… |

> 表格里是**摘要**（超过 140 字截断）；下面每位还有**逐位详解**（完整原文 / 要哪张票 / 真调用命令 / 缺什么会怎么报）。

---

## 逐位详解

### `auto_publish`

- **域**：`social`（社交发布）
- **类型**：只读（不改状态、不出网） · **需参数**：否
- **要哪张票（静态）**：零作用域（空 payload 下不需要票）
- **它做什么**：社交推广 / 发布作品 / 收益平台·**全自动执行**（只读骨架·门）：五原语 PLAN/COMPOSE/PUBLISH/TRACK/SETTLE；核心口径 = **全自动 = 除「发布/提现/改价」之外全自动**（那几下不可逆+涉钱 ⇒ 必须过门：逐条确认或有 TTL 的令牌，默认 0 张）；六条红线（发布过门/密钥DPAPI/每次留痕 source_kind=publish/一人一号/收益只汇总不代提/不刷量）；平台名单**主人未给 ⇒ 一个平台名都不编**；type=external
- **怎么调**：`py -3.14 tools/codex-scripts/five-dim.py cap auto_publish '<json>'`
- **失败三态**（本仓统一口径，不是这一位特有）：`denied` = 缺票，会点名`missing_scopes`；`needs_*` = 缺参/缺依赖，会带原因；`failed` = 真失败，回执带上游原话。**信封 `status=ok` ≠ 本体 `ok=true`。**

### `eigenflux`

- **域**：`social`（社交发布）
- **类型**：只读（不改状态、不出网） · **需参数**：否
- **要哪张票（静态）**：零作用域（空 payload 下不需要票）
- **它做什么**：AI 朋友圈（EigenFlux）· **只读能力位**（主人令 2026-10-08「数字人可以自己找朋友、看朋友圈有没有好玩和有用的消息」）：op=status/feed/friends/candidates/digest/metadata/where。一律**现读** `~/.eigenflux/servers/eigenflux/**` 本地数据面（feed/私信/contacts/profile），**零出网**（不调 eigenflux CLI）、**零写面**、**零 policy 条目**（读类直连）；candidates 由 feed(author_agent_id)+私信(sender_id)+contacts **结构性推导**，每条附 basis；digest 打分规则写死（兴趣簇/趣味标记/新鲜度/可互动）逐条带 evidence；**对外写动作（加好友/发私信/关注/广播）不在此件、必须过既有门**；读不到一律如实报**未探测/无数据**，**不许占位、不许折绿**
- **怎么调**：`py -3.14 tools/codex-scripts/five-dim.py cap eigenflux '<json>'`
- **失败三态**（本仓统一口径，不是这一位特有）：`denied` = 缺票，会点名`missing_scopes`；`needs_*` = 缺参/缺依赖，会带原因；`failed` = 真失败，回执带上游原话。**信封 `status=ok` ≠ 本体 `ok=true`。**

---

返回 [能力总表](../03-capabilities.md)
