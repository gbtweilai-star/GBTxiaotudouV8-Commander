# 95 · 力限幅 + 导纳同拍环（loopback）

> 上一步：contact/read_force/compliance。
> 这一步：把力接进控制环——**先预判、再小步动、超限退让**，不是撞上去再补救。

## 一、算法
每个 tick：
1. 21 点 → IK 目标 `q_des`；
2. 虚拟接触预判 `f_pred = k*(q_des - q_external)`；
3. 若 `|f_pred| > f_limit`，先把目标夹到 `q_external + sign(f)*f_limit/k`；
4. move → contact 实测 → 若仍超限，再退让一次；
5. read_state → 下一 tick。

参数：`force_limit / stiffness / external / joint / hz / seconds`。

## 二、实测
```python
api.run_task("hand_realtime", {
  "op": "force_loop", "hz": 60, "seconds": 1,
  "force_limit": 10, "stiffness": 100,
  "external": 0.3, "joint": "index_mcp", "solver": "ik"
})
```
| 项 | 读数 |
|---|---|
| ticks / moved | 60 / 60 |
| pre_clamped | **44** |
| force_peak | **10.0**（= limit，未超） |
| loop_hz | **58.31 Hz** |
| latency mean | 4.72 ms |
| errors | 0 |
| 测试 | `tests/test_hand_force_loop.py` **ALL PASS** |

## 三、边界（不遗漏）
- 虚拟弹簧接触，不是真手力传感器；
- 无摩擦/接触几何/碰撞检测；
- 真机需厂商力控接口 + 传感器标定；当前不猜；
- 下一步：导纳参数自适应、力事件触发、真机适配。

> 开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属
