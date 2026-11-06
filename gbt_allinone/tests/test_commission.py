# -*- coding: utf-8 -*-
"""交办单的机器判据（2026-11-06）。

这批判据防的是两种「像人」的假象：
  ① 把问句当任务（于是该回答的时候反问）；
  ② 把「缺对象」当完整交办（于是 20 秒的模型替你猜一个对象，猜错还得重来）。
"""
import json
import sys
import tempfile
import unittest
from pathlib import Path

_REPO = Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from gbt_allinone import commission as CM   # noqa: E402


class TestParse(unittest.TestCase):
    def test_task_with_object_and_spec(self):
        r = CM.parse("帮我把那段视频导出成 1080x1920 竖屏")
        self.assertEqual(r["kind"], "task")
        self.assertEqual(r["object"], "那段视频")
        self.assertIn("1080x1920", " ".join(r["constraints"]))
        self.assertIn("竖屏", " ".join(r["constraints"]))
        self.assertTrue(r["complete"], r["missing"])

    def test_transitive_without_object_is_flagged(self):
        r = CM.parse("帮我导出")
        self.assertEqual(r["kind"], "task")
        self.assertEqual(r["missing"], ["object"])
        self.assertTrue(r["ask"])

    def test_polite_prefix_does_not_become_task(self):
        self.assertEqual(CM.parse("请")["kind"], "empty")

    def test_question_is_not_a_task(self):
        for q in ("你会看屏幕吗？", "这个能不能过线", "为什么这么慢"):
            r = CM.parse(q)
            self.assertEqual(r["kind"], "question", q)
            self.assertEqual(r["missing"], [])

    def test_accept_and_fallback_are_detected(self):
        r = CM.parse("帮我把成片验收一下，不合格就退回重渲")
        self.assertTrue(r["accept"])
        self.assertTrue(r["fallback"])

    def test_never_raises_on_empty(self):
        self.assertEqual(CM.parse("")["kind"], "empty")
        self.assertEqual(CM.parse(None)["kind"], "empty")


class TestNote(unittest.TestCase):
    def test_question_gets_no_note(self):
        self.assertEqual(CM.note(CM.parse("你会看屏幕吗")), "")

    def test_missing_object_produces_one_question_hint(self):
        n = CM.note(CM.parse("帮我导出"))
        self.assertIn("他没说", n)
        self.assertIn("只问这一件", n)

    def test_note_is_budgeted(self):
        n = CM.note(CM.parse("帮我把" + "很长的名字" * 20 + "导出成 1080x1920 竖屏"))
        self.assertLessEqual(len(n), 120)


class TestLedger(unittest.TestCase):
    def setUp(self):
        self._old = CM.LEDGER
        self.tmp = tempfile.TemporaryDirectory()
        CM.LEDGER = Path(self.tmp.name) / "commission-log.jsonl"

    def tearDown(self):
        CM.LEDGER = self._old
        self.tmp.cleanup()

    def test_dry_does_not_write(self):
        r = CM.record(CM.parse("帮我导出"), dry=True)
        self.assertFalse(r["recorded"])
        self.assertFalse(CM.LEDGER.exists())

    def test_record_and_stats(self):
        CM.record(CM.parse("帮我把成片验收一下"))
        CM.record(CM.parse("帮我导出"))
        CM.record(CM.parse("你会看屏幕吗"))
        s = CM.stats()
        self.assertEqual(s["total"], 3)
        self.assertEqual(s["kinds"]["task"], 2)
        self.assertEqual(s["kinds"]["question"], 1)
        self.assertEqual(s["missing_pct"], 50.0)
        rows = CM.recent(2)["rows"]
        self.assertEqual(len(rows), 2)

    def test_stats_on_missing_ledger_is_zero_not_error(self):
        s = CM.stats()
        self.assertTrue(s["ok"])
        self.assertEqual(s["total"], 0)


class TestOps(unittest.TestCase):
    def test_schema_has_no_action_surface(self):
        s = CM.schema()
        self.assertIn("parse", s["ops"])
        self.assertIn("没有动作面", s["note"])

    def test_parse_op_needs_text(self):
        self.assertEqual(CM.run("parse")["status"], "needs_input")

    def test_unknown_op_is_failed(self):
        self.assertEqual(CM.run("rm-rf")["status"], "failed")


if __name__ == "__main__":
    unittest.main()
