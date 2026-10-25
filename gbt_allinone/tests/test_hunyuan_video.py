# -*- coding: utf-8 -*-
"""混元视频只读骨架（R-H484）用例：**三条带牙用例必须真的咬人**。"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from gbt_allinone.tools import hunyuan_video as hv


class HunyuanVideoTests(unittest.TestCase):
    def test_shape(self):
        r = hv.run("status")
        self.assertTrue(r["ok"])
        self.assertEqual(r["kind"], "hunyuan_video")
        self.assertEqual(r["domain"], "video")
        self.assertEqual(r["type"], "internal")
        self.assertFalse(r["registerd"], "只读骨架：**未登记能力位**")
        self.assertFalse(r["wired"], "只读骨架：**未接线**")
        names = [p["name"] for p in r["primitives"]]
        self.assertEqual(names, ["T2V", "I2V", "ENHANCE", "AUDIO", "EXPORT"])

    def test_teeth_land_on_disk(self):
        """牙①：结果必须落盘 —— 只给远程链接 ⇒ 拒。"""
        bad = hv.must_land_on_disk(local_path="", remote_url="https://example/x.mp4")
        self.assertTrue(bad["denied"])
        self.assertEqual(bad["rule"], "not_landed")
        ok = hv.must_land_on_disk(local_path=r"D:\out\seg_001.mp4")
        self.assertTrue(ok["ok"])

    def test_teeth_vram_within(self):
        """牙②：显存不超限 —— 超了拒；**读数取不到也不许放行**。"""
        over = hv.must_vram_within(9000, {"dedicated_mb": 4052})
        self.assertTrue(over["denied"])
        self.assertEqual(over["rule"], "vram_exceeded")
        within = hv.must_vram_within(3000, {"dedicated_mb": 4052})
        self.assertTrue(within["ok"])
        unknown = hv.must_vram_within(1000, {})
        self.assertTrue(unknown["denied"], "显存读数取不到 ⇒ 不许当够用")
        self.assertEqual(unknown["rule"], "vram_unknown")

    def test_teeth_trace(self):
        """牙③：每次操作留痕 —— 没带 source_kind ⇒ 拒。"""
        bad = hv.must_trace("")
        self.assertTrue(bad["denied"])
        self.assertEqual(bad["rule"], "no_trace")
        self.assertTrue(hv.must_trace("hunyuan_video")["ok"])

    def test_gates_aggregate(self):
        r = hv.check_gates({"local_path": r"D:\out\seg.mp4",
                            "need_mb": 9000, "reading": {"dedicated_mb": 4052},
                            "source_kind": ""})
        self.assertFalse(r["ok"])
        self.assertEqual(r["denied"], ["trace", "vram"])

    def test_execution_face_is_not_implemented(self):
        for op in ("T2V", "I2V", "ENHANCE", "AUDIO", "EXPORT"):
            r = hv.run(op)
            self.assertFalse(r["ok"], op)
            self.assertEqual(r["reason"], "not_implemented", op)


if __name__ == "__main__":
    unittest.main()
