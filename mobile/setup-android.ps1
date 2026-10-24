# 免费装 Android 构建工具链（JDK 17 + Android cmdline-tools + platform-34）
# 全免费；总下载约 1.5–2 GB。每一步都打印真实结果，失败就停，不静默。
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$sdk = Join-Path $env:LOCALAPPDATA "Android\Sdk"
$tools = Join-Path $sdk "cmdline-tools\latest"

Write-Host "== 1/4 JDK 17 =="
$java = Get-Command java -ErrorAction SilentlyContinue
if ($java) { Write-Host "已有 java：$($java.Source)" }
else {
  Write-Host "本机没有 java。免费方案二选一（任选一条，复制去跑）："
  Write-Host "  winget install --id Microsoft.OpenJDK.17 -e"
  Write-Host "  或  https://adoptium.net/temurin/releases/?version=17 （解压后把 bin 加进 PATH）"
  Write-Host "装完重跑本脚本。"
  exit 2
}
java -version

Write-Host "== 2/4 Android cmdline-tools =="
New-Item -ItemType Directory -Force -Path $sdk | Out-Null
if (-not (Test-Path $tools)) {
  $zip = Join-Path $env:TEMP "cmdline-tools.zip"
  $url = "https://dl.google.com/android/repository/commandlinetools-win-11076708_latest.zip"
  Write-Host "下载 $url"
  Invoke-WebRequest -Uri $url -OutFile $zip -UseBasicParsing
  Expand-Archive -Path $zip -DestinationPath (Join-Path $sdk "cmdline-tools") -Force
  $unzipped = Join-Path $sdk "cmdline-tools\cmdline-tools"
  if (Test-Path $unzipped) { Move-Item $unzipped $tools }
  Remove-Item $zip -Force
}
Write-Host "cmdline-tools → $tools"

Write-Host "== 3/4 许可 + 组件（platform-tools / build-tools;34.0.0 / platforms;android-34）=="
$env:ANDROID_HOME = $sdk
$sdkmgr = Join-Path $tools "bin\sdkmanager.bat"
& $sdkmgr --sdk_root=$sdk --licenses | Out-Null
& $sdkmgr --sdk_root=$sdk "platform-tools" "build-tools;34.0.0" "platforms;android-34"

Write-Host "== 4/4 环境变量（本会话有效；永久请用 setx）=="
$env:Path = "$sdk\platform-tools;$sdk\build-tools\34.0.0;$env:Path"
Write-Host "ANDROID_HOME=$sdk"
Write-Host "✅ 工具链就绪。下一步：cd mobile && npm install && npx cap add android && npm run apk"
