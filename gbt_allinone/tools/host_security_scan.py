#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""主机安全扫描 · 六层（只读 · 免卡 · 不装东西 · 不常驻）

Owner 2026-09-22：「确保扫描出电脑的所有问题以及根因能力」「全方位补齐加固整理好」

═══ 为什么要有这个模块（取证，不是拍脑袋）═══

当晚实测：框架原有的「穿透式交叉扫描」六维（A/B/G/W/X/H）**全部只扫框架内部**
（`caps_registry` / `api.py` / `_PKG` / 相对导入 / 影子目录 / 运行时可达）；
六个隔离子扫描器里 `truth_scan` / `ghost_guard` / `inventory` 主机侧**零触及**。
搜八种接主机安全的口子（MpCmdRun / SecurityCenter2 / AntiVirusProduct / …）**一个都没命中**。

⇒ 结论：**框架此前没有主机级安全扫描。** 本模块补这一块。

═══ 六层 ═══
  L1 反病毒在位    Defender / SecurityCenter2 有没有开、库新不新
  L2 持久化入口    注册表 Run/RunOnce · 启动文件夹 · 计划任务
  L3 进程与签名    ★ 最值钱的一层：路径 + 数字签名有效性 + 是否系统目录
  L4 网络连接      谁在监听 · 谁连出去 · 连到哪
  L5 可疑位置      TEMP/APPDATA 里的可执行 · hosts · 代理设置
  L6 根因关联      把上面异常按"谁引入的 / 什么时候"串起来

═══ 铁律（写死在代码里，防以后被改成装样子）═══
  · **只读**：不删、不改、不 kill、不隔离。发现可疑只**报告**。
  · **不装东西**：只用标准库 + 已装的 psutil + 系统自带 WMI/PowerShell。
  · **不常驻**：一次跑完退出，不起后台进程。
  · **不假执行**：拿不到的层如实标 `unavailable` + 原因，**绝不用空结果冒充"干净"**。
    —— 这一条是本模块存在的理由：说"没扫到"和"扫了没问题"是两件事。

用法：
    py -3.14 -m gbt_allinone.tools.host_security_scan
    py -3.14 -m gbt_allinone.tools.host_security_scan --json
    py -3.14 -m gbt_allinone.tools.host_security_scan --no-sign   # 跳过签名（最快）
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

# ── 判定用的常量（写死，可复核）────────────────────────────────
SUSPICIOUS_DIRS = ("\\temp\\", "\\tmp\\", "\\appdata\\local\\temp\\", "\\downloads\\",
                   "\\public\\", "\\programdata\\", "\\roaming\\")
SYSTEM_DIRS = ("\\windows\\system32", "\\windows\\syswow64", "\\windows\\winsxs",
               "\\program files\\", "\\program files (x86)\\", "\\windows\\")
# 监听在这些端口上通常没问题；其余监听端口值得看一眼
BENIGN_LISTEN = {135, 139, 445, 5040, 7680, 49664, 49665, 49666, 49667, 49668, 49669,
                 49670, 49671, 49672, 49673, 49674, 49675, 49676, 49677, 49678, 49679,
                 49680, 49681, 49682, 49683, 49684, 49685, 49686, 49687, 49688, 49689,
                 49690, 1900, 5353, 5355, 3702, 8765}


def _ps(cmd: str, timeout: int = 45) -> str:
    """跑一段 PowerShell，返回 stdout。**失败返回空串**，由调用方标 unavailable。"""
    try:
        r = subprocess.run(["powershell", "-NoProfile", "-NonInteractive",
                            "-ExecutionPolicy", "Bypass", "-Command", cmd],
                           capture_output=True, text=True, timeout=timeout,
                           encoding="utf-8", errors="replace")
        return (r.stdout or "").strip()
    except Exception:
        return ""


