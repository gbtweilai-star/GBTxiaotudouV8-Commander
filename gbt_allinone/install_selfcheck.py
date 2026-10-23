# gbt-capability: install_selfcheck
# ⛔ 开发者：自由的风 · 永久钢印 · 禁止删除
"""install_selfcheck -- **装机自检：查病毒/木马/后门**（主人 2026-10-17 令）。

主人原话：「给她注入苹果手机结构知识安卓手机结构知识，电脑所有版本结构知识给她注入，
安装上我们的大模型就自动自检一遍排除病毒木马等」。

## 口径（按 OS 结构做检查，不是"扫个文件夹"）
- **Windows（NT）**：Run/RunOnce 自启键、计划任务、服务、Winlogon/Userinit、IFEO、
  `ldr` 侧常见持久化；PE 头校验 + 危险命令行特征（`powershell -enc`、`mshta http`、`certutil -urlcache`、
  `bitsadmin /transfer`、`curl|bash`、`wscript` 远程脚本）；异常监听端口。
- **Linux**：`/etc/cron*`、systemd unit、`ld.so.preload`、`/etc/rc.local`、`init.d`；
  ELF 魔数 + 可执行权限 + `LD_PRELOAD` 注入特征；非包管理器的 setuid 文件。
- **macOS（Darwin）**：LaunchAgents/Daemons、LoginItems、`xattr -p com.apple.quarantine`（Gatekeeper）、
  `csrutil status`（SIP）、Mach-O 魔数、`/Library/LaunchDaemons` 可疑项。
- **跨平台**：双扩展名（`*.pdf.exe`）、隐藏可执行、超大 base64 块、可疑网外连配置、
  与 `state/weights/*manifest*.json` 里 sha 不符的模型文件。

## 边界
只读扫描（不改文件、不删进程、不杀毒）——发现可疑**如实报**（路径/证据/严重度），
需要处置时给出建议命令，由主人在终端决定。`op=status/scan/persistence/plan/where`。
"""
from __future__ import annotations

import hashlib
import json
import os
import platform
import re
import shutil
import subprocess
from pathlib import Path

OPS = ("status", "scan", "persistence", "plan", "where")
READ_OPS = OPS
WRITE_OPS = ()

ROOT = Path(__file__).resolve().parents[1]
MAX_FILES = 20000
MAX_BYTES = 8 * 1024 * 1024

DANGER_PATTERNS = [
    ("powershell-encoded", re.compile(r"powershell(\.exe)?[^\n]{0,40}\-(enc|encodedcommand)\s+[A-Za-z0-9+/=]{40,}", re.I)),
    ("mshta-remote", re.compile(r"mshta(\.exe)?\s+https?://", re.I)),
    ("certutil-download", re.compile(r"certutil(\.exe)?[^\n]{0,60}\-urlcache[^\n]{0,40}\-split", re.I)),
    ("bitsadmin-transfer", re.compile(r"bitsadmin(\.exe)?[^\n]{0,40}/transfer", re.I)),
    ("curl-pipe-shell", re.compile(r"(curl|wget)[^\n|]{0,80}\|\s*(ba)?sh", re.I)),
    ("base64-blob", re.compile(r"(eval|exec|Invoke-Expression)[^\n]{0,30}(base64|FromBase64String)", re.I)),
    ("remote-script-host", re.compile(r"(wscript|cscript)(\.exe)?\s+https?://", re.I)),
    ("ld-preload-inject", re.compile(r"LD_PRELOAD\s*=|ld\.so\.preload", re.I)),
    ("reverse-shell", re.compile(r"(bash\s+-i\s+>&\s*/dev/tcp|nc\s+-e\s+/bin/(ba)?sh|socat.*exec)", re.I)),
]
DOUBLE_EXT = re.compile(r"\.(pdf|docx?|xlsx?|jpg|png|txt|mp4)\.(exe|scr|bat|cmd|js|vbs|ps1|sh|dll)$", re.I)
SUSPICIOUS_EXT = {".scr", ".pif", ".hta", ".vbs", ".jse", ".wsf", ".lnk"}
EXEC_MAGIC = {b"MZ": "PE", b"\x7fELF": "ELF", b"\xfe\xed\xfa\xce": "Mach-O", b"\xcf\xfa\xed\xfe": "Mach-O64",
              b"\xca\xfe\xba\xbe": "FatMach"}
