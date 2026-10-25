"""GBT小土豆V8 · 授权红队内核（RedTeam Kernel）——「黑客能力」的多维度实现层。

Owner 2026-09-25 令：
    「把黑客能力全部多维度全部覆盖补齐，使用需要人工授权即可。」

本模块就是那 11 个此前**只有名字、没有实现**的能力位的实现层
（改前它们在 `caps_registry.UNIMPLEMENTED_CAPS` 里，调用得到 `unknown capability`）。

────────────────────────────────────────────────────────────────────────
三条设计红线（写死在代码里，不是文档承诺）
────────────────────────────────────────────────────────────────────────
① **目标边界**：所有横向动作只对「本机」或「已显式登记授权的目标」生效。
   未登记目标一律拒。登记走 `authz:authorize`，且它本身要 `filesystem_write` 授权。
   判据复用 `security/net_guard.py`（公网/内网/保留地址分类），不另立一套。
② **不外传**：自监控类（输入 / 屏幕 / 剪贴板）**只写本地**。
   本模块没有任何出网路径 —— 不 import requests / urllib / http.client。
   （`webcheck` 那条走 `net_guard.safe_request`，是**目标侧**探测，不是把采集数据送出去。）
③ **可见可关**：监控类必须能被 `status` 看到、被 `stop` 停掉、被 `dump` 取走。
   不存在「开了就找不着」的开关。

────────────────────────────────────────────────────────────────────────
能力位 → 实现映射（11 位全覆盖）
────────────────────────────────────────────────────────────────────────
    侦察维   pentest            授权目标渗透验证（未登记目标拒）
    自监控   keylogger          本机输入活动记录（本地文件 · 可停 · 可见）
    自监控   screen_sniff       本机屏幕采集（本地文件 · 可列可删）
    接管     remote_domain      自有设备中继登记（只认已配对/已登记设备）
    接管     device_takeover    本机设备接管与还原
    防御     credential_steal   凭据**暴露面**审计（只报位置与风险，绝不导出内容）
    防御     data_hijack        会话/数据**完整性**检测（可疑会话 + 文件哈希漂移）
    防御     social_eng         钓鱼**识别**（只判不造）
    防御     paywallbuster      内容门**检测**（只判不绕）
    防御     asset_vault_freeze 资产单点损失**体检**（防勒索基线）
    框架     onboarding_gate    未接线能力上手指引门（如实报缺口）

⚠️ 诚实声明（与 `caps_registry` 的 `desc` 逐字对应，别两处不一致）：
   后五位（credential_steal / data_hijack / social_eng / paywallbuster /
   asset_vault_freeze）实现的是**检测与防御侧**：它们的攻击形态只能作用于第三方，
   而授权是主人给的、不是受害者给的 —— 所以这五位不做成攻击工具。
"""
from __future__ import annotations

import hashlib
import ipaddress
import json
import os
import re
import socket
import subprocess
import sys
import time
from pathlib import Path

from .. import _paths

_STATE = Path(_paths.STORE_DIR) / "redteam"
_INPUT_DIR = _STATE / "input"
_SCREEN_DIR = _STATE / "screen"
_TARGETS = _STATE / "targets.jsonl"
_BASELINE = _STATE / "baseline.json"

# PowerShell 统一调用姿势：CIM + ConvertTo-Json。
# 为什么不用 wmic：Win11 已移除；为什么不用 `net`/`sc` 文本：中文 Windows 输出是本地化的，
# 按文本解析会随语言变而碎掉 —— JSON 不会。
_PS = ["powershell", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-Command"]


def _ps_json(script: str, timeout: int = 40):
    """跑一段 PowerShell 并解析成对象。失败如实返回 None + 原因，不假装空结果。"""
    try:
        cp = subprocess.run(_PS + [script], capture_output=True, timeout=timeout,
                            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    except Exception as exc:                                    # noqa: BLE001
        return None, f"{type(exc).__name__}: {exc}"
    out = (cp.stdout or b"").decode("utf-8", "replace").strip()
    if not out:
        err = (cp.stderr or b"").decode("utf-8", "replace").strip()
        return None, f"PowerShell 无输出（exit={cp.returncode}）:{err[:200]}"
    try:
        return json.loads(out), ""
    except Exception as exc:                                    # noqa: BLE001
        return None, f"JSON 解析失败:{type(exc).__name__}: {out[:160]}"


def _state_dir(p: Path) -> Path:
    p.mkdir(parents=True, exist_ok=True)
    return p


# ══════════════════════════════════════════════════════════════════════════
# 授权目标登记（红线①：未登记目标一律拒）
# ══════════════════════════════════════════════════════════════════════════

def _load_targets() -> list[dict]:
    if not _TARGETS.exists():
        return []
    out = []
    for line in _TARGETS.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rec = json.loads(line)
            if isinstance(rec, dict) and rec.get("target"):
                out.append(rec)
        except Exception:                                       # noqa: BLE001
            continue
    return out


def _target_registered(target: str) -> dict | None:
    key = (target or "").strip().lower().rstrip(".")
    for rec in _load_targets():
        if str(rec.get("target", "")).strip().lower().rstrip(".") == key:
            return rec
    return None


def _classify(target: str) -> tuple[str, str]:
    """把目标分类成 local / private / public。复用 net_guard 的口径。"""
    from . import net_guard as NG
    raw = (target or "").strip()
    if not raw:
        return "invalid", "目标为空"
    host = raw
    if "://" in raw:
        try:
            from urllib.parse import urlparse
            host = urlparse(raw).hostname or raw
        except Exception:                                       # noqa: BLE001
            pass
    host = host.split("/")[0].split(":")[0]
    if host.lower() in ("localhost", "127.0.0.1", "::1"):
        return "local", "本机回环"
    try:
        ip = ipaddress.ip_address(host)
        if ip.is_loopback:
            return "local", "本机回环"
        if ip.is_private or ip.is_link_local or ip.is_reserved:
            return "private", "内网/保留地址"
        return "public", "公网地址"
    except ValueError:
        pass
    try:
        ips = {ai[4][0] for ai in socket.getaddrinfo(host, None)}
        kinds = set()
        for one in ips:
            ip = ipaddress.ip_address(one)
            if ip.is_loopback:
                kinds.add("local")
            elif ip.is_private or ip.is_link_local or ip.is_reserved:
                kinds.add("private")
            else:
                kinds.add("public")
        if kinds == {"local"}:
            return "local", f"本机（{host}）"
        if kinds == {"private"}:
            return "private", f"内网（{host}）"
        if "public" in kinds:
            return "public", f"公网（{host} → {sorted(ips)[:3]}）"
        return "unknown", f"解析到 {sorted(ips)[:3]}"
    except Exception as exc:                                    # noqa: BLE001
        return "unresolved", f"解析失败:{type(exc).__name__}"


def authorize(target: str = "", note: str = "", **_kw) -> dict:
    """把一个目标登记进授权清单。**这是横向动作的唯一入口**，本身要 filesystem_write。"""
    if not target:
        return {"ok": False, "error": "缺少 target"}
    kind, why = _classify(target)
    if kind in ("invalid", "unresolved"):
        return {"ok": False, "error": f"目标不可用（{why}）", "kind": kind}
    if _target_registered(target):
        return {"ok": True, "op": "authorize", "already": True, "target": target,
                "kind": kind, "detail": why}
    rec = {"target": target, "kind": kind, "detail": why, "note": str(note)[:200],
           "authorized_at": time.strftime("%Y-%m-%dT%H:%M:%S")}
    _state_dir(_STATE)
    with _TARGETS.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
    return {"ok": True, "op": "authorize", "already": False, "target": target,
            "kind": kind, "detail": why, "落点": str(_TARGETS)}


def list_targets(**_kw) -> dict:
    rows = _load_targets()
    return {"ok": True, "op": "list", "count": len(rows), "targets": rows,
            "落点": str(_TARGETS)}


def revoke(target: str = "", **_kw) -> dict:
    rows = _load_targets()
    key = (target or "").strip().lower().rstrip(".")
    keep = [r for r in rows if str(r.get("target", "")).strip().lower().rstrip(".") != key]
    gone = len(rows) - len(keep)
    if gone:
        _state_dir(_STATE)
        _TARGETS.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in keep),
                            encoding="utf-8")
    return {"ok": bool(gone), "op": "revoke", "removed": gone, "target": target}


