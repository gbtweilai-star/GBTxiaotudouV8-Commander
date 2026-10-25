import hashlib
import unittest

from gbt_allinone import api
from gbt_allinone.tools import research_intel as ri


class ResearchReportTests(unittest.TestCase):
    def payload(self):
        content = "Title\nThe executor uses threads.\n"
        return {"op": "report", "question": "Which executor?",
                "sources": [{"id": "executor", "origin": "repo:executor.py",
                             "content": content,
                             "sha256": hashlib.sha256(content.encode()).hexdigest()}],
                "claims": [{"text": "Uses threads", "source_id": "executor",
                            "quote": "The executor uses threads."}]}

    def test_normal_report_through_real_gateway_and_repeat(self):
        first = api.run_task("video_intel", self.payload(), stamp=False)
        second = api.run_task("video_intel", self.payload(), stamp=False)
        self.assertTrue(first["ok"], first)
        result = first["result"]
        self.assertEqual(result["report_id"], second["result"]["report_id"])
        self.assertEqual(result["report"]["claims"][0]["line"], 2)
        self.assertFalse(result["verified"])
        self.assertFalse(result["usable_for_decision"])
        self.assertFalse(result["source_fetched"])

    def test_gate_receives_rows_through_gateway(self):
        result = api.run_task("video_intel", {"op": "gate", "rows": [
            {"dimension": "forbidden_lists", "finding": "blocked"}]}, stamp=False)
        self.assertEqual(result["result"]["decision"], "hold")

    def test_tamper_blocked_then_corrected_input_recovers(self):
        payload = self.payload()
        payload["sources"][0]["content"] += "tampered"
        self.assertFalse(ri.run(**payload)["ok"])
        self.assertTrue(ri.run(**self.payload())["ok"])

    def test_claim_cannot_reference_absent_source_or_quote(self):
        for key, value in (("source_id", "other-room"), ("quote", "invented")):
            payload = self.payload()
            payload["claims"][0][key] = value
            result = ri.run(**payload)
            self.assertFalse(result["ok"])
            self.assertIsNone(result["report"])

    def test_duplicate_source_id_refused(self):
        payload = self.payload()
        payload["sources"].append(dict(payload["sources"][0]))
        self.assertFalse(ri.run(**payload)["ok"])

    def test_malformed_and_empty_inputs_refused(self):
        for key in ("question", "sources", "claims"):
            for value in (None, [], {}, ""):
                payload = self.payload()
                payload[key] = value
                self.assertFalse(ri.run(**payload)["ok"])

    def test_nonfinite_confidence_cannot_enable_decisions(self):
        for confidence in (float("nan"), float("inf"), -float("inf")):
            row = ri.make_intel("video_intel", "traffic_trend", "finding",
                                evidence="source", confidence=confidence)
            self.assertFalse(row["usable_for_decision"])


if __name__ == "__main__":
    unittest.main()
