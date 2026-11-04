# 127 · C#/WinRT helper 尝试：缺 UnionMetadata，编译不过

## 一、目标
用 C# 绕过 PowerShell 对 WinRT `IMapView` 的枚举缺陷，直接：
- 枚举 `MediaCapture.FrameSources`
- 创建 `MediaFrameReader`
- 连续取帧

## 二、结果
`csc.exe` 编译 `CamProbe.cs`：
- 参照 `Windows.Foundation/Media/Storage/Graphics.winmd` + `System.Runtime.WindowsRuntime.dll`；
- 报 `Windows.Foundation.IAsyncAction` 类型未定义，要求 `Windows, Version=255.255.255.255` 程序集；
- 本机 **没有 Windows SDK UnionMetadata 的 `Windows.winmd`**（`C:\Program Files (x86)\Windows Kits\10` 下未找到）；
- 编译失败，未产生可用 reader helper。

## 三、结论
- PowerShell 枚举 WinRT map 失败；
- C# 又缺 Windows SDK 元数据；
- MediaFrameReader 这条路在本机工具链下**暂时走不通**；
- 当前仍用 **WinRT 录 0.3–1s chunk → Python 读 → ONNX**。

## 四、下一步
1. 安装 Windows SDK（UnionMetadata）后可重试 C# helper；
2. 或接受 chunk 路径（0.3s 延迟量级）；
3. 不把未编译的东西算能力。

> 开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属
