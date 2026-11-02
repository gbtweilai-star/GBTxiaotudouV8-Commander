# 96 · 手部视频 → 21 点 → IK → loopback（离线视觉链）

> 摄像头仍未通；先用**本地手部视频**把“连续帧视觉 → 关节 → 手”的链跑通，不拿单张图冒充实时。

## 一、链路
```
本地视频帧
→ MediaPipe Hands（本地 tflite）
→ 21×[x,y,z]
→ hand_retarget op=ik（20-DoF）
→ hand_bridge loopback.move
```

## 二、实测
测试素材：`tests/fixtures/hand-motion.mp4`（本地手图生成的 2s/30帧运动镜头）
```python
api.run_task("hand_realtime", {"op": "video", "video": "hand-motion.mp4", "solver": "ik"})
```
| 项 | 读数 |
|---|---|
| frames | 30 |
| detected_frames | **30/30** |
| moved_frames | **30/30** |
| joint_count | 20 |
| 处理 fps | 12.88 |
| 传输 | loopback（simulated） |
| 测试 | `tests/test_hand_video.py` 输出 **ALL PASS**（MediaPipe 原生日志有 stderr 噪声） |

## 三、边界
- 这是**离线视频批处理**，不是摄像头实时流；
- 素材是本地生成的手部运动镜头，不是真人实拍；
- loopback 是仿真手，不驱动真手；
- 摄像头要等 Windows 隐私/采集后端放行；
- 真机仍需标定 + register_map + confirm。

## 四、下一步
1. 摄像头通了 → `hand_vision camera` 帧直接进这个 `video`/实时环，目标 15–30fps；
2. 加时间戳/丢帧策略/平滑滤波；
3. 真机力控/接触再接。

> 开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属