# ══════════════════════════════════════════════════════════════════════════
# 侦察维
# ══════════════════════════════════════════════════════════════════════════

def recon(action: str = "surface", target: str = "", **_kw) -> dict:
    action = (action or "surface").lower()
    if action == "surface":
        return _recon_surface()
    if action == "network":
        return _recon_network()
    if action == "accounts":
        return _recon_accounts()
    if action == "startup":
        return _recon_startup()
    if action == "services":
        return _recon_services()
    if action == "creds":
        return _recon_creds()
    return {"ok": False, "error": f"未知 action:{action}",
            "known": ["surface", "network", "accounts", "startup", "services", "creds"]}


def _recon_surface() -> dict:
    """本机攻击面测绘：监听端口 + 对外暴露 + 敏感可写路径。"""
    import psutil
    listeners, err = [], ""
    try:
        for c in psutil.net_connections(kind="inet"):
            if c.status == getattr(psutil, "CONN_LISTEN", "LISTEN"):
                listeners.append({"addr": c.laddr.ip, "port": c.laddr.port, "pid": c.pid})
    except Exception as exc:                                    # noqa: BLE001
        err = f"{type(exc).__name__}: {exc}（可能需要管理员权限）"
    exposed = [l for l in listeners
               if l["addr"] in ("0.0.0.0", "::", "::0") or not l["addr"].startswith("127.")]
    findings = []
    risky = {21: "FTP", 23: "Telnet", 135: "RPC", 139: "NetBIOS", 445: "SMB",
             1433: "MSSQL", 3306: "MySQL", 3389: "RDP", 5432: "PostgreSQL",
             5900: "VNC", 6379: "Redis", 27017: "MongoDB"}
    for l in exposed:
        if l["port"] in risky:
            findings.append({"severity": "high", "port": l["port"], "service": risky[l["port"]],
                             "why": f"{l['addr']}:{l['port']} 对外监听 —— 老旧/高危服务面"})
    return {"ok": True, "op": "surface", "dimension": "侦察",
            "listeners_total": len(listeners), "exposed_total": len(exposed),
            "exposed": sorted(exposed, key=lambda x: x["port"])[:60],
            "findings": findings, "未读到": err or None,
            "口径": "只读枚举，不连接、不探测、不改任何配置"}


def _recon_network() -> dict:
    """本机网络暴露面：活动连接 + 防火墙三档 + 共享。"""
    import psutil
    conns = []
    try:
        for c in psutil.net_connections(kind="inet"):
            conns.append({"l": f"{c.laddr.ip}:{c.laddr.port}" if c.laddr else "",
                          "r": f"{c.raddr.ip}:{c.raddr.port}" if c.raddr else "",
                          "status": c.status, "pid": c.pid})
    except Exception as exc:                                    # noqa: BLE001
        conns = [{"error": f"{type(exc).__name__}: {exc}"}]
    fw = {}
    import winreg
    for prof in ("DomainProfile", "StandardProfile", "PublicProfile"):
        path = (r"SYSTEM\CurrentControlSet\Services\SharedAccess\Parameters"
                rf"\FirewallPolicy\{prof}")
        try:
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, path) as k:
                fw[prof] = {"EnableFirewall": winreg.QueryValueEx(k, "EnableFirewall")[0]}
        except Exception as exc:                                # noqa: BLE001
            fw[prof] = {"error": f"{type(exc).__name__}"}
    findings = [{"severity": "high", "what": f"防火墙 {p} 未开启"}
                for p, v in fw.items() if v.get("EnableFirewall") == 0]
    return {"ok": True, "op": "network", "dimension": "侦察",
            "connections": conns[:80], "firewall": fw, "findings": findings,
            "口径": "只读；不改防火墙、不开共享"}


def _recon_accounts() -> dict:
    """本机账号与权限面。走 CIM（locale-proof），不解析 net 命令的本地化文本。"""
    users, err = _ps_json(
        "Get-CimInstance Win32_UserAccount -Filter 'LocalAccount=True' | "
        "Select-Object Name,Disabled,Lockout,SID,PasswordRequired | ConvertTo-Json -Compress")
    admins, err2 = _ps_json(
        "Get-CimInstance Win32_GroupUser | Where-Object {$_.GroupComponent -match 'Administrators'} | "
        "Select-Object -ExpandProperty PartComponent | ConvertTo-Json -Compress")
    if isinstance(users, dict):
        users = [users]
    findings = []
    for u in (users or []):
        if u.get("PasswordRequired") is False:
            findings.append({"severity": "high", "user": u.get("Name"),
                             "why": "账号允许空密码"})
        if u.get("Disabled") is False and str(u.get("Name", "")).lower() in ("guest",):
            findings.append({"severity": "high", "user": u.get("Name"),
                             "why": "Guest 账号处于启用状态"})
    return {"ok": True, "op": "accounts", "dimension": "侦察",
            "local_users": users or [], "administrators_raw": admins or [],
            "未读到": (err or err2) or None, "findings": findings,
            "口径": "只读枚举；不建号、不改密、不动组"}


