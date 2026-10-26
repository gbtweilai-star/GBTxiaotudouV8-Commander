#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""假桥 —— 只为验证页面发的请求长什么样（不碰 A19、不碰云）。

GET  /health                → 形状对齐真桥，selfhost 指向 :1234
POST /v1/chat/completions   → 把请求体原样记到 /tmp/mock_req.jsonl，
                              stream 时按 OpenAI SSE 回一段固定假话
GET  /_rec                  → 直接读回记录
"""
import json
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

REC = "/tmp/mock_req.jsonl"
TRANSCRIPT = "/var/minis/shared/gbtv8/state/her_transcript.jsonl"
FAKE = "（假桥）我是 GBT小土豆V8。开发者：自由的风 · 守护者：公主土豆。"


class H(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def _cors(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")

    def _json(self, code, obj):
        b = json.dumps(obj, ensure_ascii=False).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(b)))
        self._cors()
        self.end_headers()
        self.wfile.write(b)

    def do_OPTIONS(self):
        self.send_response(204)
        self._cors()
        self.send_header("Content-Length", "0")
        self.end_headers()

    def do_GET(self):
        if self.path.startswith("/health"):
            return self._json(200, {
                "ok": True, "service": "mock-bridge", "default": "selfhost",
                "upstreams": [{"name": "selfhost", "base_url": "http://127.0.0.1:1234/v1",
                               "model": "", "key_slot": "raw:loopback", "key_ready": True},
                              {"name": "ours", "base_url": "https://x", "model": "gbt-v8-v83",
                               "key_slot": "missing:potato", "key_ready": False}]})
        if self.path.startswith("/_log/tail"):
            n = 20
            try:
                n = max(1, min(200, int(self.path.split("n=")[1].split("&")[0])))
            except Exception:
                pass
            rows = []
            try:
                with open(TRANSCRIPT, encoding="utf-8") as fh:
                    for line in fh.readlines()[-n:]:
                        line = line.strip()
                        if line:
                            rows.append(json.loads(line))
            except Exception:
                rows = []
            return self._json(200, {"ok": True, "count": len(rows), "rows": rows,
                                    "file": TRANSCRIPT})
        if self.path.startswith("/_rec"):
            try:
                rows = [json.loads(x) for x in open(REC, encoding="utf-8") if x.strip()]
            except Exception:                                     # noqa: BLE001
                rows = []
            return self._json(200, {"count": len(rows), "rows": rows})
        self.send_response(404)
        self.send_header("Content-Length", "0")
        self._cors()
        self.end_headers()

    def do_POST(self):
        n = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(n).decode("utf-8", "replace") if n else "{}"
        try:
            body = json.loads(raw)
        except Exception:                                         # noqa: BLE001
            body = {"_raw": raw}
        with open(REC, "a", encoding="utf-8") as fh:
            fh.write(json.dumps({"at": time.strftime("%H:%M:%S"), "body": body},
                                ensure_ascii=False) + "\n")

        if self.path.startswith("/_log/message"):
            import os as _os
            _os.makedirs(_os.path.dirname(TRANSCRIPT), exist_ok=True)
            rec = {"at": time.strftime("%Y-%m-%dT%H:%M:%S"),
                   "role": body.get("role"), "text": str(body.get("text") or "")[:8000],
                   "upstream": body.get("upstream"), "model": body.get("model")}
            with open(TRANSCRIPT, "a", encoding="utf-8") as fh:
                fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
            return self._json(200, {"ok": True, "saved": True, "file": TRANSCRIPT})

        if body.get("stream"):
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Cache-Control", "no-cache")
            self.send_header("Connection", "close")
            self._cors()
            self.end_headers()
            for i in range(0, len(FAKE), 6):
                chunk = {"id": "mock", "object": "chat.completion.chunk",
                         "model": "mock-q5", "choices": [{"index": 0,
                                                          "delta": {"content": FAKE[i:i + 6]}}]}
                self.wfile.write(("data: " + json.dumps(chunk, ensure_ascii=False)
                                  + "\n\n").encode())
                self.wfile.flush()
                time.sleep(0.05)
            self.wfile.write(b"data: [DONE]\n\n")
            self.wfile.flush()
            self.close_connection = True
            return

        self._json(200, {"id": "mock", "model": "mock-q5",
                         "choices": [{"index": 0, "message": {"role": "assistant",
                                                              "content": FAKE}}],
                         "usage": {"prompt_tokens": 10, "completion_tokens": 20}})

    def log_message(self, *a):                                    # noqa: D401
        pass


if __name__ == "__main__":
    ThreadingHTTPServer(("127.0.0.1", 8791), H).serve_forever()
