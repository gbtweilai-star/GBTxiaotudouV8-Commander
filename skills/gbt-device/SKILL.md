---
name: gbt-device
displayName: GBT 设备域（蓝牙 · AI 蓝牙操控）用法规程
version: 1.0.0
description: GBT小土豆V8 的「设备职业域」用法规程 —— 把图鉴里 domain=device 的 2 个能力位（bluetooth / bt_control）蒸馏成能照着跑的一页：每位写清用途、只读还是要授权、真命令模板、要什么参数、失败典型样子、依赖什么（适配器/驱动/权限），并附一份**实测过的诚实账**与**本机蓝牙实测状态**（有没有适配器、能否枚举、扫描结果是什么 —— 只写实测，不许把"能调"写成"能用"）。当用户要「扫蓝牙 / 连蓝牙设备 / 用蓝牙控空调灯音箱 / 经典蓝牙配对状态」，或设备域能力位被门拦住、扫描没结果、搞不清哪一步要 device_control 授权时使用。
triggers:
  - "设备域"
  - "device 域"
  - "蓝牙"
  - "BLE"
  - "扫描蓝牙设备"
  - "连蓝牙"
  - "配对"
  - "经典蓝牙"
  - "蓝牙适配器"
  - "用蓝牙控空调"
  - "智能家居"
  - "GATT"
  - "device_control"
---

# GBT 设备域（device）用法规程

> 开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属
>
> 这是「人类视角操控一切」在**设备这一格**的用法：`gbt-omni` 负责"人话落到哪个能力位"，
> 本规程负责"落到设备域这 2 位之后，命令长什么样、哪一步要授权、失败长什么样、
> **本机蓝牙到底能不能用**"。

**唯一现读入口（别信任何二手描述，包括本文件）**：

```powershell
py -3.14 tools/codex-scripts/omni.py list --domain device      # 这 2 位是什么（图鉴现扫）
py -3.14 tools/codex-scripts/omni.py ask  "扫描一下附近的蓝牙设备"
```

**⚠️ `omni list` 标的 🔒 不等于"这一位一概不能跑"** —— 它是拿**空参数**静态算出来的
`device_control`（见 §2 第 3 条）。同一发命令**换 `op` 就能免卡**，
这是本域最反直觉、也最容易读错的一处。

---

## 0. 两位一个门：`run_task`

2 个能力位**全走同一个门**，唯一入口：

```powershell
py -3.14 tools/codex-scripts/five-dim.py cap <能力位> ['{"参数": ...}']
```

**没有第二条路**：不许直接 import 模块函数、不许自己写脚本绕过 `run_task` —— 那等于绕门。

**域怎么定的**：以 `state/skill_atlas.json` 里 `domain == "device"` 的条目为**准**（现扫读数 2 条）。
不是谁记得的清单，也不是本文件说了算。

---

## 1. 两位总表（一页看全）

| 能力位 | 用途（图鉴原文） | 门 | 参数 | 实测判定 |
|---|---|---|---|---|
| `bluetooth` | 蓝牙设备控制：扫描附近 BLE 设备、连接读写 GATT 特征（操控空调/灯/音箱等家居设备）、经典蓝牙状态报告 | **按 `op` 分档**：`status`/`scan`/`list` 免卡；其余（含 `classic`/`connect`/`read`/`write`/空参数）要 `device_control` | `op` + 该 op 自己的参数 | ✅ `status`/`scan` 真跑通 · 🔒 `classic`/`connect` 被门拦住（未验） |
| `bt_control` | AI 智能蓝牙操控：自然语言意图→扫描识别设备→协议匹配→组装指令→写入执行→验证（协议库只收公开文档协议，未知如实报告） | 同上；且 **`parse_intent` / `identify` / `control` 全都不在白名单里 ⇒ 一律要 `device_control`** | `op` / `intent` / `address` / `scan_timeout` | ⚠️ `status` 真跑通 · 🔒 `parse_intent` 被门拦住（未验） |

**两位的关系不是两个工具，是"手"和"脑"两层**（源码 `gbt_allinone/bt_control.py` 抬头自述）：

