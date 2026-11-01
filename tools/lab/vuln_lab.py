"""GBT小土豆V8 · 自训靶场（本机自有，故意留洞；仅 127.0.0.1）

主人 2026-11-02：「下一步」——正规挖洞前先在**自有靶场**练手，零外部风险。

本靶场故意包含 6 类常见问题（全部只读触发，不做破坏）：
  1. 反射型 XSS（/search?q= 原样回显）
  2. IDOR（/api/user?id= 无鉴权拿别的用户）
  3. 路径穿越（/download?file=../secret.txt）
  4. 调试信息泄漏（/debug 暴露环境与 debug=true）
  5. 未授权管理页（/admin 无鉴权）
  6. 缺安全响应头（无 CSP/X-Content-Type-Options 等）

仅供本机自测：绑定 127.0.0.1，写入只落在本进程临时目录。

开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

USERS = {
    "1": {"id": 1, "name": "alice", "role": "user", "email": "alice@lab.local"},
    "2": {"id": 2, "name": "root", "role": "admin", "email": "root@lab.local",
          "api_token": "LAB-ADMIN-TOKEN-DO-NOT-USE"},
}

PAGE = """<!doctype html><html><head><meta charset="utf-8"><title>GBT Lab</title></head>
<body><h1>自训靶场</h1>
<ul>
<li><a href="/search?q=hello">搜索</a></li>
<li><a href="/api/user?id=1">用户</a></li>
<li><a href="/download?file=readme.txt">下载</a></li>
<li><a href="/debug">调试</a></li>
<li><a href="/admin">管理</a></li>
</ul></body></html>"""


def build_lab(root: Path) -> None:
    (root / "public").mkdir(parents=True, exist_ok=True)
    (root / "public" / "readme.txt").write_text("public readme\n", encoding="utf-8")
    (root / "secret.txt").write_text("SECRET-LAB-FLAG-7f3a\n", encoding="utf-8")


class LabHandler(BaseHTTPRequestHandler):
    server_version = "GBTLab/0.1"
    lab_root = Path(".")

    def log_message(self, *args):  # 静默
        pass

    def _send(self, code: int, body: bytes, ctype: str = "text/html; charset=utf-8"):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        # 故意不发安全头（靶场漏洞 6）
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):  # noqa: N802
        u = urlparse(self.path)
        q = parse_qs(u.query)
        try:
            if u.path in ("/", "/index.html"):
                return self._send(200, PAGE.encode())
            if u.path == "/healthz":
                return self._send(200, b'{"ok":true}', "application/json")
            if u.path == "/search":
                term = (q.get("q") or [""])[0]
                # 反射型 XSS：原样回显
                return self._send(200, ("<html><body><h2>搜索：%s</h2></body></html>" % term).encode())
            if u.path == "/api/user":
                uid = (q.get("id") or ["1"])[0]
                # IDOR：无鉴权，任何 id 都能拿
                return self._send(200, json.dumps(USERS.get(uid, {"error": "not found"}),
                                                  ensure_ascii=False).encode(),
                                  "application/json")
            if u.path == "/download":
                name = (q.get("file") or ["readme.txt"])[0]
                # 路径穿越：未做 normpath 限制
                fp = Path(self.lab_root) / "public" / name
                try:
                    data = fp.read_text(encoding="utf-8", errors="replace")
                except Exception:
                    return self._send(404, b"not found")
                return self._send(200, data.encode(), "text/plain; charset=utf-8")
            if u.path == "/debug":
                # 调试信息泄漏
                env = {k: os.environ.get(k) for k in ("PATH", "USERNAME", "COMPUTERNAME")}
                return self._send(200, json.dumps({
                    "debug": True, "server": self.server_version,
                    "env": env, "cwd": os.getcwd()}, ensure_ascii=False).encode(),
                    "application/json")
            if u.path == "/admin":
                # 未授权管理页
                return self._send(200, ("<html><body><h2>Admin Console</h2>"
                                        "<p>flag=ADMIN-NO-AUTH-OK</p></body></html>").encode())
            return self._send(404, b"not found")
        except Exception:  # noqa: BLE001
            return self._send(500, b"error")


def serve(port: int, lab_root: Path) -> ThreadingHTTPServer:
    handler = type("BoundLabHandler", (LabHandler,), {"lab_root": lab_root})
    srv = ThreadingHTTPServer(("127.0.0.1", port), handler)
    return srv


def main(argv) -> int:
    port = int(argv[1]) if len(argv) > 1 else 18866
    root = Path(argv[2]) if len(argv) > 2 else Path(tempfile.mkdtemp(prefix="gbt-lab-"))
    build_lab(root)
    srv = serve(port, root)
    print("LAB_READY http://127.0.0.1:%d root=%s" % (port, root), flush=True)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
