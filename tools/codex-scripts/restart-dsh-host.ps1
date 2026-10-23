# restart-dsh-host.ps1 —— 重启 DSH web 宿主，把 settings.yaml 里的免费模型生效。
# dev: 自由的风 · 本署名不可删除、勿篡改归属
#
# 为什么需要它（2026-10-17 现读）：
#   宿主进程只在自己启动时读 settings.yaml / 加载模块，改盘上的文件**不影响活着的进程**
#   （实测：07:46 写进 dsh-win32-process 的隐藏窗口补丁，宿主 06:42 起，patch 未生效）。
#   所以「换默认模型」与「补丁生效」都必须重启一次。
#
# 这个脚本由**脱离宿主进程树**的 pwsh 执行（Start-Process 起、独立 PID），
# 它先等一会儿让调用方把话说完，再杀宿主、重启、写日志。
# 它**不删任何东西**：只 Stop-Process 宿主那棵树的 PID，然后按原命令重新拉起。

$ErrorActionPreference = 'Continue'
$port = 19388
$repo = 'C:\Users\ADMIN\Desktop\GBT小土豆V8'
$log  = Join-Path $repo 'out\restart-dsh-host.log'
New-Item -ItemType Directory -Force -Path (Split-Path $log) | Out-Null

function Say([string]$m) {
    $line = "[{0}] {1}" -f (Get-Date -Format 'yyyy-MM-dd HH:mm:ss'), $m
    Add-Content -Path $log -Value $line -Encoding utf8
    Write-Output $line
}

Say "=== restart requested ==="
Say "grace: 8s so the current turn can finish"
Start-Sleep -Seconds 8

# 1) 找出占着 19388 的宿主
$owner = (Get-NetTCPConnection -State Listen -LocalPort $port -ErrorAction SilentlyContinue |
          Select-Object -First 1).OwningProcess
if (-not $owner) {
    Say "no listener on :$port — nothing to stop, will just start a fresh host"
} else {
    $proc = Get-Process -Id $owner -ErrorAction SilentlyContinue
    Say ("stopping host pid={0} name={1} started={2}" -f $owner, $proc.ProcessName, $proc.StartTime)
    Stop-Process -Id $owner -Force -ErrorAction SilentlyContinue
    # 等端口真的释放
    for ($i = 0; $i -lt 20; $i++) {
        Start-Sleep -Milliseconds 500
        if (-not (Get-NetTCPConnection -State Listen -LocalPort $port -ErrorAction SilentlyContinue)) { break }
    }
    Say "port $port released"
}

# 2) 重新拉起（与原启动方式一致：桌面那个 cmd 跑的就是 dsh web --port 19388）
Say "starting: dsh web --port $port  (cwd=$repo)"
$p = Start-Process -FilePath 'cmd.exe' `
        -ArgumentList '/c', "dsh web --port $port >> `"$log`" 2>&1" `
        -WorkingDirectory $repo -WindowStyle Hidden -PassThru
Say ("launcher pid={0}" -f $p.Id)

# 3) 等端口回来，写终局
$ok = $false
for ($i = 0; $i -lt 60; $i++) {
    Start-Sleep -Milliseconds 500
    if (Get-NetTCPConnection -State Listen -LocalPort $port -ErrorAction SilentlyContinue) { $ok = $true; break }
}
if ($ok) { Say "UP — http://127.0.0.1:$port is listening again" }
else     { Say "DOWN — host did not come back within 30s; you can start it by hand: .\`.启动-WorkBuddy模型.cmd" }
Say "=== done ==="
