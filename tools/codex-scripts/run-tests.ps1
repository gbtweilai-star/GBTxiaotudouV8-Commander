# run-tests.ps1
#
# 跑本仓的测试 —— **按框架自己文档写明的姿势**（GBK 控制台友好、口径固定、store 隔离）。
#
# ## 为什么需要这个包装脚本（而不是一个仓根 conftest.py）
#
# 本仓的 store 层在 `gbt_allinone` 被导入时就绑定 STORE_DIR，之后的赋值**已经太晚**：
#   · 一个**仓根 `conftest.py`** 确实能赶在导入之前赋值 —— 但它会被 pytest 自动 import，
#     于是它**必然出现在"进程内依赖面"里**，而它又不在包里
#     ⇒ 破坏框架的不变式「面 ⊆ 包」，`test_dependency_face.py` 当场判红（我实测过）。
#   · `gbt_allinone/tests/conftest.py` 也不行：Python 会**先 import 父包**
#     `gbt_allinone.tests.__init__`，它在第 29 行就检查 store 并 `RuntimeError` 拒绝 ——
#     我的模块级赋值根本没机会执行（也实测过）。
#   · 框架 `injected_dirs()` 只认「`PYTHONPATH` 注入 **且** 落在 `SKIP_DIRS` 里」的目录，
#     仓根两条都不满足 ⇒ **框架没有接受仓根 conftest 的机制**。
#
# ⇒ 正解就是框架报错信息里的**解法①**：**起 Python 之前**把环境变量设好。
#   本脚本是 PowerShell 文件，**永远不会被 Python 导入** ⇒ 不进依赖面、不碰框架判据。
#
# 用法：
#   pwsh -NoProfile -File tools/codex-scripts/run-tests.ps1                     # 全量
#   pwsh -NoProfile -File tools/codex-scripts/run-tests.ps1 -Target gbt_allinone/tests/test_dependency_face.py
#   pwsh -NoProfile -File tools/codex-scripts/run-tests.ps1 -Extra '-k','face'
#   pwsh -NoProfile -File tools/codex-scripts/run-tests.ps1 -Show 30            # 只看尾部 30 行

param(
  [string]$Target = 'gbt_allinone/tests',
  [string[]]$Extra = @(),
  [int]$Show = 25,
  [string]$StoreDir = ''
)

$ErrorActionPreference = 'Continue'
if (-not $StoreDir) { $StoreDir = Join-Path $env:TEMP 'gbt-pytest-store' }

# ── 框架文档的解法①：起 Python 之前设好，且不覆盖调用者已设的值 ──────────────
if (-not $env:GBT_STORE_DIR) {
  New-Item -ItemType Directory -Force -Path $StoreDir | Out-Null
  $env:GBT_STORE_DIR = $StoreDir
}
# ── 输出落文件：不再用管道截尾（那会把 pytest 的汇总行冲掉，我踩过）─────────
$out = Join-Path $env:TEMP 'gbt-run-tests.out.txt'
$bt = Join-Path $env:TEMP 'gbt-pytest-basetemp'

Write-Output ("GBT_STORE_DIR = " + $env:GBT_STORE_DIR)
Write-Output ("target        = " + $Target)
Write-Output ("输出落盘      = " + $out)

py -3.14 -m pytest $Target -q --no-header -p no:cacheprovider `
  --basetemp=$bt -rf --tb=short @Extra *> $out
$rc = $LASTEXITCODE

Write-Output ''
Write-Output ("---- 尾部 " + $Show + " 行（完整输出见上面那个文件）----")
Get-Content $out -Tail $Show | ForEach-Object { '  ' + $_ }
Write-Output ("pytest 退出码 = " + $rc)
exit $rc
