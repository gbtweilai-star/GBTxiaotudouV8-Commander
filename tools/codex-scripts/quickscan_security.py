# -*- coding: utf-8 -*-
r"""quick_scan 安全面（S）· 主机安全 + 恶意软件启发式（只读）

为什么单独一件：`gbt_allinone/tools/host_security_scan.py` 的六层（L1-L6）设计很正，
本件**不重复它**，只补它看不见的那一格，并把它接进速扫的判据面。

它看不见的那一格（2026-09-23 实测）：
    L1 读 `Get-MpComputerStatus` → 报告「反病毒在位 True」
    但**从不读 `Get-MpPreference -ExclusionPath`** → 看不见
    **`C:\Users\ADMIN` 整条被排除** ⇒ 本工作区根本不在实时防护视野里。
    「在位」与「在看你」是两件事 —— 只报前者，等于给人一个假的覆盖感。

本件补的判据：
    S1 反病毒可见性  AV_EXCLUSION_BLINDSPOT / AV_EXCLUSION_BROAD /
                    AV_STALE_SIGNATURE / AV_NEVER_FULL_SCAN / AV_DETECTION_HISTORY
    S2 持久化与远控  PERSIST_REMOTE_CONTROL / PERSIST_USER_WRITABLE / PERSIST_WMI
    S3 内容 IOC      IOC_EXEC_PATTERN（下载执行/编码命令/解码器滥用/关防护…）
    S4 供应链        NPM_POSTINSTALL
    S5 网络与解析    HOSTS_TAMPERED / DNS 代理异常

铁律（照抄 host_security_scan 的，不许放宽）：
  · 只读：不删、不改、不 kill、不隔离、不改 Defender 设置
  · 不装东西：只用标准库 + 系统自带 PowerShell
  · 不常驻：一次跑完退出
  · 不假执行：拿不到的层标 unavailable + 原因，**绝不用空结果冒充"干净"**
"""
from __future__ import annotations

import json
import os
import re
import subprocess
from pathlib import Path

DEFENDER_SIG_MAX_AGE_H = 72          # 特征库超过 72h 未更新即提醒
QUICK_SCAN_MAX_AGE_H = 7 * 24        # 快速扫描超过 7 天未跑即提醒

# 远控/远程桌面类产品：自启意味着「这台机器长期对外可被接管」，需人确认是否是本人装的
REMOTE_CONTROL_HINTS = ("tvnserver", "tightvnc", "awesun", "oray", "teamviewer",
                        "rustdesk", "anydesk", "向日葵", "todesk", "vnc", "radmin",
                        "supremo", "gotohttp", "ammyy", "logmein", "splashtop")

# 内容 IOC：全部指向"下载并执行 / 解码执行 / 关闭防护 / 持久化"这几类手法
IOC_RULES = [
    ("encoded_command", re.compile(r"(?i)-e(?:nc(?:odedcommand)?)?\s+[A-Za-z0-9+/=]{60,}")),
    ("from_base64", re.compile(r"(?i)\[?Convert\]?::FromBase64String\s*\(")),
    ("iex", re.compile(r"(?i)\bIEX\s*\(|Invoke-Expression")),
    ("download_string", re.compile(r"(?i)DownloadString\s*\(|DownloadFile\s*\(|DownloadData\s*\(")),
    ("webclient", re.compile(r"(?i)New-Object\s+Net\.WebClient|Net\.WebClient\b")),
    ("certutil_decode", re.compile(r"(?i)certutil(?:\.exe)?\s+-(?:decode|urlcache|decodehex)")),
    ("mshta_remote", re.compile(r"(?i)\bmshta(?:\.exe)?\s+(?:javascript:|vbscript:|https?://)")),
    ("rundll32_js", re.compile(r"(?i)\brundll32(?:\.exe)?\s+javascript:")),
    ("bitsadmin", re.compile(r"(?i)\bbitsadmin(?:\.exe)?\s+/transfer")),
    ("hidden_window", re.compile(r"(?i)-w(?:indowstyle)?\s+hidden")),
    ("disable_av", re.compile(r"(?i)Set-MpPreference\s+-(?:Disable\w+|Exclusion\w+)")),
    ("add_exclusion", re.compile(r"(?i)Add-MpPreference\s+-Exclusion(?:Path|Process|Extension)")),
    ("firewall_off", re.compile(r"(?i)netsh\s+advfirewall\s+set\s+\w+\s+state\s+off")),
    ("shadow_delete", re.compile(r"(?i)vssadmin(?:\.exe)?\s+delete\s+shadows")),
    ("recovery_off", re.compile(r"(?i)bcdedit(?:\.exe)?\s+/set\s+\S+\s+recoveryenabled\s+no")),
    ("reg_run_add", re.compile(r"(?i)\breg(?:\.exe)?\s+add\s+\S*\\Run\S*\s")),
    ("wmic_exec", re.compile(r"(?i)\bwmic(?:\.exe)?\s+.*process\s+call\s+create")),
    ("schtasks_create", re.compile(r"(?i)\bschtasks(?:\.exe)?\s+/create")),
    ("runas_verb", re.compile(r"(?i)Start-Process\b[^\n]*-Verb\s+RunAs")),
]
# 这些路径下命中 IOC 属"本仓就是在做安全研究"，与"藏了后门"要分开报
SECURITY_TOOLING_HINT = re.compile(
    r"(?i)(\\|/)(security|recon|pentest|attack|red_?team|exploit|tests?|fixtures?|"
    r"samples?|\.scratch|\.shadow-repo|_upstream|vendor|node_modules)(\\|/)")


