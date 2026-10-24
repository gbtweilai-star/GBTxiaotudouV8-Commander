# 设备 · `device`（9 位）

> 自动生成，数据源 `gbt_allinone/caps_registry.py`。只读 = 不改状态、不出网；其余调用前需人工授权（作用域门）。参数以 `requires_params` 标出；**必填载荷**与**常见错误**两列只写注册表登记过的（没登记就写「无必填」/通用三态），不猜。

| 能力位 | 类型 | 需参数 | 必填载荷 | 常见错误 | 它做什么 |
|---|---|---|---|---|---|
| `bluetooth` | 只读 | — | —（空载荷走该位默认 op） | `user_error` | 蓝牙设备控制：扫描附近 BLE 设备、连接读写 GATT 特征（操控空调/灯/音箱等家居设备）、经典蓝牙状态报告 |
| `body_click` | 只读 | — | —（空载荷走该位默认 op） | `user_error` | 身体·点：按坐标点按（参数 x,y,clicks） |
| `body_map` | 只读 | — | —（空载荷走该位默认 op） | `user_error` | 身体·清单：现读这台设备的七根感官与六根动作（零作用域，只读） |
| `body_open` | 只读 | — | —（空载荷走该位默认 op） | `user_error` | 身体·打开：用系统默认程序打开文件/网址（参数 target） |
| `body_say` | 只读 | — | —（空载荷走该位默认 op） | `user_error` | 身体·说：系统 TTS 念一句（参数 text，可调 rate） |
| `body_see` | 只读 | — | —（空载荷走该位默认 op） | `user_error` | 身体·看：截当前屏幕落 png（可选 monitor 序号） |
| `body_type` | 只读 | — | —（空载荷走该位默认 op） | `user_error` | 身体·打字：向前台窗口键入文本（参数 text） |
| `body_volume` | 只读 | — | —（空载荷走该位默认 op） | `user_error` | 身体·音量：读或设主音量（参数 level 0~1；不传则只读） |
| `bt_control` | 只读 | — | —（空载荷走该位默认 op） | `user_error` | AI 智能蓝牙操控：自然语言意图→扫描识别设备→协议匹配→组装指令→写入执行→验证（协议库只收公开文档协议，未知如实报告） |

> 表格里是**摘要**（超过 140 字截断）；下面每位还有**逐位详解**（完整原文 / 要哪张票 / 真调用命令 / 缺什么会怎么报）。

---

## 逐位详解

### `bluetooth`

- **域**：`device`（设备）
- **类型**：只读（不改状态、不出网） · **需参数**：否
- **要哪张票（静态）**：`device_control`
- **必填载荷**：无必填（空载荷落到该位默认 op；位内更细的 op 参数见模块）
- **常见错误**：参数非法 → `user_error`
- **它做什么**：蓝牙设备控制：扫描附近 BLE 设备、连接读写 GATT 特征（操控空调/灯/音箱等家居设备）、经典蓝牙状态报告
- **怎么调**：`py -3.14 tools/codex-scripts/five-dim.py cap bluetooth '<json>'`
- **失败三态**（本仓统一口径，不是这一位特有）：`denied` = 缺票，会点名`missing_scopes`；`needs_*` = 缺参/缺依赖，会带原因；`failed` = 真失败，回执带上游原话。**信封 `status=ok` ≠ 本体 `ok=true`。**

### `body_click`

- **域**：`device`（设备）
- **类型**：只读（不改状态、不出网） · **需参数**：否
- **要哪张票（静态）**：`desktop_control`
- **必填载荷**：无必填（空载荷落到该位默认 op；位内更细的 op 参数见模块）
- **常见错误**：参数非法 → `user_error`
- **它做什么**：身体·点：按坐标点按（参数 x,y,clicks）
- **怎么调**：`py -3.14 tools/codex-scripts/five-dim.py cap body_click '<json>'`
- **失败三态**（本仓统一口径，不是这一位特有）：`denied` = 缺票，会点名`missing_scopes`；`needs_*` = 缺参/缺依赖，会带原因；`failed` = 真失败，回执带上游原话。**信封 `status=ok` ≠ 本体 `ok=true`。**

### `body_map`

- **域**：`device`（设备）
- **类型**：只读（不改状态、不出网） · **需参数**：否
- **要哪张票（静态）**：零作用域（空 payload 下不需要票）
- **必填载荷**：无必填（空载荷落到该位默认 op；位内更细的 op 参数见模块）
- **常见错误**：参数非法 → `user_error`
- **它做什么**：身体·清单：现读这台设备的七根感官与六根动作（零作用域，只读）
- **怎么调**：`py -3.14 tools/codex-scripts/five-dim.py cap body_map '<json>'`
- **失败三态**（本仓统一口径，不是这一位特有）：`denied` = 缺票，会点名`missing_scopes`；`needs_*` = 缺参/缺依赖，会带原因；`failed` = 真失败，回执带上游原话。**信封 `status=ok` ≠ 本体 `ok=true`。**

### `body_open`

