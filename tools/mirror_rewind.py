#!/usr/bin/env python3
"""镜像空间回滚动作（供 rehearsal.rollback 调用）

回到上一个时间线版本；没有时间线就如实说没有，不假装回滚过。
"""
import socket, json, sys
def call(op, payload=None):
    body = json.dumps({"op": op, "payload": payload or {}}).encode()
    s = socket.socket(); s.settimeout(120)
    try:
        s.connect(("127.0.0.1", 8765))
        s.sendall(b"POST /api/mirror HTTP/1.0\r\nHost: x\r\nContent-Type: application/json\r\n"
                  b"Content-Length: " + str(len(body)).encode() + b"\r\n\r\n" + body)
        b = b""
        while True:
            c = s.recv(65536)
            if not c: break
            b += c
        return json.loads(b.split(b"\r\n\r\n", 1)[1])
    finally:
        s.close()

st = call("status")
r = (st.get("gbt_result") or {}).get("result") or st.get("result") or {}
n = r.get("timelines") or 0
if not n:
    print("  没有时间线可回滚（timelines=0）—— 如实报告，不假装回滚过")
    sys.exit(0)
d = call("rewind", {"version": 1})
print("  rewind →", "ok" if d.get("ok") else str(d.get("error"))[:120])
sys.exit(0 if d.get("ok") else 1)
