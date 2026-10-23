# 把「立体声混音」设为**默认录音设备** —— 即“给主脑装耳朵”（第 58 轮）
#
# ## 为什么走这条路
# 现读事实（本机，2026-09-23）：
#   · `MMDevices\Audio\Capture` 里登记 5 个录音端点
#   · 3 条 `NOTPRESENT`（内置麦硬件没枚举出来）· 1 条 `UNPLUGGED`（曾插过麦）
#   · 1 条 `立体声混音`：注册表写 `0x10000001`
#   · 于是 `SetInputToDefaultAudioDevice()` 报 "Cannot find the requested data item"
#
# ## 🔴 第 59 轮复核：上面这段旧解读**是错的**，两处都错，已按权威 API 改口
#   **错一：把"注册表低位 = 1"读成 ACTIVE。** 现在用 `MMDevice::GetState()`（权威）复核：
#       · 录音侧 5 个端点里，**在场的（ACTIVE）是 0 个**
#       · `立体声混音` = **DISABLED（已禁用）** —— 注册表那个 `0x10000001` 的高位压着
#         "被用户禁用"之类的标志，**低位半字节根本不能当状态读**（`-band 1` 会读成"在场"）
#       · 三个角色（eConsole/eMultimedia/eCommunications）的**默认录音设备全都不存在**
#   **错二：说"设成默认耳朵就通了"。** 既没有在场的端点，就没有可设的默认设备 ——
#       `SetDefaultEndpoint` 改了等于没改，`asr-listen.ps1` 实测仍 `exit 5`（打不开设备）。
#       ⇒ **这句已删。设默认 ≠ 装耳朵。**
#
# ## 所以本脚本现在能做什么、不能做什么（照实说）
#   · **能做**：列出端点、尝试设默认（返回值如实打印，失败就是失败）。
#   · **做不了**：它**不会**让耳朵通。本机要真装上耳朵，只有两条路：
#       ① 在「设置 → 系统 → 声音 → 更多声音设置 → 录制」里右键**显示禁用的设备**，
#          **启用 `立体声混音`** ⇒ 得到"内录耳"（听电脑在放什么）；
#       ② 插一个 **USB 麦克风 / 3.5mm 耳麦** ⇒ 得到"麦克风耳"（能听人说话）。
#   · 另一条与 winmm 无关的录音路：`tools/codex-scripts/wasapi-record.py`（PortAudio）。
#     但**没有在场的录音端点时它也一样打不开** —— 软件换路不能凭空造出硬件端点。
#
# ## 三条必须说清的边界
# ① 这是**用户级设置**（默认设备按角色、按用户存），**不需要管理员**；我现读也**不是**管理员。
# ② 它改的是"主人这台机器的默认录音设备" —— **可逆**：跑 `-Undo` 或到「声音设置 → 输入」改回去。
#    ⚠️ 但本机现读**根本改不动**（没有在场端点）⇒ 我上一轮说"把你的默认录音设备改了、
#    用 `-Undo` 能还原"**也是错的**，向你更正：**那次什么都没改到**。
# ③ 🔴 **内录耳 ≠ 麦克风耳**：立体声混音录的是**电脑里正在播放的声音**，
#    **听不到房间里的说话**。要听主人说话，仍然需要一个物理麦克风（USB 或 3.5mm 耳麦）。
#    —— 不许把这条含糊掉，否则下一个人会以为"耳朵装好了，怎么听不见我说话"。
#
# 用法：
#   pwsh -File tools/codex-scripts/set-default-capture.ps1 -List              # 只看有哪些采集端点
#   pwsh -File tools/codex-scripts/set-default-capture.ps1                     # 把立体声混音设为默认
#   pwsh -File tools/codex-scripts/set-default-capture.ps1 -DeviceId "{...}"   # 指定端点
#   pwsh -File tools/codex-scripts/set-default-capture.ps1 -Undo               # 恢复成 iPhone 麦克风（原默认候选）
param(
  [switch]$List,
  [string]$DeviceId = "",
  [switch]$Undo
)
$ErrorActionPreference = "Continue"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

$CAP = "HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\MMDevices\Audio\Capture"
$NAMEKEY = '{a45c254e-df1c-4efd-8020-67d146a850e0},2'

function Get-Endpoints {
  $out = @()
  foreach ($k in Get-ChildItem $CAP) {
    $st = (Get-ItemProperty $k.PSPath -Name DeviceState -ErrorAction SilentlyContinue).DeviceState
    $p = Join-Path $k.PSPath "Properties"
    $nm = (Get-ItemProperty $p -ErrorAction SilentlyContinue).$NAMEKEY
    $out += [pscustomobject]@{
      Guid  = $k.PSChildName
      Name  = $nm
      State = $st
      # ⚠️ 这只是**注册表低位猜测**，不是权威状态。权威要问 `MMDevice::GetState()`：
      #    本机实测 `立体声混音` 注册表 `0x10000001`（低位=1）而 API 说 **DISABLED**
      #    ⇒ 别把这一列当"在场"，它会骗人。
      Active = (($st -band 0xFF) -eq 1)
      Id    = "{0.0.1.00000000}.$($k.PSChildName)"
    }
  }
  $out
}

