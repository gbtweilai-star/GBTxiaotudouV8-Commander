# 15 · 设备控制 (`device`)

> 9 能力位 · 七根身体感官 + 六根身体动作 + 蓝牙 BLE
>
> 自然语言意图 → 识别 → 协议匹配 → 执行 → 验证
>
> 开发者：自由的风 · 本署名不可删除、不可篡改归属

---

## 能力清单（逐位，取自注册表 · 全部只读）

### 蓝牙（2 位）

| 能力位 | 说明 |
|---|---|
| `bluetooth` | 蓝牙设备控制：扫描附近 BLE 设备、连接读写 GATT 特征（操控空调/灯/音箱等家居设备）、经典蓝牙状态报告 |
| `bt_control` | AI 智能蓝牙操控：自然语言意图→扫描识别设备→协议匹配→组装指令→写入执行→验证（协议库只收公开文档协议，未知如实报告） |

### 身体桥（7 位 · `body_*`）

| 能力位 | 参数 | 说明 |
|---|---|---|
| `body_map` | — | 身体·清单：现读这台设备的**七根感官与六根动作**（零作用域，只读） |
| `body_see` | `monitor`（可选） | 身体·看：截当前屏幕落 png |
| `body_say` | `text` · `rate`（可选） | 身体·说：系统 TTS 念一句 |
| `body_click` | `x` · `y` · `clicks` | 身体·点：按坐标点按 |
| `body_type` | `text` | 身体·打字：向前台窗口键入文本 |
| `body_open` | `target` | 身体·打开：用系统默认程序打开文件/网址 |
| `body_volume` | `level` 0~1（不传则只读） | 身体·音量：读或设主音量 |

> **七根感官 + 六根动作**：`body_map` 是这一族的"自知"入口——先问清楚这台机器
> 有哪些感官和动作，再谈操控。**不知道有什么，就不该乱动。**

---

## 架构设计

```
    自然语言意图
         │
    ┌────▼────┐
    │ 意图解析 │  "把客厅灯调暗"
    └────┬────┘
         │
    ┌────▼────┐
    │ 设备识别 │  匹配已配对设备
    └────┬────┘
         │
    ┌────▼────┐
    │ 协议匹配 │  BLE GATT服务/特征值
    └────┬────┘
         │
    ┌────▼────┐
    │ 执行     │  写特征值
    └────┬────┘
         │
    ┌────▼────┐
    │ 验证     │  读回确认
    └─────────┘
```

## API参考

### 扫描BLE设备

```python
import gbt_allinone as gbt

result = gbt.run_task("bluetooth", {"op": "scan", "duration": 5})
# 返回: {
#   ok, devices: [{
#     address: "AA:BB:CC:DD:EE:FF",
#     name: "Living Room Light",
#     rssi: -45,
#     services: ["0000fff0-0000-1000-8000-00805f9b34fb"]
#   }]
# }
```

### 读GATT

```python
result = gbt.run_task("bluetooth", {
    "op": "read",
    "address": "AA:BB:CC:DD:EE:FF",
    "service": "0000fff0-0000-1000-8000-00805f9b34fb",
    "characteristic": "0000fff1-0000-1000-8000-00805f9b34fb"
})
# 返回: {ok, value: [0x01, 0x64], hex: "0164"}
```

### 写GATT

```python
result = gbt.run_task("bluetooth", {
    "op": "write",
    "address": "AA:BB:CC:DD:EE:FF",
    "service": "...",
    "characteristic": "...",
    "value": [0x01, 0x32]   # 亮度50%
})
```

### 自然语言操控

```python
result = gbt.run_task("bt_control", {
    "intent": "把客厅灯调暗一点"
})
# 返回: {
#   ok,
#   matched_device: "Living Room Light",
#   protocol: "BLE-GATT",
#   action: "write",
#   value: [0x01, 0x32],
#   verified: true
# }
```

## 支持设备类型

| 类型 | 协议 | 说明 |
|---|---|---|
| 智能灯泡 | BLE GATT | 开关/亮度/色温/颜色 |
| 智能插座 | BLE GATT | 开关/定时 |
| 传感器 | BLE GATT | 温度/湿度/电量读 |
| 手环/手表 | BLE GATT | 心率/步数读 |
| 蓝牙音箱 | A2DP | 播放/暂停/音量 |

## 依赖

```
pip install bleak    # 跨平台BLE库（推荐）
# 或
pip install pybluez  # Windows传统蓝牙
```

缺失时如实报 `needs_dependency`，不静默失败。

---

## 身体桥用法（`body_*` 七位）

### 先问清楚有什么

```python
import gbt_allinone as gbt

result = gbt.run_task("body_map", {})
# 返回: {
#   ok,
#   senses: ["see", "say", "volume", ...],   # 七根感官
#   actions: ["click", "type", "open", ...], # 六根动作
#   platform: "win32"
# }
```

**这是这一族的入口**：先 `body_map` 拿到本机真实清单，再按清单动手。

### 看 / 说 / 听

```python
# 看：截屏
gbt.run_task("body_see", {"monitor": 1})
# 返回: {ok, path: "store/frames/xxx.png"}

# 说：系统 TTS
gbt.run_task("body_say", {"text": "任务完成了", "rate": 1.0})

# 音量：读或设
gbt.run_task("body_volume", {})              # 只读
gbt.run_task("body_volume", {"level": 0.4})  # 设置
```

### 动：点 / 打字 / 打开

```python
# 点：按坐标
gbt.run_task("body_click", {"x": 960, "y": 540, "clicks": 1})

# 打字：向前台窗口
gbt.run_task("body_type", {"text": "hello"})

# 打开：系统默认程序
gbt.run_task("body_open", {"target": "https://example.com"})
gbt.run_task("body_open", {"target": "C:/path/to/file.pdf"})
```

### 与触手的区别

| 维度 | `body_*`（身体桥） | `tentacle`（触手） |
|---|---|---|
| 粒度 | 粗（坐标级/系统级） | 细（UIA 元素级） |
| 依赖 | 零依赖（纯系统 API） | 需 uiautomation / dxcam |
| 定位 | 保底通路 | 主通路 |
| 典型场景 | 系统级动作（音量/打开/TTS） | 界面元素操作 |

**选路原则**：能走触手就走触手（更精确）；触手不可用或只需系统级动作时走身体桥。

---

## 安全边界

| 作用域 | 覆盖 |
|---|---|
| `device_control` | 连接、写入或控制蓝牙及其他外部设备 |

**纪律**：
- 只操作已配对或用户明确指定的设备
- 写操作前读回确认当前状态
- 不改设备固件、不做未授权的配对
- `body_*` 七位在注册表里标**只读**（零作用域），但**动作本身会改屏幕/音量/前台窗口**——纪律靠"先 `body_map` 再动手"这条守，不靠门

> 开发者：自由的风 · GBT小土豆V8 · 独立私人框架，与任何企业公司无关
