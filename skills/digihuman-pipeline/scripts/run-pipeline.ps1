# 数字人流水线 · 一键编排（GBT 口径）
#
# 用法：
#   pwsh -File run-pipeline.ps1 -Stage all  -Ref "C:\path\ref.png" -Name mychar
#   pwsh -File run-pipeline.ps1 -Stage tpose -Ref "C:\path\ref.png" -Name mychar
#   pwsh -File run-pipeline.ps1 -Stage render -Name mychar          # 用已存在的产物渲染
#   pwsh -File run-pipeline.ps1 -Stage all -Ref ... -DryRun       # 只打印命令
#
# 可用阶段：all | gen | tpose | model | decimate | rig | weight | anim | render | gate
# 每阶段结束打印**读数**；关键阶段不达标即中止（不产生半成品）。

param(
  [string]$Stage = "all",
  [string]$Ref,          # 注意：不要用 -Input，那是 PowerShell 自动变量
  [string]$Name = "char",
  [string]$Workspace = "C:\Users\ADMIN\Desktop\GBT小土豆V8",
  [switch]$DryRun
)

$ErrorActionPreference = 'Continue'
$OutputEncoding = [Console]::OutputEncoding = [Text.Encoding]::UTF8
$env:PYTHONIOENCODING = 'utf-8'

$TOOLS   = Join-Path $Workspace 'tools\codex-scripts'
$DH      = Join-Path $Workspace 'holo_pet\assets\digital-human'
$RAW     = Join-Path $DH "raw\$Name"
$PY_IMG  = 'C:\Python310\python.exe'          # 图像/数值（PIL/numpy/cv2）
$PY_WEB  = 'python'                            # Playwright（3.12）
$TRIPO   = Join-Path $env:APPDATA 'npm\tripo.cmd'
$SERVER  = Join-Path $Workspace 'plugins\gbt-master\tools\serve-digital-human.mjs'

$TPOSE_PROMPT = 'full body T-pose reference sheet of the same character: arms extended horizontally straight out to both sides at shoulder height, legs straight and shoulder-width apart, standing upright, facing the camera directly, no accessories in hands, plain pure white background, symmetric, entire body visible head to toe, studio lighting, photorealistic'

New-Item -ItemType Directory -Force -Path $RAW | Out-Null

function Say($msg)  { Write-Host "`n=== $msg ===" -ForegroundColor Cyan }
function Info($msg) { Write-Host "  $msg" }
function Run($cmd) {
  Info "→ $cmd"
  if ($DryRun) { return 0 }
  Invoke-Expression $cmd 2>&1 | ForEach-Object { "    $_" }
  return $LASTEXITCODE
}
function Need($path, $what) {
  if (-not (Test-Path $path)) { Write-Host "  ✗ 缺少 $what：$path" -ForegroundColor Red; exit 1 }
  Info "✓ $what 就绪"
}
function Want($cond, $msg) {
  if ($cond) { Info "✓ $msg" } else { Write-Host "  ✗ $msg —— 停下来，不带病往下走" -ForegroundColor Red; exit 1 }
}

# ── 阶段实现 ──────────────────────────────────────────────────────────────
function Stage-Gen {
  Say "[1/9] 图生网格 + 贴图"
  Need $Ref '参考图'
  $out = Join-Path $RAW 'gen'
  Run "& '$TRIPO' make '$Ref' --then texture -o '$out' --json --yes --no-open --name '$Name-gen'"
  $glb = Get-ChildItem $out -Recurse -Filter 'model.glb' -ErrorAction SilentlyContinue | Sort-Object LastWriteTime -Desc | Select-Object -First 1
  if (-not $DryRun) { Want ($null -ne $glb) '产出 model.glb' ; Info "  文件: $($glb.FullName)"; Info "  大小: $([math]::Round($glb.Length/1MB,2)) MB" }
  return $glb
}

