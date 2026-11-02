# 98 · 视频时序：时间戳 / 丢帧 / 处理延迟

> 上一步：EMA 平滑；这一步补时序，避免“处理比视频还慢却不自知”。

## 一、新增
`hand_realtime op=video` 参数：
- `max_fps`：按视频时间戳丢弃过密帧；
- 输出：
  - `dropped_frames`
  - `process_latency_ms_mean / p95`（MediaPipe+IK+move）
  - `frame_age_s_mean`（当前墙钟 − 视频时间戳）

## 二、实测（30 帧 / 15fps 素材，`max_fps=10`）
| 项 | 读数 |
|---|---|
| frames | 30 |
| detected / moved | 15 / 15 |
| dropped | **15** |
| process_latency mean/p95 | **176.95 / 776.41 ms** |
| frame_age mean | **10.751 s** |
| 测试 | `tests/test_hand_video_timing.py` 输出 **ALL PASS** |

**重要**：处理延迟远高于视频帧间隔，帧年龄超过 10s。这说明本机 CPU 上 MediaPipe+IK+loopback 还不够实时；不能拿“处理了 15 帧”冒充实时 15fps。

## 三、边界
- 离线视频批处理，不是摄像头流；
- `max_fps` 是**丢弃**，不是加速；
- 延迟由 CPU 推理/IK 决定，不是网络；
- 摄像头仍未通。

## 四、下一步
1. 降分辨率/跳帧 ROI（先检测手部区域，再裁切）以降低 MediaPipe 延迟；
2. 自适应平滑（快动少平滑）；
3. 摄像头通后做真实端到端延迟。

> 开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属
