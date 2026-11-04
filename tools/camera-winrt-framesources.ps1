# camera-winrt-framesources.ps1 — 列 FrameSources/格式，诊断 MediaFrameReader
param()
$ErrorActionPreference = "Stop"
Add-Type -AssemblyName System.Runtime.WindowsRuntime
$asAction = ([System.WindowsRuntimeSystemExtensions].GetMethods() | Where-Object {
    $_.Name -eq 'AsTask' -and $_.GetParameters().Count -eq 1 -and $_.GetParameters()[0].ParameterType.Name -eq 'IAsyncAction' })[0]
function AwaitAction($op) { $t = $asAction.Invoke($null, @($op)); $t.Wait(-1) | Out-Null }
[Windows.Media.Capture.MediaCapture,Windows.Media.Capture,ContentType=WindowsRuntime] | Out-Null
[Windows.Media.Capture.MediaCaptureInitializationSettings,Windows.Media.Capture,ContentType=WindowsRuntime] | Out-Null
[Windows.Media.Capture.MediaCaptureMemoryPreference,Windows.Media.Capture,ContentType=WindowsRuntime] | Out-Null
[Windows.Media.Capture.StreamingCaptureMode,Windows.Media.Capture,ContentType=WindowsRuntime] | Out-Null
[Windows.Media.Capture.Frames.MediaFrameSource,Windows.Media.Capture.Frames,ContentType=WindowsRuntime] | Out-Null
$cap = New-Object Windows.Media.Capture.MediaCapture
$settings = New-Object Windows.Media.Capture.MediaCaptureInitializationSettings
$settings.StreamingCaptureMode = [Windows.Media.Capture.StreamingCaptureMode]::Video
$settings.MemoryPreference = [Windows.Media.Capture.MediaCaptureMemoryPreference]::Cpu
AwaitAction ($cap.InitializeAsync($settings))
$sources = @($cap.FrameSources.Values)
Write-Output ("SOURCES " + $sources.Count)
Write-Output ("KEYS " + (@($cap.FrameSources.Keys) -join ","))
foreach ($s in $sources) {
    Write-Output ("TYPE " + $s.GetType().FullName)
    if ($s.PSObject.Properties["Value"]) { $s = $s.Value }
    $info = $s.SourceInfo
    Write-Output ("SOURCE " + $info.Id + " kind=" + $info.SourceKind + " type=" + $info.SourceType)
    foreach ($fmt in $s.SupportedFormats) {
        Write-Output ("  FMT " + $fmt.Subtype + " " + $fmt.VideoFormat.Width + "x" + $fmt.VideoFormat.Height + " fps=" + $fmt.FrameRate.Numerator + "/" + $fmt.FrameRate.Denominator)
    }
}
$cap.Dispose()


