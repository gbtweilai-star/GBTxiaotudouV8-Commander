# 主脑离线听觉 · Windows 桌面识别器（System.Speech）· 零密钥、零安装
#
# 为什么要有它：`voice` 能力位的 asr 原来只认云端 `GBT_ASR_BASE_URL/API_KEY`，
# 没配就如实报 `needs_dependency` ⇒ **「没密钥就听不见」**。而本机现读有
# `MS-2052-80-DESK（zh-CN）` 离线识别器 —— 桌面识别器 8.0，Windows 自带。
# 这条腿补上之后，"大脑执行层自动监听"才不需要任何密钥。
#
# ── 两条输入通道（第 59 轮加的第二条，因为第一条在本机是死的）──────────────────
#   ① 设备直连： `SetInputToDefaultAudioDevice()` —— **底层是旧版 waveIn 映射器**。
#      本机现读 `waveInGetNumDevs() = 0` ⇒ 这条**永远**抛 "Cannot find the requested
#      data item"。⚠️ 这跟插不插麦克风无关，也**不是**"设了默认设备就能通"：
#      权威 API（MMDevice）现读录音侧 5 个端点，**在场的 0 个**（1 禁用 / 1 拔出 / 3 不在场），
#      且三个角色的默认录音设备**全都不存在** ⇒ 根本没有可设的东西。
#      **所以第 58 轮那句"设成默认耳朵就通了"是错的话，已删。**
#   ② 文件直连： `SetInputToWaveFile(路径)` —— **不吃设备，吃 WAV**。
#      ⇒ 只要别处能把声音落成 WAV（如 WASAPI 录音，见 `wasapi-record.py`），
#        识别这一段就与 winmm 完全无关。这就是本机绕开死路的那条腿。
#
# 输出契约（**只吐一行 JSON**，Python 侧按最后一行解析）：
#   {ok, heard, text, confidence, culture, seconds, reason}
# 退出码（Python 侧据此分辨"坏"与"安静"）：
#   0 = 跑完了（heard 可能是 false —— **没听到 ≠ 出错**）
#   3 = System.Speech 加载不了（缺.NET 组件）
#   4 = 没有该语言的离线识别器
#   5 = 打不开默认录音设备（没有在场的输入端点）
#   6 = 打不开指定的 WAV 文件（路径不存在 / 格式识别器不接受）
#
# 🔴 纪律：**绝不伪造识别结果**。听不到就 heard=false + reason 照实写。
param(
  [double]$Seconds = 6,
  [string]$Culture = "zh-CN",
  [double]$MinConfidence = 0.0,
  [string]$WavFile = ""
)
$ErrorActionPreference = "Continue"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

function Emit($o) { $o | ConvertTo-Json -Compress }

try { Add-Type -AssemblyName System.Speech -ErrorAction Stop }
catch { Emit @{ ok = $false; heard = $false; status = "needs_dependency"
                reason = "System.Speech 加载失败：$($_.Exception.Message)" }; exit 3 }

$all = @()
try { $all = [System.Speech.Recognition.SpeechRecognitionEngine]::InstalledRecognizers() }
catch { Emit @{ ok = $false; heard = $false; status = "needs_dependency"
                reason = "枚举识别器失败：$($_.Exception.Message)" }; exit 3 }

$have = @($all | ForEach-Object { $_.Culture.Name })
$rec = $all | Where-Object { $_.Culture.Name -eq $Culture } | Select-Object -First 1
if (-not $rec) {
  Emit @{ ok = $false; heard = $false; status = "no_recognizer"
          reason = "本机没有 $Culture 的离线识别器"; have = $have }; exit 4
}

$eng = New-Object System.Speech.Recognition.SpeechRecognitionEngine $rec

# ── 选输入通道 ────────────────────────────────────────────────────────────
$usingWav = ($WavFile -ne "")
if ($usingWav) {
  if (-not (Test-Path -LiteralPath $WavFile)) {
    $eng.Dispose()
    Emit @{ ok = $false; heard = $false; status = "no_input"; source = "wav"
            reason = "WAV 文件不存在：$WavFile" }; exit 6
  }
  try { $eng.SetInputToWaveFile((Resolve-Path -LiteralPath $WavFile).Path) }
  catch {
    $eng.Dispose()
    Emit @{ ok = $false; heard = $false; status = "no_input"; source = "wav"
            reason = "打不开 WAV：$($_.Exception.Message)" }; exit 6
  }
} else {
  try { $eng.SetInputToDefaultAudioDevice() }
  catch {
    $eng.Dispose()
    Emit @{ ok = $false; heard = $false; status = "no_input"; source = "device"
            reason = "打不开默认录音设备：$($_.Exception.Message)"
            hint = "本机录音侧现读 0 个在场端点（旧版 waveIn 映射器数 0）。可改用 -WavFile <路径> 喂 WAV。" }; exit 5
  }
}

try {
  $eng.LoadGrammar((New-Object System.Speech.Recognition.DictationGrammar))
  if ($usingWav) { $r = $eng.Recognize() }                        # 文件输入：整段跑完
  else { $r = $eng.Recognize([TimeSpan]::FromSeconds($Seconds)) }
} catch {
  $eng.Dispose()
  Emit @{ ok = $false; heard = $false; status = "error"
          reason = "识别过程出错：$($_.Exception.Message)" }; exit 5
}
$eng.Dispose()

$src = if ($usingWav) { "wav" } else { "device" }
if ($null -eq $r) {
  Emit @{ ok = $true; heard = $false; text = ""; seconds = $Seconds; culture = $Culture
          recognizer = $rec.Id; source = $src
          reason = if ($usingWav) { "WAV 里没有识别到语音（安静，不是坏）" }
                    else { "$Seconds 秒内没有识别到语音（安静，不是坏）" } }; exit 0
}
$conf = [math]::Round([double]$r.Confidence, 3)
if ($conf -lt $MinConfidence) {
  Emit @{ ok = $true; heard = $false; text = ""; seconds = $Seconds; culture = $Culture
          recognizer = $rec.Id; source = $src; confidence = $conf
          reason = "听到了但置信度 $conf 低于门槛 $MinConfidence —— 不当成指令" }; exit 0
}
Emit @{ ok = $true; heard = $true; text = $r.Text; confidence = $conf
        seconds = $Seconds; culture = $Culture; recognizer = $rec.Id; source = $src }; exit 0
