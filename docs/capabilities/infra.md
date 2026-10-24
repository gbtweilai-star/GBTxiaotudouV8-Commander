# 基础设施（云电脑） · `infra`（2 位）

> 自动生成，数据源 `gbt_allinone/caps_registry.py`。只读 = 不改状态、不出网；其余调用前需人工授权（作用域门）。参数以 `requires_params` 标出；**必填载荷**与**常见错误**两列只写注册表登记过的（没登记就写「无必填」/通用三态），不猜。

| 能力位 | 类型 | 需参数 | 必填载荷 | 常见错误 | 它做什么 |
|---|---|---|---|---|---|
| `cloud_pc` | 只读 | — | —（注册表：无必填） | `user_error` | 云电脑独立窗口（只读骨架·门）：面板加一个**独立窗口**给她（数字人）**安装**云电脑（卡片 + 触手，**不是 iframe**）；五原语 PROVISION/CONNECT/STATUS/SNAPSHOT/RELEASE（逐个标花钱与不可逆）；五条红线（密钥DPAPI/先… |
| `cloud_plugin` | 只读 | — | —（注册表：无必填） | `user_error` | 云插件（只读骨架）：**云源注册表 + 触手双向连接**。**无限扩容 = 加一行**（SOURCES 元组）—— 现登记 10 个云源（云卡触手 / 云电脑 / 云卡ComfyUI / 能源池 / 统一密钥网关 / 免费模型池 / H3mini / a1.art / LibTV… |

> 表格里是**摘要**（超过 140 字截断）；下面每位还有**逐位详解**（完整原文 / 要哪张票 / 真调用命令 / 缺什么会怎么报）。

---

## 逐位详解

### `cloud_pc`

- **域**：`infra`（基础设施（云电脑））
- **类型**：只读（不改状态、不出网） · **需参数**：否
- **要哪张票（静态）**：零作用域（空 payload 下不需要票）
- **必填载荷**：无必填（注册表 `requires_params=false`；空载荷落到该位默认 op）
- **常见错误**：参数非法 → `user_error`
- **它做什么**：云电脑独立窗口（只读骨架·门）：面板加一个**独立窗口**给她（数字人）**安装**云电脑（卡片 + 触手，**不是 iframe**）；五原语 PROVISION/CONNECT/STATUS/SNAPSHOT/RELEASE（逐个标花钱与不可逆）；五条红线（密钥DPAPI/先算账再花钱/每次留痕 source_kind=cloud_pc/不绕官方入口/身份内核不变）；type=external
- **怎么调**：`py -3.14 tools/codex-scripts/five-dim.py cap cloud_pc '<json>'`
- **失败三态**（本仓统一口径，不是这一位特有）：`denied` = 缺票，会点名`missing_scopes`；`needs_*` = 缺参/缺依赖，会带原因；`failed` = 真失败，回执带上游原话。**信封 `status=ok` ≠ 本体 `ok=true`。**

### `cloud_plugin`

- **域**：`infra`（基础设施（云电脑））
- **类型**：只读（不改状态、不出网） · **需参数**：否
- **要哪张票（静态）**：零作用域（空 payload 下不需要票）
- **必填载荷**：无必填（注册表 `requires_params=false`；空载荷落到该位默认 op）
- **常见错误**：参数非法 → `user_error`
- **它做什么**：云插件（只读骨架）：**云源注册表 + 触手双向连接**。**无限扩容 = 加一行**（SOURCES 元组）—— 现登记 10 个云源（云卡触手 / 云电脑 / 云卡ComfyUI / 能源池 / 统一密钥网关 / 免费模型池 / H3mini / a1.art / LibTV / Tripo3D）。**绑定一次两个方向都查得到**，台账同 tentacle_bind（只增不删）。五原语各自标清**可逆性/花费/是否卡门**。五条红线（密钥DPAPI/先算账再花钱/每次留痕/不绕官方入口/身份内核不变）。op=status/sources/primitives/ledger/bind/resolve/expand/check_key/check_bill/check_bypass/check_trace
- **怎么调**：`py -3.14 tools/codex-scripts/five-dim.py cap cloud_plugin '<json>'`
- **失败三态**（本仓统一口径，不是这一位特有）：`denied` = 缺票，会点名`missing_scopes`；`needs_*` = 缺参/缺依赖，会带原因；`failed` = 真失败，回执带上游原话。**信封 `status=ok` ≠ 本体 `ok=true`。**

---

返回 [能力总表](../03-capabilities.md)
