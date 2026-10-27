# SpaceBeamLite（iOS 复刻版 · 可编译工程）

对齐开源项目 `CalmyJane/SpaceBeam` 的核心链路，**目标：后置摄像头画面 → 实时特效 → 外接屏/投影**。

> 本工程由 GBT小土豆V8 生成（2026-10-27）。**未在 Xcode 里编译过**（本机没有 Mac），
> 所以状态是"源码完整、待编译验证"。第一件事就是 `xcodebuild` 过一遍，报错按注释改。

## 一、能力对照（对齐 SpaceBeam）

| 能力 | SpaceBeam（Android） | 本工程（iOS） |
|---|---|---|
| 后置/前置/超广/长焦切换 | CameraX `enumerateCameras` | ✅ `CameraController` 按 `deviceType` 枚举 |
| 万花筒特效 | GLES 着色器 | ✅ Metal 着色器 `Kaleidoscope.metal` |
| 送外接屏 | `DisplayManager` + `Presentation` | ✅ `ExternalDisplay`（`UIScreen.screens`） |
| 手/脸驱动 | MediaPipe | ✅ Vision `VNDetectHumanHandPoseRequest` |
| 录制 | MediaRecorder | ✅ ReplayKit |
| 无线投屏 | Miracast | ⚠️ iOS 只有 AirPlay（系统镜像，非 App 能力） |

## 二、编译（需要一台 Mac）

```bash
# 1. 建工程（xcodegen 一把，比手点省事）
brew install xcodegen
cd SpaceBeamLite && xcodegen generate

# 2. 编译到真机（不要模拟器：没有相机）
xcodebuild -project SpaceBeamLite.xcodeproj -scheme SpaceBeamLite \
  -destination 'generic/platform=iOS' -configuration Release build
```

没有 Mac 也可以：把仓库推到 GitHub，用 **Actions 的 macOS runner 免费额度**跑
`xcodebuild`，产物是未签名 `.app`，再用 Sideloadly / AltStore 在手机上签名安装。
工作流文件：`.github/workflows/ios-build.yml`。

## 三、必开的权限（Info.plist）

```xml
<key>NSCameraUsageDescription</key><string>拍摄画面用于实时投影</string>
<key>NSMicrophoneUsageDescription</key><string>录制时同步声音</string>
```

## 四、使用

1. 手机插上 HDMI 转接器（或先连 AirPlay 接收端）
2. 打开 App → 选择摄像头（Back / Ultrawide / Telephoto）
3. 选预设（2×2 / 3×3 / 6 向）→ 点"投到外屏"
4. 用滑杆调 段数 / 旋转 / 缩放

## 五、诚实的边界

- **App 不发光**：光从外接屏/投影仪出。
- **iOS 没有 Miracast**：无线只能 AirPlay（需要 Apple TV / Mac / 授权电视）。
- **未编译验证**：本机无 Xcode，第一次编译大概率要改几处 API（注释里标了）。
