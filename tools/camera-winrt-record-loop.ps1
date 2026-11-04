# camera-winrt-record-loop.ps1 — WinRT 连续录制 1s 小段（实时性靠 chunk）
param(
  [string]$OutDir = "camchunks",
  [int]$Chunks = 3,
  [double]$SecondsPerChunk = 1.0
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
[Windows.Media.MediaProperties.MediaEncodingProfile,Windows.Media.MediaProperties,ContentType=WindowsRuntime] | Out-Null
[Windows.Media.MediaProperties.VideoEncodingQuality,Windows.Media.MediaProperties,ContentType=WindowsRuntime] | Out-Null
[Windows.Storage.StorageFolder,Windows.Storage,ContentType=WindowsRuntime] | Out-Null
[Windows.Storage.StorageFile,Windows.Storage,ContentType=WindowsRuntime] | Out-Null
[Windows.Storage.CreationCollisionOption,Windows.Storage,ContentType=WindowsRuntime] | Out-Null
$folder = AwaitOp ([Windows.Storage.StorageFolder]::GetFolderFromPathAsync((Resolve-Path $OutDir).Path)) ([Windows.Storage.StorageFolder])
$cap = New-Object Windows.Media.Capture.MediaCapture
AwaitAction ($cap.InitializeAsync())
$profile = [Windows.Media.MediaProperties.MediaEncodingProfile]::CreateMp4([Windows.Media.MediaProperties.VideoEncodingQuality]::HD720p)
for ($i = 1; $i -le $Chunks; $i++) {
    $name = "chunk-{0:D4}.mp4" -f $i
    $file = AwaitOp ($folder.CreateFileAsync($name, [Windows.Storage.CreationCollisionOption]::ReplaceExisting)) ([Windows.Storage.StorageFile])
    AwaitAction ($cap.StartRecordToStorageFileAsync($profile, $file))
    Start-Sleep -Milliseconds ([int]($SecondsPerChunk * 1000))
    AwaitAction ($cap.StopRecordAsync())
    Write-Output ("chunk " + $i + " " + $name)
}
$cap.Dispose()
Write-Output ("DONE " + $Chunks + " " + $OutDir)

