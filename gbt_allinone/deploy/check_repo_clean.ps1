# =============================================================================
#  check_repo_clean.ps1 — 仓库洁净检查(发现"非本项目文件"早告警)
#  背景: 其他 AutoClaw agent 会话可能把本目录当工作目录, 其启动文件会落进来。
#  用法:  powershell -File gbt_allinone\deploy\check_repo_clean.ps1 [-Quiet]
#  退出码: 0=干净  1=发现外来文件
# =============================================================================
[CmdletBinding()]
param([switch]$Quiet)
$root = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$known = @(
    'AGENTS.md', 'JURISDICTION.md', 'REMINDER.md',
    '.legal-proxy-capability.json', '.jw-proxy-capability.json', '.tyc-proxy-capability.json',
    'config\mcporter.json'
)
$found = @()
foreach ($f in $known) { $p = Join-Path $root $f; if (Test-Path -LiteralPath $p) { $found += $f } }
if (Test-Path -LiteralPath (Join-Path $root '.opencode')) { $found += '.opencode\' }
$mine = @('AGENTS.md','SOUL.md','IDENTITY.md','MEMORY.md','USER.md','TOOLS.md','HEARTBEAT.md')
if ($found.Count -eq 0) { if (-not $Quiet) { Write-Host '[gbt-guard] 仓库干净: 未发现外来文件' -ForegroundColor Green }; exit 0 }
Write-Host ('[gbt-guard] 发现 ' + $found.Count + ' 个疑似外来文件(非本项目):') -ForegroundColor Yellow
$found | ForEach-Object { Write-Host ('   - ' + $_) }
Write-Host '[gbt-guard] 这些通常来自其它 agent 会话把本目录当工作目录; 已在 .gitignore 隔离, 不影响本项目。' -ForegroundColor Yellow
exit 1