- `bluetooth` = **手**：`scan` / `connect` / `read` / `write` / `classic` / `status` 原语；
- `bt_control` = **脑**：意图解析 → 设备识别 → 协议匹配 → 指令组装 → 闭环验证，
  真正的写入最后还是**调 `bluetooth` 的手**去写。

---

## 2. 门：哪一步要授权（**以 policy 实测为准**）

### 1) 静态查出来的作用域

`gbt_allinone/security/policy.py` 里两位**共用一个分支**，规则是"**列白名单**"：

```python
elif kind == "bluetooth":            # 288-290 行
    if op not in ("status", "scan", "list"):
        add("device_control")
elif kind == "bt_control":           # 291-293 行
    if op not in ("status", "scan", "list"):
        add("device_control")
```

`device_control` 的口径原文（`auth_gate.py` 第 50 行 `SCOPES` 表；
`policy.py` 第 32 行是同一句话的作用域表）：
**「连接、写入或控制蓝牙及其他外部设备」**。`omni.py` 的静态探查（空参数）读数：

```
bluetooth   -> ('device_control',)   risk=high
bt_control  -> ('device_control',)   risk=high
```

### 2) 空参数最坑：`bluetooth` 不带 `op` = 默认走 `scan`，但门按空 op 判 ⇒ 要授权

```powershell
py -3.14 tools/codex-scripts/five-dim.py cap bluetooth        # ⚠️ 被拒！
py -3.14 tools/codex-scripts/five-dim.py cap bluetooth '{"op":"scan","timeout":5}'   # ✅ 免卡
```

实测（`policy.evaluate` 直查）：

| 调用 | 静态作用域 | 说明 |
|---|---|---|
| `bluetooth`（空 payload） | `('device_control',)` | 路由上默认 `op="scan"`，**但门拿不到 `op`，按空 op 判 ⇒ 拒** |
| `bluetooth {"op":"status"}` | `()` | 免卡 |
| `bluetooth {"op":"scan"}` | `()` | 免卡 |
| `bluetooth {"op":"classic"}` | `('device_control',)` | 免卡不了 |
| `bt_control {"op":"parse_intent",...}` | `('device_control',)` | **纯本地正则，也要卡** |
| `bt_control {"op":"control",...}` | `('device_control',)` | 要卡（真会连设备） |

**踩坑记录（不许再踩）**：`cap bluetooth` 不带 payload 会被门拒；这不是"扫描要授权"，
是**空 op 被 fail-closed 兜住了**。要扫码就写明 `{"op":"scan"}`。

### 3) 被拒时**长什么样**（不许绕门，照抄去要授权）

被拒返回的是**扁平错误信封**（顶层，没有 `gbt_result`）：

```json
{
 "status": "denied",
 "kind": "bluetooth",
 "denied": true,
 "message": "capability requires human authorization",
 "reason": "需要人工授权（device_control）：连接、写入或控制蓝牙及其他外部设备",
 "scopes": ["device_control"],
 "missing": ["device_control"],
 "how_to_grant": [
  "终端运行: python -m gbt_allinone auth grant --scope device_control --ttl 600",
  "或主人手写 store/auth_grants.jsonl 追加一行（格式见 auth_gate.SCOPES 与 README）"
 ],
 "note": "授权一次性消耗；AI 调用路径无权自行发放"
}
```

**授权只能主人在终端发放**。`ai_can_grant = false`（实测 `auth_gate.status()` 读数），
本机当前 `device_control` 可用授权 **0** 条、`owner_control` **0** 条。
AI 永远无权给自己发授权 —— **缺就如实报缺什么，不许找旁路、不许改 `policy.py`**。

---

## 3. `bluetooth`（手 · 原语层）怎么调

### 3.1 `op` 清单（源码 `bluetooth_cap.run` 实认 6 个）

