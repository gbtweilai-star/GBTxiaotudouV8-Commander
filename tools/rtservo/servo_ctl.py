"""Add servo self-restart + client library for RtServo (Medium-integrity daemon)."""
import json
import os
import socket
import subprocess
import sys
import time

ROOT = r"C:\Users\Lenovo E14 Gen 5\Desktop\GBT小土豆V8\tools\rtservo"
PS1 = os.path.join(ROOT, "rtservo-daemon.ps1")
LOG = os.path.join(ROOT, "daemon.log")
PIDFILE = os.path.join(ROOT, "daemon.pid")
PORT = 7791


def alive():
    try:
        with socket.create_connection(("127.0.0.1", PORT), timeout=2) as s:
            f = s.makefile("rw", encoding="utf-8", newline="\n")
            f.write("PING\n")
            f.flush()
            return bool(f.readline().strip())
    except Exception:
        return False


def start():
    if alive():
        return {"ok": True, "already": True}
    psi = (
        'Start-Process powershell.exe -ArgumentList @('
        f"'-NoProfile','-NonInteractive','-ExecutionPolicy','Bypass','-File','{PS1}','-Port','{PORT}'"
        ") -WindowStyle Hidden"
    )
    r = subprocess.run(["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", psi],
                       capture_output=True, text=True, timeout=30)
    for _ in range(30):
        time.sleep(0.5)
        if alive():
            return {"ok": True, "started": True, "stderr": (r.stderr or "")[:200]}
    return {"ok": False, "error": "daemon did not come up", "stderr": (r.stderr or "")[:400]}


if __name__ == "__main__":
    print(json.dumps(start(), ensure_ascii=False))
