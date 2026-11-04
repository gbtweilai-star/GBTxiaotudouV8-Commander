# gbt-capability: comfyui
# 开发者：自由的风 · 永久钢印 · 禁止删除
<#
start-comfyui-local.ps1 — 启动本机 ComfyUI（CPU，127.0.0.1:8188）。
不下载模型、不联网生成；只拉起本地服务。已运行则直接返回。
#>
$ErrorActionPreference = 'Stop'
$Repo = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..')).Path
$Server = Join-Path $Repo 'vendor\ComfyUI'
$Py = Join-Path $Repo 'pyembed\python.exe'
if (-not (Test-Path (Join-Path $Server 'run_gbt.py'))) { throw "缺 ComfyUI 运行时：$Server\run_gbt.py" }
function Test-Up {
    try { $r = Invoke-WebRequest -Uri 'http://127.0.0.1:8188/' -TimeoutSec 3 -UseBasicParsing; return ($r.StatusCode -eq 200) } catch { return $false }
}
if (Test-Up) { Write-Output 'ComfyUI 已在 127.0.0.1:8188 运行'; exit 0 }
$env:TEMP = Join-Path $Repo '.scratch\lead\tmp'
$env:TMP = $env:TEMP
New-Item -ItemType Directory -Force -Path $env:TEMP | Out-Null
Start-Process -FilePath $Py -ArgumentList @('-B','-X','utf8','run_gbt.py') -WorkingDirectory $Server -WindowStyle Hidden
for ($i = 0; $i -lt 30; $i++) {
    Start-Sleep -Seconds 2
    if (Test-Up) { Write-Output 'ComfyUI 已启动：http://127.0.0.1:8188'; exit 0 }
}
throw 'ComfyUI 启动超时（看 vendor\ComfyUI 控制台/日志）'