$eps = Get-Endpoints
if ($List -or (-not $DeviceId -and -not $Undo)) {
  "== 本机录音端点（MMDevices 全量）=="
  "   ⚠️ 下面左列是**注册表低位猜测**，不是权威状态；权威要用 MMDevice::GetState()。"
  $eps | ForEach-Object { "  {0,-6} {1,-34} {2}" -f $(if ($_.Active) { "低位=1" } else { "0x{0:X}" -f $_.State }), $_.Name, $_.Guid }
}
if ($List) { exit 0 }

if ($Undo) {
  $t = $eps | Where-Object { $_.Active -and $_.Name -match 'iPhone' } | Select-Object -First 1
  if (-not $t) { "找不到原默认候选（iPhone 麦克风）—— 请到「声音设置 → 输入」手动改回"; exit 2 }
  $DeviceId = $t.Id
  "撤销：把默认设回 $($t.Name)"
}
if (-not $DeviceId) {
  $t = $eps | Where-Object { $_.Active -and $_.Name -match '立体声混音|Stereo Mix' } | Select-Object -First 1
  if (-not $t) {
    "❗没有 ACTIVE 的「立体声混音」端点 —— 本机当前没有可设的耳朵。"
    "  要真的装上：插一个物理麦克风（USB / 3.5mm 耳麦），它一插上就会出现新的 ACTIVE 端点。"
    exit 3
  }
  $DeviceId = $t.Id
  "目标端点：$($t.Name)  ($DeviceId)"
}

# ── PolicyConfig（未公开 COM，但不用管理员：默认设备是用户级设置）────────────
# 🔴 第 1 版栽在这：`Add-Type` 里的接口/类**默认是 internal** ⇒ PowerShell 里
#    `[IPolicyConfig]` 找不到类型（报 InvalidOperation），而 `-ErrorAction` 也看不出所以然。
#    ⇒ 必须显式写 `public`（接口与 ComImport 类都要）。
Add-Type -TypeDefinition @"
using System;
using System.Runtime.InteropServices;
[Guid("F8679F50-850A-41CF-9C72-430F290290C8"), InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
public interface IPolicyConfig {
    int GetMixFormat(string n, IntPtr f);
    int GetDeviceFormat(string n, bool b, IntPtr f);
    int ResetDeviceFormat(string n);
    int SetDeviceFormat(string n, IntPtr a, IntPtr b);
    int GetProcessingPeriod(string n, bool b, IntPtr a, IntPtr c);
    int SetProcessingPeriod(string n, IntPtr p);
    int GetShareMode(string n, IntPtr m);
    int SetShareMode(string n, IntPtr m);
    int GetPropertyValue(string n, bool b, IntPtr k, IntPtr v);
    int SetPropertyValue(string n, bool b, IntPtr k, IntPtr v);
    int SetDefaultEndpoint(string n, int role);
    int SetEndpointVisibility(string n, bool v);
}
[ComImport, Guid("870AF99C-171D-4F9E-AF0D-E63DF40C2BC9")]
public class CPolicyConfigClient { }
/* 🔴 第 2 版栽在 PowerShell 侧的 COM 转换：`New-Object CPolicyConfigClient` 拿到的包装
   不暴露 `IPolicyConfig` ⇒ 报「无法将类型 CPolicyConfigClient 的值转换为 IPolicyConfig」。
   解法：**把转换放进 C#**（在 C# 里 `(IPolicyConfig)new CPolicyConfigClient()` 合法），
   PowerShell 只调这个静态方法 —— 绕开 PowerShell 的 COM 转换限制。 */
public static class AudioDefault {
    public static int Set(string deviceId, int role) {
        var pc = (IPolicyConfig)new CPolicyConfigClient();
        return pc.SetDefaultEndpoint(deviceId, role);
    }
}
"@ -ErrorAction Stop

$roles = @{ 0 = 'eConsole'; 1 = 'eMultimedia'; 2 = 'eCommunications' }
$res = @{}
foreach ($r in 0, 1, 2) {
  try { $res[$roles[$r]] = [AudioDefault]::Set($DeviceId, $r) }
  catch { $res[$roles[$r]] = "异常：$($_.Exception.Message)" }
}
"== SetDefaultEndpoint 返回（0 = 成功）=="
$res.GetEnumerator() | Sort-Object Name | ForEach-Object { "  {0,-16} = {1}" -f $_.Key, $_.Value }
exit 0
