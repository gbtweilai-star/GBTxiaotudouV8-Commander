# 编译预检（没有 Xcode 时能做的事）

> 2026-10-27 ｜ 本文件记录**静态审过的 API 风险**与已修项。真正的判定只有 `xcodebuild`。

## 已修（不修必报错或必黑屏）

| # | 问题 | 症状 | 处理 |
|---|---|---|---|
| 1 | `onChange(of:) { old, new in }` 是 iOS 17 API，工程原写 16.0 | 编译报 `extra argument in call` 或部署目标不符 | 部署目标改 **17.0**（注释说明了回退法） |
| 2 | 外接屏 `UIWindow` 没 `makeKeyAndVisible()` | 部分 iPhone 外接屏黑屏，日志正常 | 已加 |
| 3 | `KaleidoscopeRenderer` 是 class 却用 `@State` 持有 | 状态变了不刷新；SwiftUI 警告 | 加 `ObservableObject` + 改 `@StateObject` |

## 需要 Xcode 才能确认的（风险最高在前）

| # | 位置 | 风险 | 备选方案 |
|---|---|---|---|
| 1 | `CameraController.discover()` | `activeFormat.videoFieldOfView` 只能在会话配置后读；初次枚举可能拿到默认值 | 改用 `device.position` + `deviceType` 排序 |
| 2 | `ExternalDisplay.attach` | `win.windowScene = scene` 必须在 addSubview 之前；某些场景 `connectedScenes` 里找不到绑定该 screen 的 scene | 退回 `UIApplication.shared.windows` 里的旧 API |
| 3 | `Kaleidoscope.metal` | `fmod` 在 Metal 里可用，但 `float2 pos[3]` 数组初始化在部分版本需 `const float2` | 改成逐个赋值 |
| 4 | `Recorder.stop()` | `RPPreviewViewController` 的 delegate 属性名在旧 SDK 是 `previewControllerDelegate`，新 SDK 同 | 若报错改 `delegate` |
| 5 | `.metal` 是否进编译 | xcodegen 的 `sources: Sources` 应包含，但若被当资源则 `makeDefaultLibrary()` 返回 nil | Build Phases 手动加进 Compile Sources |

## 编译命令（拿到 Mac 就这一条）

```bash
brew install xcodegen && xcodegen generate
xcodebuild -project SpaceBeamLite.xcodeproj -scheme SpaceBeamLite \
  -sdk iphoneos -configuration Release CODE_SIGNING_ALLOWED=NO build 2>&1 | tee /tmp/build.log
```

把 `/tmp/build.log` 里第一批 `error:` 贴回来即可 —— 我按报错逐条改，不再猜。
