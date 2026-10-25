#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""GBT小土豆 · 全息面板鉴权门（本地反向代理）

用途
    把"只绑回环"的全息面板（默认 127.0.0.1:8765）安全地交给外部隧道，
    例如： cloudflared tunnel --url http://127.0.0.1:8766
    没有密钥的请求一律 401；带对密钥的请求换成 Cookie，密钥不再留在 URL 里。

设计约束（与 deploy/DEPLOY.md 同口径）
    - 只绑回环地址，拒绝绑 0.0.0.0；公网入口只允许隧道 / 反向代理。
    - 只依赖标准库，不引入任何第三方依赖。
    - 不记录请求体、不记录密钥；不打印每请求访问日志。
    - 支持 SSE（面板的 /api/events 靠它推事件）：响应边收边发，不做缓冲。

密钥来源（按优先级）
    1) 环境变量 GBT_PANEL_GATE_TOKEN
    2) %USERPROFILE%\\.gbt\\panel_gate_token（不存在则生成 32 字节随机并落盘）

用法
    py -3.10 deploy/panel_gate.py                 # 127.0.0.1:8766 -> 127.0.0.1:8765
    py -3.10 deploy/panel_gate.py --show-url      # 只打印带密钥的地址（密钥别贴到聊天里）
    py -3.10 deploy/panel_gate.py --selftest      # 自检：401 / 换 Cookie / 放行 / 错密钥四条契约

密钥文件权限（建议做一次，别让沙箱用户也读得到）
    icacls "%USERPROFILE%\\.gbt\\panel_gate_token" /inheritance:r /grant:r "%USERDOMAIN%\\%USERNAME%:(R,W)"
