# -*- coding: utf-8 -*-
"""理解任何事（know_map）判据。"""
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from gbt_allinone import know_map as KM  # noqa: E402


def _fixture() -> Path:
    d = Path(tempfile.mkdtemp(prefix="km_fix_"))
    (d / "main.py").write_text("import helper\nimport os\n", encoding="utf-8")
    (d / "helper.py").write_text("from . import util\n", encoding="utf-8")
    (d / "util.py").write_text("VALUE = 1\n", encoding="utf-8")
    (d / "README.md").write_text("# \u8bf4明\n\u8fd9里用到 helper.py \u548c util.py\n", encoding="utf-8")
    sub = d / "sub"
    sub.mkdir()
    (sub / "deep.py").write_text("x = 1\n", encoding="utf-8")
    return d


class ScanTest(unittest.TestCase):

    def test_missing_target_is_honest(self):
        r = KM.run("scan", target="\u6839\u672c\u4e0d\u5b58\u5728\u7684\u8def\u5f84zzz")
        self.assertFalse(r["ok"])
        self.assertEqual(r["reason"], "target_not_found")

    def test_empty_target_is_not_success(self):
        d = Path(tempfile.mkdtemp(prefix="km_empty_"))
        r = KM.run("scan", target=str(d))
        self.assertFalse(r["ok"])
        self.assertEqual(r["reason"], "empty_target")

    def test_scan_counts_and_entrypoint(self):
        r = KM.run("scan", target=str(_fixture()))
        self.assertTrue(r["ok"], r)
        self.assertGreaterEqual(r["files"], 5)
        self.assertIn("main.py", r["entrypoints"])
        self.assertIn(".py", r["by_ext"])


class BuildTest(unittest.TestCase):

    def test_every_edge_carries_evidence(self):
        """主判据：每条边必须能指回 path 或 path:line。"""
        d = _fixture()
        r = KM.run("build", target=str(d), slug="selftest-km")
        self.assertTrue(r["ok"], r)
        g = KM._load("selftest-km")
        self.assertGreater(len(g["edges"]), 0)
        for e in g["edges"]:
            self.assertTrue(e.get("evidence"), e)
            self.assertIn(e["rel"], ("\u5bfc\u5165", "\u63d0\u53ca"))

    def test_layers_split_structure_and_knowledge(self):
        d = _fixture()
        KM.run("build", target=str(d), slug="selftest-km")
        lay = KM.run("layers", slug="selftest-km")
        self.assertTrue(lay["ok"], lay)
        self.assertIn("\u77e5\u8bc6", lay["layers"])
        self.assertIn("\u7ed3\u6784", lay["layers"])

    def test_partial_visible_when_truncated(self):
        d = _fixture()
        r = KM.run("build", target=str(d), slug="selftest-km", max_files=2)
        self.assertTrue(r["ok"], r)
        self.assertTrue(r.get("partial"), "截断必须在图上可见")


class TeachTest(unittest.TestCase):

    def setUp(self):
        KM.run("build", target=str(_fixture()), slug="selftest-km")

    def test_tour_steps_have_evidence(self):
        r = KM.run("tour", slug="selftest-km")
        self.assertTrue(r["ok"], r)
        for s in r["steps"]:
            self.assertTrue(s.get("evidence"), s)

    def test_ask_needs_query_and_returns_evidence(self):
        self.assertEqual(KM.run("ask", slug="selftest-km")["reason"], "need_query")
        r = KM.run("ask", slug="selftest-km", query="helper")
        self.assertTrue(r["ok"])
        self.assertGreater(r["hit_count"], 0)
        for h in r["hits"]:
            self.assertTrue(h.get("evidence"), h)

    def test_impact_needs_changed_and_is_honest(self):
        self.assertEqual(KM.run("impact", slug="selftest-km")["reason"], "need_changed")
        r = KM.run("impact", slug="selftest-km", changed="helper.py")
        self.assertTrue(r["ok"])
        self.assertIn("helper.py", r["matched_nodes"])

    def test_unknown_op_fails_closed(self):
        r = KM.run("nope")
        self.assertFalse(r["ok"])
        self.assertEqual(r["reason"], "unknown_op")


if __name__ == "__main__":
    unittest.main(verbosity=2)
