# 一键无限出片 —— 一条命令：出帧 → 合成 → 校验 → 落盘（第 58 轮）
#
# ## 它把哪两半接成一条
#   ① 出帧：`genrouter.py image`（轮询池：云优先、本机兜底、每次调用硬截止、超时切腿、失败冷却）
#   ② 成片：`make-video.py`（Ken Burns + 交叉溶解 + 可选字幕/配乐 → mp4 → **ffprobe 回读校验**）
#
# ## 三条口径（写死，别含糊）
#   ① **"无限"是额度上的**：本地/云免费额度内想跑多少跑多少；**时间上受限**（本机 CPU 一张 586 秒）。
#   ② **不是"逐帧生成式视频"**：帧是真生成的，**帧间运动是 ffmpeg 算的**（推移/溶解）。
#      本机无 CUDA、内存 7.4GB ⇒ 逐帧生成式视频不做。这条不许说反。
#   ③ **出帧失败就如实回落**：云腿挂住/冷却时，回落到目录里**已有的帧**并在输出里写明原因，
#      **不假装这一轮出了新帧**。
#
# 用法：
#   pwsh -File tools/codex-scripts/gen-video.ps1 -Prompt "a golden potato robot in a neon city" -Frames 4
#   pwsh -File tools/codex-scripts/gen-video.ps1 -Prompt "..." -Frames 6 -Sec 4 -Music bgm.mp3 -Srt cap.srt
#   pwsh -File tools/codex-scripts/gen-video.ps1 -Prompt "(跳过出帧)" -SkipGen      # 只用已有帧合成
param(
  [Parameter(Mandatory = $true)][string]$Prompt,
  [int]$Frames = 4,
  [double]$Sec = 3.0,
  [int]$Fps = 30,
  [string]$Out = "render/video/one-click.mp4",
  [string]$Music = "",
  [string]$Srt = "",
  [switch]$SkipGen,
  [string]$FramesDir = "render/router"
)
$ErrorActionPreference = "Continue"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$root = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
Set-Location $root

function Line($m) { Write-Host $m }

# ── ① 出帧 ─────────────────────────────────────────────────────────────────
$files = @()
$genNote = ""
if ($SkipGen) {
  $genNote = "按 -SkipGen 跳过出帧，只用已有帧"
} else {
  Line "[1/3] 出帧：$Frames 张（轮询池，云优先、本机兜底）…"
  $raw = (python tools\codex-scripts\genrouter.py image --prompt $Prompt --n $Frames 2>&1 | Out-String)
  $i = $raw.IndexOf("{")
  if ($i -ge 0) {
    try {
      $j = $raw.Substring($i) | ConvertFrom-Json
      # 🔴 第 23 轮我自己的错：`genrouter` 的 JSON **按 status 有不同形状** ——
      #    `done` 才有 images/轮询顺序/成功/共；`no_backend`/`no_prompt` 等**没有这些键**，
      #    直接取就会得到三个空值拼成「轮询顺序 · 成功 /」，**看不出真因**。
      #    （与 five-dim 摘要器那个错同类：**不同 status 不同形状，读者必须跟着分**。）
      if ($j.status -eq "done") {
        $files = @($j.images | Where-Object { $_.ok -eq $true } | ForEach-Object { $_.file })
        $genNote = "轮询顺序 " + ($j.'轮询顺序' -join ' / ') + " · 成功 " + $j.'成功' + "/" + $j.'共'
      } else {
        $genNote = "出帧没成（status=" + $j.status + "）：" + $j.detail + " " + $j.hint
      }
    } catch { $genNote = "出帧输出解析失败：" + $_.Exception.Message }
  } else { $genNote = "出帧没吐 JSON（看 genrouter 的 stderr）" }
  Line ("      " + $genNote)
}

# 🔴 回落：云腿挂住/冷却时不装样子 —— 用目录里已有的帧，并把原因写清
if ($files.Count -eq 0) {
  $have = @(Get-ChildItem $FramesDir -File -ErrorAction SilentlyContinue |
            Where-Object { $_.Extension -match '^\.(png|jpg|jpeg|webp|bmp)$' } |
            Sort-Object Name | ForEach-Object { $_.FullName })
  if ($have.Count -eq 0) {
    Line "❌ 既没出到新帧，$FramesDir 里也没有可用帧 —— 如实报缺，不合成空片。"
    Line "   原因：$genNote"
    exit 3
  }
  $files = $have
  Line "      ⚠️ 回落：本轮**没有出到新帧**（$genNote）⇒ 用 $FramesDir 里已有的 $($have.Count) 张合成。"
}

# ── ② 合成 ─────────────────────────────────────────────────────────────────
Line "[2/3] 合成：$($files.Count) 帧 × $Sec 秒 · $Fps fps → $Out"
$mv = @("tools\codex-scripts\make-video.py", "--frames") + $files +
      @("--out", $Out, "--sec", "$Sec", "--fps", "$Fps")
if ($Music) { $mv += @("--music", $Music) }
if ($Srt) { $mv += @("--srt", $Srt) }
$mraw = (python @mv 2>&1 | Out-String)
$mi = $mraw.IndexOf("{")
if ($mi -lt 0) { Line "❌ 合成没吐 JSON："; Line $mraw; exit 4 }
$mj = $mraw.Substring($mi) | ConvertFrom-Json

# ── ③ 校验与播报（读的是 ffprobe 回读值，不是"我以为"）─────────────────────
Line "[3/3] 校验（ffprobe 回读）"
if ($mj.ok -ne $true) {
  Line "❌ 合成/校验未过：$($mj.status)"
  Line ($mj | ConvertTo-Json -Depth 6)
  exit 5
}
$p = $mj.ffprobe
Line ("      ✅ " + $mj.out)
Line ("         时长 " + $p.dur + "s · " + $p.w + "×" + $p.h + " · " + $p.vcodec +
      " · " + $p.fps + " · " + $p.frames + " 帧 · " + [math]::Round($p.size / 1MB, 2) + " MB" +
      $(if ($p.has_audio) { " · 含音轨" } else { " · 无音轨" }))
Line "      口径：真生成的帧 + 真合成的运动（**不是**逐帧生成式视频）"
exit 0