def _ps(cmd: str, timeout: int = 60) -> str:
    """跑 PowerShell 返回 stdout；失败返回空串，由调用方标 unavailable。"""
    try:
        r = subprocess.run(["powershell", "-NoProfile", "-NonInteractive",
                            "-ExecutionPolicy", "Bypass", "-Command", cmd],
                           capture_output=True, text=True, timeout=timeout,
                           encoding="utf-8", errors="replace")
        return (r.stdout or "").strip()
    except Exception:
        return ""


def _ps_json(cmd: str, timeout: int = 60):
    raw = _ps(cmd, timeout=timeout)
    if not raw:
        return None
    try:
        return json.loads(raw)
    except Exception:
        return None


def _fault(sev, code, what, evidence, fix):
    return {"sev": sev, "plane": "S", "code": code, "what": what,
            "evidence": str(evidence)[:400], "fix": fix}


# ══════════════════════════════════════════════════════════════════
# S1 · 反病毒「在位」与「在看你」
# ══════════════════════════════════════════════════════════════════
def scan_av(workspace: Path) -> dict:
    out = {"present": False, "status": None, "exclusions": [],
           "workspace_excluded": False, "covering": [], "detections": [],
           "unavailable": []}
    st = _ps_json("Get-MpComputerStatus -ErrorAction SilentlyContinue | "
                  "Select-Object AMServiceEnabled,AntivirusEnabled,"
                  "RealTimeProtectionEnabled,IsTamperProtected,"
                  "AntivirusSignatureVersion,AntivirusSignatureLastUpdated,"
                  "AntivirusSignatureAge,QuickScanAge,QuickScanEndTime,"
                  "FullScanEndTime | ConvertTo-Json -Compress")
    if st:
        out["present"] = True
        out["status"] = st
    else:
        out["unavailable"].append("Get-MpComputerStatus 无返回")

 # 这一格是 host_security_scan.py 缺的：排除项决定"它到底在不在看你"
    exc = _ps_json("Get-MpPreference -ErrorAction SilentlyContinue | "
                   "Select-Object -ExpandProperty ExclusionPath | ConvertTo-Json -Compress")
    if exc is None:
        out["unavailable"].append("Get-MpPreference -ExclusionPath 无返回")
    else:
        items = exc if isinstance(exc, list) else [exc]
        flat = []
        for it in items:
            if not isinstance(it, str):
                continue
            for piece in re.split(r"[\r\n]+", it):
                piece = piece.strip()
                if piece:
                    flat.append(piece)
        # 有些机器把多条路径塞进同一个字符串里（空格分隔且每段像盘符路径）
        expanded = []
        for piece in flat:
            parts = re.findall(r"[A-Za-z]:\\[^;]*?(?=\s+[A-Za-z]:\\|$)", piece)
            expanded.extend([p.strip() for p in parts] if len(parts) > 1 else [piece])
        out["exclusions"] = sorted({e for e in expanded if e})
        ws = str(workspace).lower().rstrip("\\")
        for e in out["exclusions"]:
            e2 = e.lower().rstrip("\\")
            e2 = os.path.expandvars(e2.replace("$env:userprofile",
                                               os.path.expanduser("~").lower()))
            if ws == e2 or ws.startswith(e2 + "\\") or e2.startswith(ws):
                out["workspace_excluded"] = True
                out["covering"].append(e)

    det = _ps_json("Get-MpThreatDetection -ErrorAction SilentlyContinue | "
                   "Sort-Object InitialDetectionTime -Descending | "
                   "Select-Object -First 10 ThreatID,InitialDetectionTime,"
                   "ThreatStatusID,Resources | ConvertTo-Json -Compress")
    if det:
        out["detections"] = det if isinstance(det, list) else [det]
    return out


