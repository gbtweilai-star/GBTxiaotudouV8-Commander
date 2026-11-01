# 触手主干 · 一键安装/上线（Windows）
#
# 主人令（2026-11-01）：「项目落地了？」——这份脚本就是"落地"的那一步：
#   查权重 → 缺就下分片并合并 → 校验 sha256 → 写 ACTIVE.json → 起引擎 → 自检 → 可选守护/自启
#
# 用法（在仓库根执行）：
#   powershell -ExecutionPolicy Bypass -File tools\commander-install.ps1
#   powershell -ExecutionPolicy Bypass -File tools\commander-install.ps1 -WithSupervisor
#   powershell -ExecutionPolicy Bypass -File tools\commander-install.ps1 -Autostart
#
# 三条纪律：
#   1) 幂等：权重在就跳过下载；引擎活着就复用；重复跑不会重复装。
#   2) 不静默：每一步打印读数；下载/合并/校验失败就停，并说清缺什么。
#   3) 不假报：自启注册不成就**如实说没做成**（第一版曾 Out-Null 掉 schtasks 的错误、打印"已注册"，
#      那是假报，已修）。不加 -Autostart 不碰系统设置。
param(
    [switch]$Force,
    [switch]$WithSupervisor,
    [switch]$Autostart
)
$ErrorActionPreference = "Stop"
$Repo = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $Repo

function Section($t) { Write-Host "`n== $t ==" -ForegroundColor Cyan }

$Rel = "https://github.com/gbtweilai-star/GBTxiaotudouV8-Commander/releases/download/v1.0.0"
$Wd = Join-Path $Repo "state\weights"
$Gguf = Join-Path $Wd "gbt-v8-v82-q5_0.gguf"
$Sha = "983f19a66928aa6927a6b42ae4ab28ac0889e015788e4553303df01c0fcd262f"
New-Item -ItemType Directory -Force -Path $Wd | Out-Null

Section "1/6 Python"
$py = Get-Command python -ErrorAction SilentlyContinue
if (-not $py) {
    $emb = Join-Path (Split-Path -Parent $Repo) "pyembed\python.exe"
    if (Test-Path $emb) { $py = Get-Item $emb } else { throw "找不到 python（也没有 embeddable 的 pyembed\python.exe）" }
}
Write-Host "python: $($py.Source)"

Section "2/6 权重"
if ((Test-Path $Gguf) -and -not $Force) {
    $gb = [math]::Round((Get-Item $Gguf).Length / 1GB, 2)
    Write-Host "已存在 $Gguf  ($gb GB)，跳过下载"
} else {
    $parts = @()
    for ($i = 1; $i -le 9; $i++) {
        $name = "gbt-v8-v82-q5_0.gguf.part$i"
        $dst = Join-Path $Wd $name
        if (-not (Test-Path $dst)) {
            Write-Host "  下载 $name ..."
            try { Invoke-WebRequest -Uri "$Rel/$name" -OutFile $dst -UseBasicParsing }
            catch { Remove-Item $dst -ErrorAction SilentlyContinue; break }
        }
        $parts += $dst
    }
    if ($parts.Count -eq 0) { throw "一个分片都没下到（网络或 Release 不可达）" }
    Write-Host "  合并 $($parts.Count) 片 ..."
    $out = [IO.File]::Create($Gguf)
    try { foreach ($p in $parts) { $fs = [IO.File]::OpenRead($p); $fs.CopyTo($out); $fs.Close() } }
    finally { $out.Close() }
    foreach ($p in $parts) { Remove-Item $p -Force -ErrorAction SilentlyContinue }
    Write-Host "  已合并 → $Gguf"
}

Section "3/6 sha256 校验"
$h = (Get-FileHash $Gguf -Algorithm SHA256).Hash.ToLower()
if ($h -ne $Sha) { throw "sha256 不匹配：拿到 $h，期望 $Sha —— 拒绝使用" }
Write-Host "sha256 OK（与 WEIGHTS.md 公布值逐字相同）"