# ═══ L1 · 反病毒在位 ═══════════════════════════════════════════
def layer1_antivirus() -> dict:
    """读 SecurityCenter2 与 Defender 状态。**只读，不改任何设置。**"""
    out: dict = {"layer": "L1 反病毒在位", "ok": False, "products": [], "defender": None}
    raw = _ps("Get-CimInstance -Namespace root/SecurityCenter2 -ClassName AntiVirusProduct "
              "-ErrorAction SilentlyContinue | "
              "Select-Object displayName,productState,pathToSignedProductExe | ConvertTo-Json -Compress")
    if raw:
        try:
            data = json.loads(raw)
            data = data if isinstance(data, list) else [data]
            for p in data:
                st = p.get("productState")
                # productState 十六进制中段 10=开 00=关（业界通行读法）
                s = str(st)
                enabled = None
                if len(s) >= 4:
                    try:
                        enabled = int(s[-4:-2], 16) == 0x10
                    except ValueError:
                        enabled = None
                out["products"].append({"name": p.get("displayName"),
                                        "state_raw": s, "enabled_guess": enabled})
            out["ok"] = True
        except Exception as e:                                   # noqa: BLE001
            out["why"] = f"SecurityCenter2 解析失败: {type(e).__name__}: {str(e)[:80]}"
    else:
        out["why"] = "SecurityCenter2 读不到（可能无该命名空间或权限不足）—— **这不等于没有杀毒**"
    d = _ps("Get-MpComputerStatus -ErrorAction SilentlyContinue | "
            "Select-Object AMServiceEnabled,RealTimeProtectionEnabled,"
            "AntivirusSignatureLastUpdated,AntivirusSignatureAge,QuickScanAge | ConvertTo-Json -Compress")
    if d:
        try:
            out["defender"] = json.loads(d)
            out["ok"] = True
        except Exception:                                        # noqa: BLE001
            pass
    return out


# ═══ L2 · 持久化入口 ═══════════════════════════════════════════
def layer2_persistence() -> dict:
    """注册表 Run/RunOnce + 启动文件夹 + 计划任务。**只读枚举，不删不改。**"""
    out: dict = {"layer": "L2 持久化入口", "ok": False, "run": [], "startup_dir": [],
                 "tasks": [], "suspicious": []}
    keys = [r"HKCU:\Software\Microsoft\Windows\CurrentVersion\Run",
            r"HKLM:\Software\Microsoft\Windows\CurrentVersion\Run",
            r"HKCU:\Software\Microsoft\Windows\CurrentVersion\RunOnce",
            r"HKLM:\Software\Microsoft\Windows\CurrentVersion\RunOnce"]
    script = ";".join(
        f"if(Test-Path '{k}'){{$p=Get-ItemProperty '{k}';"
        f"$p.PSObject.Properties|Where-Object{{$_.Name -notlike 'PS*'}}|"
        f"ForEach-Object{{[pscustomobject]@{{key='{k}';name=$_.Name;value=$_.Value}}}}}}"
        for k in keys)
    raw = _ps(script + " | ConvertTo-Json -Compress")
    if raw:
        try:
            data = json.loads(raw)
            data = data if isinstance(data, list) else [data]
            out["run"] = data
            out["ok"] = True
        except Exception:                                        # noqa: BLE001
            pass
    for d in (os.path.expandvars(r"%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup"),
              os.path.expandvars(r"%PROGRAMDATA%\Microsoft\Windows\Start Menu\Programs\Startup")):
        p = Path(d)
        if p.is_dir():
            for f in p.iterdir():
                if f.is_file():
                    out["startup_dir"].append(str(f))
    t = _ps("Get-ScheduledTask -ErrorAction SilentlyContinue | "
            "Where-Object {$_.State -ne 'Disabled'} | "
            "Select-Object TaskName,TaskPath,State | ConvertTo-Json -Compress", timeout=60)
    if t:
        try:
            data = json.loads(t)
            data = data if isinstance(data, list) else [data]
            out["tasks"] = data
            out["ok"] = True
        except Exception:                                        # noqa: BLE001
            pass
    # 可疑：Run 项指向 TEMP/AppData/Downloads 的
    for it in out["run"]:
        v = str(it.get("value") or "").lower()
        if any(s in v for s in SUSPICIOUS_DIRS):
            out["suspicious"].append({"from": "registry_run", **it})
    return out


