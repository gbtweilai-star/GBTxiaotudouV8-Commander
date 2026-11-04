# 131 · 桌面版 API 支持 camera_chunks（2 chunk / 300帧 / moved 300）

## 一、接口
`POST http://127.0.0.1:8766/api/dh/hand`
```json
{"op":"camera_chunks","dir":"C:\\Users\\Public\\gbt-camchunks","max_chunks":2}
```

## 二、实测
| 项 | 读数 |
|---|---|
| chunks | 2 |
| frames | **300** |
| detected | **300** |
| moved | **300** |
| detect mean | 83.87 ms |
| IK mean | 0.54 ms |
| fps | **11.47** |
| realtime_ok | **true**（刚过 10fps 线） |

- 这是桌面版进程里读 chunk → ONNX → IK → loopback 的真实结果；
- 300/300 帧都有手，说明测试视频是手部素材；
- 摄像头实际 chunk 仍需 WinRT 录制目录。

## 三、当前桌面版手部 API
| op | 状态 |
|---|---|
| `onnx_image` | ✅ 21点/20关节/moved |
| `onnx_chunked` | ✅ 30帧/27.82fps/moved 30 |
| `camera_chunks` | ✅ 300帧/11.47fps/moved 300 |
| MediaPipe image | ❌ 无 mediapipe |
| WinRT 录制 | 外部 PowerShell，桌面内未接 |

## 四、边界
- `camera_chunks` 读的是已完成 chunk 文件，不是 MediaFrameReader 真流；
- 300 帧 26s，11.47fps 是批处理吞吐，不是端到端低延迟；
- loopback 仿真，真机需标定。

## 五、下一步
1. Windows 侧录 chunk 后自动投递到目录，再接此 API；
2. UI 加“手部视频/chunk”按钮；
3. 真机/摄像头硬件边界不变。

> 开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属
