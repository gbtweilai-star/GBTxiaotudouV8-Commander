# gbt-capability: sync_guard
# 开发者：自由的风 · 永久钢印 · 禁止删除
<#
sync-guard-patrol.ps1 — 双仓同步巡检（可挂 Windows 计划任务 / 项目调度）
做三件只读+台账的事：
  1) sync_guard patrol（sha1 对账）
  2) record=true  → state/sync_guard.jsonl 台账
  3) notify=true  → DRIFT 写审计 error、ALIGNED 写 ok（alerts 会读到）
退出码：ALIGNED=0，DRIFT=1（计划任务里就是"红/绿"）。
用法：
  powershell -NoProfile -ExecutionPolicy Bypass -File tools\sync-guard-patrol.ps1
#>
param([string]$Repo = '')

$ErrorActionPreference = 'Stop'
if (-not $Repo) {
    if (Test-Path -LiteralPath (Join-Path (Get-Location) 'gbt_allinone')) { $Repo = (Get-Location).Path }
    else { $Repo = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..')).Path }
}
$Repo = (Resolve-Path -LiteralPath $Repo).Path
$ws = Split-Path -Parent $Repo

$cands = @()
if ($env:GBT_PYTHON) { $cands += $env:GBT_PYTHON }
$cands += (Join-Path $Repo 'pyembed\python.exe')
$cands += (Join-Path $ws 'pyembed\python.exe')
$found = Get-ChildItem (Join-Path $env:USERPROFILE 'Documents\deepseek-harness\default-workspace\*\pyembed\python.exe') -ErrorAction SilentlyContinue | Select-Object -First 1
if ($found) { $cands += $found.FullName }
$py = ''
foreach ($c in $cands) { if ($c -and (Test-Path -LiteralPath $c)) { $py = $c; break } }
if (-not $py) { $cmd = Get-Command python -ErrorAction SilentlyContinue; if ($cmd) { $py = $cmd.Source } }
if (-not $py) { $cmd = Get-Command py -ErrorAction SilentlyContinue; if ($cmd) { $py = $cmd.Source } }
if (-not $py) { throw '找不到 python；设 GBT_PYTHON 或把 pyembed 放仓根' }

$helper = Join-Path $Repo 'tools\codex-scripts\sync-guard-run.py'
if (-not (Test-Path -LiteralPath $helper)) { throw "巡检助手缺失：$helper" }
& $py -B -X utf8 $helper $Repo --with-sched
exit $LASTEXITCODE
