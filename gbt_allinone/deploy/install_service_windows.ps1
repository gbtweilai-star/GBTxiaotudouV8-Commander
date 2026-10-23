# =============================================================================
#  install_service_windows.ps1 — 把 gbt_wallet 注册为 Windows 服务(两种方式, 二选一)
# -----------------------------------------------------------------------------
#  方式 A: 计划任务(推荐, 零第三方依赖, 内置)
#      - 任务在开机时以指定账号运行; 自动重启(UAC 下的失败重试);
#      - 适合单机自建部署, 不需要额外二进制。
#  方式 B: NSSM(第三方, 可执行文件需自行下载)
#      - 真正的 Windows 服务, 支持 services.msc / sc.exe 统一管理、自动重启;
#      - 需要 nssm.exe(https://nssm.cc/download); 本脚本不自带、不下载。
#
#  两种方式都用同一个"密封环境文件"提供口令: 运行 `-Action Seal` 交互输入口令,
#  脚本用 Windows DPAPI 加密后写入 env 文件(默认 LocalMachine 作用域), 明文不落盘。
#  DPAPI 的边界(务必知悉): 同机管理员/SYSTEM 仍可解密; 它防的是"文件被拷走/误提交",
#  不防"主机已被完全接管"。要更强隔离, 请把钱包放到独立主机/容器 + 反向代理(见 DEPLOY.md)。
#
#  用法:
#    # 1) 先密封口令文件(只需一次; 换口令时重跑)
#    powershell -ExecutionPolicy Bypass -File gbt_allinone\deploy\install_service_windows.ps1 `
#        -Action Seal -EnvFile C:\ProgramData\gbt-wallet\wallet.env
#    # 2) 安装(二选一)
#    ... -Action Install -Mode Task -EnvFile C:\ProgramData\gbt-wallet\wallet.env
#    ... -Action Install -Mode Nssm -EnvFile C:\ProgramData\gbt-wallet\wallet.env -NssmPath C:\tools\nssm\nssm.exe
#    # 3) 启停 / 状态 / 卸载
#    ... -Action Start | Stop | Status | Uninstall [-Mode Task|Nssm]
#
#  退出码: 0=成功  1=参数/环境错误  2=缺少依赖(nssm/powershell)  3=需要管理员权限
# =============================================================================
[CmdletBinding()]
param(
    [ValidateSet('Seal', 'Install', 'Uninstall', 'Start', 'Stop', 'Status')]
    [string]$Action = 'Install',
    [ValidateSet('Task', 'Nssm')]
    [string]$Mode = 'Task',
    [string]$EnvFile = '',
    [string]$NssmPath = '',
    [int]$Port = 0,
    [string]$TaskName = 'GbtWalletService',
    [string]$ServiceName = 'GbtWallet',
    [ValidateSet('LocalMachine', 'CurrentUser')]
    [string]$DpapiScope = 'LocalMachine',
    [switch]$NonIsolated,
    [switch]$DryRun
)

$ErrorActionPreference = 'Stop'
$repoRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
# 默认安装"隔离实例"(run_isolated.ps1: 本地依赖 + 独立端口/数据目录); 传 -NonIsolated 回退共享版
$runner = Join-Path $PSScriptRoot $(if ($NonIsolated) { 'run_wallet.ps1' } else { 'run_isolated.ps1' })
$powershellExe = Join-Path $env:SystemRoot 'System32\WindowsPowerShell\v1.0\powershell.exe'

function Say($m) { Write-Host "[gbt-service] $m" -ForegroundColor Cyan }
function Warn($m) { Write-Host "[gbt-service] $m" -ForegroundColor Yellow }
function Fail($m, [int]$code = 1) { Write-Host "[gbt-service] $m" -ForegroundColor Red; exit $code }
function Is-Admin {
    $id = [Security.Principal.WindowsIdentity]::GetCurrent()
    (New-Object Security.Principal.WindowsPrincipal($id)).IsInRole(
        [Security.Principal.WindowsBuiltInRole]::Administrator)
}
function Invoke-Step([string]$desc, [scriptblock]$block) {
    if ($DryRun) { Say "[DryRun] $desc"; return }
    Say $desc
    & $block
}

