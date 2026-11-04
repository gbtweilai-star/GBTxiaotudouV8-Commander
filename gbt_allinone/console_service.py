"""GBT小土豆V8 · 认知界面服务自启（Python 侧）

主人 2026-11-01 令：「服务重启后要跑 python tools/console-server.py --port 8766，
这个直接做到原生 APP 里面自动执行就好了。」

职责：桌面壳/CLI 启动时确保 127.0.0.1:8766 在跑；幂等；起不来只报原因、不拖垮调用方。
不新增能力位（这是服务自启助手，不是可派发能力）。

开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PORT = int(os.environ.get("GBT_CONSOLE_PORT") or 8766)
STATE = ROOT / "gbt_allinone" / "store" / "console-server.json"
_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)
_DETACHED = getattr(subprocess, "DETACHED_PROCESS", 0)


def _python() -> str:
    embedded = ROOT / "pyembed" / "python.exe"
    return str(embedded) if embedded.is_file() else sys.executable


def _listener_pids(port: int = PORT) -> list:
    """谁在听这个端口（netstat -ano）。用于区分"健康在跑"和"占了端口但不通"。"""
    try:
        r = subprocess.run(["netstat", "-ano", "-p", "tcp"], capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=10,
                           creationflags=_NO_WINDOW)
    except Exception:  # noqa: BLE001
        return []
    pids = []
    for line in (r.stdout or "").splitlines():
        parts = line.split()
        if len(parts) >= 5 and parts[0].upper().startswith("TCP") \
                and parts[1].endswith(":%d" % port) and parts[3].upper() == "LISTENING":
            try:
                pids.append(int(parts[4]))
            except ValueError:
                pass
    return pids


def ping(port: int = PORT, timeout: float = 2.0) -> dict:
    """探一次 /api/ping（轻量，不触发 console 数据构建），顺带取 /api/state 计数（慢也不影响判定）。

    🔴 2026-11-02 实测：原来只探 /api/state，冷缓存建数据 >0.9s ⇒ 健康检查假阴性，
       于是又起了一个进程，Windows 的 SO_REUSEADDR 让它**真的绑上**同一端口 ⇒ 双开。
       双开时订阅者收不到另一个进程的广播。判据要轻、要快。
    """
    base = "http://127.0.0.1:%d" % port
    try:
        with urllib.request.urlopen(base + "/api/ping", timeout=timeout) as r:
            d = json.loads(r.read().decode("utf-8"))
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "reason": str(e)[:120], "port": port}
    out = {"ok": bool(d.get("pong")), "port": port, "pid": d.get("pid")}
    if out["ok"]:
        # 只在 ping 通了才去取 /api/state（冷缓存建数据慢，但不能因此判死）；
        # 取不到就如实留空，不编 caps。
        try:
            with urllib.request.urlopen(base + "/api/state",
                                        timeout=max(timeout, 8.0)) as r:
                s = json.loads(r.read().decode("utf-8"))
            out.update({"caps": s.get("caps"), "skills": s.get("skills")})
        except Exception:  # noqa: BLE001
            pass
    return out


def status(port: int = PORT) -> dict:
    p = ping(port)
    out = {"up": bool(p.get("ok")), "port": port, "python": _python()}
    if p.get("ok"):
        out["caps"] = p.get("caps")
        out["skills"] = p.get("skills")
    try:
        d = json.loads(STATE.read_text(encoding="utf-8"))
        out["last"] = d
    except Exception:  # noqa: BLE001
        out["last"] = None
    return out


def start(port: int = PORT, wait_s: float = 15.0) -> dict:
    """起服务并等端口接管；返回 {ok, already, pid, waited_ms, caps, port, reason?}。"""
    p = ping(port)
    if p.get("ok"):
        # 记下真 pid（/api/ping 会报）；不然再 start 一次就把状态文件里的 pid 抹成 0，stop() 就废了。
        rec = {"pid": int(p.get("pid") or 0), "port": port,
               "note": "already running (not started by this helper)",
               "checked_at": time.strftime("%Y-%m-%dT%H:%M:%S")}
        try:
            STATE.parent.mkdir(parents=True, exist_ok=True)
            STATE.write_text(json.dumps(rec, ensure_ascii=False), encoding="utf-8")
        except Exception:  # noqa: BLE001
            pass
        return {"ok": True, "already": True, "port": port,
                "caps": p.get("caps"), "skills": p.get("skills"), "pid": p.get("pid")}
    stale = _listener_pids(port)
    if stale:
        # 端口有人听、但 /api/ping 不通 ⇒ 僵死/旧版。**不双开**（双开会串广播）。
        return {"ok": False, "already": False, "port": port, "stale_pids": stale,
                "reason": "端口被占用但 /api/ping 不通（僵死或旧进程），不双开",
                "hint": "taskkill /PID <pid> /F 后再 start"}
    cmd = [_python(), "-X", "utf8", str(ROOT / "tools" / "console-server.py"),
           "--port", str(port)]
    flags = _DETACHED | _NO_WINDOW if os.name == "nt" else 0
    try:
        proc = subprocess.Popen(cmd, cwd=str(ROOT), stdout=subprocess.DEVNULL,
                                stderr=subprocess.DEVNULL, creationflags=flags,
                                start_new_session=(os.name != "nt"))
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "port": port, "reason": "起不来：%s" % str(e)[:120]}
    t0 = time.time()
    while time.time() - t0 < wait_s:
        time.sleep(0.5)
        if proc.poll() is not None:
            return {"ok": False, "port": port, "pid": proc.pid,
                    "reason": "进程启动即退出（exit %s），多半是端口被占" % proc.returncode}
        q = ping(port, timeout=1.5)
        if q.get("ok"):
            rec = {"pid": proc.pid, "port": port, "python": _python(),
                   "started_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
                   "waited_ms": int((time.time() - t0) * 1000)}
            try:
                STATE.parent.mkdir(parents=True, exist_ok=True)
                STATE.write_text(json.dumps(rec, ensure_ascii=False), encoding="utf-8")
            except Exception:  # noqa: BLE001
                pass
            return {"ok": True, "already": False, "pid": proc.pid, "port": port,
                    "waited_ms": rec["waited_ms"], "caps": q.get("caps")}
    return {"ok": False, "port": port, "pid": proc.pid,
            "reason": "进程起了但 :%d 一直没接管（端口被占？）" % port}


def _cmdline(pid: int) -> str:
    """取进程命令行（只用于判断"这个 pid 是不是我们的 console-server"）。"""
    if os.name != "nt":
        try:
            return pathlib.Path("/proc/%d/cmdline" % pid).read_text(errors="replace")
        except Exception:  # noqa: BLE001
            return ""
    try:
        r = subprocess.run(
            ["powershell", "-NoProfile", "-Command",
             "(Get-CimInstance Win32_Process -Filter 'ProcessId=%d').CommandLine" % pid],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            timeout=20, creationflags=_NO_WINDOW)
        return (r.stdout or "").strip()
    except Exception:  # noqa: BLE001
        return ""


def _ours(pid: int) -> bool:
    return pid > 0 and "console-server.py" in _cmdline(pid)


def stop() -> dict:
    """停掉我们自己起的那个：状态文件 pid → 该端口监听 pid（都要求命令行是 console-server.py）。

    端口以状态文件为准（支持隔离端口 18766 的测试），不要拿默认 8766 去匹配：
    否则跑隔离端口测试时会把正式端口的生产进程一起杀了。
    """
    try:
        d = json.loads(STATE.read_text(encoding="utf-8"))
        pid = int(d.get("pid") or 0)
        port = int(d.get("port") or PORT)
    except Exception:  # noqa: BLE001
        d, pid, port = {}, 0, PORT
    candidates = []
    if pid > 0:
        candidates.append(pid)
    candidates += [p for p in _listener_pids(port) if p not in candidates]
    hit = [p for p in candidates if _ours(p)]
    if not hit:
        return {"ok": False, "reason": "没找到我们的 console-server 进程（不误杀别的进程）",
                "checked_pids": candidates}
    stopped = []
    for p in hit:
        try:
            if os.name == "nt":
                subprocess.run(["taskkill", "/PID", str(p), "/F"], capture_output=True,
                               timeout=30, creationflags=_NO_WINDOW)
            else:
                os.kill(p, 15)
            stopped.append(p)
        except Exception as e:  # noqa: BLE001
            return {"ok": False, "stopped": stopped, "reason": str(e)[:120]}
    try:
        STATE.unlink()
    except Exception:  # noqa: BLE001
        pass
    return {"ok": True, "stopped": stopped}


def ensure_server(port: int = PORT) -> dict:
    """桌面壳入口统一调这个：能起就起，起不来只报原因。"""
    out = start(port)
    if not out.get("ok"):
        print("[console] 认知界面服务未就绪（不牵连启动）：%s" % out.get("reason"))
    elif out.get("already"):
        print("[console] 认知界面服务已在跑：http://127.0.0.1:%d/console/index.html" % port)
    else:
        print("[console] 认知界面服务已自启：http://127.0.0.1:%d/console/index.html（等了 %d ms）"
              % (port, out.get("waited_ms", 0)))
    return out


if __name__ == "__main__":
    import sys as _sys
    cmd = _sys.argv[1] if len(_sys.argv) > 1 else "ensure"
    if cmd == "status":
        print(json.dumps(status(), ensure_ascii=False, indent=2))
    elif cmd == "stop":
        print(json.dumps(stop(), ensure_ascii=False))
    elif cmd == "start":
        print(json.dumps(start(), ensure_ascii=False))
    else:
        print(json.dumps(ensure_server(), ensure_ascii=False))
