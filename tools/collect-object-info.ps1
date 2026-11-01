# 采集秋叶版 ComfyUI 的节点契约快照（/object_info）
#
# 为什么要有这个脚本：
#   「GBT天真 跟秋叶版一比一」要真测，必须有秋叶整包的节点清单（核心 + 插件，约 1495 把）。
#   这份清单只能在**装了秋叶版的机器上**从运行中的 ComfyUI 取。
#   取回来后放到 state/comfyui_object_info.json，`tools/comfy-parity.py` 会自动切到真快照。
#
# 用法（在秋叶版那台机器上，ComfyUI 已启动）：
#   powershell -NoProfile -ExecutionPolicy Bypass -File tools\collect-object-info.ps1
#   powershell ... -File tools\collect-object-info.ps1 -Url http://127.0.0.1:8188 -Out state\comfyui_object_info.json
#
# 只读：一个 GET，不提交、不改任何东西。

param(
  [string]$Url = "http://127.0.0.1:8188",
  [string]$Out = "state\comfyui_object_info.json",
  [int]$TimeoutSec = 60
)

$ErrorActionPreference = "Stop"
$full = Join-Path -Path (Get-Location) -ChildPath $Out
$dir = Split-Path -Parent $full
if ($dir -and -not (Test-Path $dir)) { New-Item -ItemType Directory -Force -Path $dir | Out-Null }

try {
  $r = Invoke-WebRequest -Uri "$Url/object_info" -UseBasicParsing -TimeoutSec $TimeoutSec
} catch {
  Write-Host "拉取失败：$($_.Exception.Message)" -ForegroundColor Red
  Write-Host "先确认：① 秋叶版 ComfyUI 已启动  ② 端口是 8188（或改 -Url）"
  exit 1
}

if ($r.StatusCode -ne 200) {
  Write-Host "HTTP $($r.StatusCode)" -ForegroundColor Red
  exit 1
}

# 校验：必须是 JSON 对象、且节点数像样（>100）
try {
  $obj = $r.Content | ConvertFrom-Json
} catch {
  Write-Host "返回不是 JSON：$($_.Exception.Message)" -ForegroundColor Red
  exit 1
}

$names = @($obj.PSObject.Properties.Name)
if ($names.Count -lt 100) {
  Write-Host "节点只有 $($names.Count) 个 —— 不像秋叶整包（可能只起了核心），仍照实落盘并提示" -ForegroundColor Yellow
}

[System.IO.File]::WriteAllText($full, $r.Content, (New-Object System.Text.UTF8Encoding($false)))
Write-Host "落盘：$full" -ForegroundColor Green
Write-Host "节点数：$($names.Count)"

Write-Host ""
Write-Host "下一步（回到 GBT 仓库根目录）："
Write-Host "  py -3 -X utf8 tools/comfy-parity.py"
Write-Host "它会自动切到这份真快照，输出「秋叶整包」的真实覆盖率与按类缺口。"