"""
from __future__ import annotations

import argparse
import hmac
import http.client
import os
import secrets
import sys
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

COOKIE_NAME = "gbt_panel_key"
TOKEN_FILE = os.path.join(os.path.expanduser("~"), ".gbt", "panel_gate_token")
LOOPBACK = ("127.0.0.1", "::1", "localhost")
HOP_BY_HOP = {
    "connection", "keep-alive", "proxy-authenticate", "proxy-authorization",
    "te", "trailers", "transfer-encoding", "upgrade",
}


def load_token(path: str = TOKEN_FILE) -> tuple[str, str]:
    """返回 (token, 来源说明)。生成新 token 时落盘，权限尽量收紧。"""
    env = os.environ.get("GBT_PANEL_GATE_TOKEN", "").strip()
    if env:
        return env, "env:GBT_PANEL_GATE_TOKEN"
    try:
        with open(path, encoding="utf-8") as fh:
            existing = fh.read().strip()
        if existing:
            return existing, "file:" + path
    except FileNotFoundError:
        pass
    except OSError as exc:
        # 读不到就大声失败：绝不静默换一把新密钥（否则线上地址会莫名失效 = 静默失效）
        raise SystemExit("密钥文件不可读：%s（%s）\n可用环境变量 GBT_PANEL_GATE_TOKEN 指定，或修复该文件权限。" % (path, exc))
    token = secrets.token_urlsafe(32)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(token)
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass
    return token, "generated:" + path


class Gate(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    server_version = "gbt-panel-gate/1.0"

    def log_message(self, fmt, *args):  # 不落访问日志（查询串可能带密钥）
        return

    # ---------- 鉴权 ----------

    def _given_token(self) -> tuple[str, bool]:
        """返回 (客户端给的密钥, 是否来自查询串)。"""
        parsed = urllib.parse.urlparse(self.path)
        query = urllib.parse.parse_qs(parsed.query, keep_blank_values=True)
        in_query = (query.get("k") or [""])[0]
        if in_query:
            return in_query, True
        header = self.headers.get("Authorization", "")
        if header.lower().startswith("bearer "):
            return header[7:].strip(), False
        for part in self.headers.get("Cookie", "").split(";"):
            name, _, value = part.strip().partition("=")
            if name == COOKIE_NAME:
                return value, False
        return "", False

    def _authorized(self) -> tuple[bool, bool]:
        given, from_query = self._given_token()
        if not given:
            return False, False
        return hmac.compare_digest(given, self.server.token), from_query  # type: ignore[attr-defined]

    # ---------- 响应工具 ----------

    def _message(self, code: int, text: str, extra_headers=()) -> None:
        payload = (
            "<!doctype html><meta charset=\"utf-8\"><title>%d</title>"
            "<body style=\"font-family:system-ui;background:#0b1020;color:#e8ecf8;padding:2rem\">"
            "<h1>%d</h1><p>%s</p></body>" % (code, code, text)
        ).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        for key, value in extra_headers:
            self.send_header(key, value)
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(payload)

    # ---------- 反向代理 ----------

    def _proxy(self) -> None:
        parsed = urllib.parse.urlparse(self.path)
        query = urllib.parse.parse_qs(parsed.query, keep_blank_values=True)
        query.pop("k", None)
        rest = urllib.parse.urlencode({k: v[0] for k, v in query.items()})
        path = parsed.path + (("?" + rest) if rest else "")

        length = int(self.headers.get("Content-Length") or 0)
        body = self.rfile.read(length) if length else None

        headers = {}
        for key, value in self.headers.items():
            if key.lower() in HOP_BY_HOP:
                continue
            headers[key] = value
        kept = [c.strip() for c in self.headers.get("Cookie", "").split(";")
                if c.strip() and not c.strip().startswith(COOKIE_NAME + "=")]
        if kept:
            headers["Cookie"] = "; ".join(kept)
        else:
            headers.pop("Cookie", None)
        headers["X-Forwarded-Proto"] = self.headers.get("X-Forwarded-Proto", "http")
        headers["X-Forwarded-For"] = self.client_address[0]

        server = self.server  # type: ignore[assignment]
        conn = http.client.HTTPConnection(server.upstream_host, server.upstream_port, timeout=300)
        try:
            conn.request(self.command, path, body=body, headers=headers)
            upstream = conn.getresponse()
        except Exception as exc:  # noqa: BLE001
            self._message(502, "上游面板不可达：%s" % exc)
            return

        self.send_response(upstream.status)
        for key, value in upstream.getheaders():
            if key.lower() in HOP_BY_HOP or key.lower() == "content-length":
                continue
            self.send_header(key, value)
        send_body = self.command != "HEAD" and upstream.status not in (204, 304)
        if send_body:
            self.send_header("Transfer-Encoding", "chunked")
        else:
            self.send_header("Content-Length", "0")
        self.end_headers()
        if not send_body:
            conn.close()
            return
        # 注意：必须用 read1。HTTPResponse.read(n) 会一直阻塞到凑满 n 字节，
        # 那会把 SSE 憋到下一次凑满 4KB 才吐（面板心跳只有 13 字节 → 要等好几分钟）。
        # read1 最多只做一次底层读，有多少发多少，这才是流式该有的行为。
        reader = getattr(upstream, "read1", None) or upstream.read
        try:
            while True:
                chunk = reader(4096)                 # 边收边发 → SSE 实时到达
                if not chunk:
                    break
                self.wfile.write(b"%x\r\n" % len(chunk) + chunk + b"\r\n")
                self.wfile.flush()
            self.wfile.write(b"0\r\n\r\n")
            self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError, TimeoutError):
            pass
        finally:
            conn.close()

    # ---------- 入口 ----------

    def _handle(self) -> None:
        ok, from_query = self._authorized()
        if not ok:
            self._message(
                401,
                "未授权。请在地址后带上 ?k=&lt;密钥&gt; —— 密钥见鉴权门启动时打印，"
                "或读 %s" % TOKEN_FILE.replace("&", "&amp;").replace("<", "&lt;"),
            )
            return
        if from_query and self.command in ("GET", "HEAD"):
            parsed = urllib.parse.urlparse(self.path)
            query = urllib.parse.parse_qs(parsed.query, keep_blank_values=True)
            query.pop("k", None)
            rest = urllib.parse.urlencode({k: v[0] for k, v in query.items()})
            location = parsed.path + (("?" + rest) if rest else "")
            secure = "; Secure" if self.headers.get("X-Forwarded-Proto", "").lower() == "https" else ""
            self.send_response(302)
            self.send_header("Location", location or "/")
            self.send_header(
                "Set-Cookie",
                "%s=%s; Path=/; HttpOnly; SameSite=Lax%s" % (COOKIE_NAME, self.server.token, secure),  # type: ignore[attr-defined]
            )
            self.send_header("Content-Length", "0")
            self.end_headers()
            return
        self._proxy()

    do_GET = do_HEAD = do_POST = do_PUT = do_DELETE = do_PATCH = do_OPTIONS = _handle


# ---------- 自检（三条契约，不需要真面板） ----------

def _selftest() -> int:
    import threading
    import urllib.error
    import urllib.request

    class Upstream(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def log_message(self, fmt, *args):
            return

        def do_GET(self):
            payload = b"UPSTREAM-OK"
            self.send_response(200)
            self.send_header("Content-Type", "text/plain")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

    upstream = ThreadingHTTPServer(("127.0.0.1", 0), Upstream)
    threading.Thread(target=upstream.serve_forever, daemon=True).start()

    token = "selftest-token-" + secrets.token_hex(4)
    gate = ThreadingHTTPServer(("127.0.0.1", 0), Gate)
    gate.daemon_threads = True
    gate.token = token
    gate.upstream_host = "127.0.0.1"
    gate.upstream_port = upstream.server_port
    threading.Thread(target=gate.serve_forever, daemon=True).start()
    port = gate.server_port

    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, *a, **kw):
            return None

    opener = urllib.request.build_opener(NoRedirect)
    failures = []

    try:
        urllib.request.urlopen("http://127.0.0.1:%d/" % port, timeout=5)
        failures.append("契约1 未带密钥应当 401，实际放行了")
    except urllib.error.HTTPError as exc:
        if exc.code != 401:
            failures.append("契约1 期望 401，实际 %s" % exc.code)

    try:
        opener.open("http://127.0.0.1:%d/?k=%s" % (port, token), timeout=5)
        failures.append("契约2 带密钥的 GET 应当 302 换 Cookie，实际未被重定向")
    except urllib.error.HTTPError as exc:
        cookie = exc.headers.get("Set-Cookie") or ""
        if exc.code != 302 or COOKIE_NAME not in cookie:
            failures.append("契约2 期望 302 + Set-Cookie，实际 %s / %s" % (exc.code, cookie))

    req = urllib.request.Request("http://127.0.0.1:%d/" % port,
                                 headers={"Cookie": "%s=%s" % (COOKIE_NAME, token)})
    with urllib.request.urlopen(req, timeout=5) as resp:
        body = resp.read()
        if resp.status != 200 or body != b"UPSTREAM-OK":
            failures.append("契约3 带 Cookie 应当透传到上游，实际 %s / %r" % (resp.status, body))

    req2 = urllib.request.Request("http://127.0.0.1:%d/" % port,
                                  headers={"Cookie": "%s=wrong" % COOKIE_NAME})
    try:
        urllib.request.urlopen(req2, timeout=5)
        failures.append("契约4 错误 Cookie 应当 401，实际放行了")
    except urllib.error.HTTPError as exc:
        if exc.code != 401:
            failures.append("契约4 期望 401，实际 %s" % exc.code)

    gate.shutdown()
    upstream.shutdown()
    if failures:
        for item in failures:
            print("FAIL " + item)
        return 1
    print("PASS 4/4：401 拦截 · 密钥换 Cookie · Cookie 放行 · 错误密钥 401")
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="GBT 全息面板鉴权门")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8766)
    parser.add_argument("--upstream-host", default="127.0.0.1")
    parser.add_argument("--upstream-port", type=int, default=8765)
    parser.add_argument("--token-file", default=TOKEN_FILE)
    parser.add_argument("--quiet-url", action="store_true", help="不打印带密钥的完整地址")
    parser.add_argument("--selftest", action="store_true", help="跑四条契约自检后退出")
    parser.add_argument("--show-url", action="store_true",
                        help="只打印带密钥的访问地址后退出（密钥不落聊天，自己终端里看）")
    args = parser.parse_args(argv)

    if args.selftest:
        return _selftest()
    if args.show_url:
        token, source = load_token(args.token_file)
        print("http://%s:%d/?k=%s" % (args.host, args.port, token))
        print("# 密钥来源: %s" % source, file=sys.stderr)
        return 0
    if args.host not in LOOPBACK:
        print("拒绝启动：鉴权门只允许绑回环地址，当前 --host %s" % args.host, file=sys.stderr)
        return 2
    if not (0 < args.port < 65536) or not (0 < args.upstream_port < 65536):
        print("拒绝启动：端口不合法", file=sys.stderr)
        return 2

    token, source = load_token(args.token_file)
    server = ThreadingHTTPServer((args.host, args.port), Gate)
    server.daemon_threads = True
    server.token = token
    server.upstream_host = args.upstream_host
    server.upstream_port = args.upstream_port

    print("GBT 面板鉴权门: http://%s:%d/  ->  http://%s:%d/"
          % (args.host, args.port, args.upstream_host, args.upstream_port))
    print("密钥来源: %s" % source)
    if not args.quiet_url:
        print("带密钥地址: http://%s:%d/?k=%s" % (args.host, args.port, token))
    print("隧道用法:   cloudflared tunnel --url http://%s:%d" % (args.host, args.port))
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
