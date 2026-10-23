# -*- coding: utf-8 -*-
"""gen_corpus_v58 -- v57 逐字节不动 + **OS 结构知识 / 装机自检 / 自卫反控** 实战行。

主人令（2026-10-17）：
  · 「给她注入苹果手机结构知识安卓手机结构知识，电脑所有版本结构知识给她注入，
     安装上我们的大模型就自动自检一遍排除病毒木马等」
  · 「这些都要我们的大模型会啊」⇒ 不是框架会，是**模型自己答得出、做得到**。

来源：
  · `gbt_allinone/install_selfcheck.py`（本仓新位）的 OS 知识与检测口径（现读源码）
  · `sec_defenses` / `omni_plug`（counter_strike/counter_plan）现读行为
  · 公开、稳定的系统架构与安全检查常识（不调用在线杀毒、不编造专有细节）
纪律：v57 基础逐字节不动；只追加；manifest 记条数与来源。
"""
from __future__ import annotations
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / ".scratch" / "self_knowledge_v57.jsonl"
OUT = ROOT / ".scratch" / "self_knowledge_v58.jsonl"
MAN = ROOT / "state" / "train" / "corpus_v58_manifest.json"


def _os_rows() -> list:
    return [
        ("iPhone（iOS）的系统结构是怎么分层的？",
         "① 硬件 → ② 内核 **Darwin/XNU**（Mach 微内核 + BSD 层，XNU = Mach+BSD+IOKit）→ ③ 系统服务层"
         "（launchd 管进程、SpringBoard 是桌面/应用启动器、securityd 管钥匙串）→ ④ 框架层（Foundation/UIKit/"
         "SwiftUI、Metal）→ ⑤ App 层。App 跑在**沙盒**里：只能访问自己的容器（Documents/Library/tmp），"
         "跨 App 取数据必须经系统框架（如 UIDocumentPicker）或共享容器；越权靠 **entitlements** 申请，"
         "**代码签名 + 公证（notarization）**保证来源可信。"),
        ("iOS App 装到手机里是什么结构、签名怎么验？",
         "分发包装是 **IPA**（本质 zip）：`Payload/YourApp.app/` 内含可执行 Mach-O、`Info.plist`"
         "（bundle id、版本、权限用途描述 UsageDescription）、资源、`_CodeSignature/`、内嵌描述文件"
         "（开发/Ad Hoc/企业）或 App Store 签名。验签链：苹果根证书 → 开发者证书 → 描述文件 → 可执行哈希；"
         "企业签/超级签常被滥用 ⇒ 见到**陌生描述文件/未知开发者**要警惕。越狱机常见：Cydia/Sileo、"
         "ssh 22 端口、`/private/var/` 可写、绕过签名的 app —— 这些是**高风险信号**。"),
        ("iOS 上要检查哪些持久化/权限点（防后门）？",
         "① **配置描述文件（MDM/Configuration Profile）**：设置→通用→VPN与设备管理，陌生描述文件可改代理/装证书/远控；"
         "② 企业级信任证书；③ 后台刷新/定位/麦克风/相机/通讯录**隐私权限**被谁长期占用；"
         "④ 越狱痕迹（Cydia/Sileo、ssh、rootless 路径）；⑤ 陌生 VPN/代理；⑥ 屏幕使用时间/描述文件锁；"
         "⑦ 自签 App 的 profile 过期与来源。口径：**只读检查 + 人工确认**，不擅自删描述文件。"),
        ("安卓（Android）的系统结构是怎么分层的？",
         "① Linux 内核（驱动、电源、内存）→ ② **HAL**（硬件抽象）→ ③ 原生库（libc、ART 运行时）→ "
         "④ **Android Runtime（ART，跑 DEX/OAT）** + 系统服务（**system_server** 里 ActivityManager/"
         "PackageManager 等）→ ⑤ 框架层（Java/Kotlin API）→ ⑥ App。进程靠 **zygote** fork，"
         "跨进程用 **Binder IPC**，强制访问控制是 **SELinux**。App 沙盒 = 独立 uid + 私有数据目录；"
         "权限在 **AndroidManifest** 声明，危险权限要运行时授权。"),
        ("APK / AAB 结构是什么、装之前看什么？",
         "**APK** = zip：`AndroidManifest.xml`（包名、versionCode、**permissions**、四大组件 activity/service/"
         "receiver/provider 与 `android:exported`）、`classes.dex`（可多 dex）、`lib/<abi>/*.so`、`res/`、"
         "`META-INF/`（v1 签名）、APK Signature Scheme v2/v3（整包签名）。**AAB** 是上架包，由商店切分 APK。"
         "装前看：① 签名（是否同开发者/是否 debug 自签）；② 权限是否越界（无障碍/设备管理员/悬浮窗/读取短信/"
         "录音）；③ 有无陌生 `exported` 组件；④ 是否要求关闭 Play Protect。"),
        ("安卓上要检查哪些持久化/后门点？",
         "① **设备管理员**（Device Admin）与 **无障碍服务（Accessibility）**——后者能读屏/代点，是木马最爱；"
         "② 悬浮窗（SYSTEM_ALERT_WINDOW）与通知监听；③ 开机自启（BOOT_COMPLETED）/前台服务常驻；"
         "④ 陌生**输入法**与 **VPN/代理**；⑤ root 痕迹（Magisk/su、解锁 bootloader）；⑥ 开发者选项 + USB 调试常开；"
         "⑦ 安装来源（未知来源）；⑧ 可疑的 `provider/exported` 组件。处置：先禁用/卸载，人工确认。"),
        ("Windows 的系统结构（所有版本同源）怎么讲？",
         "① **NT 内核**（Executive + 微内核：对象管理、IRP、驱动模型 WDM/KMDF）→ ② 用户态子系统"
         "（Win32/NTAPI、.NET、UWP）→ ③ 系统服务（services.exe、Svchost）→ ④ 安全（**UAC**、令牌、ACL、"
         "**Defender**、Credential Guard）→ ⑤ 应用层。**注册表**是配置总库（HKLM/HKCU，含 Run/RunOnce、"
         "Services、Winlogon、IFEO）；程序是 **PE 格式**（.exe/.dll：DOS 头 → PE 头 → 节表 → 导入表），"
         "正规分发带 **Authenticode 签名**。"),
        ("Windows 上怎么查自启/后门/可疑项（可照着做）？",
         "① 自启：`reg query HKCU\\Software\\Microsoft\\Windows\\CurrentVersion\\Run`、同路径 HKLM、"
         "`RunOnce`、`Winlogon`（Shell/Userinit）、`IFEO`（调试器劫持）；② 计划任务：`schtasks /query /fo csv`；"
         "③ 服务：`sc query type= service`、`Get-Service`；④ 启动目录：`shell:startup`、`shell:common startup`；"
         "⑤ 签名：`Get-AuthenticodeSignature <file>`；⑥ 网络：`netstat -ano`（陌生 LISTEN/ESTABLISHED 记 PID）；"
         "⑦ 进程：`Get-Process | sort CPU` + 路径校验；⑧ 系统文件：`sfc /scannow` / `DISM /Online /Cleanup-Image /RestoreHealth`。"
         "口径：**只读排查 + 人工确认**，不擅自删注册表/杀进程。"),
        ("Linux 的系统结构怎么讲？",
         "① 内核（进程调度、内存、VFS、网络栈、驱动）→ ② 用户态：**init 系统**（现代发行版多为 **systemd**："
         "unit/target/timer）→ ③ 系统库与运行时 → ④ Shell/应用。关键面：**/proc 与 /sys**（内核现读）、"
         "**文件权限/SUID/capabilities**、**SELinux / AppArmor** 强制访问控制、**ELF** 可执行格式、"
         "**cron/systemd timer** 定时与自启、`LD_PRELOAD` 动态库注入。"),
        ("Linux 上怎么查自启/后门/可疑项？",
         "① 定时：`crontab -l`、`ls /etc/cron.*`、`systemctl list-timers`；② 服务自启："
         "`systemctl list-unit-files --state=enabled`、`ls /etc/systemd/system`；③ 注入：`cat /etc/ld.so.preload`、"
         "检查 `LD_PRELOAD` 环境；④ 提权面：`find / -perm -4000 -type f`（SUID 清单人工核对）、`getcap -r /`；"
         "⑤ 网络：`ss -lntp` / `netstat -lntp`（端口↔进程）；⑥ 进程：`ps auxf` 看异常父子链；"
         "⑦ 文件完整性：`sha256sum` 对照发布清单；⑧ 日志：`journalctl -xe`。处置只给建议，不自动删/杀。"),
        ("macOS 的系统结构怎么讲？",
         "① **Darwin**（XNU = Mach + BSD + IOKit）→ ② **launchd**（系统/用户服务与自启，配置在 LaunchDaemons/"
         "LaunchAgents 的 plist）→ ③ 框架层（Cocoa/AppKit、Metal）→ ④ App（.app bundle：Mach-O + Info.plist + "
         "`_CodeSignature`）。安全四件套：**Gatekeeper**（公证/隔离位 com.apple.quarantine）、**TCC**（隐私授权："
         "相机/麦克风/屏幕录制/完全磁盘访问）、**SIP**（系统完整性保护，`csrutil status`）、**沙盒/entitlements**。"),
        ("macOS 上怎么查自启/后门/可疑项？",
         "① `launchctl list` 看用户/系统 agent；② `ls ~/Library/LaunchAgents /Library/LaunchAgents /Library/LaunchDaemons`"
         "；③ 登录项（系统设置→通用→登录项）；④ 隔离位：`xattr -p com.apple.quarantine <file>`；"
         "⑤ 签名：`codesign -dv --verbose=4 <app>`、`spctl --assess -vv <app>`；⑥ SIP：`csrutil status`；"
         "⑦ 网络：`lsof -i -P | grep LISTEN`；⑧ 定时：`crontab -l`、launchd `StartInterval`。只读排查，处置人工确认。"),
    ]


