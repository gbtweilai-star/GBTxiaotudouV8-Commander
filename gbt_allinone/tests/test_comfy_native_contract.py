# -*- coding: utf-8 -*-
"""原生节点契约判据（comfy_native）—— 不要 ComfyUI 的厚重外壳。"""
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from gbt_allinone.tools import comfy_native as CN  # noqa: E402


class ContractTest(unittest.TestCase):

    def test_contract_is_readable_and_counts_nodes(self):
        r = CN.run({"op": "contract"})
        self.assertTrue(r["ok"], "契约快照读不到就不许当通过")
        self.assertGreaterEqual(r["contract_nodes"], 900)
        self.assertGreaterEqual(len(r["native_nodes"]), 18)

    def test_native_nodes_share_comfyui_names(self):
        """关键契约：她的图可以用 ComfyUI 节点名，而我们自己跑。"""
        r = CN.run({"op": "contract"})
        overlap = set(r["native_also_in_contract"])
        for need in ("ImageScale", "ImageCrop", "ImageInvert", "EmptyImage", "SaveImage"):
            self.assertIn(need, overlap)

    def test_not_native_is_grouped_with_reasons(self):
        r = CN.run({"op": "contract"})
        self.assertGreater(r["contract_only"], 0)
        self.assertTrue(r["not_native_by_reason"])
        for why, row in r["not_native_by_reason"].items():
            self.assertTrue(why.strip())
            self.assertGreater(row["count"], 0)


class ValidateTest(unittest.TestCase):

    def test_unknown_node_is_an_error(self):
        wf = {"nodes": [{"id": "n1", "node": "NoSuchNode", "inputs": {}}], "edges": []}
        r = CN.run({"op": "validate", "workflow": wf})
        self.assertFalse(r["ok"])
        self.assertTrue(any("NoSuchNode" in e for e in r["errors"]))

    def test_contract_only_node_is_warning_not_error(self):
        """契约已纳·原生未接 ⇒ 警告，不许当成能跑。"""
        con = CN._contract_load()
        name = next((n for n in con if n == "KSampler"), None)
        if not name:
            self.skipTest("契约里没有 KSampler")
        wf = {"nodes": [{"id": "n1", "node": name, "inputs": {}}], "edges": []}
        r = CN.run({"op": "validate", "workflow": wf})
        self.assertTrue(r["warnings"])
        self.assertIn(name, r["contract_only_used"])

    def test_missing_required_input_is_an_error(self):
        wf = {"nodes": [{"id": "n1", "node": "ImageScale", "inputs": {}}], "edges": []}
        r = CN.run({"op": "validate", "workflow": wf})
        self.assertFalse(r["ok"])
        self.assertTrue(any("缺必填" in e for e in r["errors"]))

    def test_cycle_is_caught(self):
        wf = {"nodes": [{"id": "n1", "node": "LoadImage", "inputs": {"path": "x"}},
                        {"id": "n2", "node": "ImageInvert", "inputs": {"out": "y"}}],
              "edges": [{"from": "n1", "to": "n2", "field": "image->image"},
                        {"from": "n2", "to": "n1", "field": "out->path"}]}
        r = CN.run({"op": "validate", "workflow": wf})
        self.assertTrue(any("成环" in e for e in r["errors"]))


class NativeRunTest(unittest.TestCase):

    def test_graph_runs_without_comfyui(self):
        """⚡ 主判据：不启 8188、不装重壳，图照样跑出产物。"""
        d = tempfile.mkdtemp(prefix="cn_native_")
        try:
            wf = {"nodes": [
                {"id": "n1", "node": "EmptyImage",
                 "inputs": {"width": 32, "height": 16, "out": os.path.join(d, "a.png")}},
                {"id": "n2", "node": "ImageScale",
                 "inputs": {"width": 64, "height": 32, "out": os.path.join(d, "b.png")}},
                {"id": "n3", "node": "ImageInvert", "inputs": {"out": os.path.join(d, "c.png")}}],
                  "edges": [{"from": "n1", "to": "n2", "field": "out->image"},
                            {"from": "n2", "to": "n3", "field": "out->image"}]}
            r = CN.run({"op": "run", "workflow": wf, "expect": {}})
            self.assertTrue(r.get("ok"), r)
            for f in ("a.png", "b.png", "c.png"):
                self.assertTrue((Path(d) / f).is_file(), "%s 没落盘" % f)
            from PIL import Image
            self.assertEqual(Image.open(Path(d) / "a.png").size, (32, 16))
            self.assertEqual(Image.open(Path(d) / "b.png").size, (64, 32))
        finally:
            shutil.rmtree(d, ignore_errors=True)

    def test_whitelist_fail_closed(self):
        wf = {"nodes": [{"id": "n1", "node": "NotANode", "inputs": {}}], "edges": []}
        r = CN.run({"op": "run", "workflow": wf})
        self.assertFalse(r.get("ok"))

    def test_read_ops_registered(self):
        self.assertIn("contract", CN._READ_OPS)
        self.assertIn("validate", CN._READ_OPS)


if __name__ == "__main__":
    unittest.main(verbosity=2)
