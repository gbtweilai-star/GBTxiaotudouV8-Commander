# =============================================================================
#  codex_key_env.ps1 — 从 DPAPI 保险箱解封上游密钥（DeepSeek · FreeLLMAPI）并注入当前会话环境
# -----------------------------------------------------------------------------
#  设计要点：
#    * 明文只在内存里走一趟：读 DPAPI 文件 -> 解密 -> 写 $env: 变量，不落盘；
#    * 幂等：已经有值就不覆盖（外部显式指定的值优先，不搞静默改写）；
#    * 失败可见：解封失败会 Write-Warning，不装作没事发生。
#    * 多库：DeepSeek 与 FreeLLMAPI 各一个 DPAPI 文件、各自熵值，互不可解。
#
#  用法：
#    手动：   . gbt_allinone\deploy\codex_key_env.ps1
#    开机：   在 PowerShell profile 里 dot-source 本文件（见 install_codex_key_env.ps1）
#    启动器： codex-key-launch.ps1 会自动调用本文件
# =============================================================================

$ErrorActionPreference = 'Stop'

$VaultFile = 'C:\Users\ADMIN\Desktop\GBT小土豆V8\gbt_allinone\store\secrets\deepseek_api.dpapi'
$Entropy   = 'GBTxiaotudouV8:deepseek:v1'

# ---- FreeLLMAPI 统一网关 -----------------------------------------------------
# Codex 终端 provider=freellmapi 读的是 FREELLMAPI_API_KEY；config.toml 里只写 env_key，
# 密钥本体只存在下头这个 DPAPI 文件里。
$FllmVaultFile = 'C:\Users\ADMIN\Desktop\GBT小土豆V8\gbt_allinone\store\secrets\freellmapi_api.dpapi'
$FllmEntropy   = 'GBTxiaotudouV8:freellmapi:v1'

if (-not $env:FREELLMAPI_API_KEY) {
    if (-not (Test-Path -LiteralPath $FllmVaultFile)) {
        Write-Warning "FreeLLMAPI 密钥保险箱不存在：$FllmVaultFile（Codex 会报缺 FREELLMAPI_API_KEY）"
    } else {
        $fllmPlain = $null
        try {
            if (-not ('System.Security.Cryptography.ProtectedData' -as [type])) {
                Add-Type -AssemblyName System.Security -ErrorAction Stop
            }
            $fllmBlob = [IO.File]::ReadAllBytes($FllmVaultFile)
            $fllmPlain = [Security.Cryptography.ProtectedData]::Unprotect(
                $fllmBlob, [Text.Encoding]::UTF8.GetBytes($FllmEntropy),
                [Security.Cryptography.DataProtectionScope]::CurrentUser)
            $fllmKey = [Text.Encoding]::UTF8.GetString($fllmPlain).Trim()
            if ([string]::IsNullOrWhiteSpace($fllmKey)) {
                Write-Warning 'FreeLLMAPI 密钥解封为空，拒绝注入'
            } else {
                $env:FREELLMAPI_API_KEY = $fllmKey
            }
        } catch {
            Write-Warning "FreeLLMAPI 密钥解封失败：$($_.Exception.Message)"
        } finally {
            if ($fllmPlain) { [Array]::Clear($fllmPlain, 0, $fllmPlain.Length) }
        }
    }
}

if ($env:DEEPSEEK_API_KEY) {
    # 已有值：尊重现有环境，不再解封
    return
}

if (-not (Test-Path -LiteralPath $VaultFile)) {
    Write-Warning "DeepSeek 密钥保险箱不存在：$VaultFile（Codex 直连会缺 key）"
    return
}

try {
    if (-not ('System.Security.Cryptography.ProtectedData' -as [type])) {
        Add-Type -AssemblyName System.Security -ErrorAction Stop
    }
    $entropyBytes = [Text.Encoding]::UTF8.GetBytes($Entropy)
    $blob = [IO.File]::ReadAllBytes($VaultFile)
    $plain = [Security.Cryptography.ProtectedData]::Unprotect(
        $blob, $entropyBytes,
        [Security.Cryptography.DataProtectionScope]::CurrentUser)
    $key = [Text.Encoding]::UTF8.GetString($plain).Trim()
    if ([string]::IsNullOrWhiteSpace($key)) {
        Write-Warning 'DeepSeek 密钥解封为空，拒绝注入'
        return
    }
    $env:DEEPSEEK_API_KEY = $key
    $env:GBT_DEEPSEEK_KEY = $key
} catch {
    Write-Warning "DeepSeek 密钥解封失败：$($_.Exception.Message)"
} finally {
    if ($plain) { [Array]::Clear($plain, 0, $plain.Length) }
}
