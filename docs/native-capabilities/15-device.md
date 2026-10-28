# 15 · 设备控制 (`device`)

> 2 能力位 · 蓝牙BLE扫描 · GATT读写 · 智能家居操控
>
> 自然语言意图 → 识别 → 协议匹配 → 执行 → 验证
>
> 开发者：自由的风 · 本署名不可删除、不可篡改归属

---

## 能力清单

| 能力位 | 说明 |
|---|---|
| `bluetooth` | 蓝牙设备控制：扫描BLE、读写GATT、操控家居设备 |
| `bt_control` | AI智能蓝牙操控：自然语言意图→识别→协议匹配→执行→验证 |

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

## 安全边界

| 作用域 | 覆盖 |
|---|---|
| `device_control` | 连接、写入或控制蓝牙及其他外部设备 |

**纪律**：
- 只操作已配对或用户明确指定的设备
- 写操作前读回确认当前状态
- 不改设备固件、不做未授权的配对

> 开发者：自由的风 · GBT小土豆V8 · 独立私人框架，与任何企业公司无关