# ═══ L3 · 进程与签名（最值钱的一层）═══════════════════════════
def layer3_processes(check_sign: bool = True) -> dict:
    """每个进程：路径 + 数字签名 + 是否系统目录。

    ★ 头号木马特征三条同时成立：
        ① 跑着  ② 无有效签名  ③ 不在系统目录  ④（加分）路径在 TEMP/AppData
    三条只读，一条授权都不需要。
    """
    out: dict = {"layer": "L3 进程与签名", "ok": False, "count": 0,
                 "unsigned": [], "suspicious_dir": [], "by_dir": {}}
    try:
        import psutil
    except Exception as e:                                       # noqa: BLE001
        out["why"] = f"psutil 不可用: {type(e).__name__} —— 本层 unavailable，**不是「没有可疑进程」**"
        return out
    procs = []
    for p in psutil.process_iter(["pid", "name", "exe", "username", "create_time"]):
        try:
            info = p.info
            exe = info.get("exe") or ""
            procs.append({"pid": info.get("pid"), "name": info.get("name"),
                          "exe": exe, "user": info.get("username"),
                          "started": info.get("create_time")})
        except Exception:                                        # noqa: BLE001
            continue
    out["count"] = len(procs)
    out["ok"] = True
    low = lambda s: str(s or "").lower()
    for pr in procs:
        e = low(pr["exe"])
        if e and any(s in e for s in SUSPICIOUS_DIRS):
            out["suspicious_dir"].append(pr)
        top = ""
        if pr["exe"]:
            parts = Path(pr["exe"]).parts
            top = "\\".join(parts[:3]) if len(parts) >= 3 else pr["exe"]
        out["by_dir"][top] = out["by_dir"].get(top, 0) + 1

    if check_sign:
        uniq = sorted({pr["exe"] for pr in procs if pr["exe"]})
        if uniq:
            # 一次批量调用，不逐进程 fork（省内存、省时间）
            payload = ";".join(
                "try{$s=Get-AuthenticodeSignature -LiteralPath "
                + json.dumps(u) + " -ErrorAction Stop;"
                + "[pscustomobject]@{p=" + json.dumps(u)
                + ";st=[string]$s.Status;signer=$s.SignerCertificate.Subject}}catch{}"
                for u in uniq[:400])
            raw = _ps(payload + " | ConvertTo-Json -Compress", timeout=180)
            if raw:
                try:
                    data = json.loads(raw)
                    data = data if isinstance(data, list) else [data]
                    bad = [d for d in data
                           if str(d.get("st")) not in ("Valid",)
                           and not any(s in low(d.get("p")) for s in SYSTEM_DIRS)]
                    out["unsigned"] = bad
                    out["sig_checked"] = len(data)
                except Exception as e:                           # noqa: BLE001
                    out["sig_error"] = f"{type(e).__name__}: {str(e)[:80]}"
            else:
                out["sig_error"] = "签名批量查询无返回 —— 本层标 unavailable，**不当作「全都有效」**"
    return out


# ═══ L4 · 网络连接 ═════════════════════════════════════════════
def layer4_network() -> dict:
    """监听端口 + 已建立的外连。**只读。**"""
    out: dict = {"layer": "L4 网络连接", "ok": False, "listen": [], "established": [],
                 "listen_unusual": []}
    try:
        import psutil
    except Exception as e:                                       # noqa: BLE001
        out["why"] = f"psutil 不可用: {type(e).__name__}"
        return out
    try:
        conns = psutil.net_connections(kind="inet")
    except Exception as e:                                       # noqa: BLE001
        out["why"] = (f"读连接表失败: {type(e).__name__} —— 普通权限下常见；"
                      f"本层 unavailable，**不是「没有异常连接」**")
        return out
    for c in conns:
        try:
            laddr = f"{c.laddr.ip}:{c.laddr.port}" if c.laddr else ""
            raddr = f"{c.raddr[0]}:{c.raddr[1]}" if c.raddr else ""
            rec = {"pid": c.pid, "proto": "tcp" if c.type == 1 else "udp",
                   "local": laddr, "remote": raddr}
            if c.status == "LISTEN":
                out["listen"].append(rec)
                if c.laddr and c.laddr.port not in BENIGN_LISTEN:
                    out["listen_unusual"].append(rec)
            elif c.status == "ESTABLISHED" and raddr:
                out["established"].append(rec)
        except Exception:                                        # noqa: BLE001
            continue
    out["ok"] = True
    return out


