param(
  [Parameter(Mandatory=$true)][string]$Path,
  [Parameter(Mandatory=$true)][string]$Out,
  [string]$Lang = "zh-Hans-CN"
)

# win_ocr.ps1 -- Windows.Media.Ocr 桥（零安装 / 离线 / 不吃 pip）
# 只吃本地路径，只回 UTF-8 JSON 文本，绝不返回图片。

$ErrorActionPreference = "Stop"

function Write-Result($hashtable) {
  [System.IO.File]::WriteAllText($Out, ($hashtable | ConvertTo-Json -Compress -Depth 8),
    (New-Object System.Text.UTF8Encoding($false)))
}

function Fail($msg) {
  Write-Result @{ ok = $false; backend = "windows-media-ocr"; reason = $msg }
  exit 1
}

try {
  if (-not (Test-Path -LiteralPath $Path)) { Fail "image not found: $Path" }

  Add-Type -AssemblyName System.Runtime.WindowsRuntime | Out-Null

  $asTaskGeneric = ([System.WindowsRuntimeSystemExtensions].GetMethods() | Where-Object {
      $_.Name -eq "AsTask" -and
      $_.GetParameters().Count -eq 1 -and
      $_.GetParameters()[0].ParameterType.Name -like "IAsyncOperation*" -and
      $_.GetParameters()[0].ParameterType.Name -notlike "*WithProgress*" })[0]
  if ($null -eq $asTaskGeneric) { Fail "AsTask interop not found (System.Runtime.WindowsRuntime missing)" }

  function Await($op, $t) {
    $m = $asTaskGeneric.MakeGenericMethod($t)
    $task = $m.Invoke($null, @($op))
    $task.Wait(-1) | Out-Null
    $task.Result
  }

  [Windows.Storage.StorageFile, Windows.Storage, ContentType=WindowsRuntime] | Out-Null
  [Windows.Storage.Streams.IRandomAccessStream, Windows.Storage.Streams, ContentType=WindowsRuntime] | Out-Null
  [Windows.Graphics.Imaging.BitmapDecoder, Windows.Graphics.Imaging, ContentType=WindowsRuntime] | Out-Null
  [Windows.Graphics.Imaging.SoftwareBitmap, Windows.Graphics.Imaging, ContentType=WindowsRuntime] | Out-Null
  [Windows.Media.Ocr.OcrEngine, Windows.Foundation, ContentType=WindowsRuntime] | Out-Null
  [Windows.Media.Ocr.OcrResult, Windows.Foundation, ContentType=WindowsRuntime] | Out-Null
  [Windows.Globalization.Language, Windows.Globalization, ContentType=WindowsRuntime] | Out-Null

  # ---- 选引擎：先按指定语言，再退到任意中文，最后退到用户配置 ----
  $engine = $null
  if ($Lang) {
    try {
      $engine = [Windows.Media.Ocr.OcrEngine]::TryCreateFromLanguage(
        (New-Object Windows.Globalization.Language $Lang))
    } catch { $engine = $null }
  }
  $tags = @([Windows.Media.Ocr.OcrEngine]::AvailableRecognizerLanguages | ForEach-Object { $_.LanguageTag })
  if ($null -eq $engine) {
    foreach ($t in $tags) {
      if ($t -like "zh*") {
        try {
          $engine = [Windows.Media.Ocr.OcrEngine]::TryCreateFromLanguage(
            (New-Object Windows.Globalization.Language $t))
          if ($null -ne $engine) { break }
        } catch { }
      }
    }
  }
  if ($null -eq $engine) {
    $engine = [Windows.Media.Ocr.OcrEngine]::TryCreateFromUserProfileLanguages()
  }
  if ($null -eq $engine) {
    Fail ("no OCR engine available; installed languages = " + ($tags -join ","))
  }

  # ---- 解码 ----
  $full = (Resolve-Path -LiteralPath $Path).Path
  $file = Await ([Windows.Storage.StorageFile]::GetFileFromPathAsync($full)) ([Windows.Storage.StorageFile])
  $stream = Await ($file.OpenAsync([Windows.Storage.FileAccessMode]::Read)) ([Windows.Storage.Streams.IRandomAccessStream])
  $decoder = Await ([Windows.Graphics.Imaging.BitmapDecoder]::CreateAsync($stream)) ([Windows.Graphics.Imaging.BitmapDecoder])
  $bmp = Await ($decoder.GetSoftwareBitmapAsync()) ([Windows.Graphics.Imaging.SoftwareBitmap])

  $res = Await ($engine.RecognizeAsync($bmp)) ([Windows.Media.Ocr.OcrResult])

  # ---- 拼行：中文词之间不留空格，西文词之间留一个空格 ----
  $cjkPat = "[\u2E80-\u2EFF\u3000-\u303F\u3040-\u30FF\u3400-\u4DBF\u4E00-\u9FFF\uF900-\uFAFF\uFE30-\uFE4F\uFF00-\uFFEF]"
  $lineTexts = New-Object System.Collections.ArrayList
  $boxes = New-Object System.Collections.ArrayList
  $lineCount = 0
  foreach ($ln in $res.Lines) {
    $lineCount++
    $lineText = ""
    $words = New-Object System.Collections.ArrayList
    $minX = [double]::MaxValue; $minY = [double]::MaxValue
    $maxX = 0.0; $maxY = 0.0
    foreach ($w in $ln.Words) {
      $t = [string]$w.Text
      if ($lineText.Length -gt 0) {
        $pc = $lineText.Substring($lineText.Length - 1, 1)
        $cc = $t.Substring(0, 1)
        if (($pc -notmatch $cjkPat) -and ($cc -notmatch $cjkPat)) { $lineText += " " }
      }
      $lineText += $t
      $r = $w.BoundingRect
      $rx = [double]$r.X; $ry = [double]$r.Y
      $rw = [double]$r.Width; $rh = [double]$r.Height
      if ($rx -lt $minX) { $minX = $rx }
      if ($ry -lt $minY) { $minY = $ry }
      if (($rx + $rw) -gt $maxX) { $maxX = $rx + $rw }
      if (($ry + $rh) -gt $maxY) { $maxY = $ry + $rh }
      [void]$words.Add(@{ text = $t; x = [int]$rx; y = [int]$ry; w = [int]$rw; h = [int]$rh })
    }
    if ($lineText.Length -eq 0) { continue }
    [void]$lineTexts.Add($lineText)
    [void]$boxes.Add(@{
      text  = $lineText
      x     = [int]$minX
      y     = [int]$minY
      w     = [int]($maxX - $minX)
      h     = [int]($maxY - $minY)
      words = $words
    })
  }

  $text = ($lineTexts -join "`n").TrimEnd()
  Write-Result @{
    ok        = $true
    backend   = "windows-media-ocr"
    lang      = $engine.RecognizerLanguage.LanguageTag
    lines     = $lineCount
    chars     = $text.Length
    languages = $tags
    text      = $text
    boxes     = $boxes
  }
  exit 0
} catch {
  Fail ($_.Exception.GetType().Name + " :: " + $_.Exception.Message)
}