def _selfcheck_rows() -> list:
    return [
        ("「安装上我们的大模型就自动自检一遍」具体检查什么？",
         "固定五步：① **校验**安装包与模型文件的 sha256/签名（对 `state/weights/*manifest*.json` 与发布清单）；"
         "② **特征扫描**：危险命令行（`powershell -enc`、`mshta http`、`certutil -urlcache`、`bitsadmin /transfer`、"
         "`curl|bash`、base64 执行、反连 shell）、双扩展名（`*.pdf.exe`）、脚本型可执行（.scr1/.vbs/.hta）、"
         "隐藏可执行；③ **持久化**：Win 自启键/计划任务/服务，POSIX cron/systemd/launchd/rc.local/ld.so.preload；"
         "④ **网络**：异常监听端口与陌生外连；⑤ **出报告**给人工复核（只读，不擅自杀/删）。"),
        ("装机自检发现可疑项之后怎么处置（边界）？",
         "口径写死：**命中≠定罪**。处置顺序：① 记录路径/哈希/命中特征/时间；② 核对来源与签名；"
         "③ 给出**建议命令**让人在终端决定（禁用自启、隔离文件、重装、改密）；④ 高危（反连 shell/窃密/远控）"
         "先断网再排查；⑤ **不自动删除、不自动杀进程、不改注册表**——避免误伤与证据破坏。"),
        ("模型文件本身的完整性怎么验？",
         "三件：① 发布清单里应有每个权重分片的 **sha256** 与总字节数；② 本地用 `sha256sum`/`Get-FileHash` 对照；"
         "③ 大小与分片数（如 7B bf16 约 15GB、4 分片）对得上，且 `config.json`/`tokenizer` 齐全。"
         "不一致就**不要加载**：先查传输损坏/被替换，再决定重下。口径：验不过不跑，如实报哪一片不一致。"),
        ("木马/病毒在装机场景最常见的伪装是什么？",
         "① 伪装成「模型加速包/驱动/补丁」的可执行；② 双扩展名 `模型.zip.exe`；③ 带宏的 Office/PDF 诱饵；"
         "④ 安装器里捆绑的自启项与浏览器插件；⑤ 「破解版」签名缺失或自签；⑥ 用 `powershell -enc`/base64 隐藏的下载器；"
         "⑦ 伪装成系统进程名但路径在临时目录。识别要点：**看路径、看签名、看自启、看外连**，四件一起核。"),
        ("为什么要按 OS 结构做自检，而不是只扫文件名？",
         "因为攻击面长在结构上：Windows 的自启在注册表/计划任务、Linux 在 systemd/cron/LD_PRELOAD、"
         "macOS 在 launchd/隔离位、iOS 在描述文件/越狱、Android 在设备管理员/无障碍服务。只扫文件名会漏掉"
         "**合法文件名放在合法位置做非法的事**；按结构逐层核对（持久化点、签名、权限、网络）才抓得住。"),
    ]


