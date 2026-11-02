# 129 · 桌面版打包手部 ONNX + API 验证

## 一、打包内容
`GBT小土豆V8桌面版\payload` 新增：
- `gbt_allinone/tentacle/`：`hand_onnx.py`、`hand_onnx_image.py`、`hand_onnx_chunked_chain.py`、`hand_camera_bridge.py`、`hand_camera_chunks.py`、`hand_realtime.py`、`hand_ik.py`、`hand_image.py` 等；
- `tools/model-bridge/hand_onnx_chunk_worker.py`；
- `vendor/hand-tracking/`：palm/handpose ONNX + `mp_palmdet.py`/`mp_handpose.py`；
- `vendor/pylibs/cv2` + `numpy`（约 169MB）；
- `pyembed/python313._pth` 增加 `..\vendor\pylibs`；
- `tests/fixtures/hand-21.png`。

## 二、Unicode 路径修复
桌面版路径含中文，`cv2.dnn.readNet(path)` 打不开 ONNX：
- `mp_palmdet.py` / `mp_handpose.py` 改为 `np.fromfile(...)` + `cv2.dnn.readNetFromONNX(bytes)`；
- 修复后中文路径可加载。

## 三、API 验证（真实桌面版进程）
`POST http://127.0.0.1:8766/api/dh/hand`
```json
{"op":"onnx_image","image":"C:\\Users\\Public\\hand-21.png"}
```
返回：
```json
{"ok": true, "op": "onnx_image", "detected_hand": "left",
 "landmarks": 21, "solver": "ik", "joint_count": 20,
 "moved": true, "read_state_ok": true, "seconds": 0.1653}
```
- 桌面版 `proactive` 同时返回 200；
- 说明打包后的 ONNX 链在桌面进程里真实跑通，不是只在源码工作区。

## 四、边界
- `hand_image`（MediaPipe）仍不可用：payload 没打包 MediaPipe；
- 新 `onnx_image` 是不依赖 MediaPipe 的替代入口；
- 摄像头仍走 WinRT chunk（外部 PowerShell），桌面版内未接；
- loopback 仿真，不驱动真手。

## 五、下一步
1. UI 增加“手部 ONNX 图片”按钮；
2. 把 `onnx_chunked` 接桌面版 API（本地视频路径）；
3. 摄像头 chunk / 真机仍是硬件边界。

> 开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属
