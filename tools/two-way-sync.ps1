# gbt-capability: two-way-sync
# 开发者：自由的风 · 永久钢印 · 禁止删除
<#
two-way-sync.ps1 — 交付树 ↔ live 工作仓 双向同步（执行器）
计划/校验/注册表插入/刷新链由 Python 计划器做（tools\codex-scripts\two-way-sync.py）；
本脚本负责文件复制 + 备份 + 静默窗口守卫（Windows 上 PowerShell 能写 Desktop，Python 不行）。

用法（在 live 仓根或任意目录）：
  powershell -NoProfile -ExecutionPolicy Bypass -File tools\two-way-sync.ps1 status
  powershell ... -File tools\two-way-sync.ps1 plan-pull
  powershell ... -File tools\two-way-sync.ps1 pull -Apply
  powershell ... -File tools\two-way-sync.ps1 push -Apply -Refresh
  powershell ... -File tools\two-way-sync.ps1 verify

参数：
  -Live <path>       live 仓根（默认：当前目录有 gbt_allinone 则用之，否则脚本上两级）
  -Delivery <path>   交付树（默认 $env:GBT_DELIVERY 或 ~\Desktop\GBT小土豆V8）
  -Apply             真写盘；不加只预览
  -Force             push 时跳过"静默 60 秒"守卫
  -Refresh           push 后跑 live 刷新链（export/docs/bindings/audit/authz）
#>
param(
    [ValidateSet('status', 'plan-pull', 'plan-push', 'pull', 'push', 'verify')]
    [string]$Mode = 'status',
    [string]$Live = '',
    [string]$Delivery = '',
    [switch]$Apply,
    [switch]$Force,
    [switch]$Refresh
)

$ErrorActionPreference = 'Stop'