def _defense_rows() -> list:
    return [
        ("被黑客 AI 攻击时，我的自卫-反控闭环是什么？",
         "① **门先锁**：转账类（`transfer`）与 security 域进攻/黑客面能力位**必须主人授权**，AI 不能自授；"
         "② **防御面可自授**：`sec_defenses` 属于防御，可自动执行蓝队验证（攻击面是否真被挡住）；"
         "③ **反控**：`omni_plug op=counter_strike` 用**极限触手数量**并行对攻击源发 `ai_control`（chat/tools），"
         "收 text/tool_calls/usage 作证据；④ **证据链**：落 incidents 账本 → 报告/披露。"
         "硬钉：只对攻击源发、只认 https、拒重定向、钥匙只回槽名、缺啥如实报。"),
        ("为什么「反控」不等于「报复」？边界在哪？",
         "反控的目的只有两个：**让它停** 与 **拿到证据**。边界：① 只对**记录在案的攻击源**发；"
         "② 不越权、不写入对方系统、不破坏数据；③ 不把本地密钥/审计内容塞进反控 prompt（避免二次泄露）；"
         "④ 拿到 tool_calls/usage 就停，转人工报告与披露流程；⑤ 全程留痕，可复核。"),
        ("手机/电脑上的自卫层在做什么？",
         "页面级自卫层：① **看**——扫输入/粘贴/页面文本里的攻击特征（提示词注入、越狱、套密钥、破门指令、"
         "数据外带、远控话术）；② **拦**——命中即阻断提交 + 固定条警告；③ **留证**——证据写本地环形缓冲并可导出；"
         "④ **反控**——若配了本机框架地址（如 `http://<局域网IP>:8877`）就把证据上报，框架跑 "
         "`sec_defenses` + `counter_strike`；未联网则**只拦截留证**并明说「反控需框架在线」，不假装已反控。"),
    ]


