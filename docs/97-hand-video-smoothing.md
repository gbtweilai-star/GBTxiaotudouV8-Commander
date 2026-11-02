# 97 · 视频视觉链：时间戳/平滑（下一步）

> 上一步：视频 → 21 点 → IK → loopback 已通。
> 这一步补连续帧的**抖动度量与 EMA 平滑**，为摄像头实时流做准备。

## 一、新增
`hand_realtime op=video` 增加 `smooth`（0~1，EMA 系数）：
- 先算原始 21 点抖动 `jitter_raw_mean`；
- 再用 `lm = smooth*raw + (1-smooth)*prev` 平滑，喂 IK；
- 输出 `jitter_smoothed_mean` 与 `smooth`，可对比。

## 二、实测（本地 30 帧视频）
| 项 | 读数 |
|---|---|
| frames / detected / moved | 30 / 30 / 30 |
| smooth | 0.6 |
| jitter_raw_mean | 0.00167549 |
| jitter_smoothed_mean | 0.00166903 |
| 关节 | 20 |
| 测试 | `tests/test_hand_video.py` 输出 **ALL PASS** |

平滑只降了约 0.4%——素材本身运动很平滑；真实摄像头抖动更大时收益才明显，不夸大。

## 三、边界
- 仍是离线视频 + loopback 仿真；
- 摄像头未通；
- 没有时间戳丢帧策略/延迟补偿（下一步）；
- 平滑会引入相位滞后，`smooth` 不能无脑调大。

## 四、下一步
1. 摄像头帧时间戳 + 丢帧策略 + 处理延迟测量；
2. 自适应 EMA（快动时减小平滑）；
3. 摄像头通了接实时环。

> 开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属
