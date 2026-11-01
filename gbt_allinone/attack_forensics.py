"""GBT小土豆V8 · 攻击取证与主动防御（合法边界内的"绝地反击"）

主人 2026-11-02：受攻击时要极限并发、采集足够证据、全面反击。
本模块做**合法**的那一半：
  · 攻击取证：本机证据全量采集（进程/连接/审计/最近文件/策略审计/系统信息），
    多触手（并行采集器）并发采集，产出带 sha256 的证据链 + ZIP；
  · 极限并发：回收**我们自己**的非必需进程/后台任务，给采集触手让出内存与算力；
  · 主动防御：给出封堵/限速/诱捕/凭据轮换建议，并可写防火墙封禁清单（只对本机生效）；
  · 合法报告：一键生成可交警方/CNCERT 的证据包（含时间线、哈希、采集者）。

**处置范围**：
  · 涉及第三方系统的动作超出本框架处置范围，
    本框架不实施；
  · 只对本机证据、自有资产、以及平台/警方要求的材料做处置。

开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属
"""
from __future__ import annotations

import hashlib
import json
import os
import platform
import shutil
import socket
import subprocess
import sys
import time
import zipfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "outputs" / "forensics"

# 超出处置范围的动作（由 counterstrike 统一返回 blocked_illegal）
ILLEGAL_OPS = {
    "power_off": "接管/切断攻击者电源",
    "console_takeover": "接管攻击者控制台",
    "kbm_cut": "切断攻击者键盘鼠标",
    "hack_back": "访问第三方主机",
    "wipe_attacker": "删除第三方数据",
}
LEGAL_BASIS = ("处置范围：本机取证、封堵、上报（仅限自有资产）；"
               "涉及第三方系统的动作不在本框架处置范围内。")

# 我们自己可回收的进程/后台（白名单：绝不能停的）
ESSENTIAL_NAMES = ("console-server.py", "llama-server", "model-bridge", "engine")
RECLAIMABLE_HINTS = ("omni-run.py", "mock_platform.py", "vuln_lab.py", "lab_scan.py",
                     "gradio", "jupyter", "electron")


