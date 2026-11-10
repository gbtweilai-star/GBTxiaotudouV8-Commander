# -*- coding: utf-8 -*-
"""GBT小土豆V8 · DSH 插件统一入口的本机桥（只读优先）。

为什么要有这一层（主人 2026-11-10）：
    「你别动她的环境把插件统一入口就好了啊」——DSH 插件不该直接 import 框架内部，
    更不该手改她的 profile。插件只认这个 HTTP 桥；桥在本仓进程内调
    `gbt_allinone.api.run_task()`，作用域/授权/审计仍走原来的门。

口径：
    · 只绑 127.0.0.1，且要求本地令牌（默认 `state/dsh-plugin/bridge-token`）；
    · `GET /caps` 只读；`POST /run` 里 **`safe: True` 的能力直接执行**；
    · `safe: False` 的能力必须显式 `confirm: true`，否则回 `need_confirm`，
      并说明它属于“会改状态”的那一类（不替调用方猜）。
"""
from __future__ import annotations

import argparse
import hmac
import json
import os
import secrets
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

_DEFAULT_TOKEN_FILE = ROOT / "state" / "dsh-plugin" / "bridge-token"
_CAPS_CACHE: dict = {"items": None}


def _token_file() -> Path:
    raw = os.environ.get("GBT_DSH_BRIDGE_TOKEN_FILE")
    return Path(raw) if raw else _DEFAULT_TOKEN_FILE


def ensure_token() -> str:
    """读令牌；没有就现生成一个（原子落盘，0600 语义靠目录隔离）。"""
    env = str(os.environ.get("GBT_DSH_BRIDGE_TOKEN") or "").strip()
    if env:
        return env
    path = _token_file()
    if path.is_file():
        token = path.read_text(encoding="utf-8").strip()
        if token:
            return token
    path.parent.mkdir(parents=True, exist_ok=True)
    token = secrets.token_hex(24)
    tmp = path.with_name("%s.tmp-%d" % (path.name, os.getpid()))
    with open(tmp, "w", encoding="utf-8", newline="") as fh:
        fh.write(token + "\n")
        fh.flush()
        os.fsync(fh.fileno())
    os.replace(tmp, path)
    return token


def _api():
    from gbt_allinone import api
    return api


def _caps(detail: bool = False) -> list:
    if _CAPS_CACHE["items"] is None:
        _CAPS_CACHE["items"] = _api().list_capabilities(filter_dangerous=False)
    rows = _CAPS_CACHE["items"]
    if detail:
        return list(rows)
    return [{"name": r.get("name"), "status": r.get("status"),
             "safe": bool(r.get("safe"))} for r in rows]


def _cap_row(kind: str) -> dict:
    for row in _caps(detail=True):
        if row.get("name") == kind:
            return row
    return {}