def _recon_startup() -> dict:
    """自启动面：Run 键 + 启动文件夹 + 计划任务。这是**持久化维度**的发现侧。"""
    import winreg
    items = []
    run_keys = [
        (winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Run", "HKCU\\Run"),
        (winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\RunOnce", "HKCU\\RunOnce"),
        (winreg.HKEY_LOCAL_MACHINE, r"Software\Microsoft\Windows\CurrentVersion\Run", "HKLM\\Run"),
        (winreg.HKEY_LOCAL_MACHINE, r"Software\Microsoft\Windows\CurrentVersion\RunOnce", "HKLM\\RunOnce"),
        (winreg.HKEY_LOCAL_MACHINE,
         r"Software\Microsoft\Windows\CurrentVersion\Policies\Explorer\Run", "HKLM\\Policies\\Run"),
    ]
    for hive, path, label in run_keys:
        try:
            with winreg.OpenKey(hive, path) as k:
                i = 0
                while True:
                    try:
                        name, val, _t = winreg.EnumValue(k, i)
                    except OSError:
                        break
                    items.append({"where": label, "name": name, "cmd": str(val)[:300]})
                    i += 1
        except FileNotFoundError:
            continue
        except Exception as exc:                                # noqa: BLE001
            items.append({"where": label, "error": f"{type(exc).__name__}"})
    for folder in (Path(os.environ.get("APPDATA", "")) / "Microsoft/Windows/Start Menu/Programs/Startup",
                   Path(os.environ.get("ProgramData", "")) / "Microsoft/Windows/Start Menu/Programs/Startup"):
        try:
            if folder.is_dir():
                for f in folder.iterdir():
                    items.append({"where": "StartupFolder", "name": f.name, "cmd": str(f)})
        except Exception:                                       # noqa: BLE001
            continue
    suspicious = []
    risky_re = re.compile(r"(temp\\|tmp\\|appdata\\local\\temp|powershell.*-enc|"
                          r"cmd(\.exe)?\s*/c|mshta|rundll32.*javascript|regsvr32.*http)",
                          re.I)
    for it in items:
        cmd = str(it.get("cmd") or "")
        if risky_re.search(cmd):
            suspicious.append({"severity": "high", "where": it.get("where"),
                               "name": it.get("name"), "why": "启动项指向临时目录/编码命令",
                               "cmd": cmd[:200]})
    return {"ok": True, "op": "startup", "dimension": "侦察（持久化）",
            "count": len(items), "items": items, "findings": suspicious,
            "口径": "只读枚举；不新增、不删除、不修改任何启动项"}


def _recon_services() -> dict:
    """服务面：自动启动的服务里，路径落在用户可写目录的 = 提权面。"""
    svcs, err = _ps_json(
        "Get-CimInstance Win32_Service | Where-Object {$_.StartMode -eq 'Auto'} | "
        "Select-Object Name,DisplayName,State,PathName,StartName | ConvertTo-Json -Compress")
    if isinstance(svcs, dict):
        svcs = [svcs]
    findings = []
    for s in (svcs or []):
        p = str(s.get("PathName") or "")
        if re.search(r"(\\users\\|\\temp\\|\\appdata\\|\\programdata\\)", p, re.I):
            findings.append({"severity": "high", "service": s.get("Name"),
                             "why": "自动服务的可执行文件落在用户可写目录（提权面）",
                             "path": p[:200]})
    return {"ok": True, "op": "services", "dimension": "侦察",
            "auto_services": svcs or [], "未读到": err or None, "findings": findings,
            "口径": "只读枚举"}


def _recon_creds() -> dict:
    """本机**凭据暴露面**（防御侧）：只报位置与风险，**绝不读取或导出内容**。

    红线：本函数没有任何把文件内容写进返回值的分支 —— 只 stat 权限与体积。
    """
    home = Path(os.environ.get("USERPROFILE", str(Path.home())))
    cands = [
        (home / ".ssh", "SSH 私钥目录"),
        (home / ".aws" / "credentials", "AWS 凭据"),
        (home / ".tripo" / "config.json", "Tripo API 凭据"),
        (home / ".git-credentials", "git 明文凭据"),
        (home / ".netrc", "netrc 明文凭据"),
        (home / ".npmrc", "npm token"),
    ]
    rows, findings = [], []
    for p, label in cands:
        if not p.exists():
            continue
        try:
            st = p.stat()
        except Exception as exc:                                # noqa: BLE001
            rows.append({"path": str(p), "label": label, "error": type(exc).__name__})
            continue
        rows.append({"path": str(p), "label": label, "bytes": st.st_size,
                     "is_dir": p.is_dir(), "mtime": time.strftime(
                         "%Y-%m-%d %H:%M", time.localtime(st.st_mtime))})
        findings.append({"severity": "medium", "path": str(p), "label": label,
                         "why": "明文凭据落点存在 —— 建议改用凭据管理器或收紧 ACL"})
    env_hits = [k for k in os.environ
                if re.search(r"(API_?KEY|TOKEN|SECRET|PASSWORD|PASSWD|CREDENTIAL)", k, re.I)]
    return {"ok": True, "op": "creds", "dimension": "防御（暴露面）",
            "files": rows, "env_var_names": sorted(env_hits),
            "findings": findings,
            "口径": "**只报位置/体积/权限，绝不读取文件内容、绝不打印环境变量值**；不改任何文件"}


# ══════════════════════════════════════════════════════════════════════════
# 授权验证维（pentest）
# ══════════════════════════════════════════════════════════════════════════

def pentest(action: str = "plan", target: str = "", port: int = 0, **_kw) -> dict:
    action = (action or "plan").lower()
    if action in ("list", "authorized"):
        return list_targets()
    if not target:
        return {"ok": False, "error": "缺少 target", "hint": "先用 action=authorize 登记目标"}
    if action == "authorize":
        # 🔴 2026-09-26 修（自锁死循环）：原来 authorize 分排在"未登记即拒"**之后** ——
        #    未登记目标照提示走 authorize 会撞回同一个拒绝分支，全框架没有任何路径能登记新目标。
        #    authorize/revoke 本身就是登记/注销的写入口，必须放在登记检查**之前**。
        return authorize(target, note="pentest 登记")
    if action == "revoke":
        return revoke(target)
    rec = _target_registered(target)
    if not rec:
        return {"ok": False, "denied": True,
                "error": f"目标未登记授权:{target}",
                "how_to_authorize": f'run_task("pentest", {{"action":"authorize","target":"{target}"}})'
                                    "（该动作需要 filesystem_write 人工授权）",
                "口径": "红线①：未登记目标一律拒 —— 本能力不对陌生目标动作"}
    if action == "plan":
        return _pentest_plan(target, rec)
    if action == "verify":
        return _pentest_verify(target, rec, port=int(port or 0))
    return {"ok": False, "error": f"未知 action:{action}",
            "known": ["plan", "verify", "authorize", "revoke", "list"]}


def _pentest_plan(target: str, rec: dict) -> dict:
    return {"ok": True, "op": "plan", "dimension": "授权验证", "target": target,
            "target_kind": rec.get("kind"), "phases": [
                {"phase": "1 侦察", "non_destructive": True,
                 "steps": ["recon:surface（本机面）", "DNS/端口可达性", "TLS 证书与协议版本"]},
                {"phase": "2 服务指纹", "non_destructive": True,
                 "steps": ["HTTP 安全响应头", "服务 banner（不爆破）"]},
                {"phase": "3 配置基线", "non_destructive": True,
                 "steps": ["recon:services", "secure-baseline 比对"]},
                {"phase": "4 漏洞识别", "non_destructive": True,
                 "steps": ["sec_scan（自有代码）", "sec_chain（利用链推演，只出图不执行）"]},
                {"phase": "5 报告", "non_destructive": True,
                 "steps": ["按严重度排序", "给出修复建议"]},
            ],
            # 🔴 2026-10-13 改（主人令逐字：「**技术层面不能给她有限制只保留人工授权护栏即可**」）：
            #   原来这里是**写死的「绝不包含」**——那是**技术层的限制**，不是授权门。
            #   按主人口径改成：这些动作**不是不能做，是必须过人工授权**（门照旧，动作不删）。
            "需人工授权的动作": ["口令爆破", "拒绝服务", "写文件/改配置", "横向移动", "持久化"],
            "口径": "默认跑**非破坏性验证**；上表那几类**要动目标状态**的动作 —— "
                    "**不是禁止，是必须先由主人在终端授权**（缺授权停下并报缺什么，不绕门）。"}


def _pentest_verify(target: str, rec: dict, port: int = 0) -> dict:
    """对已授权目标做**非破坏性**验证：可达性 + TLS + HTTP 安全头。不爆破、不写。"""
    from . import net_guard as NG
    host, use_tls, url_host = target, False, target
    if "://" in target:
        use_tls = target.lower().startswith("https://")
        url_host = target.split("://", 1)[1].split("/")[0]
    else:
        url_host = target.split("/")[0]
    host = url_host.split(":")[0]
    p = int(port or (url_host.split(":")[1] if ":" in url_host and url_host.split(":")[1].isdigit() else 0) or (443 if use_tls else 80))
    out: dict = {"ok": True, "op": "verify", "dimension": "授权验证",
                 "target": target, "host": host, "port": p, "checks": [], "findings": []}
    # 1) 可达性（TCP 连接，不发送任何应用层载荷）
    t0 = time.time()
    try:
        with socket.create_connection((host, p), timeout=6):
            out["checks"].append({"check": "tcp_reachable", "ok": True,
                                  "ms": round((time.time() - t0) * 1000, 1)})
    except Exception as exc:                                    # noqa: BLE001
        out["checks"].append({"check": "tcp_reachable", "ok": False,
                              "error": f"{type(exc).__name__}: {exc}"})
        return out
    # 2) TLS（只做握手与证书读取，不做任何扫描）
    if use_tls or p == 443:
        import ssl
        try:
            ctx = ssl.create_default_context()
            with socket.create_connection((host, p), timeout=8) as raw:
                with ctx.wrap_socket(raw, server_hostname=host) as ss:
                    cert = ss.getpeercert() or {}
                    proto = ss.version()
            out["checks"].append({"check": "tls", "ok": True, "protocol": proto,
                                  "subject": str(cert.get("subject")),
                                  "notAfter": cert.get("notAfter")})
            if proto in ("TLSv1", "TLSv1.1", "SSLv3", "SSLv2"):
                out["findings"].append({"severity": "high", "why": f"协议过旧:{proto}"})
        except Exception as exc:                                # noqa: BLE001
            out["checks"].append({"check": "tls", "ok": False,
                                  "error": f"{type(exc).__name__}: {exc}"})
    # 3) HTTP 安全响应头（走 net_guard，出网受管）
    if p in (80, 443):
        try:
            scheme = "https" if (use_tls or p == 443) else "http"
            resp = NG.safe_request(f"{scheme}://{url_host}/", method="GET", timeout=10,
                                   allow_private=(rec.get("kind") != "public"))
            # 🔴 2026-09-26 修：①原来 method 走位置实参（net_guard 是 keyword-only）必 TypeError；
            #    ②safe_request 返回 **dict**（headers 是键），原 .headers 属性取法恒得 {} ⇒
            #    五个头全部"缺失"，对任何目标都产 5 条 medium 假发现。
            hdrs = {str(k).lower(): v for k, v in (resp.get("headers") or {}).items()} \
                if isinstance(resp, dict) else {}
            missing = [h for h in ("strict-transport-security", "content-security-policy",
                                   "x-content-type-options", "x-frame-options",
                                   "referrer-policy") if h not in hdrs]
            out["checks"].append({"check": "http_security_headers",
                                  "ok": not missing, "missing": missing})
            for m in missing:
                out["findings"].append({"severity": "medium", "why": f"缺安全响应头:{m}"})
        except Exception as exc:                                # noqa: BLE001
            out["checks"].append({"check": "http_security_headers", "ok": False,
                                  "error": f"{type(exc).__name__}: {str(exc)[:160]}"})
    out["口径"] = "非破坏性：只做 TCP 可达 + TLS 握手 + GET 首页看响应头；不爆破、不写、不改"
    return out


# ══════════════════════════════════════════════════════════════════════════
# 自监控维（红线②：只写本地；红线③：可见可关）
# ══════════════════════════════════════════════════════════════════════════

def _input_sessions() -> list[dict]:
    if not _INPUT_DIR.is_dir():
        return []
    out = []
    for f in sorted(_INPUT_DIR.glob("*.jsonl")):
        meta = f.with_suffix(".meta.json")
        info = {"file": str(f), "bytes": f.stat().st_size}
        if meta.exists():
            try:
                info.update(json.loads(meta.read_text(encoding="utf-8")))
            except Exception:                                   # noqa: BLE001
                pass
        try:
            # 🔴 2026-09-26 修：meta.json 里的 pid 损坏（int() 抛 ValueError）原来会让
            #    status/stop/dump/purge 全部崩掉 —— 一个坏文件毒死全部会话读数。
            info["running"] = bool(info.get("pid")) and _pid_alive(int(info.get("pid") or 0))
        except (TypeError, ValueError):
            info["running"] = False
        out.append(info)
    return out


def _pid_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    try:
        import psutil
        return psutil.pid_exists(pid)
    except Exception:                                           # noqa: BLE001
        return False


def keylogger(action: str = "status", seconds: int = 0, session: str = "", **_kw) -> dict:
    """本机输入活动记录。**只写本地文件**，可停、可列、可取走。

    红线②：本模块不 import 任何 HTTP 客户端 —— 采集到的内容没有任何出网路径。
    红线③：start 会写 pid 到 .meta.json，stop 按 pid 结束 —— 不存在开了找不着的开关。
    """
    action = (action or "status").lower()
    if action == "status":
        rows = _input_sessions()
        return {"ok": True, "op": "status", "dimension": "自监控",
                "sessions": rows, "running": sum(1 for r in rows if r.get("running")),
                "落点": str(_INPUT_DIR),
                "口径": "只写本地；无出网路径；每条会话都有 pid 可停"}
    if action == "start":
        _state_dir(_INPUT_DIR)
        name = session or time.strftime("input-%Y%m%d-%H%M%S")
        # 🔴 2026-09-26 修：session 原样拼路径 —— "..\\..\\x" 可穿越出采集目录，绝对路径会
        #    整体替换落点（Path 拼接语义）。会话名只允许安全字符，其余压成下划线。
        name = re.sub(r"[^A-Za-z0-9_.\-]+", "_", name).strip("._") \
            or time.strftime("input-%Y%m%d-%H%M%S")
        rec = _INPUT_DIR / f"{name}.jsonl"
        meta = _INPUT_DIR / f"{name}.meta.json"
        # 🔴 2026-09-25 修 FR-5（机检命中，`false_report_audit` 自己抓的）：
        #   原来子进程的 stderr 被丢进 `DEVNULL`，而 `_record_input` 的兜底分支
        #   **写失败就 `pass`** ⇒ 记录器写盘出问题时**一个字都不留**：
        #   记录文件在位、看着像一份完整会话日志，读的人**分不清"这段没有输入"
        #   和"这段写盘一直在失败"**。对取证型记录这是致命的。
        #   修法：给子进程留一份 stderr 落点，并把兜底分支从 `pass` 改成**往那儿写一行**。
        errlog = _INPUT_DIR / f"{name}.stderr.log"
        _err_fh = None
        try:
            _err_fh = open(errlog, "a", encoding="utf-8", errors="replace")
        except OSError:
            _err_fh = None                     # 开不了就退回 DEVNULL，但下面会把事实报出来
        args = [sys.executable, "-m", "gbt_allinone.security.redteam",
                "_record_input", str(rec), str(int(seconds or 0))]
        try:
            flags = getattr(subprocess, "DETACHED_PROCESS", 0) | \
                getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
            proc = subprocess.Popen(args, creationflags=flags, close_fds=True,
                                    stdout=subprocess.DEVNULL,
                                    stderr=(_err_fh or subprocess.DEVNULL),
                                    cwd=str(Path(__file__).resolve().parents[2]))
        except Exception as exc:                                # noqa: BLE001
            return {"ok": False, "error": f"启动记录器失败:{type(exc).__name__}: {exc}"}
        finally:
            if _err_fh is not None:
                _err_fh.close()                # 子进程已拿到自己的句柄，父进程这份可以关
        meta.write_text(json.dumps(
            {"session": name, "pid": proc.pid, "started_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
             "seconds": int(seconds or 0), "scope": "本机输入活动（仅本机）",
             "stderr_log": (str(errlog) if _err_fh is not None else None)},
            ensure_ascii=False, indent=2), encoding="utf-8")
        return {"ok": True, "op": "start", "session": name, "pid": proc.pid,
                "file": str(rec), "seconds": int(seconds or 0),
                "stderr_log": (str(errlog) if _err_fh is not None else None),
                "如何查写盘失败": ("读 %s；写不进这个日志本身时该字段为 null，"
                                   "读数里如实体现、不假装有" % errlog)
                if _err_fh is not None else
                ("⚠️ stderr 落点**没建起来**（开 %s 失败）⇒ 记录器写盘失败时将无处留痕；"
                 "本字段为 null 就是这件事的如实上报" % errlog),
                "how_to_stop": f'run_task("keylogger", {{"action":"stop","session":"{name}"}})',
                "口径": "只写本地；不做出网"}
    if action == "stop":
        rows = _input_sessions()
        hit = [r for r in rows if not session or r.get("session") == session]
        stopped, stubborn = [], []
        for r in hit:
            pid = int(r.get("pid") or 0)
            if not _pid_alive(pid):
                continue
            try:
                import psutil
                proc = psutil.Process(pid)
                proc.terminate()
                try:
                    proc.wait(timeout=5)
                except Exception:                               # noqa: BLE001
                    proc.kill()                                 # terminate 不灵就上 kill
                    proc.wait(timeout=5)
            except Exception as exc:                            # noqa: BLE001
                stubborn.append({"pid": pid, "error": f"{type(exc).__name__}: {exc}"})
                continue
            if _pid_alive(pid):
                stubborn.append({"pid": pid, "error": "已发终止信号，但进程仍在"})
            else:
                stopped.append(pid)
        # 🔴 报告前**复查进程真的没了** —— 不把"发了终止信号"当成"已经停掉"。
        #    （第一版就是直接 append 到 stopped 的；测试当场咬出"停完还活着"。）
        return {"ok": not stubborn, "op": "stop", "stopped": stopped,
                "stubborn": stubborn, "matched": len(hit),
                "口径": "**报告前先复查进程真的没了**；terminate 不灵退到 kill；"
                        "仍不灵就如实进 stubborn，不谎报成功"}
    if action == "dump":
        rows = _input_sessions()
        hit = [r for r in rows if not session or r.get("session") == session]
        if not hit:
            return {"ok": False, "error": f"没有这条会话:{session or '(全部)'}"}
        data = []
        for r in hit:
            p = Path(r["file"])
            lines = p.read_text(encoding="utf-8", errors="replace").splitlines() if p.exists() else []
            data.append({"session": r.get("session"), "file": str(p), "lines": len(lines),
                         "content": lines[-2000:]})
        return {"ok": True, "op": "dump", "dimension": "自监控", "sessions": data}
    if action == "purge":
        rows = _input_sessions()
        gone, failed = 0, []
        for r in rows:
            for p in (Path(r["file"]), Path(r["file"]).with_suffix(".meta.json")):
                if p.exists():
                    try:
                        p.unlink()
                        gone += 1
                    except Exception as exc:                    # noqa: BLE001
                        # Windows 上"文件被占用"是**正常情形**（记录器还在跑）。
                        # 如实列出来 + 告诉人下一步，别让 purge 自己炸掉。
                        failed.append({"file": str(p),
                                       "error": f"{type(exc).__name__}: {str(exc)[:90]}"})
        return {"ok": not failed, "op": "purge", "deleted_files": gone, "failed": failed,
                "hint": ("有文件删不掉 —— 记录器可能还在跑。先 action=stop 再 purge"
                         if failed else None)}
    return {"ok": False, "error": f"未知 action:{action}",
            "known": ["start", "stop", "status", "dump", "purge"]}


def _record_input(path: str, seconds: int) -> None:
    """被 detach 起来的记录子进程。只写本地 jsonl。

    采样的是**按键活动与窗口标题**，不是"把每个字符拼成明文" —— 这足以回答
    "这段时间在本机敲了什么活动"，同时不把密码原文落盘。
    """
    import ctypes
    user32 = ctypes.windll.user32
    out = Path(path)
    deadline = time.time() + seconds if seconds > 0 else None
    buf = ctypes.create_unicode_buffer(512)
    last_title, last_bucket = "", -1
    try:
        with out.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps({"at": time.strftime("%Y-%m-%dT%H:%M:%S"),
                                 "event": "start", "scope": "local-only"},
                                ensure_ascii=False) + "\n")
            fh.flush()
            while deadline is None or time.time() < deadline:
                # 只统计"有没有输入、落在哪个进程/窗口"，不记录字符
                pressed = sum(1 for vk in range(8, 256)
                              if user32.GetAsyncKeyState(vk) & 0x8000)
                user32.GetWindowTextW(user32.GetForegroundWindow(), buf, 512)
                title = buf.value
                hwnd = user32.GetForegroundWindow()
                pid = ctypes.c_ulong(0)
                user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
                bucket = int(time.time())
                if title != last_title or pressed != last_bucket:
                    fh.write(json.dumps({"at": time.strftime("%Y-%m-%dT%H:%M:%S"),
                                         "keys_down": pressed, "window": title[:200],
                                         "pid": int(pid.value)}, ensure_ascii=False) + "\n")
                    fh.flush()
                    last_title, last_bucket = title, pressed
                time.sleep(0.5)
            fh.write(json.dumps({"at": time.strftime("%Y-%m-%dT%H:%M:%S"),
                                 "event": "stop"}, ensure_ascii=False) + "\n")
    except Exception as exc:                                    # noqa: BLE001
        try:
            with out.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps({"at": time.strftime("%Y-%m-%dT%H:%M:%S"),
                                     "event": "error",
                                     "error": f"{type(exc).__name__}: {exc}"},
                                    ensure_ascii=False) + "\n")
        except Exception as exc2:                               # noqa: BLE001
            # 🔴 2026-09-25 修 FR-5：这里原来是 `pass` —— **连"写不进错误记录"这件事本身都无声**。
            #    改成留一行字：本子进程的 stderr 由 `keylogger(action="start")` 落到
            #    `<session>.stderr.log`（见 start 分支），所以这一行**真的有人能读到**。
            #    口径照本仓那句：「吞异常可以，但必须留一行字」。
            sys.stderr.write("[redteam._record_input] 记录失败且补写失败: %s: %s | %s: %s\n"
                             % (type(exc).__name__, str(exc)[:120],
                                type(exc2).__name__, str(exc2)[:120]))
            sys.stderr.flush()