def _sha256(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S")


# ── 采集器（只读本机，各自产出证据文件）────────────────────────────────
def _c_system(base: Path) -> dict:
    data = {"hostname": socket.gethostname(), "platform": platform.platform(),
            "cpu": os.cpu_count(), "pid": os.getpid(), "python": sys.version,
            "time": _now(), "user": os.environ.get("USERNAME")}
    (base / "system.json").write_text(json.dumps(data, ensure_ascii=False, indent=1),
                                      encoding="utf-8")
    return {"kind": "system", "files": ["system.json"], "note": "系统/主机身份"}


def _c_processes(base: Path) -> dict:
    rows = []
    try:
        out = subprocess.run(["powershell", "-NoProfile", "-Command",
                              "Get-CimInstance Win32_Process | Select-Object ProcessId,Name,"
                              "CommandLine,CreationDate | ConvertTo-Json -Compress"],
                             capture_output=True, text=True, timeout=30)
        rows = json.loads(out.stdout or "[]")
        if isinstance(rows, dict):
            rows = [rows]
    except Exception as e:  # noqa: BLE001
        rows = [{"error": str(e)[:120]}]
    (base / "processes.json").write_text(json.dumps(rows, ensure_ascii=False, indent=1),
                                         encoding="utf-8")
    return {"kind": "processes", "files": ["processes.json"], "count": len(rows),
            "note": "进程快照（含命令行，找可疑进程）"}


def _c_connections(base: Path) -> dict:
    rows = []
    try:
        out = subprocess.run(["powershell", "-NoProfile", "-Command",
                              "Get-NetTCPConnection | Select-Object LocalAddress,LocalPort,"
                              "RemoteAddress,RemotePort,State,OwningProcess | "
                              "ConvertTo-Json -Compress"],
                             capture_output=True, text=True, timeout=30)
        rows = json.loads(out.stdout or "[]")
        if isinstance(rows, dict):
            rows = [rows]
    except Exception as e:  # noqa: BLE001
        rows = [{"error": str(e)[:120]}]
    (base / "connections.json").write_text(json.dumps(rows, ensure_ascii=False, indent=1),
                                          encoding="utf-8")
    # 外连摘要（攻击者 IP 画像）
    remotes = {}
    for r in rows:
        ra = r.get("RemoteAddress")
        if ra and ra not in ("127.0.0.1", "::1", "0.0.0.0"):
            remotes[ra] = remotes.get(ra, 0) + 1
    (base / "remote-summary.json").write_text(
        json.dumps(sorted(remotes.items(), key=lambda x: -x[1])[:200], ensure_ascii=False,
                   indent=1), encoding="utf-8")
    return {"kind": "connections", "files": ["connections.json", "remote-summary.json"],
            "count": len(rows), "note": "网络连接 + 外连 IP 摘要"}


def _c_audit(base: Path) -> dict:
    files = []
    for rel in ("gbt_allinone/store/audit.jsonl", "state/orchestration-ledger.jsonl",
                "state/security-policy-audit.jsonl", "state/omni-plug.jsonl"):
        p = ROOT / rel
        if p.is_file():
            dst = base / ("audit-" + p.name)
            shutil.copy2(p, dst)
            files.append(dst.name)
    return {"kind": "audit", "files": files, "note": "审计/账本/策略日志（时间线）"}


def _c_recent_files(base: Path) -> dict:
    rows = []
    cutoff = time.time() - 24 * 3600
    for p in ROOT.rglob("*"):
        try:
            if not p.is_file() or "outputs" in p.parts or "state" in p.parts:
                continue
            st = p.stat()
            if st.st_mtime >= cutoff:
                rows.append({"path": str(p.relative_to(ROOT)), "mtime": int(st.st_mtime),
                             "bytes": st.st_size})
        except Exception:
            continue
    rows.sort(key=lambda x: -x["mtime"])
    (base / "recent-files.json").write_text(json.dumps(rows[:500], ensure_ascii=False, indent=1),
                                           encoding="utf-8")
    return {"kind": "recent-files", "files": ["recent-files.json"], "count": len(rows[:500]),
            "note": "近 24h 被改文件（找植入/篡改）"}


def _c_policy(base: Path) -> dict:
    data = {}
    for rel in ("state/security-policy.json",):
        p = ROOT / rel
        if p.is_file():
            data[rel] = json.loads(p.read_text(encoding="utf-8"))
    (base / "policy-state.json").write_text(json.dumps(data, ensure_ascii=False, indent=1),
                                           encoding="utf-8")
    return {"kind": "policy", "files": ["policy-state.json"], "note": "当前安全策略/攻击模式状态"}




def _ps(cmd: str, timeout: int = 30) -> object:
    out = subprocess.run(["powershell", "-NoProfile", "-Command", cmd],
                         capture_output=True, text=True, timeout=timeout)
    return json.loads(out.stdout or "[]")


def _c_eventlog(base: Path) -> dict:
    """安全/系统事件最近 200 条（需权限；无权限如实标注）。"""
    try:
        rows = _ps("Get-WinEvent -LogName Security -MaxEvents 200 -ErrorAction Stop | "
                   "Select-Object TimeCreated,Id,ProviderName,Message | "
                   "ConvertTo-Json -Compress", timeout=60)
        (base / "eventlog-security.json").write_text(
            json.dumps(rows, ensure_ascii=False, indent=1), encoding="utf-8")
        return {"kind": "eventlog", "files": ["eventlog-security.json"],
                "count": len(rows) if isinstance(rows, list) else 1,
                "note": "Windows 安全事件（登录/失败/权限）"}
    except Exception as e:  # noqa: BLE001
        (base / "eventlog-unavailable.json").write_text(
            json.dumps({"reason": "需要管理员权限或事件日志不可读：%s" % str(e)[:160]},
                       ensure_ascii=False, indent=1), encoding="utf-8")
        return {"kind": "eventlog", "files": ["eventlog-unavailable.json"],
                "available": False, "note": "安全事件日志不可读（如实标注，不伪造）"}


def _c_services(base: Path) -> dict:
    rows = _ps("Get-Service | Select-Object Name,DisplayName,Status,StartType | "
               "ConvertTo-Json -Compress")
    (base / "services.json").write_text(json.dumps(rows, ensure_ascii=False, indent=1),
                                       encoding="utf-8")
    return {"kind": "services", "files": ["services.json"], "note": "服务运行状态（可疑服务）"}


def _c_tasks(base: Path) -> dict:
    rows = _ps("Get-ScheduledTask | Select-Object TaskName,TaskPath,State | "
               "ConvertTo-Json -Compress")
    (base / "scheduled-tasks.json").write_text(json.dumps(rows, ensure_ascii=False, indent=1),
                                               encoding="utf-8")
    return {"kind": "scheduled-tasks", "files": ["scheduled-tasks.json"],
            "note": "计划任务（持久化点）"}


def _c_startup(base: Path) -> dict:
    rows = _ps("Get-CimInstance Win32_StartupCommand | Select-Object Name,Command,Location,User | "
               "ConvertTo-Json -Compress")
    (base / "startup.json").write_text(json.dumps(rows, ensure_ascii=False, indent=1),
                                      encoding="utf-8")
    return {"kind": "startup", "files": ["startup.json"], "note": "开机自启（持久化点）"}


def _c_users(base: Path) -> dict:
    rows = _ps("Get-LocalUser | Select-Object Name,Enabled,LastLogon,Description | "
               "ConvertTo-Json -Compress")
    (base / "users.json").write_text(json.dumps(rows, ensure_ascii=False, indent=1),
                                     encoding="utf-8")
    return {"kind": "users", "files": ["users.json"], "note": "本地账户（异常账户）"}


def _c_netconfig(base: Path) -> dict:
    rows = _ps("Get-NetIPConfiguration | ConvertTo-Json -Compress")
    arp = _ps("Get-NetNeighbor -ErrorAction SilentlyContinue | Select-Object IPAddress,"
              "LinkLayerAddress,State | ConvertTo-Json -Compress")
    dns = _ps("Get-DnsClientCache | Select-Object Entry,Data,TimeToLive | "
              "ConvertTo-Json -Compress")
    (base / "netconfig.json").write_text(json.dumps(rows, ensure_ascii=False, indent=1),
                                         encoding="utf-8")
    (base / "arp.json").write_text(json.dumps(arp, ensure_ascii=False, indent=1),
                                   encoding="utf-8")
    (base / "dns-cache.json").write_text(json.dumps(dns, ensure_ascii=False, indent=1),
                                         encoding="utf-8")
    return {"kind": "network", "files": ["netconfig.json", "arp.json", "dns-cache.json"],
            "note": "网卡/ARP/DNS 缓存（横向移动痕迹）"}


def _c_firewall(base: Path) -> dict:
    rows = _ps("Get-NetFirewallProfile | Select-Object Name,Enabled,DefaultInboundAction,"
               "DefaultOutboundAction | ConvertTo-Json -Compress")
    rules = _ps("Get-NetFirewallRule -ErrorAction SilentlyContinue | Where-Object Enabled -eq True | "
                "Select-Object DisplayName,Direction,Action,Profile | ConvertTo-Json -Compress")
    (base / "firewall-profiles.json").write_text(json.dumps(rows, ensure_ascii=False, indent=1),
                                                 encoding="utf-8")
    (base / "firewall-rules.json").write_text(json.dumps(rules, ensure_ascii=False, indent=1),
                                              encoding="utf-8")
    return {"kind": "firewall", "files": ["firewall-profiles.json", "firewall-rules.json"],
            "note": "防火墙状态（封堵依据/被改痕迹）"}


def _c_software(base: Path) -> dict:
    rows = _ps("Get-ItemProperty 'HKLM:\\Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\*' | "
               "Where-Object DisplayName | Select-Object DisplayName,DisplayVersion,InstallDate,Publisher | "
               "ConvertTo-Json -Compress")
    (base / "installed-software.json").write_text(json.dumps(rows, ensure_ascii=False, indent=1),
                                                  encoding="utf-8")
    return {"kind": "software", "files": ["installed-software.json"],
            "note": "已安装软件（可疑软件/后门）"}


def _c_memory(base: Path) -> dict:
    """内存转储：需要 procdump/管理员；没有则如实标 unavailable（绝不伪造）。"""
    procdump = shutil.which("procdump") or shutil.which("procdump64")
    if not procdump:
        (base / "memory-unavailable.json").write_text(json.dumps(
            {"reason": "未安装 procdump/内存转储工具，且默认无管理员权限；不伪造内存证据"},
            ensure_ascii=False, indent=1), encoding="utf-8")
        return {"kind": "memory", "files": ["memory-unavailable.json"], "available": False,
                "note": "内存证据不可用（如实标注）"}
    try:
        out = base / "memory.dmp"
        subprocess.run([procdump, "-accepteula", "-ma", "-o", str(out), str(os.getpid())],
                       capture_output=True, timeout=120)
        if out.is_file():
            return {"kind": "memory", "files": ["memory.dmp"], "note": "内存转储"}
    except Exception:  # noqa: BLE001
        pass
    (base / "memory-unavailable.json").write_text(json.dumps(
        {"reason": "procdump 存在但转储失败（权限/路径）；如实标注"},
        ensure_ascii=False, indent=1), encoding="utf-8")
    return {"kind": "memory", "files": ["memory-unavailable.json"], "available": False,
            "note": "内存证据不可用（如实标注）"}


def _c_timeline(base: Path) -> dict:
    """把审计/策略/账本事件合成时间线（给警方看的顺序）。"""
    events = []
    for rel, tag in (("gbt_allinone/store/audit.jsonl", "audit"),
                     ("state/security-policy-audit.jsonl", "policy"),
                     ("state/orchestration-ledger.jsonl", "ledger"),
                     ("state/attack-evidence.jsonl", "evidence")):
        p = ROOT / rel
        if not p.is_file():
            continue
        for ln in p.read_text(encoding="utf-8", errors="replace").splitlines()[-300:]:
            if not ln.strip():
                continue
            try:
                d = json.loads(ln)
            except Exception:
                continue
            t = str(d.get("at") or d.get("iso") or "")
            events.append({"at": t, "source": tag, "event": str(d.get("event") or d.get("type") or ""),
                           "summary": str(d)[:300]})
    events.sort(key=lambda x: x.get("at") or "")
    (base / "timeline.json").write_text(json.dumps(events, ensure_ascii=False, indent=1),
                                        encoding="utf-8")
    lines = ["# 攻击事件时间线（自动合成）", ""]
    for e in events[-200:]:
        lines.append("- %s [%s] %s — %s" % (e.get("at"), e.get("source"),
                                            e.get("event"), e.get("summary")[:160]))
    (base / "timeline.md").write_text(chr(10).join(lines) + chr(10), encoding="utf-8")
    return {"kind": "timeline", "files": ["timeline.json", "timeline.md"],
            "count": len(events), "note": "合成事件时间线（按时间排序）"}


COLLECTORS = [
    ("system", _c_system), ("processes", _c_processes), ("connections", _c_connections),
    ("eventlog", _c_eventlog), ("services", _c_services), ("scheduled-tasks", _c_tasks),
    ("startup", _c_startup), ("users", _c_users), ("network", _c_netconfig),
    ("firewall", _c_firewall), ("software", _c_software), ("memory", _c_memory),
    ("audit", _c_audit), ("recent-files", _c_recent_files), ("timeline", _c_timeline),
    ("policy", _c_policy),
]



def collect(agents: int = 32, incident: str = "") -> dict:
    """多触手（并行采集器）极限并发采集，产出证据链 + ZIP。"""
    agents = max(2, min(int(agents), 64))
    iid = incident or time.strftime("%Y%m%d-%H%M%S")
    base = OUT / iid
    base.mkdir(parents=True, exist_ok=True)
    results = []
    t0 = time.time()
    with ThreadPoolExecutor(max_workers=agents) as ex:
        futs = {ex.submit(fn, base): name for name, fn in COLLECTORS}
        for fut in futs:
            name = futs[fut]
            try:
                r = fut.result()
            except Exception as e:  # noqa: BLE001
                r = {"kind": name, "error": str(e)[:200], "files": []}
            results.append(r)
    files = sorted([p for p in base.iterdir() if p.is_file()])
    # 哈希链：prev_chain = sha256(prev_chain + file_sha256)，任何人改一个文件链就断
    chain, prev = [], "GENESIS"
    for p in files:
        fh = _sha256(p)
        link = hashlib.sha256((prev + fh).encode()).hexdigest()
        chain.append({"name": p.name, "sha256": fh, "prev": prev, "chain": link,
                      "bytes": p.stat().st_size, "at": _now()})
        prev = link
    manifest = {
        "incident": iid, "at": _now(), "agents": agents,
        "collectors": results, "elapsed_ms": int((time.time() - t0) * 1000),
        "files": [{"name": p.name, "sha256": _sha256(p), "bytes": p.stat().st_size}
                  for p in files],
        "hash_chain": chain, "chain_root": prev,
        "chain_of_custody": {
            "collector": "GBT小土豆V8（本机只读采集）",
            "owner": os.environ.get("USERNAME"),
            "notice": "哈希为采集时快照；提交警方/CNCERT 前请勿再改动本目录"},
    }
    mf = base / "manifest.json"
    mf.write_text(json.dumps(manifest, ensure_ascii=False, indent=1), encoding="utf-8")
    files.append(mf)
    # 证据索引（交警方/CNCERT 的目录）
    idx = ["# 证据索引 %s" % iid, "",
           "- 采集时间: %s" % _now(),
           "- 机器: %s" % socket.gethostname(),
           "- 采集器: %d 个（极限并发 agents=%d，耗时 %dms）" % (len(results), agents, manifest["elapsed_ms"]),
           "- 哈希链根: `%s`" % prev, "",
           "## 文件清单（sha256）"]
    for f in manifest["files"]:
        idx.append("- `%s` — `%s` (%d bytes)" % (f["name"], f["sha256"], f["bytes"]))
    idx += ["", "## 法律声明", "",
            "本证据包由 GBT小土豆V8 在本机只读采集；哈希链可校验是否被改；",
            "提交警方/CNCERT 前请勿修改本目录内容，否则 chain_root 失效。", ""]
    idxp = base / "evidence-index.md"
    idxp.write_text("\n".join(idx), encoding="utf-8")
    files.append(idxp)
    zpath = OUT / ("%s-evidence.zip" % iid)
    with zipfile.ZipFile(zpath, "w", zipfile.ZIP_DEFLATED) as z:
        for f in files:
            z.write(f, f.name)
    return {"ok": True, "incident": iid, "dir": str(base), "zip": str(zpath),
            "files": len(files), "agents": agents,
            "collectors": [r.get("kind") for r in results],
            "elapsed_ms": manifest["elapsed_ms"],
            "zip_sha256": _sha256(zpath), "zip_bytes": zpath.stat().st_size}


def _free_mb() -> int:
    try:
        out = subprocess.run(["powershell", "-NoProfile", "-Command",
                              "(Get-CimInstance Win32_OperatingSystem).FreePhysicalMemory"],
                             capture_output=True, text=True, timeout=20)
        return int((out.stdout or "0").strip() or 0) // 1024
    except Exception:  # noqa: BLE001
        return 0


def reclaim_own_workers(apply: bool = False) -> dict:
    """极限并发：回收**我们自己**的非必需进程（不碰系统/用户进程）。"""
    before = _free_mb()
    rows = []
    try:
        out = subprocess.run(["powershell", "-NoProfile", "-Command",
                              "Get-CimInstance Win32_Process | Select-Object ProcessId,Name,"
                              "CommandLine | ConvertTo-Json -Compress"],
                             capture_output=True, text=True, timeout=30)
        rows = json.loads(out.stdout or "[]")
        if isinstance(rows, dict):
            rows = [rows]
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "reason": str(e)[:160]}
    candidates, kept = [], 0
    me = os.getpid()
    for r in rows:
        cl = str(r.get("CommandLine") or "")
        if not cl or "python" not in cl.lower() and "electron" not in cl.lower():
            continue
        if (str(ROOT) not in cl and str(ROOT.parent) not in cl
                and not any(h in cl for h in RECLAIMABLE_HINTS)):
            continue
        if any(e in cl for e in ESSENTIAL_NAMES):
            kept += 1
            continue
        if int(r.get("ProcessId") or 0) == me:
            continue
        candidates.append({"pid": r.get("ProcessId"), "name": r.get("Name"),
                           "cmd": cl[:160]})
    stopped = []
    if apply:
        for c in candidates:
            try:
                subprocess.run(["taskkill", "/PID", str(c["pid"]), "/F"],
                               capture_output=True, timeout=15)
                stopped.append(c["pid"])
            except Exception:
                pass
    after = _free_mb()
    return {"ok": True, "reclaimed_candidates": candidates, "stopped": stopped,
            "kept_essential": kept, "apply": bool(apply),
            "free_mb_before": before, "free_mb_after": after,
            "freed_mb": max(0, after - before),
            "notice": "只回收本框架自己的非必需进程；系统/用户进程一律不碰（要关需主人确认）"}


