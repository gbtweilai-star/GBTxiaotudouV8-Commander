# =============================================================================
#  install_codex_key_env.ps1 — 把 DPAPI 密钥注入挂到所有 PowerShell 会话启动点
# -----------------------------------------------------------------------------
#  为什么是 profile 而不是 HKCU\Environment：
#    注册表明文等于把 Key 摆在桌面上；profile 里只放"去哪儿取"，
#    真正的密钥每次会话启动时从 DPAPI 现场解封，落盘的永远只有密文。
#
#  覆盖范围：Windows PowerShell 5.1 + PowerShell 7 两个 profile。
#  （图形入口请用 codex-key-launch.ps1 包一层，见同目录文件头说明。）
#
#  用法：
#    powershell -File gbt_allinone\deploy\install_codex_key_env.ps1
#    ... -DryRun      # 只打印将要写入的内容
#    ... -Uninstall   # 移除注入块（两份 profile 都清）
# =============================================================================
[CmdletBinding()]
param(
    [switch]$DryRun,
    [switch]$Uninstall
)

$ErrorActionPreference = 'Stop'

$Marker  = 'GBT DeepSeek key injection'
$Inject  = 'C:\Users\ADMIN\Desktop\GBT小土豆V8\gbt_allinone\deploy\codex_key_env.ps1'
$Profiles = @(
    'C:\Users\ADMIN\Documents\WindowsPowerShell\Microsoft.PowerShell_profile.ps1',
    'C:\Users\ADMIN\Documents\PowerShell\Microsoft.PowerShell_profile.ps1'
)

$Begin = "# >>> $Marker >>>"
$End   = "# <<< $Marker <<<"

$Block = @"
$Begin
# 从 DPAPI 保险箱解封 DeepSeek 密钥并注入当前会话（明文不落盘）
`$__gbtKeyEnv = '$Inject'
if (Test-Path -LiteralPath `$__gbtKeyEnv) { . `$__gbtKeyEnv }
Remove-Variable __gbtKeyEnv -ErrorAction SilentlyContinue
$End
"@

function Strip([string]$text) {
    $pattern = '(?ms)^' + [regex]::Escape($Begin) + '.*?^' + [regex]::Escape($End) + '\r?\n?'
    return [regex]::Replace($text, $pattern, '')
}

foreach ($path in $Profiles) {
    $dir = Split-Path -Parent $path
    if (-not (Test-Path -LiteralPath $dir)) {
        Write-Host "[key-env] 跳过（目录不存在）：$dir"
        continue
    }
    $exists = Test-Path -LiteralPath $path
    $text = if ($exists) { [IO.File]::ReadAllText($path) } else { '' }
    $cleaned = Strip $text

    if ($Uninstall) {
        if ($DryRun) { Write-Host "[key-env] [DryRun] 移除注入块：$path"; continue }
        [IO.File]::WriteAllText($path, $cleaned, (New-Object Text.UTF8Encoding($true)))
        Write-Host "[key-env] 已移除注入块：$path"
        continue
    }

    $new = $cleaned.TrimEnd() + "`r`n`r`n" + $Block + "`r`n"
    if ($DryRun) {
        Write-Host "[key-env] [DryRun] 将写入：$path"
        Write-Host $Block
        continue
    }

    if ($exists) {
        $backup = "$path.pre-keyenv-$(Get-Date -Format yyyyMMdd-HHmmss)"
        Copy-Item -LiteralPath $path -Destination $backup -Force
        Write-Host "[key-env] 已备份原 profile：$backup"
    }
    [IO.File]::WriteAllText($path, $new, (New-Object Text.UTF8Encoding($true)))
    Write-Host "[key-env] 已写入注入块：$path"
}

if (-not $Uninstall -and -not $DryRun) {
    Write-Host "[key-env] 验证：另起一个 PowerShell 会话（会加载 profile），只打印掩码"
    # 用临时脚本探针而不是 -Command 字符串：引号经过两层 PowerShell 会被吃掉
    $probeFile = Join-Path $env:TEMP ("gbt_keyenv_probe_$(Get-Date -Format yyyyMMddHHmmss).ps1")
    $probeBody = @'
if ($env:DEEPSEEK_API_KEY) {
    "session key: " + $env:DEEPSEEK_API_KEY.Substring(0,5) + "****"
} else {
    "session key: (none)"
}
'@
    [IO.File]::WriteAllText($probeFile, $probeBody, (New-Object Text.UTF8Encoding($true)))
    & powershell -ExecutionPolicy Bypass -File $probeFile
    Remove-Item -LiteralPath $probeFile -Force -ErrorAction SilentlyContinue
}