if ($Port -le 0) { if ($env:GBT_WALLET_PORT) { $Port = [int]$env:GBT_WALLET_PORT } else { $Port = 8097 } }
if (-not $EnvFile) { $EnvFile = Join-Path $env:ProgramData 'gbt-wallet\wallet.env' }
if (-not (Test-Path -LiteralPath $runner)) { Fail "找不到 $runner (启动器需与本脚本同目录)" }

# ---------- Seal: 交互输入口令 -> DPAPI 加密写入 env 文件 ----------
function New-SealedEnvFile {
    if (-not (Test-Path -LiteralPath (Split-Path -Parent $EnvFile))) {
        Invoke-Step "创建目录 $(Split-Path -Parent $EnvFile)" {
            New-Item -ItemType Directory -Path (Split-Path -Parent $EnvFile) -Force | Out-Null }
    }
    if ($DryRun) {
        Say "[DryRun] 将交互读取口令并以 DPAPI($DpapiScope) 加密写入 $EnvFile"
        return
    }
    $sec = Read-Host 'Wallet passphrase (将被 DPAPI 加密, 不回显)' -AsSecureString
    $ptr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($sec)
    try {
        $plain = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($ptr)
        if (-not $plain) { Fail '口令为空, 中止' }
        Add-Type -AssemblyName System.Security
        $scope = [Security.Cryptography.DataProtectionScope]::$DpapiScope
        $blob = [Security.Cryptography.ProtectedData]::Protect(
            [Text.Encoding]::UTF8.GetBytes($plain), $null, $scope)
        $b64 = [Convert]::ToBase64String($blob)
    } finally {
        [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($ptr)
        $plain = $null
    }
    if ($NonIsolated) {
        $dataDir = if ($env:GBT_WALLET_DIR) { $env:GBT_WALLET_DIR } else { Join-Path $env:USERPROFILE '.gbt\gbt_wallet' }
    } else {
        $dataDir = Join-Path $repoRoot 'gbt_runtime\wallet'   # 隔离实例: 数据落在仓库内
    }
    $lines = @(
        '# gbt-wallet 服务环境(由 install_service_windows.ps1 -Action Seal 生成)',
        '# GBT_WALLET_PASS 已用 Windows DPAPI 加密; 同机管理员/SYSTEM 仍可解密 —— 见 DEPLOY.md',
        "GBT_WALLET_PASS_DPAPI=$b64",
        "GBT_WALLET_PASS_DPAPI_SCOPE=$DpapiScope",
        "GBT_WALLET_DIR=$dataDir",
        "GBT_WALLET_PORT=$Port",
        'GBT_WALLET_BIND_HOST=127.0.0.1',
        'GBT_CORS_ORIGINS='
    )
    if (-not $NonIsolated) {
        $lines += "GBT_LEDGER_DIR=$(Join-Path $repoRoot 'gbt_runtime\ledger')"
        $lines += "GBT_NOTIFY_DIR=$(Join-Path $repoRoot 'gbt_runtime\ledger')"
    }
    if ($env:GBT_WALLET_API_TOKEN) { $lines += "GBT_WALLET_API_TOKEN=$($env:GBT_WALLET_API_TOKEN)" }
    if ($env:GBT_EVM_RPC) { $lines += "GBT_EVM_RPC=$($env:GBT_EVM_RPC)" }
    # UTF-8 无 BOM 写出: 避免非 ASCII(中文注释 / 含中文的路径值)被 ASCII 编码写坏
    [System.IO.File]::WriteAllLines($EnvFile, [string[]]$lines, (New-Object System.Text.UTF8Encoding($false)))
    Say "已写入密封环境文件: $EnvFile (DPAPI 作用域: $DpapiScope)"
    # ACL 收紧: 去掉继承, 仅 SYSTEM + Administrators 可读
    # (用 .NET ACL 而不是 icacls: PS 5.1 会给含括号/冒号的参数补引号, icacls 会报"无效参数")
    try {
        $acl = Get-Acl -LiteralPath $EnvFile
        $acl.SetAccessRuleProtection($true, $false)
        foreach ($rule in @($acl.Access)) { [void]$acl.RemoveAccessRule($rule) }
        foreach ($sid in @('S-1-5-18', 'S-1-5-32-544')) {   # SYSTEM / Administrators(用 SID 免语言差异)
            $id = New-Object Security.Principal.SecurityIdentifier($sid)
            $rule = New-Object Security.AccessControl.FileSystemAccessRule($id, 'Read', 'Allow')
            [void]$acl.AddAccessRule($rule)
        }
        Set-Acl -LiteralPath $EnvFile -AclObject $acl
        Say '已收紧 ACL: 仅 SYSTEM 与 Administrators 可读'
    } catch { Warn "icacls 收紧失败(请手工确认权限): $_" }
    Warn '提醒: 口令明文仅存在于本次输入的内存中; 若要换口令, 重新 Seal 并重启服务。'
}

# ---------- 方式 A: 计划任务 ----------
function Get-TaskActionCmd {
    # 计划任务动作: 解释器 + <runner> -Foreground -Port <端口> -EnvFile <密封文件>
    # (runner 默认 run_isolated.ps1 = 隔离实例; -NonIsolated 时用 run_wallet.ps1)
    @(
        '-NoProfile', '-NonInteractive', '-ExecutionPolicy', 'Bypass',
        '-File', ('"' + $runner + '"'),
        '-Foreground', '-Port', "$Port", '-EnvFile', ('"' + $EnvFile + '"')
    ) -join ' '
}
function Install-Task {
    if (-not (Test-Path -LiteralPath $EnvFile)) { Fail "缺少环境文件 $EnvFile ; 先运行 -Action Seal" }
    $action = (Get-TaskActionCmd)
    Invoke-Step "注册计划任务 $TaskName (开机启动, 以 SYSTEM 运行)" {
        $sa = New-ScheduledTaskAction -Execute $powershellExe -Argument $action -WorkingDirectory $repoRoot
        $tr = New-ScheduledTaskTrigger -AtStartup
        $set = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries `
            -StartWhenAvailable -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1) `
            -ExecutionTimeLimit ([TimeSpan]::Zero)
        $pr = New-ScheduledTaskPrincipal -UserId 'SYSTEM' -LogonType ServiceAccount -RunLevel Highest
        Register-ScheduledTask -TaskName $TaskName -Action $sa -Trigger $tr -Settings $set -Principal $pr -Force | Out-Null
        Start-ScheduledTask -TaskName $TaskName
        Say "已注册并启动: $TaskName"
    }
}
function Uninstall-Task {
    Invoke-Step "停止并删除计划任务 $TaskName" {
        try { Stop-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue } catch { }
        Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false -ErrorAction SilentlyContinue
    }
    Stop-PortOwner
}

# ---------- 方式 B: NSSM ----------
function Get-Nssm {
    if ($NssmPath -and (Test-Path -LiteralPath $NssmPath)) { return $NssmPath }
    $c = Get-Command nssm -ErrorAction SilentlyContinue
    if ($c) { return $c.Source }
    Fail "未找到 nssm.exe; 下载后传 -NssmPath 或加入 PATH (本脚本不自动下载)" 2
}
function Install-Nssm {
    $nssm = Get-Nssm
    if (-not (Test-Path -LiteralPath $EnvFile)) { Fail "缺少环境文件 $EnvFile ; 先运行 -Action Seal" }
    $action = Get-TaskActionCmd
    Invoke-Step "注册 Windows 服务 $ServiceName (NSSM)" {
        & $nssm install $ServiceName $powershellExe $action | Out-Null
        & $nssm set $ServiceName AppDirectory $repoRoot | Out-Null
        & $nssm set $ServiceName Start SERVICE_AUTO_START | Out-Null
        & $nssm set $ServiceName AppExit Default Restart | Out-Null
        & $nssm set $ServiceName AppRestartDelay 5000 | Out-Null
        $logDir = Join-Path $env:ProgramData 'gbt-wallet\logs'
        New-Item -ItemType Directory -Path $logDir -Force | Out-Null
        & $nssm set $ServiceName AppStdout (Join-Path $logDir 'service.out.log') | Out-Null
        & $nssm set $ServiceName AppStderr (Join-Path $logDir 'service.err.log') | Out-Null
        & $nssm set $ServiceName AppRotateFiles 1 | Out-Null
        & $nssm set $ServiceName AppRotateBytes 10485760 | Out-Null
        Start-Service $ServiceName
        Say "已安装并启动服务: $ServiceName"
    }
}
function Uninstall-Nssm {
    $nssm = Get-Nssm
    Invoke-Step "停止并卸载服务 $ServiceName" {
        & $nssm stop $ServiceName confirm | Out-Null
        & $nssm remove $ServiceName confirm | Out-Null
    }
}

# ---------- 停止占用端口的进程(用于任务模式, 任务停止不一定杀子进程) ----------
function Get-PortOwners {
    try {
        $conn = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
        if ($conn) { return @($conn.OwningProcess | Select-Object -Unique) }
    } catch { }
    return @()
}
function Stop-PortOwner {
    $owners = @(Get-PortOwners)
    if ($owners.Count -eq 0) { Say "端口 $Port 当前无监听进程"; return }
    foreach ($ownerPid in $owners) {
        if ($DryRun) { Say "[DryRun] 将结束进程 PID $ownerPid (占用 $Port)"; continue }
        try { Stop-Process -Id $ownerPid -Force; Say "已结束 PID $ownerPid" }
        catch { Warn "结束 PID $ownerPid 失败: $_" }
    }
}

# ---------- 分发 ----------
switch ($Action) {
    'Seal' {
        if ($DpapiScope -eq 'LocalMachine' -and -not (Is-Admin) -and -not $DryRun) {
            Warn 'LocalMachine 作用域的 DPAPI 通常需要管理员权限; 若失败请以管理员运行, 或改用 -DpapiScope CurrentUser'
        }
        New-SealedEnvFile
    }
    'Install' {
        if (-not (Is-Admin)) { Fail '安装服务/计划任务需要管理员权限(以管理员身份打开 PowerShell)' 3 }
        if ($Mode -eq 'Task') { Install-Task } else { Install-Nssm }
    }
    'Uninstall' {
        if (-not (Is-Admin)) { Fail '卸载需要管理员权限' 3 }
        if ($Mode -eq 'Task') { Uninstall-Task } else { Uninstall-Nssm }
    }
    'Start' {
        if ($Mode -eq 'Task') { Invoke-Step "启动计划任务 $TaskName" { Start-ScheduledTask -TaskName $TaskName } }
        else { $nssm = Get-Nssm; Invoke-Step "启动服务 $ServiceName" { & $nssm start $ServiceName } }
        Say "健康检查: http://127.0.0.1:$Port/api/gbtwallet/health"
    }
    'Stop' {
        if ($Mode -eq 'Task') {
            Invoke-Step "停止计划任务 $TaskName" { try { Stop-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue } catch { } }
            Stop-PortOwner
        } else {
            $nssm = Get-Nssm
            Invoke-Step "停止服务 $ServiceName" { & $nssm stop $ServiceName }
        }
    }
    'Status' {
        if ($Mode -eq 'Task') {
            $t = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
            if ($t) { $i = Get-ScheduledTaskInfo -TaskName $TaskName
                Say "任务 ${TaskName}: State=$($t.State) LastRun=$($i.LastRunTime) LastResult=$($i.LastTaskResult)" }
            else { Warn "任务 $TaskName 未注册" }
        } else {
            $s = Get-Service -Name $ServiceName -ErrorAction SilentlyContinue
            if ($s) { Say "服务 ${ServiceName}: Status=$($s.Status) StartType=$($s.StartType)" }
            else { Warn "服务 $ServiceName 未安装" }
        }
        $owners = @(Get-PortOwners)
        if ($owners.Count -gt 0) { Say "端口 $Port 监听 PID: $($owners -join ',')" }
        else { Say "端口 $Port 无监听进程" }
        try {
            $r = Invoke-WebRequest -Uri "http://127.0.0.1:$Port/api/gbtwallet/health" -TimeoutSec 5 -UseBasicParsing
            Say "HTTP 健康检查: $($r.StatusCode)"
        } catch { Warn "HTTP 健康检查失败: $($_.Exception.Message)" }
    }
}
exit 0
