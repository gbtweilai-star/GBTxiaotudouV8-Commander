# -*- coding: utf-8 -*-
"""对话层送帧接线测试（2026-11-07）。

不连真模型：拦 urllib，检查 `_openai_chat` 是否把原生帧编成
OpenAI 兼容的 image_url data URL，而不是只发文本。
"""
from __future__ import annotations

import base64
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
SERVER = ROOT / "tools" / "console-server.py"
PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
)


def _load():
    spec = importlib.util.spec_from_file_location("console_server_frame_test", SERVER)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class _Resp:
    def __init__(self, payload=None):
        self._payload = payload or {"choices": [{"message": {"content": "OK"}}]}

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self):
        return json.dumps(self._payload).encode("utf-8")


class ChatFrameWiringTest(unittest.TestCase):
    def _run(self, image_path="", image_paths=None):
        mod = _load()
        box = {}

        def fake_urlopen(req, timeout=None):
            box["body"] = json.loads(req.data.decode("utf-8"))
            return _Resp()

        cfg = {"base_url": "http://127.0.0.1:1", "name": "vlm", "api_key": "k",
               "temperature": 0.0, "max_tokens": 16}
        with mock.patch("urllib.request.urlopen", fake_urlopen):
            out = mod._openai_chat("看图", cfg, image_path=image_path,
                                   image_paths=image_paths or [])
        return out, box.get("body") or {}

    def test_frame_becomes_image_url(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "frame.png"
            p.write_bytes(PNG)
            out, body = self._run(str(p))
        self.assertTrue(out.get("ok"), out.get("error"))
        self.assertTrue(out.get("image_sent"), out)
        content = body["messages"][-1]["content"]
        self.assertIsInstance(content, list)
        self.assertEqual(content[0]["type"], "text")
        self.assertEqual(content[1]["type"], "image_url")
        self.assertTrue(content[1]["image_url"]["url"].startswith("data:image/png;base64,"))

    def test_jpeg_frame_gets_jpeg_mime(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "frame.jpg"
            p.write_bytes(b"\xff\xd8\xff\xe0" + b"0" * 64)
            out, body = self._run(str(p))
        self.assertTrue(out.get("image_sent"), out)
        content = body["messages"][-1]["content"]
        self.assertTrue(content[1]["image_url"]["url"].startswith("data:image/jpeg;base64,"))

    def test_missing_frame_is_not_claimed(self):
        out, body = self._run(str(Path(tempfile.gettempdir()) / "no-such-frame-xyz.png"))
        self.assertFalse(out.get("image_sent"), out)
        self.assertIsInstance(body["messages"][-1]["content"], str)
        mod = _load()
        marked = mod._mark_frame_degraded(dict(out), {"path": "x.png", "missing": True}, "帧缺失")
        self.assertTrue(marked.get("degraded"), marked)
        self.assertEqual(marked.get("why_degraded"), "帧缺失")

    def test_multiple_frames_go_in_order(self):
        with tempfile.TemporaryDirectory() as td:
            a = Path(td) / "a.png"
            b = Path(td) / "b.png"
            a.write_bytes(PNG)
            b.write_bytes(PNG)
            out, body = self._run("", image_paths=[str(a), str(b)])
        self.assertEqual(out.get("images_sent"), 2, out)
        content = body["messages"][-1]["content"]
        self.assertEqual([c["type"] for c in content],
                         ["text", "image_url", "image_url"])

    def test_frame_cap_is_four(self):
        with tempfile.TemporaryDirectory() as td:
            paths = []
            for i in range(6):
                p = Path(td) / ("f%d.png" % i)
                p.write_bytes(PNG)
                paths.append(str(p))
            out, body = self._run("", image_paths=paths)
            mod = _load()
            urls = mod._frames_data_urls(paths)
        self.assertEqual(len(urls), 4)
        self.assertEqual(out.get("images_sent"), 4, out)

    def test_partial_frames_are_marked_degraded(self):
        mod = _load()
        res = mod._mark_frame_degraded({"ok": True, "images_sent": 4},
                                       {"path": "x", "frames_total": 10}, "x")
        self.assertTrue(res.get("degraded"), res)
        self.assertIn("4/10", res.get("why_degraded") or "")

    def test_reasoning_length_retries_once_with_bigger_budget(self):
        mod = _load()
        calls = []

        def fake(req, timeout=None):
            calls.append(json.loads(req.data.decode("utf-8"))["max_tokens"])
            if len(calls) == 1:
                return _Resp({"choices": [{"message": {"content": None}, "finish_reason": "length"}],
                              "usage": {"completion_tokens_details": {"reasoning_tokens": 535}}})
            return _Resp({"choices": [{"message": {"content": "看到了"}, "finish_reason": "stop"}]})

        cfg = {"base_url": "http://127.0.0.1:1", "name": "vlm", "api_key": "k",
               "temperature": 0.0, "max_tokens": 1024}
        with mock.patch("urllib.request.urlopen", fake):
            out = mod._openai_chat("看图", cfg)
        self.assertTrue(out.get("ok"), out)
        self.assertEqual(out.get("text"), "看到了")
        self.assertEqual(len(calls), 2)
        self.assertGreater(calls[1], calls[0])

    def test_reasoning_only_never_faked_as_answer(self):
        mod = _load()
        empty = {"choices": [{"message": {"content": None}, "finish_reason": "length"}],
                 "usage": {"completion_tokens_details": {"reasoning_tokens": 900}}}
        with mock.patch("urllib.request.urlopen", lambda req, timeout=None: _Resp(empty)):
            out = mod._openai_chat("看图", {"base_url": "http://127.0.0.1:1", "name": "vlm",
                                            "api_key": "k", "max_tokens": 128})
        self.assertFalse(out.get("ok"), out)
        self.assertIn("思考", out.get("error") or "")

    def test_without_frame_stays_text(self):
        out, body = self._run("")
        self.assertTrue(out.get("ok"), out.get("error"))
        self.assertFalse(out.get("image_sent"))
        self.assertIsInstance(body["messages"][-1]["content"], str)


if __name__ == "__main__":
    unittest.main()