def judge_av(av: dict, workspace: Path) -> list:
    f = []
    if not av.get("present"):
        f.append(_fault("P2", "AV_UNAVAILABLE",
                        "读不到反病毒状态（本层是「没扫到」，不是「没有病毒」）",
                        "; ".join(av.get("unavailable") or ["无返回"]),
                        "确认 Windows Defender 服务是否被停用；不要把它读成干净"))
        return f
    st = av.get("status") or {}
    if av.get("workspace_excluded"):
        f.append(_fault(
            "P0", "AV_EXCLUSION_BLINDSPOT",
            "**反病毒把本工作区整条排除了** —— 「在位」不等于「在看你」",
            "排除项命中：%s（共 %d 条排除）｜ 本仓 %s 的实时防护与按需扫描均不覆盖"
            % (" | ".join(av["covering"][:3]), len(av.get("exclusions") or []), workspace),
            "把该排除项撤掉（Set-MpPreference -RemoveExclusionPath），再对本仓跑一次 "
            "MpCmdRun -Scan；**撤销排除要主人点头**"))
    broad = [e for e in (av.get("exclusions") or [])
             if re.fullmatch(r"[A-Za-z]:\\Users\\[^\\]+\\?", e.strip())
             or re.fullmatch(r"[A-Za-z]:\\?", e.strip())]
    if broad and not av.get("workspace_excluded"):
        f.append(_fault("P1", "AV_EXCLUSION_BROAD",
                        "反病毒排除了整个用户目录或整个盘（保护面被大幅削弱）",
                        " | ".join(broad[:4]), "收窄到具体目录，别整条排除"))
    age = st.get("AntivirusSignatureAge")
    if isinstance(age, (int, float)) and age > DEFENDER_SIG_MAX_AGE_H:
        f.append(_fault("P2", "AV_STALE_SIGNATURE",
                        "病毒特征库过期（检出能力下降）",
                        "特征库已 %s 小时未更新（版本 %s）"
                        % (age, st.get("AntivirusSignatureVersion")),
                        "联网更新：Update-MpSignature"))
    q = st.get("QuickScanAge")
    if isinstance(q, (int, float)) and q > QUICK_SCAN_MAX_AGE_H:
        f.append(_fault("P2", "AV_STALE_QUICK_SCAN",
                        "很久没跑过快速扫描",
                        "QuickScanAge = %s 天（上次 %s）"
                        % (round(q / 24, 1), st.get("QuickScanEndTime")),
                        "跑一次快速扫描，或对本仓跑 MpCmdRun -Scan"))
    if not st.get("FullScanEndTime"):
        f.append(_fault("P2", "AV_NEVER_FULL_SCAN",
                        "从没跑过全盘扫描（全盘从未被覆盖）",
                        "FullScanEndTime 为空", "择机跑一次全盘扫描（耗时长，自行择时）"))
    for d in (av.get("detections") or [])[:3]:
        f.append(_fault("P2", "AV_DETECTION_HISTORY",
                        "反病毒历史检出记录（**可能是它把本框架自己的行为当成了威胁**）",
                        "ThreatID=%s at %s  resources=%s"
                        % (d.get("ThreatID"), d.get("InitialDetectionTime"),
                           str(d.get("Resources"))[:120]),
                        "逐条核：若是本框架的自动化脚本触发的误报，记进白名单说明；"
                        "若是真样本，隔离并溯源"))
    return f


