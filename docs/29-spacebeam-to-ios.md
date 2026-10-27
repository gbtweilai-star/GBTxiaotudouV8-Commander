# 把 SpaceBeam 这条路搬到 iOS：需要什么（技术评估）

> 2026-10-27 ｜ 依据：实读 `CalmyJane/SpaceBeam`（130 文件，Kotlin，GPL-3.0）
> 目的：以后再听到"开源有现成的"，一眼判断**能不能落到这台 iPhone 上**。

## 一、SpaceBeam 到底由哪几块组成（源码实证）

| 模块 | 实现 | 证据 |
|---|---|---|
| 取流 | CameraX + Camera2，枚举全部摄像头，按焦距命名 Ultrawide/Wide/Narrow/Telephoto | `MainActivity.kt:850` 附近 `enumerateCameras()` |
| 特效 | GLES 着色器（万花筒/着色器链），EGL 离屏渲染 | `KaleidoscopeRenderer.kt`（900+ 行） |
| 手/脸识别 | **MediaPipe** `tasks-vision:0.10.14` | `app/build.gradle.kts:98` |
| 陀螺仪 | Android SensorManager | 同上文件 |
| 送外屏 | `DisplayManager` + `android.app.Presentation`（第二块屏） | `ExternalDisplayHelper.kt` |
| 录制 | MediaRecorder / MediaCodec（EGL 直录） | `KaleidoscopeRenderer.kt:946` |

**关键**：它没有任何"发光"代码。**光从外接屏/投影仪出。**

## 二、逐块映射到 iOS

| 能力 | Android | iOS 对应 | 能不能在**我们的环境**里做 |
|---|---|---|---|
| 摄像头取流 | CameraX | `AVCaptureSession`（需 App 内 + 用户授权） | ❌ 命令行拿不到 |
| GPU 特效 | GLES / EGL | Metal（`MTKView` + shader） | ❌ 同上 |
| 手/脸关键点 | MediaPipe | Vision（`VNDetectHumanHandPoseRequest` 等） | ⚠️ 仅对**静态图**可用（我们已有 `apple-vision`） |
| 陀螺仪 | SensorManager | CoreMotion | ❌ 无 CLI |
| 送外屏 | DisplayManager + Presentation | `UIScreen.screens` / `ExternalDisplayScene` | ❌ 需 App 内 |
| 无线投屏 | Miracast / SmartView | **AirPlay（不支持 Miracast）** | ⚠️ 只能系统镜像，人手点 |
| 录制 | MediaRecorder | ReplayKit | ❌ |

**结论一句话**：这条路在 iOS 上**必须写成一个原生 App**，脚本/框架补不了。

## 三、iOS 上真正缺的三样（不是懒，是系统边界）

1. **Miracast 根本不支持** —— 苹果只做 AirPlay，且接收端必须是苹果生态（Apple TV / Mac / 授权电视）。
2. **外接显示渲染要 App 内代码** —— `UIScreen.screens` 需要 App 生命周期，无可用的 CLI/深链。
3. **摄像头流不向进程外开放** —— 没有"把相机帧交给 shell"的通道。

## 四、如果真要做，工作量（按人日估）

| 方案 | 内容 | 估时 | 备注 |
|---|---|---|---|
| **A. 最小可用** | 相机预览 + 外接屏 Presentation + 简单着色器 | 5–8 人日 | 等于 SpaceBeam 的 1/3 |
| **B. 对齐 SpaceBeam** | 加万花筒着色器链、手/脸驱动、录制 | 15–25 人日 | MediaPipe → Vision 需重写 |
| **C. 完整商业化** | 加预设、参数面板、录制编码、散热与降帧策略 | 40+ 人日 | 还得过 App Store 审核（相机+外接屏） |

**共同前提**：一台 Mac + Xcode + 开发者账号 + 真机调试。**这套我们目前没有。**

## 五、不写 App 时，我们能做的等价物（现实落点）

| 需求 | 我们的做法 | 命令 |
|---|---|---|
| 拍实物投大屏（静态） | 拍 → 摆正/去阴影/提亮 → 1080p 展台画面 | `gbt visualizer` |
| 屏幕内容投墙（真光） | 反色+镜像 + 凸透镜 | `gbt lens` |
| 单张内容投墙（最亮） | 生成透明胶片 + 闪光灯 | `gbt slide` |
| 投到已有大屏 | AirPlay 到 Mac/电视 | `gbt receiver` |

## 六、判断口诀（以后照这个问）

```
① 这件事要不要"光"？ 要 → 光必须从屏幕/投影仪/胶片出，手机摄像头永远不行
② 要不要实时相机流？ 要 → iOS 只能写成 App，脚本无解
③ 要不要无线投屏？   要 → 只能 AirPlay，接收端必须存在
④ 是不是别人视频里的效果？ → 先查那台设备有没有光机（Galaxy Beam / Moto Mod）
```

## 七、给主人的一句话

**SpaceBeam 是"Android 原生 App + 外接显示"的组合，不是"手机自己会投影"。**
我们手上这台 iPhone 不缺想法，缺的是：App 工程环境（Mac + Xcode）和一个会发光的接收端。
**零成本能做的，我们已经全做了。**
