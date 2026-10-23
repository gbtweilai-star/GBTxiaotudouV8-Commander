# -*- coding: utf-8 -*-
"""触手认知包 · 带牙用例（R-H195）。

① 认知包五件缺一即拒（missing_context）；
② 红线④：三问答不出 ⇒ 拒执行；
③ 红线②：缺参 ⇒ missing_params；缺痕 ⇒ no_trace（**不许默认值填充**）；
④ 红线①：没有读数 ⇒ 不许标"已完成"；
⑤ 红线⑤：能力全息但**只激活相关子集**（没聚焦 / 激活不存在的能力 ⇒ 拒）；
⑥ 拉起触手必须传认知包 + 预期输出，且**深度有上限**；
⑦ 只读：无网络/写盘路径。
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
for p in (ROOT, ROOT / "gbt_allinone"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from gbt_allinone.tools import tentacle_cognition as tc  # noqa: E402

GOOD = dict(task_id="T-1", goal="查场景大类", scene="深夜写代码", boundary="只读",
            capabilities=["scene_anchor", "hook_registry"])
ANSWERS = {"what": "查场景大类", "why_allowed": "认知包已注入", "rollback": "丢弃结果即可"}


class PackTests(unittest.TestCase):
    def test_five_fields_all_required(self):
        bad = tc.inject("T-1", "查场景", "", "只读", ["scene_anchor"])
        self.assertFalse(bad["ok"])
        self.assertEqual(bad["rule"], "missing_context")
        self.assertIn("scene", bad["missing"])
        good = tc.inject(**GOOD)
        self.assertTrue(good["ok"])
        self.assertEqual(sorted(good["pack"]), sorted(tc.PACK_FIELDS + ("actor", "expected_output", "depth")))

    def test_depth_ceiling(self):
        out = tc.inject(task_id="T-2", goal="g", scene="s", boundary="b",
                        capabilities=["x"], depth=tc.DEFAULT_MAX_DEPTH + 1)
        self.assertEqual(out["rule"], "depth_exceeded")


class CockpitTests(unittest.TestCase):
    def test_selfcheck_three_questions(self):
        bad = tc.selfcheck(None, what="做事", why_allowed="", rollback="")
        self.assertFalse(bad["ok"])
        self.assertEqual(bad["rule"], "no_selfcheck")
        self.assertIn("why_allowed", bad["unanswered"])
        self.assertTrue(tc.selfcheck(None, **ANSWERS)["ok"])

    def test_preflight_blocks_guesswork_and_no_trace(self):
        miss = tc.preflight({}, {"op": "classes"}, ["op", "seed"], trace_ref="tr-1",
                            answers=ANSWERS)
        self.assertEqual(miss["rule"], "missing_params")
        self.assertIn("seed", miss["missing"])
        notrace = tc.preflight({}, {"op": "classes"}, ["op"], trace_ref="", answers=ANSWERS)
        self.assertEqual(notrace["rule"], "no_trace")
        ok = tc.preflight({}, {"op": "classes"}, ["op"], trace_ref="tr-1", answers=ANSWERS)
        self.assertTrue(ok["ok"])

    def test_claim_done_needs_readings(self):
        self.assertFalse(tc.claim_done([])["ok"])
        self.assertEqual(tc.claim_done([])["rule"], "no_readings")
        self.assertTrue(tc.claim_done(["classes=8"])["ok"])


class FocusTests(unittest.TestCase):
    def test_holographic_capability_must_be_focused(self):
        caps = ["scene_anchor", "hook_registry", "brand_outro"]
        self.assertEqual(tc.focus(caps, "深夜", [])["rule"], "not_focused")
        self.assertEqual(tc.focus(caps, "深夜", ["不存在的能力"])["rule"], "unknown_capability")
        ok = tc.focus(caps, "深夜", ["scene_anchor"])
        self.assertTrue(ok["ok"])
        self.assertEqual(ok["counts"], {"all": 3, "activated": 1})


class SpawnTests(unittest.TestCase):
    def test_spawn_requires_pack_and_expected_output(self):
        self.assertEqual(tc.spawn("browser", None)["rule"], "missing_context")
        self.assertEqual(tc.spawn("browser", {"task_id": "T-1", "goal": "g"})["rule"],
                         "missing_params")
        self.assertEqual(tc.spawn("browser", {"task_id": "T-1", "goal": "g"},
                                  expected_output="o", depth=9)["rule"], "depth_exceeded")
        self.assertTrue(tc.spawn("browser", {"task_id": "T-1", "goal": "g"},
                                 expected_output="o", depth=1)["ok"])

    def test_module_has_no_network_or_write_paths(self):
        src = Path(tc.__file__).read_text(encoding="utf-8")
        for bad in ("import requests", "import urllib", "import socket", "import subprocess",
                    ".write_text(", ".write_bytes(", "unlink(", "from ..store"):
            self.assertNotIn(bad, src, "只读骨架里不该出现：%s" % bad)


if __name__ == "__main__":
    unittest.main()
