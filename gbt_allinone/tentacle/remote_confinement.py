# -*- coding: utf-8 -*-
# gbt-capability: subprocess, filesystem_write  ⏻ 开发者：自由的风 · GBT小土豆V8 · 永久钢印
"""执行者隔离（remote_confinement）—— 把**执行的人**也关进去，不只是关被测的靶标。

主人 2026-10-09 点破的缺口（原话）：
  「沙盒隔离的是**被测试的东西**（靶标），没有隔离**执行的人**（云端模型）。
    云端模型通过这条中继敲的命令，跑在你的真实账号上。」

现状对照（本仓真读数，不是推断）：
  · 靶标：hacker-mirror 房间「dimension/」（隔离✅，reality 不动）
  · 执行：tentacle/desktop_commander.remote_start() —— subprocess.Popen(第三方包 remote 子命令)，
    以**当前用户身份**跑（实测 whoami=desktop-vpvp0bp\admin，本机未提权但仍是主人账号）
  ⇒ 中间**没有隔断**。本件就是那道隔断。

三条纪律：
  ① **默认拒启**：隔离面不成立时，remote_start 一律拒绝（fail-closed），不许「先跑起来再说」；
  ② **门保留**：remote_device 授权仍由主人在终端发；AI 无权自授（本件只**查**这张票，不发）；
  ③ **给启用路径**：拒绝时必须说清「这台机器上怎么才算隔离」——本机现读的三条：
     · WSL（Ubuntu 在）  · 低权账号（CodexSandboxOffline / srt-sandbox 在）  · Docker（守护进程未跑）
"""
from __future__ import annotations

import json
import shutil
import subprocess
import time
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent.parent
STATE = _ROOT / "gbt_allinone" / "store" / "remote_confinement.json"
PID = _ROOT / "gbt_allinone" / "store" / "dc_remote.pid"
DEFAULT_TTL_S = 1800          # 中继最长活着 30 分钟（看门狗口径）


def _run(cmd, timeout=25):
    try:
        cp = subprocess.run(cmd, capture_output=True, timeout=timeout)
        out = ((cp.stdout or b"") + (cp.stderr or b"")).decode("utf-8", "replace").strip()
        return {"ok": cp.returncode == 0, "rc": cp.returncode, "out": out[:400]}
    except Exception as exc:                                       # noqa: BLE001
        return {"ok": False, "rc": None, "out": ("%s: %s" % (type(exc).__name__, exc))[:200]}


def _identity() -> dict:
    who = _run(["whoami"])
    admin = _run(["powershell", "-NoProfile", "-Command",
                  "([Security.Principal.WindowsPrincipal]::new("
                  "[Security.Principal.WindowsIdentity]::GetCurrent())).IsInRole("
                  "[Security.Principal.WindowsBuiltInRole]::Administrator)"])
    return {"whoami": who.get("out") or "", "elevated": (admin.get("out") or "").strip().lower() == "true"}


def _relay_pid() -> int:
    try:
        return int(PID.read_text(encoding="utf-8").strip() or 0)
    except (OSError, ValueError):
        return 0


def _pid_alive(pid: int) -> bool:
    if not pid:
        return False
    try:
        cp = subprocess.run(["tasklist", "/FI", "PID eq %d" % pid],
                            capture_output=True, timeout=15)
        return str(pid) in (cp.stdout or b"").decode("utf-8", "replace")
    except Exception:                                              # noqa: BLE001
        return False


def _surface() -> dict:
    """本机**现读**的隔离面（不是猜）：三条路各自能不能用。"""
    docker_cli = shutil.which("docker")
    docker_daemon = _run(["docker", "version", "--format", "{{.Server.Version}}"]) if docker_cli else {"ok": False, "out": "docker 不在 PATH"}
    wsl = shutil.which("wsl")
    distros = []
    if wsl:
        d = _run(["wsl", "-l", "-q"])
        distros = [x.strip() for x in (d.get("out") or "").replace("\x00", "").splitlines() if x.strip()]
    users = _run(["powershell", "-NoProfile", "-Command",
                  "(Get-LocalUser | Where-Object {$_.Enabled} | Select-Object -ExpandProperty Name) -join ','"])
    lows = [u for u in (users.get("out") or "").split(",")
            if u.strip() and u.strip().lower() not in ("administrator", "admin", "guest", "defaultaccount")]
    return {"docker_cli": bool(docker_cli), "docker_daemon": bool(docker_daemon.get("ok")),
            "docker_note": (docker_daemon.get("out") or "")[:120],
            "wsl": bool(wsl), "wsl_distros": distros,
            "low_priv_accounts": lows}


