# =============================================================================
#  bootstrap_deps.ps1 — 项目本地依赖隔离
# -----------------------------------------------------------------------------
#  把 gbt_allinone/requirements.txt 装到 gbt_allinone\.pylibs (不写全局 site-packages)。
#  启动器会把该目录注入 sys.path, 因此 AutoClaw bundled python 被重置也不影响本项目。
#  用法:  powershell -ExecutionPolicy Bypass -File gbt_allinone\deploy\bootstrap_deps.ps1 [-Force]
#  退出码: 0=就绪/已安装  2=找不到可用解释器  5=安装失败
# =============================================================================
[CmdletBinding()]
param([switch]$Force, [string]$Python = '')

$ErrorActionPreference = 'Stop'
$root  = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$libs  = Join-Path $root 'gbt_allinone\.pylibs'
$req   = Join-Path $root 'gbt_allinone\requirements.txt'
$mark  = Join-Path $libs '.ok'

function Say($m) { Write-Host "[gbt-deps] $m" -ForegroundColor Cyan }
function Fail($m, [int]$c = 5) { Write-Host "[gbt-deps] $m" -ForegroundColor Red; exit $c }

function Resolve-Py {
    $cands = @()
    if ($Python) { $cands += $Python }
    if ($env:GBT_PYTHON) { $cands += $env:GBT_PYTHON }
    $c = Get-Command python -ErrorAction SilentlyContinue
    if ($c) { $cands += $c.Source }
    foreach ($v in @('.venv\Scripts\python.exe', 'venv\Scripts\python.exe')) {
        $p = Join-Path $root $v; if (Test-Path -LiteralPath $p) { $cands += $p }
    }
    $pyLauncher = Get-Command py -ErrorAction SilentlyContinue
    if ($pyLauncher) { $cands += $pyLauncher.Source }
    foreach ($exe in $cands) {
        try {
            $ver = & $exe -c "import sys;print('%d.%d'%sys.version_info[:2])" 2>$null
            if ($LASTEXITCODE -eq 0 -and $ver) { return @{ exe = $exe; ver = "$ver" } }
        } catch { }
    }
    return $null
}

if ((Test-Path -LiteralPath $mark) -and -not $Force) { Say "本地依赖已就绪: $libs"; exit 0 }

$py = Resolve-Py
if (-not $py) { Fail '找不到可用的 python 解释器' 2 }
Say "使用解释器: $($py.exe) (Python $($py.ver))"
Say "安装依赖 -> $libs"
if (-not (Test-Path -LiteralPath $libs)) { New-Item -ItemType Directory -Path $libs -Force | Out-Null }
& $py.exe -m pip install --disable-pip-version-check --target $libs -r $req
if ($LASTEXITCODE -ne 0) { Fail '依赖安装失败' 5 }
"ok $(Get-Date -Format o)" | Set-Content -LiteralPath $mark -Encoding ASCII
$sz = [math]::Round(((Get-ChildItem $libs -Recurse -File | Measure-Object Length -Sum).Sum)/1MB, 1)
Say "完成: $libs ($sz MB)"
exit 0