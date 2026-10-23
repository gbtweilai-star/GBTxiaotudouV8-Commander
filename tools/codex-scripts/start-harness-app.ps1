# start-harness-app.ps1 - open the DeepSeek Harness desktop app reliably.
#
# ASCII-only on purpose: powershell.exe 5.1 reads a BOM-less .ps1 as ANSI, so non-ASCII
# literals break parsing. The install folder name has no non-ASCII parts, but keep it clean.
#
# Why this exists (measured 2026-10-18 03:36):
#   The app is single-instance and its embedded host child can linger/duplicate
#   (9 processes observed; host children started twice at 03:24 and 03:31).
#   A new launch then either hands off to a window-less instance (exit 0 = "flashes and closes")
#   or races the existing host. Clearing every instance and starting one fresh copy fixed it:
#   window visible at t+10s, 5 processes, stable through t+40s.
#
# Steps (touches no config and no user data):
#   1) a visible window exists -> relaunch (single-instance focuses it)
#   2) no window -> stop every instance (none of them owns a visible window)
#   3) launch once, wait up to 30s for a window
#   4) log to out\harness-launch.log and report honestly

$ErrorActionPreference = 'Continue'
$repo = 'C:\Users\ADMIN\Desktop\GBT小土豆V8'
$log  = Join-Path $repo 'out\harness-launch.log'
New-Item -ItemType Directory -Force -Path (Split-Path $log) | Out-Null

function Say([string]$m) {
    $line = "[{0}] {1}" -f (Get-Date -Format 'yyyy-MM-dd HH:mm:ss'), $m
    Add-Content -Path $log -Value $line -Encoding utf8
    Write-Output $line
}

Say '=== launch requested ==='

$programs = Join-Path $env:LOCALAPPDATA 'Programs'
$dir = Get-ChildItem -LiteralPath $programs -Directory -ErrorAction SilentlyContinue |
       Where-Object { $_.Name -like 'DeepSeek*' } | Select-Object -First 1
if ($null -eq $dir) { Say "FAIL app directory not found under $programs"; exit 2 }

$exe = Get-ChildItem -LiteralPath $dir.FullName -Filter '*.exe' -ErrorAction SilentlyContinue |
       Where-Object { $_.Name -notmatch '^(?i)(uninstall|unins)' } | Select-Object -First 1
if ($null -eq $exe) { Say "FAIL exe not found in $($dir.FullName)"; exit 2 }

$name = $exe.BaseName
Say ("app: {0}" -f $exe.FullName)

$procs   = @(Get-Process -Name $name -ErrorAction SilentlyContinue)
$visible = @($procs | Where-Object { $_.MainWindowHandle -ne 0 })
Say ("state: processes={0} visible={1}" -f $procs.Count, $visible.Count)

if ($visible.Count -gt 0) {
    Say 'visible window found -> focus it (no restart)'
    Start-Process -FilePath $exe.FullName | Out-Null
    exit 0
}

if ($procs.Count -gt 0) {
    $ids = ($procs | ForEach-Object { $_.Id }) -join ','
    Say ("clearing window-less instances: {0}" -f $ids)
    $procs | ForEach-Object { Stop-Process -Id $_.Id -Force -ErrorAction SilentlyContinue }
    Start-Sleep -Seconds 4
}

Say 'launching app ...'
Start-Process -FilePath $exe.FullName | Out-Null

for ($i = 0; $i -lt 30; $i++) {
    Start-Sleep -Seconds 1
    $now = @(Get-Process -Name $name -ErrorAction SilentlyContinue | Where-Object { $_.MainWindowHandle -ne 0 })
    if ($now.Count -gt 0) {
        Say ("OK window appeared: pid={0} in {1}s" -f $now[0].Id, ($i + 1))
        exit 0
    }
}

Say 'FAIL window did not appear within 30s - see out\harness-launch.log'
exit 1
