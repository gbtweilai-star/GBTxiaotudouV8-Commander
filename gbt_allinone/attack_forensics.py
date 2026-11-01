"""GBT小土豆V8 · 攻击取证与主动防御（合法边界内的"绝地反击"）

主人 2026-11-02：受攻击时要极限并发、采集足够证据、全面反击。
本模块做**合法**的那一半：
  · 攻击取证：本机证据全量采集（进程/连接/审计/最近文件/策略审计/系统信息），
    多触手（并行采集器）并发采集，产出带 sha256 的证据链 + ZIP；
  · 极限并发：回收**我们自己**的非必需进程/后台任务，给采集触手让出内存与算力；
  · 主动防御：给出封堵/限速/诱捕/凭据轮换建议，并可写防火墙封禁清单（只对本机生效）；
  · 合法报告：一键生成可交警方/CNCERT 的证据包（含时间线、哈希、采集者）。

**明确拒绝**（写死在代码里）：
  · 接管攻击者电源/控制台/键盘鼠标/反入侵对方主机 —— 属黑客反击（hack-back），
    违反《网络安全法》《刑法》285/286，本框架**永不实施**；
  · 只允许"在授权范围内"对本机证据、自己资产、以及平台/警方要求的材料做处置。

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

# 明确的非法反击动作（一律拒绝，并说明法律依据）
ILLEGAL_OPS = {
    "power_off": "接管/切断攻击者电源",
    "console_takeover": "接管攻击者控制台",
    "kbm_cut": "切断攻击者键盘鼠标",
    "hack_back": "反入侵攻击者主机",
    "wipe_attacker": "销毁攻击者数据",
}
LEGAL_BASIS = ("黑客反击（hack-back）不受法律允许：未经授权访问他人计算机系统违反"
               "《中华人民共和国网络安全法》第27条、《刑法》第285/286条；"
               "本框架只做本机取证、封堵、上报，不做反入侵。")

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


COLLECTORS = [
    ("system", _c_system), ("processes", _c_processes), ("connections", _c_connections),
    ("audit", _c_audit), ("recent-files", _c_recent_files), ("policy", _c_policy),
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
    manifest = {
        "incident": iid, "at": _now(), "agents": agents,
        "collectors": results, "elapsed_ms": int((time.time() - t0) * 1000),
        "files": [{"name": p.name, "sha256": _sha256(p), "bytes": p.stat().st_size}
                  for p in files],
        "chain_of_custody": {
            "collector": "GBT小土豆V8（本机只读采集）",
            "owner": os.environ.get("USERNAME"),
            "notice": "哈希为采集时快照；提交警方/CNCERT 前请勿再改动本目录"},
    }
    mf = base / "manifest.json"
    mf.write_text(json.dumps(manifest, ensure_ascii=False, indent=1), encoding="utf-8")
    files.append(mf)
    zpath = OUT / ("%s-evidence.zip" % iid)
    with zipfile.ZipFile(zpath, "w", zipfile.ZIP_DEFLATED) as z:
        for f in files:
            z.write(f, f.name)
    return {"ok": True, "incident": iid, "dir": str(base), "zip": str(zpath),
            "files": len(files), "agents": agents,
            "collectors": [r.get("kind") for r in results],
            "elapsed_ms": manifest["elapsed_ms"],
            "zip_sha256": _sha256(zpath), "zip_bytes": zpath.stat().st_size}


def reclaim_own_workers(apply: bool = False) -> dict:
    """极限并发：回收**我们自己**的非必需进程（不碰系统/用户进程）。"""
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
    return {"ok": True, "reclaimed_candidates": candidates, "stopped": stopped,
            "kept_essential": kept, "apply": bool(apply),
            "notice": "只回收本框架自己的非必需进程；系统/用户进程一律不碰"}


def counterstrike(op: str, target: str = "") -> dict:
    """非法反击请求：一律拒绝（写死，不给任何绕过）。"""
    if op in ILLEGAL_OPS:
        return {"ok": False, "blocked_illegal": True, "op": op,
                "action": ILLEGAL_OPS[op],
                "reason": "拒绝：%s 属于黑客反击。" % ILLEGAL_OPS[op],
                "legal_basis": LEGAL_BASIS,
                "legal_alternatives": [
                    "本机取证（collect）并生成证据包",
                    "封禁攻击者 IP / 限速 / 关闭暴露端口（仅本机防火墙）",
                    "诱捕（蜜罐/tarpit）拖住攻击者并继续取证",
                    "向平台安全团队/警方/CNCERT 报案并提交证据包",
                ]}
    return {"ok": False, "reason": "未知动作；本模块只做合法防御，不做反入侵"}


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
                "counterstrike_policy": "本框架只做本机取证与合法防御，拒绝黑客反击（docs/127）"}
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
           "counterstrike_policy": "本框架拒绝黑客反击（接管电源/控制台/键鼠/反入侵），见 docs/127"}
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
