# ComfyUI 本地服务 · 起停件（CPU 路线）
#
# 口径（写死）：
#   · **只监听回环** `127.0.0.1`，不开外网面 —— 本机自用，不对外暴露。
#   · `--cpu`：本机无 CUDA（AMD RX 6500M），必须显式走 CPU，否则 torch 会去摸不存在的 CUDA
#     并抛一堆看不懂的错。
#   · 日志落 `~/ComfyUI/comfy.log`，PID 落 `~/ComfyUI/comfy.pid` ⇒ **可查、可停**，
#     不靠"我记着它开着"。
#
# 用法：
#   pwsh -File tools/codex-scripts/comfy-serve.ps1            # 起（已在跑就只报读数）
#   pwsh -File tools/codex-scripts/comfy-serve.ps1 -Status    # 只看状态
#   pwsh -File tools/codex-scripts/comfy-serve.ps1 -Stop      # 停
param(
  [string]$Root = "$env:USERPROFILE\ComfyUI",
  [int]$Port = 8188,
  [switch]$Stop,
  [switch]$Status
)
$ErrorActionPreference = "Continue"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$log = Join-Path $Root "comfy.log"
$pidFile = Join-Path $Root "comfy.pid"
$vpy = Join-Path $Root ".venv\Scripts\python.exe"

function Running {
  if (-not (Test-Path $pidFile)) { return $null }
  $p = Get-Content $pidFile -ErrorAction SilentlyContinue | Select-Object -First 1
  if (-not $p) { return $null }
  $proc = Get-Process -Id $p -ErrorAction SilentlyContinue
  if ($proc) { return $proc } else { return $null }
}

function Probe {
  try {
    $r = Invoke-WebRequest -UseBasicParsing -TimeoutSec 4 "http://127.0.0.1:$Port/system_stats"
    return ($r.Content | ConvertFrom-Json)
  } catch { return $null }
}

$proc = Running
$stats = Probe

if ($Stop) {
  if ($proc) { Stop-Process -Id $proc.Id -Force; Remove-Item $pidFile -Force -ErrorAction SilentlyContinue
               "已停：PID $($proc.Id)" } else { "没在跑（pid 文件里没有活进程）" }
  exit 0
}

if ($Status -or $proc) {
  if (-not $proc) { "状态：没在跑"; exit 1 }
  "状态：在跑（PID $($proc.Id)）"
  if ($stats) {
    "  HTTP 127.0.0.1:$Port 通"
    "  设备：$($stats.devices -join ', ')"
    "  torch：$($stats.system.comfyui_version) · python $($stats.system.python_version -replace 'None','')"
  } else { "  HTTP 不通（进程在但服务没起来 —— 看 $log 末尾）" }
  if (Test-Path $log) { "  日志末尾："; Get-Content $log -Tail 4 | ForEach-Object { "    $_" } }
  exit 0
}

if (-not (Test-Path $vpy)) { "❌ venv 不在：先跑 comfy-install.ps1"; exit 2 }

"起服务：$vpy main.py --cpu --listen 127.0.0.1 --port $Port"
$p = Start-Process -FilePath $vpy `
  -ArgumentList @("main.py", "--cpu", "--listen", "127.0.0.1", "--port", "$Port") `
  -WorkingDirectory $Root -RedirectStandardOutput $log -RedirectStandardError (Join-Path $Root "comfy.err.log") `
  -PassThru -WindowStyle Hidden
$p.Id | Set-Content -Path $pidFile -Encoding ascii
"PID $($p.Id) · 等它就绪（最多 90 秒）…"

for ($i = 1; $i -le 30; $i++) {
  Start-Sleep -Seconds 3
  $s = Probe
  if ($s) { "✅ 就绪（第 $($i * 3) 秒）：设备 $($s.devices -join ', ')"; exit 0 }
  if ($p.HasExited) { "❌ 进程退了（exit $($p.ExitCode)）—— 日志末尾："
                      Get-Content $log -Tail 12 | ForEach-Object { "   $_" }; exit 3 }
}
"⚠️ 90 秒没就绪，但进程还在（PID $($p.Id)）—— 日志末尾："
Get-Content $log -Tail 12 | ForEach-Object { "   $_" }
exit 4
