# 100 · 常驻推理进程 + tracker 复用 + 三线程流水（结论：本机 CPU 不适合实时手势）

> 按主人指定方向：常驻推理进程、模型只初始化一次、视频帧走 IPC、tracker 复用、采集/推理/IK/HAL 分线程。
> 本次真跑，结论不是“优化成功”，而是有数据证明**本机 CPU 做不到 >10fps/100ms**。

## 一、结构
```
hand_tracker_worker.py（常驻子进程；Hands 只建一次）
   │ stdout JSONL: landmarks + infer_ms
   ▼
hand_pipeline.py:
   read_worker 线程 ──► ik_q ──► ik_worker 线程 ──► hal_q ──► hal_worker 线程
```
- worker 启动 `init_ms` 单独测；
- 每帧 `infer_ms` 由 worker 自己测；
- IK/HAL 各自线程，不是串行；
- 最后 `realtime_ok = (infer_p95 <= 100ms and pipeline_fps >= 10)`。

## 二、实测（30 帧本地视频）
| 项 | 读数 |
|---|---|
| worker | persistent |
| init_ms | **2896.59** |
| worker_frames / ik_done / hal_done | 30 / 30 / 30 |
| infer_ms mean | **506.51** |
| infer_ms p95 | **718.66** |
| ik_ms mean | 127.68 |
| hal_ms mean | 0.13 |
| pipeline_fps | **1.44** |
| realtime_ok | **false** |
| verdict | **本机 CPU 不适合实时手势（infer p95 >100ms / fps<10）** |
| 测试 | `tests/test_hand_pipeline.py` **ALL PASS** |

## 三、结论（照实）
- 常驻 worker + tracker 复用 + 三线程都做了；
- 仍 **1.44fps / infer p95 718ms**，远达不到实时；
- 瓶颈是 MediaPipe 在 Intel CPU 上的推理本身，不是模型初始化、不是线程串行、不是 ROI；
- 因此明确写：**本机 CPU 不适合实时手势**；不拿低 fps 冒充 15fps。

## 四、若还要实时，只剩
1. 换更轻的本地手部关键点模型（ONNX/专用轻量网络）；
2. 换有 GPU/NPU 的硬件；
3. 接受离线/异步，不做实时闭环。

> 开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属
