# gbt-capability: sync_guard
# 开发者：自由的风 · 永久钢印 · 禁止删除
<#
setup-sync-push.ps1 — 配置双仓巡检的外部推送通道（写 state/sync_push.json，计划任务也能读）
用法：
  powershell -NoProfile -ExecutionPolicy Bypass -File tools\setup-sync-push.ps1 -Webhook "https://.../hook"
  powershell ... -Feishu "https://open.feishu.cn/open-apis/bot/v2/hook/xxxx"
  powershell ... -N8n "http://127.0.0.1:5678/webhook/gbt"
  powershell ... -Test            # 用已配置的第一条发一条测试 POST
  powershell ... -Clear           # 清空（回到桌面 toast 兜底）
说明：环境变量 GBT_SYNC_PUSH_WEBHOOK / GBT_FEISHU_WEBHOOK / GBT_N8N_WEBHOOK 优先于本文件；
      URL 是凭据，只写 state/（不进源码交付、不打印全文）。
#>
param(
    [string]$Webhook = '',
    [string]$Feishu = '',
    [string]$N8n = '',
    [switch]$Clear,
    [switch]$Test,
    [string]$Repo = ''
)

$ErrorActionPreference = 'Stop'
if (-not $Repo) {
    if (Test-Path -LiteralPath (Join-Path (Get-Location) 'gbt_allinone')) { $Repo = (Get-Location).Path }
    else { $Repo = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..')).Path }
}
$Repo = (Resolve-Path -LiteralPath $Repo).Path
$state = Join-Path $Repo 'state'
$cfgPath = Join-Path $state 'sync_push.json'
New-Item -ItemType Directory -Force -Path $state | Out-Null

function Mask-Url($u) {
    if (-not $u) { return '(未配置)' }
    $s = [string]$u
    if ($s.Length -le 16) { return '***' }
    return $s.Substring(0, 8) + '…' + $s.Substring($s.Length - 4)
}

if ($Clear) {
    if (Test-Path -LiteralPath $cfgPath) { Remove-Item -LiteralPath $cfgPath -Force }
    Write-Output '已清空 state/sync_push.json（推送回到桌面 toast 兜底）'
    exit 0
}

$cfg = @{}
if (Test-Path -LiteralPath $cfgPath) {
    try { $cfg = Get-Content -LiteralPath $cfgPath -Raw -Encoding utf8 | ConvertFrom-Json -AsHashtable } catch { $cfg = @{} }
}
if (-not ($cfg -is [hashtable])) { $cfg = @{} }
if ($Webhook) { $cfg['webhook'] = $Webhook }
if ($Feishu) { $cfg['feishu'] = $Feishu }
if ($N8n) { $cfg['n8n'] = $N8n }

if ($cfg.Count -gt 0) {
    $json = $cfg | ConvertTo-Json -Depth 4
    [IO.File]::WriteAllText($cfgPath, $json + "`n", (New-Object Text.UTF8Encoding($false)))
    Write-Output ("已写入 " + $cfgPath)
} else {
    Write-Output '没有提供任何 URL；未改动。用 -Webhook/-Feishu/-N8n 指定。'
}
foreach ($k in @('webhook', 'feishu', 'n8n')) {
    Write-Output ("  {0,-8} {1}" -f $k, (Mask-Url $cfg[$k]))
}

if ($Test) {
    $target = $null; $label = $null
    foreach ($k in @('webhook', 'feishu', 'n8n')) { if ($cfg[$k]) { $label = $k; $target = $cfg[$k]; break } }
    if (-not $target) {
        $envMap = @{ webhook = 'GBT_SYNC_PUSH_WEBHOOK'; feishu = 'GBT_FEISHU_WEBHOOK'; n8n = 'GBT_N8N_WEBHOOK' }
        foreach ($k in @('webhook', 'feishu', 'n8n')) {
            if ([Environment]::GetEnvironmentVariable($envMap[$k])) { $label = $k; $target = [Environment]::GetEnvironmentVariable($envMap[$k]); break }
        }
    }
    if (-not $target) { Write-Output '没有可用通道可测（先配置或用环境变量）；桌面 toast 由巡检自动兜底。'; exit 2 }
    $payload = @{ source = 'sync_guard.setup'; text = 'GBT 双仓巡检：测试消息'; at = (Get-Date).ToString('s') }
    $body = $payload | ConvertTo-Json -Depth 4
    if ($label -eq 'feishu') { $body = @{ msg_type = 'text'; content = @{ text = 'GBT 双仓巡检：测试消息' } } | ConvertTo-Json -Depth 4 }
    try {
        $resp = Invoke-RestMethod -Method Post -Uri $target -ContentType 'application/json; charset=utf-8' -Body ([Text.Encoding]::UTF8.GetBytes($body)) -TimeoutSec 10
        Write-Output ("测试推送成功（{0}）：{1}" -f $label, (($resp | ConvertTo-Json -Compress) | Select-Object -First 1))
        exit 0
    } catch {
        Write-Output ("测试推送失败（{0}）：{1}" -f $label, $_.Exception.Message)
        exit 1
    }
}