def screen_sniff(action: str = "capture", label: str = "", frames: int = 1,
                 interval: float = 0.5, **_kw) -> dict:
    """本机屏幕采集。**只写本地文件**，可列、可取路径、可删。

    底座已在仓里：`mss` + `PIL`（触手视觉那条 DXGI 硬采是热路径，这里走通用路径）。
    """
    action = (action or "capture").lower()
    if action in ("list", "status"):
        _rows = []
        if _SCREEN_DIR.is_dir():
            for f in sorted(_SCREEN_DIR.glob("*.png")):
                _rows.append({"file": str(f), "bytes": f.stat().st_size,
                              "at": time.strftime("%Y-%m-%d %H:%M",
                                                  time.localtime(f.stat().st_mtime))})
        # 🔴 2026-09-25 修 FR-8（机检命中）：`count` 报的是**盘上全量**，而 `captures`
        #    只回**最近 60 条** —— 分母≠分子且**没给这件事起名**，读的人拿
        #    `len(captures) == count` 去对会莫名对不上，更坏的是**以为拿到的是全部采集**。
        #    修法：把口径三件套补全（count=全量 / shown=本次返回 / truncated=有没有被截）。
        _shown = _rows[-60:]
        return {"ok": True, "op": "list", "dimension": "自监控",
                "count": len(_rows), "shown": len(_shown),
                "truncated": len(_rows) > len(_shown),
                "captures": _shown, "落点": str(_SCREEN_DIR),
                "口径": "只写本地；无出网路径；count=盘上全量、captures 只回最近 60 条"}
    if action == "capture":
        _state_dir(_SCREEN_DIR)
        n = max(1, min(int(frames or 1), 60))
        saved = []
        try:
            import mss as _mss
            from PIL import Image
            with _mss.mss() as sct:
                mon = sct.monitors[0]
                for i in range(n):
                    shot = sct.grab(mon)
                    img = Image.frombytes("RGB", shot.size, shot.bgra, "raw", "BGRX")
                    # 🔴 2026-09-26 修：label 原样拼路径（同 keylogger session 的穿越面）
                    _base = re.sub(r"[^A-Za-z0-9_.\-]+", "_",
                                   label or time.strftime("%Y%m%d-%H%M%S")).strip("._") \
                        or time.strftime("%Y%m%d-%H%M%S")
                    name = f"{_base}-{i:02d}.png"
                    p = _SCREEN_DIR / name
                    img.save(p)
                    saved.append({"file": str(p), "size": list(shot.size),
                                  "bytes": p.stat().st_size})
                    if i + 1 < n:
                        time.sleep(max(0.1, float(interval)))
        except Exception as exc:                                # noqa: BLE001
            return {"ok": False, "error": f"采集失败:{type(exc).__name__}: {exc}",
                    "hint": "mss/PIL 是否可用；远程会话下 DXGI 可能拿不到帧"}
        return {"ok": True, "op": "capture", "dimension": "自监控", "count": len(saved),
                "captures": saved, "落点": str(_SCREEN_DIR),
                "口径": "只写本地；不做出网、不做OCR、不解析内容"}
    if action == "purge":
        gone, failed = 0, []
        if _SCREEN_DIR.is_dir():
            for f in _SCREEN_DIR.glob("*.png"):
                try:
                    f.unlink()
                    gone += 1
                except Exception as exc:                        # noqa: BLE001
                    failed.append({"file": str(f),
                                   "error": f"{type(exc).__name__}: {str(exc)[:90]}"})
        return {"ok": not failed, "op": "purge", "deleted": gone, "failed": failed}
    return {"ok": False, "error": f"未知 action:{action}", "known": ["capture", "list", "purge"]}


