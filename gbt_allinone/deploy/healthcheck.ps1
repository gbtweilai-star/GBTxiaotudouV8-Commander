# =============================================================================
#  healthcheck.ps1 — gbt_wallet 与融合框架的自检(可被计划任务/监控每 5 分钟调用)
# -----------------------------------------------------------------------------
#  检查项:
#    A. 钱包 HTTP: GET {Base}/api/gbtwallet/health  -> 200 且 ok=true
#       (设置了 GBT_WALLET_API_TOKEN 时自动带 Authorization: Bearer)
#    B. 框架自检: python -c "gbt_allinone.run_task('health')" -> status=ok 且能力清单可用
#    C. 接轨层: auth 状态(是否启用鉴权/令牌指纹) + platform_client 可导入
#    D. 本地数据根: master.enc 是否存在(钱包是否已初始化)
#
#  退出码(位掩码): 0=全部正常
#                  1=钱包 HTTP 异常  2=框架自检异常  4=接轨层异常
#                  (可叠加: 3=钱包+框架都异常, 7=全部异常)
#
#  用法:
#    powershell -ExecutionPolicy Bypass -File gbt_allinone\deploy\healthcheck.ps1
#    ... -Json                       # 输出单行 JSON(喂给监控/告警管道)
#    ... -Base https://wallet.example.com -Token $env:GBT_WALLET_API_TOKEN
# =============================================================================
[CmdletBinding()]
param(
    [int]$Port = 0,
    [string]$Base = '',
    [string]$Token = '',
    [int]$TimeoutSec = 8,
    [switch]$SkipFramework,
    [switch]$Json
)

$ErrorActionPreference = 'Continue'
$repoRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$exit = 0
$result = [ordered]@{ ts = (Get-Date).ToString('s'); checks = [ordered]@{} }

function Note($m) { if (-not $Json) { Write-Host $m } }

if ($Port -le 0) { if ($env:GBT_WALLET_PORT) { $Port = [int]$env:GBT_WALLET_PORT } else { $Port = 8097 } }
if (-not $Base) { if ($env:GBT_WALLET_API_BASE) { $Base = $env:GBT_WALLET_API_BASE } else { $Base = "http://127.0.0.1:$Port" } }
$Base = $Base.TrimEnd('/')
if (-not $Token) { $Token = [string]$env:GBT_WALLET_API_TOKEN }

# ---------- 解释器(路径无关, 与 run_wallet.ps1 同一策略) ----------
# 返回 @{ exe = <解释器路径>; pre = @(<前置参数>) }; 用数组传递, 避免把
# "C:\Program Files\..." 这类带空格的路径按空格切开。
function Resolve-Py {
    $cands = @()
    if ($env:GBT_PYTHON) { $cands += $env:GBT_PYTHON }
    $c = Get-Command python -ErrorAction SilentlyContinue
    if ($c) { $cands += $c.Source }
    foreach ($rel in @('.venv\Scripts\python.exe', 'venv\Scripts\python.exe')) {
        $p = Join-Path $repoRoot $rel
        if (Test-Path -LiteralPath $p) { $cands += $p }
    }
    foreach ($cand in $cands) {
        if (-not $cand) { continue }
        try {
            $probe = "import sys; sys.path.insert(0, r'$repoRoot'); import fastapi, gbt_allinone"
            $null = & $cand '-c' $probe 2>$null
            if ($LASTEXITCODE -eq 0) { return @{ exe = $cand; pre = @() } }
        } catch { }
    }
    foreach ($rel in @((Join-Path (Split-Path $PSHOME -Parent) 'python.exe'),
                       (Join-Path (Split-Path (Split-Path $PSHOME -Parent) -Parent) 'python.exe'))) {
        if ($rel -and (Test-Path -LiteralPath $rel)) {
            try {
                $probe = "import sys; sys.path.insert(0, r'$repoRoot'); import fastapi, gbt_allinone"
                $null = & $rel '-c' $probe 2>$null
                if ($LASTEXITCODE -eq 0) { return @{ exe = $rel; pre = @() } }
            } catch { }
        }
    }
    $py = Get-Command py -ErrorAction SilentlyContinue
    if ($py) { return @{ exe = $py.Source; pre = @('-3') } }   # 兜底: py 启动器
    return $null
}
$pyInfo = Resolve-Py
function Invoke-Py([string]$code) {
    if (-not $pyInfo) { throw '找不到可用 python 解释器' }
    if ($pyInfo.pre.Count -gt 0) { & $pyInfo.exe @($pyInfo.pre) '-c' $code 2>&1 }
    else { & $pyInfo.exe '-c' $code 2>&1 }
}

