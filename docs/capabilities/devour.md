# 吞天（自我进化） · `devour`（5 位）

> 自动生成，数据源 `gbt_allinone/caps_registry.py`。只读 = 不改状态、不出网；其余调用前需人工授权（作用域门）。参数以 `requires_params` 标出；**必填载荷**与**常见错误**两列只写注册表登记过的（没登记就写「无必填」/通用三态），不猜。

| 能力位 | 类型 | 需参数 | 必填载荷 | 常见错误 | 它做什么 |
|---|---|---|---|---|---|
| `devour_fusion` | 只读 | — | —（注册表：无必填） | `user_error` | 吞天 × 原生能力 融合台账（主人令「把蒸馏提炼出契合自己的原生能力和吞天融合到一起…以及记入能力」）：吞进来的东西**三件齐才算融合** —— ①原生位三处齐（注册/分派/图鉴）②有效触手标签 ③触手库永久记忆页；`status=已融合` 而三件不齐**当场拒**（假账拦下）。… |
| `devour_github` | 只读 | 是 | `repo` | `user_error` | 吞天：吞噬 GitHub 仓库为知识胶囊（自我进化的核心——吸收外部能力） |
| `devour_pulse` | 只读 | — | —（注册表：无必填） | `user_error` | 吞天：完整认知循环（吞噬→反思→消化→重组→进化） |
| `devour_reflect` | 只读 | — | —（注册表：无必填） | `user_error` | 吞天：反思（回顾吞噬历史学习模式，发现弱能力与重组机会） |
| `devour_scan` | 只读 | — | —（注册表：无必填） | `user_error` | 吞天：能力缺口扫描（域覆盖对照+进化方向） |

> 表格里是**摘要**（超过 140 字截断）；下面每位还有**逐位详解**（完整原文 / 要哪张票 / 真调用命令 / 缺什么会怎么报）。

---

## 逐位详解

### `devour_fusion`

- **域**：`devour`（吞天（自我进化））
- **类型**：只读（不改状态、不出网） · **需参数**：否
- **要哪张票（静态）**：零作用域（空 payload 下不需要票）
- **必填载荷**：无必填（注册表 `requires_params=false`；空载荷落到该位默认 op）
- **常见错误**：参数非法 → `user_error`
- **它做什么**：吞天 × 原生能力 融合台账（主人令「把蒸馏提炼出契合自己的原生能力和吞天融合到一起…以及记入能力」）：吞进来的东西**三件齐才算融合** —— ①原生位三处齐（注册/分派/图鉴）②有效触手标签 ③触手库永久记忆页；`status=已融合` 而三件不齐**当场拒**（假账拦下）。`fuse` 补第三件（调 obsidian_vault.remember）；`audit` 逐条列缺件与补法。图片里那三个开源件先记 **`待吞`**（要装上才能吞，装不上就写不上）。op=intake/list/audit/fuse/verify/where
- **怎么调**：`py -3.14 tools/codex-scripts/five-dim.py cap devour_fusion '<json>'`
- **失败三态**（本仓统一口径，不是这一位特有）：`denied` = 缺票，会点名`missing_scopes`；`needs_*` = 缺参/缺依赖，会带原因；`failed` = 真失败，回执带上游原话。**信封 `status=ok` ≠ 本体 `ok=true`。**

### `devour_github`

- **域**：`devour`（吞天（自我进化））
- **类型**：只读（不改状态、不出网） · **需参数**：是 —— 要吞噬的 GitHub 仓库 URL（也认 url=）
- **要哪张票（静态）**：`data_export`、`filesystem_write`
- **必填载荷**：`repo` —— 要吞噬的 GitHub 仓库 URL（也认 url=）
- **常见错误**：缺参 / 参数非法 → `user_error`（必填：`repo`）
- **它做什么**：吞天：吞噬 GitHub 仓库为知识胶囊（自我进化的核心——吸收外部能力）
- **怎么调**：`py -3.14 tools/codex-scripts/five-dim.py cap devour_github '<json>'`
- **失败三态**（本仓统一口径，不是这一位特有）：`denied` = 缺票，会点名`missing_scopes`；`needs_*` = 缺参/缺依赖，会带原因；`failed` = 真失败，回执带上游原话。**信封 `status=ok` ≠ 本体 `ok=true`。**

### `devour_pulse`

- **域**：`devour`（吞天（自我进化））
- **类型**：只读（不改状态、不出网） · **需参数**：否
- **要哪张票（静态）**：`data_export`、`filesystem_write`、`external_llm`
- **必填载荷**：无必填（注册表 `requires_params=false`；空载荷落到该位默认 op）
- **常见错误**：参数非法 → `user_error`
- **它做什么**：吞天：完整认知循环（吞噬→反思→消化→重组→进化）
- **怎么调**：`py -3.14 tools/codex-scripts/five-dim.py cap devour_pulse '<json>'`
- **失败三态**（本仓统一口径，不是这一位特有）：`denied` = 缺票，会点名`missing_scopes`；`needs_*` = 缺参/缺依赖，会带原因；`failed` = 真失败，回执带上游原话。**信封 `status=ok` ≠ 本体 `ok=true`。**

### `devour_reflect`

- **域**：`devour`（吞天（自我进化））
- **类型**：只读（不改状态、不出网） · **需参数**：否
- **要哪张票（静态）**：零作用域（空 payload 下不需要票）
- **必填载荷**：无必填（注册表 `requires_params=false`；空载荷落到该位默认 op）
- **常见错误**：参数非法 → `user_error`
- **它做什么**：吞天：反思（回顾吞噬历史学习模式，发现弱能力与重组机会）
- **怎么调**：`py -3.14 tools/codex-scripts/five-dim.py cap devour_reflect '<json>'`
- **失败三态**（本仓统一口径，不是这一位特有）：`denied` = 缺票，会点名`missing_scopes`；`needs_*` = 缺参/缺依赖，会带原因；`failed` = 真失败，回执带上游原话。**信封 `status=ok` ≠ 本体 `ok=true`。**

### `devour_scan`

- **域**：`devour`（吞天（自我进化））
- **类型**：只读（不改状态、不出网） · **需参数**：否
- **要哪张票（静态）**：零作用域（空 payload 下不需要票）
- **必填载荷**：无必填（注册表 `requires_params=false`；空载荷落到该位默认 op）
- **常见错误**：参数非法 → `user_error`
- **它做什么**：吞天：能力缺口扫描（域覆盖对照+进化方向）
- **怎么调**：`py -3.14 tools/codex-scripts/five-dim.py cap devour_scan '<json>'`
- **失败三态**（本仓统一口径，不是这一位特有）：`denied` = 缺票，会点名`missing_scopes`；`needs_*` = 缺参/缺依赖，会带原因；`failed` = 真失败，回执带上游原话。**信封 `status=ok` ≠ 本体 `ok=true`。**

---

返回 [能力总表](../03-capabilities.md)