# ══════════════════════════════════════════════════════════════════
# S2 · 持久化与远控
# ══════════════════════════════════════════════════════════════════
def scan_persistence() -> dict:
    out = {"run": [], "startup": [], "wmi": [], "unavailable": []}
    keys = [r"HKCU:\Software\Microsoft\Windows\CurrentVersion\Run",
            r"HKLM:\Software\Microsoft\Windows\CurrentVersion\Run",
            r"HKCU:\Software\Microsoft\Windows\CurrentVersion\RunOnce",
            r"HKLM:\Software\Microsoft\Windows\CurrentVersion\RunOnce"]
    got_any = False
    for k in keys:
        d = _ps_json("if (Test-Path '%s') { Get-ItemProperty -Path '%s' | "
                     "Select-Object * -ExcludeProperty 'PS*' | ConvertTo-Json -Compress }" % (k, k))
        if isinstance(d, dict):
            for name, value in d.items():
                out["run"].append({"key": k, "name": name, "value": str(value)})
            got_any = True
    if not got_any:
        out["unavailable"].append("Run/RunOnce 读不到")
    for d in (os.path.expandvars(r"%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup"),
              os.path.expandvars(r"%PROGRAMDATA%\Microsoft\Windows\Start Menu\Programs\Startup")):
        p = Path(d)
        if p.is_dir():
            for x in p.iterdir():
                if x.is_file() and x.name.lower() != "desktop.ini":
                    out["startup"].append(str(x))
    wmi = _ps_json("Get-CimInstance -Namespace root/subscription -ClassName __EventFilter "
                   "-ErrorAction SilentlyContinue | Select-Object Name,Query | "
                   "ConvertTo-Json -Compress", timeout=60)
    if wmi:
        out["wmi"] = wmi if isinstance(wmi, list) else [wmi]
    return out


def judge_persistence(p: dict) -> list:
    f = []
    rc = []
    for it in (p.get("run") or []):
        v = str(it.get("value") or "")
        low = v.lower()
        if any(h in low for h in REMOTE_CONTROL_HINTS):
            rc.append("%s = %s" % (it.get("name"), v[:160]))
        if re.search(r"\\node_modules\\", low) or re.search(r"\\appdata\\", low):
            f.append(_fault("P2", "PERSIST_USER_WRITABLE",
                            "开机自启指向**用户可写目录**（可被替换劫持）",
                            "%s = %s" % (it.get("name"), v[:180]),
                            "移到 Program Files 或用签名校验后再放行"))
    if rc:
        f.append(_fault("P1", "PERSIST_REMOTE_CONTROL",
                        "开机自启里有**远程接管类**软件（这台机器长期可被外部接管）",
                        " | ".join(rc[:4]),
                        "确认是你本人装的；不用就停掉自启并卸载。**这条不是病毒判定，是暴露面判定**"))
    if p.get("startup"):
        f.append(_fault("P2", "PERSIST_STARTUP_FILE",
                        "启动文件夹里有条目（每次登录都会执行）",
                        "%d 个：%s" % (len(p["startup"]),
                                     "; ".join(Path(s).name for s in p["startup"][:6])),
                        "确认每一条是你放的；不用的删掉"))
    # WMI 过滤器：Windows 自带的几个（SCM Event Log Filter / BVTFilter）是系统件，别误报
    BUILTIN_WMI = {"scm event log filter", "bvtfilter", "tslogonfilter",
                   "msft_wmi_consumers", "wmi activity filter"}
    wmi_odd = [w for w in (p.get("wmi") or [])
               if str(w.get("Name") or "").strip().lower() not in BUILTIN_WMI]
    if wmi_odd:
        f.append(_fault("P1", "PERSIST_WMI",
                        "存在**非系统内置**的 WMI 事件订阅持久化（高级持久化手法）",
                        "; ".join("%s :: %s" % (str(w.get("Name"))[:40],
                                                str(w.get("Query"))[:90]) for w in wmi_odd[:3]),
                        "逐条核对 Query 指向什么；不认得就按可疑处理"))
    return f


# ══════════════════════════════════════════════════════════════════
# S3 · 内容 IOC
# ══════════════════════════════════════════════════════════════════
def scan_iocs(prod_files) -> dict:
    hits, tooling = [], []
    scanned = 0
    for path, size in prod_files:
        if path.suffix.lower() not in (".py", ".ps1", ".psm1", ".bat", ".cmd", ".vbs",
                                       ".js", ".mjs", ".cjs", ".sh", ".hta", ".wsf"):
            continue
        if size > 1_500_000:
            continue
        try:
            t = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        scanned += 1
        rel = str(path)
        for name, rx in IOC_RULES:
            m = rx.search(t)
            if not m:
                continue
            ln = t.count("\n", 0, m.start()) + 1
            rec = {"rule": name, "file": rel, "line": ln,
                   "snippet": re.sub(r"\s+", " ", m.group(0))[:90]}
            (tooling if SECURITY_TOOLING_HINT.search(rel) else hits).append(rec)
    return {"scanned": scanned, "hits": hits[:60], "hits_n": len(hits),
            "security_tooling": tooling[:30], "security_tooling_n": len(tooling)}


