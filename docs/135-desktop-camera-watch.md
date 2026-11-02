# 135 · 目录监视自动处理 WinRT chunk：150帧/45.3fps

## 一、新增
- `hand_camera_watch.py`：轮询目录，发现新的 `chunk-*.mp4` 就送入 ONNX/IK/HAL；
- `hand_realtime op=camera_watch`：
  ```json
  {"op":"camera_watch","dir":"C:\\Users\\Public\\gbt-watch",
   "seconds":2,"poll":0.2,"max_chunks":2}
  ```
- 桌面版 `POST /api/dh/hand` 直接支持。

## 二、桌面版 API 实测
| 项 | 读数 |
|---|---|
| frames | **150** |
| detected | **150** |
| moved | **150** |
| detect mean | **20.58 ms** |
| IK mean | 0.15 ms |
| fps | **45.29** |
| realtime_ok | **true** |

- 读的是已存在的 chunk；轮询目录，不直接碰 WinRT；
- 录制仍由 PowerShell `camera-winrt-record-loop.ps1` 负责；
- 这边只负责“新 chunk 自动进链”。

## 三、完整链路
```
PowerShell WinRT 录 chunk
→ 目录出现 chunk-*.mp4
→ camera_watch 轮询
→ ONNX detect
→ IK
→ loopback
```

## 四、边界
- 不是 MediaFrameReader 真流；
- 需要外部录制进程先写 chunk；
- loopback 仿真，真机需标定。

## 五、下一步
1. UI 增加 camera_watch 按钮（选目录+秒数）；
2. 外部录制进程和桌面版一起启动；
3. 真机/摄像头硬件边界不变。

> 开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属
