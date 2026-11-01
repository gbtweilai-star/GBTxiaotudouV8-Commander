# gbt-capability: sync_guard
# 开发者：自由的风 · 永久钢印 · 禁止删除
<#
setup-boot-trigger.ps1 — 给 GBT-SyncGuard 补"开机触发"（需要管理员）
为什么脚本不自己提权：DSH 会话无法自动弹 UAC；请用管理员 PowerShell 跑本脚本。
用法（管理员）：
  powershell -NoProfile -ExecutionPolicy Bypass -File tools\setup-boot-trigger.ps1
效果：重建 GBT-SyncGuard = 开机触发 + 每 6 小时重复（保留原命令/工作目录）。
非管理员：只打印该怎么做，不改系统。
#>
param([string]$Repo = '')

$ErrorActionPreference = 'Stop'
if (-not $Repo) {
    if (Test-Path -LiteralPath (Join-Path (Get-Location) 'gbt_allinone')) { $Repo = (Get-Location).Path }
    else { $Repo = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..')).Path }
}
$Repo = (Resolve-Path -LiteralPath $Repo).Path
$runner = Join-Path $Repo 'tools\sync-guard-patrol.ps1'

$id = [Security.Principal.WindowsIdentity]::GetCurrent()
$principal = New-Object Security.Principal.WindowsPrincipal($id)
$isAdmin = $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $isAdmin) {
    Write-Output '需要管理员权限：请右键"以管理员身份运行" PowerShell，然后执行：'
    Write-Output ('  powershell -NoProfile -ExecutionPolicy Bypass -File "' + (Join-Path $Repo 'tools\setup-boot-trigger.ps1') + '"')
    Write-Output '（非管理员不动系统；登录自启已由 Startup\GBT-SyncGuard.cmd 覆盖）'
    exit 2
}

try {
    $svc = New-Object -ComObject Schedule.Service
    $svc.Connect()
    $root = $svc.GetFolder('\')
    $task = $svc.NewTask(0)
    $task.RegistrationInfo.Description = 'GBT 双仓同步巡检（开机 + 每 6 小时；DRIFT 写 alerts + 推送）'
    $task.Settings.Enabled = $true
    $task.Settings.StartWhenAvailable = $true
    $task.Settings.ExecutionTimeLimit = 'PT10M'
    $task.Settings.DisallowStartIfOnBatteries = $false
    $task.Settings.StopIfGoingOnBatteries = $false
    $boot = $task.Triggers.Create(8)          # TASK_TRIGGER_BOOT
    $time = $task.Triggers.Create(1)          # TASK_TRIGGER_TIME + 6h repetition
    $time.StartBoundary = (Get-Date).AddMinutes(2).ToString('yyyy-MM-ddTHH:mm:ss')
    $time.Repetition.Interval = 'PT6H'
    $time.Repetition.Duration = 'P3650D'
    $act = $task.Actions.Create(0)
    $act.Path = 'powershell.exe'
    $act.Arguments = '-NoProfile -ExecutionPolicy Bypass -File "' + $runner + '"'
    $act.WorkingDirectory = $Repo
    $root.RegisterTaskDefinition('GBT-SyncGuard', $task, 6, $null, $null, 3) | Out-Null
    Write-Output '已重建 GBT-SyncGuard：开机触发 + 每 6 小时'
    & schtasks.exe /Query /TN "GBT-SyncGuard" /V /FO LIST 2>&1 | Select-String -Pattern 'Status|Next Run Time|Schedule Type|Repeat: Every|Scheduled Task State' | ForEach-Object { $_.Line.Trim() }
    exit 0
} catch {
    Write-Output ('重建失败：' + $_.Exception.Message)
    exit 1
}
