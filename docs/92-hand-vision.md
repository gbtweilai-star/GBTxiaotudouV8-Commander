# 92 · 手部视觉入口（MediaPipe 本地）· 当前状态

> 目标：摄像头/图片/视频 → 21 点手部关键点 → hand_retarget/IK → hand_bridge。
> 本页只写实测，不把“装了库”说成“摄像头跑通”。

## 一、已落地
| 件 | 读数 |
|---|---|
| MediaPipe | **0.10.21**（本机 `vendor/pylibs`，手动解 wheel） |
| OpenCV | **5.0.0**（contrib，本地） |
| 能力位 | `hand_vision`，op=`status/image/camera` |
| 图片模式 | 本地 MediaPipe Hands 推理，返回 21×[x,y,z]+左右手 |
| 摄像头模式 | 打开失败 → **`needs_camera` fail-closed**，不返回假帧 |
| 依赖 | protobuf 4.25.3 / absl / attrs / flatbuffers / matplotlib 等本地 wheel |

## 二、摄像头为什么没通
实测三种后端都打不开：
- `cv2.CAP_MSMF` / `CAP_DSHOW` / `CAP_ANY`：`can't be used to capture by index`
- ffmpeg dshow：`Unable to BindToObject for Integrated Camera`
- OpenCV 报 `obsensor ... Camera index out of range`

设备管理器里 **Integrated Camera 状态 OK**，所以不是“没有摄像头”，而是：
1. Windows 相机隐私/策略没放行；
2. 摄像头被其它进程占用；
3. OpenCV/FFmpeg 的采集后端绑定失败。

**没有伪造摄像头帧，也没有假装 21 点。**

## 三、下一步（需要环境配合）
1. 设置 → 隐私和安全性 → 相机 → 允许桌面应用；
2. 关掉可能占用摄像头的程序（会议/浏览器/相机）；
3. 仍不行 → 用 **图片/视频文件** 喂 `hand_vision image`，先验证 21 点→IK→loopback 全链；
4. 摄像头通了再把 `hand_vision camera` 接进 `hand_realtime`。

> 开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属
