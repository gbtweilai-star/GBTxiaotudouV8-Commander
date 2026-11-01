# 触手主干 · 本机引擎守护（PowerShell）
#
# 干什么：每 15 秒打一次 /health，**连续 2 次不通**就把 llama-server 拉起来；
#        拉了还不通就把日志尾部打出来（不静默）。
#
# 为什么需要它：llama-server 是独立进程，崩了/被系统回收了，主干就会静默降级到
#   云端/词表 —— 主人看到的只是"她变笨了"，看不到"引擎没了"。守护把这件事变成可见。
#
# 用法：
#   powershell -ExecutionPolicy Bypass -File tools\commander-supervisor.ps1
#   powershell -ExecutionPolicy Bypass -File tools\commander-supervisor.ps1 -Once
#
# 退出：Ctrl+C（或杀进程）。日志：state/commander/supervisor.log
param(
    [int]$IntervalSec = 15,
    [int]$FailThreshold = 2,
    [switch]$Once
)
$ErrorActionPreference = "Continue"
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$Repo = $Root
if (Test-Path (Join-Path $Root "pyproject.toml")) { $Repo = $Root }
elseif (Test-Path (Join-Path $Root "GBTxiaotudouV8-Commander-main\pyproject.toml")) {
    $Repo = Join-Path $Root "GBTxiaotudouV8-Commander-main"
}
$Log = Join-Path $Repo "state\commander\supervisor.log"
New-Item -ItemType Directory -Force -Path (Split-Path $Log) | Out-Null

function Write-Log([string]$msg) {
    $line = "{0}  {1}" -f (Get-Date -Format "yyyy-MM-ddTHH:mm:ss"), $msg
    Add-Content -Path $Log -Value $line -Encoding utf8
    Write-Host $line
}

function Test-Engine {
    try {
        $r = Invoke-WebRequest -Uri "http://127.0.0.1:8792/health" -UseBasicParsing -TimeoutSec 3
        return ($r.StatusCode -eq 200)
    } catch { return $false }
}

function Start-Engine {
    $py = Join-Path $Repo "state\weights\ACTIVE.json"
    $server = Get-ChildItem -Path (Join-Path $Repo "vendor") -Recurse -Filter "llama-server.exe" -ErrorAction SilentlyContinue | Select-Object -First 1
    $w = $null
    if (Test-Path $py) {
        $rec = Get-Content $py -Raw -Encoding utf8 | ConvertFrom-Json
        $name = $rec.active_artifact
        if (-not $name) { $name = $rec.model }
        if ($name) { $w = Join-Path (Join-Path $Repo "state\weights") $name }
    }
    if (-not $server) { Write-Log "起不来：vendor 下没有 llama-server.exe"; return $false }
    if (-not $w -or -not (Test-Path $w)) { Write-Log "起不来：权重不在（$w）"; return $false }
    # ⚠️ 路径里有空格（`Lenovo E14 Gen 5`）：Start-Process 的 -ArgumentList 传数组时
    #    会按空格拼、不自动加引号 ⇒ 实测报 `error: invalid argument: E14`。
    #    所以这里**自己加引号，拼成一个字符串**再传。
    $argList = @("-m", "`"$w`"", "--host", "127.0.0.1", "--port", "8792",
                 "-c", "2048", "-t", "12", "-ngl", "0", "--no-webui",
                 "--sleep-idle-seconds", "600") -join " "
    $logFile = Join-Path $Repo "state\commander\engine.log"
    $p = Start-Process -FilePath $server.FullName -ArgumentList $argList -WorkingDirectory $Repo `
        -RedirectStandardOutput $logFile -RedirectStandardError "$logFile.err" -PassThru -WindowStyle Hidden
    Set-Content -Path (Join-Path $Repo "state\commander\engine.pid") -Value $p.Id -Encoding utf8
    Write-Log "已拉起 llama-server pid=$($p.Id)"
    return $true
}

Write-Log "守护启动 · 间隔 ${IntervalSec}s · 阈值 $FailThreshold"
$fails = 0
while ($true) {
    if (Test-Engine) {
        if ($fails -gt 0) { Write-Log "引擎已恢复（此前连续失败 $fails 次）" }
        $fails = 0
    } else {
        $fails++
        Write-Log "health 不通（第 $fails 次）"
        if ($fails -ge $FailThreshold) {
            $ok = Start-Engine
            Start-Sleep -Seconds 6
            if (Test-Engine) { Write-Log "拉起成功"; $fails = 0 } else {
                Write-Log "拉起后仍不通，日志尾部："
                $tail = Get-Content (Join-Path $Repo "state\commander\engine.log") -Tail 8 -ErrorAction SilentlyContinue
                foreach ($t in $tail) { Write-Log "  $t" }
            }
        }
    }
    if ($Once) { break }
    Start-Sleep -Seconds $IntervalSec
}
