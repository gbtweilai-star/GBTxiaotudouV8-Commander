# 89 · 眼手脑同拍 · 灵巧手 loopback 跑通

> 对应主人问：「触手不是吞噬过机械手精密操控能力吗？没有就补齐跑通。」
> 结论：`hand_retarget` / `hand_bridge` 没丢；本次把两者接成**同一拍闭环** `hand_realtime`，并跑通测试。

## 一、链路（同一 tick）
```
21 点手部流（landmarks）
  → hand_retarget（15/20 DoF 几何重定向）
  → hand_bridge（loopback 手 HAL：move）
  → read_state（回读）
  → 下一帧，采集/重定向/动作/回读同拍
```
不是 `see → 子进程 → click` 的三段式。

## 二、实测（本地，无网络/无硬件）
| 指标 | 读数 |
|---|---|
| ticks | 60（60Hz × 1s） |
| moved | **60/60** |
| loop_hz | **57.98 Hz** |
| latency mean | **0.31 ms** |
| latency p95 | **0.6 ms** |
| errors | 0 |
| transport | loopback（simulated，不驱动真手） |
| 测试 | `tests/test_hand_realtime.py` **ALL PASS** |

调用（万能插）：
```python
api.run_task("hand_realtime", {"op": "loop", "hz": 60, "seconds": 1.0})
```

## 三、已补齐 vs 仍缺
| 项 | 状态 |
|---|---|
| 21 点 → 15/20 DoF 关节角 | ✅ |
| 手 HAL loopback 真状态机 | ✅ |
| 眼/脑/手同拍 58Hz | ✅ |
| Modbus TCP 真帧 / 串口 / CAN | ✅ 协议层；真机需 register_map + confirm |
| 逆运动学（IK）优化 | ✅ 每指平面 3-link box-constrained IK；`op=ik`；同拍 58.35Hz / 6.04ms |
| 接触/触觉/力控 | ❌ 无硬件、无模型，不假装；真机需 register_map + confirm |
| 真机精密操控 | ❌ loopback 不是真手 |

> 开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属