def assess() -> dict:
    """执行面现状（只读，逐项现读）。"""
    ident, surf = _identity(), _surface()
    pid = _relay_pid()
    return {"ok": True, "op": "assess", "执行身份": ident,
            "中继": {"pid": pid or None, "alive": _pid_alive(pid)},
            "隔离面": surf}


def verify_profile(profile: str) -> dict:
    """**真验**一条隔离路能不能跑（不是看它在不在）。没验过 = 不算数。"""
    s = _surface()
    if profile == "docker":
        if not s["docker_daemon"]:
            return {"ok": False, "evidence": "Docker 守护进程未跑：%s" % s["docker_note"][:80]}
        r = _run(["docker", "run", "--rm", "node:22-alpine", "node", "-e",
                 "console.log(chr(99)+chr(111)+chr(110)+chr(102)+chr(105)+chr(110)+chr(101)+chr(100))"], timeout=180)
        return {"ok": r["ok"], "evidence": (r["out"] or ("rc=%s" % r["rc"]))[:140]}
    if profile == "wsl":
        d = s["wsl_distros"]
        if not d:
            return {"ok": False, "evidence": "WSL 无发行版"}
        r = _run(["wsl", "-d", d[0], "--", "node", "-v"], timeout=90)
        return {"ok": r["ok"], "evidence": ("%s: %s" % (d[0], r["out"]))[:140]}
    if profile == "low_priv_account":
        return {"ok": False,
                "evidence": "低权账号在（%s）但**免交互启动未配**：runas 要交互口令，脚本起不来"
                            " ⇒ 需主人先配好（本件不代配、也不会替你存口令）"
                            % ",".join(s["low_priv_accounts"])}
    return {"ok": False, "evidence": "不认的隔离档：%s" % profile}


def verdict() -> dict:
    """隔离是否成立 —— **fail-closed**：证明不了隔离就算没隔离。

    🔴 区分两件事（别把「路存在」念成「这次真隔离了」）：
      · confined_now：**当前启动器**是否真在隔离里跑 —— 现在**否**（宿主 Popen 直接起）；
      · profiles_available / profiles_verified：哪些路**真验过**能跑。
    """
    a = assess()
    s = a["隔离面"]
    avail = []
    if s["docker_daemon"]:
        avail.append("docker")
    if s["wsl"] and s["wsl_distros"]:
        avail.append("wsl")
    if s["low_priv_accounts"]:
        avail.append("low_priv_account")
    seen = {p: verify_profile(p) for p in ("wsl", "docker")}
    verified = [p for p, v in seen.items() if v.get("ok")]
    why = ("当前启动器=宿主 Popen（以「%s」身份），**执行面未隔离**；已验能用的隔离档：%s"
           % (a["执行身份"].get("whoami") or "?", "、".join(verified) or "无"))
    return {"ok": True, "op": "verdict", "confined_now": False,
            "profiles_available": avail, "profiles_verified": verified,
            "verify": seen, "why": why, "执行身份": a["执行身份"], "隔离面": s,
            "enable": [
                "① 起 Docker Desktop（起完 docker version 能通）⇒ profile=docker",
                "② 用 WSL 发行版跑中继 ⇒ profile=wsl（%s）" % (",".join(s["wsl_distros"]) or "无"),
                "③ 给低权账号（%s）配好免交互启动 ⇒ profile=low_priv_account" % (",".join(s["low_priv_accounts"]) or "无"),
            ]}