Section "4/6 ACTIVE.json 指针"
$active = Join-Path $Wd "ACTIVE.json"
@{
    active_artifact = "gbt-v8-v82-q5_0.gguf"
    model           = "gbt-v8-v82-q5_0.gguf"
    sha256          = $Sha
    size_gb         = [math]::Round((Get-Item $Gguf).Length / 1GB, 2)
    installed_at    = (Get-Date -Format "yyyy-MM-ddTHH:mm:ss")
    lane            = "selfhost / commander"
} | ConvertTo-Json | Set-Content -Path $active -Encoding utf8
Write-Host "已写 $active"

Section "5/6 起引擎（幂等）"
$health = $null
try { $health = Invoke-WebRequest "http://127.0.0.1:8792/health" -UseBasicParsing -TimeoutSec 3 } catch {}
if ($health -and $health.StatusCode -eq 200) {
    Write-Host "引擎已在跑，复用"
} else {
    & $py.Source -X utf8 -c "import sys;sys.path.insert(0,'.');from gbt_allinone.tentacle import commander as C;r=C.start();print({k:r.get(k) for k in ('ok','already','pid','boot_s','stage')})"
    if ($LASTEXITCODE -ne 0) { throw "引擎起失败，看 state/commander/engine.log" }
}

Section "6/6 自检"
& $py.Source -X utf8 -c "import sys;sys.path.insert(0,'.');import gbt_allinone as g,json;r=g.run_task('pulse_core',{'op':'verify'},probe=True)['gbt_result']['result'];print('pulse_core:', 'PASS' if r['ok'] else 'FAIL', r['failed']);q=g.run_task('cap_self',{'op':'verify'},probe=True)['gbt_result']['result'];print('cap_self :', 'PASS' if q['ok'] else 'FAIL', q['counts'])"

if ($WithSupervisor) {
    Section "守护"
    Start-Process -FilePath "powershell" -ArgumentList @("-ExecutionPolicy", "Bypass", "-File", (Join-Path $Repo "tools\commander-supervisor.ps1")) -WorkingDirectory $Repo -WindowStyle Minimized
    Write-Host "守护已起（日志 state\commander\supervisor.log）"
}

if ($Autostart) {
    Section "登录自启（计划任务）"
    # 三次踩坑记在这（别再走回头路）：
    #   1) `schtasks /TR` 处理不了带空格的路径（实测 ERROR: Invalid argument/option - 'E14'）；
    #   2) 第一版把它的输出 Out-Null 了 ⇒ 明明失败还打印"已注册"（假报，本仓最忌）；
    #   3) 沙箱里 CIM 被拒、schtasks 也够不到沙箱临时目录。
    # 现在：能注册就注册并**查回来**再报；注册不了就**如实说没做成**，并给手动办法。
    $script = Join-Path $Repo "tools\commander-supervisor.ps1"
    $registered = $false
    try {
        $action = New-ScheduledTaskAction -Execute "powershell.exe" -Argument ("-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File `"{0}`"" -f $script)
        $trigger = New-ScheduledTaskTrigger -AtLogOn
        $settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1)
        Register-ScheduledTask -TaskName "GBT-Commander-Supervisor" -Action $action -Trigger $trigger -Settings $settings -Description "GBT小土豆V8 · 触手主干引擎守护" -Force | Out-Null
        $t = Get-ScheduledTask -TaskName "GBT-Commander-Supervisor" -ErrorAction Stop
        Write-Host "已注册：$($t.TaskName) · 状态 $($t.State)"
        $registered = $true
    } catch {
        Write-Host "未能注册（原因：$($_.Exception.Message)）" -ForegroundColor Yellow
    }
    if (-not $registered) {
        Write-Host "自启没做成 —— 不写假成功。手动两种办法（二选一）："
        Write-Host "  A) 每次登录后手动起守护（最简单，现在就能用）："
        Write-Host "     powershell -NoProfile -ExecutionPolicy Bypass -File `"$script`""
        Write-Host "  B) 不用管理员的自启：把下面这条路做成快捷方式，丢进「启动」文件夹（Win+R 输入 shell:startup）："
        Write-Host "     目标：powershell.exe -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File `"$script`""
        Write-Host "  C) 有管理员权限时：在管理员终端里跑一次 tools\commander-install.ps1 -Autostart"
    }
}

Write-Host "`n落地完成。" -ForegroundColor Green
