# ComfyUI 本地安装件 · 官方源 · CPU 路线（主人 2026-09-23 拍板 A 方案）
#
# 为什么走这条路而不是截图里那个"终极版"：
#   截图那个是**第三方重打包**（"解压即用无审核"），来源不明、不入供应链审查 —— 不装。
#   官方 `comfyanonymous/ComfyUI`（GPL-3.0）+ 官方 Comfy-Org 模型仓，才是可追责的那条路。
#
# 为什么是 CPU：
#   本机现读 **AMD Radeon RX 6500M（无 CUDA，nvidia-smi 不存在）** ⇒ 截图里"支持 30/40/50"与本机无关。
#   所以 `torch` 走官方 **CPU 轮子**（比默认 CUDA 轮子小 2GB+，且不会装一堆用不上的 CUDA 库）。
#
# 为什么独立 venv 而不是仓的解释器：
#   本仓声明口径是 3.14.5，而 **torch 目前没有 cp314 轮子** ⇒ 用 3.12 单独建 venv，互不污染。
#
# 用法：
#   pwsh -File tools/codex-scripts/comfy-install.ps1                 # 全装（含模型）
#   pwsh -File tools/codex-scripts/comfy-install.ps1 -SkipModel      # 只装程序，先不拉模型
#
# 退出码：0=全好 · 1=克隆失败 · 2=venv 失败 · 3=依赖装失败 · 4=模型下载失败
param(
  [string]$Root = "$env:USERPROFILE\ComfyUI",
  [string]$Py = "C:\Python312\python.exe",
  [switch]$SkipModel
)
$ErrorActionPreference = "Continue"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
function Say($m) { Write-Host ("[{0}] {1}" -f (Get-Date -Format "HH:mm:ss"), $m) }

Say "目标：$Root"
Say "解释器：$Py"

# ── 1/4 克隆官方仓 ────────────────────────────────────────────────────────
if (Test-Path (Join-Path $Root ".git")) {
  Say "1/4 已存在仓，跳过克隆"
} else {
  Say "1/4 克隆官方 ComfyUI（--depth 1）…"
  git clone --depth 1 https://github.com/comfyanonymous/ComfyUI $Root 2>&1 | ForEach-Object { Say "   $_" }
  if (-not (Test-Path (Join-Path $Root "main.py"))) { Say "❌ 1/4 失败：没拿到 main.py"; exit 1 }
}
Say "1/4 ✅ $(git -C $Root rev-parse --short HEAD 2>&1)"

# ── 2/4 venv ─────────────────────────────────────────────────────────────
$venv = Join-Path $Root ".venv"
if (Test-Path (Join-Path $venv "Scripts\python.exe")) {
  Say "2/4 venv 已存在，跳过"
} else {
  Say "2/4 建 venv（3.12）…"
  & $Py -m venv $venv 2>&1 | ForEach-Object { Say "   $_" }
  if (-not (Test-Path (Join-Path $venv "Scripts\python.exe"))) { Say "❌ 2/4 失败：venv 没建起来"; exit 2 }
}
$vpy = Join-Path $venv "Scripts\python.exe"
Say "2/4 ✅ $(& $vpy --version 2>&1)"

# ── 3/4 依赖：torch 走 **CPU 轮子**，再装 ComfyUI 自己的 requirements ────────
Say "3/4 升级 pip …"
& $vpy -m pip install --upgrade pip 2>&1 | Select-Object -Last 2 | ForEach-Object { Say "   $_" }
Say "3/4 装 torch/torchvision（CPU 索引，约 250MB）…"
& $vpy -m pip install torch torchvision --index-url https://download.pytorch.org/whl/cpu 2>&1 |
  Select-Object -Last 4 | ForEach-Object { Say "   $_" }
$tv = & $vpy -c "import torch;print('torch', torch.__version__, 'cuda', torch.cuda.is_available())" 2>&1
Say "3/4 torch：$tv"
if ($tv -notmatch "torch ") { Say "❌ 3/4 失败：torch 装不上"; exit 3 }
Say "3/4 装 ComfyUI requirements …"
& $vpy -m pip install -r (Join-Path $Root "requirements.txt") 2>&1 |
  Select-Object -Last 6 | ForEach-Object { Say "   $_" }
Say "3/4 ✅ 依赖装完"

# ── 4/4 SD1.5 模型（fp16 优先，失败退到 fp32；**只下官方 Comfy-Org 仓**）────
if ($SkipModel) { Say "4/4 跳过（-SkipModel）"; Say "下一步：pwsh -File tools/codex-scripts/comfy-run.ps1"; exit 0 }
$ck = Join-Path $Root "models\checkpoints"
New-Item -ItemType Directory -Force -Path $ck | Out-Null
$want = @(
  @{ n = "v1-5-pruned-emaonly-fp16.safetensors"; u = "https://huggingface.co/Comfy-Org/stable-diffusion-v1-5-archive/resolve/main/v1-5-pruned-emaonly-fp16.safetensors"; gb = 2.1 },
  @{ n = "v1-5-pruned-emaonly.safetensors";      u = "https://huggingface.co/Comfy-Org/stable-diffusion-v1-5-archive/resolve/main/v1-5-pruned-emaonly.safetensors";      gb = 4.3 }
)
$got = $null
foreach ($m in $want) {
  $dst = Join-Path $ck $m.n
  if ((Test-Path $dst) -and ((Get-Item $dst).Length -gt 100MB)) { Say "4/4 已有 $($m.n)，跳过下载"; $got = $dst; break }
  Say "4/4 下载 $($m.n)（约 $($m.gb)GB，官方 Comfy-Org 仓）…"
  & curl.exe -L --fail --retry 2 -o $dst $m.u 2>&1 | Select-Object -Last 2 | ForEach-Object { Say "   $_" }
  if ((Test-Path $dst) -and ((Get-Item $dst).Length -gt 100MB)) {
    Say "4/4 ✅ $($m.n) $([math]::Round((Get-Item $dst).Length/1GB,2))GB"; $got = $dst; break
  }
  Say "   这个源没成，换下一个"
}
if (-not $got) { Say "❌ 4/4 失败：模型没下来（检查网络/代理，或手动放 models\checkpoints）"; exit 4 }

Say "全部就绪。下一步："
Say "  起服务： pwsh -File tools/codex-scripts/comfy-serve.ps1"
Say "  出图：   python tools/codex-scripts/comfy-run.py --prompt '…'"
exit 0
