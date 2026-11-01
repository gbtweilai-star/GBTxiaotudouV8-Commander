# gbt-capability: drama_forge
# 开发者：自由的风 · 永久钢印 · 禁止删除
<#
stock-fetch.ps1 — 按镜取 CC 授权真实照片（Openverse API），给 drama-build 当 assets_dir。
只取 by / by-sa / cc0；每张写 credits.json（作者/许可/来源），不冒充自有素材。
用法：
  powershell -NoProfile -ExecutionPolicy Bypass -File tools\stock-fetch.ps1 `
    -QueriesFile queries.json -OutDir outputs\drama-forge\xxx\assets-stock
#>
param(
    [Parameter(Mandatory = $true)][string]$QueriesFile,
    [Parameter(Mandatory = $true)][string]$OutDir
)
$ErrorActionPreference = 'Stop'
$queries = Get-Content -LiteralPath $QueriesFile -Raw -Encoding utf8 | ConvertFrom-Json
if ($queries -is [string]) { $queries = @($queries) }
New-Item -ItemType Directory -Force -Path $OutDir | Out-Null
$credits = @()
$i = 0
foreach ($q in $queries) {
    $i++
    $name = 'shot-{0:D2}.jpg' -f $i
    $path = Join-Path $OutDir $name
    $encoded = [uri]::EscapeDataString([string]$q)
    $api = "https://api.openverse.org/v1/images/?q=$encoded&page_size=10&license=by,by-sa,cc0"
    $pick = $null
    try {
        $r = Invoke-RestMethod -Uri $api -TimeoutSec 45 -Headers @{ 'User-Agent' = 'GBT-Tianzhen/1.0 (drama stock)' }
        $pick = @($r.results) | Where-Object { $_.url -and $_.width -ge 800 -and $_.height -ge 800 } | Select-Object -First 1
    } catch {
        Write-Output ("  ⚠️ 查询失败：{0} — {1}" -f $q, $_.Exception.Message)
    }
    if ($pick) {
        try {
            Invoke-WebRequest -Uri $pick.url -OutFile $path -TimeoutSec 60 -UseBasicParsing -Headers @{ 'User-Agent' = 'Mozilla/5.0' }
            $credits += [ordered]@{ shot = $i; query = [string]$q; file = $name; url = $pick.url;
                creator = $pick.creator; license = $pick.license; license_url = $pick.license_url;
                source = $pick.foreign_landing_url; attribution = $pick.attribution }
            Write-Output ("  {0} ← {1} [{2}] {3}" -f $name, $q, $pick.license, $pick.creator)
            continue
        } catch {
            Write-Output ("  ⚠️ 下载失败：{0} — {1}" -f $q, $_.Exception.Message)
        }
    }
    # 兜底：Picsum（随机真实照片；许可标注见 credits）
    try {
        Invoke-WebRequest -Uri ("https://picsum.photos/1080/1920?random={0}" -f (100 + $i)) -OutFile $path -TimeoutSec 60 -UseBasicParsing -Headers @{ 'User-Agent' = 'Mozilla/5.0' }
        $credits += [ordered]@{ shot = $i; query = [string]$q; file = $name; url = 'https://picsum.photos/';
            creator = 'Picsum (Unsplash)'; license = 'unsplash'; license_url = 'https://unsplash.com/license'; source = 'https://picsum.photos/'; attribution = 'Picsum random photo' }
        Write-Output ("  {0} ← 兜底 Picsum（{1}）" -f $name, $q)
    } catch {
        Write-Output ("  ❌ 兜底也失败：{0}" -f $q)
    }
}
$credits | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath (Join-Path $OutDir 'credits.json') -Encoding utf8
Write-Output ("素材：{0} 张 → {1}" -f $i, $OutDir)
