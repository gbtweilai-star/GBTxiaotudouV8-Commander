# -*- coding: utf-8 -*-
"""身体·免疫（2026-11-04 主人令）。

主人原话：「身体健康排查以及隐藏的无关进程必须要强制关闭这是自我保护机制，
以及发现病毒木马等一列问题都要采取行动把危险和问题都排除干净」

为什么不能靠 Defender 兜底：
  实测这台机器 Defender 实时保护开着、特征库当日更新，
  但 aclui.dll.js 蠕虫在启动文件夹躺了 43 天，**Defender 一条记录都没有**。
  特征库没收录 = 它不会拦。所以免疫必须自己长，不能外包。

免疫的三层：
  L1 体检（op=scan）  —— 只读，查七类持久化与活体进程，给证据不问结果
  L2 清剿（op=purge） —— 断自启 → 杀活体 → 送回收站；不可逆的都标 requires_admin
  L3 记账（op=record）—— 每次清剿留痕，供事后复盘

判定原则（宁可漏报不可误杀）：
  · 只看**行为特征**，不靠文件名：.js/.vbs 跑在 wscript 上、指向 Temp、
    注册表自启指向脚本 —— 这些是恶意，不是"名字像病毒"。
  · 系统进程/框架自身/用户程序一律进白名单，命中也不动。
  · 需要管理员的项**不假装做到**，如实列进 requires_admin，交给人提权。

依赖：stdlib（winreg / subprocess / os）+ 复用 excrete 的回收站。
"""

from __future__ import annotations
from gbt_allinone.tools._opcall import call as _oc_call

import json
import os
import re
import subprocess
import sys
import time

try:
    import winreg
except ImportError:                                          # 非 Windows
    winreg = None

from .excrete import _recycle_one, _human

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_HOME = os.path.join(_ROOT, "state", "immune")
_LEDGER = os.path.join(_HOME, "ledger.jsonl")
_QUAR = os.path.join(_HOME, "quarantine")

_USER = os.environ.get("USERPROFILE") or os.path.expanduser("~")

# 脚本宿主：恶意 .js/.vbs 通常借这三个跑
_HOSTS = ("wscript.exe", "cscript.exe", "mshta.exe")
# 白名单：这些进程/路径命中也不动（自己的器官）
_SELF_SAFE = ("GBT小土豆V8", "gbt_allinone", "pyembed", "console-server",
              "LobeHub", "lobehub", "GBT-", "GBTxiaotudou", "sync-guard",
              "Commander", "gbt-router", "qa-pyembed")
# 白名单：系统目录（Windows 自己的任务/脚本一律不问）
_SYS_SAFE = ("%systemroot%", "c:\\windows\\", "\\system32\\", "hpatchmon",
             "c:\\program files\\windows", "c:\\programdata\\microsoft")

# 高危脚本扩展名：恶意件在自启点出现基本都是这些
_SCRIPT_HIGH = (".js", ".vbs", ".vbe", ".jse", ".wsf", ".hta")
# 低危：正常工具也常用来自启，只提示不判高危（避免误杀自己人）
_SCRIPT_LOW = (".cmd", ".bat", ".ps1")
_SCRIPT_EXT = _SCRIPT_HIGH + _SCRIPT_LOW


def _ps(cmd: str, timeout: int = 60) -> str:
    try:
        p = subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", cmd],
                           capture_output=True, text=True, timeout=timeout,
                           encoding="utf-8", errors="replace")
        return (p.stdout or "") + (p.stderr or "")
    except Exception as exc:                                 # noqa: BLE001
        return "_ERR_ %s: %s" % (type(exc).__name__, exc)


def _script_level(s: str) -> str | None:
    """判定一个路径/命令行的脚本危险级别。high / low / None。

    high = 脚本宿主类（.js/.vbs/.wsf…），恶意件的标配
    low  = .cmd/.bat/.ps1，正版工具也常用来自启 —— 只提示，不当毒
    """
    if not s:
        return None
    low = s.lower()
    for e in _SCRIPT_HIGH:
        if low.endswith(e) or (e + " ") in low or (e + '"') in low:
            return "high"
    for e in _SCRIPT_LOW:
        if low.endswith(e) or (e + " ") in low or (e + '"') in low:
            return "low"
    return None


def _is_script_path(s: str) -> bool:
    return _script_level(s) is not None


def _is_temp(s: str) -> bool:
    low = (s or "").lower()
    return ("\\temp\\" in low) or ("\\tmp\\" in low) or ("appdata\\local\\temp" in low)