def judge_iocs(io: dict) -> list:
    f = []
    if io.get("hits_n"):
        top = io["hits"]
        f.append(_fault("P1", "IOC_EXEC_PATTERN",
                        "生产脚本里出现「下载执行/编码命令/解码器滥用」类手法",
                        "%d 处（另有 %d 处位于安全研究/测试目录，已分列）：%s"
                        % (io["hits_n"], io.get("security_tooling_n", 0),
                           "; ".join("%s:%s %s" % (h["file"], h["line"], h["rule"])
                                     for h in top[:3])),
                        "逐处看是不是自己写的运维脚本；若不是，按可疑样本处置"))
    if io.get("security_tooling_n"):
        f.append(_fault("P2", "IOC_IN_SECURITY_TOOLING",
                        "安全研究/测试目录里含同类手法（属预期，但要让读的人知道）",
                        "%d 处，例：%s" % (io["security_tooling_n"],
                                       "; ".join("%s:%s %s" % (h["file"], h["line"], h["rule"])
                                                 for h in io["security_tooling"][:3])),
                        "保留但标注；本仓确有安全研究模块，不当作后门"))
    return f


# ══════════════════════════════════════════════════════════════════
# S4 · 供应链（npm postinstall）
# ══════════════════════════════════════════════════════════════════
def scan_npm_hooks(workspace: Path) -> dict:
    out = {"packages": 0, "hooks": [], "unavailable": []}
    skip = {"node_modules", ".git", "__pycache__", "_upstream", "site-packages"}
    for dp, dn, fn in os.walk(workspace):
        dn[:] = [d for d in dn if d not in skip]
        if "package.json" not in fn:
            continue
        p = Path(dp) / "package.json"
        try:
            d = json.loads(p.read_text(encoding="utf-8", errors="replace"))
        except Exception:
            continue
        out["packages"] += 1
        for field in ("preinstall", "install", "postinstall", "prepare"):
            v = (d.get("scripts") or {}).get(field)
            if v:
                out["hooks"].append({"file": str(p), "field": field, "cmd": str(v)[:160]})
    return out


def judge_npm(n: dict) -> list:
    f = []
    risky = [h for h in (n.get("hooks") or [])
             if re.search(r"(?i)curl|wget|Invoke-WebRequest|node\s+-e|base64|http", h["cmd"])]
    if risky:
        f.append(_fault("P1", "NPM_POSTINSTALL_REMOTE",
                        "npm 生命周期脚本里含**联网下载/内联执行**（供应链投毒面）",
                        "%d 处，例：%s" % (len(risky),
                                       "; ".join("%s[%s] %s" % (h["file"], h["field"], h["cmd"][:60])
                                                 for h in risky[:2])),
                        "核对是不是自己写的构建脚本；第三方包的 postinstall 联网要格外警觉"))
    elif n.get("hooks"):
        f.append(_fault("P2", "NPM_LIFECYCLE_HOOKS",
                        "存在 npm 生命周期脚本（安装即会执行）",
                        "%d 处，例：%s" % (len(n["hooks"]),
                                       "; ".join("%s[%s]" % (h["file"], h["field"])
                                                 for h in n["hooks"][:3])),
                        "知悉即可；联网类见上一条"))
    return f


# ══════════════════════════════════════════════════════════════════
# S5 · hosts / 代理
# ══════════════════════════════════════════════════════════════════
BENIGN_HOSTS = re.compile(r"(?i)^\s*(127\.0\.0\.1|::1|0\.0\.0\.0)\s+(localhost|"
                          r"broadcasthost|ip6-\S+)")
DOCKER_HOSTS = re.compile(r"(?i)(docker\.internal|host\.docker\.internal|"
                          r"kubernetes\.docker\.internal)")


def scan_dns_proxy() -> dict:
    out = {"hosts": None, "proxy": None, "unavailable": []}
    hp = Path(os.path.expandvars(r"%SystemRoot%\System32\drivers\etc\hosts"))
    if hp.is_file():
        try:
 # BOM：hosts 首行是 `\ufeff# Copyright ...`，`strip()` **不会**去掉 \ufeff，
            # 于是注释行被当成"非默认映射"报成 HOSTS_TAMPERED（2026-09-23 实测抓到的误报）。
            live = [line.strip() for line in hp.read_text(encoding="utf-8-sig", errors="replace").splitlines()
                    if line.strip() and not line.strip().lstrip("\ufeff").startswith("#")]
            out["hosts"] = {"path": str(hp), "active": live}
        except OSError as e:
            out["unavailable"].append("hosts 读失败: %s" % type(e).__name__)
    pr = _ps_json("Get-ItemProperty 'HKCU:\\Software\\Microsoft\\Windows\\CurrentVersion\\"
                  "Internet Settings' | Select-Object ProxyEnable,ProxyServer,AutoConfigURL | "
                  "ConvertTo-Json -Compress")
    if pr:
        out["proxy"] = pr
    return out


