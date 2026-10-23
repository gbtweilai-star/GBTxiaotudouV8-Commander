# GBT小土豆V8 · 一键安装（Windows）
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$W = Join-Path $Root "state\weights"
$Gguf = Join-Path $W "gbt-v8-v82-q5_0.gguf"
$Rel = "https://github.com/gbtweilai-star/GBTxiaotudouV8-Commander/releases/download/v1.0.0"

Write-Host "== 1/4 检查 Python ==" -ForegroundColor Cyan
$py = "C:\Python312\python.exe"
if (-not (Test-Path $py)) { $py = "python" }
& $py -c "import sys; print(sys.version)" | Out-Null
if ($LASTEXITCODE -ne 0) { throw "没找到可用的 Python 3.x" }

Write-Host "== 2/4 安装依赖 ==" -ForegroundColor Cyan
& $py -m pip install --upgrade numpy "llama-cpp-python>=0.3.0" 2>&1 | Select-Object -Last 3

Write-Host "== 3/4 权重（3 片，合计 4.88 GB）==" -ForegroundColor Cyan
if (Test-Path $Gguf) {
  Write-Host "已存在 $Gguf，跳过下载"
} else {
  New-Item -ItemType Directory -Force -Path $W | Out-Null
  $parts = 1..3 | ForEach-Object { "gbt-v8-v82-q5_0.gguf.part$_" }
  foreach ($p in $parts) {
    $dst = Join-Path $W $p
    if (-not (Test-Path $dst)) { Write-Host "下载 $p …"; curl.exe -L --fail -o $dst "$Rel/$p" }
  }
  Write-Host "合并 …"
  $out = [IO.File]::Create($Gguf)
  foreach ($p in $parts) {
    $fs = [IO.File]::OpenRead((Join-Path $W $p)); $fs.CopyTo($out); $fs.Close()
  }
  $out.Close()
  foreach ($p in $parts) { Remove-Item (Join-Path $W $p) -Force }
  Write-Host "已合并 → $Gguf"
}

Write-Host "== 4/4 起服务 http://127.0.0.1:8792 ==" -ForegroundColor Cyan
& $py (Join-Path $Root "tools\model-bridge\local_llm_server.py") --model $Gguf --port 8792 --ctx 256 --threads 8
