# 界面 · `ui`（1 位）

> 自动生成，数据源 `gbt_allinone/caps_registry.py`。只读 = 不改状态、不出网；其余调用前需人工授权（作用域门）。参数以 `requires_params` 标出；**必填载荷**与**常见错误**两列只写注册表登记过的（没登记就写「无必填」/通用三态），不猜。

| 能力位 | 类型 | 需参数 | 必填载荷 | 常见错误 | 它做什么 |
|---|---|---|---|---|---|
| `ui_card` | 只读 | — | —（注册表：无必填） | `user_error` | **ACUI 卡片协议**（吞噬上游参考项目 Scene Protocol/ACUI 蒸出的我们自己的版本，2026-11-02 主人令）：op=schema/validate/create/close/action/snapshot/events/clear/verify… |

> 表格里是**摘要**（超过 140 字截断）；下面每位还有**逐位详解**（完整原文 / 要哪张票 / 真调用命令 / 缺什么会怎么报）。

---

## 逐位详解

### `ui_card`

- **域**：`ui`（界面）
- **类型**：只读（不改状态、不出网） · **需参数**：否
- **要哪张票（静态）**：零作用域（空 payload 下不需要票）
- **必填载荷**：无必填（注册表 `requires_params=false`；空载荷落到该位默认 op）
- **常见错误**：参数非法 → `user_error`
- **它做什么**：**ACUI 卡片协议**（吞噬上游参考项目 Scene Protocol/ACUI 蒸出的我们自己的版本，2026-11-02 主人令）：op=schema/validate/create/close/action/snapshot/events/clear/verify。卡片是**纯数据**：kind/action.type 白名单 · 纯文本（拒 HTML/脚本/事件属性）· TTL 到期自动清 · 最多 20 张/4 动作/2000 字；动作只回发 `ui_card_action` 事件给主循环（`executed=false`），不在这里执行任何工具。**纯函数·零作用域**：不写盘/不出网；审计由调用方追加。
- **怎么调**：`py -3.14 tools/codex-scripts/five-dim.py cap ui_card '<json>'`
- **失败三态**（本仓统一口径，不是这一位特有）：`denied` = 缺票，会点名`missing_scopes`；`needs_*` = 缺参/缺依赖，会带原因；`failed` = 真失败，回执带上游原话。**信封 `status=ok` ≠ 本体 `ok=true`。**

---

返回 [能力总表](../03-capabilities.md)

---

> 开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属