# ---------- A. 钱包 HTTP ----------
$http = [ordered]@{ ok = $false; status = $null; body = $null; error = '' ; url = "$Base/api/gbtwallet/health" }
try {
    $headers = @{}
    if ($Token) { $headers['Authorization'] = "Bearer $Token" }
    $r = Invoke-WebRequest -Uri $http.url -Headers $headers -TimeoutSec $TimeoutSec -UseBasicParsing
    $http.status = [int]$r.StatusCode
    $parsed = $null
    try { $parsed = $r.Content | ConvertFrom-Json } catch { }
    $http.body = $parsed
    if ($r.StatusCode -eq 200 -and $parsed -and $parsed.ok -eq $true) {
        $http.ok = $true
        Note ("[A] 钱包 HTTP OK  : {0}  initialized={1} pending={2} version={3}" -f `
                $http.url, $parsed.initialized, $parsed.pending, $parsed.version)
    } else {
        $http.error = "非 200 或 ok!=true (status=$($r.StatusCode))"
        $exit = $exit -bor 1
        Note "[A] 钱包 HTTP 异常: $($http.error)"
    }
} catch {
    $code = $null
    try { $code = [int]$_.Exception.Response.StatusCode } catch { }
    $http.status = $code
    $http.error = $_.Exception.Message
    $exit = $exit -bor 1
    if ($code -eq 401) {
        $http.error = '401 鉴权失败: 服务已启用 GBT_WALLET_API_TOKEN, 请提供同一令牌'
    }
    Note "[A] 钱包 HTTP 失败: $($http.error)"
}
$result.checks.wallet_http = $http

# ---------- B. 框架自检 ----------
$fw = [ordered]@{ ok = $false; version = ''; caps = 0; error = '' }
if ($SkipFramework) {
    $fw.ok = $true; $fw.error = 'skipped'
    Note '[B] 框架自检   : 已跳过 (-SkipFramework)'
} elseif (-not $pyInfo) {
    $fw.error = '找不到可用 python 解释器'
    $exit = $exit -bor 2
    Note "[B] 框架自检失败: $($fw.error)"
} else {
    # 注意: 传给原生 exe 的 Python 源码里只能用单引号字符串 —— Windows PowerShell 5.1
    # 在向原生命令传参时会剥掉双引号(经典 quoting 问题), 用双引号会得到 "rC:\..." 这类语法错误。
    $probe = @"
import json, sys
sys.path.insert(0, r'$repoRoot')
import gbt_allinone as g
r = g.run_task('health')
lc = g.list_capabilities()
print(json.dumps({'status': r.get('status'), 'caps': len(lc),
                  'version': getattr(g, '__version__', ''),
                  'python': (r.get('result') or {}).get('python')}, ensure_ascii=False))
"@
    try {
        $out = Invoke-Py $probe
        $text = ($out | Select-Object -Last 1)
        $obj = $text | ConvertFrom-Json
        if ($obj.status -eq 'ok' -and $obj.caps -gt 0) {
            $fw.ok = $true; $fw.version = $obj.version; $fw.caps = [int]$obj.caps
            Note ("[B] 框架自检 OK: run_task(health)={0}, 能力 {1} 项, python {2}" -f `
                    $obj.status, $obj.caps, $obj.python)
        } else {
            $fw.error = "status=$($obj.status) caps=$($obj.caps)"
            $exit = $exit -bor 2
            Note "[B] 框架自检异常: $($fw.error)"
        }
    } catch {
        $fw.error = $_.Exception.Message
        $exit = $exit -bor 2
        Note "[B] 框架自检失败: $($fw.error)"
    }
}
$result.checks.framework = $fw