| `op` | 干什么 | 参数 | 门 |
|---|---|---|---|
| `status` | 报后端就绪度（**不碰硬件**） | 无 | 免卡 |
| `scan` | 真扫附近 BLE 广播（**不配对、不连接**） | `timeout`（秒，默认 5.0）· `name_filter` | 免卡 |
| `classic` | 只读枚举 Windows 蓝牙栈里的 PnP 设备 | 无 | 🔒 `device_control` |
| `connect` | **连上**设备并列出 GATT 服务 | `address`（MAC）· `timeout`（默认 20） | 🔒 `device_control` |
| `read` | 读一个 GATT 特征（hex 回读） | `address` · `char_uuid` · `timeout` | 🔒 `device_control` |
| `write` | **写** GATT 特征（真改设备状态） | `address` · `char_uuid` · `value_hex` | 🔒 `device_control` |

**`read` 也归 `device_control`** —— 别以为"读"就免卡；policy 的白名单只有 `status`/`scan`/`list`。

### 3.2 真命令（**本机跑过的原样**）

```powershell
# ✅ 后端就绪度（只读，本机真跑通）
py -3.14 tools/codex-scripts/five-dim.py cap bluetooth '{"op":"status"}'

# ✅ 真扫 BLE（免卡，本机真跑通）
py -3.14 tools/codex-scripts/five-dim.py cap bluetooth '{"op":"scan","timeout":5}'

# 🔒 要 device_control：只读枚举经典蓝牙 PnP（本机未跑通，卡在授权门）
py -3.14 tools/codex-scripts/five-dim.py cap bluetooth '{"op":"classic"}'

# 🔒 要 device_control：列出某设备 GATT 服务（本机未跑，卡在授权门）
py -3.14 tools/codex-scripts/five-dim.py cap bluetooth '{"op":"connect","address":"XX:XX:XX:XX:XX:XX"}'

# 🔒 要 device_control：读一个特征（本机未跑，卡在授权门）
py -3.14 tools/codex-scripts/five-dim.py cap bluetooth '{"op":"read","address":"XX:XX:XX:XX:XX:XX","char_uuid":"00002a19-0000-1000-8000-00805f9b34fb"}'

# ⛔ 会改设备状态的写入：本规程**不建议**手搓，走 bt_control 的脑
# py -3.14 tools/codex-scripts/five-dim.py cap bluetooth '{"op":"write","address":"...","char_uuid":"...","value_hex":"01"}'
```

### 3.3 真返回字段（**本机实测原样抄**）

`{"op":"status"}` 内层 body：

```json
{"ok": true,
 "ble_backend": "bleak",
 "classic_backend": "win-bluetooth-stack",
 "ops": ["scan","connect","read","write","classic","status"],
 "note": "scan/connect/read/write 控制 BLE 设备；classic 报告已配对经典设备"}
```

`{"op":"scan","timeout":5}` 内层 body（**本机 2026-09-22 实测**）：

```json
{"ok": true, "backend": "bleak",
 "devices": [{"address":"70:89:7F:34:A4:92","name":"(未命名)","rssi":-92},
             {"address":"73:9E:DE:32:43:E6","name":"(未命名)","rssi":-82},
             {"address":"63:43:0B:BE:D8:C6","name":"(未命名)","rssi":-49},
             {"address":"7D:EB:92:41:B5:4D","name":"(未命名)","rssi":-58},
             {"address":"43:36:A3:BF:34:E1","name":"(未命名)","rssi":-75}]}
```

**字段怎么读**：`devices[].address` = BLE 地址（**Windows 上未必是硬件 MAC**，
是系统给的身份标识，随机化地址很常见）· `name` = 广播名（`"(未命名)"` = 该设备没广播名字）·
`rssi` = 信号强度 dBm（**越接近 0 越强**；-49 很近，-92 基本在边缘）。

### 3.4 失败典型样子

