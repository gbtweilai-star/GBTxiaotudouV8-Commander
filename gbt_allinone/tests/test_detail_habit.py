# -*- coding: utf-8 -*-
"""习惯判据：**逐步细节化**（主人令 2026-10-09）——每一步都要答满五问，明细必须逐项。

锁两件事：① `_quintet` 各种形态都答满且「明细」是非空列表；② `tools/codex-scripts/detail-check.py`
真会咬（含负例）。这两条合起来才叫「习惯长牙」——只有正例的判据不算判据。
"""
import importlib.util
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from gbt_allinone.tools.media_run import _quintet  # noqa: E402


def _detail_check():
    spec = importlib.util.spec_from_file_location(
        "gbt_detail_check", ROOT / "tools" / "codex-scripts" / "detail-check.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class StepwiseDetailHabitTest(unittest.TestCase):

    def test_human_step_answers_all_five(self):
        v = {"ok": True, "validator": "drama.parse_timed",
             "criteria": [{"id": "R1", "过": True, "detail": "8 镜三项全中"}]}
        q = _quintet("script", None, "projects/x/01script.md", v, None, "projects/x/01script.md", "")
        for k in ("输入", "动作", "明细", "判据", "接点"):
            self.assertIn(k, q, "五问缺「%s」" % k)
        self.assertIsInstance(q["明细"], list)
        self.assertEqual(q["明细"][0]["id"], "R1")           # 逐条判据就是明细
        self.assertTrue(q["判据"]["过"])

    def test_machine_step_detail_is_per_item_not_a_total(self):
        res = {"shots": [{"no": 1, "dur": 5.0, "shot_size": "特写", "camera": "推近",
                          "emotion": "好奇", "palette": ["a", "b"], "subtitle": "睁眼"},
                         {"no": 2, "dur": 5.0, "shot_size": "中景", "camera": "跟拍",
                          "emotion": "紧张", "palette": ["c", "d"], "subtitle": "爬行"}],
               "ok": True}
        q = _quintet("assets", "ffmpeg.lavfi", None, None, res, "o.mp4", "s.md")
        self.assertEqual(len(q["明细"]), 2, "两镜就应当有两条明细，不是一个合计")
        self.assertEqual(q["明细"][1]["镜"], 2)
        self.assertEqual(q["输入"]["上游"], "s.md")

    def test_dimensions_become_detail_items(self):
        res = {"ok": True, "dimensions": {"color_grade": {"look": "潮湿阴冷"},
                                         "finish": {"grain": 6}, "qc": {"verdict": "不通过"}}}
        q = _quintet("edit", "edit_pipeline.render", None, None, res, "e.mp4", "a.mp4")
        self.assertEqual(len(q["明细"]), 3, "三维就该三条")

    def test_the_checker_actually_bites(self):
        dc = _detail_check()
        good = {"steps": [_quintet("assets", "ffmpeg.lavfi", None, None,
                                   {"shots": [{"no": 1}]}, "o.mp4", "")]}
        self.assertTrue(dc.check(good)["ok"], dc.check(good))
        bad_total = {"steps": [{"step": "assets", "输入": 1, "动作": "x",
                                "明细": 8, "判据": {"过": True}, "接点": "y"}]}
        self.assertFalse(dc.check(bad_total)["ok"], "明细只报合计必须红")
        bad_missing = {"steps": [{"step": "assets", "输入": 1, "动作": "x",
                                  "明细": [1], "判据": {"过": True}}]}
        self.assertFalse(dc.check(bad_missing)["ok"], "缺接点必须红")

    def test_checker_selftest_is_green(self):
        self.assertEqual(_detail_check().selftest(), 0, "判据自检必须全过")


if __name__ == "__main__":
    unittest.main()
