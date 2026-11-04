# 90 · 手指数值 IK · 细节与边界

> 对应「细节点别把重要东西遗漏」。本页写清 `hand_ik` 到底解什么、不解什么、怎么验。

## 一、问题
`hand_retarget` 的几何法直接从骨段夹角读屈曲：快，但它是量角器，不是追目标。
需要 IK 时，目标不是“看起来弯”，而是**指尖/关节落在观察到的 3D 点**，且关节不越限。

## 二、实现（无第三方依赖）
对每根手指（thumb/index/middle/ring/pinky）：

1. **手指平面**：x = 腕→中指 MCP（所有手指共用掌前向）；n = x × (TIP−MCP)；y = n × x。
2. **目标投影**：把 MCP/PIP/DIP/TIP 投到该平面，得到 t2/t3/t4。
3. **骨长**：L1=‖MCP→PIP‖、L2=‖PIP→DIP‖、L3=‖DIP→TIP‖。
4. **3-link FK**：
   - q2 = L1·[cos a1, sin a1]
   - q3 = q2 + L2·[cos(a1+a2), sin(a1+a2)]
   - q4 = q3 + L3·[cos(a1+a2+a3), sin(a1+a2+a3)]
5. **box-constrained 坐标下降**：对 a1/a2/a3 逐维网格搜索，最小化 q2/q3/q4 与 t2/t3/t4 的平方误差；每维夹在模型关节限位内；12 轮 × 25 格。
6. 输出 MCP/PIP/DIP 角度 + 每指 `rms_m` 残差 + `limit_hits`；外展仍沿用几何解。

## 三、实测
| 用例 | 结果 |
|---|---|
| 直手 | 非拇指屈曲 ≤0.05 rad；残差 0 |
| 弯食指 | `index_mcp=0.785`、`index_pip=1.249`、`index_dip=0.644`；残差 **5.76e-4 m** |
| 限位 | 15 关节全部在模型限位内 |
| 万能插 `op=ik` | 返回关节角 + 残差 + 命中 |
| 同拍 loop（IK） | **60/60 tick，58.35 Hz，6.04 ms 平均** |
| 测试 | `tests/test_hand_ik.py`、`tests/test_hand_realtime.py` **ALL PASS** |

## 四、边界（重要，不遗漏）
- **每指平面 3-link**，不是全手 21-DoF 全局 IK；手指侧摆/对掌仍是近似；
- 没有接触/触觉/力控模型；没有真手硬件；
- loopback 是**仿真状态机**，`simulated=true`；真机需 `register_map` + `confirm`；
- Modbus TCP 是协议帧，不等于已连上某台手；
- 相机手部跟踪输入未接（当前用 21 点流/合成轨迹验证闭环）；接摄像头需本地手部关键点模型。

> 开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属