def grant_state() -> dict:
    """**只查**主人发的 remote_device 票（AI 不发）。"""
    from .. import auth_gate as AG
    try:
        rows = AG._expire_stale(AG._load_grants())
        live = [g for g in rows if g.get("scope") == "remote_device"]
        return {"ok": True, "live": len(live),
                "note": "门在 auth_gate（remote_device）；只能主人在终端发"}
    except Exception as exc:                                       # noqa: BLE001
        return {"ok": False, "error": ("%s: %s" % (type(exc).__name__, exc))[:120]}


def guard_start(*, grant=None, profile: str = "", acknowledge_host_execution: bool = False,
                ttl_s: int = DEFAULT_TTL_S) -> dict:
    """启中继前的**最后一道闸**。不隔离就拒；拒了要说清怎么才能开。"""
    v = verdict()
    g = grant_state()
    if not g.get("live") and not grant:
        return {"ok": False, "reason": "needs_grant", "scope": "remote_device",
                "why": "启远程执行面 = 不可逆的对外接管通道，必须有主人发的 remote_device 票",
                "how_to_grant": "python -m gbt_allinone auth grant --scope remote_device --ttl 600（只能主人发）",
                "隔离": v}
    # 指定了隔离档 ⇒ 必须**真验过**才放行（不是「它在不在」）
    if profile:
        pv = verify_profile(profile)
        if not pv.get("ok"):
            return {"ok": False, "reason": "profile_unverified", "profile": profile,
                    "why": "指定的隔离档没验过：%s" % pv.get("evidence"),
                    "enable": v["enable"], "隔离": v}
        return {"ok": True, "profile": profile, "ttl_s": int(ttl_s), "隔离": v, "票": g,
                "verify": pv, "note": "隔离档已真验：%s" % pv.get("evidence")}
    if not v["confined_now"] and not acknowledge_host_execution:
        return {"ok": False, "reason": "unconfined_refused",
                "why": "**执行面未隔离**：" + v["why"] + " —— 未隔离一律拒启（fail-closed）",
                "what_this_means": "中继若在未隔离下启动，云端模型敲的命令会以"
                                   "「%s」身份在**宿主真机**执行；靶标在沙箱、执行不在，等于没隔离"
                                   % (v["执行身份"].get("whoami") or "当前用户"),
                "enable": v["enable"], "隔离": v}
    return {"ok": True, "profile": "host_acknowledged", "ttl_s": int(ttl_s), "隔离": v, "票": g,
            "note": "⚠️ 主人显式确认「明知未隔离仍启」⇒ 记录在案（本件只记账，不美化）"}


def mark_started(pid: int, profile: str, ttl_s: int = DEFAULT_TTL_S) -> dict:
    STATE.parent.mkdir(parents=True, exist_ok=True)
    rec = {"pid": int(pid), "profile": profile, "started_at": time.time(),
           "deadline": time.time() + int(ttl_s), "ttl_s": int(ttl_s)}
    STATE.write_text(json.dumps(rec, ensure_ascii=False, indent=1), encoding="utf-8")
    return rec


def ttl_state() -> dict:
    """看门狗读数：还剩多久 / 是否已过期。"""
    try:
        rec = json.loads(STATE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {"ok": True, "tracked": False}
    left = int(rec.get("deadline", 0) - time.time())
    return {"ok": True, "tracked": True, "pid": rec.get("pid"), "profile": rec.get("profile"),
            "remaining_s": left, "expired": left <= 0}


def run(op: str = "verdict", **kw) -> dict:
    op = str(op or "verdict").lower()
    if op in ("assess", "status"):
        return assess()
    if op == "verdict":
        return verdict()
    if op == "grant":
        return dict({"op": "grant"}, **grant_state())
    if op == "ttl":
        return dict({"op": "ttl"}, **ttl_state())
    if op == "guard":
        return dict({"op": "guard"}, **guard_start(
            grant=kw.get("grant"), profile=str(kw.get("profile") or ""),
            acknowledge_host_execution=bool(kw.get("acknowledge_host_execution")),
            ttl_s=int(kw.get("ttl_s") or DEFAULT_TTL_S)))
    return {"ok": False, "error": "不认的 op：%s" % op,
            "known": ["assess", "verdict", "grant", "ttl", "guard"]}
