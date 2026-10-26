#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""mock_a19 —— 假容器（:1234），只为**彩排**：验证她一起来，整条链能不能自动跑通。

红线：所有回答都带 MOCK 前缀，且 listener 端口与真容器一致但**绝不冒充真权重**。
用完立刻 kill；它写进账本的行也按前缀清掉。
"""
import json, time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

MODEL = "gbt-v8-v82-q5_0(mock)"
ANSWER = "MOCK：我是 GBT小土豆V8 的彩排替身，用来验证链路，不是真权重。"


class H(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def _j(self, obj, code=200):
        b = json.dumps(obj, ensure_ascii=False).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(b)))
        self.end_headers()
        self.wfile.write(b)

    def do_GET(self):
        if self.path.startswith("/v1/models"):
            return self._j({"object": "list", "data": [{"id": MODEL, "object": "model"}]})
        return self._j({"error": "no route"}, 404)

    def do_POST(self):
        n = int(self.headers.get("Content-Length") or 0)
        body = json.loads(self.rfile.read(n) or b"{}")
        msgs = body.get("messages") or []
        t0 = time.time()
        out = {"id": "mock", "object": "chat.completion", "model": MODEL,
               "choices": [{"index": 0, "message": {"role": "assistant",
                                                    "content": ANSWER},
                            "finish_reason": "stop"}],
               "usage": {"prompt_tokens": sum(len(str(m.get("content"))) for m in msgs) // 2,
                         "completion_tokens": 28,
                         "total_tokens": 0},
               "mock": True, "seconds": round(time.time() - t0, 3)}
        return self._j(out)

    def log_message(self, *a):
        pass


if __name__ == "__main__":
    print("mock A19 on :1234 · %s" % MODEL)
    ThreadingHTTPServer(("127.0.0.1", 1234), H).serve_forever()