| 失败 | 真实返回 | 根因 / 下一步 |
|---|---|---|
| 没装 bleak | `{"ok": false, "status": "needs_dependency", "missing": "bleak", "install": "python -m pip install bleak"}` | 装依赖 |
| 蓝牙没开 / 适配器不在位 | `{"ok": false, "error": "扫描失败: ...", "hint": "确认蓝牙已开启（bthserv 运行 + 适配器在位）"}` | 查 `bthserv` 与适配器 |
| 设备不在范围内 / 是经典设备 | `{"ok": false, "error": "连接失败: Device with address AA:BB:CC:DD:EE:FF was not found.", "hint": "确认设备在范围内、未连接、且非经典蓝牙(音箱类)"}` | **本机实测原样**（拿一个不存在的地址探的） |
| 读特征失败 | `{"ok": false, "error": "读取失败: Device with address ... was not found."}` | 同上 |
| 值不是 hex | `{"ok": false, "error": "value_hex 非法：需十六进制字符串（如 '01' 或 '01ff00'）"}` | 给 hex，**不带 `0x` 前缀**（带了他会自己剥） |
| 特征不支持写 | `{"ok": false, "error": "写入失败: ...", "hint": "确认特征 UUID 支持 WRITE/WRITE_NO_RESPONSE 属性（先 connect 探查）"}` | 先 `connect` 探属性 |
| 未知 op | 抛 `ValueError: 未知 op: xxx（可用: scan/connect/read/write/classic/status）` | 拼错 op 名 |

### 3.5 依赖什么（**本机实测读数**）

| 依赖 | 本机状态 |
|---|---|
| Python | **3.14.5**（cpython-314-64） |
| `bleak`（BLE 后端） | ✅ **3.0.2**，位于 `...\pythoncore-3.14-64\Lib\site-packages\bleak\` |
| WinRT 支撑包 | ✅ `winrt-runtime` 3.2.1 + `Windows.Devices.Bluetooth` / `.Advertisement` / `.Enumeration` / `.Foundation` / `.Storage.Streams` 全 3.2.1（**`bleak-winrt` 已不需要，本机也没装**） |
| 蓝牙适配器 | ✅ **RZ608 Bluetooth(R) Adapter**（`USB\VID_0E8D&PID_0608&MI_00`），PnP `Status = OK` |
| 蓝牙支持服务 | ✅ `bthserv` = **Running**（StartType Manual） |
| 权限 | 见 §2：`scan`/`status` 免卡；其余 `device_control`，**只能主人发** |

---

## 4. `bt_control`（脑 · 智能层）怎么调

### 4.1 `op` 清单（源码 `bt_control.run` 实认 5 个）

| `op` | 干什么 | 参数 | 门 |
|---|---|---|---|
| `status` | 报可用 op + 协议库清单（**不碰硬件**） | 无 | 免卡 |
| `parse_intent` | 自然语言 → `{device_type, action, params}`（**纯本地正则，不碰硬件**） | `intent` | 🔒 `device_control`（**白名单没它**） |
| `smart_scan` | 扫描 + 按广播名预判生态 | `scan_timeout`（默认 8.0） | 🔒 `device_control`（**白名单没它**） |
| `identify` | 连上设备、读 GATT 服务清单 → 匹配协议库 | `address` | 🔒 `device_control`（会连接） |
| `control` | 端到端：意图 → 定位设备 → 识别协议 → 执行 → 验证 | `intent` · `address`（可选）· `scan_timeout` | 🔒 `device_control`（会连接/写入） |

⚠️ **`parse_intent` 明明是纯本地计算，却也要 `device_control`** —— 因为 `policy.py` 的白名单
只写了 `status`/`scan`/`list`，`parse_intent` 不在里面，被 **fail-closed** 兜住了。
这是**已知的过度收紧**，如实报，**不许绕**（要跑就请主人发 `device_control`）。

### 4.2 真命令

```powershell
# ✅ 协议库与 op 清单（只读，本机真跑通）
py -3.14 tools/codex-scripts/five-dim.py cap bt_control '{"op":"status"}'

# 🔒 要 device_control（本机被门拦住，未验）
py -3.14 tools/codex-scripts/five-dim.py cap bt_control '{"op":"parse_intent","intent":"空调调到26度"}'

