# -*- coding: utf-8 -*-
"""取帧回执必须带 path（2026-11-07）。

`see` 的帧原本只在 `image_base64` 里，`看` 回执把它过滤掉后，按路径取帧的调用方
（对话层 / 视觉链）只拿到 fmt/size —— 等于没帧。这里守住补上的那一步。
"""
from __future__ import annotations

import base64
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
PNG = b"\x89PNG\r\n\x1a\n" + b"0" * 40


def _load():
    # 必须按包导入：omni_plug 里有 dataclass 与相对导入，裸按文件加载会炸
    from gbt_allinone import omni_plug
    return omni_plug


class FramePathReceiptTest(unittest.TestCase):
    def test_memory_frame_becomes_file_with_path(self):
        mod = _load()
        with tempfile.TemporaryDirectory() as td:
            with mock.patch.object(mod, "FRAME_DIR", Path(td)):
                cap = mod._persist_frame({"ok": True, "fmt": "png",
                                          "image_base64": base64.b64encode(PNG).decode()})
                self.assertTrue(cap.get("path"), cap)
                p = Path(cap["path"])
                self.assertTrue(p.is_file())
                self.assertEqual(p.read_bytes(), PNG)
                self.assertEqual(p.suffix, ".png")
                self.assertEqual(cap.get("frame_bytes"), len(PNG))

    def test_jpeg_format_maps_to_jpg(self):
        mod = _load()
        with tempfile.TemporaryDirectory() as td:
            with mock.patch.object(mod, "FRAME_DIR", Path(td)):
                cap = mod._persist_frame({"ok": True, "fmt": "jpeg",
                                          "image_base64": base64.b64encode(b"\xff\xd8\xffx").decode()})
                self.assertEqual(Path(cap["path"]).suffix, ".jpg")

    def test_existing_path_is_left_alone(self):
        mod = _load()
        cap = {"ok": True, "path": "C:/already/there.png", "image_base64": "AAAA"}
        self.assertEqual(mod._persist_frame(dict(cap)), cap)

    def test_no_frame_is_left_alone(self):
        mod = _load()
        cap = {"ok": True, "fmt": "png"}
        self.assertEqual(mod._persist_frame(dict(cap)), cap)


if __name__ == "__main__":
    unittest.main()
