import unittest

from gbt_allinone.tools import tentacle_pipeline as tp


class TentaclePipelineTests(unittest.TestCase):
    def test_constitution_counts(self):
        self.assertEqual(len(tp.LAYERS), 4)
        self.assertEqual(len(tp.STEPS), 7)
        self.assertEqual(len(tp.AXIOMS), 3)
        self.assertEqual(len(tp.RED_LINES), 5)
        self.assertEqual(len(tp.SHORT_BOARDS), 6)

    def test_report_direction_only_goes_up_one_layer(self):
        self.assertTrue(tp.route_allowed("L1", "L2")["ok"])
        self.assertFalse(tp.route_allowed("L1", "L3")["ok"])
        self.assertFalse(tp.route_allowed("L3", "L2")["ok"])

    def test_authorization_direction_only_goes_down_one_layer(self):
        self.assertTrue(tp.route_allowed("L4", "L3", direction="auth")["ok"])
        self.assertFalse(tp.route_allowed("L4", "L2", direction="auth")["ok"])
        self.assertFalse(tp.route_allowed("L2", "L3", direction="auth")["ok"])

    def test_report_requires_evidence(self):
        bad = tp.report_valid({"self_check": True})
        self.assertFalse(bad["ok"])
        self.assertIn("evidence", bad["missing"])
        good = tp.report_valid({"self_check": True, "readings": {"x": 1}, "evidence": "trace:1"})
        self.assertTrue(good["ok"])

    def test_dry_run_requires_readings(self):
        self.assertFalse(tp.dry_run_valid({})["ok"])
        self.assertTrue(tp.dry_run_valid({"workspace_isolated": True})["ok"])

    def test_publish_requires_review_rollback_and_auth(self):
        bad = tp.publish_ready(review_ok=True, rollback="snap")
        self.assertFalse(bad["ok"])
        self.assertIn("authorization", bad["missing"])
        good = tp.publish_ready(review_ok=True, rollback="snap", authorization="owner")
        self.assertTrue(good["ok"])

    def test_readouts_are_honest_about_gap(self):
        r = tp.readouts()
        self.assertTrue(r["ok"])
        self.assertIn("known_gap", r)

    def test_unknown_direction_cannot_fall_through_to_authorization(self):
        self.assertFalse(tp.route_allowed("L4", "L3", direction="typo")["ok"])

    def test_failed_or_untyped_self_check_is_rejected(self):
        for self_check in (False, "false", 1, {"ok": False}):
            with self.subTest(self_check=self_check):
                self.assertFalse(tp.report_valid({
                    "self_check": self_check, "readings": {"count": 1},
                    "evidence": "trace:1",
                })["ok"])

    def test_failed_or_invalid_readings_are_rejected(self):
        for readings in (None, [], "passed", {"isolated": False},
                         {"isolated": "false"}, {"value": None},
                         {"value": float("nan")}, {"value": float("inf")},
                         {"": 1}, {"nested": {"ok": False}}):
            with self.subTest(readings=readings):
                self.assertFalse(tp.run(op="dry_run", readings=readings)["ok"])
        self.assertTrue(tp.dry_run_valid({"failures": 0, "delta": -1})["ok"])

    def test_report_rejects_bad_input_and_blank_evidence(self):
        for report in ([], "passed", 1):
            self.assertFalse(tp.run(op="report", report=report)["ok"])
        for evidence in ("  ", {}, ["trace:1"]):
            self.assertFalse(tp.report_valid({
                "self_check": True, "readings": {"count": 1},
                "evidence": evidence,
            })["ok"])

    def test_structural_pass_does_not_claim_evidence_verified(self):
        result = tp.report_valid({"self_check": True,
                                  "readings": {"count": 1}, "evidence": "trace:1"})
        self.assertTrue(result["ok"])
        self.assertFalse(result["evidence_verified"])
        self.assertEqual(result["validation_scope"], "structure_only")


if __name__ == "__main__":
    unittest.main()
