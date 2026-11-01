# gbt-capability: sync_guard
# 开发者：自由的风 · 永久钢印 · 禁止删除
<#
setup-system-task.ps1 — 注册"无人登录也跑"的 GBT-SyncGuard-System（需管理员）
效果：SYSTEM 账户 + 开机触发 + 每 6 小时；工作目录=仓根；跑 tools\sync-guard-patrol.ps1
      （巡检 + sched_tick 到期工作流，共用心跳）。
非管理员：只打印提权命令，不改系统。
用法（管理员）：
  powershell -NoProfile -ExecutionPolicy Bypass -File tools\setup-system-task.ps1
#>
param([string]$Repo = '')

$ErrorActionPreference = 'Stop'
if (-not $Repo) { $Repo = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..')).Path }
$Repo = (Resolve-Path -LiteralPath $Repo).Path
$runner = Join-Path $Repo 'tools\sync-guard-patrol.ps1'
if (-not (Test-Path -LiteralPath $runner)) { throw "runner 缺失：$runner" }

$id = [Security.Principal.WindowsIdentity]::GetCurrent()
$pr = New-Object Security.Principal.WindowsPrincipal($id)
if (-not $pr.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    Write-Output '需要管理员：右键"以管理员身份运行" PowerShell，然后执行：'
    Write-Output ('  powershell -NoProfile -ExecutionPolicy Bypass -File "' + (Join-Path $Repo 'tools\setup-system-task.ps1') + '"')
    Write-Output '（非管理员不动系统；登录自启已由 Startup\GBT-SyncGuard.cmd 覆盖）'
    exit 2
}

$svc = New-Object -ComObject Schedule.Service
$svc.Connect()
$root = $svc.GetFolder('\')
$task = $svc.NewTask(0)
$task.RegistrationInfo.Description = 'GBT 双仓巡检 + 到期工作流（SYSTEM 无人登录；6h/开机）'
$task.Settings.Enabled = $true
$task.Settings.StartWhenAvailable = $true
$task.Settings.ExecutionTimeLimit = 'PT15M'
$task.Settings.DisallowStartIfOnBatteries = $false
$task.Settings.StopIfGoingOnBatteries = $false
$task.Principal.UserId = 'SYSTEM'
$task.Principal.LogonType = 5          # TASK_LOGON_SERVICE_ACCOUNT
$task.Principal.RunLevel = 1           # highest
$boot = $task.Triggers.Create(8)
$time = $task.Triggers.Create(1)
$time.StartBoundary = (Get-Date).AddMinutes(2).ToString('yyyy-MM-ddTHH:mm:ss')
$time.Repetition.Interval = 'PT6H'
$time.Repetition.Duration = 'P3650D'
$act = $task.Actions.Create(0)
$act.Path = 'powershell.exe'
$act.Arguments = '-NoProfile -ExecutionPolicy Bypass -File "' + $runner + '"'
$act.WorkingDirectory = $Repo
$root.RegisterTaskDefinition('GBT-SyncGuard-System', $task, 6, 'SYSTEM', '', 5) | Out-Null
Write-Output '已注册 GBT-SyncGuard-System（SYSTEM / 开机 / 每 6 小时）'
& schtasks.exe /Query /TN "GBT-SyncGuard-System" /V /FO LIST 2>&1 | Select-String -Pattern 'TaskName|Status|Next Run Time|Task To Run|Run As User|Schedule Type|Repeat: Every' | ForEach-Object { $_.Line.Trim() }
exit 0