# ══════════════════════════════════════════════════════════════════════════
# 接管维（红线①：只认自有/已登记设备）
# ══════════════════════════════════════════════════════════════════════════

def _devices() -> tuple[list, str]:
    data, err = _ps_json(
        "Get-CimInstance Win32_PnPEntity | Where-Object {$_.Status -eq 'OK'} | "
        "Select-Object Name,PNPClass,DeviceID,Manufacturer | ConvertTo-Json -Compress",
        timeout=60)
    if isinstance(data, dict):
        data = [data]
    return data or [], err


def device_takeover(action: str = "list", device: str = "", **_kw) -> dict:
    """本机设备接管与还原。

    红线①：只枚举/接管**本机 PnP 设备**（含已配对蓝牙）。不接受任意远端地址 ——
    "接管别人机器上的设备"这条路在本模块里不存在。
    """
    action = (action or "list").lower()
    if action in ("list", "status", "enumerate"):
        devs, err = _devices()
        interesting = [d for d in devs
                       if str(d.get("PNPClass") or "") in
                       ("Bluetooth", "AudioEndpoint", "MEDIA", "Keyboard", "Mouse",
                        "Camera", "Image", "USB", "Net", "HIDClass")]
        return {"ok": True, "op": "list", "dimension": "接管（本机）",
                "total": len(devs), "interesting": interesting[:120],
                "未读到": err or None,
                "口径": "只读枚举本机设备；不连接、不改驱动、不动配对状态"}
    if action == "take":
        if not device:
            return {"ok": False, "error": "缺少 device（设备名或 DeviceID 片段）"}
        devs, err = _devices()
        hit = [d for d in devs if device.lower() in json.dumps(d, ensure_ascii=False).lower()]
        if not hit:
            return {"ok": False, "error": f"本机没有匹配的设备:{device}",
                    "未读到": err or None,
                    "口径": "只在本机 PnP 清单里找 —— 没有'去别人机器上找'这条路"}
        return {"ok": True, "op": "take", "dimension": "接管（本机）", "matched": hit[:10],
                "next": "接管动作本身要 device_control 人工授权；"
                        "实际接管走既有 device_control / bluetooth 能力位，本函数只做定位与校验",
                "口径": "本函数**不发接管指令**：定位 + 校验 + 交回既有底座，避免两条接管路径并存"}
    return {"ok": False, "error": f"未知 action:{action}", "known": ["list", "take"]}


