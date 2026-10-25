# =============================================================================
#  run_isolated.ps1 — 一键启动【隔离实例】的钱包服务
# -----------------------------------------------------------------------------
#  与共享环境完全隔离, 互不干扰:
#    * 依赖: 只用 gbt_allinone\.pylibs (缺则自动 bootstrap), 不碰全局 site-packages;
#    * 端口: 默认 8098 (避开常见的 8097 共用实例);
#    * 数据: 全部落在 <仓库>\gbt_runtime\ (wallet/ledger/notify), 不写 ~\.gbt;
#    * 绑定: 只绑 127.0.0.1。
#  用法:
#    $env:GBT_WALLET_PASS='...' ; powershell -File gbt_allinone\deploy\run_isolated.ps1
#    ... -Port 8099 -Foreground
#  退出码: 0=已启动  1=参数/环境错误  2=无解释器  3=端口被占  4=未初始化  5=启动失败
# =============================================================================
[CmdletBinding()]
param(
    [int]$Port = 0,
    [string]$Python = '',
    [string]$EnvFile = '',
    [switch]$Foreground,
    [switch]$DryRun
)

$ErrorActionPreference = 'Stop'
$repoRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$pylibs   = Join-Path $repoRoot 'gbt_allinone\.pylibs'
$bootstrap= Join-Path $PSScriptRoot 'bootstrap_deps.ps1'
$runtime  = Join-Path $repoRoot 'gbt_runtime'
$dataDir  = Join-Path $runtime 'wallet'
$ledgerDir= Join-Path $runtime 'ledger'

function Say($m)  { Write-Host "[gbt-iso] $m" -ForegroundColor Cyan }
function Warn($m) { Write-Host "[gbt-iso] $m" -ForegroundColor Yellow }
function Fail($m, [int]$c = 1) { Write-Host "[gbt-iso] $m" -ForegroundColor Red; exit $c }

if ($Port -le 0) { $Port = if ($env:GBT_ISOLATED_PORT) { [int]$env:GBT_ISOLATED_PORT } else { 8098 } }

# 1) 本地依赖
if (-not (Test-Path -LiteralPath (Join-Path $pylibs '.ok'))) {
    Say "本地依赖缺失, 执行 bootstrap..."
    & powershell -NoProfile -ExecutionPolicy Bypass -File $bootstrap
    if ($LASTEXITCODE -ne 0) { Fail "依赖 bootstrap 失败(退出 $LASTEXITCODE)" 2 }
}

# 2) 解释器
function Resolve-Py {
    $cands = @()
    if ($Python) { $cands += $Python }
    if ($env:GBT_PYTHON) { $cands += $env:GBT_PYTHON }
    $c = Get-Command python -ErrorAction SilentlyContinue
    if ($c) { $cands += $c.Source }
    foreach ($exe in $cands) {
        try { & $exe -c "import sys" 2>$null; if ($LASTEXITCODE -eq 0) { return $exe } } catch { }
    }
    return $null
}
$py = Resolve-Py
if (-not $py) { Fail '找不到可用 python 解释器(可传 -Python 或设 $env:GBT_PYTHON)' 2 }

# 2.5) 可选: 从密封 env 文件加载(含 DPAPI 口令解封); 随后隔离目录/端口会覆盖其中的目录项
function Import-SealedEnv([string]$path) {
    if (-not (Test-Path -LiteralPath $path)) { Fail "env 文件不存在: $path" 1 }
    $dpapi = ''; $dpapiScope = 'LocalMachine'
    foreach ($line in Get-Content -LiteralPath $path -Encoding UTF8) {
        $t = $line.Trim()
        if (-not $t -or $t.StartsWith('#')) { continue }
        $i = $t.IndexOf('=')
        if ($i -lt 1) { continue }
        $k = $t.Substring(0, $i).Trim(); $v = $t.Substring($i + 1)
        if ($k -eq 'GBT_WALLET_PASS_DPAPI') { $dpapi = $v; continue }
        if ($k -eq 'GBT_WALLET_PASS_DPAPI_SCOPE') { $dpapiScope = $v; continue }
        Set-Item -Path ("Env:" + $k) -Value $v
    }
    if ($dpapi -and -not $env:GBT_WALLET_PASS) {
        try {
            Add-Type -AssemblyName System.Security
            $scope = [Security.Cryptography.DataProtectionScope]$dpapiScope
            $env:GBT_WALLET_PASS = [Text.Encoding]::UTF8.GetString(
                [Security.Cryptography.ProtectedData]::Unprotect(
                    [Convert]::FromBase64String($dpapi), $null, $scope))
            Say "已从密封 env 解封口令(DPAPI/$dpapiScope)"
        } catch { Fail "DPAPI 解封失败: $_" 1 }
    }
}
if ($EnvFile) { Import-SealedEnv $EnvFile }

# 3) 隔离环境变量
$env:GBT_WALLET_DIR       = $dataDir
$env:GBT_LEDGER_DIR       = $ledgerDir
$env:GBT_NOTIFY_DIR       = $ledgerDir
$env:GBT_WALLET_PORT      = "$Port"
$env:GBT_WALLET_BIND_HOST = '127.0.0.1'
foreach ($d in @($runtime, $dataDir, $ledgerDir)) { if (-not (Test-Path -LiteralPath $d)) { New-Item -ItemType Directory -Path $d -Force | Out-Null } }

# 4) 口令
if (-not $env:GBT_WALLET_PASS) {
    if ($DryRun) { Warn '[DryRun] 未提供 GBT_WALLET_PASS' }
    else {
        $sec = Read-Host 'Wallet passphrase' -AsSecureString
        $ptr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($sec)
        $env:GBT_WALLET_PASS = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($ptr)
        [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($ptr)
    }
}

# 5) 端口守卫
$listen = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
if ($listen) { Fail "端口 $Port 已被占用 (PID $($listen.OwningProcess -join ',')) — 换端口或先释放" 3 }

# 6) 启动(注入 .pylibs + 仓库根)
$bootstrapCode = "import sys; sys.path.insert(0, r'$pylibs'); sys.path.insert(0, r'$repoRoot'); " +
                 "import runpy; runpy.run_module('gbt_wallet.api', run_name='__main__')"

Say "隔离实例: 端口=$Port  数据=$dataDir  依赖=$pylibs"
Say "健康检查: http://127.0.0.1:$Port/api/gbtwallet/health"

if ($DryRun) { Say "[DryRun] 将执行: `"$py`" -c <bootstrap(gbt_wallet.api)>"; exit 0 }

if ($Foreground) {
    & $py -c $bootstrapCode --port $Port
    exit $LASTEXITCODE
} else {
    $args = @('-c', ('"' + $bootstrapCode + '"'), '--port', "$Port")
    Start-Process -FilePath $py -ArgumentList $args -WorkingDirectory $repoRoot -WindowStyle Hidden
    Start-Sleep -Seconds 3
    try {
        $r = Invoke-WebRequest -Uri "http://127.0.0.1:$Port/api/gbtwallet/health" -TimeoutSec 8 -UseBasicParsing
        Say "已启动, HTTP 健康检查: $($r.StatusCode)"
    } catch { Warn "已拉起进程, 但健康检查未通过: $($_.Exception.Message)" }
    exit 0
}