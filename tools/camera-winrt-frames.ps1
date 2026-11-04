# camera-winrt-frames.ps1 — WinRT 常驻抓帧桥（PowerShell 侧）
param(
  [string]$OutDir = "$PSScriptRoot\..\.scratch\lead\camframes",
  [int]$Frames = 30,
  [double]$Fps = 3.0
)
$ErrorActionPreference = "Stop"
New-Item -ItemType Directory -Force -Path $OutDir | Out-Null
Add-Type -AssemblyName System.Runtime.WindowsRuntime
$asAction = ([System.WindowsRuntimeSystemExtensions].GetMethods() | Where-Object {
    $_.Name -eq 'AsTask' -and $_.GetParameters().Count -eq 1 -and $_.GetParameters()[0].ParameterType.Name -eq 'IAsyncAction' })[0]
$asOp = ([System.WindowsRuntimeSystemExtensions].GetMethods() | Where-Object {
    $_.Name -eq 'AsTask' -and $_.GetParameters().Count -eq 1 -and $_.GetParameters()[0].ParameterType.Name -eq 'IAsyncOperation`1' })[0]
function AwaitAction($op) { $t = $asAction.Invoke($null, @($op)); $t.Wait(-1) | Out-Null }
function AwaitOp($op, $rt) { $t = $asOp.MakeGenericMethod($rt).Invoke($null, @($op)); $t.Wait(-1) | Out-Null; $t.Result }
[Windows.Media.Capture.MediaCapture,Windows.Media.Capture,ContentType=WindowsRuntime] | Out-Null
[Windows.Media.MediaProperties.ImageEncodingProperties,Windows.Media.MediaProperties,ContentType=WindowsRuntime] | Out-Null
[Windows.Storage.Streams.InMemoryRandomAccessStream,Windows.Storage.Streams,ContentType=WindowsRuntime] | Out-Null
[Windows.Storage.Streams.DataReader,Windows.Storage.Streams,ContentType=WindowsRuntime] | Out-Null
$cap = New-Object Windows.Media.Capture.MediaCapture
AwaitAction ($cap.InitializeAsync())
$props = [Windows.Media.MediaProperties.ImageEncodingProperties]::CreateJpeg()
$nFrames = 0
$t0 = [Diagnostics.Stopwatch]::StartNew()
for ($i = 0; $i -lt $Frames; $i++) {
    $stream = New-Object Windows.Storage.Streams.InMemoryRandomAccessStream
    AwaitAction ($cap.CapturePhotoToStreamAsync($props, $stream))
    $stream.Seek(0)
    $size = [uint32]$stream.Size
    $reader = New-Object Windows.Storage.Streams.DataReader($stream.GetInputStreamAt(0))
    AwaitOp ($reader.LoadAsync($size)) ([uint32]) | Out-Null
    $buf = New-Object byte[] $size
    $reader.ReadBytes($buf)
    $tmp = Join-Path $OutDir ("frame-{0:D4}.jpg" -f ($i + 1))
    [IO.File]::WriteAllBytes($tmp, $buf)
    $latest = Join-Path $OutDir "latest.jpg"
    $tmpLatest = Join-Path $OutDir "latest.tmp"
    [IO.File]::WriteAllBytes($tmpLatest, $buf)
    Move-Item -LiteralPath $tmpLatest -Destination $latest -Force
    $reader.Dispose(); $stream.Dispose()
    $nFrames++
    Write-Output ("frame " + $nFrames + " " + $size + " " + [math]::Round($t0.Elapsed.TotalSeconds,2))
    $sleep = (1.0 / [math]::Max(0.1, $Fps)) - 0.2
    if ($sleep -gt 0) { Start-Sleep -Milliseconds ([int]($sleep * 1000)) }
}
$cap.Dispose()
Write-Output ("DONE " + $nFrames + " " + $OutDir)

