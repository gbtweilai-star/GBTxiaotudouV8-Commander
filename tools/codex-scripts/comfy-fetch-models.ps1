# 取 Stable Diffusion「OpenPose + LoRA」组合技所需的三件真身（可复现 · 带 sha256 验真）
#
# ## 为什么不能只下"随便一个 LoRA 和 ControlNet"
# 主人 2026-09-23 的原话是「抓取 Stable Diffusion 超强插件组合技 OpenPose+Lora，
# 把这两个的专业化能力学会并且跑通闭环，做自己的逼真数字人」。
# 本机现读（那天实测）：
#   · ComfyUI 0.37.0 在 `$env:USERPROFILE\ComfyUI`，venv python 3.12.10 / **torch 2.14.0+cpu**（无 CUDA）
#   · 全机模型**只有一个 SD1.5 fp16**；`models\controlnet` 与 `models\loras` **只有占位文件**
#   · `custom_nodes` 只有示例 ⇒ 没有 ControlNet 预处理器、没有 Manager
#   · 磁盘可用 40.5 GB（够）· 内存 总 7.4 GB / **可用 0.33 GB**（这是真天花板）
# ⇒ 三件缺一不可，且**底模必须换成逼真底模**：
#   原版 `v1-5-pruned-emaonly` 出的是"插画脸"，加了 OpenPose+LoRA 也还是插画脸
#   —— 想"逼真数字人"，先要有出真人的底模。
#
# ## 三件真身（体积与 sha256 都是从 HuggingFace LFS 元数据现读的，不是我编的）
#   ① 逼真底模   SG161222/Realistic_Vision_V5.1_noVAE · fp16-no-ema · 1.99 GiB
#   ② OpenPose   webui/ControlNet-modules-safetensors · control_openpose-fp16 · 689 MiB
#   ③ LoRA       latent-consistency/lcm-lora-sdv1-5 · 128 MiB
#
# ## 🔴 关于 ③ 的口径（不许含糊）
#   LCM-LoRA 是**速度/一致性** LoRA，**不是身份 LoRA**。选它是因为本机**算力是瓶颈**：
#   它让 SD1.5 从 20 步降到 4-8 步 ⇒ 在 CPU 上把 586 秒/张 压到约 1/4。
#   **要做"你自己那张脸"，必须有在你自己照片上训练出来的身份 LoRA** ——
#   而这件事**在本机不可行**（CPU · 7.4 GB 内存 · 无 CUDA），只有云上训或换机器。
#   本脚本只解决"把路铺好"，不假装已经把身份 LoRA 训好了。
#
# ## 用法
#   pwsh -File tools/codex-scripts/comfy-fetch-models.ps1 -List      # 只看缺什么、多大
#   pwsh -File tools/codex-scripts/comfy-fetch-models.ps1            # 取齐三件（带 sha256 验真）
#   pwsh -File tools/codex-scripts/comfy-fetch-models.ps1 -What lora # 只取一件
#
# 退出码：0 全部到位并验真通过 · 2 有文件没到位/验真失败 · 3 找不到 ComfyUI
param(
  [ValidateSet('all', 'checkpoint', 'controlnet', 'lora')]
  [string]$What = 'all',
  [switch]$List,
  [switch]$Force            # 已存在也重下
)
$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

$COMFY = Join-Path $env:USERPROFILE 'ComfyUI'
if (-not (Test-Path $COMFY)) { "❗找不到 ComfyUI：$COMFY"; exit 3 }

