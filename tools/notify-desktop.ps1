# gbt-capability: notify_desktop
# 开发者：自由的风 · 永久钢印 · 禁止删除
<#
notify-desktop.ps1 — 零依赖 Windows 桌面通知（WinRT Toast，Win10/11）
用法：
  powershell -NoProfile -ExecutionPolicy Bypass -File tools\notify-desktop.ps1 -Title "GBT" -Message "双仓同步漂移"
返回：0=已投递 toast；1=失败（错误写 stderr）
#>
param(
    [string]$Title = 'GBT小土豆V8',
    [string]$Message = '有新的巡检信号'
)

$ErrorActionPreference = 'Stop'
try {
    [Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime] | Out-Null
    [Windows.Data.Xml.Dom.XmlDocument, Windows.Data.Xml.Dom.XmlDocument, ContentType = WindowsRuntime] | Out-Null
    $safeTitle = [System.Security.SecurityElement]::Escape($Title)
    $safeMsg = [System.Security.SecurityElement]::Escape($Message)
    $template = @"
<toast><visual><binding template="ToastGeneric"><text>$safeTitle</text><text>$safeMsg</text></binding></visual></toast>
"@
    $xml = New-Object Windows.Data.Xml.Dom.XmlDocument
    $xml.LoadXml($template)
    $toast = New-Object Windows.UI.Notifications.ToastNotification $xml
    [Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier('GBT小土豆V8').Show($toast)
    Write-Output 'toast_sent'
    exit 0
} catch {
    # 非打包进程（如被 Python 子进程拉起）WinRT 会报 no package identity ⇒ 退回托盘气泡
    try {
        Add-Type -AssemblyName System.Windows.Forms
        Add-Type -AssemblyName System.Drawing
        $n = New-Object System.Windows.Forms.NotifyIcon
        $n.Icon = [System.Drawing.SystemIcons]::Information
        $n.Visible = $true
        $n.ShowBalloonTip(6000, $Title, $Message, [System.Windows.Forms.ToolTipIcon]::Info)
        Start-Sleep -Seconds 7
        $n.Dispose()
        Write-Output 'balloon_sent'
        exit 0
    } catch {
        Write-Error ("toast_failed: " + $_.Exception.Message)
        exit 1
    }
}
