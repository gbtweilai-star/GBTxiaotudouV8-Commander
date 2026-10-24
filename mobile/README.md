# 手机壳（免费路径）· Capacitor

> 这里的每一件都**不需要付费账号**：Android 出 APK 不需要 Play Console；iOS 出 `.ipa` 不需要 Apple Developer Program。
> 代价写在下面「两条路各自的门槛」里，不美化。

## 一句话结论

| 目标 | 免费路径 | 能不能 | 门槛（真实） |
|---|---|---|---|
| **iPhone 装到桌面** | 已经有了：PWA（Safari → 添加到主屏幕） | ✅ 现在就能用 | 无 |
| **Android 装成 App** | 本地打 **APK**，自签 keystore，挂 GitHub Releases 发 | ✅ 能 | 装 JDK 17 + Android SDK（约 **1.5–2 GB**，全免费） |
| **iPhone 装成 App（真 .ipa）** | 免费 Apple ID 自签 + Sideloadly/AltStore | ⚠️ 能，但 **7 天过期** | 要**一台 Mac 或 CI 的 macOS runner** 来编译；iOS 不能只在 Windows 上编 |
| 上 TestFlight / App Store | Apple Developer **$99/年** | ❌ 免费做不到 | 你要的是免费，所以**这条路不走** |
| 上 Google Play | Play Console **$25 一次性** | ❌ 免费做不到 | 同上，不走 |

**iOS 为什么必须有 Mac**：`xcodebuild` 只有 macOS 版。免费替代 = GitHub Actions 的 **macOS runner**
（公开仓库的 Actions 分钟数免费），在 CI 里编出未签名 `.app` → 打包成 `.ipa` → 回到 Windows 用 **Sideloadly**
+ 免费 Apple ID 签装（7 天一次续签）。**不是技术不行，是工具链只在 macOS 上。**

## 目录

```
mobile/
├── capacitor.config.json   # webDir 指到 ../outputs/open-source-release（就是发布页那套静态件）
├── package.json            # @capacitor/{core,cli,android,ios}
├── setup-android.ps1       # 一键装 JDK+SDK（免费，约 1.5–2 GB，会打印每一步）
├── build-apk.ps1           # 一键出未签名/自签 APK
└── github-actions-mobile.yml  # 免费 macOS runner 编 iOS（复制到 .github/workflows/）
```

## Android：出 APK（免费）

```powershell
cd mobile
.\setup-android.ps1          # 装 JDK17 + cmdline-tools + platform-tools + build-tools + platform-34
npm install                  # @capacitor/*
npx cap add android
npx cap sync android
.\build-apk.ps1              # 出 app-debug.apk；要正式自签则生成 keystore 后 assembleRelease
```

- 自签：`keytool -genkeypair -v -keystore gbt-release.jks -alias gbt -keyalg RSA -keysize 2048 -validity 10000`
  （免费；keystore 自己保存，**不要提交进仓库**）。
- 分发：把 APK 传到 GitHub Releases，别人下载时引导「允许安装未知来源」。
- 大小：SDK 约 1.5–2 GB，首次 Gradle 再下 ~500 MB 依赖。

## iOS：免费自签（需要 Mac 或 CI）

```bash
# 在 macOS（或 GitHub Actions macos-latest）里：
npm install && npx cap add ios && npx cap sync ios
xcodebuild -workspace ios/App/App.xcworkspace -scheme App -configuration Release \
           -sdk iphoneos CODE_SIGNING_ALLOWED=NO build
# 把 App.app 打成 Payload/App.app → zip 改名 App.ipa（未签名）
```

回到 Windows：装 **Sideloadly**（免费），用免费 Apple ID 登录 → 拖入 `.ipa` → 安装。
限制照实说：**签名 7 天过期**、每台设备同时最多 3 个自签 App、无推送、无 TestFlight。

## 装到手机上会坏掉什么（必须知道）

发布页是纯静态件，所以壳里跑的是「页面 + 网络」。**这些能力位在手机壳里不会工作**：

- 所有 `process_execute` / 读本机文件 / 调本地命令的位（手机没有你的 Windows 机器）；
- 依赖 DPAPI 保险箱、`store/` 审计账本的位；
- 需要本机 GPU/ComfyUI/Blender 的位。

⇒ 手机壳的正确用法是「**看 + 问 + 指挥**」：页面、目录、示范命令都看得到；
**真执行留在你的电脑上**（这也是为什么我们没有把「执行」塞进手机壳）。

## 未验（如实标）

本目录**只是脚手架**：`setup-android.ps1` / `build-apk.ps1` 在本机（node 24 / rust 1.97 有，**JDK/SDK 没有**）**没有真跑过**。
第一次跑请把输出贴回来，我按真实报错改，不拿「应该能行」糊过去。
