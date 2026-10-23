# ear-listen.ps1 — 离线中文「耳朵」：听懂一句话 → 变成一个动作名（不联网、不要密钥）
#
# 为什么用 Windows 自带识别器，而不是装 whisper/vosk：
#   ① 本机装了什么：`System.Speech` 的已安装识别器里有 **zh-CN（MS-2052-80-DESK）** —— 现读得到；
#   ② 离线、零密钥、零下载，正好合"数字人本机听得懂"这条要求；
#   ③ 命令词模式对**短指令**准得多，而我们要的恰恰是"走过来/挥挥手/坐下"这类短指令。
#   缺点如实写：它**不是通用听写**（长句自由说话会掉），所以我们同时挂一条 Dictation 兜底，
#   兜底只用来"听个大概"，动作仍以命令词命中为准。
#
# 用法（主机侧调用，给浮层/App 用）：
#   pwsh -NoProfile -File tools/digihuman/ear-listen.ps1 -Wave <某个wav> -Json
#   pwsh -NoProfile -File tools/digihuman/ear-listen.ps1 -Seconds 8 -Json      # 用默认麦克风
#
# 回执（单行 JSON，永远有 ok 与 why，不许哑失败）：
#   {"ok":true,"text":"走过来","action":"come","conf":0.87,"heard":[...],"source":"wave"}
param(
  [string]$Wave = "",
  [int]$Seconds = 8,
  [string]$Lang = "zh-CN",
  [double]$MinConf = 0.55,
  [switch]$Dictation,
  [switch]$Json
)

$ErrorActionPreference = "Stop"
function Emit($obj) {
  $s = $obj | ConvertTo-Json -Compress -Depth 5
  if ($Json) { Write-Output $s } else { Write-Output $s }
}

$ACTIONS = @{
  "走过来" = "come"; "过来" = "come"; "走近一点" = "come"; "过来吧" = "come"; "到我这里" = "come";
  # 2026-10-20 增：实测「走过来」是唯一会抖到门槛下的命令（0.479/0.491/0.591/0.597/0.659）
  # ⇒ 加两个**更独特的同义口令**，让引擎有更可能匹配高分的机会（不是降门槛）。
  "走过来这里" = "come"; "过来我这边" = "come"
  "停下" = "stop"; "别动了" = "stop"; "停" = "stop"; "站住" = "stop"
  "挥手" = "wave"; "挥挥手" = "wave"; "打个招呼" = "wave"; "说你好" = "wave"
  "坐下" = "sit"; "坐吧" = "sit"
  "站起来" = "stand"; "起来" = "stand"
  "转一圈" = "spin"; "转身" = "spin"; "转个圈" = "spin"
  "跳一下" = "jump"; "跳" = "jump"
  "点头" = "nod"; "摇头" = "shake"
  "跳舞" = "dance"; "比心" = "heart"; "鼓掌" = "clap"; "抱抱" = "hug"
}
$PHRASES = @($ACTIONS.Keys) | Sort-Object -Unique

try {
  Add-Type -AssemblyName System.Speech
} catch {
  Emit @{ ok = $false; why = "System.Speech 加载失败"; detail = $_.Exception.Message }; exit 2
}

try {
  $culture = [System.Globalization.CultureInfo]::GetCultureInfo($Lang)
  $rec = New-Object System.Speech.Recognition.SpeechRecognitionEngine($culture)

  # ① 命令词文法（主路：短指令，准）
  # 🔴 2026-10-20 实测踩坑：第一版把「命令词 + 通配符 + 自由听写」一起挂上 ⇒ 识别结果全崩
  #    （走过来→走格拉 conf=0.046 / 挥挥手→亏会上 / 坐下→这下）。真因是**两条文法互相打架**：
  #    听写那条永远能给出"更像话"的候选，引擎就拿它顶掉了命令词。⇒ 命令词单独挂，听写要显式 -Dictation 才挂。
  $choices = New-Object System.Speech.Recognition.Choices
  foreach ($p in $PHRASES) { [void]$choices.Add($p) }
  $gb = New-Object System.Speech.Recognition.GrammarBuilder
  $gb.Culture = $culture
  $gb.Append($choices)
  $cmdGrammar = New-Object System.Speech.Recognition.Grammar($gb)
  $cmdGrammar.Name = "gbt-commands"
  [void]$rec.LoadGrammar($cmdGrammar)

  if ($Dictation) {
    $dict = New-Object System.Speech.Recognition.DictationGrammar
    $dict.Name = "gbt-dictation"
    [void]$rec.LoadGrammar($dict)
  }

  $rec.MaxAlternates = 3
  $rec.InitialSilenceTimeout = [TimeSpan]::FromSeconds(2)
  $rec.BabbleTimeout = [TimeSpan]::FromSeconds(1)
  $rec.EndSilenceTimeout = [TimeSpan]::FromSeconds(0.7)
  $rec.EndSilenceTimeoutAmbiguous = [TimeSpan]::FromSeconds(1.2)

  if ($Wave) {
    if (-not (Test-Path $Wave)) { Emit @{ ok = $false; why = "wav 不在：$Wave" }; exit 3 }
    $rec.SetInputToWaveFile((Resolve-Path $Wave).Path)
  } else {
    $rec.SetInputToDefaultAudioDevice()
  }

  $heard = New-Object System.Collections.ArrayList
  $deadline = (Get-Date).AddSeconds($Seconds)
  while ((Get-Date) -lt $deadline) {
    $res = $null
    try { $res = $rec.Recognize([TimeSpan]::FromSeconds(3)) } catch { break }
    if ($null -eq $res) {
      if ($Wave) { break }        # 文件读完就结束
      continue
    }
    $txt = $res.Text
    $conf = $res.Confidence
    [void]$heard.Add(@{ text = $txt; conf = [Math]::Round([double]$conf, 3); grammar = $res.Grammar.Name })
    if ($Wave -and $heard.Count -ge 1) { continue }
  }
  $rec.Dispose()

  if ($heard.Count -eq 0) {
    Emit @{ ok = $false; why = "没听清（没有识别结果）"; source = $(if ($Wave) { "wave" } else { "mic" }); action = $null }
    exit 4
  }

  # 把听来的话对到动作：先精确包含，再取最长匹配
  $best = $null; $bestLen = 0; $bestConf = 0.0
  foreach ($h in $heard) {
    foreach ($k in $ACTIONS.Keys) {
      if ($h.text -and $h.text.Contains($k) -and $k.Length -gt $bestLen) {
        $best = $ACTIONS[$k]; $bestLen = $k.Length; $bestConf = $h.conf; $bestKey = $k
      }
    }
  }
  $top = $heard[0]
  $accepted = ($null -ne $best) -and ([double]$top.conf -ge $MinConf)
  Emit @{
    ok       = $true
    text     = $top.text
    conf     = $top.conf
    action   = $(if ($accepted) { $best } else { $null })
    matched  = $(if ($accepted) { $bestKey } else { $null })
    accepted = $accepted
    why      = $(if ($accepted) { "命中命令词" } elseif ($null -eq $best) { "没对上任何命令词" } else { "置信度 $(($top.conf)) 低于门槛 $MinConf" })
    heard    = @($heard)
    source   = $(if ($Wave) { "wave" } else { "mic" })
    lang     = $Lang
    min_conf = $MinConf
  }
  exit 0
} catch {
  Emit @{ ok = $false; why = "识别器异常"; detail = $_.Exception.Message; source = $(if ($Wave) { "wave" } else { "mic" }) }
  exit 5
}
