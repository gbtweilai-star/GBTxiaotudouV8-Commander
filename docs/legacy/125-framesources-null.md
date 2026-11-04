# 125 · MediaFrameReader 诊断：FrameSources 枚举为 null，reader 建不起来

## 一、现象
`camera-winrt-framesources.ps1`：
- `SOURCES 1`（相机源数量 1）；
- `KEYS` 为空；
- 枚举出的 source 是 **null**；
- 无法拿 `SourceInfo`/`SupportedFormats`；
- 因此 `CreateFrameReaderAsync(source, Bgra8)` 仍失败（AggregateException）。

## 二、结论
- 不是“没有相机源”，是 PowerShell 对 WinRT `IMapView` 的枚举适配有问题；
- 需要按 **source ID/键** 取 `MediaFrameSource`，或换 C#/WinRT 项目；
- 当前不把 MediaFrameReader 算通。

## 三、当前可用
- WinRT 拍照单帧 ✅
- WinRT 连续 1s chunk 录制 ✅（3s/720p/46帧）
- Python 读 chunk → ONNX 5 detected/5 moved ✅
- MediaFrameReader ❌
- OpenCV/DShow/VfW ❌

## 四、下一步
1. 用 `FrameSources` 的 key 精确取 source，再列 formats；
2. 或写一个最小 C#/WinRT helper（PowerShell 对 WinRT map 支持弱）；
3. 不通过就继续用 0.3–1s chunk，不冒充实时流。

> 开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属
