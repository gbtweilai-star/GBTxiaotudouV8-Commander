<#
.SYNOPSIS
  万能插（YuanbaoKit · Desktop\超级万能插）HTTP 网关调用器。

.DESCRIPTION
  为什么必须走这个脚本：
    PowerShell 5.1 的 -Body 传字符串时默认按 ISO-8859-1 编码发送，
    中文路径会变成 ???  ⇒  网关回 ENOENT（路径不存在），
    看起来像工具坏了，其实是调用方编码问题（2026-11-06 实测）。
  本脚本统一把 body 转成 UTF-8 字节再发。

  前置：网关需在跑
    node server.mjs --http 7788      # 工作目录 <万能插>\runtime

.EXAMPLE
  .\tools\ybk.ps1 -Health
  .\tools\ybk.ps1 -Tool sys.info
  .\tools\ybk.ps1 -Tool fs.list -ArgsJson '{"path":"C:\Users\Lenovo E14 Gen 5\Desktop\GBT小土豆V8"}'
  .\tools\ybk.ps1 -Tool tool.list -ArgsJson '{"detail":"summary"}'
#>
param(
  [string]$Tool,
  [string]$ArgsJson = '{}',
  [string]$Url = 'http://127.0.0.1:7788',
  [switch]$Health,
  [switch]$Raw
)

$ErrorActionPreference = 'Stop'

if ($Health) {
  $h = Invoke-RestMethod "$Url/health" -TimeoutSec 8
  if ($Raw) { $h | ConvertTo-Json -Depth 5 } else { "ok={0}  tools={1}" -f $h.ok, $h.tools }
  return
}

if (-not $Tool) {
  throw "缺 -Tool。例：-Tool fs.list -ArgsJson '{""path"":""C:\""}'（或用 -Health 探活）"
}

$body = '{"tool":"' + $Tool + '","args":' + $ArgsJson + '}'
$bytes = [System.Text.Encoding]::UTF8.GetBytes($body)
$r = Invoke-RestMethod "$Url/call" -Method Post -Body $bytes `
      -ContentType 'application/json; charset=utf-8' -TimeoutSec 60

if ($Raw) { $r | ConvertTo-Json -Depth 20 }
elseif ($null -ne $r.result) { $r.result | ConvertTo-Json -Depth 20 }
else { $r | ConvertTo-Json -Depth 20 }