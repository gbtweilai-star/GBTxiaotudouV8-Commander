# gbt-capability: drama_forge
# 开发者：自由的风 · 永久钢印 · 禁止删除
<#
drama-build.ps1 — 短剧一键产线（剧本 → 分镜 → SAPI 旁白 → SRT → 竖屏 MP4）
为什么要有这一层：SAPI 在"Python 子进程再拉 PowerShell"里会被安全策略拒（本机实测），
但**在 PowerShell 进程自身里可用**。所以 TTS 放在 PS 层，装配交给 Python 的 drama_forge。
用法：
  powershell -NoProfile -ExecutionPolicy Bypass -File tools\drama-build.ps1 `
    -ScriptFile .\script.txt -Name 醒来E1 [-AssetsDir .\assets] [-MinDur 5] [-MaxDur 60]
#>
param(
    [Parameter(Mandatory = $true)][string]$ScriptFile,
    [string]$Name = '',
    [string]$AssetsDir = '',
    [double]$MinDur = 5,
    [double]$MaxDur = 180,
    [switch]$Gen,
    [string]$StockQueriesFile = "",
    [string]$Voice = "local",
    [string]$Rate = "",
    [string]$Pitch = "",
    [switch]$CloudTts,
    [string]$Repo = ''
)

$ErrorActionPreference = 'Stop'
if (-not $Repo) { $Repo = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..')).Path }
$Repo = (Resolve-Path -LiteralPath $Repo).Path
$ScriptFile = (Resolve-Path -LiteralPath $ScriptFile).Path
if (-not $Name) { $Name = 'drama-' + (Get-Date -Format 'MMdd-HHmm') }
$ws = Split-Path -Parent $Repo
$py = Join-Path $ws 'pyembed\python.exe'
if (-not (Test-Path -LiteralPath $py)) { $py = 'python' }

$stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
$outRoot = Join-Path $Repo "outputs\drama-forge\$Name"
$ttsDir = Join-Path $Repo "outputs\drama-forge\_tts\$stamp"
$prepJson = Join-Path $ttsDir 'prep.json'
$reqJson = Join-Path $ttsDir 'request.json'
New-Item -ItemType Directory -Force -Path $ttsDir | Out-Null

Write-Output '== 1/3 剧本 → 分镜 =='
& $py -B -X utf8 (Join-Path $Repo 'tools\codex-scripts\drama-prep.py') $Repo $ScriptFile $ttsDir $prepJson
if ($LASTEXITCODE -ne 0) { throw 'drama-prep 失败（检查剧本时间码格式 0s – 4s）' }
$prep = Get-Content -LiteralPath $prepJson -Raw -Encoding utf8 | ConvertFrom-Json

Write-Output '== 2/3 旁白（本地优先；Edge 需 -CloudTts 显式开） =='
$edge = Join-Path $Repo 'tools\codex-scripts\edge-tts.py'
if ($CloudTts -and $Voice -match '^zh-TW-') {
    foreach ($sh in $prep.shots) {
        $txt = [IO.File]::ReadAllText($sh.txt, [Text.Encoding]::UTF8)
        if (-not $txt) { continue }
        $mp3 = Join-Path $ttsDir ("shot-{0:D2}.mp3" -f [int]$sh.idx)
        $edgeArgs = @('--text-file', $sh.txt, '--out', $mp3, '--voice', $Voice)
        if ($Rate) { $edgeArgs += @('--rate', $Rate) }
        if ($Pitch) { $edgeArgs += @('--pitch', $Pitch) }
        & $py -B -X utf8 $edge @edgeArgs
        if ($LASTEXITCODE -ne 0) { throw ("镜 {0} Edge 配音失败" -f $sh.idx) }
        Write-Output ("  镜 {0}: {1}（{2}）" -f $sh.idx, (Split-Path $mp3 -Leaf), $Voice)
    }
} else {
    Add-Type -AssemblyName System.Speech
    foreach ($sh in $prep.shots) {
        $txt = [IO.File]::ReadAllText($sh.txt, [Text.Encoding]::UTF8)
        if (-not $txt) { continue }
        $wav = Join-Path $ttsDir ("shot-{0:D2}.wav" -f [int]$sh.idx)
        $ps = "Add-Type -AssemblyName System.Speech;`$s=New-Object System.Speech.Synthesis.SpeechSynthesizer;`$vs=`$s.GetInstalledVoices()|ForEach-Object{`$_.VoiceInfo};`$pick=`$vs|Where-Object{`$_.Culture.Name -eq 'zh-TW' -and `$_.Gender -eq 'Female'}|Select-Object -First 1;if(-not `$pick){`$pick=`$vs|Where-Object{`$_.Culture.Name -like 'zh-*'}|Select-Object -First 1};if(`$pick){`$s.SelectVoice(`$pick.Name)};`$s.SetOutputToWaveFile('$wav');`$s.Speak([IO.File]::ReadAllText('$($sh.txt)'));`$name=`$s.Voice.Name;`$s.Dispose();Write-Output `$name"
        $used = & powershell -NoProfile -Command $ps 2>&1 | Select-Object -Last 1
        if ($LASTEXITCODE -ne 0 -or -not (Test-Path $wav)) { throw ("镜 {0} 本地配音失败" -f $sh.idx) }
        Write-Output ("  镜 {0}: {1}（本地 {2}）" -f $sh.idx, (Split-Path $wav -Leaf), $used)
    }
}

Write-Output '== 3/3 装配（ffmpeg + 字幕） =='
$req = @{
    op = 'make'; name = $Name; script = $prep.script; audio_dir = $ttsDir; voice = $Voice
    min_dur = $MinDur; max_dur = $MaxDur
}
if ($AssetsDir) { $req.assets_dir = (Resolve-Path -LiteralPath $AssetsDir).Path }
if ($StockQueriesFile) {
    $stockDir = Join-Path $outRoot 'assets-stock'
    New-Item -ItemType Directory -Force -Path $stockDir | Out-Null
    Write-Output '== 2.5/3 取 CC 授权真实照片（Openverse；兜底 Picsum） =='
    & powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $Repo 'tools\stock-fetch.ps1') -QueriesFile $StockQueriesFile -OutDir $stockDir
    $req.assets_dir = $stockDir
}
[IO.File]::WriteAllText($reqJson, ($req | ConvertTo-Json -Depth 5), (New-Object Text.UTF8Encoding($false)))
& $py -B -X utf8 (Join-Path $Repo 'tools\codex-scripts\drama-make.py') $Repo $reqJson
exit $LASTEXITCODE
