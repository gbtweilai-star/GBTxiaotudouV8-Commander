# Fix our-free-model combos: replace the dead opencode bare ids with the
# Kilo-lane models that actually answer.
#
# Why this is needed: the plugin ships combo defaults pointing at opencode
# bare ids (`nemotron-3.5-super-vl-free`, `big-pickle`, ...). That lane is a
# shared free quota and keeps returning HTTP 429 "Free usage limit reached".
# A combo request then burns five candidates per retry and the turn dies.
# Measured on this machine 2026-11-08:
#     bare ids   97-100% failure
#     kilo lane   0-4% failure
#
# Usage:
#   .\fix-free-combo.ps1              # rewrite combos only
#   .\fix-free-combo.ps1 -Restart     # rewrite combos, then restart DSH
#
# The plugin keeps settings in memory and flushes that copy back to disk, so a
# disk edit alone gets overwritten. A restart (or the settings page's "hot
# reload plugin" button) re-reads the file.

param(
    [switch]$Restart,
    [switch]$Quiet
)

$ErrorActionPreference = 'Stop'
$settings = Join-Path $env:USERPROFILE '.dsh\our-free-model\settings.json'

if (-not (Test-Path -LiteralPath $settings)) {
    Write-Host "settings.json not found: $settings" -ForegroundColor Red
    exit 1
}

# Kilo lane, ordered by measured reliability.
$stable = @(
    'dots-studio/dots-3-note-preview:free',
    'openrouter/free',
    'nvidia/nemotron-3.5-lightning:free',
    'nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free',
    'nvidia/nemotron-3.5-super-vl:free',
    'cohere/north-mini-code:free',
    'reflection/beam-free',
    'nvidia/nemotron-3-ultra-550b-a55b:free',
    'kilo-auto/free'
)

# Large-context chain, ordered by real context window from the plugin catalog:
# beam-free 1M, nemotron-3.5-super-vl 1M, lightning 1M, ultra 1M,
# dots-studio 512K, openrouter 200K, kilo-auto 256K.
$big = @(
    'reflection/beam-free',
    'nvidia/nemotron-3.5-super-vl:free',
    'nvidia/nemotron-3.5-lightning:free',
    'nvidia/nemotron-3-ultra-550b-a55b:free',
    'dots-studio/dots-3-note-preview:free',
    'openrouter/free',
    'kilo-auto/free'
)

$stamp = Get-Date -Format 'yyyyMMddHHmmss'
$backup = "$settings.bak-fixcombo-$stamp"
$raw = [System.IO.File]::ReadAllText($settings, [System.Text.Encoding]::UTF8)
[System.IO.File]::WriteAllText($backup, $raw, (New-Object System.Text.UTF8Encoding($false)))
if (-not $Quiet) { Write-Host "backup: $backup" }

$doc = $raw | ConvertFrom-Json
foreach ($combo in $doc.combos) {
    if ($combo.id -eq 'combo:recommended-free') { $combo.models = $stable }
    elseif ($combo.id -eq 'combo:big-window-free') { $combo.models = $big }
}

[System.IO.File]::WriteAllText(
    $settings,
    ($doc | ConvertTo-Json -Depth 20),
    (New-Object System.Text.UTF8Encoding($false))
)

# Read back and verify, never trust the write.
# A dead bare id has no provider prefix (no '/'), e.g. `big-pickle`.
# Kilo-lane ids always look like `org/model` or `org/model:free`.
$check = [System.IO.File]::ReadAllText($settings, [System.Text.Encoding]::UTF8) | ConvertFrom-Json
$bad = 0
foreach ($combo in $check.combos) {
    $bare = @($combo.models | Where-Object { $_ -notmatch '/' })
    if ($bare.Count -gt 0) {
        $bad += $bare.Count
        Write-Host ("  {0}: still has bare id(s): {1}" -f $combo.id, ($bare -join ', ')) -ForegroundColor Yellow
    }
    if (-not $Quiet) {
        Write-Host ("  {0}  ->  {1} models" -f $combo.id, $combo.models.Count) -ForegroundColor Green
    }
}
if ($bad -gt 0) {
    Write-Host "WARNING: $bad dead bare id(s) still present" -ForegroundColor Yellow
    exit 1
}
if (-not $Quiet) {
    Write-Host ''
    Write-Host 'Combos rewritten. The plugin still holds the old list in memory.' -ForegroundColor Cyan
    Write-Host 'To apply: settings page -> "hot reload plugin", or run this with -Restart.' -ForegroundColor Cyan
}

if (-not $Restart) { exit 0 }

# Restart detached through WMI so this script survives killing its own host.
Write-Host 'Restarting DeepSeek Harness in 5s...' -ForegroundColor Yellow
$log = Join-Path $env:USERPROFILE '.dsh\restart-dsh.log'
$exe = Join-Path $env:LOCALAPPDATA 'Programs\DeepSeek Harness\DeepSeek Harness.exe'
if (-not (Test-Path -LiteralPath $exe)) {
    Write-Host "exe not found: $exe" -ForegroundColor Red
    exit 1
}
$inner = @"
Start-Sleep -Seconds 5
Get-Process -Name 'DeepSeek Harness' -ErrorAction SilentlyContinue | Stop-Process -Force
Start-Sleep -Seconds 6
Start-Process -FilePath '$exe'
"@
$enc = [Convert]::ToBase64String([System.Text.Encoding]::Unicode.GetBytes($inner))
Invoke-CimMethod -ClassName Win32_Process -MethodName Create -Arguments @{
    CommandLine = "powershell.exe -NoProfile -WindowStyle Hidden -EncodedCommand $enc"
} | Out-Null
"[$(Get-Date -Format o)] fix-free-combo restart issued" | Out-File -FilePath $log -Append -Encoding utf8
Write-Host 'Restart issued. The app will come back in about 15 seconds.' -ForegroundColor Green