function Stage-Tpose($srcImg) {
  Say "[2/9] 转 T-pose（五条判据：水平双臂/直立双腿/正面全身/无遮挡物/白底）"
  $src = if ($srcImg) { $srcImg } else { $Ref }
  Need $src '待转姿势的参考图'
  $out = Join-Path $RAW 'tpose'
  Run "& '$TRIPO' generate image-to-image '$src' --prompt `"$TPOSE_PROMPT`" -o '$out' --json --yes --no-open --name '$Name-tpose'"
  $img = Get-ChildItem $out -Recurse -Include 'generated_image.png','preview.png' -ErrorAction SilentlyContinue | Sort-Object LastWriteTime -Desc | Select-Object -First 1
  if (-not $DryRun -and $img) {
    $norm = Join-Path $RAW 'tpose\T-pose参考-规范化.png'
    Run "& '$PY_IMG' -X utf8 '$TOOLS\normalize-image.py' '$($img.FullName)' '$norm'"
    Info "  ⚠ 必做人工复核：打开 $norm，五条判据全过才继续（可用 shot-glb 的 view-glb.html 直接看）"
    return $norm
  }
}

function Stage-Model($tposeImg) {
  Say "[3/9] T-pose 建模 + 贴图（高保真档）"
  $src = if ($tposeImg) { $tposeImg } else { Join-Path $RAW 'tpose\T-pose参考-规范化.png' }
  Need $src 'T-pose 参考图'
  $out = Join-Path $RAW 'model'
  Run "& '$TRIPO' make '$src' --then texture -o '$out' --json --yes --no-open --name '$Name-model'"
  $glb = Get-ChildItem $out -Recurse -Filter 'model.glb' -ErrorAction SilentlyContinue | Sort-Object LastWriteTime -Desc | Select-Object -First 1
  if (-not $DryRun) {
    Want ($null -ne $glb) '产出高模 model.glb'
    Run "& '$PY_IMG' -X utf8 '$TOOLS\rig-gate-check.py' '$($glb.FullName)'"   # 顶点量读数（无骨架时会提示）
  }
  return $glb
}

function Stage-Decimate {
  Say "[4/9] 减面（1 万面）+ 转 FBX（Mixamo/实时可用）"
  $taskFile = Join-Path $RAW 'gen\task.txt'
  if (Test-Path $taskFile) { $task = (Get-Content $taskFile -Raw).Trim() } else { Write-Host "  ⚠ 没有记录 task id：请把上一步输出的 task_id 写入 $taskFile" -ForegroundColor Yellow; if (-not $DryRun) { exit 1 } }
  $out = Join-Path $RAW 'mixed'
  Run "& '$TRIPO' make '$task' --then 'decimate:10000,convert:fbx' -o '$out' --json --yes --no-open --name '$Name-low'"
  $fbx = Get-ChildItem $out -Recurse -Filter '*.fbx' -ErrorAction SilentlyContinue | Sort-Object LastWriteTime -Desc | Select-Object -First 1
  if (-not $DryRun -and $fbx) { Info "  FBX: $($fbx.FullName) · $([math]::Round($fbx.Length/1MB,2)) MB" }
  return $fbx
}

function Stage-Rig($lowGlb) {
  Say "[5/9] 量骨架（22 关节，吸附网格实体）"
  $src = if ($lowGlb) { $lowGlb } else { Join-Path $RAW 'mixed\model.glb' }
  Need $src '低模网格'
  $r = Run "& '$PY_IMG' -X utf8 '$TOOLS\autorig-skeleton.py' '$src'"
  Want ($r -eq 0) '骨架提取成功（看图：render/绑骨-骨架落在实体上.png 落在身体上）'
}

function Stage-Weight {
  Say "[6/9] 算权重 + 导出绑骨 GLB + 姿态测试"
  $r = Run "& '$PY_IMG' -X utf8 '$TOOLS\autorig-skin.py'"
  Want ($r -eq 0) '权重与导出成功（权重和须恒 1.0000）'
}

function Stage-Gate {
  Say "[7/9] 门限四条复核"
  $glb = Join-Path $DH 'raw\rig\model-rigged.glb'
  Need $glb '绑骨 GLB'
  $r = Run "& '$PY_IMG' -X utf8 '$TOOLS\rig-gate-check.py' '$glb'"
  Want ($r -eq 0) '四条门限通过（关节≥20 / 骨名可映射 / 绑定姿势 T / 权重齐）'
  Run "& '$PY_IMG' -X utf8 '$TOOLS\validate-glb.py' '$glb'"
}

function Stage-Anim {
  Say "[8/9] idle + walk 动画烘焙（循环必须闭合）"
  $r = Run "& '$PY_IMG' -X utf8 '$TOOLS\anim-make.py'"
  Want ($r -eq 0) '动画烘焙成功（循环闭合误差须 ≈0）'
}

function Stage-Render {
  Say "[9/9] 棚拍渲染 + 客观读数"
  if (-not $DryRun) {                       # 空跑不得有任何副作用（不启服务）
    $job = Start-Job -ScriptBlock { param($s) node $s } -ArgumentList $SERVER
    Start-Sleep -Seconds 3
    $up = (Test-NetConnection -ComputerName 127.0.0.1 -Port 8788 -WarningAction SilentlyContinue).TcpTestSucceeded
    Want $up '本地服务 8788 已就绪'
  }
  $glbHi = Join-Path $DH 'raw\rig\model-rigged-hi.glb'
  $glb   = Join-Path $DH 'raw\rig\model-rigged.glb'
  $target = if (Test-Path $glbHi) { $glbHi } else { $glb }
  Run "& '$PY_WEB' '$TOOLS\shot-glb.py' '/holo_pet/assets/digital-human/raw/rig/model-rigged.glb' '低模-转正.png' '-1.5708'"
  Run "& '$PY_WEB' '$TOOLS\shot-glb.py' '/holo_pet/assets/digital-human/raw/rig/model-rigged.glb' '低模-脸.png' '-1.5708' 'head' 'ss=3&beauty=1'"
  $animGlb = Join-Path $DH 'raw\rig\model-rigged-anim.glb'
  if (Test-Path $animGlb) {
    Run "& '$PY_WEB' '$TOOLS\shot-glb.py' '/holo_pet/assets/digital-human/raw/rig/model-rigged-anim.glb' '动画条-walk.png' '-1.5708' '' 'clip=walk&strip=8&inplace=1'"
    Run "& '$PY_WEB' '$TOOLS\shot-glb.py' '/holo_pet/assets/digital-human/raw/rig/model-rigged-anim.glb' '动画条-idle.png' '-1.5708' '' 'clip=idle&strip=6&inplace=1'"
  }
  Run "& '$PY_IMG' -X utf8 '$TOOLS\measure-clarity.py' 'render\低模-脸.png'"
  if (-not $DryRun) {
    # 四步收尾：认端口 → 认命令行 → 杀 → 复核
    $owner = (Get-NetTCPConnection -State Listen -LocalPort 8788 -ErrorAction SilentlyContinue | Select-Object -First 1).OwningProcess
    if ($owner) {
      $proc = Get-CimInstance Win32_Process -Filter "ProcessId=$owner"
      if ($proc.CommandLine -match 'serve-digital-human') { Stop-Process -Id $owner -Force; Start-Sleep -Seconds 2 }
    }
    Info "  8788 已收尾: $(-not (Test-NetConnection -ComputerName 127.0.0.1 -Port 8788 -WarningAction SilentlyContinue).TcpTestSucceeded)"
  }
}

# ── 调度 ──────────────────────────────────────────────────────────────────
Say "数字人流水线 · 阶段=$Stage · 角色=$Name"
Info "工作区: $Workspace"
Info "产物目录: $RAW"
if ($DryRun) { Info "** DryRun：只打印命令，不执行 **" }

switch ($Stage) {
  'gen'      { Stage-Gen | Out-Null }
  'tpose'    { Stage-Tpose $null | Out-Null }
  'model'    { Stage-Model $null | Out-Null }
  'decimate' { Stage-Decimate | Out-Null }
  'rig'      { Stage-Rig $null }
  'weight'   { Stage-Weight }
  'anim'     { Stage-Anim }
  'gate'     { Stage-Gate }
  'render'   { Stage-Render }
  'all'      {
    Stage-Gen | Out-Null
    Stage-Tpose $null | Out-Null
    Stage-Model $null | Out-Null
    Stage-Decimate | Out-Null
    Stage-Rig $null
    Stage-Weight
    Stage-Gate
    Stage-Anim
    Stage-Render
  }
  default { Write-Host "未知阶段：$Stage" -ForegroundColor Red; exit 1 }
}

Say "完成"
Info "状态源记得更新：$DH\STATUS.json（读数 / 花费 / 缺口 / 下一步）"
