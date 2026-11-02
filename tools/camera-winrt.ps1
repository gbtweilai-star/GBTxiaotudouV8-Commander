# camera-winrt.ps1 — WinRT MediaCapture 抓一帧到 jpg（绕开 OpenCV/DirectShow 绑定问题）
param([string]$OutFile = "camera-winrt.jpg")
$ErrorActionPreference = "Stop"
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
$stream = New-Object Windows.Storage.Streams.InMemoryRandomAccessStream
$props = [Windows.Media.MediaProperties.ImageEncodingProperties]::CreateJpeg()
AwaitAction ($cap.CapturePhotoToStreamAsync($props, $stream))
$stream.Seek(0)
$size = [uint32]$stream.Size
$reader = New-Object Windows.Storage.Streams.DataReader($stream.GetInputStreamAt(0))
AwaitOp ($reader.LoadAsync($size)) ([uint32]) | Out-Null
$buf = New-Object byte[] $size
$reader.ReadBytes($buf)
[IO.File]::WriteAllBytes($OutFile, $buf)
$reader.Dispose(); $stream.Dispose(); $cap.Dispose()
Write-Output ("OK " + $OutFile + " " + $size)

