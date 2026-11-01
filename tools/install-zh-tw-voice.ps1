# gbt-capability: drama_forge
# 开发者：自由的风 · 永久钢印 · 禁止删除
<#
install-zh-tw-voice.ps1 — 装 Windows zh-TW 语言包（含本地台湾腔女声），不花钱。
必须管理员；非管理员只打印命令，不改系统。
用法（管理员）：
  powershell -NoProfile -ExecutionPolicy Bypass -File tools\install-zh-tw-voice.ps1
#>
$ErrorActionPreference = 'Stop'
$id = [Security.Principal.WindowsIdentity]::GetCurrent()
$pr = New-Object Security.Principal.WindowsPrincipal($id)
if (-not $pr.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    Write-Output '需要管理员。右键“以管理员身份运行” PowerShell，然后执行：'
    Write-Output '  Add-WindowsCapability -Online -Name Language.TextToSpeech~~~zh-TW~0.0.1.0'
    Write-Output '  # 或：powershell -NoProfile -ExecutionPolicy Bypass -File tools\install-zh-tw-voice.ps1'
    exit 2
}
$name = 'Language.TextToSpeech~~~zh-TW~0.0.1.0'
Write-Output ("安装 {0} ..." -f $name)
try {
    $r = Add-WindowsCapability -Online -Name $name
    Write-Output ("状态：{0}" -f $r.RestartNeeded)
} catch {
    Write-Output ("安装失败：{0}" -f $_.Exception.Message)
    Write-Output '可改用 设置 → 时间和语言 → 语言和区域 → 添加繁体中文（台湾）→ 语音包'
    exit 3
}
Add-Type -AssemblyName System.Speech
$s = New-Object System.Speech.Synthesis.SpeechSynthesizer
$s.GetInstalledVoices() | ForEach-Object { $v = $_.VoiceInfo; "{0} | {1} | {2}" -f $v.Name, $v.Culture.Name, $v.Gender }
$s.Dispose()
Write-Output '完成。drama-build 默认 Voice=local 会自动优先 zh-TW Female；不再需要 Edge 云 TTS。'
exit 0