- **域**：`device`（设备）
- **类型**：只读（不改状态、不出网） · **需参数**：否
- **要哪张票（静态）**：`process_execute`
- **必填载荷**：无必填（空载荷落到该位默认 op；位内更细的 op 参数见模块）
- **常见错误**：参数非法 → `user_error`
- **它做什么**：身体·打开：用系统默认程序打开文件/网址（参数 target）
- **怎么调**：`py -3.14 tools/codex-scripts/five-dim.py cap body_open '<json>'`
- **失败三态**（本仓统一口径，不是这一位特有）：`denied` = 缺票，会点名`missing_scopes`；`needs_*` = 缺参/缺依赖，会带原因；`failed` = 真失败，回执带上游原话。**信封 `status=ok` ≠ 本体 `ok=true`。**

### `body_say`

- **域**：`device`（设备）
- **类型**：只读（不改状态、不出网） · **需参数**：否
- **要哪张票（静态）**：`audio_output`
- **必填载荷**：无必填（空载荷落到该位默认 op；位内更细的 op 参数见模块）
- **常见错误**：参数非法 → `user_error`
- **它做什么**：身体·说：系统 TTS 念一句（参数 text，可调 rate）
- **怎么调**：`py -3.14 tools/codex-scripts/five-dim.py cap body_say '<json>'`
- **失败三态**（本仓统一口径，不是这一位特有）：`denied` = 缺票，会点名`missing_scopes`；`needs_*` = 缺参/缺依赖，会带原因；`failed` = 真失败，回执带上游原话。**信封 `status=ok` ≠ 本体 `ok=true`。**

### `body_see`

- **域**：`device`（设备）
- **类型**：只读（不改状态、不出网） · **需参数**：否
- **要哪张票（静态）**：`filesystem_write`
- **必填载荷**：无必填（空载荷落到该位默认 op；位内更细的 op 参数见模块）
- **常见错误**：参数非法 → `user_error`
- **它做什么**：身体·看：截当前屏幕落 png（可选 monitor 序号）
- **怎么调**：`py -3.14 tools/codex-scripts/five-dim.py cap body_see '<json>'`
- **失败三态**（本仓统一口径，不是这一位特有）：`denied` = 缺票，会点名`missing_scopes`；`needs_*` = 缺参/缺依赖，会带原因；`failed` = 真失败，回执带上游原话。**信封 `status=ok` ≠ 本体 `ok=true`。**

### `body_type`

- **域**：`device`（设备）
- **类型**：只读（不改状态、不出网） · **需参数**：否
- **要哪张票（静态）**：`desktop_control`
- **必填载荷**：无必填（空载荷落到该位默认 op；位内更细的 op 参数见模块）
- **常见错误**：参数非法 → `user_error`
- **它做什么**：身体·打字：向前台窗口键入文本（参数 text）
- **怎么调**：`py -3.14 tools/codex-scripts/five-dim.py cap body_type '<json>'`
- **失败三态**（本仓统一口径，不是这一位特有）：`denied` = 缺票，会点名`missing_scopes`；`needs_*` = 缺参/缺依赖，会带原因；`failed` = 真失败，回执带上游原话。**信封 `status=ok` ≠ 本体 `ok=true`。**

### `body_volume`

- **域**：`device`（设备）
- **类型**：只读（不改状态、不出网） · **需参数**：否
- **要哪张票（静态）**：`audio_output`
- **必填载荷**：无必填（空载荷落到该位默认 op；位内更细的 op 参数见模块）
- **常见错误**：参数非法 → `user_error`
- **它做什么**：身体·音量：读或设主音量（参数 level 0~1；不传则只读）
- **怎么调**：`py -3.14 tools/codex-scripts/five-dim.py cap body_volume '<json>'`
- **失败三态**（本仓统一口径，不是这一位特有）：`denied` = 缺票，会点名`missing_scopes`；`needs_*` = 缺参/缺依赖，会带原因；`failed` = 真失败，回执带上游原话。**信封 `status=ok` ≠ 本体 `ok=true`。**

### `bt_control`

- **域**：`device`（设备）
- **类型**：只读（不改状态、不出网） · **需参数**：否
- **要哪张票（静态）**：`device_control`
- **必填载荷**：无必填（空载荷落到该位默认 op；位内更细的 op 参数见模块）
- **常见错误**：参数非法 → `user_error`
- **它做什么**：AI 智能蓝牙操控：自然语言意图→扫描识别设备→协议匹配→组装指令→写入执行→验证（协议库只收公开文档协议，未知如实报告）
- **怎么调**：`py -3.14 tools/codex-scripts/five-dim.py cap bt_control '<json>'`
- **失败三态**（本仓统一口径，不是这一位特有）：`denied` = 缺票，会点名`missing_scopes`；`needs_*` = 缺参/缺依赖，会带原因；`failed` = 真失败，回执带上游原话。**信封 `status=ok` ≠ 本体 `ok=true`。**

---

返回 [能力总表](../03-capabilities.md)
