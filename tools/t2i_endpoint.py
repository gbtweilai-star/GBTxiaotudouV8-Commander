#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""t2i_endpoint —— 自建文生图端点的**最小契约壳**（给 qwen-image / comfyui / 任何自建服务套一层）。

为什么需要它：`comfy_native.t2i_qwen` 认的是一种很窄的契约 ——
    POST {prompt, size, steps, seed}  →  {image_b64 | url}
各家自建服务（vLLM、ComfyUI、diffusers 裸脚本）回包形状都不一样，套一层就不用改节点。

用法：
    T2I_BACKEND=http://127.0.0.1:8188/prompt python3 tools/t2i_endpoint.py --port 8899
    # 然后： export GBT_T2I_ENDPOINT=http://127.0.0.1:8899/v1/images/generations

没配后端时会**如实回 501**，不假装出图。
"""
import argparse
import base64
import json
import os
import time
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

BACKEND = os.environ.get("T2I_BACKEND", "")
MODEL = os.environ.get("T2I_MODEL", "qwen-image")


class H(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def _json(self, code, obj):
        b = json.dumps(obj, ensure_ascii=False).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(b)))
        self.end_headers()
        self.wfile.write(b)

    def do_GET(self):
        if self.path.startswith("/health"):
            return self._json(200, {
                "ok": bool(BACKEND), "service": "t2i-endpoint", "model": MODEL,
                "backend": BACKEND or None,
                "missing": [] if BACKEND else ["T2I_BACKEND（要指向你自建的出图服务）"],
                "contract": {"in": ["prompt", "size", "steps", "seed"],
                             "out": ["image_b64", "url"]}})
        return self._json(404, {"error": "no route"})

    def do_POST(self):
        n = int(self.headers.get("Content-Length") or 0)
        try:
            body = json.loads(self.rfile.read(n) or b"{}")
        except Exception:                                         # noqa: BLE001
            return self._json(400, {"error": "请求体不是 JSON"})

        if not BACKEND:
            return self._json(501, {
                "ok": False, "status": "needs_dependency",
                "missing": ["T2I_BACKEND"], "model": MODEL,
                "口径": "没有后端就不假装出图"})

        t0 = time.time()
        try:
            req = urllib.request.Request(
                BACKEND, data=json.dumps({
                    "prompt": body.get("prompt") or "",
                    "size": body.get("size") or "768x1024",
                    "steps": int(body.get("steps") or 8),
                    "seed": int(body.get("seed") or 0),
                }).encode(), method="POST",
                headers={"Content-Type": "application/json"})
            raw = urllib.request.urlopen(req, timeout=300).read()
            try:
                d = json.loads(raw)
            except Exception:                                     # noqa: BLE001
                # 后端直接回字节流也算数
                return self._json(200, {"image_b64": base64.b64encode(raw).decode(),
                                        "model": MODEL,
                                        "seconds": round(time.time() - t0, 2)})
            out = {"model": d.get("model") or MODEL,
                   "seconds": round(time.time() - t0, 2)}
            if d.get("image_b64"):
                out["image_b64"] = d["image_b64"]
            elif d.get("url") or d.get("image"):
                out["url"] = d.get("url") or d.get("image")
            elif d.get("images"):
                out["url"] = d["images"][0] if isinstance(d["images"][0], str) else None
                out["image_b64"] = d["images"][0] if isinstance(d["images"][0], str) is False else None
            else:
                return self._json(502, {"error": "后端回包认不出", "raw": str(d)[:300]})
            return self._json(200, out)
        except Exception as exc:                                  # noqa: BLE001
            return self._json(502, {"error": "%s: %s" % (type(exc).__name__, str(exc)[:200]),
                                    "backend": BACKEND})

    def log_message(self, *a):                                    # noqa: D401
        pass


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8899)
    a = ap.parse_args()
    print("t2i-endpoint :%d · backend=%s · model=%s" % (a.port, BACKEND or "(未配)", MODEL))
    ThreadingHTTPServer(("127.0.0.1", a.port), H).serve_forever()
