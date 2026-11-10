# 项目测绘 · `project`（3 位）

> 自动生成，数据源 `gbt_allinone/caps_registry.py`。只读 = 不改状态、不出网；其余调用前需人工授权（作用域门）。参数以 `requires_params` 标出；**必填载荷**与**常见错误**两列只写注册表登记过的（没登记就写「无必填」/通用三态），不猜。

| 能力位 | 类型 | 需参数 | 必填载荷 | 常见错误 | 它做什么 |
|---|---|---|---|---|---|
| `platform_profile` | 只读 | — | —（注册表：无必填） | `user_error` | 【量化·项目结构】读取量化项目结构（真实测绘；外部业务模块 quant_tech，未挂载则如实报缺口） |
| `project_context` | 只读 | — | —（注册表：无必填） | `user_error` | 项目上下文：**文档面**（blueprint 蓝图 / brief 简报 / search 只读检索 / status）＋ **代码结构四面**（2026-09-23 接，补上「专业级编程AI」缺的那半身）：`symbols` 符号（顶层 def/class，可按名问「在哪定义… |
| `sync_guard` | 只读 | — | —（注册表：无必填） | `user_error` | 双仓同步巡检（2026-11-01）：交付树 ↔ live 工作仓 的 sha1 对账——status（只报差异）/ verify（判 ALIGNED：only_live=0 · 非档案 only_delivery=0 · differ=0 · 两边 cap 计数相等）/ pat… |

> 表格里是**摘要**（超过 140 字截断）；下面每位还有**逐位详解**（完整原文 / 要哪张票 / 真调用命令 / 缺什么会怎么报）。

---

## 逐位详解

### `platform_profile`

- **域**：`project`（项目测绘）
- **类型**：只读（不改状态、不出网） · **需参数**：否
- **要哪张票（静态）**：零作用域（空 payload 下不需要票）
- **必填载荷**：无必填（注册表 `requires_params=false`；空载荷落到该位默认 op）
- **常见错误**：参数非法 → `user_error`
- **它做什么**：【量化·项目结构】读取量化项目结构（真实测绘；外部业务模块 quant_tech，未挂载则如实报缺口）
- **怎么调**：`py -3.14 tools/codex-scripts/five-dim.py cap platform_profile '<json>'`
- **失败三态**（本仓统一口径，不是这一位特有）：`denied` = 缺票，会点名`missing_scopes`；`needs_*` = 缺参/缺依赖，会带原因；`failed` = 真失败，回执带上游原话。**信封 `status=ok` ≠ 本体 `ok=true`。**

### `project_context`

- **域**：`project`（项目测绘）
- **类型**：只读（不改状态、不出网） · **需参数**：否
- **要哪张票（静态）**：零作用域（空 payload 下不需要票）
- **必填载荷**：无必填（注册表 `requires_params=false`；空载荷落到该位默认 op）
- **常见错误**：参数非法 → `user_error`
- **它做什么**：项目上下文：**文档面**（blueprint 蓝图 / brief 简报 / search 只读检索 / status）＋ **代码结构四面**（2026-09-23 接，补上「专业级编程AI」缺的那半身）：`symbols` 符号（顶层 def/class，可按名问「在哪定义」）· `deps` 依赖（内部 import 边 + 外部三方名）· `calls` 调用图（**复用现成 `tools/call_graph.py`**：find/callers/callees/trace/dead_code，4.2s / 351 文件）· `tests` 测试面（模块被哪些测试**提到**过）· `structure` 三面速览（4.4s，**刻意不含调用图**）。全部只读。⚠️ 四处诚实边界随结果一起带出：符号只收**顶层**；依赖只看 **import 语句**；调用图带**未解析率**（本仓约 0.66，所以「没人调用」先天有缺口）；测试面是**提到过**的代理**不是行覆盖**。
- **怎么调**：`py -3.14 tools/codex-scripts/five-dim.py cap project_context '<json>'`
- **失败三态**（本仓统一口径，不是这一位特有）：`denied` = 缺票，会点名`missing_scopes`；`needs_*` = 缺参/缺依赖，会带原因；`failed` = 真失败，回执带上游原话。**信封 `status=ok` ≠ 本体 `ok=true`。**

### `sync_guard`

- **域**：`project`（项目测绘）
- **类型**：只读（不改状态、不出网） · **需参数**：否
- **要哪张票（静态）**：零作用域（空 payload 下不需要票）
- **必填载荷**：无必填（注册表 `requires_params=false`；空载荷落到该位默认 op）
- **常见错误**：参数非法 → `user_error`
- **它做什么**：双仓同步巡检（2026-11-01）：交付树 ↔ live 工作仓 的 sha1 对账——status（只报差异）/ verify（判 ALIGNED：only_live=0 · 非档案 only_delivery=0 · differ=0 · 两边 cap 计数相等）/ patrol（verify + 可选写 state/sync_guard.jsonl 台账；notify=true 时 DRIFT 写审计 error、ALIGNED 写 ok，alerts 能读到；DRIFT 时按 env 优先推 webhook/飞书/n8n，未配置则桌面 toast（零依赖））/ where。DRIFT 时出 alerts（sync_drift / caps_mismatch）并给修复命令；**只读，不自动 pull/push**，修复由 tools/two-way-sync.ps1 执行。交付树路径默认 ~/Desktop/GBT小土豆V8，可用 delivery 参数或 GBT_DELIVERY 覆盖
- **怎么调**：`py -3.14 tools/codex-scripts/five-dim.py cap sync_guard '<json>'`
- **失败三态**（本仓统一口径，不是这一位特有）：`denied` = 缺票，会点名`missing_scopes`；`needs_*` = 缺参/缺依赖，会带原因；`failed` = 真失败，回执带上游原话。**信封 `status=ok` ≠ 本体 `ok=true`。**

---

返回 [能力总表](../03-capabilities.md)
