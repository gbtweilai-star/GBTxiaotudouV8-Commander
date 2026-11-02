# 109 · 长视频链闭环：进程回收 + IK/HAL，150帧 28fps 跑通

> 上一步：chunked_proc 只做视觉，150 帧 21fps。
> 这一步：把 chunk landmarks 交回父进程做 **IK + loopback**，形成完整手部链。

## 一、架构
```
父进程
  ├─ 每 60 帧 spawn hand_onnx_chunk_worker（视觉）
  │     → 子进程加载 ONNX → 处理 → 导出 landmarks.json → 退出
  ├─ 读回 landmarks
  ├─ hand_retarget op=ik / retarget
  └─ hand_bridge loopback.move + read_state
```

## 二、实测（150 帧 / 10s / chunk=60）
| 项 | 读数 |
|---|---|
| frames | **150** |
| hand_frames | **150** |
| ik_ok | **150** |
| moved | **150** |
| chunks | 3 |
| fps | **28.03** |
| seconds | **5.35** |
| ik mean | 0.31 ms |
| chunk visual p95 | 22.38 / 36.61 / 34.51 ms |
| realtime_ok | **true** |
| 测试 | `tests/test_hand_onnx_chunked.py` **ALL PASS** |

## 三、结论
- **长跑退化被真进程回收干掉**；
- 150 帧完整链：21fps（纯视觉）→ **28.03fps（含 IK/HAL）**；
- 为什么含 IK 反而更快？视觉 chunk 模型不退化，父进程 IK 仅 0.31ms；
- 不再拿 30 帧短片段冒充长跑。

## 四、边界
- 仍是离线视频；摄像头未接；
- loopback 仿真，不驱动真手；
- 子进程模型加载 40–62ms/chunk，摊薄可接受；
- 真机需标定 + register_map + confirm。

## 五、下一步
1. 摄像头流按帧数/时间切 chunk + 看门狗；
2. 实时流与离线 chunk 共用同一 IK/HAL 接口；
3. 真机适配。

> 开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属