function Resolve-Live {
    param([string]$p)
    if ($p) { return (Resolve-Path -LiteralPath $p).Path }
    if (Test-Path -LiteralPath (Join-Path (Get-Location) 'gbt_allinone')) { return (Get-Location).Path }
    return (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..\..')).Path
}

function Find-Py {
    param([string]$liveRoot)
    $ws = Split-Path -Parent $liveRoot
    $cand = Join-Path $ws 'pyembed\python.exe'
    if (Test-Path -LiteralPath $cand) { return $cand }
    return 'py'
}

$LiveRoot = Resolve-Live $Live
if (-not $Delivery) {
    if ($env:GBT_DELIVERY) { $Delivery = $env:GBT_DELIVERY }
    else { $Delivery = Join-Path $env:USERPROFILE 'Desktop\GBT小土豆V8' }
}
if (-not (Test-Path -LiteralPath $Delivery)) { throw "交付树不存在：$Delivery（用 -Delivery 指定，或设 GBT_DELIVERY）" }
$Delivery = (Resolve-Path -LiteralPath $Delivery).Path
$Py = Find-Py $LiveRoot
$Planner = Join-Path $LiveRoot 'tools\codex-scripts\two-way-sync.py'
if (-not (Test-Path -LiteralPath $Planner)) { $Planner = Join-Path $PSScriptRoot 'codex-scripts\two-way-sync.py' }
if (-not (Test-Path -LiteralPath $Planner)) { throw "计划器缺失：$Planner" }

function Invoke-Planner {
    param([string]$op)
    $out = & $Py -B -X utf8 $Planner $op --live $LiveRoot --delivery $Delivery --json 2>&1
    $txt = ($out | Out-String).Trim()
    try { return ($txt | ConvertFrom-Json) }
    catch { throw "计划器输出不是 JSON（$op）：`n$txt" }
}

function Show-Plan {
    param($plan, [string]$head)
    $files = @($plan.copy)
    Write-Host ("{0}：{1} 个文件" -f $head, $files.Count)
    $files | Select-Object -First 40 | ForEach-Object { Write-Host ("  " + $_) }
    if ($files.Count -gt 40) { Write-Host ("  ... 共 {0} 个" -f $files.Count) }
}

function Backup-Copy {
    param([string]$srcRepo, [string]$dstRepo, [string]$rel, [string]$stamp, [string]$tag)
    $src = Join-Path $srcRepo ($rel -replace '/', '\')
    $dst = Join-Path $dstRepo ($rel -replace '/', '\')
    if (-not (Test-Path -LiteralPath $src)) { return $false }
    if (Test-Path -LiteralPath $dst) {
        $bk = Join-Path $LiveRoot ("state\sync-backup\{0}-{1}\{2}" -f $stamp, $tag, ($rel -replace '/', '\'))
        New-Item -ItemType Directory -Force -Path (Split-Path -Parent $bk) | Out-Null
        Copy-Item -LiteralPath $dst -Destination $bk -Force
        # newer-wins（2026-11-01 主人令）：**目标比源新 >5s 就不覆盖**。
        # 注意：`-Force` 不再能绕过这一条（外部自动化就是拿 -Force 把新改动打回的）；
        # 真要覆盖更新的一侧，必须显式 -ForceOverwrite。
        $si = Get-Item -LiteralPath $src
        $di = Get-Item -LiteralPath $dst
        if ($di.LastWriteTimeUtc -gt $si.LastWriteTimeUtc.AddSeconds(5)) {
            if (-not $ForceOverwrite) {
                Write-Host ("  跳过（目标更新，拒绝旧覆盖新）：" + $rel)
                return $false
            }
        }
    }
    New-Item -ItemType Directory -Force -Path (Split-Path -Parent $dst) | Out-Null
    Copy-Item -LiteralPath $src -Destination $dst -Force
    return $true
}

$stamp = Get-Date -Format 'yyyyMMdd-HHmmss'

switch ($Mode) {
    'status' {
        $st = Invoke-Planner 'status'
        Write-Host ("live caps={0} / delivery caps={1}" -f $st.live_caps, $st.delivery_caps)
        Write-Host ("source files: live={0} delivery={1} | only_live={2} only_delivery={3} differ={4} quiet={5}s" -f `
            $st.live_files, $st.delivery_files, @($st.only_live).Count, @($st.only_delivery).Count, @($st.differ).Count, $st.quiet_age_s)
        Write-Host ("verdict: {0}" -f $st.verdict)
        @($st.only_delivery) | Select-Object -First 15 | ForEach-Object { Write-Host ("  - " + $_) }
        @($st.only_live) | Select-Object -First 15 | ForEach-Object { Write-Host ("  + " + $_) }
        @($st.differ) | Select-Object -First 15 | ForEach-Object { Write-Host ("  ~ " + $_) }
    }
    'plan-pull' {
        Show-Plan (Invoke-Planner 'plan-pull') '拉取计划（live → delivery）'
    }
    'plan-push' {
        Show-Plan (Invoke-Planner 'plan-push') '推送计划（delivery → live）'
    }
    'pull' {
        $plan = Invoke-Planner 'plan-pull'
        Show-Plan $plan '拉取计划（live → delivery）'
        if (-not $Apply) { Write-Host '  （预览；加 -Apply 才写盘）'; break }
        $n = 0
        foreach ($rel in @($plan.copy)) {
            if (Backup-Copy $LiveRoot $Delivery $rel $stamp 'pull') { $n++ }
        }
        Write-Host ("已拉取 {0} 个文件；旧版备份在 live\state\sync-backup\{1}-pull\" -f $n, $stamp)
        Write-Host '提示：交付树刷新链请在 PowerShell 里跑（脚本已能从 live 刷新）；然后 verify。'
    }
    'push' {
        $st = Invoke-Planner 'status'
        if ((-not $Force) -and ([double]$st.quiet_age_s -ge 0) -and ([double]$st.quiet_age_s -lt 60)) {
            throw ("live 最近 {0:N0}s 内仍有源码写入 ⇒ 拒绝推送（防并发覆盖）。确认可推时加 -Force。" -f $st.quiet_age_s)
        }
        $plan = Invoke-Planner 'plan-push'
        Show-Plan $plan '推送计划（delivery → live）'
        if (-not $Apply) { Write-Host '  （预览；加 -Apply 才写盘）'; break }
        $n = 0
        foreach ($rel in @($plan.copy)) {
            if (Backup-Copy $Delivery $LiveRoot $rel $stamp 'push') { $n++ }
        }
        Write-Host ("已推送 {0} 个文件；旧版备份在 live\state\sync-backup\{1}-push\" -f $n, $stamp)
        $capsOut = & $Py -B -X utf8 $Planner apply-push-caps --live $LiveRoot --delivery $Delivery 2>&1
        Write-Host ("caps 插入：{0}" -f (($capsOut | Out-String).Trim()))
        if ($Refresh) {
            Write-Host '跑 live 刷新链（export/docs/bindings/audit/authz）...'
            $ref = & $Py -B -X utf8 $Planner refresh --live $LiveRoot --delivery $Delivery 2>&1
            Write-Host (($ref | Out-String).Trim())
        }
        $v = Invoke-Planner 'verify'
        Write-Host ("verify: {0}（live caps={1} delivery caps={2}）" -f $v.verdict, $v.live_caps, $v.delivery_caps)
        if ($v.verdict -ne 'ALIGNED') { exit 1 }
    }
    'verify' {
        $v = Invoke-Planner 'verify'
        Write-Host ("verify: {0} | live caps={1} / delivery caps={2} | only_live={3} only_delivery={4} differ={5}" -f `
            $v.verdict, $v.live_caps, $v.delivery_caps, @($v.only_live).Count, @($v.only_delivery).Count, @($v.differ).Count)
        if ($v.verdict -ne 'ALIGNED') {
            @($v.only_live) | Select-Object -First 20 | ForEach-Object { Write-Host ("  + " + $_) }
            @($v.differ) | Select-Object -First 20 | ForEach-Object { Write-Host ("  ~ " + $_) }
            exit 1
        }
    }
}