def judge_dns(d: dict) -> list:
    f = []
    h = d.get("hosts")
    if h:
        odd = [line for line in h["active"]
               if not BENIGN_HOSTS.match(line) and not DOCKER_HOSTS.search(line)]
        if odd:
            f.append(_fault("P1", "HOSTS_TAMPERED",
                            "hosts 文件有非默认映射（可能被劫持或用于屏蔽）",
                            "%d 条：%s" % (len(odd), "; ".join(odd[:4])),
                            "逐条确认；不认识的域名映射删掉（改 hosts 要主人点头）"))
    if d.get("proxy") and d["proxy"].get("ProxyEnable") == 1 \
            and not d["proxy"].get("AutoConfigURL"):
        f.append(_fault("P2", "PROXY_SET",
                        "系统代理已开启（可能被中间人）",
                        "ProxyServer=%s" % d["proxy"].get("ProxyServer"),
                        "确认是不是你自己开的"))
    return f


# ══════════════════════════════════════════════════════════════════
# S6 · 扩展名伪装（读文件头，不看后缀）
# ══════════════════════════════════════════════════════════════════
EXEC_EXTS = {".exe", ".dll", ".sys", ".scr", ".cpl", ".ocx", ".pyd", ".so", ".com"}
MAGIC = [
    (b"MZ", "PE"), (b"\x7fELF", "ELF"), (b"PK\x03\x04", "ZIP"),
    (b"\x89PNG", "PNG"), (b"\xff\xd8\xff", "JPEG"), (b"GIF8", "GIF"),
    (b"%PDF", "PDF"), (b"\x1f\x8b", "GZIP"), (b"Rar!", "RAR"), (b"7z\xbc\xaf", "7Z"),
    (b"\xd0\xcf\x11\xe0", "OLE"), (b"SQLite format 3", "SQLITE"),
]
# 这些后缀本来就装二进制壳，别报
CONTAINER_EXTS = {".bin", ".dat", ".pak", ".cvr", ".hyb", ".glb", ".gltf", ".onnx",
                  ".pt", ".pth", ".safetensors", ".model", ".weights", ".sample"}


def scan_ext_mismatch(prod_files) -> dict:
    out = {"checked": 0, "disguised": [], "unavailable": []}
    for path, size in prod_files:
        if size < 64 or size > 200_000_000:
            continue
        ext = path.suffix.lower()
        if ext in CONTAINER_EXTS:
            continue
        try:
            with path.open("rb") as fh:
                head = fh.read(16)
        except OSError:
            continue
        out["checked"] += 1
        kind = None
        for sig, name in MAGIC:
            if head.startswith(sig):
                kind = name
                break
        if kind is None:
            continue
        is_exec_kind = kind in ("PE", "ELF")
        is_exec_ext = ext in EXEC_EXTS
        if is_exec_kind and not is_exec_ext:
            out["disguised"].append({"file": str(path), "ext": ext, "real": kind})
        elif is_exec_ext and not is_exec_kind and kind not in ("PE", "ELF"):
            out["disguised"].append({"file": str(path), "ext": ext,
                                     "real": kind + "（后缀说可执行，头不是）"})
    return out


def judge_ext_mismatch(e: dict) -> list:
    if not e.get("disguised"):
        return []
    d = e["disguised"]
    return [_fault("P1", "EXT_MISMATCH_PE",
                   "扩展名与真实文件头不符（**伪装**：后缀说不是可执行，头是 PE/ELF；或反之）",
                   "%d 个（共查 %d）：%s" % (len(d), e.get("checked"),
                                       "; ".join("%s [%s→%s]" % (x["file"], x["ext"], x["real"])
                                                 for x in d[:3])),
                   "逐个核；正常软件很少把 PE 藏在 .png/.txt/.json 下。"
                   "**只报不判**：先看是不是测试样本或打包产物")]


