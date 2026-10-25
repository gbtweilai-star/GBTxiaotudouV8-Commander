# -*- coding: utf-8 -*-
"""吞天闭环 · 带牙用例（R-H258）。

咬的是「吞完会不会留垃圾把自己卡死」这件事：
  垃圾带进下一阶段 / 少一段没回灌 / 垃圾静默留 / 中断没续跑点 / 吞未取证来源 —— 都要红。
"""
from __future__ import annotations

import unittest

from gbt_allinone.tools import absorb_loop as al


class StageTests(unittest.TestCase):
    def test_three_stages_and_one_loop(self):
        self.assertEqual([s["key"] for s in al.STAGES],
                         ["DISTILL", "REFINE", "ABSORB"])
        self.assertEqual(al.LOOP["key"], "FED_BACK")

    def test_status_shape(self):
        st = al.run("status")
        self.assertTrue(st["ok"])
        self.assertTrue(st["readonly"])
        self.assertEqual(st["stages"], ["DISTILL", "REFINE", "ABSORB"])
        self.assertEqual(st["red_lines"], 5)

    def test_stages_op_carries_in_out(self):
        ss = al.run("stages")["stages"]
        self.assertEqual(ss[0]["in"], "原始料")
        self.assertEqual(ss[-1]["out"], "落地物")


class TeethCaseTests(unittest.TestCase):
    """四条带牙闸。"""

    def test_case1_junk_at_stage_boundary_rejected(self):
        r = al.run("gate_stage", stage="DISTILL",
                   leftovers=["a.json.deploy_bak", "b.txt"])
        self.assertFalse(r["ok"], r)
        self.assertEqual(r["rule"], "stage_dirty")
        self.assertTrue(al.run("gate_stage", stage="DISTILL",
                               leftovers=["b.txt"])["ok"])

    def test_case1_unknown_stage_rejected(self):
        self.assertEqual(al.run("gate_stage", stage="EAT")["rule"], "unknown_stage")

    def test_case2_missing_stage_rejected(self):
        r = al.run("gate_loop", stages_ran=["DISTILL", "REFINE"], fed_back=True)
        self.assertFalse(r["ok"], r)
        self.assertEqual(r["rule"], "loop_not_closed")
        self.assertEqual(r["missing"], ["ABSORB"])

    def test_case2_missing_feedback_rejected(self):
        r = al.run("gate_loop", stages_ran=["DISTILL", "REFINE", "ABSORB"],
                   fed_back=False)
        self.assertFalse(r["ok"], r)
        self.assertEqual(r["missing"], ["FED_BACK"])

    def test_case2_full_loop_ok(self):
        self.assertTrue(al.run("gate_loop",
                               stages_ran=["DISTILL", "REFINE", "ABSORB"],
                               fed_back=True)["ok"])

    def test_case3_silent_junk_rejected(self):
        r = al.run("gate_junk", paths=["x.tmp", "y.txt"])
        self.assertFalse(r["ok"], r)
        self.assertEqual(r["rule"], "junk_left_silently")

    def test_case3_declared_junk_ok(self):
        # 要么清、要么**显式登记理由** —— 登记了的就不算静默留
        r = al.run("gate_junk", paths=["x.tmp"], declared=["x.tmp"])
        self.assertTrue(r["ok"], r)
        self.assertEqual(r["declared"], ["x.tmp"])

    def test_case4_interrupted_without_resume_point_rejected(self):
        r = al.run("gate_resume", state={"stages_done": ["DISTILL"],
                                         "interrupted": True})
        self.assertFalse(r["ok"], r)
        self.assertEqual(r["rule"], "not_resumable")

    def test_case4_resume_point_ok(self):
        r = al.run("gate_resume", state={"stages_done": ["DISTILL"],
                                         "interrupted": True,
                                         "resume_from": "REFINE"})
        self.assertTrue(r["ok"], r)
        self.assertEqual(r["resume_from"], "REFINE")

    def test_case4_bad_resume_point_rejected(self):
        r = al.run("gate_resume", state={"stages_done": ["DISTILL"],
                                         "interrupted": True,
                                         "resume_from": "CHEW"})
        self.assertEqual(r["rule"], "bad_resume_point")

    def test_redline4_unevidenced_source_rejected(self):
        self.assertEqual(al.run("gate_source")["rule"], "source_unspecified")
        self.assertEqual(al.run("gate_source", source="unknown")["rule"],
                         "source_not_evidenced")
        self.assertTrue(al.run("gate_source", source="主人提供")["ok"])


class ScanTests(unittest.TestCase):
    """只读扫盘 + 去重 + 空样本不许当绿（§45）。"""

    def test_scan_junk_readonly_and_deduped(self):
        sc = al.run("junk")
        self.assertTrue(sc["readonly"])
        paths = [j["path"] for j in sc["junk"]]
        self.assertEqual(len(paths), len(set(paths)), "扫描面嵌套，必须去重")

    def test_scan_counts_sample(self):
        sc = al.run("junk")
        self.assertGreater(sc["scanned"], 0, "扫到 0 个文件 ⇒ 先怀疑扫描器自己")

    def test_scan_finds_known_junk_suffixes(self):
        for n in ("a.tmp", "b.json.deploy_bak", "c.partial"):
            self.assertIsNotNone(al._hit_junk(n))
        self.assertIsNone(al._hit_junk("normal.json"))


if __name__ == "__main__":
    unittest.main()
