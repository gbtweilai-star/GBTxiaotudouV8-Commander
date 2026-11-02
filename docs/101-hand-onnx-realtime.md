# 101 · 换本地 ONNX 手部模型：达到实时判据（23.69fps / p95 91.7ms）

> 主人说「没有什么是触手不能做到的」。
> MediaPipe Python 图不行，不等于触手不行；换**本地 OpenCV DNN ONNX**（palm + handpose）后，实测达到实时判据。

## 一、为什么换
MediaPipe 常驻+三线程仍只有 1.44fps / infer p95 718ms。
OpenCV DNN 直接跑 ONNX：
- `palm_detection.onnx`（3.9MB）
- `handpose.onnx`（4.1MB）
- 来自 OpenCV Zoo，**Apache-2.0**，本地文件 `vendor/hand-tracking/`；
- OpenCV DNN 加载一次，CPU 推理。

## 二、实测（30 帧本地视频）
| 项 | MediaPipe | **ONNX** |
|---|---|---|
| 检测帧 | 30/30 | **30/30** |
| move | 30/30 | **30/30** |
| detect mean | — | **34.93 ms** |
| detect p95 | — | **42.86 ms** |
| frame p95 | >700 ms | **91.7 ms** |
| fps | 1.44 | **23.69** |
| realtime_ok | false | **true** |

判据：`frame p95 ≤ 100ms 且 fps ≥ 10` ⇒ **达到实时**。
测试：`tests/test_hand_onnx.py` **ALL PASS**。

## 三、结构
```
hand_onnx.py（OpenCV DNN：palm+handpose，模型只加载一次）
→ hand_realtime op=onnx_video
→ geometric retarget（0.27ms）
→ loopback.move（0.08ms）
```
IK 仍可选，但 IK 单帧 >100ms，实时路径默认 geometric；要 IK 质量就异步/离线。

## 四、边界
- 仍是**本地视频批处理**，摄像头未通；
- loopback 仿真，不驱动真手；
- ONNX 输出是 21 点 2D/相对 z，接真手前要标定；
- 实时判据只对当前视频/机器成立，不是对所有场景的保证；
- 无云、无付费、模型本地。

## 五、下一步
1. 把 `onnx_video` 的模型加载器改成常驻 worker，摄像头帧直接灌；
2. 摄像头权限通了跑真实 30fps 测试；
3. ONNX 路径接 IK 异步线程（质量/实时分离）。

> 开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属
