# 119 · 摄像头突破：WinRT MediaCapture 能开，OpenCV/DSHOW/VfW 不能

## 一、实测
| 路径 | 结果 |
|---|---|
| OpenCV MSMF/DSHOW/ANY | 打不开 |
| ffmpeg dshow | `Unable to BindToObject` |
| ffmpeg vfwcap | `No such device` |
| **WinRT MediaCapture（PowerShell 直接跑）** | **INIT_OK** |
| **WinRT CapturePhotoToStreamAsync** | **成功写出 1280×720 JPEG（88KB）** |
| WinRT 从 Python 子进程调用 | `AggregateException`（会话/WinRT 环境限制） |

## 二、结论
- 摄像头硬件没坏，是 **OpenCV/DirectShow/VfW 绑定路径**不行；
- **WinRT 路径能开、能抓帧**，证明相机可用；
- Python 直接拉起 WinRT 失败，所以不能把 WinRT 抓帧塞进 `hand_vision` 的 Python 子进程；
- 需要 **PowerShell 侧常驻抓帧/文件管道**，Python 只读帧文件/管道，才能进 ONNX 链。

## 三、已落文件
`tools/camera-winrt.ps1`：
```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File tools\camera-winrt.ps1 -OutFile frame.jpg
```
- 抓单帧 → JPEG；
- 已实测成功；
- 测试图片已删除，不留用户画面。

## 四、下一步
1. 写 **PowerShell 常驻抓帧循环**（帧文件/命名管道），Python 读最新帧；
2. 帧 → ONNX 34ms → IK/HAL；
3. 仍是单帧/低帧率起步，不冒充 30fps。

> 开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属
