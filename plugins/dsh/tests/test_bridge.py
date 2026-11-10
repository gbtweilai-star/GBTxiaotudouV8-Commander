# -*- coding: utf-8 -*-
"""DSH 统一入口桥的判据：只读直接过、改状态必须 confirm、令牌必须校验。"""
import json
import os
import sys
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from pathlib import Path

_REPO = Path(__file__).resolve().parents[3]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

os.environ.setdefault("GBT_STORE_DIR", tempfile.mkdtemp(prefix="gbt_bridge_store_"))

from plugins.dsh.bridge import gbt_bridge as BR      # noqa: E402


class TestBridge(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._tmp = tempfile.TemporaryDirectory()
        cls._token = "test-token-0123456789"
        cls.server = BR.make_server("127.0.0.1", 0, cls._token)
        cls.port = cls.server.server_address[1]
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls._tmp.cleanup()

    def _url(self, path):
        return "http://127.0.0.1:%d%s" % (self.port, path)

    def _get(self, path, token=None):
        req = urllib.request.Request(self._url(path))
        if token:
            req.add_header("x-gbt-token", token)
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                return resp.status, json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            return e.code, json.loads(e.read().decode("utf-8"))

    def _post(self, body, token=None):
        req = urllib.request.Request(
            self._url("/run"),
            data=json.dumps(body).encode("utf-8"),
            headers={"content-type": "application/json"},
            method="POST",
        )
        if token:
            req.add_header("x-gbt-token", token)
        try:
            with urllib.request.urlopen(req, timeout=120) as resp:
                return resp.status, json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            return e.code, json.loads(e.read().decode("utf-8"))

    def test_health_is_open_but_read_only(self):
        status, body = self._get("/health")
        self.assertEqual(status, 200)
        self.assertTrue(body.get("ok"))
        self.assertGreater(body.get("caps"), 400, "能力位总数应超过 400")

    def test_caps_requires_token(self):
        status, body = self._get("/caps")
        self.assertEqual(status, 401)
        self.assertEqual(body.get("status"), "unauthorized")

    def test_caps_with_token_and_domain_filter(self):
        status, body = self._get("/caps?domain=system&limit=5", token=self._token)
        self.assertEqual(status, 200)
        self.assertTrue(body.get("ok"))
        self.assertLessEqual(len(body.get("items") or []), 5)

    def test_safe_cap_runs_without_confirm(self):
        status, body = self._post({"kind": "cap_self", "payload": {"op": "list"}},
                                  token=self._token)
        self.assertEqual(status, 200)
        self.assertTrue(body.get("ok"))
        self.assertEqual(body["envelope"].get("status"), "ok")

    def test_mutating_cap_needs_confirm(self):
        from gbt_allinone import api
        unsafe = [r for r in api.list_capabilities(filter_dangerous=False)
                  if r.get("status") == "enabled" and r.get("safe") is False]
        self.assertTrue(unsafe, "注册表里应有会改状态的能力位")
        kind = unsafe[0]["name"]
        status, body = self._post({"kind": kind, "payload": {}}, token=self._token)
        self.assertEqual(status, 403)
        self.assertEqual(body.get("status"), "need_confirm")
        self.assertIn(kind, body.get("error") or "")

    def test_payload_must_be_object(self):
        status, body = self._post({"kind": "cap_self", "payload": ["x"]},
                                  token=self._token)
        self.assertEqual(status, 400)
        self.assertEqual(body.get("status"), "needs_input")


if __name__ == "__main__":
    unittest.main(verbosity=2)
