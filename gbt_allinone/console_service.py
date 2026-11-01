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


def ping(port: int = PORT, timeout: float = 0.9) -> dict:
    """探一次 /api/state。"""
    try:
        with urllib.request.urlopen("http://127.0.0.1:%d/api/state" % port,
                                    timeout=timeout) as r:
            d = json.loads(r.read().decode("utf-8"))
        return {"ok": True, "caps": d.get("caps"), "skills": d.get("skills"), "port": port}
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "reason": str(e)[:120], "port": port}


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
        rec = {"pid": 0, "port": port, "note": "already running (not started by this helper)",
               "checked_at": time.strftime("%Y-%m-%dT%H:%M:%S")}
        try:
            STATE.parent.mkdir(parents=True, exist_ok=True)
            STATE.write_text(json.dumps(rec, ensure_ascii=False), encoding="utf-8")
        except Exception:  # noqa: BLE001
            pass
        return {"ok": True, "already": True, "port": port,
                "caps": p.get("caps"), "skills": p.get("skills")}
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
        q = ping(port, timeout=0.7)
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


def stop() -> dict:
    """按状态文件里的 pid 停掉（只停我们自己起的那个）。"""
    try:
        d = json.loads(STATE.read_text(encoding="utf-8"))
        pid = int(d.get("pid") or 0)
    except Exception:  # noqa: BLE001
        return {"ok": False, "reason": "没有状态文件（不是本助手起的）"}
    if pid <= 0:
        return {"ok": False, "reason": "状态文件里没有 pid"}
    try:
        if os.name == "nt":
            subprocess.run(["taskkill", "/PID", str(pid), "/F"], capture_output=True,
                           timeout=30, creationflags=_NO_WINDOW)
        else:
            os.kill(pid, 15)
        return {"ok": True, "stopped": pid}
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "reason": str(e)[:120]}


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
