# 出 Android APK（免费：不装 Play Console、不上架）
# 前置：setup-android.ps1 已跑过（java / ANDROID_HOME / sdkmanager 组件都在）
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $root

if (-not $env:ANDROID_HOME) {
  $guess = Join-Path $env:LOCALAPPDATA "Android\Sdk"
  if (Test-Path $guess) { $env:ANDROID_HOME = $guess } else { throw "没找到 ANDROID_HOME；先跑 setup-android.ps1" }
}
Write-Host "ANDROID_HOME=$env:ANDROID_HOME"

if (-not (Test-Path "android")) {
  Write-Host "== 首次：加 android 平台 =="
  npm install
  npx cap add android
}
npm run sync

Write-Host "== 构建 debug APK（自签，可直接装；不需要任何账号）=="
Push-Location android
try {
  .\gradlew.bat assembleDebug
} finally {
  Pop-Location
}

$apk = Get-ChildItem -Recurse -Filter "app-debug.apk" android | Select-Object -First 1
if (-not $apk) { throw "没找到 app-debug.apk —— 把上面的 Gradle 报错贴回来" }
Write-Host ""
Write-Host "✅ APK：$($apk.FullName)"
Write-Host "   大小：$([math]::Round($apk.Length/1MB,1)) MB"
Write-Host "   安装：手机开『允许安装未知来源』→ 拷过去点安装"
Write-Host ""
Write-Host "要**正式自签**（可长期升级）再做这两步（keystore 自己保存，别进仓库）："
Write-Host "  keytool -genkeypair -v -keystore gbt-release.jks -alias gbt -keyalg RSA -keysize 2048 -validity 10000"
Write-Host "  然后 android/gradle.properties 配 RELEASE_STORE_FILE/PASSWORD/ALIAS 后 gradlew assembleRelease"