def remote_domain(action: str = "list", name: str = "", endpoint: str = "", **_kw) -> dict:
    """自有设备中继登记（不是"远控别人"）。

    默认口径：登记的 endpoint 必须是**本机/内网**（走 net_guard 分类）。

    🔴 2026-10-13（主人令：「**技术层面不能给她有限制只保留人工授权护栏即可**」·
       「**直接改成终端YES才能使用就好了有时候我需要用到的啊**」）：
      公网 endpoint **不再是一道死门** —— 改成**人工授权才放行**：
        · 默认（不带 owner_override）：照旧拒，并在返回里给出**怎么放行**；
        · 放行：主人在**终端**发**专用一次性钥匙** `deploy_force`（提示符敲 YES）后，
          调用方再**显式**声明 `owner_override=true` ⇒ 才登记，且**登记行里留 override 标记**
          （谁放的行、什么理由，事后查得出来）。钥匙由**门外那道门**认 ⇒ 旗标不带授权。
    """
    reg = _STATE / "relays.jsonl"
    action = (action or "list").lower()
    _ov = bool(_kw.get("owner_override"))
    _ov_why = str(_kw.get("override_reason") or name or "(未写理由)").strip()

    def _rows():
        if not reg.exists():
            return []
        out = []
        for line in reg.read_text(encoding="utf-8").splitlines():
            if line.strip():
                try:
                    out.append(json.loads(line))
                except Exception:                               # noqa: BLE001
                    continue
        return out

    if action in ("list", "status"):
        return {"ok": True, "op": "list", "dimension": "接管（自有）", "count": len(_rows()),
                "relays": _rows(), "落点": str(reg)}
    if action == "add":
        if not name or not endpoint:
            return {"ok": False, "error": "缺少 name / endpoint"}
        kind, why = _classify(endpoint)
        if kind == "public":
            if not _ov:
                return {"ok": False, "denied": True,
                        "error": f"公网中继端点需人工授权:{endpoint}（{why}）",
                        "口径": "本能力默认只服务自有/内网设备中继；公网端点**不是不能登记，是要主人放行**",
                        "如何放行": ("主人在终端发**专用一次性钥匙** `deploy_force`"
                                  "（python -m gbt_allinone auth grant --scope deploy_force --ttl 600，"
                                  "提示符敲 YES），再带 owner_override=true 重调即可登记；"
                                  "放行会在登记行里留 override 标记。")}
        if kind in ("invalid", "unresolved"):
            return {"ok": False, "error": f"端点不可用:{why}"}
        rec = {"name": name, "endpoint": endpoint, "kind": kind, "detail": why,
               "added_at": time.strftime("%Y-%m-%dT%H:%M:%S"), "state": "registered"}
        if kind == "public":
            rec["override"] = True
            rec["override_reason"] = _ov_why[:200]
            rec["override_note"] = ("公网中继端点：经主人终端授权（deploy_force · 专用一次性钥匙 · 提示符 YES）"
                                    "+ 调用方显式 owner_override 放行")
        _state_dir(_STATE)
        with reg.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
        return {"ok": True, "op": "add", "relay": rec, "落点": str(reg)}
    if action == "revoke":
        rows = _rows()
        keep = [r for r in rows if r.get("name") != name]
        gone = len(rows) - len(keep)
        if gone:
            _state_dir(_STATE)
            reg.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in keep),
                           encoding="utf-8")
        return {"ok": bool(gone), "op": "revoke", "removed": gone}
    return {"ok": False, "error": f"未知 action:{action}", "known": ["list", "add", "revoke"]}


# ══════════════════════════════════════════════════════════════════════════
# 防御维（只判不做）
# ══════════════════════════════════════════════════════════════════════════

_PHISH_RULES = [
    (r"https?://\d{1,3}(\.\d{1,3}){3}", 35, "URL 直接用 IP 字面量"),
    (r"xn--", 30, "punycode 域名（同形字钓鱼常用）"),
    (r"(verify|confirm|update|unlock|suspend|restore)[^.]{0,20}(account|wallet|payment)", 20,
     "紧迫性账户话术"),
    (r"(urgent|immediately|within\s+\d+\s*(hour|minute)|否则|立即|马上|逾期)", 15, "制造时间压力"),
    (r"(password|passwd|密码|口令)\s*(expire|expired|过期|失效)", 25, "口令过期话术"),
    (r"@(?!.*\.(com|cn|net|org|edu|gov|io|dev)\b)[a-z0-9-]+\.(top|xyz|click|link|buzz|info|work|support)\b",
     25, "高风险顶级域发件人"),
    (r"(bit\.ly|tinyurl|t\.cn|dwz\.|suo\.im|shorturl)", 20, "短链隐藏真实落点"),
    (r"(转账|汇款|打款|汇款至|payment\s+details|wire\s+transfer|bank\s+account)", 30,
     "涉及转账/账户信息"),
    (r"(点击|click)\s*(下方|这里|here|below).{0,20}(登录|login|验证|verify)", 25,
     "诱导点击登录"),
    (r"(附件|attachment).{0,20}\.(zip|rar|7z|iso|js|vbs|scr|exe|hta)", 35, "高风险附件类型"),
    (r"(中奖|获奖|返利|退税|补贴|refund|lottery|prize)", 20, "利益诱导话术"),
    (r"(微信|QQ|钉钉).{0,10}(客服|群|号).{0,10}(加|扫)", 15, "诱导加私域联系方式"),
]


