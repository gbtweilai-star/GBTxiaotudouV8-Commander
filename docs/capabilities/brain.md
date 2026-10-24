# 梦境/闭环 · `brain`（2 位）

> 自动生成，数据源 `gbt_allinone/caps_registry.py`。只读 = 不改状态、不出网；其余调用前需人工授权（作用域门）。参数以 `requires_params` 标出；**必填载荷**与**常见错误**两列只写注册表登记过的（没登记就写「无必填」/通用三态），不猜。

| 能力位 | 类型 | 需参数 | 必填载荷 | 常见错误 | 它做什么 |
|---|---|---|---|---|---|
| `absorb_loop` | 只读 | — | —（注册表：无必填） | `user_error` | 吞天闭环（只读骨架）：蒸馏 DISTILL → 提炼 REFINE → 吸收 ABSORB + 回灌 FED_BACK；四条机械闸（stage_dirty 阶段间不许留垃圾 / loop_not_closed 三阶段必须齐且回灌 / junk_left_silently 垃圾要么… |
| `dream_replay` | 只读 | — | —（注册表：无必填） | `user_error` | 做梦技能只读重演：五原语闭环，不写盘、不执行（巩固默认不开） |

> 表格里是**摘要**（超过 140 字截断）；下面每位还有**逐位详解**（完整原文 / 要哪张票 / 真调用命令 / 缺什么会怎么报）。

---

## 逐位详解

### `absorb_loop`

- **域**：`brain`（梦境/闭环）
- **类型**：只读（不改状态、不出网） · **需参数**：否
- **要哪张票（静态）**：零作用域（空 payload 下不需要票）
- **必填载荷**：无必填（注册表 `requires_params=false`；空载荷落到该位默认 op）
- **常见错误**：参数非法 → `user_error`
- **它做什么**：吞天闭环（只读骨架）：蒸馏 DISTILL → 提炼 REFINE → 吸收 ABSORB + 回灌 FED_BACK；四条机械闸（stage_dirty 阶段间不许留垃圾 / loop_not_closed 三阶段必须齐且回灌 / junk_left_silently 垃圾要么清要么登记 / not_resumable 中断必须留续跑点）+ 五条红线（吞完清场/闭环可续/每阶段留痕 source_kind=absorb/不吞未取证来源/垃圾不许静默留）
- **怎么调**：`py -3.14 tools/codex-scripts/five-dim.py cap absorb_loop '<json>'`
- **失败三态**（本仓统一口径，不是这一位特有）：`denied` = 缺票，会点名`missing_scopes`；`needs_*` = 缺参/缺依赖，会带原因；`failed` = 真失败，回执带上游原话。**信封 `status=ok` ≠ 本体 `ok=true`。**

### `dream_replay`

- **域**：`brain`（梦境/闭环）
- **类型**：只读（不改状态、不出网） · **需参数**：否
- **要哪张票（静态）**：零作用域（空 payload 下不需要票）
- **必填载荷**：无必填（注册表 `requires_params=false`；空载荷落到该位默认 op）
- **常见错误**：参数非法 → `user_error`
- **它做什么**：做梦技能只读重演：五原语闭环，不写盘、不执行（巩固默认不开）
- **怎么调**：`py -3.14 tools/codex-scripts/five-dim.py cap dream_replay '<json>'`
- **失败三态**（本仓统一口径，不是这一位特有）：`denied` = 缺票，会点名`missing_scopes`；`needs_*` = 缺参/缺依赖，会带原因；`failed` = 真失败，回执带上游原话。**信封 `status=ok` ≠ 本体 `ok=true`。**

---

返回 [能力总表](../03-capabilities.md)
