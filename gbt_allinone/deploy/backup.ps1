# =============================================================================
#  backup.ps1 — gbt_wallet 数据根备份(master.enc + 全部账本/台账)
# -----------------------------------------------------------------------------
#  备份内容(存在才备, 缺失仅告警): master.enc(必需), state.json, invoices.json,
#    cursor.json, ledger.jsonl(append-only 审计/资金事件), users.json, otps.json,
#    sessions.json, orders.json, engine_tasks.json, receipts.json, bindings.json,
#    settlements.json, activations.json, invoice_user.json(发票->用户映射), scan.log
#
#  恢复步骤: 见 gbt_allinone/deploy/DEPLOY.md「密钥与备份策略 -> 恢复」。
#  安全须知:
#    * 备份里含助记词密文(master.enc)与全部账本; 拿到备份 + 口令 = 拿到资金。
#      故本脚本会 1) 收紧备份目录 ACL 2) 拒绝把备份放在数据根内 3) 提示异地/离线保存。
#    * 真正的恢复能力来自"离线助记词" —— 备份丢了也能凭助记词重建(见 DEPLOY.md)。
#
#  用法:
#    powershell -ExecutionPolicy Bypass -File gbt_allinone\deploy\backup.ps1
#    ... -DataDir D:\gbt\gbt_wallet -OutDir E:\backups\gbt -Keep 30 -Zip
#
#  退出码: 0=成功(含仅告警)  1=失败  2=钱包未初始化(无 master.enc)
# =============================================================================
[CmdletBinding()]
param(
    [string]$DataDir = '',
    [string]$OutDir = '',
    [int]$Keep = 0,
    [switch]$Zip,
    [switch]$DryRun
)

$ErrorActionPreference = 'Stop'
function Say($m) { Write-Host "[backup] $m" -ForegroundColor Cyan }
function Warn($m) { Write-Host "[backup] $m" -ForegroundColor Yellow }
function Fail($m, [int]$code = 1) { Write-Host "[backup] $m" -ForegroundColor Red; exit $code }

if (-not $DataDir) { if ($env:GBT_WALLET_DIR) { $DataDir = $env:GBT_WALLET_DIR } else { $DataDir = Join-Path $env:USERPROFILE '.gbt\gbt_wallet' } }
if (-not $OutDir) { if ($env:GBT_BACKUP_DIR) { $OutDir = $env:GBT_BACKUP_DIR } else { $OutDir = Join-Path $env:ProgramData 'gbt-wallet-backups' } }
if ($Keep -le 0) { if ($env:GBT_BACKUP_KEEP) { $Keep = [int]$env:GBT_BACKUP_KEEP } else { $Keep = 14 } }

$dataFull = [IO.Path]::GetFullPath($DataDir)
$outFull = [IO.Path]::GetFullPath($OutDir)
if (-not (Test-Path -LiteralPath $dataFull)) { Fail "数据根不存在: $dataFull" 2 }

