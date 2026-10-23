# -*- coding: utf-8 -*-
"""裸 socket 读 /api/events 20 秒 —— 区分「流是死的」与「我的读法有问题」。

上一版用 urllib + read(1) 收到 0 字节。实现里明明有 flush，且 15s 一次心跳。
所以要么流真死，要么读法不对。裸 socket 不吃任何客户端缓冲，能一锤定音。
"""
import json
import socket
import sys
import threading
import time
import urllib.request
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
Path(__file__).resolve().parent.parent

raw = []


def reader(sock, seconds):
    sock.settimeout(seconds)
    t0 = time.time()
    try:
        while time.time() - t0 < seconds:
            data = sock.recv(4096)
            if not data:
                raw.append(b"__EOF__")
                break
            raw.append(data)
    except socket.timeout:
        raw.append(b"__RECV_TIMEOUT__")
    except Exception as e:  # noqa: BLE001
        raw.append(("__ERR__" + str(e)).encode())


s = socket.create_connection(("127.0.0.1", 8765), timeout=10)
s.sendall(b"GET /api/events HTTP/1.1\r\nHost: 127.0.0.1:8765\r\n"
          b"Accept: text/event-stream\r\nConnection: keep-alive\r\n\r\n")

th = threading.Thread(target=reader, args=(s, 20), daemon=True)
th.start()
time.sleep(3.0)

body = json.dumps({"kind": "caps_called_audit", "payload": {}, "confirm": True}).encode()
req = urllib.request.Request("http://127.0.0.1:8765/api/capability", data=body,
                             headers={"Content-Type": "application/json"}, method="POST")
with urllib.request.urlopen(req, timeout=20) as r:
    posted = json.loads(r.read().decode())
print("POST:", json.dumps(posted, ensure_ascii=False))
th.join(timeout=24)

blob = b"".join(raw)
print("\n原始收到 %d 字节" % len(blob))
print("--- 前 600 字节 ---")
print(blob[:600].decode("utf-8", "replace"))
print("--- 末 600 字节 ---")
print(blob[-600:].decode("utf-8", "replace"))

blocks = [b for b in blob.split(b"\n\n") if b.strip()]
print("\nSSE 块数: %d" % len(blocks))
rid = posted.get("request_id")
for b in blocks:
    if rid and rid.encode() in b:
        print("\n=== 命中 request_id 的块 ===")
        print(b.decode("utf-8", "replace")[:900])
        break
else:
    print("没有块带 request_id=%s" % rid)