def counterstrike(op: str, target: str = "") -> dict:
    """超出处置范围的请求：统一返回 blocked_illegal（无绕过）。"""
    if op in ILLEGAL_OPS:
        return {"ok": False, "blocked_illegal": True, "op": op,
                "action": ILLEGAL_OPS[op],
                "reason": "%s 超出本框架处置范围。" % ILLEGAL_OPS[op],
                "legal_basis": LEGAL_BASIS,
                "legal_alternatives": [
                    "本机取证（collect）并生成证据包",
                    "封禁攻击者 IP / 限速 / 关闭暴露端口（仅本机防火墙）",
                    "诱捕（蜜罐/tarpit）拖住攻击者并继续取证",
                    "向平台安全团队/警方/CNCERT 报案并提交证据包",
                ]}
    return {"ok": False, "reason": "未知动作；本模块处置范围为本机取证与合法防御"}


def respond(reason: str, evidence: str = "", agents: int = 32, ttl: int = 600,
            reclaim: bool = True, incident: str = "", user_report: bool = False) -> dict:
    """受攻击响应：**先举证** → 进攻击模式（V8 自我决策）→ 回收资源 → 极限并发取证 → 证据包。
    没证据：明确返回"未发现被攻击证据"，不进入攻击模式。"""
    sys.path.insert(0, str(ROOT))
    from gbt_allinone import security_policy as SP
    on = SP.enter_attack_mode(reason or "detected attack", evidence, ttl,
                              user_report=user_report)
    if not on.get("ok") and on.get("not_admitted"):
        return {"ok": False, "not_admitted": True,
                "conclusion": "未发现被攻击证据",
                "explain": on.get("explain"),
                "hint": on.get("hint"),
                "rule": "没证据不许说被攻击；如确有攻击，请用 --user-report 记录陈述或先取证",
                "counterstrike_policy": "本框架处置范围：本机取证与合法防御（docs/127）"}
    rec = reclaim_own_workers(apply=reclaim)
    col = collect(agents=agents, incident=incident)
    out = {"ok": True, "attack_mode": on.get("attack"), "reclaim": rec,
           "collect": col,
           "legal_alternatives": [
               "封禁攻击者 IP（防火墙/安全组，只对自有资产）",
               "关闭/限制暴露端口，启用限速",
               "诱捕拖住攻击者，继续取证",
               "把证据包交平台/警方/CNCERT 追责",
           ],
           "counterstrike_policy": "本框架处置范围：本机取证与合法防御（docs/127）"}
    try:
        from gbt_allinone import orchestration as OB
        OB.record("incident", "attack-forensics",
                  detail="受攻击响应：攻击模式 + 回收资源 + %d 采集器取证；证据包 %s"
                         % (col.get("collectors") and len(col["collectors"]) or 0, col.get("zip")),
                  evidence=col.get("zip"))
    except Exception:  # noqa: BLE001
        pass
    return out


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["collect", "reclaim", "respond", "counterstrike"])
    ap.add_argument("--reason", default="detected attack")
    ap.add_argument("--evidence", default="")
    ap.add_argument("--agents", type=int, default=32)
    ap.add_argument("--ttl", type=int, default=600)
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--op", default="")
    a = ap.parse_args()
    if a.cmd == "collect":
        out = collect(agents=a.agents)
    elif a.cmd == "reclaim":
        out = reclaim_own_workers(apply=a.apply)
    elif a.cmd == "respond":
        out = respond(a.reason, a.evidence, a.agents, a.ttl, reclaim=a.apply)
    else:
        out = counterstrike(a.op)
    print(json.dumps(out, ensure_ascii=False, indent=2))
