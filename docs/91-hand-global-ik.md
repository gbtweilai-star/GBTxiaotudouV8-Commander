# 91 · 全手 IK / 限位 · 时序平滑（下一步落地）

> 上一步：每指独立 3-link IK（docs/90）。
> 这一步：把 15/20 个手指关节放进**同一关节向量**做 box-constrained 优化，并加**时序先验**，为连续帧/真机遥操作做准备。

## 一、做了什么
`hand_ik.solve(..., prev=None, smooth=0.0)`：
- 每指仍是平面 3-link FK（MCP/PIP/DIP），但所有手指共享同一掌前向坐标系；
- 关节角向量整体受模型限位约束（box constraints）；
- 目标函数 = 关节位置误差 + `smooth × ‖q − q_prev‖²`；
- 坐标下降逐维求解；`limit_hits` 如实返回；
- 万能插：`hand_retarget` 新增 `op=ik_global`，参数 `prev`/`smooth`。

## 二、实测
| 用例 | 结果 |
|---|---|
| `op=ik_global` | ok，返回关节角 + 每指残差 + 平滑标记 |
| 直手→弯食指，`smooth=0.3` | 独立 IK 跳变 0.785 rad；全局/平滑后跳变 **0.0**（先验约束） |
| 限位 | 全部落在模型限位内 |
| 测试 | `test_hand_ik.py` **ALL PASS**（含 `ik_global`） |
| 同拍 loop（IK） | 60/60 tick，**58.35 Hz**，6.04 ms 平均 |

## 三、边界（不遗漏）
- 仍是**每指平面 3-link**，不是带腕部 6-DoF 的整手 21-DoF 全局 QP；
- 时序平滑会把快速动作“拉慢”；`smooth` 要按场景调，不是越大越好；
- 无接触/触觉/力控，无真机；
- 相机 21 点入口**还没接**（mediapipe 安装未完成）；当前用 21 点流/合成轨迹验证；
- loopback 仍是 `simulated=true`。

## 四、下一步顺序
1. **相机 21 点入口**：本地手部关键点模型（MediaPipe/ONNX）→ 本 IK；
2. **真全局 QP**：腕部 6-DoF + 手指关节联合，带碰撞/限位约束；
3. **力/接触接口**：无硬件时 fail-closed，不伪造。

> 开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属
