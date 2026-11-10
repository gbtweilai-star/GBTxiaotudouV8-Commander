# 梦境/闭环 · `brain`（4 位）

> 自动生成，数据源 `gbt_allinone/caps_registry.py`。只读 = 不改状态、不出网；其余调用前需人工授权（作用域门）。参数以 `requires_params` 标出；**必填载荷**与**常见错误**两列只写注册表登记过的（没登记就写「无必填」/通用三态），不猜。

| 能力位 | 类型 | 需参数 | 必填载荷 | 常见错误 | 它做什么 |
|---|---|---|---|---|---|
| `absorb_loop` | 只读 | — | —（注册表：无必填） | `user_error` | 【吞天·闭环】吞天闭环（只读骨架）：蒸馏 DISTILL → 提炼 REFINE → 吸收 ABSORB + 回灌 FED_BACK；四条机械闸（stage_dirty 阶段间不许留垃圾 / loop_not_closed 三阶段必须齐且回灌 / junk_left_silent… |
| `dream_replay` | 只读 | — | —（注册表：无必填） | `user_error` | 做梦技能只读重演：五原语闭环，不写盘、不执行（巩固默认不开） |
| `route_ledger` | 只读 | — | —（注册表：无必填） | `user_error` | **路由台账 · 反思账本**：记「用户原话 → 路由结果 → 实际用了哪个」，让触发词从**真实使用**里长出来，而不是编。op=stats（攒到哪了：真实问法 / 能力覆盖 / 探针剔掉多少）· op=plan（**动手前先算账**：该补哪个能力、还差几条、下一级是什么）·… |
| `semantic_match` | 只读 | — | —（注册表：无必填） | `user_error` | **中文语义匹配**（bge-small-zh-v1.5 · ONNX 94.85MB · 零 torch）：把一句话编码成 512 维向量，和 424 个能力描述算余弦，给 top-k **参考**候选。铁律：**只给候选、不拍板**（返回里没有 best/chosen），不改… |

> 表格里是**摘要**（超过 140 字截断）；下面每位还有**逐位详解**（完整原文 / 要哪张票 / 真调用命令 / 缺什么会怎么报）。

---

## 逐位详解

### `absorb_loop`

- **域**：`brain`（梦境/闭环）
- **类型**：只读（不改状态、不出网） · **需参数**：否
- **要哪张票（静态）**：零作用域（空 payload 下不需要票）
- **必填载荷**：无必填（注册表 `requires_params=false`；空载荷落到该位默认 op）
- **常见错误**：参数非法 → `user_error`
- **它做什么**：【吞天·闭环】吞天闭环（只读骨架）：蒸馏 DISTILL → 提炼 REFINE → 吸收 ABSORB + 回灌 FED_BACK；四条机械闸（stage_dirty 阶段间不许留垃圾 / loop_not_closed 三阶段必须齐且回灌 / junk_left_silently 垃圾要么清要么登记 / not_resumable 中断必须留续跑点）+ 五条红线（吞完清场/闭环可续/每阶段留痕 source_kind=absorb/不吞未取证来源/垃圾不许静默留）
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

### `route_ledger`

- **域**：`brain`（梦境/闭环）
- **类型**：只读（不改状态、不出网） · **需参数**：否
- **要哪张票（静态）**：零作用域（空 payload 下不需要票）
- **必填载荷**：无必填（注册表 `requires_params=false`；空载荷落到该位默认 op）
- **常见错误**：参数非法 → `user_error`
- **它做什么**：**路由台账 · 反思账本**：记「用户原话 → 路由结果 → 实际用了哪个」，让触发词从**真实使用**里长出来，而不是编。op=stats（攒到哪了：真实问法 / 能力覆盖 / 探针剔掉多少）· op=plan（**动手前先算账**：该补哪个能力、还差几条、下一级是什么）· op=export（导出可用的 (原话 → 能力) 真值对）· op=record（记账，内部用）。铁律：分母取 orchestration-ledger 的**真实调用分布**，不是能力总数；读不到真实分布就**拒绝盲补**（盲补即等于编）。常用说法：路由还缺什么 / 该补哪个能力 / 触发词够不够 / 台账攒到哪了 / 路由质量 / 说话认不认得出 / 规则还差多少 / 还差几条。
- **怎么调**：`py -3.14 tools/codex-scripts/five-dim.py cap route_ledger '<json>'`
- **失败三态**（本仓统一口径，不是这一位特有）：`denied` = 缺票，会点名`missing_scopes`；`needs_*` = 缺参/缺依赖，会带原因；`failed` = 真失败，回执带上游原话。**信封 `status=ok` ≠ 本体 `ok=true`。**

### `semantic_match`

- **域**：`brain`（梦境/闭环）
- **类型**：只读（不改状态、不出网） · **需参数**：否
- **要哪张票（静态）**：零作用域（空 payload 下不需要票）
- **必填载荷**：无必填（注册表 `requires_params=false`；空载荷落到该位默认 op）
- **常见错误**：参数非法 → `user_error`
- **它做什么**：**中文语义匹配**（bge-small-zh-v1.5 · ONNX 94.85MB · 零 torch）：把一句话编码成 512 维向量，和 424 个能力描述算余弦，给 top-k **参考**候选。铁律：**只给候选、不拍板**（返回里没有 best/chosen），不改任何现有排序。实测口径：短词（≤4 字）错误率最高，那类输入请走关键词精确匹配；组合词/长句自然表达才是它的主场。op=match（text + top_k）· status · build（重建向量缓存）。常用说法：语义匹配 / 意思相近 / 像哪个能力 / 换个说法认不认得出 / 语义找能力。
- **怎么调**：`py -3.14 tools/codex-scripts/five-dim.py cap semantic_match '<json>'`
- **失败三态**（本仓统一口径，不是这一位特有）：`denied` = 缺票，会点名`missing_scopes`；`needs_*` = 缺参/缺依赖，会带原因；`failed` = 真失败，回执带上游原话。**信封 `status=ok` ≠ 本体 `ok=true`。**

---

返回 [能力总表](../03-capabilities.md)
