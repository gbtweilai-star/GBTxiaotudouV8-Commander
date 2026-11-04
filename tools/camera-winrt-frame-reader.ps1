# camera-winrt-frame-reader.ps1 — MediaFrameReader 连续帧（BGRA raw）
param(
  [string]$OutDir = "camraw",
  [int]$Frames = 10,
  [double]$Fps = 10.0
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
[Windows.Media.Capture.MediaCaptureInitializationSettings,Windows.Media.Capture,ContentType=WindowsRuntime] | Out-Null
[Windows.Media.Capture.MediaCaptureMemoryPreference,Windows.Media.Capture,ContentType=WindowsRuntime] | Out-Null
[Windows.Media.Capture.StreamingCaptureMode,Windows.Media.Capture,ContentType=WindowsRuntime] | Out-Null
[Windows.Media.Capture.Frames.MediaFrameReader,Windows.Media.Capture.Frames,ContentType=WindowsRuntime] | Out-Null
[Windows.Media.Capture.Frames.MediaFrameReaderAcquisitionMode,Windows.Media.Capture.Frames,ContentType=WindowsRuntime] | Out-Null
[Windows.Media.MediaProperties.MediaEncodingSubtypes,Windows.Media.MediaProperties,ContentType=WindowsRuntime] | Out-Null
[Windows.Graphics.Imaging.SoftwareBitmap,Windows.Graphics.Imaging,ContentType=WindowsRuntime] | Out-Null
[Windows.Graphics.Imaging.BitmapPixelFormat,Windows.Graphics.Imaging,ContentType=WindowsRuntime] | Out-Null
[Windows.Graphics.Imaging.BitmapAlphaMode,Windows.Graphics.Imaging,ContentType=WindowsRuntime] | Out-Null
[Windows.Storage.Streams.Buffer,Windows.Storage.Streams,ContentType=WindowsRuntime] | Out-Null
[Windows.Storage.Streams.DataReader,Windows.Storage.Streams,ContentType=WindowsRuntime] | Out-Null
$cap = New-Object Windows.Media.Capture.MediaCapture
$settings = New-Object Windows.Media.Capture.MediaCaptureInitializationSettings
$settings.StreamingCaptureMode = [Windows.Media.Capture.StreamingCaptureMode]::Video
$settings.MemoryPreference = [Windows.Media.Capture.MediaCaptureMemoryPreference]::Cpu
AwaitAction ($cap.InitializeAsync($settings))
$source = @($cap.FrameSources.Values)[0]
$reader = AwaitOp ($cap.CreateFrameReaderAsync($source, [Windows.Media.MediaProperties.MediaEncodingSubtypes]::Bgra8)) ([Windows.Media.Capture.Frames.MediaFrameReader])
$reader.AcquisitionMode = [Windows.Media.Capture.Frames.MediaFrameReaderAcquisitionMode]::Realtime
AwaitAction ($reader.StartAsync())
$n = 0
while ($n -lt $Frames) {
    $frame = $reader.TryAcquireLatestFrame()
    if ($null -eq $frame) { Start-Sleep -Milliseconds 20; continue }
    try {
        $sb = $frame.VideoMediaFrame.SoftwareBitmap
        if ($null -eq $sb) { Start-Sleep -Milliseconds 20; continue }
        if ($sb.BitmapPixelFormat -ne [Windows.Graphics.Imaging.BitmapPixelFormat]::Bgra8) {
            $sb = [Windows.Graphics.Imaging.SoftwareBitmap]::Convert($sb, [Windows.Graphics.Imaging.BitmapPixelFormat]::Bgra8, [Windows.Graphics.Imaging.BitmapAlphaMode]::Premultiplied)
        }
        $w = $sb.PixelWidth; $h = $sb.PixelHeight
        $buf = New-Object Windows.Storage.Streams.Buffer ([uint32]($w * $h * 4))
        $sb.CopyToBuffer($buf)
        $dr = [Windows.Storage.Streams.DataReader]::FromBuffer($buf)
        $arr = New-Object byte[] ($w * $h * 4)
        $dr.ReadBytes($arr)
        $name = "frame-{0:D4}.raw" -f ($n + 1)
        [IO.File]::WriteAllBytes((Join-Path $OutDir $name), $arr)
        [IO.File]::WriteAllText((Join-Path $OutDir "latest.json"), ('{"w":%d,"h":%d}' -f $w, $h))
        Copy-Item -LiteralPath (Join-Path $OutDir $name) -Destination (Join-Path $OutDir "latest.raw") -Force
        $dr.Dispose()
        $n++
        Write-Output ("frame " + $n + " " + $w + "x" + $h)
    } finally {
        $frame.Dispose()
    }
    Start-Sleep -Milliseconds ([int](1000.0 / [math]::Max(1.0, $Fps)))
}
AwaitAction ($reader.StopAsync())
$reader.Dispose(); $cap.Dispose()
Write-Output ("DONE " + $n)