# 🔒 要 device_control（本机未跑，卡在授权门）
py -3.14 tools/codex-scripts/five-dim.py cap bt_control '{"op":"smart_scan","scan_timeout":8}'
py -3.14 tools/codex-scripts/five-dim.py cap bt_control '{"op":"identify","address":"XX:XX:XX:XX:XX:XX"}'
py -3.14 tools/codex-scripts/five-dim.py cap bt_control '{"op":"control","intent":"开灯"}'
```

### 4.3 真返回字段（本机实测原样抄）

`{"op":"status"}` 内层 body：

```json
{"ok": true,
 "ops": ["control","smart_scan","parse_intent","identify"],
 "protocol_library": ["Xiaomi Mi","Tuya BLE","HID over GATT","Apple Continuity",
                      "Nordic UART (NUS)","Device Information","HomeKit HAP","Battery Service"],
 "note": "AI 操控层：意图→识别→协议→执行→验证；协议库只收公开文档协议"}
```

**协议库 8 条**（源码 `PROTOCOL_LIBRARY` 逐条带 `source` 出处，**全部来自公开文档/蓝牙 SIG 规范**）：

| 服务 UUID（前缀） | 协议 | 能控什么 | 配对要求 |
|---|---|---|---|
| `6e400001-...` | Nordic UART (NUS) | DIY/ESPHome 开源设备，**唯一能直接写文本命令的一类** | 通常无需配对 |
| `0000fe00-...` | Tuya BLE | 涂鸦生态智能灯/插座/空调伴侣 | 需配对密钥 |
| `0000fe95-...` | Xiaomi Mi | 米家生态 | 需米家账号级配对 |
| `00000096-0026bb765291` | HomeKit HAP | HomeKit 认证家居 | 需 HAP 配对（TLV8 加密） |
| `00001812-...` | HID over GATT | 键盘/鼠标/遥控（连接即被 OS 接管） | 系统配对 |
| `d0611e78-...` | Apple Continuity | iPhone/iPad/Mac/Watch | 需 Apple 认证（**来源标注"逆向公开文档，非官方"**） |
| `0000180f-...` | Battery Service | 任意 BLE 外设电量（特征 `0x2A19`） | 无需（**只读**） |
| `0000180a-...` | Device Information | 厂商/型号/序列号 | 无需（**只读**） |

### 4.4 失败典型样子

| 失败 | 真实返回 | 根因 / 下一步 |
|---|---|---|
| 意图解析不出来 | `{"ok": false, "error": "无法解析意图", "hint": "示例：'空调开机' / '空调调到26度' / '开灯' / '扫描设备' / '查电量'", "supported": [...]}` | 换说法；**本机实测原样**（喂"把那个弄一下"就是这条）|
| 意图为空 | `{"ok": false, "error": "缺少意图文本"}` | `intent` 没给 |
| 附近扫不到设备 | `{"ok": false, "error": "附近无 BLE 设备"}` | 设备没广播 / 距离远 |
| 扫描本身失败 | `{"ok": false, "error": "扫描失败", "detail": {...}}` | 看 `detail` 里 `bluetooth` 的原报错 |
| 发现了但没给地址 | `{"ok": false, "status": "need_address", "candidates": [...前5台...], "message": "发现多台设备，请指定地址或用 identify 逐台识别", "hint": "control(intent='...', address='XX:XX:...')"}` | **这是正常的二次确认**，不是错 |
| 设备需配对/私有协议 | `{"ok": false, "status": "needs_pairing_or_protocol", "paths": [{"protocol":..., "requirement":..., "how":...}], "hint": "配对类设备：Windows 设置→蓝牙→配对后重试；或提供该型号的公开协议码..."}` | **框架如实报"做不了"**，不伪造执行 |
| 没匹配到公开协议 | `{"ok": false, "message": "未匹配到可控协议（设备无公开控制服务）"}` | 厂商私有协议，需型号/协议码 |
| 连不上 | `{"ok": false, "error": "连接失败", "detail": {...}}` | 同 §3.4 |
| `identify` 没给地址 | `{"ok": false, "error": "identify 需要 address"}` | 补 `address` |
| 查电量没给地址 | `{"ok": false, "error": "查电量需指定设备地址（先 discover）"}` | 先 `smart_scan` |

**`control` 只对 NUS 一类真写**：其余一律走"如实报告控制路径"分支 —— **它不会假装成功**。
这是本域最值得信任的一点，也是"未知如实报告"这条设计红线的落地。

---

## 5. 🔴 报告层三条红线（**读返回值时必须守**）

### 红线 ①：被拒返回的是**扁平信封**，没有 `gbt_result`

被拒时**顶层就是 body**：`status` / `denied` / `missing` / `reason` / `how_to_grant` 全在顶层。
**不许**只读 `r["gbt_result"]` —— 那会读到空气，然后把"门明明拒了"报成
`status: unknown · denied: false`。
（`five-dim.py` 第 108-113 行的注释记着这个真实事故：**门说拒了，报表说未知、没拒** ——
"这正是给故障喘息：读的人以为只是没跑通，不会去看缺什么授权"。
所以 `cap` 被拒时会把 `missing_scopes` / `reason` / `how_to_grant` 原样打出来。）

**通过的调用反而是嵌套的**：顺利时 `gbt_result` 是
`{"status":"ok","kind":...,"result":{...内层真 body...}}` —— 真 body 在**第二层 `result`** 里。

### 红线 ②：外层 `status:"ok"` ≠ 本体 `ok:true`

**这是两层不同的东西**，别混：

- 外层 `gbt_result.status == "ok"` = **门放行了、任务跑完了**（流程层）；
- 本体 `result.ok` = **这件事本身成了**（业务层）。

**本机实测的反例**（拿一个不存在的地址 `AA:BB:CC:DD:EE:FF` 探的，没碰任何真设备）：

```json
{"ok": false, "error": "连接失败: Device with address AA:BB:CC:DD:EE:FF was not found.",
 "hint": "确认设备在范围内、未连接、且非经典蓝牙(音箱类)"}
