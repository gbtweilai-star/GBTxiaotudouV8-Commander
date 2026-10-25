# =============================================================================
#  install_codex_relay_watchdog.ps1 — 给 Codex 中继装上真正的"狗绳"
# -----------------------------------------------------------------------------
#  背景：v1 看门狗脚本存在，但没有任何计划任务/服务在启动它 ——
#        2026-09-17 早上 4446 挂掉后无人拉起，三条会话全 0 token。
#        本脚本把 codex_relay_watchdog.py --once 注册为每分钟一次的计划任务，
#        中继挂掉后最多 60 秒自动恢复。
#
#  为什么用"每分钟跑一次 --once"而不是常驻死循环：
#    * 无常驻进程 → 不会因为看门狗自己死掉而再次静默；
#    * 单实例锁保证不叠加；
#    * 计划任务本身就是"看门狗在看门"的证据，schtasks /Query 可查。
#
#  用法（需当前用户身份，通常不必管理员）：
#    powershell -File gbt_allinone\deploy\install_codex_relay_watchdog.ps1
#    ... -Uninstall      # 卸载计划任务
#    ... -DryRun         # 只打印将要执行的命令
# =============================================================================
[CmdletBinding()]
param(
    [string]$TaskName = '\GBT\CodexRelayWatchdog',
    [string]$Python   = 'C:\Python310\python.exe',
    [string]$Repo     = 'C:\Users\ADMIN\Desktop\GBT小土豆V8',
    [switch]$Uninstall,
    [switch]$DryRun
)

$ErrorActionPreference = 'Stop'

function Say([string]$m) { Write-Host "[watchdog] $m" }

$script = Join-Path $Repo 'gbt_allinone\deploy\codex_relay_watchdog.py'

if ($Uninstall) {
    if ($DryRun) { Say "[DryRun] schtasks /Delete /TN $TaskName /F"; exit 0 }
    schtasks /Delete /TN $TaskName /F | Out-Null
    Say "已卸载计划任务 $TaskName"
    exit 0
}

if (-not (Test-Path $script)) { throw "找不到看门狗脚本: $script" }
if (-not (Test-Path $Python)) { throw "找不到解释器: $Python（看门狗只需标准库，3.10 即可）" }

$action = '"{0}" "{1}" --once' -f $Python, $script
$schArgs = @('/Create', '/TN', $TaskName, '/TR', $action, '/SC', 'MINUTE', '/MO', '1', '/F')

if ($DryRun) {
    Say "[DryRun] schtasks $($schArgs -join ' ')"
    Say "[DryRun] （不会真的注册）"
    exit 0
}

Say "注册计划任务 $TaskName（每 1 分钟执行一次 --once）"
schtasks @schArgs | Out-Null

Say "任务信息："
schtasks /Query /TN $TaskName /FO LIST | Select-String -Pattern 'TaskName|Status|Next Run|下次运行|状态|任务名'

Say "立即跑一轮，验证自愈链路"
schtasks /Run /TN $TaskName | Out-Null
Start-Sleep -Seconds 8

& $Python $script --status
$code = $LASTEXITCODE
if ($code -eq 0) {
    Say "验收通过：中继健康（4446 有响应且 key_source 可用）"
} else {
    Say "验收未通过：--status 返回 $code，请看 C:\Users\ADMIN\.codex\log\relay_watchdog.log"
    exit $code
}