def _safe_path(s: str) -> bool:
    """白名单：自己的器官 + 系统目录，命中即不问。"""
    low = (s or "").lower()
    if any(k.lower() in low for k in _SELF_SAFE):
        return True
    if any(k.lower() in low for k in _SYS_SAFE):
        return True
    return False


# ══════════════════════════════════════════════════════════════
# L1 体检
# ══════════════════════════════════════════════════════════════
def _scan_runkeys() -> list[dict]:
    """注册表自启点。指向脚本/Temp 的一律高危。"""
    out = []
    if not winreg:
        return out
    keys = [
        (winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Run", "HKCU"),
        (winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\RunOnce", "HKCU"),
        (winreg.HKEY_LOCAL_MACHINE, r"Software\Microsoft\Windows\CurrentVersion\Run", "HKLM"),
        (winreg.HKEY_LOCAL_MACHINE,
         r"Software\WOW6432Node\Microsoft\Windows\CurrentVersion\Run", "HKLM"),
    ]
    for hive, path, tag in keys:
        try:
            with winreg.OpenKey(hive, path) as k:
                i = 0
                while True:
                    try:
                        name, val, _ = winreg.EnumValue(k, i)
                    except OSError:
                        break
                    i += 1
                    if not name or name == "(default)":
                        continue
                    bad = _is_script_path(str(val)) or _is_temp(str(val))
                    if bad and not _safe_path(str(val)):
                        out.append({
                            "kind": "runkey", "severity": "high",
                            "where": "%s\\%s" % (tag, path),
                            "name": name, "target": str(val),
                            "evidence": "开机自启指向脚本或临时目录",
                            "auto_fixable": True,
                            "fix": "del_reg",
                            "admin": (tag == "HKLM"),
                        })
        except OSError:
            pass
    return out


def _scan_startup() -> list[dict]:
    """启动文件夹里的脚本。"""
    out = []
    dirs = [
        os.path.join(_USER, r"AppData\Roaming\Microsoft\Windows\Start Menu\Programs\Startup"),
        r"C:\ProgramData\Microsoft\Windows\Start Menu\Programs\StartUp",
    ]
    for d in dirs:
        if not os.path.isdir(d):
            continue
        try:
            for fn in os.listdir(d):
                if fn.lower().endswith(".ini"):
                    continue
                lvl = _script_level(fn)
                if not lvl:
                    continue
                full = os.path.join(d, fn)
                if _safe_path(full):
                    continue
                if lvl == "low":
                    # .cmd/.bat 正版工具也自启，只登记不判毒、不自动清
                    out.append({
                        "kind": "startup", "severity": "low", "where": d,
                        "name": fn, "target": full,
                        "evidence": "启动文件夹里的普通脚本（正版工具也这样，仅登记）",
                        "auto_fixable": False, "fix": "manual", "admin": False,
                    })
                    continue
                out.append({
                    "kind": "startup", "severity": "high", "where": d,
                    "name": fn, "target": full,
                    "evidence": "启动文件夹里放脚本宿主文件（.js/.vbs/.wsf）= 开机静默执行",
                    "auto_fixable": True, "fix": "recycle",
                    "admin": d.lower().startswith("c:\\programdata"),
                })
        except OSError:
            pass
    return out


def _scan_tasks() -> list[dict]:
    """计划任务：执行体是脚本，或参数里带 wscript/Temp。"""
    out = []
    txt = _ps("Get-ScheduledTask | ForEach-Object { $t=$_; "
              "foreach($a in $t.Actions){ "
              "'{0}|{1}|{2}|{3}' -f $t.TaskPath,$t.TaskName,$a.Execute,$a.Arguments } }")
    for line in txt.splitlines():
        if "|" not in line or line.startswith("_ERR_"):
            continue
        parts = line.split("|")
        if len(parts) < 4:
            continue
        tpath, tname, exe, args = parts[0], parts[1], parts[2], parts[3]
        blob = (exe + " " + args)
        # 只把「脚本宿主」「高危脚本」「临时目录」当毒。
        # 普通 .cmd/.ps1 任务不算 —— Windows 自己就有好几个（hpatchmonTask 等），
        # 一刀切会把系统自己的任务也报成毒，那是误杀。
        bad = (any(h in blob.lower() for h in ("wscript", "cscript", "mshta"))
               or _script_level(exe) == "high"
               or _script_level(args.strip()) == "high"
               or _is_temp(blob))
        if bad and not _safe_path(blob):
            out.append({
                "kind": "scheduled_task", "severity": "high",
                "where": tpath + tname, "name": tname,
                "target": blob.strip()[:200],
                "evidence": "计划任务用脚本宿主执行，或指向临时目录",
                "auto_fixable": False,        # 删任务要管理员，交给提权
                "fix": "delete_task",
                "admin": True,
            })
    return out


def _scan_processes() -> list[dict]:
    """活体：跑在脚本宿主上的可疑进程。"""
    out = []
    txt = _ps("Get-CimInstance Win32_Process | Where-Object { $_.Name -match "
              "'wscript|cscript|mshta|rundll32' } | ForEach-Object { "
              "'{0}|{1}' -f $_.ProcessId,$_.CommandLine }")
    for line in txt.splitlines():
        if "|" not in line or line.startswith("_ERR_"):
            continue
        pid, cl = line.split("|", 1)
        if not pid.strip().isdigit():
            continue
        if _safe_path(cl):
            continue
        bad = _is_script_path(cl) or _is_temp(cl)
        if bad:
            out.append({
                "kind": "process", "severity": "high",
                "where": "PID " + pid.strip(), "name": (cl.strip()[:80] or "?"),
                "target": cl.strip()[:220], "pid": int(pid.strip()),
                "evidence": "脚本宿主正在执行临时目录里的脚本",
                "auto_fixable": True, "fix": "kill", "admin": False,
            })
    return out


def _scan_wmi() -> list[dict]:
    """WMI 事件订阅持久化（无文件后门）。"""
    out = []
    txt = _ps("Get-CimInstance -Namespace root\\subscription "
              "-ClassName CommandLineEventConsumer -EA SilentlyContinue | "
              "ForEach-Object { '{0}|{1}' -f $_.Name,$_.CommandLineTemplate }")
    for line in txt.splitlines():
        if "|" not in line or line.startswith("_ERR_"):
            continue
        name, cl = line.split("|", 1)
        if not name.strip():
            continue
        if _safe_path(cl):
            continue
        out.append({
            "kind": "wmi_subscription", "severity": "high",
            "where": "root\\subscription", "name": name.strip(),
            "target": cl.strip()[:220],
            "evidence": "WMI 事件订阅常驻执行 —— 无文件后门常用手法",
            "auto_fixable": False, "fix": "manual", "admin": True,
        })
    return out


def _scan_droppers() -> list[dict]:
    """AppData 根目录下的游离脚本（下载器常落这里）。"""
    out = []
    roots = [os.path.join(_USER, "AppData", "Roaming"), os.path.join(_USER, "AppData", "Local")]
    known_ok = ("npm", "pnpm", "Microsoft", "Packages", "Programs", "Temp", "Google",
                "Adobe", "Mozilla", "LobeHub", "JetBrains", "pip", "node-gyp")
    for r in roots:
        if not os.path.isdir(r):
            continue
        try:
            for fn in os.listdir(r):
                full = os.path.join(r, fn)
                if os.path.isfile(full) and _script_level(fn) == "high":
                    out.append({
                        "kind": "dropper", "severity": "medium", "where": r,
                        "name": fn, "target": full,
                        "evidence": "AppData 根目录的游离脚本，无正常程序会用这个位置",
                        "auto_fixable": True, "fix": "recycle", "admin": False,
                    })
        except OSError:
            pass
    return out


def _scan_programdata() -> list[dict]:
    r"""ProgramData 里藏在软件子目录下的脚本。

    实战教训：aclui 蠕虫把副本塞进 C:\ProgramData\Adobe\AIR\start\，
    伪装成 Adobe AIR 的启动脚本 —— 那里既不是启动文件夹、也不在注册表，
    只扫 AppData 会整个漏掉。限制深度 3，避免把 ProgramData 走穿。
    """
    out = []
    base = os.environ.get("ProgramData") or r"C:\ProgramData"
    if not os.path.isdir(base):
        return out
    for dp, dns, fns in os.walk(base):
        depth = dp[len(base):].count(os.sep)
        if depth >= 3:
            dns[:] = []
        for fn in fns:
            if _script_level(fn) != "high":
                continue
            full = os.path.join(dp, fn)
            if _safe_path(full):
                continue
            out.append({
                "kind": "programdata_script", "severity": "high",
                "where": dp, "name": fn, "target": full,
                "evidence": "ProgramData 的软件子目录里藏着脚本宿主文件 —— "
                            "既非启动项也非注册表，是典型藏身处",
                "auto_fixable": False,      # 系统目录，必须提权
                "fix": "recycle_manual", "admin": True,
            })
    return out


def op_scan() -> dict:
    """只读体检：八类持久化 + 活体进程。"""
    checks = {
        "runkey": _scan_runkeys,
        "startup": _scan_startup,
        "scheduled_task": _scan_tasks,
        "process": _scan_processes,
        "wmi_subscription": _scan_wmi,
        "dropper": _scan_droppers,
        "programdata_script": _scan_programdata,
    }
    findings, errors = [], {}
    for name, fn in checks.items():
        try:
            findings.extend(fn())
        except Exception as exc:                             # noqa: BLE001
            errors[name] = "%s: %s" % (type(exc).__name__, str(exc)[:80])

    by_sev = {}
    for f in findings:
        by_sev[f["severity"]] = by_sev.get(f["severity"], 0) + 1
    need_admin = [f for f in findings if f.get("admin")]
    auto_ok = [f for f in findings if f.get("auto_fixable") and not f.get("admin")]

    return {
        "ok": not findings,
        "at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "found": len(findings),
        "by_severity": by_sev,
        "auto_fixable": len(auto_ok),
        "requires_admin": len(need_admin),
        "findings": findings,
        "errors": errors,
        "verdict": ("体内干净" if not findings else
                    "发现 %d 处可疑（%d 处可自动清剿，%d 处需管理员）"
                    % (len(findings), len(auto_ok), len(need_admin))),
    }


# ══════════════════════════════════════════════════════════════
# L2 清剿
# ══════════════════════════════════════════════════════════════
def _kill_pid(pid: int) -> tuple[bool, str]:
    try:
        p = subprocess.run(["taskkill", "/PID", str(pid), "/F", "/T"],
                           capture_output=True, text=True, timeout=30,
                           encoding="utf-8", errors="replace")
        return p.returncode == 0, (p.stdout or p.stderr or "").strip()[:120]
    except Exception as exc:                                 # noqa: BLE001
        return False, str(exc)[:120]


def _del_reg(where: str, name: str) -> tuple[bool, str]:
    tag, rest = where.split("\\", 1)
    key = ("HKEY_CURRENT_USER\\" if tag == "HKCU" else "HKEY_LOCAL_MACHINE\\") + rest
    try:
        p = subprocess.run(["reg", "delete", key, "/v", name, "/f"],
                           capture_output=True, text=True, timeout=30,
                           encoding="utf-8", errors="replace")
        return p.returncode == 0, ((p.stdout or "") + (p.stderr or "")).strip()[:120]
    except Exception as exc:                                 # noqa: BLE001
        return False, str(exc)[:120]


def op_purge(dry_run: bool = True, scan: dict = None) -> dict:
    """清剿：断自启 → 杀活体 → 送回收站。

    默认 dry_run=True 只报不动。不可逆或需提权的项**不会偷偷跳过**，
    全部列进 requires_admin 交给人。
    """
    rep = scan or op_scan()
    todo = [f for f in rep.get("findings", []) if f.get("auto_fixable")]
    blocked = [f for f in rep.get("findings", []) if not f.get("auto_fixable")]

    if dry_run:
        return {
            "ok": True, "dry_run": True,
            "would_act": len(todo), "blocked": len(blocked),
            "plan": [{"fix": f["fix"], "target": f.get("target"), "kind": f["kind"]}
                     for f in todo],
            "requires_admin": [{"kind": f["kind"], "where": f.get("where"),
                                "fix": f.get("fix")} for f in blocked],
            "note": "演习。真清给 dry_run=false。需要管理员的项不会被动 —— "
                    "它们会原样列进 requires_admin，不假装处理过。",
        }

    # 顺序：先杀活体（否则它继续重建），再断自启，最后清文件
    order = {"kill": 0, "del_reg": 1, "delete_task": 2, "recycle": 3}
    todo.sort(key=lambda f: order.get(f.get("fix"), 9))

    done, failed = [], []
    for f in todo:
        fix = f.get("fix")
        try:
            if fix == "kill":
                ok, msg = _kill_pid(f["pid"])
            elif fix == "del_reg":
                ok, msg = _del_reg(f["where"], f["name"])
            elif fix == "recycle":
                ok, msg = _recycle_one(f["target"])
            else:
                ok, msg = False, "未知处置方式 %s" % fix
        except Exception as exc:                             # noqa: BLE001
            ok, msg = False, "%s: %s" % (type(exc).__name__, str(exc)[:80])
        rec = {"kind": f["kind"], "fix": fix, "target": f.get("target"),
               "ok": ok, "msg": msg}
        (done if ok else failed).append(rec)

    entry = {"at": time.strftime("%Y-%m-%dT%H:%M:%S"), "done": len(done),
             "failed": len(failed), "blocked": len(blocked),
             "detail": done + failed}
    _ledger_append(entry)

    return {
        "ok": not failed,
        "dry_run": False,
        "cleared": len(done),
        "failed": failed,
        "requires_admin": [{"kind": f["kind"], "where": f.get("where"),
                            "target": f.get("target"), "fix": f.get("fix")}
                           for f in blocked],
        "msg": "清剿 %d 项，失败 %d 项，%d 项需提权（未擅自处理）"
               % (len(done), len(failed), len(blocked)),
    }


# ══════════════════════════════════════════════════════════════
# L2.5 交付通道：把「需提权」变成可执行脚本（生成，不代跑）
# ══════════════════════════════════════════════════════════════
# 由来（2026-11-04 实战血账）：
#   计划任务 \Skype（伪装成 Skype）每 30 分钟空跑，动作指向已删除的
#   %TEMP%\aclui.dll.js，Windows Script Host 于是每半小时弹一次
#   「无法找到脚本文件」。op_scan 跑一次就抓到了 —— 但判据只把它标成
#   admin=True / auto_fixable=False，而当时**没有任何东西把这行标注
#   变成动作**，于是报告烂在文件里 43 天，弹窗照弹。
#   结论：判据没错，缺的是出口。这一层只补出口 ——
#   把 blocked 项写成脚本，人点一次 UAC 就结算；脚本里每一项逐条报
#   OK / FAIL / SKIP，失败的如实写出来，不假装做到。
_WORK = os.path.join(_HOME, "work")

def _elevate_payload(rows: list[dict]) -> list[dict]:
    """挑出提权脚本该处理的项，裁成 ps1 需要的字段。"""
    keep = []
    for f in rows:
        if not f.get("admin"):
            continue
        keep.append({
            "kind": f.get("kind") or "",
            # scan_programdata 用 recycle_manual 表示「送回收站但需提权」；
            # ps1 侧只认 recycle，这里归一 —— 否则落入 default 被 SKIP，
            # 就重演「扫得到却清不掉」。
            "fix": "recycle" if (f.get("fix") or "") == "recycle_manual"
                   else (f.get("fix") or ""),
            "where": f.get("where") or "",
            "name": f.get("name") or "",
            "target": f.get("target") or "",
            "pid": int(f.get("pid") or 0),
        })
    return keep

def _build_elevate_ps1(items: list[dict], log_path: str) -> str:
    """生成提权脚本正文。数据驱动：项走 JSON、逻辑走 switch，不逐项拼代码。"""
    data = json.dumps(items, ensure_ascii=False)
    tpl = r'''# -*- coding: utf-8 -*-
# body_immune 生成的提权清除脚本 —— 不会自己跑，必须人点 UAC。
# 生成于 __AT__
# 下面每一项都会逐条报 OK / FAIL / SKIP；失败的如实写出来，不假装做到。

$ErrorActionPreference = "Continue"
$Log = "__LOG__"
$Done = 0
$Fail = 0
$Skip = 0

function W([string]$m) {
    $line = "[{0}] {1}" -f (Get-Date -Format "HH:mm:ss"), $m
    Write-Host $line
    try { $line | Out-File -FilePath $Log -Append -Encoding UTF8 } catch { }
}

W "=============================================================="
W " body_immune elevate"
W "=============================================================="

$me = New-Object Security.Principal.WindowsPrincipal([Security.Principal.WindowsIdentity]::GetCurrent())
if (-not $me.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    W "ABORT: 当前不是管理员，本脚本什么也不做。"
    W "请改用同目录的 .cmd 启动，它会自己请求提权。"
    exit 10
}
W "elevated = True"

$Items = '__ITEMS__' | ConvertFrom-Json

foreach ($it in $Items) {
    W "--------------------------------------------------------------"
    W ("[item] " + $it.kind + "    fix=" + $it.fix)
    if ($it.where)  { W ("       where  : " + $it.where) }
    if ($it.target) { W ("       target : " + $it.target) }

    $ok = $false
    $skip = $false

    switch ($it.fix) {
        "delete_task" {
            $name = ([string]$it.where).TrimStart('\')
            $file = Join-Path $env:WINDIR ("System32\Tasks\" + $name)
            if (Test-Path $file) {
                # 恶意件常见手法：建完任务就把创建者削成只读、删除权收归管理员。
                # 不先夺回来，schtasks /Delete 一样会被拒（0x80070005）。
                $null = takeown /f "$file" /a 2>&1
                $null = icacls "$file" /grant "*S-1-5-32-544:(F)" /c 2>&1
            }
            $null = schtasks /Delete /TN "$name" /F 2>&1
            $still = Get-ScheduledTask -TaskName $name -ErrorAction SilentlyContinue
            if ($still -and (Test-Path $file)) {
                $null = Remove-Item $file -Force -ErrorAction SilentlyContinue
                $still = Get-ScheduledTask -TaskName $name -ErrorAction SilentlyContinue
            }
            $ok = -not $still
        }
        "del_reg" {
            $null = reg delete "$($it.where)" /v "$($it.name)" /f 2>&1
            $ok = ($LASTEXITCODE -eq 0)
        }
        "kill" {
            if ([int]$it.pid -gt 0) {
                Stop-Process -Id ([int]$it.pid) -Force -ErrorAction SilentlyContinue
                $ok = -not (Get-Process -Id ([int]$it.pid) -ErrorAction SilentlyContinue)
            }
        }
        "recycle" {
            $p = ([string]$it.target)
            if (Test-Path $p) {
                try {
                    $sh = New-Object -ComObject Shell.Application
                    $folder = $sh.NameSpace((Split-Path $p -Parent))
                    $leaf = Split-Path $p -Leaf
                    if ($folder) { $folder.ParseName($leaf).InvokeVerb("delete") }
                    Start-Sleep -Milliseconds 400
                    $ok = -not (Test-Path $p)
                } catch { $ok = $false }
            } else { $ok = $true }
        }
        default {
            W "       SKIP 不认识的处置方式，留给人工"
            $skip = $true
        }
    }

    if ($skip) {
        $Skip++
    } elseif ($ok) {
        W "       OK   已清除"
        $Done++
    } else {
        W "       FAIL 未能清除（权限仍不足 / 目标被占用 / 需重启后重试）"
        $Fail++
    }
}

W "=============================================================="
W ("结果  OK={0}   FAIL={1}   SKIP={2}" -f $Done, $Fail, $Skip)
W ("日志  {0}" -f $Log)
W "=============================================================="
if ($Fail -gt 0) { exit 3 } else { exit 0 }
'''
    return (tpl.replace("__AT__", time.strftime("%Y-%m-%d %H:%M:%S"))
               .replace("__LOG__", log_path)
               .replace("__ITEMS__", data))

def _build_elevate_cmd(ps1_name: str) -> str:
    """包装器：双击即自提权，用户只点一次 UAC。"""
    return "\r\n".join([
        "@echo off",
        "title body_immune - 提权清除",
        "net session >nul 2>&1",
        "if %errorlevel%==0 goto RUN",
        "echo [*] 需要管理员权限，正在请求提权...",
        "echo [*] 请在 UAC 窗口点【是】",
        "powershell -NoProfile -ExecutionPolicy Bypass -Command \"Start-Process -FilePath '%~f0' -Verb RunAs\"",
        "exit /b",
        ":RUN",
        "echo [+] 已提权，开始执行",
        "echo.",
        "powershell -NoProfile -ExecutionPolicy Bypass -File \"%~dp0{0}\"".format(ps1_name),
        "echo.",
        "pause",
        "",
    ])

def op_elevate(scan: dict = None, dry_run: bool = False) -> dict:
    """把 admin=True 的项写成「一键提权」脚本。只生成，不代跑。

    提权必须由人点确认 —— agent 不能替人按 UAC，也不该绕。
    """
    rep = op_scan() if scan is None else scan
    items = _elevate_payload(rep.get("findings", []))
    if not items:
        return {"ok": True, "count": 0,
                "msg": "没有需要提权的项；op=purge 就能清完"}

    ts = time.strftime("%Y%m%d-%H%M%S")
    if dry_run:
        return {"ok": True, "dry_run": True, "count": len(items),
                "items": items,
                "note": "演习。真生成给 dry_run=false，会在 state/immune/work 下写 .ps1 + .cmd。"}

    os.makedirs(_WORK, exist_ok=True)
    ps1_path = os.path.join(_WORK, "elevate-%s.ps1" % ts)
    cmd_path = os.path.join(_WORK, "elevate-%s.cmd" % ts)
    log_path = os.path.join(_WORK, "elevate-%s.log" % ts)

    body = _build_elevate_ps1(items, log_path)
    # .ps1 一律 utf-8-sig：PowerShell 5.1 读无 BOM 的 UTF-8 会按 GBK 解，
    # 中文乱码还会吃掉字符串结束引号（AGENTS.md 3.1 第二条）。
    with open(ps1_path, "w", encoding="utf-8-sig", newline="\r\n") as fh:
        fh.write(body)
    # .cmd 用 GBK：cmd.exe 默认按 ANSI 读，UTF-8 中文会花
    with open(cmd_path, "w", encoding="gbk", errors="replace", newline="\r\n") as fh:
        fh.write(_build_elevate_cmd(os.path.basename(ps1_path)))

    _ledger_append({"at": time.strftime("%Y-%m-%dT%H:%M:%S"), "op": "elevate",
                    "count": len(items), "ps1": ps1_path,
                    "targets": [i["where"] or i["target"] for i in items]})
    return {
        "ok": True, "count": len(items), "dry_run": False,
        "ps1": ps1_path, "cmd": cmd_path, "log": log_path,
        "items": [{"kind": i["kind"], "fix": i["fix"],
                   "where": i["where"], "target": i["target"]} for i in items],
        "how": "双击 .cmd，UAC 点【是】。脚本逐项报 OK / FAIL，失败的不装成功。",
    }

# ══════════════════════════════════════════════════════════════
# L3.5 常态核对：拿这次和上次比，只报变化
# ══════════════════════════════════════════════════════════════
# 为什么要有这一层：
#   \Skype 那 43 天里，op_scan 从来没被执行过 —— 抓到也白抓。
#   核对的价值不在「今天有几项」，而在「今天比昨天多了什么」。
_PATROL = os.path.join(_HOME, "patrol")
_PATROL_LAST = os.path.join(_PATROL, "last.json")
_PATROL_TASK = "GBT-ImmunePatrol"
_PATROL_RUNNER = os.path.join(_HOME, "patrol_run.py")

def _patrol_key(f: dict) -> str:
    return "|".join([str(f.get("kind") or ""), str(f.get("where") or ""),
                     str(f.get("name") or "")])

def op_patrol(persist: bool = True) -> dict:
    """跑一次体检，与上次快照比，报新增 / 消失 / 仍在。"""
    rep = op_scan()
    cur = {}
    for f in rep.get("findings", []):
        cur[_patrol_key(f)] = f

    prev = {}
    try:
        with open(_PATROL_LAST, "r", encoding="utf-8") as fh:
            snap = json.load(fh)
        for row in snap.get("items", []):
            k = row.get("key")
            if k:
                prev[k] = row
    except Exception:                                        # noqa: BLE001
        prev = {}

    added = [cur[k] for k in cur if k not in prev]
    gone = [prev[k] for k in prev if k not in cur]
    stayed = [cur[k] for k in cur if k in prev]

    now = time.strftime("%Y-%m-%dT%H:%M:%S")
    if persist:
        os.makedirs(_PATROL, exist_ok=True)
        rows = []
        for k, v in cur.items():
            row = dict(v)
            row["key"] = k
            rows.append(row)
        tmp = _PATROL_LAST + ".tmp"
        try:
            with open(tmp, "w", encoding="utf-8") as fh:
                json.dump({"at": now, "items": rows}, fh, ensure_ascii=False, indent=2)
            os.replace(tmp, _PATROL_LAST)                    # 原子替换，半个快照不落盘
        except Exception:                                    # noqa: BLE001
            pass
        _ledger_append({"at": now, "op": "patrol", "found": len(cur),
                        "added": len(added), "gone": len(gone),
                        "stayed": len(stayed)})

    if added:
        verdict = "新增 %d 项 —— 需要立刻看" % len(added)
    elif cur:
        verdict = "与上次一致：%d 项仍在（未处理，不是已清）" % len(cur)
    else:
        verdict = "干净：无持久化异常"

    def brief(rows):
        return [{"kind": r.get("kind"), "where": r.get("where"),
                 "target": (r.get("target") or "")[:120]} for r in rows[:20]]

    return {
        "ok": True, "at": now, "found": len(cur), "verdict": verdict,
        "added": brief(added), "gone": brief(gone), "stayed": brief(stayed),
        "snapshot": _PATROL_LAST if persist else None,
        "next": "op=elevate 生成提权脚本 / op=purge dry_run=false 清可自动项",
    }

def _patrol_runner_src() -> str:
    """每日核对入口。路径自推导，不写死。"""
    return (
        "# -*- coding: utf-8 -*-\n"
        "# body_immune 每日核对入口（由 op=install_patrol 生成，勿手改）\n"
        "import os\n"
        "import sys\n"
        "\n"
        "_here = os.path.dirname(os.path.abspath(__file__))\n"
        "_root = os.path.dirname(os.path.dirname(_here))\n"
        "sys.path.insert(0, _root)\n"
        "\n"
        "from gbt_allinone import immune\n"
        "\n"
        "r = immune.op_patrol()\n"
        "print(r.get('verdict'))\n"
        "for it in r.get('added') or []:\n"
        "    print('  + %s %s' % (it.get('kind'), it.get('where')))\n"
    )

def op_install_patrol(dry_run: bool = True, at: str = "09:00",
                      remove: bool = False) -> dict:
    """注册 / 卸载「每日核对」计划任务（HKCU 级，不需要管理员）。

    默认 dry_run=True：只把要执行的命令摆出来给人看，不真装。
    """
    if remove:
        cmd = ["schtasks", "/Delete", "/TN", _PATROL_TASK, "/F"]
        what = "卸载每日核对任务"
    else:
        cmd = ["schtasks", "/Create", "/TN", _PATROL_TASK,
               "/TR", '"%s" "%s"' % (sys.executable, _PATROL_RUNNER),
               "/SC", "DAILY", "/ST", str(at), "/F"]
        what = "注册每日核对任务（每天 %s）" % at

    if dry_run:
        return {"ok": True, "dry_run": True, "task": _PATROL_TASK,
                "would": what, "cmd": cmd,
                "note": "演习。真装给 dry_run=false。"}

    if not remove:
        os.makedirs(_HOME, exist_ok=True)
        with open(_PATROL_RUNNER, "w", encoding="utf-8") as fh:
            fh.write(_patrol_runner_src())

    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=60,
                           encoding="utf-8", errors="replace")
        out = ((p.stdout or "") + (p.stderr or "")).strip()
        ok = p.returncode == 0
    except Exception as exc:                                 # noqa: BLE001
        ok, out = False, "%s: %s" % (type(exc).__name__, str(exc)[:120])

    _ledger_append({"at": time.strftime("%Y-%m-%dT%H:%M:%S"),
                    "op": "install_patrol", "remove": bool(remove),
                    "ok": ok, "msg": out[:200]})
    return {"ok": ok, "dry_run": False, "task": _PATROL_TASK,
            "did": what, "output": out[:400],
            "verify": "schtasks /Query /TN %s" % _PATROL_TASK}
# ══════════════════════════════════════════════════════════════
# L3 记账
# ══════════════════════════════════════════════════════════════
def _ledger_append(rec: dict) -> None:
    os.makedirs(_HOME, exist_ok=True)
    try:
        with open(_LEDGER, "a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    except Exception:                                        # noqa: BLE001
        pass


def op_record(limit: int = 20) -> dict:
    rows = []
    try:
        with open(_LEDGER, "r", encoding="utf-8") as f:
            lines = [ln for ln in f if ln.strip()]
        rows = [json.loads(ln) for ln in lines[-int(limit):]][::-1]
    except Exception:                                        # noqa: BLE001
        pass
    return {"ok": True, "count": len(rows), "rows": rows, "ledger": _LEDGER}


def op_status() -> dict:
    body = op_scan()
    return {
        "ok": body["ok"],
        "at": body["at"],
        "found": body["found"],
        "by_severity": body["by_severity"],
        "auto_fixable": body["auto_fixable"],
        "requires_admin": body["requires_admin"],
        "verdict": body["verdict"],
        "quarantine": _QUAR if os.path.isdir(_QUAR) else None,
        "next": "op=scan 看明细 / op=purge 真清",
    }


def op_schema() -> dict:
    return {
        "ok": True,
        "cap": "body_immune",
        "note": "免疫器官：自己长，不外包给 Defender（实测 Defender 43 天没报过这台机器的毒）",
        "ops": {
            "schema": "本契约",
            "status": "免疫状态（轻量体检）",
            "scan": "完整体检：七类持久化 + 活体进程，逐条给证据",
            "purge": "清剿：断自启→杀活体→送回收站；默认 dry_run=True",
            "record": "免疫史",
            "elevate": "生成提权脚本（.ps1+.cmd）：把 admin=True 的项变成人点一次 UAC 就结算的交付物",
            "patrol": "常态核对：与上次快照比，报新增/消失；只读不动手",
            "install_patrol": "注册/卸载每日核对任务（HKCU 级，默认演习）",
        },
        "detects": {
            "runkey": "注册表 Run 指向脚本/临时目录",
            "startup": "启动文件夹放 .js/.vbs",
            "scheduled_task": "计划任务用脚本宿主执行",
            "process": "脚本宿主正在跑临时目录里的脚本",
            "wmi_subscription": "WMI 事件订阅常驻（无文件后门）",
            "dropper": "AppData 根目录的游离脚本",
        },
        "discipline": "只看行为特征，不靠文件名；系统/框架/用户程序进白名单；"
                      "需提权的项如实列 requires_admin，不假装做到",
    }


def run(op: str = "status", **kw) -> dict:
    ops = {"schema": op_schema, "status": op_status, "scan": op_scan,
           "purge": op_purge, "record": op_record,
           "elevate": op_elevate, "patrol": op_patrol,
           "install_patrol": op_install_patrol}
    fn = ops.get(str(op or "status"))
    if not fn:
        return {"ok": False, "error": "不认识的 op：%s（可选 %s）"
                % (op, "/".join(sorted(ops)))}
    return _oc_call(fn, kw)