# ══════════════════════════════════════════════════════════════════
# S7 · 按需真实扫描（MpCmdRun）—— 默认不跑，需人显式开启
# ══════════════════════════════════════════════════════════════════
def av_ondemand(workspace: Path, timeout: int = 1800) -> dict:
    """对本仓跑一次 Windows Defender 按需扫描。

    🔴 纪律：本函数**默认不被调用**（要 `--av-scan`）。
    理由：本机 Defender 曾把**本框架自己的 pwsh 自动化**判为威胁（ThreatID 2147941383），
    自动触发处置有可能把你自己的工具当场隔离掉。所以：
      · 必须显式开启；
      · 用 `-DisableRemediation` 让它**只报不动手**；
      · 拿不到结果就如实报 unavailable，不假装干净。
    """
    exe = Path(os.environ.get("ProgramFiles", r"C:\Program Files")) / "Windows Defender" / "MpCmdRun.exe"
    if not exe.exists():
        return {"ran": False, "reason": "MpCmdRun.exe 不存在"}
    cmd = [str(exe), "-Scan", "-ScanType", "3", "-File", str(workspace),
           "-DisableRemediation"]
    try:
        r = subprocess.run(cmd, capture_output=True, timeout=timeout, text=True,
                           encoding="utf-8", errors="replace")
        return {"ran": True, "rc": r.returncode,
                "stdout": (r.stdout or "")[-1500:], "stderr": (r.stderr or "")[-500:],
                "remediation": "disabled（只报不动手）"}
    except subprocess.TimeoutExpired:
        return {"ran": False, "reason": "timeout>%ds" % timeout}
    except Exception as e:
        return {"ran": False, "reason": "%s: %s" % (type(e).__name__, str(e)[:120])}


def judge_av_ondemand(a: dict) -> list:
    if a is None:
        return []
    if not a.get("ran"):
        return [_fault("P2", "AV_ONDEMAND_SCAN",
                       "按需扫描没跑成（本项是「没扫到」，不是「干净」）",
                       str(a.get("reason"))[:200],
                       "手工跑：MpCmdRun.exe -Scan -ScanType 3 -File <本仓> -DisableRemediation")]
    rc = a.get("rc")
    txt = (a.get("stdout") or "") + (a.get("stderr") or "")
    re.search(r"(?i)(found\s+\d+\s+threat|threat\s+detected|no threats)", txt)
    if rc not in (0, 1, 2):
        return [_fault("P2", "AV_ONDEMAND_SCAN",
                       "按需扫描返回异常退出码",
                       "rc=%s ｜ %s" % (rc, txt[-200:]), "手工复跑看详细输出")]
    if re.search(r"(?i)found\s+[1-9]\d*\s+threat|threat\s+detected", txt):
        return [_fault("P0", "AV_ONDEMAND_THREAT",
                       "**按需扫描在本仓检出威胁**",
                       txt[-300:], "按 Defender 报告定位文件；溯源后处理")]
    return []          # 干净就不报 —— 但结果落进 rep['S_security']['av_ondemand'] 可复核


# ══════════════════════════════════════════════════════════════════
# S8 · 接入仓里已有的主机六层（**不重造轮子**）
# ══════════════════════════════════════════════════════════════════
def scan_host_layers(check_sign: bool = False) -> dict:
    """复用 `gbt_allinone.tools.host_security_scan` 的 L3/L4/L5，把它们的结果变成判据。

    为什么要复用它而不是自己写：它已经写好了"拿不到的层标 unavailable、绝不用空结果
    冒充干净"的纪律，以及只读铁律。**重复实现 = 两处真相。**
    """
    try:
        import sys
        sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
        from gbt_allinone.tools import host_security_scan as hs
    except Exception as e:
        return {"unavailable": ["导入 host_security_scan 失败: %s" % type(e).__name__]}
    out = {"unavailable": []}
    try:
        out["L3"] = hs.layer3_processes(check_sign=check_sign)
    except Exception as e:
        out["unavailable"].append("L3: %s" % type(e).__name__)
    try:
        out["L4"] = hs.layer4_network()
    except Exception as e:
        out["unavailable"].append("L4: %s" % type(e).__name__)
    try:
        out["L5"] = hs.layer5_suspicious_locations()
    except Exception as e:
        out["unavailable"].append("L5: %s" % type(e).__name__)
    return out


