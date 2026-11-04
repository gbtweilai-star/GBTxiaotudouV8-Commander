# 126 · 0.3s chunk 低延迟相机：12帧/32fps 处理

## 一、做法
`camera-winrt-record-loop.ps1 -Chunks 5 -SecondsPerChunk 0.3`：
- WinRT 连续录 5 个 **0.3s** chunk；
- Python `camera_chunks` 依次读；
- ONNX → IK/HAL。

## 二、实测
| 项 | 读数 |
|---|---|
| chunks | 5 |
| frames | **12** |
| detected | **0** |
| moved | 0 |
| detect mean | 12.2ms |
| 处理 fps | **32.23** |
| realtime_ok | false（无手，coverage=0） |

- 0.3s chunk 比 1s 延迟更低，处理侧 32fps；
- 画面里仍没有手，所以 detected=0，不伪造；
- 录制/读帧/ONNX 链正常。

## 三、边界
- 这还是“录完一段再读”，不是 MediaFrameReader 真流；
- 0.3s chunk 的实际端到端延迟约 0.3–0.6s；
- 手入镜后才有 coverage 可谈。

## 四、下一步
1. 手入镜，测 0.3s chunk 的 detected/coverage；
2. MediaFrameReader 仍待 C# helper；
3. 不把 0 检测当模型失败。

> 开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属