# 三件真身：url / 落点 / 期望字节 / 期望 sha256（HF 的 LFS oid 就是文件 sha256）
$MODELS = @(
  [pscustomobject]@{
    Key = 'checkpoint'; Name = '逼真底模 Realistic Vision V5.1 (fp16-no-ema)'
    Url = 'https://huggingface.co/SG161222/Realistic_Vision_V5.1_noVAE/resolve/main/Realistic_Vision_V5.1_fp16-no-ema.safetensors'
    Dest = Join-Path $COMFY 'models\checkpoints\Realistic_Vision_V5.1_fp16-no-ema.safetensors'
    Bytes = 2132625894
    Sha256 = '99a75a901f4fec732056930a89fa34cf360f6f72d75ce5bf333ddf82adf8dd2a'
  }
  [pscustomobject]@{
    Key = 'controlnet'; Name = 'ControlNet OpenPose (fp16)'
    Url = 'https://huggingface.co/webui/ControlNet-modules-safetensors/resolve/main/control_openpose-fp16.safetensors'
    Dest = Join-Path $COMFY 'models\controlnet\control_openpose-fp16.safetensors'
    Bytes = 722596338
    Sha256 = '337a30c5636697704370bd2413b43cebf1937abcdccc96f3525018ad5c220702'
  }
  [pscustomobject]@{
    Key = 'lora'; Name = 'LoRA LCM-SD1.5（速度/一致性，非身份）'
    Url = 'https://huggingface.co/latent-consistency/lcm-lora-sdv1-5/resolve/main/pytorch_lora_weights.safetensors'
    Dest = Join-Path $COMFY 'models\loras\lcm-lora-sdv1-5.safetensors'
    Bytes = 134621556
    Sha256 = '8f90d840e075ff588a58e22c6586e2ae9a6f7922996ee6649a7f01072333afe4'
  }
)

function Get-State($m) {
  if (-not (Test-Path $m.Dest)) { return 'missing' }
  $len = (Get-Item $m.Dest).Length
  if ($len -ne $m.Bytes) { return "size_mismatch($len/$($m.Bytes))" }
  return 'present'
}

if ($What -eq 'all') { $todo = $MODELS } else { $todo = $MODELS | Where-Object { $_.Key -eq $What } }

"== 目标：$COMFY =="
"== 三件真身现状 =="
foreach ($m in $MODELS) {
  "  {0,-12} {1,-46} {2,14:N0} B  {3}" -f $m.Key, $m.Name, $m.Bytes, (Get-State $m)
}
$need = ($MODELS | Where-Object { (Get-State $_) -ne 'present' })
$needBytes = ($need | Measure-Object Bytes -Sum).Sum
"  待取：{0} 件 · 合计 {1:N2} GiB" -f $need.Count, ($needBytes / 1GB)
if ($List) { exit 0 }

$fail = 0
foreach ($m in $todo) {
  if ((Get-State $m) -eq 'present' -and -not $Force) { "跳过（已到位）：$($m.Name)"; continue }
  $dir = Split-Path $m.Dest -Parent
  if (-not (Test-Path $dir)) { New-Item -ItemType Directory -Path $dir -Force | Out-Null }
  "下载 $($m.Name)  ->  $(Split-Path $m.Dest -Leaf)"
  $t0 = Get-Date
  # --fail：HTTP 错误码不许当成功；-C -：断点续传；--retry：网络抖动不重头来
  & curl.exe -L --fail --retry 3 --retry-delay 3 -C - -o $m.Dest $m.Url
  if ($LASTEXITCODE -ne 0) { "  ❌ curl 退出码 $LASTEXITCODE"; $fail++; continue }
  $secs = ((Get-Date) - $t0).TotalSeconds
  $len = (Get-Item $m.Dest).Length
  $sha = (Get-FileHash -Algorithm SHA256 -Path $m.Dest).Hash.ToLower()
  $okLen = ($len -eq $m.Bytes)
  $okSha = ($sha -eq $m.Sha256)
  "  用时 {0:N0}s · {1:N0} B（期望 {2:N0}）· sha256 {3}" -f $secs, $len, $m.Bytes, $(if ($okSha) { '✅ 逐字节对上' } else { "❌ 不符：$sha" })
  if (-not $okLen) { "  ❌ 长度不符"; $fail++ }
  if (-not $okSha) { "  ❌ sha256 不符 —— 文件可能被截断或换过，**不许当成品用**"; $fail++ }
}

"== 收口 =="
foreach ($m in $MODELS) { "  {0,-12} {1}" -f $m.Key, (Get-State $m) }
if ($fail -gt 0) { "❌ 有 $fail 处没到位/没验真 —— 不许往下跑图"; exit 2 }
"✅ 三件全部到位且 sha256 逐字节对上"
exit 0
