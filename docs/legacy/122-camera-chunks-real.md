# 122 · WinRT 连续 chunk → 真实相机 detected/moved（首个真实相机数据）

## 一、链路
```
PowerShell WinRT 连续录 1s chunk
→ chunk-0001/2/3.mp4
→ Python hand_camera_chunks
→ ONNX detect → IK → loopback.move → read_state
```

## 二、实测（3 个 1s chunk）
| 项 | 读数 |
|---|---|
| chunks | 3 |
| frames | **33** |
| detected | **5** |
| moved | **5** |
| detect mean | 30.53ms |
| IK mean | 0.32ms |
| 处理 fps | 18.41 |
| realtime_ok | false（coverage 5/33 < 0.8） |

- 这是**真实相机帧**跑出的 detected/moved，不是手图伪造；
- 5/33 说明手只出现在部分帧，覆盖率不足；
- 未达实时判据，不冒充。

## 三、意义
- OpenCV/DirectShow/VfW 全部失败；
- **WinRT 连续录像 + Python ONNX** 已能从真实相机拿到手部结果；
- 下一步把“录 1s → 再读”换成 MediaFrameReader 流，才能提高覆盖率/实时性。

## 四、下一步
1. MediaFrameReader（或 0.3s chunk）提高实时性；
2. 手保持在画面内，测 coverage；
3. 帧/块回收 + 力限幅接同一链。

> 开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属
