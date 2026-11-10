param([int]$MainPort = 8792, [int]$BridgePort = 8791)
# GBT小土豆V8 主链路自启：llama-server(主权重) -> model_bridge(8791)
# 幂等：端口已在监听就跳过；删掉启动项里的 GBT-Bridge.vbs 即取消
$ErrorActionPreference = 'Stop'
$root = 'C:\Users\Lenovo E14 Gen 5\Desktop\GBT小土豆V8'
$logs = Join-Path $root 'state\logs'
New-Item -ItemType Directory -Force -Path $logs | Out-Null

# ---- 1) 主权重 llama-server ----
$alive = Get-NetTCPConnection -LocalPort $MainPort -State Listen -ErrorAction SilentlyContinue
if (-not $alive) {
    $exe   = Join-Path $root 'vendor\llama\llama-server.exe'
    $model = Join-Path $root 'state\weights\gbt-v8-v82-q5_0.gguf'
    $tmpl  = Join-Path $root 'vendor\llama\gbt-user-assistant.jinja'
    if (-not (Test-Path $exe))   { throw "missing $exe" }
    if (-not (Test-Path $model)) { throw "missing $model" }
    $a = @('-m',$model,'--host','127.0.0.1','--port',"$MainPort",'-c','32768','-t','12','-ngl','0','--no-webui','--alias','gbt-v8-v82-q5_0','--no-context-shift')
    if (Test-Path $tmpl) { $a += @('--chat-template-file', $tmpl) }
    $a += @('--sleep-idle-seconds','600')
    Start-Process -FilePath $exe -WorkingDirectory (Join-Path $root 'vendor\llama') -ArgumentList $a -WindowStyle Hidden `
        -RedirectStandardOutput (Join-Path $logs "main-$MainPort.out.log") `
        -RedirectStandardError  (Join-Path $logs "main-$MainPort.err.log")
}

# ---- 2) 等主权重就绪（最多 120s）----
for ($i = 0; $i -lt 40; $i++) {
    Start-Sleep -Seconds 3
    if (Get-NetTCPConnection -LocalPort $MainPort -State Listen -ErrorAction SilentlyContinue) { break }
}

# ---- 3) 桥 ----
$b = Get-NetTCPConnection -LocalPort $BridgePort -State Listen -ErrorAction SilentlyContinue
if (-not $b) {
    $py      = Join-Path $root 'pyembed\python.exe'
    $starter = Join-Path $root '_start_bridge.py'
    if (-not (Test-Path $starter)) { throw "missing $starter" }
    Start-Process -FilePath $py -ArgumentList ('"' + $starter + '"') -WorkingDirectory $root -WindowStyle Hidden
}
"done"