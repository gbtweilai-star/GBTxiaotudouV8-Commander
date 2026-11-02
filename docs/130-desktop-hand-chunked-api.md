# 130 · 桌面版 API 支持 onnx_chunked（30帧/27.8fps/moved 30）

## 一、接口
`POST http://127.0.0.1:8766/api/dh/hand`
```json
{"op":"onnx_chunked","video":"C:\\Users\\Public\\hand-motion.mp4",
 "frames":30,"chunk":30,"timeout":120}
```

## 二、实测（桌面版真实进程）
| 项 | 读数 |
|---|---|
| frames | **30** |
| hand_frames | **30** |
| ik_ok | **30** |
| moved | **30** |
| chunk 视觉 mean/p95 | 21.23 / **24.88ms** |
| IK mean | 0.42ms |
| fps | **27.82** |
| realtime_ok | **true** |
| 总耗时 | 1.08s |

## 三、打包细节
- 桌面 payload 需要 `payload/.scratch/lead`（chunk 中间文件目录），已创建；
- `onnx_chunked` 复用：
  - `hand_onnx` + 模型；
  - `hand_onnx_chunk_worker.py`；
  - `hand_onnx_chunked_chain.py`；
  - `hand_ik.py`/`hand_retarget.py`/`hand_bridge.py`。

## 四、当前桌面版可用入口
| 入口 | 状态 |
|---|---|
| `GET /api/dh/hand` | 旧模型/状态 |
| `POST /api/dh/hand` `op=onnx_image` | ✅ 21点/20关节/moved |
| `POST /api/dh/hand` `op=onnx_chunked` | ✅ 30帧/27.8fps/moved 30 |
| MediaPipe `image` | ❌ payload 无 mediapipe |
| 摄像头 | 外部 WinRT chunk，未接桌面内 |

## 五、下一步
1. UI 加“手部视频/图片”入口；
2. `camera_chunks` 也可接同一 API（需帧目录）；
3. 真机/摄像头仍是硬件边界。

> 开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属