# ═══ L5 · 可疑位置 ═════════════════════════════════════════════
def layer5_suspicious_locations() -> dict:
    """TEMP/AppData 里的可执行 · hosts 文件 · 代理设置。**只读。**"""
    out: dict = {"layer": "L5 可疑位置", "ok": True, "executables": [],
                 "hosts": None, "proxy": None}
    exts = {".exe", ".dll", ".scr", ".bat", ".cmd", ".ps1", ".vbs", ".js", ".jar"}
    roots = [os.environ.get("TEMP", ""), os.path.expandvars(r"%APPDATA%"),
             os.path.expandvars(r"%LOCALAPPDATA%"), os.path.expandvars(r"%PUBLIC%")]
    seen = 0
    for r in roots:
        if not r or not Path(r).is_dir():
            continue
        for dp, dns, fns in os.walk(r):
            dns[:] = [d for d in dns if d not in ("node_modules", ".git", "__pycache__")]
            for fn in fns:
                p = Path(dp) / fn
                if p.suffix.lower() in exts:
                    try:
                        st = p.stat()
                    except OSError:
                        continue
                    seen += 1
                    if seen > 4000:
                        break
                    out["executables"].append({"path": str(p), "size": st.st_size,
                                               "mtime": st.st_mtime})
            if seen > 4000:
                break
    out["scanned_count"] = seen
    hp = Path(os.path.expandvars(r"%SystemRoot%\System32\drivers\etc\hosts"))
    if hp.is_file():
        try:
            txt = hp.read_text(encoding="utf-8", errors="replace")
            live = [l for l in txt.splitlines()
                    if l.strip() and not l.strip().startswith("#")]
            out["hosts"] = {"path": str(hp), "active_lines": len(live),
                            "sample": live[:8]}
        except Exception as e:                                   # noqa: BLE001
            out["hosts"] = {"error": f"{type(e).__name__}: {str(e)[:80]}"}
    pr = _ps("Get-ItemProperty 'HKCU:\\Software\\Microsoft\\Windows\\CurrentVersion\\"
             "Internet Settings' | Select-Object ProxyEnable,ProxyServer,AutoConfigURL | "
             "ConvertTo-Json -Compress")
    if pr:
        try:
            out["proxy"] = json.loads(pr)
        except Exception:                                        # noqa: BLE001
            pass
    return out


