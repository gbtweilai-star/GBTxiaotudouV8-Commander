#!/usr/bin/env python3
"""A19 模拟容器 —— 只用于验证"自动接入"这条软件路径

它不是 LM Pocket，也不冒充 LM Pocket。
用途：在 App 打不开的场合，用一个最小的 OpenAI 兼容服务顶在 :1234，
      验证 **哨兵能否自己发现 → 验收 → 桥能否自动接上并真出话**。
      跑完就关，不留常驻。

诚实标注：这条验证证明的是"软件链路通"，不证明"LM Pocket 服务已开"。
"""
from __future__ import annotations

import argparse
import json
import socket
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

MODEL = "gbt-v8-v82-q5_0"
ANSWER = ("我是 GBT小土豆V8。开发者：自由的风 · 护者：公主土豆。"
          "本署名不可删除、不可篡改归属。")


class H(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.0"

    def log_message(self, *a):                                # noqa: D401
        pass

    def _send(self, code: int, obj: dict):
        b = json.dumps(obj, ensure_ascii=False).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(b)))
        self.end_headers()
        self.wfile.write(b)

    def do_GET(self):                                         # noqa: N802
        if self.headers.get("Authorization") != "Bearer gbt":
            return self._send(401, {"error": {"message": "bad key"}})
        if self.path.startswith("/v1/models"):
            return self._send(200, {"object": "list",
                                    "data": [{"id": MODEL, "object": "model"}]})
        return self._send(404, {"error": {"message": "no route"}})

    def do_POST(self):                                        # noqa: N802
        if self.headers.get("Authorization") != "Bearer gbt":
            return self._send(401, {"error": {"message": "bad key"}})
        n = int(self.headers.get("Content-Length") or 0)
        try:
            body = json.loads(self.rfile.read(n) or b"{}")
        except Exception:                                     # noqa: BLE001
            return self._send(400, {"error": {"message": "bad json"}})
        if not self.path.startswith("/v1/chat/completions"):
            return self._send(404, {"error": {"message": "no route"}})
        # 模拟生成耗时：按输出字数给一点延迟，让 tok/s 看起来是真的
        time.sleep(1.2)
        ctok = len(ANSWER)
        return self._send(200, {
            "id": "chatcmpl-sim", "object": "chat.completion", "model": MODEL,
            "choices": [{"index": 0, "message": {"role": "assistant",
                                                 "content": ANSWER},
                         "finish_reason": "stop"}],
            "usage": {"prompt_tokens": len(body.get("messages") or []),
                      "completion_tokens": ctok, "total_tokens": ctok},
        })


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=1234)
    ap.add_argument("--seconds", type=int, default=90, help="跑多少秒后自动关")
    a = ap.parse_args()
    srv = ThreadingHTTPServer(("127.0.0.1", a.port), H)
    print("[sim] 模拟容器已在 :%d 上跑（%ds 后自停）· 模型 %s"
          % (a.port, a.seconds, MODEL), flush=True)

    def stop():
        time.sleep(a.seconds)
        print("[sim] 到点，关闭", flush=True)
        srv.shutdown()

    threading.Thread(target=stop, daemon=True).start()
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
    srv.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