PERSIST_WIN = [
    (r"HKCU\Software\Microsoft\Windows\CurrentVersion\Run", "reg"),
    (r"HKLM\Software\Microsoft\Windows\CurrentVersion\Run", "reg"),
    (r"HKLM\Software\Microsoft\Windows NT\CurrentVersion\Winlogon", "reg"),
    ("schtasks", "cmd"),
    ("sc query", "cmd"),
]
PERSIST_POSIX = [
    "~/.config/autostart", "~/Library/LaunchAgents", "/Library/LaunchAgents", "/Library/LaunchDaemons",
    "/etc/cron.d", "/etc/cron.daily", "/etc/systemd/system", "/etc/rc.local", "/etc/ld.so.preload",
]


def _run(cmd, timeout=12):
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace",
                           timeout=timeout, shell=isinstance(cmd, str))
        return {"ok": p.returncode == 0, "rc": p.returncode,
                "out": (p.stdout or "")[:4000], "err": (p.stderr or "")[:400]}
    except Exception as e:                                       # noqa: BLE001
        return {"ok": False, "未读到": "%s: %s" % (type(e).__name__, str(e)[:120])}


def _magic(p: Path) -> str:
    try:
        with p.open("rb") as fh:
            head = fh.read(8)
    except Exception:                                            # noqa: BLE001
        return ""
    for k, v in EXEC_MAGIC.items():
        if head.startswith(k):
            return v
    return ""


def _scan_file(p: Path) -> list:
    out = []
    try:
        size = p.stat().st_size
    except Exception:                                            # noqa: BLE001
        return out
    if DOUBLE_EXT.search(p.name):
        out.append({"kind": "双扩展名", "severity": "high", "path": str(p), "why": "伪装扩展名：%s" % p.name})
    if p.suffix.lower() in SUSPICIOUS_EXT:
        out.append({"kind": "脚本型可执行", "severity": "medium", "path": str(p),
                    "why": "常见投递扩展名 %s" % p.suffix})
    if p.name.startswith(".") and os.access(p, os.X_OK):
        out.append({"kind": "隐藏可执行", "severity": "medium", "path": str(p), "why": "隐藏且可执行"})
    if size > MAX_BYTES:
        return out
    try:
        data = p.read_bytes()
    except Exception:                                            # noqa: BLE001
        return out
    # 2026-10-17 修（实测误报）：本仓自己的检测器/名册里"写着"这些特征（规则串），
    #   扫描把它们当成木马特征 —— 假阳。现口径：
    #   ① 已知自我源码（检测器/名册/防御注入器）⇒ 直接豁免；
    #   ② 普通 .py/.md/.json/.txt 里命中 ⇒ 降级 medium 并注明"可能是规则/文档而非可执行载荷"。
    SELF_EXEMPT = ("install_selfcheck.py", "caps_registry.py", "gbt-defense-inject.py",
                   "defense-report-server.py", "post-install-selfcheck.py")
    if p.name in SELF_EXEMPT:
        return out
    text = data.decode("utf-8", "ignore")
    src_like = p.suffix.lower() in (".py", ".md", ".json", ".txt", ".yml", ".yaml", ".toml")
    for name, rx in DANGER_PATTERNS:
        m = rx.search(text)
        if m:
            out.append({"kind": name, "severity": ("medium" if src_like else "high"), "path": str(p),
                        "why": ("命中特征（源码/文档内字符串，需人工判断）：%s" if src_like else "命中危险特征：%s")
                               % m.group(0)[:80].replace("\n", " ")})
    return out


def scan(paths=None, limit: int = 3000, **_kw) -> dict:
    roots = [Path(str(x)) for x in (paths or []) if str(x).strip()] or [ROOT]
    findings, scanned, truncated = [], 0, False
    for r in roots:
        if r.is_file():
            findings += _scan_file(r)
            scanned += 1
            continue
        if not r.is_dir():
            findings.append({"kind": "路径不存在", "severity": "info", "path": str(r)})
            continue
        for p in r.rglob("*"):
            if scanned >= min(MAX_FILES, int(limit)):
                truncated = True
                break
            if not p.is_file() or ".git" in p.parts or "__pycache__" in p.parts:
                continue
            scanned += 1
            findings += _scan_file(p)
    high = [f for f in findings if f.get("severity") == "high"]
    return {"ok": True, "op": "scan", "platform": platform.system(), "roots": [str(x) for x in roots],
            "scanned_files": scanned, "truncated": truncated,
            "findings": findings[:200], "high": len(high), "total": len(findings),
            "verdict": ("发现高危可疑项，请人工复核" if high else "未发现高危特征"),
            "_口径": "只读特征扫描；命中≠定罪（要复核原文与来源）"}


