# 120 · WinRT 帧桥 → ONNX 手部链（真实相机帧 + 手图验证）

## 一、架构
```
PowerShell WinRT 抓帧（camera-winrt-frames.ps1）
→ 帧文件 frame-XXXX.jpg / latest.jpg
→ Python hand_camera_bridge
→ hand_onnx.detect
→ IK → loopback
```
为什么分两层：Python 子进程直接调 WinRT 会 AggregateException；PowerShell 能抓，Python 只读帧。

## 二、实测
| 素材 | files | read | detected | moved | detect mean | fps |
|---|---|---|---|---|---|---|
| 真实相机帧（画面无手） | 5 | 5 | **0** | 0 | 31.35ms | 24.82（读帧） |
| 本地手图伪造帧 | 3 | 3 | **3** | **3** | 22.34ms | **35.19** |

- 真实相机：WinRT 抓帧成功，5 帧 85–102KB；ONNX 读帧正常，画面里没手所以 detected=0（不伪造）。
- 手图帧：21 点 → IK 0.15ms → move 3/3，整链通。

## 三、当前限制
- WinRT**拍照式抓帧**约 1.2fps（0.6–1s/帧），不是 30fps 视频流；
- 真实相机画面里没有手，所以没有“相机→手”的 detected 证据；
- 需要 **MediaFrameReader** 才能连续 15–30fps；
- 真机仍需标定。

## 四、下一步
1. 用 MediaFrameReader 替换拍照式抓帧；
2. 手入镜后测真实 detected/moved；
3. 帧桥 + chunk 进程回收 + 力限幅接同一链。

> 开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属
