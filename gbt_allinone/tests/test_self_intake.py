# -*- coding: utf-8 -*-
"""未命中即取源判据（self_intake）。"""
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from gbt_allinone import self_intake as SI  # noqa: E402
from gbt_allinone.security import policy  # noqa: E402


def _scopes(payload):
    d = policy.evaluate("self_intake", payload or {})
    return sorted(getattr(d, "scopes", ()) or ())


class GateTest(unittest.TestCase):

    def test_unknown_topic_is_refused(self):
        """主判据：本地未命中且无出处 ⇒ **拒绝干活**。"""
        r = SI.run("gate", topic="zzz_一个不存在的概念_不可能有出处")
        self.assertFalse(r["ok"])
        self.assertTrue(r["denied"])
        self.assertEqual(r["rule"], "no_knowledge_no_source")
        self.assertEqual(r["next_action"], "intake")
        self.assertIn("self_intake", r["how"])

    def test_source_ref_that_exists_passes(self):
        r = SI.run("gate", topic="zzz_一个不存在的概念_不可能有出处",
                   source_ref="AGENTS.md")
        self.assertTrue(r["ok"])
        self.assertEqual(r["basis"], "source_ref")

    def test_source_ref_that_does_not_exist_is_refused(self):
        r = SI.run("gate", topic="zzz_一个不存在的概念", source_ref="no/such/file.md")
        self.assertFalse(r["ok"])
        self.assertEqual(r["rule"], "source_ref_missing")

    def test_gate_needs_topic(self):
        r = SI.run("gate")
        self.assertFalse(r["ok"])
        self.assertEqual(r["reason"], "need_topic")


class KnownTest(unittest.TestCase):

    def test_known_returns_hit_or_honest_miss(self):
        r = SI.run("known", topic="休谟 趣味")
        self.assertTrue(r["ok"])
        if not r["known"]:
            self.assertEqual(r["next_action"], "intake")
            self.assertIn("rule", r)


class IntakeTest(unittest.TestCase):

    def test_no_source_fetched_is_honest(self):
        r = SI.run("intake", topic="空源测试", urls=["http://127.0.0.1:1/nope"])
        self.assertFalse(r["ok"])
        self.assertEqual(r["reason"], "no_source_fetched")
        self.assertTrue(r["failed"])

    def test_local_file_intake_then_known_hits(self):
        """递归：取源 → 入库 → 再查就命中。"""
        topic = "判据测试_铝合金焊接工艺"
        r = SI.run("intake", topic=topic, files=["AGENTS.md"], lang="zh")
        self.assertTrue(r["ok"], r)
        self.assertGreater(r["sources"], 0)
        k = SI.run("known", topic=topic)
        self.assertTrue(k["known"], "intake 后必须命中" if r["indexed"] else "")
        # 收尾：删掉这次测试造的胶囊与护照（不留垃圾）
        for p in (r.get("capsule"), r.get("passport")):
            if p and Path(p).is_file():
                Path(p).unlink()
        for d in (ROOT / "gbt_allinone" / "store" / "devoured").glob("*铝合金*"):
            if d.is_dir():
                shutil.rmtree(d, ignore_errors=True)

    def test_intake_needs_topic(self):
        r = SI.run("intake")
        self.assertFalse(r["ok"])
        self.assertEqual(r["reason"], "need_topic")


class RulesAndGateTest(unittest.TestCase):

    def test_rules_state_the_executor_is_the_plug(self):
        r = SI.run("rules")
        self.assertTrue(r["ok"])
        self.assertEqual(len(r["loop"]), 5)
        self.assertEqual(len(r["iron_laws"]), 3)

    def test_read_ops_zero_scope_write_needs_grant(self):
        for op in SI.READ_OPS:
            with self.subTest(op=op):
                self.assertEqual(_scopes({"op": op}), [])
        self.assertEqual(_scopes({"op": "intake"}), ["filesystem_write"])

    def test_unknown_op_fails_closed(self):
        r = SI.run("nope")
        self.assertFalse(r["ok"])
        self.assertEqual(r["reason"], "unknown_op")
        self.assertIn("executor", r)


class DirectionTest(unittest.TestCase):

    def test_miss_carries_direction_from_graph(self):
        from gbt_allinone import topic_web as TW
        TW.run("build", items=[
            {"id": "d1", "source": "HN", "title": "agentic pentest",
             "text": "Agentic pentest. Red team.", "tags": ["Agent安全"]},
            {"id": "d2", "source": "X", "title": "Anthropic Cyber Verification",
             "text": "Anthropic expands Cyber Verification.", "tags": ["Agent安全"]},
        ])
        r = SI.run("gate", topic="Agent安全边界实验")
        self.assertEqual(r["rule"], "no_knowledge_no_source")
        d = r.get("direction") or {}
        self.assertTrue(d.get("anchors"))
        self.assertTrue(d.get("suggest_terms"))


class ChainAndMatchTest(unittest.TestCase):

    def test_chain_all_three_present(self):
        r = SI.run("chain")
        self.assertTrue(r["ok"], r)
        self.assertEqual(r["missing"], [])
        self.assertEqual([s["capsule_id"] for s in r["steps"]],
                         ["high-iq-g-factor", "design-thinking-dschool", "hume-aesthetics"])

    def test_chain_is_fail_closed(self):
        old = SI.CHAIN
        try:
            SI.CHAIN = old + [{"step": 9, "name": "不存在的第四件",
                              "capsule_id": "no-such-capsule-zzz", "keys": ["zzz不存在"],
                              "rule": "x"}]
            r = SI.run("chain")
            self.assertFalse(r["ok"])
            self.assertIn("no-such-capsule-zzz", r["missing"])
        finally:
            SI.CHAIN = old

    def test_title_match_beats_body_crosstalk(self):
        r = SI.run("known", topic="高智商")
        self.assertTrue(r["known"], r)
        self.assertEqual(r["matched_in"], "title")
        self.assertIn("高智商", str(r["matched"]))
        self.assertNotIn("设计思维", str(r["matched"]))

    def test_new_capsules_are_hits(self):
        for q in ("高智商 g因子", "设计思维 d.school"):
            with self.subTest(q=q):
                self.assertTrue(SI.run("known", topic=q)["known"], q)



if __name__ == "__main__":
    unittest.main(verbosity=2)
