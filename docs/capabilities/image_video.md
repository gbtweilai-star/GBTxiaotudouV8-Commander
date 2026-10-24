# 图像/视频生成 · `image_video`（1 位）

> 自动生成，数据源 `gbt_allinone/caps_registry.py`。只读 = 不改状态、不出网；其余调用前需人工授权（作用域门）。参数以 `requires_params` 标出；**必填载荷**与**常见错误**两列只写注册表登记过的（没登记就写「无必填」/通用三态），不猜。

| 能力位 | 类型 | 需参数 | 必填载荷 | 常见错误 | 它做什么 |
|---|---|---|---|---|---|
| `a1art_skill` | 只读 | — | —（空载荷走该位默认 op） | `user_error` | a1.art API 技能（只读骨架·门）：五原语 LOOKUP→UPLOAD→GENERATE→OPTIMIZE→POLL；密钥只走 DPAPI/密钥池、结果必须落盘、不调不支持组件、810012 如实报 |

> 表格里是**摘要**（超过 140 字截断）；下面每位还有**逐位详解**（完整原文 / 要哪张票 / 真调用命令 / 缺什么会怎么报）。

---

## 逐位详解

### `a1art_skill`

- **域**：`image_video`（图像/视频生成）
- **类型**：只读（不改状态、不出网） · **需参数**：否
- **要哪张票（静态）**：零作用域（空 payload 下不需要票）
- **必填载荷**：无必填（空载荷落到该位默认 op；位内更细的 op 参数见模块）
- **常见错误**：参数非法 → `user_error`
- **它做什么**：a1.art API 技能（只读骨架·门）：五原语 LOOKUP→UPLOAD→GENERATE→OPTIMIZE→POLL；密钥只走 DPAPI/密钥池、结果必须落盘、不调不支持组件、810012 如实报
- **怎么调**：`py -3.14 tools/codex-scripts/five-dim.py cap a1art_skill '<json>'`
- **失败三态**（本仓统一口径，不是这一位特有）：`denied` = 缺票，会点名`missing_scopes`；`needs_*` = 缺参/缺依赖，会带原因；`failed` = 真失败，回执带上游原话。**信封 `status=ok` ≠ 本体 `ok=true`。**

---

返回 [能力总表](../03-capabilities.md)
