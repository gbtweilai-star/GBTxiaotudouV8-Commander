"""原生浏览器、万能插与触手接入的边界回归。"""
from __future__ import annotations

import base64
import hashlib
import json
import os
import socket
import struct
import tempfile
import threading
import types
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from unittest import mock

os.environ.setdefault("GBT_STORE_DIR", tempfile.mkdtemp(prefix="gbt_native_browser_"))

from gbt_allinone import api, browser_cap, native_browser, preflight  # noqa: E402
from gbt_allinone.security import policy  # noqa: E402


class _FakeCdpClient:
    def __init__(self, result):
        self.result = result
        self.calls = []

    def call(self, method, params=None, timeout=None):
        self.calls.append((method, params or {}))
        return self.result

    def close(self):
        return None


def _recv_exact(conn, count):
    chunks = bytearray()
    while len(chunks) < count:
        chunk = conn.recv(count - len(chunks))
        if not chunk:
            raise ConnectionError("websocket closed")
        chunks.extend(chunk)
    return bytes(chunks)


def _read_client_frame(conn):
    first, second = _recv_exact(conn, 2)
    opcode = first & 0x0F
    length = second & 0x7F
    if length == 126:
        length = struct.unpack("!H", _recv_exact(conn, 2))[0]
    elif length == 127:
        length = struct.unpack("!Q", _recv_exact(conn, 8))[0]
    mask = _recv_exact(conn, 4) if second & 0x80 else b""
    payload = _recv_exact(conn, length)
    if mask:
        payload = bytes(byte ^ mask[index % 4]
                        for index, byte in enumerate(payload))
    return opcode, payload


def _send_server_frame(conn, payload):
    raw = payload.encode("utf-8")
    if len(raw) < 126:
        header = bytes((0x81, len(raw)))
    elif len(raw) < 65536:
        header = bytes((0x81, 126)) + struct.pack("!H", len(raw))
    else:
        header = bytes((0x81, 127)) + struct.pack("!Q", len(raw))
    conn.sendall(header + raw)


class _FakeCdpHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    calls = []

    def log_message(self, *_args):
        return None

    def _json(self, value, status=200):
        raw = json.dumps(value).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def do_GET(self):
        port = self.server.server_port
        if self.path == "/json/version":
            self._json({"Browser": "FakeChrome/1.0", "Protocol-Version": "1.3"})
            return
        if self.path == "/json":
            self._json([{
                "id": "tab-1",
                "title": "Fake",
                "url": "about:blank",
                "type": "page",
                "webSocketDebuggerUrl": (
                    f"ws://127.0.0.1:{port}/devtools/page/tab-1"),
            }])
            return
        if self.path == "/devtools/page/tab-1":
            key = self.headers.get("Sec-WebSocket-Key") or ""
            expected = base64.b64encode(hashlib.sha1(
                (key + "258EAFA5-E914-47DA-95CA-C5AB0DC85B11").encode()
            ).digest()).decode()
            self.send_response(101)
            self.send_header("Upgrade", "websocket")
            self.send_header("Connection", "Upgrade")
            self.send_header("Sec-WebSocket-Accept", expected)
            self.end_headers()
            opcode, payload = _read_client_frame(self.connection)
            if opcode != 0x1:
                return
            message = json.loads(payload.decode("utf-8"))
            type(self).calls.append(message)
            method = message.get("method")
            if method == "Page.navigate":
                result = {"frameId": "frame-1", "loaderId": "loader-1"}
            else:
                result = {"ok": True}
            _send_server_frame(
                self.connection,
                json.dumps({"id": message.get("id"), "result": result}),
            )
            return
        self._json({"error": "not found"}, status=404)


class TestNativeBrowser(unittest.TestCase):
    def test_status_is_honest_without_cdp(self):
        with mock.patch.object(native_browser, "_http_json", return_value=None), \
                mock.patch.object(native_browser, "_tab_rows", return_value=[]):
            result = native_browser.status()
        self.assertFalse(result["ok"])
        self.assertTrue(result["needs_browser_debug"])
        self.assertEqual(result["status"], "needs_browser_debug")

    def test_ensure_reuses_existing_target_without_navigation(self):
        current = {
            "ok": True,
            "cdp_available": True,
            "endpoint": "http://127.0.0.1:9222",
            "browser": "Chrome/Test",
            "tab_count": 1,
        }
        tab = {
            "id": "tab-1",
            "title": "Example",
            "url": "https://example.com/path/",
            "type": "page",
            "webSocketDebuggerUrl": "",
        }
        with mock.patch.object(native_browser, "status", return_value=current), \
                mock.patch.object(native_browser, "_tab_rows", return_value=[tab]), \
                mock.patch.object(native_browser, "navigate") as navigate:
            result = native_browser.ensure("https://example.com/path")
        self.assertTrue(result["ok"])
        self.assertEqual(result["status"], "already_satisfied")
        self.assertTrue(result["already_open"])
        self.assertEqual(result["tab_id"], "tab-1")
        navigate.assert_not_called()

    def test_cookie_values_require_explicit_owner_request(self):
        client = _FakeCdpClient({
            "cookies": [{"name": "session", "value": "secret-value"}],
        })
        tab = {"id": "tab-1", "type": "page"}
        with mock.patch.object(native_browser, "_with_tab", return_value=(tab, client)):
            masked = native_browser.get_cookies()
            plain = native_browser.get_cookies(include_values=True)
        self.assertTrue(masked["values_masked"])
        self.assertEqual(masked["cookies"][0]["value"], "secr****")
        self.assertFalse(plain["values_masked"])
        self.assertEqual(plain["cookies"][0]["value"], "secret-value")

    def test_screenshot_is_a_side_effect(self):
        decision = policy.evaluate("browser", {
            "op": "native",
            "action": "screenshot",
        })
        self.assertIn("browser_control", decision.scopes)
        self.assertIn("filesystem_write", decision.scopes)
        self.assertTrue(preflight.is_side_effect(
            "browser", {"op": "native", "action": "screenshot"}, decision))
        self.assertNotIn("screenshot", native_browser.capabilities()["read_only_actions"])

    def test_api_private_network_authorization_reaches_browser(self):
        raw_decision = {
            "decision": types.SimpleNamespace(allow_private=True),
        }
        with mock.patch.object(browser_cap, "run", return_value={"ok": True}) as run:
            api._run_benign("browser", {
                "op": "native",
                "action": "navigate",
                "url": "http://127.0.0.1:8080",
            }, raw_decision)
        self.assertTrue(run.call_args.kwargs["allow_private"])
        self.assertEqual(run.call_args.kwargs["url"], "http://127.0.0.1:8080")


class TestNativeBrowserCdpTransport(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        _FakeCdpHandler.calls = []
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), _FakeCdpHandler)
        cls.server.daemon_threads = True
        cls.thread = threading.Thread(
            target=cls.server.serve_forever,
            name="gbt-fake-cdp",
            daemon=True,
        )
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=3)

    def test_navigate_uses_real_rfc6455_frame_transport(self):
        result = native_browser.navigate(
            "https://1.1.1.1/path",
            port=self.server.server_port,
            timeout=3,
        )
        self.assertTrue(result["ok"])
        self.assertEqual(result["frame_id"], "frame-1")
        self.assertEqual(result["loader_id"], "loader-1")
        self.assertTrue(any(
            call.get("method") == "Page.navigate"
            and call.get("params", {}).get("url") == "https://1.1.1.1/path"
            for call in _FakeCdpHandler.calls
        ))


if __name__ == "__main__":
    unittest.main(verbosity=2)
