"""心智引擎回归：功能型人类心智闭环、置信度和隐私边界。"""
from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(os.path.dirname(_HERE))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from gbt_allinone import _paths  # noqa: E402
from gbt_allinone import api, mind_engine  # noqa: E402


class TestMindEngine(unittest.TestCase):
    def setUp(self):
        self._old_store = _paths.STORE_DIR
        self._tmp = tempfile.TemporaryDirectory(prefix="gbt_mind_test_")
        _paths.STORE_DIR = Path(self._tmp.name)
        try:
            mind_engine._state_path().unlink()
        except FileNotFoundError:
            pass

    def tearDown(self):
        _paths.STORE_DIR = self._old_store
        self._tmp.cleanup()

    def test_mental_cycle_exposes_human_like_internal_state(self):
        pulse = mind_engine.observe(
            "pre_work",
            task="修复部署闭环",
            importance=0.78,
            side_effect=True,
            risk=0.44,
            certainty=0.56,
        )
        self.assertTrue(pulse["ok"])
        for key in (
            "appraisal", "needs", "self_model", "owner_model",
            "intention", "metacognition", "reasoning_options",
        ):
            self.assertIn(key, pulse)
        self.assertGreaterEqual(len(pulse["reasoning_options"]), 2)
        self.assertEqual(pulse["mind_loop"][0], "perception")
        self.assertEqual(pulse["mind_loop"][-1], "reflection")

    def test_fatigued_owner_inference_is_confident_and_low_burden(self):
        pulse = mind_engine.observe(
            "user_message",
            text="今天太累了，但还有一个不重要的日志要补",
            importance=0.45,
        )
        owner = pulse["owner_model"]
        self.assertEqual(owner["state"], "fatigued")
        self.assertGreaterEqual(owner["confidence"], 0.5)
        self.assertIn("打扰", owner["current_need"])
        self.assertEqual(pulse["communication"]["posture"], "compress")
        self.assertEqual(pulse["communication"]["action"], "defer")

    def test_mistake_creates_guilt_report_and_reflection(self):
        pulse = mind_engine.observe(
            "mistake",
            task="误删临时目录",
            lesson="删除前先扫描路径并确认",
            guard="先列出目标再执行删除",
            severity="critical",
        )
        self.assertGreater(pulse["emotions"]["guilt"], mind_engine._BASELINE["guilt"])
        self.assertEqual(pulse["communication"]["action"], "speak_now")
        self.assertEqual(pulse["reflection"]["event"], "mistake")
        recalled = mind_engine.recall("删除", limit=5)["lessons"]
        self.assertTrue(recalled)
        self.assertIn("删除前先扫描", recalled[0]["lesson"])

    def test_repeated_lesson_merges_instead_of_duplicates(self):
        first = mind_engine.remember_lesson(
            "同行部署产物", "先校验镜像与生产契约", "用 parity 报告"
        )
        second = mind_engine.remember_lesson(
            "同行部署产物", "先校验镜像与生产契约", "用 parity 报告"
        )
        self.assertFalse(first["duplicate"])
        self.assertTrue(second["duplicate"])
        self.assertEqual(second["lesson"]["occurrences"], 2)

    def test_metacognition_pauses_on_high_risk_low_confidence(self):
        result = mind_engine.metacognition(
            "pre_work",
            task="不可逆迁移",
            importance=0.95,
            side_effect=True,
            risk=0.95,
            controllability=0.18,
            certainty=0.28,
        )
        self.assertTrue(result["should_pause"])
        self.assertEqual(result["mode"], "ask")
        self.assertTrue(result["risks"])
        self.assertTrue(result["checks"])

    def test_reflection_changes_self_model_without_dumping_prompt(self):
        prompt = "秘密项目" + "长内容" * 80
        before = mind_engine.pulse()["self_model"]["confidence"]["competence"]
        mind_engine.observe("user_message", text=prompt, importance=0.8)
        mind_engine.observe(
            "task_succeeded",
            task="完成一个可验证任务",
            importance=0.8,
            side_effect=False,
            certainty=0.9,
        )
        after = mind_engine.pulse()["self_model"]["confidence"]["competence"]
        self.assertGreater(after, before)
        raw = mind_engine._state_path().read_text(encoding="utf-8")
        self.assertNotIn(prompt, raw)
        self.assertNotIn("长内容长内容长内容", raw)
        state = json.loads(raw)
        self.assertIn("reflections", state)
        self.assertTrue(state["reflections"])

    def test_api_mind_pre_work_route(self):
        result = api.run_task("mind", {
            "op": "pre_work",
            "task": "修复图形采集",
            "side_effect": True,
            "risk": 0.62,
            "certainty": 0.5,
        })
        body = result.get("gbt_result", result)
        self.assertEqual(body["status"], "ok")
        payload = body["result"]
        self.assertTrue(payload["ok"])
        self.assertIn("intention", payload)
        self.assertTrue(payload["recalled_lessons"] is not None)


if __name__ == "__main__":
    unittest.main(verbosity=2)