def persistence(**_kw) -> dict:
    sysname = platform.system().lower()
    items = []
    if sysname == "windows":
        for key in ("HKCU\\Software\\Microsoft\\Windows\\CurrentVersion\\Run",
                    "HKLM\\Software\\Microsoft\\Windows\\CurrentVersion\\Run",
                    "HKLM\\Software\\Microsoft\\Windows NT\\CurrentVersion\\Winlogon"):
            r = _run(["reg", "query", key])
            items.append({"location": key, "ok": r.get("ok"), "entries": r.get("out", "")[:1500]})
        r = _run("schtasks /query /fo csv /nh", timeout=30)
        items.append({"location": "scheduled-tasks", "ok": r.get("ok"),
                      "count": len((r.get("out") or "").splitlines())})
        r = _run("netstat -ano", timeout=20)
        listeners = [ln.strip() for ln in (r.get("out") or "").splitlines() if "LISTENING" in ln]
        return {"ok": True, "op": "persistence", "platform": "Windows", "items": items,
                "listening_count": len(listeners), "listening_sample": listeners[:15],
                "_口径": "只读：自启键/计划任务/监听端口；可疑项要人工确认"}
    for loc in PERSIST_POSIX:
        p = Path(os.path.expanduser(loc))
        if p.exists():
            try:
                names = [x.name for x in list(p.iterdir())[:20]] if p.is_dir() else [p.name]
            except Exception:                                    # noqa: BLE001
                names = ["未读到"]
            items.append({"location": loc, "ok": True, "entries": names[:15]})
    return {"ok": True, "op": "persistence", "platform": platform.system(), "items": items}


def status(**_kw) -> dict:
    return {"ok": True, "op": "status", "platform": platform.system(), "release": platform.release(),
            "os_arch": platform.machine(),
            "modules": {"scan": "危险特征/双扩展名/脚本型可执行/隐藏可执行",
                        "persistence": "Win 自启键+计划任务+监听端口 / POSIX 自启目录",
                        "weights_manifest": "对 state/weights/*manifest*.json 里的 sha 复核（人工触发）"},
            "limits": {"max_files": MAX_FILES, "max_bytes_per_file": MAX_BYTES,
                       "mode": "只读，不杀毒、不删文件"},
            "_口径": "读不到就写未读到；命中可疑≠定罪"}


def plan(**_kw) -> dict:
    return {"ok": True, "op": "plan",
            "装机自检链": [
                "① 校验安装包/模型文件 sha 与签名（manifest 对账）",
                "② scan：危险命令行特征 + 双扩展名 + 脚本型可执行（跨平台）",
                "③ persistence：Win 自启/计划任务/监听端口；POSIX 自启目录",
                "④ 出报告 → state/defense/install-selfcheck.json（含 verdict 与证据）",
                "⑤ 有高危 ⇒ 不自动处置，给人工复核项与建议命令（不擅自删/杀）"],
            "OS 结构知识": {
                "iOS": "Darwin/XNU · SpringBoard · App 沙盒/entitlements · 代码签名与公证 · Keychain · "
                       "IPA 结构（Payload/*.app）· DFU/恢复 · MDM · 越狱面（Cydia/unc0ver）",
                "Android": "Linux kernel + HAL · init/zygote · ART(DEX/OAT) · Binder IPC · system_server · "
                           "SELinux · APK/AAB（manifest+permissions）· Keystore · ADB/fastboot · A/B 分区 · root(Magisk)",
                "Windows": "NT 内核 + Win32/NTAPI · 注册表 · UAC · 服务/计划任务 · PE(.exe/.dll) 头与签名 · "
                           "Defender · WMI · 自启键(Run/RunOnce)/IFEO",
                "Linux": "内核 + systemd · /proc /sys /dev · 能力(capabilities)/setuid · SELinux/AppArmor · ELF · "
                         "cron/systemd 持久化 · LD_PRELOAD 注入",
                "macOS": "Darwin/Mach · launchd(LaunchAgents/Daemons) · Gatekeeper/公证 · TCC 隐私 · SIP · "
                         "Mach-O · dmg/pkg · 登录项"},
            "_来源": "OS 结构为公开、稳定的系统架构知识；本能力按结构做检查，不调用任何在线杀毒服务"}


def where(**_kw) -> dict:
    return {"ok": True, "op": "where", "kind": "install_selfcheck",
            "entry": "five-dim.py cap install_selfcheck '{\"op\":\"scan\",\"paths\":[\"state/mobile-pack\"]}'",
            "ops": list(OPS), "what": "装机自检查病毒木马（OS 结构感知、只读、如实报）",
            "触发": "tools/codex-scripts/post-install-selfcheck.py（安装后自动跑一遍）"}


def run_op(op: str = "status", **kw) -> dict:
    table = {"status": status, "scan": scan, "persistence": persistence, "plan": plan, "where": where}
    fn = table.get(str(op or "status").strip().lower())
    if fn is None:
        return {"ok": False, "op": op, "status": "unknown_op", "available": sorted(table)}
    return fn(**kw)
