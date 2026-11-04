# camera-winrt-video.ps1 — WinRT MediaCapture 录制一段视频（连续相机路径）
param(
  [string]$OutFile = "camera-winrt.mp4",
  [double]$Seconds = 3.0,
  [string]$Quality = "HD720p"
)
$ErrorActionPreference = "Stop"
$dir = Split-Path -Parent $OutFile
if (-not $dir) { $dir = "." }
$name = Split-Path -Leaf $OutFile
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
$folder = AwaitOp ([Windows.Storage.StorageFolder]::GetFolderFromPathAsync((Resolve-Path $dir).Path)) ([Windows.Storage.StorageFolder])
$file = AwaitOp ($folder.CreateFileAsync($name, [Windows.Storage.CreationCollisionOption]::ReplaceExisting)) ([Windows.Storage.StorageFile])
$cap = New-Object Windows.Media.Capture.MediaCapture
AwaitAction ($cap.InitializeAsync())
$profile = [Windows.Media.MediaProperties.MediaEncodingProfile]::CreateMp4([Windows.Media.MediaProperties.VideoEncodingQuality]::$Quality)
AwaitAction ($cap.StartRecordToStorageFileAsync($profile, $file))
Start-Sleep -Seconds $Seconds
AwaitAction ($cap.StopRecordAsync())
$cap.Dispose()
Write-Output ("OK " + $OutFile)