def _os_cmd_rows() -> list:
    return [
        ("给我一份「装机后 10 分钟自检」清单（跨平台）？",
         "1) 校验安装包/权重 sha 与签名；2) 查自启（Win Run/RunOnce/计划任务；Linux cron/systemd；macOS launchd）；"
         "3) 查监听端口与陌生外连；4) 查登录项/设备管理（手机：描述文件/设备管理员/无障碍）；"
         "5) 查杀软/防护状态（Defender/Play Protect/Gatekeeper）；6) 查系统更新与补丁；7) 查浏览器扩展；"
         "8) 查最近安装的可疑程序（Win：`Get-WinEvent` 安装日志；Linux：`/var/log/dpkg.log`；macOS：`system_profiler SPApplicationsDataType`）；"
         "9) 备份关键配置；10) 出报告 + 人工复核清单。全程只读优先，处置人工确认。"),
        ("如果我发现机器上有陌生持久化项，第一步做什么？",
         "先**别删**：① 记录（路径、命令行、启动方式、哈希、创建时间）；② 判断来源（签名/安装时间/父进程）；"
         "③ 断网隔离（若疑似远控/窃密）；④ 用只读方式确认（`Get-AuthenticodeSignature`/`codesign`/`sha256sum`）；"
         "⑤ 给主人建议命令（禁用启动项/隔离文件/改密/重装）；⑥ 结论写「确认/可疑/排除」并留证。"),
    ]


def main():
    base = [json.loads(l) for l in SRC.read_text(encoding="utf-8").splitlines() if l.strip()]
    base_sha = hashlib.sha256(SRC.read_bytes()).hexdigest()
    adds = ([("OS结构·iOS", q, a) for q, a in _os_rows()[:3]]
            + [("OS结构·Android", q, a) for q, a in _os_rows()[3:6]]
            + [("OS结构·Windows", q, a) for q, a in _os_rows()[6:8]]
            + [("OS结构·Linux", q, a) for q, a in _os_rows()[8:10]]
            + [("OS结构·macOS", q, a) for q, a in _os_rows()[10:12]]
            + [("装机自检", q, a) for q, a in _selfcheck_rows()]
            + [("自卫反控", q, a) for q, a in _defense_rows()]
            + [("装机自检清单", q, a) for q, a in _os_cmd_rows()])
    rows = list(base) + [{"instruction": q, "output": a, "family": fam, "source": "v58-" + fam}
                         for fam, q, a in adds]
    OUT.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")
    blob = OUT.read_bytes()
    MAN.parent.mkdir(parents=True, exist_ok=True)
    MAN.write_text(json.dumps({
        "gen": "v58", "parent": "v57", "count": len(rows), "bytes": len(blob),
        "sha256": hashlib.sha256(blob).hexdigest(), "base_count": len(base),
        "base_sha256": base_sha, "base_unchanged": hashlib.sha256(SRC.read_bytes()).hexdigest() == base_sha,
        "appended": len(adds),
        "by_kind": {"iOS": 3, "Android": 3, "Windows": 2, "Linux": 2, "macOS": 2,
                    "装机自检": len(_selfcheck_rows()), "自卫反控": len(_defense_rows()),
                    "装机清单": len(_os_cmd_rows())},
        "directives": ["主人 2026-10-17：「给她注入苹果手机结构知识安卓手机结构知识，电脑所有版本结构知识给她注入，安装上我们的大模型就自动自检一遍排除病毒木马等」",
                       "主人 2026-10-17：「这些都要我们的大模型会啊」"],
        "why": "OS 五平台结构 + 装机自检(查杀/持久化/完整性) + 自卫反控链（全部为模型可答的实战口径）",
    }, ensure_ascii=False, indent=1), encoding="utf-8")
    print("v58：%d 条（基底 v57 %d + 追加 %d）· %d 字节 · sha %s"
          % (len(rows), len(base), len(adds), len(blob), hashlib.sha256(blob).hexdigest()[:16]))
    print("  基底 sha 未变:", hashlib.sha256(SRC.read_bytes()).hexdigest() == base_sha)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
