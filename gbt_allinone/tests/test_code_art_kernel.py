# -*- coding: utf-8 -*-
"""代码艺术内核 · 带牙用例（R-H188）。

① 五原语齐、三层归位（表达层/生成层/交付层）；
② 红线①：**无种子不许导出**（seed_missing）；
③ 红线②：图层**只追加**，要改走 `rollback_layer()`（可逆）；
④ 红线③：索引**只读**（骨架期空，不假装有数据）；
⑤ 红线④：**批量导出必带元数据**（meta=False + batch=True ⇒ 拒）；
⑥ 导出记录带元数据（种子/画布/图层数）；内核只读：无网络/写盘/绘图路径。
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
for p in (ROOT, ROOT / "gbt_allinone"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from gbt_allinone.tools import code_art_kernel as cak  # noqa: E402


class PrimitiveTests(unittest.TestCase):
    def test_five_primitives_and_three_layers(self):
        st = cak.CodeArtKernel().status()
        self.assertEqual([p["key"] for p in st["primitives"]], list(cak.PRIMITIVES))
        self.assertEqual({p["layer"] for p in st["primitives"]},
                         {"表达层", "生成层", "交付层"})

    def test_index_is_readonly_and_empty_in_skeleton(self):
        idx = cak.CodeArtKernel().index("noise")
        self.assertTrue(idx["readonly"])
        self.assertEqual(idx["count"], 0, "骨架期索引为空 —— 空就是空")


class RedLineTests(unittest.TestCase):
    def setUp(self):
        self.k = cak.CodeArtKernel()
        self.w = self.k.new_work("art-001", "深夜写代码时看到的那张图")

    def test_export_without_seed_is_refused(self):
        out = self.k.export(self.w)
        self.assertFalse(out["ok"])
        self.assertEqual(out["reason"], "seed_missing")
        self.assertEqual(self.w.status, "draft", "被拒的导出不许改状态")

    def test_layers_only_append_and_rollback_is_the_way_back(self):
        self.k.add_layer(self.w, {"kind": "bg", "color": "#111"})
        self.k.add_layer(self.w, {"kind": "noise", "amt": 0.2})
        self.assertEqual(len(self.w.layers), 2)
        back = self.k.rollback_layer(self.w, 1)
        self.assertEqual(back["dropped"], 1)
        self.assertEqual(len(self.w.layers), 1)
        self.assertEqual(self.w.layers[0]["kind"], "bg", "回退是从栈顶往下丢")

    def test_batch_export_must_carry_metadata(self):
        self.k.set_seed(self.w, 20260920)
        bad = self.k.export(self.w, batch=True, meta=False)
        self.assertFalse(bad["ok"])
        self.assertEqual(bad["reason"], "batch_needs_metadata")
        ok = self.k.export(self.w, batch=True, meta=True)
        self.assertTrue(ok["ok"])
        self.assertTrue(ok["with_metadata"])

    def test_export_record_carries_seed_canvas_and_layers(self):
        self.k.set_canvas(self.w, 2048, 2048, "webgl")
        self.k.set_seed(self.w, 42)
        self.k.add_layer(self.w, {"kind": "bg"})
        rec = self.k.export(self.w, fmt="webp")
        self.assertTrue(rec["ok"])
        self.assertEqual(rec["seed"], 42)
        self.assertEqual(rec["canvas"], [2048, 2048, "webgl"])
        self.assertEqual(rec["layers_count"], 1)
        self.assertEqual(self.w.status, "exported")
        self.assertEqual(len(self.w.exports), 1)

    def test_module_has_no_draw_network_or_write_paths(self):
        src = Path(cak.__file__).read_text(encoding="utf-8")
        for bad in ("import requests", "import urllib", "import socket", "import subprocess",
                    ".write_text(", ".write_bytes(", "unlink(", "from ..store",
                    "PIL", "matplotlib", "turtle"):
            self.assertNotIn(bad, src, "只读内核里不该出现：%s" % bad)


if __name__ == "__main__":
    unittest.main()