# ---------- C. 接轨层 ----------
$ig = [ordered]@{ ok = $false; auth_enabled = $false; auth_enforced = $null; fingerprint = ''; error = '' }
$probe2 = @"
import json, sys
sys.path.insert(0, r'$repoRoot')
from gbt_allinone.integration.auth import status
from gbt_allinone.integration.platform_client import WalletClient
print(json.dumps({'auth': status(), 'client': bool(WalletClient)}, ensure_ascii=False))
"@
if (-not $pyInfo) {
    $ig.error = '找不到可用 python 解释器'; $exit = $exit -bor 4
} else {
    try {
        $out2 = Invoke-Py $probe2
        $obj2 = (($out2 | Select-Object -Last 1)) | ConvertFrom-Json
        $ig.ok = $true
        $ig.auth_enabled = [bool]$obj2.auth.auth_enabled
        $ig.fingerprint = [string]$obj2.auth.token_fingerprint
        Note ("[C] 接轨层 OK   : auth_enabled={0} token指纹={1} cors={2}" -f `
                $ig.auth_enabled, $(if ($ig.fingerprint) { $ig.fingerprint } else { '(未设置)' }), `
                ($obj2.auth.cors_origins -join ','))
        if ($ig.auth_enabled -and -not $Token) {
            Note '    ⚠ 服务端已启用令牌鉴权, 但本脚本未拿到令牌(设 $env:GBT_WALLET_API_TOKEN 或 -Token)'
        }
        # "env 里设了令牌" ≠ "服务真的在鉴权": 集成层没被加载时令牌形同虚设(退回不鉴权)。
        # 因此做一次无令牌探测: 期望被拒(401); 若拿到 200, 说明鉴权实际未生效。
        if ($ig.auth_enabled) {
            $enforced = $false
            try {
                $probeNone = Invoke-WebRequest -Uri "$Base/api/gbtwallet/health" -TimeoutSec $TimeoutSec -UseBasicParsing
                if ($probeNone.StatusCode -eq 200) { $enforced = $false }
            } catch {
                $code2 = $null
                try { $code2 = [int]$_.Exception.Response.StatusCode } catch { }
                if ($code2 -eq 401) { $enforced = $true }
            }
            $ig.auth_enforced = $enforced
            if ($enforced) { Note '    ✓ 无令牌探测被拒(401) —— 鉴权确实生效' }
            else {
                $ig.error = 'env 已设令牌, 但无令牌请求仍返回 200: 鉴权未生效(服务可能未加载接轨层)'
                $exit = $exit -bor 4
                Note "    ✗ $($ig.error)"
            }
        }
    } catch {
        $ig.error = $_.Exception.Message; $exit = $exit -bor 4
        Note "[C] 接轨层失败: $($ig.error)"
    }
}
$result.checks.integration = $ig

# ---------- D. 数据根 ----------
$dataDir = if ($env:GBT_WALLET_DIR) { $env:GBT_WALLET_DIR } else { Join-Path $env:USERPROFILE '.gbt\gbt_wallet' }
$dr = [ordered]@{ dir = $dataDir; initialized = (Test-Path -LiteralPath (Join-Path $dataDir 'master.enc')) }
$result.checks.data_root = $dr
Note ("[D] 数据根      : {0} (master.enc {1})" -f $dataDir, $(if ($dr.initialized) { '存在' } else { '缺失' }))

$result.exit_code = $exit
if ($Json) {
    ($result | ConvertTo-Json -Depth 6 -Compress)
} else {
    if ($exit -eq 0) { Write-Host '[healthcheck] 全部正常 (exit 0)' -ForegroundColor Green }
    else { Write-Host "[healthcheck] 存在异常, exit=$exit (1=钱包 2=框架 4=接轨层)" -ForegroundColor Red }
}
exit $exit
