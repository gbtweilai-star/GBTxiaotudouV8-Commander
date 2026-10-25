#!/usr/bin/env python3
"""端口/服务探针 —— 只用 TCP socket，不依赖 curl。

为什么不用 curl：
  iSH 上 curl 对 node 起的服务会秒回 000（connection refused），
  而同一个端口用 python socket 连是通的、HTTP 也回 200。
  实测 :3001 就是这样被误判成"停了"。所以探活一律走 socket。

用法：
  python3 tools/svcprobe.py tcp  <port>...          每个端口一行：up / down
  python3 tools/svcprobe.py http <port> <path>...   打 HTTP GET，打印状态码
  python3 tools/svcprobe.py wait <port> <seconds>   轮询等到通为止，通=0 超时=1
"""
import socket
import sys
import time


def tcp_up(port: int, timeout: float = 2.0) -> bool:
    s = socket.socket()
    s.settimeout(timeout)
    try:
        s.connect(("127.0.0.1", port))
        return True
    except OSError:
        return False
    finally:
        s.close()


def http_get(port: int, path: str = "/", timeout: float = 8.0, auth: str | None = None):
    """返回 (状态码, 正文前 400 字节)。连不上返回 (None, 原因)。"""
    s = socket.socket()
    s.settimeout(timeout)
    try:
        s.connect(("127.0.0.1", port))
        req = "GET %s HTTP/1.0\r\nHost: 127.0.0.1\r\n" % path
        if auth:
            req += "Authorization: Bearer %s\r\n" % auth
        req += "Connection: close\r\n\r\n"
        s.sendall(req.encode())
        buf = b""
        while len(buf) < 8192:
            c = s.recv(4096)
            if not c:
                break
            buf += c
        head, _, body = buf.partition(b"\r\n\r\n")
        first = head.split(b"\r\n")[0].decode("latin-1")
        parts = first.split()
        code = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else None
        return code, body[:400]
    except OSError as e:
        return None, type(e).__name__
    finally:
        s.close()


def main(argv):
    if len(argv) < 2:
        print(__doc__)
        return 2
    cmd = argv[1]

    if cmd == "tcp":
        bad = 0
        for p in argv[2:]:
            ok = tcp_up(int(p))
            print("  :%-5s %s" % (p, "✅ up" if ok else "🔴 down"))
            bad += 0 if ok else 1
        return 0 if bad == 0 else 1

    if cmd == "http":
        if len(argv) < 4:
            print("用法: svcprobe.py http <port> <path> [path...]")
            return 2
        port = int(argv[2])
        bad = 0
        for path in argv[3:]:
            code, body = http_get(port, path)
            if code is None:
                print("  :%-5s %-16s 🔴 %s" % (port, path, body))
                bad += 1
            else:
                print("  :%-5s %-16s ✅ HTTP %s" % (port, path, code))
                bad += 0 if code == 200 else 1
        return 0 if bad == 0 else 1

    if cmd == "wait":
        port = int(argv[2])
        budget = int(argv[3]) if len(argv) > 3 else 60
        t0 = time.time()
        while time.time() - t0 < budget:
            if tcp_up(port, timeout=1.5):
                print("  :%-5s ✅ %ds 内就绪" % (port, int(time.time() - t0)))
                return 0
            time.sleep(2)
        print("  :%-5s 🔴 %ds 超时未起" % (port, budget))
        return 1

    print("未知子命令:", cmd)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))