# 备份不得落在数据根内部(否则数据根丢失时备份一起丢)
if ($outFull.TrimEnd('\') -eq $dataFull.TrimEnd('\') -or $outFull.StartsWith($dataFull.TrimEnd('\') + '\')) {
    Fail "备份目录不能位于数据根内部: $outFull ; 请换到独立卷/独立主机" 1
}
# 同卷告警(不是错误, 但要提醒异地)
$sameVolume = $false
try { $sameVolume = ([IO.Path]::GetPathRoot($outFull)).ToLower() -eq ([IO.Path]::GetPathRoot($dataFull)).ToLower() } catch { }
if ($sameVolume) { Warn "备份目录与数据根在同一卷($([IO.Path]::GetPathRoot($dataFull))) —— 建议再同步到异地/离线介质" }

$required = @('master.enc')
$optional = @('state.json', 'invoices.json', 'cursor.json', 'ledger.jsonl', 'users.json',
    'otps.json', 'sessions.json', 'orders.json', 'engine_tasks.json', 'receipts.json',
    'bindings.json', 'settlements.json', 'activations.json', 'invoice_user.json', 'scan.log')

$stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
$dest = Join-Path $outFull ("gbt-wallet-$stamp")

# ACL 收紧(用 .NET ACL 而不是 icacls: PS 5.1 会给含括号的参数补引号, icacls 会报"无效参数")
function Protect-BackupPath([string]$path) {
    try {
        $acl = Get-Acl -LiteralPath $path
        $acl.SetAccessRuleProtection($true, $false)              # 断开继承且不保留继承项
        foreach ($rule in @($acl.Access)) { [void]$acl.RemoveAccessRule($rule) }
        $inherit = [Security.AccessControl.InheritanceFlags]'ContainerInherit, ObjectInherit'
        $props = [Security.AccessControl.PropagationFlags]::None
        $sids = @('S-1-5-18', 'S-1-5-32-544')                    # SYSTEM / Administrators(用 SID 免语言差异)
        $sids += [string][Security.Principal.WindowsIdentity]::GetCurrent().User
        foreach ($sid in $sids) {
            $id = New-Object Security.Principal.SecurityIdentifier($sid)
            $rule = New-Object Security.AccessControl.FileSystemAccessRule(
                $id, 'FullControl', $inherit, $props, 'Allow')
            [void]$acl.AddAccessRule($rule)
        }
        Set-Acl -LiteralPath $path -AclObject $acl
        return $true
    } catch { return $false }
}

if (-not (Test-Path -LiteralPath (Join-Path $dataFull 'master.enc'))) {
    Fail "钱包未初始化(缺少 master.enc): $dataFull —— 无需备份; 请先 gbt_wallet.cli init 并离线备份助记词" 2
}

if ($DryRun) {
    Say "[DryRun] 数据根: $dataFull"
    Say "[DryRun] 目标  : $dest"
    Say "[DryRun] 保留份数: $Keep ; 压缩: $($Zip.IsPresent)"
    Say "[DryRun] 将备份: $((@($required) + @($optional)) -join ', ')"
    exit 0
}

if (-not (Test-Path -LiteralPath $dest)) { New-Item -ItemType Directory -Path $dest -Force | Out-Null }
# 先收紧目录 ACL: 之后拷贝进来的文件会继承这套收紧后的权限
if (Protect-BackupPath $dest) { Say '已收紧备份目录 ACL(继承已断开; 仅 SYSTEM/Administrators/当前用户)' }
else { Warn "备份目录 ACL 收紧失败, 请手工确认权限: $dest" }

$manifest = [ordered]@{
    schema        = 'gbt-wallet-backup/1'
    created_utc   = (Get-Date).ToUniversalTime().ToString('yyyy-MM-ddTHH:mm:ssZ')
    host          = $env:COMPUTERNAME
    user          = "$env:USERDOMAIN\$env:USERNAME"
    data_dir      = $dataFull
    app_version   = 'gbt_wallet 0.5.0'
    files         = @()
    missing       = @()
    warnings      = @()
}
$bytesTotal = 0
foreach ($name in (@($required) + @($optional))) {
    $src = Join-Path $dataFull $name
    if (-not (Test-Path -LiteralPath $src)) {
        $manifest.missing += $name
        continue
    }
    try {
        Copy-Item -LiteralPath $src -Destination (Join-Path $dest $name) -Force
        $hash = (Get-FileHash -LiteralPath $src -Algorithm SHA256).Hash
        $len = (Get-Item -LiteralPath $src).Length
        $bytesTotal += $len
        $manifest.files += [ordered]@{ name = $name; bytes = $len; sha256 = $hash }
    } catch {
        Fail "拷贝失败: $name -> $_" 1
    }
}

# 校验: master.enc 必须逐字节一致
$srcKey = Join-Path $dataFull 'master.enc'
$dstKey = Join-Path $dest 'master.enc'
if ((Get-FileHash -LiteralPath $srcKey -Algorithm SHA256).Hash -ne
    (Get-FileHash -LiteralPath $dstKey -Algorithm SHA256).Hash) {
    Fail 'master.enc 校验不一致, 备份不完整(请重试并检查磁盘)' 1
}
if ($manifest.missing.Count -gt 0) {
    $manifest.warnings += "缺失未备份: $($manifest.missing -join ', ') (通常是尚未产生该台账)"
}

$mc = $manifest | ConvertTo-Json -Depth 6
[System.IO.File]::WriteAllText((Join-Path $dest 'manifest.json'), $mc, (New-Object System.Text.UTF8Encoding($false)))

if ($Zip) {
    $zipPath = "$dest.zip"
    try {
        Compress-Archive -Path (Join-Path $dest '*') -DestinationPath $zipPath -Force
        Say "已压缩: $zipPath ($([math]::Round((Get-Item $zipPath).Length/1MB,2)) MB)"
    } catch { Warn "压缩失败(原始目录仍在): $_" }
}

# 轮转: 只保留最近 $Keep 份(目录与同名 zip 一起清理)
$all = @(Get-ChildItem -LiteralPath $outFull -Directory -Filter 'gbt-wallet-*' | Sort-Object Name -Descending)
if ($all.Count -gt $Keep) {
    foreach ($old in ($all | Select-Object -Skip $Keep)) {
        try {
            Remove-Item -LiteralPath $old.FullName -Recurse -Force
            $z = "$($old.FullName).zip"
            if (Test-Path -LiteralPath $z) { Remove-Item -LiteralPath $z -Force }
            Say "已清理过期备份: $($old.Name)"
        } catch { Warn "清理失败 $($old.Name): $_" }
    }
}

Say ("完成: {0} 个文件, {1:N2} MB -> {2}" -f $manifest.files.Count, ($bytesTotal / 1MB), $dest)
if ($manifest.missing.Count -gt 0) { Warn "注意: 有 $($manifest.missing.Count) 个文件不存在, 详见 manifest.json" }
Warn '关键提醒: master.enc 需要口令才能解密; 请确认离线助记词备份仍然可用(见 DEPLOY.md 恢复步骤)'
exit 0
