# 身体控制 · `body_control`（1 位）

> 自动生成，数据源 `gbt_allinone/caps_registry.py`。只读 = 不改状态、不出网；其余调用前需人工授权（作用域门）。参数以 `requires_params` 标出；**必填载荷**与**常见错误**两列只写注册表登记过的（没登记就写「无必填」/通用三态），不猜。

| 能力位 | 类型 | 需参数 | 必填载荷 | 常见错误 | 它做什么 |
|---|---|---|---|---|---|
| `body_control` | 只读 | — | —（注册表：无必填） | `user_error` | **身体控制 / 触手 / 全息投影状态口**（主人 2026-11-02 定名）：op=schema/status/inventory/move/verify。**如实报缺**：缺感觉/执行器（未绑定或已被主人拔掉）报 not_supported；全绑定也最多 parti… |

> 表格里是**摘要**（超过 140 字截断）；下面每位还有**逐位详解**（完整原文 / 要哪张票 / 真调用命令 / 缺什么会怎么报）。

---

## 逐位详解

### `body_control`

- **域**：`body_control`（身体控制）
- **类型**：只读（不改状态、不出网） · **需参数**：否
- **要哪张票（静态）**：零作用域（空 payload 下不需要票）
- **必填载荷**：无必填（注册表 `requires_params=false`；空载荷落到该位默认 op）
- **常见错误**：参数非法 → `user_error`
- **它做什么**：**身体控制 / 触手 / 全息投影状态口**（主人 2026-11-02 定名）：op=schema/status/inventory/move/verify。**如实报缺**：缺感觉/执行器（未绑定或已被主人拔掉）报 not_supported；全绑定也最多 partial 且 `executed=false` —— 深度学习 + 无模型不等于能动，不假装能动。本件 zero-scope，只读状态/清单；不驱动任何硬件。
- **怎么调**：`py -3.14 tools/codex-scripts/five-dim.py cap body_control '<json>'`
- **失败三态**（本仓统一口径，不是这一位特有）：`denied` = 缺票，会点名`missing_scopes`；`needs_*` = 缺参/缺依赖，会带原因；`failed` = 真失败，回执带上游原话。**信封 `status=ok` ≠ 本体 `ok=true`。**

---

返回 [能力总表](../03-capabilities.md)

---

> 开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属
