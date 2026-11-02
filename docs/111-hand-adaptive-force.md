# 111 · 自适应刚度 + 接触事件（长视频链）

> 下一步：力限幅不能只会“夹目标”，还要按接触状态调柔顺。

## 一、实现
`onnx_chunked` 新增：
- `adapt=true`：接触时按 `k *= 0.9` 降低刚度，离触时 `k *= 1.02` 恢复；
- `contact_on/off` 事件（0.8×limit / 0.2×limit 双阈值）；
- `compliance` 每 tick 同步给 loopback；
- 输出 `stiffness_start/end`、`contact_events`、`k_trace`。

## 二、实测（60 帧 / limit=0.5 / external=0）
| 项 | 读数 |
|---|---|
| frames / moved | 60 / 60 |
| force_peak | **0.5（= limit）** |
| pre_clamped | 60 |
| adjustments | 13 |
| stiffness | 100 → **10（k_min）** |
| contact_events | `contact_on` 1 条 |
| fps | 14.81 |
| realtime_ok | true（刚过 10fps 线） |
| 测试 | `tests/test_hand_onnx_chunked_adapt.py` **ALL PASS** |

## 三、结论
- 力峰值不超限；
- 刚度按接触自适应降/升；
- 代价：每帧 `compliance/contact` 调用把 fps 从 42 降到 **14.8**，仍过实时线但余量小；
- 仍是虚拟弹簧模型，不是真手传感器。

## 四、边界 / 下一步
- 摄像头未通；真机需标定 + 力传感器；
- 下一步：接触事件防抖、刚度恢复速率限制、把 compliance 调用降频（每 N 帧），把 fps 拉回 30+。

> 开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属
