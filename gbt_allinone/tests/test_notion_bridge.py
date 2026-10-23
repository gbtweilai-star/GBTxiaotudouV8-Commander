from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
WORKSPACE = ROOT.parent
for path in (WORKSPACE, ROOT):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from gbt_allinone import notion_bridge as NB  # noqa: E402


class NotionBridgeTests(unittest.TestCase):
    def setUp(self):
        NB._CACHE.clear()
        NB._LAST_ERROR = ""
        self.env = mock.patch.dict(os.environ, {}, clear=False)
        self.env.start()
        os.environ.pop("GBT_NOTION_TOKEN", None)
        os.environ.pop("NOTION_TOKEN", None)
        self.tmp = tempfile.TemporaryDirectory()
        self.secret = Path(self.tmp.name) / "notion.dpapi"
        os.environ["GBT_NOTION_SECRET_FILE"] = str(self.secret)

    def tearDown(self):
        self.env.stop()
        self.tmp.cleanup()

    def test_status_reports_missing_without_credential(self):
        status = NB.status()

        self.assertTrue(status["ok"])
        self.assertFalse(status["configured"])
        self.assertEqual(status["credential_source"], "missing")
        self.assertNotIn("token", json.dumps(status).lower())

    def test_store_token_uses_encrypted_file_without_plaintext(self):
        marker = "ntn_test_marker_123456789"
        with (
            mock.patch.object(NB, "_protect_dpapi", return_value=b"ciphertext"),
            mock.patch.object(NB, "_unprotect_dpapi", return_value=marker.encode("utf-8")),
        ):
            stored = NB.store_token(marker)
            status = NB.status()

        self.assertTrue(stored["ok"])
        self.assertEqual(self.secret.read_bytes(), b"ciphertext")
        self.assertNotIn(marker.encode("utf-8"), self.secret.read_bytes())
        self.assertTrue(status["configured"])
        self.assertEqual(status["credential_source"], "dpapi")
        self.assertTrue(status["credential_protected"])

    def test_search_returns_metadata_without_full_page_payload(self):
        response = {
            "results": [
                {
                    "object": "page",
                    "id": "page-1",
                    "url": "https://www.notion.so/page-1",
                    "created_time": "2026-09-14T08:00:00Z",
                    "last_edited_time": "2026-09-14T08:12:00Z",
                    "in_trash": False,
                    "properties": {
                        "title": {
                            "type": "title",
                            "title": [{"plain_text": "会议记录"}],
                        }
                    },
                    "secret_field": "must-not-leak",
                }
            ],
            "has_more": False,
        }
        with mock.patch.object(NB, "_request", return_value=response):
            result = NB.search("会议")

        self.assertTrue(result["ok"])
        self.assertEqual(result["results"][0]["title"], "会议记录")
        self.assertNotIn("secret_field", json.dumps(result))

    def test_page_extracts_transcription_status_and_children(self):
        page = {
            "object": "page",
            "id": "page-1",
            "url": "https://www.notion.so/page-1",
            "created_time": "2026-09-14T08:00:00Z",
            "last_edited_time": "2026-09-14T08:12:00Z",
            "in_trash": False,
            "properties": {
                "title": {
                    "type": "title",
                    "title": [{"plain_text": "会议 2026/9/14"}],
                }
            },
        }
        roots = {
            "results": [
                {
                    "id": "transcription-1",
                    "type": "transcription",
                    "has_children": True,
                    "transcription": {
                        "title": [{"plain_text": "会议"}],
                        "status": "transcription_not_started",
                    },
                }
            ],
            "has_more": False,
        }
        children = {
            "results": [
                {
                    "id": "paragraph-1",
                    "type": "paragraph",
                    "has_children": False,
                    "paragraph": {"rich_text": [{"plain_text": "确认框架接入"}]},
                }
            ],
            "has_more": False,
        }

        def request(_method, path, **_kwargs):
            if path.startswith("/pages/"):
                return page
            if "transcription-1" in path:
                return children
            return roots

        with mock.patch.object(NB, "_request", side_effect=request):
            result = NB.page("page-1")

        self.assertTrue(result["ok"])
        self.assertIn("会议 [transcription not started]", result["text"])
        self.assertIn("确认框架接入", result["text"])

    def test_run_rejects_unknown_operation_without_network(self):
        with mock.patch.object(NB, "_request", side_effect=AssertionError("must not call")):
            result = NB.run({"op": "delete"})

        self.assertFalse(result["ok"])
        self.assertIn("未知 Notion 操作", result["error"])


if __name__ == "__main__":
    unittest.main()
