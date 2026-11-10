"""RtServo 客户端：连常驻伺服，提供 move/click/find/track。

完整性说明（2026-11-07 实测）：
  pyembed python = Low(0x1000)  -> SetCursorPos 被拒绝
  powershell.exe  = Medium(0x2000) -> 正常
  由 Medium 进程拉起的子进程仍是 Low（继承受限令牌）
  所以输入必须有 Medium 进程内经 DLL 直接调用，这条链路就是 daemon。
"""
import json
import os
import socket
import subprocess
import time

ROOT = os.path.dirname(os.path.abspath(__file__))
PS1 = os.path.join(ROOT, "rtservo-daemon.ps1")
CMD = os.path.join(ROOT, "start-servo.cmd")
DLL = os.path.join(ROOT, "Servo.dll")
LOG = os.path.join(ROOT, "daemon.log")
PORT = 7791


class ServoError(RuntimeError):
    pass


class Servo:
    def __init__(self, port=PORT, autostart=True):
        self.port = port
        self._sock = None
        self._f = None
        if autostart and not self.alive():
            self.start()

    # ---------- lifecycle ----------
    def alive(self, timeout=2.0):
        try:
            with socket.create_connection(("127.0.0.1", self.port), timeout=timeout) as s:
                f = s.makefile("rw", encoding="utf-8", newline="\n")
                f.write("PING\n")
                f.flush()
                line = f.readline()
                return bool(line.strip())
        except Exception:
            return False

    def start(self, wait_s=25.0):
        if self.alive():
            return True
        subprocess.Popen(["cmd.exe", "/c", CMD],
                         creationflags=0x08000000,
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        deadline = time.time() + wait_s
        while time.time() < deadline:
            if self.alive(1.5):
                return True
            time.sleep(0.4)
        raise ServoError("伺服没起来 —— 看 " + LOG + "（很可能被 Low 完整性拉起）")

    def close(self):
        for obj in (self._f, self._sock):
            try:
                if obj:
                    obj.close()
            except Exception:
                pass
        self._f = self._sock = None

    # ---------- transport ----------
    def _conn(self):
        if self._sock is None:
            self._sock = socket.create_connection(("127.0.0.1", self.port), timeout=30)
            self._f = self._sock.makefile("rw", encoding="utf-8", newline="\n")
        return self._f

    def cmd(self, line, timeout=60):
        try:
            f = self._conn()
            self._sock.settimeout(timeout)
            f.write(line + "\n")
            f.flush()
            raw = f.readline()
        except Exception:
            self.close()
            raise
        if not raw:
            self.close()
            raise ServoError("伺服断开")
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            raise ServoError("坏响应: " + raw[:200])

    # ---------- ops ----------
    def ping(self):
        return self.cmd("PING")

    def move(self, x, y):
        return self.cmd("MOVE %d %d" % (int(x), int(y)))

    def click(self, x, y):
        return self.cmd("CLICK %d %d" % (int(x), int(y)))

    def rect(self, pid):
        return self.cmd("RECT %d" % int(pid))

    def find(self, r, g, b, tol=40, step=3, pid=0):
        return self.cmd("FIND %d %d %d %d %d %d" % (r, g, b, tol, step, int(pid)))

    def track(self, r, g, b, seconds=6.0, gain=1.2, dead=20, tol=40, step=2, pid=0):
        return self.cmd("TRACK %d %d %d %d %d %.2f %.2f %d %d"
                        % (r, g, b, tol, step, seconds, gain, dead, int(pid)),
                        timeout=seconds + 30)

    def track2(self, r, g, b, seconds=6.0, gain=1.2, dead=20, tol=40, step=2, pid=0):
        return self.cmd("TRACK2 %d %d %d %d %d %.2f %.2f %d %d"
                        % (r, g, b, tol, step, seconds, gain, dead, int(pid)),
                        timeout=seconds + 30)

    def tpl_track(self, seconds=6.0, min_score=0.80, dead=20, pid=0):
        return self.cmd("TPTRACK %.2f %.2f %d %d"
                        % (seconds, min_score, dead, int(pid)),
                        timeout=seconds + 30)

    def tpl_find(self, min_score=0.80, pid=0):
        return self.cmd("TPFIND %.2f %d %d" % (min_score, dead, int(pid)))

    def tpl_load(self, path):
        return self.cmd("TPLOAD " + path)

    def drag(self, x1, y1, x2, y2, steps=18, hold_ms=80):
        return self.cmd("DRAG %d %d %d %d %d %d"
                        % (int(x1), int(y1), int(x2), int(y2), int(steps), int(hold_ms)))

    def key(self, combo):
        return self.cmd("KEY " + combo)


if __name__ == "__main__":
    s = Servo()
    print("alive:", s.alive())
    print("ping:", json.dumps(s.ping(), ensure_ascii=False))
    s.close()
