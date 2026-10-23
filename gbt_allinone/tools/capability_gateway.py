# gbt-capability: capability_gateway
# ⛔ 开发者：自由的风 · 永久钢印 · 禁止删除
"""能力网关 · 把 run_task 万能插暴露成本地 HTTP API（2026-09-26 主人令同化外部 AI）。

安全设计（三道闸）：
  1. **只绑 127.0.0.1** —— 本机外部 AI（GenOffice agent 等）可调，公网不可达；
  2. **令牌鉴权** —— 请求头 X-GBT-Token 必须等于环境变量 GBT_GATEWAY_TOKEN（宿主设置，不落盘）；
  3. **门不绕过** —— 调用方按「非可信会话」处理：policy 全套作用域闸照常生效，
     受限能力照样要人工授权（网关不给任何人开后门）。

用法：
  python tools/capability_gateway.py serve [--port 31717]
  curl -X POST http://127.0.0.1:31717/run_task -H "X-GBT-Token: <token>" \
       -d '{"kind":"scrapling","payload":{"op":"status"}}'
  GET /health → 存活与版本（免令牌）
"""
from __future__ import annotations

import json
import os
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

_PORT_DEFAULT = 31717
_MAX_BODY = 1_000_000


def _token_ok(received: str | None) -> bool:
    token = os.environ.get("GBT_GATEWAY_TOKEN", "").strip()
    return bool(token) and bool(received) and received.strip() == token


class Handler(BaseHTTPRequestHandler):
    server_version = "GBT-CapabilityGateway/1.0"

    def _json(self, code: int, obj: dict):
        body = json.dumps(obj, ensure_ascii=False, default=str).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path == "/health":
            self._json(200, {"ok": True, "service": "gbt-capability-gateway",
                             "version": "1.0", "auth": "X-GBT-Token header",
                             "note": "调用方按非可信会话处理：受限能力照常走人工授权闸"})
            return
        self._json(404, {"ok": False, "error": "未知路径（仅 /health 与 /run_task）"})

    def do_POST(self):
        if self.path != "/run_task":
            self._json(404, {"ok": False, "error": "未知路径"})
            return
        if not _token_ok(self.headers.get("X-GBT-Token")):
            self._json(401, {"ok": False, "denied": True,
                             "error": "令牌缺失或不匹配（X-GBT-Token ≠ GBT_GATEWAY_TOKEN）"})
            return
        try:
            length = int(self.headers.get("Content-Length") or 0)
            if length <= 0 or length > _MAX_BODY:
                self._json(400, {"ok": False, "error": "请求体缺失或超过 1MB 限额"})
                return
            req = json.loads(self.rfile.read(length).decode("utf-8"))
            kind = str(req.get("kind") or "").strip()
            payload = req.get("payload") or {}
            if not kind:
                self._json(400, {"ok": False, "error": "缺 kind"})
                return
            from gbt_allinone import api as _api
            # 🔒 关键：不进 owner_session —— 调用方按「非可信会话」走全套作用域闸
            result = _api.run_task(kind, payload if isinstance(payload, dict) else {})
            self._json(200, {"ok": True, "kind": kind, "result": result})
        except Exception as exc:                               # noqa: BLE001
            self._json(500, {"ok": False, "error": f"{type(exc).__name__}: {str(exc)[:200]}"})


def main():
    port = int(sys.argv[sys.argv.index("--port") + 1]) if "--port" in sys.argv else _PORT_DEFAULT
    if not os.environ.get("GBT_GATEWAY_TOKEN"):
        print("🔴 未设 GBT_GATEWAY_TOKEN —— 网关拒绝裸奔启动（先在宿主设置令牌）")
        return 2
    srv = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    print(f"GBT 能力网关在线: http://127.0.0.1:{port}  (health / run_task · 令牌鉴权 · 非可信会话闸)")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
