# 94 · 力/接触接口（loopback 仿真）

> 下一步：精密操控不能只有位置，还要有“力/接触/柔顺”接口。没有真手硬件，先在 loopback 里把数学和状态机跑通；真机必须 fail-closed。

## 一、新增 op
`hand_bridge`：
- `contact`：`{joint, external, stiffness?, damping?}` → `force = k*(q - q_external)`；仅 loopback；
- `read_force`：读回所有关节力；
- `compliance`：设置虚拟刚度/阻尼；
- 真机（modbus/serial/can）调用这些 → **`needs_hardware`**，不伪造传感器。

## 二、实测
| 项 | 读数 |
|---|---|
| 连接 | loopback / generic_20dof |
| move | index_mcp=0.5 |
| contact | k=100, external=0.2 → **force=30.0** |
| read_force | index_mcp=30.0 |
| compliance | stiffness=50, damping=0.1 |
| 测试 | `tests/test_hand_force.py` **ALL PASS** |

## 三、边界
- 这是**虚拟弹簧接触模型**，不是真手力传感器；
- 没有摩擦/接触几何/碰撞检测；
- 真机需要厂商力控接口 + 传感器标定；当前不猜；
- 下一步可做：阻抗/导纳控制环、力限幅、接触事件 → 与 `hand_realtime` 同拍。

> 开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属