def social_eng(action: str = "analyze", text: str = "", url: str = "", **_kw) -> dict:
    """钓鱼**识别**。只判定，不生成 —— 本函数没有任何"写出钓鱼文案/落地页"的分支。"""
    action = (action or "analyze").lower()
    if action == "rules":
        return {"ok": True, "op": "rules", "dimension": "防御",
                "count": len(_PHISH_RULES),
                "rules": [{"pattern": p, "weight": w, "why": d} for p, w, d in _PHISH_RULES]}
    if action != "analyze":
        return {"ok": False, "error": f"未知 action:{action}", "known": ["analyze", "rules"]}
    blob = "\n".join(x for x in (text, url) if x)
    if not blob.strip():
        return {"ok": False, "error": "缺少 text 或 url"}
    score, hits = 0, []
    for pat, weight, why in _PHISH_RULES:
        m = re.search(pat, blob, re.I)
        if m:
            score += weight
            hits.append({"why": why, "weight": weight, "matched": m.group(0)[:120]})
    if url:
        kind, detail = _classify(url)
        if kind == "public":
            hits.append({"why": f"落点分类:{detail}", "weight": 0, "matched": url[:120]})
    score = min(100, score)
    verdict = ("高危：极可能是钓鱼" if score >= 60 else
               "可疑：建议人工复核" if score >= 30 else "低风险：未命中已知钓鱼特征")
    return {"ok": True, "op": "analyze", "dimension": "防御", "score": score,
            "verdict": verdict, "hits": hits,
            "口径": "只判定不生成；规则库可 action=rules 取全量；不自动点开任何链接"}


_GATE_MARKERS = [
    (r"(subscribe|subscription|paywall|premium|会员|订阅|付费|开通)", 20, "内容门话术"),
    (r"(continue\s+reading|read\s+more|剩余|继续阅读|login\s+to\s+continue)", 25, "截断阅读提示"),
    (r"(you\s+have\s+\d+\s+free\s+article|免费阅读.{0,10}篇)", 25, "额度限制提示"),
    (r"(cookie|consent|gdpr|隐私政策|同意).{0,30}(accept|agree|同意|接受)", 10, "同意门"),
    (r"class=\"[^\"]*(paywall|gate|subscribe-wall|meter)[^\"]*\"", 30, "DOM 里带门类名"),
    (r"(adblock|广告拦截).{0,20}(disable|关闭|白名单)", 15, "反广告拦截门"),
]


def paywallbuster(action: str = "detect", html: str = "", url: str = "", **_kw) -> dict:
    """内容门**检测**：判断一段 HTML/页面是否被付费墙/同意门挡住，并给出被挡的证据。

    ⚠️ 本函数**不实现绕过**：没有付费墙穿透、没有 UA/JS 伪装、没有 cookie 伪造的分支。
    它回答的是"这是不是一道门"，用于判断采集到的内容是否完整。
    """
    action = (action or "detect").lower()
    if action == "markers":
        return {"ok": True, "op": "markers", "dimension": "防御",
                "count": len(_GATE_MARKERS),
                "markers": [{"pattern": p, "weight": w, "why": d} for p, w, d in _GATE_MARKERS]}
    if action != "detect":
        return {"ok": False, "error": f"未知 action:{action}", "known": ["detect", "markers"]}
    blob = html or ""
    if not blob.strip():
        return {"ok": False, "error": "缺少 html（本函数只做离线判定，不抓页面）",
                "hint": "要抓页面请走 browser 能力位；本函数不做网络请求"}
    score, hits = 0, []
    for pat, weight, why in _GATE_MARKERS:
        m = re.search(pat, blob, re.I)
        if m:
            score += weight
            hits.append({"why": why, "weight": weight, "matched": m.group(0)[:120]})
    prob = min(99, score)
    visible = len(re.sub(r"<[^>]+>", "", blob))
    truncated = visible < 1200 and prob >= 20
    return {"ok": True, "op": "detect", "dimension": "防御",
            "gate_probability": prob, "hits": hits, "visible_text_chars": visible,
            "likely_truncated": truncated,
            "verdict": ("几乎确定被门挡住" if prob >= 60 else
                        "可能有门" if prob >= 25 else "未发现内容门"),
            "口径": "**只判不绕**；离线判定，不发任何请求；不伪装 UA、不伪造 cookie"}


def asset_vault_freeze(action: str = "audit", path: str = "", **_kw) -> dict:
    """资产**单点损失体检**（防勒索基线）。只体检与建议，**不实现冻结/加密**。"""
    action = (action or "audit").lower()
    if action != "audit":
        return {"ok": False, "error": f"未知 action:{action}", "known": ["audit"]}
    import winreg
    checks, findings = [], []
    # 卷影副本（勒索软件最常删的东西）
    sc, err = _ps_json("Get-CimInstance Win32_ShadowCopy | "
                       "Select-Object ID,InstallDate,VolumeName | ConvertTo-Json -Compress")
    n_sc = len(sc) if isinstance(sc, list) else (1 if sc else 0)
    checks.append({"check": "volume_shadow_copies", "count": n_sc,
                   "ok": n_sc > 0, "未读到": err or None})
    if n_sc == 0:
        findings.append({"severity": "high",
                         "why": "没有卷影副本 —— 勒索/误删后无本机回滚点"})
    # 受控文件夹访问（CFA，Defender 的反勒索开关）
    try:
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE,
                            r"SOFTWARE\Microsoft\Windows Defender\Features") as k:
            cfa = winreg.QueryValueEx(k, "TamperProtection")[0]
        checks.append({"check": "defender_tamper_protection", "value": cfa, "ok": bool(cfa)})
    except Exception as exc:                                    # noqa: BLE001
        checks.append({"check": "defender_tamper_protection", "ok": False,
                       "error": type(exc).__name__})
    # BitLocker
    bl, err2 = _ps_json("Get-CimInstance Win32_EncryptableVolume -ErrorAction SilentlyContinue | "
                        "Select-Object DriveLetter,ProtectionStatus | ConvertTo-Json -Compress")
    checks.append({"check": "bitlocker", "volumes": bl or [], "未读到": err2 or None})
    if not bl:
        findings.append({"severity": "medium", "why": "拿不到 BitLocker 状态（或未加密）—— 物理失窃即全丢"})
    # 关键资产清单
    key_dirs, total = [], 0
    for d in ("gbt_allinone/store", "memory", "delivery", "docs", "holo_pet/assets"):
        p = Path(__file__).resolve().parents[2] / d
        if p.is_dir():
            n = sum(1 for _ in p.rglob("*") if _.is_file())
            total += n
            key_dirs.append({"dir": d, "files": n})
    return {"ok": True, "op": "audit", "dimension": "防御（防勒索）",
            "checks": checks, "key_assets": key_dirs, "key_assets_total": total,
            "findings": findings,
            "口径": "只体检：读卷影副本/防护开关/加密状态。**不加密、不冻结、不改任何文件或开关**"}


# ══════════════════════════════════════════════════════════════════════════
# 完整性维（data_hijack 的检测侧）
# ══════════════════════════════════════════════════════════════════════════

