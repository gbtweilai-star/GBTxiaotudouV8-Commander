# 124 · MediaFrameReader 尝试：初始化失败（AggregateException）

## 一、目标
用 `MediaFrameReader` 把相机变成连续帧流，替代 1s 录制 chunk / 拍照式抓帧。

## 二、结果
`camera-winrt-frame-reader.ps1`：
- `MediaCapture.InitializeAsync(settings)`（Video/Cpu）；
- `CreateFrameReaderAsync(source, Bgra8)`；
- 在 `AwaitOp(...)` 处抛 **AggregateException**，frame reader 未创建；
- 没有产生 raw 帧，不冒充成功。

可能原因（待定位）：
1. `FrameSources` 选择/格式不匹配；
2. `MediaCaptureInitializationSettings` 需要 SharingMode/MediaCategory 等；
3. MediaFrameReader 在该驱动/会话下不支持 Bgra8；
4. Python/非交互会话对 WinRT 相机资源的限制。

## 三、当前可用相机路径
| 路径 | 状态 |
|---|---|
| 拍照抓单帧（WinRT） | ✅ |
| 连续录 1s chunk（WinRT） | ✅ 3s/720p/46帧 |
| Python 读 chunk → ONNX/IK/HAL | ✅ 真实相机 detected=5/moved=5（33帧） |
| MediaFrameReader | ❌ AggregateException |
| OpenCV/DShow/VfW | ❌ |

## 四、下一步
1. 打印 `FrameSources` 的 source/format 清单，按实际格式创建 reader；
2. 若驱动不支持，退回 **0.3–0.5s chunk 录制** 做低延迟；
3. 不把 MediaFrameReader 未通算成“实时流”。

> 开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属
