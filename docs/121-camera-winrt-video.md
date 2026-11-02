# 121 · WinRT 连续相机视频：3s/720p/46帧，ONNX 29.32fps

## 一、突破
之前 WinRT 只能拍照（1.2fps）。现在用 `MediaCapture.StartRecordToStorageFileAsync` 连续录制：

```powershell
powershell -File tools\camera-winrt-video.ps1 -OutFile camera.mp4 -Seconds 3
```

实测：
- **3.01s / 1280×720 / 46 帧 / 2.0MB**；
- 文件可被 OpenCV 正常读取；
- Python 侧 ONNX 处理 **29.32 fps**（infer mean 23.04ms，p95 45.88ms）。

## 二、为什么这重要
- OpenCV/DirectShow/VfW 都打不开摄像头；
- WinRT **能连续录视频**，证明相机不是坏的；
- 录制文件是 MP4，可直接进现有 ONNX/IK/HAL 链；
- 不是“抓一张图”冒充实时。

## 三、这次检测结果
- 46 帧处理，**detected=0**；
- 原因：镜头里没有人手（只有人脸/房间），不是模型坏了；
- 不伪造 detected。

## 四、下一步
1. 手入镜后重录 3s，验证 detected/moved；
2. 需要真·实时就把“录 3s → 再读”改成 MediaFrameReader 流；
3. 帧桥/录制 + chunk 回收 + 力限幅接同一链。

> 开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属
