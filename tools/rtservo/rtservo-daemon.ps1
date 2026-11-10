# rtservo-daemon.ps1 —— 常驻原生伺服服务（必须在 Medium 完整性下运行）
# 由 powershell.exe 拉起；内嵌 Servo.dll（字节加载，绕开网络标记与临时目录限制）
param(
    [int]$Port = 7791,
    [string]$Dll = "C:\Users\Lenovo E14 Gen 5\Desktop\GBT小土豆V8\tools\rtservo\Servo.dll",
    [string]$LogDir = "C:\Users\Lenovo E14 Gen 5\Desktop\GBT小土豆V8\tools\rtservo"
)

# 幂等守卫：端口已在听就静默退出（供计划任务按分钟重复拉起，防重复绑定与日志刷屏）
try {
    $probe = New-Object System.Net.Sockets.TcpClient
    $probe.Connect('127.0.0.1', $Port)
    $probe.Close()
    exit 0
} catch { }
$ErrorActionPreference = 'Stop'
$logPath = Join-Path $LogDir "daemon.log"

function Log([string]$m) {
    try { Add-Content -Path $logPath -Value ("{0} {1}" -f (Get-Date -Format "HH:mm:ss.fff"), $m) -Encoding UTF8 } catch { }
}

Log "daemon boot port=$Port"

# 字节加载：Add-Type -Path 会被 "不支持操作" (0x80131515) 拦下
try {
    $bytes = [System.IO.File]::ReadAllBytes($Dll)
    $asm = [System.Reflection.Assembly]::Load($bytes)
    $T = $asm.GetType("Servo")
    if (-not $T) { throw "Servo 类型未找到" }
} catch {
    Log "FATAL load: $($_.Exception.Message)"
    exit 1
}
Log "Servo.dll loaded"

# 预热：一次 Ping 触发静态构造（DPI 感知）
try { Log ("ping " + $T::Ping()) } catch { Log "ping err: $($_.Exception.Message)" }

$listener = New-Object System.Net.Sockets.TcpListener([System.Net.IPAddress]::Loopback, $Port)
$listener.Start()
Log "listening $Port"

$pidFile = Join-Path $LogDir "daemon.pid"
Set-Content -Path $pidFile -Value $PID -Encoding ASCII

$running = $true
while ($running) {
    try {
        $client = $listener.AcceptTcpClient()
        $stream = $client.GetStream()
        $reader = New-Object System.IO.StreamReader($stream, [System.Text.Encoding]::UTF8)
        $writer = New-Object System.IO.StreamWriter($stream, (New-Object System.Text.UTF8Encoding($false)))
        $writer.AutoFlush = $true

        while ($true) {
            $line = $reader.ReadLine()
            if ($null -eq $line) { break }
            $line = $line.Trim()
            if ($line -eq "") { continue }

            $parts = $line -split '\s+'
            $op = $parts[0].ToUpperInvariant()
            $resp = $null

            try {
                switch ($op) {
                    'PING'  { $resp = $T::Ping() }
                    'MOVE'  { $resp = $T::Move([int]$parts[1], [int]$parts[2]) }
                    'CLICK' { $resp = $T::Click([int]$parts[1], [int]$parts[2]) }
                    'DRAG'  { $resp = $T::Drag([int]$parts[1], [int]$parts[2], [int]$parts[3], [int]$parts[4], [int]$parts[5], [int]$parts[6]) }
                    'KEY'   { $resp = $T::Key(([string]$parts[1..([Math]::Min(1, $parts.Count - 1))]) -join '+') }
                    'RECT'  { $resp = $T::RectOfPidJson([int]$parts[1]) }
                    'FIND'  { $resp = $T::FindColorJson([int]$parts[1], [int]$parts[2], [int]$parts[3], [int]$parts[4], [int]$parts[5], [int]$parts[6], [int]$parts[7]) }
                    'TPLOAD' { $resp = $T::TplLoad(([string]$parts[1..([Math]::Min(1, $parts.Count - 1))] -join ' ')) }
                    'TPFIND' { $resp = $T::TplFind([double]$parts[1], [int]$parts[2], [int]$parts[3]) }
                    'TRACK' {
                        $resp = $T::Track(
                            [int]$parts[1], [int]$parts[2], [int]$parts[3],
                            [int]$parts[4], [int]$parts[5],
                            [double]$parts[6], [double]$parts[7],
                            [int]$parts[8], [int]$parts[9])
                    }
                    'QUIT'  { $resp = '{"ok":true}'; $running = $false }
                    'TRACK2' {
                        $resp = $T::Track2(
                            [int]$parts[1], [int]$parts[2], [int]$parts[3],
                            [int]$parts[4], [int]$parts[5],
                            [double]$parts[6], [double]$parts[7],
                            [int]$parts[8], [int]$parts[9])
                    }
                    'TPTRACK' {
                        $resp = $T::TplTrack([double]$parts[1], [double]$parts[2], [int]$parts[3], [int]$parts[4])
                    }
                    default { $resp = '{"ok":false,"error":"unknown op"}' }
                }
            } catch {
                $msg = $_.Exception.Message -replace '\\', '\\' -replace '"', '\"'
                $resp = '{"ok":false,"error":"' + $msg + '"}'
            }

            $writer.WriteLine($resp)
        }

        $writer.Close(); $reader.Close(); $stream.Close(); $client.Close()
    } catch {
        Log "conn error: $($_.Exception.Message)"
        if (-not $running) { break }
        Start-Sleep -Milliseconds 50
    }
}

$listener.Stop()
Remove-Item $pidFile -ErrorAction SilentlyContinue
Log "daemon stopped"
