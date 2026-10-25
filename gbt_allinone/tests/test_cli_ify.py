# -*- coding: utf-8 -*-
"""软件命令化（cli_ify）判据。"""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from gbt_allinone import cli_ify as C  # noqa: E402


class GateTest(unittest.TestCase):

    def test_fail_closed_without_signals(self):
        r = C.run("gate", name="x")
        self.assertFalse(r["ok"])
        self.assertEqual(r["reason"], "need_signals")

    def test_three_routes(self):
        self.assertEqual(C.run("gate", name="a", has_cli=True)["route"], "cli")
        self.assertEqual(C.run("gate", name="b", has_api=True)["route"], "api-wrapped")
        self.assertEqual(C.run("gate", name="c", has_gui=True)["route"], "gui-only")

    def test_cli_wins_over_api_and_gui(self):
        r = C.run("gate", name="d", has_cli=True, has_api=True, has_gui=True)
        self.assertEqual(r["route"], "cli")

    def test_rule_says_wrap_not_rewrite(self):
        self.assertIn("包壳", C.run("gate", name="e", has_api=True)["rule"])


class PlanTest(unittest.TestCase):

    def test_six_steps_and_seven_phase_mapping(self):
        r = C.run("plan", name="gimp")
        self.assertTrue(r["ok"])
        self.assertEqual(len(r["steps"]), 6)
        self.assertEqual(len(r["upstream_7phase"]), 7)

    def test_plan_needs_name(self):
        self.assertEqual(C.run("plan")["reason"], "need_name")


class RegistryTest(unittest.TestCase):

    def test_check_is_honest(self):
        r = C.run("check")
        self.assertIn("ok", r)
        self.assertEqual(r["ok"], r["violation_count"] == 0)

    def test_registry_missing_is_not_empty_green(self):
        old = C.REG
        try:
            C.REG = Path("\u6839\u672c\u4e0d\u5b58\u5728\u7684\u767b\u8bb0\u8868.json")
            self.assertEqual(C.run("registry")["reason"], "registry_not_found")
            self.assertIn("C1", [v["c"] for v in C.run("check")["violations"]])
        finally:
            C.REG = old

    def test_unknown_op_fails_closed(self):
        r = C.run("nope")
        self.assertFalse(r["ok"])
        self.assertEqual(r["reason"], "unknown_op")


if __name__ == "__main__":
    unittest.main(verbosity=2)
