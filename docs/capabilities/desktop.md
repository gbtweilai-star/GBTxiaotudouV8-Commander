# 桌面智能体 · `desktop`（2 位）

> 自动生成，数据源 `gbt_allinone/caps_registry.py`。只读 = 不改状态、不出网；其余调用前需人工授权（作用域门）。参数以 `requires_params` 标出；**必填载荷**与**常见错误**两列只写注册表登记过的（没登记就写「无必填」/通用三态），不猜。

| 能力位 | 类型 | 需参数 | 必填载荷 | 常见错误 | 它做什么 |
|---|---|---|---|---|---|
| `control_loop` | 只读 | — | —（注册表：无必填） | `user_error` | 快慢双脑控制回路（蒸馏自 Jev/TypeSafe System One + browser-use/jev-ultrafast）：动作是**枚举**（CLICK/TYPE_TEXT/SELECT/SCROLL_*/WAIT/DONE/BLOCKED，枚举外不存在）· 一次观测出… |
| `ul_tars_desktop` | **需授权** | — | —（注册表：无必填） | `user_error` / `failed` | Ul-TARS Desktop desktop agent |

> 表格里是**摘要**（超过 140 字截断）；下面每位还有**逐位详解**（完整原文 / 要哪张票 / 真调用命令 / 缺什么会怎么报）。

---

## 逐位详解

### `control_loop`

- **域**：`desktop`（桌面智能体）
- **类型**：只读（不改状态、不出网） · **需参数**：否
- **要哪张票（静态）**：零作用域（空 payload 下不需要票）
- **必填载荷**：无必填（注册表 `requires_params=false`；空载荷落到该位默认 op）
- **常见错误**：参数非法 → `user_error`
- **它做什么**：快慢双脑控制回路（蒸馏自 Jev/TypeSafe System One + browser-use/jev-ultrafast）：动作是**枚举**（CLICK/TYPE_TEXT/SELECT/SCROLL_*/WAIT/DONE/BLOCKED，枚举外不存在）· 一次观测出「操作+目标」两个头 · 只为 TYPE_TEXT 调生成模型 · **执行前两查（新鲜+遮挡）+ DONE 必须独立验证** · 低置信度才升级慢脑（无慢脑如实 BLOCKED）· 预算闸（单次时延+每分钟次数）· 每次决策写 state/control_loop.jsonl 审计链。**它只决策不动手**：动作仍走 desktop_control 等门。op=decide/observe/act/demo/selftest
- **怎么调**：`py -3.14 tools/codex-scripts/five-dim.py cap control_loop '<json>'`
- **失败三态**（本仓统一口径，不是这一位特有）：`denied` = 缺票，会点名`missing_scopes`；`needs_*` = 缺参/缺依赖，会带原因；`failed` = 真失败，回执带上游原话。**信封 `status=ok` ≠ 本体 `ok=true`。**

### `ul_tars_desktop`

- **域**：`desktop`（桌面智能体）
- **类型**：**需授权**（会写盘 / 花钱 / 出网） · **需参数**：否
- **要哪张票（静态）**：零作用域（空 payload 下不需要票）
- **必填载荷**：无必填（注册表 `requires_params=false`；空载荷落到该位默认 op）
- **常见错误**：参数非法 → `user_error`；依赖不在位 → `needs_dependency`；上游不给 → `needs_input` / `failed`（带上游原话）
- **它做什么**：Ul-TARS Desktop desktop agent
- **怎么调**：`py -3.14 tools/codex-scripts/five-dim.py cap ul_tars_desktop '<json>'`
- **失败三态**（本仓统一口径，不是这一位特有）：`denied` = 缺票，会点名`missing_scopes`；`needs_*` = 缺参/缺依赖，会带原因；`failed` = 真失败，回执带上游原话。**信封 `status=ok` ≠ 本体 `ok=true`。**

---

返回 [能力总表](../03-capabilities.md)