def judge_host_layers(h: dict) -> list:
    if not h:
        return []
    f = []
    if h.get("unavailable"):
        f.append(_fault("P2", "HOSTSEC_UNAVAILABLE",
                        "主机层有拿不到的部分（是「没扫到」，不是「没问题」）",
                        "; ".join(h["unavailable"][:4]),
                        "按提示补权限或换方式；别把 unavailable 读成干净"))
    l3 = h.get("L3") or {}
    if l3.get("ok"):
        un = l3.get("unsigned") or []
        if un:
            f.append(_fault("P1", "PROC_UNSIGNED",
                            "跑着的进程里存在未签名/签名无效且不在系统目录的",
                            "%d 个：%s" % (len(un), "; ".join(
                                str(x.get("p"))[:70] for x in un[:3])),
                            "核对是不是自研/绿色软件；结合路径是否在 TEMP/AppData 判风险。"
                            "**只报不判**"))
    l4 = h.get("L4") or {}
    if l4.get("ok"):
        u = [x for x in (l4.get("listen_unusual") or [])
             if not str(x.get("local", "")).startswith("127.0.0.1")]
        if u:
            f.append(_fault("P1", "PORT_UNUSUAL_LISTEN",
                            "非典型端口在监听（且不是只听本机）",
                            "%d 个：%s" % (len(u), "; ".join(
                                "%s pid=%s" % (x.get("local"), x.get("pid")) for x in u[:4])),
                            "逐个核 pid 归属；不认得就查"))
        est = l4.get("established") or []
        if est:
            f.append(_fault("P2", "NET_EGRESS_UNKNOWN",
                            "存在已建立的外连（需核目标是否可解释）",
                            "%d 条，例：%s" % (len(est), "; ".join(
                                "%s→%s pid=%s" % (x.get("local"), x.get("remote"), x.get("pid"))
                                for x in est[:3])),
                            "把目标域名/IP 与 pid 对上；解释不了的外连要追"))
    l5 = h.get("L5") or {}
    ex = l5.get("executables") or []
    if ex:
        f.append(_fault("P2", "EXEC_IN_SUSPICIOUS_DIR",
                        "TEMP/AppData/Public 里存在可执行文件（木马常见落脚点）",
                        "%d 个：%s" % (len(ex), "; ".join(
                            str(x.get("path"))[:70] for x in ex[:3])),
                        "核对来源；带签名的多为正常安装残留，无签名的优先看"))
    return f


# ══════════════════════════════════════════════════════════════════
def run(workspace: Path, prod_files, *, av_scan: bool = False,
        host_layers: bool = False, host_check_sign: bool = False) -> dict:
    """跑完 S 面，返回 {report, faults}"""
    av = scan_av(workspace)
    persist = scan_persistence()
    iocs = scan_iocs(prod_files)
    npm = scan_npm_hooks(workspace)
    dns = scan_dns_proxy()
    ext = scan_ext_mismatch(prod_files)
    ond = av_ondemand(workspace) if av_scan else None
    host = scan_host_layers(check_sign=host_check_sign) if host_layers else None
    faults = (judge_av(av, workspace) + judge_persistence(persist) + judge_iocs(iocs)
              + judge_npm(npm) + judge_dns(dns) + judge_ext_mismatch(ext)
              + judge_av_ondemand(ond) + judge_host_layers(host or {}))
    unavailable = (av.get("unavailable") or []) + (persist.get("unavailable") or []) \
        + (dns.get("unavailable") or []) + (ext.get("unavailable") or []) \
        + ((host or {}).get("unavailable") or [])
    return {
        "report": {"av": av, "persistence": persist, "iocs": iocs, "npm": npm,
                   "dns": dns, "ext_mismatch": ext, "av_ondemand": ond,
                   "host_layers": host, "unavailable": unavailable,
                   "honest_boundary": (
                       "本面覆盖：反病毒在位**与可见性** / 持久化与远控 / 内容 IOC / "
                       "npm 供应链 / hosts 与代理 / 扩展名伪装 / "
                       "（可选）按需真实扫描 /（可选）主机六层 L3-L5。"
                       "**不覆盖**：全盘哈希比对病毒库（本件不用外部库）、实时行为监控、"
                       "内核 rootkit、已删除痕迹、内存注入。"
                       "IOC 是**启发式**：命中只说明「这段代码长得像那些手法」，"
                       "不说明它一定是恶意 —— 一律只报不判，由人核。")},
        "faults": faults,
    }


if __name__ == "__main__":
    import sys
    w = Path(sys.argv[1]) if len(sys.argv) > 1 else Path.cwd()
    r = run(w, [])
    print(json.dumps(r["report"], ensure_ascii=False, indent=1)[:6000])
    for x in r["faults"]:
        print("[%s] %-26s %s" % (x["sev"], x["code"], x["what"]))
        print("     证据: %s" % x["evidence"][:160])
