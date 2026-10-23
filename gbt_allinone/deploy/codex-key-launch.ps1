# =============================================================================
#  codex-key-launch.ps1 — 带密钥的 Codex 启动器（给非终端入口用）
# -----------------------------------------------------------------------------
#  终端入口走 PowerShell profile（自动注入）；图形入口（快捷方式/双击）
#  走这个启动器：先从 DPAPI 解封密钥注入环境，再拉起目标进程 ——
#  子进程继承环境，所以 Codex 及其派生的 codex.exe 都能拿到 DEEPSEEK_API_KEY。
#
#  用法：
#    powershell -NoProfile -ExecutionPolicy Bypass -File codex-key-launch.ps1
#    powershell ... -File codex-key-launch.ps1 -Target "C:\path\app.exe" -Args "-x"
# =============================================================================
[CmdletBinding()]
param(
    [string]$Target = '',
    [string[]]$Args = @()
)

$ErrorActionPreference = 'Stop'
$here = Split-Path -Parent $MyInvocation.MyCommand.Path

. (Join-Path $here 'codex_key_env.ps1')

if (-not $env:DEEPSEEK_API_KEY) {
    Write-Warning '未取得密钥，仍将启动目标进程（Codex 可能会报缺 key）'
}

if (-not $Target) {
    $cli = 'C:\Users\ADMIN\AppData\Local\OpenAI\Codex\bin\12219cbfbcbddde7\codex.exe'
    if (Test-Path -LiteralPath $cli) { $Target = $cli }
}

if (-not $Target -or -not (Test-Path -LiteralPath $Target)) {
    throw "找不到启动目标：$Target（用 -Target 显式指定）"
}

Start-Process -FilePath $Target -ArgumentList $Args -WorkingDirectory (Get-Location).Path

Write-Host "[codex-key-launch] 已启动：$Target（密钥来源：DPAPI 保险箱）"