def data_hijack(action: str = "session", path: str = "", **_kw) -> dict:
    """会话/数据**完整性检测**。只检测，不劫持 —— 没有中间人、没有重放、没有注入。"""
    action = (action or "session").lower()
    if action == "session":
        checks, findings = [], []
        # 本机会话
        try:
            import psutil
            users = [{"name": u.name, "host": u.host, "terminal": u.terminal,
                      "started": time.strftime("%Y-%m-%d %H:%M", time.localtime(u.started))}
                     for u in psutil.users()]
        except Exception as exc:                                # noqa: BLE001
            users, _ = [], None
            findings.append({"severity": "low", "why": f"会话枚举失败:{type(exc).__name__}"})
        checks.append({"check": "local_sessions", "count": len(users), "sessions": users})
        # 浏览器 cookie/token 落点的权限面（只 stat，不读内容）
        home = Path(os.environ.get("LOCALAPPDATA", ""))
        stores = []
        for pat in ("Google/Chrome/User Data/Default/Cookies",
                    "Microsoft/Edge/User Data/Default/Cookies",
                    "Google/Chrome/User Data/Default/Login Data"):
            p = home / pat
            if p.exists():
                stores.append({"path": str(p), "bytes": p.stat().st_size})
        checks.append({"check": "browser_credential_stores", "count": len(stores),
                       "stores": stores})
        if stores:
            findings.append({"severity": "medium",
                             "why": f"本机有 {len(stores)} 个浏览器凭据/会话库 —— "
                                    "这是会话劫持的首要目标，建议全盘加密 + 锁屏"})
        # 框架自己的账本完整性
        audit = Path(_paths.STORE_DIR) / "audit.jsonl"
        checks.append({"check": "framework_audit_ledger",
                       "exists": audit.exists(),
                       "lines": (len(audit.read_text(encoding="utf-8", errors="replace")
                                       .splitlines()) if audit.exists() else 0)})
        return {"ok": True, "op": "session", "dimension": "完整性", "checks": checks,
                "findings": findings,
                "口径": "只读取权限/体积/行数；**不读取 cookie 值、不读 token 明文**"}
    if action in ("baseline", "verify"):
        root = Path(path) if path else Path(__file__).resolve().parents[2]
        cur = {}
        n = 0
        for f in sorted(root.rglob("*")):
            # 🔴 2026-09-26 修（一字定生死）：原来两个条件共用 `break` —— sorted(rglob) 首项
            #    是目录，首条即 `not f.is_file()` ⇒ 整个循环当场退出 ⇒ 指纹恒为空 dict 的 sha
            #    ⇒ verify 对任何篡改都报"干净"（假绿）。目录该 continue 跳过，超限才 break。
            if n > 20000:
                break
            if not f.is_file():
                continue
            if any(part in (".git", "node_modules", "__pycache__", ".scratch", "store",
                            "vendor") for part in f.parts):
                continue
            try:
                st = f.stat()
                cur[str(f.relative_to(root))] = [st.st_size, int(st.st_mtime)]
                n += 1
            except Exception:                                   # noqa: BLE001
                continue
        digest = hashlib.sha256(
            json.dumps(cur, sort_keys=True).encode("utf-8")).hexdigest()[:16]
        if action == "baseline":
            _state_dir(_STATE)
            _BASELINE.write_text(json.dumps(
                {"root": str(root), "at": time.strftime("%Y-%m-%dT%H:%M:%S"),
                 "files": len(cur), "digest": digest}, ensure_ascii=False, indent=2),
                encoding="utf-8")
            return {"ok": True, "op": "baseline", "dimension": "完整性",
                    "root": str(root), "files": len(cur), "digest": digest,
                    "落点": str(_BASELINE)}
        prev = {}
        if _BASELINE.exists():
            try:
                prev = json.loads(_BASELINE.read_text(encoding="utf-8"))
            except Exception:                                   # noqa: BLE001
                prev = {}
        if not prev:
            return {"ok": False, "error": "还没有基线 —— 先 action=baseline",
                    "hint": 'run_task("data_hijack", {"action":"baseline"})'}
        drift = [] if prev.get("digest") == digest else [
            {"severity": "medium", "why": "文件树指纹与基线不一致",
             "baseline": prev.get("digest"), "now": digest,
             "baseline_at": prev.get("at"), "files_before": prev.get("files"),
             "files_now": len(cur)}]
        return {"ok": True, "op": "verify", "dimension": "完整性",
                "clean": not drift, "drift": drift, "files": len(cur), "digest": digest}
    return {"ok": False, "error": f"未知 action:{action}",
            "known": ["session", "baseline", "verify"]}


# ══════════════════════════════════════════════════════════════════════════
# 框架维：上手指引门
# ══════════════════════════════════════════════════════════════════════════

def onboarding_gate(action: str = "gaps", **_kw) -> dict:
    """未接线能力上手指引门：如实报"登记了但没实现"的缺口，并给出接线配方。"""
    action = (action or "gaps").lower()
    if action not in ("gaps", "list"):
        return {"ok": False, "error": f"未知 action:{action}", "known": ["gaps", "list"]}
    from ..caps_registry import BENIGN_CAPS, UNIMPLEMENTED_CAPS, all_caps
    gaps = sorted(UNIMPLEMENTED_CAPS)
    return {"ok": True, "op": "gaps", "dimension": "框架",
            "benign": len(BENIGN_CAPS), "unimplemented": len(gaps), "total": len(all_caps()),
            "gaps": gaps,
            "recipe": ("要给一个名字接上实现，三处都要动："
                       "① caps_registry.BENIGN_CAPS 的 {domain,desc,handler,safe}"
                       "② api.run_task 的 if 链加分支"
                       "③ policy.evaluate 给它挂作用域（否则门看不见它）"),
            "口径": "只读；不改注册表"}


# ══════════════════════════════════════════════════════════════════════════
# 统一入口
# ══════════════════════════════════════════════════════════════════════════

def _credential_steal(**_kw) -> dict:
    """`credential_steal` = 侦察维的 `creds`（凭据**暴露面**审计，防御侧）。"""
    return _recon_creds()


def _redteam_recon(**_kw) -> dict:
    """`redteam_recon` = 侦察维总入口。"""
    return recon(**_kw)


OPS = {
    "redteam_recon": _redteam_recon,
    "recon": recon,
    "pentest": pentest,
    "keylogger": keylogger,
    "screen_sniff": screen_sniff,
    "device_takeover": device_takeover,
    "remote_domain": remote_domain,
    "credential_steal": _credential_steal,
    "social_eng": social_eng,
    "paywallbuster": paywallbuster,
    "asset_vault_freeze": asset_vault_freeze,
    "data_hijack": data_hijack,
    "onboarding_gate": onboarding_gate,
}


def run(cap: str, payload: dict | None = None) -> dict:
    """能力位统一入口（`api.run_task` 的 if 链调它）。

    签名刻意收成 `(cap, payload)`：仓里的调用方把**能力位名**和 **payload 里的 op**
    都叫 "op"，展开成 kwargs 会撞名（`run(op=..., op=...)` = TypeError）。
    这里统一收进一个 dict，并把 `op` / `method` 归一成各实现认的 `action`。
    """
    fn = OPS.get(str(cap or "").strip())
    if not fn:
        return {"ok": False, "error": f"未知 op:{cap}", "known": sorted(OPS)}
    kw = dict(payload or {})
    if "action" not in kw:
        for alt in ("op", "method"):
            if kw.get(alt):
                kw["action"] = kw.pop(alt)
                break
    kw.pop("op", None)
    return fn(**kw)


if __name__ == "__main__":                                      # 被 detach 的记录子进程用
    if len(sys.argv) >= 3 and sys.argv[1] == "_record_input":
        _record_input(sys.argv[2], int(sys.argv[3]) if len(sys.argv) > 3 else 0)
    else:
        print(json.dumps({"error": "本模块只作为库使用；内部子命令：_record_input <path> <seconds>"},
                         ensure_ascii=False))