```

**本体明明 `ok:false`，但经 `run_task` 出来外层仍是 `status:"ok"`**
（`api.py` 只在授权被拒/未知能力位时改外层 `status`，目标函数自己返 `ok:false` 不改外层）。

⇒ **判成败必须看 `result.ok`，不许看 `status`。**

### 红线 ③：**退出码不可信**

`five-dim.py cap` 的退出码只看外层：

```python
return 0 if out["status"] in ("ok", "success") else 1
```

⇒ **本体失败（`ok:false`）而外层 `status:"ok"` 时，退出码照样是 `0`。**
**不许拿 `$LASTEXITCODE -eq 0` 当"这事办成了"的证据** —— 必须打开 JSON 读 `result.ok`。

**正确读法（三步，一步都不能省）**：

1. 看有没有 `gbt_result` —— 没有 ⇒ 被拒，去读顶层 `missing` / `how_to_grant`，**停**；
2. 有 ⇒ 进 `gbt_result.result` 读**本体**返回值；
3. 判 `content.result.ok`（可能在更深一层），**别用 `status` 代替、别用退出码代替**。

---

## 6. 诚实账（**这一段是拿真跑换来的，不许写成"能用"**）

### 6.1 真跑过的（命令 → 真实读数 → 判定）

| 命令 | 关键返回 | 判定 |
|---|---|---|
| `cap bluetooth '{"op":"status"}'` | `status:"ok"` · 本体 `ok:true` · `ble_backend:"bleak"` · `classic_backend:"win-bluetooth-stack"` · 6 个 op | ✅ **可用**（只读自报） |
| `cap bluetooth '{"op":"scan","timeout":5}'` | `status:"ok"` · 本体 `ok:true` · `backend:"bleak"` · **5 台设备**（RSSI -49/-58/-75/-82/-92），**名字全是 `(未命名)`** | ✅ **真能扫**（扫的是广播，不是"能连"） |
| `cap bluetooth '{"op":"classic"}'` | `status:"denied"` · `missing:["device_control"]` · `stamp:false` | 🔒 **未验 —— 卡在授权门** |
| `cap bluetooth`（空参数） | `status:"denied"` · `missing:["device_control"]` | 🔒 **未验** —— 且这是"空 op 被 fail-closed"的坑（§2 第 2 条） |
| `cap bluetooth '{"op":"connect","address":"AA:BB:CC:DD:EE:FF"}'` | `status:"denied"` | 🔒 **未验 —— 卡在授权门** |
| `cap bt_control '{"op":"status"}'` | `status:"ok"` · 本体 `ok:true` · 4 个 op · 8 条协议库 | ✅ **可用**（只读自报） |
| `cap bt_control '{"op":"parse_intent","intent":"空调调到26度"}'` | `status:"denied"` · `missing:["device_control"]` | 🔒 **未验 —— 卡在授权门**（纯本地计算也被卡） |
| `omni.py list --domain device` | 2 条，两位都标 🔒 | 图鉴口径一致 |
| `omni.py ask "扫描一下附近的蓝牙设备"` | `bluetooth` 得 10.5 分排第一 · 标"要过授权门：device_control" | ✅ 路由正确 |
| `auth_gate.status()` | `ai_can_grant:false` · `device_control` 可用授权 **0** · `owner_control` **0** | 确认**无授权可借** |

### 6.2 未验过的（**如实标"未验 + 卡在哪"**）

| 未验的事 | 为什么没验 |
|---|---|
| **`connect` 真连一台设备** | 🔒 卡在 `device_control` 授权门。**且连上会改变设备状态**（占用连接），按纪律**不做** |
| **`read` 真读一个 GATT 特征** | 🔒 卡在授权门（policy 把 `read` 也归 `device_control`），且需要先 `connect` |
| **`write` 真写一个特征** | ⛔ **会改设备状态，一律不做**。本规程只给命令模板，不替你写 |
| **`classic` 真枚举经典蓝牙** | 🔒 卡在授权门。**注**：同一件事用 `Get-PnpDevice -Class Bluetooth`（PowerShell 只读）**本机已跑通**，见 §6.3 |
| **`bt_control` 端到端 `control` / `smart_scan` / `identify`** | 🔒 卡在授权门；且 `control` 对 NUS 设备会**真写入**，即使有授权也需人明确点单 |
| **配对 / 断开 / 删除配对记录** | ⛔ **改设备状态，一律不做**。配对要走「Windows 设置 → 蓝牙」人或系统动作，**框架不做** |
| **`bt_control` 纯本地 `parse_intent` 真实返回** | 🔒 经门被拦。**注**：直接调模块函数本机能出结果（`{"ok":true,"device_type":"air_conditioner","action":"set_temperature","params":{"temp":26}}`），**但那等于绕门，规程只作旁证记录、不当验收证据** |
| **`identify_device` 协议匹配** | 同上（直调模块可跑：喂 Tuya FE00 + 电量 180F 能匹配出 `Tuya BLE`/`Battery Service`，`confidence:"high"`）；**经门未验** |

### 6.3 本机蓝牙诚实账（三行读完）

1. **有适配器，而且是好的**：`RZ608 Bluetooth(R) Adapter`（`USB\VID_0E8D&PID_0608&MI_00`）
   PnP `Status = OK`，`bthserv` 服务 **Running**，`Get-PnpDevice -Class Bluetooth` 共 **26 条**。
2. **能枚举、能扫描**：`scan` 真扫到 5 台 BLE 广播（RSSI -49 ~ -92 都有）；
   经典侧已配对 **iPhone**（带 Avrcp 传输、电话簿访问 PSE、个人区域网 NAP、服务发现等服务，
   多数 `Status = OK`，少数 `LE 通用属性服务` 行是 `Unknown`）。
3. **但"能调"≠"能用"**：本机**没有任何可直控的智能家居设备**，
   扫到的 5 台**全是 `(未命名)` 广播**（未识别、未连接、未验证协议）；
   `connect`/`read`/`write` 一概**未验**（授权门）；本机 `device_control` 可用授权 **0** 条。
   ⇒ 本域现在能诚实说的是：**"扫描通道在本机确定可用"**，
   **不许**说成"框架能操控我家的蓝牙设备"。

---

## 7. 踩到的坑（写死，别再踩）

1. **`cap bluetooth` 不带 payload ⇒ 被拒**。路由默认 `op="scan"`，但门按**空 op** 判 ⇒ 挂
   `device_control`。想扫码必须写 `{"op":"scan"}`。（§2 第 2 条）
2. **`read` 也要 `device_control`**。别按常识以为"读是只读所以免卡" —— 白名单只有
   `status`/`scan`/`list`。
3. **`bt_control` 的 `parse_intent` 是纯本地正则，照样要 `device_control`**（fail-closed 兜的）。
   已知过度收紧，**如实报，不绕门**。
4. **被拒的信封是扁平的**，没有 `gbt_result`。只读 `gbt_result` 会把"拒绝"读成"未知"。（红线①）
5. **外层 `status:"ok"` 不代表本体成功**（红线②），**退出码 0 更不代表**（红线③）。
6. **BLE 地址 ≠ 硬件 MAC**。Windows 会做地址随机化，`scan` 出的 `address` 只当系统身份用，
   **别当 MAC 写进任何档案**。
7. **扫描到 ≠ 能控**。BLE 广播是全公开的，谁都能听见；"扫到 5 台"只证明**适配器+驱动+权限**这一层通，
   **不证明**对方是可控设备、也不证明框架能写它。
8. **`omni ask` 给的 🔒 是空参数静态算的**。它说"要 device_control"对 `scan` 其实是**偏严**的
   （`scan` 实测免卡）；反过来空参数又确实会被拒。**以本规程 §2 的按 op 分档表为准**。

---

## 8. 验收（做完怎么证明真的做了）

1. **`cap bluetooth '{"op":"status"}'` / `cap bt_control '{"op":"status"}'`** —— 后端就绪度自报（只读）；
2. **`cap bluetooth '{"op":"scan","timeout":5}'`** —— 断言必须能读到 `devices` **非空**
   （全 `(未命名)` 也算通，证明广播通道真在收）；
3. **`omni.py list --domain device`** —— 确认正好 2 位、域口径一致；
4. **被拒的动作**：报告里必须原样写出 `missing_scopes` / `reason` / `how_to_grant`，
   并说明**卡在哪一步**，**不许**把"被门拦住"写成"跑过了"；
5. **读返回值**：按 §5 三步读到底层 `result.ok` 再下结论。

---

## 9. 固化与出处

| 什么 | 在哪 |
|---|---|
| 本规程（源） | `<仓>/skills/gbt-device/SKILL.md` |
| 本规程（装机） | `~/.openclaw-autoclaw/skills/gbt-device/SKILL.md` |
| 图鉴（域口径**唯一真相**） | `state/skill_atlas.json`（`domain == "device"` 的 2 条） |
| 授权门与作用域 | `gbt_allinone/auth_gate.py`（`SCOPES` / 一次性消耗 / `ai_can_grant:false`） |
| 作用域静态规则 | `gbt_allinone/security/policy.py` 第 288-293 行 |
| 手（原语层） | `gbt_allinone/bluetooth_cap.py` |
| 脑（智能层 + 协议库） | `gbt_allinone/bt_control.py` |
| 能力位路由 | `gbt_allinone/api.py` 第 960-975 行 |
| 万能插入口 | `py -3.14 tools/codex-scripts/five-dim.py cap <能力位> ['{...}']` |
| 人话落点 | `py -3.14 tools/codex-scripts/omni.py ask "扫描一下附近的蓝牙设备"` → 落到 `bluetooth` |
| 本件验收 | `py -3.14 tools/codex-scripts/verify-distill.py --domain device --skill gbt-device` |

**依赖是真硬件 + 真驱动 + 真授权**：无适配器 / `bthserv` 停了 / 没装 `bleak`，
或没有主人发的 `device_control`，对应动作就是**做不了** ——
**如实报哪一层断了，不要假装连上了。**
