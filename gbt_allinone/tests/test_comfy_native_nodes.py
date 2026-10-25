# -*- coding: utf-8 -*-
"""传统算法面原生节点判据（R-H997）。"""
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from gbt_allinone.tools import comfy_native as CN  # noqa: E402

NEW_NODES = ("ImageBlend", "ImageHueSaturation", "ImageLevels", "ImageRotate",
             "ImageTranspose", "ImagePadForOutpaint", "MaskBlur", "MaskComposite",
             "ImageBatchMulti")


class CamelCaseDispatchTest(unittest.TestCase):

    def test_camelcase_node_runs_as_op(self):
        """回归：曾把 op 转小写 ⇒ 驼峰节点名全被 fail-closed。"""
        d = tempfile.mkdtemp(prefix="cn_case_")
        try:
            out = os.path.join(d, "e.png")
            r = CN.run({"op": "EmptyImage", "inputs": {"width": 8, "height": 8, "out": out}})
            self.assertTrue(r.get("ok"), r)
            self.assertTrue(Path(out).is_file())
        finally:
            shutil.rmtree(d, ignore_errors=True)

    def test_lowercase_typo_still_fails_closed(self):
        r = CN.run({"op": "emptimage", "inputs": {}})
        self.assertFalse(r.get("ok"))


class TraditionalFamilyTest(unittest.TestCase):

    def setUp(self):
        self.d = tempfile.mkdtemp(prefix="cn9_")
        CN.run({"op": "EmptyImage", "inputs": {"width": 48, "height": 32, "color": 16711680, "out": self.f("red.png")}})
        CN.run({"op": "EmptyImage", "inputs": {"width": 48, "height": 32, "color": 255, "out": self.f("blue.png")}})
        CN.run({"op": "EmptyImage", "inputs": {"width": 24, "height": 16, "color": 0, "out": self.f("m1.png")}})
        CN.run({"op": "EmptyImage", "inputs": {"width": 24, "height": 16, "color": 16777215, "out": self.f("m2.png")}})

    def tearDown(self):
        shutil.rmtree(self.d, ignore_errors=True)

    def f(self, n):
        return os.path.join(self.d, n)

    def _run(self, node, **inputs):
        inputs["out"] = self.f(node + ".png")
        r = CN.run({"op": node, "inputs": inputs})
        self.assertTrue(r.get("ok"), node + " 没跑通")
        self.assertTrue(Path(inputs["out"]).is_file(), node + " 没落盘")
        return r.get("result") or {}

    def test_image_blend(self):
        res = self._run("ImageBlend", image1=self.f("red.png"), image2=self.f("blue.png"), blend_factor=0.4, blend_mode="multiply")
        self.assertEqual(res["blend_mode"], "multiply")

    def test_image_blend_rejects_unknown_mode(self):
        r = CN.run({"op": "ImageBlend", "inputs": {"image1": self.f("red.png"), "image2": self.f("blue.png"), "blend_mode": "nope", "out": self.f("x.png")}})
        self.assertFalse(r.get("ok"))

    def test_hue_saturation_marks_itself_approximate(self):
        res = self._run("ImageHueSaturation", image=self.f("red.png"), hue=0.3, saturation=0.2)
        self.assertIn("honest", res)

    def test_levels_runs(self):
        res = self._run("ImageLevels", image=self.f("red.png"), black=10, white=240, gamma=1.2)
        self.assertEqual(res["gamma"], 1.2)

    def test_levels_rejects_inverted_range(self):
        r = CN.run({"op": "ImageLevels", "inputs": {"image": self.f("red.png"), "black": 200, "white": 10, "out": self.f("l.png")}})
        self.assertFalse(r.get("ok"))

    def test_rotate_expands_canvas(self):
        res = self._run("ImageRotate", image=self.f("red.png"), angle=30)
        self.assertGreater(res["size"][0], 48)

    def test_transpose_swaps_size(self):
        res = self._run("ImageTranspose", image=self.f("red.png"), transpose="rotate_90")
        self.assertEqual(res["size"], [32, 48])

    def test_transpose_rejects_unknown(self):
        r = CN.run({"op": "ImageTranspose", "inputs": {"image": self.f("red.png"), "transpose": "nope", "out": self.f("t.png")}})
        self.assertFalse(r.get("ok"))

    def test_pad_grows_and_is_honest(self):
        res = self._run("ImagePadForOutpaint", image=self.f("red.png"), left=8, top=4, right=8, bottom=4)
        self.assertEqual(res["size"], [64, 40])
        self.assertIn("honest", res)

    def test_pad_rejects_zero(self):
        r = CN.run({"op": "ImagePadForOutpaint", "inputs": {"image": self.f("red.png"), "out": self.f("p.png")}})
        self.assertFalse(r.get("ok"))

    def test_mask_blur(self):
        res = self._run("MaskBlur", mask=self.f("m2.png"), radius=3)
        self.assertEqual(res["radius"], 3)

    def test_mask_composite(self):
        res = self._run("MaskComposite", mask1=self.f("m1.png"), mask2=self.f("m2.png"), x=4, y=2, operation="add")
        self.assertEqual(res["operation"], "add")

    def test_batch_multi_stacks(self):
        res = self._run("ImageBatchMulti", image1=self.f("red.png"), image2=self.f("blue.png"))
        self.assertEqual(res["count"], 2)
        self.assertEqual(res["size"][1], 64)

    def test_batch_multi_needs_two(self):
        r = CN.run({"op": "ImageBatchMulti", "inputs": {"image1": self.f("red.png"), "out": self.f("b.png")}})
        self.assertFalse(r.get("ok"))


class CoverageTest(unittest.TestCase):

    def test_native_set_grew(self):
        r = CN.run({"op": "contract"})
        self.assertGreaterEqual(len(r["native_nodes"]), 27)
        for n in NEW_NODES:
            self.assertIn(n, r["native_nodes"])

    def test_same_name_plus_own_equals_total(self):
        """同名 + 自有 必须等于原生总数（不许漏算）。"""
        r = CN.run({"op": "contract"})
        self.assertEqual(len(r["native_also_in_contract"]) + len(r["native_only"]), len(r["native_nodes"]))


if __name__ == "__main__":
    unittest.main(verbosity=2)

