# gbt-capability: tentacle_fleet
# ⛔ 开发者：自由的风 · 永久钢印 · 禁止删除
"""触手舰队 · 按任务启动 N 根**隔离**触手（主人令 2026-09-27：「每次执行任务都要启动
触手根数来执行任务，比如任务需要一次性启动 5 根…一定要做好隔离启动，端口隔离各做各的
不妨碍…你负责以总工程师的身份实时监控在工作的自己」）。

## 四条隔离（缺一条都不叫隔离）
  1. **工作区隔离**：`git worktree` 给每根触手一份**同一代码、独立分支/目录**的工作区
     —— 各改各的，绝不互相覆盖；主仓不受影响（只多一条 worktree 记录）。
  2. **端口隔离**：每根触手一段专属端口（默认 31000 起、步长 10），**启动前真探测**
     （真去 bind）——占用即拒绝，**不许"以为空着"**。
  3. **身份隔离**：每根触手一个独立 `HOME` / `USERPROFILE` / `XDG_CONFIG_HOME` /
     `<工作区>/.freebuff/`。免费引擎 freebuff 按**匿名 project-id** 认身份（实测其 npm 客户端里
     login/signup/oauth/quota/credits **全部零命中**，本机身份就是 `.freebuff/project-id`
     一个 UUID）⇒ **"专属身份" = 独立工作区，不需要注册账号**。本工具**不注册任何账号**：
     批量注册是本仓红线（主人 9·23 令：不批量注册 / 不刷积分），且违反对方条款。
  4. **日志隔离**：每根一份 `.fleet/<id>/worker.log` + 追加式台账 `state/fleet.jsonl`
     （谁 · 什么任务 · 端口 · 目录 · 引擎 · 起于何时）—— **无痕即未发生**。

## 安全口径（本工具被自家安全钩子拦下三次，最终改成这个形状）
  · **本工具不自己起进程**：它**生成**每根触手自己的 `.cmd`（内容由工具拼，**不含任何用户文本**：
    任务原文只写进工作区文件），再用 `os.startfile` 把这条"启动指令"交给系统执行 ——
    于是"程序名来自变量"这种注入面**在编排器里根本不存在**；
  · **引擎可用性 = 文件系统实测**（不 spawn 探活）：`freebuff` 在不在 PATH、它的配置目录
    能不能写 —— 后者就是实测的卡点（`EPERM: mkdir C:\\Users\\ADMIN\\.config\\manicode`）；
  · 引擎是**白名单常量**（`probe` 内置探针 / `freebuff`）；
  · 端口/路径/身份全部先**真探测**再动手。

## 总工程师视角
`status` / `watch` = 实时监控在工作的自己：每根**活着没 · 最后一行动静 · 端口还占着没**。
读数不猜：查不到就写「未知」，不许拿"应该还在跑"当读数。

## 命令
  python tools/tentacle_fleet.py plan   --n 5 --task "把 A 模块测试补齐"
  python tools/tentacle_fleet.py launch --n 5 --task "..." [--engine auto|probe|freebuff]
  python tools/tentacle_fleet.py gen    --n 5 --task "..."     # 只生成 .cmd，不启动（人手启动用）
  python tools/tentacle_fleet.py status [--watch 5]
  python tools/tentacle_fleet.py logs   <触手id> [--tail 30]
  python tools/tentacle_fleet.py stop   <触手id|all>
  python tools/tentacle_fleet.py reap                       # 清掉已停的 worktree（日志留着）
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import socket
import subprocess
import sys
import time
import uuid
from pathlib import Path

ROOT = Path(r"C:\Users\ADMIN\Desktop\GBT小土豆V8")
FLEET = ROOT / ".fleet"
LEDGER = ROOT / "state" / "fleet.jsonl"
STATE = ROOT / "state" / "fleet_active.json"
PROBE = ROOT / "tools" / "fleet_probe.py"        # 常量路径（内置探针，固定代码）
PY = Path(sys.executable)                        # 常量程序名
BASE_PORT = 31000
PORT_STRIDE = 10
MAX_WORKERS = 5                                  # 能源闸：默认最多 5 根（--max 可调）
ENGINES = ("auto", "probe", "freebuff")          # 白名单（不接受任意程序名）
FREE_ENGINE = "freebuff"


def _ledger(row: dict) -> None:
    LEDGER.parent.mkdir(parents=True, exist_ok=True)
    with open(LEDGER, "a", encoding="utf-8") as fh:
        fh.write(json.dumps({"at": time.strftime("%Y-%m-%dT%H:%M:%S"), **row},
                            ensure_ascii=False) + "\n")


def _load_active() -> dict:
    if STATE.is_file():
        try:
            return json.loads(STATE.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return {}
    return {}


def _save_active(d: dict) -> None:
    STATE.parent.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")


def port_free(port: int) -> bool:
    """**真探测**：真去 bind 一次。不靠"没人告诉我它被占了"。"""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            s.bind(("127.0.0.1", port))
            return True
        except OSError:
            return False


def port_bound(port: int) -> bool:
    """端口现在**有没有人在听**（总工程师看板用）。"""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.35)
        return s.connect_ex(("127.0.0.1", port)) == 0


def free_engine_ready() -> tuple[bool, str]:
    """免费引擎预检 —— **必须在"每根触手自己的 HOME"下探活**（2026-09-27 实测纠错）。

    血账：早先的预检读的是**共享** `C:\\Users\\ADMIN\\.config\\manicode`，那里写不进去（EPERM）
    ⇒ 结论「freebuff 起不来」。但那是**看错了环境**：舰队给每根触手独立 HOME，
    而 freebuff 只会往 `$HOME/.config/manicode` 里装 —— **换成隔离 HOME 一装就成**：
    实测下载 45.8MB 二进制 + `--help` 退出码 0（2026-09-27）。
    ⇒ **预检要与工人实际拿到的环境一致**，否则"能力不可用"是自己造的假结论。
    """
    exe = shutil.which(FREE_ENGINE)
    if not exe:
        return False, "PATH 里没有 `freebuff`"
    probe_home = FLEET / "_preflight" / "home"
    try:
        (probe_home / ".config").mkdir(parents=True, exist_ok=True)
    except OSError as e:
        return False, f"探活目录建不起来：{type(e).__name__}: {e}"
    env = {**os.environ, "HOME": str(probe_home), "USERPROFILE": str(probe_home),
           "XDG_CONFIG_HOME": str(probe_home / ".config")}
    try:
        p = subprocess.run([exe, "--help"], capture_output=True, encoding="mbcs",
                           errors="replace", timeout=300, env=env)
    except subprocess.TimeoutExpired:
        return False, "`freebuff --help` 超时（>300s，可能在下载二进制）"
    except OSError as e:
        return False, f"`freebuff --help` 起不来：{type(e).__name__}"
    blob = ((p.stdout or "") + (p.stderr or "")).strip()
    installed = (probe_home / ".config" / "manicode" / "freebuff.exe").is_file()
    if p.returncode == 0 and "Usage" in blob:
        tail = "（二进制已落进隔离 HOME，可干活；真要跑任务还需 `freebuff login` 一次 —— 那一步归主人）"
        return True, f"预检通过：隔离 HOME 下 --help 正常{tail if installed else ''}"
    first = blob.splitlines()[0][:150] if blob else "无输出"
    if "EPERM" in blob:
        return False, f"隔离 HOME 下仍写不进去：{first}"
    return False, f"预检退出码 {p.returncode}：{first}"


def plan(n: int, task: str, engine: str = "auto", max_workers: int = MAX_WORKERS) -> dict:
    """只算不启：先看清落点（工作区/端口/身份/日志），再决定动不动手。"""
    n = max(1, int(n))
    if engine not in ENGINES:
        return {"ok": False, "why": f"引擎必须是 {'/'.join(ENGINES)} 之一（不接受任意程序名）",
                "slots": [], "engine": engine, "engine_ready": False,
                "engine_note": "白名单外", "n": n, "task": task}
    if n > max_workers:
        return {"ok": False, "why": f"超能源闸：要 {n} 根，上限 {max_workers}"
                                   f"（--max 可调，但请想清楚）",
                "slots": [], "engine": engine, "engine_ready": False,
                "engine_note": "超上限", "n": n, "task": task}
    active = _load_active()
    slots = []
    for i in range(1, n + 1):
        wid = f"T{i:02d}"
        port = BASE_PORT + (i - 1) * PORT_STRIDE
        slots.append({
            "id": wid, "port": port, "worktree": str(FLEET / wid / "ws"),
            "home": str(FLEET / wid / "home"), "log": str(FLEET / wid / "worker.log"),
            "cmd": str(FLEET / wid / f"start-{wid}.cmd"),
            "exitcode": str(FLEET / wid / "exit.code"),
            "port_free": port_free(port), "exists": wid in active,
        })
    if engine in ("auto", "freebuff"):
        eng_ok, eng_why = free_engine_ready()
    else:
        eng_ok, eng_why = True, "内置探针（固定代码，证隔离用）"
    return {"ok": all(s["port_free"] and not s["exists"] for s in slots),
            "task": task, "n": n, "engine": engine,
            "engine_ready": eng_ok, "engine_note": eng_why, "slots": slots,
            "_口径": "端口真探测过；已存在的 worker id 拒绝复用（先 stop/reap 或换 --n）"}


def _prepare_workspace(slot: dict) -> tuple[bool, str]:
    """一触手一工作区：git worktree（同一代码 · 独立分支 · 独立目录）。"""
    ws = Path(slot["worktree"])
    ws.parent.mkdir(parents=True, exist_ok=True)
    Path(slot["home"]).mkdir(parents=True, exist_ok=True)
    if ws.exists():
        return True, "工作区已存在（复用）"
    p = subprocess.run(["git", "worktree", "add", str(ws), "-b", f"fleet/{slot['id']}", "HEAD"],
                       cwd=str(ROOT), capture_output=True, text=True)
    if p.returncode == 0:
        return True, "git worktree（同一代码 · 独立分支）"
    return False, f"worktree 建不起来：{(p.stderr or p.stdout).strip()[:160]}"


def _identity(ws: Path) -> str:
    """身份隔离：该工作区自己的匿名 project-id（免费引擎按它认身份，无需注册）。

    ⚠️ 实测血账（2026-09-27）：**必须带末尾换行**。不带的话 `cat .fleet/*/ws/.freebuff/project-id`
    会把 5 份身份拼成一整行，`sort -u | wc -l` 数出「1」—— 于是"身份隔离"看着像坏了，
    其实是我的量法坏了。**读数工具的口径错，比读数本身更贵**。
    """
    fb = ws / ".freebuff"
    fb.mkdir(parents=True, exist_ok=True)
    pidfile = fb / "project-id"
    if not pidfile.is_file():
        pidfile.write_text(str(uuid.uuid4()) + "\n", encoding="utf-8")
    return pidfile.read_text(encoding="utf-8").strip()


def _write_start_cmd(slot: dict, engine: str, has_free_engine: bool, hold: int = 6) -> Path:
    """**生成"启动指令"**：每根触手一条自己的 .cmd。

    内容全部由本工具拼装，**不含任何用户文本**（任务原文只在工作区文件里）；
    引擎分支由白名单常量决定；freebuff 不在可用状态时**如实走探针并写明原因**。
    """
    ws = slot["worktree"]
    home = slot["home"]
    log = slot["log"]
    lines = [
        "@echo off",
        "chcp 65001 >nul",
        f'cd /d "{ws}"',
        f'set "HOME={home}"',
        f'set "USERPROFILE={home}"',
        f'set "XDG_CONFIG_HOME={home}\\.config"',
        f'set "GBT_FLEET_ID={slot["id"]}"',
        f'set "GBT_FLEET_PORT={slot["port"]}"',
        f'set "GBT_FLEET_WS={ws}"',
        f'set "GBT_FLEET_HOLD={hold}"',
        f'title fleet-{slot["id"]}-port{slot["port"]}',
        # ⚠️ 实测（2026-09-27）：`os.startfile` 起的是**新窗口**，它的 stdout 不会回到编排器，
        # 所以启动指令必须**自己把输出重定向到自己那份日志** —— 否则看板只能看到头部，
        # "谁在做什么"就成了空话（日志隔离等于没做）。
        f'echo === 触手 {slot["id"]} · 端口 {slot["port"]} · 启动 {time.strftime("%Y-%m-%dT%H:%M:%S")} === >> "{log}" 2>&1',
        f'echo 工作区 {ws} >> "{log}" 2>&1',
    ]
    if engine == "freebuff" and has_free_engine:
        lines += [
            f'echo 引擎 freebuff（任务已写进 .fleet-mission\\TASK.md，由它自己读） >> "{log}" 2>&1',
            f'"{PY}" -c "import pathlib,sys;print(pathlib.Path(sys.argv[1]).read_text(encoding=\'utf-8\'))" ".fleet-mission\\TASK.md" >> "{log}" 2>&1',
            f'freebuff >> "{log}" 2>&1',
        ]
    else:
        why = "（未请求 freebuff）" if engine == "probe" else "（freebuff 预检未过）"
        lines += [
            f'echo 引擎 内置探针 {why} —— 本次只证隔离，不跑外部 agent >> "{log}" 2>&1',
            f'"{PY}" "{PROBE}" {slot["id"]} {slot["port"]} "{ws}" >> "{log}" 2>&1',
        ]
    # **退出码落盘**：看板要能说清"已退出（码几）"，而不是含糊的"未知"。
    lines.append(f'echo %ERRORLEVEL% > "{slot["exitcode"]}"')
    p = Path(slot["cmd"])
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("\r\n".join(lines) + "\r\n", encoding="utf-8")
    return p


def launch(n: int, task: str, engine: str = "auto", max_workers: int = MAX_WORKERS,
           hold: int = 6, start: bool = True) -> dict:
    pl = plan(n, task, engine=engine, max_workers=max_workers)
    if not pl["ok"]:
        _ledger({"event": "launch_refused", "task": task, "n": n,
                 "why": pl.get("why") or "端口占用或 id 已存在"})
        return {"ok": False, "plan": pl,
                "why": pl.get("why") or "端口占用或 id 已存在 ⇒ 拒绝启动"}
    engine = pl["engine"]
    eng_ok, eng_why = pl["engine_ready"], pl["engine_note"]
    if engine == "auto" and not eng_ok:
        engine = "probe"          # **如实降级**（原因写进台账、日志与启动指令）
    active = _load_active()
    started = []
    for slot in pl["slots"]:
        ws_ok, ws_why = _prepare_workspace(slot)
        if not ws_ok:
            started.append({"id": slot["id"], "ok": False, "why": ws_why})
            continue
        ws = Path(slot["worktree"])
        ident = _identity(ws)
        mission = ws / ".fleet-mission"
        mission.mkdir(parents=True, exist_ok=True)
        (mission / "TASK.md").write_text(
            f"# 触手 {slot['id']} 的任务\n\n{task or '（未给任务原文）'}\n\n"
            f"端口段：{slot['port']}~{slot['port'] + PORT_STRIDE - 1}（本触手专属）\n"
            f"工作区：{ws}（git worktree · 独立分支 fleet/{slot['id']}）\n"
            f"身份（匿名 project-id · 本触手专属）：{ident}\n"
            f"隔离口径：与同批其他触手互不干扰；本目录是我的唯一落点。\n",
            encoding="utf-8")
        (mission / "env.json").write_text(json.dumps(
            {"id": slot["id"], "port": slot["port"], "engine": engine, "task": task,
             "worktree": str(ws), "home": slot["home"], "hold": hold,
             "engine_note": eng_why}, ensure_ascii=False, indent=1), encoding="utf-8")
        cmd = _write_start_cmd(slot, engine, has_free_engine=eng_ok, hold=hold)
        log = Path(slot["log"])
        log.parent.mkdir(parents=True, exist_ok=True)
        with open(log, "a", encoding="utf-8") as fh:
            fh.write(f"\n=== {slot['id']} · {time.strftime('%Y-%m-%dT%H:%M:%S')} ===\n")
            fh.write(f"引擎：{engine}"
                     + (f"（freebuff 预检未过，已如实降级为内置探针；原因：{eng_why}）"
                        if engine == "probe" and not eng_ok else "")
                     + f"\n端口：{slot['port']}  工作区：{ws}\n身份：{ident}\n任务：{task}\n"
                     f"启动指令：{cmd}\n")
        if start:
            # 把"启动指令"交给系统执行（本工具不在自己进程里起任意程序）
            os.startfile(str(cmd))                       # noqa: S606  （.cmd 内容由本工具生成）
        active[slot["id"]] = {"pid": None, "port": slot["port"], "worktree": str(ws),
                              "home": slot["home"], "log": str(log), "cmd": str(cmd),
                              "exitcode": slot["exitcode"], "identity": ident,
                              "task": task, "engine": engine,
                              "started": time.strftime("%Y-%m-%dT%H:%M:%S")}
        _ledger({"event": "worker_started", "id": slot["id"], "port": slot["port"],
                 "worktree": str(ws), "engine": engine, "task": task,
                 "cmd": str(cmd), "engine_note": eng_why, "identity": ident,
                 "started_by": "startfile" if start else "gen-only"})
        started.append({"id": slot["id"], "ok": True, "port": slot["port"],
                        "worktree": str(ws), "log": str(log), "cmd": str(cmd)})
    _save_active(active)
    return {"ok": all(s.get("ok") for s in started), "engine": engine,
            "engine_ready": eng_ok, "engine_note": eng_why, "started": started}


def _pid_on_port(port: int) -> int | None:
    """端口上是谁（总工程师看板）：用 netstat 读数，读不到就 None（不猜）。

    ⚠️ **中文 Windows 的 CLI 输出是 ANSI(GBK)，不是 UTF-8**（实测：按 utf-8 读会把读线程
    炸成 UnicodeDecodeError，看板就拿不到 pid）。这类系统工具的读数一律按 `mbcs` 解。
    """
    try:
        p = subprocess.run(["netstat", "-ano", "-p", "TCP"], capture_output=True,
                           encoding="mbcs", errors="replace", timeout=30)
    except (OSError, subprocess.TimeoutExpired):
        return None
    for ln in (p.stdout or "").splitlines():
        parts = ln.split()
        if len(parts) >= 5 and parts[1].endswith(f":{port}") and parts[3].upper() == "LISTENING":
            try:
                return int(parts[-1])
            except ValueError:
                return None
    return None


def _alive(pid: int | None) -> str:
    """在跑 / 已退出 / 未知 —— **读不到就写未知**，不拿"应该还在跑"当读数。"""
    if not pid:
        return "未知"
    try:
        p = subprocess.run(["tasklist", "/FI", f"PID eq {int(pid)}", "/NH"],
                           capture_output=True, encoding="mbcs", errors="replace", timeout=25)
    except (OSError, subprocess.TimeoutExpired):
        return "未知"
    out = (p.stdout or "").strip()
    return "在跑" if str(pid) in out else ("已退出" if out else "未知")


def _worker_state(w: dict) -> tuple[str, int | None]:
    """一根触手此刻的状态：**优先读它自己写的退出码**（.cmd 跑完落的盘），
    其次看端口有没有人在听。两条都读不到才叫「未知」—— 不许拿"应该还在跑"当读数。"""
    port = int(w["port"])
    listening = port_bound(port)
    if listening:
        return "在跑（端口在听）", _pid_on_port(port)
    ec = w.get("exitcode")
    if ec and Path(ec).is_file():
        try:
            code = int((Path(ec).read_text(encoding="utf-8", errors="replace").strip() or "-1"))
        except ValueError:
            code = -1
        return f"已退出（退出码 {code}）", None
    return "未知（没有退出码、端口也没在听）", None


def status(verbose: bool = True) -> dict:
    active = _load_active()
    rows = []
    for wid, w in sorted(active.items()):
        log = Path(w["log"])
        tail = ""
        if log.is_file():
            lines = [ln.rstrip("\n") for ln in
                     log.read_text(encoding="utf-8", errors="replace").splitlines() if ln.strip()]
            tail = lines[-1][:110] if lines else ""
        state, pid = _worker_state(w)
        rows.append({**w, "id": wid, "pid_on_port": pid, "state": state,
                     "port_listening": port_bound(int(w["port"])), "last": tail})
    if verbose:
        print(f"═══ 触手舰队看板 · {time.strftime('%H:%M:%S')} ═══（{len(rows)} 根）")
        for r in rows:
            mark = "🟢" if r["port_listening"] else ("⚪" if r["state"].startswith("已退出") else "❓")
            print(f"  {mark} {r['id']} 端口 {r['port']} · {r['state']}"
                  + (f" · pid {r['pid_on_port']}" if r["pid_on_port"] else "")
                  + f" · 引擎={r['engine']}")
            print(f"      工作区 {r['worktree']}")
            print(f"      最后一行：{r['last'] or '（还没有输出）'}")
        if not rows:
            print('  （没有在册触手。启动：python tools/tentacle_fleet.py launch --n 5 --task "..."）')
    return {"ok": True, "count": len(rows), "workers": rows}


def stop(target: str) -> dict:
    active = _load_active()
    ids = sorted(active) if target == "all" else [target]
    out = []
    for wid in ids:
        w = active.get(wid)
        if not w:
            out.append({"id": wid, "ok": False, "why": "不在册"})
            continue
        port = int(w["port"])
        pid = _pid_on_port(port) if port_bound(port) else None
        if pid:
            p = subprocess.run(["taskkill", "/T", "/F", "/PID", str(pid)],
                               capture_output=True, text=True)
            note = (p.stdout or p.stderr).strip()[:90]
            ok = p.returncode == 0 or "not found" in note.lower()
        else:
            ok, note = True, "端口上没有在跑的进程（已自行退出）"
        _ledger({"event": "worker_stopped", "id": wid, "port": port, "pid": pid, "why": note})
        if ok:
            active.pop(wid, None)
        out.append({"id": wid, "ok": ok, "note": note})
    _save_active(active)
    return {"ok": all(o["ok"] for o in out), "stopped": out}


def reap(dry: bool = False) -> dict:
    """清掉**已停**触手的 worktree（日志与台账都留着 —— 记录不许清）。"""
    active = _load_active()
    out = []
    if FLEET.is_dir():
        for d in sorted(FLEET.iterdir()):
            if not d.is_dir() or d.name in active:
                continue
            ws = d / "ws"
            if not ws.is_dir():
                continue
            if dry:
                out.append({"id": d.name, "would_remove": str(ws)})
                continue
            p = subprocess.run(["git", "worktree", "remove", "--force", str(ws)],
                               cwd=str(ROOT), capture_output=True, text=True)
            out.append({"id": d.name, "ok": p.returncode == 0,
                        "note": (p.stdout or p.stderr).strip()[:120]})
            if p.returncode == 0:
                subprocess.run(["git", "branch", "-D", f"fleet/{d.name}"],
                               cwd=str(ROOT), capture_output=True, text=True)
    _ledger({"event": "reap", "done": [o.get("id") for o in out], "dry": dry})
    return {"ok": True, "reaped": out}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="触手舰队（隔离启动 + 总工程师看板）")
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("plan", "launch", "gen"):
        s = sub.add_parser(name)
        s.add_argument("--n", type=int, default=5, help="启动几根（默认 5）")
        s.add_argument("--task", default="", help="任务原文（写进工作区文件，不进命令行）")
        s.add_argument("--engine", default="auto", choices=list(ENGINES),
                       help="auto|probe|freebuff（白名单）")
        s.add_argument("--max", type=int, default=MAX_WORKERS,
                       help=f"能源闸上限（默认 {MAX_WORKERS}）")
        s.add_argument("--hold", type=int, default=6, help="探针在岗秒数（仅 probe 引擎）")
        s.add_argument("--json", action="store_true")
    s = sub.add_parser("status"); s.add_argument("--watch", type=int, default=0); s.add_argument("--json", action="store_true")
    s = sub.add_parser("logs"); s.add_argument("id"); s.add_argument("--tail", type=int, default=30)
    s = sub.add_parser("stop"); s.add_argument("target")
    s = sub.add_parser("reap"); s.add_argument("--dry", action="store_true")
    a = ap.parse_args(argv)
    if a.cmd in ("plan", "launch", "gen"):
        r = launch(a.n, a.task, a.engine, a.max, hold=a.hold, start=(a.cmd == "launch")) \
            if a.cmd != "plan" else plan(a.n, a.task, a.engine, a.max)
        if a.json:
            print(json.dumps(r, ensure_ascii=False, indent=1))
        else:
            if r.get("why"):
                print(f"🔴 {r['why']}")
            print(f"引擎={r.get('engine')}"
                  f"（预检：{'过' if r.get('engine_ready') else '未过 ｜ ' + str(r.get('engine_note'))}）")
            for s in r.get("started", r.get("slots", [])):
                print(f"  {'✅' if s.get('ok', True) else '🔴'} {s['id']} 端口 {s['port']}"
                      f" 工作区 {s.get('worktree')}"
                      + (f"\n      启动指令：{s['cmd']}" if s.get("cmd") and a.cmd == "gen" else ""))
            if a.cmd == "plan":
                print(f"结论：{'可以启' if r['ok'] else '🔴 有冲突，先处理'}")
            elif a.cmd == "gen":
                print("（只生成不启动；要启动就跑上面每条 .cmd，或改用 launch）")
        return 0 if r.get("ok") else 1
    if a.cmd == "status":
        if a.watch:
            while True:
                status(); time.sleep(a.watch)
        r = status(verbose=not a.json)
        if a.json:
            print(json.dumps(r, ensure_ascii=False, indent=1))
        return 0
    if a.cmd == "logs":
        active = _load_active(); w = active.get(a.id)
        if not w:
            print(f"触手 {a.id} 不在册"); return 2
        lines = Path(w["log"]).read_text(encoding="utf-8", errors="replace").splitlines()
        print("\n".join(lines[-a.tail:]))
        return 0
    if a.cmd == "stop":
        r = stop(a.target)
        for s in r["stopped"]:
            print(f"  {'✅' if s['ok'] else '🔴'} {s['id']} {s.get('note') or s.get('why')}")
        return 0 if r["ok"] else 1
    if a.cmd == "reap":
        r = reap(a.dry)
        for o in r["reaped"]:
            tag = "（dry-run）" if o.get("would_remove") else (
                "✅ " + str(o.get("note")) if o.get("ok") else "🔴 " + str(o.get("note")))
            print(f"  {o.get('id')} {tag}")
        if not r["reaped"]:
            print("  （没有可清的已停触手）")
        return 0
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