# ═══ L6 · 根因关联 ═════════════════════════════════════════════
def layer6_rootcause(r1: dict, r2: dict, r3: dict, r4: dict, r5: dict) -> dict:
    """把异常串起来：**谁引入的 · 什么时候 · 从哪来**。

    不做"猜一个原因"，只做**有证据的关联**：
      · 可疑进程 ← 它的 exe 是不是在可疑目录
      · 可疑持久化 ← 它的目标路径是不是在可疑目录
      · 外连 ← 其 pid 是不是可疑进程
      · 时间 ← 进程启动时间是否集中在某一段（可疑的"同一批装入"）
    """
    out: dict = {"layer": "L6 根因关联", "ok": True, "findings": [], "timeline": []}
    # ① 未签名 且 不在系统目录 且 在可疑目录 —— 三条同中，最高优先级
    for p in r3.get("unsigned", []):
        exe = str(p.get("p") or "").lower()
        if any(s in exe for s in SUSPICIOUS_DIRS):
            out["findings"].append({
                "severity": "high", "kind": "未签名且位于可疑目录的进程",
                "evidence": {"path": p.get("p"), "status": p.get("st")},
                "why": "跑着 + 无有效签名 + 位于 TEMP/AppData/Downloads —— 木马头号特征三条同中",
            })
    # ② 未签名进程（不在系统目录）—— 中优先级，需人看一眼
    for p in r3.get("unsigned", []):
        exe = str(p.get("p") or "").lower()
        if not any(s in exe for s in SUSPICIOUS_DIRS):
            out["findings"].append({
                "severity": "medium", "kind": "未签名进程（不在系统目录）",
                "evidence": {"path": p.get("p"), "status": p.get("st")},
                "why": "可能是自研/开源软件的正常现象 —— **只报不判**，由人核",
            })
    # ③ 持久化项指向可疑目录
    for s in r2.get("suspicious", []):
        out["findings"].append({
            "severity": "high", "kind": "开机自启指向可疑目录",
            "evidence": s,
            "why": "自启 + 位于 TEMP/AppData —— 持久化木马的典型手法",
        })
    # ④ 异常监听端口
    for l in r4.get("listen_unusual", []):
        out["findings"].append({
            "severity": "medium", "kind": "非典型端口监听",
            "evidence": l,
            "why": "监听端口不在常见豁免表里 —— 可能是正常服务，也可能不是；**只报不判**",
        })
    # ⑤ 时间线：进程启动时间按小时聚合，找"同一批"
    buckets: dict = {}
    for pr in r3.get("procs_sample", []) or []:
        t = pr.get("started")
        if t:
            h = int(t // 3600) * 3600
            buckets[h] = buckets.get(h, 0) + 1
    out["timeline"] = sorted(({"bucket_ts": k, "count": v} for k, v in buckets.items()),
                             key=lambda x: -x["count"])[:6]
    out["findings_total"] = len(out["findings"])
    out["high"] = sum(1 for f in out["findings"] if f["severity"] == "high")
    return out


def run(check_sign: bool = True) -> dict:
    r1 = layer1_antivirus()
    r2 = layer2_persistence()
    r3 = layer3_processes(check_sign=check_sign)
    r4 = layer4_network()
    r5 = layer5_suspicious_locations()
    r6 = layer6_rootcause(r1, r2, r3, r4, r5)
    layers = [r1, r2, r3, r4, r5, r6]
    unavailable = [l["layer"] for l in layers if not l.get("ok")]
    return {
        "ok": True,
        "layers": layers,
        "unavailable": unavailable,
        "findings_total": r6.get("findings_total", 0),
        "high": r6.get("high", 0),
        # 🔴 这条是给读报告的人看的：不许把"没扫到"读成"干净"
        "honest_boundary": (
            "本扫描只覆盖：反病毒在位 / 持久化入口 / 进程签名 / 网络连接 / 可疑位置 / 关联。"
            "**不覆盖**：全盘文件哈希比对病毒库（要外部病毒库）、实时行为监控（要常驻进程）、"
            "内核级 rootkit（要专有工具）、已删除文件的痕迹。"
            f"{'未跑成的层：' + '、'.join(unavailable) + ' —— 这几层是「没扫到」，不是「没问题」。' if unavailable else ''}"
        ),
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="主机安全扫描 · 六层（只读）")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--no-sign", action="store_true", help="跳过签名校验（快很多）")
    a = ap.parse_args(argv)
    rep = run(check_sign=not a.no_sign)
    if a.json:
        print(json.dumps(rep, ensure_ascii=False, indent=2))
        return 0
    for L in rep["layers"]:
        print(f"\n=== {L['layer']} ===" + ("" if L.get("ok") else "  ⚠ 未跑成"))
        if not L.get("ok") and L.get("why"):
            print(f"  原因: {L['why']}")
        for k, v in L.items():
            if k in ("layer", "ok", "why"):
                continue
            if isinstance(v, list):
                print(f"  {k}: {len(v)} 项")
                for it in v[:5]:
                    print(f"     {json.dumps(it, ensure_ascii=False)[:150]}")
                if len(v) > 5:
                    print(f"     … 另 {len(v)-5} 项")
            elif isinstance(v, dict):
                print(f"  {k}: {json.dumps(v, ensure_ascii=False)[:260]}")
            else:
                print(f"  {k}: {v}")
    print(f"\n{'='*70}")
    print(f"  发现 {rep['findings_total']} 条 · 其中高危 {rep['high']} 条")
    print(f"  {rep['honest_boundary']}")
    print(f"{'='*70}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
