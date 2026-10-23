# -*- coding: utf-8 -*-
"""创作融合台 判据（comfy_forge）。"""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from gbt_allinone import comfy_forge as CF  # noqa: E402
from gbt_allinone.security import policy  # noqa: E402


class ForgeContractTest(unittest.TestCase):

    def test_snapshot_is_readable(self):
        r = CF.run("evidence")
        self.assertTrue(r["ok"], "快照读不到就不许当通过")
        p = r["provenance"]
        self.assertGreaterEqual(p["surface_nodes"], CF.MIN_NODES,
                                "节点数低于阈值 ⇒ 判断连")
        self.assertIsNotNone(p["captured_at"], "快照必须写采集时间")

    def test_families_cover_every_node(self):
        r = CF.run("families")
        self.assertTrue(r["ok"])
        total = sum(f["nodes"] for f in r["families"])
        self.assertEqual(total, r["total_nodes"], "分族必须一个不漏")
        names = {f["family"] for f in r["families"]}
        for need in ("生图", "视频", "音频", "3D"):
            self.assertIn(need, names)

    def test_every_family_points_at_real_capabilities(self):
        from gbt_allinone import caps_tables
        live = {c["name"] for c in caps_tables.all_caps()}
        r = CF.run("families")
        for f in r["families"]:
            for cap in f["feeds_capabilities"]:
                self.assertIn(cap, live, "%s 饲了不存在的能力位 %s" % (f["family"], cap))

    def test_unknown_op_fails_closed(self):
        r = CF.run("no_such_op")
        self.assertFalse(r["ok"])
        self.assertEqual(r["reason"], "unknown_op")

    def test_find_requires_query(self):
        r = CF.run("find")
        self.assertFalse(r["ok"])
        self.assertEqual(r["reason"], "need_query", "不给词不许猜")

    def test_chinese_query_reaches_english_nodes(self):
        """主人令后补：她用中文问，节点名全英文。"""
        r = CF.run("find", q="视频", limit=5)
        self.assertTrue(r["ok"])
        self.assertGreater(r["total"], 0, "中文关键词必须能到达英文节点")

    def test_read_only_zero_scope(self):
        for op in CF.READ_OPS:
            with self.subTest(op=op):
                d = policy.evaluate("comfy_forge", {"op": op})
                scopes = sorted(getattr(d, "scopes", ()) or ())
                self.assertEqual(scopes, [], "只读台不许挂作用域")
        self.assertEqual(tuple(CF.WRITE_OPS), (), "本位不许有写 op")


if __name__ == "__main__":
    unittest.main(verbosity=2)