class _Handler(BaseHTTPRequestHandler):
    server_version = "GBT-DSH-Bridge/0.1"
    token = ""

    def log_message(self, fmt, *args):                      # noqa: A003
        sys.stderr.write("[gbt-bridge] " + (fmt % args) + "\n")

    # ── 基础 ────────────────────────────────────────────────────────────
    def _loopback_only(self) -> bool:
        host = self.client_address[0] if self.client_address else ""
        return host in ("127.0.0.1", "::1", "::ffff:127.0.0.1")

    def _send(self, status: int, body: dict) -> None:
        data = json.dumps(body, ensure_ascii=False, default=str).encode("utf-8")
        self.send_response(status)
        self.send_header("content-type", "application/json; charset=utf-8")
        self.send_header("cache-control", "no-store")
        self.send_header("content-length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _authorized(self) -> bool:
        got = (self.headers.get("x-gbt-token")
               or self.headers.get("authorization", "").replace("Bearer ", "", 1))
        return bool(got) and hmac.compare_digest(str(got).strip(), self.token)

    def _read_json(self):
        length = int(self.headers.get("content-length") or 0)
        if length <= 0:
            return {}
        raw = self.rfile.read(length)
        return json.loads(raw.decode("utf-8"))

    # ── 路由 ────────────────────────────────────────────────────────────
    def do_GET(self):                                      # noqa: N802
        if not self._loopback_only():
            return self._send(403, {"ok": False, "error": "只允许回环地址访问"})
        parsed = urlparse(self.path)
        if parsed.path == "/health":
            try:
                total = len(_caps())
                return self._send(200, {"ok": True, "service": "gbt-dsh-bridge",
                                        "version": "0.1.0", "caps": total,
                                        "token_file": str(_token_file()),
                                        "repo": str(ROOT)})
            except Exception as e:                         # noqa: BLE001
                return self._send(500, {"ok": False, "error": str(e)[:300]})
        if not self._authorized():
            return self._send(401, {"ok": False, "status": "unauthorized",
                                    "error": "缺少/错误 x-gbt-token；令牌见 %s" % _token_file()})
        if parsed.path == "/caps":
            q = parse_qs(parsed.query)
            domain = (q.get("domain") or [""])[0].strip()
            keyword = (q.get("keyword") or [""])[0].strip().lower()
            detail = (q.get("detail") or [""])[0] not in ("", "0", "false", "False")
            limit = int((q.get("limit") or ["60"])[0] or 60)
            try:
                rows = _caps(detail=detail)
            except Exception as e:                         # noqa: BLE001
                return self._send(500, {"ok": False, "error": str(e)[:300]})
            if domain:
                rows = [r for r in rows if str(r.get("domain") or "") == domain]
            if keyword:
                rows = [r for r in rows
                        if keyword in str(r.get("name") or "").lower()
                        or keyword in str(r.get("desc") or "").lower()]
            total = len(rows)
            return self._send(200, {"ok": True, "total": total,
                                    "returned": min(total, limit),
                                    "items": rows[:max(0, limit)]})
        return self._send(404, {"ok": False, "error": "unknown route %s" % parsed.path})

    def do_POST(self):                                     # noqa: N802
        if not self._loopback_only():
            return self._send(403, {"ok": False, "error": "只允许回环地址访问"})
        if urlparse(self.path).path != "/run":
            return self._send(404, {"ok": False, "error": "unknown route"})
        if not self._authorized():
            return self._send(401, {"ok": False, "status": "unauthorized",
                                    "error": "缺少/错误 x-gbt-token；令牌见 %s" % _token_file()})
        try:
            body = self._read_json()
        except Exception as e:                             # noqa: BLE001
            return self._send(400, {"ok": False, "error": "JSON 解析失败：%s" % str(e)[:200]})
        kind = str(body.get("kind") or "").strip()
        payload = body.get("payload") or {}
        confirm = body.get("confirm") is True
        if not kind:
            return self._send(400, {"ok": False, "status": "needs_input",
                                    "error": "缺少 kind（能力位名）"})
        if not isinstance(payload, dict):
            return self._send(400, {"ok": False, "status": "needs_input",
                                    "error": "payload 必须是对象"})
        try:
            row = _cap_row(kind)
        except Exception:                                  # noqa: BLE001
            row = {}
        # 只读优先：登记为 safe 的直接执行；其余必须显式确认。
        safe = row.get("safe") is True
        if not safe and not confirm:
            return self._send(403, {
                "ok": False, "status": "need_confirm",
                "kind": kind,
                "error": "能力位 %r 会改状态（未登记为 safe），必须显式 confirm=true" % kind,
                "how": "重发同一请求并带 confirm:true；只读能力不需要这一步",
                "safe": False,
                "desc": str(row.get("desc") or "")[:200],
            })
        try:
            envelope = _api().run_task(kind, payload)
        except Exception as e:                             # noqa: BLE001
            return self._send(500, {"ok": False, "status": "failed",
                                    "error": str(e)[:400], "kind": kind})
        return self._send(200, {"ok": bool(envelope.get("ok")), "kind": kind,
                                "envelope": envelope})


def make_server(host: str = "127.0.0.1", port: int = 0, token: str | None = None):
    """建一个可直接 `serve_forever()` 的桥（测试用 port=0 取随机口）。"""
    handler = type("GBTBridgeHandler", (_Handler,), {"token": token or ensure_token()})
    return ThreadingHTTPServer((host, int(port)), handler)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="GBT小土豆V8 · DSH 能力桥（只读优先）")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=int(os.environ.get("GBT_DSH_BRIDGE_PORT", "8790")))
    parser.add_argument("--token-file", default="")
    parser.add_argument("--print-token", action="store_true")
    args = parser.parse_args(argv)
    if args.token_file:
        os.environ["GBT_DSH_BRIDGE_TOKEN_FILE"] = args.token_file
    token = ensure_token()
    if args.print_token:
        print(token)
        return 0
    server = make_server(args.host, args.port, token)
    info = {"ok": True, "service": "gbt-dsh-bridge",
            "listen": "http://%s:%d" % (args.host, server.server_address[1]),
            "token_file": str(_token_file()), "repo": str(ROOT)}
    print(json.dumps(info, ensure_ascii=False))
    sys.stdout.flush()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
